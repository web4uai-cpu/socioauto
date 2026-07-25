web: uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: celery -A src.orchestrator.tasks.celery_app worker -Q orchestrator -l info
beat: celery -A src.orchestrator.tasks.celery_app beat -l info
