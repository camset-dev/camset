"""The editor's Menu "As on the camera", from a definition alone: a copy of editor/src/menu_rows.rs (a group's rows,
from each setting's place in its definition: row, row_at, under_option, row_tab, row_group and row_mode, which
camkit.placement writes) and of the parts of editor/src/pages/menu.rs that choose the Menu's entries and a tab's groups
(menu_tabs, entry_of, off_menu_in, tab_groups, and group_key from menu_rows.rs). The definition viewer
(kit/tools/proof_viewer.py --public) draws its menu with it, so a page built from public files alone shows the tabs,
groups and rows the editor shows. The editor is the reference: a change to its layout is made here too
(kit/tests/test_menu_rows.py holds its own cases, copied, and compares the a1 II's default Menu with the one a test of
editor/src/pages/menu.rs writes, editor/tests/data/menu_ILCE-1M2_fw4.00.json).

Which settings are laid out is the caller's (shown): the editor's Menu by default lists the live settings without the
Expert ones; the viewer's Expert switch lists every setting, the memory sets' too.
"""
import collections

OTHER_TAB = "Other"          # the editor's entry for the tabs a definition does not list (pages/menu.rs)
MORE = "More settings in this group"


def norm(s) -> str:
    """Lower-case letters and digits only, as the editor compares menu labels (menu_rows::norm)."""
    return "".join(c for c in (s or "").lower() if c.isascii() and (c.islower() or c.isdigit()))


# ---------------------------------------------------------------- a setting's place (editor/src/schema.rs, Setting)

def placed(s) -> bool:
    """Whether the definition places the setting on a row of the camera's menu (row, with a sort key as long)."""
    return bool(s.get("row")) and len(s["row"]) == len(s.get("row_at") or [])


def page_prefix(s) -> int | None:
    """How many of row's labels lead to the page an option of its owner's row opens, when the setting is on one."""
    opt = s.get("under_option")
    if opt is None or not placed(s):
        return None
    return next((p + 1 for p in range(1, len(s["row"]) - 1) if s["row"][p] == opt), None)


def on_page(s) -> bool:
    return page_prefix(s) is not None


def same_row(a, b) -> bool:
    return (a.get("row") or []) == (b.get("row") or []) and (a.get("row_at") or []) == (b.get("row_at") or []) \
        and a.get("row_mode") == b.get("row_mode")


def links_with(a, b) -> bool:
    """One setting kept in several records: the same name in the same place, never a copy with its setting."""
    return a["key"] == b["key"] or (a.get("name") == b.get("name") and same_row(a, b) and a.get("under_option") == b.get("under_option")
                                    and a.get("copy_of") is None and b.get("copy_of") is None)


def option_tree(s) -> list | None:
    """The options as the camera nests them, when option_tree fits the values (Setting::option_tree); else None."""
    tree = s.get("option_tree") or []
    nest = lambda n: bool(n.get("options"))          # noqa: E731
    if not any(nest(n) for n in tree) or any((n.get("value") is not None) == nest(n) or len(n.get("options") or []) == 1 for n in tree):
        return None
    held = [v for n in tree for v in ([n["value"]] if n.get("value") is not None else []) + [o[0] for o in n.get("options") or []]]
    return tree if len(set(held)) == len(held) and sorted(set(held)) == sorted({v for v, _ in s.get("values") or []}) else None


def nests_option(s, option: str) -> bool:
    """Whether the option tree shows option's choices itself (a setting under that option is then no choice beside it)."""
    labels = {}
    for v, lab in s.get("values") or []:
        labels.setdefault(v, lab)          # the first label of a value, as Setting::label_for finds it
    return any(n.get("options") and (n.get("label") == option or any(labels.get(v) == option for v, _ in n["options"]))
               for n in option_tree(s) or [])


def is_own(s) -> bool:
    """Its row's own setting: placed, named as the row, and not the sub-choice of an option."""
    return placed(s) and s.get("under_option") is None and norm(s["row"][-1]) == norm(s.get("name"))


