# 26. A user LUT reaches the camera only through the kit's import tool

- **Date:** 2026-11-19
- **Status:** accepted
- **Never broken:** 14th in AGENTS.md's list
- **Rule:** A user LUT reaches the camera only through `kit/tools/lut_import.py`, run on the owner's word for that run,
  which the run carries as `--allow "Manage User LUTs"`: a `.cube` file from that clone's `private/lut/`, by Sony's
  documented ImportLUTFile, into user place 16, and only where the camera's own Import/Edit table was seen to show it
  empty since the last import, never as a settings file and never through Manage User LUTs' Import on the camera's menu,
  which no run opens. No settings file takes it off: it stays on the camera until the owner deletes it there by hand. On
  every camera the default is no, until its owner says so for the run.

## Context

Two of the a1 II's rows need a user LUT in the camera to be mapped: Manage User LUTs and its Import/Edit. The menu's
Import loads a file from a card, which no run opens ([decision 8](0008-by-hand-only-usb-language-region-and-network-identity.md),
and [decision 24](0024-a-look-lap-opens-every-row-to-look-at.md)'s "what loads"), and
[decision 6](0006-no-hand-made-settings-files.md) said the kit uploads only files the camera wrote. Asked on 2026-11-19
whether that rule might change "so a Sony .cube from private/lut can be imported into an empty user place by the kit's
tool, on your word", the owner chose "Change the rule": a new record for the one tool, decision 6 narrowed to settings
files, and one import into User16. A LUT replaces no setting; Sony publishes the look profiles and documents the import
in its SDK's reference.

## Decision

The owner's word for the run is the run's `--allow "Manage User LUTs"`: the agent passes it only when its owner said so
for that run (the playbook's section 1), the tool stops before anything connects without it, and the run's
`events.jsonl` and `lut_import.jsonl` keep it. Place 16 is the only place, in the tool, `kit/camkit/link.py` and
camlink alike. The a1 II's owner allowed one import into User16 on 2026-11-19, "into an empty user place".

Empty is what the camera's own Import/Edit table shows, seen: no property Sony documents tells an empty place from a
held one, and DeleteUserBaseLook lists every place (the a1 II listed 1 to 16 and All on 2026-11-19 with all sixteen
empty). The tool's `--seen-empty` names a frame of a look at Manage User LUTs > Import/Edit made with `kit/drive.py`
(nothing chosen) on which the kit's own OCR reads User16's row as "User16: (No Import)", taken after the last import
the camera was asked for and at most an hour before this one, on the same day; the frame, its SHA-256 and the row as read
are logged. After an import the same look is made again, so the row's new reading is on record.

How the kit holds to it, in three places that each refuse before anything is sent (`kit/camkit/link.py`'s
`lut_refused` and the guard on the line, then camlink's `kit/common/lut_file.h`, against the clone's folder it was
built with): the file's real path inside the clone's `private/lut/`, never through a link, `.cube`, a name and size
Sony's reference takes, a .cube LUT's text, its bytes the SHA-256 the run logged; the look above, in the tool; then,
read on the camera and never set, the import enabled, the camera not recording, and its list of user places readable
and holding nothing no reading of it explains. The SDK
gets a copy of the bytes checked, in a folder only the user can open, never the file. One SDK call, no key pressed,
nothing on the screen answered; only the camera's `ImportLUTFile_Result_OK` counts as an import, and an answer that does
not come is restored by hand, nothing more sent. The run starts from a known file and ends restoring it
([decision 15](0015-every-run-starts-from-a-known-file-and-ends-restoring-it.md)): a record that does not go back fails
the restore unless the camera's not-by-file list names it as holding a user LUT. The kit deletes no LUT. What the run
learns goes into the coverage ledger by record key alone
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): a LUT's records may hold its name, a
value.

Before the camera's first run of the tool (2026-11-19) the Rule line took place 16 for empty "while the camera does not
list it as holding a LUT", read from DeleteUserBaseLook, which lists every place.

## Consequences

`kit/tools/check_public.py` counts `private/lut/` among the places a public file may name
([decision 18](0018-one-public-codebase-with-a-private-overlay.md)). A second import needs a look taken after the
first, which shows place 16 held until the owner deletes the LUT.
