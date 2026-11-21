"""Records that no settings file sets back, by model. A memory slot's (NOT_BY_FILE, and SET_EXTRA in some sets): an
upload leaves them as the slot's last registration wrote them; kit/provers/memreg_run.py expects its section's three
to differ after its restore, and kit/tools/upload_check.py and kit/provers/mode_switch.py's --restore leave a slot's
out of a restore's count only where the camera's download shows that slot filled (filled_left_of): a slot that reads
empty tolerates nothing. A user LUT's (USER_LUT): kit/tools/lut_import.py takes them, and only them, as the LUT's own
state when they differ after its restore (docs/decisions/0026); any other record that did not go back fails its
restore."""
from pathlib import Path

# the slot's filled mark, its registration family and the exposure mode it was registered in (kit2_small_1109:
# 00159_restored.DAT and 00289_restored.DAT differ from the files before the registrations in these alone)
NOT_BY_FILE = {"ILCE-1M2": (0x023c, 0x11ab, 0x11ad)}

# a set's filled mark and the code it holds once the slot is registered (2 empty, 4 filled on the a1 II)
FILLED_MARK = {"ILCE-1M2": (0x023c, 4)}

# the file sections of the body's memory slots (data/<camera>/camera_<camera>.json's memory_sets: on the a1 II Stills
# 1-3, Movie 4-6, S&Q 7-9, Time-lapse 10-12). A set section's records share one layout (the definition's set: keys), so
# NOT_BY_FILE's three are the same records in each; seen in section 1 (kit2_small_1109), and in a Movie, S&Q or
# Time-lapse section first by that family's first registration, whose own restore check (memreg_run's) counts every
# other record of the file (2026-11-21, branch memreg-slots)
MEMORY_SECTIONS = {"ILCE-1M2": tuple(range(1, 13))}

# what a registration writes besides NOT_BY_FILE in some sections, by model and section: in the S&Q and Time-lapse sets,
# 0x0170 (the maintainer's log of 2026-10-30: "Records only registration writes: 0x023c, 0x11ab ..., 0x11ad and,
# in S&Q and Time-lapse sets, 0x0170"; kit2_memmirror 00316-00325 wrote set7:0x0170 beside set7:0x023c and 0x11ab,
# 00427-00436 the same in set10). Whether a settings file puts it back has never been checked: memreg_run's own restore
# leaves it counted (its section's three alone), so the first S&Q or Time-lapse registration shows it by key
SET_EXTRA = {"ILCE-1M2": {n: (0x0170,) for n in range(7, 13)}}

# the records that hold a user LUT in the camera, as keys ("global:0x0123"), named from a first import's run once its
# downloads have been looked at; none yet, so every record that does not go back after an import fails its restore
USER_LUT = {"ILCE-1M2": ()}


def memory_left(model: str, sections=None) -> frozenset:
    """The keys ("set7:0x023c") of the records a registration writes and no settings file sets back (NOT_BY_FILE, and
    SET_EXTRA's for the section) in each of `sections` (default: every one of the model's MEMORY_SECTIONS); empty for a
    model they do not name."""
    sections = MEMORY_SECTIONS.get(model, ()) if sections is None else sections
    extra = SET_EXTRA.get(model, {})
    return frozenset(f"set{n}:0x{rid:04x}" for n in sections
                     for rid in (*NOT_BY_FILE.get(model, ()), *extra.get(n, ())) if model in NOT_BY_FILE)


def filled_sections(cs) -> tuple:
    """The memory sections the settings file `cs` (camkit.camset) shows filled: its FILLED_MARK record holds the filled
    code there."""
    rid, code = FILLED_MARK.get(cs.model, (None, None))
    out = []
    for n in MEMORY_SECTIONS.get(cs.model, ()) if rid is not None else ():
        rec = cs.get(n, rid)
        if rec is not None and rec.value() == code:
            out.append(n)
    return tuple(out)


def filled_left_of(after) -> frozenset:
    """memory_left for the slots the camera's download `after` (a path) shows filled, nothing for a slot it shows empty:
    the records a restore check leaves out of its count, decided by the download itself (camkit.session takes it as its
    `expected`). Nothing where the file cannot be read."""
    from . import camset
    try:
        cs = camset.read(Path(after))
        return memory_left(cs.model, filled_sections(cs))
    except Exception:
        return frozenset()
