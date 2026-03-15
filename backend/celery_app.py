"""Celery application factory and configuration for background tasks."""
import os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

try:
    from celery import Celery

    celery_app = Celery('spec2test', broker=REDIS_URL, backend=REDIS_URL)
    # Optional: load celery config from environment
    celery_app.conf.update(task_serializer='json', accept_content=['json'], result_serializer='json')
    # Ensure tasks are imported so the worker registers them when started inside Docker
    try:
        # Import the tasks module so @celery_app.task decorated functions are registered
        import importlib
        importlib.import_module('backend.tasks')
    except Exception:
        # best-effort; worker may still start and log missing tasks if import fails
        pass
except Exception:
    # celery is not available - provide a minimal dummy object so imports don't fail during development
    class _DummyCelery:
        def __init__(self):
            self.conf = {}

        def task(self, *args, **kwargs):
            def _decorator(f):
                return f

            return _decorator

        def __getattr__(self, item):
            # fallback for attributes like 'AsyncResult' etc. Return a lambda that raises informative error when used.
            def _missing(*a, **k):
                raise RuntimeError('Celery is not installed in this environment. Install celery to use task features.')

            return _missing

    celery_app = _DummyCelery()


if __name__ == '__main__':
    print('Celery app configured with broker:', REDIS_URL)