def owner(firsts, s):
    """The row's own setting among firsts that s is a sub-choice of, when there is one."""
    if s.get("under_option") is None:
        return None
    return next((o for o in firsts if is_own(o) and same_row(o, s)), None)


def beside_owner(firsts, s):
    """The own setting that shows s beside its option, so that s is no row of its own (menu_rows::beside_owner)."""
    opt = s.get("under_option")
    o = owner(firsts, s) if opt is not None else None
    return o if o is not None and any(lab == opt for _, lab in o.get("values") or []) and not nests_option(o, opt) else None


def sub_choices(own, among) -> list:
    """[(setting, option)]: the settings of among shown beside own's options, in the order own lists them, an option's
    several by their order in the definition, then name; one setting kept in several records once."""
    if not is_own(own):
        return []
    labels = [lab for _, lab in own.get("values") or []]
    out = []
    for s in among:
        opt = s.get("under_option")
        if not same_row(s, own) or s["key"] == own["key"] or on_page(s) or opt is None or nests_option(own, opt) or opt not in labels:
            continue
        out.append((labels.index(opt), s, opt))
    out.sort(key=lambda x: (x[0], x[1].get("order", 0), x[1].get("name") or ""))
    seen, kept = [], []
    for _, s, opt in out:
        if not any(links_with(o, s) for o in seen):
            kept.append((s, opt))
        seen.append(s)
    return kept


def base_name(name: str) -> str:
    n = (name or "").strip()
    for tail in ("(stills)", "(movie)"):
        if n.endswith(tail):
            n = n[:-len(tail)]
            break
    return norm(n)


# ---------------------------------------------------------------- a group's rows (menu_rows::lay_out)

def _key(rows: list, firsts: list, i: int) -> list:
    s = rows[i][0]
    k = list(s["row_at"])
    if is_own(s):
        k += [-3, 0]
    elif s.get("under_option") is not None:
        o = owner(firsts, s)
        labels = [lab for _, lab in (o or {}).get("values") or []]
        k += [-2, labels.index(s["under_option"]) if s["under_option"] in labels else 2 ** 63 - 1]
    else:
        k += [-1, 0]
    return k + [i]


def _nest(rows: list, firsts: list, placed_rows: list, mode, strip, lines: list) -> None:
    def node(s, n):
        k = strip(s)
        return tuple(s["row_at"][k:k + n]), tuple(s["row"][k:k + n])
    length = lambda s: len(s["row"]) - strip(s)          # noqa: E731
    here, deeper = collections.defaultdict(set), set()
    for i in placed_rows:
        s = rows[i][0]
        here[node(s, length(s))].add(base_name(s.get("name")) if on_page(s) else s["key"])
        for n in range(1, length(s)):
            deeper.add(node(s, n))
    opened, row_here = [], None
    for i in sorted(placed_rows, key=lambda i: _key(rows, firsts, i)):
        s = rows[i][0]
        k = strip(s)
        path = list(zip(s["row_at"][k:], s["row"][k:], strict=True))
        common = 0
        while common < min(len(opened), len(path)) and opened[common] == path[common]:
            common += 1
        del opened[common:]
        if common == len(path):
            lines.append(("row", i, len(path) - 1 if row_here == path else len(path)))
            continue
        row_here = None
        for level in range(common, len(path)):
            label = path[level][1]
            labels = ([mode] if mode else []) + [p[1] for p in path[:level + 1]]
            opened.append(path[level])
            mine = node(s, level + 1)
            if level + 1 < len(path):
                lines.append(("heading", label, level, labels))
            elif is_own(s) or ((s.get("under_option") is None or on_page(s)) and len(here.get(mine, ())) == 1 and mine not in deeper):
                lines.append(("row", i, level))          # its own setting, or one alone on it with no rows under it
                if on_page(s):
                    row_here = list(path)
            else:
                lines.append(("heading", label, level, labels))
                lines.append(("row", i, level + 1))


