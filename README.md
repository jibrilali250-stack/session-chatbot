# AI Chatbot Assistant

A full-stack AI chatbot with conversation memory and custom guardrails. 

## Features
- **Backend**: Python, FastAPI
- **Frontend**: HTML, CSS, Vanilla JavaScript
- **AI Integration**: Groq API (Llama 3) for ultra-fast responses
- **Memory**: In-memory session tracking for multi-turn conversations
- **Safety**: Custom guardrails to filter and block inappropriate content

## How to Run Locally

1. Clone this repository.
2. Create a virtual environment: `python3 -m venv .venv`
3. Activate it: `source .venv/bin/activate`
4. Install dependencies: `pip install -r backend/requirements.txt`
5. Create a `.env` file in the `backend` folder and add your Groq API key:
   `GROQ_API_KEY=your-api-key-here`
6. Start the backend: `cd backend && python -m uvicorn main:app --reload --port 8000`
7. Open a new terminal, start the frontend: `cd frontend && python3 -m http.server 5500`
8. Open `http://localhost:5500` in your browser.
