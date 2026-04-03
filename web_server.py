"""Local HTTP server for the chat UI — separate from Ollama's port."""

from __future__ import annotations

import threading

from flask import Flask, jsonify, render_template, request

from chatbot import chat_once, load_conversation_template, load_system_prompt
from indexing import FileIndexStore
from llm import LLMClient


def create_app(llm: LLMClient, index_store: FileIndexStore) -> Flask:
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

    @app.get("/api/index/folders")
    def api_list_folders():
        try:
            folders = index_store.list_folders()
            return jsonify({"folders": folders})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/index/folders")
    def api_add_folder():
        data = request.get_json(silent=True) or {}
        path = (data.get("path") or "").strip()
        if not path:
            return jsonify({"error": "Path is empty"}), 400
        result = index_store.add_folder(path)
        if not result.ok:
            return jsonify({"error": result.error or "Failed to add folder"}), 400
        return jsonify(
            {
                "folder_path": result.folder_path,
                "txt_files_stored": result.txt_files_stored,
                "folders": index_store.list_folders(),
            }
        )

    return app


def run_web_server(
    llm: LLMClient,
    *,
    host: str,
    port: int,
    index_store: FileIndexStore,
) -> None:
    app = create_app(llm, index_store)
    # threaded=True so the browser can open while a long LLM call runs
    app.run(host=host, port=port, threaded=True, use_reloader=False)


__all__ = ["create_app", "run_web_server"]
