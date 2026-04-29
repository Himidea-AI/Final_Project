"""change_ix supervised eval 단위 테스트."""

import pandas as pd


def test_compute_transition_labels_lh_to_hh_is_emerging():
    from validation.experiments.emerging_district.change_ix_eval import (
        compute_transition_labels,
    )

    df = pd.DataFrame(
        {
            "dong_code": ["11440660", "11440660"],
            "quarter": [20231, 20232],
            "change_ix": ["HL", "LH"],
        }
    )
    labels = compute_transition_labels(df)
    assert labels.iloc[1]["is_emerging"] == 1


def test_compute_transition_labels_hh_to_hl_is_declining():
    from validation.experiments.emerging_district.change_ix_eval import (
        compute_transition_labels,
    )

    df = pd.DataFrame(
        {
            "dong_code": ["11440660", "11440660"],
            "quarter": [20231, 20232],
            "change_ix": ["HH", "HL"],
        }
    )
    labels = compute_transition_labels(df)
    assert labels.iloc[1]["is_declining"] == 1
