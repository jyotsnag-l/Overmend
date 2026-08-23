FROM python:3.11-slim

WORKDIR /app

# Copy packages and sandbox-worker app
COPY packages/ packages/
COPY apps/sandbox-worker/ apps/sandbox-worker/

WORKDIR /app/apps/sandbox-worker

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
