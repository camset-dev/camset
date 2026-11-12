"""Which settings files the camera wrote: the downloads manifest (docs/decisions/0006).

Every settings file the link downloads is recorded, with its SHA-256, in its camera's downloads.jsonl
(runs/<model>_fw<fw>/downloads.jsonl, beside that camera's runs: camkit.paths). Link.upload and
kit/tools/upload_check.py send a file only when its bytes are those of a download in that manifest: a download of one
camera is never taken for another's. A copy of a download passes wherever it sits; a file written or edited by anything else
does not, whatever folder it is in: a value written in with camset.with_values, make_sample.py's output, the
editor's sample, a file with the right name in a dat/ folder. On 2026-11-01 a file edited by hand put the a1 II into
a restart loop in Movie mode; since then settings are changed on the camera and watched, and only what the camera
wrote goes back to it.

Downloads made before the manifest existed are taken in with adopt() (kit/tools/upload_check.py --adopt): a file is
adopted only when a run's events.jsonl logged its download, its size is the one logged, and it was not written after
the download.
"""
import hashlib
import time
from pathlib import Path

from . import jsonl, paths

MANIFEST = "downloads.jsonl"
DECISION = "docs/decisions/0006"
INSTEAD = ("change the setting on the camera, watch it take, and download that state (a run's own download is "
           "what goes back)")


class NotADownload(Exception):
    """The file's bytes are not a download's: it is never uploaded."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _root(root) -> Path:
    """The camera's run root: root when given, else camkit.paths.run_root()."""
    return Path(root) if root is not None else paths.run_root()


def manifest_path(root: Path = None) -> Path:
    return _root(root) / MANIFEST


def _shown(path: Path, root: Path) -> str:
    """The path as the manifest keeps it: relative to the camera's run root when inside it, else absolute."""
    p = Path(path).resolve()
    try:
        return p.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def entries(root: Path = None) -> list[dict]:
    """The manifest's entries; a line that is not an entry (one cut short by a crash) is left out, and the others
    still count."""
    return jsonl.read(manifest_path(root), bad="skip")


def newest_start(root: Path = None, under: Path = None) -> Path | None:
    """The camera's newest session start file: the last *_before.DAT the downloads manifest lists that is still there
    (under: within that run folder only), None when there is none. The manifest's order is the order of download; a
    file name's number is not (a run's counter starts again, and "93438" sorts after "239606" as text, 2026-11-11)."""
    root = _root(root)
    inside = Path(under).resolve() if under is not None else None
    for e in reversed(entries(root)):
        p = Path(root) / e.get("path", "")
        if p.name.endswith("_before.DAT") and p.exists() and (inside is None or inside in p.resolve().parents):
            return p
    return None


def record(path: Path, root: Path = None, **fields) -> dict:
    """Note a file the camera just wrote (the link's download). Returns the entry. A file that is no settings file
    (empty, cut short, another kind of file: camset.peek cannot read its header) is refused with NotADownload and not
    noted: an entry for it would let its bytes, an empty file's among them, pass check() as the camera's."""
    from . import camset                     # here: camset reads the camera files when it is imported
    path, root = Path(path), _root(root)
    data = path.read_bytes()
    try:
        camset.peek(data)
    except ValueError as e:
        raise NotADownload(f"{path}: not recorded as a camera download: it is not a settings file ({len(data)} bytes; "
                           f"{e}). Download the settings again; if the same happens, check the camera's card and "
                           f"its link.") from None
    entry = {"t": round(time.time(), 3), "path": _shown(path, root), "sha256": hashlib.sha256(data).hexdigest(),
             "bytes": len(data), **{k: v for k, v in fields.items() if v is not None}}
    root.mkdir(parents=True, exist_ok=True)
    jsonl.append(manifest_path(root), entry)
    return entry


def check(path: Path, root: Path = None) -> dict:
    """The manifest entry whose bytes the file holds; NotADownload when there is none (decision 6)."""
    path, root = Path(path), _root(root)
    if not path.is_file():
        raise NotADownload(f"{path}: no such file")
    if path.stat().st_size == 0:
        raise NotADownload(f"{path}: not a camera download: it is empty (0 bytes), and a settings file the camera "
                           f"wrote never is. Nothing is uploaded from it ({DECISION}): {INSTEAD}.")
    digest = sha256(path)
    known = entries(root)
    for e in known:
        if e.get("sha256") == digest:
            return e
    here = _shown(path, root)
    if any(e.get("path") == here for e in known):
        raise NotADownload(f"{path}: not a camera download any more: it changed after the camera wrote it (its SHA-256 "
                           f"is not the one recorded in {manifest_path(root)}). Nothing edited is uploaded "
                           f"({DECISION}): {INSTEAD}.")
    raise NotADownload(f"{path}: not a camera download (its SHA-256 is in no entry of {manifest_path(root)}): only "
                       f"files the camera wrote are uploaded, never one written or edited by hand or by a script "
                       f"({DECISION}). Instead: {INSTEAD}.")


def _say(msg: str):
    print(msg, flush=True)


def adopt(root: Path = None, slack: float = 300.0, say=_say) -> list[dict]:
    """Take in downloads made before the manifest: those a run's events.jsonl logged ("cmd" "download ..." with an
    ok reply), whose size is the logged one and whose file was not written after the download (slack seconds for the
    rename and the log line). Returns the entries added. A logged download that is no settings file (record refuses
    it: cut short, another kind of file) is left out and said, "not adopted: <path>: <why>", and the others are still
    taken in."""
    root = _root(root)
    have = {e.get("sha256") for e in entries(root)}
    added = []
    for log in sorted(root.glob("*/events.jsonl")):
        for ev in jsonl.read(log, bad="skip"):
            reply = ev.get("reply")
            if ev.get("kind") != "cmd" or not str(ev.get("cmd", "")).startswith("download") or \
                    not isinstance(reply, dict) or not reply.get("ok"):
                continue
            p = _found(reply.get("path"), root)
            if p is None or p.stat().st_size != reply.get("bytes") or p.stat().st_mtime > ev.get("t", 0) + slack:
                continue
            digest = sha256(p)
            if digest in have:
                continue
            have.add(digest)
            try:
                added.append(record(p, root, adopted_from=_shown(log, root)))
            except NotADownload as e:           # its own words name the file and why
                say(f"not adopted: {e}")
    return added


def _found(logged, root: Path) -> Path | None:
    """The logged download's file: where it was written, else the same place under this camera's run root (a clone
    that moved, or runs moved under their camera's folder by kit/tools/migrate_runs.py)."""
    if not logged:
        return None
    p = Path(logged)
    if p.is_file():
        return p
    parts = p.parts
    if "runs" in parts:
        rest = parts[len(parts) - parts[::-1].index("runs"):]
        for tail in (rest, rest[1:] if rest and paths.KEY.match(rest[0]) else None):
            q = Path(root).joinpath(*tail) if tail else None
            if q is not None and q.is_file():
                return q
    return None
