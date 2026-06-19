# Startup Idea Validator

A multi-agent system that evaluates a product or startup idea from three
independent expert perspectives, then synthesizes them into a single
structured verdict.

## How it works

You submit a short text description of an idea. Three agents evaluate it
**independently and concurrently**, each with a distinct role:

- **Market Skeptic** — questions real demand, the actual target user, who
  already solves this problem, and why anyone would switch.
- **Technical Evaluator** — assesses feasibility, realistic MVP scope, and
  whether the proposed complexity is proportional to the value.
- **Venture Advocate** — argues the strongest credible version of the idea
  and where the upside is if it works.

A fourth agent, the **Synthesis Agent**, reads all three evaluations and
produces a final verdict: a viability score, top risks, top strengths, and a
recommendation to proceed, pivot, or stop.

## Scope (v1)

This is a deliberately minimal first version. In scope:

- Single API endpoint, no frontend
- Three evaluators run independently and concurrently, then one synthesis
  pass — not a multi-turn debate between agents
- Structured JSON output validated against a fixed schema (Pydantic)
- No persistence — stateless, one idea in, one verdict out

Explicitly out of scope for v1 (possible later iterations):

- Multi-turn agent debate / agents responding to each other
- Web search or external market-research grounding
- A frontend or saved evaluation history
- Batch evaluation or idea comparison

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your real GEMINI_API_KEY
uvicorn main:app --reload
```

## Usage

```bash
curl -X POST http://127.0.0.1:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"idea": "A weather-aware mood tracking app with AI-generated daily suggestions"}'
```

Response shape:

```json
{
  "market_skeptic": { "summary": "...", "key_points": ["..."], "stance": "mixed" },
  "technical_evaluator": { "summary": "...", "key_points": ["..."], "stance": "positive" },
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

## Tests

```bash
pytest
```

Covers JSON-parsing edge cases (markdown-fenced responses, malformed output)
and schema validation. Does not call the real Gemini API.

## Stack

FastAPI, Pydantic, Google Gen AI SDK (`google-genai`, async, Gemini models).
Chosen over Flask for this project because the core workload — concurrent
agent calls with strict JSON-schema validation on each response — is exactly
what FastAPI + Pydantic are built for.

## Project structure

```
startup-validator/
├── main.py           # FastAPI app, orchestration, /evaluate endpoint
├── schemas.py         # Pydantic models for agent + verdict output
├── prompts.py         # System prompts for the four agents
├── test_main.py       # Unit tests (parsing + schema validation)
├── requirements.txt
├── .env.example
└── .gitignore
```
