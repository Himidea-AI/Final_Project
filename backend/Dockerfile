FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (GeoPandas, psycopg2 등에 필요)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
