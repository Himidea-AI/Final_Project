# validation/exceptions.py
"""Imputed v4 파이프라인 예외 클래스."""


class ImputationError(Exception):
    """역산 파이프라인 base 예외."""


class KOSISFetchError(ImputationError):
    """KOSIS API 응답 없음/빈 결과 — Phase 0-1."""


class KOSISItemAmbiguousError(ImputationError):
    """경상/불변 itm_id 모두 fallback 실패 — Phase 0-1."""


class LearningPathInvalidError(ImputationError):
    """3 path 모두 NaN/inf MNAR 결과 — Phase 0-3."""


class EnsembleInstabilityError(ImputationError):
    """6 seed 분산이 합격선 1-1 임계 (>0.10) 초과 — Phase 1."""


class ExtrapolationCellOverflowError(ImputationError):
    """외삽 셀이 137 중 50% 초과 — 모델 자체 의문."""


class AuditFailureWithDiagnoses(ImputationError):
    """Phase 2 감사 5종 이상 fail — 정직 보고."""


class V4DBLoadError(ImputationError):
    """seoul_district_sales_imputed_v4 적재 실패."""


class WorldLoaderRegressionError(ImputationError):
    """world_loader 수정 후 회귀 테스트 fail."""


class SensitivityZeroImpactError(ImputationError):
    """Phase 4 sensitivity 가 절대값 < 1% — imputed 효과 측정 불가."""
