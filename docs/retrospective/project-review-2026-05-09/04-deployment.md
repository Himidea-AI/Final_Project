# 04 - Deployment / DevOps Review
**Date**: 2026-05-09
**Reviewer**: Code Review Agent
**Branch reviewed**: dev

---

## 🚨 한 줄 진단

**프로덕션 빌드가 TypeScript(타입 검사기. 컴파일 시점에 타입 오류를 잡음) 검사 우회 + redis(메모리 캐시 DB. 인증 안 걸린 채 외부 노출되면 즉시 침해 가능) 가 외부 노출 + prod 마이그레이션(데이터베이스 구조를 바꾸는 절차. 컬럼 추가/삭제 등) 명령 누락.**

## 비전문가용 요약

- **무엇이 문제인가요?**
  - 프런트(사용자가 보는 화면 쪽 코드) 프로덕션 빌드(운영 배포용 결과물 생성) 시 "타입 검사 단계"(코드 안에서 변수 종류가 맞는지 확인하는 자동 점검) 를 임시로 끈 핫픽스(급한 불만 끄고 가는 임시 수정)가 그대로 잔존 → 타입 오류가 있어도 배포됨.
  - 캐시 서버(요청 결과를 잠깐 저장해서 재요청을 빠르게 처리하는 서버, 여기서는 Redis)가 인증 없이 인터넷에 그대로 열려 있음.
  - 운영 docker-compose(여러 컨테이너를 한 번에 띄우는 오케스트레이션 도구) 에 "DB 마이그레이션 실행" 명령이 없음 → 스키마(테이블 구조 정의) 변경 배포 시 수동 누락 위험.
- **얼마나 위험한가요?** Redis 노출은 즉시 침해 가능. 빌드 우회는 잠재 버그 누설. 마이그레이션 누락은 다음 스키마 변경 배포 시 500 에러(서버 내부 오류).
- **얼마나 걸리나요?** 3 항목 모두 합쳐 0.5 일.

## 가장 시급한 5 가지 (P0)

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| R-1 | `frontend/Dockerfile:10` | `npx vite build`(Vite 가 프론트 코드를 번들링하는 명령) (tsc(타입 검사기) 우회) | `npm run build` 로 복원 |
| R-2 | `docker-compose.prod.yml` | `alembic upgrade head`(현재 DB 스키마를 최신 마이그레이션까지 적용하는 명령) 누락 | prod backend 서비스 command 에 추가 |
| R-3 | `docker-compose.prod.yml:44` | Redis `6379:6379` 외부 노출 | `ports:` 블록 제거 |
| R-4 | `backend/Dockerfile`(이미지 빌드 절차를 적은 명령 스크립트) | 컨테이너(앱과 그 의존성을 격리한 박스. 가상머신보다 가볍고 빠름) root(시스템에서 모든 권한을 가진 최고 관리자 계정) 실행 | `USER appuser` 추가 |
| R-5 | `.github/workflows/deploy.yml` | 테스트 단계 없이 prod 배포 | pytest(파이썬 테스트 실행기)/vitest(프론트 테스트 실행기) job 선행 |

---

## 1. Docker 빌드 구성: 잘 짜인 뼈대 위의 두 개의 균열

배포 파이프라인(코드를 받아 운영 서버에 올리기까지의 자동 흐름)의 출발점은 Docker(애플리케이션을 컨테이너 단위로 묶어 어디서나 똑같이 실행하게 해주는 도구) 이미지(컨테이너의 설계도. 한 번 만들면 여러 컨테이너로 띄울 수 있음)다. 이번 리뷰에서 확인한 결과 백엔드(서버 쪽 코드)는 비교적 모범적인 패턴을 따르고 있지만, 프런트엔드 쪽은 과거 핫픽스가 남긴 흔적과 보안 기본 원칙 누락이 함께 보였다.

### 1.1 Backend Dockerfile - 토대는 튼튼하다

`backend/Dockerfile`은 builder/runtime 두 단계로 나뉜 multi-stage build(Dockerfile 을 두 단계로 나눠 빌드 도구는 운영 이미지에 포함하지 않게 만드는 패턴)를 채택하고 있고, 이는 운영 이미지에 gcc·g++ 같은 빌드 도구(코드를 실행 파일로 변환할 때 쓰는 컴파일러)가 따라 들어가지 않게 막아 준다. 베이스 이미지(다른 이미지를 만드는 기반이 되는 출발 이미지)로 `python:3.12-slim`을 쓰고, BuildKit(Docker 의 차세대 이미지 빌드 엔진)의 `--mount=type=cache,target=/root/.cache/pip` 옵션으로 pip(파이썬 패키지 설치 도구) 캐시(다운로드한 결과를 잠깐 저장해 재사용하는 영역)를 레이어(이미지 안에서 변경 단위로 쌓이는 한 층) 사이에 재사용하기 때문에 재빌드 속도도 빠르다. PyTorch(딥러닝 프레임워크)는 `--extra-index-url .../whl/cpu`를 명시해 CPU 전용 wheel(미리 빌드된 파이썬 패키지 파일)을 받아 설치하므로 GPU(그래픽 처리 장치) wheel 이 끌고 오는 수백 MB 의존성을 회피했다. 런타임(실행 단계) 단계에는 `libpq5`(PostgreSQL 클라이언트 라이브러리), `gdal-bin`(지리정보 처리 도구) 등 꼭 필요한 시스템 패키지만 추가했고, `PYTHONUTF8=1`, `LANG=C.UTF-8` 환경변수(프로그램에 설정값을 전달하는 외부 변수) 설정으로 한국어 데이터 처리 시 인코딩(문자를 컴퓨터 숫자로 표현하는 규칙) 문제도 예방하고 있다.

다만 두 가지 약점이 명확하다. 첫째, **`USER` 지시어(Dockerfile 안에서 어떤 사용자로 실행할지 지정하는 명령)가 없어 컨테이너가 root 권한으로 동작한다(R-4)**. 이는 컨테이너 탈출(컨테이너 격리를 뚫고 호스트 시스템에 접근하는 공격) 또는 마운트(호스트 디렉토리를 컨테이너 안에서도 보이게 연결하는 것)된 볼륨(컨테이너 외부에 데이터를 영구 저장하는 디스크 공간) 손상 시 피해 범위를 크게 키우는 요소다. 둘째, **Dockerfile 레벨의 `HEALTHCHECK`(컨테이너가 정상 동작 중인지 주기적으로 자동 확인하는 지시어) 지시어가 정의되어 있지 않다**. compose(docker-compose 의 줄임말) 단에서도 backend 헬스체크(/health 같은 엔드포인트로 서비스가 살아있는지 자동 확인)가 빠져 있어, 컨테이너가 살아 있어도 실제 서비스가 동작하는지 알 수 없는 상태다. 참고로 `run_server.py`의 `WindowsSelectorEventLoopPolicy`(Windows 에서 비동기 이벤트 처리를 위한 정책 설정)는 Windows 개발 환경 대응 코드인데, Docker CMD(컨테이너 시작 시 기본으로 실행할 명령)가 `uvicorn src.main:app`(Python 비동기 웹 서버 실행)을 직접 호출하므로 컨테이너 안에서는 실행되지 않아 무해하다.

