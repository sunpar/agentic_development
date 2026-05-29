# Copilot Review Policy

This reference supports `slice-agent-review-loop`.

Keep work evidence-based, bounded, GPT 5.5 extra-high-reasoning, and safe. Prefer concise artifacts that a human reviewer can audit. Cite files/docs used for claims. Avoid scope expansion. Use dry-run behavior for scripts before mutating target repositories.

For GitHub PRs, request Copilot review with `gh pr edit <PR> --add-reviewer @copilot`. When used with Codex review, submit both requests in parallel and wait for Copilot-specific review activity for up to 10 minutes before recording a timeout.
