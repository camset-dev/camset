"""Which bodies the Sony Camera Remote SDK lets this kit work with, read from the SDK's own reference.

    .venv/bin/python kit/tools/sdk_support.py [kit/sdk/CrSDK_API_Reference_vX.YY.ZZ] [--json] > table.md

Prints a Markdown table, one row per model in the SDK's compatibility list:
- **links:** remote control over USB, wired Ethernet or wireless, from "Supporting physical layer";
- **what the kit needs:**
  - **settings file** (DownloadSettingFile / UploadSettingFile): download and upload, which every
    proof and every restore uses;
  - **buttons** (CameraButtonFunction): the menu presses that drive every walk and proof;
  - **dials** (CameraDialFunction);
  - **OSD** (GetOSDImage): the second pair of eyes.

Rerun it when a new SDK version arrives; docs/CAMERA_SUPPORT.md says what the kit needs and how to read kit/tools/body_check.py's answers.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cells(row: str) -> list[str]:
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).strip().lstrip("﻿")
            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]


def table(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    rows = [cells(r) for r in re.findall(r"<tr.*?</tr>", path.read_text(encoding="utf-8", errors="ignore"), re.S)]
    head = next((r for r in rows if "ILCE-1M2" in r), None)          # the model columns' header row
    if head is None:
        raise SystemExit(f"{path}: no model table found (this SDK reference's layout is not the one this reads)")
    models = head[4:]
    return models, {r[1]: r[4:] for r in rows if len(r) > 4}


def physical(path: Path) -> dict[str, dict[str, bool]]:
    """Model -> {usb, ethernet, wireless}: remote control mode ("R") over each link."""
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="ignore"))))
    start = text.find("Model Name USB")              # the table itself, not the contents at the top
    seg = text[start:text.find("refers for RemoteControlMode", start)]
    out = {}
    for m in re.finditer(r"\b\d+ ([A-Z][A-Z0-9-]+)(?:\(BURANO\))?(?: \(Ver\.[\d.]+ or later\))?((?: \*\d)*)((?: [✓-]){3,9})", seg):
        marks = m.group(3).split()
        marks += ["-"] * (9 - len(marks))
        out[m.group(1)] = {"usb": marks[0] == "✓", "ethernet": marks[3] == "✓", "wireless": marks[6] == "✓",
                           "notes": m.group(2).strip()}
    return out


FEATURES = {"settings_file": ("api", "DownloadSettingFile"), "buttons": ("prop", "CrDeviceProperty_CameraButtonFunction"),
            "dials": ("prop", "CrDeviceProperty_CameraDialFunction"), "osd": ("api", "GetOSDImage")}


def support(ref: Path) -> dict:
    """{model: {usb, ethernet, ethernet_adapter, wireless, settings_file, buttons, dials, osd}} from the reference."""
    h = ref / "html" if (ref / "html").exists() else ref
    models, apis = table(h / "function_list" / "api_list.html")
    _, props = table(h / "function_list" / "device_property_list.html")
    phys = physical(h / "other" / "compatibility.html")
    out = {}
    for i, m in enumerate(models):
        p = phys.get(m, {})
        row = {"usb": bool(p.get("usb")), "ethernet": bool(p.get("ethernet")),
               "ethernet_adapter": bool(p.get("ethernet")) and "*2" in p.get("notes", ""),
               "wireless": bool(p.get("wireless"))}
        for name, (kind, key) in FEATURES.items():
            v = (apis if kind == "api" else props).get(key)
            row[name] = bool(v and i < len(v) and v[i] in ("✔", "✓"))
        out[m] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", nargs="?", help="the SDK's API reference folder (default: the newest in kit/sdk/)")
    ap.add_argument("--json", action="store_true", help="also write private/data/sdk_support.json (read by kit/tools/body_check.py)")
    a = ap.parse_args()
    ref = Path(a.ref) if a.ref else next((p for p in sorted((ROOT / "kit" / "sdk").glob("CrSDK_API_Reference_v*")) if p.is_dir()), None)
    if ref is None:
        sys.exit("No CrSDK_API_Reference_v<version>/ in kit/sdk/: put Sony's Camera Remote SDK zip there and run python3 kit/setup.py")
    rows = support(ref)
    yes = lambda b: "yes" if b else "-"   # noqa: E731
    print(f"From {ref.name}.\n")
    print("| Model | USB | Ethernet | Wireless | Settings file | Buttons | Dials | OSD |")
    print("|---|---|---|---|---|---|---|---|")
    for m, r in rows.items():
        print(f"| {m} | {yes(r['usb'])} | {yes(r['ethernet'])}{' (USB-C adapter)' if r['ethernet_adapter'] else ''} "
              f"| {yes(r['wireless'])} | {yes(r['settings_file'])} | {yes(r['buttons'])} | {yes(r['dials'])} | {yes(r['osd'])} |")
    if a.json:
        if (ROOT / "private" / "data").exists():  # noqa: SIM108 (two long arms read apart)
            out = ROOT / "private" / "data" / "sdk_support.json"
        else:
            out = ROOT / ".cache" / "sdk_support.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"sdk": ref.name, "models": rows}, f, indent=1)
        print(f"\nwrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
