# eval.py — flow

```
run_eval([])
    ↓
ValueError (test_cases cannot be empty)

run_eval(TEST_CASES, top_k=5)
    ↓
for (query, expected_keyword) in test_cases:
    hybrid_search(query, top_k)
        ↓
    top result's content contains expected_keyword (case-insensitive)?
        ├── yes → PASS
        └── no  → FAIL
    (a hybrid_search() failure or empty result list is also recorded
     as a FAIL with the error, not a crash)
    ↓
return {passed, total, details}
    ↓
print PASS/FAIL per query, then "N/total passed"
```

Result on the ingested `wiki` corpus: 5/5 passed.
