"""
외부 API 클라이언트 패키지 — 7개 공공/오픈 데이터 소스 연동 + CSV 로더
"""

from .base_client import BaseAPIClient
from .seoul_opendata import SeoulOpendataClient
from .sgis_api import SgisAPIClient
from .semas_api import SemasAPIClient
from .golmok_api import GolmokAPIClient
from .molit_api import MolitAPIClient
from .sns_trend import NaverTrendClient
from .csv_loader import CsvDataLoader

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
