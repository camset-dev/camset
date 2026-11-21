---
render_macros: true
---
# Data files and their schemas

Each data file names its [JSON Schema](https://json-schema.org/) (draft 2020-12) in `schemas/` with a `$schema` key,
so an editor or `check-jsonschema` checks it. Below, each file's purpose and what writes it, then its schema's own
description and fields, printed from the schema, the one place each field is defined. How the kit checks or derives a
field is in that field's description or in the docstring of the code it names.

## What a mapping delivers

A camera's results are one folder, `data/<model>_fw<fw>/`, the definition `kit/schema_update.py --write` writes from
it and the proofs, `editor/definitions/<model>_fw<fw>.json`
([decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md)), and the model's page,
`docs/models/<model>_fw<fw>.md`, whose entry in `mkdocs.yml`'s nav `kit/tools/build_docs.py` writes. The a1 II's
folder, `data/ILCE-1M2_fw4.00/`, is the pattern for each file. With the definition come its record names for Kaitai's
tools, `docs/formats/sony_camset_ids_<model>_fw<fw>.ksy` ([the file format](formats/index.md)), which
`kit/tools/build_docs.py --no-viewer` writes from it (the pre-commit hook runs it at each commit); CI's
`build_docs.py --check` fails a pull request without it. The definition and `data/` hold only what is the same for any
owner; how each thing was proved stays in private files beside your runs, never in the submission
([below](#the-mappings-evidence)).

The definition's sample, `editor/definitions/<model>_fw<fw>.DAT`, is the one settings file published: a download the
camera wrote right after Initialize, never the owner's own file, its personal text and the records its camera file
lists in [`personal_records`](#records-that-hold-an-owners-own-data-personal_records) zeroed by
`kit/tools/make_sample.py`. Its docstring (`kit/tools/make_sample.py`) says how the Picture Profile parameters
Initialize leaves are taken from each profile's own Reset, and the limits of that evidence.

| File | How it is made | Needed |
|---|---|---|
| `camera_<model>_fw<fw>.json`: the camera's own facts (its container block, tabs, memories, link-critical and volatile records, the records that hold an owner's own data, its wording) | By hand; the container block from `kit/tools/identify.py`'s draft when no known block reads the camera's files | Yes: the definition's `camera` section is copied from it, and the kit reads the camera's files through its block |
| `help_guide_menu_<model>_fw<fw>.jsonl`: the Help Guide's menu list | By hand, from Sony's published Help Guide: one line per item with its tab, group, name and modes, and no other text of Sony's (decision 13) | Optional: `kit/schema_update.py` and the safety review (`python -m camkit.safety`) read it |
| `help_<model>_fw<fw>.json`: each setting's help | By hand, in your own words, never Sony's (decision 13): what each setting a person meets in the menus does; records shown in Expert mode only get none | Optional |
| `hand_tables_<model>_fw<fw>.json`: what the mapping found by hand | By hand, as the mapping finds each fact (the playbook, Phase 6), never by a kit step | Optional: `kit/schema_update.py` applies it to the definition ([below](#the-hand-tables-file-what-the-mapping-found-by-hand)) |
| `settings_reset_<model>_fw<fw>.json`: which settings Camera Settings Reset and Initialize put back | By hand, from the downloads before and after each reset, only where the owner allows one (the playbook, Phase 5) | Optional: the model page shows it |
| `seen_<model>_fw<fw>.json`: the facts your looks established that hold for every camera of the model | `kit/tools/coverage.py --write`, where your looks file is | Optional: the coverage ledger's public form is built from the public sources and this file ([below](#the-coverage-ledger-what-is-settled-and-what-a-proof-needs)) |

What would differ between owners stays with whoever maps the camera, in `private/evidence/<model>_fw<fw>/`: the menu
tree ([below](#the-menu-tree-the-cameras-menus)), the accepted rulings
([below](#the-accepted-file-what-the-report-leaves-open)), the record shapes (the value shapes of the records no
setting covers, which the proof viewer shows), and the coverage ledger's looks file and private form.
`kit/tools/check_public.py` refuses each in `data/`: one found there is moved by hand into that folder. It refuses
the coverage ledger's public form there too, which is printed and never kept. Pass 1's map, `runs/<model>_fw<fw>/kit2_pass1/map_all.json`, stays with the runs, written by `kit/pass1_map.py`.

The pre-commit hooks and CI (`.github/workflows/kit-ci.yml`) check every definition and every data folder's camera,
help, reset, hand tables and seen files against their schemas; the Help Guide's menu list has none yet. The
kit's tests check the menu tree, the accepted file, the hand evidence file and the looks file against theirs where they
are present.

## `editor/definitions/<model>_fw<fw>.json`: what every record means

Written by `kit/schema_update.py --write` for the camera the kit works on, on the machine that holds its runs, never by
the pre-commit hook; `kit/tools/build_docs.py --definitions` brings every definition's parts from `data/` up to date
without runs. The editor ships the ones in `editor/definitions/` and reads the user's own too (the editor's guide,
"Definitions"). Schema: `schemas/definition.schema.json`.

{{ schema_fields("definition") }}

### A setting

{{ schema_fields("definition", "$defs/setting") }}

### The mapping's evidence

A definition says what the camera is, never how, when, in which run or from which state each thing was proved
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): two owners who map the same
model and firmware completely get the same definition. `kit/schema_update.py --write` writes the public file lean and
what it leaves out into `private/evidence/<model>_fw<fw>.json`, in the private overlay, never submitted
([decision 18](decisions/0018-one-public-codebase-with-a-private-overlay.md)). By setting key, that file holds
`source`, `note_evidence` (the owner's word among it), `in_sets_proved` and `menu_blocked`, the whole proof behind the
public lean `proved` (its run, day and menu rows, each value name's source, a sample's count), the dates of
`unproved_reason` and `unproved_sets` and what shows each `not_offered` mark; and a layout's `note_evidence`. The kit
reads the two put back together; the editor, the docs site and the generated files read the public file alone, and
`kit/tools/check_public.py` refuses a definition that carries any of the evidence, a run's name or a date. How the two
are split and merged, and what a write does with evidence that no longer fits (`--drop-stale`, `--accept-stale`,
`--finish-write`), is in `kit/camkit/definitions.py`'s docstring. The hand tables' evidence has a file of its own
([below](#the-hand-evidence-file-how-each-hand-fact-was-proved)).

### Where a setting sits on the camera (`row`, `row_at`, `under_option`, `row_tab`, `row_group`, `row_mode`)

`kit/schema_update.py` hangs each setting on the row of the camera's menu tree (the mapper's own, in
`private/evidence/<model>_fw<fw>/`) that its proof paths lead to, with `kit/camkit/placement.py`, the placement the
proof viewer uses too, and writes the six fields from it; without the tree or the evidence the places stay as written.
The editor lays a tab out from them alone ("As on the camera"). A proof path steps into a row's submenu with ` > `,
names an option of the row with ` / `, and ends with the proof's context in brackets; where two rows under one row
bear one label, `#n` names the n-th of them, from 0 ("Rec. Media Settings > Recording Media#1", the movie one). A
path that names an option and
steps below it is on the page that option opens: "Picture Profile > PP2 > Black Gamma > Level" gives `row`
`["Picture Profile", "PP2", "Black Gamma", "Level"]` and `under_option` "PP2". `order` sorts a setting in the editor's
"Flat list", by the top row of its group that its proof went through; one that went through none sorts after those
rows, and a record the plain pass adds takes the number after the definition's highest. A setting no path places gets
none of the six fields, and the editor lists it after the camera's rows, under "More settings in this group".

Where the camera's hand tables hold `MENUS` (a menu for each position of its shooting-mode switch: the a1 II's Still,
Movie and S&Q), the definition carries them as `camera.menus`, and each placed setting the menus that hold it
(`row_menus`, in `MENUS`' order; `kit/camkit/placement.py`, `by_menu`):

- **Where a menu's own tree holds the setting's row.** The top row is matched by the merged numbering of a tab's top
  rows, which serves every menu, and each row below by its label among the rows that menu read. A row that menu's
  walk read as a list or checklist, with nothing read below it, holds a setting whose last label one of its options
  names: Movie's Playback Filter Condition, a checklist of the items the Stills menu holds as rows.
- **Where proofs made in one of the menu's modes reach the row.** A proof made in a mode is that mode's reading of
  the row. The mode is the one a proof's context names; for a proof whose context names none, it is the one the
  camera's own files say it was made in, which the writer keeps in the proof's evidence. A proof whose base download
  is gone gives no mode: it adds no menu by its mode, not even the Still menu's, though it still places its setting.
  Rows the menu never read are then taken from those proofs' paths, in the setting's own order.
- **Rows given by hand.** `HAND_PLACES` gives the row of a record no proof path places: one a row's own function
  writes, or a row the walk can never read, seen on the camera. Such a row is in every menu whose tree has its top
  row. Its public entry is the row alone; why it is the record's is in the private hand evidence.

`row_places` gives a menu's place where it differs from the setting's own: always with its `row` and `row_at`, and
with `"under_option": null` where that menu has no option the setting's own place has. No place rests on My Menu's
item pages. A menu's place keeps the setting's own order in two cases: among rows that menu read turned round (from
the row the camera held), and below rows the setting's own menu never read. Nor does it rest on where an option
list's reading began. The setting's own place takes its own menu's walk as it read the rows, and that walk may itself
have begun at a held row.

**`row_menus` follows the mapping.** It follows how deep each mode's walk read and in which modes the proofs were made.
A setting proved only in Stills is not in the Movie menu until Movie's walk reads its row or a proof is made there, even
where the camera shows it. So two owners of a model get the same `row_menus` only once the mapping is complete.
`kit/schema_update.py` prints, at every pass, the settings listed in fewer menus than their top row stands in, and the
menus each lacks. A row whose walk in a menu found that Right opens nothing there (it draws no ›) holds no rows in that
menu, so the settings below it elsewhere are not counted as open work for it; the print names each such row apart, as
one crawl's reading. A write that would list a setting in fewer menus than the definition there does says each and
stops, unless it is run with `--accept-lost-menus` and their count.

**Two rows of one label.** Where the camera tells two rows of one label under one row (or two top rows of one tab)
apart by an icon alone, the camera's `ROW_ICONS` hand table gives each icon's words by the row's path (its tab, its top
row's group, then its labels, "label#n" for the n-th), and the definition says them in `row_icons` beside `row`, one
item a level, the words or null, in a place and in a menu's place alike; `row` keeps the camera's own labels, and an
editor draws "Custom Key/Dial Set. (Movie)" from the two. A `ROW_ICONS` entry or a `HAND_PLACES` row that names its
group stops the write where that group no longer holds the row it names.

A write with the menu tree on the computer writes these from `MENUS`, and none of them without it. With no menu tree
there (a fresh clone, CI) it leaves the definition's as they are, as it does the places. A write from a definition read
without its proof paths (its evidence file not on the computer) leaves every place and these fields as they are too,
whatever paths the pass adds to a few settings, unless the definition held no place at all (a new camera's first pass).

### What the editor offers outside Expert mode

Outside Expert mode the editor offers a setting's values only where a proof on the camera established them, read from
the setting's `proved`; of any other it says that it is not checked on the camera yet and the camera may refuse a file
holding it, and Expert mode's "Offer values…" brings those back. A setting with no `proved` offers every value. A value
is established when its scale was proved by samples on a straight line (`proved.sampled.linear`: every value of the
list, every number of a range), or when `proved.values` lists it: the values a proof chose and those whose name has a
source on the camera (`ESTABLISHING` in `kit/camkit/definitions.py`), never a name a hand table gives that no proof and
no other setting's proof covers (`counted`, in both of the writer's passes). `proved.values` also lists a value a rule
named from another setting's proof, one that offers the same list (a picker's slots, one array's elements, a hold and
its live setting, a copy), where no proof chose it on this one; the setting then carries `proved.shared: true`, and
which values are such only the private evidence says, for the one value no proof chose can be the owner's own
([decision 25](decisions/0025-a-proof-says-when-its-list-was-lent-by-another-setting.md)). The editor offers those
values as any proved one but never calls them checked on the camera. Every write names values afresh from that
write's proofs and tables: a name no rule gives any more leaves the list. A value the menus never offer
(`not_offered`) is left out whatever its proof. Nothing in a definition tells what the owner's camera held:
`kit/writer/proofs.py` (`without_observed`, `without_written_with`, `without_held`) and `kit/pass2_report.py`
(`start_lines`, `sampled_from_start`) say what each write leaves out, and the schema refuses those fields. Nor does a
public list ever stop one value short of a value its own camera held, for the gap would name it: every write, a look
or `--write`, counts each list one value short in its gate line, a value a `not_offered` mark names, one its
`video_system_values` list under the other video system than the proof's values, or an `unproved_reason` covers aside
(the mark says why, the same for every owner), and lists it with whether a start file of
the camera held the missing value (`kit/writer/listgaps.py`, never which value). One no start file held, or with none
here to tell, a ruling of kind "one value short" in the accepted file accepts by its key; one a start file held is
never accepted, and `--write` refuses until the value is proved from another start, a held `not_offered` mark says the
camera holds it from the factory and no list chooses it back, or a reason keeps the setting out.

### When the camera greys a row (`inactive_when`, `inactive_if`, `grey_in`)

- **`inactive_when`:** the camera greys the row while another record holds certain values.
- **`inactive_if`:** the same rule, true only in some shooting modes (`family`) or only with a device on the HDMI
  socket (`hdmi_device`). It is a key of its own: an editor that predates it ignores it rather than showing a false
  grey.
- **`grey_in`:** the shooting modes in which the camera draws the row grey whatever the file holds.
- **Mode names:** both name modes as `camera.live_mode` does, never menus, since one menu (the a1 II's S&Q) serves two
  modes. A menu's view dims a row only where the rule holds in every mode the view stands for: the file's own mode when
  it is one of the menu's, else all of the menu's modes. Otherwise the view says the condition beside the row, and it
  never dims on a cable it cannot see.
- **Where they come from:** `grey_in` and `inactive_if` come from `RECORD_FIXES` alone; an older `inactive_when` may
  have no entry. `"inactive_when": null` takes a rule found wrong out, and a `grey_in` or `inactive_if` the tables stop
  giving leaves the definition.
- **What the writer refuses:**
  - any rule on the live-mode record;
  - a mode the row's menus do not serve;
  - on the mapper's computer, an entry whose `looks` in the hand evidence miss a side.

  `kit/camkit/grey_rules.py` says each check.

### A picker's list walked whole (`PICKER_LISTS`)

A first kit gave every function picker of a camera one list, the union of every function code it met in any of them.
Where a picker's list was walked whole on the camera, the camera's `PICKER_LISTS` hand table cuts each setting it
covers to exactly the codes the walks wrote (`walked_lists` in `kit/writer/offered.py`, whose docstrings give every
condition: each refuses rather than guesses, and a value a proof, the sample or a download holds outside the walked
codes stops the write). Use it for codes no list of that picker's screen offers. A code the same screen's other keys
offer but this one's list leaves out, or a factory value its list cannot choose back, is a `NOT_OFFERED` mark instead.

### Values the menus never offer (`not_offered`)

A value a setting lists that the camera's menus never offer is marked, with why in plain words and the menu whose list
leaves it out. The marks are the camera's `NOT_OFFERED` hand table; `kit/writer/offered.py` writes a mark only while
its evidence, in the hand evidence file, holds, and a later walk that writes the value drops it. A `held` value, one
the camera writes itself though its list cannot choose it back, stays offered. An option refused under another setting
is never this: such refusals (`menu_blocked`) depend on the camera's state and stay in the evidence.

### A value kept in more than one record (`copies`, `copy_of`, `copy_for`, `keeps_apart`, `camera.live_mode`)

The camera keeps some values in a live record and per-mode copies beside it (each Picture Profile parameter in use, the
profile in use, the settings Different Set for Still/Mv keeps per mode), and some in memory set records it writes alike
(the a1 II's Zone place for each way of holding the camera, its copies no shooting mode's). The one rule every file the camera writes
keeps: in each section the setting equals the copy for that section's mode (`copy_for`; the live settings' mode by
`camera.live_mode`, a memory set's by `camera.memory_sets.modes`), and where the mode or the copies' modes are not
known, it equals at least one of its copies. What follows an edit is the copies rule (`copies`, `copy_of`);
`keeps_apart`, on a switch of the camera's own, says what the switch did on the camera, for the editor to tell and ask
about, never to decide by (the editor's guide). The families and their modes are the camera's `COPIES`, `COPY_MODES`,
`COPY_MODES_UNKNOWN` and `KEEPS_APART` hand tables; `kit/writer/copies.py` writes the fields and checks them against
the camera's own downloads at every write, keys, mode names and the switches' value codes only. No copy shares its setting's name: "… (stills)"
and "… (movie)", or "… (copy 1)" and "… (copy 2)" where its mode is not known yet (a test checks it). What the a1 II's
boxes were proved to do is on [its page](models/ILCE-1M2_fw4.00.md).

### Two limits kept in order (`at_most`, `at_least`)

A lower limit the camera never lets past its upper (the a1 II's ISO Range Limit ends, ISO AUTO's Minimum and Maximum
and their copies) names the upper in `at_most`, and the upper names it back in `at_least`; `moves_it` says a proof
showed a value chosen past the other move the other to it. The order is each value's place in the two lists, which
list the same values. The camera's `LIMIT_PAIRS` hand table names the pairs; `kit/writer/limits.py` writes them and
checks the order against the camera's downloads at every write.

### How far a focus frame travels (`frame`)

Each Focus Area option's frame stops at limits of its own, and several options keep their frame's centre in the same
records, so a record's `range` cannot hold them: each record of a frame's place carries `frame`, its axis, the place's
other record and the limits by area, from the camera's `FRAME_TRAVEL` hand table (`kit/writer/frames.py`). A box whose
size the file holds has one rule instead: the bounds it stays inside and its size records, read in the same section. A
place not measured yet carries none. Where the limits change with another setting (the a1 II's Aspect Ratio), the
frame names it (`by`), read in the same section, and each limit the values it is for; a box's rule then gives each
value's picture. Where the shooting mode decides which limits hold (`in_modes`), a section's mode is the one
`camera.memory_sets.modes` lists its memory set under (the live settings': `camera.live_mode`): its modes read `by`,
or take the limits for one value of it without reading it, measured or inferred; a mode no entry names has none.

{{ schema_fields("definition", "$defs/setting/properties/frame") }}

Each of its `limits`:

{{ schema_fields("definition", "$defs/setting/properties/frame/properties/limits/items") }}

Each of a box limit's `pictures`:

{{ schema_fields("definition", "$defs/setting/properties/frame/properties/limits/items/properties/pictures/items") }}

## `data/<model>_fw<fw>/camera_<model>_fw<fw>.json`: the camera's own facts

Schema: `schemas/camera.schema.json`.

{{ schema_fields("camera") }}

### The container block (`file`)

`kit/tools/identify.py FILE.DAT` says which block reads a file, and for a file none reads prints a draft to correct by
hand: the block is right when the file reads and both checksums hold. The editor reads a file by trial, once for each
distinct block of its definitions: the magic, then the model and the firmware, which pick the definition, then the
framing, which its trailer checksum must confirm. `docs/formats/sony_camset.ksy` describes the ILCE-1M2's container
for Kaitai's tools and ImHex, tied to its block by a test.

{{ schema_fields("camera", "$defs/file_block") }}

A checksum (`header_checksum`, `trailer_checksum`):

{{ schema_fields("camera", "$defs/checksum") }}

The firmware (`firmware`):

{{ schema_fields("camera", "$defs/file_block/properties/firmware") }}

The records' framing (`records`):

{{ schema_fields("camera", "$defs/file_block/properties/records") }}

### Records that hold an owner's own data (`personal_records`)

To find a body's personal records: download; ask the owner to change one such thing on the camera, by their own hand (register a lens
to a preset slot they do not use: it needs a held custom key or the lens's ring, and overwrites the slot; set the
file-name prefix); download again and compare the two (`kit/tools/upload_check.py --diff REF TAG` lists the records
that differ). Every record that changed goes in: under `zeroed` when any value of it is the owner's, under `defaults`
with the camera's own default bytes when it has one. The bytes the diff prints are the owner's (a lens's name, its
serial number): copy them nowhere, not into notes, the camera file or a message; only the records' ids go into the
list. A default's bytes go into the published sample, so read them from the file the camera wrote right after
Initialize, the one `make_sample.py` is given, never from the owner's working file:
`.venv/bin/python -c "import sys; sys.path.insert(0, 'kit'); from camkit import camset; print(camset.read('SRC.DAT').get(0, 0x0b5b).raw.hex())"`
prints them, with that file in place of `SRC.DAT` and the record's id in place of `0x0b5b` (on Windows
`.venv\Scripts\python`). If Initialize left the owner's value in that record, ask the owner to set the camera's own
default on the camera by hand, download, and read the record there. What the model's Help Guide says Save/Load
Settings keeps tells which things to try ([the playbook](REMAPPING_PLAYBOOK.md#16-new-model-first-day), section 16).
With a list that names none, the pull request says what was tried. `kit/tools/check_public.py` stops a pull request
that weakens a camera's list or changes a default's bytes for the maintainer's eye.

{{ schema_fields("camera", "properties/personal_records") }}

Each entry of `zeroed` and of `not_text`:

{{ schema_fields("camera", "properties/personal_records/properties/zeroed/items") }}

Each entry of `defaults`:

{{ schema_fields("camera", "properties/personal_records/properties/defaults/items") }}

## The hand tables file: what the mapping found by hand

`data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json`. A fix to what a record means goes here and nowhere else, never
into the definition by hand (the playbook, Phase 6). `kit/writer/hand_tables.py` refuses a file out of its shape and
`kit/writer/hand_facts.py` applies the tables the plain pass reads; each docstring says how. Schema:
`schemas/hand-tables.schema.json`.

{{ schema_fields("hand-tables") }}

A `RECORD_FIXES` entry:

{{ schema_fields("hand-tables", "$defs/record_fix") }}

A `NEW_RECORDS` or `FILTER_FLAGS` entry:

{{ schema_fields("hand-tables", "$defs/new_record") }}

A `FRAME_PROOFS` entry:

{{ schema_fields("hand-tables", "$defs/frame_proof") }}

A `PICKER_LISTS` entry:

{{ schema_fields("hand-tables", "$defs/picker_list") }}

A `NOT_OFFERED` mark:

{{ schema_fields("hand-tables", "$defs/not_offered") }}

A `KEEPS_APART` entry:

{{ schema_fields("hand-tables", "$defs/keeps_apart") }}

A `LIMIT_PAIRS` entry:

{{ schema_fields("hand-tables", "$defs/limit_pair") }}

A `FRAME_TRAVEL` entry, and each of its `limits`, its `boxes` and its `pictures`:

{{ schema_fields("hand-tables", "$defs/frame_travel") }}

{{ schema_fields("hand-tables", "$defs/frame_limit") }}

{{ schema_fields("hand-tables", "$defs/frame_box") }}

{{ schema_fields("hand-tables", "$defs/frame_picture") }}

## The hand evidence file: how each hand fact was proved

`private/evidence/<model>_fw<fw>.hand.json`, beside the definition's evidence file; `kit/writer/hand_evidence.py`'s
docstring says how each pass reads it. With no evidence in it, as the description below asks of a mapper who proved
none of those entries by hand, it reads:

```json
{"$schema": "../../schemas/hand-evidence.schema.json", "hand_format": 2, "camera": "<model>_fw<fw>", "tables": {}}
```

{{ schema_fields("hand-evidence") }}

What each table's evidence holds (`tables`):

{{ schema_fields("hand-evidence", "properties/tables") }}

A `FRAME_PROOFS` entry's evidence:

{{ schema_fields("hand-evidence", "properties/tables/properties/FRAME_PROOFS/additionalProperties") }}

A look behind a `RECORD_FIXES` entry's `grey_in` or `inactive_if`:

{{ schema_fields("hand-evidence", "properties/tables/properties/RECORD_FIXES/additionalProperties/properties/looks/items") }}

## The menu tree: the camera's menus

`private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json`, from the page scan's page model and the crawls
(`kit/tools/menu_tree.py --help`); `--fold` takes a later crawl's walk into it, row by row, in the camera's order. The
proof viewer's rows come from it, and each setting's place in the definition. Schema: `schemas/menu-tree.schema.json`.

{{ schema_fields("menu-tree") }}

## `data/<model>_fw<fw>/help_<model>_fw<fw>.json`: each setting's help

Its text goes into the definition's `help` and `option_help` (`kit/camkit/help_files.py`). Help never passes from one camera's definition to another's: a new camera's first definition starts with none. Schema:
`schemas/help-file.schema.json`.

{{ schema_fields("help-file") }}

## The reset file: what each reset puts back

`data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json`; `kit/camkit/datafiles.py` (`reset_not_lean`) and
`kit/tools/check_public.py` hold it to the lean shape. Schema: `schemas/settings-reset.schema.json`.

{{ schema_fields("settings-reset") }}

### A setting's readings

{{ schema_fields("settings-reset", "$defs/record") }}

## The accepted file: what the report leaves open

`private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json`, read by `kit/schema_update.py --write`'s gate
(`kit/writer/gate.py`). Settle each question with a proof, or look at it (report.md, the proof viewer) and accept it
here with why. Every entry answers a question the report holds now: one that no longer does is taken out, so it hides
no later question on the same record, and `--write` lists any such entry. Schema: `schemas/accepted.schema.json`.

{{ schema_fields("accepted") }}

### An entry

{{ schema_fields("accepted", "properties/accepted/items") }}

## The coverage ledger: what is settled, and what a proof needs

The ledger says, for every menu row, every value of every setting and every record of the file, what is known
([decision 23](decisions/0023-a-ledger-says-what-is-settled-and-a-proof-is-made-once.md)), so no session does the
same work twice. It is generated each time from the sources that already exist, so it cannot drift:
`kit/camkit/coverage.py` builds it (its docstring lists the sources, the two forms and what counts as settled), and
`kit/tools/coverage.py` prints and writes it (`--print`, `--todo`, `--row`, `--record`, `--proofs`, `--bundles`: its
`--help`).

**The looks file.** Of a row, its mode, what was done and the option, the latest line wins, except one that did not
reach the row, and the records an earlier line saw change stay seen; a line naming no mode stands for every mode.
`kit/tools/coverage.py --record ... --result retract` withdraws one, in the ledger in the mode it names or in every
mode, and a retracted opening makes no row (a crawl's misreading); the first open still withdraws a retracted row's
opening in every mode. A hand tables `UNPROVED` reason on a setting a proof reached makes its other values "no proof possible":
values no menu writes, a fact of the model.

{{ schema_fields("looks") }}

**Two forms.** The public form is never kept in a file: `kit/tools/coverage.py --print` prints it, built from the
public sources and the seen file, the same in any clone ([decision 23](decisions/0023-a-ledger-says-what-is-settled-and-a-proof-is-made-once.md)).
`--write` writes the seen file and, beside the looks file, the private form: the full build, each status with its
citations. `--check` exits 1 unless the public form and the seen file are lean and, where your looks file is, the
seen file is what `--write` writes from it; the kit's tests check every definition's public form in CI.

{{ schema_fields("coverage") }}

The seen file:

{{ schema_fields("coverage-seen") }}

Each of its `facts`:

{{ schema_fields("coverage-seen", "$defs/fact") }}

**The statuses.** An entry takes the first that applies, in this order. A label the menu repeats in a tab holds no
setting of its own and takes the first one's status (`same_label_as`); a row with values still to try carries
`values_left`, how many, and is never settled; the private form also counts `values_inferred`, those the definition's
writer named from another setting's proof, read from the proof's names, where the public form, which has the setting's
mark alone (`proved.shared`), says "proved or named from a shared list" of each value the proof lists
([decision 25](decisions/0025-a-proof-says-when-its-list-was-lent-by-another-setting.md)). `kit/tools/coverage.py
--shared` shows each list's grounds and where its own proof lines do not bear the writer out.

{{ coverage_table("rows") }}

A record's status (the public form merges the last three into `unmapped`, for whether a record varied is the owner's
evidence: `unmapped` says only that the mapping found no menu row that changes the record, so it does not know what the
record holds, and the public files never list or count which unmapped records changed,
[decision 27](decisions/0027-what-unmapped-means-and-what-stays-private.md); a byte field, `<record>@<offset>`, is two
bytes, as the editor reads one):

{{ coverage_table("records") }}

**What a run does with it.** Before it presses on a row, `kit/drive.py`, `kit/crawl_run.py` and `kit/prove_run.py` ask
the ledger and by default only print its answer; only `--skip-settled` makes the crawl and the prover leave a settled
row out, and `kit/drive.py` never does.

**A proof is made once.** A proof is valid when the conditions marked required hold, read from what `proofs.jsonl`
already holds:

{{ coverage_table("validity") }}

"Valid" claims what the proof records and nothing more: not what the option means in another state, nor that no other
record moves where the proof did not look. A second proof of an option with a valid one is a repeat, which
`kit/tools/coverage.py --proofs` counts.
