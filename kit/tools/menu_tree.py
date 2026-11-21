"""Write a camera's menu tree, private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json, from pass 1: the page
scan's page model and the crawls' walks (its shape: schemas/menu-tree.schema.json).

    .venv/bin/python kit/tools/menu_tree.py --dry-run                    # say what it would write, write nothing
    .venv/bin/python kit/tools/menu_tree.py [--scan kit2_page_scan] [--crawl kit2_crawl ...] [--replace]
    .venv/bin/python kit/tools/menu_tree.py --mode Movie --scan kit2_page_scan_movie [--crawl kit2_crawl_movie] [--replace]
    .venv/bin/python kit/tools/menu_tree.py --fold kit2_fin_crawl_brk [--fold ...] [--mode Movie] [--dry-run]
    .venv/bin/python kit/tools/menu_tree.py --add "My Menu > My Menu Setting" --scan kit2_page_scan_1118p [--dry-run]

The tree is the mapper's own, private whole (camkit.datafiles, docs/decisions/0016): which rows the walk found greyed
or could not read, which option lists it read and where each began are the state the camera stood in, so it is never
submitted. kit/schema_update.py places each setting on its rows, and the definition's menu list and places are what
is public of the menus.

Runs named here are in the camera's runs/<model>_fw<fw>/ (camkit.paths), and the camera's key names the file. From
the scan's model.json (kit/page_model.py): every page of the menus in the order of its counter ("5/65"), its tab and
group from its breadcrumb, and each row's label as the readers settled it. From each crawl's rows.jsonl
(kit/crawl_run.py): what the walk found at that row (walked, submenu with its rows, never opened and why, greyed or
an information notice, unhandled), its screen kind; from its map.json (kit/pass1_map.py): the option labels in their
order, and a number field's count, first and last value. A row no crawl reached is "never" when the never-open list
names it, "greyed" when the scan saw it greyed, else "seen". No value the camera held is written (decision 16): only
the menus' own names, a carousel's options too (carousel_names: the walk reads an option with a second axis as it
shows the sub-choice it was left on, the camera's own setting, "Spot: S" for a Spot left on S). An existing
file is replaced only with --replace (the a1 II's Stills menu was made by hand); --carousel-names names an existing tree's
carousel options by that rule and changes nothing else.

The file's "tabs" are the Stills menu. --mode NAME writes the menu of another shooting mode (Movie, S&Q: the name as
the camera's Still/Movie/S&Q switch says it, and as the proofs' contexts say it, "[Movie mode]") from that mode's page
scan and crawls into the file's "modes", beside the Stills menu, which it leaves as it is; a mode already there is
replaced only with --replace, and replacing the Stills menu keeps the modes. A scan alone gives each page's top rows
("seen", their rows unknown); kit/camkit/placement.py then takes the rows under them from the proofs' own paths.

--add "TAB > GROUP" --scan SCAN takes one group's pages from a page scan into the existing tree's menu (the Stills
menu, or --mode's) where that menu has none of them, changing nothing else: its rows as tree() writes a page the crawls
never reached (seen, greyed, or never), the group placed in the scan's order among the menu's pages, a tab the menu
lacks among its tabs where the scan has it (My Menu's own setting page, "My Menu > My Menu Setting", into a Stills menu
written by hand before My Menu was read). A group named as its tab and a number ("My Menu > My Menu1") is a page of
the owner's own items, and is refused (docs/decisions/0016).

--fold CRAWL takes a later crawl's walk into the existing tree (the Stills menu, or --mode's), changing nothing else
(fold): each top row the crawl walked is found in the tree by its label, never by its page counter, which moves with
the camera's state ("38/63" in one state is "40/65" in another), and only where one top row bears it. What the walk read
fills what the tree did not know, and never moves a row the tree holds: a row the tree held greyed, seen or unread
takes the crawl's walk (Bracket Type's options, walked with the drive mode dial on BRK), a row with no rows under it
takes the crawl's rows whole (Playback's Aspect Marker Disp.: Aspect Marker Disp., then Aspect Marker Level), and a row
the tree had walked keeps what it read. Under a row the tree knows the rows of, a crawl row is matched by its label
where one row bears it; where a label repeats under the row (the stills and the movie Recording Media rows, which the
walk reads alike), its rows are folded only when the crawl and the tree hold the same number of them in the same slots,
and never take options from the crawl's map, which keeps one row per path (the last one walked); a row the tree lacks
is added only after the tree's last row, at its own slot; anything else is left as it is. Each row it changes or
leaves is said (folded_rows).

Every label, the scan's, a crawl's and the tree's own on --fold, is the one the camera draws where the records name the
row otherwise (camkit.row_names: ROW_NAMES in the camera's hand tables), so an older name and the camera's are one row.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, datafiles, definitions, jsonl, paths, placement, row_names, safety  # noqa: E402

SCHEMA = ROOT / "schemas" / "menu-tree.schema.json"


def counter(page: str) -> tuple:
    """A page's place: its counter's number ("5/65" is 5), pages with no counter last, in the scan's order."""
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", page or "")
    return (0, int(m.group(1))) if m else (1, 0)


