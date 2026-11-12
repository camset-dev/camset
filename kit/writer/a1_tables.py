"""The ILCE-1M2 firmware 4.00's own hand tables, which kit/schema_update.py applies to that definition alone (TODO:
into data/<model>_fw<fw>/camera_*.json, docs/decisions/0020): carousel options named by their option, records whose
name or note the camera proved wrong, records the menus never write found by hand (NEW_RECORDS, FRAME_PROOFS), label
fixes, the records a row proves but whose options do not name (KEEP_LABELS), and the layout's model appendix.
Every table is bound once (kit/tests/test_definitions.py checks it): a later binding would shadow the first for every
reader.

The file is public and holds what the camera is: names, value tables, structure, the notes that say what a record
holds, the writer's rules. Its evidence (each hand proof's values, run, day and menu row, a sample's count, the owner's
allowances, the runs and days and values seen that prove a note, what shows a not-offered mark, the day a reason was
settled) is the mapping's, kept in the private overlay (private/evidence/ILCE-1M2_fw4.00.hand.json, docs/decisions/0016)
and put back into these tables last (HAND_EVIDENCE, writer/hand_evidence.py). kit/tests/test_lean_tables.py keeps it
out of here."""
import re

from camkit import definitions, paths
from runner import read_json

from . import hand_evidence
from .mirror import mirror_key, mirror_of

# Carousel options are proved with whatever second-axis value the camera held ("Spot: <size>",
# "Self-timer(Cont.): <delay and shots>"). Where the record names only the option, its label is the
# option's name; the axis has its own record (not proved yet).
CAROUSEL = {
    ("global:0x0350", 2): "Spot", ("global:0x0e06", 2): "Spot",                     # Metering Mode
    ("global:0x0e68", 3): "Spot", ("global:0x0e6a", 3): "Spot", ("global:0x0e6c", 3): "Spot",
    ("global:0x0e68", 5): "Custom", ("global:0x0e6a", 5): "Custom", ("global:0x0e6c", 5): "Custom",
    ("global:0x02b5", 7): "Self-timer(Cont.)", ("global:0x1486", 6): "Self-timer(Cont.)",
    # here the part after the colon is the value itself: the screen's whole text is the label
    ("global:0x036f", 1): "D-Range Optimizer: Auto",
}

ISO_TABLE = "global:0x0334"
# proved records the schema lacked: key -> (the sibling it is laid out like, its name)
NEW_LIKE = {
    "global:0x0b63": ("global:0x0b65", "ISO Range Limit (upper)"),
    "global:0x0b67": ("global:0x0b69", "ISO Range Limit (upper)"),
    "global:0x0b6b": ("global:0x0b6d", "ISO Range Limit (upper)"),
    "global:0x04d0": ("global:0x04ce", "Interval (16 shots)"),
    # Different Set for Still/Mv: the movie side of White Balance and Picture Profile (Movie mode,
    # 2026-10-30), beside the stills side 0x0e0e / 0x0e12; whole labels ("Fluor.: Warm White")
    "global:0x0e10": ("global:0x0e0e", "White Balance (movie)"),
    "global:0x0e14": ("global:0x0e12", "Picture Profile (movie)"),
    # ISO AUTO Minimum in Movie mode (the box behind ISO > ISO AUTO, 2026-11-01) wrote 0x0dfa and this,
    # as Maximum wrote 0x0e00 and 0x0e04: the copy in use and Movie's
    "global:0x0dfe": ("global:0x0dfa", "ISO Auto Range Limit Min (movie)"),
    # the mode dial in S&Q mode (turned by hand, 2026-10-30), beside the
    # movie (0x13e1) and S&Q Motion (0x13e2) records: P 2, A 3, S 4, M 5; 0 until first written
    "global:0x13e3": ("global:0x13e2", "Exposure mode (time-lapse)"),
    # the slider (HDMI Info. Display Off, over the OSD, 2026-10-30) wrote 0x1476, not the guessed 0x1479
    "global:0x1476": ("global:0x1479", "Aspect Marker Level"),
    # S&Q's Record Setting (2026-10-31, each File Format and S&Q Rec Frame Rate switched by a file):
    # XAVC HS 4K and XAVC S HD keep one record at every rate; XAVC S 4K one per rate (60p 0x0254,
    # 30p 0x0256, 24p 0x0258, 120p 0x025a)
    "global:0x024e": ("global:0x0212", "Record Setting (S&Q, XAVC HS 4K)"),
    "global:0x025c": ("global:0x0220", "Record Setting (S&Q, XAVC S HD)"),
    "global:0x0258": ("global:0x0256", "Record Setting (S&Q, XAVC S 4K, 24p)"),
    "global:0x025a": ("global:0x0256", "Record Setting (S&Q, XAVC S 4K, 120p)"),
    # Movie mode's Record Setting, one record per File Format and Rec Frame Rate, in that order
    # (2026-10-31: the format loaded by a file, the rate chosen in the menu, 24p over the OSD).
    # XAVC HS 4K offers no 30p. 0x021e, XAVC S 4K at 120p, was an unmapped record that changed
    "global:0x0210": ("global:0x020e", "Record Setting (XAVC HS 8K, 24p)"),
    "global:0x0214": ("global:0x0212", "Record Setting (XAVC HS 4K, 24p)"),
    "global:0x0216": ("global:0x0212", "Record Setting (XAVC HS 4K, 120p)"),
    "global:0x021a": ("global:0x0218", "Record Setting (XAVC S 4K, 30p)"),
    "global:0x021c": ("global:0x0218", "Record Setting (XAVC S 4K, 24p)"),
    "global:0x021e": ("global:0x0218", "Record Setting (XAVC S 4K, 120p)"),
    "global:0x0222": ("global:0x0220", "Record Setting (XAVC S HD, 30p)"),
    "global:0x0224": ("global:0x0220", "Record Setting (XAVC S HD, 24p)"),
    "global:0x0226": ("global:0x0220", "Record Setting (XAVC S HD, 120p)"),
    # Playback Filter Condition's choosers (kit/provers/filter_run.py, 2026-11-07): each condition's value, laid out
    # like Image Order beside it; the box and the never-set flag of each are hand tables (FILTER_FLAGS)
    "global:0x12b0": ("global:0x12b7", "Playback Filter Condition: Still Images/Movies"),
    "global:0x12b3": ("global:0x12b7", "Playback Filter Condition: Shot Mark"),
    "global:0x12b4": ("global:0x12b7", "Playback Filter Condition: Protect"),
    "global:0x12b5": ("global:0x12b7", "Playback Filter Condition: Voice Memo"),
    "global:0x12c9": ("global:0x12b7", "Playback Filter Condition: FTP Transfer Status"),
    "global:0x12ca": ("global:0x12b7", "Playback Filter Condition: Smartphone Trans State"),
}
NEW_WHOLE_LABELS = {"global:0x0e10", "global:0x0e14", "global:0x024e", "global:0x025c", "global:0x0258", "global:0x025a"}
NEW_WHOLE_LABELS |= {f"global:0x{i:04x}" for i in (0x0210, 0x0214, 0x0216, 0x021a, 0x021c, 0x021e, 0x0222, 0x0224, 0x0226)}
NEW_WHOLE_LABELS |= {f"global:0x{i:04x}" for i in (0x12b0, 0x12b3, 0x12b4, 0x12b5, 0x12c9, 0x12ca)}

# records the camera writes only once their screen is first saved: until then they read 0 whatever
# the box shows (Rating Set: the 1-star box is ticked by default, 2026-10-29)
LATE_COPY = {rid: (" The second copy of this box: 0 until the Rating Set screen is first saved (or Rating is "
                   "put on a key), so a 0 in a file never saved there says nothing about the box; the first "
                   "copy (0x%04x) is the one to read." % (rid - 0x16bd + 0x0f96))
             for rid in range(0x16bd, 0x16c2)}

# records whose name or note the camera proved wrong, applied every run
RECORD_FIXES = {
    # Different Set for Still/Mv (2026-10-30): choosing in Stills mode writes these and the record in
    # use (0x0334 ISO, 0x0350 Metering, 0x0367 WB, 0x0053 PP); in Movie mode their movie twins
    # (0x0df4, 0x0e08, 0x0e10, 0x0e14) and the record in use; the mode switch loads the record in use
    "global:0x0df2": {"name": "ISO (stills)"},
    "global:0x0e06": {"name": "Metering Mode (stills)"},
    "global:0x0e08": {"name": "Metering Mode (movie)"},
    "global:0x0e0e": {"name": "White Balance (stills)"},
    "global:0x0e12": {"name": "Picture Profile (stills)"},
    # ISO AUTO's two boxes in Stills mode wrote the record in use and these (kit2_pass2, "[Stills mode]"): their Stills
    # copies, named as the other families' are, so no copy shares its setting's name
    "global:0x0dfc": {"name": "ISO Auto Range Limit Min (stills)"},
    "global:0x0e02": {"name": "ISO AUTO Max (stills)"},
    # Exposure Comp.'s two copies (COPIES; which mode's each is, is not known yet, COPY_MODES_UNKNOWN): named apart from
    # the setting and from each other, claiming no mode
    **{k: {"name": f"Exposure Comp. (copy {n})",
           "note": "A copy the camera keeps of Exposure Comp.; which shooting mode's it is, is not known yet."}
       for n, k in enumerate(("global:0x0e16", "global:0x13d6"), 1)},
    # ISO AUTO's two boxes in Movie mode (2026-11-01): each wrote the record in use and this one; the
    # camera keeps Minimum <= Maximum, raising Maximum when Minimum passes it
    "global:0x0e04": {"name": "ISO AUTO Max (movie)",
                      "note": "Movie mode's ISO AUTO Maximum. Setting Minimum above Maximum raises both "
                              "Maximum records to Minimum's value, and they stay there when Minimum comes back down."},
    # it follows S&Q Shoot Mode (0 S&Q Motion, 1 Time-lapse; S&Q mode, 2026-10-30), beside 0x13bf
    "global:0x118b": {"name": "S&Q Shoot Mode: Motion or Time-lapse"},   # "(second record)" until 2026-11-07
    # the a1 II's Help Guide (ilc/2440) lists PP1-PP6, PP10, PP11 and PPLUT1-4; the camera shows the
    # last four as User1-4 (with "(No Import)" until a LUT is imported), Movie mode only (2026-10-31)
    "global:0x0053": {"name": "Picture Profile",
                      "note": "No 7-9: PP7-PP9 are not on this body's menu (see their records). 12-15, offered in "
                              "Movie mode only, are the Help Guide's PPLUT1-PPLUT4: profiles that apply an imported "
                              "user LUT, shown as User1-User4."},
    **{f"set:0x{rid:04x}": {"name": f"Zone position memory (vertical {o}, grid index, copy {n})"}  # note: FRAME_PROOFS
       for o, n, rid in (("A", 1, 0x0f32), ("A", 2, 0x0f34), ("A", 3, 0x0f36))},   # B: NEW_RECORDS (2026-11-02)
    # a third Drive Mode record (2026-10-31): it takes 0x02b5's codes on every choice once Camera Settings Reset has
    # set 0x1126 to 7, and not before. Not 0x0b72 (loaded back by a file, 0x13d4 still moved)
    # named "Drive Mode (third record)" until 2026-11-07: a photographer's name, the mapping words in the note
    "global:0x13d4": {"name": "Drive Mode (menu choice)",
                      "note": "Takes the same codes as Drive Mode 0x02b5 when the drive mode is chosen from the "
                      "menu, on a body Camera Settings Reset has set 0x1126 to 7 on, which a file cannot set back: "
                      "a body never reset may not keep this record in step. A settings file sets it."},
    # proved with the mode dial (2026-10-30): no longer "probable"
    "global:0x13e2": {"name": "Exposure mode (S&Q Motion)"},
    # proved with the rest of Drive Mode Limit's list (kit2_pass2): "(inferred: next slot)" was the first guess's
    "global:0x13fd": {"name": "Drive Mode Limit: Single Shooting"},
    # the old crawl read the row's icon as a letter glued to its name ("SISO Range Limit", 2026-11-11): the row's own
    # words; the upper limits, added later (NEW_LIKE), are named so there too
    **{f"global:0x{_r:04x}": {"name": "ISO Range Limit"} for _r in (0x0b65, 0x0b69, 0x0b6d)},
    **{f"global:0x{_r:04x}": {"name": "ISO Range Limit (upper)"} for _r in (0x0b63, 0x0b67, 0x0b6b)},
    # found by hand (2026-10-30): DISP pressed while looking through the finder steps it,
    # beside the monitor's DISP Mode 0x04e5; registering memory slots set 0x11ad to the dial's mode
    # Focus Area Limit's grid (kit/provers/grid_run.py, 2026-10-30): every cell proved its record
    "global:0x01b0": {"name": "Focus Area Limit: Tracking: Zone"},
    "global:0x04e6": {"name": "Finder DISP Mode"},      # its values and note: FRAME_PROOFS (by hand, 2026-11-02)
    "set:0x11ad": {"name": "Memory slot exposure mode (stills registration)"},   # note: FRAME_PROOFS (2026-11-02)
    # registering a memory slot in S&Q Motion or Time-lapse writes 1 into the set's copy, which a file
    # then does not put back (sets 7 and 10, 2026-10-30)
    "global:0x0170": {"name": "S&Q Motion or Time-lapse active"},       # note: FRAME_PROOFS (2026-11-02)
    # setting C.Temp./Filter's temperature (2500-9900 K, 2026-10-30) wrote 0x0b91 and 0x0b93, never this
    "global:0x0b95": {"name": "WB Color Temp. (C.Temp./Filter, movie)"},   # note: FRAME_PROOFS (2026-11-02)
    # Movie mode's Aspect Marker set through the menu (runs/kit2_small_1109, kit/provers/mode_switch.py --set, 2026-11-09)
    "global:0x1479": {"name": "Unknown (beside Aspect Marker Level)",
                      "note": "Not Aspect Marker Level (0x1476), nor another marker type's level, nor Movie mode's "
                              "Aspect Marker, whose row is one list, Off and the ratios, writing 0x0326: none of them "
                              "writes it."},
    "global:0x1478": {"name": "Aspect Marker Disp."},           # OCR had glued an icon on ("ErAspect")
    # ISO AUTO Min. SS (2026-10-31): 0 in 0x0336 is the first option, an automatic speed, whose
    # Slower...Faster axis (Left/Right on it) is 0x04d2
    "global:0x04d2": {"name": "ISO AUTO Min. SS: automatic speed",
                      "note": "Used when ISO AUTO Min. SS (0x0336) is 0 (automatic); Right/Left on that option."},
    # S&Q's Record Setting with XAVC S 4K, one record per S&Q Rec Frame Rate (frame 117557 was at 30p);
    # HS 4K is 0x024e and S HD 0x025c at every rate
    "global:0x0256": {"name": "Record Setting (S&Q, XAVC S 4K, 30p)"},
    "global:0x0254": {"name": "Record Setting (S&Q, XAVC S 4K, 60p)"},
    # the movie records proved before the grid were each format's 60p one
    "global:0x020e": {"name": "Record Setting (XAVC HS 8K, 30p)"},
    "global:0x0212": {"name": "Record Setting (XAVC HS 4K, 60p)"},
    "global:0x0218": {"name": "Record Setting (XAVC S 4K, 60p)"},
    "global:0x0220": {"name": "Record Setting (XAVC S HD, 60p)"},
    # placed settings whose names still carried the mapping's words (2026-11-07): what they hold, in plain words
    **{f"global:0x{rid:04x}": {"name": f"Focus Area remembered ({o})"}
       for rid, o in ((0x0e68, "horizontal"), (0x0e6a, "vertical, grip down"), (0x0e6c, "vertical, grip up"))},
    # which Custom box (Custom 1-3, firmware 4.00's word for Free Size, as its values say) each holding remembers
    **{f"global:0x{rid:04x}": {"name": f"Custom area remembered ({o})"}
       for rid, o in ((0x1315, "horizontal"), (0x1317, "horizontal, copy 1"), (0x1319, "horizontal, copy 2"),
                      (0x1393, "horizontal, copy 3"), (0x131b, "vertical, grip down"),
                      (0x131d, "vertical, grip down, copy 1"), (0x131f, "vertical, grip down, copy 2"),
                      (0x1395, "vertical, grip down, copy 3"), (0x1321, "vertical, grip up"),
                      (0x1323, "vertical, grip up, copy 1"), (0x1325, "vertical, grip up, copy 2"),
                      (0x1397, "vertical, grip up, copy 3"))},
    "global:0x04e2": {
        "name": "Camera position state (not a setting)",
        "note": "Set by the camera, not by a loaded file: 1 with the camera level, 8 held vertically (grip down "
                "and grip up alike); a file holding 1, uploaded with the camera held vertically, downloads as 8."},
}
# records proved by a row whose options do not name their values: a flag several options share
# (File Format sets 0x16ae to 1 for every HD format and 8 for every 4K/8K one, Movie mode 2026-10-30)
KEEP_LABELS = {"global:0x16ae"}
# Reg. Custom Shoot Set (2026-10-30): a hold's ISO keeps the schema's fuller names ("ISO 50 (multi-frame
# NR)"); its Exposure Comp. counts quarter stops down from 20, so the whole scale is named by that rule
# (EV_DOWN_FROM_20) rather than value by value: -0.3 stored 21, +4.7 stored 1
EV_DOWN_FROM_20 = {f"global:0x0bf9[{i}]" for i in range(3)}
KEEP_LABELS |= {f"global:0x0c01[{i}]" for i in range(3)} | EV_DOWN_FROM_20
# Exposure Std. Adjust (2026-10-30): proved by Up/Down counts from ±0 (+6/6 stored 0, -6/6 12, +2/6 4),
# so its proofs carry counts, not the camera's words; the schema's sixths in lowest terms stand
KEEP_LABELS |= {"global:0x0346", "global:0x0348", "global:0x034a", "global:0x034c", "global:0x034e"}
# Proxy Rec. Settings: 16M (0) and 9M (1) proved under Proxy File Format XAVC HS HD (runs/kit2_pass2, 2026-10-29),
# their labels kept as the definition has them, 1's naming the proxy format it was proved under. Code 3, with its
# label "9M 4:2:0 10bit (XAVC S HD)", has been in the list since the first definition, and no proof names it, so it
# stays offered in Expert mode only. The crawl (runs/kit2_crawl_proxy_shd, 2026-11-08) shows only that under one main
# movie File Format the row is greyed and shows 6M 4:2:0 8bit, whatever the record holds: it neither proves nor
# contradicts code 3's label. The row's options under each main movie File Format are open. The note, which said "9M
# was stored as 3" from the first definition with no source here, is written here so a regeneration keeps its words.
# Which formats and states the camera was in for the crawl, and what the record held, are the camera's own settings
# and not said (decision 16)
KEEP_LABELS |= {"global:0x0284"}
# Proof contexts in other words (writer/proofs.menu_row renames the passes' rows and a row the definition kept): session
# B's hand-recorded JPEG/HEIF Switch line named the slot Recording Media was on as found; it says "on one slot" now
# (2026-11-09), which is what the proof needs, and no slot is named here either. The S&Q rows of October named the S&Q
# switch's family mode as the camera was found ("S&Q mode (…)"); "S&Q mode" is what those rows need, and the pattern
# takes either family mode, so neither is singled out. Recording Media on either two-slot state (Sort Recording,
# Simult. Recording) says "on both slots" for the same reason: which of the two the camera was set to is the owner's
# (decision 16, 2026-11-09). AF Area Registration's runs of 2026-11-09 tagged two of their attempts with what the
# last-left records were to show ("Spot size last left: ...", "Custom slot last left: ..."), which the registrations do
# not need and which may follow from the area the camera held at the run's start: "Switch V/H AF Area Off" is what they
# need. A context that says its state was found goes for every camera (writer/proofs.py, AS_FOUND)
CONTEXT_WORDS = {r"Recording Media Slot \d+": "Recording Media on one slot",
                 r"Recording Media (?:Sort|Simult\.) Recording": "Recording Media on both slots",
                 r"S&Q mode \((?:Time-lapse|S&Q Motion)\)": "S&Q mode",
                 r"Switch V/H AF Area Off, (?:Spot size|Custom slot) last left: [^\]]*": "Switch V/H AF Area Off"}
