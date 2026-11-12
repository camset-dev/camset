"""Where each setting sits on the camera's own menu: the row its proof went through, in the menus the kit walked
(private/evidence/<model>_fw<firmware>/menu_tree_<model>_fw<firmware>.json, the mapper's own). One placement for the two that need it: the proof
viewer (kit/tools/proof_viewer.py) hangs every record on its row with it, and kit/schema_update.py writes each
setting's place into the definition with it ("row", "row_at", "under_option", "row_tab", "row_group" and "row_mode":
docs/DATA_CONTRACTS.md), so the editor lays a group's rows out as the camera does without the tree.

A proof's menu path ("Bracket Settings > Focus Bracket Settings > Shooting Interval [Movie mode]") steps into a
row's submenu with " > ", names an option of the row with " / " (the setting is the choice the camera shows beside
that option: "Drive Mode / Continuous Shooting" is the continuous shooting speed), and ends with the proof's context
in brackets, which says nothing about the place except the shooting mode the proof was made in ("[Movie mode]").

The tree's top-level "tabs" are the Stills menu; its "modes" hold the menus of the camera's other shooting modes
(Movie, S&Q), each written by kit/tools/menu_tree.py --mode. A setting the Stills menu has no row for, proved in a
mode (its context names it) or, by a path with no context, on a row only a mode's menu has, hangs on that mode's row;
the rows of a tab are numbered over the Stills menu's top rows with each mode's own rows slotted in where that mode's
menu has them (merge_tops), so one number orders them all.
"""
import collections
import difflib
import re

from .match import LOOKALIKES


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def strict(s) -> str:
    """A label with its signs kept ("hi+(e-shutter)"), to tell apart labels norm() makes alike."""
    return re.sub(r"\s+", "", (s or "").lower())


def split(path: str) -> list:
    """A proof's menu path as its labels, the context in brackets left out."""
    path = re.sub(r"\s*\[[^\]]*\]", "", path)
    return [x.strip() for x in re.split(r" > | / | › ", path) if x.strip()]


def steps(path: str) -> list:
    """A proof's menu path as (how it is reached, label) pairs, as split() reads its labels: "" for the first, ">"
    for a step into a submenu (" > ", " › "), "/" for an option of the row before (" / ")."""
    path = re.sub(r"\s*\[[^\]]*\]", "", path)
    out, how = [], ""
    for x in re.split(r"( > | / | › )", path):
        if x in (" > ", " › "):
            how = ">"
        elif x == " / ":
            how = "/"
        elif x.strip():
            out.append((how if out else "", x.strip()))
    return out


def context(path: str) -> list:
    """The words of a path's context in brackets ("[Movie mode, Log Shooting On]"), one entry per comma."""
    return [w.strip() for m in re.findall(r"\[([^\]]*)\]", path or "") for w in m.split(",") if w.strip()]


def mode_of(path: str, modes) -> str | None:
    """The shooting mode of `modes` (the menu tree's mode names) a path's context names: "[Movie mode]" or "[movie]"
    is the mode "Movie"; None when it names none."""
    for w in context(path):
        for m in modes:
            if norm(w) and norm(w) in (norm(m), norm(m) + "mode"):
                return m
    return None