def crawl_rows(crawl: Path) -> dict:
    """{(page counter, slot): the crawl's summary of that top-level row}: the last line of each wins (a crawl
    resumed walks a row again). Each row's label as the camera draws it (camed)."""
    return {(r.get("page"), r.get("slot")): camed(r) for r in jsonl.read(crawl / "rows.jsonl")}


def crawl_readings(crawl: Path) -> dict:
    """{path tuple: {an option's label: every reading of it}} from the crawl's options.jsonl (kit/crawl_run.py, read by
    kit/pass1_labels.py: the label agreed, OCR's, the vision reader's "selected"), each path as the camera draws it
    (camkit.row_names); none without that file."""
    out = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in jsonl.read(crawl / "options.jsonl", bad="skip") if (crawl / "options.jsonl").exists() else []:
        path, label = r.get("path"), r.get("label")
        if not isinstance(path, list) or not isinstance(label, str) or not label.strip():
            continue
        vlm = r.get("vlm") if isinstance(r.get("vlm"), dict) else {}
        out[row_names.renamed(path)][label] |= {x for x in (label, r.get("ocr"), vlm.get("selected")) if isinstance(x, str) and x.strip()}
    return out


def drawn_options(opts: list, readings: dict) -> dict:
    """{option: its label as the camera draws it} for the options whose leading token (at most row_names.ICON_LEAD
    characters) another reading of the same option left out (`readings`: crawl_readings' for the row): the evidence
    that the token is an icon's letters ("W Rating", which the vision reader read "Rating"); none on length alone.
    A glyph the camera draws before an option is caught the same way ("› On" under S&Q's Peaking Display, "/ Histogram"
    on the Monitor list): harmless, since placement.option_names only reads it where no option names a label exactly,
    and a glyph is no part of a label either."""
    out = {}
    for o in opts:
        token, _, rest = o.partition(" ")
        if rest and 0 < len(token) <= row_names.ICON_LEAD and any(placement.norm(x) == placement.norm(rest)
                                                                    for x in readings.get(o, ())):
            out[o] = rest
    return out


def crawl_map(crawl: Path) -> dict:
    """{path tuple: the map's row} from the crawl's map.json (kit/pass1_map.py), when there is one, each path as the
    camera draws it (camkit.row_names)."""
    f = crawl / "map.json"
    if not f.exists():
        return {}
    return {row_names.renamed(r["path"]): r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}


def camed(row: dict, parent: tuple = ()) -> dict:
    """A crawl's row summary with its label, and its rows' under it, as the camera draws them where the crawl wrote an
    older name (camkit.row_names: ROW_NAMES in the camera's hand tables), each renamed under the path the crawl wrote."""
    label = row.get("label")
    here = (*parent, label or "")
    out = {**row, "label": row_names.renamed(here)[-1]} if label else dict(row)
    if isinstance(row.get("submenu"), list):
        out["submenu"] = [camed(s, here) if isinstance(s, dict) else s for s in row["submenu"]]
    return out


def camed_rows(rows: list, parent: tuple = ()) -> None:
    """A tree's rows (in place), each label as the camera draws it where the tree was written with an older one
    (camed's rule)."""
    for r in rows:
        here = (*parent, r.get("label") or "")
        if r.get("label"):
            r["label"] = row_names.renamed(here)[-1]
        camed_rows(r.get("children") or [], here)


def carousel_names(options: list) -> list:
    """A carousel's options by their own names, never by the sub-choice an option showed while the walk read it: the
    sub-choice is what that option was left on, the camera's own setting (docs/decisions/0016). "Spot: S" is "Spot",
    "Tracking: Wide" "Tracking", "Continuous Shooting: Mid" "Continuous Shooting" (made-up examples): a label "Name:
    choice" whose name no other option of the carousel has. Options that share a name are options of their own and stay whole ("Fluor.:
    Warm White", "Fluor.: Cool White"). An option whose sub-choices are numbered slots shows one of them alone ("Custom
    2" of Focus Area's Custom 1-3): a label "Name N", N one digit, whose name no other option has is "Name" (White
    Balance's Custom 1-3, three options, stay; "ISO 100" is no slot). The a1 II's tree carried such sub-choices until 2026-11-09; a test reads every tree for them."""
    def head(label):
        m = re.fullmatch(r"(.+?):\s+\S.*", label)
        return m[1].strip() if m else None

    def stem(label):
        m = re.fullmatch(r"(.*[A-Za-z])\s*[1-9]", label)          # a numbered slot, one digit ("Custom 2")
        return m[1].strip() if m else None
    heads = collections.Counter(h for o in options if (h := head(o)))
    stems = collections.Counter(st for o in options if (st := stem(o)))
    out = []
    for o in options:
        h, st = head(o), stem(o)
        out.append(h if h and heads[h] == 1 else st if not h and st and stems[st] == 1 else o)
    return out


