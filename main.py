"""
Startup Idea Validator — v1

Pipeline:
  1. Three evaluator agents (Market Skeptic, Technical Evaluator, Venture
     Advocate) run concurrently against the idea text, independently.
  2. The Synthesis Agent receives the idea + all three evaluations and
     produces a final structured verdict.

No persistence, no frontend, no multi-turn agent debate — that's deliberately
out of scope for v1. Single endpoint: POST /evaluate.
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types as genai_types

from prompts import (
    MARKET_SKEPTIC_PROMPT,
    SYNTHESIS_PROMPT,
    TECHNICAL_EVALUATOR_PROMPT,
    VENTURE_ADVOCATE_PROMPT,
)
from schemas import AgentEvaluation, IdeaRequest, SynthesisVerdict, ValidationResult

load_dotenv()

MODEL = "gemini-2.5-flash"

app = FastAPI(title="Startup Idea Validator")
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
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1000,
        ),
    )
    raw_text = response.text
    return _parse_json_response(raw_text)


async def evaluate_idea(idea: str) -> ValidationResult:
    # Step 1: run the three evaluators concurrently
    skeptic_raw, technical_raw, advocate_raw = await asyncio.gather(
        _call_agent(MARKET_SKEPTIC_PROMPT, idea),
        _call_agent(TECHNICAL_EVALUATOR_PROMPT, idea),
        _call_agent(VENTURE_ADVOCATE_PROMPT, idea),
    )

    market_skeptic = AgentEvaluation(**skeptic_raw)
    technical_evaluator = AgentEvaluation(**technical_raw)
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


@app.get("/health")
async def health():
    return {"status": "ok"}
