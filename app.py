from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lotto_app.analysis import (
    GameRules,
    generate_combinations,
    next_model_combinations,
    number_metrics,
    structural_summary,
    walk_forward_backtest,
)
from lotto_app.data import DrawDataset, load_draws


RULES = GameRules()
DEFAULT_WORKBOOK = Path(__file__).with_name("lotto_copy.xlsx")


st.set_page_config(
    page_title="Ultra 58 Lab",
    page_icon="🎱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,600&display=swap');
    :root {
        --ink: #15221b;
        --muted: #5f6e65;
        --paper: #f6f7f2;
        --line: #d8ddd5;
        --green: #176b4d;
        --red: #c84437;
        --gold: #c2912f;
        --blue: #386d9b;
    }
    .stApp {
        color: var(--ink);
        background-color: var(--paper);
        background-image: linear-gradient(rgba(21,34,27,.035) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(21,34,27,.035) 1px, transparent 1px);
        background-size: 28px 28px;
        font-family: 'IBM Plex Sans', 'Aptos', sans-serif;
    }
    h1, h2, h3 { font-family: 'Newsreader', Georgia, serif; letter-spacing: 0; }
    h1 { font-size: clamp(2rem, 4vw, 4rem); line-height: 1; margin-bottom: .25rem; }
    h2 { font-size: 1.65rem; }
    [data-testid="stSidebar"] { background: #edf0e9; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"], [data-testid="stSidebar"] * { color: var(--ink); }
    [data-testid="stMetric"] {
        background: rgba(255,255,255,.72);
        border-top: 3px solid var(--green);
        padding: .9rem 1rem;
        min-height: 110px;
        color: var(--ink);
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: var(--ink); }
    [data-testid="stMetricValue"] { font-family: 'Newsreader', Georgia, serif; }
    .kicker { color: var(--red); font-size: .78rem; font-weight: 600; text-transform: uppercase; }
    .subhead { color: var(--muted); font-size: 1.05rem; max-width: 760px; }
    .odds-strip {
        border-left: 4px solid var(--gold);
        background: rgba(255,255,255,.75);
        padding: .75rem 1rem;
        margin: .8rem 0 1.2rem;
    }
    .score-note { color: var(--muted); font-size: .88rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 1.25rem; border-bottom: 1px solid var(--line); }
    .stTabs [data-baseweb="tab"] { padding-left: 0; padding-right: 0; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); }
    @media (max-width: 700px) {
        h1 { font-size: 2.5rem; }
        [data-testid="stMetric"] { min-height: 96px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_uploaded(content: bytes, name: str) -> DrawDataset:
    return load_draws(content, source_name=name)


@st.cache_data(show_spinner=False)
def analyze(draws: pd.DataFrame):
    metrics = number_metrics(draws, RULES)
    structure = structural_summary(draws, RULES)
    backtest = walk_forward_backtest(draws, RULES)
    model_combinations = next_model_combinations(draws, RULES)
    return metrics, structure, backtest, model_combinations


with st.sidebar:
    st.markdown("### Dataset")
    uploaded = st.file_uploader(
        "Draw history",
        type=["xlsx", "xls", "csv"],
        help="Required columns: Draw Date and Winning Numbers",
    )
    if uploaded is None:
        st.caption("Using the bundled 6/58 history snapshot.")
        dataset = load_draws(DEFAULT_WORKBOOK)
    else:
        dataset = load_uploaded(uploaded.getvalue(), uploaded.name)

    st.markdown("### Combination settings")
    seed = st.number_input(
        "Reproducible seed",
        min_value=0,
        max_value=2_147_483_647,
        value=20260922,
        step=1,
    )
    st.caption("Changing the seed changes examples, not their theoretical odds.")
    st.divider()
    st.markdown("**Fair-draw premise**")
    st.caption(
        "The app describes historical profiles. It does not claim that past draws influence an independent future draw."
    )

if not dataset.is_usable:
    st.error("No valid 6/58 draws were found in the selected file.")
    st.stop()

draws = dataset.draws
metrics, structure, backtest, model_combinations = analyze(draws)
generated = generate_combinations(draws, metrics, seed=int(seed), rules=RULES)

st.markdown('<div class="kicker">Historical draw intelligence</div>', unsafe_allow_html=True)
st.title("Ultra 58 Lab")
st.markdown(
    '<div class="subhead">Audit draw history, challenge selection algorithms against untouched results, and build diversified example lines without confusing historical fit with future probability.</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="odds-strip"><strong>Exact jackpot odds for every valid line:</strong> 1 in {RULES.jackpot_denominator:,}. No score on this page changes that probability.</div>',
    unsafe_allow_html=True,
)

metric_columns = st.columns(4)
metric_columns[0].metric("Validated draws", f"{len(draws):,}")
metric_columns[1].metric(
    "Date coverage",
    f"{draws.iloc[0]['draw_date']:%b}-{draws.iloc[-1]['draw_date']:%b %Y}",
)
metric_columns[2].metric("Rejected rows", len(dataset.rejected))
metric_columns[3].metric(
    "Corrected signals",
    int(metrics["adjusted_p"].lt(0.05).sum()),
    help="Numbers surviving Benjamini-Hochberg correction at 5%.",
)

overview_tab, numbers_tab, structure_tab, backtest_tab, studio_tab, quality_tab = st.tabs(
    ["Overview", "Number Lab", "Structure", "Backtest", "Combination Studio", "Data Quality"]
)

with overview_tab:
    st.header("What the history says")
    st.write(
        "Frequency differences exist in the sample, but a difference becomes evidence only when it survives correction for checking all 58 numbers."
    )
    frequency = metrics.sort_values("number")
    figure = px.bar(
        frequency,
        x="number",
        y="frequency",
        color="z_score",
        color_continuous_scale=["#386d9b", "#e8e6d7", "#c84437"],
        labels={"number": "Number", "frequency": "Appearances", "z_score": "Z-score"},
    )
    figure.add_hline(
        y=float(frequency.iloc[0]["expected"]),
        line_dash="dash",
        line_color="#176b4d",
        annotation_text="Fair-draw expectation",
    )
    figure.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(title="Deviation"),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(figure, use_container_width=True)

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Highest historical scores")
        st.dataframe(
            metrics.head(10)[
                ["number", "historical_score", "frequency", "draws_since_seen", "adjusted_p"]
            ].style.format(
                {"historical_score": "{:.1f}", "adjusted_p": "{:.3f}"}
            ),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        st.subheader("Interpretation")
        st.markdown(
            "- **Historical score:** descriptive blend of frequency, split-half stability, pair participation, and recent coverage.\n"
            "- **Adjusted p-value:** controls false discoveries across 58 number tests.\n"
            "- **Draws since seen:** an absence counter, not evidence that a number is due."
        )

with numbers_tab:
    st.header("All-number audit")
    display_metrics = metrics.copy()
    display_metrics["significant"] = display_metrics["adjusted_p"] < 0.05
    st.dataframe(
        display_metrics.style.format(
            {
                "expected": "{:.2f}",
                "z_score": "{:.2f}",
                "raw_p": "{:.4f}",
                "adjusted_p": "{:.4f}",
                "historical_score": "{:.1f}",
                "stability_score": "{:.1f}",
            }
        ),
        hide_index=True,
        use_container_width=True,
        height=620,
    )
    st.download_button(
        "Download number metrics",
        display_metrics.to_csv(index=False).encode("utf-8"),
        "ultra58-number-metrics.csv",
        "text/csv",
    )

with structure_tab:
    st.header("Draw structure")
    structure_columns = st.columns(4)
    structure_columns[0].metric("Mean sum", f"{structure['mean_sum']:.1f}")
    structure_columns[1].metric("Mean odd count", f"{structure['mean_odd']:.2f}")
    structure_columns[2].metric("Mean low count", f"{structure['mean_low']:.2f}")
    structure_columns[3].metric("Mean adjacent gap", f"{structure['mean_average_gap']:.2f}")

    structure_frame = pd.DataFrame(
        {
            "sum": [sum(values) for values in draws["numbers"]],
            "odd_count": [sum(number % 2 for number in values) for values in draws["numbers"]],
            "low_count": [sum(number <= 29 for number in values) for values in draws["numbers"]],
        }
    )
    chart_left, chart_right = st.columns(2)
    with chart_left:
        sum_figure = px.histogram(
            structure_frame,
            x="sum",
            nbins=16,
            color_discrete_sequence=["#176b4d"],
            labels={"sum": "Draw sum"},
        )
        sum_figure.update_layout(
            title="Historical sum distribution",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(sum_figure, use_container_width=True)
    with chart_right:
        parity_counts = structure_frame["odd_count"].value_counts().sort_index()
        parity_figure = go.Figure(
            go.Bar(
                x=parity_counts.index,
                y=parity_counts.values,
                marker_color="#386d9b",
            )
        )
        parity_figure.update_layout(
            title="Odd numbers per draw",
            xaxis_title="Odd count",
            yaxis_title="Draws",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(parity_figure, use_container_width=True)

with backtest_tab:
    st.header("Did an algorithm beat random selection?")
    if backtest is None:
        st.info("At least 70 valid draws are required for the 30-draw holdout protocol.")
    else:
        st.write(
            "Each rule predicts one line using only earlier draws. The last 30 records remain an untouched holdout; Holm p-values account for testing multiple strategies."
        )
        st.markdown(
            f"**Development:** {backtest.development_range}  ·  "
            f"**Holdout:** {backtest.holdout_range}  ·  "
            f"**Development leader:** {backtest.selected_model}"
        )
        development_column, holdout_column = st.columns(2)
        with development_column:
            st.subheader("Development walk-forward")
            st.dataframe(
                backtest.development.style.format(
                    {"mean_matches": "{:.3f}", "raw_p": "{:.4f}", "holm_p": "{:.4f}"}
                ),
                hide_index=True,
                use_container_width=True,
            )
        with holdout_column:
            st.subheader("Untouched holdout")
            st.dataframe(
                backtest.holdout.style.format(
                    {"mean_matches": "{:.3f}", "raw_p": "{:.4f}", "holm_p": "{:.4f}"}
                ),
                hide_index=True,
                use_container_width=True,
            )
        if backtest.holdout["holm_p"].lt(0.05).any():
            st.warning("A holdout result survived correction. It still requires independent replication.")
        else:
            st.success("No tested rule demonstrated a statistically significant holdout advantage.")
        st.subheader("What each model proposes next")
        st.dataframe(model_combinations, hide_index=True, use_container_width=True)

with studio_tab:
    st.header("Diversified example lines")
    st.write(
        "Profiles organize historical characteristics. Conservative, Balanced, and Diversified are labels for construction rules, not risk or winning probability."
    )
    for profile in generated["profile"].unique():
        st.subheader(str(profile))
        profile_rows = generated[generated["profile"] == profile].drop(columns="profile")
        st.dataframe(
            profile_rows.style.format(
                {
                    "average_gap": "{:.2f}",
                    "historical_score": "{:.1f}",
                    "structural_similarity": "{:.1f}",
                    "profile_score": "{:.1f}",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.download_button(
        "Download generated lines",
        generated.to_csv(index=False).encode("utf-8"),
        f"ultra58-lines-seed-{int(seed)}.csv",
        "text/csv",
    )

with quality_tab:
    st.header("Data quality ledger")
    quality_columns = st.columns(3)
    quality_columns[0].metric("Accepted", len(draws))
    quality_columns[1].metric("Rejected", len(dataset.rejected))
    quality_columns[2].metric("Source", dataset.source_name)
    st.markdown(
        f"Validated date range: **{draws.iloc[0]['draw_date']:%B %d, %Y}** through "
        f"**{draws.iloc[-1]['draw_date']:%B %d, %Y}**."
    )
    if dataset.rejected:
        st.subheader("Rejected rows")
        st.dataframe(
            pd.DataFrame([row.__dict__ for row in dataset.rejected]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.success("No malformed or duplicate rows were detected.")

st.divider()
st.caption(
    "This analysis is intended for educational and entertainment purposes only. Lottery draws remain random, past results do not determine future outcomes, and no model can guarantee winning numbers."
)