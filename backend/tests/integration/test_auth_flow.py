import uuid
import pytest

def test_signup_and_login_flow(client):
    """
    회원가입 ➜ 로그인으로 이어지는 Auth 통합 흐름 검증
    """
    unique_id = str(uuid.uuid4())[:8]
    email = f"integration_test_{unique_id}@example.com"
    password = "TestPassword123!"

    # 1. 회원가입 테스트
    signup_data = {
        "companyName": "통합테스트컴퍼니",
        "bizNumber": f"123-45-{unique_id[:5]}",
        "contactName": "테스터",
        "position": "통합테스터",
        "email": email,
        "phone": "010-0000-0000",
        "storeCount": "1",
        "password": password,
        "plan": "starter",
        "agreeTerms": True
    }

    res_signup = client.post("/auth/signup", json=signup_data)
    assert res_signup.status_code == 200
    
    # 2. 로그인 테스트
    login_data = {
        "email": email,
        "password": password
    }
    res_login = client.post("/auth/login", json=login_data)
    assert res_login.status_code == 200