def lay_out(rows: list) -> list:
    """A group's rows (each a list of linked settings, the first leading) as the camera lists them, as lines:
    ("heading", label, depth, labels), ("row", index, depth), ("mode", name) over the rows only another shooting mode's
    menu has, and ("more",) over the rows the definition does not place; a group that places none is the flat list."""
    firsts = [r[0] for r in rows]
    placed_rows = [i for i in range(len(rows)) if placed(rows[i][0])]
    if not placed_rows:
        return [("row", i, 0) for i in range(len(rows))]
    placed_rows = [i for i in placed_rows if beside_owner(firsts, rows[i][0]) is None]
    lead = []
    for i in placed_rows:
        s, n = rows[i][0], page_prefix(rows[i][0])
        if n and (s["row"][:n], s["row_at"][:n]) not in lead:
            lead.append((s["row"][:n], s["row_at"][:n]))
    one = len(lead) == 1

    def strip(s):
        n = page_prefix(s)
        return 0 if n is None else n if one else n - 1
    lines = []
    _nest(rows, firsts, [i for i in placed_rows if rows[i][0].get("row_mode") is None], None, strip, lines)
    modes = {}
    for i in placed_rows:
        m = rows[i][0].get("row_mode")
        if m:
            modes[m] = min(modes.get(m, rows[i][0]["row_at"][0]), rows[i][0]["row_at"][0])
    for m in sorted(modes, key=lambda m: (modes[m], m)):
        lines.append(("mode", m))
        _nest(rows, firsts, [i for i in placed_rows if rows[i][0].get("row_mode") == m], m, strip, lines)
    rest = [i for i in range(len(rows)) if not placed(rows[i][0])]
    if rest:
        lines.append(("more",))
        lines += [("row", i, 0) for i in rest]
    return lines


# ---------------------------------------------------------------- the Menu's entries and a tab's groups (pages/menu.rs)

def shown(doc: dict, expert: bool = False) -> list:
    """The settings the editor's Menu lists for the live settings (pages/menu.rs, settings_in with target 0): those of
    area global, but the Expert ones (a derived working copy, a flag, an alternate numbering); with expert, every
    setting of the definition (the viewer's Expert switch: the memory sets' too)."""
    return list(doc["settings"]) if expert else [s for s in doc["settings"] if s.get("area") == "global" and not s.get("expert")]


def camera_tab(s) -> str:
    return s["row_tab"] if s.get("row_tab") and placed(s) else s.get("tab") or ""


def camera_group(s) -> str:
    return s["row_group"] if s.get("row_group") and placed(s) else s.get("group") or ""


def group_key(order: int, name: str, settings: list) -> tuple:
    """A tab's groups as on the camera: the ones it places rows of by their first row, a page an option opens after
    its owner's row's group, then the others by their place in the definition, each by name last."""
    page = min((s["row_at"][n - 1] for s in settings for n in [page_prefix(s)] if n), default=-1)
    at = min((s["row_at"][0] for s in settings if placed(s)), default=None)
    return (False, at, page, name) if at is not None else (True, order, page, name)


