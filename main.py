"""
Startup Idea Validator — v1.1

Pipeline (4 Gemini calls total per evaluation, run one after another):
  1. Market Skeptic and Technical Evaluator each run a single structured
     call (no search) — competitors and build-vs-buy notes are drawn from
     the model's own training knowledge, not live lookup. 1 call each.
     Search-grounded versions exist (_call_agent_grounded,
     MARKET_SKEPTIC_RESEARCH_PROMPT, TECHNICAL_EVALUATOR_RESEARCH_PROMPT,
     TECHNICAL_EVALUATOR_TRIAGE_PROMPT) but are currently unused — reverted
     to stay within Gemini's free-tier daily quota (20 requests/day on
     this project) while iterating on prompts/output quality. Revisit if
     moving to a paid tier or once development has slowed down.
  2. Venture Advocate runs a single structured call, no search. 1 call.
  3. The Synthesis Agent receives the idea + all three evaluations and
     produces a final structured verdict. 1 call.

Rate limits: calls are run serially (not via asyncio.gather) and retry
automatically on transient 503 (model overloaded) errors — see
_generate_with_retry. At 4 calls/evaluation and a 20/day quota, that's
5 evaluations/day before hitting RESOURCE_EXHAUSTED; a single 503 retry
adds 1 call to whichever evaluation hits it.

No persistence, no frontend changes here, no multi-turn agent debate —
deliberately out of scope. Single endpoint: POST /evaluate.
"""

import asyncio
import json
import os
import random

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from prompts import (
    MARKET_SKEPTIC_PROMPT,
    MARKET_SKEPTIC_RESEARCH_PROMPT,
    SYNTHESIS_PROMPT,
    TECHNICAL_EVALUATOR_PROMPT,
    TECHNICAL_EVALUATOR_RESEARCH_PROMPT,
    TECHNICAL_EVALUATOR_TRIAGE_PROMPT,
    VENTURE_ADVOCATE_PROMPT,
)
from schemas import AgentEvaluation, IdeaRequest, SynthesisVerdict, ValidationResult

load_dotenv()

MODEL = "gemini-2.5-flash"

app = FastAPI(title="Startup Idea Validator")

