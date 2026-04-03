# Personal Files Assistant — CLI chatbot

## Description

This project is a **terminal conversation bot** written in Python. It runs a simple read–eval loop: you type messages, and the assistant replies. The bot is **not tied to a single LLM vendor**: conversation logic and prompts live in one place, while the actual model calls go through a small **`LLMClient` interface**. The included backend talks to **[Ollama](https://ollama.com/)** on your machine, so you can run local open models without sending data to a cloud API by default.

Session **conversation history** is folded into each request using a **text template** (separate from code), alongside a **system prompt** (also in its own file). That keeps behavior easy to tweak without editing Python.

## Requirements

- **Python 3.9+** (adjust if your environment differs).
- **Ollama** installed and running, with at least one model pulled (e.g. `ollama pull llama3.2`).

## Installation

From the project root:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Start the chat from the project directory:

```bash
python3 main.py
```

Default model is `llama3.2`. Use another Ollama model:

```bash
python3 main.py --model mistral
python3 main.py -m llama3.1
```

- **Exit:** send an empty line, or press Ctrl+C (or Ctrl+D for EOF).

Ensure the model name matches what `ollama list` shows and that the Ollama daemon is reachable (default: `http://127.0.0.1:11434`).

## How it works

### High-level flow

1. **`main.py`** parses `--model` / `-m`, constructs an **`OllamaLLM`** instance, and passes it to **`run_chat_loop`** in `chatbot.py`.
2. **`chatbot.py`** loads **`prompts/system_prompt.txt`** and **`prompts/conversation_template.txt`**, maintains an in-memory list of prior **(user, assistant)** turns, and on each user message:
   - Builds the **user** payload by filling the template with `{chat_history}` and `{user_message}`.
   - Calls **`llm.complete(system=…, user=…)`** with the system prompt and that built user text.
3. **`llm/llm.py`** defines the **`LLMClient`** protocol: any object with `complete(*, system, user) -> str` can be plugged in.
4. **`llm/ollama/ollama_llm.py`** implements that protocol using the **`ollama`** Python library (`ollama.chat` with `system` + `user` messages).

So **`chatbot.py` never imports Ollama**; only the Ollama submodule does.

### Folder structure

```
personalfilesassistant/
├── main.py                 # CLI + wires OllamaLLM → chat loop
├── chatbot.py              # Prompts, history, template, REPL (backend-agnostic)
├── requirements.txt
├── README.md
├── prompts/
│   ├── system_prompt.txt       # System message (persona / rules)
│   └── conversation_template.txt  # {chat_history}, {user_message}
└── llm/
    ├── __init__.py         # Re-exports LLMClient
    ├── llm.py              # LLMClient protocol
    └── ollama/
        ├── __init__.py     # Re-exports OllamaLLM
        └── ollama_llm.py   # Ollama implementation
```

### Customization

| What | Where |
|------|--------|
| Assistant personality / rules | `prompts/system_prompt.txt` |
| How history + latest user text are presented | `prompts/conversation_template.txt` |
| Default model name | `main.py` (`default="llama3.2"`) |
| Another LLM (OpenAI, etc.) | New module under `llm/` implementing `LLMClient`, then swap the import in `main.py` |

### Adding another backend

Implement a class with:

```python
def complete(self, *, system: str, user: str) -> str: ...
```

Pass an instance of that class to `run_chat_loop(...)` from `main.py` (or a future config-driven loader).
