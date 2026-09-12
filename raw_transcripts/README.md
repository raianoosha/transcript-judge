# CallBuddy AI Voice Agent — QA Transcript Pack

This folder contains **8 sample call transcripts** for a QA review exercise. Each
file captures a full call between a **Caller** and the **AI Agent**, plus the
**System** activity (variables set, actions/tool calls, and their results) that
happened behind the scenes.

The transcripts are plain `.txt` so they render cleanly in any editor and export
neatly to PDF (use a monospaced font like Menlo / Courier / Consolas when
converting so the alignment holds).

> **All data in this pack is synthetic / fictional** — every name, phone number,
> email, order/tracking ID, and product is fabricated for this exercise. Details
> are written to look like a real production call log; none of it maps to an
> actual customer, order, or payment.

## The exercise

Review the 8 calls and write a short QA report: for each call, give your assessment
of how the AI agent handled it. Aim to spend ~60–90 minutes; we'll discuss your
report live.

## Files

| File                                | Scenario                    |
|-------------------------------------|-----------------------------|
| `conversation-01-return.txt`          | Order return                |
| `conversation-02-order-tracking.txt`        | Order tracking / status     |
| `conversation-03-cancel-order.txt`          | Order cancellation          |
| `conversation-04-place-order.txt`       | Product inquiry + new order |
| `conversation-05-billing-dispute.txt`      | Escalation to live agent    |
| `conversation-06-account-update.txt`  | Email update + rewards      |
| `conversation-07-reschedule-delivery.txt` | Delivery reschedule         |
| `conversation-08-order-status.txt`      | Order lookup                |

## How to read a transcript

Each file has four sections:

```
1. HEADER        — transcript id, scenario, outcome, timing.
2. CALL METADATA — the inbound call details and caller-on-file info.
3. SYSTEM INIT   — variables and actions set up before/at the greeting.
4. TIMELINE      — the turn-by-turn conversation, interleaved with system notes.
```

Line-prefix legend used in the TIMELINE:

```
AI AGENT >   spoken by the AI voice agent
CALLER   >   spoken by the human caller
[SYS]        system note — variable set/updated, action call, or tool result
[TIME]       wall-clock timestamp for the following turn
```

## What your report should include

For each point you raise, capture something like:

```
call id | timestamp | severity | observation | evidence (quote the relevant line)
```

Use whatever severity scale you're comfortable with (e.g. Critical / High /
Medium / Low) and note briefly why you rated each finding the way you did.

Submit your report in any format you like (doc, spreadsheet, or plain text). We'll
walk through it together in the live session.
