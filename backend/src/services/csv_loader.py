"""
CSV 데이터 로더 — 오프라인 폴백용 유틸리티

외부 API 장애 시 디스크에 저장된 CSV 파일을 로드하는 클래스.
"""

from pathlib import Path

import pandas as pd


class CsvDataLoader:
    """로컬 CSV 파일을 로드하는 유틸리티 클래스."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def load_living_population(
        self,
        file_path: str,
        district_prefix: str = "11440",
    ) -> pd.DataFrame:
        """생활인구 CSV 로드 후 행정동 코드 prefix로 필터링."""
        df = pd.read_csv(file_path, dtype={"adstrd_code_se": str})
        return df[df["adstrd_code_se"].str.startswith(district_prefix)].reset_index(drop=True)

    def load_sgis_stats(self, file_path: str) -> pd.DataFrame:
        """SGIS 통계 CSV 로드 (헤더 없음)."""
        column_names = ["year", "area_code", "indicator_code", "value"]
        df = pd.read_csv(
            file_path,
            header=None,
            names=column_names,
            dtype={"area_code": str},
        )
        return df

    def load_store_info(
        self,
        file_path: str,
        sgg_name: str = "마포구",
        encoding: str = "utf-8",
    ) -> pd.DataFrame:
        """점포 정보 CSV 로드 후 시군구명으로 필터링."""
        df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
        return df[df["시군구명"] == sgg_name].reset_index(drop=True)

    def load_rent_building(
        self,
        file_path: str = "data/processed/rent_building_mapo.csv",
    ) -> pd.DataFrame:
        """매장용빌딩 임대료·공실률·수익률 CSV 로드."""
        return pd.read_csv(file_path, encoding="utf-8-sig")

    def load_commercial_change(
        self,
        file_path: str,
        encoding: str = "cp949",
    ) -> pd.DataFrame:
        """상권 변화 CSV 로드."""
        return pd.read_csv(file_path, encoding=encoding)
