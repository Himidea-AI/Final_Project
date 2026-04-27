import requests
import json
import time

def test_final_verification():
    url = "http://localhost:8000/analyze"
    payload = {
        "business_type": "cafe",
        "brand_name": "메가커피",
        "target_district": "서교동",
        "existing_stores": [],
        "monthly_rent": 3500000,
        "scenarios": ["standard"]
    }
    
    print(f"--- [TEST] 서교동/메가커피 분석 시작 ---")
    start_time = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            print(f"--- [SUCCESS] 분석 완료 (소요시간: {end_time - start_time:.2f}s) ---")
            
            # 정량 지표 확인
            metrics = result.get("data", {}).get("analysis_metrics", {})
            print(f"\n[분석 결과 요약]")
            print(f"- 등급: {metrics.get('district_grade')}")
            print(f"- 성장률: {metrics.get('growth_rate')}%")
            print(f"- 경쟁 점수: {metrics.get('competition_score')}")
            
            # 리포트 길이 확인
            report = result.get("data", {}).get("analysis_report", "")
            print(f"- 리포트 길이: {len(report)} 자")
            
            # JSON 저장
            with open("final_simulation_result.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            print(f"\n[파일 저장] final_simulation_result.json 저장 완료")
            
            return result
        else:
            print(f"--- [FAILURE] 상태 코드: {response.status_code} ---")
            print(response.text)
            return None
    except Exception as e:
        print(f"--- [ERROR] {str(e)} ---")
        return None

if __name__ == "__main__":
    test_final_verification()
