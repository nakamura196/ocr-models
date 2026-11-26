"""Check catalog.json against the schema and the rules the schema cannot express.

Usage: uv run python scripts/validate.py   (exit code 1 on any problem)

Rules beyond the schema:
- Every delivery URL (`url`) and provenance URL (`source`) is pinned to a 40-hex commit.
- A `current` or `legacy` release has a SHA-256 for every file.
- A file with no delivery `url` yet is reported as a to-do (not an error):
  it still has to be mirrored to Hugging Face by publish_hf.py.
- `charset` and `classes` refer to files that exist under charsets/ and classes/.
- (model id, release id) pairs are unique.
"""

from __future__ import annotations

import json
import sys

from jsonschema import Draft202012Validator

from catalog import PINNED_URL, ROOT, SCHEMA, iter_files, label, load


def problems(catalog: dict, todos: list[str] | None = None) -> list[str]:
    out: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for err in Draft202012Validator(schema).iter_errors(catalog):
        out.append(f"schema: {'/'.join(map(str, err.absolute_path))}: {err.message}")
    if out:
        return out

    seen: set[tuple[str, str]] = set()
    for model in catalog["models"]:
        for release in model["releases"]:
            key = (model["id"], release["id"])
            if key in seen:
                out.append(f"duplicate release {key}")
            seen.add(key)
            for field, folder in (("charset", "charsets"), ("classes", "classes")):
                stem = release.get(field)
                if stem and not any((ROOT / folder).glob(f"{stem}.*")):
                    out.append(f"{model['id']}@{release['id']}: {folder}/{stem}.* not found (run sync_upstream.py)")

    for model, release, vname, f in iter_files(catalog):
        where = label(model, release, vname, f)
        for field in ("url", "source"):
            if f[field] and not PINNED_URL.match(f[field]):
                out.append(f"{where}: {field} is not pinned to a commit: {f[field]}")
        if release["status"] != "pending":
            if not f["sha256"]:
                out.append(f"{where}: missing sha256 (run sync_upstream.py)")
        if not f["url"] and todos is not None:
            todos.append(f"{where}: not yet mirrored (no delivery url)")
    return out


def main() -> int:
    todos: list[str] = []
    found = problems(load(), todos)
    for t in todos:
        print(f"todo: {t}")
    for p in found:
        print(f"error: {p}", file=sys.stderr)
    print(f"{len(found)} error(s), {len(todos)} todo(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
