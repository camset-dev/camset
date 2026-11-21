"""When the camera greys a row that inactive_when cannot say truly: a setting's grey_in (the shooting modes in which
the camera draws its row grey whatever the file holds) and inactive_if (inactive_when's rule, true only in some
shooting modes, `family`, or only with a device on the HDMI socket, `hdmi_device`), the hand tables' alone
(RECORD_FIXES), and the private looks that must prove each side (the hand evidence's RECORD_FIXES part, "looks").

The modes are the camera's own names for its shooting modes (camera.live_mode's, the a1 II's Stills, Movie, S&Q and
Time-lapse), never menu names: the S&Q menu serves both S&Q Motion and Time-lapse, so a fact that differs between them
is written by naming only the mode it holds in. inactive_if is a key of its own, not more keys inside inactive_when:
an editor that predates it reads inactive_when and ignores keys it does not know, and would show the rule's grey with
no cable and in every mode; it ignores inactive_if whole. No rule of either kind stands on the live-mode record itself:
the editor would grey the row in every menu's view whenever the file stands in that mode (grey_in says it instead).
problems() is what the writer refuses and kit/tools/check_public.py holds a definition to; look_problems() is the
sides of a hand-table entry its looks do not prove (docs/DATA_CONTRACTS.md, "When the camera greys a row")."""

RULE_KEYS = ("record", "name", "values", "except", "unlock", "unlock_label")      # inactive_when's, kept in inactive_if
CONDITIONS = ("family", "hdmi_device")      # what inactive_if adds: the modes it holds in, a device on the HDMI socket
FIELDS = ("grey_in", "inactive_if")         # a setting's fields of this kind: the hand tables' alone (RECORD_FIXES)
EVIDENCE = ("looks",)                       # a RECORD_FIXES entry's private fields (the hand evidence): never copied
DRAWN = ("grey", "white")                   # what a look saw of the row
KIT_SET = ("mode", "blocker")               # what the kit set in a look's run: the shooting mode always, the blocker's value
HDMI = ("in", "out")                        # the HDMI cable in a look, as the chain's context line gives it
HELP = ("shoot mode", "another setting", "none")        # what the camera's Help or its notice on the grey row named
LOOK_KEYS = ("run", "line", "mode", "drawn", "blocker", "kit_set", "hdmi", "help")


def live_names(camera: dict) -> list:
    """The camera's names for its shooting modes, in the order of the live-mode record's values (camera.live_mode's
    modes, {value: name}); [] where the camera file gives none."""
    modes = ((camera or {}).get("live_mode") or {}).get("modes") or {}
    try:
        return [modes[k] for k in sorted(modes, key=int)]
    except (TypeError, ValueError):
        return list(modes.values())


def live_record(camera: dict) -> int | None:
    """The live-mode record's id (camera.live_mode's key, "global:0x13bf" -> 0x13bf), or None."""
    key = str(((camera or {}).get("live_mode") or {}).get("key") or "")
    try:
        return int(key.split(":")[1].split("[")[0], 16) if key.startswith("global:0x") else None
    except (IndexError, ValueError):
        return None


def menu_modes(camera: dict) -> dict:
    """{a camera menu's name: the shooting modes it serves} (camera.menus)."""
    return {m.get("name"): list(m.get("modes") or []) for m in (camera or {}).get("menus") or [] if isinstance(m, dict)}


def _names(x, field: str, names: list, where: str) -> list:
    """What is wrong with a list of mode names (`x`): not a list of names, empty, one twice, or one the camera lacks."""
    if not isinstance(x, list) or not x or not all(isinstance(m, str) and m for m in x):
        return [f"{where}: {field} is not a list of the camera's shooting-mode names"]
    out = [f"{where}: {field} names {m!r} twice" for m in sorted({m for m in x if x.count(m) > 1})]
    if names:
        out += [f"{where}: {field} names {m!r}, none of the camera's shooting modes ({', '.join(names)})"
                for m in x if m not in names]
    return out


