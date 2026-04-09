# 마포구 프랜차이즈 상권분석 시뮬레이터 — 서비스 아키텍처

## 1. 사용자 여정 (User Journey)

```mermaid
graph TD
    subgraph "1단계: 회원가입"
        J1["🧑 사용자 접속"]
        J2["회원가입<br/>- 이름/연락처<br/>- 프랜차이즈 정보 입력"]
        J3["프랜차이즈 선택<br/>(검색 / 드롭박스 / 사업자등록증)"]
        J4["프랜차이즈 매핑 완료<br/>- 브랜드명<br/>- 업종코드<br/>- 본사 정보"]
    end

    subgraph "2단계: 시뮬레이션 설정"
        S1["마포구 지도에서 동 선택<br/>(16개 행정동)"]
        S2["상세 설정<br/>- 기존 가맹점과의 거리<br/>- 예상 보증금/월세<br/>- 예상 인테리어 비용<br/>- 인건비 조정"]
        S3["시뮬레이션 실행 버튼"]
    end

    subgraph "3단계: 분석 결과"
        R1["📊 12개월 매출 예측<br/>(월별 차트 + 신뢰구간)"]
        R2["💰 BEP 손익분기점<br/>(누적 손익 차트)"]
        R3["📉 생존률/폐업률<br/>(월별 생존 곡선)"]
        R4["⚖️ 법률 리스크<br/>(가맹사업법/임대차/위생)"]
        R5["🏪 경쟁 분석<br/>(주변 점포수/폐업률)"]
        R6["👥 상권 분석<br/>(유동인구/주거인구/연령대)"]
    end

    subgraph "4단계: 리포트"
        P1["📄 PDF 리포트 다운로드<br/>(전체 분석 결과 종합)"]
    end

    J1 --> J2 --> J3 --> J4
    J4 --> S1 --> S2 --> S3
    S3 --> R1
    S3 --> R2
    S3 --> R3
    S3 --> R4
    S3 --> R5
    S3 --> R6
    R1 --> P1
    R2 --> P1
    R3 --> P1
    R4 --> P1
    R5 --> P1
    R6 --> P1
```

## 2. 시스템 아키텍처

```mermaid
graph TB
    subgraph "클라이언트"
        BROWSER["🌐 브라우저<br/>React + Tailwind CSS"]
    end

    subgraph "프론트엔드 (C1 강민)"
        FE_AUTH["회원가입/로그인<br/>프랜차이즈 선택 UI"]
        FE_MAP["마포구 지도<br/>행정동 선택"]
        FE_SETTING["시뮬레이션 설정<br/>거리/비용 입력"]
        FE_DASH["결과 대시보드<br/>차트 + 리스크 카드"]
        FE_PDF["PDF 생성/다운로드"]
    end

    subgraph "Nginx"
        NGX["리버스 프록시<br/>:80 → Frontend<br/>/api → Backend:8000"]
    end

    subgraph "백엔드 API (FastAPI)"
        API_AUTH["POST /api/auth/signup<br/>POST /api/auth/login"]
        API_FRAN["GET /api/franchise/search<br/>프랜차이즈 검색/매핑"]
        API_SIM["POST /api/simulate<br/>시뮬레이션 실행"]
        API_PDF["GET /api/report/{id}/pdf<br/>PDF 다운로드"]
    end

    subgraph "LangGraph Agent (B1 예진)"
        SUP["Supervisor<br/>워크플로우 제어"]
        MA["Market Analyst<br/>상권 데이터 수집"]
        CA["Competition Analyst<br/>경쟁 점포 분석"]
        PA["Population Analyst<br/>인구 분석"]
        LA["Legal Analyst<br/>법률 리스크 (RAG)"]
        SYN["Synthesis<br/>종합 리포트 생성"]
    end

    subgraph "딥러닝 모델 (A1 찬영)"
        INTF["ModelOutput.generate()"]
        LSTM["LSTM 매출 예측<br/>(26피처, Attention)"]
        SURV["생존률 예측<br/>(LSTM + Attention)"]
        BEP_CALC["BEP 계산<br/>(공식 기반)"]
    end

    subgraph "B2 시뮬레이션 (수지니)"
        SIM12["12개월 시뮬레이션<br/>(계절성 + 비용)"]
        SHAP["SHAP 분석<br/>(피처 기여도)"]
        SCENARIO["시나리오 비교<br/>(낙관/기본/비관)"]
    end

    subgraph "RAG (A2 봉환)"
        RETRIEVER["LegalDocumentRetriever"]
        PGVEC["pgvector 벡터 검색"]
        LLM["Claude / Gemini<br/>법률 답변 생성"]
    end

    subgraph "데이터 저장소"
        PG["PostgreSQL<br/>24개 테이블 + pgvector"]
        REDIS["Redis<br/>세션 + 캐시"]
    end

    BROWSER --> NGX
    NGX --> FE_AUTH & FE_MAP & FE_SETTING & FE_DASH & FE_PDF
    FE_AUTH --> API_AUTH
    FE_MAP --> API_SIM
    FE_SETTING --> API_SIM
    FE_PDF --> API_PDF

    API_FRAN --> PG
    API_SIM --> SUP
    SUP --> MA & CA & PA & LA
    MA --> INTF
    CA --> PG
    PA --> PG
    LA --> RETRIEVER --> PGVEC --> PG
    PGVEC --> LLM

    INTF --> LSTM & SURV & BEP_CALC
    LSTM --> PG
    SURV --> PG

    INTF --> SIM12
    SIM12 --> SHAP & SCENARIO

    MA & CA & PA & LA --> SYN
    SIM12 --> SYN
    SYN --> API_SIM
    SYN --> API_PDF

    API_AUTH --> REDIS
    API_SIM --> REDIS
```

