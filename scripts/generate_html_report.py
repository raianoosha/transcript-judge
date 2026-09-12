#!/usr/bin/env python3
"""
generate_html_report.py

Turns a scores.jsonl file (output of batch_score.py) into a single self-contained
HTML report: one section per transcript, dimension scores as bars, verdict badges,
and evidence/summary text.

Usage:
    python generate_html_report.py --input results/scores.jsonl --output results/report.html
"""

import argparse
import html
import json
from pathlib import Path
from datetime import datetime, timezone

DIMENSION_LABELS = {
    "resolution": "Issue Resolution",
    "accuracy": "Accuracy",
    "empathy_tone": "Empathy & Tone",
    "policy_adherence": "Policy Adherence",
    "clarity": "Clarity",
    "efficiency": "Efficiency",
}

VERDICT_STYLE = {
    "pass": {"label": "Pass", "color": "#2F6F4E", "bg": "#EAF3EC"},
    "needs_review": {"label": "Needs review", "color": "#9A6B12", "bg": "#FBF1DD"},
    "fail": {"label": "Fail", "color": "#A83A3A", "bg": "#FBEAEA"},
}


def load_results(path: Path) -> list:
    results = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def score_bar(score: int, max_score: int = 5) -> str:
    pct = round((score / max_score) * 100)
    color = "#2F6F4E" if score >= 4 else ("#9A6B12" if score == 3 else "#A83A3A")
    return (
        f'<div class="bar-track">'
        f'<div class="bar-fill" style="width:{pct}%; background:{color};"></div>'
        f'</div>'
    )


def render_transcript(result: dict, index: int) -> str:
    tid = html.escape(str(result.get("transcript_id", f"transcript_{index}")))

    if "error" in result and "scores" not in result:
        return f"""
        <section class="card errored">
          <div class="card-head">
            <h2>{tid}</h2>
            <span class="badge" style="color:#A83A3A; background:#FBEAEA;">Error</span>
          </div>
          <p class="error-text">{html.escape(result["error"])}</p>
        </section>
        """

    scores = result.get("scores", {})
    verdict = result.get("verdict", "needs_review")
    v_style = VERDICT_STYLE.get(verdict, VERDICT_STYLE["needs_review"])
    overall = result.get("overall_score", "")
    summary = html.escape(result.get("summary", ""))

    rows = []
    for key, label in DIMENSION_LABELS.items():
        dim = scores.get(key, {})
        s = dim.get("score", 0)
        evidence = html.escape(dim.get("evidence", ""))
        rows.append(f"""
          <div class="dim-row">
            <div class="dim-label">
              <span>{label}</span>
              <span class="dim-score">{s}/5</span>
            </div>
            {score_bar(int(s) if s else 0)}
            <p class="evidence">{evidence}</p>
          </div>
        """)

    return f"""
    <section class="card">
      <div class="card-head">
        <h2>{tid}</h2>
        <span class="badge" style="color:{v_style['color']}; background:{v_style['bg']};">
          {v_style['label']} &middot; {overall}/5
        </span>
      </div>
      <p class="summary">{summary}</p>
      <div class="dims">
        {''.join(rows)}
      </div>
    </section>
    """


def render_failed_evidence(result: dict) -> str:
    tid = html.escape(str(result.get("transcript_id", "")))
    overall = result.get("overall_score", "")
    summary = html.escape(result.get("summary", ""))
    scores = result.get("scores", {})

    rows = []
    for key, label in DIMENSION_LABELS.items():
        dim = scores.get(key, {})
        s = dim.get("score", "")
        evidence = html.escape(dim.get("evidence", ""))
        if not evidence:
            continue
        rows.append(f"""
          <li><strong>{label} ({s}/5):</strong> {evidence}</li>
        """)

    return f"""
    <div class="failed-item">
      <h3>{tid} <span class="failed-score">{overall}/5</span></h3>
      <p class="summary">{summary}</p>
      <ul class="evidence-list">
        {''.join(rows)}
      </ul>
    </div>
    """


def render_failed_section(results: list) -> str:
    failed = [r for r in results if r.get("verdict") == "fail" and "scores" in r]
    if not failed:
        return ""

    items = "".join(render_failed_evidence(r) for r in failed)
    return f"""
    <section class="failed-section">
      <h2>Failed Transcripts &mdash; Judge's Evidence</h2>
      {items}
    </section>
    """