# Image Jump Setting's three dials: each list walked whole on its own row (runs/kit2_pass2, 2026-10-29). The note kept
# from the first schema said how the Front dial was told apart before then, from the value a file held, which is the
# camera's own setting (decision 16): replaced
for _k, _n in (("global:0x03d1", "Front dial"), ("global:0x03d2", "Rear Dial L"), ("global:0x03d3", "Rear Dial R")):
    RECORD_FIXES[_k] = {"name": _n, "note": "Jump method for this dial in playback; the three dials share one list."}
RECORD_FIXES["global:0x0284"] = {
    "name": "Proxy Rec. Settings",
    "note": "Movie menu only. Under Proxy File Format XAVC HS HD the list offers 16M 4:2:0 10bit (0) and 9M 4:2:0 "
            "10bit (1). Code 3, in the list since the first definition, is named by no proof. Under one main movie "
            "File Format the row is greyed and shows 6M 4:2:0 8bit, whatever the record holds. Which options the row "
            "offers under each main movie File Format is open."}
# Playback Filter Condition (kit/provers/filter_run.py, 2026-11-07): choosing a condition ticks its box (a record
# each, 1), writes its value (NEW_LIKE above) and clears a flag that read 1 until the condition was first set; Rating's
# grid ticks one record per star box. The options name the value, not these: hand tables (KEEP_LABELS).
FILTER_ITEMS = {0x1290: ("Still Images/Movies", 0x12ba), 0x1293: ("Shot Mark", 0x12bd), 0x1294: ("Protect", 0x12be),
                0x1295: ("Rating", 0x12bf), 0x1296: ("FTP Transfer Status", 0x12c0),
                0x1297: ("Smartphone Trans State", 0x12c1), 0x1298: ("Voice Memo", 0x12c2)}
FILTER_STARS = dict(zip(range(0x1282, 0x1288), ["★", "★★", "★★★", "★★★★", "★★★★★", "★OFF"], strict=True))
TICK_VALUES = [[0, "Not ticked"], [1, "Ticked"]]
FILTER_FLAGS = {}
for _rid, (_item, _never) in FILTER_ITEMS.items():
    FILTER_FLAGS[f"global:0x{_rid:04x}"] = {
        "like": "global:0x12b7", "name": f"Playback Filter Condition: {_item} (box)", "values": TICK_VALUES,
        "note": f"The box of the {_item} condition on the Playback Filter Condition screen: choosing a value ticks it, "
                f"Enter on the ticked box unticks it and keeps the value."}
    FILTER_FLAGS[f"global:0x{_never:04x}"] = {
        "like": "global:0x12b7", "name": f"Playback Filter Condition: {_item} never set", "values": [[0, "Set once"], [1, "Never set"]],
        "note": f"1 until a value is first chosen for the {_item} condition, 0 from then on whatever the box. "
                f"A settings file sets it."}
for _rid, _star in FILTER_STARS.items():
    FILTER_FLAGS[f"global:0x{_rid:04x}"] = {
        "like": "global:0x12b7", "name": f"Playback Filter Condition: Rating {_star} (box)", "values": TICK_VALUES,
        "note": f"The {_star} box of the Rating condition's grid on the Playback Filter Condition screen. "
                f"Ticking it also writes the rating's second copy (0x{0x16bd + _rid - 0x1282:04x}), as Rating Set(Custom "
                f"Key)'s box of the same star does."}
KEEP_LABELS |= set(FILTER_FLAGS)
# the ratings' second copies (0x16bd-0x16c2): Rating Set(Custom Key)'s boxes mirror them and the filter's Rating grid
# writes them too, one per star box; the filter's options name the star, not the copy's value
KEEP_LABELS |= {f"global:0x{_r:04x}" for _r in range(0x16bd, 0x16c3)}
# values the proofs name with something that is not the value's own: Movie mode's Metering Mode list
# shows Spot with its size, which is a record of its own (0x04d4); its stills twins say "Spot"
VALUE_FIXES = {("global:0x0e08", 2): "Spot",
               ("global:0x118b", 1): "Time-lapse",      # the interval icon read as "4e"
               ("global:0x03a7", 7): "Airplane",        # the camera's word; the report took "Plane" as agreeing
               ("global:0x0336", 0): "Automatic (Slower to Faster)",
               # S&Q's Record Setting with XAVC S 4K: the screen's wording, as its siblings have it
               ("global:0x0256", 14): "140M 4:2:2 10bit",
               ("global:0x0256", 18): "100M 4:2:0 8bit",
               ("global:0x0256", 22): "60M 4:2:0 8bit",
               # the camera shows no space before "(" in both (frame kit2_pass3_autoframe2 00012)
               ("global:0x1172", 2): "Auto Start(15s swtc)",
               # the drive mode, not the carousel's title with its second axis ("...: Lo", "...: 10 Sec. 3
               # Img."): the step is a record of its own (0x04ca, 0x04c4)
               ("global:0x02b5", 11): "White Balance Bracket", ("global:0x1486", 10): "White Balance Bracket",
               ("global:0x13d4", 11): "White Balance Bracket", ("global:0x13d4", 7): "Self-timer(Cont.)",
               # two card-slot icons with 1 and 2 in them before the words (frame kit2_pass2 37388_down, 2026-11-07):
               # the map read them "⏮ / ⏭", the bar's OCR "1/7"; the vision model's "1 / 2" is what the icons show
               ("global:0x13bb", 1): "1 / 2 This Image"}
# records the menus never write, found by hand on the camera (2026-10-30); added when missing, laid
# out from the latest download, the other fields like `like`
NEW_RECORDS = {
    **FILTER_FLAGS,
    "global:0x16c2": {"like": "global:0x16c1", "name": "Playback Filter Condition: Rating ★OFF (copy)", "values": TICK_VALUES,
                      "note": "The second copy of the Rating condition's ★OFF box (0x1287), written as the ★-★★★★★ "
                              "copies 0x16bd-0x16c1 are, which Rating Set(Custom Key) shares."},
    "set:0x023c": {"like": "set:0x0b8d", "name": "Memory slot filled", "values": [[2, "Empty"], [4, "Registered"]],
                   "note": "2 in a slot never registered (as Initialize leaves it); registering the slot in any "
                           "family writes 4. Sets 1-3 are the Stills slots 1-3, 4-6 Movie's, 7-9 S&Q Motion's, "
                           "10-12 Time-lapse's; M1-M4 go to the card, not this file. A settings file does not set "
                           "it."},
    "set:0x11ab": {"like": "set:0x0b8d", "name": "Memory slot registration family",
                   "values": [[0, "Stills"], [1, "Not written (empty, or Movie)"], [4, "S&Q Motion or Time-lapse"]],
                   "note": "Written when the slot is registered: 0 in Stills mode, 4 in S&Q Motion and Time-lapse; "
                           "a Movie-mode registration (sets 4-6) leaves it 1, as Initialize does. A settings file "
                           "does not set it."},
    "global:0x18cb": {"like": "global:0x04e5", "name": "Recall Custom hold: registration working copy",
                      "values": [], "note": "4 slots: Recall Custom hold 1-3 and a fourth that copies whichever "
                      "hold's registration screen was opened last. Uploading a file does not set the fourth slot."},
    # a hold's bracket: Register copies the live Cont. / Single Bracket setting as its place in the live list from 0 (the
    # live codes skip 13, 20, 42 and 60); the live settings set by a file, 2026-10-31, values below. The first
    # registrations copied the live settings as the camera was found, the camera's own (decision 16): not listed
    "global:0x0e80": {"like": "global:0x04e5", "name": "Recall Custom hold: Cont. Bracket setting", "values": [],
                      "note": "4 slots: Recall Custom hold 1-3 and the registration working copy. Registering Cont. "
                      "Bracket in a hold copies the live Cont. Bracket setting (0x04c6) here, numbered by its place "
                      "in the live list from 0: live 3, 10, 14, 19 and 43 wrote 2, 9, 12, 17 and 39. "
                      "The hold's screen shows only \"Cont. Bracket\"; the step and images are these."},
    "global:0x0e84": {"like": "global:0x04e5", "name": "Recall Custom hold: Single Bracket setting", "values": [],
                      "note": "4 slots, as 0x0e80. Registering Single Bracket in a hold copies the live Single Bracket "
                      "setting (0x04c8) here, numbered by its place in the live list from 0: live 1, 3, 21 and 64 "
                      "wrote 0, 2, 18 and 59."},
    **{f"set:0x{rid:04x}": {"like": "set:0x0f0b", "name": f"Zone position memory (grid index, copy {n})", "values": [],
                            "note": ""} for n, rid in ((5, 0x0f2c), (6, 0x0f2e), (7, 0x0f30))},
    "global:0x0c09": {"like": "global:0x04e5", "name": "Recall Custom hold: registration stamp", "values": [],
                      "note": "4 slots: Recall Custom hold 1-3 and the registration working copy (as 0x18cb). Every "
                      "Register writes 29 into its hold's slot and the working copy. What 29 stands for is not known. "
                      "A settings file sets it. View only."},
    "global:0x1126": {"like": "global:0x04e5", "name": "Unknown camera state (not a menu setting)", "values": [],
                      "note": "Camera Settings Reset and Initialize both set 7, and an uploaded file does not set it. "
                              "Not the DISP layouts, not the Fn cursor, not an SDK property. Once it is 7, choosing a "
                              "drive mode also writes 0x13d4."},
}
# PP7's preset values, outside this body's Gamma and Color Mode lists: named from the first a1's PP7
# (S-Log2 / S-Gamut), which shares the file's profile layout; the ILCE-1M2 refuses them in PP1
PP7_VALUES = {("global:0x052b[6]", 15): "S-Log2 (the first a1's PP7; not offered on this body)",
              ("global:0x073b[6]", 11): "S-Gamut (the first a1's PP7; not offered on this body)"}
