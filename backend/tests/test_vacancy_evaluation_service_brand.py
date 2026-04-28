"""evaluate_top_vacancies 의 brand_name 인자 동작."""

from unittest.mock import patch

from src.services.brand_menu_loader import BrandNotFoundError
from src.services.vacancy_evaluation_service import evaluate_top_vacancies

SPOT = {"dong_name": "서교동", "lat": 37.5544, "lon": 126.9220, "id": "v1"}


@patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse")
@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_evaluate_with_brand_loads_menu(mock_loader, mock_pse):
    """brand_name 제공 → brand_menu_loader 호출 → vacancy_pse 에 menu_items 패스."""
    mock_loader.return_value = [{"name": "라떼", "price": 5000}]
    mock_pse.return_value = {
        "narrative": "test",
        "pse_summary": {
            "visits_per_day": {"mean": 10.0, "ci95": 1.0, "min": 9, "max": 11},
            "revenue_per_day": {"mean": 100000, "ci95": 5000},
            "vacancy_vs_avg_visits_ratio": {"mean": 1.0, "ci95": 0.1},
        },
    }
    out = evaluate_top_vacancies(
        vacancy_spots=[SPOT],
        category="카페",
        brand_name="이디야",
        n_seeds=1,
    )
    mock_loader.assert_called_once_with("이디야")
    # vacancy_pse 호출 시 menu_items 가 패스됐는지 확인
    _, kwargs = mock_pse.call_args
    assert kwargs.get("menu_items") == [{"name": "라떼", "price": 5000}]
    assert len(out) == 1


@patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse")
@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_evaluate_without_brand_skips_loader(mock_loader, mock_pse):
    """brand_name=None (기본) → loader 호출 X (하위 호환)."""
    mock_pse.return_value = {
        "narrative": "test",
        "pse_summary": {
            "visits_per_day": {"mean": 5.0, "ci95": 1.0, "min": 4, "max": 6},
            "revenue_per_day": {"mean": 50000, "ci95": 2500},
            "vacancy_vs_avg_visits_ratio": {"mean": 1.0, "ci95": 0.1},
        },
    }
    out = evaluate_top_vacancies(vacancy_spots=[SPOT], category="카페", n_seeds=1)
    mock_loader.assert_not_called()
    assert len(out) == 1


@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_brand_not_found_returns_error_response(mock_loader):
    """BrandNotFoundError → 결과 빈 list + log.warning (전체 평가 중단)."""
    mock_loader.side_effect = BrandNotFoundError("스타벅스 마포 매장 없음")
    out = evaluate_top_vacancies(
        vacancy_spots=[SPOT],
        category="카페",
        brand_name="스타벅스",
        n_seeds=1,
    )
    # 정책: brand 없으면 모든 spot 평가 불가 (모두 같은 brand 가정)
    assert out == []