COPY 전략(이미지 빌드 시 호스트 파일을 이미지 안으로 복사하는 방식)에서는 `COPY backend/`, `COPY models/`, `COPY data/`가 차례로 들어가는데, `data/` 디렉토리가 수백 MB까지 커질 수 있어 이미지 사이즈가 점진적으로 부풀 위험은 모니터링이 필요하다.

### 1.2 Frontend Dockerfile - 핫픽스가 굳어 버린 사례

프런트엔드는 `node:20-alpine`(Node.js 20 버전이 들어간 가벼운 리눅스 이미지)에서 빌드하고 `nginx:alpine`(웹 서버. 정적 파일 서빙 + 백엔드로 요청 프록시)으로 정적 파일(HTML, CSS, JS 처럼 미리 만들어진 변하지 않는 파일)을 서빙하는 표준 multi-stage build 패턴을 따른다. 문제는 `frontend/Dockerfile:10`의 빌드 명령이다. 본래 `package.json`(npm 프로젝트 정보와 의존성 목록을 담은 파일)의 `build` 스크립트는 `tsc && vite build` 조합으로 TypeScript 컴파일러가 타입 검사를 먼저 수행하고 그 후 Vite(최신 프론트 빌드 도구)가 번들링(여러 파일을 하나로 묶는 작업)한다. 그런데 현재는 `npx vite build`만 호출하도록 핫픽스가 들어갔다. 옆에 달린 주석은 "C2 hotfix" 표식만 남아 있고, 본래 의도였던 "임시 우회 후 복원"은 지켜지지 않았다(R-1).

**왜 중요한가**: 타입 에러가 빌드를 차단하지 못하면, `string | undefined`(문자열일 수도 있고 비어 있을 수도 있다는 타입)를 `string`(반드시 문자열)으로 다루다 런타임(실제 사용자가 쓰는 실행 시점)에 화이트 스크린(화면이 통째로 하얗게 뜨는 치명 오류)을 만드는 류의 버그가 그대로 사용자에게 도달한다. CI(지속적 통합. 코드가 들어올 때마다 자동 검사·빌드·테스트하는 구조)에 별도의 `tsc --noEmit`(파일을 만들지 않고 타입만 검사) 단계도 없으므로 타입 안전성은 사실상 사람의 눈에 의존하는 셈이다.

**어떻게 고치나**: `RUN npx vite build`를 `RUN npm run build`로 되돌리고, 빌드가 깨진다면 그 시점부터 발견되는 타입 오류를 정상적으로 제거한 뒤 머지(브랜치 코드를 본 줄기로 합치는 것)한다. 동시에 `frontend/Dockerfile:7`의 `npm install`(노드 패키지 설치)도 `npm ci`(lockfile 엄격 준수 모드 설치)로 바꿔야 한다(R-8). `npm install`은 lockfile(package-lock.json. 정확한 패키지 버전을 박제)과 불일치 시에도 슬그머니 새 버전을 받기 때문에 컨테이너 빌드 사이에 패키지가 달라지는 비결정성(같은 입력에도 결과가 들쭉날쭉한 성질)을 만든다.

이 외에도 nginx:alpine 이미지를 그대로 쓰면 master 프로세스(nginx 의 관리자 프로세스로, 워커들을 띄우고 감독)가 root이고 worker(실제 요청을 처리하는 자식 프로세스)만 nginx 사용자로 떨어지는 구조라서, 보안적으로는 부분적으로만 안전하다. Dockerfile 레벨의 `HEALTHCHECK`도 없다.

---

## 2. Docker Compose: 개발용과 운영용의 격차

`docker-compose.yml`(개발)과 `docker-compose.prod.yml`(운영)을 분리한 점은 좋다. 그러나 운영 compose 에서 누락된 항목이 누적되어 있다.

### 2.1 개발 컴포즈

개발 환경에는 frontend, backend, redis 세 서비스가 정의되어 있다. PostgreSQL(오픈소스 관계형 데이터베이스)은 AWS RDS(아마존이 운영하는 클라우드 DB 서비스)로 이관되었기 때문에 `docker-compose.yml:37-54`에서 의도적으로 주석 처리되어 있다. backend의 `command`에는 `alembic upgrade head && python -m src.database.seed`(테스트 데이터 초기 입력 스크립트)가 선행 실행되도록 적혀 있어, 로컬에서는 자동으로 마이그레이션과 시드(초기 데이터 채우기)가 돈다. `volumes: - ./backend:/app` 마운트로 코드 변경이 즉시 반영되고, 이는 개발 편의 측면에서 정상이다.

다만 두 가지 신경 쓰일 만한 부분이 있다. 첫째, Redis 포트가 `6379:6379`로 호스트(컨테이너를 띄운 실제 PC/서버)에 노출되어 있어 개발자 노트북에서 외부 네트워크에 그대로 노출될 수 있다(R-3). 둘째, `depends_on`(컨테이너 시작 순서를 지정하는 옵션)이 redis만 검사하고 RDS 연결 가능 여부는 다루지 않는다. RDS가 다운되어 있으면 backend가 일단 뜬 뒤 첫 쿼리에서 실패한다.

### 2.2 운영 컴포즈 - 누락된 6가지

운영 compose 는 `restart: always`(컨테이너가 죽으면 자동 재시작), 코드 볼륨 마운트 제거, `app_network`(컨테이너끼리만 통하는 내부 네트워크) 명시, redis_data 볼륨 등 정석적인 항목을 갖췄지만 나머지는 비어 있다. 핵심은 **backend 서비스에 alembic을 실행하는 `command`가 없다(R-2)**. dev compose 에는 있지만 prod compose 에는 누락되었기 때문에, 스키마 변경이 들어간 배포에서 누군가 수동으로 `alembic upgrade head`를 잊으면 즉시 500 에러로 이어진다. `scripts/deploy.sh`에도 alembic 단계는 없다.

