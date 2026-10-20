# Chatbot spec

## Goal
A chatbot that remembers the conversation within a session.

## Endpoints
- `GET /health`
- `POST /sessions` → `session_id`
- `POST /chat` (`session_id`, `message` 1-4000 chars) → `reply`, `input_tokens`, `output_tokens`, `seconds`, `cost`, `turns_in_memory`, `guardrail` (null or the reason)
- `GET /sessions/{session_id}` → the messages so far
- `DELETE /sessions/{session_id}`
- `GET /guardrails` and `PUT /guardrails` → read / change the guardrail settings

## Rules
- Sessions live in memory.
- Only the last `MAX_HISTORY_TURNS` turns are sent to the model.
- Guardrails run before and after the model call.
- Blocked messages are not saved.

## Errors
- 404 unknown session
- 422 bad input
- 502 LLM failure

## UI
Plain HTML chat page served on port 5500.
