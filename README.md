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
- **Indexed folders** (top right): paste an **absolute path** to a directory on this computer and click **Add**. The server records that folder and all **`.pdf`** files under it (recursively) in **SQLite** (`data/files_index.db`). Each folder and file has a persisted state (**NOT_STARTED**, **STARTED**, **COMPLETED**). A **background pipeline** (producer + consumer threads) picks up new or changed `.pdf` files, runs the index step (currently a **no-op**), and updates counts. The panel shows folder state and “`N` .pdf file(s) — `M` indexed”; it **polls every few seconds** so progress updates live. Exact duplicate paths are rejected; a **subfolder of an already indexed folder** is also rejected. Adding a **parent** folder removes redundant **child** rows. Browsers cannot read arbitrary disk paths, so the path field is manual; the server must run on the same machine as those files.


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

1. **`main.py`** parses arguments, constructs **`OllamaLLM`**, starts **`IndexingPipeline`** (background threads), then either:
   - **`run_web_server`** (`web_server.py`): **Flask**, **`templates/index.html`**, **`POST /api/chat`**, **`/api/index/folders`**; or
   - **`run_chat_loop`** (`chatbot.py`): terminal REPL (no indexing UI / pipeline).
2. **`indexing/FileIndexStore`** (`indexing/file_index_store.py`) persists folders and **`.pdf`** file rows (table `pending_txt_files` is legacy name) with **`state`** and **`mtime_ns`**. **`indexing/pipeline.py`** runs a **producer** (periodic filesystem scan + enqueue on new folders) and a **consumer** (dequeue → **NOT_STARTED**/**STARTED** → no-op index → **COMPLETED**). On startup, **incomplete** files (not **COMPLETED**) are re-queued so work resumes after restart. Replace **`_noop_index_file`** when you add real indexing.
3. **`indexing/states.py`** defines **`compute_folder_state`**: a folder is **COMPLETED** when every file is **COMPLETED** (or there are zero files); **NOT_STARTED** when all files are **NOT_STARTED**; otherwise **STARTED**.
4. **`chatbot.py`** loads **`prompts/system_prompt.txt`** and **`prompts/conversation_template.txt`**, maintains an in-memory list of prior **(user, assistant)** turns, and on each user message:
   - Builds the **user** payload by filling the template with `{chat_history}` and `{user_message}`.
   - Calls **`llm.complete(system=…, user=…)`** with the system prompt and that built user text.
5. **`llm/llm.py`** defines the **`LLMClient`** protocol: any object with `complete(*, system, user) -> str` can be plugged in.
6. **`llm/ollama/ollama_llm.py`** implements that protocol using the **`ollama`** Python library (`ollama.chat` with `system` + `user` messages).

So **`chatbot.py` never imports Ollama**; only the Ollama submodule does.

### Folder structure

```
personalfilesassistant/
├── main.py                 # Entry: web UI (default) or --cli
├── web_server.py           # Flask app + /api/chat + /api/index/folders
├── indexing/
│   ├── file_index_store.py # SQLite + scans
│   ├── pipeline.py         # Producer / consumer threads + queue
│   └── states.py           # NOT_STARTED / STARTED / COMPLETED rules
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
