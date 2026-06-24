"""
Output schemas for each agent.

Design note: all three evaluator agents (Market Skeptic, Technical Evaluator,
Venture Advocate) share the same base output shape — a summary, a list of key
points, and a stance. Market Skeptic and (conditionally) Technical Evaluator
also fill in two extra optional fields (existing_solutions, build_vs_buy)
when they have web search grounding available. Venture Advocate and the
Synthesis Agent never populate these — they default to empty/null. Keeping
one shared schema (rather than a separate class per agent) means the
Synthesis Agent can still treat all three evaluations uniformly.
"""

from pydantic import BaseModel
from typing import Literal


class Competitor(BaseModel):
    name: str
    how_they_solve_it: str


class AgentEvaluation(BaseModel):
    summary: str
    key_points: list[str]
    stance: Literal["positive", "mixed", "negative"]
    existing_solutions: list[Competitor] = []
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
