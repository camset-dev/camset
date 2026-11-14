"""Write a camera's menu tree, private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json, from pass 1: the page
scan's page model and the crawls' walks (its shape: schemas/menu-tree.schema.json).

    .venv/bin/python kit/tools/menu_tree.py --dry-run                    # say what it would write, write nothing
    .venv/bin/python kit/tools/menu_tree.py [--scan kit2_page_scan] [--crawl kit2_crawl ...] [--replace]
    .venv/bin/python kit/tools/menu_tree.py --mode Movie --scan kit2_page_scan_movie [--crawl kit2_crawl_movie] [--replace]

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
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, datafiles, definitions, jsonl, paths, safety  # noqa: E402

SCHEMA = ROOT / "schemas" / "menu-tree.schema.json"


def counter(page: str) -> tuple:
    """A page's place: its counter's number ("5/65" is 5), pages with no counter last, in the scan's order."""
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", page or "")
    return (0, int(m.group(1))) if m else (1, 0)


def crawl_rows(crawl: Path) -> dict:
    """{(page counter, slot): the crawl's summary of that top-level row}: the last line of each wins (a crawl
    resumed walks a row again)."""
    return {(r.get("page"), r.get("slot")): r for r in jsonl.read(crawl / "rows.jsonl")}


def crawl_map(crawl: Path) -> dict:
    """{path tuple: the map's row} from the crawl's map.json (kit/pass1_map.py), when there is one."""
    f = crawl / "map.json"
    if not f.exists():
        return {}
    return {tuple(r["path"]): r for r in json.loads(f.read_text(encoding="utf-8"))["rows"]}


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


def row_of(label: str, summary: dict | None, path: tuple, maps: dict, greyed: bool = False, never: str = None) -> dict:
    """One row of the tree, with its children when the crawl walked a submenu."""
    if summary is None:
        state, why = (("never", never) if never else ("greyed", "") if greyed else ("seen", "not walked"))
        return {"label": label, "state": state, "why": why or "", "kind": ""}
    state, why = state_of(summary, greyed)
    kind = summary.get("kind") or ""
    out = {"label": label, "state": state, "why": why, "kind": "notice" if is_notice(summary.get("outcome") or "") else kind}
    m = maps.get(path)
    if m and kind == "fields":
        out["fields"] = fields_of(m)
    elif m:
        opts = labels_of(m)
        if opts:
            out["options"] = carousel_names(opts) if kind == "dialog" else opts
    subs = summary.get("submenu") or []
    if subs:
        out["kind"] = "submenu"
        out["children"] = [row_of(s.get("label") or "", s, path + (s.get("label") or "",), maps) for s in subs]
    return out


def tree(scan: Path, crawls: list, key: str, mode: str = None) -> dict:
    """The menu tree of camera `key` from the scan's model.json and the crawls' rows and maps; with `mode`, that
    shooting mode's menu, the entry of the file's "modes"."""
    model = json.loads((scan / "model.json").read_text(encoding="utf-8"))
    visited, maps = {}, {}
    for c in crawls:                               # a later crawl adds what an earlier one did not reach
        for k, v in crawl_rows(c).items():
            visited.setdefault(k, v)
        for k, v in crawl_map(c).items():
            maps.setdefault(k, v)
    tabs = collections.OrderedDict()
    for page in sorted(model, key=lambda p: counter(p.get("page"))):
        crumb = [x.strip() for x in (page.get("breadcrumb") or "").split(">") if x.strip()]
        if not crumb:
            continue
        rows = []
        for r in page.get("rows") or []:
            label = (r.get("label") or "").strip()
            if not label:
                continue
            seen = visited.get((page.get("page"), r.get("slot")))
            rows.append(row_of(label, seen, (label,), maps, greyed=bool(r.get("greyed")),
                               never=r.get("never_open") or safety.never_open(label)))
        tabs.setdefault(crumb[0], []).append({"page": page.get("page") or "", "group": " > ".join(crumb[1:]),
                                             "rows": rows})
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
                         "and crawls, leaving the Stills menu as it is")
    ap.add_argument("--out", default=None,
                    help="the file to write (default: private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written; write nothing")
    ap.add_argument("--replace", action="store_true", help="replace an existing menu tree")
    ap.add_argument("--carousel-names", action="store_true",
                    help="name the existing tree's carousel options by their own names (carousel_names), nothing else")
    a = ap.parse_args(argv)
    root = paths.run_root()
    key = root.name
    if not a.dry_run:
        datafiles.stop_if_left(key, "menu_tree.py")          # a tree still in data/ is moved first, never written past
    default = definitions.menu_tree_file(key)
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
