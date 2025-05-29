# Dockerfile
FROM python:3.11-slim

# Install compilers
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    clang \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]