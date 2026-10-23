# Contributing

Thanks for your interest in StudyForge AI.

## Setup

Follow [Getting started](README.md#getting-started). Use Python 3.11 and Node.js 20+.

## Workflow

1. Create a branch from `main`: `git checkout -b feature/short-description`.
2. Make focused changes with tests.
3. Run the checks:
   ```bash
   cd backend && ruff check . && ruff format --check . && pytest -q
   cd frontend && npm run lint && npm run typecheck && npm test && npm run build
   ```
4. Open a pull request describing what changed and how you verified it. CI must pass.

## Guidelines

- **No fabricated output.** Generated content must come from the uploaded document; if a reliable result cannot be produced, return an honest limitation instead.
- **Keep it CPU-friendly.** Do not add mandatory model downloads or GPU dependencies. Optional integrations must degrade gracefully.
- **Isolation first.** Every new endpoint that touches user data must resolve the workspace with `get_workspace` and filter by it; return 404 for other workspaces' records.
- **Never log document text** or quiz answers.
- **Backend style:** Ruff (lint + format), type hints, small pure functions in `app/nlp`, database work in `app/services`.
- **Frontend style:** reuse components in `src/components/ui`, use design tokens from `tailwind.config.js` / `index.css`, keep pages accessible (labels, roles, keyboard support).
- **Docs:** update `README.md`, `docs/` and `CHANGELOG.md` when behaviour changes.

## Reporting issues

Include the file type, approximate size, what you expected and what happened. Do not attach private study material; a minimal synthetic document that reproduces the problem is best.
