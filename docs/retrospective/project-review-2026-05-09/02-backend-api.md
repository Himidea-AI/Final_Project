# Backend API + Services Code Review
> 날짜: 2026-05-09 | 브랜치: dev
> 범위: backend/src/main.py, backend/src/api/, backend/src/services/, backend/src/config/settings.py, backend/tests/
> 제외: agents/, chains/, simulation/, database/models.py, ingest/, evaluation/

---

## 🚨 한 줄 진단

**5 개 관리자 엔드포인트가 인증 없이 노출 + 비밀번호 변경 시 클라이언트가 권한(role)을 직접 주장 → 즉시 패치 필요.**

## 비전문가용 요약

- **무엇이 문제인가요?** 회원의 계정을 강제 탈퇴시키거나 매니저를 승인·거절하는 API 가 "누가 호출했는지" 검증 없이 동작합니다. 다른 회원의 ID 만 알면 외부 누구라도 호출 가능합니다.
- **얼마나 위험한가요?** URL 만 알면 악용 가능. 보안 사고 시 회사 책임이 커집니다.
- **얼마나 걸리나요?** 6 개 라우터에 `Depends(get_current_user)` 추가 + role 은 JWT 토큰에서만 추출 → 약 1 일 작업.

## 가장 시급한 3 가지 (P0)

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| C-1 | `main.py:2024,2041,2054,2074,2153` | 5 개 `/auth/*` 라우터 인증 없음 | `Depends(get_current_user)` 추가 + 본인 소유 자원 체크 |
| C-2 | `main.py:2098` + `services/auth.py:882` | `PasswordChangeBody.role` 클라이언트 주장 신뢰 | role 은 JWT 클레임에서만 추출 |
| C-3 | `main.py:269` | 매 요청마다 `sa.create_engine()` + async 핸들러 블로킹 | `get_sync_engine()` 싱글톤 사용 |

전체 진단·HIGH·MEDIUM·승인 조건은 아래 본문 참조.

> 용어 미리 안내 (이 문서 전반에서 반복됨)
> - **FastAPI**(파이썬 백엔드 웹 프레임워크): 우리 서버가 HTTP 요청을 받고 응답하는 데 쓰는 도구입니다.
> - **endpoint**(클라이언트가 호출하는 백엔드의 입구. 예: GET /auth/managers): 프런트엔드(브라우저·앱)가 두드리는 "URL + 동작" 한 짝을 가리킵니다.
> - **JWT**(로그인 인증 토큰. 발급된 후 모든 요청에 첨부): 로그인하면 서버가 발급해 주고, 이후 모든 요청에 함께 보내서 "나 아까 그 사람이에요"를 증명하는 도장 같은 것입니다.
> - **Depends(get_current_user)**(FastAPI 가 요청마다 현재 로그인 사용자 정보를 자동 주입하는 의존성 함수): 라우터 함수가 시작될 때 FastAPI 가 알아서 "지금 호출한 사람 정보"를 끼워 넣어 주는 장치입니다. 이게 빠지면 서버는 누가 부른지 모릅니다.
> - **IDOR**(Insecure Direct Object Reference. URL ID 만 바꾸면 남의 자료를 볼 수 있는 취약점): 예를 들어 `/orders/123` 을 `/orders/124` 로만 바꿔도 남의 주문이 보이는 식의 보안 결함입니다.
> - **JWT 클레임**(토큰 안에 들어 있는 사용자 ID·역할 같은 정보 조각): JWT 안에는 이름표처럼 "이 사람의 ID는 X, 역할은 master" 같은 정보가 들어 있고, 이 조각 하나하나를 클레임이라고 부릅니다.
> - **async / 이벤트 루프**(파이썬 비동기 처리 구조. 한 작업이 멈추면 다른 작업까지 멈춤): 한 명의 직원(이벤트 루프)이 여러 손님 주문을 번갈아 처리하는 구조입니다. 한 손님 일에 직원이 막혀 버리면 다른 손님은 줄을 서서 기다려야 합니다.
> - **run_in_threadpool**(동기 함수를 별도 스레드에서 실행해 이벤트 루프 멈춤을 막는 헬퍼): "오래 걸리는 일은 옆 사람한테 시키기" 도우미. 메인 직원(이벤트 루프)이 멈추지 않게 합니다.

---

## 진단 개요