class Menu:
    """The Menu of one definition as the editor lays it out on the camera's rows."""

    def __init__(self, doc: dict):
        cam = doc.get("camera") or {}
        text = cam.get("text") or {}
        self.doc, self.tabs = doc, list(doc.get("tabs") or [])
        self.families = [f for f in cam.get("families") or [] if f.get("prefix")]
        self.my_menu = text.get("my_menu_name") or "My Menu"
        self.has_my_menu = bool((cam.get("my_menu") or {}).get("records"))
        self.off = text.get("off_menu_name") or "Not in the menus"
        # the editor's camera_layout(): rows as on the camera when the definition places any setting (the viewer has
        # no flat list to ask for); a definition that places none keeps every setting in its own tab and group, and the
        # entry for what the menus do not hold is not there
        self.camera = any(placed(s) for s in doc["settings"])
        self.placed_groups = collections.defaultdict(set)
        for s in doc["settings"]:
            if placed(s):
                self.placed_groups[camera_tab(s)].add(camera_group(s))

    def family(self, s):
        return next((f for f in self.families if (s.get("group") or "").startswith(f["prefix"])), None)

    def off_menu(self, s) -> bool:
        """A setting of a tab the definition lists on no row of the camera, whose group has none on one either."""
        return (self.camera and not placed(s) and s.get("tab") in self.tabs and not (self.has_my_menu and s.get("tab") == self.my_menu)
                and self.family(s) is None and (s.get("group") or "") not in self.placed_groups.get(s.get("tab"), ()))

    def layout_tab(self, s) -> str:
        return camera_tab(s) if self.camera and self.family(s) is None else s.get("tab") or ""

    def layout_group(self, s) -> str:
        return camera_group(s) if self.camera and self.family(s) is None else s.get("group") or ""

    def beside(self, own, settings: list) -> list:
        """[(setting, option)] shown beside own's options in the editor's detail panel (pages/detail.rs, beside): the
        sub-choices among `settings` (the ones the Menu lists) of own's tab as shown whose camera group is own's, a
        family's too (a Creative Look's parameters beside its row's looks)."""
        if not is_own(own):
            return []
        tab, group = self.layout_tab(own), camera_group(own)
        return sub_choices(own, [s for s in settings if self.layout_tab(s) == tab and camera_group(s) == group])

    def entry_of(self, s) -> str:
        if self.off_menu(s):
            return self.off
        tab = self.layout_tab(s)
        return tab if (self.has_my_menu and tab == self.my_menu) or tab in self.tabs or tab == self.off else OTHER_TAB

    def entries(self, settings: list = None) -> list:
        """[(entry, its settings)]: the Menu's entries in order, for `settings` (shown(); by default every setting of the
        definition): the definition's tabs (My Menu's left out when it has a page of its own), Other, the entry for
        what the menus do not hold (as on the camera only), then My Menu's own tab; each only when it holds a setting,
        but the definition's tabs."""
        mine = collections.defaultdict(list)
        for s in self.doc["settings"] if settings is None else settings:
            mine[self.entry_of(s)].append(s)
        names = [t for t in self.tabs if not (self.has_my_menu and t == self.my_menu) and t not in (OTHER_TAB, self.off)]
        names += [t for t in (OTHER_TAB, self.off) + ((self.my_menu,) if self.has_my_menu else ()) if mine.get(t)]
        return [(t, mine.get(t, [])) for t in names]

    def groups(self, entry: str, settings: list) -> list:
        """[(group, family or None, rows)]: a tab's groups as tab_groups orders them, each a list of rows of linked
        settings; a family's settings first, all in one row (its table), then the camera's groups in the camera's order,
        a family's group that is the page an option opens among them."""
        off = entry == self.off
        groups = {}
        for s in settings:
            g = f"{s.get('tab')} > {s.get('group')}" if off else self.layout_group(s)
            groups.setdefault(g, [s.get("order", 0), []])[1].append(s)
        out = []
        for f in self.families:
            fam = [s for g, (_, v) in sorted(groups.items(), key=lambda kv: (kv[1][0], kv[0])) if g.startswith(f["prefix"]) for s in v]
            groups = {g: v for g, v in groups.items() if not g.startswith(f["prefix"]) or (self.camera and any(on_page(s) for s in v[1]))}
            if fam:
                out.append((f.get("title") or f["prefix"], f, [fam]))
        at = {t: i for i, t in enumerate(self.tabs)}
        order = (lambda kv: (at.get(kv[1][1][0].get("tab"), len(at)), kv[1][0], kv[0])) if off else \
            (lambda kv: group_key(kv[1][0], kv[0], kv[1][1])) if self.camera else (lambda kv: (kv[1][0], kv[0]))
        for g, (_, items) in sorted(groups.items(), key=order):
            rows = []
            for s in items:
                r = next((r for r in rows if links_with(r[0], s)), None)
                if r is None:
                    rows.append([s])
                else:
                    r.append(s)
            out.append((g, None, rows))
        return out