def rule_problems(rule, where: str, names: list = (), live: int | None = None) -> list:
    """What is wrong with an inactive_if (`rule`): its keys (inactive_when's, record, values and unlock among them, and
    one or both conditions, nothing else), a family that is not some of the camera's modes, an hdmi_device other than
    true, or a rule on the live-mode record."""
    if not isinstance(rule, dict):
        return [f"{where}: inactive_if is not an object"]
    out = [f"{where}: inactive_if holds {k!r}, which it does not have (inactive_when's keys, family, hdmi_device)"
           for k in rule if k not in RULE_KEYS + CONDITIONS]
    for k, t in (("record", int), ("unlock", int), ("name", str), ("unlock_label", str)):
        if not isinstance(rule.get(k), t) or isinstance(rule.get(k), bool):
            out.append(f"{where}: inactive_if has no {k} ({'a whole number' if t is int else 'words'})")
    for k in ("values", "except"):
        if (k in rule or k == "values") and not (isinstance(rule.get(k), list) and
                                                 all(isinstance(v, int) and not isinstance(v, bool) for v in rule[k])):
            out.append(f"{where}: inactive_if's {k} is not a list of whole numbers")
    if not any(k in rule for k in CONDITIONS):
        out.append(f"{where}: inactive_if names no condition (family, hdmi_device): a rule that holds always is "
                   "inactive_when")
    if "family" in rule:
        out += _names(rule["family"], "inactive_if's family", names, where)
        if names and isinstance(rule["family"], list) and set(names) <= set(rule["family"]):
            out.append(f"{where}: inactive_if's family names every shooting mode: a rule that holds in all of them is "
                       "inactive_when")
    if "hdmi_device" in rule and rule["hdmi_device"] is not True:
        out.append(f"{where}: inactive_if's hdmi_device is only ever true")
    if live is not None and rule.get("record") == live:
        out.append(f"{where}: inactive_if stands on the live-mode record: write the modes it holds in as grey_in, or as "
                   "the family of a rule on another record")
    return out


def grey_in_problems(grey, where: str, names: list = (), served: list = None) -> list:
    """What is wrong with a grey_in (`grey`): not some of the camera's mode names; with `served` (the modes of the
    menus that list the row, None when unknown), a mode none of them serves, or every one (the row must be drawn white
    somewhere)."""
    out = _names(grey, "grey_in", names, where)
    if out or served is None:
        return out
    if not served:
        return [f"{where}: grey_in on a setting listed in no camera menu"]
    out += [f"{where}: grey_in names {m!r}, which no menu that lists the row serves ({', '.join(served)})"
            for m in grey if m not in served]
    if set(served) <= set(grey):
        out.append(f"{where}: grey_in names every mode its menus serve: the row would be drawn white nowhere")
    return out


def problems(doc: dict) -> list:
    """Each place a definition's grey_in, inactive_if or inactive_when is not as this module says, one line each,
    naming the setting and the field, never a value but the camera's mode names: grey_in and inactive_if as
    grey_in_problems and rule_problems say (the modes the camera's live_mode names; grey_in within the modes of the
    menus in the setting's row_menus), an inactive_when on the live-mode record, and a setting holding a look (the
    hand evidence's, never public)."""
    cam = doc.get("camera") or {}
    names, live, by_menu = live_names(cam), live_record(cam), menu_modes(cam)
    out = []
    for s in doc.get("settings") or []:
        where = s.get("key") or s.get("name") or "a setting"
        if "grey_in" in s:
            served = None
            if by_menu:
                served = list(dict.fromkeys(m for menu in s.get("row_menus") or [] for m in by_menu.get(menu) or []))
            out += grey_in_problems(s["grey_in"], where, names, served)
        if "inactive_if" in s:
            out += rule_problems(s["inactive_if"], where, names, live)
        iw = s.get("inactive_when")
        if "inactive_when" in s and not isinstance(iw, dict):
            out.append(f"{where}: inactive_when is not an object")
        elif isinstance(iw, dict) and live is not None and iw.get("record") == live:
            out.append(f"{where}: inactive_when stands on the live-mode record: write the modes it holds in as grey_in")
        out += [f"{where}: holds {k!r}, the hand evidence's (a look), never the definition's" for k in EVIDENCE if k in s]
    return out


def holds(rule: dict, value) -> bool:
    """Whether the rule's record value greys the row (inactive_when's sense: one of values, or any but except)."""
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    return value in (rule.get("values") or []) or (bool(rule.get("except")) and value not in rule["except"])