이번 리뷰는 백엔드 API 진입점부터 서비스 레이어, 설정, 테스트까지 백엔드 전반을 살핀 결과를 정리합니다. 가장 큰 흐름은 두 가지입니다. 하나는 **인증·권한 처리가 라우터별로 일관되지 않아 일부 관리자 엔드포인트(endpoint, 클라이언트가 호출하는 백엔드의 입구. 예: GET /auth/managers)가 사실상 공개되어 있다는 점**, 다른 하나는 **동기 DB 호출과 async(파이썬 비동기 처리 구조. 한 작업이 멈추면 다른 작업까지 멈춤) 핸들러가 섞이면서 성능과 안정성에 구조적 부담을 주고 있다는 점**입니다. 그 외에도 에러 처리, 설정 관리, OpenAPI 표면, 미들웨어, 테스트 격리 등 머지 전에 정리하면 좋을 항목들이 적지 않게 발견되었습니다.

라우터 중 일부(simulation_foresee.py, simulation_ai.py, vacancy_evaluation.py 등)는 모범적으로 작성되어 있어 "어떻게 고쳐야 하는가"의 레퍼런스로 삼기 좋습니다. 즉, 이번 이슈들은 "팀 전체가 못 한다"기보다 "표준 패턴이 있는데 main.py 의 일부 구간이 그 패턴을 따라가지 못했다"고 보는 편이 정확합니다.

---

## 1. 인증과 권한 (CRITICAL)

### 왜 중요한가

API 가 "누가 호출했는지", "그 사람이 이 자원을 다룰 권한이 있는지" 두 단계를 모두 검증해야 합니다. 한 단계라도 빠지면 IDOR(Insecure Direct Object Reference. URL ID 만 바꾸면 남의 자료를 볼 수 있는 취약점) 취약점이 됩니다. 쉽게 말해 출입증 검사(누구지?)와 권한 검사(이 방에 들어올 수 있는 사람인가?)를 둘 다 해야 한다는 뜻입니다. 본 프로젝트는 이미 `jwt_auth.py` 에 `get_current_user`(로그인된 사용자 정보를 꺼내 주는 함수), `get_optional_user`(있으면 꺼내고, 없으면 비회원으로 진행하는 함수) 가 잘 정의되어 있는데, main.py 의 일부 관리자 라우터가 이 의존성을 빠뜨린 상태입니다.

### C-1 인증 없는 관리 엔드포인트 5개

`main.py:2024`(GET /auth/managers?owner_id=), `main.py:2041`(PATCH /auth/manager/{id}/approve), `main.py:2054`(PATCH /auth/manager/{id}/reject), `main.py:2074`(POST /auth/user/{user_id}/deactivate), `main.py:2153`(GET /auth/organization/{owner_id}) 다섯 개 엔드포인트는 모두 `Depends(get_current_user)`(FastAPI 가 요청마다 현재 로그인 사용자 정보를 자동 주입하는 의존성 함수) 가 없습니다. 즉, 토큰 없이도 호출 가능하고 URL/쿼리 파라미터만 알면 타 팀장의 매니저 목록을 보거나, 임의의 매니저를 승인·거절하거나, 다른 사용자 계정을 강제 탈퇴시키는 일이 가능합니다.

아래는 현재 코드(`main.py:2024-2031`)입니다. 라우터 함수 정의에 "로그인 사용자 정보를 받아라"는 문구가 빠져 있어서, 누구든 이 URL 만 알면 호출할 수 있습니다.

```python
@app.get("/auth/managers")
async def get_managers(owner_id: str):  # JWT Depends 없음
    result = await run_in_threadpool(auth.get_managers, owner_id)
    return result
```

수정은 단순합니다. 의존성으로 `UserContext`(로그인한 사람의 ID·역할 묶음) 를 주입받고, 본인 소유 자원만 다룰 수 있도록 owner_id 를 토큰에서 끌어쓰면 됩니다.

아래는 고친 모습입니다. `Depends(get_current_user)` 한 줄로 "로그인 안 했으면 못 들어옴"이 자동 적용되고, 역할(role)도 클라이언트가 보낸 값이 아니라 토큰 안에서 직접 꺼냅니다.

```python
@app.get("/auth/managers")
async def get_managers(user: UserContext = Depends(get_current_user)):
    if user.role != 'master':
        raise HTTPException(status_code=403, detail='팀장만 접근 가능')
    result = await run_in_threadpool(auth.get_managers, user.user_id)
    return result
```

다섯 개 엔드포인트 모두 같은 패턴으로 손보면 되고, simulation_foresee.py 가 이미 모범 예시이므로 차분히 옮기면 됩니다.

### C-2 권한 상승: change_password 가 클라이언트 role 을 신뢰

