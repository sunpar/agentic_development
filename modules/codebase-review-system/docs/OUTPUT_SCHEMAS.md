# Output Schemas

Schemas live in `schemas/` and are intentionally JSON-Schema compatible, while validators use Python stdlib checks. The main contracts are `feature_model`, `slice_plan`, `slice_result`, `wave_result`, and `pr_review_loop`.

`feature_model.schema.json` and `slice_plan.schema.json` mirror the stricter validator behavior for required fields, nonempty arrays where execution needs concrete context, ID and branch-name patterns, slice type and risk enums, positive expected PR size fields, and nonempty wave membership.

The Python validators remain authoritative for cross-object checks that JSON Schema cannot express cleanly, including duplicate IDs, unknown dependencies, dependency cycles, dependency wave ordering, same-wave edit conflicts, and declared same-wave parallel conflicts.
