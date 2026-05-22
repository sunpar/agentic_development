# Parallel Wave Rules

Same-wave slices must have no dependency edge and no overlapping edit scope unless explicitly merge-safe. Serialize lockfiles, package manifests, CI config, generated files, shared schemas, migrations, global app config, public API contracts, routing tables, and shared test fixtures. High-risk slices should usually be serialized.