# Focus frame positions (2026-10-31): moving the frame on the shooting screen changes no live record;
# registering a memory slot (Stills slot 3 = set 3) copies the position into the set. Nine zone
# positions and two spot moves, registered one by one (runs/kit2_frame_reg)
ZONE = [[0, "Centre"], [1, "Up"], [2, "Right"], [3, "Left"], [4, "Down"], [5, "Lower right"], [6, "Lower left"],
        [7, "Upper left"], [8, "Upper right"]]
ZONE_NOTE = ("The Zone focus area's place on its 3 x 3 grid, written only when a memory slot is registered: moving "
             "the zone on the shooting screen changes no live record. With Switch V/H AF Area Off a registration "
             "writes the place into these six records and the six vertical copies alike, and a Tracking zone keeps "
             "its place here too.")
# the frame positions run was made with the owner's word for Camera Set. Memory (framepos_run.py --allow): every record
# whose note takes its facts says so in its evidence (the hand evidence's "allowance"), as the records its proof lines
# credit do
# the frame run of 2026-10-31 moved the point under Focus Area Spot only (runs/kit2_frame/drive.jsonl chooses Spot three
# times and never Expand Spot); the frame positions run below moved it under Expand Spot too
# the frame positions run (kit/provers/framepos_run.py, runs/kit2_framepos, 2026-11-09; framepos.jsonl): with Switch V/H
# AF Area Off, under each Spot size and Expand Spot, three Left and two Up presses on the shooting screen, Stills slot 1
# registered before and after, moved all eight point records alike (the current X and Y, and the level, grip-down and
# grip-up copies), Spot S, M, L and XL and Expand Spot by one step and Spot XS by a smaller one, and the frame put back
# registered as before. Only the presses and the moves are said: where the point stood is the camera's own setting
# (docs/decisions/0016), and so is the AF Frame Move Amt that run left as the camera had it. The step run
# (framepos_run.py --frame-move-amt, runs/kit2_framepos_amt, 2026-11-09; contexts "Switch V/H AF Area Off, camera
# level, AF Frame Move Amt Standard" and "... Large") set AF Frame Move Amt by the menu, Standard for one session and
# Large for the other, and measured the steps the same way, every copy of a record moving alike: FRAME_STEPS holds
# them, and the notes' step sentences (STEP_FACTS) are built from it alone. The Tracking areas (Focus Mode on
# Continuous AF by the menu, kit2_framepos's later session) moved the same records as their plain areas: Tracking: Spot
# M and Tracking: Expand Spot the eight point records, Tracking: Zone the twelve zone records, Tracking: Custom 1 Custom
# 1's box records; no record moved for a Tracking area alone
# the steps a press moved a frame, {(AF Frame Move Amt's option, area): (X, Y) a press}: the spots' from their three Left
# and two Up presses in the step run; Custom 1's box's by one press each way, Right, Left, Up and Down, under each
# option (framepos_run.py --moves, runs/kit2_framepos_amt_one, 2026-11-09): opposite presses moved it by the same step,
# its ten records alike, and every put-back matched
FRAME_STEPS = {("Standard", "Spot M"): (30, 20), ("Standard", "Spot XS"): (20, 20),
               ("Large", "Spot M"): (60, 38), ("Large", "Spot XS"): (36, 32),
               ("Standard", "Custom 1"): (28, 19), ("Large", "Custom 1"): (56, 38)}
_SM, _SXS, _LM, _LXS, _SB, _LB = (FRAME_STEPS[k] for k in (("Standard", "Spot M"), ("Standard", "Spot XS"),
                                                            ("Large", "Spot M"), ("Large", "Spot XS"),
                                                            ("Standard", "Custom 1"), ("Large", "Custom 1")))
# the step sentences, each in the notes word for word: "point" in the spot's notes, "box" in the Custom boxes', "all" in
# AF Frame Move Amt's and in the model page's Focus frame position row (a test holds them to FRAME_STEPS)
STEP_FACTS = {
    "point": (f"Under AF Frame Move Amt Standard a press moved Spot M's point {_SM[0]} in X and {_SM[1]} in Y and "
              f"Spot XS's {_SXS[0]} and {_SXS[1]}; under Large Spot M's point {_LM[0]} in X and {_LM[1]} in Y and "
              f"Spot XS's {_LXS[0]} and {_LXS[1]}"),
    "box": (f"Under AF Frame Move Amt Standard a press moved Custom 1's box {_SB[0]} in X and {_SB[1]} in Y, and "
            f"under Large {_LB[0]} in X and {_LB[1]} in Y, twice Standard's both ways"),
    "all": (f"under Standard a press moved Spot M's point {_SM[0]} in X and {_SM[1]} in Y, Spot XS's {_SXS[0]} and "
            f"{_SXS[1]}, and Custom 1's box {_SB[0]} and {_SB[1]}; under Large Spot M's point {_LM[0]} in X and "
            f"{_LM[1]} in Y, Spot XS's {_LXS[0]} and {_LXS[1]}, and the box {_LB[0]} and {_LB[1]}, twice Standard's")}
FRAMEPOS_POINT = (" With Switch V/H AF Area Off, Left and Up presses under Spot S, M, L, XL and XS and under Expand Spot "
                  "moved all eight point records together, the current X and Y and the level, grip-down and grip-up "
                  "copies: each press moves the point by a step AF Frame Move "
                  "Amt sets, the same for Spot S, M, L and XL and Expand Spot and smaller for Spot XS, Left lowering X "
                  "and Up lowering Y. " + STEP_FACTS["point"] + ". Under Tracking: Spot M and Tracking: Expand Spot the "
                  "same presses moved the same records the same way: a Tracking area keeps its frame's place in its "
                  "plain area's records.")
AF_NOTE = ("The Spot focus point on the 640 x 480 grid (320, 240 = centre), written only when a memory slot is "
           "registered: moving the point on the shooting screen changes no live record. With Focus Area on Spot, a "
           "Left press lowered X and an Up press lowered Y (the vertical copies kept theirs). Expand Spot keeps its "
           "point in the same records." + FRAMEPOS_POINT)
# each hand proof's values, sample count, run, day and menu row, and the owner's allowance, are the hand evidence's
FRAME_PROOFS = {**{k: {"values": ZONE, "note": ZONE_NOTE}
                   for k in ("set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f2c", "set:0x0f2e", "set:0x0f30")},
                **{k: {"note": AF_NOTE} for k in ("set:0x019c", "set:0x01be", "set:0x019e", "set:0x01c4")}}
# A memory's exposure (2026-10-31): 1/250 F5.6, 1/500 F8 and 1/60 F11 set through the SDK, each followed by
# registering Stills slot 3: set 3's block (0x0180) and memory 3's block of the live mirror (0x018c, +640)
# took them alike (runs/kit2_exposure_reg). The other memories' blocks share the layout
EXPOSURE_NOTES = {
    288: "F-number x 100: F5.6 560, F8 800, F11 1100.",
    290: "The shutter speed's numerator (1 for 1/250, 1/500, 1/60).",
    292: "The shutter speed's denominator: 250, 500, 60 for 1/250, 1/500, 1/60.",
    260: "APEX Av + 16, in 256ths: F8 5632 (22.0), F11 5888 (23.0), one stop apart. 0 when the aperture had not "
         "been set since the file was loaded.",
    262: "APEX Tv + 16, in 256ths: 1/500 6400 (25.0), 1/60 5632 (22.0), three stops apart. 0 when the shutter "
         "speed had not been set since the file was loaded.",
}
for off, note in EXPOSURE_NOTES.items():
    line = note + " Written when the memory is registered."
    FRAME_PROOFS[f"set:0x0180@{off}"] = {"note": line}
    FRAME_PROOFS[f"global:0x018c@{640 + off}"] = {"note": line + " The live copy of memory 3's block."}
    # slots 1 and 2, each registered at 1/500 F8 and 1/60 F11 in turn: only the registered slot's block
    # moved (runs/kit2_exposure_reg12, 2026-11-01)
    for slot in (1, 2):
        FRAME_PROOFS[f"global:0x018c@{320 * (slot - 1) + off}"] = {
            "note": note + f" Written when Stills slot {slot} is registered. The live copy of memory {slot}'s block."}
# set through the Camera Remote SDK's own setters, each value read back and downloaded, the original set
# back after (sdk_probe.py, runs/kit2_sdk_probe, Movie mode, 2026-11-01; the script is in the maintainers'
# private/ archive since 2026-11-04): each moved one record
FRAME_PROOFS.update({
    "global:0x10fd": {"note": "The movie self-timer's Rec Start delay: 3 s 1, 5 s 2, 10 s 3.",
                      "values": [[1, "3"], [2, "5"], [3, "10"]]},
    "global:0x10ff": {"note": "The movie self-timer's Repetition: Only Once 0 (the SDK's Off), Repeat 1 (On).",
                      "values": [[0, "Only Once"], [1, "Repeat"]]},
    "global:0x10ac": {"note": "Focus Bracket's Step Width (1-10), stored as the number."},
    "global:0x10aa": {"note": "Focus Bracket's Number of Shots, stored as the number."},
    "global:0x04e5": {"note": "The DISP display mode on the monitor: Display All Info 0, No Disp. Info 1, Histogram 2, "
                      "Level 3 (the SDK's 2-5; For Viewfinder 4 was not offered in Movie mode). A settings file does "
                      "not restore it.",
                      "values": [[0, "Display All Information"], [1, "No Display Information"], [2, "Histogram"],
                                 [3, "Level"], [4, "For Viewfinder"]]},
})
# the Screen Reader's settings, chosen in its menu with the reader Off, which is silent: Volume taken down
# first, the owner's value back last (kit/drive.py, runs/kit2_screenreader, 2026-11-01; 0 records differ after)
# Fast 4 sits above Fast 3 when the list scrolls (2026-11-02)
SR_SPEED = [[0, "Fast 4"], [1, "Fast 3"], [2, "Fast 2"], [3, "Fast 1"], [4, "Standard"], [5, "Slow 1"], [6, "Slow 2"]]
FRAME_PROOFS.update({
    "global:0x0478": {"note": "The Screen Reader's speed, fastest first.", "values": SR_SPEED},
    "global:0x0e37": {"note": "A copy of the Screen Reader's Speed (0x0478): every choice wrote both.",
                      "values": SR_SPEED},
    # proved since on the camera by kit/provers/scale_run.py, every value (runs/kit2_pass2, the owner having allowed
    # the row remotely, the Screen Reader itself not switched): a note only, the report's proof standing
    "global:0x0479": {"note": "The Screen Reader's Volume, 0-15, stored the other way round (15 - the volume): 0 was "
                      "15, 15 was 0."},
    "global:0x13ca": {"note": "MENU Long Press to Switch: by its name, holding MENU switches the Screen Reader on "
                      "or off (not tried). On 0, Off 1.", "values": [[0, "On"], [1, "Off"]]},
    # On only with headphones in and Volume 0 first (the owner's rule; headphones confirmed 2026-11-02)
    "global:0x0477": {"note": "The Screen Reader itself: On 0, Off 1.", "values": [[0, "On"], [1, "Off"]]},
})
# changed by hand by the owner while kit/tools/hdmi_watch.py --each downloaded after every option screen closed;
# each value read off the frame of the option chosen (runs/kit2_hdmi_watch, 2026-11-02). These stay by hand
# (sound, light, connections, the Delete page). Touch Func. in Shooting and Finder Frame Rate are greyed
# with HDMI connected: changed with the cable out, watched through the OSD
VOL15 = sorted([15 - v, str(v)] for v in range(16))
TOUCH_AE = [[0, "AE OFF"], [1, "AE ON"]]
for _k, _vals, _note in (
        ("global:0x0385", [[0, "Auto"], [1, "Off"]], "AF Illuminator."),
        ("global:0x048d", [[0, "On:all"], [1, "On:w/o shutter"], [2, "On:shutter only"], [3, "Off"]],
         "Audio Signal(Shooting)."),
        ("global:0x101a", [[0, "On"], [1, "Off"]], "Audio Signal(Start/End)."),
        ("global:0x047b", [[1, "Manual"], [2, "Sunny Weather"]], "The monitor's Brightness Setup."),
        ("global:0x049e", [[0, "Power Link"], [1, "REC Link"], [2, "REC Link&STBY"], [3, "Auto"]],
         "Video Light Mode; 0x18e4 is written with it."),
        ("global:0x18e4", [[0, "Power Link"], [1, "REC Link"], [2, "REC Link&STBY"], [3, "Auto"]],
         "A copy of Video Light Mode (0x049e): every choice wrote both."),
        ("global:0x046f", [[0, "Off"], [1, "Multi-Selector Only"], [2, "Dial + Wheel"], [3, "All"]],
         "Lock Operation Parts."),
        ("global:0x13ba", [[0, "Select When Exec"], [1, "Delete Both"], [2, "Del. Select Only"]],
         "Delete Slot1/2 (a setting on the Delete page)."),
        ("global:0x1722", [[0, "Enable"], [1, "Disable"]], "Wake On LAN."),
        ("global:0x0076", [[0, "Off"], [1, "On"]], "Bluetooth Function; 0x0401 holds it the other way round."),
        ("global:0x0401", [[0, "On"], [1, "Off"]],
         "Bluetooth Function, the other way round from 0x0076: every choice wrote both."),
        ("global:0x0480", [[0, "Standard"], [1, "High"], [2, "Higher"]],
         "Finder Frame Rate (greyed with HDMI connected)."),
        ("global:0x1195", TOUCH_AE,
         "Touch Focus's AE OFF / AE ON, the carousel's second axis (Touch Func. in Shooting itself is 0x0476)."),
        ("global:0x1196", TOUCH_AE,
         "Touch Tracking's AE OFF / AE ON, the carousel's second axis (Touch Func. in Shooting itself is 0x0476)."),
        ("global:0x1197", TOUCH_AE,
         "Touch Shutter's AE OFF / AE ON, the carousel's second axis (Touch Func. in Shooting itself is 0x0476)."),
):
    FRAME_PROOFS[_k] = {"note": _note, "values": _vals}
