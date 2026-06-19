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
from schemas import AgentEvaluation, SynthesisVerdict


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
