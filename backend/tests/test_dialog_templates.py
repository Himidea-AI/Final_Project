"""dialog_templates 단위 테스트 — Mode B (Pure Policy + Template 자연어)."""

import random

from src.simulation.dialog_templates import TEMPLATES, pick_dialog


class TestPickDialog:
    def test_pick_returns_string(self):
        rng = random.Random(42)
        out = pick_dialog("creative_freelancer", "morning_visit_cafe", 9, rng)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_pick_is_deterministic_with_seed(self):
        """같은 seed → 같은 결과 (재현성)."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        a = pick_dialog("office_worker", "lunch_decide", 12, rng1)
        b = pick_dialog("office_worker", "lunch_decide", 12, rng2)
        assert a == b

    def test_unknown_archetype_returns_fallback(self):
        rng = random.Random(42)
        out = pick_dialog("nonexistent_type", "morning_visit_cafe", 9, rng)
        assert out == "..."  # fallback

    def test_unknown_situation_returns_fallback(self):
        rng = random.Random(42)
        out = pick_dialog("creative_freelancer", "nonexistent_situation", 9, rng)
        assert out == "..."


class TestTemplatesCoverage:
    """archetype × situation 의 cover 검증 — Mode B default 정상 동작 보장."""

    REQUIRED_SITUATIONS = ["morning_visit_cafe", "lunch_decide", "evening_decide", "rest"]
    MIN_LINES_PER_BUCKET = 5

    def test_all_archetypes_have_required_situations(self):
        """personas.py 의 8 archetype 모두 필수 situation 5+ 문장."""
        archetype_ids = [
            "creative_freelancer",
            "office_worker",
            "broadcasting_staff",
            "student_couple",
            "retired_local",
            "young_parent",
            "tourist_foreign",
            "f&b_owner",
        ]
        for arc in archetype_ids:
            assert arc in TEMPLATES, f"archetype '{arc}' 누락"
            for sit in self.REQUIRED_SITUATIONS:
                bucket = TEMPLATES[arc].get(sit, [])
                assert len(bucket) >= self.MIN_LINES_PER_BUCKET, (
                    f"{arc} × {sit}: {len(bucket)} 문장 (최소 {self.MIN_LINES_PER_BUCKET} 필요)"
                )

    def test_no_empty_strings(self):
        """모든 템플릿 문장이 비어있지 않음."""
        for arc, situations in TEMPLATES.items():
            for sit, lines in situations.items():
                for line in lines:
                    assert isinstance(line, str) and line.strip(), f"{arc} × {sit}: 빈 문자열 발견"
