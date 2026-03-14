# Minimal Dockerfile placeholder for the AI UI testing agent
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai-ui-testing-agent .
CMD ["python", "-m", "pipeline.ingestion.doc_loader"]

