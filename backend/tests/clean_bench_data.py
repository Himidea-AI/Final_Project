"""
F&B 창업 법률 Golden Set 정제 스크립트 (v2)

입력: bench_review_filled.csv
출력:
  - bench_review_v5.csv (현행법, 정답지)
  - bench_review_v5_future.csv (미시행 법령 별도)
  - system_prompt_guideline.txt (에이전트 시스템 프롬프트용 가이드)

3대 핵심 이슈 자동 정제:
  Issue A - 영업지역 보호 → 가맹사업법 제12조의4
  Issue B - 필수품목 구입강제 → 가맹사업법 제12조 (공정거래법 매칭 교정)
  Issue C - 허위·과장 정보제공 → 가맹사업법 제9조 (신규 쿼리 추가)
"""

import pandas as pd
import re
from pathlib import Path
from datetime import date

INPUT = Path(__file__).resolve().parent.parent.parent / 'docs' / 'team' / 'bench_review_filled.csv'
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / 'docs' / 'team'
TODAY = date(2026, 4, 27)


# ─────────────────────────────────────────────────────────────
# 헬퍼 함수
# ─────────────────────────────────────────────────────────────

def is_future_effective(snippet):
    """[시행일: YYYY. MM. DD.] 패턴이 오늘보다 미래면 True"""
    if pd.isna(snippet):
        return False
    m = re.search(r'\[시행일:\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', str(snippet))
    if m:
        try:
            return date(*map(int, m.groups())) > TODAY
        except ValueError:
            return False
    return False


def extract_miss_article(snippet):
    """MISS 행 snippet에서 '[미반환] 기대 조문: 제N조' 추출"""
    if pd.isna(snippet):
        return None
    m = re.search(r'기대 조문:\s*(\S+)', str(snippet))
    return m.group(1) if m else None


def rebuild_expected(group):
    """human_verdict='O' returned + MISS 정답유지 articles로 재구성"""
    correct_o = group.loc[group['human_verdict'] == 'O', 'returned_article'].dropna().tolist()
    miss_kept = group[
        (group['match'] == 'MISS') &
        (group['action'].str.contains('유지', na=False))
    ]
    miss_articles = miss_kept['snippet'].apply(extract_miss_article).dropna().tolist()
    return ' / '.join(sorted(set(correct_o + miss_articles)))


def calc_f1(group):
    """쿼리별 F1 재계산 (new_expected vs RAG 반환)"""
    expected_str = group['new_expected'].iloc[0]
    if not expected_str:
        return 0.0
    expected = set(filter(None, expected_str.split(' / ')))
    returned = set(group['returned_article'].dropna().tolist())
    if not expected or not returned:
        return 0.0
    tp = len(expected & returned)
    if tp == 0:
        return 0.0
    precision = tp / len(returned)
    recall = tp / len(expected)
    return 2 * precision * recall / (precision + recall)


# ─────────────────────────────────────────────────────────────
# 메인 정제 로직
# ─────────────────────────────────────────────────────────────

