# BioIDE backend. The scientific stack is ~275 MB installed, which is why this
# runs as a container rather than on a serverless platform.
FROM python:3.12-slim

# COBRApy's default LP solver (GLPK via swiglpk) needs a C toolchain to build
# on some platforms; build-essential is removed again in the same layer.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential && apt-get autoremove -y

COPY app ./app

# Projects, provenance and notebook sessions. Mount a volume here to keep them
# across restarts; without one they are lost when the container is replaced.
ENV BIOIDE_DATA_DIR=/data
RUN mkdir -p /data

# Code execution is off by default in a container image, because a hosted
# instance has no single trusted user. Turn it on deliberately.
ENV BIOIDE_ALLOW_CODE_EXEC=0 \
    BIOIDE_ALLOW_LOCAL_INSTALL=0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

# One worker: loaded models and notebook sessions are per-process state.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
