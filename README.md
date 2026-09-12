# Transcript Judge

An LLM-as-judge project for scoring customer support conversation transcripts against a fixed rubric. Works two ways:

1. **As a Claude Code skill** — drop `SKILL.md` into `.claude/skills/transcript-judge/` in any repo, and Claude Code will use it whenever you ask it to judge, score, or review a support transcript.
2. **As a standalone batch scorer** — `scripts/batch_score.py` calls the Anthropic API directly to score many transcripts at once and writes results to JSONL + CSV.

## Project structure

```
transcript-judge/
├── SKILL.md                     # Rubric + judging instructions (source of truth)
├── rubric.json                  # Same rubric in structured form, for programmatic use
├── examples/                    # Calibration examples (gold-scored transcripts)
│   ├── example_strong.json
│   └── example_weak.json
├── raw_transcripts/             # Source call transcripts (.txt), the only input the scorer needs
├── scripts/
│   ├── batch_score.py           # Batch scoring script (calls Anthropic API)
│   ├── parse_raw_transcripts.py # Parses raw .txt transcripts into the judge's prompt format
│   └── generate_html_report.py  # Turns scores.jsonl into a readable HTML report
├── results/                     # Output directory for batch runs (created automatically)
└── README.md
```

`raw_transcripts/*.txt` is parsed on the fly by `batch_score.py` (via `parse_raw_transcripts.py`) — there's no separate JSON copy to keep in sync. If you add or edit a raw transcript, the next run picks it up automatically.

## Option 1: Use as a Claude Code skill

Copy the skill folder into your project:

```bash
mkdir -p .claude/skills/transcript-judge
cp SKILL.md .claude/skills/transcript-judge/
cp -r examples .claude/skills/transcript-judge/
```

Then in Claude Code, just paste a transcript and ask something like:
> "Score this support transcript" or "How did this agent do?"

Claude Code will load the skill and return the structured JSON scores.

## Option 2: Batch-score with the Python script

1. Install the dependency:
   ```bash
   pip install anthropic --break-system-packages
   ```
2. Set your API key:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Put your raw call transcripts in a folder as individual `.txt` files, following the format `parse_raw_transcripts.py` expects: a header block, call metadata, system initialization, and a timestamped conversation timeline with `[SYS]` action/error notes (see `raw_transcripts/` for real examples). This is what preserves the backend ground truth (order data, action success/failure, internal-only fields) that the judge cross-checks agent claims against.

   Legacy flat-dialogue `.json` transcripts (`{"transcript_id": ..., "transcript": [{"role": ..., "text": ...}, ...]}`, see `examples/example_strong.json`) are still supported, but without system context the judge can only score what's said, not verify it.
4. Run:
   ```bash
   python scripts/batch_score.py --input-dir ./raw_transcripts --output ./results/scores.jsonl
   ```
   This writes:
   - `results/scores.jsonl` — one full JSON judgment per line
   - `results/scores.csv` — a flattened summary for quick review in a spreadsheet

   Add `--html ./results/report.html` to also generate a readable HTML report (score bars, verdict badges, evidence, per transcript):
   ```bash
   python scripts/batch_score.py --input-dir ./raw_transcripts --output ./results/scores.jsonl --html ./results/report.html
   ```

The script reads the rubric directly out of `SKILL.md`, so the skill and the batch script are always scoring against the exact same criteria — edit `SKILL.md` once and both stay in sync.

## Generating an HTML report on its own

If you already have a `scores.jsonl` (from a previous run) and just want the report:
```bash
python scripts/generate_html_report.py --input results/scores.jsonl --output results/report.html
```
This is a single self-contained HTML file (no external assets) — open it directly in a browser, or attach it to an email/Slack message for a quick visual QA summary. It shows an overall average score, a pass/needs_review/fail breakdown, and a card per transcript with bar-charted dimension scores and the evidence the judge cited.

## Calibrating the rubric

Before scoring a real batch, read `examples/example_strong.json` and `examples/example_weak.json`. These are gold-labeled transcripts showing what a 5 vs. a 1 actually looks like on each dimension. If your team's judgments diverge from these anchors, edit the anchor text in `SKILL.md` (and mirror the change in `rubric.json`) rather than changing individual scores after the fact — that keeps the judge consistent across runs.

## Adjusting verdict thresholds

The pass/needs_review/fail cutoffs are defined at the bottom of `SKILL.md` under "Overall Verdict" and mirrored in `rubric.json`'s `verdict_thresholds`. These are a reasonable starting default (pass ≥ 4.0 with no dimension ≤ 2) — tighten or loosen them once you've scored a real batch and see where your team agrees/disagrees with the judge.

## Next steps / ideas to extend

- Add a second rubric variant (e.g., `rubric_sales.json` + a `SKILL.md` reference file) if you later want to judge a different conversation type.
- Add inter-rater reliability checks by having a human score the same sample and comparing to the judge's output.
- Swap `batch_score.py` to use the Batches API if you're scoring hundreds/thousands of transcripts, to cut cost.
