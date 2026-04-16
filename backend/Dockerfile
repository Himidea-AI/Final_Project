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
ENV PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 프로젝트 루트 컨텍스트에서 백엔드 환경 설정 파일 복사
COPY backend/requirements.txt .

# BuildKit 캐시 및 PyTorch CPU 전용 인덱스를 활용하여 컴파일 최적화 및 경량화 설치
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --compile --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

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
ENV PYTHONDONTWRITEBYTECODE=1
# 한글 인코딩 깨짐 방지: Python UTF-8 모드 + 로케일 설정
ENV PYTHONUTF8=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 애플리케이션 소스 코드 및 주요 AI 모듈 복사 (Context: 프로젝트 루트)
COPY backend/ .
COPY models/ ./models
COPY data/ ./data

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
