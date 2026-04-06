"""
외부 API 클라이언트 패키지 — 7개 공공/오픈 데이터 소스 연동 + CSV 로더
"""
from src.services.base_client import BaseAPIClient
from src.services.seoul_opendata import SeoulOpendataClient
from src.services.sgis_api import SgisAPIClient
from src.services.semas_api import SemasAPIClient
from src.services.golmok_api import GolmokAPIClient
from src.services.molit_api import MolitAPIClient
from src.services.sns_trend import NaverTrendClient
from src.services.csv_loader import CsvDataLoader

__all__ = [
    "BaseAPIClient",
    "SeoulOpendataClient",
    "SgisAPIClient",
    "SemasAPIClient",
    "GolmokAPIClient",
    "MolitAPIClient",
    "NaverTrendClient",
    "CsvDataLoader",
]
