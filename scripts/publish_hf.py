"""Mirror catalogued files that have no delivery URL yet to Hugging Face, then pin them.

Usage:
  uv run python scripts/publish_hf.py                  # show the plan only (no network writes)
  op run --env-file=.env.local -- uv run python scripts/publish_hf.py --apply

The token comes from $HF_TOKEN (resolved by `op run` from 1Password; see .env.example).
Never write it to a file.

Layout on Hugging Face (one repo per model family = one license per repo):
  <hf-repo>/<release-id>/<file name>        native variant
  <hf-repo>/<release-id>/web/<file name>    web variant
Files are uploaded in a single commit per repo. Each `url` is then set to
https://huggingface.co/<hf-repo>/resolve/<commit sha>/<path>, so it never changes.

Only files whose bytes were already checked by sync_upstream.py (cached, sha256 known)
are uploaded; each is re-hashed before upload.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from catalog import iter_files, label, load, save
from sync_upstream import fetch, sha256_of

# Model id -> Hugging Face repo. Models not listed here are never mirrored
# (e.g. PP-OCRv6 is referenced on PaddlePaddle's own repos).
HF_REPOS = {
    "ndlocr-lite": "nakamura196/ndlocr-lite-onnx",
    "ndlkotenocr-lite": "nakamura196/ndlkotenocr-lite-onnx",
}


def model_card(model: dict, repo: str, files: list[tuple[dict, str, dict, str]]) -> str:
    lines = [
        "---",
        f"license: {model['license'].lower()}",
        "tags: [ocr, onnx]",
        "---",
        "",
        f"# {model['name']['en']} — ONNX mirror",
        "",
        f"Unmodified copies of the ONNX files published by {model['upstream']['repo']},",
        "plus graphs converted for onnxruntime-web where noted. Mirrored so that browser",
        "apps can fetch them with CORS and every app can pin the same immutable URL.",
        "",
        f"Credit: {model['credit']}",
        "",
        "The catalog, checksums, input shapes, and conversion scripts live in",
        "https://github.com/nakamura196/ocr-models. Always fetch by commit, not by branch.",
        "",
        "| Path | Bytes | SHA-256 | Source |",
        "|---|---:|---|---|",
    ]
    for _release, _vname, f, path in files:
        lines.append(f"| `{path}` | {f['bytes']:,} | `{f['sha256']}` | {f['source'] or 'converted'} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually create repos and upload")
    args = ap.parse_args()

    catalog = load()
    plan: dict[str, list[tuple[dict, str, dict, str]]] = defaultdict(list)
    models = {}
    for model, release, vname, f in iter_files(catalog):
        repo = HF_REPOS.get(model["id"])
        if not repo or f["url"]:
            continue
        if not f["sha256"] or not f["source"]:
            print(f"skip {label(model, release, vname, f)}: run sync_upstream.py first", file=sys.stderr)
            continue
        path = f"{release['id']}/{f['name']}" if vname == "native" else f"{release['id']}/{vname}/{f['name']}"
        plan[repo].append((release, vname, f, path))
        models[repo] = model

    for repo, files in plan.items():
        print(f"{repo}: {len(files)} file(s)")
        for _r, _v, f, path in files:
            print(f"  {path}  {f['bytes']:,} B")
    if not plan:
        print("nothing to publish")
        return 0
    if not args.apply:
        print("dry run; pass --apply to upload")
        return 0

    from huggingface_hub import CommitOperationAdd, HfApi

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("error: HF_TOKEN is not set (run through `op run`)", file=sys.stderr)
        return 1
    api = HfApi(token=token)
    for repo, files in plan.items():
        ops = []
        for _r, _v, f, path in files:
            local = fetch(f["source"])
            if sha256_of(local) != f["sha256"]:
                print(f"error: {path}: cached file does not match sha256", file=sys.stderr)
                return 1
            ops.append(CommitOperationAdd(path_in_repo=path, path_or_fileobj=str(local)))
        ops.append(CommitOperationAdd(path_in_repo="README.md",
                                      path_or_fileobj=model_card(models[repo], repo, files).encode()))
        api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
        info = api.create_commit(repo, operations=ops, commit_message="Mirror from upstream (ocr-models)")
        commit = info.oid
        for _r, _v, f, path in files:
            f["url"] = f"https://huggingface.co/{repo}/resolve/{commit}/{path}"
        print(f"{repo}: committed {commit}")
        save(catalog)  # save after each repo so a later failure does not lose pinned URLs
    return 0


if __name__ == "__main__":
    sys.exit(main())
