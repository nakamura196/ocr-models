"""Fetch every catalogued file, check it, and fill in what the catalog lacks.

Usage:
  uv run python scripts/sync_upstream.py            # fill missing sha256 / input_shapes, write charsets/ and classes/
  uv run python scripts/sync_upstream.py --verify   # also re-check files whose sha256 is already known
  uv run python scripts/sync_upstream.py --verify --max-mb 2000   # include the large GGUF files

What it does, per file:
- Downloads from `source` (upstream, pinned) if set, otherwise from `url`.
  Files are cached under $OCR_MODELS_CACHE (default ~/.cache/ocr-models), keyed by SHA-256 of the URL.
- Fails if the byte count differs from `bytes`, or if a known `sha256` differs.
- Fills `sha256` when null, and `input_shapes` for .onnx files (read from the graph).

Charsets and class lists:
- `ndlmoji-<blob8>`: model.charset_train in src/config/NDLmoji.yaml at the release's upstream commit.
  <blob8> is the first 8 hex digits of the file's git blob id, so the name changes when upstream edits it.
- `ndl-layout-<blob8>`: names (and markdown, if present) in src/config/ndl.yaml.
- `ppocrv6`: PostProcess.character_dict in the recognizer's inference.yml.
All are written as JSON (arrays/objects of strings). App-specific formats are generated from these.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

from catalog import ROOT, iter_files, label, load, save

CACHE = Path(os.environ.get("OCR_MODELS_CACHE", Path.home() / ".cache" / "ocr-models"))
RAW = "https://raw.githubusercontent.com"


def fetch(url: str) -> Path:
    """Download once into the cache and return the local path."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if dest.is_file():
        return dest
    part = dest.with_suffix(".part")
    print(f"  downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as resp, part.open("wb") as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
    part.replace(dest)
    return dest


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def onnx_input_shapes(path: Path) -> dict[str, list[int | str]]:
    import onnx

    model = onnx.load(str(path), load_external_data=False)
    initializers = {i.name for i in model.graph.initializer}
    shapes: dict[str, list[int | str]] = {}
    for inp in model.graph.input:
        if inp.name in initializers:
            continue
        dims = inp.type.tensor_type.shape.dim
        shapes[inp.name] = [d.dim_value if d.HasField("dim_value") else (d.dim_param or "?") for d in dims]
    return shapes


def sync_files(catalog: dict, verify: bool, max_bytes: int) -> list[str]:
    errors: list[str] = []
    for model, release, vname, f in iter_files(catalog):
        where = label(model, release, vname, f)
        is_onnx = f["name"].endswith(".onnx")
        needed = f["sha256"] is None or (is_onnx and "input_shapes" not in f)
        if not needed and not verify:
            continue
        if f["bytes"] > max_bytes:
            print(f"skip {where}: {f['bytes']:,} bytes is over --max-mb", file=sys.stderr)
            continue
        url = f["source"] or f["url"]
        if not url:
            errors.append(f"{where}: neither source nor url")
            continue
        path = fetch(url)
        size = path.stat().st_size
        if size != f["bytes"]:
            errors.append(f"{where}: {size:,} bytes, catalog says {f['bytes']:,}")
            continue
        digest = sha256_of(path)
        if f["sha256"] is None:
            f["sha256"] = digest
            print(f"filled {where}: sha256 {digest[:12]}…")
        elif f["sha256"] != digest:
            errors.append(f"{where}: sha256 {digest} != catalog {f['sha256']}")
            continue
        if is_onnx:
            f["input_shapes"] = onnx_input_shapes(path)
    return errors


def upstream_config(model: dict, release: dict, relpath: str) -> bytes:
    repo = model["upstream"]["repo"].removeprefix("https://github.com/")
    url = f"{RAW}/{repo}/{release['upstream_ref']['commit']}/{relpath}"
    return fetch(url).read_bytes()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sync_tables(catalog: dict) -> list[str]:
    errors: list[str] = []
    written: dict[Path, str] = {}

    def emit(path: Path, obj, where: str) -> None:
        text = json.dumps(obj, ensure_ascii=False, sort_keys=True)
        if path in written and written[path] != text:
            errors.append(f"{where}: {path.name} differs from another release that uses the same id")
            return
        written[path] = text
        write_json(path, obj)

    for model in catalog["models"]:
        for release in model["releases"]:
            where = f"{model['id']}@{release['id']}"
            cs = release.get("charset")
            if cs and cs.startswith("ndlmoji-"):
                data = upstream_config(model, release, "src/config/NDLmoji.yaml")
                if not git_blob_id(data).startswith(cs.removeprefix("ndlmoji-")):
                    errors.append(f"{where}: NDLmoji.yaml blob is {git_blob_id(data)[:8]}, not {cs}")
                else:
                    emit(ROOT / "charsets" / f"{cs}.json", list(yaml.safe_load(data)["model"]["charset_train"]), where)
            elif cs == "ppocrv6":
                cfg = next(f for f in release["variants"]["native"]["files"] if f["role"] == "recognizer-config")
                data = yaml.safe_load(fetch(cfg["url"]).read_bytes())
                emit(ROOT / "charsets" / "ppocrv6.json", [str(c) for c in data["PostProcess"]["character_dict"]], where)
            cl = release.get("classes")
            if cl and cl.startswith("ndl-layout-"):
                data = upstream_config(model, release, "src/config/ndl.yaml")
                if not git_blob_id(data).startswith(cl.removeprefix("ndl-layout-")):
                    errors.append(f"{where}: ndl.yaml blob is {git_blob_id(data)[:8]}, not {cl}")
                else:
                    doc = yaml.safe_load(data)
                    obj = {"names": {str(k): v for k, v in doc["names"].items()}}
                    if "markdown" in doc:
                        obj["markdown"] = {str(k): v for k, v in doc["markdown"].items()}
                    emit(ROOT / "classes" / f"{cl}.json", obj, where)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="re-check files whose sha256 is already known")
    ap.add_argument("--max-mb", type=int, default=500, help="skip files larger than this (default 500)")
    args = ap.parse_args()

    catalog = load()
    errors = sync_files(catalog, args.verify, args.max_mb * 1_000_000)
    errors += sync_tables(catalog)
    save(catalog)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
