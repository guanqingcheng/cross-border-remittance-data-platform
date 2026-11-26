"""The AI SQL review must fail closed: anything short of a valid, clean answer blocks the change.

These tests replace the Anthropic client with a fake, so they need no API key, cost nothing,
and run in CI. Exit codes: 0 = pass, 1 = blocked by findings, 2 = review could not run.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from sql_review import review_sql

SQL_FILE = "sql_review/examples/usp_GetTransfersUpdatedSince_good.sql"


def make_response(text=None, stop_reason="end_turn", blocks=None):
    content = blocks if blocks is not None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        model="claude-haiku-5-5",
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


def review_json(verdict="pass", findings=None):
    return json.dumps({"verdict": verdict, "summary": "test", "findings": findings or []})


def finding(rule="R1", severity="error", file=SQL_FILE):
    return {"file": file, "line": 3, "rule": rule, "severity": severity, "message": "test"}


def run_review(monkeypatch, response=None, error=None):
    """Run main() on one file with a fake client that returns `response` or raises `error`."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            if error is not None:
                raise error
            return response

    monkeypatch.setattr(review_sql.anthropic, "Anthropic", FakeClient)
    monkeypatch.setattr(review_sql, "load_dotenv", lambda: None)
    monkeypatch.setattr("sys.argv", ["review_sql", SQL_FILE])
    return review_sql.main()


# --- The review could not run: exit 2 ---

def test_invalid_json_fails_closed(monkeypatch):
    assert run_review(monkeypatch, make_response("this is not JSON")) == 2


def test_cut_off_answer_fails_closed(monkeypatch):
    assert run_review(monkeypatch, make_response('{"verdict": "pa', stop_reason="max_tokens")) == 2


def test_refusal_fails_closed(monkeypatch):
    assert run_review(monkeypatch, make_response("", stop_reason="refusal")) == 2


def test_answer_without_text_fails_closed(monkeypatch):
    assert run_review(monkeypatch, make_response(blocks=[])) == 2


def test_unknown_rule_fails_closed(monkeypatch):
    response = make_response(review_json("pass", [finding(rule="R99")]))
    assert run_review(monkeypatch, response) == 2


def test_unknown_verdict_fails_closed(monkeypatch):
    assert run_review(monkeypatch, make_response(review_json(verdict="looks fine"))) == 2


def test_finding_for_unreviewed_file_fails_closed(monkeypatch):
    response = make_response(review_json("fail", [finding(file="database/other.sql")]))
    assert run_review(monkeypatch, response) == 2


def test_api_error_fails_closed(monkeypatch):
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    assert run_review(monkeypatch, error=error) == 2


def test_missing_api_key_fails_closed(monkeypatch):
    # The real client, with no key anywhere: it must not be treated as a pass
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(review_sql, "load_dotenv", lambda: None)
    monkeypatch.setattr("sys.argv", ["review_sql", SQL_FILE])
    assert review_sql.main() == 2


# --- The code decides from the findings: exit 1 ---

def test_error_finding_blocks_even_if_model_says_pass(monkeypatch):
    response = make_response(review_json("pass", [finding(severity="error")]))
    assert run_review(monkeypatch, response) == 1


def test_model_fail_verdict_blocks_without_findings(monkeypatch):
    assert run_review(monkeypatch, make_response(review_json("fail"))) == 1


# --- Only a clean, valid answer passes: exit 0 ---

def test_clean_answer_passes(monkeypatch):
    assert run_review(monkeypatch, make_response(review_json("pass"))) == 0


def test_warning_only_passes(monkeypatch):
    response = make_response(review_json("pass", [finding(rule="R5", severity="warning")]))
    assert run_review(monkeypatch, response) == 0


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal", "pause_turn", "tool_use"])
def test_any_unexpected_stop_reason_fails_closed(monkeypatch, stop_reason):
    # Even a well-formed passing answer is rejected if the model did not finish normally
    assert run_review(monkeypatch, make_response(review_json("pass"), stop_reason=stop_reason)) == 2
