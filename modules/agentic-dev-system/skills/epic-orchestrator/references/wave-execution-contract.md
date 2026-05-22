# Wave Execution Contract

- Dispatch each task to dedicated implementor context.
- Wait for completion evidence for all tasks.
- Do not merge by default; require explicit merge opt-in.
- Run post-wave verification after an opted-in merge.
- On conflict/blocker, stop and report.