class Place:
    """Where a record sits in the camera's own menu (the schema's "menu": tab, group, row label, order): by the
    top-level row its proof went through, else by its group's name (kit/schema_update.py gives settings the
    camera's own group names since 2026-11-03; the cut breadcrumbs of older schemas, "Image Qua...", are still
    mended here). Records the menu does not
    list (Movie-only rows, SDK-only records, the memory mirrors) keep their schema group, after the camera's."""

    def __init__(self, doc):
        self.tabs = set(doc.get("tabs") or [])
        self.rows = collections.defaultdict(dict)        # tab -> row label (lower) -> menu entry
        self.groups = collections.defaultdict(list)      # tab -> groups in the camera's order
        self.display = {}                                # a group's name without the icon read as a letter
        for m in sorted(doc.get("menu") or [], key=lambda m: m["order"]):
            self.rows[m["tab"]].setdefault(m["label"].lower(), m)
            if m["group"] not in self.groups[m["tab"]]:
                self.groups[m["tab"]].append(m["group"])

    def segments(self, path: str, tab: str) -> list:
        segs = split(path)
        while segs and (segs[0] in self.tabs or segs[0] in self.groups.get(tab, ())):
            segs.pop(0)
        return segs

    def group_named(self, tab: str, name: str):
        if name in self.groups.get(tab, ()):
            return name
        cut = name.split(" › ")[0].split(" > ")[0]
        # a group icon read as a letter ("DCnct./Remote Sht." on the menu page, "Cnct./Remote Sht." in a breadcrumb)
        icon = [g for g in self.groups.get(tab, ()) if len(g) == len(cut) + 1 and g.endswith(cut)]
        if len(icon) == 1:
            self.display[icon[0]] = cut
            return icon[0]
        if cut.endswith("..."):
            hits = [g for g in self.groups.get(tab, ()) if g.startswith(cut[:-3])]
            if len(hits) == 1:
                return hits[0]
        return None

    def of(self, s) -> dict:
        tab, menu = s.get("tab") or "Other", (s.get("proved") or {}).get("menu") or []
        for path in [menu] if isinstance(menu, str) else menu:
            for seg in self.segments(path, tab)[:2]:
                m = self.rows[tab].get(seg.lower())
                if m:
                    return {"cg": m["group"], "cgi": self.groups[tab].index(m["group"]), "row": m["label"], "ro": m["order"]}
        g = self.group_named(tab, s.get("group") or "")
        sub = (s.get("group") or "").split(" › ")[1:] or (s.get("group") or "").split(" > ")[1:]
        if not sub:      # a submenu the proof went through ("Auto Framing Settings > Crop Level")
            segs = self.segments(menu if isinstance(menu, str) else (menu or [""])[0], tab)
            sub = segs[:1] if len(segs) > 1 else []
        if g:
            return {"cg": g, "cgi": self.groups[tab].index(g), "row": sub[0] if sub else "", "ro": 9999}
        return {"cg": s.get("group") or "", "cgi": None, "row": sub[0] if sub else "", "ro": 9999}