또한 운영 서비스 어디에도 **resource limits**(컨테이너가 사용할 수 있는 메모리·CPU 상한)가 정의되어 있지 않다(R-15). ABM(에이전트 기반 모형. 가상의 개체들을 시뮬레이션) 1000 에이전트 시뮬레이션, LightGBM(빠른 트리 기반 머신러닝 라이브러리) 학습/추론, SHAP(머신러닝 예측의 근거를 설명하는 기법) 해석은 모두 메모리를 짧게 폭발시킬 수 있는 작업이고 Lightsail(AWS 의 저가형 VPS 서비스) 4GB 인스턴스에서는 호스트 OOM(Out Of Memory. 메모리 부족으로 시스템이 강제로 프로세스를 죽이는 현상)이 한 번 터지면 모든 컨테이너가 같이 죽는다. backend 헬스체크도 없고(R-16), logging 드라이버(컨테이너 로그를 어디에 어떻게 저장할지 정하는 설정) 설정도 없어 기본 json-file 드라이버가 `max-size`(로그 파일 한 개의 최대 크기) 없이 동작하면서 디스크를 천천히 소모한다(R-22). 마지막으로 `docker-compose.prod.yml:1`에 적힌 `version: "3.8"`은 Docker Compose V2에서 deprecated(공식적으로 더 이상 권장하지 않음)된 키이며 실행 시 경고를 만든다(R-12).

---

## 3. nginx 설정: 좋은 동작과 빈 보안 헤더

`frontend/nginx.conf`는 SPA(Single Page Application. 한 페이지 안에서 라우팅 처리되는 프론트) 라우팅(URL 에 따라 다른 화면을 보여주는 처리)과 시뮬레이션 장기 요청을 다루기 위한 실용적인 설정이 들어 있다.

### 3.1 잘 동작하는 부분

`nginx.conf:28`의 `try_files $uri $uri/ /index.html`(요청한 파일이 없으면 index.html 로 대체하라는 명령)은 React Router(React 에서 클라이언트 사이드 라우팅을 담당하는 라이브러리)가 클라이언트 사이드(사용자 브라우저 쪽)에서 다루는 경로를 정확히 fallback(일치하는 게 없을 때 대체 경로로 보내는 것) 해 준다. `/api/`로 들어오는 트래픽은 백엔드로 리버스 프록시(클라이언트 요청을 받아 내부 서버로 넘겨주는 역할)되며 `nginx.conf:46-48`에 `Upgrade`/`Connection` 헤더가 명시되어 있어 WebSocket(서버-클라이언트 양방향 실시간 통신 프로토콜)이 가능하다. `nginx.conf:41-43`에서 `proxy_read_timeout`, `proxy_send_timeout`, `proxy_connect_timeout`(프록시 연결과 통신 시 최대 대기 시간들)을 모두 300초로 늘려 두었기 때문에 ABM 시뮬레이션 같은 장시간 요청이 게이트웨이(요청을 처음 받는 입구) 단에서 끊기지 않는다. `nginx.conf:18-21`의 gzip(응답을 압축해 전송량을 줄이는 방식) 활성화와 `nginx.conf:35-37`의 `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`(원래 클라이언트 IP·프로토콜 정보를 백엔드로 전달하는 헤더들) 전달도 정상이다.

### 3.2 보안 헤더 공백 (R-7, HIGH)

**왜 중요한가**: server 블록 어디에도 `X-Frame-Options`(다른 사이트에서 iframe 으로 끼워 넣지 못하게 막는 헤더), `X-Content-Type-Options`(브라우저가 파일 종류를 추측하지 않게 막는 헤더), `Content-Security-Policy`, `Referrer-Policy`(어떤 페이지에서 왔는지 정보 노출을 제한)가 없다. 이 보안 헤더(브라우저에 보내는 응답 헤더. 클릭재킹·XSS 등을 자동 방어)들은 브라우저가 자동으로 적용하는 방어선이며, 클릭재킹(투명한 버튼 위에 가짜 화면을 덮어 사용자가 모르게 클릭하게 하는 공격)·MIME sniffing(브라우저가 파일 종류를 잘못 추측해 악성 코드를 실행하게 되는 취약점)·XSS(악성 스크립트를 페이지에 주입해 다른 사용자 브라우저에서 실행시키는 공격) 등 흔한 공격을 비용 없이 차단한다. 헤더만 추가하면 끝나는 일을 미루고 있는 셈이다.

**어떻게 고치나**: server 블록에 `add_header X-Frame-Options "SAMEORIGIN" always;`, `add_header X-Content-Type-Options "nosniff" always;`, `add_header Referrer-Policy "strict-origin-when-cross-origin" always;`, 그리고 가능하면 단순한 CSP(Content-Security-Policy. 어떤 리소스를 로드할 수 있는지 제한하는 헤더) 한 줄을 추가한다.

### 3.3 압축·캐시·HTTPS의 빈자리

`nginx.conf:21`의 `gzip_types`(어떤 종류의 응답을 압축할지 지정)에는 `text/plain`, `text/css`, `application/javascript` 등은 있지만 **`application/json`(JSON 형식 데이터의 MIME 타입)이 빠져 있다(R-10)**. API(서버가 외부에 제공하는 호출 창구) JSON 응답은 압축되지 않고 통째로 전송되며, ABM 결과처럼 큰 페이로드(요청·응답 본문에 들어가는 실제 데이터)가 오갈 때 회선 비용을 키운다. 정적 자산용 `Cache-Control` 헤더(브라우저가 응답을 얼마나 오래 캐시할지 알려주는 헤더)도 부재하다(R-11). Vite 는 빌드 산출물(빌드를 돌려 만들어진 결과 파일)에 hash(파일 내용을 짧은 고유 문자열로 요약한 값)가 박힌 chunk(번들이 자동으로 잘라낸 작은 파일 조각) 파일을 만들기 때문에 `assets/` 경로에 `expires 1y; add_header Cache-Control "public, immutable";`(1년 동안 절대 변하지 않는 파일로 캐시)를 붙이면 안전하게 1년 캐시를 유지할 수 있는데, 현재는 매 요청마다 다시 받아 가는 셈이다.

