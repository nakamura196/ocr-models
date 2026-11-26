# ocr-models — notes for Claude Code

Public repository. Write everything here in English (README, code, comments, commits, notes).

## Invariants

- No model binaries in git (`*.onnx`, `*.gguf` are ignored). Weights live on Hugging Face.
- Every `url` and `source` is pinned to a 40-hex commit. `validate.py` enforces it.
- Do not hand-edit `sha256` or `input_shapes`; run `scripts/sync_upstream.py`.
  Hand-edited `catalog.json` must stay in `json.dumps(indent=2)` form (a test checks).
- Never delete or rewrite an existing Hugging Face commit or repo that an app may pin
  (`nakamura196/ndlocr-lite-web-onnx` @ 6b27f9f and `ndlkotenocr-lite-web-onnx` @ ac0d8e0
  are still used by the public IIIF Kasane). Freeze them; point their README at the new repos.
- `HF_TOKEN` comes from 1Password via `op run`. Never write it to disk or print it.
- `publish_hf.py --apply` writes to public Hugging Face repos. Ask the user before running it.

## Adding a model or release

1. Add the release to `catalog.json` with `source` (upstream, pinned), `bytes`, and `sha256: null`.
2. `uv run python scripts/sync_upstream.py` to fill hashes, shapes, charsets, classes.
3. `uv run python scripts/validate.py && uv run pytest -q`.
4. If it must be mirrored, add the model to `HF_REPOS` in `publish_hf.py`, dry-run, then ask.

## Consumers (as of 2026-11-25)

- Local OCR desktop: `~/git/toyo/local-ocr` (`core/ndl_assets.py`, `engines/ppocr.py`, `core/yigdzin_assets.py`)
- Local OCR iOS: `~/git/hi/miyako/local-ocr-ios` (`LocalOCR/Download/ModelCatalog.swift`), being merged into
  `~/git/hi/miyako/koten-ocr-ios.worktrees/monorepo` (`Packages/OCRKit/`)
- KotenOCR iOS: `~/git/hi/miyako/koten-ocr-ios` (`setup.sh`)
- KotenOCR Android: `~/git/hi/miyako/koten-ocr-android`
- IIIF Kasane: `~/git/iiif/iiif-kasane/packages/iiif-viewer/src/react/inference/models/`

Lab notebook: `docs/notes/registry-design.md`.
