"""
Minimal v1 test coverage.

Scope: test the JSON-parsing helper and schema validation in isolation,
since those are the parts most likely to break (model not following the
"JSON only" instruction). Does NOT call the real Gemini API — no network,
no API key required to run these.
"""

import json

import pytest

from main import _parse_json_response
from schemas import AgentEvaluation, Competitor, SynthesisVerdict


def test_parse_plain_json():
    raw = '{"summary": "ok", "key_points": ["a"], "stance": "mixed"}'
    assert _parse_json_response(raw) == json.loads(raw)


def test_parse_json_wrapped_in_markdown_fence():
    raw = '```json\n{"summary": "ok", "key_points": ["a"], "stance": "mixed"}\n```'
    result = _parse_json_response(raw)
    assert result["summary"] == "ok"


def test_parse_json_wrapped_in_plain_fence():
    raw = '```\n{"summary": "ok", "key_points": ["a"], "stance": "mixed"}\n```'
    result = _parse_json_response(raw)
    assert result["summary"] == "ok"


def test_parse_malformed_json_raises():
    with pytest.raises(json.JSONDecodeError):
        _parse_json_response("not json at all")


def test_agent_evaluation_schema_accepts_valid_data():
    data = {"summary": "ok", "key_points": ["a", "b"], "stance": "positive"}
    evaluation = AgentEvaluation(**data)
    assert evaluation.stance == "positive"


def test_agent_evaluation_defaults_existing_solutions_and_build_vs_buy():
    """An evaluation with no search-grounded fields (e.g. Venture Advocate's
    output) should default to an empty competitor list and a null
    build_vs_buy, not raise or require them."""
    data = {"summary": "ok", "key_points": ["a"], "stance": "positive"}
    evaluation = AgentEvaluation(**data)
    assert evaluation.existing_solutions == []
    assert evaluation.build_vs_buy is None


def test_agent_evaluation_accepts_populated_competitors_and_build_vs_buy():
    data = {
        "summary": "ok",
        "key_points": ["a"],
        "stance": "mixed",
        "existing_solutions": [
            {"name": "CompetitorX", "how_they_solve_it": "Does the core thing already."}
        ],
        "build_vs_buy": "Buying is clearly easier here.",
    }
    evaluation = AgentEvaluation(**data)
    assert len(evaluation.existing_solutions) == 1
    assert evaluation.existing_solutions[0].name == "CompetitorX"
    assert evaluation.build_vs_buy == "Buying is clearly easier here."


def test_competitor_schema_requires_name_and_how_they_solve_it():
    competitor = Competitor(name="Acme", how_they_solve_it="Same core feature.")
    assert competitor.name == "Acme"


def test_agent_evaluation_schema_rejects_invalid_stance():
    data = {"summary": "ok", "key_points": ["a"], "stance": "enthusiastic"}
    with pytest.raises(ValueError):
        AgentEvaluation(**data)


def test_synthesis_verdict_schema_accepts_valid_data():
    data = {
        "viability_score": 7,
        "top_risks": ["risk1"],
        "top_strengths": ["strength1"],
        "recommendation": "proceed",
        "reasoning": "the panel mostly agreed",
    }
    verdict = SynthesisVerdict(**data)
    assert verdict.recommendation == "proceed"


def test_synthesis_verdict_schema_rejects_invalid_recommendation():
    data = {
        "viability_score": 7,
        "top_risks": ["risk1"],
        "top_strengths": ["strength1"],
        "recommendation": "maybe",
        "reasoning": "unclear",
    }
    with pytest.raises(ValueError):
        SynthesisVerdict(**data)
