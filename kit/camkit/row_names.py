"""A menu row's name as the camera draws it, where the records know the row by an older name: ROW_NAMES in the camera's
hand tables (data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, schemas/hand-tables.schema.json), each older row
path and the camera's own, labels from the top-level row with " > " between ({"Proxy Settings > Px Proxy Recording":
"Proxy Settings > Proxy Recording"}). Until 2026-11-20 the kit could read the icon the camera draws before a label into
the label (page_model's icon_vote and camkit.crawl.icon_entry read it right of the icon since); the proof lines,
crawls, seen records and walk patterns written before keep their names (nobody edits a run's line), and every
comparison of a row's name exactly goes through here, so the older name and the camera's are one row: camkit.first_open's
seen keys, kit/prove_run.py's --rows, kit/pass1_map.py's map, kit/tools/menu_tree.py, camkit.placement, the hand tables'
walk patterns (writer/offered.py), the definition's proof rows (writer/proofs.menu_row), kit/pass2_report.py's row
names, kit/tools/proof_viewer.py and kit/tools/leads.py. No safety check ever sees a renamed name: the never-open list,
the look lap's lists and its "seen" judge a row under the label the camera draws now (camkit.first_open.Seen.
seen_as_drawn).

The one kind of entry (fault): the camera's path is the older path with its last label less a leading token of at most
ICON_LEAD characters, an icon's letters ("Proxy Settings > Px Proxy Recording" is "Proxy Settings > Proxy Recording"),
or the kit's own "#n" form of that label ("Rec. Media Settings > Recording Media (Movie)" is "Rec. Media Settings >
Recording Media#1", camkit.placement.nth); every label above the last the same, and no label of either side one a
safety list names. A table is read once a process, before a run opens its link (table), and one that holds anything
else is refused in plain words. A camera whose file holds no ROW_NAMES, or no file, has every name as it is."""
import json
import re

from . import safety

SEP = " > "
TABLE = "ROW_NAMES"
ICON_LEAD = 4           # characters an icon before a label is read as at most: "S&Q", "LAN", "Saa", "MR", "R"
# where a row's path ends in a proof's or the report's name: an option of the row (" / "), or a field, an axis or a
# context in brackets (camkit.placement.steps)
_TAIL = re.compile(r" / | \[")
_NTH = re.compile(r"(.*\S)#(\d+)")                  # the kit's "#n" form of a label (camkit.placement.nth)
_QUALIFIED = re.compile(r"(.*\S) \(([A-Za-z]+)\)")  # the kit's own older name of one of two rows: "Recording Media (Movie)"
# the safety lists no side of an entry may hold a label of
_LISTS = ("never_open", "look_destructive", "acts_on_open", "owner_never_listed")
_TABLES: dict = {}       # the camera asked (None: the one the kit works on) -> its table, read once a process
_RENAMED: dict = {}      # (the table's id, labels) -> renamed's answer
_FAULTS: dict = {}


def forget() -> None:
    """Every table and answer kept, dropped: the next call reads them again (a test that rewrites a file or names
    another camera: kit/tests/conftest.py's own_runs)."""
    for d in (_TABLES, _RENAMED, _FAULTS):
        d.clear()


def _camera(camera):
    """The camera named, else the one the kit works on (camkit.paths.camera); None where nothing names one."""
    if camera:
        return camera
    from . import paths
    try:
        return (paths.camera() or (None,))[0]
    except Exception:                       # no camera named, or one the config does not list: no table
        return None


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


def fault(old, new) -> str | None:
    """Why the entry (`old`, `new`: the older path's labels and the camera's) is not the one kind ROW_NAMES holds, or
    None: every label above the last the same in both; the camera's last label the older one with its leading token of
    at most ICON_LEAD characters and the space after it left out ("Px Proxy Recording" -> "Proxy Recording", "S&Q Record
    Setting" -> "Record Setting"), or the kit's "#n" form of the older label less a one-word qualifier in brackets, the
    kit's own older name of one of two rows of a label ("Recording Media (Movie)" -> "Recording Media#1"; never a bare
    label to its "#n", which would take the other row of that label too); and no label of either side one
    the never-open list, the look lap's destructive list, the acts-on-open list or OWNER_NEVER names."""
    old, new = tuple(old), tuple(new)
    got = _FAULTS.get((old, new), False)
    if got is not False:
        return got
    why = None
    if not old or not new or len(old) != len(new) or old[:-1] != new[:-1]:
        why = "only its last label may differ, every label above it the same"
    else:
        lo, lc = old[-1], new[-1]
        m = _NTH.fullmatch(lc)
        base = m[1] if m else lc
        token, _, rest = lo.partition(" ")
        q = _QUALIFIED.fullmatch(lo)
        iconed = bool(rest) and 0 < len(token) <= ICON_LEAD and rest == base
        if safety.plain(lo) == safety.plain(lc):
            why = "it renames the row to itself"
        elif not (iconed or (m and q and q[1] == base)):
            why = (f"the camera's last label is the older one less a leading token of at most {ICON_LEAD} characters "
                   "(an icon's letters), or its \"#n\" form")
    if why is None:
        listed = [(x, f) for x in (*old, *new) for f in _LISTS if getattr(safety, f)(x)]
        if listed:
            why = f"a safety list names {listed[0][0]!r} ({listed[0][1]}): no such row is renamed"
    _FAULTS[(old, new)] = why
    return why