# The three volume scales changed by hand that day are proved since on the camera by kit/provers/scale_run.py, every
# value (runs/kit2_pass2, the owner having allowed each row remotely): only their notes are here, and the report's
# proof stands, each value named by its readers (a hand table's values or proof would put its own over it)
FRAME_PROOFS["global:0x0051"] = {
    "note": "Playback/Monitor. Vol., 0-15, stored the other way round (15 - the volume): 0 was 15, 15 was 0."}
FRAME_PROOFS["global:0x03c4"] = {
    "note": "Voice Memo Play Vol., 0-15, stored the other way round (15 - the volume): 0 was 15, 15 was 0."}
FRAME_PROOFS["global:0x12c8"] = {
    "note": "Audio Signal Volume, 0-5, stored the other way round (5 - the volume): 0 was 5, 5 was 0."}
# A put-back is no sample: a value a round started from and put back is the camera's own setting (docs/decisions/0016),
# so the hand tables list only the values a round chose
# Monitor Brightness's manual level, with Brightness Setup on Manual: the hand round (2026-11-02) chose -2, and
# kit/drive.py chose -1 on the slider (runs/kit2_small_1109, 2026-11-09), the owner having allowed the brightness rows
# remotely that day; every value is proved since by kit/provers/scale_run.py --panel-row (runs/kit2_pass2): the note
# and that day's allowance only, the report's proof standing and naming each value (-2, -1, ±0, +1, +2)
FRAME_PROOFS["global:0x0052"] = {
    "note": "The monitor's manual brightness, with Brightness Setup on Manual: -2 is 0, +2 is 4."}
NEW_RECORDS.update({
    "global:0x1195": {"like": "global:0x0476", "name": "Touch Focus: AE", "values": TOUCH_AE, "note": ""},
    "global:0x1196": {"like": "global:0x0476", "name": "Touch Tracking: AE", "values": TOUCH_AE, "note": ""},
    "global:0x1197": {"like": "global:0x0476", "name": "Touch Shutter: AE", "values": TOUCH_AE, "note": ""},
})
# Self-timer Type, a two-axis carousel open with the Drive Mode dial on the self-timer (by hand, 2026-11-02):
# the type, and each type's own second axis, every value read off the carousel frame (Cont.'s last three by
# the strip's order: 10s C3, 10s C5, 5s C3, 5s C5, 2s C3, 2s C5)
SINGLE_DELAY = [[0, "10 sec"], [1, "5 sec"], [2, "2 sec"]]
CONT_SHOTS = [[0, "10 Sec. 3 Img."], [1, "10 Sec. 5 Img."], [2, "5 Sec. 3 Img."], [3, "5 Sec. 5 Img."],
              [4, "2 Sec. 3 Img."], [5, "2 Sec. 5 Img."]]
for _k, _vals, _note in (
        ("global:0x02bd", [[0, "Self-timer (Single)"], [1, "Self-timer (Cont)"]], "Self-timer Type: Single or Cont."),
        ("global:0x13ef", SINGLE_DELAY, "Self-timer Type's Single delay, its carousel's second axis."),
        ("global:0x13f1", CONT_SHOTS, "Self-timer Type's Cont. delay and shots, its carousel's second axis.")):
    FRAME_PROOFS[_k] = {"note": _note, "values": _vals}
# the registered lens list is Preset Focus/Zoom's: six slots, presets 1-5 by a custom key held down and 6 by a
# lens's Function Ring (Help Guide). Registering preset 1 (Custom Key/Dial Set., hold the key; by hand, 2026-11-02)
# rewrote slot 1. The lenses each preset was registered with, and what they wrote, are the hand evidence's (the owner
# lets the lens names be public, but they say how the notes were found); what a slot held before a registration is not
# said anywhere (decision 16)
PRESET = (" Preset Focus/Zoom's six slots: 1-5 registered by a custom key held down, 6 by a lens Function Ring. "
          "Mounting a lens or loading a file writes nothing here.")
for _k, _name, _note in (
        ("global:0x167c", "Preset Focus/Zoom: lens name", "Each slot's lens name; a teleconverter is added to it "
                                                          "(the lens's name, then \" + 2X Teleconverter\")."),
        ("global:0x16a1", "Preset Focus/Zoom: lens serial number", "Each slot's lens serial number: a preset recalls "
                                                                   "only on the very lens it was registered with. A "
                                                                   "teleconverter leaves it the lens's."),
        ("global:0x1694", "Preset Focus/Zoom: focal length (mm)", "The focal length when the preset was registered, "
                                                                 "a teleconverter included."),
        ("global:0x1682", "Preset Focus/Zoom: focus position (probable)", ""),
        ("global:0x1688", "Preset Focus/Zoom: zoom position (probable)", "No zoom position registered reads 65536000 "
                                                                         "or -1, by the lens."),
        ("global:0x1732", "Preset Focus/Zoom: focal length x 10", "0x1694 in tenths of a millimetre."),
        ("global:0x1437", "Preset Focus/Zoom: slot flag A", "3 with a zoom, 1 with a prime; 0 in a slot never "
                                                            "registered."),
        ("global:0x16f3", "Preset Focus/Zoom: slot flag B", "2 with a zoom, 3 with a prime and in a slot never "
                                                            "registered."),
        ("global:0x168e", "Preset Focus/Zoom: lens data C", "Written on registering; its meaning is not known."),
        ("global:0x172c", "Preset Focus/Zoom: lens data D", "Written on registering, as 0x168e; an APS-C or A-mount "
                                                            "lens might tell what it holds."),
        ("global:0x0b75", "Preset Focus/Zoom: slot registered", "1 in a registered slot.")):
    FRAME_PROOFS[_k] = {"note": (_note + PRESET).strip()}
    NEW_RECORDS[_k] = {"like": "global:0x167c", "name": _name, "values": [], "note": ""}
NEW_RECORDS.update({
    "global:0x13ef": {"like": "global:0x02bd", "name": "Self-timer(Single): delay", "values": SINGLE_DELAY, "note": ""},
    "global:0x13f1": {"like": "global:0x02bd", "name": "Self-timer(Cont.): delay and shots", "values": CONT_SHOTS,
                      "note": ""},
})
# Movie mode's Audio Rec Level, a 0-31 slider (kit/drive.py --confirm: its footer offers Reset on another key,
# OK only on the value wanted; runs/kit2_unattended, 2026-11-02): the level as itself, the start put back last. Both
# ends and a middle lie on the line, so the scale is sampled (KIT_PLAN's line rule; "linear" is checked by the writer),
# and the level put back is no sample: it is the camera's own setting (docs/decisions/0016)
FRAME_PROOFS["global:0x0018"] = {
    "note": "Audio Rec Level, 0-31, stored as the level itself.", "values": [[v, str(v)] for v in range(32)]}
# Focus Area's Custom 1-3 boxes (Free Size before firmware 4.00): their size lives only in the memory sets. The
# box's editor (Focus Area, Custom lit, SET = C4, the owner's go-ahead) changed one side, then Stills slot 1
# was registered and diffed (runs/kit2_freesize, 2026-11-02; the start file put back after, 0 records differ).
# Height and width in the 640 x 480 screen's units; one click of the front dial changes the height by 4, and three
# clicks of the rear dial L change the width by 16 (16/3 a click: the clicks are not all the same). The sizes the
# boxes had and were set to are the owner's, in the hand evidence with each record's sample count
BOX = " Kept only in the memory sets: a slot holds the sizes it was registered with."
for _k, _name, _note in (
        ("set:0x14b4", "Custom 1 box: height", "Custom 1's height (set with the front dial, 4 units a click)."),
        ("set:0x14b6", "Custom 1 box: width", "Custom 1's width (set with the rear dial L, 16 units every three clicks)."),
        ("set:0x14b8", "Custom 2 box: height", "Custom 2's height (set with the front dial, 4 units a click)."),
        ("set:0x14ba", "Custom 2 box: width", "Custom 2's width (set with the rear dial L, 16 units every three clicks)."),
        ("set:0x14bc", "Custom 3 box: height", "Custom 3's height (set with the front dial, 4 units a click)."),
        ("set:0x14be", "Custom 3 box: width", "Custom 3's width (set with the rear dial L, 16 units every three clicks)."),
        ("set:0x1488", "Custom box in use: height",
         "The height of the Custom box chosen as Focus Area, whichever of the three."),
        ("set:0x148a", "Custom box in use: width",
         "The width of the Custom box chosen as Focus Area, whichever of the three."),
        ("set:0x148c", "Custom box in use: height x 1000", "0x1488 times 1000, written with it."),
        ("set:0x148e", "Custom box in use: width x 1000", "0x148a times 1000, written with it."),
        ("set:0x14b0", "Custom box in use: height (copy)", "A copy of 0x1488, written with it."),
        ("set:0x14b2", "Custom box in use: width (copy)", "A copy of 0x148a, written with it."),
        ("set:0x14c0", "Custom 1 box: default height", "Custom 1's default height: no change moved it, "
                                                       "and Reset (C4 in the editor) puts the box back to it."),
        ("set:0x14c2", "Custom 1 box: default width", "Custom 1's default width, as 0x14c0."),
        ("set:0x14c4", "Custom 2 box: default height", "Custom 2's default height, as 0x14c0."),
        ("set:0x14c6", "Custom 2 box: default width", "Custom 2's default width, as 0x14c0."),
        ("set:0x14c8", "Custom 3 box: default height", "Custom 3's default height, as 0x14c0."),
        ("set:0x14ca", "Custom 3 box: default width", "Custom 3's default width, as 0x14c0.")):
    FRAME_PROOFS[_k] = {"note": _note + BOX}
    NEW_RECORDS[_k] = {"like": _k, "name": _name, "values": [], "note": ""}

# memories 4-12 (Movie, S&Q Motion, Time-lapse slots 1-3; the owner's go-ahead 2026-11-02): each family in M
# through the menu, two exposures set through the SDK, every slot registered at each (runs/kit2_memmirror). The
# ILCE-1M2's live copy (0x018c), one block a memory set, as its camera file's mirror says
A1_MIRROR = mirror_of({"camera": read_json(definitions.camera_file(paths.A1II))})

# Only the registered slot's block of the live mirror moved. The raw stop values stayed 0 outside Stills
MIRROR = {4: ("Movie", "1/500 F8 and 1/60 F11"), 7: ("S&Q Motion", "1/500 F8 and 1/250 F11"),
          10: ("Time-lapse", "1/500 F8 and 0.8\" F11, stored 4/5")}
for _first, (_fam, _) in MIRROR.items():
    for _i in range(3):
        _set = _first + _i
        _how = f" Written when {_fam} slot {_i + 1} (memory set {_set}) is registered."
        for _off, _note in ((288, "F-number x 100."), (290, "The shutter speed's numerator."),
                            (292, "The shutter speed's denominator.")):
            FRAME_PROOFS[mirror_key(A1_MIRROR, _set, _off)] = {"note": _note + _how}
FRAME_PROOFS.update({
    "set:0x023c": {"note": "2 in a slot never registered (as Initialize leaves it); registering it in any family "
                           "writes 4, which no settings file clears.", "values": [[2, "Empty"], [4, "Registered"]]},
    "set:0x11ab": {"note": "Written when the slot is registered: 0 in Stills, 4 in S&Q Motion and Time-lapse; a "
                           "Movie registration leaves it 1, as an empty slot has it. No settings file sets it.",
                   "values": [[0, "Stills"], [1, "Not written (empty, or Movie)"], [4, "S&Q Motion or Time-lapse"]]},
})
# Image Quality Settings with Recording Media on one slot (Slot 1, set for the run, the start file put back after,
# 0 records differ; runs/kit2_unattended, 2026-11-02): one column, whose cells save as they are chosen. Its File Format is 0x01da,
# which JPEG/HEIF Switch also writes, and its RAW File Type 0x01dc, every option in the list's order
ONE_SLOT = " With Recording Media on one slot, Image Quality Settings has one column."
FRAME_PROOFS.update({
    "global:0x01dc": {"note": "RAW File Type for single-slot recording." + ONE_SLOT,
                      "values": [[0, "Uncompressed"], [2, "Lossless Comp (L)"], [3, "Lossless Comp (M)"],
                                 [4, "Lossless Comp (S)"], [7, "Compressed"]]},
    "global:0x01da": {"note": "File Format for single-slot recording: RAW 0, RAW & JPEG 1, RAW & HEIF 2, JPEG 3, HEIF 4. "
                              "The list shows RAW, RAW & JPEG, JPEG with JPEG/HEIF Switch on JPEG, and RAW, "
                              "RAW & HEIF, HEIF with it on HEIF; the switch writes HEIF 4 here from JPEG." + ONE_SLOT,
                      "values": [[0, "RAW"], [1, "RAW & JPEG"], [2, "RAW & HEIF"], [3, "JPEG"], [4, "HEIF"]]},
})
RECORD_FIXES.update({"global:0x01dc": {"name": "RAW File Type (one slot)"},
                     "global:0x01da": {"name": "File Format (one slot)"}})
# Distortion Comp., greyed (Auto) with one lens, opens with another (2026-11-02): Off and back, and its guides read
# with drive.py (runs/kit2_lens50). The flag differs by lens; the lenses used are in the hand evidence
FRAME_PROOFS["global:0x0294"] = {
    "note": "Distortion Comp.: Auto 0, Off 1. Greyed at Auto with a lens that always corrects, open with one that "
            "does not.",
    "values": [[0, "Auto"], [1, "Off"]]}
