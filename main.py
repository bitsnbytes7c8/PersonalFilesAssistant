"""Entry point: wire CLI to an LLM backend and start the local web UI."""

import argparse
import webbrowser
from pathlib import Path
from threading import Timer

from chatbot import run_chat_loop
from indexing import FileIndexStore
from llm.ollama import OllamaLLM
from web_server import run_web_server

_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_DB = _PROJECT_ROOT / "data" / "files_index.db"


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversation bot")
    parser.add_argument(
        "--model",
        "-m",
        default="llama3.2",
        help="Ollama model name (default: %(default)s)",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Use the terminal chat loop instead of the web UI",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Web server bind address (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8080,
        help="Web server port — not Ollama's port (default: %(default)s; Ollama API is usually 11434)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser tab automatically",
    )
    args = parser.parse_args()
    llm = OllamaLLM(model=args.model)

    if args.cli:
        run_chat_loop(llm)
        return

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:

        def open_browser() -> None:
            webbrowser.open(url)

        Timer(0.35, open_browser).start()

    print(f"Web UI: {url}")
    print("Press Ctrl+C to stop.\n")
    index_store = FileIndexStore(_DEFAULT_DB)
    run_web_server(llm, host=args.host, port=args.port, index_store=index_store)


if __name__ == "__main__":
    main()