def main():
    df = pd.read_csv(INPUT)
    print(f'[1] 입력 로드: {len(df)}행')

    # ── (1) 미시행 법령 자동 식별 + 정답에서 자동 제외 ────────
    df['future_effective'] = df['snippet'].apply(is_future_effective)
    n_future = df['future_effective'].sum()
    print(f'[2] 미시행 법령 식별: {n_future}건')
    if n_future > 0:
        for _, row in df[df['future_effective']].iterrows():
            print(f'    - {row["law"]} {row["returned_article"]} '
                  f'({row["query"][:30]}...)')

    df.loc[df['future_effective'] & (df['human_verdict'] == 'O'), 'human_verdict'] = 'X'
    df.loc[df['future_effective'] & df['action'].fillna('').isin(['', '정답에 추가']),
           'action'] = '미시행 - 자동 제외'
    df.loc[df['future_effective'] & (df['match'] == '정답'), 'match'] = '정답_미시행'

    # ── (2) Issue A: 영업지역 → 제12조의4 정답 락 ─────────────
    territory = df['query'].str.contains('영업지역', na=False)
    df.loc[territory, 'expected_articles'] = '제12조의4'
    print(f'[3] Issue A - 영업지역 정답 락: 제12조의4 ({territory.sum()}행)')

    # ── (3) Issue B: 필수품목 → 가맹사업법 제12조 정답 락 ─────
    # 기존 공정거래법 쿼리 → 가맹사업법으로 재분류 + 정답 교정
    tied_mask = df['query'].str.contains('필수물품|필수품목|구입강제', na=False, regex=True)
    df.loc[tied_mask, 'law'] = '가맹사업법'
    df.loc[tied_mask, 'query'] = '가맹본부 필수품목 구입강제 가맹사업법'
    df.loc[tied_mask, 'expected_articles'] = '제12조'
    # 기존 공정거래법 returned 조문은 모두 잘못된 매칭 → X
    df.loc[tied_mask & (df['human_verdict'] == 'O'), 'human_verdict'] = 'X'
    df.loc[tied_mask & (df['action'] == '정답에 추가'), 'action'] = '무관 (Issue B 교정)'
    # MISS 제55조(공정거래법) → 제거 후 MISS 제12조로 교체
    miss_55_mask = tied_mask & (df['match'] == 'MISS') & df['snippet'].str.contains('제55조', na=False)
    df.loc[miss_55_mask, 'snippet'] = '[미반환] 기대 조문: 제12조'
    print(f'[4] Issue B - 필수품목 정답 락: 가맹사업법 제12조 ({tied_mask.sum()}행)')

    # ── (4) Issue C: 허위·과장 → 가맹사업법 제9조 신규 쿼리 ────
    issue_c_rows = pd.DataFrame([
        {
            'law': '가맹사업법',
            'query': '허위 과장 정보제공 예상매출액 가맹사업법',
            'expected_articles': '제9조',
            'returned_article': None,
            'match': 'MISS',
            'snippet': '[미반환] 기대 조문: 제9조',
            'f1': 0.0,
            'human_verdict': '',
            'action': '정답 유지',
            'future_effective': False,
        },
        {
            'law': '가맹사업법',
            'query': '허위 과장 정보제공 예상매출액 가맹사업법',
            'expected_articles': '제9조',
            'returned_article': None,
            'match': 'MISS',
            'snippet': '[미반환] 기대 조문: 제9조의2',
            'f1': 0.0,
            'human_verdict': '',
            'action': '정답 유지',
            'future_effective': False,
        },
    ])
    df = pd.concat([df, issue_c_rows], ignore_index=True)
    print(f'[5] Issue C - 허위·과장 신규 쿼리 추가: 가맹사업법 제9조 (2행)')

    # ── (5) 쿼리별 new_expected 재구성 ───────────────────────
    df['new_expected'] = df.groupby('query', group_keys=False).apply(
        lambda g: pd.Series([rebuild_expected(g)] * len(g), index=g.index)
    )

    # ── (6) F1 재계산 ────────────────────────────────────────
    f1_per_query = df.groupby('query').apply(calc_f1)
    print(f'\n[6] 쿼리별 F1 재계산:')
    for q, f1 in f1_per_query.items():
        print(f'    {q[:50]:50s} F1={f1:.3f}')
    print(f'    {"-"*55}')
    print(f'    Macro F1 평균: {f1_per_query.mean():.3f}')
    print(f'    Median F1:     {f1_per_query.median():.3f}')

    # ── (7) 분리 저장 ────────────────────────────────────────
    df_current = df[~df['future_effective']].copy()
    df_future = df[df['future_effective']].copy()

    out_current = OUTPUT_DIR / 'bench_review_v5.csv'
    out_future = OUTPUT_DIR / 'bench_review_v5_future.csv'

    df_current.to_csv(out_current, index=False, encoding='utf-8-sig')
    print(f'\n[7] 저장: {out_current} ({len(df_current)}행)')

    if len(df_future) > 0:
        df_future.to_csv(out_future, index=False, encoding='utf-8-sig')
        print(f'    저장: {out_future} ({len(df_future)}행, 미시행)')

    # ── (8) 통계 요약 ────────────────────────────────────────
    print(f'\n[8] 통계 요약 (v5):')
    print(f'    O (정답): {(df_current["human_verdict"] == "O").sum()}')
    print(f'    X (무관): {(df_current["human_verdict"] == "X").sum()}')
    print(f'    MISS 정답유지: {df_current["action"].str.contains("정답 유지", na=False).sum()}')
    print(f'    총 쿼리 수: {df_current["query"].nunique()}')

    return df_current, f1_per_query


if __name__ == '__main__':
    df, f1 = main()
