"""상권 단위 유동인구를 동별로 집계하여 시간대별 유동인구 CSV 생성."""
import pandas as pd
import numpy as np
from pathlib import Path

DONG_MAP = {
    "아현동": "11440555", "공덕동": "11440565", "도화동": "11440585",
    "용강동": "11440590", "대흥동": "11440600", "염리동": "11440610",
    "신수동": "11440630", "서강동": "11440655", "서교동": "11440660",
    "합정동": "11440680", "망원1동": "11440690", "망원2동": "11440700",
    "연남동": "11440710", "성산1동": "11440720", "성산2동": "11440730",
    "상암동": "11440740",
}

# 상권명 → 동 매핑 (상권명에 포함된 동 이름 기준)
TRDAR_DONG_MAP = {
    # 아현동
    "아현동주민센터": "아현동", "아현뉴타운": "아현동",
    # 공덕동
    "공덕오거리": "공덕동", "공덕역": "공덕동",
    "KB국민은행 대흥동지점": "대흥동",
    # 도화동
    "도화동 먹자골": "도화동", "도화현대": "도화동",
    # 용강동
    "누리 꿈 스퀘어": "용강동",
    # 대흥동
    "대흥동주민센터": "대흥동", "대흥역": "대흥동",
    "마포중앙 나들이": "대흥동",
    # 염리동
    # 신수동
    "신수동주민센터": "신수동", "신수동": "신수동",
    # 서강동
    "서강동": "서강동", "서강대역": "서강동",
    # 서교동
    "서교동": "서교동", "서교초등학교": "서교동",
    "KB국민은행 서교동지점": "서교동",
    # 합정동
    "합정동": "합정동", "합정역": "합정동",
    # 망원동
    "망원동 먹자골": "망원1동", "망원동주민센터": "망원1동", "망원동": "망원1동",
    # 연남동
    "연남동": "연남동", "연남FM": "연남동",
    # 성산동
    "성산동주민센터": "성산1동",
    # 상암동
    "상암동": "상암동",
    # 홍대/신촌 → 서교동
    "홍대": "서교동", "홍익": "서교동",
    "신촌로": "서교동", "신촌거리": "서교동", "신촌기차역": "서교동",
    # 마포구청 → 공덕동
    "마포구청역": "공덕동", "마포래미안": "공덕동", "마포자이": "공덕동",
    # 이대/신촌역 → 서강동
    "이대역": "서강동", "이대": "서강동", "신촌역": "서강동",
    # 래미안 → 아현동
    "래미안 1단지": "아현동", "래미안 2단지": "아현동",
    # 나들이 → 대흥동
    "나들이": "대흥동",
    # 학교
    "만리초등학교": "아현동", "한서초등학교": "서강동",
    "서울서초등학교": "서강동", "창전마을": "서강동",
    "숙명여자대학교역": "용강동",
    # 별이름 → 상암동 (월드컵 근처)
    "별이름": "상암동",
    "서교초등학교": "서교동",
}


def load_trdar_mapping():
    """공식 상권→동 매핑 테이블 로드."""
    mapping_path = Path(__file__).parent.parent / "data" / "processed" / "trdar_dong_mapping.csv"
    mdf = pd.read_csv(mapping_path)
    # 상권코드 → 동 이름 (우리 DONG_MAP 기준)
    dong_name_col = [c for c in mdf.columns if "행정동명" in c or "동명" in c]
    if not dong_name_col:
        dong_name_col = [mdf.columns[-1]]  # 마지막 컬럼
    result = {}
    for _, row in mdf.iterrows():
        trdar_cd = str(row["TRDAR_CD"])
        dong_nm = str(row[dong_name_col[0]])
        # 우리 동 목록에 있는지 확인
        if dong_nm in DONG_MAP:
            result[trdar_cd] = dong_nm
        else:
            # 1동/2동 변환 시도
            for dn in DONG_MAP.keys():
                base = dn.replace("1동", "동").replace("2동", "동")
                if dong_nm == base or dong_nm == dn:
                    result[trdar_cd] = dn
                    break
    return result


