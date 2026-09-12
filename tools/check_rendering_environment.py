#!/usr/bin/env python3
"""Check the recorded rendering dependencies and font bytes before rebuilding."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import subprocess

from matplotlib import font_manager, ft2font

ROOT = Path(__file__).resolve().parents[1]


def main():
    expected = json.loads((ROOT / "release/rendering-environment.json").read_text())
    actual = {"python": platform.python_version(), "freetype": ft2font.__freetype_version__,
              "packages": {name: metadata.version(name) for name in expected["packages"]},
              "plot_fonts_sha256": {}}
    for weight in ("normal", "bold"):
        path = Path(font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight=weight)))
        actual["plot_fonts_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = Path(subprocess.check_output(["fc-match", "-f", "%{file}", "DejaVu Sans"], text=True))
    actual["typst_font_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    mismatches = [key for key in actual if actual[key] != expected[key]]
    if mismatches:
        raise SystemExit("Rendering environment differs from release: " + ", ".join(mismatches))
    print(json.dumps(actual, indent=2))


if __name__ == "__main__":
    main()
