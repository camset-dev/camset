"""A menu row's name as the camera draws it, where the records know the row by an older name: ROW_NAMES in the camera's
hand tables (data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, schemas/hand-tables.schema.json), each older row
path and the camera's own, labels from the top-level row with " > " between ({"Proxy Settings > Px Proxy Recording":
"Proxy Settings > Proxy Recording"}). Until 2026-11-20 the kit could read the icon the camera draws before a label into
the label (page_model's icon_vote and camkit.crawl.icon_entry read it right of the icon since); the proof lines,
crawls, seen records and walk patterns written before keep their names (nobody edits a run's line), and every
comparison of a row's name exactly goes through here, so the older name and the camera's are one row: camkit.first_open's
seen keys, kit/prove_run.py's --rows, kit/pass1_map.py's map, kit/tools/menu_tree.py, camkit.placement, the hand tables'
walk patterns (writer/offered.py), the definition's proof rows (writer/proofs.menu_row) and kit/pass2_report.py's row
names. An entry names a row and everything under it ("S&Q Settings > S&Q Record Setting" renames that row's paths and
none above it). Labels are compared as the network checks compare them (safety.plain: case, spacing and the signs at
either end aside). A camera whose file holds no ROW_NAMES, or no file, has every name as it is."""
import json
import re

from . import safety

SEP = " > "
TABLE = "ROW_NAMES"
# where a row's path ends in a proof's or the report's name: an option of the row (" / "), or a field, an axis or a
# context in brackets (camkit.placement.steps)
_TAIL = re.compile(r" / | \[")
_CACHE: dict = {}


def _camera(camera):
    """The camera named, else the one the kit works on (camkit.paths.camera), worked out once for each state of what
    names it (the environment's camera, the config file and its time, the runs' folder): a row's name is compared often."""
    if camera:
        return camera
    import os

    from . import paths
    cfg = paths._pkg().CONFIG                # camkit.CONFIG, which the tests set
    try:
        stamp = cfg.stat().st_mtime_ns
    except OSError:
        stamp = None
    state = (os.environ.get(paths.ENV), str(cfg), stamp, str(paths.runs_top()))
    if _CAMERA.get("state") != state:
        try:
            got = (paths.camera() or (None,))[0]
        except Exception:                   # no camera named, or one the config does not list: no table
            got = None
        _CAMERA.update(state=state, camera=got)
    return _CAMERA["camera"]


_CAMERA: dict = {}


def labels(path) -> tuple:
    """A row's path as its labels: a tuple or list as it is, a name split at " > " (what follows the path aside)."""
    if isinstance(path, str):
        return tuple(x.strip() for x in _split(path)[0].split(SEP) if x.strip())
    return tuple(str(x) for x in path or ())


def _split(name: str) -> tuple:
    """(the path, what follows it) of a row's name as written."""
    m = _TAIL.search(name)
    return (name[:m.start()], name[m.start():]) if m else (name, "")


def _key(path) -> tuple:
    return tuple(safety.plain(x) for x in path)


def table(camera: str | None = None) -> dict:
    """{older path compared plain (a tuple of plain labels): (the older path's labels as written, the camera's)} of the
    camera `camera` (by default the one the kit works on); {} for a camera with no file or no ROW_NAMES. Read again
    whenever the file changes. A table the kit cannot use is refused in plain words (ValueError): an entry that is no
    two names, a name with an empty label, a row renamed to itself, or a camera name that is itself an older one."""
    camera = _camera(camera)
    if not camera:
        return {}
    from . import datafiles
    p = datafiles.hand_tables_file(camera)
    try:
        stamp = p.stat().st_mtime_ns
    except OSError:
        return {}
    if _CACHE.get(camera, (None,))[0] != (str(p), stamp):
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
        _CACHE[camera] = ((str(p), stamp), read(doc.get(TABLE) or {}, p))
    return _CACHE[camera][1]


def read(entries, where="ROW_NAMES") -> dict:
    """table()'s shape of a ROW_NAMES object, refused in plain words (ValueError) where the kit cannot use it."""
    if not isinstance(entries, dict):
        raise ValueError(f"{where}: {TABLE} is no object of older row names and the camera's")
    out = {}
    for old, new in entries.items():
        a, b = labels(old), (labels(new) if isinstance(new, str) else ())
        if not a or not b or SEP.join(a) != str(old).strip() or SEP.join(b) != str(new).strip():
            raise ValueError(f"{where}: {TABLE}'s {old!r}: each side is a row's path, its labels with ' > ' between")
        if _key(a) == _key(b):
            raise ValueError(f"{where}: {TABLE}'s {old!r} renames the row to itself")
        out[_key(a)] = (a, b)
    chained = [SEP.join(b) for _, b in out.values() if _key(b) in out]
    if chained:
        raise ValueError(f"{where}: {TABLE} renames {chained[0]!r}, which it also names as an older name: give each "
                         "older name the camera's at once")
    return out


def renamed(path, camera: str | None = None) -> tuple:
    """The path's labels (a tuple, a list or a name: labels()) as the camera draws them: the longest older path it
    starts with put as the camera's (table), the labels after it kept; as they are where it starts with none."""
    got = labels(path)
    names = table(camera)
    k = _key(got)
    for n in range(len(got), 0, -1) if names else ():
        if k[:n] in names:
            return (*names[k[:n]][1], *got[n:])
    return got


def renamed_name(name: str, camera: str | None = None) -> str:
    """A row's name as written (labels with " > " between, then any " / option", field, axis or " [context]" a proof's
    or the report's name carries) with its path as the camera draws it (renamed), what follows as it is; the name as it
    is where its path is no older one."""
    name = str(name or "")
    head, tail = _split(name)
    new = renamed(head, camera)
    return SEP.join(new) + tail if new != labels(head) else name


def names(name: str, camera: str | None = None) -> list:
    """The row's name as given, as the camera draws it (renamed_name) and as each older name the table gives the same
    row, what follows its path kept: what a pattern written with any of them is to match (writer/offered.py)."""
    name = str(name or "")
    head, tail = _split(name)
    new = renamed(head, camera)
    out = [name, renamed_name(name, camera)]
    for old, cam in table(camera).values():
        if _key(new[:len(cam)]) == _key(cam):
            out.append(SEP.join((*old, *new[len(cam):])) + tail)
    return list(dict.fromkeys(out))


def same(a, b, camera: str | None = None) -> bool:
    """Whether two row paths or names (their paths) are one row: equal as the camera draws them, compared plain."""
    return _key(renamed(a, camera)) == _key(renamed(b, camera))


def as_in(asked, held, camera: str | None = None) -> list:
    """Each name of `asked` as `held` writes the same row (what follows the path equal, the paths the same row), where
    `asked` names it otherwise; as asked where held has no such name. A run asked for a row by an older name, or by the
    camera's where its map still holds the older one, gets the map's own name (kit/prove_run.py --rows)."""
    held = list(held)
    out = []
    for a in asked:
        head, tail = _split(a)
        hit = a if a in held else next((h for h in held if _split(h)[1] == tail and same(_split(h)[0], head, camera)),
                                       None)
        out.append(hit or a)
    return out
