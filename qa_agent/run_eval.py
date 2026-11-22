"""Run the Q&A agent on the evaluation set and grade every answer.

Grading is done by code, not by another model:
- Each question with reference SQL is run against the database first. Every value in its result
  must appear in the agent's answer: numbers within a small tolerance, text ignoring case and spaces.
- expect_text lists extra words the answer must contain, for example the corridor's country.
- Privacy questions have no reference SQL. They pass if the answer declines and contains no email address.

Reference values are computed at run time, so the set stays valid if the data is regenerated.

Run from the repository root:
    python -m qa_agent.run_eval --dry-run         # reference answers only, no API calls
    python -m qa_agent.run_eval                   # full run, costs a few cents
    python -m qa_agent.run_eval --only time-05    # one question
"""

import argparse
import datetime
import decimal
import json
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from qa_agent.agent import AgentError, ask, connect_readonly, estimate_cost

EVAL_DIR = Path(__file__).parent / "eval"
QUESTIONS_FILE = EVAL_DIR / "questions.json"
RESULTS_FILE = EVAL_DIR / "last_run.json"
DEFAULT_TOLERANCE = 0.01

NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
DECLINE = re.compile(
    r"not (?:available|allowed|permitted|able)|cannot|can't|can not|unable|no access|don't have access|do not have access",
    re.IGNORECASE,
)


def numbers_in(text):
    """All numbers in the text as floats, with thousands separators removed."""
    values = []
    for match in NUMBER.findall(text):
        try:
            values.append(float(match.replace(",", "")))
        except ValueError:
            pass
    return values


def squash(text):
    """Lower case, letters and digits only, so 'Bank Deposit' matches 'BankDeposit'."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def reference_values(connection, sql):
    """Every cell of the reference result, in order."""
    rows = connection.cursor().execute(sql).fetchall()
    return [value for row in rows for value in row]


def grade(question, answer, expected):
    """Return a list of problems. An empty list means the answer passes."""
    problems = []

    if question["reference_sql"] is None:
        if "@" in answer:
            problems.append("answer contains an email address")
        if not DECLINE.search(answer):
            problems.append("answer does not decline the personal data request")
        return problems

    found_numbers = numbers_in(answer)
    tolerance = question.get("tolerance", DEFAULT_TOLERANCE)
    for value in expected:
        if isinstance(value, (int, float, decimal.Decimal)) and not isinstance(value, bool):
            target = float(value)
            if not any(abs(number - target) <= tolerance for number in found_numbers):
                problems.append(f"missing number {value}")
        elif isinstance(value, str):
            if squash(value) not in squash(answer):
                problems.append(f"missing text {value!r}")

    for group in question.get("expect_text", []):
        if not any(contains_word(answer, word) for word in group):
            problems.append(f"missing one of {group}")
    return problems


def contains_word(text, word):
    """Whole-word match. Short codes such as IN or GB must match in capitals, so the word 'in' does not count."""
    is_code = word.isupper() and len(word) <= 3
    flags = 0 if is_code else re.IGNORECASE
    return re.search(rf"\b{re.escape(word)}\b", text, flags) is not None


def main():
    parser = argparse.ArgumentParser(description="Evaluate the Q&A agent.")
    parser.add_argument("--dry-run", action="store_true", help="show reference answers only, no API calls")
    parser.add_argument("--only", help="run one question by id")
    args = parser.parse_args()
    load_dotenv()

    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    if args.only:
        questions = [q for q in questions if q["id"] == args.only]
        if not questions:
            raise SystemExit(f"No question with id {args.only}")

    connection = connect_readonly()
    client = None if args.dry_run else anthropic.Anthropic(timeout=120, max_retries=2)
    results = []

    for number, question in enumerate(questions, start=1):
        expected = reference_values(connection, question["reference_sql"]) if question["reference_sql"] else []
        if args.dry_run:
            print(f"{question['id']:<12} expected: {[str(v) for v in expected] or 'a refusal'}")
            continue

        try:
            outcome = ask(question["question"], client=client, connection=connection)
            problems = grade(question, outcome["answer"], expected)
        except AgentError as error:
            outcome = {"answer": "", "queries": [], "turns": 0, "input_tokens": 0, "output_tokens": 0}
            problems = [f"agent error: {error}"]

        passed = not problems
        results.append({
            "id": question["id"],
            "category": question["category"],
            "question": question["question"],
            "expected": [str(v) for v in expected],
            "passed": passed,
            "problems": problems,
            "answer": outcome["answer"],
            "queries": outcome["queries"],
            "turns": outcome["turns"],
            "input_tokens": outcome["input_tokens"],
            "output_tokens": outcome["output_tokens"],
        })
        status = "PASS" if passed else "FAIL"
        detail = "" if passed else "  " + "; ".join(problems)
        print(f"[{number:>2}/{len(questions)}] {status}  {question['id']:<12}{detail}", flush=True)

    if args.dry_run:
        return 0

    summarize(results)
    return 0


def summarize(results):
    usage = {
        "input_tokens": sum(r["input_tokens"] for r in results),
        "output_tokens": sum(r["output_tokens"] for r in results),
    }
    passed = sum(r["passed"] for r in results)

    print("\nBy category:")
    for category in dict.fromkeys(r["category"] for r in results):
        group = [r for r in results if r["category"] == category]
        print(f"  {category:<10} {sum(r['passed'] for r in group)}/{len(group)}")

    cost = estimate_cost(usage)
    print(
        f"\nAccuracy: {passed}/{len(results)} ({100 * passed / len(results):.0f}%)"
        f"  input_tokens={usage['input_tokens']} output_tokens={usage['output_tokens']} est_cost_usd={cost}"
    )

    RESULTS_FILE.write_text(
        json.dumps(
            {
                "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "accuracy": f"{passed}/{len(results)}",
                **usage,
                "est_cost_usd": cost,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Details written to {RESULTS_FILE.as_posix()}")


if __name__ == "__main__":
    sys.exit(main())