`main.py:2097-2150`, `services/auth.py:880-899` 에서 `PasswordChangeBody`(비밀번호 변경 요청 본문) 가 `role: str` 필드를 받아, 그 값으로 어떤 테이블(`users` vs `manager_users`)을 조회할지 결정합니다.

아래 코드는 "역할(role)을 클라이언트(브라우저)가 직접 적어 보내고, 서버가 그 말을 믿고 테이블을 골라 비밀번호를 바꿔준다"는 뜻입니다. 이건 마치 "내가 사장이라고 적어 보내면 사장 비밀번호 창구로 안내해 주는 것"과 같습니다.

```python
class PasswordChangeBody(BaseModel):
    role: str  # main.py:2098 -- 클라이언트가 master/manager 직접 제출
    old_password: str
    new_password: str

def change_password(self, user_id: str, role: str, ...):
    table = 'users' if role == 'master' else 'manager_users'
    conn.execute(text(f'SELECT password_hash FROM {table} WHERE id = :id'), ...)
```

문제는 role 이 클라이언트가 보내는 값이라는 것입니다. manager 사용자가 role=master 로 위조해 보내면, master 테이블의 비밀번호를 시도할 수 있는 경로가 열립니다. 권한 상승 그 자체이며, 클라이언트가 권한을 결정하는 어떤 모델도 신뢰해선 안 됩니다.

수정은 두 가지입니다. 첫째, `PasswordChangeBody`(pydantic / BaseModel — 요청·응답 데이터 형태를 검증하는 라이브러리에서 만든 요청 데이터 클래스) 에서 `role` 필드를 제거합니다. 둘째, 라우터에서 `Depends(get_current_user)` 로 받은 `user.role` 만 사용합니다. JWT 클레임(토큰 안에 들어 있는 사용자 ID·역할 같은 정보 조각) 은 서버가 발급할 때 직접 박아 넣은 값이라 위조 위험이 없습니다.

### H-6 change_password 라우터 자체의 인증 누락

`main.py:2143` 의 `PUT /auth/user/{user_id}/password` 도 `Depends(get_current_user)` 없이 노출되어 있습니다. URL 의 `user_id` 는 클라이언트가 임의로 바꿀 수 있으므로 C-1 과 같은 IDOR 패턴입니다. 즉 "남의 ID 만 알면 남의 비밀번호를 바꾸는 시도를 할 수 있는" 구조라는 뜻입니다. C-2 와 묶어서 한 번에 수정하는 것이 자연스럽습니다.

### M-7 위조 토큰을 무인증으로 동등 취급

`jwt_auth.py:112-113` 의 `get_optional_user`(토큰이 있으면 사용자 정보 꺼내고, 없으면 None 반환하는 선택 인증 함수) 는 위조 JWT 가 들어와도 `HTTPException`(FastAPI 에서 4xx/5xx 응답으로 변환되는 예외) 을 그냥 잡아 None 으로 반환합니다.

아래 코드는 "예외(에러)가 나면 그냥 무시하고, 토큰이 없는 사람과 똑같이 취급하라"는 뜻입니다.

```python
except HTTPException:
    return None  # 위조 토큰 = 토큰 없음과 동일 취급
```

선택적 인증 구간이라는 의도는 이해되지만, "위조"와 "토큰 없음"을 같게 다루면 공격자가 의도적으로 위조 토큰을 보내도 정상 흐름으로 흡수됩니다. 정책을 명시적으로 결정해야 합니다. 위조면 401(인증 실패) 을 던질지, 진짜로 무인증과 동등 취급할지 코드와 문서에 둘 중 하나로 박아 두는 것이 안전합니다.

---

## 2. DB 접근 안정성과 이벤트 루프

### 왜 중요한가

FastAPI(파이썬 백엔드 웹 프레임워크) 는 async 핸들러 안에서 동기 I/O(읽기/쓰기 작업) 를 직접 호출하면 이벤트 루프(파이썬 비동기 처리 구조. 한 작업이 멈추면 다른 작업까지 멈춤) 전체가 멈춥니다. 한 명의 직원이 모든 손님 주문을 도는데, 한 손님 일이 오래 걸리면 그 동안 다른 손님은 전부 줄을 서야 하는 상황입니다. 이 프로젝트는 SQLAlchemy(파이썬 ORM. SQL 직접 쓰지 않고 객체로 DB 다루는 도구) 동기 엔진을 쓰면서도 일부 구간에서 `run_in_threadpool`(동기 함수를 별도 스레드에서 실행해 이벤트 루프 멈춤을 막는 헬퍼) 없이 호출하거나, 매 요청마다 새 엔진을 만들어 풀이 누수되는 상황입니다.