# Allow the static frontend (opened directly from disk as a file:// page, or
# served from any localhost dev server) to call this API. "*" is fine for a
# local v1 tool with no auth and no sensitive data; revisit if this is ever
# deployed publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazily construct the Gemini client on first real use.

    Constructing genai.Client() validates the API key immediately and
    raises if it's missing/empty. Doing this lazily (rather than at module
    import time) means importing main.py — e.g. for tests that only need
    _parse_json_response — doesn't require a real API key to be set.
    """
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


async def _generate_with_retry(**kwargs):
    """Call generate_content, retrying on transient 503 (model overloaded).

    Gemini occasionally returns 503 UNAVAILABLE when the model is under
    high demand — this is a known, common, temporary condition on Google's
    side, not a bug in our request. We retry up to 3 times with exponential
    backoff (1s, 2s, 4s) plus a little jitter, then give up and let the
    error propagate as before. Any other error (bad request, auth failure,
    etc.) is not retried — retrying those would just waste time.
    """
    client = _get_client()
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            return await client.aio.models.generate_content(**kwargs)
        except genai_errors.ServerError as e:
            is_last_attempt = attempt == max_attempts - 1
            if "503" not in str(e) or is_last_attempt:
                raise
            delay = (2 ** attempt) + random.uniform(0, 0.5)
            print(f"--- Gemini 503 (overloaded), retrying in {delay:.1f}s (attempt {attempt + 1}/{max_attempts}) ---")
            await asyncio.sleep(delay)


def _parse_json_response(raw_text: str) -> dict:
    """Strip markdown code fences if present, then parse JSON.

    Models occasionally wrap JSON in ```json fences despite instructions.
    This is a one-line defensive strip, not a retry/repair system — if
    parsing still fails after this, we let it raise.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def _call_agent(system_prompt: str, user_content: str) -> dict:
    response = await _generate_with_retry(
        model=MODEL,
        contents=user_content,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=2048,
        ),
    )
    raw_text = response.text
    try:
        return _parse_json_response(raw_text)
    except json.JSONDecodeError:
        print(f"--- RAW AGENT RESPONSE (failed to parse) ---\n{raw_text}\n--- END ---")
        raise


async def _call_agent_grounded(system_prompt: str, user_content: str) -> str:
    """Call Gemini with web search enabled. Returns plain text, not JSON.

    Gemini's search-grounded output should not be parsed as structured JSON
    (per Google's own SDK guidance) — this is a free-text research step,
    consumed as context by a separate structured call afterward.
    """
    response = await _generate_with_retry(
        model=MODEL,
        contents=user_content,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1024,
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
        ),
    )
    return response.text


async def _call_agent_plain_text(system_prompt: str, user_content: str) -> str:
    """Call Gemini for a short plain-text answer (no search, no JSON parsing).

    Used for the cheap build-vs-buy triage check.
    """
    response = await _generate_with_retry(
        model=MODEL,
        contents=user_content,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=10,
        ),
    )
    return response.text.strip()


async def _evaluate_market_skeptic(idea: str) -> AgentEvaluation:
    # Reverted to a single call (no search) to stay within Gemini's
    # free-tier daily quota (20 requests/day on this project) while
    # actively iterating on prompts/output quality. Competitors are now
    # drawn from the model's training knowledge rather than live search —
    # less current, but enough to keep development moving. The grounded
    # research path still exists (_call_agent_grounded,
    # MARKET_SKEPTIC_RESEARCH_PROMPT) if revisited later with more quota.
    raw = await _call_agent(MARKET_SKEPTIC_PROMPT, idea)
    return AgentEvaluation(**raw)


async def _evaluate_technical(idea: str) -> AgentEvaluation:
    # Single call, no search — same reasoning as _evaluate_market_skeptic
    # above (stay within the 20/day free-tier quota during active
    # development). Build-vs-buy notes come from training knowledge.
    raw = await _call_agent(TECHNICAL_EVALUATOR_PROMPT, idea)
    return AgentEvaluation(**raw)


async def evaluate_idea(idea: str) -> ValidationResult:
    # Step 1: run the three evaluators one after another. 4 calls total
    # for the whole evaluation (Market Skeptic, Technical Evaluator,
    # Venture Advocate, then Synthesis below) — no search grounding
    # currently, all from training knowledge. Serialized + retried on
    # transient 503s; see module docstring for the quota math.
    market_skeptic = await _evaluate_market_skeptic(idea)
    technical_evaluator = await _evaluate_technical(idea)
    advocate_raw = await _call_agent(VENTURE_ADVOCATE_PROMPT, idea)
    venture_advocate = AgentEvaluation(**advocate_raw)

    # Step 2: synthesis agent reads the idea + all three evaluations
    synthesis_input = (
        f"Idea:\n{idea}\n\n"
        f"Market Skeptic evaluation:\n{market_skeptic.model_dump_json()}\n\n"
        f"Technical Evaluator evaluation:\n{technical_evaluator.model_dump_json()}\n\n"
        f"Venture Advocate evaluation:\n{venture_advocate.model_dump_json()}\n"
    )
    synthesis_raw = await _call_agent(SYNTHESIS_PROMPT, synthesis_input)
    synthesis = SynthesisVerdict(**synthesis_raw)

    return ValidationResult(
        market_skeptic=market_skeptic,
        technical_evaluator=technical_evaluator,
        venture_advocate=venture_advocate,
        synthesis=synthesis,
    )


@app.post("/evaluate", response_model=ValidationResult)
async def evaluate(request: IdeaRequest):
    if not request.idea.strip():
        raise HTTPException(status_code=400, detail="Idea text cannot be empty.")
    try:
        return await evaluate_idea(request.idea)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise HTTPException(
            status_code=502, detail=f"Agent returned malformed output: {e}"
        )
    except genai_errors.ServerError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gemini is currently overloaded and retries were exhausted. Try again shortly. ({e})",
        )


@app.get("/health")
async def health():
    return {"status": "ok"}