class Tree:
    """The camera's tabs, groups and rows (the menu tree), each group under the schema's name for it, and each row a
    node: {"id", "l" (its label), "st", "why", "opts", "walk", "kids", "recs", "subs"}, the shape the proof viewer
    draws. `walks` gives a row its pass 1 frames by its path (the viewer's; none here otherwise). `mode` names one of
    the tree's other shooting modes ("modes": Movie, S&Q) to read that mode's menu instead of the Stills menu."""

    def __init__(self, doc, tree, walks=None, mode=None):
        walks, n = walks or {}, [0]
        self.mode = mode
        self.place = Place(doc)
        self.named = {}         # (tab, the schema menu's group) -> the tree's group: one read off the page cut or with an icon
        self.where = {}         # a row's id -> ((its tab, its group, the tree's name for it), its labels from the top row down, its "row_at")
        self.tops = collections.defaultdict(list)          # tab -> its top rows' (label, group), in the menu's order
        self.tabs = []
        menus = tree["tabs"] if mode is None else next((m["tabs"] for m in tree.get("modes") or [] if m.get("mode") == mode), [])
        for tb in menus:
            groups, tops = [], 0
            for pg in tb["pages"]:
                g = next((x for x in groups if x["name"] == pg["group"]), None)
                if not g:
                    g = {"name": pg["group"], "num": len(groups) + 1, "rows": [], "extra": []}
                    groups.append(g)
                    cands = self.place.groups.get(tb["tab"], ())
                    # a group icon read as a letter in the tree's own breadcrumb ("0Cnct./Remote Sht.", a mode's scan)
                    lead = [c for c in cands if c != pg["group"] and norm(pg["group"])[1:] == norm(c)]
                    same = [c for c in cands if c == pg["group"]] or lead or \
                        [c for c in cands if norm(pg["group"]) in norm(c) or norm(c) in norm(pg["group"])][:1]
                    for c in same:          # the name itself, else the one schema name it is cut from
                        self.named[(tb["tab"], c)] = pg["group"]
                        icon = norm(c)[1:].startswith(norm(pg["group"])) and not norm(c).startswith(norm(pg["group"]))
                        g["name"] = c if c in lead else c[1:] if icon else (c if len(c) >= len(pg["group"]) else pg["group"])
                for r in pg["rows"]:
                    g["rows"].append(self._node(r, [], [tops], (tb["tab"], g, pg["group"]), walks, n))
                    self.tops[tb["tab"]].append((r["label"], g["name"]))
                    tops += 1
            self.tabs.append({"tab": tb["tab"], "groups": groups})
        self.by_tab = {t["tab"]: t for t in self.tabs}

    def _node(self, r, path, at, group, walks, n):
        n[0] += 1
        path = path + [r["label"]]
        out = {"id": f"{self.mode}:n{n[0]}" if self.mode else f"n{n[0]}", "l": r["label"], "st": r.get("state") or "", "why": r.get("why") or "",
               "opts": r.get("options") or [], "walk": walks.get(tuple(norm(x) for x in path), []),
               "kids": [self._node(c, path, at + [i], group, walks, n) for i, c in enumerate(r.get("children") or [])],
               "recs": [], "subs": []}
        self.where[out["id"]] = (group, path, at)
        return out

    @staticmethod
    def nodes(rows, depth=0):
        for x in rows:
            yield x, depth
            yield from Tree.nodes(x["kids"], depth + 1)

    def locate(self, tab, segs, near=None, anywhere=True) -> tuple:
        """(the deepest row whose labels follow segs from a top row, how many of segs lead to it); else, with
        `anywhere`, a row of that label (in near's group first), the camera's menus repeating some labels (Fixed Speed
        STBY, Tracking Shift Range); else (None, 0). Labels are compared by norm(); of sibling rows that norm() alike
        ("Hi+ (E-Shutter)" and "Hi (E-Shutter)"), the one written as the label read is taken."""
        t = self.by_tab.get(tab)
        if not t:
            return None, 0
        keys = [norm(x) for x in segs]

        def kid(rows, i):
            same = [k for k in rows if norm(k["l"]) == keys[i]]
            return next((k for k in same if strict(k["l"]) == strict(segs[i])), same[0] if same else None)

        best = None
        for g in t["groups"]:
            for top in g["rows"]:
                cur, i = top, 0
                if not segs or norm(top["l"]) != keys[0]:
                    continue
                i = 1
                while i < len(segs):
                    nxt = kid(cur["kids"], i)
                    if not nxt:
                        break
                    cur, i = nxt, i + 1
                if not best or i > best[1]:
                    best = (cur, i)
        if best or not anywhere:
            return best or (None, 0)
        for seg in keys[:1]:
            for g in sorted(t["groups"], key=lambda g: g["name"] != near):
                hits = [x for x, _ in self.nodes(g["rows"]) if norm(x["l"]) == seg]
                if hits:
                    return hits[0], 1
        return None, 0

    def find(self, tab, segs, near=None, anywhere=True):
        return self.locate(tab, segs, near, anywhere)[0]

    def segments(self, path, tab, whole=False) -> list:
        """A path's labels; the tab's and its groups' names it starts with left out, unless `whole` (a row named as
        its group: Drive Mode, White Balance)."""
        t = self.by_tab.get(tab) or {"groups": []}
        segs = split(path)
        names = {norm(tab)} | {norm(g["name"]) for g in t["groups"]}
        while segs and norm(segs[0]) in names and not whole:
            segs.pop(0)
        return segs

    def group_of(self, tab, name):
        """The tree's group shown under the schema group `name` (or its name without the icon read as a letter)."""
        t = self.by_tab.get(tab)
        if not t:
            return None
        gname = self.named.get((tab, name), name)
        return next((x for x in t["groups"] if x["name"] == gname or x["name"] == self.place.display.get(name, name)), None)

    def hang(self, tab, menus, near, name, by_name=True, anywhere=True) -> tuple:
        """Where a record hangs: (its row, None), by the first of its proof paths that leads to a row, else by its
        name in its camera group (`near`; not without `by_name`), else by a path that starts at a row named as its
        group; (None, its group) when its group is the camera's but no row is found; (None, None) when the tab or the
        group is not the camera's. A path is tried without the group's name first, as it was read before rows named
        as their group were placed (2026-11-06), so a record placed then stays where it was. Without `anywhere` a
        path must lead from a top row (locate), as one into another tab must."""
        t = self.by_tab.get(tab)
        if not t:
            return None, None
        for path in menus:
            segs = self.segments(path, tab)
            hit = self.find(tab, segs, near, anywhere) if segs else None
            if hit:
                return hit, None
        g = self.group_of(tab, near)
        if g and by_name:
            hit = next((x for x, _ in self.nodes(g["rows"]) if norm(x["l"]) == norm(name)), None)
            if hit:
                return hit, None
        for path in menus:
            segs = self.segments(path, tab, whole=True)
            if segs != self.segments(path, tab):
                hit = self.find(tab, segs, near, anywhere)
                if hit:
                    return hit, None
        return None, g

    # ---------------------------------------------------------------- a setting's place, for its definition

    def leads(self, tab, path, node, near=None) -> bool:
        """Whether a path leads to `node`, read with or without its group's name."""
        return any(self.locate(tab, self.segments(path, tab, whole), near)[0] is node for whole in (False, True))

    def leftover(self, tab, path, node, near=None) -> str | None:
        """The one label a path names past `node` ("Continuous Shooting" in "Drive Mode / Continuous Shooting"), as
        read, when the path leads to the node and names exactly one more; else None."""
        raw = split(path)
        for whole in (False, True):
            segs = self.segments(path, tab, whole)
            got, used = self.locate(tab, segs, near) if segs else (None, 0)
            if got is node and used == len(segs) - 1:
                return raw[-1]
        return None

    def beyond(self, tab, path, node, near=None) -> list:
        """The submenu steps a path takes past `node` (" > " steps, up to its first option, " / "), as read, when the
        path leads to the node: the rows under it the tree does not know."""
        st = steps(path)
        for whole in (False, True):
            segs = self.segments(path, tab, whole)
            got, used = self.locate(tab, segs, near) if segs else (None, 0)
            if got is node:
                rest = st[len(st) - len(segs) + used:]
                out = []
                for how, label in rest:
                    if how != ">":
                        break
                    out.append(label)
                return out
        return []

    def grow(self, node, labels) -> dict:
        """The row `labels` names under `node`, made from a proof's path where the tree does not know the rows under
        a row (a submenu the walk never opened, a mode's row read off its page scan alone): each made row comes
        after its siblings, so they keep the order the definition lists the settings proved through them."""
        group, path, at = self.where[node["id"]]
        for label in labels:
            kid = next((k for k in node["kids"] if norm(k["l"]) == norm(label)), None)
            if not kid:
                kid = {"id": f"{node['id']}.{len(node['kids'])}", "l": label, "st": "proof", "why": "", "opts": [],
                       "walk": [], "kids": [], "recs": [], "subs": [], "made": True}
                self.where[kid["id"]] = (group, path + [label], at + [len(node["kids"])])
                node["kids"].append(kid)
            node, (group, path, at) = kid, self.where[kid["id"]]
        return node