NAMED = "a carousel's options by their own names, not by the sub-choice each was left on"     # the sources say so


def held_choices(doc: dict) -> list:
    """[(mode, row, option)] of every carousel option in a menu tree `doc` (its Stills menu and each mode's) that is
    named by a sub-choice (carousel_names would name it otherwise): what must never be in a published tree."""
    out = []

    def walk(rows, mode):
        for r in rows:
            if r.get("kind") == "dialog" and r.get("options"):
                out.extend((mode, r["label"], o) for o, n in zip(r["options"], carousel_names(r["options"]), strict=True)
                           if o != n)
            walk(r.get("children") or [], mode)
    for mode, tabs in [("Stills", doc.get("tabs") or [])] + [(m.get("mode"), m.get("tabs") or [])
                                                           for m in doc.get("modes") or []]:
        for t in tabs:
            for pg in t.get("pages") or []:
                walk(pg.get("rows") or [], mode)
    return out


def named_by_rule(doc: dict) -> int:
    """Every carousel's options in a menu tree `doc` named by carousel_names, in place; how many it renamed."""
    n = 0

    def walk(rows):
        nonlocal n
        for r in rows:
            if r.get("kind") == "dialog" and r.get("options"):
                names = carousel_names(r["options"])
                n += sum(a != b for a, b in zip(r["options"], names, strict=True))
                r["options"] = names
            walk(r.get("children") or [])
    for tabs in [doc.get("tabs") or []] + [m.get("tabs") or [] for m in doc.get("modes") or []]:
        for t in tabs:
            for pg in t.get("pages") or []:
                walk(pg.get("rows") or [])
    return n


def labels_of(row: dict) -> list:
    """A list's option labels in their order, one per index (a lap can visit an option twice)."""
    by = {}
    for o in row.get("options") or []:
        if not isinstance(o.get("index"), list):
            by.setdefault(o["index"], o.get("label") or "")
    return [by[i] for i in sorted(by)]


def fields_of(row: dict) -> list:
    """A number-field screen's fields: each one's count, first and last value, as the walk read them."""
    by = collections.defaultdict(dict)
    for o in row.get("options") or []:
        at = o.get("index")
        if isinstance(at, list) and len(at) == 2:
            by[at[0]].setdefault(at[1], o.get("label") or "")
    out = []
    for f in sorted(by):
        vals = [by[f][i] for i in sorted(by[f])]
        out.append({"count": len(vals), "first": vals[0] if vals else "", "last": vals[-1] if vals else ""})
    return out


INFO_FIRST = "an information notice comes first"


def is_notice(outcome: str) -> bool:
    """A crawl outcome that is a notice the walk stopped at: "notice", or "notice (named, not passed: ...)" for one a run
    named with --info-ok and did not pass (kit/crawl_run.py)."""
    return outcome == "notice" or outcome.startswith("notice (")


def state_of(summary: dict, greyed: bool) -> tuple:
    """(state, why) of a row the crawl visited, in the schema's words. A row whose notice a run passed with --info-ok
    (its summary's "info_ok") keeps the mark that an information notice comes first, walked or not."""
    outcome = summary.get("outcome") or ""
    if outcome == "walked":
        state, why = "walked", ""
    elif outcome.startswith("skipped:"):
        return "never", outcome.split(":", 1)[1].strip()
    elif outcome.startswith("submenu"):
        state, why = "submenu", "" if outcome in ("submenu crawled",) else outcome
    elif is_notice(outcome):
        return ("greyed", "") if greyed else ("info", INFO_FIRST)
    else:
        state, why = "unhandled", outcome
    if summary.get("info_ok") and INFO_FIRST not in why:
        why = f"{INFO_FIRST}; {why}" if why else INFO_FIRST
    return state, why