# by hand, the second round (HDMI out, watched through the OSD; runs/kit2_hdmi_watch, 2026-11-02): the viewfinder's
# rows open only with Select Finder/Monitor on VF(Manual); Finder DISP Mode by DISP at the finder, a MENU visit after
# each press for the download. Enlarge Screen On also set Custom Button 2 to Enlarge Menu Scrn (stills and movie)
# and the monitor to Monitor(Manual); the session's start file put them back
PM2 = [[0, "-2"], [1, "-1"], [2, "±0"], [3, "+1"], [4, "+2"]]
for _k, _vals, _note in (
        ("global:0x047c", [[0, "Auto"], [1, "Manual"]],
         "The viewfinder's Brightness Setup (open with Select Finder/Monitor on VF(Manual))."),
        ("global:0x1465", [[0, "Off"], [2, "On (Custom Btn 2)"]],
         "Enlarge Screen. Setting it On also assigns Enlarge Menu Scrn to Custom Button 2 (0x0410 and 0x042a, 2547) "
         "and puts the monitor on Monitor(Manual) (0x047a 7)."),
        ("global:0x03cb", [[0, "30 Images"], [3, "9 Images"]], "Playback's Image Index."),
        ("global:0x03c7", [[0, "JPEG"], [1, "HEIF(4:2:0)"], [2, "HEIF(4:2:2)"]],
         "Playback > Edit > JPEG/HEIF Switch (the shooting menu's is 0x01d8)."),
        ("global:0x04a2", [[0, "On"], [1, "Off"]],
         "Shutter When Pwr OFF (Setup Option; Off brings a warning about the sensor)."),
):
    FRAME_PROOFS[_k] = {"note": _note, "values": _vals}
# The viewfinder's two scales chosen by hand that day are proved since on the camera by kit/provers/scale_run.py,
# every value (runs/kit2_pass2, 2026-11-11, the HDMI cable out, the eye sensor covered and the monitor folded in, the
# owner having said the viewfinder's rows may be run that day; Viewfinder Bright. with --panel-row, Brightness Setup set
# to Manual): only their notes are here, and the report's proof stands, each value named by its readers (-2, -1, ±0, +1,
# +2). With the HDMI cable in, both rows only answer "This function is currently disabled.", whatever Select
# Finder/Monitor says (2026-10-31, 2026-11-10). The allowance that stays is of a look kit/drive.py made at the
# brightness row with the owner's word for the brightness rows (runs/kit2_small_1109, 2026-11-09)
VF_ONLY = (" Its row opens only with the finder in use, which takes the monitor folded in and the eye sensor covered "
           "(an eye at the finder).")
VF_CABLE = " With the HDMI cable in, its row answers \"This function is currently disabled.\""
FRAME_PROOFS["global:0x0c89"] = {
    "note": "The viewfinder's manual brightness, with Brightness Setup on Manual: -2 is 0, +2 is 4." + VF_ONLY
            + VF_CABLE}
FRAME_PROOFS["global:0x047d"] = {"note": "Finder Color Temp.: -2 is 0, +2 is 4." + VF_ONLY + VF_CABLE}
FRAME_PROOFS["global:0x04e6"] = {
    "note": "The finder's display mode in use, the monitor's codes (0x04e5). DISP pressed at the finder steps it "
            "through the modes ticked in DISP Set > Finder (0x0cba-0x0cbd), in the list's order, and comes round "
            "after one press per mode ticked. DISP Set > Finder moves it when the mode in use leaves the cycle. A "
            "settings file sets it.",
    "values": [[0, "Display All Info."], [1, "No Disp. Info."], [2, "Histogram"], [3, "Level"]]}
RECORD_FIXES.update({"global:0x03c7": {"name": "JPEG/HEIF Switch (Playback)"},
                     # its old name came from an early guess; retested by the owner's offer, neither moves it
                     "global:0x1672": {"name": "Unknown flag (not a setting)",
                                       "note": "Screen Reader and Disp Set of Multi Media do not move it."}})
# the vertical focus points (Switch V/H AF Area = AF Point + AF Area; runs/kit2_vertical, 2026-11-02): with the camera
# held grip down, then grip up, and that orientation's Focus Area on Spot, the spot moved with the multi-selector (Left
# twice, Up twice), then Stills slot 1 registered with the camera level. A point's place is kept only in a memory set,
# as the level one's
VERT = (" Written when a memory slot is registered: with the camera held that way and Focus Area on Spot, a Left press "
        "of the multi-selector lowered the orientation's X and an Up press its Y." + FRAMEPOS_POINT)
for _k, _note in (("set:0x01c0", "The spot's X with the camera held grip down."),
                  ("set:0x01c6", "The spot's Y with the camera held grip down."),
                  ("set:0x01c2", "The spot's X with the camera held grip up."),
                  ("set:0x01c8", "The spot's Y with the camera held grip up.")):
    FRAME_PROOFS[_k] = {"note": _note + VERT}
# Custom 1-3 boxes' places (kit/provers/framepos_run.py, runs/kit2_framepos, 2026-11-09, framepos.jsonl; context
# "Switch V/H AF Area Off, camera level"): under each box, Stills slot 1 registered, three Left and two Up presses on
# the shooting screen, slot 1 registered again, the box put back and a third registration matching the first. Ten
# records of the memory sets moved each time, the same way as the presses (Left lowers X, Up lowers Y), and the spot's
# point records (0x019c, 0x019e, 0x01be-0x01c8) did not: a box keeps its place apart from the spot's. Two are shared by
# the three boxes (the box in use, as 0x019c/0x019e are the spot's); each box has three X and three Y laid out as the
# spot's level, grip-down and grip-up copies, which moved alike with Switch V/H AF Area Off (so copies, as the Zone's),
# and a fourth X and Y. That run left AF Frame Move Amt as the camera had it; the step run (framepos_run.py
# --frame-move-amt, runs/kit2_framepos_amt, 2026-11-09) set it by the menu, Standard for one session and Large for the
# other, and under Custom 1 the ten records moved alike; the one-press run (runs/kit2_framepos_amt_one, 2026-11-09)
# measured the box's steps FRAME_STEPS holds, by one press each way under each option; Custom 2 and 3 were not
# measured, so their notes say the steps are Custom 1's. The notes
# give those steps, never the boxes' sizes or where a box stood (docs/decisions/0016). Sampled from the two
# registrations, as the spot's point records are. Tracking: Custom 1 (kit2_framepos's later session, Focus Mode on
# Continuous AF by the menu) moved the same ten records as Custom 1, alike
BOX_PLACE = (" Written when a memory slot is registered: moving the box on the shooting screen changes no live record. "
             "With Switch V/H AF Area Off, Left and Up presses under each Custom box lower its X and Y records and the "
             "two the boxes share, the records moving with the presses, and leave the spot's point records as they "
             "are. " + STEP_FACTS["box"] + ". Under Tracking: Custom 1 the same presses moved Custom 1's records and "
             "the shared two the same way: a Tracking area keeps its box's place in the plain box's records.")
BOX_COPIES = (" Each box's three X and three Y records are laid out as the spot's level, grip-down and grip-up copies "
              "(0x01be-0x01c8); with Switch V/H AF Area Off they moved alike, so which orientation each keeps is not "
              "told.")
BOX_PLACES = {0x1327: ("Custom box position in use: X", "The X of the Custom box in use, whichever of the three, as "
                                                           "0x019c is the spot's."),
              0x1329: ("Custom box position in use: Y", "The Y of the Custom box in use, whichever of the three, as "
                                                           "0x019e is the spot's.")}
for _n, (_x, _y, _x4, _y4) in {1: ((0x1333, 0x1335, 0x1337), (0x1339, 0x133b, 0x133d), 0x139f, 0x13a1),
                               2: ((0x133f, 0x1341, 0x1343), (0x1345, 0x1347, 0x1349), 0x13a3, 0x13a5),
                               3: ((0x134b, 0x134d, 0x134f), (0x1351, 0x1353, 0x1355), 0x13a7, 0x13a9)}.items():
    for _axis, _ids, _four in (("X", _x, _x4), ("Y", _y, _y4)):
        for _i, _rid in enumerate(_ids, 1):
            BOX_PLACES[_rid] = (f"Custom {_n} box position: {_axis} (copy {_i})",
                                f"Custom {_n}'s {_axis}, one of three copies." + BOX_COPIES)
        BOX_PLACES[_four] = (f"Custom {_n} box position: {_axis} (copy 4)",
                             f"Custom {_n}'s {_axis}, a fourth copy beside the three laid out as the spot's orientation "
                             "copies; it moved with them.")
for _rid, (_name, _note) in BOX_PLACES.items():
    _k = f"set:0x{_rid:04x}"
    FRAME_PROOFS[_k] = {"note": _note + BOX_PLACE}
    NEW_RECORDS[_k] = {"like": "set:0x019c", "name": _name, "values": [], "note": ""}
# AF Frame Move Amt, proved by the menu in pass 2, sizes the step a press moves a focus frame: the step run
# (framepos_run.py --frame-move-amt, runs/kit2_framepos_amt, 2026-11-09) set it by the menu to Standard and to Large and
# measured the steps through Stills slot 1's registrations, as the point's and the boxes' notes give them. A note only,
# no proof: the writer merges the proof the definition holds with the report's, as for any setting (schema_update's
# by_lines_of takes only an entry that lists values)
FRAME_PROOFS["global:0x03a3"] = {
    "note": "Sizes the step a press of the multi-selector moves a focus frame: " + STEP_FACTS["all"] + "."}
# Movie mode's Auto Create Still Image refuses while a remote session is connected ("Connected to Remote Shooting.
# Cannot be executed."): the owner changed it with the session closed, a download before and after (2026-11-02)
FRAME_PROOFS["global:0x171c"] = {
    "note": "Auto Create Still Image (Movie mode): On 0, Off 1. Refused while connected to Remote Shooting.",
    "values": [[0, "On"], [1, "Off"]]}
# by hand, the third round (Movie mode, watched through the OSD; runs/kit2_hdmi_watch, 2026-11-02); the round's start
# file put back after: a 4320p HDMI choice had taken the picture off the capture dongle
FRAME_PROOFS["global:0x04a3"] = {
    "note": "Auto Pixel Mapping (Setup Option): On 0, Off 1; turning it Off asks to confirm, as pixel mapping must "
            "then be done by hand.", "values": [[0, "On"], [1, "Off"]]}
FRAME_PROOFS["global:0x0494"] = {
    "note": "Only selectable when Rec. Media dur HDMI Output = Off (HDMI Only): 60p 10bit 0, 30p 10bit 2, 24p 10bit "
            "4. Odd values (1, 3) are probably the PAL rates 50p/25p; the camera keeps them but the menu cannot "
            "select them in NTSC mode.",
    "values": [[0, "60p 10bit"], [2, "30p 10bit"], [4, "24p 10bit"]]}
RAW_OFF = ("Greyed even with Log Shooting On and Rec. Media dur HDMI Output On (\"This function is currently "
           "disabled.\"): probably needs a RAW recorder on HDMI.")
RECORD_FIXES.update({
    "global:0x122e": {"name": "Wi-Fi Connect"},
    "global:0x0495": {"name": "Movie HDMI Output RAW", "note": RAW_OFF},
    "global:0x0496": {"name": "RAW Output Setting", "note": RAW_OFF},
})
# the rest of the by-hand list, driven remotely on the owner's go-ahead ("please do them yourself", 2026-11-02):
# USB Streaming (Network Streaming's own settings moved no record: the Help Guide has them unsaved by Save/Load),
# Silent Mode's target list, the Dial/Wheel checkbox and the two names, typed on the camera's keyboard
FRAME_PROOFS["global:0x02b3"] = {
    "note": "USB Streaming > Output Res/Frame Rate. 7, HD (1080p) 25p, is a PAL rate: every PAL rate is stored one code "
            "above its NTSC counterpart (the Movie, S&Q and Time-lapse frame rates, proved under each system).",
    "values": [[0, "4K (2160p) 30p"], [2, "4K (2160p) 15p"], [4, "HD (1080p) 60p"], [6, "HD (1080p) 30p"],
               [8, "HD (720p) 30p"], [7, "HD (1080p) 25p (PAL)"]]}
FRAME_PROOFS["global:0x02b4"] = {
    "note": "USB Streaming > Movie Rec During Streaming.", "values": [[0, "Enable"], [1, "Disable"]]}
FRAME_PROOFS["global:0x02d9"] = {
    "note": "Silent Mode Settings > Target Function Settings > Auto Pixel Mapping: whether Silent Mode turns Auto "
            "Pixel Mapping off.", "values": [[0, "Not Target"], [1, "Off"]]}
FRAME_PROOFS["global:0x0e29"] = {
    "note": "The Dial/Wheel page's checkbox (Custom Key/Dial Set., stills, page 6). Ticking it again copies the M-mode "
            "dial functions over the other-mode ones (0x0407-0x040e: dial 2's Other took dial 2's M-mode function).",
    "values": [[0, "Off (unticked)"], [1, "On (ticked)"]]}
# the title's and the prefix's examples are the camera's factory words ("C", "DSC") and what the run typed
FRAME_PROOFS["global:0x0b5c"] = {
    "note": "Text: the movie title, one ASCII byte per character, zero-filled (\"C\" read 67, 0...; typed \"Ca\" "
            "read 67, 97, 0...)."}
FRAME_PROOFS["global:0x0b5b"] = {
    "note": "Text: the 3-character file-name prefix as ASCII bytes, the first in the low byte (DSC = 0x435344; "
            "typed DSD = 0x445344). Stills' File/Folder Settings > Set File Name."}
RECORD_FIXES["global:0x02d9"] = {"name": "Silent Mode target: Auto Pixel Mapping"}
# Stills through the menu (Mode Dial Control Set = Set with Menu; runs/kit2_stillsx, 2026-11-02), the start file put
# back after: the mode in use as the carousel sets it, two registrations of Stills slot 1, and Focus Area's records
# that only move with Switch V/H AF Area Off
FRAME_PROOFS["global:0x10b6"] = {
    "note": "The exposure mode in use: follows the mode dial (the camera writes the dial position here on load), or "
            "the Shoot Mode carousel with Mode Dial Control Set = Set with Menu. View only.",
    "values": [[0, "Intelligent Auto"], [1, "P"], [2, "A"], [3, "S"], [4, "M"]]}
FRAME_PROOFS["global:0x13e0"] = {
    "note": "As 0x10b6, numbered from Intelligent Auto 0, P 2 to M 5; written with it by the mode dial or the Shoot "
            "Mode carousel. View only.",
    "values": [[0, "Intelligent Auto"], [2, "P"], [3, "A"], [4, "S"], [5, "M"]]}
# Stills slot 1 registered again in S and in M (runs/kit2_small_1109, 2026-11-09, kit/drive.py and
# kit/provers/mode_switch.py), the start file put back after each: the three records took 3 and 4, as P and A took 1
# and 2 on 2026-11-02, so all four registrations are proved
FRAME_PROOFS["set:0x0b8d"] = {
    "note": "Written when the slot is registered: a Stills registration in P writes 1, in A 2, in S 3 and in M 4.",
    "values": [[1, "P"], [2, "A"], [3, "S"], [4, "M"]]}
