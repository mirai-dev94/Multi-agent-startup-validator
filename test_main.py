"""
Test coverage for v2.

Scope: JSON-parsing helper, schema validation, and the SQLite database
layer. Does NOT call the real Gemini API or write to the real database file
— database tests use a temporary file that is cleaned up after each test.
No API key or network required to run these.
"""

import json
import tempfile
from pathlib import Path

import pytest

import database
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


def test_agent_evaluation_defaults_existing_solutions_and_build_vs_buy():
    """An evaluation with no extra fields filled in (e.g. Venture Advocate's
    output) should default to null for both, not raise or require them."""
    data = {"summary": "ok", "key_points": ["a"], "stance": "positive"}
    evaluation = AgentEvaluation(**data)
    assert evaluation.existing_solutions is None
    assert evaluation.build_vs_buy is None


def test_agent_evaluation_accepts_populated_existing_solutions_and_build_vs_buy():
    data = {
        "summary": "ok",
        "key_points": ["a"],
        "stance": "mixed",
        "existing_solutions": "Daylio and Reflectly already handle mood tracking.",
        "build_vs_buy": "Buying is clearly easier here.",
    }
    evaluation = AgentEvaluation(**data)
    assert evaluation.existing_solutions == "Daylio and Reflectly already handle mood tracking."
    assert evaluation.build_vs_buy == "Buying is clearly easier here."


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


# ---------------------------------------------------------------------------
# Database tests — use a temp file so the real evaluations.db is untouched
# ---------------------------------------------------------------------------

SAMPLE_RESULT = {
    "market_skeptic": {
        "summary": "ok", "key_points": ["a"], "stance": "mixed",
        "existing_solutions": "Competitor A does similar things.",
        "build_vs_buy": None,
    },
    "technical_evaluator": {
        "summary": "fine", "key_points": ["b"], "stance": "positive",
        "existing_solutions": None, "build_vs_buy": None,
    },
    "venture_advocate": {
        "summary": "great", "key_points": ["c"], "stance": "positive",
        "existing_solutions": None, "build_vs_buy": None,
    },
    "synthesis": {
        "viability_score": 7,
        "top_risks": ["risk1"],
        "top_strengths": ["strength1"],
        "recommendation": "proceed",
        "reasoning": "Panelists broadly agreed.",
    },
}


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Redirect database.DB_PATH to a temp file for the duration of each test."""
    temp_db = tmp_path / "test_evaluations.db"
    monkeypatch.setattr(database, "DB_PATH", temp_db)
    database.init_db()
    return temp_db


def test_save_and_retrieve_evaluation(tmp_db):
    saved_id = database.save_evaluation("Test idea", SAMPLE_RESULT)
    assert isinstance(saved_id, int)
    assert saved_id > 0

    item = database.get_evaluation(saved_id)
    assert item is not None
    assert item["idea"] == "Test idea"
    assert item["result"]["synthesis"]["viability_score"] == 7


def test_list_evaluations_most_recent_first(tmp_db):
    database.save_evaluation("First idea", SAMPLE_RESULT)
    database.save_evaluation("Second idea", SAMPLE_RESULT)

    items = database.list_evaluations()
    assert len(items) == 2
    assert items[0]["idea_snippet"] == "Second idea"  # most recent first
    assert items[1]["idea_snippet"] == "First idea"


def test_list_evaluations_truncates_long_idea(tmp_db):
    long_idea = "A" * 200
    database.save_evaluation(long_idea, SAMPLE_RESULT)

    items = database.list_evaluations()
    assert len(items[0]["idea_snippet"]) <= 121  # 120 chars + ellipsis
    assert items[0]["idea_snippet"].endswith("…")


def test_delete_evaluation(tmp_db):
    saved_id = database.save_evaluation("To delete", SAMPLE_RESULT)
    deleted = database.delete_evaluation(saved_id)
    assert deleted is True
    assert database.get_evaluation(saved_id) is None


def test_delete_nonexistent_evaluation(tmp_db):
    deleted = database.delete_evaluation(99999)
    assert deleted is False


def test_get_nonexistent_evaluation(tmp_db):
    item = database.get_evaluation(99999)
    assert item is None
