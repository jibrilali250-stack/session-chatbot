"""Chatbot API with session management and conversation history."""
import os
import uuid
from typing import Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import guardrails
from llm_client import MODEL, ask_llm

load_dotenv()

# Configuration
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))

# In-memory session store
sessions: Dict[str, List[dict]] = {}

app = FastAPI(title="Chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5500")],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions")
def create_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    return {"session_id": session_id}


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get the message history for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": sessions[session_id]}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[session_id]
    return {"status": "deleted"}


@app.get("/guardrails")
def get_guardrails():
    return guardrails.load_config()


@app.put("/guardrails")
def put_guardrails(config: guardrails.GuardrailConfig):
    guardrails.save_config(config)
    return config


@app.post("/chat")
def chat(req: ChatRequest):
    config = guardrails.load_config()

    # Validate session if provided
    if req.session_id:
        if req.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        history = sessions[req.session_id]
    else:
        history = []

    allowed, text, reason = guardrails.check_input(req.message, config)
    if not allowed:
        return _blocked(config, reason)
    input_reason = reason  # None or "masked: ..."

    # Build conversation context with history
    prompt = _build_prompt_with_history(history, text)

    try:
        result = ask_llm(prompt, model=MODEL)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM failure: {e}")

    allowed, reply, reason = guardrails.check_output(result["text"], config)
    if not allowed:
        return _blocked(config, reason)

    # Save to session history if session_id provided
    turns_in_memory = 0
    if req.session_id:
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": reply})
        
        # Keep only the last MAX_HISTORY_TURNS turns (each turn = user + assistant pair)
        if len(history) > MAX_HISTORY_TURNS * 2:
            sessions[req.session_id] = history[-(MAX_HISTORY_TURNS * 2):]
        
        turns_in_memory = len(sessions[req.session_id]) // 2

    return {
        "reply": reply,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "seconds": result["seconds"],
        "cost": result["cost"],
        "turns_in_memory": turns_in_memory,
        "guardrail": input_reason,
    }


def _build_prompt_with_history(history: List[dict], current_message: str) -> str:
    """Build a prompt that includes conversation history."""
    if not history:
        return current_message
    
    # Take only the last MAX_HISTORY_TURNS turns for context
    recent_history = history[-(MAX_HISTORY_TURNS * 2):]
    
    # Format conversation history
    conversation = []
    for msg in recent_history:
        if msg["role"] == "user":
            conversation.append(f"User: {msg['content']}")
        elif msg["role"] == "assistant":
            conversation.append(f"Assistant: {msg['content']}")
    
    # Add current message
    conversation.append(f"User: {current_message}")
    
    # Build the full prompt with context
    prompt = "Continue this conversation:\n\n" + "\n\n".join(conversation)
    return prompt


def _blocked(config, reason):
    return {
        "reply": config.blocked_message,
        "input_tokens": 0,
        "output_tokens": 0,
        "seconds": 0,
        "cost": None,
        "turns_in_memory": 0,
        "guardrail": reason,
    }