## 3. 회원가입 + 프랜차이즈 매핑 상세

```mermaid
sequenceDiagram
    participant U as 사용자
    participant FE as 프론트엔드
    participant API as 백엔드 API
    participant DB as PostgreSQL
    participant FTC as 공정위 API

    U->>FE: 회원가입 클릭
    FE->>U: 가입 폼 표시<br/>(이름, 연락처, 이메일)

    U->>FE: 프랜차이즈 입력
    Note over FE: 입력 방식 (택 1)<br/>① 검색: "BBQ" 입력<br/>② 드롭박스: 업종→브랜드 선택<br/>③ 사업자등록증: OCR 스캔

    FE->>API: GET /api/franchise/search?q=BBQ
    API->>DB: store_info 검색
    API->>FTC: 공정위 정보공개서 조회
    FTC-->>API: 브랜드 정보 (매출, 가맹점수, 폐점률)
    API-->>FE: 매칭 결과 리스트

    U->>FE: 브랜드 선택 확인
    FE->>API: POST /api/auth/signup
    API->>DB: 사용자 + 프랜차이즈 정보 저장
    API-->>FE: 가입 완료 + JWT 토큰
    FE-->>U: 메인 페이지로 이동
```

## 4. 시뮬레이션 실행 상세

```mermaid
sequenceDiagram
    participant U as 사용자
    participant FE as 프론트엔드
    participant API as 백엔드 API
    participant SUP as Supervisor
    participant MA as Market Analyst
    participant LA as Legal Analyst
    participant DL as 딥러닝 모델
    participant B2 as 시뮬레이션
    participant DB as PostgreSQL

    U->>FE: 합정동 선택 + 설정 입력
    Note over FE: - 기존 가맹점 거리: 500m 이내 3개<br/>- 보증금: 5000만<br/>- 월세: 200만<br/>- 인테리어: 4000만

    FE->>API: POST /api/simulate
    API->>SUP: 워크플로우 시작

    SUP->>MA: 상권 분석 요청
    MA->>DB: 합정동 매출/점포/유동인구 조회
    MA->>DL: ModelOutput.generate(합정동, 커피)
    DL->>DB: LSTM 입력 데이터 로드
    DL-->>MA: 매출 예측 + 생존률 + BEP

    MA->>B2: 12개월 시뮬레이션 요청
    B2-->>MA: 월별 시나리오 + SHAP 분석

    MA-->>SUP: 상권 분석 완료

    SUP->>LA: 법률 검토 요청
    LA->>DB: pgvector 법률 문서 검색
    LA-->>SUP: 법률 리스크 (6개 항목)

    SUP->>SUP: 종합 리포트 생성
    SUP-->>API: 최종 결과

    API->>DB: simulation_result 저장
    API-->>FE: 결과 JSON

    FE-->>U: 대시보드 표시
    Note over U: 매출 차트 + BEP + 생존률<br/>+ 법률 리스크 + 경쟁 분석

    U->>FE: PDF 다운로드 클릭
    FE->>API: GET /api/report/{id}/pdf
    API-->>FE: PDF 파일
    FE-->>U: 다운로드 완료
```

## 5. PDF 리포트 구조

