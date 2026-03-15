"""FastAPI backend to accept uploads, start jobs, and query status."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uuid
from pathlib import Path
from .schemas import RunOptions, JobCreateResponse, JobStatus
from .tasks import run_pipeline_task
from .celery_app import celery_app
import json
from fastapi.staticfiles import StaticFiles
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title='Spec2Test API')

# Add CORS middleware BEFORE mounting static files
origins = ["http://localhost:3000"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Serve generated reports/artifacts under /artifacts
_artifacts_dir = Path('reports')
_artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount('/artifacts', StaticFiles(directory=str(_artifacts_dir)), name='artifacts')

# Serve Allure report under /allure
_allure_dir = Path('allure-report')
if _allure_dir.exists():
    app.mount('/allure', StaticFiles(directory=str(_allure_dir)), name='allure')


UPLOAD_DIR = Path('uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post('/api/upload', response_model=JobCreateResponse)
async def upload_and_run(request: Request):
    """Accept a JSON body or a multipart form (if supported) and start a pipeline job.

    JSON body format example:
      { "url": "https://...", "options": { ... } }

    Multipart form (file upload) is supported only if python-multipart is installed; otherwise the endpoint returns a helpful error.
    """
    logger.info('=== UPLOAD ENDPOINT CALLED ===')
    content_type = request.headers.get('content-type', '')
    logger.info(f'Content-Type: {content_type}')
    source = None
    run_opts = RunOptions()

    # If the client sent JSON, prefer that (safe for non-multipart runtimes)
    if 'application/json' in content_type:
        payload = await request.json()
        url = payload.get('url')
        options = payload.get('options')
        if not url and not payload.get('file'):
            raise HTTPException(status_code=400, detail='Either file path or url must be provided in JSON')
        if url:
            source = url
        if options:
            run_opts = RunOptions(**options)

    elif 'multipart/form-data' in content_type:
        # multipart requires python-multipart; attempt to parse form but otherwise return an instructive error
        try:
            form = await request.form()
        except Exception:
            raise HTTPException(status_code=501, detail='Server does not support multipart file uploads (install python-multipart)')

        file = form.get('file')
        url = form.get('url')
        options = form.get('options')
        if not file and not url:
            raise HTTPException(status_code=400, detail='Either file or url must be provided')
        if file:
            # Save file to disk
            dest = UPLOAD_DIR / f"{uuid.uuid4()}_{getattr(file, 'filename', 'upload')}"
            with open(dest, 'wb') as fh:
                # file may be UploadFile or SpooledTemporaryFile-like
                content = await file.read()
                fh.write(content)
            source = str(dest.resolve())
        else:
            source = url
        if options:
            try:
                run_opts = RunOptions(**(json.loads(options) if isinstance(options, str) else options))
            except Exception:
                run_opts = RunOptions()
    else:
        # unsupported content type
        raise HTTPException(status_code=415, detail='Unsupported content type. Send JSON or multipart/form-data')

    # Enqueue Celery task if Celery is available; otherwise run synchronously
    # pydantic v2 uses model_dump; fall back to dict for older versions
    if hasattr(run_opts, 'model_dump'):
        opts_payload = run_opts.model_dump()
    elif hasattr(run_opts, 'dict'):
        # noinspection PyDeprecation
        opts_payload = run_opts.dict()
    else:
        opts_payload = {}

    # If the Celery task object provides .delay, try to use it, but fall back to synchronous execution
    if hasattr(run_pipeline_task, 'delay') and callable(getattr(run_pipeline_task, 'delay')):
        try:
            logger.info(f'Enqueuing Celery task for source: {source}')
            task = run_pipeline_task.delay(source, opts_payload)
            logger.info(f'Task enqueued with Celery ID: {task.id}')
            return JobCreateResponse(job_id=task.id, status='queued')
        except Exception as e:
            # Log the enqueue error and fall back to synchronous execution
            logger.warning('Celery enqueue failed (%s); falling back to synchronous execution', e)

    # Otherwise run synchronously using a dummy self with update_state
    class _DummySelf:
        def update_state(self, state='PROGRESS', meta=None):
            # no-op for synchronous fallback
            return

    try:
        # Call the underlying function implementation to avoid Task.apply_async behavior
        if hasattr(run_pipeline_task, 'run') and callable(getattr(run_pipeline_task, 'run')):
            res = run_pipeline_task.run(_DummySelf(), source, opts_payload)
        else:
            # Fallback: attempt direct call
            res = run_pipeline_task(_DummySelf(), source, opts_payload)
        job_id = res.get('job_id') if isinstance(res, dict) else str(uuid.uuid4())
        return JobCreateResponse(job_id=job_id, status='completed')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Synchronous task execution failed: {e}')


@app.get('/api/status/{job_id}', response_model=JobStatus)
def get_status(job_id: str):
    # Try Celery AsyncResult if available
    try:
        if hasattr(celery_app, 'AsyncResult'):
            async_result = celery_app.AsyncResult(job_id)
            state = getattr(async_result, 'state', 'PENDING')
            info = getattr(async_result, 'info', None) or {}
            logs = info.get('logs') if isinstance(info, dict) else None
            artifact = info.get('report') if isinstance(info, dict) else None
            return JobStatus(job_id=job_id, status=state, logs=logs or [], artifact_url=artifact)
    except Exception:
        pass

    # Fallback: check for a job_result file created by synchronous run
    potential = Path('reports') / f'job_{job_id}' / f'job_result_{job_id}.json'
    if potential.exists():
        try:
            data = json.loads(potential.read_text())
            status = data.get('status', 'COMPLETED')
            logs = data.get('logs', [])
            artifact = data.get('artifacts', {})
            return JobStatus(job_id=job_id, status=status, logs=logs or [], artifact_url=artifact)
        except Exception:
            return JobStatus(job_id=job_id, status='UNKNOWN', logs=[], artifact_url=None)

    return JobStatus(job_id=job_id, status='PENDING', logs=[], artifact_url=None)


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.get('/api/allure-report')
def allure_report_status():
    """Check if Allure report exists"""
    allure_dir = Path('allure-report')
    index_path = allure_dir / 'index.html'
    return {
        'exists': allure_dir.exists(),
        'has_index': index_path.exists(),
        'url': '/allure/index.html' if index_path.exists() else None
    }


@app.get('/api/jobs')
def list_jobs():
    """Return a list of job summaries from reports/job_<id>/job_result_<id>.json"""
    out = []
    base = Path('reports')
    if not base.exists():
        return out
    for jd in sorted(base.glob('job_*'), reverse=True):
        if jd.is_dir():
            # find job_result_*.json
            for f in jd.glob('job_result_*.json'):
                try:
                    data = json.loads(f.read_text())
                    job_id = f.stem.replace('job_result_','')
                    status = data.get('status')
                    artifacts = data.get('artifacts', {})
                    
                    # Extract filename from embeddings file if available
                    filename = 'Untitled'
                    if 'embeddings' in artifacts:
                        try:
                            emb_path = Path(artifacts['embeddings'])
                            if emb_path.exists():
                                emb_data = json.loads(emb_path.read_text())
                                source_path = emb_data.get('source', '')
                                if source_path:
                                    filename = Path(source_path).name
                        except Exception:
                            pass
                    
                    out.append({
                        'job_id': job_id, 
                        'status': status, 
                        'artifacts': artifacts,
                        'filename': filename,
                        'created_at': jd.stat().st_ctime,
                        'has_report': 'allure_report' in artifacts or bool(Path('allure-report').exists())
                    })
                except Exception:
                    continue
    # Already sorted by reverse=True
    return out


@app.get('/api/jobs/{job_id}')
def get_job_details(job_id: str):
    """Get detailed information about a specific job"""
    base = Path('reports')
    job_dir = base / f'job_{job_id}'
    result_file = job_dir / f'job_result_{job_id}.json'
    
    if not result_file.exists():
        raise HTTPException(status_code=404, detail='Job not found')
    
    try:
        data = json.loads(result_file.read_text())
        
        # Extract filename
        filename = 'Untitled'
        artifacts = data.get('artifacts', {})
        if 'embeddings' in artifacts:
            try:
                emb_path = Path(artifacts['embeddings'])
                if emb_path.exists():
                    emb_data = json.loads(emb_path.read_text())
                    source_path = emb_data.get('source', '')
                    if source_path:
                        filename = Path(source_path).name
            except Exception:
                pass
        
        return {
            'job_id': job_id,
            'filename': filename,
            'status': data.get('status'),
            'artifacts': artifacts,
            'logs': data.get('logs', []),
            'error': data.get('error'),
            'warnings': data.get('warnings', [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Error reading job: {str(e)}')


