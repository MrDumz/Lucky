from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from math import comb, exp, sqrt
import random
from statistics import mean, pstdev

import pandas as pd


@dataclass(frozen=True)
class GameRules:
    maximum: int = 58
    pick_count: int = 6

    @property
    def jackpot_denominator(self) -> int:
        return comb(self.maximum, self.pick_count)


@dataclass(frozen=True)
class BacktestResult:
    development: pd.DataFrame
    holdout: pd.DataFrame
    selected_model: str
    development_range: str
    holdout_range: str


def _minmax(values: list[float], neutral: float = 50.0) -> list[float]:
    low, high = min(values), max(values)
    if high == low:
        return [neutral] * len(values)
    return [100 * (value - low) / (high - low) for value in values]


def _binomial_two_sided(successes: int, trials: int, probability: float) -> float:
    probabilities = [
        comb(trials, value)
        * probability**value
        * (1 - probability) ** (trials - value)
        for value in range(trials + 1)
    ]
    observed = probabilities[successes]
    return min(1.0, sum(value for value in probabilities if value <= observed + 1e-15))


def _benjamini_hochberg(values: list[float]) -> list[float]:
    count = len(values)
    order = sorted(range(count), key=values.__getitem__)
    adjusted = [1.0] * count
    running = 1.0
    for reverse_rank, index in enumerate(reversed(order), start=1):
        rank = count - reverse_rank + 1
        running = min(running, values[index] * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def number_metrics(draws: pd.DataFrame, rules: GameRules = GameRules()) -> pd.DataFrame:
    combinations_list = list(draws["numbers"])
    draw_count = len(combinations_list)
    frequencies = Counter(number for draw in combinations_list for number in draw)
    midpoint = rules.maximum // 2
    expected = draw_count * rules.pick_count / rules.maximum
    standard_deviation = sqrt(
        draw_count
        * (rules.pick_count / rules.maximum)
        * (1 - rules.pick_count / rules.maximum)
    )

    split = max(1, draw_count // 2)
    first = Counter(number for draw in combinations_list[:split] for number in draw)
    second = Counter(number for draw in combinations_list[split:] for number in draw)
    pair_counts = Counter(
        pair for draw in combinations_list for pair in combinations(draw, 2)
    )

    numbers = list(range(1, rules.maximum + 1))
    frequency_values = [float(frequencies[number]) for number in numbers]
    frequency_scores = _minmax(frequency_values)
    stability_values = [
        1 / (1 + abs(first[number] / split - second[number] / max(1, draw_count - split)))
        for number in numbers
    ]
    stability_scores = _minmax(stability_values)
    pair_values = [
        mean(
            pair_counts[tuple(sorted((number, other)))]
            for other in numbers
            if other != number
        )
        for number in numbers
    ]
    pair_scores = _minmax(pair_values)

    gaps: list[int] = []
    for number in numbers:
        appearances = [
            index for index, draw in enumerate(combinations_list) if number in draw
        ]
        gaps.append(draw_count - 1 - max(appearances) if appearances else draw_count)
    coverage_scores = [100 * exp(-gap / 40) for gap in gaps]

    raw_p_values = [
        _binomial_two_sided(
            frequencies[number], draw_count, rules.pick_count / rules.maximum
        )
        for number in numbers
    ]
    adjusted_p_values = _benjamini_hochberg(raw_p_values)

    rows: list[dict[str, object]] = []
    for index, number in enumerate(numbers):
        historical_score = (
            0.40 * frequency_scores[index]
            + 0.30 * stability_scores[index]
            + 0.20 * pair_scores[index]
            + 0.10 * coverage_scores[index]
        )
        rows.append(
            {
                "number": number,
                "frequency": frequencies[number],
                "expected": expected,
                "z_score": (frequencies[number] - expected) / standard_deviation,
                "raw_p": raw_p_values[index],
                "adjusted_p": adjusted_p_values[index],
                "draws_since_seen": gaps[index],
                "band": "Low" if number <= midpoint else "High",
                "historical_score": historical_score,
                "stability_score": stability_scores[index],
            }
        )

    result = pd.DataFrame(rows)
    return result.sort_values(
        ["historical_score", "number"], ascending=[False, True], ignore_index=True
    )


def structural_summary(draws: pd.DataFrame, rules: GameRules = GameRules()) -> dict[str, float]:
    combinations_list = list(draws["numbers"])
    sums = [sum(draw) for draw in combinations_list]
    odd_counts = [sum(number % 2 for number in draw) for draw in combinations_list]
    low_counts = [
        sum(number <= rules.maximum // 2 for number in draw)
        for draw in combinations_list
    ]
    consecutive = [
        sum(right - left == 1 for left, right in zip(draw, draw[1:]))
        for draw in combinations_list
    ]
    average_gaps = [
        (draw[-1] - draw[0]) / (rules.pick_count - 1) for draw in combinations_list
    ]
    return {
        "mean_sum": mean(sums),
        "sum_sd": pstdev(sums),
        "mean_odd": mean(odd_counts),
        "mean_low": mean(low_counts),
        "mean_consecutive_pairs": mean(consecutive),
        "mean_average_gap": mean(average_gaps),
    }


def _hypergeometric_overlap_pmf(rules: GameRules) -> list[float]:
    denominator = comb(rules.maximum, rules.pick_count)
    return [
        comb(rules.pick_count, matches)
        * comb(rules.maximum - rules.pick_count, rules.pick_count - matches)
        / denominator
        for matches in range(rules.pick_count + 1)
    ]


def _total_overlap_tail(total: int, targets: int, rules: GameRules) -> float:
    distribution = [1.0]
    single = _hypergeometric_overlap_pmf(rules)
    for _ in range(targets):
        expanded = [0.0] * (len(distribution) + rules.pick_count)
        for left_index, left_value in enumerate(distribution):
            for right_index, right_value in enumerate(single):
                expanded[left_index + right_index] += left_value * right_value
        distribution = expanded
    return sum(distribution[total:])


def _holm(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [1.0] * len(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted


def _predict(history: list[tuple[int, ...]], model: str, rules: GameRules) -> tuple[int, ...]:
    numbers = range(1, rules.maximum + 1)
    frequencies = Counter(number for draw in history for number in draw)
    if model == "Fixed control":
        return tuple(range(1, rules.pick_count + 1))
    if model == "Cumulative frequency":
        return tuple(sorted(sorted(numbers, key=lambda value: (-frequencies[value], value))[:6]))
    if model == "Recent frequency":
        weighted = {
            number: sum(
                2 ** (-(len(history) - 1 - index) / 20)
                for index, draw in enumerate(history)
                if number in draw
            )
            for number in numbers
        }
        return tuple(sorted(sorted(numbers, key=lambda value: (-weighted[value], value))[:6]))
    if model == "Most overdue":
        last_seen = {
            number: max(
                (index for index, draw in enumerate(history) if number in draw),
                default=-1,
            )
            for number in numbers
        }
        return tuple(sorted(sorted(numbers, key=lambda value: (last_seen[value], value))[:6]))
    if model == "Least frequent":
        return tuple(sorted(sorted(numbers, key=lambda value: (frequencies[value], value))[:6]))

    top = sorted(numbers, key=lambda value: (-frequencies[value], value))[:14]
    target_sum = mean(sum(draw) for draw in history)
    candidates = [
        candidate
        for candidate in combinations(top, rules.pick_count)
        if sum(value % 2 for value in candidate) == 3
        and sum(value <= rules.maximum // 2 for value in candidate) == 3
    ]
    if not candidates:
        return tuple(sorted(top[: rules.pick_count]))
    return tuple(
        sorted(
            min(
                candidates,
                key=lambda candidate: (
                    abs(sum(candidate) - target_sum),
                    -sum(frequencies[value] for value in candidate),
                    candidate,
                ),
            )
        )
    )


def _evaluate_split(
    draws: list[tuple[int, ...]],
    start: int,
    end: int,
    rules: GameRules,
) -> pd.DataFrame:
    models = [
        "Fixed control",
        "Cumulative frequency",
        "Recent frequency",
        "Most overdue",
        "Least frequent",
        "Structural frequency",
    ]
    rows: list[dict[str, object]] = []
    raw_p_values: list[float] = []
    totals: list[int] = []
    for model in models:
        overlaps = [
            len(set(_predict(draws[:index], model, rules)) & set(draws[index]))
            for index in range(start, end)
        ]
        total = sum(overlaps)
        totals.append(total)
        raw_p_values.append(_total_overlap_tail(total, len(overlaps), rules))
        rows.append(
            {
                "model": model,
                "mean_matches": mean(overlaps),
                "total_matches": total,
                "draws_with_2_plus": sum(value >= 2 for value in overlaps),
                "maximum_match": max(overlaps),
            }
        )
    adjusted = _holm(raw_p_values)
    for row, raw_p, adjusted_p in zip(rows, raw_p_values, adjusted):
        row["raw_p"] = raw_p
        row["holm_p"] = adjusted_p
    return pd.DataFrame(rows)


def walk_forward_backtest(
    draws: pd.DataFrame, rules: GameRules = GameRules()
) -> BacktestResult | None:
    combinations_list = list(draws["numbers"])
    if len(combinations_list) < 70:
        return None
    holdout_start = len(combinations_list) - 30
    development = _evaluate_split(combinations_list, 30, holdout_start, rules)
    holdout = _evaluate_split(
        combinations_list, holdout_start, len(combinations_list), rules
    )
    selected_model = str(
        development.sort_values(
            ["mean_matches", "model"], ascending=[False, True]
        ).iloc[0]["model"]
    )
    development_range = (
        f"{draws.iloc[30]['draw_date']:%b %d, %Y} – "
        f"{draws.iloc[holdout_start - 1]['draw_date']:%b %d, %Y}"
    )
    holdout_range = (
        f"{draws.iloc[holdout_start]['draw_date']:%b %d, %Y} – "
        f"{draws.iloc[-1]['draw_date']:%b %d, %Y}"
    )
    return BacktestResult(
        development=development,
        holdout=holdout,
        selected_model=selected_model,
        development_range=development_range,
        holdout_range=holdout_range,
    )


def generate_combinations(
    draws: pd.DataFrame,
    metrics: pd.DataFrame,
    *,
    count_per_profile: int = 5,
    seed: int = 20260922,
    rules: GameRules = GameRules(),
) -> pd.DataFrame:
    randomizer = random.Random(seed)
    metric_map = metrics.set_index("number")["historical_score"].to_dict()
    structure = structural_summary(draws, rules)
    candidates: set[tuple[int, ...]] = set()
    while len(candidates) < 20_000:
        candidates.add(
            tuple(
                sorted(
                    randomizer.sample(
                        range(1, rules.maximum + 1), rules.pick_count
                    )
                )
            )
        )

    def structural_score(candidate: tuple[int, ...]) -> float:
        sum_scale = max(structure["sum_sd"], 1.0)
        sum_score = 100 * exp(-abs(sum(candidate) - structure["mean_sum"]) / sum_scale)
        odd_score = 100 * exp(
            -abs(sum(value % 2 for value in candidate) - structure["mean_odd"])
        )
        low_score = 100 * exp(
            -abs(
                sum(value <= rules.maximum // 2 for value in candidate)
                - structure["mean_low"]
            )
        )
        gap = (candidate[-1] - candidate[0]) / (rules.pick_count - 1)
        gap_score = 100 * exp(-abs(gap - structure["mean_average_gap"]) / 2)
        return mean([sum_score, odd_score, low_score, gap_score])

    profiles = {
        "Conservative": (0.70, 0.30),
        "Balanced": (0.50, 0.50),
        "Diversified": (0.30, 0.70),
    }
    selected: list[dict[str, object]] = []
    selected_numbers: list[set[int]] = []
    for profile, (number_weight, structure_weight) in profiles.items():
        ranked: list[tuple[float, tuple[int, ...], float, float]] = []
        for candidate in candidates:
            number_score = mean(metric_map[number] for number in candidate)
            candidate_structure = structural_score(candidate)
            profile_score = (
                number_weight * number_score
                + structure_weight * candidate_structure
            )
            if profile == "Diversified":
                profile_score += 0.12 * (100 - candidate_structure)
            ranked.append(
                (profile_score, candidate, number_score, candidate_structure)
            )
        ranked.sort(key=lambda item: (-item[0], item[1]))
        added = 0
        for profile_score, candidate, number_score, candidate_structure in ranked:
            candidate_set = set(candidate)
            if any(len(candidate_set & prior) > 2 for prior in selected_numbers):
                continue
            odd = sum(number % 2 for number in candidate)
            low = sum(number <= rules.maximum // 2 for number in candidate)
            selected.append(
                {
                    "profile": profile,
                    "combination": " – ".join(f"{number:02d}" for number in candidate),
                    "odd_even": f"{odd}/{rules.pick_count - odd}",
                    "low_high": f"{low}/{rules.pick_count - low}",
                    "sum": sum(candidate),
                    "average_gap": (candidate[-1] - candidate[0])
                    / (rules.pick_count - 1),
                    "historical_score": number_score,
                    "structural_similarity": candidate_structure,
                    "profile_score": profile_score,
                }
            )
            selected_numbers.append(candidate_set)
            added += 1
            if added == count_per_profile:
                break
    return pd.DataFrame(selected)


def next_model_combinations(
    draws: pd.DataFrame, rules: GameRules = GameRules()
) -> pd.DataFrame:
    history = list(draws["numbers"])
    models = [
        "Fixed control",
        "Cumulative frequency",
        "Recent frequency",
        "Most overdue",
        "Least frequent",
        "Structural frequency",
    ]
    return pd.DataFrame(
        {
            "model": models,
            "combination": [
                " – ".join(f"{number:02d}" for number in _predict(history, model, rules))
                for model in models
            ],
        }
    )