def row_of(label: str, summary: dict | None, path: tuple, maps: dict, greyed: bool = False, never: str = None,
           readings: dict = None) -> dict:
    """One row of the tree, with its children when the crawl walked a submenu. A row the walk found a notice on, never
    opening it, takes no options or fields from the map, which keeps one row per label path: those are its twin's of
    one label (the S&Q menu's second Shoot Mode row beside the walked first). An option whose leading token another
    reading of it left out has its label as the camera draws it in "drawn_options" (drawn_options; `readings`:
    crawl_readings')."""
    if summary is None:
        state, why = (("never", never) if never else ("greyed", "") if greyed else ("seen", "not walked"))
        return {"label": label, "state": state, "why": why or "", "kind": ""}
    state, why = state_of(summary, greyed)
    kind = summary.get("kind") or ""
    out = {"label": label, "state": state, "why": why, "kind": "notice" if is_notice(summary.get("outcome") or "") else kind}
    m = None if is_notice(summary.get("outcome") or "") else maps.get(path)
    if m and kind == "fields":
        out["fields"] = fields_of(m)
    elif m:
        opts = labels_of(m)
        if opts:
            out["options"] = carousel_names(opts) if kind == "dialog" else opts
            drawn = drawn_options(out["options"], (readings or {}).get(path) or {})
            if drawn:
                out["drawn_options"] = drawn
    subs = summary.get("submenu") or []
    if subs:
        out["kind"] = "submenu"
        out["children"] = [row_of(s.get("label") or "", s, path + (s.get("label") or "",), maps, readings=readings)
                           for s in subs]
    return out


def page_rows(page: dict, visited: dict, maps: dict, readings: dict = None) -> list:
    """A scanned page's rows as the tree holds them: each label as the camera draws it (camkit.row_names), and what the
    crawls (`visited`, by page counter and slot; `maps`, by path) found there, else seen, greyed or never."""
    rows = []
    for r in page.get("rows") or []:
        label = (r.get("label") or "").strip()
        if not label:
            continue
        label = row_names.renamed((label,))[-1]          # as the camera draws it (camkit.row_names)
        seen = visited.get((page.get("page"), r.get("slot")))
        rows.append(row_of(label, seen, (label,), maps, greyed=bool(r.get("greyed")), readings=readings,
                           never=r.get("never_open") or safety.never_open(label)))
    return rows


def added(menu: dict, scan: Path, tab: str, group: str) -> list:
    """The pages of `tab` > `group` in the page scan's model taken into a menu of the tree (`menu`, changed in place):
    each page's rows as page_rows writes a page no crawl reached, the pages after the menu's last page of that tab that
    comes before them in the scan, or, for a tab the menu lacks, the tab before the first of the menu's tabs that comes
    after it in the scan (last when none does). Refused (SystemExit) where the menu holds that group already, the scan
    holds none of its pages, or the group is named as its tab and a number (a page of the owner's own items). What it
    did, one line each."""
    if placement.item_page(group, tab):
        sys.exit(f"{tab} > {group} is a page of the owner's own items (its tab's name and a number): never taken into a "
                 "tree (docs/decisions/0016)")
    if any(pg.get("group") == group for t in menu.get("tabs") or [] if t["tab"] == tab for pg in t.get("pages") or []):
        sys.exit(f"the menu holds {tab} > {group} already: --add takes in only a group it lacks")
    model = sorted(json.loads((scan / "model.json").read_text(encoding="utf-8")), key=lambda p: counter(p.get("page")))
    crumb = lambda p: [x.strip() for x in (p.get("breadcrumb") or "").split(">") if x.strip()]          # noqa: E731
    pages = [p for p in model if crumb(p)[:1] == [tab] and " > ".join(crumb(p)[1:]) == group]
    if not pages:
        sys.exit(f"{scan / 'model.json'} holds no page of {tab} > {group}")
    new = [{"page": p.get("page") or "", "group": group, "rows": page_rows(p, {}, {})} for p in pages]
    order = list(dict.fromkeys(crumb(p)[0] for p in model if crumb(p)))
    have = next((t for t in menu.get("tabs") or [] if t["tab"] == tab), None)
    if have is None:
        later = [i for i, t in enumerate(menu.get("tabs") or []) if t["tab"] in order and order.index(t["tab"]) > order.index(tab)]
        at = later[0] if later else len(menu.get("tabs") or [])
        menu.setdefault("tabs", []).insert(at, {"tab": tab, "pages": new})
        where = f"a tab of its own, before {menu['tabs'][at + 1]['tab']}" if at + 1 < len(menu["tabs"]) else "a tab of its own, last"
    else:
        groups = [crumb(p)[1:] and " > ".join(crumb(p)[1:]) for p in model if crumb(p)[:1] == [tab]]
        before = {g for g in groups[:groups.index(group)]}
        at = max([i + 1 for i, pg in enumerate(have["pages"]) if pg.get("group") in before], default=0)
        have["pages"][at:at] = new
        where = f"{tab}'s page {at + 1}"
    return [f"{tab} > {group}: {len(new)} pages, {sum(len(p['rows']) for p in new)} rows, as {where}"]