### C-3 매 요청마다 sa.create_engine() 호출

`main.py:259-278` 의 `_resolve_user_biz_number`(로그인 사용자에게서 사업자번호를 찾아주는 내부 함수) 는 `/simulate` async 핸들러 안쪽에서 직접 호출됩니다.

아래 코드는 "요청이 올 때마다 DB 연결 통로(엔진)를 새로 만든다"는 뜻입니다. 비유하자면 손님이 올 때마다 카페 문을 새로 짓는 격입니다. 더구나 그걸 비동기 흐름 한복판에서 동기적으로(=직원이 그 자리에 멈춰서) 하기 때문에 다른 요청까지 같이 멈춥니다.

```python
def _resolve_user_biz_number(user: UserContext | None) -> str | None:
    engine = sa.create_engine(settings.postgres_url)  # 매 요청마다 새 엔진 생성
    with engine.connect() as conn:  # asyncio 이벤트 루프 블로킹
        row = conn.execute(sa.text('SELECT biz_number FROM users WHERE id = :id')).first()
```

요청마다 `sa.create_engine()`(create_engine / 커넥션 풀 — DB 연결을 모아두는 객체. 매 요청마다 새로 만들면 누수) 이 호출되므로 connection pool(연결 풀, DB 연결을 미리 만들어 두고 재사용하는 묶음) 이 매번 새로 만들어지고, 기존 풀은 GC(가비지 컬렉터, 안 쓰는 메모리를 회수하는 파이썬 내부 기능) 까지 살아 있어 사실상 누수입니다. 게다가 동기 호출이 그대로 async 핸들러 안에서 일어나 이벤트 루프가 막힙니다. 트래픽이 늘면 가장 먼저 무너지는 지점입니다.

수정은 두 단계로 충분합니다. 첫째, 이미 잘 만들어 둔 `database/sync_engine.py` 의 `get_sync_engine(settings.postgres_url)` 싱글톤(앱 전체에서 단 하나만 만들어 공유하는 객체) 을 사용합니다. 둘째, 이 함수를 호출하는 자리는 `await run_in_threadpool(_resolve_user_biz_number, user)` 로 감싸거나, 가능하면 async 드라이버로 바꿉니다.

### M-4 corp_brand_resolver 의 별도 엔진 싱글톤

`services/corp_brand_resolver.py:31-38` 은 `_engine: sa.Engine | None = None` 을 모듈 전역으로 잡아 자체 싱글톤을 운영합니다. 이미 `database/sync_engine.py` 의 `get_sync_engine()` 이 URL 기반으로 풀을 캐싱(한 번 만든 결과를 저장해 두고 재사용)하는데, 별도 싱글톤이 또 있으니 풀 진단이 두 곳으로 갈리고 hot reload(코드 수정 시 서버를 끄지 않고 다시 적용하는 개발 기능) 시 엔진이 중복 생성됩니다. 통일하는 편이 운영이 단순합니다.

### H-3 환경변수 키 직접 접근

`main.py:449`, `main.py:519` 는 `os.environ['POSTGRES_URL']` 로 환경변수(서버 시작 시 OS 에서 읽어오는 설정값) 를 읽습니다. 변수 누락 시 `KeyError`(딕셔너리에서 없는 키를 찾을 때 나는 파이썬 기본 예외) 가 그대로 터지면서 핸들러가 500(서버 내부 오류) 으로 떨어집니다. 프로젝트는 이미 `settings.postgres_url`(설정 객체에서 정돈해 둔 동일 값) 을 가지고 있으므로 그쪽으로 통일하면 됩니다. 굳이 환경변수에서 다시 읽을 필요가 없습니다.

---

## 3. 에러 처리

### 왜 중요한가

예외를 잡고 아무 일도 하지 않으면(silent failure, 조용한 실패), 진짜 장애가 났을 때 로그(서버가 자기 동작 기록을 남기는 텍스트)에 흔적이 남지 않아 원인 추적이 사실상 불가능해집니다. 운영 시 가장 비싼 비용은 "왜 안 되는지 모르는 시간"이고, 이 비용을 키우는 패턴이 코드 곳곳에 있습니다.

### H-1 except Exception: pass

`main.py:1855-1856` 은 브랜드 조회 에러를 완전히 소진합니다.

