"""Catalog invariants. Runs offline (no downloads)."""

import json

from catalog import ROOT, iter_files, load
from validate import problems


def test_catalog_is_valid():
    assert problems(load()) == []


def test_catalog_is_saved_in_canonical_form():
    # scripts rewrite catalog.json with json.dumps(indent=2); hand edits must match.
    text = (ROOT / "catalog.json").read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), ensure_ascii=False, indent=2) + "\n"


def test_roles_are_unique_per_variant():
    # Guard against copying a URL from one release into another: within one
    # (model, release), a role appears once per variant.
    for model in load()["models"]:
        for release in model["releases"]:
            for variant in release["variants"].values():
                roles = [f["role"] for f in variant["files"]]
                assert len(roles) == len(set(roles)), (model["id"], release["id"])


def test_recognizer_height_matches_release():
    # The 16px vs 24px mix-up between apps is the reason this repository exists.
    expected = {("ndlocr-lite", "2.0.0"): 24, ("ndlocr-lite", "2026-04"): 24, ("ndlocr-lite", "2026-02"): 16}
    for model, release, _v, f in iter_files(load()):
        key = (model["id"], release["id"])
        if key in expected and f["role"].startswith("recognizer"):
            (shape,) = f["input_shapes"].values()
            assert shape[2] == expected[key], (key, f["name"], shape)


def test_charsets_are_lists_of_single_characters():
    for path in (ROOT / "charsets").glob("*.json"):
        chars = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(chars, list) and chars, path
        if path.stem.startswith("ndlmoji-"):
            assert all(len(c) == 1 for c in chars), path
