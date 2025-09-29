# Windsurf Workflow Checklist

## Daily Setup
- [ ] Pull latest changes from main branch
- [ ] Activate poetry/venv and ensure dependencies installed
- [ ] Start backend services (Postgres, FastAPI via gunicorn or uvicorn)
- [ ] Launch frontend dev server (if applicable)
- [ ] Verify .env configuration matches environment (API keys, DB URL)

## Task Intake
- [ ] Read issue/ticket description and acceptance criteria
- [ ] Review related files or previous tasks in docs/
- [ ] Confirm target branch and code ownership guidelines
- [ ] Update docs/todo.md with tasks in progress

## Development Loop
- [ ] Create/update plan using Cascade `update_plan`
- [ ] Implement backend changes with minimal diff via `apply_patch`
- [ ] Implement frontend changes and keep styling consistent
- [ ] Run relevant automated tests (pytest, frontend tests)
- [ ] Perform manual QA (HTTP requests, UI interactions)
- [ ] Log or capture evidence of fixes (screenshots, console output)

## Review & Documentation
- [ ] Update docs/done.md and docs/todo.md accordingly
- [ ] Note configuration or deployment steps in docs/
- [ ] Ensure new endpoints/components are documented
- [ ] Mention migration or schema changes explicitly

## Delivery
- [ ] Summarize changes with sections: Summary, Verification, Recommended Actions
- [ ] Provide commands for verification (tests, service restarts)
- [ ] Highlight follow-up work or known limitations
- [ ] Confirm deployment status or next steps
