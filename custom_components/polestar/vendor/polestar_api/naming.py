"""Small naming helpers (no imports, so anything can use them)."""

from __future__ import annotations


def model_from_slug(slug: str | None) -> str | None:
    """"polestar-2" -> "Polestar 2". Used when neither discovery nor C3 names the model."""
    if not slug or not isinstance(slug, str):
        return None
    words = [w for w in slug.replace("_", "-").split("-") if w]
    if not words:
        return None
    return " ".join([words[0].capitalize(), *words[1:]])
