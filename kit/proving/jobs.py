"""What a run proves: the rows of pass 1's map in the reviewed scope, each made a job by its kind (a list's labels,
number fields' sampled steps, a side list's lap, a checklist's boxes), and the jobs of the other walks (the second
axes, Creative Look's panels, White Balance's grids); which proofs a job is done with (planned), and the keys the
proofs file and --rows name them by.

ICON_ROWS and LABELS below are the ILCE-1M2's (firmware 4.00), as is checklists.DISP_MODES: main() empties them for
another body (camkit.models). TODO: into data/<model>_fw<fw>/camera_*.json (docs/decisions/0019, 0020).
OSD_ROWS and HELP_TEXT are the run's (main() sets jobs.OSD_ROWS and jobs.HELP_TEXT before jobs())."""
import re

from camkit import ROOT, safety
from runner import read_json

from . import base
from .base import number
from .checklists import CHECK_LATER, star_label
from .looks import LOOK_CODES, LOOK_PARAMS
from .screens import option_key
from .sidelists import fix_lap, signed
from .tables import table_planned
from .wbgrid import WB_AXES

KINDS = ("list", "dialog", "fields", "sidelist", "checklist")   # list popups; carousels (main options); number fields
                                                   # and PP1's side lists (numbers sampled)
PP = "PP1"                       # Picture Profile panels are proved on PP1 (the map calls it "option 1")
PPS = [PP]                       # --pp: the profiles to prove (stills offers PP1-PP6, PP10, PP11)
# Carousels whose titles repeat: Creative Look's six custom slots show the look each is based on (the
# user's own choice). They are told apart by the selected icon ("1 ST" ... "6 BW") against pass 1's
# pictures, and labelled by slot, never by the base look.
ICON_ROWS = {"Creative Look": ["ST(Standard)", "PT(Portrait)", "NT(Neutral)", "VV(Vivid)", "VV2(Vivid 2)", "FL(Film)",
                               "FL2(Film 2)", "FL3(Film 3)", "IN(Instant)", "SH(Soft Highkey)", "BW(Black & White)",
                               "SE(Sepia)"] + [f"Custom Look {i}" for i in range(1, 7)]}
# Laps pass 1 read a step late here and there (the carousel title redraws after the strip): the
# camera's own sequence. Each label is still checked on the screen as the proof chooses it.
LABELS = {
    "ISO": ["ISO AUTO"] + [f"ISO {v}" for v in (50, 64, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800,
                                                 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000,
                                                 12800, 16000, 20000, 25600, 32000, 40000, 51200, 64000, 80000,
                                                 102400)],
    # stills mode offers no PP7-PP9 (the schema's 9 values agree); pass 1 read PP5 as "PP4" once
    "Picture Profile": ["Off", "PP1", "PP2", "PP3", "PP4", "PP5", "PP6", "PP10", "PP11"],
}
COUPLED = {"ISO Range Limit"}    # number fields that push each other (lower <= upper): not sampled one by one

OSD_ROWS = False
OSD_ONLY: set = set()

# --help-text: no proofs; the camera's own help for each list / dialog row and every option (C4, the
# trash button, owner-allowed for this alone, 2026-11-01): nothing is chosen
HELP_TEXT = False

# rows a dated owner decision in the reviewed scope names (jobs() reads them): their last labels are the never-open
# rows of sound, light or motion this run may open (decision 2; LiveCamera's row check)
APPROVED: set = set()
# never-open labels the operator named with --allow (the owner's word, per row): jobs() keeps the rows whose path
# holds one even where the reviewed scope excludes it, and the camera may open those labels only
ALLOWED: set = set()


def scope_rows(scope: dict, map_rows: list) -> tuple:
    """(allowed, excluded, approved) row names of a reviewed scope against a map's rows.
    allowed: the scope's "prove" list; an empty one (the template's, for a new body) means every row of the map,
    as the template's note says. Rows in "ask_user" are left out unless a dated owner decision names them
    (decisions: [{"date", "rows", "why"}]), and so are the never-open rows (checked per job) except the sound,
    light or motion rows such a decision names (decision 2)."""
    approved = safety.approved_rows(scope)
    excluded = {x for rows in scope["exclude"].values() for x in rows}
    ask = {x for rows in (scope.get("ask_user") or {}).values() for x in rows} - approved
    allowed = set(scope["prove"]) or {" > ".join(r["path"]) for r in map_rows} - excluded
    return allowed - ask, excluded | ask, approved


