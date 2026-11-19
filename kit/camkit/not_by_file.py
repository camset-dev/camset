"""A memory slot's records that no settings file sets back, by model: an upload leaves them as the slot's last
registration wrote them. kit/provers/memreg_run.py expects them to differ after its restore, and kit/tools/upload_check.py
leaves them out of a restore by hand's count, in each of Memory 1-3's sections."""

# the slot's filled mark, its registration family and the exposure mode it was registered in (kit2_small_1109:
# 00159_restored.DAT and 00289_restored.DAT differ from the files before the registrations in these alone)
NOT_BY_FILE = {"ILCE-1M2": (0x023c, 0x11ab, 0x11ad)}
