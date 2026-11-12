"""Before anything else: which camera, how it connects, how the kit will see its screen, and what that allows.

    .venv/bin/python kit/tools/body_check.py --model "a7 IV" --link usb --eyes hdmi
    .venv/bin/python kit/tools/body_check.py --list                 # the names it knows

Ask the owner three things first, then run this with the answers:
1. **Which camera?** The model name on the body ("a7 IV") or its model number ("ILCE-7M4").
2. **How will it connect?** `usb` (a USB-C data cable), `lan` (Ethernet with access authentication)
   or `wifi`.
3. **How will the kit see the screen?** `hdmi` (a capture dongle; micro-HDMI bodies need a
   micro-to-full cable) or `osd` (the camera sends its own screen through the SDK; no dongle).

It checks the answers against Sony's SDK support table (private/data/sdk_support.json, written by
kit/tools/sdk_support.py --json from your copy of the SDK reference; kept private, since nothing taken from Sony's
documents is published: docs/RELEASING.md). It says what the kit can do with this body: everything,
settings files only, or nothing. It names what is missing, and prints the settings to put in
private/config.json and the environment. It needs no camera.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# names people use -> the model numbers in the SDK's tables
ALIASES = {
    "a1 ii": "ILCE-1M2", "a1": "ILCE-1", "a9 iii": "ILCE-9M3", "a9 ii": "ILCE-9M2",
    "a7r vi": "ILCE-7RM6", "a7r v": "ILCE-7RM5", "a7r iva": "ILCE-7RM4A", "a7r iv": "ILCE-7RM4",
    "a7cr": "ILCE-7CR", "a7s iii": "ILCE-7SM3", "a7 v": "ILCE-7M5", "a7 iv": "ILCE-7M4",
    "a7c ii": "ILCE-7CM2", "a7c": "ILCE-7C", "a6700": "ILCE-6700",
    "fx2": "ILME-FX2", "fx3a": "ILME-FX3A", "fx3": "ILME-FX3", "fx30": "ILME-FX30", "fx6": "ILME-FX6",
    "zv-e1": "ZV-E1", "zv-e10 ii": "ZV-E10M2", "rx1r iii": "DSC-RX1RM3", "rx0 ii": "DSC-RX0M2",
}


def resolve(name: str, models: dict) -> str | None:
    key = " ".join(name.lower().replace("α", "a").split())
    if name.upper() in models:
        return name.upper()
    if key in ALIASES:
        return ALIASES[key]
    squeezed = key.replace(" ", "")
    return next((m for k, m in ALIASES.items() if k.replace(" ", "") == squeezed), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--link", choices=["usb", "lan", "wifi"])
    ap.add_argument("--eyes", choices=["hdmi", "osd"])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, m in sorted(ALIASES.items(), key=lambda x: x[1]):
            print(f"{m:12s} {k}")
        return
    table = ROOT / "private" / "data" / "sdk_support.json"
    if not table.exists():
        table = ROOT / ".cache" / "sdk_support.json"
    if not table.exists():
        sys.exit("No SDK support table yet: put Sony's Camera Remote SDK zip into kit/sdk/, run python3 kit/setup.py, then\n"
                 "  python3 kit/tools/sdk_support.py --json\nWhat its answers mean: docs/CAMERA_SUPPORT.md, \"The short answers\".")
    data = json.loads(table.read_text(encoding="utf-8"))
    models = data["models"]
    if not (a.model and a.link and a.eyes):
        ap.error("give --model, --link and --eyes (ask the owner first), or --list")
    model = resolve(a.model, models)
    if model is None or model not in models:
        sys.exit(f"{a.model!r} is not in the SDK's support table ({data['sdk']}): the kit cannot drive it")
    r = models[model]
    problems, notes = [], []
    link_ok = {"usb": r["usb"], "lan": r["ethernet"], "wifi": r["wireless"]}[a.link]
    if not link_ok:
        problems.append(f"the SDK does not remote-control the {model} over {a.link}; "
                        f"it does over: {', '.join(k for k, v in (('usb', r['usb']), ('lan', r['ethernet']), ('wifi', r['wireless'])) if v) or 'nothing'}")
    if a.link == "lan" and r["ethernet_adapter"]:
        notes.append("Ethernet goes through a USB-C wired LAN adapter (gigabit recommended)")
    if a.eyes == "osd" and not r["osd"]:
        problems.append(f"the {model} has no OSD image in the SDK: the kit needs an HDMI capture dongle to see the screen")
    if r["settings_file"] and r["buttons"]:
        verdict = "EVERYTHING: walk the menus, prove every setting, restore files"
    elif r["settings_file"]:
        verdict = ("SETTINGS FILES ONLY: the editor works (download, edit, upload); the kit cannot press buttons, "
                   "so mapping needs a person pressing while the kit watches and downloads after each step")
    else:
        verdict = "NOTHING: no settings-file transfer and no button presses in the SDK"
    if not r["dials"] and r["buttons"]:
        notes.append("no remote dial turns: rows driven by a dial (Var. Shutter speed and the like) stay by hand")
    print(f"{a.model} = {model} (SDK {data['sdk']})")
    print(f"  the kit can do: {verdict}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    for n in notes:
        print(f"  note: {n}")
    if problems or not r["settings_file"]:
        return
    print("  settings:")
    if a.link == "usb":
        print("    environment: CAMSET_USB=1 (USB-C data cable; Remote Shooting on; unplug other links)")
    elif a.link == "lan":
        print('    private/config.json: "camera_ip": "<the camera\'s address>"; the owner fills ~/.config/camset/network.json')
    else:
        print("    wifi: the link has no Wi-Fi mode yet (USB or LAN for now)")
    if a.eyes == "hdmi":
        print('    private/config.json: "eyes": "hdmi", and "hdmi": {"device", "size", "fps", "crop"} for the dongle '
              "(camera HDMI at 1080p; micro-HDMI bodies need a micro-to-full cable)")
    else:
        print('    private/config.json: "eyes": "osd" (every scan, crawl and proof watches the SDK\'s OSD image; '
              "scan the menu in this mode too)")
    print("  next: docs/QUICKSTART.md, step 2 (the body check ends step 1)")


if __name__ == "__main__":
    main()
