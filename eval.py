# Stage 8: eval - basic eval harness for hybrid retrieval quality.
# Pipeline order: ... -> hybrid_search.py -> eval.py
from hybrid_search import hybrid_search

# Each case: a real query, and a phrase that should appear in header,
# source, or content of at least one of the top-k hits (recall@k).
# Phrases are specific enough that a random wiki page should not pass.
TEST_CASES = [
    ("How do I navigate the network editor?", "network editor"),
    ("What is the OP Create Dialog used for?", "create dialog"),
    ("How do I set preferences in TouchDesigner?", "preference"),
    ("How does network path navigation work?", "path"),
    ("How do I zoom in the network editor?", "zoom"),
]


def _haystack(payload: dict) -> str:
    return " ".join(
        [
            str(payload.get("header_title") or ""),
            str(payload.get("source") or ""),
            str(payload.get("content") or ""),
        ]
    ).lower()


def run_eval(test_cases: list[tuple[str, str]], top_k: int = 5) -> dict:
    """
    Run each (query, expected_phrase) test case through hybrid_search()
    and check whether the phrase appears in ANY of the top_k results
    (recall@k), looking at header_title, source, and content.
    """
    if not test_cases:
        raise ValueError("test_cases cannot be empty")

    passed = 0
    details = []

    for query, expected in test_cases:
        try:
            results = hybrid_search(query, top_k=top_k)
        except Exception as e:
            details.append({"query": query, "passed": False, "error": str(e)})
            continue

        if not results:
            details.append({"query": query, "passed": False, "error": "no results returned"})
            continue

        needle = expected.lower()
        matched_in_header = False
        matched = False
        for payload, _ in results:
            if needle in _haystack(payload):
                matched = True
            header_source = f"{payload.get('header_title') or ''} {payload.get('source') or ''}".lower()
            if needle in header_source:
                matched_in_header = True

        if matched:
            passed += 1
        details.append(
            {
                "query": query,
                "passed": matched,
                "expected": expected,
                "matched_in_header_or_source": matched_in_header,
            }
        )

    return {
        "passed": passed,
        "total": len(test_cases),
        "details": details,
    }


if __name__ == "__main__":
    summary = run_eval(TEST_CASES)

    for detail in summary["details"]:
        status = "PASS" if detail["passed"] else "FAIL"
        where = " (header/source)" if detail.get("matched_in_header_or_source") else ""
        print(f"{status}: '{detail['query']}'{where}")
        if not detail["passed"] and "error" in detail:
            print(f"       error: {detail['error']}")

    print(f"\n{summary['passed']}/{summary['total']} passed")