def jobs(scope_names=None):
    """List rows of the map in the reviewed scope: {"path": [...], "labels": [option labels in order]}."""
    reviewed = base.PASS1 / "pass2_scope_draft.json"
    # a fresh machine, or a new camera, has no reviewed scope yet (runs/ is not versioned): the template's exclusions
    scope = read_json(reviewed if reviewed.exists() else ROOT / "data" / "pass2_scope_template.json")
    allowed, excluded, approved = scope_rows(scope, read_json(base.MAP)["rows"])
    APPROVED.update(approved)
    if ALLOWED:
        allowed |= {" > ".join(r["path"]) for r in read_json(base.MAP)["rows"] if ALLOWED & set(r["path"])}
    out = {}
    if OSD_ROWS:                                    # seen through the OSD, HDMI can come and go
        OSD_ONLY.update(scope["exclude"].get("could take the menus off HDMI or blank a screen", []))
        allowed |= OSD_ONLY
    if HELP_TEXT:
        # help chooses nothing (C4, OK, MENU): the rows kept from proofs for what choosing them would do
        # (HDMI, monitor, sound, the remote session) are read too, the owner's go-ahead (2026-11-01);
        # the never-open list still applies
        allowed |= excluded
    if base.MAP != base.PASS1 / "map_all.json":
        # pass 3: a run's own map of rows a switched blocker opened; every row in it is in scope
        # unless the reviewed scope excluded it (the never-open list still applies)
        allowed |= {" > ".join(r["path"]) for r in read_json(base.MAP)["rows"]} - (set() if HELP_TEXT else excluded)
    for r in read_json(base.MAP)["rows"]:
        name = " > ".join(r["path"])
        if r["kind"] not in KINDS or (r["kind"] != "sidelist" and name not in allowed) or \
                (r["kind"] != "sidelist" and scope_names and name not in scope_names):
            continue
        if safety.path_refused(r["path"], approved, ALLOWED):
            continue
        if r["kind"] == "fields":
            out[name] = iso_range_job(r) if name in COUPLED else fields_job(r)
            continue
        if r["kind"] == "checklist":
            later = name.startswith(CHECK_LATER) and not (scope_names and name in scope_names)
            if name in allowed and not later and (not scope_names or name in scope_names) and \
                    not safety.path_refused(r["path"], approved, ALLOWED):
                out[name] = check_job(r)
            continue
        if r["kind"] == "sidelist":
            if r["path"][:2] == ["Picture Profile", "option 1"]:
                for pp in PPS:                   # every profile has the same panel: pass 1 walked PP1's
                    path = ["Picture Profile", pp] + r["path"][2:]
                    as_pp1 = " > ".join(["Picture Profile", PP] + r["path"][2:])
                    if as_pp1 in allowed and (not scope_names or " > ".join(path) in scope_names):
                        out[" > ".join(path)] = side_job(r, path)
            continue
        by_index = {}
        for o in r["options"]:                 # the lap visited some rows twice: one label per index
            by_index.setdefault(o["index"], o["label"])
        labels = [by_index[i] for i in sorted(by_index)]
        if name in ICON_ROWS:
            by_o = {}
            for o in r["options"]:
                by_o.setdefault(o["index"], o["frame"])
            labels = ICON_ROWS[name]
            if len(labels) != len(by_o):
                print(f"skipping {name}: pass 1 saw {len(by_o)} options, expected {len(labels)}")
                continue
            out[name] = {"path": r["path"], "labels": labels, "kind": r["kind"],
                         "icon_frames": [by_o[i] for i in sorted(by_o)]}
            continue
        if name in LABELS:
            if len(LABELS[name]) == len(labels):
                labels = LABELS[name]
            elif base.MAP == base.PASS1 / "map_all.json":
                print(f"skipping {name}: pass 1 saw {len(labels)} options, the known sequence has {len(LABELS[name])}")
                continue
            # another mode's own map (Movie: ISO 100-32000, Picture Profile with User LUT slots,
            # 2026-10-30): its own reading stands, every label must be one of the known ones or new
            else:
                print(f"{name}: this map's {len(labels)} options, not the known {len(LABELS[name])}", flush=True)
        if any("★" in l for l in labels) and r["kind"] != "list":
            continue                           # star ratings outside list popups: not counted yet
        if len({option_key(l) for l in labels}) != len(labels):
            print(f"skipping {name}: two options read the same ({labels})", flush=True)
            continue
        out[name] = {"path": r["path"], "labels": labels, "kind": r["kind"],
                     **({"eyes": "osd"} if name in OSD_ONLY else {})}
    return list(out.values())