```mermaid
graph TD
    subgraph "PDF 리포트"
        P0["📄 표지<br/>마포구 프랜차이즈 상권분석 리포트<br/>합정동 × 커피-음료<br/>생성일: 2026-04-09"]

        P1["1. 입지 요약<br/>- 선택 행정동: 합정동<br/>- 업종: 커피-음료<br/>- 브랜드: OO커피<br/>- 기존 가맹점: 500m 이내 3개"]

        P2["2. 매출 예측<br/>📊 12개월 월별 매출 차트<br/>- 월평균: 4,720만원<br/>- 연매출: 5.66억원<br/>- 신뢰구간: ±10%"]

        P3["3. 손익분기점(BEP)<br/>💰 누적 손익 차트<br/>- BEP: 18개월<br/>- 초기투자: 1.3억원<br/>- 월순이익: 280만원<br/>- ROI: 25.8%"]

        P4["4. 생존률 분석<br/>📉 12개월 생존 곡선<br/>- 1년 생존률: 72%<br/>- 리스크: safe<br/>- 동일 업종 평균 폐업률: 12%"]

        P5["5. 경쟁 환경<br/>🏪 주변 점포 현황<br/>- 동일 업종: 40개<br/>- 프랜차이즈: 25개<br/>- 최근 개업: 5개/분기<br/>- 최근 폐업: 3개/분기"]

        P6["6. 상권 분석<br/>👥 인구/트렌드<br/>- 유동인구: 32,000명/일<br/>- 주거인구: 33,150명<br/>- 2030 비율: 45%<br/>- 네이버 트렌드: 하락(-42%)"]

        P7["7. 법률 리스크<br/>⚖️ 항목별 판정<br/>- 가맹사업법: ⚠️ 주의<br/>- 상가임대차: ✅ 안전<br/>- 식품위생: ⚠️ 주의<br/>- 용도지역: ✅ 안전<br/>- 다중이용업소: ✅ 안전<br/>- 공정위 정보공개서: ✅ 안전"]

        P8["8. SHAP 분석<br/>🔍 매출 기여 요인<br/>- 유동인구: +1,800만<br/>- 주거인구: +900만<br/>- 경쟁점포: -600만<br/>- 임대료: -400만<br/>- 트렌드: -200만"]

        P9["9. 종합 의견<br/>AI Agent 종합 판정<br/>- 추천도: ★★★★☆<br/>- 핵심 리스크: 경쟁 과열<br/>- 권고사항: ..."]
    end

    P0 --> P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7 --> P8 --> P9
```

## 6. 기술 스택

```mermaid
graph LR
    subgraph "프론트엔드"
        REACT["React 18"]
        TS["TypeScript"]
        TAIL["Tailwind CSS"]
        VITE["Vite"]
        CHART["Chart.js / Recharts"]
        PDF_LIB["jsPDF / react-pdf"]
    end

    subgraph "백엔드"
        FAST["FastAPI"]
        PYDANTIC["Pydantic v2"]
        SA["SQLAlchemy"]
        LC["LangChain"]
        LG["LangGraph"]
        ANTHRO["Anthropic SDK"]
    end

    subgraph "AI/ML"
        TORCH["PyTorch"]
        SK["scikit-learn"]
        SHAP_LIB["SHAP"]
        HF["HuggingFace<br/>(임베딩)"]
    end

    subgraph "인프라"
        DOCKER["Docker Compose"]
        NGINX["Nginx"]
        PG_DB["PostgreSQL 16<br/>+ pgvector"]
        REDIS_DB["Redis 7"]
    end

    REACT --- TS --- TAIL --- VITE
    FAST --- PYDANTIC --- SA
    LC --- LG --- ANTHRO
    TORCH --- SK --- SHAP_LIB --- HF
    DOCKER --- NGINX --- PG_DB --- REDIS_DB
```

## 7. API 엔드포인트

| Method | Path | 설명 | 담당 |
|--------|------|------|------|
| POST | `/api/auth/signup` | 회원가입 (프랜차이즈 정보 포함) | C1+C2 |
| POST | `/api/auth/login` | 로그인 | C1+C2 |
| GET | `/api/franchise/search` | 프랜차이즈 검색 | B1 |
| GET | `/api/franchise/{id}` | 프랜차이즈 상세 (공정위 정보공개서) | A2 |
| POST | `/api/simulate` | 시뮬레이션 실행 | B1 |
| GET | `/api/simulate/{id}` | 시뮬레이션 결과 조회 | B1 |
| GET | `/api/report/{id}/pdf` | PDF 리포트 다운로드 | B2+C1 |
| GET | `/api/districts` | 마포구 16개 동 목록 | A1 |
| GET | `/api/districts/{code}/stats` | 동별 통계 (매출/인구/점포) | A1 |
