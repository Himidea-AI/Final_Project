# 로그인/인증 백엔드 구현 핵심 정리

작성 기준: 2026-04-29

## 1. 핵심 정의

로그인 기능은 **FastAPI 엔드포인트가 요청을 받고, `AuthService`가 DB에서 사용자와 비밀번호를 검증한 뒤, 성공 시 JWT `access_token`을 발급하는 구조**이다.

```text
Frontend
  -> /auth/login
  -> AuthService.login()
  -> users 테이블 조회
  -> bcrypt 비밀번호 검증
  -> JWT access_token 발급
  -> Frontend 저장 및 사용
```

## 2. 관련 핵심 파일

| 파일 | 역할 |
|---|---|
| `backend/src/main.py` | 인증 API 엔드포인트 정의 |
| `backend/src/services/auth.py` | 회원가입, 로그인, 초대코드, 매니저 승인 로직 |
| `backend/src/services/jwt_auth.py` | JWT 발급/검증 및 FastAPI dependency |
| `backend/src/database/models.py` | `users`, `manager_users`, `invite_codes` 테이블 정의 |
| `backend/src/config/settings.py` | JWT secret, algorithm, 만료시간 설정 |

## 3. 사용자 유형

| 유형 | 저장 테이블 | 설명 |
|---|---|---|
| 팀장/master | `users` | 프랜차이즈 본부 담당자 계정 |
| 매니저/manager | `manager_users` | 팀장의 초대코드로 가입하는 하위 계정 |

## 4. 팀장 회원가입 흐름

API: `POST /auth/signup`

```text
1. 이메일 중복 확인
2. 사업자등록번호 중복 확인
3. 사업자번호 + 기업명으로 브랜드 매핑
4. 비밀번호 bcrypt 해시 생성
5. users 테이블에 회원 저장
6. biz_brand_mapping 테이블에 브랜드 매핑 저장
7. JWT access_token 발급
```

회원가입 성공 응답에는 `user`, `brand`, `verification`, `access_token`이 포함된다.

## 5. 팀장 로그인 흐름

API: `POST /auth/login`

```text
1. email로 users 테이블 조회
2. 계정이 없으면 오류 반환
3. bcrypt로 비밀번호 검증
4. is_active=false 계정은 로그인 차단
5. last_login_at 갱신
6. biz_brand_mapping 또는 FTC 데이터로 브랜드 정보 조회
7. JWT access_token 발급
```

성공 응답 구조:

```text
{
  status: "success",
  user: {...},
  brand: {...},
  access_token: "..."
}
```

## 6. 매니저 가입/로그인 흐름

### 6.1 초대코드 발급

API: `POST /auth/invite-code`

팀장이 `owner_id`로 초대코드를 발급한다. 초대코드는 `invite_codes` 테이블에 저장된다.

### 6.2 초대코드 검증

API: `POST /auth/verify-invite`

초대코드가 유효하면 팀장의 기업명, 사업자번호, 가맹점 수, `owner_id`를 반환한다.

### 6.3 매니저 회원가입

API: `POST /auth/manager/signup`

```text
1. 초대코드 검증
2. users + manager_users 전체에서 이메일 중복 확인
3. 비밀번호 bcrypt 해시 생성
4. manager_users 테이블에 저장
5. is_active=true, is_approved=false 상태로 생성
6. 초대코드 used_count 증가
```

매니저 회원가입 직후에는 JWT를 발급하지 않는다. 팀장 승인이 필요하기 때문이다.

### 6.4 매니저 승인

API: `PATCH /auth/manager/{manager_id}/approve`

팀장이 매니저를 승인하면 `manager_users.is_approved=true`가 된다. 담당 구/행정동도 함께 저장할 수 있다.

### 6.5 매니저 로그인

API: `POST /auth/manager/login`

```text
1. email로 manager_users 조회
2. 소속 팀장 users 테이블과 JOIN
3. is_active=false면 로그인 차단
4. is_approved=false면 로그인 차단
5. bcrypt로 비밀번호 검증
6. last_login_at 갱신
7. JWT access_token 발급
```

## 7. JWT 구현

JWT 관련 코드는 `backend/src/services/jwt_auth.py`에 있다.

| 함수 | 역할 |
|---|---|
| `create_access_token()` | JWT 발급 |
| `decode_token()` | JWT 서명 및 만료 검증 |
| `get_current_user()` | Bearer 토큰 필수 인증 dependency |
| `get_optional_user()` | 토큰이 있으면 파싱, 없으면 `None` |

JWT payload 주요 필드:

| 필드 | 의미 |
|---|---|
| `sub` | 사용자 ID |
| `role` | `master` 또는 `manager` |
| `email` | 사용자 이메일 |
| `owner_id` | 매니저의 소속 팀장 ID |
| `iat` | 발급 시각 |
| `exp` | 만료 시각 |

설정값:

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `JWT_SECRET_KEY` | `dev-only-not-secret-replace-in-prod` | JWT 서명 키 |
| `JWT_ALGORITHM` | `HS256` | JWT 알고리즘 |
| `JWT_EXPIRE_MINUTES` | `1440` | 토큰 만료 시간 |

## 8. 현재 JWT 사용 범위

현재 Bearer 토큰을 필수로 요구하는 대표 API는 `simulation-history` 라우터이다.

```text
Authorization: Bearer <access_token>
```

`simulation-history`에서는 토큰에서 `user_id`, `role`, `owner_id`를 읽어 시뮬레이션 이력 조회/저장 권한을 판단한다.

## 9. 관련 DB 테이블

| 테이블 | 역할 |
|---|---|
| `users` | 팀장 계정 저장 |
| `manager_users` | 매니저 계정 저장 |
| `invite_codes` | 팀장 초대코드 저장 |
| `biz_brand_mapping` | 사업자번호와 브랜드 매핑 저장 |
| `ftc_brand_franchise` | 공정위 프랜차이즈 브랜드 원천 데이터 |

## 10. 반드시 기억할 점

- 비밀번호는 평문 저장이 아니라 `bcrypt` 해시로 저장된다.
- 팀장 로그인은 `users` 테이블을 기준으로 검증한다.
- 매니저 로그인은 `manager_users`와 `users`를 JOIN해서 소속 기업 정보를 함께 반환한다.
- 매니저는 가입 직후 바로 로그인할 수 없고, 팀장 승인 후 로그인 가능하다.
- 로그인 성공 시 프론트엔드는 `access_token`을 받아 이후 인증 API에 Bearer 토큰으로 사용한다.
- 현재 코드 기준으로 `manager_login` 서비스 응답의 `user`에는 `owner_id`가 포함되어 있지 않아, 매니저 JWT payload의 `owner_id`가 비어 있을 수 있다.
