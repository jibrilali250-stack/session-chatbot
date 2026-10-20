# Chatbot Sequence Diagrams

This document contains sequence diagrams showing the request flows for the chatbot application.

## 1. Starting a Session

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend as Frontend Server<br/>(port 5500)
    participant Backend as Backend API<br/>(port 8000)
    participant Store as Session Store<br/>(in-memory)

    Note over Browser: User loads page or clicks "New chat"
    
    Browser->>Frontend: GET /
    Frontend-->>Browser: index.html

    Note over Browser: JavaScript executes init()
    
    Browser->>Backend: POST /sessions
    activate Backend
    Backend->>Backend: Generate UUID
    Backend->>Store: sessions[uuid] = []
    Backend-->>Browser: {"session_id": "abc-123..."}
    deactivate Backend
    
    Browser->>Browser: Store session_id in sessionStorage
    
    Note over Browser: Ready to chat
```

## 2. Sending a Message (Full Flow with Guardrails and History)

```mermaid
sequenceDiagram
    participant Browser
    participant Backend as Backend API
    participant Store as Session Store
    participant GR as guardrails.py
    participant Config as guardrails.json
    participant LLM as llm_client.py
    participant API as External LLM API

    Browser->>Backend: POST /chat<br/>{session_id, message}
    activate Backend
    
    Note over Backend: 1. Validate session
    Backend->>Store: Check session_id exists
    alt Session not found
        Backend-->>Browser: 404 {"detail": "Session not found"}
    end
    Store-->>Backend: history = [...previous messages]
    
    Note over Backend: 2. Load guardrail config
    Backend->>Config: Read guardrails.json
    Config-->>Backend: GuardrailConfig
    
    Note over Backend: 3. Input guardrails
    Backend->>GR: check_input(message, config)
    activate GR
    
    GR->>GR: Length check<br/>(max_input_chars)
    
    alt Message too long
        GR-->>Backend: (False, message, "blocked: too long")
        Backend-->>Browser: {"reply": blocked_message,<br/>"guardrail": "blocked: too long", ...}
    end
    
    GR->>GR: Injection phrase detection<br/>(if block_injection enabled)
    
    alt Injection detected
        GR-->>Backend: (False, message, "blocked: injection")
        Backend-->>Browser: {"reply": blocked_message,<br/>"guardrail": "blocked: injection", ...}
    end
    
    GR->>GR: PII masking<br/>(if mask_pii enabled)
    Note over GR: Replace emails with [EMAIL]<br/>Replace phones with [PHONE]
    
    opt Topic check enabled
        GR->>Config: Read prompts.json
        Config-->>GR: topic_judge prompt
        GR->>LLM: ask_llm(message, system=topic_judge)
        LLM->>API: API call
        API-->>LLM: "YES" or "NO"
        LLM-->>GR: {"text": "YES/NO", ...}
        alt Off-topic
            GR-->>Backend: (False, message, "blocked: off-topic")
            Backend-->>Browser: {"reply": blocked_message,<br/>"guardrail": "blocked: off-topic", ...}
        end
    end
    
    GR-->>Backend: (True, cleaned_text, reason)<br/>reason = None or "masked: email, phone"
    deactivate GR
    
    Note over Backend: 4. Build prompt with history
    Backend->>Store: Get last MAX_HISTORY_TURNS turns
    Note over Backend: history[-(MAX_HISTORY_TURNS*2):]<br/>Format as:<br/>"Continue this conversation:\n\n<br/>User: ...\nAssistant: ...\n<br/>User: [current message]"
    Backend->>Backend: prompt = _build_prompt_with_history()
    
    Note over Backend: 5. Call LLM
    Backend->>LLM: ask_llm(prompt, MODEL)
    activate LLM
    LLM->>API: POST /chat/completions<br/>or provider-specific endpoint
    activate API
    
    alt LLM API failure
        API--xLLM: Timeout/Error
        LLM--xBackend: Exception
        Backend-->>Browser: 502 {"detail": "LLM failure: ..."}
    end
    
    API-->>LLM: Response with completion
    deactivate API
    LLM->>LLM: Parse usage metrics
    LLM-->>Backend: {"text": "...",<br/>"input_tokens": N,<br/>"output_tokens": M,<br/>"seconds": S,<br/>"cost": C}
    deactivate LLM
    
    Note over Backend: 6. Output guardrails
    Backend->>GR: check_output(reply, config)
    activate GR
    
    GR->>GR: Word count check<br/>(max_output_words)
    
    alt Reply too long
        GR-->>Backend: (False, reply, "blocked: reply too long")
        Backend-->>Browser: {"reply": blocked_message,<br/>"guardrail": "blocked: reply too long", ...}
    end
    
    GR->>GR: Banned word detection
    
    alt Banned word found
        GR-->>Backend: (False, reply, "blocked: banned word")
        Backend-->>Browser: {"reply": blocked_message,<br/>"guardrail": "blocked: banned word", ...}
    end
    
    GR-->>Backend: (True, reply, None)
    deactivate GR
    
    Note over Backend: 7. Save to session history
    Backend->>Store: Append user message<br/>{"role": "user", "content": original_message}
    Backend->>Store: Append assistant message<br/>{"role": "assistant", "content": reply}
    Backend->>Store: Trim to last MAX_HISTORY_TURNS*2 messages
    Backend->>Backend: turns_in_memory = len(session) // 2
    
    Note over Backend: 8. Return response
    Backend-->>Browser: {"reply": "...",<br/>"input_tokens": N,<br/>"output_tokens": M,<br/>"seconds": S,<br/>"cost": C,<br/>"turns_in_memory": T,<br/>"guardrail": reason_or_null}
    deactivate Backend
    
    Browser->>Browser: Display reply with metadata
