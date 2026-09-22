from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
from typing import BinaryIO

import pandas as pd


@dataclass(frozen=True)
class RejectedRow:
    row_number: int
    draw_date: str
    combination: str
    reason: str


@dataclass(frozen=True)
class DrawDataset:
    draws: pd.DataFrame
    rejected: tuple[RejectedRow, ...]
    source_name: str

    @property
    def is_usable(self) -> bool:
        return not self.draws.empty


def _parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(str(value).replace(",", ""), errors="raise")
    return parsed.date()


def _parse_numbers(value: object, maximum: int) -> tuple[int, ...]:
    numbers = tuple(int(item) for item in re.findall(r"\d+", str(value)))
    if len(numbers) != 6:
        raise ValueError("expected exactly six numbers")
    if len(set(numbers)) != 6:
        raise ValueError("numbers must be distinct")
    if any(number < 1 or number > maximum for number in numbers):
        raise ValueError(f"numbers must be between 1 and {maximum}")
    return tuple(sorted(numbers))


def load_draws(
    source: str | Path | bytes | BinaryIO,
    *,
    maximum: int = 58,
    source_name: str | None = None,
) -> DrawDataset:
    if isinstance(source, bytes):
        workbook: str | Path | BinaryIO = BytesIO(source)
    else:
        workbook = source

    name = source_name or getattr(source, "name", None) or Path(str(source)).name
    if str(name).lower().endswith(".csv"):
        frame = pd.read_csv(workbook)
    else:
        frame = pd.read_excel(workbook, sheet_name=0)
    normalized_columns = {str(column).strip().lower(): column for column in frame.columns}
    date_column = normalized_columns.get("draw date")
    numbers_column = normalized_columns.get("winning numbers")
    if date_column is None or numbers_column is None:
        raise ValueError("input must contain Draw Date and Winning Numbers columns")

    accepted: list[dict[str, object]] = []
    rejected: list[RejectedRow] = []
    seen_dates: set[date] = set()

    for offset, row in frame.iterrows():
        row_number = int(offset) + 2
        raw_date = row[date_column]
        raw_numbers = row[numbers_column]
        try:
            draw_date = _parse_date(raw_date)
            numbers = _parse_numbers(raw_numbers, maximum)
            if draw_date in seen_dates:
                raise ValueError("duplicate draw date")
            seen_dates.add(draw_date)
            accepted.append({"draw_date": draw_date, "numbers": numbers})
        except (TypeError, ValueError) as error:
            rejected.append(
                RejectedRow(
                    row_number=row_number,
                    draw_date=str(raw_date),
                    combination=str(raw_numbers),
                    reason=str(error),
                )
            )

    draws = pd.DataFrame(accepted, columns=["draw_date", "numbers"])
    if not draws.empty:
        draws = draws.sort_values("draw_date", ignore_index=True)
    return DrawDataset(draws=draws, rejected=tuple(rejected), source_name=str(name))
