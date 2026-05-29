# Review Comment Resolution

This reference supports `slice-agent-review-loop`.

## Procedure

Fetch thread-aware review comments when resolution state matters. Treat flat comment lists as classification input only. Reply to and resolve GitHub threads only when the user explicitly asks for that write action or the orchestrator is running an authorized repair loop.

## Commands

```bash
python3 ~/.codex/codebase-review-factory/scripts/poll_review_comments.py --pr 123 --output-json actionable-review-report.json --output-md actionable-review-report.md
gh api graphql -f query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved isOutdated path line comments(first:20){nodes{id body author{login}}}}}}}}' -f owner=OWNER -f name=REPO -F number=123
```

## Output Contract

- Group feedback by `must_fix`, `should_fix`, and `info`.
- Include provider counts for Codex, Copilot, human, and unknown reviewers.
- For each handled thread, reply with the commit or evidence that addressed it.
- Resolve only threads that are no longer active or were explicitly handled.

## Good Example

`Fixed the P1 review-thread resolution bug in cf49086, added test_review_repair_resolves_only_threads_no_longer_active, replied on the thread, and resolved only that thread.`

## Bad Example

`Resolved every open thread after one repair commit without checking which comments were addressed.`
