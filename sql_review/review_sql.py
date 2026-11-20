"""AI review of changed SQL files, used as a CI gate.

Claude checks the files against the rules in rules.md and must answer with JSON
that matches REVIEW_SCHEMA. The gate fails closed: a missing API key, an API
error, a refusal, a cut-off answer, or JSON that does not match the schema all
count as a failed review, never as a pass.

Exit codes: 0 = passed, 1 = blocked by error findings, 2 = review could not run.

Usage, from the repository root:
    python -m sql_review.review_sql path/to/file.sql [more files]
    python -m sql_review.review_sql --base origin/main    # files changed since that ref
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# The only place the model is chosen. Every call uses this constant.
MODEL = "claude-haiku-5-5"
# Claude Haiku 5.5 list price per million tokens, for prompts of 100K tokens or fewer
PRICE_PER_MTOK = {"input": 0.10, "output": 0.50}

RULES_FILE = Path(__file__).with_name("rules.md")
RULE_IDS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
SQL_ROOT = "database/"

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "rule": {"type": "string", "enum": RULE_IDS},
                    "severity": {"type": "string", "enum": ["error", "warning"]},
                    "message": {"type": "string"},
                },
                "required": ["file", "line", "rule", "severity", "message"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "summary", "findings"],
    "additionalProperties": False,
}


class ReviewError(Exception):
    """The review could not produce a trustworthy result."""


def changed_sql_files(base_ref):
    """Return SQL files under database/ that were added or modified since base_ref."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    return [
        path for path in result.stdout.splitlines()
        if path.startswith(SQL_ROOT) and path.lower().endswith(".sql")
    ]


def build_prompt(paths):
    """Put each file in its own tag, with line numbers so findings can point at a line."""
    parts = []
    for path in paths:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
        numbered = "\n".join(f"{number}: {line}" for number, line in enumerate(lines, start=1))
        parts.append(f'<file path="{path}">\n{numbered}\n</file>')
    return "Review these files.\n\n" + "\n\n".join(parts)


def call_claude(prompt):
    """Send one review request and return the parsed JSON and the token usage."""
    client = anthropic.Anthropic(timeout=120, max_retries=2)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=RULES_FILE.read_text(encoding="utf-8"),
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
    )
    # Anything other than a normal finish means the JSON may be missing or cut off
    if response.stop_reason != "end_turn":
        raise ReviewError(f"Unexpected stop reason: {response.stop_reason}")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise ReviewError("The response has no text block")
    try:
        review = json.loads(text)
    except json.JSONDecodeError as error:
        raise ReviewError(f"The response is not valid JSON: {error}") from error
    return review, response.model, response.usage


def validate(review, paths):
    """Check the answer again in code, so a malformed answer can never pass."""
    if review.get("verdict") not in ("pass", "fail"):
        raise ReviewError("verdict must be 'pass' or 'fail'")
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise ReviewError("findings must be a list")
    for finding in findings:
        if finding.get("rule") not in RULE_IDS:
            raise ReviewError(f"Unknown rule: {finding.get('rule')}")
        if finding.get("severity") not in ("error", "warning"):
            raise ReviewError(f"Unknown severity: {finding.get('severity')}")
        if finding.get("file") not in paths:
            raise ReviewError(f"Finding points at a file that was not reviewed: {finding.get('file')}")


def decide(review):
    """The gate decides from the findings, not from the model's own verdict alone."""
    has_error = any(finding["severity"] == "error" for finding in review["findings"])
    # Block if either the model or the findings say so
    return "fail" if has_error or review["verdict"] == "fail" else "pass"


def print_report(review, final_verdict, model, usage):
    for finding in sorted(review["findings"], key=lambda f: (f["file"], f["line"])):
        print(f"  {finding['severity'].upper():7} {finding['rule']} {finding['file']}:{finding['line']}  {finding['message']}")
    print(f"Summary: {review['summary']}")
    cost = (usage.input_tokens * PRICE_PER_MTOK["input"] + usage.output_tokens * PRICE_PER_MTOK["output"]) / 1_000_000
    print(f"model={model} input_tokens={usage.input_tokens} output_tokens={usage.output_tokens} est_cost_usd={cost:.5f}")
    print(f"Verdict: {final_verdict.upper()}")


def main():
    parser = argparse.ArgumentParser(description="AI review of SQL files")
    parser.add_argument("files", nargs="*", help="SQL files to review")
    parser.add_argument("--base", help="review SQL files under database/ changed since this git ref")
    args = parser.parse_args()
    load_dotenv()

    try:
        paths = list(args.files) if args.files else changed_sql_files(args.base) if args.base else []
        if not paths:
            print("No SQL files to review.")
            return 0
        print(f"Reviewing {len(paths)} file(s) with {MODEL}: {', '.join(paths)}")
        review, model, usage = call_claude(build_prompt(paths))
        validate(review, paths)
    except Exception as error:  # noqa: BLE001
        # Fail closed: whatever went wrong (no API key, network, bad JSON, git),
        # the change is not approved
        print(f"Review could not run, so the check fails: {type(error).__name__}: {error}")
        return 2

    final_verdict = decide(review)
    print_report(review, final_verdict, model, usage)
    return 1 if final_verdict == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
