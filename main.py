"""Entry point: wire CLI to an LLM backend and start the chat loop."""

import argparse

from chatbot import run_chat_loop
from llm.ollama import OllamaLLM


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversation bot")
    parser.add_argument(
        "--model",
        "-m",
        default="llama3.2",
        help="Ollama model name (default: %(default)s)",
    )
    args = parser.parse_args()
    run_chat_loop(OllamaLLM(model=args.model))


if __name__ == "__main__":
    main()