def tree(scan: Path, crawls: list, key: str, mode: str = None) -> dict:
    """The menu tree of camera `key` from the scan's model.json and the crawls' rows and maps; with `mode`, that
    shooting mode's menu, the entry of the file's "modes"."""
    model = json.loads((scan / "model.json").read_text(encoding="utf-8"))
    visited, maps, readings = {}, {}, {}
    for c in crawls:                               # a later crawl adds what an earlier one did not reach
        for k, v in crawl_rows(c).items():
            visited.setdefault(k, v)
        for k, v in crawl_map(c).items():
            maps.setdefault(k, v)
        for k, v in crawl_readings(c).items():
            readings.setdefault(k, v)
    tabs = collections.OrderedDict()
    for page in sorted(model, key=lambda p: counter(p.get("page"))):
        crumb = [x.strip() for x in (page.get("breadcrumb") or "").split(">") if x.strip()]
        if not crumb:
            continue
        tabs.setdefault(crumb[0], []).append({"page": page.get("page") or "", "group": " > ".join(crumb[1:]),
                                             "rows": page_rows(page, visited, maps, readings)})
    model_name, firmware = paths.split(key)
    names = ", ".join(c.name for c in crawls) or "none"
    source = (f"Written by kit/tools/menu_tree.py from the page scan {scan.name} (kit/page_model.py's page model) and "
              f"the crawls {names} (kit/crawl_run.py, kit/pass1_map.py){f', in {mode} mode' if mode else ''}. Labels "
              f"are as read on screen, {NAMED}; states and reasons are as the walk found them.")
    out = [{"tab": t, "pages": pages} for t, pages in tabs.items()]
    if mode:
        return {"mode": mode, "source": source, "tabs": out}
    return {"$schema": "../../schemas/menu-tree.schema.json", "model": model_name, "firmware": firmware,
            "source": source, "tabs": out}


def with_mode(doc: dict, menu: dict) -> dict:
    """The tree `doc` with the mode menu `menu` in its "modes", in place of one of that name (the others kept, in
    their order; a new one last), its Stills menu as it is."""
    modes = [m for m in doc.get("modes") or [] if m.get("mode") != menu["mode"]]
    at = next((i for i, m in enumerate(doc.get("modes") or []) if m.get("mode") == menu["mode"]), len(modes))
    return {**doc, "modes": modes[:at] + [menu] + modes[at:]}


def known(r: dict | None) -> int:
    """How much a row of the tree says of the camera: 3 a screen the walk read (walked), 2 a submenu with its rows,
    1 any other state the walk found (greyed, an information notice, never opened, unhandled, a submenu with no rows),
    0 a row only seen on its page, or none."""
    if not r:
        return 0
    if r.get("state") == "walked":
        return 3
    if r.get("children"):
        return 2
    return 0 if r.get("state") in ("seen", "", None) else 1


def unshared(r: dict) -> dict:
    """A crawl's row (row_of) with no options or fields on a row whose label another row beside it repeats, at every
    depth: the crawl's map keeps one row per path, the last walked, so it gives each of them that one's (two Recording
    Media rows, one list each, would both show the movie row's)."""
    kids = r.get("children") or []
    if not kids:
        return r
    seen = collections.Counter(placement.norm(c.get("label")) for c in kids)
    out = []
    for c in kids:
        c = unshared(c)
        if seen[placement.norm(c.get("label"))] > 1:
            c = {k: v for k, v in c.items() if k not in ("options", "fields")}
        out.append(c)
    return {**r, "children": out}


def folded(old: dict, new: dict, subs: list, path: tuple, said: list) -> dict:
    """A tree's row `old` with what a crawl's row `new` (row_of; `subs`, its rows' summaries in the crawl, for their
    slots) adds, each change said in `said` by its path: two submenus' rows merged (folded_rows), else the crawl's row
    where it says more of the camera (known) and the tree's row has no rows under it to lose, else the tree's row as it
    is."""
    if old.get("children") and new.get("children"):
        return {**old, "children": folded_rows(old["children"], new["children"], subs, path, said)}
    if known(new) > known(old) and not old.get("children"):
        new = unshared(new)
        said.append(f"{' > '.join(path)}: {old.get('state') or 'seen'} -> {new.get('state')}"
                    + (f" ({len(new['children'])} rows)" if new.get("children") else "")
                    + (f" ({len(new['options'])} options)" if new.get("options") else ""))
        return new
    return old


