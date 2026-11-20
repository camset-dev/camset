"""The shooting mode a settings file was saved in, by the camera's own live-mode record: the camera file's `live_mode`
(its record's key and the code of each mode; no camera's fact here). Read from a file once and kept in the camera's
cache, runs/<model>_fw<fw>/_cache/live_mode.json, by the file's SHA-256 and the record's key, the raw code only (so a
mode the camera file names later, or renames, needs no new reading): the writer reads the mode of every counted proof
whose context names none from its base download (kit/pass2_report.py silent_modes, writer/proofs.with_menu_modes),
about 1,250 files on the a1 II, 50 s to parse afresh and well under a second from the cache. A file that cannot be
read or parsed gives no mode and is not kept, so it is read afresh next time; a cache that cannot be read or written
changes nothing. Only a write keeps what it read (save()); a dry run keeps nothing."""
import hashlib
import json
import re
from pathlib import Path

from . import camset

CACHE = None                # a cache file in place of the camera's (the tests)
FORMAT = 1
KEY = re.compile(r"(global|set(\d+)):0x([0-9a-f]{4})")


def cache_file(run_root: Path) -> Path:
    """The camera's live-mode cache: CACHE where it is set, else <run_root>/_cache/live_mode.json."""
    return Path(CACHE) if CACHE is not None else Path(run_root) / "_cache" / "live_mode.json"


class Reader:
    """Each settings file's shooting mode by `live_mode` (the camera file's: {"key", "modes": {code: mode}}), cached in
    `cache` (cache_file); save() writes what was read afresh. With no usable live_mode it reads nothing (None)."""

    def __init__(self, live_mode: dict | None, cache: Path | None):
        lm = live_mode if isinstance(live_mode, dict) else {}
        m = KEY.fullmatch(str(lm.get("key") or ""))
        self.where = (0 if m[1] == "global" else int(m[2]), int(m[3], 16)) if m else None
        self.key = lm.get("key")
        self.modes = {str(k): v for k, v in (lm.get("modes") or {}).items()}
        self.cache, self.codes, self.fresh = cache, {}, False
        self.by_path = {}
        if self.where is None or cache is None:
            return
        try:
            kept = json.loads(Path(cache).read_text(encoding="utf-8"))
            if kept.get("format") == FORMAT and kept.get("key") == self.key and isinstance(kept.get("codes"), dict):
                self.codes = kept["codes"]
        except (OSError, ValueError, AttributeError):
            pass                    # none yet, or one that cannot be read: read afresh

    def mode(self, path) -> str | None:
        """The mode the file at `path` was saved in, by its live-mode record's code; None where there is no live_mode,
        no such file or record, or a code live_mode names no mode for."""
        if self.where is None or path is None:
            return None
        path = Path(path)
        if path not in self.by_path:
            try:
                data = path.read_bytes()
            except OSError:
                return None
            sha = hashlib.sha256(data).hexdigest()
            if sha not in self.codes:
                try:
                    rec = camset.parse(data, name=str(path)).get(*self.where)
                except (ValueError, IndexError):
                    return None                 # no settings file this reader frames: not kept, read afresh next time
                v = rec.value() if rec is not None else None
                if not isinstance(v, int):
                    return None                 # no such record: not kept either
                self.codes[sha] = v
                self.fresh = True
            self.by_path[path] = self.codes[sha]
        code = self.by_path[path]
        return self.modes.get(str(code)) if code is not None else None

    def save(self) -> None:
        """The codes read afresh written to the cache (nothing where none was, or it cannot be written)."""
        if not self.fresh or self.cache is None:
            return
        try:
            Path(self.cache).parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(self.cache).with_suffix(".tmp")
            tmp.write_text(json.dumps({"format": FORMAT, "key": self.key, "codes": self.codes}, sort_keys=True),
                           encoding="utf-8")
            tmp.replace(self.cache)
            self.fresh = False
        except OSError:
            pass
