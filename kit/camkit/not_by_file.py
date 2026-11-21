"""Records that no settings file sets back, by model. A memory slot's (NOT_BY_FILE): an upload leaves them as the slot's
last registration wrote them; kit/provers/memreg_run.py expects them to differ after its restore, and
kit/tools/upload_check.py and kit/provers/mode_switch.py's --restore leave them out of a restore's count in every
memory section the body has (memory_left). A user LUT's (USER_LUT): kit/tools/lut_import.py takes them, and only them,
as the LUT's own state when they differ after its restore (docs/decisions/0026); any other record that did not go back
fails its restore."""

# the slot's filled mark, its registration family and the exposure mode it was registered in (kit2_small_1109:
# 00159_restored.DAT and 00289_restored.DAT differ from the files before the registrations in these alone)
NOT_BY_FILE = {"ILCE-1M2": (0x023c, 0x11ab, 0x11ad)}

# the file sections of the body's memory slots (data/<camera>/camera_<camera>.json's memory_sets: on the a1 II Stills
# 1-3, Movie 4-6, S&Q 7-9, Time-lapse 10-12). A set section's records share one layout (the definition's set: keys), so
# NOT_BY_FILE's three are the same records in each; seen in section 1 (kit2_small_1109), and in a Movie, S&Q or
# Time-lapse section first by that family's first registration, whose own restore check (memreg_run's) counts every
# other record of the file (2026-11-21, branch memreg-slots)
MEMORY_SECTIONS = {"ILCE-1M2": tuple(range(1, 13))}

# the records that hold a user LUT in the camera, as keys ("global:0x0123"), named from a first import's run once its
# downloads have been looked at; none yet, so every record that does not go back after an import fails its restore
USER_LUT = {"ILCE-1M2": ()}


def memory_left(model: str) -> frozenset:
    """The keys ("set4:0x023c") of NOT_BY_FILE's records in each of the model's MEMORY_SECTIONS; empty for a model either
    does not name."""
    return frozenset(f"set{n}:0x{rid:04x}" for n in MEMORY_SECTIONS.get(model, ()) for rid in NOT_BY_FILE.get(model, ()))
