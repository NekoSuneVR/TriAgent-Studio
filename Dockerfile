FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/triagent
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN groupadd --gid 10001 triagent && useradd --uid 10001 --gid 10001 --create-home triagent && mkdir -p /data && chown -R triagent:triagent /data /opt/triagent
USER 10001:10001
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/triagent
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
