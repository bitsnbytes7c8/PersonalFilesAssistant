"""Local HTTP server for the chat UI — separate from Ollama's port."""

from __future__ import annotations

import threading

from flask import Flask, jsonify, render_template, request

from chatbot import chat_once, load_conversation_template, load_system_prompt
from llm import LLMClient


def create_app(llm: LLMClient) -> Flask:
    app = Flask(__name__)
    system_prompt = load_system_prompt()
    conversation_template = load_conversation_template()
    history: list[tuple[str, str]] = []
    lock = threading.Lock()

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/api/chat")
    def api_chat():
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message is empty"}), 400
        try:
            with lock:
                reply = chat_once(
                    llm,
                    system_prompt,
                    conversation_template,
                    history,
                    user_message,
                )
                history.append((user_message, reply))
                turns = [{"user": u, "assistant": a} for u, a in history]
            return jsonify({"turns": turns})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


def run_web_server(llm: LLMClient, *, host: str, port: int) -> None:
    app = create_app(llm)
    # threaded=True so the browser can open while a long LLM call runs
    app.run(host=host, port=port, threaded=True, use_reloader=False)


__all__ = ["create_app", "run_web_server"]
