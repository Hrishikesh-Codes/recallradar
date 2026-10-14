"""`recallradar-eval`: run labelled checks through the real pipeline and score the verdicts.

Each case is one line of JSONL: an input (text, link, or barcode), the verdict a careful human
gives it, and the recalls that should be listed. The M1 smoke set (data/labels/m1_smoke.jsonl) is
small and hand-made; it catches regressions while tuning, and is not an accuracy claim. SPEC §6.9's
labelled set (M3) is what the README will report.

Errors are counted by how much they could hurt someone:
- overclaim: "Recalled" when a human says only some units are, or none (§6.4 forbids this);
- dangerous miss: a recalled product reported as all clear;
- false alarm: an unrecalled product reported as recalled or "check your unit".
"""

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from recallradar_core.db.session import get_sessionmaker
from recallradar_core.enums import RecallSource
from recallradar_core.settings import get_settings
from recallradar_identify.barcode import parse_barcode
from recallradar_identify.link import parse_link
from recallradar_identify.query import ProductQuery
from recallradar_identify.text import parse_text
from recallradar_matching.embed import Embedder
from recallradar_matching.engine import Tier, check, embed_query

DEFAULT_CASES = Path("data/labels/m1_smoke.jsonl")
INGESTED = [
    RecallSource.CPSC,
    RecallSource.FDA_FOOD,
    RecallSource.FDA_DRUG,
    RecallSource.FDA_DEVICE,
]
_POSITIVE = {Tier.RECALLED, Tier.CHECK_UNIT}


@dataclass
class Outcome:
    id: str
    expected: Tier
    got: Tier
    expected_recalls: list[str]
    got_recalls: list[str]
    seconds: float
    errors: list[str] = field(default_factory=list)


def to_query(kind: str, value: str) -> ProductQuery:
    if kind == "text":
        return parse_text(value)
    if kind == "link":
        return parse_link(value)
    if kind == "barcode":
        return parse_barcode(value)  # no Open Food Facts lookup: offline and repeatable
    raise ValueError(f"unknown input type {kind!r}")


def judge(case: dict[str, Any], got: Tier, got_recalls: list[str]) -> list[str]:
    expected = Tier(case["verdict"])
    wanted = set(case["recalls"])
    errors = []
    if got is Tier.RECALLED and expected is not Tier.RECALLED:
        errors.append("overclaim")
    if expected in _POSITIVE and got not in _POSITIVE:
        errors.append("dangerous_miss")
    if expected not in _POSITIVE and got in _POSITIVE:
        errors.append("false_alarm")
    if wanted and got in _POSITIVE and not wanted & set(got_recalls):
        errors.append("wrong_recall")
    if got is not expected and not errors:
        errors.append("wrong_verdict")
    return errors


def evaluate(cases: list[dict[str, Any]], embedder: Embedder) -> list[Outcome]:
    sessions = get_sessionmaker()
    outcomes = []
    for case in cases:
        query = to_query(case["type"], case["input"])
        started = time.perf_counter()
        with sessions() as session:
            result = check(
                session, query, embedding=embed_query(embedder, query), ingested=INGESTED
            )
        seconds = time.perf_counter() - started
        got_recalls = [f"{m.recall.source}:{m.recall.source_recall_id}" for m in result.matches]
        outcomes.append(
            Outcome(
                id=case["id"],
                expected=Tier(case["verdict"]),
                got=result.verdict,
                expected_recalls=case["recalls"],
                got_recalls=got_recalls,
                seconds=seconds,
                errors=judge(case, result.verdict, got_recalls),
            )
        )
    return outcomes


def summarize(outcomes: list[Outcome]) -> dict[str, Any]:
    errors = Counter(e for o in outcomes for e in o.errors)
    latencies = sorted(o.seconds for o in outcomes)
    return {
        "cases": len(outcomes),
        "correct": sum(not o.errors for o in outcomes),
        "errors": dict(errors),
        "latency_ms_p50": round(statistics.median(latencies) * 1000),
        "latency_ms_max": round(latencies[-1] * 1000),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report", type=Path, help="write per-case results as JSON here")
    args = parser.parse_args(argv)
    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    embedder = Embedder(get_settings().model_cache_dir)
    embedder.warm_up()
    outcomes = evaluate(cases, embedder)
    for o in outcomes:
        mark = "ok " if not o.errors else "ERR"
        detail = f" {','.join(o.errors)}" if o.errors else ""
        print(f"{mark} {o.id:28s} expected={o.expected:12s} got={o.got:12s}{detail}")
        if o.errors:
            print(f"    expected {o.expected_recalls or '-'}; got {o.got_recalls or '-'}")
    summary = summarize(outcomes)
    print(json.dumps(summary))
    if args.report:
        args.report.write_text(
            json.dumps({"summary": summary, "cases": [asdict(o) for o in outcomes]}, indent=2)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
