from math import comb
from pathlib import Path

from lotto_app.analysis import (
    GameRules,
    generate_combinations,
    number_metrics,
    walk_forward_backtest,
)
from lotto_app.data import load_draws


def _dataset():
    workbook = Path(__file__).parents[1] / "lotto_copy.xlsx"
    return load_draws(workbook).draws


def test_exact_jackpot_odds() -> None:
    assert GameRules().jackpot_denominator == comb(58, 6) == 40_475_358


def test_rankings_and_backtest_are_complete() -> None:
    draws = _dataset()
    metrics = number_metrics(draws)
    backtest = walk_forward_backtest(draws)

    assert len(metrics) == 58
    assert set(metrics["number"]) == set(range(1, 59))
    assert not metrics["adjusted_p"].lt(0.05).any()
    assert backtest is not None
    assert len(backtest.development) == 6
    assert len(backtest.holdout) == 6
    assert not backtest.holdout["holm_p"].lt(0.05).any()


def test_generated_combinations_are_valid_unique_and_diversified() -> None:
    draws = _dataset()
    generated = generate_combinations(draws, number_metrics(draws))
    parsed = [
        tuple(int(number.strip()) for number in value.split("–"))
        for value in generated["combination"]
    ]

    assert len(parsed) == 15
    assert len(set(parsed)) == 15
    assert all(len(set(values)) == 6 for values in parsed)
    assert all(1 <= number <= 58 for values in parsed for number in values)
    assert max(
        len(set(left) & set(right))
        for index, left in enumerate(parsed)
        for right in parsed[index + 1 :]
    ) <= 2