"""Runs tests/test_set.csv against the chatbot and stores every result in the test_results table.

Usage (from the project folder, with OPENAI_API_KEY set in .env):
    python -m tests.run_tests

A row passes when the reply contains at least one of its expected keywords (separated by |).
Queries containing | are multi-turn: earlier parts are sent first in the same session (memory tests).
"""
import csv
import sys
import uuid
from pathlib import Path

from app import db
from app.llm import ChatError, complete
from app.prompt import build_messages

CSV = Path(__file__).with_name("test_set.csv")


def ask(turns: list[str]) -> tuple[str, int]:
    history: list[dict] = []
    reply, latency = "", 0
    for turn in turns:
        reply, latency, _ = complete(build_messages(history, turn))
        history += [{"role": "user", "content": turn}, {"role": "bot", "content": reply}]
    return reply, latency


def main() -> int:
    db.init_db()
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    passed, latencies, run_id = 0, [], uuid.uuid4().hex[:6]
    print(f"Run {run_id}: {len(rows)} test cases\n")
    for row in rows:
        turns = row["query"].split("|")
        keywords = [k.strip().lower() for k in row["expected_keywords"].split("|")]
        try:
            reply, latency = ask(turns)
        except ChatError as err:
            reply, latency = f"ERROR: {err.user_message}", 0
        ok = any(k in reply.lower() for k in keywords)
        passed += ok
        latencies.append(latency)
        db.save_test_result(row["category"], row["query"], row["expected_behaviour"] + " [" + row["expected_keywords"] + "]", reply, ok, latency)
        print(f"{'PASS' if ok else 'FAIL'}  [{row['category']}] {row['query']}  ({latency} ms)")
        if not ok:
            print("      reply:", reply.replace("\n", " ")[:200])
    timed = [x for x in latencies if x]
    print(f"\n{passed}/{len(rows)} passed ({passed / len(rows):.0%})")
    if timed:
        timed.sort()
        print(f"Latency: median {timed[len(timed) // 2]} ms, max {timed[-1]} ms, under 5 s: {sum(t < 5000 for t in timed)}/{len(timed)}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
