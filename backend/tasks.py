from .celery_app import celery_app
import uuid
import os
from pathlib import Path
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import List

REPORTS_DIR = Path('reports')
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _embed_batch_with_timeout(embedder, batch: List[str], backend: str, model: str, batch_size: int, timeout: int):
    """Call embedder.embed_chunks for a single batch with a timeout enforced via ThreadPoolExecutor.
    Returns embeddings list on success or raises an exception on failure/timeout.
    """
    def _call():
        return embedder.embed_chunks(batch, backend=backend, model=model, batch_size=batch_size)

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_call)
        try:
            return fut.result(timeout=timeout)
        except FutureTimeout:
            fut.cancel()
            raise TimeoutError(f'Embedding batch timed out after {timeout}s')


@celery_app.task(bind=True)
def run_pipeline_task(self, docs_source: str, options: dict):
    """Run the pipeline in-process by calling pipeline modules directly.

    This task now performs embeddings in incremental batches. It reports progress via
    self.update_state(...) so the API can show live percentage progress.

    Options (supported):
      - chunk_size, tokenize, max_tokens, overlap_tokens
      - model (embedding model), batch_size (per-batch), embed_batch_timeout (seconds), embed_retries
      - generate_tests, run_executor, simulate_executor, test_max_steps, planner_model
    """
    job_id = str(uuid.uuid4())
    job_reports_dir = REPORTS_DIR / f'job_{job_id}'
    job_reports_dir.mkdir(parents=True, exist_ok=True)
    logs = []

    def log(msg):
        logs.append(str(msg))
        try:
            self.update_state(state='PROGRESS', meta={'logs': logs[-50:]})
        except Exception:
            pass

    try:
        log(f'Starting job {job_id} for source: {docs_source}')

        # Import pipeline modules
        try:
            import importlib
            doc_loader = importlib.import_module('pipeline.ingestion.doc_loader')
            chunker = importlib.import_module('pipeline.ingestion.chunker')
            embedder = importlib.import_module('pipeline.ingestion.embedder')
            gen_mod = importlib.import_module('pipeline.test_generator.generator_agent')
            exec_mod = importlib.import_module('pipeline.agents.executor.playwright_runner')
            allure_mod = importlib.import_module('pipeline.agents.executor.generate_allure_results')
        except Exception as e:
            log(f'Failed to import pipeline modules: {e}')
            log(traceback.format_exc())
            return {'job_id': job_id, 'status': 'ERROR', 'error': f'Import error: {e}', 'logs': logs}

        # 1) Load documents
        log('Loading documents...')
        docs = doc_loader.load_documents(docs_source)
        if not docs:
            msg = 'No documents found by loader'
            log(msg)
            return {'job_id': job_id, 'status': 'ERROR', 'error': msg, 'logs': logs}

        # choose target (prefer webgoat-like name if present)
        target = None
        for d in docs:
            p = (d.get('path') or '')
            t = (d.get('text') or '').lower()
            if 'webgoat' in p.lower() or 'webgoat' in t:
                target = d
                break
        if not target:
            target = docs[0]
        log(f"Selected document: {target.get('path')}")

        text = target.get('text') or ''
        if not text or text.strip() == '':
            msg = 'Selected document has no usable text'
            log(msg)
            return {'job_id': job_id, 'status': 'ERROR', 'error': msg, 'logs': logs}

        # 2) Chunking
        chunk_size = int(options.get('chunk_size', 500))
        tokenize = bool(options.get('tokenize', False))
        if tokenize:
            log('Chunking by tokens...')
            chunks = chunker.chunk_text_by_tokens(text, max_tokens=int(options.get('max_tokens',200)), overlap_tokens=int(options.get('overlap_tokens',20)), model=options.get('model','text-embedding-3-small'))
        else:
            log('Chunking by characters...')
            chunks = chunker.chunk_text(text, chunk_size=chunk_size)
        total_chunks = len(chunks)
        log(f'Created {total_chunks} chunks')

        # 3) Embeddings (batched, with timeout + retries)
        has_key = bool(os.environ.get('OPENAI_API_KEY'))
        backend = 'openai' if has_key else 'dummy'
        model = options.get('model','text-embedding-3-small')
        batch_size = int(options.get('batch_size',100))
        embed_timeout = int(options.get('embed_batch_timeout',30))
        embed_retries = int(options.get('embed_retries', 2))

        log(f'Embedding backend: {backend} (batch_size={batch_size}, timeout={embed_timeout}s, retries={embed_retries})')

        embeddings = []
        if total_chunks == 0:
            log('No chunks to embed')
        else:
            # iterate batches and embed incrementally
            for idx in range(0, total_chunks, batch_size):
                batch = chunks[idx: idx + batch_size]
                attempt = 0
                batch_emb = None
                while attempt <= embed_retries:
                    attempt += 1
                    try:
                        log(f'Embedding batch {idx + 1}-{idx + len(batch)} (attempt {attempt})')
                        # run embedding with per-batch timeout enforced
                        batch_emb = _embed_batch_with_timeout(embedder, batch, backend, model, len(batch), embed_timeout)
                        if not batch_emb:
                            raise RuntimeError('Empty embedding result')
                        embeddings.extend(batch_emb)
                        break
                    except Exception as e:
                        log(f'Batch embedding error: {e} (attempt {attempt})')
                        if attempt > embed_retries:
                            log('Max retries exceeded for batch; aborting job')
                            return {'job_id': job_id, 'status': 'ERROR', 'error': f'embedding_failed: {e}', 'logs': logs}
                        else:
                            # small backoff
                            import time

                            time.sleep(1 + attempt)
                # update progress after each batch
                done = len(embeddings)
                percent = int(100.0 * done / total_chunks) if total_chunks else 100
                try:
                    self.update_state(state='PROGRESS', meta={'phase': 'embedding', 'progress': percent, 'done': done, 'total': total_chunks, 'logs': logs[-20:]})
                except Exception:
                    pass

        if not embeddings or len(embeddings) != total_chunks:
            msg = 'Embedding count mismatch or embedding failed'
            log(msg)
            return {'job_id': job_id, 'status': 'ERROR', 'error': msg, 'logs': logs}

        log(f'Generated {len(embeddings)} embeddings')
        embeddings_path = job_reports_dir / f'out_embeddings_{job_id}.json'
        embeddings_path.write_text(json.dumps({'source': target.get('path'), 'chunks': chunks, 'embeddings': embeddings}, ensure_ascii=False))
        log(f'Saved embeddings: {embeddings_path}')

        result_payload = {'job_id': job_id, 'status': 'SUCCESS', 'artifacts': { 'embeddings': str(embeddings_path) }, 'logs': logs}

        # 4) Generate test plan (optional)
        gen_res = None
        plan_path = None
        if options.get('generate_tests', True):
            try:
                log('Running LLM test planner...')
                generate_test_plan = getattr(gen_mod, 'generate_test_plan')
                ctx_chunks = chunks[:min(20, len(chunks))]
                context_text = '\n\n'.join(ctx_chunks)
                objective = options.get('test_objective') or f"Generate a test plan to validate the feature described in the docs: {target.get('path')}"
                gen_res = generate_test_plan(context=context_text, objective=objective, max_steps=int(options.get('test_max_steps',20)), model=options.get('planner_model','gpt-3.5-turbo'))
                plan_path = job_reports_dir / f'generated_test_plan_{job_id}.json'
                plan_path.write_text(json.dumps(gen_res, ensure_ascii=False, indent=2))
                log(f'Wrote test plan: {plan_path}')
                result_payload['artifacts']['plan'] = str(plan_path)
            except Exception as e:
                log(f'Test planner failed: {e}')
                log(traceback.format_exc())
                # continue, but mark in payload
                result_payload.setdefault('warnings',[]).append(f'planner_failed: {e}')

        # 5) Run executor (optional)
        executor_report_path = job_reports_dir / f'generated_test_plan_report_{job_id}.json'
        if options.get('run_executor', True):
            try:
                log('Running executor...')
                run_steps = getattr(exec_mod, 'run_steps')
                # Determine steps: prefer gen_res['plan']['steps'] else try to read plan file if present
                steps = None
                if gen_res and isinstance(gen_res, dict) and 'plan' in gen_res:
                    steps = gen_res['plan'].get('steps', [])
                elif plan_path and plan_path.exists():
                    data = json.loads(plan_path.read_text())
                    steps = data.get('plan',{}).get('steps', []) if isinstance(data, dict) else data.get('steps', [])
                else:
                    # fallback: no plan -> skip executor
                    steps = []

                exec_report = run_steps(steps, out_report=str(executor_report_path), headless=True, simulate_only=bool(options.get('simulate_executor', True)))
                log(f'Executor finished, report: {executor_report_path}')
                result_payload['artifacts']['executor_report'] = str(executor_report_path)
            except Exception as e:
                log(f'Executor failed: {e}')
                log(traceback.format_exc())
                result_payload.setdefault('warnings',[]).append(f'executor_failed: {e}')

        # 6) Convert executor report to Allure results
        allure_dir = job_reports_dir / 'allure-results'
        allure_dir.mkdir(parents=True, exist_ok=True)
        try:
            log('Converting executor report to Allure results...')
            if executor_report_path.exists():
                report_json = json.loads(executor_report_path.read_text())
                for s in report_json.get('results', []):
                    try:
                        allure_mod.make_result(s, allure_dir)
                    except Exception:
                        # best-effort per-step
                        log('Allure make_result failed for a step')
                result_payload['artifacts']['allure_results'] = str(allure_dir)
                # Try to generate HTML report if allure CLI present
                try:
                    import subprocess
                    allure_report_dir = job_reports_dir / 'allure-report'
                    subprocess.run(['allure', 'generate', str(allure_dir), '-o', str(allure_report_dir), '--clean'], check=True)
                    result_payload['artifacts']['allure_report'] = str(allure_report_dir)
                    log(f'Allure HTML report generated at {allure_report_dir}')
                except Exception:
                    log('Allure CLI not available or generation failed; results are in allure-results')
            else:
                log('No executor report to convert to Allure')
        except Exception as e:
            log(f'Allure conversion failed: {e}')
            log(traceback.format_exc())
            result_payload.setdefault('warnings',[]).append(f'allure_failed: {e}')

        # Persist final result payload to file
        final_path = job_reports_dir / f'job_result_{job_id}.json'
        final_path.write_text(json.dumps(result_payload, indent=2))
        log(f'Job completed: {final_path}')

        # Return structured result
        return result_payload

    except Exception as e:
        log(f'Unhandled exception: {e}')
        log(traceback.format_exc())
        return {'job_id': job_id, 'status': 'ERROR', 'error': str(e), 'logs': logs}