def sample_steps(seq: list, parse=None) -> list:
    """Steps to prove in one number field's Up-ordered values: the lowest, middle and highest when
    every value is a number (the rest are inferred if the record turns out linear in the value);
    every step when any value is text or there are only a few. One value pass 1 could not read
    (Shooting Start Time's "51") does not stop the sampling."""
    nums = [(parse or number)(v) for v in seq]
    known = {n for n in nums if n is not None}
    if any(n is None and v.strip() for n, v in zip(nums, seq, strict=True)) or nums.count(None) > 1 or len(known) <= 3:
        return list(range(len(seq)))
    ranked = sorted(known)
    picks = [ranked[0], ranked[len(ranked) // 2], ranked[-1]]
    return sorted({nums.index(p) for p in picks})


EVERY_MAX = 64          # --every proves a number scale in full up to this many values (a count of shots runs to 9999)


def every_value(todo: list) -> list:
    """--every: side lists and number fields proved at every value instead of the lowest, middle and highest, where
    the scale has EVERY_MAX values or fewer. The three samples and the straight line through them stand for the
    values between (pass2_report's "linear"); proving a few scales in full checks that the line holds at every step
    of its family of encodings, with the sampling kept for the rest (2026-11-06)."""
    for j in todo:
        if j["kind"] == "sidelist" and len(j["values"]) <= EVERY_MAX:
            j["plan"] = list(range(len(j["values"])))
        elif j["kind"] == "fields":
            for f in j["fields"]:
                if len(f["values"]) <= EVERY_MAX:
                    f["plan"] = list(range(len(f["values"])))
    return todo


def fields_job(r) -> dict:
    """Number fields: per field (in the order pass 1 walked them, Right from the field the screen
    opens on), its values in Up order; step 0 is the value pass 1 opened on. Labels list every field."""
    walks = {}
    for o in r["options"]:
        k, step = o["index"]
        walks.setdefault(k, {}).setdefault(step, (o["label"], o["frame"]))
    fields = []
    for k in sorted(walks):
        steps = [walks[k][s][0] for s in sorted(walks[k])]
        seq = [(lab.split(" | ") + [""] * (k + 1))[k].strip() for lab in steps]
        fields.append({"labels": steps, "values": seq, "plan": sample_steps(seq), "map_path": r["path"],
                       "frames": [walks[k][s][1] for s in sorted(walks[k])]})
    return {"path": r["path"], "kind": "fields", "fields": fields}


def iso_range_job(r) -> dict:
    """ISO Range Limit: Minimum and Maximum, each the 34 ISO steps 50 ... 102400. Down raises the ISO,
    Up lowers it, and the fields stop at the ends (pass 1 walked them as one lap, backwards). A field
    pushed past the other moves it too: the final check of each field shows that as a change."""
    values = LABELS["ISO"][1:]
    return {"path": r["path"], "kind": "fields", "wrap": False, "inc": "down",
            "fields": [{"labels": values, "values": values, "plan": sample_steps(values)} for _ in range(2)]}


def planned(job) -> set:
    """The proof indices a row is done with (a number field ends on the value it opened on, step 0)."""
    if job["kind"] == "fields":
        return {(k, s) for k, f in enumerate(job["fields"]) for s in set(f["plan"]) | {0}}
    if job["kind"] == "sidelist":
        return set(job["plan"])
    if job["kind"] == "lookbase":
        return set(range(len(LOOK_CODES)))
    if job["kind"] == "axis":
        return set(range(len(job["values"])))
    if job["kind"] == "look":
        return {(job["look"], p, "back") for p in LOOK_PARAMS}
    if job["kind"] == "wbgrid":
        return ({(job["preset"], axis, "back") for axis in WB_AXES} if not job.get("only_corners") else set()) | \
            ({(job["preset"], "corner", "back")} if job.get("corners") else set())
    if job["kind"] == "checklist":
        return set(range(len(job["labels"]) + 1))            # each box, then the visit that restores the last
    if job["kind"] == "table":                               # functions with screens of their own MENU does not
        return {k for k in range(len(job["labels"])) if table_planned(job, k)}      # leave are passed over
    return set(range(len(job["labels"])))


def side_job(r, path) -> dict:
    """A PP side list: one lap of its values in Down order (the walk visited it twice), with pass 1's
    frame for each; numeric laps are rebuilt from their cycle (fix_lap)."""
    by = {}
    for o in r["options"]:
        by.setdefault(o["index"], (o["label"], o["frame"]))
    idx = sorted(by)
    read, frames = [by[i][0] for i in idx], [by[i][1] for i in idx]
    labels = fix_lap(read)
    fixed = [(a_, b_) for a_, b_ in zip(read, labels, strict=True) if a_ != b_]
    if fixed:
        print(f"{' > '.join(path)}: read {fixed} (OCR), the cycle says otherwise", flush=True)
    return {"path": path, "kind": "sidelist", "values": labels, "frames": frames, "map_path": r["path"],
            "plan": sample_steps(labels, parse=signed)}


def check_job(r) -> dict:
    """A checklist: its box labels in Down order (the walk's last stop is the OK/Cancel buttons)."""
    by = {}
    for o in r["options"]:
        by.setdefault(o["index"], o)
    opts = [by[i] for i in sorted(by)]
    stars = any(re.search(r"★|\*|\bstars?\b", o["label"], re.I) for o in opts)
    labels = [(star_label(r["path"], o["frame"]) if stars else None) or o["label"] for o in opts]
    labels = [l for l in labels if not re.fullmatch(r"\s*(ok|cancel|ok cancel|enter)\s*", l, re.I)]
    return {"path": r["path"], "kind": "checklist", "labels": labels}


def axis_jobs(scope_names=None) -> list:
    """One job per carousel option with a second axis (kit/axis_walk.py found its values, in Right
    order from the one held then): {"path": [row], "kind": "axis", "option", "values"}."""
    if not base.AXES.exists():
        return []
    out = []
    for row, opts in read_json(base.AXES).items():
        for opt, info in opts.items():
            if len(info["values"]) < 2 or (scope_names and f"{row} / {opt}" not in scope_names and row not in scope_names):
                continue
            out.append({"path": [row], "kind": "axis", "option": opt, "values": info["values"]})
    return out


def job_key(j) -> str:
    return " > ".join(j["path"]) + (f" / {j['option']}" if j["kind"] in ("axis", "look", "lookbase", "wbgrid", "table") else "")


def proof_key(r) -> str:
    return " > ".join(r["path"]) + (f" / {r['option']}" if r.get("kind") in ("axis", "look", "lookbase", "wbgrid", "table") else "")


def look_jobs(scope_names=None) -> list:
    """Creative Look's parameter panel, one job per look (18: twelve looks, six custom slots)."""
    base = next((j for j in jobs({"Creative Look"}) if j["path"] == ["Creative Look"]), None)
    if base is None or (scope_names and "Creative Look panels" not in scope_names):
        return []
    return [{**base, "kind": "look", "look": i, "option": f"panel {i}"} for i in range(len(base["labels"]))]


def look_base_jobs() -> list:
    """The six custom slots' base look (their panel's first cell; 2026-10-30): one job per slot."""
    return [{**j, "kind": "lookbase", "option": f"base {j['look']}"}
            for j in look_jobs({"Creative Look panels"}) if j["look"] >= 12]


def wb_jobs(scope_names=None) -> list:
    """White Balance's fine-tune grid, one job per preset (C.Temp./Filter's grid is behind its colour
    temperature, 2026-10-30)."""
    base = next((j for j in jobs({"White Balance"}) if j["path"] == ["White Balance"]), None)
    if base is None:
        return []
    return [{**base, "kind": "wbgrid", "preset": i, "option": f"grid {i}"} for i, lab in enumerate(base["labels"])]
