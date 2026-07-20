"""Core retrieval and local-LLM helpers for the personal digital twin."""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


WORD_PATTERN = re.compile(r"[a-z0-9+#.-]+")

# Small synonym groups make common questions useful without a vector database.
SYNONYM_GROUPS = (
    {"work", "job", "career", "experience", "profession", "do"},
    {"skill", "skills", "technology", "technologies", "tools", "stack"},
    {"study", "studied", "education", "degree", "university", "college"},
    {"project", "projects", "built", "build", "portfolio"},
    {"interest", "interests", "hobby", "hobbies", "enjoy"},
    {"contact", "email", "github", "linkedin", "reach"},
    {"location", "live", "based", "city", "country"},
)


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load and validate a profile JSON file."""
    profile_path = Path(path)
    with profile_path.open(encoding="utf-8") as profile_file:
        profile = json.load(profile_file)

    if not isinstance(profile, dict) or not profile:
        raise ValueError("Profile must be a non-empty JSON object.")
    return profile


def _readable_label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return "; ".join(
            f"{_readable_label(str(key))}: {_format_value(item)}"
            for key, item in value.items()
        )
    if isinstance(value, list):
        return ", ".join(_format_value(item) for item in value)
    return str(value)


def build_chunks(profile: dict[str, Any]) -> list[dict[str, str]]:
    """Turn profile sections into small searchable text chunks."""
    chunks: list[dict[str, str]] = []
    for section, value in profile.items():
        label = _readable_label(str(section))
        if isinstance(value, list) and value and all(
            isinstance(item, dict) for item in value
        ):
            for index, item in enumerate(value, start=1):
                chunks.append(
                    {
                        "section": label,
                        "text": f"{label} {index}: {_format_value(item)}",
                    }
                )
        else:
            chunks.append({"section": label, "text": f"{label}: {_format_value(value)}"})
    return chunks


def _tokens(text: str) -> set[str]:
    tokens = set(WORD_PATTERN.findall(text.lower()))
    expanded = set(tokens)
    for group in SYNONYM_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


def retrieve_context(
    question: str, chunks: list[dict[str, str]], limit: int = 3
) -> list[dict[str, str]]:
    """Return the most relevant profile chunks using lightweight token scoring."""
    query_tokens = _tokens(question)
    if not query_tokens or limit < 1:
        return []

    scored: list[tuple[float, int, dict[str, str]]] = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = _tokens(f"{chunk['section']} {chunk['text']}")
        overlap = query_tokens & chunk_tokens
        if overlap:
            # Reward matches but avoid favoring long chunks too heavily.
            score = len(overlap) / math.sqrt(max(len(chunk_tokens), 1))
            scored.append((score, -index, chunk))

    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def retrieval_answer(question: str, context: list[dict[str, str]]) -> str:
    """Create a useful no-model answer so the project always runs."""
    if not context:
        return (
            "I could not find that in my profile yet. Add the information to "
            "`data/profile.json`, then ask me again."
        )

    details = "\n".join(f"- {item['text']}" for item in context)
    return f"Here is the most relevant information from my profile:\n\n{details}"


def ollama_answer(
    question: str,
    context: list[dict[str, str]],
    model: str = "llama3.2:3b",
    base_url: str = "http://localhost:11434",
    timeout: int = 90,
) -> str:
    """Ask a local Ollama model to answer only from retrieved profile data."""
    if not context:
        return retrieval_answer(question, context)

    context_text = "\n".join(item["text"] for item in context)
    prompt = f"""You are a personal digital twin.
Answer in first person, using only the PROFILE CONTEXT below.
If the context does not contain the answer, say you do not know.
Keep the answer friendly, clear, and under 120 words.

PROFILE CONTEXT:
{context_text}

QUESTION:
{question}
"""

    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    answer = response_data.get("response", "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty response.")
    return answer


def answer_question(
    question: str,
    chunks: list[dict[str, str]],
    use_ollama: bool = False,
    model: str = "llama3.2:3b",
    base_url: str = "http://localhost:11434",
) -> tuple[str, list[dict[str, str]], str]:
    """Retrieve profile context and answer with Ollama or the built-in fallback."""
    context = retrieve_context(question, chunks)
    if use_ollama:
        try:
            return ollama_answer(question, context, model, base_url), context, "Ollama"
        except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError):
            return retrieval_answer(question, context), context, "Built-in fallback"
    return retrieval_answer(question, context), context, "Built-in retrieval"