또한 compose 에서는 443 포트를 매핑하지만 `nginx.conf`에는 SSL 블록(HTTPS 암호화 통신을 위한 인증서·키 설정)이 없다(N-4, HIGH). 결과적으로 443은 죽은 포트(외부에 열려 있지만 실제로는 응답하지 못하는 포트)이고, HTTPS(암호화된 안전한 웹 통신)는 외부 로드 밸런서(트래픽을 여러 서버에 나눠 보내는 장치) 또는 다른 레이어에서 종단(암호 해독을 책임지는 종착점)되어야만 동작한다. `log_format`이 `debug_fmt`라는 이름으로 정의되어 있어 운영 로그 포맷 이름으로는 적절치 않고(N-5), brotli(gzip 보다 더 강력한 새 압축 알고리즘) 미사용은 nginx:alpine이 모듈을 포함하지 않으므로 선택 사항이다(N-6).

---

## 4. CI/CD: 빠르지만 검증이 비어 있다

`.github/workflows/` 디렉토리에는 `deploy.yml`(push: dev 또는 수동 디스패치 시 Lightsail SSH(원격 서버에 안전하게 접속하는 프로토콜) 배포)과 `auto-pr-title.yml`(PR(Pull Request. 코드 변경을 본 줄기에 합쳐달라는 요청) 생성·수정 시 Jira(이슈/티켓 관리 도구) 티켓 ID를 제목에 붙임) 두 GitHub Actions(GitHub 의 CI/CD(지속적 통합 / 지속적 배포. 코드 변경 시 자동으로 테스트·빌드·배포) 자동화 워크플로 시스템) 워크플로우(자동화 작업의 한 묶음 정의)가 있다.

### 4.1 deploy.yml의 잘된 점

`deploy.yml:27-29`의 `concurrency.cancel-in-progress: true`(이전에 돌고 있는 같은 작업을 자동 취소)는 배포 도중 새 push가 들어오면 이전 잡(워크플로우 안의 한 작업 단위)을 자동 취소해 중복 배포 사고를 막는다. `deploy.yml:35`의 `timeout-minutes: 20`(20 분 안에 끝내지 못하면 강제 종료)은 무한 대기 잡을 차단한다. `deploy.yml:49-86`은 변경된 파일이 frontend·backend·infra(인프라. 서버·네트워크 등 시스템 기반) 중 어디에 속하는지 감지해 선택적으로 빌드하므로 디플로이(deploy. 서버에 새 코드를 올리는 작업) 시간을 크게 줄여 준다. `deploy.yml:146-155`의 헬스체크 5회 retry(실패 시 다시 시도) 루프와 `deploy.yml:176-193`의 GitHub Actions Summary(워크플로우 결과를 보기 좋게 요약 페이지로 보여주는 기능) 출력은 운영 가시성(시스템 상태가 얼마나 잘 보이는지)에 도움을 준다. SSH 자격은 `LIGHTSAIL_HOST`, `LIGHTSAIL_USER`, `LIGHTSAIL_SSH_KEY` 등 GitHub Secrets(GitHub 가 안전하게 보관해 주는 비밀값 저장소)로 관리되어 있다.

### 4.2 가장 큰 구멍 - 테스트가 없다 (R-5, HIGH)

**왜 중요한가**: `deploy.yml` 어디에도 `pytest`, `vitest`, 타입 체크, 린트(코드 스타일·실수 자동 검사)가 단계로 들어 있지 않다. 즉 dev 브랜치(독립적으로 작업하는 코드의 줄기)에 push하는 순간 어떤 테스트도 거치지 않은 채 프로덕션이 갱신된다. 대량 리팩터(기능은 그대로 두고 코드 구조만 정리하는 작업) 한 번이면 회귀(기존에 잘 되던 기능이 도로 깨지는 것)가 사용자에게 직접 노출되며, 그동안 누적된 마이그레이션·LangGraph(LLM 워크플로우를 그래프로 구성하는 프레임워크) 노드 변경처럼 영향 범위가 큰 변경에서는 특히 위험하다.

**어떻게 고치나**: 빌드/배포 단계 앞에 `test` job을 두고 backend는 pytest, frontend는 vitest를 실행한다. 헬스체크 retry는 그대로 둔다. 추가로 `paths-ignore`(어떤 경로 변경은 워크플로우 트리거에서 제외)에서 `tests/**`를 제외해 둔 부분(CI-5)도 함께 손봐야 한다. 테스트 변경이 dev에 들어가도 트리거(자동 실행을 시작시키는 신호)되지 않으면 테스트 인프라 자체의 회귀를 잡지 못한다.

### 4.3 그 외 작은 흠

`deploy.yml:113`의 `git reset --hard origin/dev`(현재 디렉토리의 모든 변경을 버리고 원격 dev 와 똑같이 맞추는 강제 명령)는 서버 측 임시 변경을 강제로 날린다. 운영 서버에서 hotfix 하다가 미커밋 상태였다면 그대로 사라진다(CI-1). `deploy.yml:118,122,126,130`에서 사용하는 `docker-compose`는 V1 CLI(명령줄 인터페이스. 터미널에서 치는 명령 도구)이며 Ubuntu Latest(GitHub Actions 가 제공하는 최신 우분투 환경)에서는 지원이 종료될 예정이다(CI-2, R-13). `deploy.yml:139`의 `sleep 20`(20 초 동안 그냥 기다림)은 컨테이너 ready(준비 완료) 여부와 무관하게 고정 대기하므로 빌드 환경 변동에 취약하다(CI-4). `auto-pr-title.yml:11`의 `actions/github-script@v6`는 v7이 최신이라 minor 업그레이드 권장 정도다(R-23). `deploy.yml:92`의 `appleboy/ssh-action@v1`은 SHA(파일 내용 전체를 고유 문자열로 요약한 해시값) 핀닝(특정 버전 고정) 없이 태그만 참조하고 있어 supply chain(코드가 의존하는 외부 패키지·도구의 공급 사슬) 위험이 약간 있다(R-24).

---

## 5. 환경 변수와 시크릿 관리

전반적으로 GitHub Secrets와 `.env`(환경 변수를 모아두는 비공개 설정 파일) 분리가 정착된 편이다. `git check-ignore -v`(파일이 .gitignore 규칙으로 무시되는지 확인하는 명령)로 검증한 결과 `.env`(line 25), `frontend/.env`(line 25 패턴 재귀 적용), `.env.txt`(line 26), `test_api_keys.py`, `marketing/` 모두 정상적으로 무시된다. `.env.example`은 무시 대상이 아니라 예제 파일로 커밋된다.