def mode_trees(doc, tree, walks=None) -> list:
    """[(mode, its Tree)] for each of the menu tree's other shooting modes ("modes": Movie, S&Q), in the tree's order;
    walks: {mode: a row's pass 1 frames by its path} (the proof viewer's; none otherwise)."""
    return [(m["mode"], Tree(doc, tree, (walks or {}).get(m["mode"]), mode=m["mode"]))
            for m in tree.get("modes") or [] if m.get("mode")]


def reach(t: "Tree", modes: list, paths: list, tab: str, near, name: str) -> tuple:
    """(the menu, the row) a setting hangs on, by its proof paths: the Stills menu's row (`t`; by the paths, else by
    its name in its camera group `near`), else a mode's (`modes`: [(name, Tree)]) by the paths its context says were
    proved in that mode, else, in a tab the Stills menu has, by a path with no context at all, on a row only a mode's
    menu has; else, the same way, a row in another tab of the menus (the row's tab is the setting's "row_tab"): the
    Stills menu's tabs in its order, then each mode's, by a path that leads there from a top row (the Custom Key cells
    on Setup's Custom Key/Dial Set. for a setting the definition keeps in Shooting); (None, None) when none leads to a
    row. kit/schema_update.py writes a setting's place by it (settings()) and the proof viewer hangs its records by
    it (grown())."""
    node, _ = t.hang(tab, paths, near, name)
    if node:
        return t, node
    said = [mode_of(p, [n for n, _ in modes]) for p in paths]
    for mode, m in modes:
        mine = [p for p, w in zip(paths, said, strict=True) if w == mode]
        if not mine and tab in t.by_tab:          # a path with no context at all, on a row only a mode's menu has
            mine = [p for p in paths if not context(p)]
        node = m.hang(tab, mine, near, "", by_name=False)[0] if mine else None
        if node:
            return m, node
    for other in [x for x in t.by_tab if x != tab]:          # a row in another tab: the Stills menu's first
        node = t.hang(other, paths, None, "", by_name=False, anywhere=False)[0]
        if node:
            return t, node
    for mode, m in modes:
        mine = [p for p, w in zip(paths, said, strict=True) if w == mode] or [p for p in paths if not context(p)]
        for other in [x for x in m.by_tab if x != tab and x in t.by_tab] if mine else []:
            node = m.hang(other, mine, None, "", by_name=False, anywhere=False)[0]
            if node:
                return m, node
    return None, None


def leaf_rows(menus: list) -> dict:
    """The rows whose rows under them the tree does not know, in each of `menus` (Trees) by id(): none listed, and
    not a screen the walk read (a list, a dialog, number fields), whose steps past it are its options ("Drive Mode >
    Self-timer(Cont.)"). Worked out before grown() makes any row."""
    return {id(m): {x["id"] for tb in m.tabs for g in tb["groups"] for x, _ in m.nodes(g["rows"])
                    if not x["kids"] and not x["opts"] and x["st"] != "walked"} for m in menus}