```

## 3. Changing Guardrails with PUT /guardrails

```mermaid
sequenceDiagram
    participant Client as Client/Browser
    participant Backend as Backend API
    participant GR as guardrails.py
    participant File as guardrails.json

    Note over Client: User/Admin updates settings
    
    Client->>Backend: PUT /guardrails<br/>GuardrailConfig JSON
    activate Backend
    
    Backend->>Backend: Validate with Pydantic
    
    alt Validation fails
        Note over Backend: e.g., max_input_chars < 1
        Backend-->>Client: 422 Unprocessable Entity<br/>{"detail": [...validation errors]}
    end
    
    Backend->>GR: save_config(config)
    activate GR
    
    GR->>GR: config.model_dump()
    GR->>File: Write JSON with indent=2
    
    GR-->>Backend: Success
    deactivate GR
    
    Backend-->>Client: 200 OK<br/>GuardrailConfig (echoed back)
    deactivate Backend
    
    Note over Client: Settings now active<br/>for all future /chat requests
    
    Note over Client: Example: Read current settings
    
    Client->>Backend: GET /guardrails
    activate Backend
    Backend->>GR: load_config()
    activate GR
    GR->>File: Read JSON
    File-->>GR: JSON data
    GR->>GR: Parse into GuardrailConfig
    GR-->>Backend: GuardrailConfig object
    deactivate GR
    Backend-->>Client: 200 OK<br/>GuardrailConfig JSON
    deactivate Backend