def main():
    data_dir = Path(__file__).parent.parent / "data" / "processed"
    df = pd.read_csv(data_dir / "golmok_floating_pop_mapo.csv")

    # 공식 매핑 테이블로 상권→동 매핑
    trdar_to_dong = load_trdar_mapping()
    df["dong_name"] = df["TRDAR_CD"].astype(str).map(trdar_to_dong)

    # 매핑 안 된 상권 확인
    unmapped = df[df["dong_name"].isna()]["TRDAR_CD_NM"].unique()
    if len(unmapped) > 0:
        print(f"  매핑 안 됨 ({len(unmapped)}개): {list(unmapped)}")

    # 매핑된 것만
    df = df[df["dong_name"].notna()].copy()
    df["dong_code"] = df["dong_name"].map(DONG_MAP)
    print(f"  매핑된 상권: {df['TRDAR_CD'].nunique()}개 / 총 {pd.read_csv(data_dir / 'golmok_floating_pop_mapo.csv')['TRDAR_CD'].nunique()}개")

    # 동별 집계
    time_cols = {
        "TMZON_00_06_FLPOP_CO": "pop_00_06",
        "TMZON_06_11_FLPOP_CO": "pop_06_11",
        "TMZON_11_14_FLPOP_CO": "pop_11_14",
        "TMZON_14_17_FLPOP_CO": "pop_14_17",
        "TMZON_17_21_FLPOP_CO": "pop_17_21",
        "TMZON_21_24_FLPOP_CO": "pop_21_24",
    }
    gender_cols = {
        "ML_FLPOP_CO": "pop_male",
        "FML_FLPOP_CO": "pop_female",
    }
    age_cols = {
        "AGRDE_10_FLPOP_CO": "pop_age_10",
        "AGRDE_20_FLPOP_CO": "pop_age_20",
        "AGRDE_30_FLPOP_CO": "pop_age_30",
        "AGRDE_40_FLPOP_CO": "pop_age_40",
        "AGRDE_50_FLPOP_CO": "pop_age_50",
        "AGRDE_60_ABOVE_FLPOP_CO": "pop_age_60",
    }
    day_cols = {
        "MON_FLPOP_CO": "pop_mon",
        "TUES_FLPOP_CO": "pop_tue",
        "WED_FLPOP_CO": "pop_wed",
        "THUR_FLPOP_CO": "pop_thu",
        "FRI_FLPOP_CO": "pop_fri",
        "SAT_FLPOP_CO": "pop_sat",
        "SUN_FLPOP_CO": "pop_sun",
    }

    all_cols = {"TOT_FLPOP_CO": "pop_total"}
    all_cols.update(time_cols)
    all_cols.update(gender_cols)
    all_cols.update(age_cols)
    all_cols.update(day_cols)

    df = df.rename(columns=all_cols)
    agg_cols = list(all_cols.values())

    result = df.groupby(["STDR_YYQU_CD", "dong_code", "dong_name"])[agg_cols].sum().reset_index()
    result = result.rename(columns={"STDR_YYQU_CD": "quarter"})

    # 파생 피처
    result["pop_lunch_ratio"] = np.where(
        result["pop_total"] > 0,
        result["pop_11_14"] / result["pop_total"], 0)
    result["pop_dinner_ratio"] = np.where(
        result["pop_total"] > 0,
        result["pop_17_21"] / result["pop_total"], 0)
    result["pop_weekend_ratio"] = np.where(
        result["pop_total"] > 0,
        (result["pop_sat"] + result["pop_sun"]) / result["pop_total"], 0)
    result["pop_female_ratio"] = np.where(
        result["pop_total"] > 0,
        result["pop_female"] / result["pop_total"], 0)
    result["pop_young_ratio"] = np.where(
        result["pop_total"] > 0,
        (result["pop_age_20"] + result["pop_age_30"]) / result["pop_total"], 0)

    result = result.sort_values(["dong_code", "quarter"]).reset_index(drop=True)

    # 저장
    out_path = data_dir / "golmok_floating_pop_dong.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n  저장: {out_path.name}")
    print(f"  shape: {result.shape}")
    print(f"  분기: {result['quarter'].min()} ~ {result['quarter'].max()}")
    print(f"  동: {result['dong_code'].nunique()}개")
    print(f"  컬럼: {list(result.columns)}")

    # 샘플
    print(f"\n  === 서교동 2024Q4 ===")
    sample = result[(result["dong_code"] == "11440660") & (result["quarter"] == 20244)]
    if len(sample) > 0:
        r = sample.iloc[0]
        print(f"  총 유동인구: {r['pop_total']:,.0f}")
        print(f"  시간대: 00-06={r['pop_00_06']:,.0f} | 06-11={r['pop_06_11']:,.0f} | 11-14={r['pop_11_14']:,.0f} | 14-17={r['pop_14_17']:,.0f} | 17-21={r['pop_17_21']:,.0f} | 21-24={r['pop_21_24']:,.0f}")
        print(f"  점심비율: {r['pop_lunch_ratio']:.1%} | 저녁비율: {r['pop_dinner_ratio']:.1%} | 주말비율: {r['pop_weekend_ratio']:.1%}")
        print(f"  여성비율: {r['pop_female_ratio']:.1%} | 2030비율: {r['pop_young_ratio']:.1%}")


if __name__ == "__main__":
    main()