FRAME_PROOFS["set:0x11ad"] = {
    "note": "Written when the slot is registered in Stills mode: the mode in use, as 0x10b6 numbers them, P 1, A 2, "
            "S 3 and M 4; a Movie-mode registration leaves it. A settings file does not set it.",
    "values": [[1, "P"], [2, "A"], [3, "S"], [4, "M"]]}
FRAME_PROOFS["global:0x0b8d"] = {
    "note": "The exposure mode last registered to a memory slot, not the menu's: a choice in the Shoot Mode carousel "
            "leaves it, and a Stills registration in P writes 1, in A 2, in S 3 and in M 4.",
    "values": [[1, "P"], [2, "A"], [3, "S"], [4, "M"]]}
# what else those two registrations wrote that no record names yet: the set's 0x00cb took 1 in both, a value no proof
# had shown it (a registration of 2026-11-02 did not write it). What it means is not known, so its values are its
# numbers. What the slot held before either registration is the camera's own and is not said (decision 16)
FRAME_PROOFS["set:0x00cb"] = {
    "note": "A Stills registration in S or in M writes 1 here. The camera keeps no copy of it outside the memory sets. "
            "What it means is not known.",
    "values": [[0, "0"], [1, "1"]]}
FRAME_PROOFS["global:0x0385"]["note"] += " The memory sets' copy follows a registration."
# 0x04e0 again in AF Area Registration's runs (runs/kit2_afreg2, 2026-11-09), where the prover chose Focus Area's areas
# in turn: Spot M then Expand Spot wrote 1 (downloads 00420 and 00428), Spot XS then Expand Spot 4 (00140 and 00148),
# Spot XL then Expand Spot 3 (00783 and 00791). Only a move from a size the prover chose counts, never one from the area
# the camera held when a run began (its own setting)
FRAME_PROOFS["global:0x04e0"] = {
    "note": "Written when Focus Area leaves Spot: the Spot size it had (S 0, M 1, L 2, XL 3, XS 4). A size chosen "
            "within Spot leaves it; the size in use is 0x0e5c.",
    "values": [[0, "S"], [1, "M"], [2, "L"], [3, "XL"], [4, "XS"]]}
# 0x12e1 again in AF Area Registration's run (runs/kit2_afreg2, 2026-11-09): the prover chose Custom 2, then Tracking:
# Wide, which wrote 1 (downloads 00940_after-custom-2.DAT and 00955_before-tracking-wide.DAT); a move from an area the
# prover chose, as 0x04e0's above
FRAME_PROOFS["global:0x12e1"] = {
    "note": "Written when Focus Area leaves Custom: the Custom slot it had (Custom 1 0, Custom 2 1, Custom 3 2); "
            "moving between Custom 2 and 3 leaves it.",
    "values": [[0, "Custom 1"], [1, "Custom 2"], [2, "Custom 3"]]}
FRAME_PROOFS["global:0x03da"] = {
    "note": "Remote Shoot Setting > RAW+J Save Image. Greyed while Save Image Size is 2M (\"not available as "
            "follows: Save Image Size 2M\"); open with Original.",
    "values": [[0, "RAW & JPEG"], [1, "JPEG Only"], [2, "RAW Only"]]}
RECORD_FIXES.update({
    "global:0x04e0": {"name": "Spot size when Spot was last left"},
    "global:0x0b8d": {"name": "Exposure mode last registered to a memory slot (P/A/S/M)"},
    "global:0x12e1": {"name": "Custom slot when Custom was last left"},
    # named AF Illuminator from an SDK code until 2026-11-02, when registering Stills slot 1 with AF Illuminator Off
    # wrote the set's 0x0385 and left this as it was; its note and values: FRAME_PROOFS (2026-11-09)
    "set:0x00cb": {"name": "Unknown (memory sets; written by a registration)"},
    "global:0x0392": {"name": "Unknown (Focus Area-like)",
                      "note": "Not the last non-Wide Focus Area: no Focus Area choice moves it, in Stills or in "
                              "Movie mode."},
    "global:0x03f9": {"name": "Bluetooth Rmt Ctrl"},                    # note: FRAME_PROOFS (2026-11-02)
    "global:0x13d1": {"name": "Unknown (moves with connection screens; the SDK lists it as Priority Key Settings)",
                      "note": "Setting PriorityKeySettings over the SDK leaves it; opening Cnct. while Power OFF's "
                              "Creators' App screen or Bluetooth Rmt Ctrl's Pairing screen moves it."},
    "global:0x13d2": {"name": "Priority Key Settings (flag 1)",
                      "note": "Becomes 1 when PC Remote priority, 2, is set over the SDK; setting camera priority, "
                              "1, again, or reconnecting, leaves it 1, and an upload puts 0 back."},
    "global:0x13d3": {"name": "Priority Key Settings (flag 2)", "note": "As 0x13d2, with it."},
})
# Movie, then the families through the menu (runs/kit2_family, 2026-11-02), the start file put back after: Auto
# Framing's Movie Rec/Streaming, Rec Frame Rate's derived record (a 30p or 24p HDMI signal took the picture off the
# capture dongle: the OSD for those), and the family records as the Shoot Mode carousel sets them
SWITCH_NOTE = (" Follows the still/movie/S&Q switch (the camera writes the switch position here on load), or the Shoot "
               "Mode carousel with Mode Dial Control Set = Set with Menu. View only.")
FRAME_PROOFS["global:0x13bf"] = {"note": "Stills 0, Movie 1, S&Q Motion 2, Time-lapse 3." + SWITCH_NOTE,
                                 "values": [[0, "Stills"], [1, "Movie"], [2, "S&Q"], [3, "Time-lapse"]]}
FRAME_PROOFS["global:0x10b7"] = {"note": "S&Q Motion and Time-lapse both 2." + SWITCH_NOTE,
                                 "values": [[0, "Stills"], [1, "Movie"], [2, "S&Q / Time-lapse"]]}
FRAME_PROOFS["global:0x0170"] = {
    "note": "1 in S&Q Motion and in Time-lapse, 0 in Stills and Movie." + SWITCH_NOTE + " In the memory sets, "
            "registering a slot in S&Q Motion or Time-lapse writes 1, and a settings file does not set the sets' "
            "copies.", "values": [[0, "Off"], [1, "On"]]}
FRAME_PROOFS["global:0x118b"] = {
    "note": "Which of the S&Q switch's two families: choosing S&Q Motion in the Shoot Mode carousel writes 0, "
            "Time-lapse 1.",
    "values": [[0, "S&Q Motion"], [1, "Time-lapse"]]}
FRAME_PROOFS["global:0x190c"] = {
    "note": "The frame rate of the active movie format, derived from the per-format Rec Frame Rate records; the "
            "camera recomputes it on load. View only.", "values": [[1, "60p"], [3, "30p"], [5, "24p"], [7, "120p"]]}
FRAME_PROOFS["global:0x1176"] = {
    "note": "Auto Framing Settings > Movie Rec/Streaming: whether the recorded or streamed movie is cropped.",
    "values": [[0, "Crop"], [1, "Do not crop"]]}
# Movie's white balance, the start file put back after each run (kit/drive.py in Movie mode, set with the menu; the
# chooser on C.Temp./Filter, then the field stepped to the temperature): 6000 K and 5000 K (runs/kit2_wbmovie,
# 2026-11-02), then both ends, 9900 K and 2500 K (runs/kit2_wbmovie2, 2026-11-08: drive.jsonl's last two entries, OK
# frames 00145_enter.png and 00197_enter.png, the field's frames before each), each written with 0x0b91. The stills
# records 0x0b93 and 0x0e0e: whether they are written too is Different Set for Still/Mv's White Balance box, the
# camera's own setting and not proved yet (decision 16). 0x0b91 and 0x0b93 have their own proofs on the same line
# (sampled, linear, 4 proofs, kit2_pass2), and
# 2500 K = 0 and 9900 K = 74 agree with them, so nothing else follows. The temperature the row held before each run is
# the camera's own setting and no proof (decision 16): only the four temperatures set are listed, and how many steps
# the field took is not said, for it would tell it. With both ends and the two between on one line, the scale is
# sampled (KIT_PLAN's line rule, checked by the writer)
FRAME_PROOFS["global:0x0b95"] = {
    "note": "Movie's own C.Temp./Filter temperature, 2500-9900 K: set in Movie mode it is written with 0x0b91, the "
            "temperature in use; set in Stills, the stills copy 0x0b93 is written with 0x0b91. Whether a change in one "
            "mode writes the other mode's copy too is Different Set for Still/Mv's White Balance box, not proved yet. "
            "Every temperature between 2500 K and 9900 K is the scale's."}
RECORD_FIXES["global:0x0b93"] = {"name": "WB Color Temp. (C.Temp./Filter, stills)"}
# proved through Image Quality Settings > RAW File Type > SLOT 2 (kit2_pass2, 2026-10-29), so not NR Shooting: its
# name kept the guess from before the proof (2026-11-03)
RECORD_FIXES["global:0x01f4"] = {"name": "RAW File Type (Slot 2)"}
# alone on the owner's go-ahead ("if you believe you can do it, you have my permission", 2026-11-02; runs/kit2_alone),
# the start file put back after: Movie's ISO readout, Time-lapse's Video Light Setting (no light attached, nothing
# shot), and with Switch V/H AF Area Off the vertical orientations' zone memories, written with the level one's
FRAME_PROOFS["global:0x1165"] = {
    "note": "Time-lapse Settings > Video Light Setting (open from Movie mode too).",
    "values": [[0, "Off"], [1, "2 Sec"], [2, "5 Sec"], [3, "10 Sec"]]}
# the ISO readouts: the two ISOs set in turn are the proofs; the ISO the run began on, put back after, is the camera's
# own setting and no sample (decision 16, as 0x0018's level)
for _k in ("global:0x0fde", "global:0x0fe0"):
    FRAME_PROOFS[_k] = {"note": "The ISO the camera is using (ISO AUTO result); recomputed on load from the ISO "
                                "settings. It holds the ISO's own codes. View only."}
NEW_RECORDS.update({f"set:0x{rid:04x}": {"like": "set:0x0f0b", "name": f"Zone position memory (vertical B, grid index, "
                                         f"copy {n})", "values": [], "note": ""}
                    for n, rid in ((1, 0x0f38), (2, 0x0f3a), (3, 0x0f3c))})
# and all nine places of each (runs/kit2_framepos, kit/provers/framepos_run.py --zone-grid, 2026-11-09): the sweep's
# "registration mirror" lines, one a record and a place, which the writer takes in beside the codes below
# (pass2_report.mirrored_values), each under ZONE's own label
for _rid in (0x0f32, 0x0f34, 0x0f36, 0x0f38, 0x0f3a, 0x0f3c):
    FRAME_PROOFS[f"set:0x{_rid:04x}"] = {
        "note": "A vertical orientation's Zone place on its 3 x 3 grid (numbered as the level zone's 0x0f2c), written "
                "only when a memory slot is registered. With Switch V/H AF Area on, a registration with the camera "
                "level leaves it; with it Off, a registration writes the Zone's place into these six and the six level "
                "records alike, and Tracking: Zone writes them as Zone does. Which triple is grip down was not tested; "
                "by the order of the other orientation records, A (0x0f32-0x0f36).",
        "values": ZONE}
# AF Area Registration (runs/kit2_afreg, 2026-11-02): with it On, holding Fn on the shooting screen ("Registered the
# focus area") copies the orientation's four live Focus Area memories into these: kind as 0x0e68, area as 0x0f46,
# Tracking start as 0x0e62 and 0x0f6e. With Switch V/H AF Area Off one hold writes all three orientations. Recalled
# by the Regist. AF Area keys; a memory slot registration copies them into the set too. Focus Area Limit excluding
# the registered area resets it to Wide (2026-10-31)
KIND = [[0, "Wide"], [1, "Zone"], [2, "Center Fix"], [3, "Spot"], [4, "Expand Spot"], [5, "Custom"], [6, "Tracking"]]
AREA = [[0, "Wide"], [1, "Zone"], [2, "Center Fix"], [3, "Spot: XL"], [4, "Spot: L"], [5, "Spot: M"], [6, "Spot: S"],
        [7, "Spot: XS"], [8, "Expand Spot"], [9, "Custom 1"], [10, "Custom 2"], [11, "Custom 3"], [12, "Tracking: Wide"],
        [13, "Tracking: Zone"], [14, "Tracking: Center Fix"], [15, "Tracking: Spot XL"], [16, "Tracking: Spot L"],
        [17, "Tracking: Spot M"], [18, "Tracking: Spot S"], [19, "Tracking: Spot XS"], [20, "Tracking: Expand Spot"],
        [21, "Tracking: Custom 1"], [22, "Tracking: Custom 2"], [23, "Tracking: Custom 3"]]
START = [[0, "Wide"], [1, "Zone"], [2, "Center Fix"], [3, "Spot: S"], [4, "Spot: M"], [5, "Spot: L"], [6, "Spot: XL"],
         [7, "Spot: XS"], [8, "Expand Spot"], [9, "Custom 1"], [10, "Custom 2"], [11, "Custom 3"]]
START_B = [[v, lab] for v, lab in AREA[:12]]                              # 0x0f6e's numbering: Spot XL first
# What each hold proved comes from the proof lines (pass2_report reads every proof run of the camera): kit2_afreg's five
# holds, recorded by hand from that run's downloads on 2026-11-09, and kit/provers/afreg_run.py's runs (kit2_afreg2 on).
# The first three of those five name no state: afreg_run proved their areas again with its setup (2026-11-11), and the
# report leaves them out (pass2_report.stood_out).
# This table gives the records their names, their values' names and the note; the lines name each hold by its area,
# which is no value of the kind and Tracking start records, so all twelve keep these names (KEEP_LABELS) and their
# entries here carry no proof of their own (FRAME_PROOFS without "proved": the report's stands, whole)
REG_NOTE = ("Written by AF Area Registration: with it On, holding Fn on the shooting screen copies the orientation's "
            "live Focus Area memories here (the camera: \"Registered the focus area\"); with Switch V/H AF Area Off "
            "one hold writes all three orientations. A Tracking area's hold writes its start area; any other area's "
            "hold copies the Tracking start area in use, which says nothing of the area registered. Focus Area Limit "
            "excluding the registered area resets it to Wide. A memory slot keeps its own copy.")