def folded_rows(old: list, new: list, subs: list, path: tuple, said: list) -> list:
    """The rows under one row, the tree's (`old`, each at its place, its slot) with a crawl's (`new`, parallel to
    `subs`, their summaries, which give each its slot), the tree's rows never moved:
      - a label one row bears in the crawl and at most one in the tree: folded into the tree's row of that label, or,
        where the tree has none, added only at its own slot just past the tree's last row (or into a tree row there
        whose label was never read); at a slot the tree holds another row at, left out and said;
      - a label repeated in the crawl or in the tree (the stills and the movie Recording Media rows): folded row for
        row only where both hold the same number of them in the same slots, each without options from the crawl's map
        (unshared); otherwise all of them left as they are, and said;
      - a crawl row with no label read is matched to nothing."""
    def slot(j, s):
        return s.get("slot") if isinstance(s.get("slot"), int) and not isinstance(s.get("slot"), bool) else j
    crawl, tree = collections.defaultdict(list), collections.defaultdict(list)
    for j, (r, s) in enumerate(zip(new, list(subs) + [{}] * (len(new) - len(subs)), strict=False)):
        if placement.norm(r.get("label")):
            crawl[placement.norm(r.get("label"))].append((slot(j, s), r, s))
    for i, r in enumerate(old):
        if placement.norm(r.get("label")):
            tree[placement.norm(r.get("label"))].append(i)
    out, added = list(old), []
    for k, rows in crawl.items():
        at, label = tree.get(k, []), rows[0][1]["label"]
        if len(rows) == 1 and len(at) <= 1:
            n, r, s = rows[0]
            if at:
                out[at[0]] = folded(old[at[0]], r, s.get("submenu") or [], path + (old[at[0]]["label"],), said)
            elif n < len(old) and not placement.norm(old[n].get("label")):
                out[n] = unshared(r)
                said.append(f"{' > '.join(path + (label,))}: into the unread row at slot {n} ({r.get('state')})")
            elif n < len(old):
                said.append(f"{' > '.join(path + (label,))}: left out, the tree holds {old[n]['label']!r} at its slot {n}")
            else:
                added.append((n, r))
        elif [n for n, _, _ in rows] == at:
            for (n, r, s), i in zip(rows, at, strict=True):
                bare = {f: v for f, v in r.items() if f not in ("options", "fields")}
                out[i] = folded(old[i], bare, s.get("submenu") or [], path + (f"{old[i]['label']} (slot {n})",), said)
        else:
            said.append(f"{' > '.join(path + (label,))}: {len(at)} rows of this label in the tree (slots "
                        f"{', '.join(map(str, at)) or 'none'}), {len(rows)} in the crawl (slots "
                        f"{', '.join(str(n) for n, _, _ in rows)}); left as they are")
    for n, r in sorted(added, key=lambda x: x[0]):
        if n == len(out):
            out.append(unshared(r))
            said.append(f"{' > '.join(path + (r['label'],))}: added at slot {n} ({r.get('state')})")
        else:
            said.append(f"{' > '.join(path + (r['label'],))}: left out, its slot {n} is past the tree's rows with a gap")
    return out


def fold(menu: dict, crawl: Path) -> list:
    """A crawl's walk (its rows.jsonl and map.json) folded into a menu of the tree (`menu`: the Stills menu or a mode's
    entry, changed in place): each top row the crawl walked found by its label among the menu's top rows, wherever
    its page, never by the crawl's page counter, and folded there (folded). What it did, one line each: a row changed
    or added, and a top row the menu holds none or several of, left out."""
    maps, readings, said = crawl_map(crawl), crawl_readings(crawl), []
    for t in menu.get("tabs") or []:                # the tree's older names as the camera draws them (camkit.row_names)
        for pg in t.get("pages") or []:
            camed_rows(pg.get("rows") or [])
    tops = [(pg, i) for t in menu.get("tabs") or [] for pg in t.get("pages") or [] for i in range(len(pg.get("rows") or []))]
    for summary in crawl_rows(crawl).values():
        label = (summary.get("label") or "").strip()
        hits = [(pg, i) for pg, i in tops if label and placement.norm(pg["rows"][i]["label"]) == placement.norm(label)]
        if len(hits) != 1:
            said.append(f"{label or '(no label read)'}: {'no top row' if not hits else f'{len(hits)} top rows'} of "
                        "that label in the menu; not folded")
            continue
        pg, i = hits[0]
        pg["rows"][i] = folded(pg["rows"][i], row_of(label, summary, (label,), maps, readings=readings), summary.get("submenu") or [],
                               (pg["rows"][i]["label"],), said)
    return said


def counts(doc: dict) -> collections.Counter:
    """How many rows the walk found in each state, in the menu `doc` (a tree's Stills menu, or a mode's entry)."""
    c = collections.Counter()

    def walk(rows):
        for r in rows:
            c[r.get("state")] += 1
            walk(r.get("children") or [])
    for t in doc["tabs"]:
        for p in t["pages"]:
            walk(p["rows"])
    return c


