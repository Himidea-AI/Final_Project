import pytest

def test_analyze_endpoint(client):
    """
    /analyze 엔드포인트 통합 테스트
    - 5인 Agent 파이프라인 (Market, Population, Legal 등) 호출 검증
    """
    sim_data = {
        "target_district": "서교동",
        "business_type": "카페",
        "brand_name": "스타벅스"
    }
    res = client.post("/analyze", json=sim_data)
    assert res.status_code == 200
    
def test_simulate_endpoint(client):
    """
    /simulate 엔드포인트 통합 테스트
    """
    sim_data = {
        "target_district": "서교동",
        "business_type": "카페",
        "brand_name": "스타벅스"
    }
    res = client.post("/simulate", json=sim_data)
    assert res.status_code == 200
