"""
Output schemas for each agent.

Design note: all three evaluator agents (Market Skeptic, Technical Evaluator,
Venture Advocate) share the same base output shape — a summary, a list of key
points, and a stance. Market Skeptic and Technical Evaluator also fill in two
extra optional plain-text fields (existing_solutions, build_vs_buy). Venture
Advocate and the Synthesis Agent never populate these — they default to
empty/null. Both fields are deliberately plain strings, not structured
objects/lists — an earlier structured-list version (one object per
competitor) caused Pydantic validation failures whenever the model returned
a string instead of an object for one entry, which wasted a scarce
free-tier evaluation. A plain string has nothing to mismatch.
"""

from pydantic import BaseModel
from typing import Literal


class AgentEvaluation(BaseModel):
    summary: str
    key_points: list[str]
    stance: Literal["positive", "mixed", "negative"]
    existing_solutions: str | None = None
    build_vs_buy: str | None = None


class SynthesisVerdict(BaseModel):
    viability_score: int  # 1-10
    top_risks: list[str]
    top_strengths: list[str]
    recommendation: Literal["proceed", "pivot", "stop"]
    reasoning: str


class IdeaRequest(BaseModel):
    idea: str


class ValidationResult(BaseModel):
    market_skeptic: AgentEvaluation
    technical_evaluator: AgentEvaluation
    venture_advocate: AgentEvaluation
    synthesis: SynthesisVerdict
