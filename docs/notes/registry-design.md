# Model registry: design and findings

## 2026-11-25 — Repository set up (Phase 1)

### Decisions

- Location `~/git/ocr/ocr-models`, public as `nakamura196/ocr-models`. A new cross-cutting group,
  because the consumers sit in three groups (toyo, hi, iiif).
- Hugging Face: new repos `nakamura196/ndlocr-lite-onnx` and `nakamura196/ndlkotenocr-lite-onnx`, holding
  both native and web files. The existing `*-web-onnx` repos stay frozen (IIIF Kasane pins them).
  Rejected: adding v2 commits to `ndlocr-lite-web-onnx` (the name would no longer describe the content);
  creating a new repo only for NDLOCR-Lite (inconsistent names for no real saving).
- Phase 1 scope: NDLOCR-Lite, NDL Kotenseki OCR-Lite, PP-OCRv6, Yigdzin-1. Kasane-only vision models
  (SAM2, Florence-2, KaoKore) later.
- Apps do not read the catalog at run time (offline use, store review, old apps vs new input shapes).

### Correction to the hand-off premise

The hand-off said NDLOCR-Lite 2.0.0 no longer ships ONNX in its GitHub repository. Not so:
`src/model/*.onnx` is present at tag `2.0.0` (`1f3adc7`) and on `master`. Only the PyPI package
leaves the files out and downloads them from `lab.ndl.go.jp`. The tag is `2.0.0`, not `v2.0.0`.

Measured with `curl -sI -H "Origin: https://kasane.ldas.jp"`:
`raw.githubusercontent.com/<commit>/…` returns `access-control-allow-origin: *` (and `cache-control: max-age=300`);
`lab.ndl.go.jp/dataset/ndlocr-lite/onnx/v2/…` returns no CORS header.

So browsers *could* read the upstream GitHub files directly. We still mirror to Hugging Face, because
GitHub raw is not meant as a CDN (5-minute cache, possible rate limits) and a mirror survives upstream changes.
The upstream GitHub commit is recorded as `source` (provenance).

The hand-off's SHA-256 for `parseq-ndl-24x384-50-tiny-278epoch-261124.onnx` had a typo
(`…0bf07cfbfbe1d9…`); upstream `model_download.py` and the downloaded bytes give `…0bf07cfbefe1d9…`.

### Findings (from `sync_upstream.py`; all bytes and known hashes verified, 0 errors)

- File names do not give detector input size. `deim-s-1024x1024*.onnx` (all three NDLOCR-Lite releases)
  has input `[N, 3, 800, 800]`. `rtmdet-s-1280x1280.onnx` has `[1, 3, 1024, 1024]` at 22be4cc and ede4283,
  and `[1, 3, 1280, 1280]` only at 95692df (2024-11). Apps must take sizes from the graph or the catalog.
- NDLOCR-Lite recognizer heights: 24 px at d25e0d4 and 2.0.0, 16 px at 109e627. Kasane's web files equal the
  109e627 recognizers byte for byte (same SHA-256).
- 2.0.0's `parseq-ndl-24x768-100-tiny-153epoch-261124.onnx` has the same git blob (`f2813e71`) as
  2026-04's `…-tegaki3-r8data-202604.onnx`: renamed, not retrained.
- 2.0.0's `ndl.yaml` keeps the 17 class names and adds a `markdown` mapping. The detector itself changed.
- NDL Kotenseki OCR-Lite model blobs are identical from tag 1.4.3 (008c098) to 39e076f (2026-11-04),
  so ede4283 (used by Local OCR desktop) is current.
- KotenOCR iOS `setup.sh` pins 95692df but expects the detector size 40,188,733, which is the
  22be4cc-and-later file. At 95692df the detector is 40,189,181 bytes and has a different input size (1280).
- The two NDLmoji character lists (blobs 3bb041a1 and 9cc3e3f1) both have 7,141 entries and differ at
  indexes 7081, 7111, 7116, 7127: the Kotenseki list has 〓 where the other has 𢌞, 𤍽, 𦾔, 𠮷.
  Local OCR desktop and Kasane both match the registry exactly.
- Local OCR desktop fetches Yigdzin-1 from `/resolve/main/`, not a commit. Catalog pins fdf4bd1.

### Not yet verified

- Pre-processing entries in `inference` are read from upstream code (`deim.py`, `parseq.py`, `rtmdet.py`),
  not tested against outputs. `verify.py` (compare with upstream on sample images) is still to write.
- The web conversion scripts (DEIM → `deim-s-layers`, RTMDet cut before NMS) are not in the repository yet.