def check(doc: dict) -> list:
    """What the JSON Schema finds wrong with the tree `doc` ([] when nothing, or when jsonschema is not installed)."""
    try:
        import jsonschema
    except ImportError:
        return []
    v = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in v.iter_errors(doc)]


def write(out: Path, doc: dict) -> None:
    """The tree `doc` into `out`, whole (datafiles.write_menu_tree)."""
    datafiles.write_menu_tree(out, doc)
    print(f"wrote {paths.shown(out) if out.resolve().is_relative_to(ROOT) else out}")


def fold_main(out: Path, crawls: list, mode: str | None, dry_run: bool) -> dict:
    """--fold: each crawl folded, in order, into the tree at `out` (its Stills menu, or `mode`'s), said row by row, the
    menu's source naming the crawls; written unless `dry_run`, and only when the JSON Schema finds nothing wrong."""
    if not out.exists():
        sys.exit(f"{out} is not there: --fold takes a crawl into an existing tree (write one first, without --fold)")
    doc = datafiles.load_menu_tree(out)
    menu = doc if not mode else next((m for m in doc.get("modes") or [] if m.get("mode") == mode.strip()), None)
    if menu is None:
        sys.exit(f"the tree holds no {mode} mode's menu: write it with --mode {mode} --scan ... first")
    for crawl in crawls:
        if not (crawl / "rows.jsonl").exists():
            sys.exit(f"{crawl / 'rows.jsonl'} is not there: --fold takes a crawl's walk (kit/crawl_run.py)")
        said = fold(menu, crawl)
        print(f"{crawl.name}{f' ({mode} mode)' if mode else ''}:" + ("" if said else " nothing to fold"))
        for line in said:
            print(f"  {line}")
        note = f"Rows folded in from the crawl {crawl.name} (menu_tree.py --fold)."
        if note not in menu.get("source", ""):
            menu["source"] = f"{menu.get('source', '').rstrip()} {note}".strip()
    wrong = check(doc)
    if wrong:
        sys.exit("the tree would not meet its schema:\n  " + "\n  ".join(wrong[:20]))
    if dry_run:
        print(f"would write {paths.shown(out) if out.resolve().is_relative_to(ROOT) else out} (--dry-run: nothing written)")
    else:
        write(out, doc)
    return doc


