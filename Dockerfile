ARG BUILD_DATE
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
# Install system deps, Python deps, and Allure CLI (requires Java runtime)
RUN echo "Build date: ${BUILD_DATE}" && apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip openjdk-21-jre-headless \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt \
    && python -m pip install --no-cache-dir uvicorn celery redis allure-pytest \
    && rm -rf /var/lib/apt/lists/* \
    # Install Allure CLI: download latest (pinned fallback) and unpack to /opt/allure
    && mkdir -p /opt/allure /usr/local/bin \
    && ( \
         ALLURE_VERSION="2.22.1"; \
         curl -sSL "https://github.com/allure-framework/allure2/releases/download/${ALLURE_VERSION}/allure-${ALLURE_VERSION}.zip" -o /tmp/allure.zip || \
         (echo "Failed to download pinned Allure ${ALLURE_VERSION}, trying latest" && curl -sSL "https://github.com/allure-framework/allure2/releases/latest/download/allure.zip" -o /tmp/allure.zip) \
       ) \
    && unzip /tmp/allure.zip -d /opt/allure \
    && ln -s /opt/allure/bin/allure /usr/local/bin/allure || true \
    && rm -f /tmp/allure.zip
COPY . /app

# default command is to run uvicorn via docker-compose override
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
