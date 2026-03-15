from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
import uuid
import threading
import subprocess
import shlex
import time

APP_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = APP_DIR / 'docs'
LOGS_DIR = APP_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Spec2Test UI")

# Ensure Allure directories exist so StaticFiles can be mounted even if report isn't generated yet
allure_report_dir = APP_DIR / 'allure-report'
allure_results_dir = APP_DIR / 'allure-results'
allure_report_dir.mkdir(parents=True, exist_ok=True)
allure_results_dir.mkdir(parents=True, exist_ok=True)

# Mount both directories so they can be served later
app.mount('/allure-report', StaticFiles(directory=str(allure_report_dir)), name='allure_report')
app.mount('/allure-results', StaticFiles(directory=str(allure_results_dir)), name='allure_results')

# Simple in-memory job registry
jobs = {}


def _run_pipeline_subprocess(job_id: str, file_path: str, generate_tests: bool, run_executor: bool, simulate_executor: bool):
    """Run the main.py pipeline as a subprocess and stream logs to a file."""
    log_path = LOGS_DIR / f"job_{job_id}.log"
    args = ["python3", str(APP_DIR / 'main.py'), '--docs', str(file_path), '--save', 'out_embeddings.json']
    if generate_tests:
        args += ['--generate-tests', '--tests-out', 'generated_test_plan.json']
    if run_executor:
        args += ['--run-executor', '--executor-out', 'reports/generated_test_plan_report.json']
    if simulate_executor:
        args += ['--simulate-executor']
    # Always attempt to generate Allure results
    args += ['--allure-generate']

    jobs[job_id]['status'] = 'running'
    jobs[job_id]['cmd'] = ' '.join(shlex.quote(x) for x in args)
    with open(log_path, 'wb') as fh:
        proc = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT)
        jobs[job_id]['pid'] = proc.pid
        proc.wait()
        jobs[job_id]['returncode'] = proc.returncode
    jobs[job_id]['status'] = 'finished' if jobs[job_id].get('returncode') == 0 else 'failed'
    jobs[job_id]['finished_at'] = time.time()


@app.post('/open-allure')
def open_allure():
    """Attempt to generate the Allure HTML report from allure-results and return redirect to the report index."""
    # If allure-results exists and allure-report is empty, try to run the CLI
    try:
        ar = allure_results_dir
        rpt = allure_report_dir
        # If results exist and report is empty (no index.html), try to generate
        index_file = rpt / 'index.html'
        if (ar.exists() and any(ar.iterdir())) and (not index_file.exists()):
            try:
                subprocess.run(['allure', 'generate', str(ar), '-o', str(rpt), '--clean'], check=True)
            except Exception as e:
                return JSONResponse({'error': 'allure_generate_failed', 'message': str(e)}, status_code=500)
        # If the index exists, redirect to it
        if index_file.exists():
            return RedirectResponse(url='/allure-report/index.html')
        else:
            return JSONResponse({'message': 'No Allure report available yet. Run a job that generates Allure results.'}, status_code=404)
    except Exception as e:
        return JSONResponse({'error': 'internal', 'message': str(e)}, status_code=500)


@app.get('/', response_class=HTMLResponse)
def index():
    html = """
    <html>
      <head>
        <title>Spec2Test Upload</title>
      </head>
      <body>
        <h1>Spec2Test - Upload document to run pipeline</h1>
        <form action="/upload" enctype="multipart/form-data" method="post">
          <label>Choose file: <input name="file" type="file"/></label><br/><br/>
          <label>Generate tests: <input name="generate_tests" type="checkbox" checked/></label><br/>
          <label>Run executor: <input name="run_executor" type="checkbox"/></label><br/>
          <label>Simulate executor (no browser): <input name="simulate_executor" type="checkbox" checked/></label><br/>
          <button type="submit">Upload & Start</button>
        </form>

        <h2>Jobs</h2>
        <div id="jobs">Loading...</div>

        <h2>Allure Report</h2>
        <p>If an Allure HTML report exists it will be served at <a href="/allure-report">/allure-report</a> (or via the buttons below)</p>
        <button onclick="window.location.href='/allure-report'">Open Allure Report</button>
        <button id="genAllure">Generate & Open Allure</button>

        <script>
          async function loadJobs(){
            const res = await fetch('/jobs');
            const data = await res.json();
            const container = document.getElementById('jobs');
            if(!data || Object.keys(data).length===0){
              container.innerHTML = '<i>No jobs yet</i>';
              return;
            }
            let html = '<ul>';
            for(const [id, j] of Object.entries(data)){
              html += `<li><b>${id}</b> - ${j.status} ${j.cmd?'<br/>'+j.cmd:''} <br/> <a href='/jobs/${id}/logs' target='_blank'>view logs</a></li>`;
            }
            html += '</ul>';
            container.innerHTML = html;
          }
          loadJobs();
          setInterval(loadJobs, 3000);
          document.getElementById('genAllure').addEventListener('click', async function(){
            const resp = await fetch('/open-allure', {method: 'POST'});
            if(resp.status === 200 || resp.status === 307){
              // redirect to the generated report (server issues redirect)
              window.location.href = '/allure-report/index.html';
            } else {
              const j = await resp.json().catch(()=>({}));
              alert('Allure generation failed or no report: ' + (j.message || j.error || JSON.stringify(j)));
            }
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post('/upload')
async def upload(file: UploadFile = File(...), generate_tests: bool = Form(True), run_executor: bool = Form(False), simulate_executor: bool = Form(True), background_tasks: BackgroundTasks = None):
    # Save uploaded file into docs/ and spawn a background job to run the pipeline
    filename = Path(file.filename).name
    dest = DOCS_DIR / filename
    with open(dest, 'wb') as fh:
        content = await file.read()
        fh.write(content)

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {'id': job_id, 'status': 'queued', 'started_at': time.time(), 'cmd': None}

    # start background thread to run pipeline
    t = threading.Thread(target=_run_pipeline_subprocess, args=(job_id, str(dest), bool(generate_tests), bool(run_executor), bool(simulate_executor)), daemon=True)
    t.start()

    return RedirectResponse(url='/', status_code=303)


@app.get('/jobs')
def list_jobs():
    return JSONResponse(content=jobs)


@app.get('/jobs/{job_id}/logs')
def get_logs(job_id: str):
    log_path = LOGS_DIR / f'job_{job_id}.log'
    if not log_path.exists():
        return PlainTextResponse('No logs yet', status_code=404)
    return PlainTextResponse(log_path.read_text(errors='ignore'))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('web.app:app', host='0.0.0.0', port=8000, reload=False)

