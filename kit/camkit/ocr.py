"""OCR for frames: labels and values, never position.

Two engines, chosen by CAMSET_OCR or private/config.json "ocr":
- "apple" (the default on macOS): Apple Vision through kit/ocr/build/ocr. Batch several paths per
  call: each call pays ~0.3 s of start-up, each extra image ~0.1-0.2 s.
- "rapidocr" (the default on Windows and Linux): PaddleOCR's models on ONNX Runtime
  (`pip install rapidocr_onnxruntime`), ~0.2 s an image. Measured against Apple Vision on the
  a1 II's menu pages in docs/PORTING.md.
Both give lines in reading order with pixel boxes from the top left. Results are cached by file
content and engine.
"""
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import KIT, built, config

OCR_BIN = built(KIT / "ocr" / "build", "ocr")
_cache: dict[str, list] = {}
_rapid = None


def engine() -> str:
    return (os.environ.get("CAMSET_OCR") or config(required=False).get("ocr")
            or ("apple" if sys.platform == "darwin" else "rapidocr"))


def available() -> list[str]:
    """The engines usable on this machine."""
    out = ["apple"] if sys.platform == "darwin" and OCR_BIN.exists() else []
    try:
        import importlib.util
        if importlib.util.find_spec("rapidocr_onnxruntime"):
            out.append("rapidocr")
    except ImportError:
        pass
    return out


def second() -> str | None:
    """An installed engine other than the configured one: another, independent vote on labels."""
    return next((e for e in available() if e != engine()), None)


@dataclass
class Line:
    text: str
    conf: float
    x: int
    y: int
    w: int
    h: int

    def inside(self, box) -> bool:
        x0, y0, x1, y1 = box
        cx, cy = self.x + self.w / 2, self.y + self.h / 2
        return x0 <= cx <= x1 and y0 <= cy <= y1


def _key(path: Path, eng: str) -> str:
    return eng + ":" + hashlib.sha1(Path(path).read_bytes()).hexdigest()


def _rapidocr(path: Path) -> list[dict]:
    """One image through RapidOCR, in the Apple helper's shape and reading order."""
    global _rapid
    if _rapid is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid = RapidOCR()
    found, _ = _rapid(str(path))
    lines = []
    for box, text, score in found or []:
        xs, ys = [int(round(p[0])) for p in box], [int(round(p[1])) for p in box]
        lines.append({"text": text.strip(), "conf": float(score), "x": min(xs), "y": min(ys),
                      "w": max(xs) - min(xs), "h": max(ys) - min(ys)})
    rows: list[list[dict]] = []            # the helper's order: lines within 8 px of each other share a row
    for ln in sorted(lines, key=lambda ln: ln["y"]):
        if rows and abs(rows[-1][0]["y"] - ln["y"]) <= 8:
            rows[-1].append(ln)
        else:
            rows.append([ln])
    return [ln for row in rows for ln in sorted(row, key=lambda ln: ln["x"])]


def read(paths, eng: str | None = None) -> dict[Path, list[Line]]:
    paths = [Path(p) for p in paths]
    eng = eng or engine()
    keys = {p: _key(p, eng) for p in paths}
    todo = [p for p in paths if keys[p] not in _cache]
    if todo and eng == "rapidocr":
        for p in todo:
            _cache[keys[p]] = _rapidocr(p)
    elif todo:
        out = subprocess.run([str(OCR_BIN), *map(str, todo)], capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
        found, failed = _apple_lines(out, todo)
        for p, lines in found.items():
            _cache[keys[p]] = lines
        if failed:
            raise RuntimeError(failed)
    return {p: [Line(**ln) for ln in _cache[keys[p]]] for p in paths}


def _apple_lines(out: str, todo: list) -> tuple:
    """({path: its lines}, why the others have none, or "") from the Apple helper's output, one JSON line per image
    naming its "file": matched by that name, so a line the helper or a library prints in between, or an image it
    skips, never puts one frame's text on another. A line carrying "error" (an image the helper could not read, or
    Vision failed on) is a failed reading, never a frame without text, as is an image the output names nowhere; the
    helper's own words say why, also from an error line that names no file."""
    by_file, errors, unnamed = {}, {}, []
    for line in out.splitlines():
        try:
            got = json.loads(line)
        except ValueError:
            continue
        if not isinstance(got, dict):
            continue
        name = str(got["file"]) if "file" in got else None
        if got.get("error"):
            if name is None:
                unnamed.append(str(got["error"]))
            else:
                errors.setdefault(name, str(got["error"]))
        elif name is not None and isinstance(got.get("lines"), list):
            by_file.setdefault(name, got["lines"])
    found = {p: by_file[str(p)] for p in todo if str(p) in by_file}
    failed = [p for p in todo if str(p) not in by_file]
    if not failed:
        return found, ""
    each = [f"{p} ({errors.get(str(p), 'no reading')})" for p in failed[:3]]
    said = f"; the helper said: {'; '.join(dict.fromkeys(unnamed))}" if unnamed else ""
    return found, (f"the OCR helper could not read {', '.join(each)}{' ...' if len(failed) > 3 else ''}{said}")


def text_in(lines: list[Line], box) -> str:
    """Text whose centre lies in box (x0, y0, x1, y1), reading order, joined by spaces."""
    return " ".join(ln.text for ln in lines if ln.inside(box)).strip()