CI 측 시크릿(`LIGHTSAIL_HOST`, `LIGHTSAIL_USER`, `LIGHTSAIL_SSH_KEY`, `DEPLOY_PATH`)도 모두 GitHub Secrets로 관리된다. 다만 코드 측에 두 가지 기본값 함정이 있다. 첫째, `backend/src/main.py:77`에서 `LANGCHAIN_TRACING_V2`(LLM(대형 언어 모델) 호출 기록을 외부 LangSmith 서비스로 보내는 추적 옵션)가 `"true"`로 기본값을 가진다(R-9). 운영 `.env`에 명시적으로 `false`를 넣지 않으면 모든 LLM 호출이 LangSmith로 전송되며, 이는 비용·프라이버시·규정 준수 측면에서 모두 위험하다. 둘째, `backend/src/main.py:143`의 `CORS_ORIGINS`(브라우저에서 다른 도메인의 API 를 부를 수 있게 허용하는 출처 목록) 기본값에 `http://localhost:3000`이 들어 있어 운영 `.env`에 정확한 도메인이 들어가지 않으면 잘못된 origin(요청을 보낸 출처)이 통과한다.

---

## 6. 빌드 산출물

`.gitignore`(git 이 추적하지 말아야 할 파일 목록)는 `frontend/dist/`(line 71)와 root `dist/`(line 11)를 모두 커버하며 실제 `git ls-files frontend/dist`도 0개로 깨끗하다. Poetry(파이썬 패키지·의존성 관리 도구)나 wheel(미리 빌드된 파이썬 패키지 파일) 패키징은 사용하지 않고 `requirements.txt`(파이썬 의존성을 단순 나열한 파일)로 단순하게 관리하고 있어 부담이 적다. 다만 `pyproject.toml`(파이썬 빌드/의존성 정의를 담는 표준 설정 파일)이 루트와 `backend/`에 각각 존재해 어느 쪽이 진짜 의존성 정의인지 신규 합류자에게 혼동을 줄 수 있다.

Vite 측은 `frontend/vite.config.ts`에서 `manualChunks`(자동 분리 외에 사용자가 직접 chunk 묶음을 지정)로 `react-vendor`, `chart-vendor`, `motion-vendor`, `icons-vendor`를 분리해 캐시 효율을 높였다. `rollup-plugin-visualizer`(번들 구성을 시각화하는 분석 플러그인) 통합으로 `npm run build:analyze` 시 번들 분석이 가능하며, `jspdf`/`html2canvas`/`xlsx` 같은 무거운 모듈은 dynamic import(필요한 시점에만 코드를 비동기로 불러오는 방식) 덕분에 자동 code splitting(번들을 작은 조각들로 잘라 필요한 것만 먼저 로드)된다.

---

## 7. 프로세스 관리: 단일 워커의 함정

운영 CMD는 `backend/Dockerfile:55`의 `uvicorn src.main:app --host 0.0.0.0 --port 8000`이다. **`--workers` 플래그(요청 처리용 프로세스를 몇 개 띄울지 정하는 옵션)가 없어 단일 프로세스만 동작한다(R-25)**. asyncio(파이썬의 비동기 처리 라이브러리) 기반이라 I/O(디스크나 네트워크처럼 외부와의 입출력) 대기 동안에는 다른 요청을 처리할 수 있지만, SHAP 계산이나 LightGBM 추론(학습된 모델로 새 데이터에 예측을 내는 작업)처럼 CPU를 길게 잡는 작업이 들어오면 다른 요청이 모두 블로킹(차단되어 대기)된다. Lightsail 인스턴스(클라우드에서 빌린 가상 서버 한 대)가 2vCPU(가상 CPU 코어)라면 CPU 절반이 노는 셈이다.

**어떻게 고치나**: `gunicorn -k uvicorn.workers.UvicornWorker --workers 2 src.main:app`(파이썬 운영용 WSGI 서버 + 비동기 워커 조합) 또는 `uvicorn --workers 2`로 전환한다. ABM 같은 장시간 작업은 별도의 워커 큐(시간이 오래 걸리는 작업을 줄 세워 백그라운드에서 처리하는 구조)(예: RQ(Redis 기반 파이썬 작업 큐), Celery(파이썬 분산 작업 큐 프레임워크))로 빼는 것이 더 좋지만 단기 개선으로는 워커 2개부터다. `--reload`(코드 변경을 감지해 서버를 자동 재시작)는 운영 CMD에 없고 `run_server.py`의 `reload=True`는 개발 전용이라 운영에 영향 없다.

---

## 8. 헬스체크: 살아 있다고만 답하는 /health

compose 단에서 Redis는 `redis-cli ping`(Redis 가 응답하는지 ping 으로 확인) 헬스체크가 정의되어 있어 `depends_on.condition: service_healthy`(의존하는 서비스가 healthy 가 될 때까지 기다림) 패턴이 정상적으로 동작한다. 그러나 backend·frontend 서비스에는 compose 헬스체크도, Dockerfile의 `HEALTHCHECK`도 없다. CI 단에서는 `curl -sf http://localhost:8000/health`(특정 URL 에 접속해 응답을 확인하는 명령)를 5회 retry하므로 외부에서의 도달성은 검증되지만, 컨테이너 자체의 상태 머신(현재 상태가 starting/healthy/unhealthy 인지 자동 추적하는 구조)은 비어 있다.

게다가 `backend/src/main.py:1336-1339`의 `/health` 엔드포인트(API 가 외부에 노출하는 한 개의 URL 진입점)는 단순 `{"status": "ok"}`만 반환한다(R-16). DB·Redis 연결을 검증하지 않기 때문에 RDS가 죽었거나 Redis가 응답하지 않는 상태에서도 헬스체크는 200(요청이 정상이라는 HTTP 상태 코드)을 반환한다. **로드밸런서가 "정상"으로 보고 트래픽을 흘려보내는데 실제로는 모든 요청이 500으로 끝나는 시나리오**가 가능하다. 최소한 DB ping과 Redis ping을 추가해 deep healthcheck(외부 의존성까지 함께 점검하는 깊은 헬스체크)를 만드는 것이 안전하다.

---

## 9. 자원 한도

