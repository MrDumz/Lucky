from pathlib import Path

from lotto_app.data import load_draws


def test_supplied_workbook_is_normalized_with_one_disclosed_rejection() -> None:
    workbook = Path(__file__).parents[1] / "lotto_copy.xlsx"

    dataset = load_draws(workbook)

    assert dataset.is_usable
    assert len(dataset.draws) == 112
    assert dataset.draws.iloc[0]["draw_date"].isoformat() == "2026-01-02"
    assert dataset.draws.iloc[-1]["draw_date"].isoformat() == "2026-09-20"
    assert len(dataset.rejected) == 1
    assert dataset.rejected[0].draw_date == "April 3, 2026"
    assert dataset.rejected[0].combination == "–"
    assert dataset.rejected[0].reason == "expected exactly six numbers"