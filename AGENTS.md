# Project rules

Follow `specs/chatbot.md` for every step.

## Skills (in `.claude/skills`)
- `git-workflow`: use for git init, .gitignore, branches, commits and PRs.
- `python-venv`: use when creating or using the virtual environment or installing dependencies.
- `fastapi-backend`: use when writing or changing backend endpoints and models.
- `html-frontend`: use when building or changing the HTML chat page.
- `markdown-docs`: use when writing specs, README or other documentation.
- `mermaid-sequence`: use when drawing sequence diagrams of request flows.
- `drawio-architecture`: use when drawing architecture diagrams.

## Rules
- API keys live only in `backend/.env`. Never write a real key anywhere else.
- Prompt text lives only in `backend/prompts.json`.
- Never edit `backend/llm_client.py`; use its `ask_llm()` and `MODEL`.
- Always plan before changing files.
