"""Shared helpers: load/save the catalog and walk its files."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.json"
SCHEMA = ROOT / "schema" / "catalog.schema.json"

# A delivery URL must point at an immutable commit, never a branch.
PINNED_URL = re.compile(
    r"^https://(huggingface\.co/[^/]+/[^/]+/resolve|raw\.githubusercontent\.com/[^/]+/[^/]+)/[0-9a-f]{40}/"
)


def load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def save(catalog: dict) -> None:
    # Keep the file stable for diffs: 2-space indent, non-ASCII kept as is.
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_files(catalog: dict) -> Iterator[tuple[dict, dict, str, dict]]:
    """Yield (model, release, variant_name, file) for every file entry."""
    for model in catalog["models"]:
        for release in model["releases"]:
            for vname, variant in release["variants"].items():
                for f in variant["files"]:
                    yield model, release, vname, f


def label(model: dict, release: dict, vname: str, f: dict) -> str:
    return f"{model['id']}@{release['id']}/{vname}/{f['role']}"
