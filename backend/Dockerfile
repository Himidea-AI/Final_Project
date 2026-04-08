# === 1. Builder Stage ===
FROM python:3.12-slim AS builder

WORKDIR /app

# 빌드 시 필요한 의존성만 설치 (gcc 등)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# 가상 환경 생성 (최종 런타임 이미지에 쉽게 복사하기 위함)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# BuildKit 캐시를 활용하여 자주 재빌드되는 경우 속도 최적화
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# === 2. Runtime Stage ===
FROM python:3.12-slim AS runtime

WORKDIR /app

# 런타임에 필수적인 시스템 라이브러리만 설치 (gcc를 제외하여 최종 이미지 대폭 경량화)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Builder에서 빌드 및 컴파일된 파이썬 가상 환경 복사
COPY --from=builder /opt/venv /opt/venv

# 가상 환경 환경변수 등록 (가상환경의 파이썬/uvicorn을 우선 사용)
ENV PATH="/opt/venv/bin:$PATH"

# 애플리케이션 소스 코드 복사
COPY . .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
