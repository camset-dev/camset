# 26. A user LUT reaches the camera only through the kit's import tool

- **Date:** 2026-11-19
- **Status:** accepted
- **Never broken:** 14th in AGENTS.md's list
- **Rule:** A user LUT reaches the camera only through `kit/tools/lut_import.py`, run on the owner's word for that run:
  a `.cube` file from that clone's `private/lut/`, by Sony's documented ImportLUTFile, into an empty user place (one the
  camera does not list as holding a LUT; 16 unless the owner names another), never as a settings file and never through
  Manage User LUTs' Import on the camera's menu, which no run opens. No settings file takes it off: it stays on the
  camera until the owner deletes it there by hand. On every camera the default is no, until its owner says so for the
  run.

## Context

Two of the a1 II's rows need a user LUT in the camera to be mapped: Manage User LUTs and its Import/Edit. The menu's
Import loads a file from a card, which no run opens ([decision 8](0008-by-hand-only-usb-language-region-and-network-identity.md),
and [decision 24](0024-a-look-lap-opens-every-row-to-look-at.md)'s "what loads"), and
[decision 6](0006-no-hand-made-settings-files.md) said the kit uploads only files the camera wrote. Asked on 2026-11-19 whether that rule might change "so a Sony .cube from
private/lut can be imported into an empty user place by the kit's tool, on your word", the owner chose "Change the rule":
a new record for the one tool, and decision 6 narrowed to settings files. A LUT replaces no setting; Sony publishes the
look profiles and documents the import in its SDK's reference.

## Decision

The owner's word is given to the agent for the run, as an allowance is (the playbook's section 1): the tool asks nothing
more today, no flag carries the word, so an agent runs it only when its owner said so for that run, and never on its
own. The a1 II's owner allowed one import into User16 on 2026-11-19.

How the kit holds to it, in three places that each refuse before anything is sent (`kit/camkit/link.py`'s
`lut_refused` and the guard on the line, then camlink's `kit/common/lut_file.h`): the file's real path inside the
clone's `private/lut/`, never through a link, `.cube`, a name and size Sony's reference takes, a .cube LUT's text, its
bytes the SHA-256 the run logged; a user place 1-16; then, read on the camera and never set, the import enabled, the
camera not recording, and the place not among the user LUTs it offers to delete. One SDK call, no key pressed, nothing
on the screen answered; only the camera's `ImportLUTFile_Result_OK` counts as an import. The run starts from a known
file and ends restoring it ([decision 15](0015-every-run-starts-from-a-known-file-and-ends-restoring-it.md)) and says which records did not go back: the LUT is live state no settings file
holds, which the owner puts back by deleting it. The kit deletes no LUT. What the run learns goes into the coverage
ledger by record key alone ([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): a LUT's
records may hold its name, a value.

## Consequences

`kit/tools/check_public.py` counts `private/lut/` among the places a public file may name
([decision 18](0018-one-public-codebase-with-a-private-overlay.md)). A second
import into a place that holds a LUT is refused until the owner deletes it.
