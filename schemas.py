"""
Output schemas for each agent.

Design note: all three evaluator agents (Market Skeptic, Technical Evaluator,
Venture Advocate) share the same output shape — a summary, a list of key
points, and a verdict-flavored score. Giving them identical schemas keeps the
Synthesis Agent's job simple (it just reads three uniform objects) and means
we only validate one shape three times instead of three different shapes.
"""

from pydantic import BaseModel
from typing import Literal


class AgentEvaluation(BaseModel):
    summary: str
    key_points: list[str]
    stance: Literal["positive", "mixed", "negative"]


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
