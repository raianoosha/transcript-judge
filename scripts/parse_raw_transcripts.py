#!/usr/bin/env python3
"""
parse_raw_transcripts.py

Converts the raw .txt call transcripts (header + call metadata +
system init + timestamped timeline with [SYS] action/error notes) into the
project's transcript JSON schema, preserving timestamps and system context
so the judge can cross-check agent claims against backend ground truth.

Usage:
    python parse_raw_transcripts.py --input-dir ./raw_transcripts --output-dir ./transcripts
"""

import argparse
import json
import re
from pathlib import Path

TIMESTAMP_RE = re.compile(r"\[(\d{1,2}:\d{2}:\d{2}\s*[AP]M)\]")
DIALOGUE_RE = re.compile(r"^\s*(AI AGENT|CALLER)\s*>\s*(.*)$")
KV_RE = re.compile(r"^([A-Za-z][A-Za-z ]*?)\s{2,}:\s*(.*)$")
SECTION_RE = re.compile(r"^-{10,}$")

ROLE_MAP = {"AI AGENT": "agent", "CALLER": "customer"}


def split_sections(text: str) -> dict:
    """Split the file into header / call_metadata / system_init / timeline sections."""
    lines = text.splitlines()
    sections = {"header": [], "call_metadata": [], "system_init": [], "timeline": []}
    current = "header"
    section_titles = {
        "CALL METADATA": "call_metadata",
        "SYSTEM INITIALIZATION  (Actions & Variables)": "system_init",
        "CONVERSATION TIMELINE": "timeline",
    }
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped in section_titles and i + 1 < len(lines) and SECTION_RE.match(lines[i + 1].strip()):
            current = section_titles[stripped]
            i += 2
            continue
        if SECTION_RE.match(stripped):
            i += 1
            continue
        sections[current].append(line)
        i += 1
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def parse_header(text: str) -> dict:
    fields = {}
    for line in text.splitlines():
        m = KV_RE.match(line)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def parse_call_metadata(text: str) -> dict:
    return parse_header(text)


def parse_timeline(text: str) -> list:
    """Group the timeline into turns keyed by timestamp, each with dialogue
    (role + text) and any raw [SYS] notes that occurred around that turn."""
    parts = TIMESTAMP_RE.split(text)
    # parts[0] is any leading text before the first timestamp (should be empty/blank)
    turns = []
    leading = parts[0].strip()
    if leading:
        turns.append({"timestamp": None, "role": "system", "text": leading})

    for i in range(1, len(parts), 2):
        timestamp = parts[i].strip()
        block = parts[i + 1] if i + 1 < len(parts) else ""
        block_lines = block.splitlines()

        dialogue_role = None
        dialogue_lines = []
        sys_lines = []
        collecting_dialogue = False

        for line in block_lines:
            m = DIALOGUE_RE.match(line)
            if m:
                dialogue_role = ROLE_MAP.get(m.group(1), m.group(1).lower())
                dialogue_lines.append(m.group(2).strip())
                collecting_dialogue = True
                continue
            if line.strip().startswith("[SYS]"):
                collecting_dialogue = False
                sys_lines.append(line.strip()[len("[SYS]"):].strip())
                continue
            if not line.strip():
                collecting_dialogue = False
                continue
            if collecting_dialogue:
                dialogue_lines.append(line.strip())
            elif sys_lines:
                sys_lines[-1] += " " + line.strip()

        if dialogue_role:
            turns.append({
                "timestamp": timestamp,
                "role": dialogue_role,
                "text": " ".join(dialogue_lines).strip(),
            })
        for sys_note in sys_lines:
            turns.append({
                "timestamp": timestamp,
                "role": "system",
                "text": sys_note.strip(),
            })

    return turns


FOOTER_RE = re.compile(r"={10,}\s*$")


def parse_transcript_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    text = FOOTER_RE.sub("", text).strip()
    sections = split_sections(text)
    header = parse_header(sections["header"])
    call_metadata = parse_call_metadata(sections["call_metadata"])
    timeline = parse_timeline(sections["timeline"])

    return {
        "transcript_id": path.stem,
        "scenario": header.get("SCENARIO", ""),
        "call_date": header.get("CALL DATE", ""),
        "duration": header.get("DURATION", ""),
        "call_outcome": header.get("CALL OUTCOME", ""),
        "call_reason": header.get("CALL REASON", ""),
        "call_metadata": call_metadata,
        "system_init": sections["system_init"],
        "timeline": timeline,
    }


def main():
    parser = argparse.ArgumentParser(description="Parse raw .txt call transcripts into transcript-judge JSON.")
    parser.add_argument("--input-dir", required=True, help="Directory of raw .txt transcripts.")
    parser.add_argument("--output-dir", required=True, help="Directory to write .json transcripts to.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.txt"))
    if not files:
        print(f"No .txt files found in {input_dir}")
        return

    for f in files:
        data = parse_transcript_file(f)
        out_path = output_dir / f"{f.stem}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote {out_path} ({len(data['timeline'])} timeline entries)")


if __name__ == "__main__":
    main()
