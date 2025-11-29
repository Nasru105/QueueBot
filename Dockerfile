FROM python:3.13-slim

WORKDIR /app

# Ensure Python can find the `app` package placed under /app/app
ENV PYTHONPATH=/app

COPY requirements.txt ./
COPY app/ ./app/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "app.bot"]
