#!/usr/bin/env python3
"""
batch_score.py

Batch-scores customer support transcripts against the rubric in SKILL.md / rubric.json
using the Anthropic API as an LLM judge.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python batch_score.py --input-dir ./raw_transcripts --output ./results/scores.jsonl

Input format:
    Each file in --input-dir should be a raw .txt call transcript in the format
    parse_raw_transcripts.py understands (header + call metadata + system init +
    timestamped timeline with [SYS] action/error notes). Transcripts are parsed
    on the fly -- there's no separate JSON intermediate to keep in sync.

    Legacy .json transcripts shaped like
    {"transcript_id": "...", "transcript": [{"role": "customer", "text": "..."}, ...]}
    are still supported for backward compatibility.

Output:
    A .jsonl file (one JSON object per line) with the judge's scores for each transcript,
    plus a summary .csv for quick spreadsheet review.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Missing dependency. Install with: pip install anthropic --break-system-packages", file=sys.stderr)
    sys.exit(1)

from parse_raw_transcripts import parse_transcript_file

MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def load_skill_instructions() -> str:
    """Load the rubric + judging instructions from SKILL.md so the script and the
    Claude Code skill always score against the exact same rubric."""
    skill_path = PROJECT_ROOT / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    # Strip the YAML frontmatter (between the two --- lines) - we just want the body.
    parts = text.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return text.strip()


ROLE_LABELS = {"agent": "AGENT", "customer": "CUSTOMER", "system": "[SYS]"}


def format_transcript(transcript: list) -> str:
    """Legacy schema: a flat list of {role, text} turns, no timestamps or system context."""
    lines = []
    for turn in transcript:
        role = turn.get("role", "unknown")
        text = turn.get("text", "")
        lines.append(f"{role.upper()}: {text}")
    return "\n".join(lines)


def format_timeline(timeline: list) -> str:
    """Current schema: timestamped turns that may include role=system entries
    (backend action calls/results) interleaved with the agent/customer dialogue."""
    lines = []
    for turn in timeline:
        role = turn.get("role", "unknown")
        label = ROLE_LABELS.get(role, role.upper())
        text = turn.get("text", "")
        ts = turn.get("timestamp")
        prefix = f"[{ts}] " if ts else ""
        lines.append(f"{prefix}{label}: {text}")
    return "\n".join(lines)


def build_prompt(transcript_id: str, data: dict) -> str:
    if "timeline" in data:
        context_parts = []
        if data.get("scenario"):
            context_parts.append(f"Scenario: {data['scenario']}")
        if data.get("call_outcome"):
            context_parts.append(f"Call outcome (system-recorded): {data['call_outcome']}")
        if data.get("call_metadata"):
            meta_lines = "\n".join(f"  {k}: {v}" for k, v in data["call_metadata"].items())
            context_parts.append(f"Call metadata:\n{meta_lines}")
        if data.get("system_init"):
            context_parts.append(f"System initialization (backend ground truth):\n{data['system_init']}")
        context_block = "\n\n".join(context_parts)

        transcript_text = format_timeline(data["timeline"])

        return (
            f"Transcript ID: {transcript_id}\n\n"
            f"--- SYSTEM CONTEXT (ground truth, not visible to the customer) ---\n{context_block}\n\n"
            f"--- CONVERSATION TIMELINE (dialogue interleaved with [SYS] backend notes) ---\n{transcript_text}\n\n"
            "Score this transcript now. Cross-check agent claims against the [SYS] context per "
            "the 'Using System Context' and 'Automatic Fail Conditions' sections. Respond with ONLY "
            "the JSON object described in the Required Output Format section -- no markdown fences, "
            "no extra commentary."
        )

    transcript_text = format_transcript(data.get("transcript", []))
    return (
        f"Transcript ID: {transcript_id}\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        "Score this transcript now. Respond with ONLY the JSON object described in the "
        "Required Output Format section -- no markdown fences, no extra commentary."
    )


def score_transcript(client: anthropic.Anthropic, system_prompt: str, transcript_id: str, data: dict) -> dict:
    user_prompt = build_prompt(transcript_id, data)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()

            # Defensive cleanup in case the model wraps the JSON in fences anyway.
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`")
                if raw_text.lower().startswith("json"):
                    raw_text = raw_text[4:].strip()

            return json.loads(raw_text)

        except (anthropic.APIError, json.JSONDecodeError) as e:
            last_error = e
            print(f"  [warn] attempt {attempt}/{MAX_RETRIES} failed for {transcript_id}: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    return {
        "transcript_id": transcript_id,
        "error": f"Failed after {MAX_RETRIES} attempts: {last_error}",
    }


def main():
    parser = argparse.ArgumentParser(description="Batch-score transcripts with the transcript-judge rubric.")
    parser.add_argument("--input-dir", required=True, help="Directory of raw .txt (or legacy .json) transcript files.")
    parser.add_argument("--output", default="results/scores.jsonl", help="Path to write JSONL results.")
    parser.add_argument("--csv", default=None, help="Optional path to also write a summary CSV.")
    parser.add_argument("--html", default=None, help="Optional path to also write an HTML report (e.g. results/report.html).")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = load_skill_instructions()

    input_dir = Path(args.input_dir)
    txt_files = sorted(input_dir.glob("*.txt"))
    json_files = sorted(input_dir.glob("*.json"))
    if not txt_files and not json_files:
        print(f"No .txt or .json transcript files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = txt_files + json_files
    results = []
    with output_path.open("w", encoding="utf-8") as out_f:
        for i, file_path in enumerate(files, start=1):
            if file_path.suffix == ".txt":
                data = parse_transcript_file(file_path)
            else:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            transcript_id = data.get("transcript_id", file_path.stem)

            print(f"[{i}/{len(files)}] Scoring {transcript_id} ...")
            result = score_transcript(client, system_prompt, transcript_id, data)
            results.append(result)
            out_f.write(json.dumps(result) + "\n")

    print(f"\nDone. Wrote {len(results)} results to {output_path}")

    csv_path = args.csv or str(output_path.with_suffix(".csv"))
    write_csv_summary(results, csv_path)
    print(f"Wrote summary CSV to {csv_path}")

    if args.html:
        from generate_html_report import load_results, render_report
        html_results = load_results(output_path)
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_report(html_results), encoding="utf-8")
        print(f"Wrote HTML report to {html_path}")


def write_csv_summary(results: list, csv_path: str):
    dimension_keys = ["resolution", "accuracy", "empathy_tone", "policy_adherence", "clarity", "efficiency"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["transcript_id", *dimension_keys, "overall_score", "verdict", "summary", "error"])
        for r in results:
            if "error" in r and "scores" not in r:
                writer.writerow([r.get("transcript_id", ""), *["" for _ in dimension_keys], "", "", "", r["error"]])
                continue
            scores = r.get("scores", {})
            row = [r.get("transcript_id", "")]
            row += [scores.get(k, {}).get("score", "") for k in dimension_keys]
            row += [r.get("overall_score", ""), r.get("verdict", ""), r.get("summary", ""), ""]
            writer.writerow(row)


if __name__ == "__main__":
    main()
