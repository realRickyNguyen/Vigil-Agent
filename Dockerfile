# Vigil API: POST /run, GET /runs/<run_id>, GET /health on port 8000.
# Zetaris and Meterless Nightshift run on the host, outside this container. localhost and 127.0.0.1 in the
# settings are rewritten to host.docker.internal at startup (app/config.py), so the same .env works:
#   docker build -t vigil .
#   docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/logs:/app/logs" -v "$(pwd)/state:/app/state" vigil
# Secrets come only from the runtime environment; .env is never copied into the image (.dockerignore).
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Standard library only at runtime; requirements.txt holds pytest, so the image can also run the offline tests.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# logs/ holds each run's trace and dossier, state/ the World Model across runs; mount both to keep them after
# the container stops. The default user stays, so a bind-mounted folder is writable on Linux hosts too.
RUN mkdir -p /app/logs /app/state

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# -u: progress lines reach `docker logs` as they happen (-I ignores PYTHONUNBUFFERED).
CMD ["python", "-I", "-u", "run.py"]
