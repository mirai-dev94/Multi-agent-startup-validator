# Startup Idea Validator

A multi-agent system that evaluates a product or startup idea from three
independent expert perspectives, then synthesizes them into a single
structured verdict.

## How it works

You submit a short text description of an idea. Three agents evaluate it
**independently**, each with a distinct role:

- **Market Skeptic** — questions real demand, the actual target user, who
  already solves this problem, and why anyone would switch.
- **Technical Evaluator** — assesses feasibility, realistic MVP scope, and
  whether the proposed complexity is proportional to the value.
- **Venture Advocate** — argues the strongest credible version of the idea
  and where the upside is if it works.

A fourth agent, the **Synthesis Agent**, reads all three evaluations and
produces a final verdict: a viability score, top risks, top strengths, and a
recommendation to proceed, pivot, or stop.

Market Skeptic and Technical Evaluator also surface known competitors and a
build-vs-buy take, respectively — currently drawn from the model's own
training knowledge, not live search (see "Search grounding" below for why,
and for the grounded version that exists in the code but isn't active).

## Scope (v2)

Started as a minimal v1; v2 adds explicit-save persistence. In scope:

- Single API endpoint (`/evaluate`), plus a static `index.html` frontend
  that calls it directly from the browser (no build step, no server for
  the frontend itself)
- Three evaluators run one after another (serialized, not concurrent — see
  "Rate limits" below), then one synthesis pass — not a multi-turn debate
  between agents
- Market Skeptic and Technical Evaluator surface competitors / a
  build-vs-buy take from training knowledge (no live search currently —
  see "Search grounding")
- Structured JSON output validated against a fixed schema (Pydantic)
- **Persistence:** evaluations saved to local SQLite on explicit Save click
  — not auto-saved. History panel shows all saves; click any to reload.
  Full detail stored per save. Saves can be deleted. Database file is
  gitignored — evaluation history never gets committed to the public repo.
- Automatic retry with backoff on transient Gemini 503 errors

Explicitly out of scope (possible later iterations):

- Multi-turn agent debate / agents responding to each other
- Search/filter/export within history
- Live web search grounding (built, currently disabled — see below)

## Rate limits

This project runs on Gemini's free tier, which on this project currently
allows **20 requests/day**. Each evaluation uses **4 Gemini calls** (Market
Skeptic, Technical Evaluator, Venture Advocate, Synthesis), so that's **5
evaluations/day** before hitting `RESOURCE_EXHAUSTED` — and a single
transient-error retry on any one call eats into that. Calls are run
serially rather than concurrently to avoid bursting requests. If you hit a
429, check whether it's a per-minute or per-day quota in the error's
`quotaId` field — per-day quotas reset at midnight Pacific Time, regardless
of which timezone you're testing from.

`max_output_tokens` is set to 4096 per call. Ideas that produce richer
panel disagreement (longer risk/strength lists, longer Synthesis reasoning)
can need more tokens than a simpler idea — a too-low limit causes the JSON
to get cut off mid-string, which fails parsing with a "502 malformed
output" error. If this happens, check the uvicorn console for a printed
`RAW AGENT RESPONSE` block (only logged on parse failure) to confirm it's
truncation before raising the limit further.

## Search grounding

The code includes a **search-grounded version** of Market Skeptic and
Technical Evaluator (`_call_agent_grounded`, `MARKET_SKEPTIC_RESEARCH_PROMPT`,
`TECHNICAL_EVALUATOR_RESEARCH_PROMPT`, `TECHNICAL_EVALUATOR_TRIAGE_PROMPT` in
`prompts.py`) that finds real, current competitors via Google Search before
writing the structured evaluation — but it is **not currently used**.

Why: each grounded evaluation needs **two** Gemini calls instead of one
(a free-text research call, then a separate structured-JSON write-up call,
since Gemini's search-tool output isn't meant to be parsed as JSON
directly). That pushed total calls per evaluation to 5-7, which exhausted
the 20/day free-tier quota within a single afternoon of testing. Reverted
to single-call, training-knowledge-only evaluators to keep iterating
without re-hitting the quota wall constantly. Worth re-enabling once
prompt/output quality work has settled down, or on a paid tier with more
daily headroom.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your real GEMINI_API_KEY
uvicorn main:app --reload
```

Then open `index.html` directly in a browser (no server needed for it) to
use the UI, or call the API directly — see below.

## Usage

```bash
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"idea": "A weather-aware mood tracking app with AI-generated daily suggestions"}'
```

Response shape:

```json
{
  "market_skeptic": {
    "summary": "...",
    "key_points": ["..."],
    "stance": "mixed",
    "existing_solutions": "Daylio and Reflectly already handle mood tracking; neither connects it to weather.",
    "build_vs_buy": null
  },
  "technical_evaluator": {
    "summary": "...",
    "key_points": ["..."],
    "stance": "positive",
    "existing_solutions": null,
    "build_vs_buy": "Buying is clearly easier here, because ..."
  },
  "venture_advocate": { "summary": "...", "key_points": ["..."], "stance": "positive" },
  "synthesis": {
    "viability_score": 6,
    "top_risks": ["..."],
    "top_strengths": ["..."],
    "recommendation": "pivot",
    "reasoning": "..."
  }
}
```

`existing_solutions` and `build_vs_buy` are plain strings, always present but
may be `null` — that's expected, not an error, when the model doesn't know of
a relevant competitor/platform or the idea doesn't call for that lens.

## Tests

```bash
pytest
```

Covers JSON-parsing edge cases (markdown-fenced responses, malformed output)
and schema validation, including the new competitor/build-vs-buy fields.
Does not call the real Gemini API — no key needed to run these.

## Stack

FastAPI, Pydantic, Google Gen AI SDK (`google-genai`, async, Gemini models —
the SDK also supports a built-in Google Search grounding tool, present in
the code but not currently active; see "Search grounding" above). Chosen
over Flask for this project because the core workload — agent calls with
strict JSON-schema validation on each response — is exactly what FastAPI +
Pydantic are built for.

## Project structure

```
startup-validator/
├── main.py            # FastAPI app, orchestration, /evaluate endpoint + history endpoints
├── database.py        # SQLite persistence layer (save, list, get, delete evaluations)
├── schemas.py         # Pydantic models for agent + verdict output
├── prompts.py         # System prompts for all agents + research/triage steps
├── index.html         # Static frontend (no build step, no server needed)
├── test_main.py       # Unit tests (parsing, schema validation, database layer)
├── requirements.txt
├── .env.example
└── .gitignore
```