def read(entries, where="ROW_NAMES") -> dict:
    """{older path compared plain (a tuple of plain labels): (the older path's labels as written, the camera's)} of a
    ROW_NAMES object, refused in plain words (ValueError) where the kit cannot use it: an entry that is no two paths, or
    not the one kind (fault), two older names alike, or an older path that is the start of another entry's camera path,
    or a camera path the start of another entry's older path (no row is renamed twice)."""
    if not isinstance(entries, dict):
        raise ValueError(f"{where}: {TABLE} is no object of older row names and the camera's")
    out = {}
    for old, new in entries.items():
        a, b = labels(old), (labels(new) if isinstance(new, str) else ())
        if not a or not b or SEP.join(a) != str(old).strip() or SEP.join(b) != str(new).strip():
            raise ValueError(f"{where}: {TABLE}'s {old!r}: each side is a row's path, its labels with ' > ' between")
        why = fault(a, b)
        if why:
            raise ValueError(f"{where}: {TABLE}'s {old!r}: {why}")
        if _key(a) in out:
            raise ValueError(f"{where}: {TABLE} names {old!r} twice")
        out[_key(a)] = (a, b)
    for ka, (a, b) in out.items():
        for kc, (c, d) in out.items():
            if ka != kc and (_key(d)[:len(a)] == ka or _key(c)[:len(b)] == _key(b)):
                raise ValueError(f"{where}: {TABLE}'s {SEP.join(a)!r} and {SEP.join(c)!r}: one row's older or camera "
                                 "path starts another's, so a row would be renamed twice")
    return out


def table(camera: str | None = None) -> dict:
    """read()'s table of the camera `camera` (by default the one the kit works on), read once a process and never again
    (a run reads it as it starts, before its link opens, through camkit.first_open.seen_record, so a table refused, or
    half saved, stops it there and never in the middle of a run); {} for a camera with no file or no ROW_NAMES."""
    got = _TABLES.get(camera)
    if got is None:
        # kept under the camera asked (None: the one the kit works on) and under the camera that is, so one read serves
        # both ways of asking
        name = _camera(camera)
        got = _TABLES.get(("camera", name))
        if got is None:
            got = _TABLES[("camera", name)] = _load(name)
        _TABLES[camera] = got
    return got


def _load(camera) -> dict:
    """The camera's table read from its hand tables file (read), {} where it has none."""
    if not camera:
        return {}
    from . import datafiles
    p = datafiles.hand_tables_file(camera)
    try:
        raw = p.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    return read(json.loads(raw).get(TABLE) or {}, p)


def renamed(path, camera: str | None = None) -> tuple:
    """The path's labels (a tuple, a list or a name: labels()) as the camera draws them: the older path it starts with
    put as the camera's (table), the labels after it kept; as they are where it starts with none. An entry is applied
    only where it is the one kind (fault), whatever handed the table in."""
    names = _TABLES.get(camera)
    if names is None:
        names = table(camera)
    if not names:                   # no table, as on every camera so far: the path as it is, at once
        return tuple(path) if isinstance(path, (tuple, list)) else labels(path)
    got = labels(path)
    k = (id(names), got)            # the table kept in _TABLES for the process, so its id names it
    if k not in _RENAMED:
        out, key = got, _key(got)
        for n in range(len(got), 0, -1):
            hit = names.get(key[:n])
            if hit and fault(*hit) is None:
                out = (*hit[1], *got[n:])
                break
        _RENAMED[k] = out
    return _RENAMED[k]


def renamed_name(name: str, camera: str | None = None) -> str:
    """A row's name as written (labels with " > " between, then any " / option", field, axis or " [context]" a proof's
    or the report's name carries) with its path as the camera draws it (renamed), what follows as it is; the name as it
    is where its path is no older one."""
    name = str(name or "")
    if not table(camera):
        return name
    head, tail = _split(name)
    new = renamed(head, camera)
    return SEP.join(new) + tail if new != labels(head) else name


def names(name: str, camera: str | None = None) -> list:
    """The row's name as given, as the camera draws it (renamed_name) and as each older name the table gives the same
    row, what follows its path kept: what a pattern written with any of them is to match (writer/offered.py)."""
    name = str(name or "")
    if not table(camera):
        return [name]
    head, tail = _split(name)
    new = renamed(head, camera)
    out = [name, renamed_name(name, camera)]
    for old, cam in table(camera).values():
        if _key(new[:len(cam)]) == _key(cam) and fault(old, cam) is None:
            out.append(SEP.join((*old, *new[len(cam):])) + tail)
    return list(dict.fromkeys(out))


def same(a, b, camera: str | None = None) -> bool:
    """Whether two row paths or names (their paths) are one row: equal as the camera draws them, compared plain."""
    return _key(renamed(a, camera)) == _key(renamed(b, camera))


def as_in(asked, held, camera: str | None = None) -> list:
    """Each name of `asked` as `held` writes the same row (what follows the path equal, the paths one row by the table),
    where `asked` names it otherwise; as asked where held has no such name, and every name as asked with no table (a
    name is then compared exactly, as kit/prove_run.py --rows compares it). A run asked for a row by an older name, or
    by the camera's where its map still holds the older one, gets the map's own name."""
    if not table(camera):
        return list(asked)
    held = list(held)
    out = []
    for a in asked:
        head, tail = _split(a)
        hit = a if a in held else next((h for h in held if _split(h)[1] == tail and same(_split(h)[0], head, camera)),
                                       None)
        out.append(hit or a)
    return out
