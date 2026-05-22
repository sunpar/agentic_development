# Model Policy

This file name is retained for compatibility with the original installed layout. The current policy is intentionally not model-neutral: system-controlled agents and scripts use the explicit model matrix below. Do not change global Codex model/profile/provider settings.

- `wave-orchestrator`: `gpt-5.3-codex-spark`, `model_reasoning_effort = "xhigh"`
- `ci-debugger`: `gpt-5.3-codex-spark`, `model_reasoning_effort = "xhigh"`
- `pr-review-manager`: `gpt-5.5`, `model_reasoning_effort = "medium"`
- `slice-refactorer`: `gpt-5.5`, `model_reasoning_effort = "medium"`
- all other module agents and direct Codex slice runners: `gpt-5.5`, `model_reasoning_effort = "xhigh"`

Scripts may accept optional `--codex-profile`, `--codex-agent`, and `--codex-extra-args` for environment configuration, but they must not switch to a model or reasoning effort outside this policy.
