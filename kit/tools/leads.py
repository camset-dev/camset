"""The leads: which records no setting covers ever changed in the camera's own downloads, and with which rows.

    .venv/bin/python kit/tools/leads.py                  # the counts: files, steps, files not read, each class
    .venv/bin/python kit/tools/leads.py --top 40         # and the 40 strongest leads, key, class, steps, row
    .venv/bin/python kit/tools/leads.py --write          # and the private leads file the coverage ledger reads

Run it before `kit/tools/coverage.py --todo`: the ledger then tells "unmapped, never seen to change" and "changed, no
row attributed" apart from "unmapped, not examined", and weighs a row by the changing records beside it. The camera is
the one the kit works on (--camera <model>_fw<fw>, CAMSET_CAMERA or private/config.json: camkit.paths), its runs are
under its run root (CAMSET_RUNS moves the runs' folder), and its definition says which records a setting covers
(camkit.coverage.records_covered, the ledger's own rule).

It reads every settings file in a run folder's dat/ (runs/<model>_fw<fw>/<run>/dat/*.DAT) with the kit's reader
(camkit.camset), each distinct file's bytes parsed once while it is recent; a file the reader refuses, or one another
model or firmware saved, is not read, counted, and breaks the chain there. A step is two files read one after the
other in one run folder, ordered by the leading number of their names (00010 after 0009; a name with none after the
numbered ones, by name), compared with camset.diff, which leaves out the camera file's volatile records: those are left
out of the leads too, so the ledger claims nothing of them. A step's row is the row of each setting whose record
changed in it, or, where the run's proofs.jsonl names the step's later file as a proof's "dat" (one with a download of
its own: its "base" another file), that proof's "path". For each record no setting covers it counts the steps it
changed in ("changes"), its distinct values across every file read ("values": a memory-set record's value is the
twelve sets' together), the rows of those steps ("rows", the 8 most frequent; "other_rows", how many more) and the run
folders it changed in ("runs"), and classes it:

    NEVER     one value in every file read
    BETWEEN   more than one value, but never changed inside a step (between run folders, or across a file not read)
    SPECIFIC  changed inside steps, every one with a row naming the same single row
    SEVERAL   changed inside steps attributed to two rows or more
    ALONE     changed only inside steps with no row

--write writes camkit.coverage.leads_file (private/evidence/<model>_fw<fw>/leads_<model>_fw<fw>.json, owner-only,
written whole), and nothing else anywhere; without it nothing is written. Never a record's value, in the file or on the
screen: keys, classes, counts and row labels only (docs/decisions/0016). It opens no link and asks no reader.
"""
import argparse
import hashlib
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import paths  # noqa: E402

CLASSES = ("NEVER", "BETWEEN", "SPECIFIC", "SEVERAL", "ALONE")
ROWS_KEPT = 8
RECENT = 32                         # parsed files kept by their bytes' hash: a file met again soon is not parsed again
NUMBER = re.compile(r"^(\d+)")
ABOUT = ("Which records no setting of the camera's definition covers changed in its own downloads, step by step, and "
         "the rows of those steps, by kit/tools/leads.py: keys, classes and counts only, never a value "
         "(docs/decisions/0016).")


def downloads(run: Path) -> list:
    """The settings files in a run folder's dat/, by the leading number of their names, then those with none by name."""
    d = Path(run) / "dat"
    if not d.is_dir():
        return []
    files = [p for p in d.iterdir() if p.suffix.upper() == ".DAT" and p.is_file()]

    def order(p):
        m = NUMBER.match(p.name)
        return (0, int(m.group(1)), p.name) if m else (1, 0, p.name)
    return sorted(files, key=order)


def proof_rows(run: Path) -> dict:
    """{file name: row} of the run's proofs.jsonl: the row path of the last proof naming the file as its download
    ("dat"), one naming its own base ("dat" and "base" alike: nothing downloaded) or another run's file aside."""
    from camkit import jsonl
    out = {}
    try:
        lines = jsonl.read(Path(run) / "proofs.jsonl", bad="skip")
    except (OSError, ValueError):
        return out
    for r in lines:
        dat, path = r.get("dat"), r.get("path")
        if not isinstance(dat, str) or not dat or not isinstance(path, list) or not path or r.get("base") == dat:
            continue
        where, _, name = dat.replace("\\", "/").rpartition("/")
        if where and where.rsplit("/", 1)[-1] != Path(run).name:
            continue
        out[name] = " > ".join(str(x) for x in path)
    return out


def row_label(s: dict) -> str:
    return " > ".join(str(x) for x in s["row"]) if s.get("row") else str(s.get("name") or s.get("key"))