아래 코드는 "어떤 에러가 나든 그냥 넘기고 아무 기록도 남기지 마라"는 뜻입니다. DB 가 죽었든, 키가 누락됐든, 네트워크가 끊겼든 전부 같은 한 줄로 묻어 버립니다.

```python
        except Exception:
            pass  # 브랜드 조회 에러 완전 소진, 스택 트레이스 없음
        return {'status': 'error', 'message': '기업명을 입력해주세요.'}
```

DB 장애든 키 누락이든 모두 "기업명을 입력해주세요" 메시지로 귀결되니 사용자도 헷갈리고 운영자도 알 수 없습니다. `logger.exception('brand lookup failed')`(logger.exception / logger.warning — 에러를 로그 시스템에 남기는 표준 함수) 한 줄만 추가해도 디버깅 가능성이 크게 올라갑니다.

### H-5 biz_mapper 의 빈 리스트 반환

`services/biz_mapper.py:130-132` 도 같은 패턴입니다.

아래 코드는 "에러가 나면 빈 결과를 돌려준다"는 뜻인데, 사용자 화면에는 "검색 결과 없음"으로 보여서 실패와 진짜 무결과를 구분할 수 없습니다.

```python
except Exception:
    return []  # DB 오류 로그 없이 빈 결과 반환
```

`ftc_brand_franchise`(공정거래위원회 가맹점 데이터 테이블) 조회가 실패해도 빈 결과처럼 보이니, 사용자는 "그런 브랜드가 없다"고 오해합니다. `logger.exception('ftc_brand_franchise 조회 실패')` 추가가 필요합니다.

### H-2 의미 없는 finally: pass 16곳

`services/auth.py` 전반에 `finally: pass`(에러가 나든 안 나든 마지막에 하는 일을 적어 두는 자리에 "아무 것도 하지 마라"고 적어 둔 것) 가 16 곳 흩어져 있습니다.

아래 코드는 그저 자리만 차지하는 빈 finally 블록입니다.

```python
finally:
    pass
```

실행상 의미가 없으므로 그냥 노이즈입니다. 그러나 보는 사람 입장에선 "여기에 정리 코드가 들어갈 자리"처럼 보여 나중에 다른 사람이 잘못된 가정을 깔고 코드를 추가할 위험이 있습니다. 일괄 삭제하는 것이 깔끔합니다.

---

## 4. 설정 관리

### 왜 중요한가

설정값은 운영 환경에서 가장 자주 사고가 나는 지점입니다. 특히 JWT secret(JWT 토큰을 서명할 때 쓰는 비밀 문자열. 이 값이 노출되면 토큰을 위조할 수 있음) 처럼 보안과 직결된 값은 PROD(운영 환경) 에서 default(기본값) 가 들어가 있는 채로 배포되면 그 자체가 사고입니다.

### H-4 PROD 에서 dev secret 검증 부재

`config/settings.py:139` 는 다음과 같습니다.

아래 한 줄은 "환경변수 JWT_SECRET_KEY 가 없으면 'dev-only-not-secret-replace-in-prod' 라는 기본값을 쓴다"는 뜻입니다. 개발할 때는 편리하지만, 운영에서도 이 값이 그대로 쓰이면 토큰 서명 키가 누구나 아는 값이 되어 버립니다.

```python
jwt_secret_key: str = os.getenv('JWT_SECRET_KEY', 'dev-only-not-secret-replace-in-prod')
```

기본값이 잘 만들어져 있는데도, `app_mode == 'PROD'` 일 때 default 가 들어왔다는 사실을 감지해 시작을 거부하는 로직이 없습니다. 즉 운영 배포 시 환경변수 설정이 빠져도 서버가 그대로 뜨고, JWT 서명 키가 누구나 아는 dev 값으로 동작합니다. 다음과 같이 검증을 추가하는 것이 안전합니다.

아래 코드는 "PROD 환경인데 키가 dev 기본값이면 서버 시작 자체를 막는다"는 안전장치입니다.

```python
@model_validator(mode='after')
def check_prod_secrets(self):
    if self.app_mode == 'PROD' and self.jwt_secret_key.startswith('dev-only'):
        raise ValueError('PROD 환경에서 JWT_SECRET_KEY 를 반드시 설정하세요')
    return self
```

`lifespan`(앱 시작·종료 시 한 번 실행되는 FastAPI 의 생명주기 함수) 에서 동등한 검증을 두는 방법도 있지만, settings 파싱 단계에서 잡는 편이 빠르고 실수가 적습니다.

### M-3 BaseSettings + os.getenv() 이중 로드