def grown(t: "Tree", modes: list, leaves: dict, paths: list, tab: str, near, name: str) -> tuple:
    """(the menu, the row) a setting hangs on (reach()), the row grown from its paths where the tree does not know
    the rows under the row they reach (`leaves`, leaf_rows(); a row made so grows on): the rest of the first such
    path's submenu steps are the rows (Tree.grow), in the order the settings come here. The definition's places
    (settings()) and the proof viewer's rows hang by it, so the two show the same rows."""
    m, node = reach(t, modes, paths, tab, near, name)
    if not node:
        return None, None
    rtab = m.where[node["id"]][0][0]
    if node["id"] in leaves[id(m)] or node.get("made"):
        more = next((m.beyond(rtab, p, node, near) for p in paths if m.leads(rtab, p, node, near)), [])
        node = m.grow(node, more) if more else node
    return m, node


def merge_tops(stills: "Tree", modes: list) -> dict:
    """Each tab's top rows numbered as one list: the Stills menu's in its order, and each mode's (`modes`: [(name,
    Tree)]) matched to them by label, its own rows slotted in where that mode's menu has them: between the rows both
    menus have around them, after the last Stills row of their own group there (before them all when their group is
    the one of the shared row before, after them all when no Stills row there is of it), in the mode's order.
    {(mode or None, tab, the row's place in its own menu): its number}."""
    out = {}
    for tab in list(stills.tops) + [t for _, m in modes for t in m.tops if t not in stills.tops]:
        line = [(None, i, norm(x), norm(g)) for i, (x, g) in enumerate(stills.tops.get(tab, []))]
        same = {}
        for name, m in modes:
            theirs = [(name, j, norm(x), norm(g)) for j, (x, g) in enumerate(m.tops.get(tab, []))]
            merged = []
            ops = difflib.SequenceMatcher(None, [x[2] for x in line], [y[2] for y in theirs], autojunk=False).get_opcodes()
            for op, i1, i2, j1, j2 in ops:
                if op == "equal":
                    merged += line[i1:i2]
                    for k in range(j2 - j1):
                        same[theirs[j1 + k][:2]] = line[i1 + k][:2]
                    continue
                gap, own = line[i1:i2], theirs[j1:j2]
                before = merged[-1][3] if merged else None
                after, at = [], -1          # each mode row: the gap's Stills row it follows (-1: none), never back
                for y in own:
                    last = max((k for k, x in enumerate(gap) if x[3] == y[3]), default=None)
                    at = max(at, last if last is not None else (-1 if y[3] == before else len(gap) - 1))
                    after.append(at)
                merged += [y for y, a in zip(own, after, strict=True) if a == -1]
                for k, x in enumerate(gap):
                    merged += [x] + [y for y, a in zip(own, after, strict=True) if a == k]
            line = merged
        at = {x[:2]: n for n, x in enumerate(line)}
        for x in line:
            out[(x[0], tab, x[1])] = at[x[:2]]
        for (name, j), stills_at in same.items():
            out[(name, tab, j)] = at[stills_at]
    return out


def option_label(said: str, values) -> str | None:
    """The option of `values` ([[value, label]]) a path names: the label read as it is, else the one whose label
    starts the words read or is started by them ("Self-timer(Single)" is the option "Self-timer")."""
    seg = norm(said.translate(LOOKALIKES))
    labels = [str(v[1]) for v in values or [] if isinstance(v, (list, tuple)) and len(v) > 1]
    same = [lab for lab in labels if norm(lab) == seg]
    if same or not seg:
        return same[0] if same else None
    near = [lab for lab in labels if norm(lab) and (seg.startswith(norm(lab)) or norm(lab).startswith(seg))]
    near = [lab for lab in near if len(norm(lab)) == max(len(norm(x)) for x in near)]
    return near[0] if len(set(near)) == 1 else None


# an option a proof names by its place in the row's list, as the provers that open a row's options with Right do: the
# White Balance grid ("White Balance / grid 11": C.Temp./Filter's fine-tune), a Creative Look's panel and base look
INDEXED = re.compile(r" / (?:grid|panel|base) (\d+)\b")