_REG = [("0x0e7a", "0x0e7c", "0x0e7e", "kind", KIND),
        ("0x0f80", "0x0f82", "0x0f84", "area", AREA),
        ("0x0e74", "0x0e76", "0x0e78", "Tracking start area", START),
        ("0x0f8c", "0x0f8e", "0x0f90", "Tracking start area, alt numbering", START_B)]
for *_ks, _what, _vals in _REG:
    for _k, _o in zip(_ks, ("horizontal", "vertical, grip down", "vertical, grip up"), strict=True):
        _key, _name = f"global:{_k}", f"Registered AF area: {_what} ({_o})"
        if _k in ("0x0e74", "0x0e76", "0x0e78", "0x0f8c", "0x0f8e", "0x0f90"):
            NEW_RECORDS[_key] = {"like": "global:0x0e62", "name": _name, "values": [], "note": ""}
        else:
            RECORD_FIXES[_key] = {"name": _name, "tab": "Focus", "group": "Focus Area"}   # beside the new six
        FRAME_PROOFS[_key] = {"note": REG_NOTE, "values": _vals}
        KEEP_LABELS.add(_key)
for _k, _n in (("0x0f24", "AF point copy: X"), ("0x0f26", "AF point copy: Y"), ("0x0f28", "AF point copy 2: X"),
               ("0x0f2a", "AF point copy 2: Y")):
    # the owner's own position and the set's values before are not named (docs/decisions/0016). The old schema gave
    # all four the X range and a unit of "(X) / 0..479 (Y)"; a Y position goes to 479, as the sets' own Y has it
    # (set:0x019e, AF point position Y), and both are pixels of the 640 x 480 grid
    RECORD_FIXES[f"global:{_k}"] = {"name": _n, "range": [0, 479] if _n.endswith("Y") else [0, 639], "unit": "px",
                                    "note": "Focus frame position on the 640x480 grid (320,240 = centre). Files "
        "saved from the camera's menu hold the position last set there, while every remote download holds the centre; "
        "moving the point in a remote session does not update it, so the camera writes it only at certain events "
        "(menu save, memory registration). Memory sets hold their own copy. It follows none of the registrations "
        "tried. View-only until an upload test."}
RECORD_FIXES["global:0x018b"] = {"name": "Network block (holds a Cnct. while Power OFF flag)",
                                 "note": "160 bytes. Its byte 45 follows Cnct. while Power OFF: 1 On, 0 Off (0x03d7 is "
                                         "the setting itself); the rest is not known."}

# by hand with no remote session open (kit/tools/hdmi_watch.py --each --closed: a session only for each download,
# opened back on the shooting screen; 2026-11-02): the rows the camera refuses, or does not keep, while connected
CLOSED = " Refused, or not kept, while a remote session is open."
FRAME_PROOFS["global:0x048e"] = {
    "note": "USB Connection Mode, in the list's order: Sel. When Connect 0, USB Streaming 1, Mass Storage 3, MTP 4, "
            "Remote Shooting 5; no option writes 2. MTP is refused (\"Connected to Remote Shooting. Cannot be "
            "executed.\") while Remote Shooting is On, even with no session open; chosen with Remote Shooting Off, "
            "it is kept when Remote Shooting is turned On again, while the row reads Sel. When Connect." + CLOSED,
    "values": [[0, "Sel. When Connect"], [1, "USB Streaming"], [3, "Mass Storage(MSC)"], [4, "MTP"],
               [5, "Remote Shooting"]]}
FRAME_PROOFS["global:0x048f"] = {"note": "USB LUN Setting." + CLOSED, "values": [[0, "Multi"], [1, "Single"]]}
FRAME_PROOFS["global:0x0490"] = {"note": "USB Power Supply." + CLOSED, "values": [[0, "On"], [4, "Off"]]}
FRAME_PROOFS["global:0x0050"] = {
    "note": "Power Save Start Time; Off and 30 Min ask to confirm (power consumption increases)." + CLOSED,
    "values": [[0, "Off"], [1, "30 Min."], [2, "5 Min."], [3, "2 Min."], [4, "1 Min."], [6, "10 Sec."]]}
# the Recall Custom holds' bracket copies (2026-10-31, runs/kit2_pass2/chain27_1031.log): every registration wrote
# the live bracket setting's place in the live list, as predicted; the live list itself is proved in full
for _k in ("global:0x0e80", "global:0x0e84"):
    FRAME_PROOFS[_k] = {"note": NEW_RECORDS[_k]["note"]}
# by hand with no session open, the network rows (2026-11-02): Airplane Mode kept the wired link; a Bluetooth remote
# and Creators' App did the pairing (the watcher stays off while "Pairing" or "Awaiting" shows)
for _k in ("global:0x0078", "global:0x0402"):
    FRAME_PROOFS[_k] = {"note": "Airplane Mode. The wired LAN stays up with it On." + CLOSED,
                        "values": [[0, "On"], [1, "Off"]]}
FRAME_PROOFS["global:0x03d7"] = {
    "note": "Cnct. while Power OFF. On asks to use a paired device or pair a new one (\"Awaiting cnct. frm "
            "Creators' App\"). Byte 45 of 0x018b moves with it." + CLOSED,
    "values": [[0, "On"], [1, "Off"]]}
FRAME_PROOFS["global:0x03f9"] = {
    "note": "Bluetooth Rmt Ctrl. On opens the Pairing screen and stays Off until a remote pairs; a session opened "
            "during pairing cuts it short." + CLOSED,
    "values": [[0, "On"], [1, "Off"]]}
# the network switches from two camera-written files (2026-10-24, the owner reminding, 2026-11-02): a file written with
# both off took the camera off the network when loaded, and each code's meaning was read off the camera. Whose file it
# was, what else it held, and how the body is set otherwise are not said (decision 16). Auto Power OFF Temp. on the
# owner's go-ahead ("you can touch this", 2026-11-02)
for _k, _n in (("global:0x122f", "Wired LAN Connect"), ("global:0x03f0", "Remote Shooting")):
    FRAME_PROOFS[_k] = {
        "note": f"{_n}: On 0, Off 1. A file written with it Off takes the camera off the network when loaded. It "
                "cannot be turned off from a session that needs it.",
        "values": [[0, "On"], [1, "Off"]]}
# Wi-Fi Connect by hand with the owner (2026-11-03): Wired LAN Connect Off, Wi-Fi Connect On, then both back, a
# download over USB after each (the closed watcher, CAMSET_USB=1); with the USB cable in, the camera refuses
# network sessions, wired and Wi-Fi alike
FRAME_PROOFS["global:0x122e"] = {
    "note": "Wi-Fi Connect: On 0, Off 1. Greyed while Wired LAN Connect is On (\"not available as follows: Wired LAN "
            "On\"). Each changed only its own record. "
            "The access point's name is in no settings file. With Wi-Fi on, a session over Wi-Fi downloads the same "
            "settings, but only with the USB cable out: while it is in, network sessions fail at the fingerprint.",
    "values": [[0, "On"], [1, "Off"]]}
FRAME_PROOFS["global:0x048b"] = {
    "note": "Auto Power OFF Temp.; High asks to confirm (\"The temperature of the device may rise to prioritize "
            "recording time\", Cancel lit).", "values": [[0, "Standard"], [1, "High"]]}
# a custom look's base look and its panel's Reset (runs/kit2_lookreset, 2026-11-03): choosing a base gives the look
# that base's parameters; the panel's Reset (C4, "Reset the current look? All parameters are reset.", Cancel lit) puts
# them back to the base's and keeps the base
LOOK_BASE_NOTE = ("Base look of a custom Creative Look (C1-C6). Choosing a base gives the look that base's parameters; "
                  "the panel's Reset (the trash button, \"Reset the current look? All parameters are reset.\", Cancel "
                  "lit) puts the parameters back to the base's and keeps the base. Written the same in Stills, Movie, "
                  "S&Q and Time-lapse.")
for _i in range(10, 16):
    RECORD_FIXES[f"global:0x0cbe[{_i}]"] = {"name": "Base Look", "note": LOOK_BASE_NOTE}
# fixed cells (2026-11-03, the owner: "creative look base-look records should be provable"): a built-in look's panel
# has no Look cell (C1-C6's starts with one, runs/kit2_pass2 25977 against 128964), so its base look is itself,
# and every camera download sampled holds its own number, numbered as C1-C6's proved list; BW's and SE's Saturation
# cells do not move (prove_run "fixed") and every file holds 0
BUILT_IN_LOOKS = {0: "ST", 1: "PT", 2: "NT", 3: "VV", 4: "VV2", 5: "FL", 6: "IN", 7: "SH", 8: "BW", 9: "SE",
                  16: "FL2", 17: "FL3"}
for _i, _look in BUILT_IN_LOOKS.items():
    _v = _i if _i < 16 else _i - 6
    FRAME_PROOFS[f"global:0x0cbe[{_i}]"] = {
        "note": f"Base look of the built-in look {_look}: fixed at itself ({_v}). Its panel has no Look cell, where "
                "C1-C6's starts with one; every camera file holds this number. Numbered as C1-C6's base-look list.",
        "values": [[_v, _look]]}
for _i, _look in ((8, "BW"), (9, "SE")):
    FRAME_PROOFS[f"global:0x0d5e[{_i}]"] = {
        "note": f"{_look}'s Saturation: fixed at 0 for the monochrome look (the cell does not move; every camera file "
                "holds 0).", "values": []}
MY_MENU_PAGES = [0x0c8a, 0x0c91, 0x0c98, 0x0c9f, 0x0ca6, 0x0cad]     # My Menu 1-6, seven item codes each
# My Menu Setting > Add Item, one item per proof (kit/provers/mymenu_run.py, 2026-11-07): the proof says which page and
# slot took which code ("my_menu"); the report's row credits every page record with every item, so the writer reads
# the proofs themselves (my_menu_items)
MY_MENU_ROW = "My Menu Setting > Add Item"
# My Menu's empty place, a hand table over all 42 slots: the code camera.my_menu.empty names (data/, 2) is "(empty)".
# Shown on the camera by the Add Item proofs (kit/provers/mymenu_run.py, runs/kit2_pass2, 2026-11-07): every place
# an item went into held that code before the add (the prover refuses an add into any other), and the location
# screen showed the places after a page's items blank (frame 222692_enter.png). kit2_mymenu_scan read only full
# pages, so it shows none. {code} in the line is the camera file's code; what shows it is the hand evidence's
MY_MENU_EMPTY = {"label": "(empty)", "line": "An empty place stores {code}."}

HOLD_BRACKET_COPIES = {"global:0x0e80": "global:0x04c6", "global:0x0e84": "global:0x04c8"}
# a Recall Custom hold's copy of a live setting, named by the live setting's table once that is proved in full and
# every proof of the hold fits it (hold_tables): the code itself (a hold's ISO stores the live ISO's code, 18 hold
# proofs, 2026-10-30), or mirrored, the hold code `mirror` minus the live one (a hold's Exposure Comp.: +4.7 EV, live
# 39, stored 1; all 19 hold proofs fit, 2026-10-30). Until then the evidence goes in the hold's note, and a hold's
# Exposure Comp. is named by EV_DOWN_FROM_20: the codes its proofs chose a hand table's, the others "counted" (counted
# out in quarter stops, no camera's word, so an editor does not offer them outside Expert mode)
HOLD_TABLES = {**{f"global:0x0c01[{i}]": {"live": "global:0x0334", "mirror": None} for i in range(3)},
               **{f"global:0x0bf9[{i}]": {"live": "global:0x0340", "mirror": 40} for i in range(3)}}
