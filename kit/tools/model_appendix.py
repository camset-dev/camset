"""The measured block of a model's page (docs/models/<MODEL>_fw<FW>.md), from its definition.

The docs site renders it where the page calls `{{ appendix_measured() }}` (kit/tools/docs_macros.py), so nothing is
written into the page. The block holds identity (model, firmware, fingerprint, record counts), the definition's size,
the records the kit ignores as volatile, and what Camera Settings Reset and Initialize did
(data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json, when there is one for this layout: the public file alone, which lists
only the settings a test could tell, camkit.datafiles). Values from anyone's camera never appear: only counts, names and
record ids.
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset  # noqa: E402

START, END = "<!-- measured:start -->", "<!-- measured:end -->"


def measured(schema: dict, layout: dict) -> str:
    settings = schema["settings"]
    proved = [s for s in settings if s.get("proved")]
    counts = (schema.get("camera") or {}).get("section_counts") or []
    names = {s["key"]: s["name"] for s in settings}
    lines = [START, "", "*Rendered from the definition when the docs are built (`kit/tools/model_appendix.py`); nothing to edit here.*", "",
             f"- **Model:** {layout.get('model')}, firmware {layout.get('firmware')}",
             f"- **Layout fingerprint:** `{layout.get('signature')}`"]
    if counts:
        lines.append(f"- **Records:** {counts[0]} live, {len(counts) - 1} memory sets of {counts[1] if len(counts) > 1 else '-'}")
    # the counts by tab and state live in docs/STATUS.md alone
    lines += [f"- **Definition:** {len(settings)} entries, {len(proved)} proved on the camera; by tab and state in "
              "[docs/STATUS.md](../STATUS.md)"]
    lines += ["", "**Ignored as volatile** (the camera file's `volatile_records`):"]
    lines += [f"- `{'global' if sec == 0 else f'set{sec}'}:0x{rid:04x}` {names.get(f'global:0x{rid:04x}', '')}"
              for sec, rid in sorted(camset.volatile(schema["model"]))]
    reset = ROOT / "data" / f"{layout.get('model')}_fw{layout.get('firmware')}" / f"settings_reset_{layout.get('model')}_fw{layout.get('firmware')}.json"
    if reset.exists():
        r = json.loads(reset.read_text(encoding="utf-8"))["records"]
        csr = collections.Counter(x["result"] for x in r.values() if "result" in x)
        ini = collections.Counter(x["initialize"] for x in r.values() if "initialize" in x)
        lines += ["", f"**Setting Reset test** ({len(r)} menu settings, `data/{reset.name}`): "
                  f"Camera Settings Reset reset {csr.get('resets', 0)} and left {csr.get('keeps', 0)}; "
                  f"Initialize reset {ini.get('resets', 0)}" + (f" and left {ini['keeps']}" if ini.get("keeps") else "") + "."]
    lines += ["", END]
    return "\n".join(lines)

