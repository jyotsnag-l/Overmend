FROM python:3.11-slim

WORKDIR /app

# Copy packages and the api app into the container
COPY packages/ packages/
COPY apps/api/ apps/api/

WORKDIR /app/apps/api

# Install dependencies, including local packages in editable mode
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