def indexed_option(path: str, opts: list, values) -> str | None:
    """The option of the row's own setting (`values`, [[value, label]]) a path names by its place in the row's list
    (INDEXED), the list being the menu tree's options (`opts`) that name a label of the setting, each once, in the
    menu's order. A place past them is an option the walk read by another's name (a custom Creative Look shows its
    base look: "ST(Standard)" again at 12): the setting's labels no option names, in order (Custom Look 1, 2, ...).
    None when the path names none."""
    m = INDEXED.search(path or "")
    if not m:
        return None
    i, listed = int(m[1]), []
    for o in opts or []:
        lab = option_label(str(o), values)
        if lab is not None and lab not in listed:
            listed.append(lab)
    if i < len(listed):
        return listed[i]
    unnamed = [str(v[1]) for v in values or [] if isinstance(v, (list, tuple)) and len(v) > 1 and str(v[1]) not in listed]
    return unnamed[i - len(listed)] if i - len(listed) < len(unnamed) else None


def option_named(said: str, node: dict, values) -> str | None:
    """The option of a row `said` names exactly (norm(), a lookalike letter mended): as the row's own setting labels
    it (`values`, [[value, label]]), else as the menu tree lists it (the row's "opts"); None when it names none."""
    seg = norm(said.translate(LOOKALIKES))
    if not seg:
        return None
    for lab in [str(v[1]) for v in values or [] if isinstance(v, (list, tuple)) and len(v) > 1] + [str(o) for o in node["opts"] or []]:
        if norm(lab.translate(LOOKALIKES)) == seg:
            return lab
    return None


def option_page(m: "Tree", tab: str, path: str, values_of) -> tuple | None:
    """(the row, the option, the labels past it) when a path names an option of a row and then steps below it into
    the page that option opens ("Picture Profile > PP2 > Black Gamma > Level": the option PP2 of Picture Profile,
    then the page's Black Gamma > Level): the row reached from one of the tab's top rows (locate, never by a label met
    anywhere), the next label an option of that row (option_named; `values_of(row)`, the row's own setting's values),
    and only " > " steps after it. The shortest such row is taken; None when the path names none."""
    st = steps(path)
    for whole in (False, True):
        segs = m.segments(path, tab, whole)
        for i in range(1, len(segs) - 1):
            node, used = m.locate(tab, segs[:i], anywhere=False)
            if node is None or used != i:
                continue
            opt = option_named(segs[i], node, values_of(node))
            if opt and all(how == ">" for how, _ in st[len(st) - len(segs) + i + 1:]):
                return node, opt, segs[i + 1:]
    return None


def page_shape(m: "Tree", node: dict, options: set, shapes: dict, first: str) -> dict:
    """The page an option of a row opens where the menu tree has no child named as that option with rows under it,
    one shape for them all (each option's page has the same rows): the row's
    child the menu tree names as one of its options (`options`, norm()ed; the walk opened one, PP1), else a page made
    under the row named as the first option a path opened (`first`), its rows grown from the paths (Tree.grow)."""
    if node["id"] not in shapes:
        shapes[node["id"]] = next((k for k in node["kids"] if norm(k["l"]) in options and k["kids"]), None) \
            or m.grow(node, [first])
    return shapes[node["id"]]


