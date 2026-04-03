"""Conversational chat with templated prompts and session history — backend-agnostic."""

from __future__ import annotations

from pathlib import Path

from llm import LLMClient

_PROJECT_ROOT = Path(__file__).resolve().parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "system_prompt.txt"
_CONVERSATION_TEMPLATE_PATH = _PROMPTS_DIR / "conversation_template.txt"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt() -> str:
    return _read_text(_SYSTEM_PROMPT_PATH)


def load_conversation_template() -> str:
    return _read_text(_CONVERSATION_TEMPLATE_PATH)


def format_chat_history(history: list[tuple[str, str]]) -> str:
    """Format prior (user, assistant) turns as plain text for the template."""
    if not history:
        return "(No prior messages in this session.)"
    lines: list[str] = []
    for user_text, assistant_text in history:
        lines.append(f"User: {user_text}")
        lines.append(f"Assistant: {assistant_text}")
        lines.append("")
    return "\n".join(lines).strip()


def build_user_message(template: str, history: list[tuple[str, str]], user_message: str) -> str:
    return template.format(
        chat_history=format_chat_history(history),
        user_message=user_message,
    )


def chat_once(
    llm: LLMClient,
    system_prompt: str,
    conversation_template: str,
    history: list[tuple[str, str]],
    user_message: str,
) -> str:
    user_content = build_user_message(conversation_template, history, user_message)
    return llm.complete(system=system_prompt, user=user_content)


def run_chat_loop(llm: LLMClient) -> None:
    system_prompt = load_system_prompt()
    conversation_template = load_conversation_template()
    history: list[tuple[str, str]] = []

    label = getattr(llm, "model", None) or type(llm).__name__
    print(f"LLM: {label} (Ctrl+C or empty line to exit)\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            break

        reply = chat_once(
            llm=llm,
            system_prompt=system_prompt,
            conversation_template=conversation_template,
            history=history,
            user_message=user_input,
        )
        history.append((user_input, reply))
        print(f"Assistant: {reply}\n")


__all__ = [
    "build_user_message",
    "chat_once",
    "format_chat_history",
    "load_conversation_template",
    "load_system_prompt",
    "run_chat_loop",
]
