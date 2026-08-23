FROM python:3.11-slim

WORKDIR /app

# Copy packages and github-worker app
COPY packages/ packages/
COPY apps/github-worker/ apps/github-worker/

WORKDIR /app/apps/github-worker

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
