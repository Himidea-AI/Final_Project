import requests
import json

url = "http://localhost:8000/analyze"
payload = {
    "business_type": "cafe",
    "brand_name": "메가커피",
    "target_district": "서교동"
}
headers = {
    "Content-Type": "application/json"
}

try:
    print(f"--- [API TEST] POST {url} 요청 전송 ---")
    response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=50)
    print(f"상태 코드: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("\n[최종 응답 JSON (구조 확인)]")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"에러 응답: {response.text}")

except Exception as e:
    print(f"❌ 요청 중 오류 발생: {str(e)}")
