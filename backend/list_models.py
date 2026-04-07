import google.generativeai as genai
import os
from dotenv import load_dotenv

# .env 파일 로드 (backend 폴더 내)
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not found in environment.")
else:
    genai.configure(api_key=api_key)
    try:
        print("Available models supporting generateContent:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"ERROR: Failed to list models: {str(e)}")
