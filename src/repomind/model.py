"""Optional local model. The investigation still runs when this is absent."""

from __future__ import annotations

import os
from pathlib import Path

MODELS = {
    "1.5b": {
        "repo": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "file": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    },
    "7b": {
        "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    },
}


def cache_dir() -> Path:
    override = os.environ.get("REPOMIND_MODEL_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "repomind" / "models"


def model_path(size: str = "1.5b") -> Path | None:
    spec = MODELS[size]
    path = cache_dir() / spec["file"]
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    return None


def llama_available() -> bool:
    try:
        import llama_cpp  # noqa: F401
    except Exception:
        return False
    return True


def download(size: str = "1.5b") -> Path:
    if size not in MODELS:
        raise ValueError("Size must be 1.5b or 7b.")
    spec = MODELS[size]
    destination = cache_dir() / spec["file"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 1_000_000:
        return destination
    url = f"https://huggingface.co/{spec['repo']}/resolve/main/{spec['file']}"
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "Install the model extra first: pip install \"repomind-local[model]\""
        ) from exc
    downloaded = hf_hub_download(
        repo_id=spec["repo"],
        filename=spec["file"],
        local_dir=str(destination.parent),
    )
    return Path(downloaded)


def rewrite(summary: str, evidence: str) -> str | None:
    """Ask the local model for a shorter case note. Return None if it cannot run."""
    path = model_path()
    if path is None or not llama_available():
        return None
    from llama_cpp import Llama

    llm = Llama(model_path=str(path), n_ctx=4096, verbose=False)
    result = llm.create_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You write a two-sentence case note for a code investigation. "
                    "Use only the facts you are given. Do not add findings, files, or causes."
                ),
            },
            {
                "role": "user",
                "content": f"Facts:\n{evidence}\n\nDraft:\n{summary}",
            },
        ],
        temperature=0.1,
        max_tokens=220,
    )
    text = result["choices"][0]["message"]["content"]
    cleaned = " ".join(text.split())
    return cleaned or None