def render_report(results: list) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total = len(results)
    verdict_counts = {"pass": 0, "needs_review": 0, "fail": 0, "error": 0}
    overall_scores = []
    for r in results:
        if "error" in r and "scores" not in r:
            verdict_counts["error"] += 1
            continue
        v = r.get("verdict", "needs_review")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        if isinstance(r.get("overall_score"), (int, float)):
            overall_scores.append(r["overall_score"])

    avg_score = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else "n/a"

    summary_chips = "".join(
        f'<div class="chip"><span class="chip-num">{verdict_counts[k]}</span>'
        f'<span class="chip-label">{VERDICT_STYLE[k]["label"] if k in VERDICT_STYLE else "Errors"}</span></div>'
        for k in ["pass", "needs_review", "fail", "error"] if verdict_counts.get(k)
    )

    sections = "".join(render_transcript(r, i) for i, r in enumerate(results, start=1))
    failed_section = render_failed_section(results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Transcript Judge Report</title>
<style>
  :root {{
    --ink: #1E1D1B;
    --paper: #FAF9F6;
    --line: #E1DDD3;
    --muted: #6B675E;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: Georgia, 'Times New Roman', serif;
    line-height: 1.5;
  }}
  .wrap {{
    max-width: 760px;
    margin: 0 auto;
    padding: 56px 24px 96px;
  }}
  header.top {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 20px;
    margin-bottom: 32px;
  }}
  header.top h1 {{
    font-size: 30px;
    margin: 0 0 6px;
    font-weight: 400;
    letter-spacing: -0.01em;
  }}
  header.top .meta {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: var(--muted);
  }}
  .summary-row {{
    display: flex;
    gap: 28px;
    align-items: baseline;
    margin: 28px 0 40px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .summary-row .avg {{
    font-size: 40px;
    line-height: 1;
  }}
  .summary-row .avg-label {{
    font-size: 12px;
    color: var(--muted);
    display: block;
    margin-top: 6px;
  }}
  .chips {{
    display: flex;
    gap: 18px;
  }}
  .chip {{
    display: flex;
    flex-direction: column;
  }}
  .chip-num {{
    font-size: 20px;
  }}
  .chip-label {{
    font-size: 11px;
    color: var(--muted);
  }}
  .card {{
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 24px 28px;
    margin-bottom: 20px;
    background: white;
  }}
  .card.errored {{
    background: #FFFBF9;
  }}
  .card-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .card-head h2 {{
    font-size: 18px;
    font-weight: 400;
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .badge {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }}
  .summary {{
    color: var(--ink);
    margin: 14px 0 20px;
    font-size: 15px;
  }}
  .error-text {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    color: #A83A3A;
    font-size: 14px;
  }}
  .dims {{
    display: grid;
    gap: 16px;
  }}
  .dim-row {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .dim-label {{
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    margin-bottom: 5px;
  }}
  .dim-score {{
    color: var(--muted);
  }}
  .bar-track {{
    height: 6px;
    background: var(--line);
    border-radius: 3px;
    overflow: hidden;
  }}
  .bar-fill {{
    height: 100%;
  }}
  .evidence {{
    font-size: 13px;
    color: var(--muted);
    margin: 6px 0 0;
  }}
  .failed-section {{
    border: 1px solid #E7C2C2;
    background: #FFF8F7;
    border-radius: 3px;
    padding: 24px 28px;
    margin-bottom: 32px;
  }}
  .failed-section h2 {{
    font-size: 18px;
    font-weight: 400;
    margin: 0 0 18px;
    color: #A83A3A;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .failed-item {{
    padding: 14px 0;
    border-top: 1px solid #E7C2C2;
  }}
  .failed-item:first-of-type {{
    border-top: none;
    padding-top: 0;
  }}
  .failed-item h3 {{
    font-size: 15px;
    font-weight: 600;
    margin: 0 0 6px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  }}
  .failed-score {{
    font-weight: 400;
    color: var(--muted);
    font-size: 13px;
  }}
  .evidence-list {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: var(--ink);
    margin: 8px 0 0;
    padding-left: 20px;
  }}
  .evidence-list li {{
    margin-bottom: 6px;
  }}
  @media (max-width: 600px) {{
    .wrap {{ padding: 32px 16px 64px; }}
    .summary-row {{ flex-wrap: wrap; gap: 20px; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="top">
      <h1>Transcript Judge Report</h1>
      <div class="meta">Generated {generated_at} &middot; {total} transcript{'s' if total != 1 else ''} scored</div>
    </header>

    <div class="summary-row">
      <div>
        <div class="avg">{avg_score}</div>
        <div class="avg-label">avg overall score</div>
      </div>
      <div class="chips">{summary_chips}</div>
    </div>

    {failed_section}

    {sections}
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Generate an HTML report from transcript-judge scores.jsonl")
    parser.add_argument("--input", required=True, help="Path to scores.jsonl")
    parser.add_argument("--output", default="results/report.html", help="Path to write the HTML report")
    args = parser.parse_args()

    input_path = Path(args.input)
    results = load_results(input_path)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(results), encoding="utf-8")

    print(f"Wrote HTML report for {len(results)} transcripts to {output_path}")


if __name__ == "__main__":
    main()
