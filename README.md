# Personal Files Assistant — local chatbot

## Description

This project is a **local conversation bot** written in Python. By default it serves a **small web UI** on your machine; you can also use a **terminal chat loop**. The bot is **not tied to a single LLM vendor**: conversation logic and prompts live in one place, while the actual model calls go through a small **`LLMClient` interface**. The included backend talks to **[Ollama](https://ollama.com/)** on your machine, so you can run local open models without sending data to a cloud API by default.

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

### Web UI (default)

Starts an HTTP server on **localhost** using port **8080** by default — **not** Ollama’s API port (typically **11434**).

```bash
python3 main.py
```

Then open the URL printed in the terminal (usually `http://127.0.0.1:8080/`). A browser tab may open automatically; use **`--no-browser`** to disable that.

- **History** appears above the text box; each reply updates the list.
- **Send** with the button or **Enter** (Shift+Enter for a newline).
- **Indexed folders** (top right): paste an **absolute path** to a directory on this computer and click **Add**. The server records that folder and all **`.txt`** files under it (recursively) in a **SQLite** database (`data/files_index.db`). Exact duplicate paths are rejected; a **subfolder of an already indexed folder** is also rejected (nested coverage). If you add a **parent** folder later, any indexed **child** folders under it are removed and replaced by the parent scan. Browsers cannot read arbitrary disk paths, so the path field is manual; the server must run on the same machine as those files.


Options:

```bash
python3 main.py -p 9000                    # custom port
python3 main.py --host 127.0.0.1 --port 8080
python3 main.py --model mistral            # Ollama model name
python3 main.py --no-browser
```

Stop the server with **Ctrl+C**.

### Terminal chat (`--cli`)

```bash
python3 main.py --cli
```

- **Exit:** send an empty line, or press Ctrl+C (or Ctrl+D for EOF).

Ensure the model name matches what `ollama list` shows and that the Ollama daemon is reachable (default: `http://127.0.0.1:11434`).

## How it works

### High-level flow

1. **`main.py`** parses arguments, constructs **`OllamaLLM`**, then either:
   - **`run_web_server`** (`web_server.py`): starts **Flask**, serves **`templates/index.html`**, **`POST /api/chat`**, and **`/api/index/folders`** (list / add indexed directories); or
   - **`run_chat_loop`** (`chatbot.py`): terminal REPL (no indexing UI).
2. **`indexing/FileIndexStore`** (`indexing/file_index_store.py`) persists chosen folder paths and discovered **`.txt`** paths in SQLite. **Content indexing is not implemented yet** — only paths are stored for future use.
3. **`chatbot.py`** loads **`prompts/system_prompt.txt`** and **`prompts/conversation_template.txt`**, maintains an in-memory list of prior **(user, assistant)** turns, and on each user message:
   - Builds the **user** payload by filling the template with `{chat_history}` and `{user_message}`.
   - Calls **`llm.complete(system=…, user=…)`** with the system prompt and that built user text.
4. **`llm/llm.py`** defines the **`LLMClient`** protocol: any object with `complete(*, system, user) -> str` can be plugged in.
5. **`llm/ollama/ollama_llm.py`** implements that protocol using the **`ollama`** Python library (`ollama.chat` with `system` + `user` messages).

So **`chatbot.py` never imports Ollama**; only the Ollama submodule does.

### Folder structure

```
personalfilesassistant/
├── main.py                 # Entry: web UI (default) or --cli
├── web_server.py           # Flask app + /api/chat + /api/index/folders
├── indexing/               # Folder / file registry (extend here for real indexing)
│   └── file_index_store.py
├── chatbot.py              # Prompts, history, template, REPL (backend-agnostic)
├── data/                   # Created at runtime; SQLite DB (gitignored)
├── requirements.txt
├── README.md
├── templates/
│   └── index.html          # Web UI
├── prompts/
│   ├── system_prompt.txt
│   └── conversation_template.txt
└── llm/
    ├── __init__.py
    ├── llm.py              # LLMClient protocol
    └── ollama/
        ├── __init__.py
        └── ollama_llm.py
```

### Customization

| What | Where |
|------|--------|
| Assistant personality / rules | `prompts/system_prompt.txt` |
| How history + latest user text are presented | `prompts/conversation_template.txt` |
| Default model / web port | `main.py` |
| Another LLM (OpenAI, etc.) | New module under `llm/` implementing `LLMClient`, then swap the import in `main.py` |

### Adding another backend

Implement a class with:

```python
def complete(self, *, system: str, user: str) -> str: ...
```

Pass an instance of that class to `run_chat_loop(...)` or `run_web_server(...)` from `main.py`.