dev compose 에는 자원 한도가 없는 것이 정상이지만, prod compose 에도 `mem_limit`, `memswap_limit`, `cpus`, `deploy.resources.limits`(컨테이너에 부여할 메모리·스왑·CPU 상한 옵션들)가 전혀 없다(R-15). ABM 1000 에이전트 시뮬레이션, LightGBM 학습/추론, SHAP 해석은 모두 메모리를 단기간에 크게 잡아먹을 수 있는 작업이다. Lightsail 4GB 인스턴스에서 backend 컨테이너가 한도 없이 메모리를 잡으면 OOM Killer(리눅스 커널이 메모리 부족 시 강제로 프로세스를 골라 죽이는 기능)가 호스트 단에서 작동해 nginx·redis·backend가 동시에 죽는 사고로 이어질 수 있다. 각 서비스에 `deploy.resources.limits.memory: 3g`, `cpus: '1.5'` 같은 명시적 한도를 두는 것이 좋다.

---

## 10. DB 배포: 자동화된 dev, 수동인 prod

PostgreSQL은 AWS RDS로 이관되었고, `docker-compose.yml:37-54`에서 로컬 DB 서비스는 의도적으로 주석 처리되어 있다. 연결 정보는 `.env`의 `POSTGRES_URL`(DB 접속 주소·계정을 한 줄로 묶은 환경 변수)로 주입한다.

가장 큰 위험은 앞서 언급한 **prod 마이그레이션 자동화 부재(R-2)**다. dev compose 의 backend `command`에는 `alembic upgrade head && python -m src.database.seed`가 들어 있는데, prod compose 에는 이 부분이 통째로 빠져 있다. `scripts/deploy.sh`에도 alembic 호출이 없다. 결과적으로 마이그레이션이 들어간 배포마다 누군가 수동으로 SSH 접속해 alembic을 돌려야 하며, 한 번이라도 잊으면 컬럼 미존재로 인한 500 에러가 즉시 발생한다. `command: > sh -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"` 형태로 묶거나, `backend/entrypoint.sh`(컨테이너가 시작할 때 가장 먼저 실행될 스크립트)를 분리해 ENTRYPOINT(컨테이너 시작 시 항상 실행될 메인 명령으로 지정하는 Dockerfile 지시어)로 지정하는 것이 표준적인 해결이다.

`depends_on`은 Redis만 검사하므로 RDS 장애는 앱 기동 후에야 드러난다. Redis 자체는 `redis:7-alpine`으로 버전을 고정했고 prod에는 `redis_data` 볼륨이 있어 RDB(Redis 의 디스크 스냅샷 영속화 방식) 영속성(서버가 꺼졌다 켜져도 데이터가 남는 성질)이 유지된다. AOF(Redis 가 모든 쓰기 명령을 로그처럼 누적 기록하는 영속화 방식)는 활성화되어 있지 않은데, 캐시·세션(사용자 로그인 상태 같은 단기 식별 정보)·잡 상태 용도라면 허용 가능한 선택이다.

---

## 11. 로깅과 관측성

운영 단에서 가장 부족한 영역이다. nginx access log(누가 어떤 URL 에 언제 접근했는지 기록한 로그)는 `/var/log/nginx/access.log`에 기록되지만 컨테이너 내부에 머무르며 외부로 수집되지 않는다. Docker log driver는 prod compose 에 logging 블록이 없으므로 기본 json-file이 사용되는데, `max-size`가 없어 `/var/lib/docker/containers/*/...-json.log`가 무한히 자란다(R-22). 디스크 가용량이 임계점을 넘으면 컨테이너가 더 이상 기동되지 못한다.

LangSmith(LLM 호출을 추적·디버깅·평가해 주는 외부 서비스) 트레이싱(요청 흐름과 호출 단계를 자동 추적·기록)은 앞서 언급했듯 `LANGCHAIN_TRACING_V2` 기본값이 `"true"`라(R-9, `backend/src/main.py:77`), API key가 `.env`에 있으면 모든 LLM 호출이 자동 전송된다. 비용·프라이버시 측면에서 운영에서는 명시적으로 끄는 것이 안전하다.

중앙 로깅(여러 서버의 로그를 한 곳에 모아 보는 시스템)(Sentry(에러 자동 수집·알림 도구), Datadog(클라우드 모니터링/관측성 플랫폼), CloudWatch(AWS 의 로그·메트릭 수집 서비스)), 메트릭(Prometheus(시계열 메트릭 수집·저장 도구)/Grafana(메트릭을 그래프 대시보드로 시각화))은 모두 미설정 상태다. 또한 루트의 `logs/` 디렉토리에는 훈련 로그(`*.log`) 파일이 다수 있는데, `.gitignore`에 `logs/`가 없어 실수 커밋 위험이 상존한다(R-18). 로그 드라이버는 각 서비스에 `logging: { driver: "json-file", options: { max-size: "50m", max-file: "5" } }` 형태로 한도를 두는 것이 즉시 가능한 개선이다.

---

## 12. 보안 자세

### 12.1 컨테이너 사용자

backend는 root로 실행되며 이는 R-4 항목과 직결된다. frontend의 nginx:alpine은 master 프로세스가 root이고 worker가 nginx 사용자로 떨어지는 부분적인 패턴이라 절반쯤 보호된다. backend Dockerfile runtime 단계 끝에 `RUN useradd -r -s /bin/false appuser && chown -R appuser /app`(시스템 사용자 appuser 생성 후 /app 소유자를 변경)과 `USER appuser`를 추가하면 즉시 해결된다.

### 12.2 노출 포트와 Redis

prod compose 에서 80(필요), 443(매핑되었지만 SSL 미설정으로 dead port), 8000(backend FastAPI(파이썬 비동기 웹 프레임워크) 직접 노출), 6379(Redis 직접 노출)가 호스트 인터페이스(서버가 외부 네트워크와 만나는 입구)에 떠 있다. **6379 노출은 가장 시급하다(R-3, `docker-compose.prod.yml:44`)**. Redis는 기본적으로 인증이 없는 상태라 외부에서 접속만 되면 임의 read/write가 가능하다. `requirepass`(Redis 접속 시 비밀번호를 요구하게 하는 설정)를 설정하지 않은 상태에서 인터넷에 노출된 Redis는 과거 다수의 사고 사례를 만든 패턴이다. `ports:` 블록을 제거하고 `app_network`를 통한 컨테이너 간 통신만 사용하도록 바꿔야 한다. 8000 backend 직접 노출도 nginx를 거치게 만들어 attack surface(공격자가 노릴 수 있는 외부 접점의 총합)를 줄이는 것이 좋다.

### 12.3 의존성 CVE

