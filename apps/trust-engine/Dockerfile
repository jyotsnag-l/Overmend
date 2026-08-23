FROM python:3.11-slim

WORKDIR /app

# Copy packages and trust-engine app
COPY packages/ packages/
COPY apps/trust-engine/ apps/trust-engine/

WORKDIR /app/apps/trust-engine

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
