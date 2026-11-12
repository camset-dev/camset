"""What camera and firmware a settings file, or the connected camera, is, and which definition knows it.

    .venv/bin/python kit/tools/identify.py FILE.DAT [FILE.DAT ...]
    .venv/bin/python kit/tools/identify.py --camera        # ask the camera (SDK), then download a file and check it
    .venv/bin/python kit/tools/identify.py --camera ILCE-1M2_fw4.00   # the same, saying which camera you expect

For a file: which container block reads it (every camera file's and every definition's "file" is tried, as the
editor tries them: the magic, the record framing, then both checksums; docs/decisions/0020), then through that block
the model, the save time, the firmware bytes (the a1 II files seen read 02 00, 03 00 and 04 00: firmware 2.00, 3.00
and 4.00), the video system where the block says where it is (the a1 II's byte after the firmware: 0 NTSC, 1 PAL, proved
on firmware 4.00 on 2026-11-06; until then the kit read a file saved on PAL as another firmware, x.01),
record counts per section, both checksums and the layout fingerprint (the block's signature: FNV-1a 64 over the model,
the first two firmware bytes and every record's id and shape, as CamSet::layout_signature in the editor computes it).
A firmware update that adds, removes, reorders or resizes records changes the fingerprint; the video system does not.

When no known block describes the file, or its checksums fail under the one that frames it, it prints a draft block:
the nearest known one, with what holds under it and what does not, for the person and their agent to correct by hand
into the new camera's data/<model>_fw<fw>/camera_<model>_fw<fw>.json ("file"), then to check with this command
again. The draft is printed, never written into a file.

The fingerprint is then looked up in the definitions' "layouts" (editor/definitions/<model>_fw<fw>.json, one per model
and firmware, docs/decisions/0019). A known fingerprint names the definition and its model page (docs/models/); an
unknown one means a new model or firmware, mapped as docs/REMAPPING_PLAYBOOK.md's "New model: first day" says, whose
definition kit/schema_update.py --write writes.

--camera reads ModelName, SoftwareVersion and the lens from the SDK (the firmware is not written in
the file), then downloads the settings and identifies that file. The body's serial number is never
printed. The download goes into that camera's own folder, runs/<ModelName>_fw<SoftwareVersion>/kit2_identify/
(camkit.paths), whichever camera the config names: identify.py is how a new camera's folder starts. It prints the
camera's key, and what to put in private/config.json when the config names another camera or none.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, definitions  # noqa: E402


def signature(data: bytes) -> str:
    """The editor's CamSet::layout_signature of a file, through the block that reads it."""
    return camset.parse(data, check=False).signature()


def known(sig: str, model: str) -> list[str]:
    """What the definitions (editor/definitions/*.json) say of a layout fingerprint: the one whose layout it is, else
    a definition of the same model on another layout, else that it is unknown."""
    out, same = [], []
    for path, s in definitions.every(evidence=False):
        rel = path.relative_to(ROOT).as_posix()
        for lay in s.get("layouts") or []:
            if lay.get("signature") == sig:
                doc = lay.get("doc") or (s.get("camera") or {}).get("doc")
                out.append(f"KNOWN: {lay.get('model')} firmware {lay.get('firmware')}: definition {rel}"
                           + (f", model page {doc}" if doc else ""))
        if s.get("model") == model:
            same.append(rel)
    if not out and same:
        out.append(f"same model, different layout: {', '.join(same)} was mapped on another firmware or body; its "
                   f"records may have moved, so prove before trusting it (the editor opens the file with the nearest "
                   f"firmware's definition, view only where the records differ)")
    return out or ["UNKNOWN layout: a new model or firmware. Map it (docs/REMAPPING_PLAYBOOK.md, \"New model: first "
                   "day\"); kit/schema_update.py --write then writes its definition, "
                   "editor/definitions/<model>_fw<fw>.json, which the editor takes with Add definition..."]


def draft(data: bytes) -> list[str]:
    """For a file no known block describes: the nearest known block as a draft, with what holds under it and what
    does not. Printed only, never written."""
    pairs = camset.camera_blocks()
    if not pairs:
        return ["  no camera file in data/ holds a container block to start a draft from"]

    def holds(b):
        return [b.magic_matches(data), b.describes(data), b.header_checksum.holds(data), b.trailer_checksum.holds(data)]
    b, keys = max(pairs, key=lambda kv: sum(holds(kv[0])))
    magic, frames, head, tail = holds(b)

    def mark(ok):
        return "holds" if ok else "does NOT hold"
    return [f"  no known container block describes this file. A draft from {', '.join(keys)}'s, unverified:",
            f"    the magic {b.magic.decode('ascii', 'replace')!r} at {b.magic_at}: {mark(magic)}",
            f"    the records framed from {b.sections_start} up to the trailer checksum at {b.trailer_checksum.at}: "
            f"{mark(frames)}",
            f"    the header checksum ({b.header_checksum.kind}) at {b.header_checksum.at}: {mark(head)}",
            f"    the trailer checksum ({b.trailer_checksum.kind}) at {b.trailer_checksum.at}: {mark(tail)}",
            "  Correct it by hand into the camera's data/<model>_fw<fw>/camera_<model>_fw<fw>.json as \"file\" "
            "(docs/DATA_CONTRACTS.md, the container block) and run this again: the block is right when the file reads "
            "and both checksums hold. A kind the vocabulary lacks is a change to the program (docs/decisions/0020).",
            "  \"file\": " + json.dumps(b.as_json(), indent=2).replace("\n", "\n  ")]


