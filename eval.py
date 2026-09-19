# Stage 8: eval - basic eval harness for hybrid retrieval quality.
# Pipeline order: ... -> hybrid_search.py -> eval.py
from hybrid_search import hybrid_search

# Each test case: a real query against the ingested wiki docs, and a
# keyword expected to appear in a genuinely relevant top result.
TEST_CASES = [
    ("How do I navigate the network editor?", "network"),
    ("What is the OP Create Dialog used for?", "create"),
    ("How do I set preferences in TouchDesigner?", "preferences"),
    ("How does network path navigation work?", "path"),
    ("How do I zoom in the network editor?", "zoom"),
]


def run_eval(test_cases: list[tuple[str, str]], top_k: int = 5) -> dict:
    """
    Run each (query, expected_keyword) test case through hybrid_search()
    and check whether the expected keyword appears in the TOP result's
    content. Returns a summary dict with pass/fail counts and details.
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

        top_payload, _ = results[0]
        found = expected.lower() in top_payload["content"].lower()

        if found:
            passed += 1
        details.append({"query": query, "passed": found, "expected": expected})

    return {
        "passed": passed,
        "total": len(test_cases),
        "details": details,
    }


if __name__ == "__main__":
    summary = run_eval(TEST_CASES)

    for detail in summary["details"]:
        status = "PASS" if detail["passed"] else "FAIL"
        print(f"{status}: '{detail['query']}'")
        if not detail["passed"] and "error" in detail:
            print(f"       error: {detail['error']}")

    print(f"\n{summary['passed']}/{summary['total']} passed")
