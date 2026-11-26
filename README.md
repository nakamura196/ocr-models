# ocr-models

One catalog for the OCR models shared by several apps:
[Local OCR](https://github.com/nakamura196/local-ocr) (desktop and iOS),
KotenOCR (iOS and Android), and [IIIF Kasane](https://kasane.ldas.jp) (web).

Before this repository, each app hand-kept its own model URLs, sizes, character lists,
and input sizes. They drifted. For example, the desktop app used 24-pixel-high NDLOCR-Lite
recognizers while the iOS apps and the web viewer still used 16-pixel ones.

## What lives where

| | Where | Why |
|---|---|---|
| Model weights (`.onnx`, `.gguf`) | Hugging Face Hub | Free for public models, serves CORS, and gives immutable URLs (`/resolve/<commit>/…`) |
| Catalog, charsets, class lists, scripts | This repository | Small, reviewable, testable |

Rules:

- **Official ONNX already on Hugging Face is referenced, not copied** (PP-OCRv6 → `PaddlePaddle/*`).
- **Everything else is mirrored** to `nakamura196/*` on Hugging Face, one repo per model family
  (one license per repo): `ndlocr-lite-onnx`, `ndlkotenocr-lite-onnx`, `yigdzin1-gguf`.
- **Every URL is pinned to a 40-hex commit.** Branch URLs (`/resolve/main/`) are rejected by `validate.py`.
- **Apps do not fetch `catalog.json` at run time.** Apps must work offline, store review must see
  fixed behaviour, and an old app must never receive a model with a new input shape. Instead, each
  app's update step generates constants from this catalog and goes through that app's own tests and PR.

## Files

- `catalog.json` — the catalog. Schema: `schema/catalog.schema.json`.
  Each model has releases. Each release has `native` and optionally `web` variants.
  Each file has `bytes`, `sha256`, `source` (provenance, pinned upstream), `url` (where apps fetch it),
  and `input_shapes` (read from the ONNX graph, not from the file name; file names lie, see below).
- `charsets/*.json` — character lists, as JSON arrays. NDL lists are named `ndlmoji-<blob8>`
  after the git blob of the upstream `NDLmoji.yaml`, so a silent upstream edit gets a new name.
- `classes/*.json` — layout class lists (`ndl-layout-<blob8>`, from upstream `ndl.yaml`).
- `scripts/sync_upstream.py` — downloads every file, checks bytes and SHA-256, fills missing values,
  reads ONNX input shapes, and writes `charsets/` and `classes/`.
- `scripts/validate.py` — schema check plus rules the schema cannot express. Run in CI.
- `scripts/publish_hf.py` — mirrors files that have no `url` yet to Hugging Face in one commit per repo,
  then writes the pinned URLs back. Dry run unless `--apply`.

## Use

```sh
uv sync --extra sync
uv run python scripts/sync_upstream.py
uv run python scripts/validate.py
uv run pytest -q
```

Publishing needs a Hugging Face token. It is read from 1Password at run time and never stored on disk:

```sh
cp .env.example .env.local   # holds only an op:// reference
op run --env-file=.env.local -- uv run python scripts/publish_hf.py --apply
```

## Things the catalog caught

- Detector file names do not give the input size. `deim-s-1024x1024*.onnx` takes 800×800.
  `rtmdet-s-1280x1280.onnx` takes 1024×1024 from 2024-12 on (1280×1280 only in 2024-11).
- NDLOCR-Lite 2.0.0's long-line recognizer is byte-identical to the 2026-04 one under a new name.
- KotenOCR iOS `setup.sh` fetches 2024-11 files but expects the detector size of 2024-12 and later.
- The two NDL character lists differ in four places: NDL Kotenseki OCR-Lite replaces four
  non-BMP characters with 〓.

## Licence

Code and catalog: MIT. Each model keeps its own licence, recorded in `catalog.json` and on its
Hugging Face model card (NDL models: CC BY 4.0; PP-OCRv6 and Yigdzin-1: Apache-2.0).