def describe(path: Path) -> str:
    data = path.read_bytes()
    try:
        cs = camset.parse(data, check=False, name=str(path))
    except ValueError as e:
        return "\n".join([f"{path}", f"  {e}"] + draft(data))
    b = cs.block
    counts = [len(s) for s in cs.sections]
    sig = cs.signature()
    users = next((keys for blk, keys in camset.camera_blocks() if blk == b), [])
    fw = b.firmware_bytes(data)
    video = b.video_system_of(data)
    lines = [f"{path}",
             f"  container: the block of {', '.join(users) or 'a known camera'}",
             f"  model {cs.model}, saved {cs.saved}",
             f"  firmware bytes {b.firmware[0]}-{camset.Offset(b.firmware[1].n - 1)}: {' '.join(f'{x:02x}' for x in fw)} "
             f"(firmware {cs.firmware} by the header)"]
    if video is not None:
        lines.append(f"  video system byte {b.video_system[0]}: {video[0]:02x} ({cs.video_system}; not part of the "
                     f"camera's identity: one firmware's files under every video system share its definition)")
    lines += [f"  sections: live {counts[0]} records, {len(counts) - 1} memory sets of "
              f"{', '.join(sorted({str(c) for c in counts[1:]}))} records",
              f"  checksums {'ok' if cs.checksums_ok else 'BAD'}; layout fingerprint {sig}"]
    if not cs.checksums_ok:
        lines += ["  the checksums do not hold under this block: the editor treats the file as unknown and never "
                  "edits it"] + draft(data)
    lines += ["  " + k for k in known(sig, cs.model)]
    return "\n".join(lines)


def ask_camera() -> list:
    """Ask the connected camera which it is, download its settings into that camera's own folder
    (runs/<model>_fw<fw>/kit2_identify), and identify the file. Returns the lines to print after the file's."""
    from camkit import models, paths
    from camkit.link import Link
    from camkit.runs import Run
    paths.check_leftovers()                          # before the link opens: their message, and nothing done
    named = paths.camera()
    with tempfile.TemporaryDirectory(prefix="camset-identify-") as tmp:
        # the link opens before the camera has said which it is: its first lines wait in a folder of their own
        first = Run("kit2_identify", root=Path(tmp))
        with Link(first) as link:
            props = {p["name"]: p for p in link.props()}
            text = {n: str(props.get(n, {}).get("text") or "") for n in ("ModelName", "SoftwareVersion", "LensModelName")}
            print(f"camera: {text['ModelName']} firmware {text['SoftwareVersion']}, lens {text['LensModelName'] or '-'}")
            cam = paths.key(text["ModelName"], text["SoftwareVersion"])
            if not paths.KEY.match(cam):
                if not named:
                    sys.exit("The camera did not say its model and firmware, so its folder in runs/ cannot be named: "
                             "add --camera <model>_fw<firmware> (the model on the body, the firmware in its menu's "
                             "Version) and run this again.")
                print(f"the camera did not say its model and firmware: its download goes to {named[0]}'s folder, "
                      f"as {named[1]} names it")
                cam = named[0]
            run = Run("kit2_identify", root=paths.run_root(cam))
            with open(run.dir / "events.jsonl", "a", encoding="utf-8", newline="\n") as f:
                f.write((first.dir / "events.jsonl").read_text(encoding="utf-8"))
            link.use_run(run)
            got = link.download("identify")
    print(describe(got))
    out = [f"this camera is {cam}: its runs go to {paths.shown(run.root)}/"]
    try:
        said = paths.key(*models.header(got))
    except (OSError, ValueError):
        said = cam
    if said != cam:
        out.append(f"  note: the file's header says {said}; the folder is named by what the camera said (its "
                   f"SoftwareVersion), as data/<model>_fw<fw>/ is")
    if not named:
        out.append(f"  nothing names a camera yet: put \"camera\": \"{cam}\" in private/config.json (or add "
                   f"--camera {cam} to each command); while runs/ holds one camera's runs, the kit takes that one")
    elif named[0] != cam:
        out.append(f"  {named[1]} names {named[0]}, not this camera: set \"camera\": \"{cam}\" in "
                   f"private/config.json (with its entry in \"cameras\" if the config lists them), or add "
                   f"--camera {cam} to each command, before the next one")
    return out


def main():
    from camkit import paths
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--camera", action="store_true", help="ask the connected camera, then identify its download "
                    "(--camera <model>_fw<fw>: the same, saying which camera you expect)")
    a = ap.parse_args()
    ask = a.camera or bool(paths.named_on_command_line())
    if not a.files and not ask:
        ap.error("give settings files, or --camera")
    for f in a.files:
        print(describe(f))
    if ask:
        print("\n".join(ask_camera()))


if __name__ == "__main__":
    main()