`config/settings.py` 는 BaseSettings(pydantic / BaseModel — 요청·응답 데이터 형태를 검증하는 라이브러리의 설정 전용 베이스 클래스. 환경변수를 자동으로 읽어 줌) 를 쓰면서도 필드마다 `os.getenv(...)` 로 값을 또 읽습니다.

아래 코드는 "이미 자동으로 환경변수를 읽어 주는 도구를 쓰면서도, 같은 작업을 손으로 한 번 더 하고 있다"는 뜻입니다.

```python
class Settings(BaseSettings):
    anthropic_api_key: str = os.getenv('ANTHROPIC_API_KEY', '')  # 불필요한 이중 로드
    ...
    class Config:  # pydantic-settings v1 스타일, v2 에서 deprecated
        env_file = '.env'
```

BaseSettings 는 필드 기본값과 환경변수를 자동으로 바인딩하므로 `os.getenv()` 는 중복입니다. 또한 `class Config` 는 pydantic-settings v2 에서 deprecated(폐기 예정. 곧 안 쓰게 될 문법) 되어 있어 `model_config = SettingsConfigDict(env_file='.env', ...)` 로 옮기는 것이 권장됩니다. 한 번에 정리하면 설정 코드가 절반으로 줄어듭니다.

---

## 5. API 표면(OpenAPI / 응답 모델)

### M-6 response_model 전무

main.py 의 30 여 개 엔드포인트 중 `sensitivity.py` 를 제외하면 `response_model=`(response_model — API 응답 형태를 명시해 OpenAPI 문서·검증을 자동화) 선언이 없습니다. response_model 이 빠지면 두 가지 문제가 생깁니다. 첫째, OpenAPI(서버가 어떤 API 들을 어떤 형태로 제공하는지 자동 생성되는 문서 스펙) 자동 스펙이 부정확해서 프런트엔드가 응답 형태를 추측해야 합니다. 둘째, 서버 응답에 의도하지 않은 필드가 새어 나가도 차단할 수단이 없습니다(예: 비밀번호 해시, 내부 ID).

당장 30 개를 한 번에 손볼 필요는 없습니다. 보안에 민감한 `/auth/*` 엔드포인트부터 response_model 을 추가하고, 신규 라우터는 처음부터 선언하도록 컨벤션을 정하면 점진적으로 좋아집니다.

### M-1 startup 이벤트가 deprecated

`main.py:188`, `main.py:202` 의 `@app.on_event('startup')`(서버가 켜질 때 한 번 실행되는 함수에 붙이는 옛날 데코레이터) 은 FastAPI 0.93 부터 deprecated 입니다. lifespan context manager(시작과 종료를 한 함수 안에서 함께 다루는 최신 방식) 로 통합하는 편이 미래 지향적이고, 종료 시점 정리(셧다운) 로직도 같은 자리에서 다룰 수 있어 깔끔합니다.

아래 코드는 "서버 시작 시 워밍업(미리 데이터를 캐시에 올려 두는 준비 작업)을 하고, 그 다음에야 서비스를 시작하라"는 패턴을 lifespan 으로 다시 쓴 모습입니다.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    _warmup_customer_revenue()
    _warmup_timeseries_cache()
    yield

app = FastAPI(lifespan=lifespan, ...)
```

### M-2 LangGraph 모듈 레벨 컴파일

`main.py:136`, `main.py:140` 에서 `compile_workflow()`, `compile_slow_graph()`(LangGraph — LLM 에이전트들의 흐름을 그래프 형태로 정의하는 라이브러리에서 그래프를 실행 가능한 형태로 미리 빌드하는 함수) 를 모듈 임포트 시점에 실행합니다. LangGraph 내부에서 import-time 예외(파일을 읽어 들이는 그 순간에 터지는 에러) 가 나면 uvicorn(파이썬 비동기 웹 서버) 시작 자체가 실패하고, 콘솔엔 traceback(에러 추적 텍스트) 만 보일 뿐 어디가 문제인지 파악하기 어렵습니다. lifespan 안으로 옮기고 try/except 로 감싸서 명확한 에러 메시지를 출력하도록 하면 디버깅이 쉬워집니다.

---

## 6. 미들웨어 (Rate Limit)

### M-5 / L-3 fail-open 과 ABM 경로 누락

`main.py:106-107`, `main.py:124-126` 의 rate limit(rate limiter — 짧은 시간 안에 너무 많은 요청을 보내면 차단하는 미들웨어) 미들웨어(요청이 라우터에 닿기 전·후에 공통 처리를 끼워 넣는 계층) 는 두 가지 문제를 함께 가지고 있습니다.

아래 코드의 첫 줄은 "이 두 경로만 보호한다"는 보호 대상 목록이고, 그 아래 except 블록은 "Redis(빠른 메모리 기반 데이터 저장소) 가 죽으면 그냥 통과시킨다"는 뜻입니다.

```python
_RATE_LIMITED_PATHS = {'/simulate', '/analyze'}  # /simulate-abm LLM 경로 누락
...
except Exception as e:
    print(f'[RATE LIMIT] Redis 연결 실패 (통과 허용): {e}')
    return False, 0  # Redis 장애 시 LLM 엔드포인트 무제한 오픈
