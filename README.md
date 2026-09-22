# Ultra 58 Lab

Ultra 58 Lab is a local Streamlit application for auditing Philippine Ultra Lotto 6/58 draw history. It validates Excel or CSV records, summarizes historical distributions, runs chronological holdout tests, and generates reproducible diversified example lines.

The application does not predict winning numbers. Every valid 6/58 combination has the same jackpot probability: 1 in 40,475,358.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open `http://localhost:8501`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Input Format

The first Excel sheet or CSV file must contain:

| Column | Example |
|---|---|
| `Draw Date` | `September 20, 2026` |
| `Winning Numbers` | `02-16-20-23-28-33` |

Rows must contain exactly six distinct integers from 1 through 58. Invalid and duplicate-date rows are disclosed in the Data Quality tab and excluded from analysis.

## Method

- Number tests use an exact two-sided binomial calculation and Benjamini-Hochberg correction across all 58 numbers.
- Backtests use expanding historical windows and reserve the final 30 draws as an untouched holdout.
- Match totals are tested against the exact repeated hypergeometric null and corrected across models with Holm's method.
- Historical Profile Scores blend frequency, split-half stability, pair participation, and recent coverage. They are descriptive scores, not forecast probabilities.
- Generated lines use a reproducible seed and share no more than two numbers with one another.