def entry(key: str, values: int, stat: dict | None) -> dict:
    """One record's lead: its class from its distinct values and the steps it changed in (stat: {"changes", "rows":
    {row: steps}, "runs": {run folder}}, None when it changed in none). Counts and row labels only."""
    if values <= 1:
        return {"key": key, "cls": "NEVER", "values": values}
    if not stat or not stat["changes"]:
        return {"key": key, "cls": "BETWEEN", "changes": 0, "values": values}
    rows = sorted(Counter(stat["rows"]).items(), key=lambda kv: (-kv[1], kv[0]))
    cls = "ALONE" if not rows else "SPECIFIC" if len(rows) == 1 else "SEVERAL"
    out = {"key": key, "cls": cls, "changes": stat["changes"], "values": values}
    if rows:
        out["rows"] = dict(rows[:ROWS_KEPT])
    if len(rows) > ROWS_KEPT:
        out["other_rows"] = len(rows) - ROWS_KEPT
    if stat["runs"]:
        out["runs"] = len(stat["runs"])
    return out


def key_number(k: str) -> int:
    return int(k.split(":")[1], 16)


class Miner:
    """The downloads of one camera, read run folder by run folder (mine)."""

    def __init__(self, camera: str, settings: list):
        from camkit import camset, coverage
        self.camset, self.coverage = camset, coverage
        self.model, self.firmware = paths.split(camera)
        self.on = coverage.records_covered(settings)
        self.rows_of = {k: sorted({row_label(s) for s in ss}) for k, ss in self.on.items()}
        try:
            self.block = camset.block_of(camera)
        except ValueError:
            self.block = None           # no camera file holds one: the reader picks the block that reads the file
        self.recent = OrderedDict()     # bytes' hash -> Camset
        self.refused = set()            # bytes' hashes the reader refused
        self.reference = None           # (hash, Camset): the first file read, the start of every chain
        self.values = {}                # unmapped record key -> {its distinct values}
        self.stats = {}                 # unmapped record key -> {"changes", "rows", "runs"}
        self.files = self.steps = self.not_read = 0

    def read(self, p: Path):
        """(hash, Camset) of a camera file this camera saved, else None (counted not read)."""
        try:
            data = p.read_bytes()
        except OSError:
            self.not_read += 1
            return None
        h = hashlib.sha256(data).digest()
        if h in self.refused:
            self.not_read += 1
            return None
        cs = self.recent.get(h)
        if cs is not None:
            self.recent.move_to_end(h)
            return h, cs
        try:
            cs = self.camset.parse(data, block=self.block, name=p.name)
            ok = cs.model == self.model and cs.firmware == self.firmware
        except Exception:               # noqa: BLE001 (a file the reader refuses, whatever it raises, is skipped)
            ok = False
        if not ok:
            self.refused.add(h)
            self.not_read += 1
            return None
        self.recent[h] = cs
        if len(self.recent) > RECENT:
            self.recent.popitem(last=False)
        return h, cs

    def value(self, cs, k: str):
        """A record's bytes in a file: a memory-set record's in every set, in set order (never written or printed)."""
        rid = key_number(k)
        if k.startswith("global:"):
            return cs.sections[0][rid].raw
        return tuple(sec[rid].raw if rid in sec else None for sec in cs.sections[1:])

    def start(self, cs) -> None:
        """The record keys as the ledger names them (camkit.coverage.records_of: section 0 live, the sets' one layout as
        "set:"), those no setting covers, the volatile ones aside, each with its value in the first file read."""
        noisy = {rid for _, rid in self.camset.volatile(cs.model)}
        keys = [f"global:0x{rid:04x}" for rid in cs.sections[0] if rid not in noisy]
        keys += [f"set:0x{rid:04x}" for rid in (cs.sections[1] if len(cs.sections) > 1 else {})]
        self.values = {k: {self.value(cs, k)} for k in keys if k not in self.on}

    def changed(self, a, b) -> set:
        """The record keys camset.diff finds differ between two files (a memory set's as "set:")."""
        return {self.coverage.record_base(c.key) for c in self.camset.diff(a, b)}

    def run(self, folder: Path) -> None:
        rows_by_file = proof_rows(folder)
        prev = None
        for p in downloads(folder):
            got = self.read(p)
            if got is None:
                prev = None             # a file not read breaks the chain: no step spans it
                continue
            h, cs = got
            if self.reference is None:
                self.reference = got
                self.start(cs)
                self.files += 1
                prev = got
                continue
            base = prev or self.reference
            try:
                changed = set() if h == base[0] else self.changed(base[1], cs)
            except ValueError:          # another layout than the first file's
                self.refused.add(h)
                self.recent.pop(h, None)
                self.not_read += 1
                prev = None
                continue
            self.files += 1
            for k in changed:
                if k in self.values:
                    self.values[k].add(self.value(cs, k))
            if prev is not None:
                self.steps += 1
                self.step(folder.name, changed, rows_by_file.get(p.name))
            prev = got

    def step(self, run: str, changed: set, proved: str | None) -> None:
        rows = {proved} if proved else {r for k in changed for r in self.rows_of.get(k, ())}
        for k in changed:
            if k not in self.values:
                continue
            st = self.stats.setdefault(k, {"changes": 0, "rows": Counter(), "runs": set()})
            st["changes"] += 1
            st["runs"].add(run)
            for r in rows:
                st["rows"][r] += 1

    def doc(self, camera: str) -> dict:
        out = {"about": ABOUT, "camera": camera, "files": self.files, "steps": self.steps, "not_read": self.not_read,
               "live": [], "sets": []}
        for k in sorted(self.values, key=key_number):
            out["live" if k.startswith("global:") else "sets"].append(entry(k, len(self.values[k]), self.stats.get(k)))
        return out