```

첫째, `/simulate-abm`(에이전트 기반 시뮬레이션 엔드포인트) 이 보호 대상에서 빠져 있습니다. ABM 시뮬레이션은 1 회 호출당 LLM 비용이 `/simulate` 와 동등하거나 그 이상이라 같이 보호받아야 합니다. 둘째, Redis 가 장애 나면 fail-open(장애 시 차단을 풀어 모두 통과시키는 정책. 반대는 fail-closed = 장애 시 모두 막음) 으로 동작해 LLM 엔드포인트가 무제한 열립니다. 외부 공격이 아니더라도 내부 장애 한 번에 비용이 폭발할 수 있습니다.

수정은 두 가지입니다. 보호 경로에 `/simulate-abm` 를 추가하고, Redis 장애 시 전략을 재검토합니다. 비용 민감 엔드포인트는 fail-closed(차단) 가 안전한 기본값이며, 적어도 알람은 띄워야 합니다.

---

## 7. 테스트

### L-1 통합 테스트의 실효성 부족

`backend/tests/integration/test_simulate_flow.py` 는 `assert status_code == 200`(응답 코드가 200(성공)인지만 확인하는 검증문) 만 확인합니다. 응답 body 에 `status: "error"` 가 들어와도 200 이면 통과합니다. 즉 회귀(전엔 잘 되던 게 다시 깨지는 것)를 잡지 못하는 테스트이며, 실제로는 "엔드포인트가 살아 있는가" 정도만 검증합니다.

또 하나 위험은 `backend/tests/integration/conftest.py`(pytest 가 자동으로 읽는 테스트 공통 설정 파일) 가 실제 RDS(.env 의 POSTGRES_URL — 운영용 클라우드 DB) 에 직접 붙는다는 점입니다. CI(코드 변경 시 자동으로 테스트를 돌리는 시스템) 환경에서 네트워크가 막히면 실패하고, 동시 실행 시 데이터 오염 가능성도 있습니다. SQLite 인메모리(메모리에만 잠깐 띄우는 가벼운 DB) 또는 Docker PostgreSQL 픽스처(테스트마다 깨끗한 DB 컨테이너를 띄워 주는 도구)를 도입해 격리하는 것이 표준입니다.

마지막으로 IDOR 시나리오, JWT 위조, 레이트 리미트 우회 같은 보안 케이스 테스트가 전무합니다. 이번 C-1, C-2, C-3 를 고치는 김에 회귀 방지용 단위 테스트를 함께 만들면 같은 사고가 재발하지 않습니다.

### L-2 job_progress_store TTL 이 lazy

`services/job_progress_store.py`(백그라운드 작업의 진행 상태를 메모리에 임시 보관하는 모듈) 는 TTL(Time To Live, 이 데이터가 살아 있을 시간) 정리가 `get_job()`(작업 상태를 조회하는 함수) 호출 시에만 발생합니다. 즉 누가 들여다봐야 그제야 만료된 데이터를 치우는 구조입니다. 실패한 job 이 get 없이 계속 쌓이면 메모리 누수가 됩니다. 주기적 GC 태스크(일정 시간마다 청소를 도는 백그라운드 작업)를 두거나 Redis 로 옮겨 자연스럽게 만료되게 만드는 두 가지 방향이 있습니다.

---

## 주요 강점

문제만 잔뜩 보면 균형이 맞지 않으니, 프로젝트가 잘하고 있는 부분도 정리합니다.

- `simulation_foresee.py`, `simulation_ai.py`, `simulation_abm_history.py` 라우터는 JWT Depends, `raise HTTPException`, status code(HTTP 응답에 함께 가는 200/400/401/403/404/500 같은 숫자 코드) 처리가 모두 깔끔합니다. 이번 C-1 수정의 레퍼런스로 삼기 좋습니다.
- `vacancy_evaluation.py` 는 `@field_validator`(pydantic 의 필드별 입력 검증 데코레이터) 로 입력값 whitelist(허용 가능한 값 목록만 통과시키는 방식) 를 잡고 `logger.exception()` 으로 에러 흔적을 남기는 패턴이 자리 잡혀 있습니다.
- `database/sync_engine.py` 의 URL-keyed 싱글톤 풀은 `pool_size=5`(평소 유지하는 연결 수), `max_overflow=10`(피크 시 잠깐 추가로 허용하는 연결 수), `pre_ping=True`(연결을 쓰기 전에 살아 있는지 확인) 로 합리적으로 구성되어 있습니다. 문제는 이 좋은 도구를 일부 코드가 안 쓰고 있다는 것뿐입니다.
- `jwt_auth.py` 는 role whitelist(허용된 역할 목록만 인정), required vs optional HTTPBearer(인증 토큰을 반드시 요구하는 모드와 선택적으로 받는 모드) 분리가 명확합니다.
- `schemas/simulation_input.py` 는 업종 whitelist, 동 코드 포맷, lat/lon bounding box(위도·경도가 특정 사각 범위 안에 있는지) 검증을 모두 갖추고 있어 입력 단계에서 사고를 차단합니다.
- `services/biz_mapper.py` 는 tenacity retry 3회(파이썬 재시도 라이브러리로 실패 시 자동 3회 재시도), EUC-KR fallback(공공 API 가 한글 인코딩을 다르게 보낼 때 대비한 보조 디코딩) 등 외부 API 의 변덕에 대한 방어가 잘 되어 있습니다.
- `services/corp_brand_resolver.py` 는 REGEXP_REPLACE 를 포함한 parameterized query(SQL 에 값을 직접 합치지 않고 자리표시자(:변수)로 안전하게 넘기는 방식. 합친 문자열로 만들면 f-string(파이썬 문자열 안에 변수를 직접 박는 문법. SQL 에 쓰면 인젝션 위험) 처럼 SQL 인젝션 위험), phase-2 substring dedup(부분 문자열 중복 제거 단계) 으로 SQL injection(악의적인 입력으로 SQL 문장을 조작해 DB 를 털거나 망가뜨리는 공격) 위험과 중복 결과 양쪽을 잡아 두었습니다.

---

## 개선 우선순위 (추천 진행 순서)

1. **C-1 / C-2 / C-3 (P0)**: 보안 + 안정성 핵심. 한 번에 묶어서 1 일 안에 처리. 회귀 테스트 동시 추가.
2. **H-1 / H-5 / H-2 (에러 처리 정리)**: 운영 디버깅 비용을 가장 크게 줄여 줍니다. 0.5 일.
3. **H-3 / H-4 / H-6 (설정·인증 보강)**: 위와 한 PR(Pull Request, 코드 변경을 팀에 제안·리뷰·머지하는 단위) 로 묶어도 무방.
4. **M-1 / M-2 (lifespan 통합)**: deprecated 제거 + 시작 안정성 개선. 0.5 일.
5. **M-3 (settings 정리)**: pydantic-settings v2 전환과 함께. 1 일.
6. **M-4 (corp_brand_resolver 엔진 통합)**: 풀 진단 일원화.
7. **M-5 / L-3 (rate limit)**: ABM 경로 추가 + fail-open 정책 검토.
8. **M-6 (response_model)**: 신규 엔드포인트부터 강제, 기존은 점진 적용.
9. **L-1 (테스트 격리 + 보안 케이스)**: 인프라 작업이라 길게 잡고 진행.
10. **L-2 (job_progress_store)**: 운영 모니터링과 함께 결정.
11. **main.py 분리**: 2963 라인 단일 파일을 `api/auth.py`, `api/mapo.py`, `api/franchise.py` 로 쪼개는 작업. simulation_foresee.py 패턴 참조. 위 항목들이 정리된 후 큰 PR 로 진행하면 충돌이 줄어듭니다.

---

## 승인 조건

C-1 (IDOR 5개), C-2 (클라이언트-role 비밀번호 변경), C-3 (블로킹 엔진 생성) 세 건이 해결되면 머지(개발 브랜치의 변경분을 main 브랜치로 합치는 행위) 승인할 수 있는 상태로 봅니다. HIGH 항목은 같은 PR 또는 후속 PR 어느 쪽이든 무방하지만, 머지 전에 트래킹 이슈(추적용 GitHub 이슈) 로 등록해 두기를 권합니다.
