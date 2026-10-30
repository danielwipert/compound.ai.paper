"""Smoke test: the repo layout from TS-11.1 exists and the src package imports."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXPECTED_DIRS = [
    "config",
    "docs",
    "data/raw",
    "data/golden",
    "data/noised",
    "data/fewshot",
    "src/noise",
    "src/gateway/adapters",
    "src/arms/a_naive",
    "src/arms/b_tooled",
    "src/arms/c_compound/nodes",
    "src/metrics",
    "src/analysis",
    "results",
    "paper/figures",
]


def test_layout_exists():
    missing = [d for d in EXPECTED_DIRS if not (ROOT / d).is_dir()]
    assert missing == []


def test_specs_present():
    for name in ["product-spec.md", "tech-spec.md", "decisions.md"]:
        assert (ROOT / "docs" / name).is_file()


def test_src_imports():
    import src.arms.c_compound.nodes  # noqa: F401
    import src.metrics  # noqa: F401
