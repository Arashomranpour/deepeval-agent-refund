"""Save each evaluation run to evaluations/results/ so it can be compared and shown.

Files written per run:
    results/runs/<run_id>.json   full run: settings + one row per test case x metric
    results/latest.json          copy of the most recent run (read by the Streamlit app)
    results/latest.md            summary table for the README / GitHub
    results/history.csv          one row per run x metric (average score, pass rate)
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from deepeval.test_run.test_run import LATEST_FULL_TEST_RUN_FILE_PATH

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RUNS_DIR = RESULTS_DIR / "runs"
HISTORY_FILE = RESULTS_DIR / "history.csv"
HISTORY_FIELDS = ["run_id", "timestamp", "metric", "average_score", "passed", "failed", "errors", "total"]


def read_latest_deepeval_run(metric_type: str) -> list[dict]:
    """Rows from the run DeepEval just finished (it rewrites this snapshot every run)."""
    path = Path(LATEST_FULL_TEST_RUN_FILE_PATH)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    run = data.get("testRun", data)
    rows = []
    for case in run.get("testCases", []):
        for metric in case.get("metricsData") or []:
            error = metric.get("error")
            success = metric.get("success")
            rows.append({
                "test_case": case.get("input") or case.get("name"),
                "metric": metric["name"].replace(" [GEval]", ""),
                "metric_type": metric_type,
                "score": metric.get("score"),
                "threshold": metric.get("threshold"),
                "status": "error" if error else ("pass" if success else "fail"),
                "reason": error or metric.get("reason"),
                "actual_output": case.get("actualOutput"),
                "expected_output": case.get("expectedOutput"),
            })
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    summary = {}
    for row in rows:
        s = summary.setdefault(row["metric"], {"metric": row["metric"], "scores": [],
                                               "passed": 0, "failed": 0, "errors": 0})
        if row["status"] == "error" or row["score"] is None:
            s["errors"] += 1
        else:
            s["scores"].append(row["score"])
            s["passed" if row["status"] == "pass" else "failed"] += 1
    out = []
    for s in summary.values():
        scores = s.pop("scores")
        s["average_score"] = round(sum(scores) / len(scores), 3) if scores else None
        s["total"] = s["passed"] + s["failed"] + s["errors"]
        out.append(s)
    return out


def save_run(rows: list[dict], settings: dict) -> Path:
    now = datetime.now()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    summary = summarize(rows)
    run = {"run_id": run_id, "timestamp": now.isoformat(timespec="seconds"),
           "settings": settings, "summary": summary, "results": rows}

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=2, ensure_ascii=False)
    run_file = RUNS_DIR / f"{run_id}.json"
    run_file.write_text(text, encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(text, encoding="utf-8")
    (RESULTS_DIR / "latest.md").write_text(to_markdown(run), encoding="utf-8")

    new_file = not HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        for s in summary:
            writer.writerow({"run_id": run_id, "timestamp": run["timestamp"],
                             **{k: s[k] for k in HISTORY_FIELDS[2:]}})
    return run_file


def to_markdown(run: dict) -> str:
    st = run["settings"]
    lines = [
        f"# Evaluation results: {run['run_id']}",
        "",
        f"Agent `{st.get('agent_model')}`, judged by `{st.get('judge_model')}`. "
        f"{st.get('test_cases')} test cases, store date {st.get('store_today')}.",
        "",
        "| Metric | Average score | Passed | Failed | Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for s in run["summary"]:
        avg = "n/a" if s["average_score"] is None else f"{s['average_score']:.2f}"
        lines.append(f"| {s['metric']} | {avg} | {s['passed']} | {s['failed']} | {s['errors']} |")
    lines += ["", "## Per test case", "", "| Test case | Metric | Score | Result |", "|---|---|---:|---|"]
    icon = {"pass": "✅ pass", "fail": "❌ fail", "error": "⚠️ error"}
    for r in run["results"]:
        score = "n/a" if r["score"] is None else f"{r['score']:.2f}"
        lines.append(f"| {r['test_case']} | {r['metric']} | {score} | {icon[r['status']]} |")
    return "\n".join(lines) + "\n"