세 개의 패키지가 알려진 위험을 갖고 있다. **`xlsx@^0.18.5`(R-6, `frontend/package.json:31`)**는 CVE(공개된 취약점 식별번호. CVE-2023-30533 같은 형식)-2023-30533 prototype pollution(JS 객체의 prototype 을 오염시켜 전 영역 동작을 바꿀 수 있는 취약점) 영향을 받는다. 0.18.x 전 라인이 영향권이며, 메인테이너(라이브러리를 책임지고 관리하는 사람)가 npm 레지스트리(npm 패키지가 등록·배포되는 공식 저장소)를 떠나 패치 버전이 npm에 올라오지 않은 상태다. `exceljs`로 교체하거나 xlsx 처리를 서버사이드(서버 쪽)로 옮기는 것이 권장된다. **`python-jose>=3.3.0`(R-17, `backend/requirements.txt:9`)**는 CVE-2024-33664 JWT(서버가 발급한 서명된 인증 토큰) 알고리즘 혼동 공격 영향을 받으며, `PyJWT`(JWT 처리에 자주 쓰는 다른 파이썬 라이브러리)로의 교체가 일반적인 권고다. **`PyPDF2>=3.0.0`(R-21)**은 유지보수가 종료되었고 후속인 `pypdf`로의 마이그레이션이 권장된다.

### 12.4 CORS와 CI 보안

CORS(Cross-Origin Resource Sharing. 다른 도메인의 API 를 브라우저에서 부를 수 있게 허용하는 메커니즘)는 `CORS_ORIGINS` env로 제어되고 기본값에 `http://localhost:3000`이 포함된다(`backend/src/main.py:143`). 운영 `.env`에 정확한 도메인을 명시하지 않으면 의도치 않은 origin이 허용될 수 있다. CI 측은 GitHub Secrets를 올바르게 활용하지만 `appleboy/ssh-action@v1`(R-24)이 SHA 핀닝 없이 태그만 참조하고 있어 supply chain 측면의 잠재 위험이 남아 있다.

---

## 13. Git Hooks: 좋은 자동 포맷, 어색한 활성화

`.githooks/` 아래에 `pre-commit`(커밋 직전에 자동으로 실행되는 git 훅)이 있고, 이 훅(특정 git 동작 직전·직후에 자동 실행되는 사용자 스크립트)은 frontend의 TS/TSX/CSS에 Prettier(코드 자동 정렬·포맷팅 도구)를, Python에 Ruff(빠른 파이썬 린터·포매터)를 적용한 뒤 변경 파일을 자동 재스테이징한다. 커밋 메시지에 Jira ID(IM3-NNN)를 자동으로 접두하는 `prepare-commit-msg`(커밋 메시지를 만들기 직전에 실행되는 git 훅)는 `scripts/` 디렉토리에 위치해 있다.

문제는 활성화 방식이 자동이 아니라는 점이다. 신규 합류자가 `git config core.hooksPath .githooks`(.githooks 폴더를 git 훅 경로로 지정하는 설정)를 직접 실행하지 않으면 훅이 동작하지 않는다. README 또는 Makefile(`make` 명령에서 사용할 작업을 정의한 빌드 스크립트)에 onboarding(새로 합류한 사람이 환경을 세팅하는 절차) 단계를 명시하거나, `npm install` 후 자동 실행되는 setup 스크립트로 처리해 주는 것이 표준적이다. 또한 `.githooks/pre-commit:25`에서 `cd frontend` 후 상대경로(현재 위치 기준 경로) `cd ..`를 사용하는데, 비표준 환경(예: `git commit`을 다른 디렉토리에서 실행)에서 실패할 가능성이 있다(R-19). 마지막으로 `prepare-commit-msg`가 `.githooks/`가 아닌 `scripts/`에 위치해 있어 두 훅의 경로가 갈리는 점은 작은 혼동을 만든다.

---

## 14. 스크립트

루트 `scripts/`에는 `deploy.sh`(긴급 수동 배포, CI와 동일 로직, V1 CLI 사용 R-14), `run_tests.sh`(Docker 기반 pytest 실행, V2 CLI 사용 R-20), `prepare-commit-msg`(Jira ID 접두 훅)가 있다. `deploy.sh`와 `run_tests.sh`가 각각 `docker-compose`(V1)와 `docker compose`(V2)로 갈려 있어 운영자 헷갈림이 발생할 수 있다. 어느 한쪽으로 통일이 필요하다.

`backend/scripts/`에는 `init_db.py`, `seed_from_csv.py`, `seed_biz_brand_mapping.py` 등 DB 초기화·시딩 스크립트, `create_test_user.py` 같은 테스트 사용자 생성 도구, `finetune_minilm.py`(MiniLM 임베딩 모델을 우리 데이터에 맞게 재학습)/`gen_triplets.py`(임베딩 학습용 anchor/positive/negative 세 쌍 데이터 생성) 같은 임베딩(텍스트 등을 의미를 담은 숫자 벡터로 변환한 표현) 파인튜닝(범용 모델을 특정 데이터에 맞춰 재학습), 그리고 `eval/`, `verify/`, `diagnostics/` 아래 다수의 평가·검증 스크립트가 있다. 대부분 로컬 실행 전용으로 의도되어 CI에 통합되지 않는다.

---

## 15. 강점 정리

이번 리뷰에서 확인한 잘된 부분들을 정리하면 다음과 같다.

먼저 **multi-stage Docker 빌드와 BuildKit pip 캐시 마운트**(`backend/Dockerfile`)로 이미지 경량화와 빌드 속도를 동시에 잡았다. 환경 분리 측면에서 dev/prod compose 를 명확히 나눴고, prod에서 코드 볼륨 마운트를 제거했다. CI는 `paths` 기반 선택적 빌드로 frontend/backend/infra 변경분만 재빌드해 시간을 절약하고, `concurrency.cancel-in-progress: true`로 중복 배포를 차단한다. pre-commit 훅이 Prettier+Ruff를 자동 적용·재스테이징하는 점, Redis가 `service_healthy` 패턴으로 정확히 의존성 게이트(앞 서비스가 준비될 때까지 막아주는 관문)로 작동하는 점, Vite vendor chunk(라이브러리 코드만 따로 모은 chunk) 분리로 캐시 효율이 좋아진 점, nginx에 gzip+300초 proxy timeout이 들어 있어 시뮬레이션 같은 장기 요청을 견디는 점, `.dockerignore`(이미지에 들어가면 안 될 파일을 지정하는 목록)로 `data/raw/`, `models/weights/`, `notebooks/`를 제외해 이미지가 불필요하게 부풀지 않게 한 점, 그리고 SSH 자격 증명 등을 모두 GitHub Secrets로 관리하는 점이 모두 모범 사례다.

