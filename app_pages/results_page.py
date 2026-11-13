"""Results page: browse DeepEval runs saved by evaluations/eval_all.py. No API key needed."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from glass import hero
from results import HISTORY_FILE, RUNS_DIR, to_markdown

BAR = "#7c9cff"  # single series: one hue (theme accent, dark surface)
ICON = {"pass": "✅ pass", "fail": "❌ fail", "error": "⚠️ error"}

hero("DeepEval · 7 metrics", "Evaluation results",
     "Scores from saved runs of evaluations/eval_all.py: trace metrics (task completion, "
     "step efficiency, plan quality, plan adherence) and output metrics (argument, tool and "
     "answer correctness). This page only reads saved files; it never calls a model.")

run_files = sorted(RUNS_DIR.glob("*.json"), reverse=True)
if not run_files:
    st.info("No saved runs yet. Run `uv run python evaluations/eval_all.py` to create one.")
    st.stop()

runs = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in run_files}
run_id = st.selectbox("Run", list(runs), format_func=lambda r: runs[r]["timestamp"].replace("T", " "))
run = runs[run_id]
settings = run["settings"]
st.caption(
    f"Agent `{settings.get('agent_model')}` · judge `{settings.get('judge_model')}` · "
    f"{settings.get('test_cases')} test cases · store date {settings.get('store_today')}"
)

results = pd.DataFrame(run["results"])
summary = pd.DataFrame(run["summary"])
thresholds = results.groupby("metric")["threshold"].first()
summary["threshold"] = summary["metric"].map(thresholds)

# --- Headline numbers ------------------------------------------------------------
judged = results[results["status"] != "error"]
c1, c2, c3 = st.columns(3)
c1.metric("Metric checks passed", f"{(judged['status'] == 'pass').sum()} / {len(results)}")
c2.metric("Average score", "n/a" if judged.empty else f"{judged['score'].mean():.2f}")
c3.metric("Errors (rate limit etc.)", int((results["status"] == "error").sum()))

# --- Average score per metric ------------------------------------------------------
st.subheader("Average score per metric")
chart_data = summary.dropna(subset=["average_score"])
base = alt.Chart(chart_data).encode(
    y=alt.Y("metric:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
)
bars = base.mark_bar(color=BAR, cornerRadiusEnd=4, height=18).encode(
    # Domain past 1.0 leaves room for the value label on a full bar.
    x=alt.X("average_score:Q", scale=alt.Scale(domain=[0, 1.12], nice=False),
            axis=alt.Axis(values=[0, 0.25, 0.5, 0.75, 1.0], format=".2f"), title="Average score (0–1)"),
    tooltip=[alt.Tooltip("metric:N", title="Metric"),
             alt.Tooltip("average_score:Q", title="Average", format=".2f"),
             alt.Tooltip("threshold:Q", title="Threshold", format=".2f"),
             alt.Tooltip("passed:Q", title="Passed"),
             alt.Tooltip("failed:Q", title="Failed"),
             alt.Tooltip("errors:Q", title="Errors")],
)
ticks = base.mark_tick(thickness=2, size=26, color="#f4f6ff", opacity=0.9).encode(
    x="threshold:Q", tooltip=[alt.Tooltip("threshold:Q", title="Threshold", format=".2f")],
)
labels = base.mark_text(align="left", dx=8, color="#e8ecf8", fontWeight=600).encode(
    x="average_score:Q", text=alt.Text("average_score:Q", format=".2f"),
)
chart = (
    (bars + ticks + labels)
    .properties(height=40 * max(len(chart_data), 1), background="transparent")
    .configure_view(stroke=None)
    .configure_axis(gridColor="rgba(255,255,255,0.08)", domainColor="rgba(255,255,255,0.2)",
                    labelColor="#c3c9de", titleColor="#a3acc7")
)
st.altair_chart(chart, use_container_width=True, theme=None)
st.caption("Bars are average scores; the thin tick on each row is that metric's pass threshold.")

st.dataframe(
    summary[["metric", "average_score", "threshold", "passed", "failed", "errors"]],
    hide_index=True, use_container_width=True,
    column_config={
        "metric": "Metric",
        "average_score": st.column_config.ProgressColumn("Average score", min_value=0, max_value=1, format="%.2f"),
        "threshold": st.column_config.NumberColumn("Threshold", format="%.2f"),
        "passed": "Passed", "failed": "Failed", "errors": "Errors",
    },
)

# --- Test case x metric grid --------------------------------------------------------
st.subheader("Every test case, every metric")
grid = results.assign(cell=results.apply(
    lambda r: ICON[r["status"]] + ("" if pd.isna(r["score"]) else f" {r['score']:.2f}"), axis=1))
st.dataframe(grid.pivot(index="test_case", columns="metric", values="cell"), use_container_width=True)

# --- Details -------------------------------------------------------------------
st.subheader("Judge's reasons")
for test_case, rows in results.groupby("test_case", sort=False):
    statuses = rows["status"].tolist()
    label = f"{'✅' if all(s == 'pass' for s in statuses) else '❌'} {test_case}"
    with st.expander(label):
        outputs = rows.dropna(subset=["actual_output"])
        if not outputs.empty:
            left, right = st.columns(2)
            left.markdown("**Agent answered**")
            left.info(outputs.iloc[0]["actual_output"])
            right.markdown("**Expected**")
            right.success(outputs.iloc[0]["expected_output"] or "n/a")
        for _, r in rows.iterrows():
            score = "n/a" if pd.isna(r["score"]) else f"{r['score']:.2f}"
            st.markdown(f"**{r['metric']}**: {ICON[r['status']]} · score {score}")
            st.caption(r["reason"] or "No reason given.")

# --- History ---------------------------------------------------------------------
if HISTORY_FILE.exists():
    history = pd.read_csv(HISTORY_FILE)
    if history["run_id"].nunique() > 1:
        st.subheader("Score over runs")
        metric = st.selectbox("Metric", sorted(history["metric"].unique()))
        h = history[history["metric"] == metric].assign(
            timestamp=lambda d: pd.to_datetime(d["timestamp"]))
        line = alt.Chart(h).mark_line(color=BAR, strokeWidth=2, point=alt.OverlayMarkDef(size=64, color=BAR)).encode(
            x=alt.X("timestamp:T", title="Run"),
            y=alt.Y("average_score:Q", scale=alt.Scale(domain=[0, 1]), title=f"{metric} average"),
            tooltip=[alt.Tooltip("timestamp:T", title="Run", format="%Y-%m-%d %H:%M"),
                     alt.Tooltip("average_score:Q", title="Average", format=".2f"),
                     "passed:Q", "failed:Q", "errors:Q"],
        )
        st.altair_chart(line, use_container_width=True)

# --- Downloads --------------------------------------------------------------------
st.subheader("Download")
d1, d2 = st.columns(2)
d1.download_button("Summary (Markdown)", to_markdown(run).encode(), file_name=f"eval_{run_id}.md",
                   use_container_width=True)
d2.download_button("Full run (JSON)", json.dumps(run, indent=2).encode(), file_name=f"eval_{run_id}.json",
                   use_container_width=True)
