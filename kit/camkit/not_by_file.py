"""Records that no settings file sets back, by model. A memory slot's (NOT_BY_FILE): an upload leaves them as the slot's
last registration wrote them; kit/provers/memreg_run.py expects them to differ after its restore, and
kit/tools/upload_check.py leaves them out of a restore by hand's count, in each of Memory 1-3's sections. A user LUT's
(USER_LUT): kit/tools/lut_import.py takes them, and only them, as the LUT's own state when they differ after its
restore (docs/decisions/0026); any other record that did not go back fails its restore."""

# the slot's filled mark, its registration family and the exposure mode it was registered in (kit2_small_1109:
# 00159_restored.DAT and 00289_restored.DAT differ from the files before the registrations in these alone)
NOT_BY_FILE = {"ILCE-1M2": (0x023c, 0x11ab, 0x11ad)}

# the records that hold a user LUT in the camera, as keys ("global:0x0123"), named from a first import's run once its
# downloads have been looked at; none yet, so every record that does not go back after an import fails its restore
USER_LUT = {"ILCE-1M2": ()}
