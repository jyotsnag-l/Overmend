FROM python:3.11-slim

WORKDIR /app

# Copy packages and recovery-worker app
COPY packages/ packages/
COPY apps/recovery-worker/ apps/recovery-worker/

WORKDIR /app/apps/recovery-worker

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
