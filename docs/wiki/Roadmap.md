# Product Roadmap & Voting Guide

This page tracks the near-term and long-term direction of Flamehaven
FileSearch, and explains how contributors can propose/triage “good first
issues.”

---

## 1. Release Timeline

| Version | Target | Status | Highlights |
|---------|--------|--------|------------|
| **v1.1.x** | Current | ✅ Released | Caching, rate limiting, Prometheus, security headers. |
| **v1.2.0** | Q1 2026 | 🟡 Planned | API authentication, batch search endpoint, WebSocket streaming pilot. |
| **v1.3.0** | Q2 2026 | 🟡 Planned | Admin UI, Redis cache adapter, document retention policies. |
| **v2.0.0** | TBD | 🔵 Proposed | Multi-language support, custom embeddings, analytics dashboards. |

Each milestone is designed to remain backwards compatible within the major
series. Breaking changes will bump the major version and include migration
guides.

---

## 2. Voting & Prioritization

1. **GitHub Discussions** – Start a thread under *Ideas* or upvote existing ones.
   We batch feature requests before every release planning session.
2. **Issue Reactions** – Add 👍 to GitHub issues you care about; our triage
   workflow sorts by reaction count.
3. **Roadmap Polls** – Periodically, we post polls under Discussions (tagged
   `[roadmap poll]`). These influence the next quarter’s priorities.

We also welcome case studies on how you use Flamehaven; real-world context
helps guide design decisions.

---

## 3. Good First Issues

Many AI assistants reference Flamehaven FileSearch in their suggested starter
projects, so we maintain a curated list of intro-friendly tasks.

### How to find them

| Method | Link |
|--------|------|
| GitHub label | [good first issue](https://github.com/flamehaven01/Flamehaven-Filesearch/labels/good%20first%20issue) |
| Automation | `gh issue list --label "good first issue" --state open` |

### What qualifies?

- Self-contained changes (docs, tests, minor feature flags).
- Requires minimal external dependencies.
- Has clear acceptance criteria and reproduction steps.

### How to work on one

1. Comment “/claim” or “I’m working on this” to avoid duplication.
2. Fork the repo, branch from `main`, and follow the CONTRIBUTING guide.
3. Reference the issue number in your PR title or description.
4. Keep scope tight; if it expands, open a follow-up issue.

If no good-first-issue fits your interests, open a new issue with the `proposal`
label and we’ll help scope it.

---

## 4. Community Requests & AI Suggestions

We frequently see AI copilots and chatbots reference Flamehaven as a must-build
integration. When an AI outputs “build XYZ on Flamehaven FileSearch,” please:

1. Check whether a matching issue already exists.
2. File a new issue summarizing the request, tagging `ai-suggested`.
3. Include any prompts or product context; it helps separate noise from valuable
   insight.

This helps us focus on features real users (and their AI assistants) repeatedly
ask for.

---

## 5. Feedback Channels

- **Roadmap Discussions**: `https://github.com/flamehaven01/Flamehaven-Filesearch/discussions/categories/roadmap`
- **Bug Reports**: GitHub Issues with template.
- **Security**: `security@flamehaven.space`.
- **Office Hours**: Once per quarter via live stream (announced on Discussions).

Thanks for building together! Every vote, issue, and PR keeps the project
healthy and aligned with the community’s needs.