def add_main(out: Path, scan, spec: str, mode: str | None, dry_run: bool) -> dict:
    """--add: one group's pages from a page scan into the tree at `out` (its Stills menu, or `mode`'s), said, the
    menu's source naming the scan; written unless `dry_run`, and only when the JSON Schema finds nothing wrong."""
    if not out.exists():
        sys.exit(f"{out} is not there: --add takes a group into an existing tree")
    if not scan:
        sys.exit("--add needs the page scan that holds the group: --scan kit2_page_scan_<...>")
    tab, _, group = (x.strip() for x in spec.partition(" > "))
    if not tab or not group:
        sys.exit(f"--add {spec!r}: name the tab, then the group, \" > \" between (\"My Menu > My Menu Setting\")")
    scan = Path(scan)
    if not (scan / "model.json").exists():
        sys.exit(f"{scan / 'model.json'} is not there: run kit/page_model.py on the page scan first")
    doc = datafiles.load_menu_tree(out)
    menu = doc if not mode else next((m for m in doc.get("modes") or [] if m.get("mode") == mode.strip()), None)
    if menu is None:
        sys.exit(f"the tree holds no {mode} mode's menu: write it with --mode {mode} --scan ... first")
    for line in added(menu, scan, tab, group):
        print(f"  {line}")
    note = f"{tab} > {group} taken in from the page scan {scan.name} (menu_tree.py --add)."
    if note not in menu.get("source", ""):
        menu["source"] = f"{menu.get('source', '').rstrip()} {note}".strip()
    wrong = check(doc)
    if wrong:
        sys.exit("the tree would not meet its schema:\n  " + "\n  ".join(wrong[:20]))
    if dry_run:
        print(f"would write {paths.shown(out) if out.resolve().is_relative_to(ROOT) else out} (--dry-run: nothing written)")
    else:
        write(out, doc)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scan", default=None, type=paths.run_arg,
                    help="the page scan whose model.json names the pages (a run in the camera's runs, or a path; "
                         "default: kit2_page_scan, and none with --mode)")
    ap.add_argument("--crawl", action="append", type=paths.run_arg,
                    help="a crawl (rows.jsonl, map.json); more than one adds what the first did not reach "
                         "(default: kit2_crawl when it is there, and none with --mode)")
    ap.add_argument("--mode", default=None,
                    help="write this shooting mode's menu (Movie, S&Q) into the tree's \"modes\", from its own scan "
                         "and crawls, leaving the Stills menu as it is; the name as the camera file's live_mode names "
                         "the mode, which the camera's MENUS table names too")
    ap.add_argument("--out", default=None,
                    help="the file to write (default: private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written; write nothing")
    ap.add_argument("--replace", action="store_true", help="replace an existing menu tree")
    ap.add_argument("--carousel-names", action="store_true",
                    help="name the existing tree's carousel options by their own names (carousel_names), nothing else")
    ap.add_argument("--add", default=None, metavar="TAB > GROUP",
                    help="take that group's pages from --scan into the existing tree's menu (the Stills menu, or "
                         "--mode's), where it has none of them (added)")
    ap.add_argument("--fold", action="append", type=paths.run_arg,
                    help="take a later crawl's walk into the existing tree, its rows found by label (fold); more than "
                         "one, in order; with --mode, into that mode's menu")
    a = ap.parse_args(argv)
    root = paths.run_root()
    key = root.name
    if not a.dry_run:
        datafiles.stop_if_left(key, "menu_tree.py")          # a tree still in data/ is moved first, never written past
    default = definitions.menu_tree_file(key)
    if a.fold:
        return fold_main(Path(a.out) if a.out else default, [Path(c) for c in a.fold], a.mode, a.dry_run)
    if a.add:
        return add_main(Path(a.out) if a.out else default, a.scan, a.add, a.mode, a.dry_run)
    if a.carousel_names:
        out = Path(a.out) if a.out else default
        doc = datafiles.load_menu_tree(out)
        held = held_choices(doc)
        for mode, row, o in held:
            print(f"  {mode}: {row}: {o!r}")
        n = named_by_rule(doc)
        for menu in [doc] + list(doc.get("modes") or []) if n else []:
            if NAMED not in menu.get("source", ""):
                menu["source"] = (f"{menu.get('source', '').rstrip('.')}. Since 2026-11-09 the labels are {NAMED} "
                                  "(menu_tree.py --carousel-names).")
        wrong = check(doc)
        if wrong:
            sys.exit("the tree does not meet its schema:\n  " + "\n  ".join(wrong[:20]))
        if a.dry_run or not n:
            print(f"{n} carousel options to name by their own names in {out}" + ("" if n else ": nothing to do"))
            return
        write(out, doc)
        print(f"named {n} carousel options by their own names in {out}")
        return
    if a.mode is not None and not (a.mode.strip() and a.scan):
        sys.exit("--mode needs the mode's name (Movie, S&Q) and its own page scan: --scan kit2_page_scan_<mode>")
    scan = Path(a.scan or paths.run_arg("kit2_page_scan"))
    if not (scan / "model.json").exists():
        sys.exit(f"{scan / 'model.json'} is not there: run kit/page_model.py on the page scan first")
    crawls = [Path(c) for c in a.crawl] if a.crawl else [c for c in [root / "kit2_crawl"] if c.exists() and not a.mode]
    out = Path(a.out) if a.out else default
    old = datafiles.load_menu_tree(out) if out.exists() else None
    menu = tree(scan, crawls, key, a.mode.strip() if a.mode else None)
    if a.mode:
        # the mode's menu beside the Stills menu, which stays as it is (none yet: an empty one, until the Stills scan's)
        model_name, firmware = paths.split(key)
        base = old or {"$schema": "../../schemas/menu-tree.schema.json", "model": model_name, "firmware": firmware,
                       "source": "No Stills menu written yet: kit/tools/menu_tree.py without --mode writes it.", "tabs": []}
        doc = with_mode(base, menu)
    else:
        doc = {**menu, "modes": old["modes"]} if old and old.get("modes") else menu
    wrong = check(doc)
    c = counts(menu)
    pages = sum(len(t["pages"]) for t in menu["tabs"])
    print(f"{key}{f' ({a.mode} mode)' if a.mode else ''}: {len(menu['tabs'])} tabs ({', '.join(t['tab'] for t in menu['tabs'])}), "
          f"{pages} pages, {sum(c.values())} rows: {dict(c)}")
    if wrong:
        print("the JSON Schema finds:\n  " + "\n  ".join(wrong[:20]))
        sys.exit(1)
    if a.dry_run:
        print(f"would write {paths.shown(out) if out.is_relative_to(ROOT) else out} (--dry-run: nothing written)")
        return doc
    there = old is not None and (not a.mode or any(m.get("mode") == menu["mode"] for m in old.get("modes") or []))
    if there and not a.replace:
        what = f"{a.mode} mode's menu is in {out} already" if a.mode else f"{out} is there already"
        sys.exit(f"{what}: --replace replaces it (an existing tree may have been corrected by hand)")
    write(out, doc)
    return doc


if __name__ == "__main__":
    main()