# values the camera's menus never offer, each checked by the writer against its evidence (not_offered_marks):
# "walk", a pattern for the report's rows that walked the row's whole list (every option, the start put back: the
# entry's evidence, in the hand evidence, says so; the writer checks that each row proves the record) and never wrote
# the value; "table", the
# table walk's picker lists (runs/kit2_tables/tables.json) on one page, every cell's list walked round to its start
# ("wrapped") and none holding the function. "held": a value the camera writes itself (the factory value, which a file
# holds until the setting is changed) and the list cannot choose back, which stays offered. The why in plain words, for
# the editor, which says it after "Not on the camera's list: A, B." and after "The camera's menus never offer this
# value:", so it names neither the values nor how many
_ISO_AUTO = r"^ISO > ISO AUTO M(?:axim|inim)um \[(?:Stills|Movie) mode\]$"
NOT_OFFERED = [
    *({"key": f"global:0x{r:04x}", "values": [198, 861], "table": ("Custom Key/Dial Set.", "Dial/Wheel"),
       "why": "The Custom Key/Dial Set. menu offers the same 17 functions for each stills dial and wheel, and no others.",
       "menu": "Custom Key/Dial Set. > Dial/Wheel"} for r in range(0x0407, 0x040f)),
    *({"key": f"global:0x{r:04x}", "values": [269], "table": ("Custom Key/Dial Set. (movie)", "Dial/Wheel"),
       "why": "The Custom Key/Dial Set. (movie) menu offers the same 18 functions for each dial and wheel, and no "
              "others.",
       "menu": "Custom Key/Dial Set. (movie) > Dial/Wheel"} for r in range(0x0421, 0x0429)),
    *({"key": f"global:0x{r:04x}[{i}]", "values": [861], "table": ("My Dial Settings", None),
       "why": "The My Dial Settings menu offers the same 18 functions on every dial, and no others.",
       "menu": "My Dial Settings"} for r in (0x045f, 0x0462, 0x0465, 0x0468) for i in range(3)),
    *({"key": k, "values": [2, 3, 4], "walk": _ISO_AUTO,
       "why": "The ISO AUTO Maximum list starts at ISO 100 in Stills mode, and no lower in Movie mode: ISO 50, ISO 64 "
              "and ISO 80 are on neither.",
       "menu": "ISO > ISO AUTO Maximum"}
      for k in ("global:0x0e00", "global:0x0e02")),
    *({"key": k, "values": [2, 4], "walk": _ISO_AUTO,
       "why": "The ISO AUTO Minimum list starts at ISO 100 in Stills mode, and no lower in Movie mode: ISO 50 and ISO 80 "
              "are on neither.",
       "menu": "ISO > ISO AUTO Minimum"}
      for k in ("global:0x0dfa", "global:0x0dfc")),
    *({"key": k, "values": [3], "walk": _ISO_AUTO, "held": True, "named_by": ISO_TABLE,
       "why": "The camera's factory value: Camera Settings Reset and Initialize write it, and a file holds it until the "
              "minimum is changed, but the menu's list starts at ISO 100, so it cannot be chosen again.",
       "menu": "ISO > ISO AUTO Minimum"}
      for k in ("global:0x0dfa", "global:0x0dfc")),
    {"key": "global:0x0204", "values": [2], "walk": r"^Movie Settings > Rec Frame Rate \[Movie mode, (?:PAL, )?File Format XAVC HS 4K[,\]]",
     "why": "With XAVC HS 4K the camera's Rec Frame Rate list offers 60p, 24p and 120p (50p and 100p on PAL), not 30p.",
     "menu": "Movie Settings > Rec Frame Rate"},
    {"key": "global:0x0202", "values": [0, 5], "walk": r"^Movie Settings > Rec Frame Rate \[Movie mode, File Format XAVC HS 8K\]",
     "why": "With XAVC HS 8K the camera's Rec Frame Rate list offers 30p and 24p only.",
     "menu": "Movie Settings > Rec Frame Rate"},
    *({"key": k, "values": [5], "walk": rf"^Movie Settings > Rec Frame Rate \[Movie mode, (?:PAL, )?File Format XAVC S-I {fmt}[,\]]",
       "why": f"With XAVC S-I {fmt} the camera's Rec Frame Rate list offers 60p, 30p and 24p (50p and 25p on PAL), not "
              "120p.",
       "menu": "Movie Settings > Rec Frame Rate"}
      for k, fmt in (("global:0x020a", "4K"), ("global:0x020c", "HD"))),
    {"key": "global:0x0e10", "values": [9], "walk": r"^White Balance \[(?:Movie mode|S&Q mode(?: \([^)]*\))?)\]$",
     "why": "Movie mode's White Balance list has no Flash: its 14 options, in Movie mode and in S&Q, leave it out.",
     "menu": "White Balance [Movie mode]"},
]
# the values the camera keeps in more than one record (copies / copy_of, kit/writer/copies.py): the live setting's key,
# then its Stills copy's and its Movie copy's. Each Picture Profile parameter (25 records 0x42 apart from 0x04e9, one
# element per profile, PP1-PP11) in use, its Stills copy 0x16 above and its Movie copy 0x2c above (on the profiles a
# menu reaches, a Stills edit writes the one in use and the Stills copy, a Movie edit the one in use and the Movie copy,
# each the other mode's copy too where Different Set for Still/Mv's box shares the setting, not proved yet; PP7-PP9's
# are laid out alike); the profile in use (0x0053, the
# camera file's picture_profile_in_use) and its copies; and the other settings Different Set for Still/Mv keeps per
# mode, each a live record with a Stills and a Movie copy. The rule that the live value equals one of
# its copies, and the stronger one that in each section it equals the copy of that section's mode (COPY_MODES), were
# checked on the camera's downloads (2026-11-10), and the writer reads a sample of them again at every write
# (copies.with_copies). Exposure Comp.'s three records are a family too: 0x0340 the setting, as the other families'
# records in use sit beside it (ISO 0x0334, Metering Mode 0x0350, White Balance 0x0367) and the holds' table is lent
# from it (HOLD_TABLES), 0x0e16 (in the block of the per-mode copies) and 0x13d6 its copies; which copy is which mode's
# is not known yet, so they carry no copy_for (COPY_MODES_UNKNOWN)
PP_PARAMETERS = range(0x04e9, 0x0b1a, 0x42)
COPIES = {**{f"global:0x{r:04x}[{i}]": [f"global:0x{r + 0x16:04x}[{i}]", f"global:0x{r + 0x2c:04x}[{i}]"]
             for r in PP_PARAMETERS for i in range(11)},
          "global:0x0053": ["global:0x0e12", "global:0x0e14"],             # Picture Profile
          "global:0x0334": ["global:0x0df2", "global:0x0df4"],             # ISO
          "global:0x0350": ["global:0x0e06", "global:0x0e08"],             # Metering Mode
          "global:0x0367": ["global:0x0e0e", "global:0x0e10"],             # White Balance
          "global:0x0dfa": ["global:0x0dfc", "global:0x0dfe"],             # ISO AUTO Minimum
          "global:0x0e00": ["global:0x0e02", "global:0x0e04"],             # ISO AUTO Maximum
          "global:0x0340": ["global:0x0e16", "global:0x13d6"],             # Exposure Comp.
          "global:0x0b91": ["global:0x0b93", "global:0x0b95"]}             # White Balance's colour temperature
# White Balance's fine-tune, A-B and G-M of each preset Movie mode offers too (Flash has no Movie copy): the record in
# use (0x0c4d A-B and 0x0c6b G-M, two apart, Flash's place among them kept), its Stills copy (0x0e99 A-B, 0x0ed1 G-M,
# four apart) and its Movie copy two above that, as the White Balance rows proved them (kit2_pass2, grids in Stills and
# in Movie mode); the copies are named "(…, stills)" and "(…, movie)" (RECORD_FIXES below)
WB_FINE_PRESETS = ("AWB", "Daylight", "Shade", "Cloudy", "Incandescent", "Fluor.: Warm White", "Fluor.: Cool White",
                   "Fluor.: Day White", "Fluor.: Daylight", "Flash", "Underwater Auto", "C.Temp./Filter")
_WB_MOVIE = [p for p in WB_FINE_PRESETS if p != "Flash"]
for _axis, _live, _copy in (("A-B", 0x0c4d, 0x0e99), ("G-M", 0x0c6b, 0x0ed1)):
    for _p in _WB_MOVIE:
        _st = _copy + 4 * _WB_MOVIE.index(_p)
        COPIES[f"global:0x{_live + 2 * WB_FINE_PRESETS.index(_p):04x}"] = [f"global:0x{_st:04x}", f"global:0x{_st + 2:04x}"]
        RECORD_FIXES[f"global:0x{_st:04x}"] = {"name": f"WB fine-tune {_axis} ({_p}, stills)"}
        RECORD_FIXES[f"global:0x{_st + 2:04x}"] = {"name": f"WB fine-tune {_axis} ({_p}, movie)"}
# the families whose copies' modes are not known yet: no copy_for, and the write checks the weaker rule (the setting
# equals one of its copies) in every section
COPY_MODES_UNKNOWN = frozenset({"global:0x0340"})
# the modes whose value each copy is, by its place in COPIES (copy_for): the Stills copy Stills', the Movie copy that of
# Movie, S&Q and Time-lapse, which use the Movie set (Movie and S&Q choices write it; the switch to Movie loads it)
COPY_MODES = (["Stills"], ["Movie", "S&Q", "Time-lapse"])
# values offered under one video system only (video_system_values, kit/writer/offered.py) where no proof walked the
# row under each system: the key, its values by system (both keys, the other system's empty when every listed value is
# one system's; the evidence is the hand evidence's). Every PAL rate is stored one code above its NTSC counterpart,
# and the PAL lists the kit walked (Movie, S&Q, Time-lapse, 2026-11-06) offer neither 60p nor 30p: the rule the
# entries lean on
VIDEO_SYSTEM_VALUES = {
    # USB Streaming's Output Res/Frame Rate: proved by hand on NTSC (runs/kit2_usbstream, 2026-11-02, before the camera
    # was first set to PAL); 7 (HD (1080p) 25p) is 6's PAL counterpart
    "global:0x02b3": {"NTSC": [0, 2, 4, 6, 8], "PAL": [7]},
    # XAVC HS 8K's Rec Frame Rate: its NTSC list walked whole (30p, 24p); under PAL its list holds a single rate, none
    # of the codes listed here, which is all the record held through the PAL walk with that format chosen
    # (runs/kit2_pal_mv5, 2026-11-06)
    "global:0x0202": {"NTSC": [2, 4], "PAL": []},
    # the HDMI 4K output rate and the RAW output rate are not here: neither list was walked under PAL, and the camera's
    # PAL downloads hold one of their NTSC-named values (2026-11-10), so the rule alone does not say what such a list
    # offers; their values stay under neither system until a walk under PAL shows otherwise
}
# each layout's model appendix (docs/models/): identify.py and the editor name it beside the schema
LAYOUT_DOCS = {"07a5b07a502c68f0": "docs/models/ILCE-1M2_fw4.00.md"}
# rows proved holding the camera one way (Switch V/H AF Area on, the camera turned by hand)
ORIENTED = re.compile(r"\[Switch V/H AF Area = [^,\]]+, camera (level|grip down|grip up)\]$")

# OCR slips in function names the old kit's crawl left in the schema, each checked on a frame of
# the camera's own picker (2026-10-29): applied to every record before anything is compared
LABEL_FIXES = {
    "faRegist. Face Priority": "Regist. Face Priority", "fhRegist. Face Priority": "Regist. Face Priority",
    "SRegist. Face Priority": "Regist. Face Priority", "S&d Record Setting": "S&Q Record Setting",
    "Sad Frame Rate Settings": "S&Q Frame Rate Settings", "Reg. AF AreatAF On": "Reg. AF Area+AF On",
    "Subject Reccgnition AF": "Subject Recognition AF",
    "Tracking On E + A5": "Tracking On (frame icon) + AF On",      # 2499; 834 is "Tracking On + AF On"
}

# records first proved through a checklist, named as their neighbours already are
NEW_CHECK_NAMES = {
    "global:0x0cb4": "Monitor: Display All Info.", "global:0x0cb9": "Monitor: Monitor Off",
    "global:0x0cba": "Finder: Display All Info.",
    "global:0x1903": "Finder: No Disp. Info. exposure display",
    "global:0x1904": "Finder: Histogram exposure display",
    "global:0x1905": "Finder: Level exposure display",
}

# The camera's own names for its menu groups (2026-11-03). Breadcrumbs read off the screen came cut ("Image
# Qua...", "Shutter/Si... › Target Function Settings"), and the Network tab's first group was read with its icon
# as a letter ("DCnct./Remote Sht.") or one letter short ("Cnct./Remote Sh."); the Help Guide's list names it
# "Cnct./Remote Sht.". The editor shows a setting's group as the schema has it.
GROUP_NAMES = {"DCnct./Remote Sht.": "Cnct./Remote Sht.", "Cnct./Remote Sh.": "Cnct./Remote Sht.",
               "DCnct./Re...": "Cnct./Remote Sht."}

# whose values a Shoot Mode family's descriptions explain: the family's own mode record (the project log, pass 3,
# Shoot Mode through the menu). Stills has none of its own; its custom-hold sets' Shoot Mode is stills only.
# 0x10b6, the mode in use, is left out: its values mean a different mode in each family.
SHOOT_MODE_RECORDS = {"Movie": ["global:0x13e1"], "S&Q": ["global:0x13e2"], "Time-lapse": ["global:0x13e3"],
                      "Stills": ["global:0x0bd5[0]", "global:0x0bd5[1]", "global:0x0bd5[2]"]}
MODE_LETTERS = {"Program Auto": "P", "Aperture Priority": "A", "Shutter Priority": "S", "Manual Exposure": "M"}

# Why no proof can reach a record (unproved_reason, written only while the record has no proof; the kinds are the
# definition schema's): each reason in a photographer's words, and the day it was settled, which is evidence (None
# here: the hand evidence gives it; 2026-11-09, the owner: the records left "not proved" each say why). The
# setting's note keeps the evidence. A working value the camera keeps for itself is "state"; a value only the camera's own saves write, which a file taken over a remote connection never shows
# changed, "camera_only"; a row greyed without equipment the camera was not proved with, "equipment"; a network block,
# changed by hand only (decision 8), "network"; one every candidate row was tried on, none moving it, "unknown"
_STATE = "state"
UNPROVED = {
    "global:0x1672": (_STATE, None,
                      "A flag the camera keeps for itself, not a menu setting: Screen Reader and Disp Set of Multi "
                      "Media, once thought to move it, leave it as it is."),
    "global:0x04e2": (_STATE, None,
                      "The camera sets it from how it is held, level or vertical, whatever a settings file says: a "
                      "working value, not a menu setting."),
    "global:0x13d1": (_STATE, None,
                      "A working value the camera keeps: it moved when the connection screens were opened, never with "
                      "a menu choice."),
    "global:0x13d2": (_STATE, None,
                      "A flag the camera turns on the first time PC Remote priority is chosen over a remote connection, "
                      "and keeps when the camera's priority is chosen again: no menu row writes it."),
    "global:0x13d3": (_STATE, None,
                      "A flag the camera turns on with the one beside it, the first time PC Remote priority is chosen "
                      "over a remote connection: no menu row writes it."),
    "global:0x0c46": (_STATE, None,
                      "The camera flips it each time a settings file is loaded: a working value, not a menu setting."),
    "global:0x18cb": (_STATE, None,
                      "The camera's working copy of a Recall Custom hold, filled from whichever hold's registration "
                      "screen was opened last: no setting of its own."),
    "global:0x1126": (_STATE, None,
                      "A state the camera keeps: no menu choice writes it, a settings file does not set it, and only "
                      "Camera Settings Reset and Initialize change it."),
    "global:0x0c09": (_STATE, None,
                      "A stamp the camera writes when a Recall Custom hold is registered, not a value a menu chooses."),
    **{f"global:0x{rid:04x}": ("camera_only", None,
                               "The camera writes it only on its own saves, a settings file saved from its menu or a "
                               "memory registration: moving the focus frame leaves it, and a file taken over a remote "
                               "connection never shows it changed, so no remote proof can reach it.")
       for rid in (0x0f24, 0x0f26, 0x0f28, 0x0f2a)},
    **{f"global:0x{rid:04x}": ("equipment", None,
                               "Greyed on this camera without a RAW recorder connected over HDMI: it can be proved "
                               "with one attached.")
       for rid in (0x0495, 0x0496)},
    "global:0x018b": ("network", None,
                      "Part of the camera's network settings, which are changed by hand only, never over a remote "
                      "connection, so no proof is made of them."),
    "global:0x0392": ("unknown", None,
                      "Every menu choice tried left it as it was: Focus Area's every area, in Stills and in Movie mode. "
                      "What writes it is not known."),
    "global:0x1479": ("unknown", None,
                      "Every menu choice tried left it as it was: Aspect Marker Level at several levels and under "
                      "another marker type, and the Movie menu's Aspect Marker list. What writes it is not known."),
}

# Last: each table's evidence put back from the private overlay, private/evidence/ILCE-1M2_fw4.00.hand.json
# (writer/hand_evidence.py): the hand proofs' values, runs, days and menu rows, the sample counts, the owner's
# allowances, the notes' evidence, what shows each not-offered mark, the day each reason was settled. The file read, or
# None on a clone without it (CI, a fresh clone), where kit/schema_update.py --write refuses to write the definition
HAND_EVIDENCE = hand_evidence.put_back(globals(), paths.A1II)