def settings(doc, tree) -> dict:
    """Each setting's place on the camera: {key: {"row": [labels from its camera group's top row down], "row_at": [the
    top row's number in its tab (merge_tops), then each row's among its siblings], "under_option": the option of the
    row's own setting it is the choice for, "row_group": the definition's name for the camera group whose page holds
    the row, "row_tab": the tab whose menu holds it, "row_mode": the shooting mode whose menu holds it}} ("under_option"
    only when it is one, "row_tab" only when the tab is not the setting's own, "row_group" only when the group is not
    the setting's own, "row_mode" only for a row the Stills menu does not have).

    A setting hangs on the row its proof paths lead to in the Stills menu, in whichever group of its tab the row is
    (a screen the definition keeps as a group of its own, Fn Menu or Recall Custom hold 1, sits on its row: Fn Menu
    Settings, Reg. Custom Shoot Set); else, by the paths its context says were proved in a mode ("[Movie mode]"), on
    that mode's row; else, by a path with no context at all, on a row only a mode's menu has, in a tab the Stills
    menu has; else, the same way, on a row in another tab (reach()).
    Where the tree does not know the rows under the row a path reaches (a submenu never walked, a mode's row read
    off its page scan alone), the rest of the path's submenu steps are the rows, in the order the definition lists
    the settings proved through them. A path that names the row's option by its place in the list (INDEXED: "White
    Balance / grid 1", "Creative Look / panel 12 / Shadows") puts the setting under that option (indexed_option).

    A path that names an option of a row and steps below it (option_page: "Picture Profile > PP2 > Black Gamma >
    Level") puts the setting on the page that option opens: "row" is the row's labels, the option, then the page's
    rows down to the setting's; "row_at" the row's, then the option's index, then each page row's among its siblings,
    so one key orders them all; "under_option" the option; "row_group" and "row_tab" as for the row, but the page is
    the setting's own group, kept (a profile's parameters stay in "Picture Profile PP2", never moved to Color/Tone).
    The option's own page is the row's child named as it, where the tree has one with rows (PP1's); else every
    option's page has one shape (page_shape), so a page the walk opened once places the rows of all. A setting the
    tree's own rows place past the row already (a child row named as an option, with rows of its own: Recognition
    Target > Animal > Recognition Part) keeps that place.
    The option's index is the setting's column in its family (its group's place among the family's groups, PP2 at 1)
    for a family's setting, else the option's place among the row's own setting's labels (else the tree's options).
    A family's setting no path places takes the place of its record's copy in another column (the same area and id)
    that one places, under the option its own group names where the copy's group ends with the copy's option, when
    the row offers that option (its own setting's labels, else the tree's options); a column whose option the row
    never offers (PP7-PP9 on the a1 II) stays unplaced. The families' other settings are not placed, nor those whose
    paths reach no row."""
    t = Tree(doc, tree)
    modes = mode_trees(doc, tree)
    number = merge_tops(t, modes)
    fams = [f["prefix"] for f in (doc.get("camera") or {}).get("families", []) if f.get("prefix")]
    groups = collections.defaultdict(set)          # tab -> the definition's groups
    for s in doc["settings"]:
        groups[s.get("tab") or "Other"].add(s.get("group") or "")
    leaves = leaf_rows([t] + [m for _, m in modes])

    def menus(s) -> list:
        m = (s.get("proved") or {}).get("menu") or []
        m = [m] if isinstance(m, str) else m
        if any((s.get("group") or "").startswith(p) for p in fams):
            return [x for x in m if INDEXED.search(x)]           # a family's setting: by an indexed path only
        return m

    def shown_in(s, m, tab, g, g_tree) -> str:
        """The definition's name for the camera group `g` that holds a setting's row: its own group's (the head of
        "Shutter/Silent › Target Function Settings") when that is the one, else a group of the tab named so (or read
        with an icon), else the tree's."""
        head = (s.get("group") or "").split(" › ")[0]
        if m.group_of(tab, head) is g or head in (g["name"], g_tree):
            return head
        have = groups[tab] | set(t.place.groups.get(tab, ()))
        for c in (g["name"], g_tree):
            if c in have:
                return c
        hits = sorted({c for c in have if norm(c) and norm(c) in (norm(g["name"]), norm(g_tree), norm(g_tree)[1:])})
        return hits[0] if len(hits) == 1 else g["name"]

    hung, near = {}, {}            # key -> (the menu, the row it hangs on), and the camera group its proof went through
    for s in doc["settings"]:
        tab, group = s.get("tab") or "Other", s.get("group") or ""
        if any(group.startswith(p) for p in fams) and not menus(s):
            continue
        near[s["key"]] = t.place.of(s)["cg"]
        m, node = grown(t, modes, leaves, menus(s), tab, near[s["key"]], s.get("name") or "")
        if node:
            hung[s["key"]] = (m, node)
    past = {}                      # key -> what each path to its row names past the row, as read (None: the row itself)
    for s in doc["settings"]:
        k = s["key"]
        if k in hung:
            m, node = hung[k]
            tab = m.where[node["id"]][0][0]          # the row's tab, another than the setting's for a row there
            past[k] = {m.leftover(tab, p, node, near[k]) for p in menus(s) if m.leads(tab, p, node, near[k])}
    own = {}                       # a row's id -> its own setting: named as the row and proved on the row itself, the first
    for s in doc["settings"]:
        _, node = hung.get(s["key"], (None, None))
        if node and node["id"] not in own and norm(s.get("name")) == norm(node["l"]) and (None in past[s["key"]] or not past[s["key"]]):
            own[node["id"]] = s
    pages, shapes = {}, {}         # key -> its place on an option's page (option_page); a row's id -> its page shape
    offered = {}                   # key -> the options its row offers (norm()ed: its own setting's labels, the tree's)
    columns = {}                   # a family's group -> its column (its place among the family's groups)
    for p in fams:
        mine = sorted(dict.fromkeys(s["group"] for s in doc["settings"] if (s.get("group") or "").startswith(p)),
                      key=lambda g: min(x.get("order", 0) for x in doc["settings"] if x.get("group") == g))
        columns.update({g: i for i, g in enumerate(mine) if g not in columns})
    values_of = lambda node: (own.get(node["id"]) or {}).get("values")          # noqa: E731
    for s in doc["settings"]:
        tab, paths = s.get("tab") or "Other", (s.get("proved") or {}).get("menu") or []
        paths = [paths] if isinstance(paths, str) else paths
        said = [mode_of(p, [n for n, _ in modes]) for p in paths]
        tries = [(t, x, paths) for x in [tab] + [o for o in t.by_tab if o != tab]] + \
            [(m, x, [p for p, w in zip(paths, said, strict=True) if w == mode]) for mode, m in modes for x in [tab] + [o for o in m.by_tab if o != tab]]
        hit = next(((m, x, got) for m, x, ps in tries for p in ps if (got := option_page(m, x, p, values_of))), None)
        if not hit or (s["key"] in hung and hung[s["key"]][1] is not hit[2][0]):
            continue               # none, or the tree's own rows already place it past the row (Recognition Target)
        m, rtab, (node, opt, rest) = hit
        vals = values_of(node) or []
        names = [str(v[1]) for v in vals if isinstance(v, (list, tuple)) and len(v) > 1] or [str(o) for o in node["opts"]]
        shape = next((k for k in node["kids"] if norm(k["l"]) == norm(opt) and k["kids"]), None) or \
            page_shape(m, node, {norm(x) for x in names + [str(o) for o in node["opts"]]}, shapes, opt)
        deep = m.grow(shape, rest)
        (_, g, g_tree), labels, at = m.where[node["id"]]
        index = columns.get(s.get("group")) if s.get("group") in columns else \
            next((i for i, x in enumerate(names) if norm(x) == norm(opt)), len(names))
        place = {"row": labels + [opt] + m.where[deep["id"]][1][len(labels) + 1:],
                 "row_at": [number.get((m.mode, rtab, at[0]), at[0])] + at[1:] + [index] + m.where[deep["id"]][2][len(at) + 1:],
                 "under_option": opt}
        if rtab != tab:
            place["row_tab"] = rtab
        shown = shown_in(s, m, rtab, g, g_tree)
        if rtab != tab and shown != (s.get("group") or ""):
            place["row_group"] = shown
        if m.mode:
            place["row_mode"] = m.mode
        pages[s["key"]] = place
        offered[s["key"]] = {norm(x) for x in names + [str(o) for o in node["opts"]]}
    by_record = collections.defaultdict(list)          # (area, id) -> the family settings placed on an option's page
    for s in doc["settings"]:
        if s["key"] in pages and s.get("group") in columns:
            by_record[(s.get("area"), s.get("id"))].append(s)
    for s in doc["settings"]:
        g = s.get("group") or ""
        if s["key"] in pages or s["key"] in hung or g not in columns:
            continue
        for c in by_record.get((s.get("area"), s.get("id")), []):
            cp, cg = pages[c["key"]], c["group"]
            head = cg[:-len(cp["under_option"])]
            if cg.endswith(cp["under_option"]) and g.startswith(head) and g != head and g.startswith(next(p for p in fams if cg.startswith(p))):
                opt, i = g[len(head):], cp["row"].index(cp["under_option"])
                if norm(opt) not in offered[c["key"]]:
                    break          # a column whose option the row never offers (PP7 on the a1 II): unplaced
                pages[s["key"]] = {**cp, "row": cp["row"][:i] + [opt] + cp["row"][i + 1:],
                                   "row_at": cp["row_at"][:i] + [columns[g]] + cp["row_at"][i + 1:], "under_option": opt}
                break
    out = dict(pages)
    for s in doc["settings"]:
        if s["key"] not in hung or s["key"] in pages:
            continue
        m, node = hung[s["key"]]
        (tab, g, g_tree), labels, at = m.where[node["id"]]
        place = {"row": labels, "row_at": [number.get((m.mode, tab, at[0]), at[0])] + at[1:]}
        mine = own.get(node["id"])
        if mine is not None and mine is not s:
            # the option every path to this row names past it, as the row's own setting labels it; none when a
            # path names none (the record is the row's too: Drive Mode's third record) or they name different ones
            said = {option_label(left, mine.get("values")) if left else None for left in past[s["key"]]}
            by_place = {indexed_option(p, node["opts"], mine.get("values")) for p in menus(s) if INDEXED.search(p)}
            if by_place:
                said = by_place
            if len(said) == 1 and None not in said:
                place["under_option"] = said.pop()
        if tab != (s.get("tab") or "Other"):
            place["row_tab"] = tab
        shown = shown_in(s, m, tab, g, g_tree)
        if shown != (s.get("group") or ""):
            place["row_group"] = shown
        if m.mode:
            place["row_mode"] = m.mode
        out[s["key"]] = place
    return out