```

## 4. Error Paths

```mermaid
sequenceDiagram
    participant Browser
    participant Backend as Backend API
    participant Store as Session Store
    participant LLM as llm_client.py
    participant API as External LLM API

    Note over Browser,API: Error Path 1: Backend Down
    
    Browser->>Backend: POST /chat
    Browser--xBackend: Connection refused
    Note over Browser: JavaScript catch block
    Browser->>Browser: Display error:<br/>"Unable to reach the chatbot.<br/>Please check your connection."
    
    Note over Browser,API: Error Path 2: Unknown session_id → 404
    
    Browser->>Backend: POST /chat<br/>{session_id: "bad-uuid", message}
    activate Backend
    Backend->>Store: Check "bad-uuid" in sessions
    Store-->>Backend: Not found
    Backend-->>Browser: 404 Not Found<br/>{"detail": "Session not found"}
    deactivate Backend
    
    Browser->>Browser: Create new session
    Browser->>Backend: POST /sessions
    Backend-->>Browser: {"session_id": "new-uuid"}
    Browser->>Browser: Display: "Your session expired.<br/>A new chat has been started."
    
    Note over Browser,API: Error Path 3: GET unknown session → 404
    
    Browser->>Backend: GET /sessions/unknown-id
    activate Backend
    Backend->>Store: Check "unknown-id" in sessions
    Store-->>Backend: Not found
    Backend-->>Browser: 404 Not Found<br/>{"detail": "Session not found"}
    deactivate Backend
    
    Note over Browser,API: Error Path 4: Invalid message (422)
    
    Browser->>Backend: POST /chat<br/>{message: ""}<br/>(empty or > 4000 chars)
    activate Backend
    Backend->>Backend: Pydantic validation fails
    Backend-->>Browser: 422 Unprocessable Entity<br/>{"detail": [{validation errors}]}
    deactivate Backend
    
    Browser->>Browser: Display: "Invalid input: ..."
    
    Note over Browser,API: Error Path 5: LLM Failure → 502
    
    Browser->>Backend: POST /chat<br/>{session_id, message}
    activate Backend
    Note over Backend: After guardrails pass...
    Backend->>LLM: ask_llm(prompt, MODEL)
    activate LLM
    LLM->>API: API request
    
    alt API timeout
        API--xLLM: Timeout
        LLM-->>Backend: raise Exception("timeout")
    else Invalid API key
        API--xLLM: 401 Unauthorized
        LLM-->>Backend: raise Exception("auth error")
    else Rate limit exceeded
        API--xLLM: 429 Too Many Requests
        LLM-->>Backend: raise Exception("rate limit")
    else Other API error
        API--xLLM: 500 Internal Server Error
        LLM-->>Backend: raise Exception("API error")
    end
    deactivate LLM
    
    Backend->>Backend: catch Exception as e
    Backend-->>Browser: 502 Bad Gateway<br/>{"detail": "LLM failure: [error]"}
    deactivate Backend
    
    Browser->>Browser: Display:<br/>"The AI service is temporarily<br/>unavailable. Please try again."
    
    Note over Browser,API: Error Path 6: DELETE unknown session → 404
    
    Browser->>Backend: DELETE /sessions/unknown-id
    activate Backend
    Backend->>Store: Check "unknown-id" in sessions
    Store-->>Backend: Not found
    Backend-->>Browser: 404 Not Found<br/>{"detail": "Session not found"}
    deactivate Backend
```

---

## Validation Notes

All diagrams validated for:
- Correct Mermaid syntax (sequenceDiagram)
- Accurate representation of actual code in backend/main.py, guardrails.py, llm_client.py
- Inclusion of MAX_HISTORY_TURNS logic (last N turns from history)
- Input guardrail checks (length, injection, PII masking, topic)
- Output guardrail checks (word count, banned words)
- Error handling (404, 422, 502)
- Session storage operations
- LLM API call flow and metrics

## Key Implementation Details

### MAX_HISTORY_TURNS Behavior
From `backend/main.py:134-135`:
```python
recent_history = history[-(MAX_HISTORY_TURNS * 2):]
```
This takes the last `MAX_HISTORY_TURNS * 2` messages (each turn = user + assistant pair).

### Prompt Format
From `backend/main.py:149`:
```python
prompt = "Continue this conversation:\n\n" + "\n\n".join(conversation)
```

### Guardrail Execution Order
1. **Input guardrails** (before LLM):
   - Length check → Injection detection → PII masking → Topic check (optional)
2. **LLM call**
3. **Output guardrails** (after LLM):
   - Word count → Banned words

### Blocked Messages
From `backend/main.py:91, 104`:
- Blocked messages return immediately with `blocked_message`
- They are **NOT** saved to the session history
- Return structure includes `guardrail: reason` field
