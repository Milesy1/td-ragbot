# Stage 8: eval - gold-source recall@k for hybrid retrieval.
from hybrid_search import hybrid_search

# Pass if any top-k hit's source or header contains a gold substring.
TEST_CASES = [
    {
        "query": "How do I navigate the network editor?",
        "gold": ["Network_Editor", "Network Editor"],
    },
    {
        "query": "What is the OP Create Dialog used for?",
        "gold": ["OP_Create_Dialog", "OP Create Dialog"],
    },
    {
        "query": "How do I set preferences in TouchDesigner?",
        "gold": ["Preferences", "Dialogs_Preferences"],
    },
    {
        "query": "How does network path navigation work?",
        "gold": ["Network_Path", "Network Path"],
    },
    {
        "query": "How do I zoom in the network editor?",
        "gold": ["Network_Editor", "Network Editor"],
    },
]


def _blob(payload: dict) -> str:
    return f"{payload.get('source') or ''} {payload.get('header_title') or ''}"


def _matches_gold(payload: dict, gold: list[str]) -> bool:
    blob = _blob(payload).lower()
    return any(needle.lower() in blob for needle in gold)


def run_eval(test_cases: list[dict] | None = None, top_k: int = 5) -> dict:
    """
    Run each gold-source test case through hybrid_search() and check
    whether any of the top_k results matches a gold source/header.
    """
    cases = test_cases or TEST_CASES
    if not cases:
        raise ValueError("test_cases cannot be empty")

    passed = 0
    details = []

    for case in cases:
        query = case["query"]
        gold = case["gold"]
        try:
            results = hybrid_search(query, top_k=top_k)
        except Exception as e:
            details.append({"query": query, "passed": False, "error": str(e), "gold": gold})
            continue

        if not results:
            details.append({"query": query, "passed": False, "error": "no results returned", "gold": gold})
            continue

        hit_at = None
        for index, (payload, score) in enumerate(results, start=1):
            if _matches_gold(payload, gold):
                hit_at = index
                break

        matched = hit_at is not None
        if matched:
            passed += 1

        top_payload, top_score = results[0]
        details.append(
            {
                "query": query,
                "passed": matched,
                "gold": gold,
                "hit_at": hit_at,
                "top1_source": top_payload.get("source"),
                "top1_header": top_payload.get("header_title"),
                "top1_score": round(float(top_score), 4),
            }
        )

    return {
        "passed": passed,
        "total": len(cases),
        "details": details,
    }


if __name__ == "__main__":
    summary = run_eval()

    for detail in summary["details"]:
        status = "PASS" if detail["passed"] else "FAIL"
        where = f" @{detail['hit_at']}" if detail.get("hit_at") else ""
        print(f"{status}{where}: '{detail['query']}'")
        print(f"       top-1: {detail.get('top1_header')} ({detail.get('top1_source')}) score={detail.get('top1_score')}")
        if not detail["passed"] and "error" in detail:
            print(f"       error: {detail['error']}")

    print(f"\n{summary['passed']}/{summary['total']} passed")