---

## 16. 위험과 기술 부채 요약

CRITICAL(가장 심각한 등급) 등급은 **R-1**(`frontend/Dockerfile:10` TypeScript 검사 우회 핫픽스 잔존)과 **R-2**(`docker-compose.prod.yml`에 `alembic upgrade head` 부재) 두 가지다. 둘 다 다음 배포 한 번이면 즉시 사고로 이어질 수 있는 항목이다.

HIGH 등급은 **R-3**(`docker-compose.prod.yml:44` Redis 6379 호스트 노출), **R-4**(`backend/Dockerfile`에 USER 미지정으로 root 실행), **R-5**(`.github/workflows/deploy.yml`에 테스트 단계 부재), **R-6**(`frontend/package.json:31` xlsx@^0.18.5, CVE-2023-30533), **R-7**(`frontend/nginx.conf` server 블록의 보안 헤더 미설정), **R-8**(`frontend/Dockerfile:7` `npm install` 사용으로 lockfile 비결정성)이 있다.

MEDIUM 등급은 **R-9**(`backend/src/main.py:77` LANGCHAIN_TRACING_V2 기본 true), **R-10**(`frontend/nginx.conf:21` gzip_types에 application/json 누락), **R-11**(정적 자산 Cache-Control 헤더 부재), **R-12**(`docker-compose.prod.yml:1` `version: 3.8` deprecated), **R-13**(`.github/workflows/deploy.yml:118,122,126,130` docker-compose V1 사용), **R-14**(`scripts/deploy.sh:26,28,30` docker-compose V1), **R-15**(prod compose 에 resource limits 부재), **R-16**(`backend/src/main.py:1337-1339` /health가 DB/Redis 미검증), **R-17**(`backend/requirements.txt:9` python-jose, CVE-2024-33664), **R-18**(루트 `logs/` 디렉토리 .gitignore 누락)이 있다.

LOW 등급은 **R-19**(`.githooks/pre-commit:25` 상대경로 cd), **R-20**(`scripts/run_tests.sh` vs `scripts/deploy.sh` V1/V2 불일치), **R-21**(`backend/requirements.txt`의 PyPDF2, 유지보수 종료), **R-22**(prod compose logging 드라이버 미설정), **R-23**(`.github/workflows/auto-pr-title.yml:11` actions/github-script@v6), **R-24**(`.github/workflows/deploy.yml:92` appleboy/ssh-action@v1 SHA 핀닝 없음), **R-25**(`backend/Dockerfile:55` uvicorn 단일 워커)다.

---

## 17. 개선 우선순위

### 즉시 수정 (Blocking)

**[R-1] TypeScript 검사 복구**: `frontend/Dockerfile:9-10`의 `RUN npx vite build`를 `RUN npm run build`로 되돌린다. `package.json`의 `build` 스크립트는 `tsc && vite build`이므로 별도 추가 작업은 필요 없다. C2 핫픽스 주석을 제거하고 `package-lock.json`을 동기화한다.

**[R-2] Prod 마이그레이션 자동화**: `docker-compose.prod.yml`의 backend 서비스에 `command: > sh -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000"` 또는 `backend/entrypoint.sh`를 분리해 ENTRYPOINT로 지정한다.

### 단기 수정 (1주 이내)

**[R-3] Redis 포트 비노출**: `docker-compose.prod.yml`의 redis 서비스에서 `ports:` 블록을 제거하고 `app_network` 내부 통신만 사용하도록 만든다.

**[R-4] Non-root 사용자**: `backend/Dockerfile` runtime 스테이지 끝에 `RUN useradd -r -s /bin/false appuser && chown -R appuser /app`과 `USER appuser`를 추가한다.

**[R-5] CI 테스트 단계 추가**: `.github/workflows/deploy.yml`에 빌드 단계 앞 `test` job을 두고 backend pytest, frontend vitest를 실행하도록 만든다.

**[R-6] xlsx CVE 대응**: `frontend/package.json:31`의 `xlsx@^0.18.5`를 `exceljs`로 교체하거나, xlsx 기능 자체를 서버사이드로 이전한다.

**[R-7] nginx Security Headers 추가**: `frontend/nginx.conf`의 server 블록에 `add_header X-Frame-Options "SAMEORIGIN" always;`, `add_header X-Content-Type-Options "nosniff" always;`, `add_header Referrer-Policy "strict-origin-when-cross-origin" always;`, `add_header X-XSS-Protection "1; mode=block" always;`를 추가한다.

**[R-15] Resource limits 추가**: prod compose 각 서비스에 `deploy.resources.limits.memory: 3g`, `cpus: '1.5'`를 추가한다.

### 중기 개선 (2주 이내)

**[R-9] LangSmith tracing 명시적 제어**: `backend/src/main.py:77`의 기본값 `"true"`를 제거하고, `.env.example`에 `LANGCHAIN_TRACING_V2=false`를 기본으로 명시한다.

**[R-10, R-11] nginx 캐시·압축 개선**: `nginx.conf:21`의 `gzip_types`에 `application/json`을 추가하고, 새로운 `location ~* ^/assets/` 블록을 두어 `expires 1y; add_header Cache-Control "public, immutable";`를 적용한다.

**[R-16] Deep healthcheck 구현**: `/health` 엔드포인트에서 DB ping과 Redis ping을 함께 수행하도록 확장한다.

**[R-13, R-14] docker compose V2 통일**: `deploy.yml`과 `scripts/deploy.sh`의 모든 `docker-compose`를 `docker compose`로 교체한다.

**[R-22] 로그 드라이버 설정**: prod compose 각 서비스에 `logging: { driver: "json-file", options: { max-size: "50m", max-file: "5" } }`를 추가해 디스크 고갈을 막는다.

**[R-18] logs/ gitignore 추가**: `.gitignore`에 `logs/`를 추가해 훈련 로그의 실수 커밋을 차단한다.

**[R-25] uvicorn 워커 수 증가**: `backend/Dockerfile:55`의 CMD에 `--workers 2`를 추가해 Lightsail 2vCPU를 활용한다.

**[R-8] npm ci 전환**: `frontend/Dockerfile:7`을 `RUN npm ci`로 바꾸고, 사전에 `package-lock.json` 동기화를 보장한다.

---

*생성: 2026-05-09 | 검토 범위: Docker, nginx, CI/CD, env, scripts, hooks, security*