def run_folders(root: Path) -> list:
    return sorted(d for d in Path(root).iterdir() if d.is_dir() and (d / "dat").is_dir()) if Path(root).is_dir() \
        else []


def mine(camera: str, root: Path = None, settings: list = None) -> dict:
    """The leads document of the camera's downloads under `root` (its run root unless given), by its definition's
    settings unless `settings` is given."""
    from camkit import definitions
    if settings is None:
        settings = definitions.load(definitions.path(camera)).get("settings") or []
    m = Miner(camera, settings)
    for folder in run_folders(root if root is not None else paths.run_root(camera)):
        m.run(folder)
    return m.doc(camera)


def summary(doc: dict) -> list:
    out = [f"{doc['camera']}: {doc['files']} files read, {doc['steps']} steps, {doc['not_read']} not read"]
    for part, said in (("live", "live records no setting covers"), ("sets", "memory sets' records no setting covers")):
        n = Counter(x["cls"] for x in doc[part])
        out.append(f"{said}: " + ", ".join(f"{c} {n[c]}" for c in CLASSES))
    return out


def strongest(doc: dict, n: int) -> list:
    """The `n` strongest leads, each "key  cls  changes  row (steps)": SPECIFIC by changes, then SEVERAL."""
    leads = [(p, x) for p, part in enumerate(("live", "sets")) for x in doc[part] if x["cls"] in ("SPECIFIC", "SEVERAL")]
    leads.sort(key=lambda px: (px[1]["cls"] != "SPECIFIC", -px[1]["changes"], px[0], key_number(px[1]["key"])))
    out = []
    for _, x in leads[:max(n, 0)]:
        rows = list(x.get("rows", {}).items())
        more = len(rows) - 3 + x.get("other_rows", 0)
        said = "; ".join(f"{r} ({c})" for r, c in rows[:3]) + (f"; {more} more rows" if more > 0 else "")
        out.append(f"{x['key']}  {x['cls']}  {x['changes']}  {said}")
    return out


def write(doc: dict, camera: str) -> Path:
    """The private leads file, whole (a temporary file put in place) and owner-only, its folder too."""
    import os

    from camkit import coverage
    p = coverage.leads_file(camera)
    p.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(p.parent, 0o700)
    try:
        return coverage._replace(p, coverage.text(doc), private=True)
    except OSError:
        p.with_name(p.name + ".part").unlink(missing_ok=True)      # the file there, if any, stays as it was
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 epilog="The camera: --camera <model>_fw<fw>, CAMSET_CAMERA or private/config.json.")
    ap.add_argument("--write", action="store_true", help="write the private leads file the coverage ledger reads")
    ap.add_argument("--top", type=int, metavar="N", help="list the N strongest leads (SPECIFIC, then SEVERAL)")
    a = ap.parse_args()
    got = paths.camera()
    if not got:
        sys.exit(paths.no_camera_message())
    camera = got[0]
    from camkit import definitions
    if not definitions.path(camera).exists():
        sys.exit(f"no definition for {camera}: kit/schema_update.py --write makes one")
    doc = mine(camera)
    print("\n".join(summary(doc)))
    for line in strongest(doc, a.top or 0):
        print(line)
    if a.write:
        try:
            p = write(doc, camera)
        except OSError as e:
            sys.exit(f"the leads file was not written: {e}")
        print(f"written: {paths.shown(p)}")


if __name__ == "__main__":
    main()