def shape_problems(looks, names: list = ()) -> list:
    """What is wrong with a list of looks as the hand evidence holds them: each {run, line, mode, drawn, kit_set[,
    blocker][, hdmi][, help]} with those words only."""
    if not isinstance(looks, list) or not looks:
        return ["looks is not a list of looks"]
    out = []
    for i, x in enumerate(looks):
        w = f"looks[{i}]"
        if not isinstance(x, dict):
            out.append(f"{w} is not an object")
            continue
        out += [f"{w} holds {k!r}, which a look does not have" for k in x if k not in LOOK_KEYS]
        out += [f"{w} has no {k}" for k in ("run", "line", "mode", "drawn", "kit_set") if k not in x]
        if "run" in x and not (isinstance(x["run"], str) and x["run"]):
            out.append(f"{w}'s run is not a run's name")
        if "line" in x and not (isinstance(x["line"], int) and not isinstance(x["line"], bool) and x["line"] > 0):
            out.append(f"{w}'s line is not a line number")
        if "mode" in x and (not isinstance(x["mode"], str) or (names and x["mode"] not in names)):
            out.append(f"{w}'s mode is none of the camera's shooting modes")
        for k, words in (("drawn", DRAWN), ("hdmi", HDMI), ("help", HELP)):
            if k in x and x[k] not in words:
                out.append(f"{w}'s {k} is none of {', '.join(map(repr, words))}")
        if "blocker" in x and not (isinstance(x["blocker"], int) and not isinstance(x["blocker"], bool)):
            out.append(f"{w}'s blocker is not a whole number")
        ks = x.get("kit_set")
        if "kit_set" in x and (not isinstance(ks, list) or "mode" not in ks or any(k not in KIT_SET for k in ks)
                               or len(set(ks)) != len(ks)):
            out.append(f"{w}'s kit_set is not \"mode\", with \"blocker\" where the kit set the blocker's value")
    return out


def look_problems(fix: dict, looks, names: list = ()) -> list:
    """The sides of a RECORD_FIXES entry's grey_in or inactive_if (`fix`) its looks (the hand evidence's, `looks`) do
    not prove, one line each, never a value. Every look's mode was set by the kit's own switch (kit_set). grey_in:
    for each mode it names, a look reading the row grey there with Help (or its notice) naming the shoot mode, and a
    look reading it white in a mode it leaves out. inactive_if: a look reading it grey at a value of the blocker that
    greys it and one reading it white at a value that does not, each value set by the kit, where its conditions hold
    (in a mode of its family, with the cable in); with a family, a look reading it white at a value that greys it in a
    mode the family leaves out; with hdmi_device, one reading it white at such a value, set by the kit, with the cable
    out. [] when the entry has neither field."""
    if not any(k in fix for k in FIELDS):
        return []
    if looks is None:
        return ["the hand evidence gives no looks"]
    bad = shape_problems(looks, names)
    if bad:
        return bad
    out = []
    grey = fix.get("grey_in")
    if isinstance(grey, list):
        for m in grey:
            if not any(x["mode"] == m and x["drawn"] == "grey" and x.get("help") == "shoot mode" for x in looks):
                out.append(f"grey_in: no look reads the row grey in {m} with Help naming the shoot mode")
        if not any(x["mode"] not in grey and x["drawn"] == "white" for x in looks):
            out.append("grey_in: no look reads the row white in a mode grey_in leaves out")
    rule = fix.get("inactive_if")
    if isinstance(rule, dict):
        family = rule.get("family") if isinstance(rule.get("family"), list) else None
        hdmi = rule.get("hdmi_device") is True

        def where(x, in_family=True, cable="in"):
            return ((family is None or (x["mode"] in family) == in_family)
                    and (not hdmi or x.get("hdmi") == cable))
        set_value = [x for x in looks if "blocker" in x and "blocker" in x["kit_set"]]
        cond = (f" in {', '.join(family)}" if family else "") + (" with the HDMI cable in" if hdmi else "")
        if not any(holds(rule, x["blocker"]) and x["drawn"] == "grey" and where(x) for x in set_value):
            out.append(f"inactive_if: no look reads the row grey at a value that greys it, set by the kit{cond}")
        if not any(not holds(rule, x["blocker"]) and x["drawn"] == "white" and where(x) for x in set_value):
            out.append(f"inactive_if: no look reads the row white at a value that does not grey it, set by the kit{cond}")
        if family is not None and not any(holds(rule, x.get("blocker")) and x["drawn"] == "white"
                                          and where(x, in_family=False) for x in looks):
            out.append("inactive_if: no look reads the row white at a value that greys it in a mode its family leaves out")
        if hdmi and not any(holds(rule, x["blocker"]) and x["drawn"] == "white" and where(x, cable="out")
                            for x in set_value):
            out.append("inactive_if: no look reads the row white at a value that greys it, set by the kit, with the "
                       "HDMI cable out")
    return out
