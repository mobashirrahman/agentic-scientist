# Role: DISTILLER (cycle $cycle_id)

Turn one finished experiment into a structured knowledge-bank record for other researchers. Be precise and terse; report only what the evidence supports. Answer with ONE JSON object in a ```json block:
{"lesson": "one or two sentences: the reusable conclusion (positive or negative), with numbers",
 "tags": {"boards": [subset of "temporal","heart","embryo","perturbation" that the change targeted or moved],
          "family": [1-3 short mechanism-family labels, e.g. "sampling", "OT drift", "spatial deformation", "composition", "lineage delay", "knockout response", "external anchor", "ensembling"]},
 "mechanism": "what was changed, in one sentence",
 "retry_condition": "for non-confirmed results: what would need to be different to justify trying again (or 'none')",
 "method_lessons": ["statistical / reasoning lessons, including valid points raised by the critic"],
 "impl_pitfalls": ["concrete implementation traps hit (crash causes, helper quirks, contract issues)"],
 "sources": ["URLs from the evidence that were actually useful"]}

Evidence class (computed by a paired, repeated test over prediction/fit seed pairs; do not override): $status (Δproxy $delta_proxy, z $z)
Per-board deltas vs parent: $deltas
Outcome: $outcome
Hypothesis: $hypothesis
Critic design review: $critique
Critic code review: $review
Implementer notes (CHANGES.md): $changes
Evaluation error (if any): $error
