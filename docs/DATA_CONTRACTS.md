---
render_macros: true
---
# Data files and their schemas

Each data file names its [JSON Schema](https://json-schema.org/) (draft 2020-12) in `schemas/` with a
`$schema` key, so an editor or `check-jsonschema` checks it. The field tables below are read from the schemas
themselves.

## What a mapping delivers

A camera's results are one folder, `data/<model>_fw<fw>/`, the definition `kit/schema_update.py --write` writes
from it and the proofs, `editor/definitions/<model>_fw<fw>.json`
([decision 19](decisions/0019-definitions-are-files-one-per-model-and-firmware.md)), and the model's page,
`docs/models/<model>_fw<fw>.md`, whose entry in `mkdocs.yml`'s nav `kit/tools/build_docs.py` writes. The a1 II's folder, `data/ILCE-1M2_fw4.00/`,
is the pattern for each file. With the definition come its record names for Kaitai's tools,
`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy` ([the file format](formats/index.md)), which
`kit/tools/build_docs.py --no-viewer` writes from it (the pre-commit hook runs it at each commit); CI's
`build_docs.py --check` fails a pull request without it. The definition and `data/` hold only what is the same for any
owner: how each thing was proved, the menu tree, the accepted rulings and the record shapes stay in private files
beside your runs, never in the submission ([below](#the-mappings-evidence)).

The definition's sample, `editor/definitions/<model>_fw<fw>.DAT`, is the one settings file published: a download the
camera wrote right after Initialize, never the owner's own file, with its personal text, and the records its camera
file lists as holding an owner's own data ([`personal_records`](#records-that-hold-an-owners-own-data-personal_records)),
zeroed by `kit/tools/make_sample.py`. Initialize leaves some records as they were. Of those, only the Picture Profile
parameters are checked so far (the reset file lists what Initialize puts back for the settings tested): the sample
takes their values after each offered profile's own Reset in Stills and in Movie (`kit/provers/pp_reset_run.py`, the
playbook's Phase 2), with `make_sample.py --take "Picture Profile PP" --from` the two runs' results, each checked
against its own downloads. When no reset download holds any of the family's records unlike its run's start file,
make_sample stops; --allow-unchanged takes the records then, the run's control being what shows a Reset writes them
(one parameter of one profile). That is the limit of the evidence: the control shows it for one parameter of one
profile; for the rest the evidence is the camera's own completion notice. A profile the body keeps records for but no
menu offers (the ILCE-1M2's PP7-PP9) cannot be reset by a menu and keeps what the base file held, which is said
plainly.

| File | How it is made | Needed |
|---|---|---|
| `camera_<model>_fw<fw>.json`: the camera's own facts (the file's container block, tabs, memories, link-critical and volatile records, the records that hold an owner's own data, the camera's wording) | By hand, from what the mapping found; the container block from `kit/tools/identify.py`'s draft when no known block reads the camera's files | Yes: a definition's `camera` section is copied from it, and the kit reads the camera's files through its block |
| `help_guide_menu_<model>_fw<fw>.jsonl`: the Help Guide's menu list | By hand, from Sony's published Help Guide: one line per item with its tab, group, name and modes, and no other text of Sony's (decision 13) | Optional: `kit/schema_update.py` and the safety review (`python -m camkit.safety`) read it when it is there |
| `help_<model>_fw<fw>.json`: each setting's help in the project's own words | By hand, in your own words, never Sony's (decision 13): what each setting a person meets in the menus does, in a sentence or two; records shown in Expert mode only get none | Optional |
| `hand_tables_<model>_fw<fw>.json`: what the mapping found by hand (records whose name or note the camera proved wrong, records found by hand, value names no proof gives, the values the menus never offer, the copies, why a record cannot be proved) | By hand, as the mapping finds each fact (the playbook, Phase 6), never by a kit step; how each was proved goes into your private hand evidence ([below](#the-hand-evidence-file-how-each-hand-fact-was-proved)) | Optional: `kit/schema_update.py` applies it to the camera's definition, every table in the a1 II's own pass and [the tables the plain pass reads](#the-hand-tables-file-what-the-mapping-found-by-hand) in any other camera's; the plain pass refuses a file that fills a table it does not read |
| `settings_reset_<model>_fw<fw>.json`: which settings Camera Settings Reset and Initialize put back | By hand, from the downloads before and after each reset, run by the owner (the playbook, Phase 5), and only where the owner allows a reset: you write it lean and edit it there, and it is the one file the kit reads ([below](#the-reset-file-what-each-reset-puts-back)) | Optional: the model page's appendix shows it when it is there |

Three files the kit needs stay with whoever maps the camera, in `private/evidence/<model>_fw<fw>/`: the menu tree,
`menu_tree_<model>_fw<fw>.json` ([below](#the-menu-tree-the-cameras-menus)), the accepted rulings,
`accepted_<model>_fw<fw>.json` ([below](#the-accepted-file-what-the-report-leaves-open)), and the record shapes,
`record_shapes_<model>_fw<fw>.json`, the value shapes of the records no setting covers, which the proof viewer shows on
your computer. What the walk found greyed or unread, a ruling on one report and a shape the
owner's files held would differ between owners, so none goes into `data/`; `kit/tools/check_public.py` refuses each
there. A clone brought up to date in the middle of a mapping can still have them in `data/<model>_fw<fw>/`:
`kit/tools/move_evidence.py` (the camera the kit works on, or `--camera <model>_fw<fw>`) moves them into
`private/evidence/<model>_fw<fw>/` once, one line per file, and stops, moving nothing, on a file that is not readable
JSON or one in both places that differs. Nothing else moves them: the kit's commands that read or write them
(`kit/pass2_report.py`, `kit/schema_update.py --write`, `kit/tools/menu_tree.py`, `kit/tools/set_twins.py` and
`kit/provers/mymenu_run.py`) stop while one is still in `data/` only, naming that command, and the readers that only
show take it as absent; the other provers do not read these files and go on. The same command makes a reset file in
the older whole shape lean, keeping the whole once in `private/evidence/<model>_fw<fw>/`.

Pass 1's map, `runs/<model>_fw<fw>/kit2_pass1/map_all.json`, which the provers, `kit/schema_update.py` and the proof
viewer read, stays with the runs and is generated too: `kit/pass1_map.py <crawl> [<crawl> ...]` writes it from the
crawls (`--dry-run` first; one that differs is replaced only with `--replace`).

The pre-commit hooks and CI (`.github/workflows/kit-ci.yml`) check every definition and every data folder's camera,
help, reset and hand tables files against their JSON Schemas (`.venv/bin/pre-commit run --all-files`); the Help Guide's menu list
has none yet. The kit's tests check the menu tree, the accepted file and the hand evidence file against theirs where
they are present.

## `editor/definitions/<model>_fw<fw>.json`: what every record means

The editor's contract, one per model and firmware: written by `kit/schema_update.py --write` (or
`kit/tools/build_docs.py --write-schema`, which runs it) for the camera the kit works on, on the machine that holds
its runs; `kit/tools/build_docs.py --definitions` brings every definition's parts from `data/` up to date without
runs. The pre-commit hook never writes one. The editor ships the ones in `editor/definitions/` and reads the user's own
too (the editor's guide, "Definitions"). `definition_format` is the file's layout: an editor refuses a newer one than
it reads, and one that reads format 2, the lean definition, refuses format 1, which carried the mapping's evidence,
saying to write it again with `kit/schema_update.py --write`. The editor checks a definition as it loads it, its format first, then the typed reading of its fields and
that it holds one layout of its own model; the full JSON Schema check is the hooks' and CI's (above). New fields may
be added elsewhere: the editor ignores fields it does not know, except in the camera section's `file`, where a kind it
does not know refuses the definition (decision 20). Schema: `schemas/definition.schema.json`.

{{ schema_fields("definition") }}

### A setting

{{ schema_fields("definition", "$defs/setting") }}

### The mapping's evidence

A definition says what the camera is, never how, when, in which run or from which state each thing was proved
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): two owners with different
settings who map the same model and firmware completely get the same definition. `kit/schema_update.py --write`
(`write()` in `kit/camkit/definitions.py`) writes the public file lean and what it left out into
`private/evidence/<model>_fw<fw>.json`, in the private overlay, git-ignored and never submitted
([decision 18](decisions/0018-one-public-codebase-with-a-private-overlay.md)). The evidence file holds, by setting
key: how the meaning was first found (`source`), what proves the note (`note_evidence`, the owner's word among it),
the registration that showed a memory copying the setting (`in_sets_proved`), the refusals the proof runs met
(`menu_blocked`), the whole proof (`proved`: its run, day and menu rows, each value name's source, a sample's count and
whether it began where the list stood), the dates of `unproved_reason` and `unproved_sets`, and what shows each
`not_offered` mark; and a layout's `note_evidence`. The public `proved` keeps only the values a proof checked
(`values`) or, for a scale proved by samples, whether they lie on one line (`sampled.linear`).

A camera's hand tables (`data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json`, [below](#the-hand-tables-file-what-the-mapping-found-by-hand)) are public in the same way: they hold names, value
tables and facts about the camera (what a record holds, its copies and families, the values its menus never offer and
why, the reasons a setting cannot be proved). How each hand fact was proved (a hand proof's values, run, day and menu
row, a sample's count, the owner's allowance, what shows a not-offered mark, a reason's date) is in
`private/evidence/<model>_fw<fw>.hand.json` ([below](#the-hand-evidence-file-how-each-hand-fact-was-proved)), which
the writer reads when it is there. Without it `--from-data` and the checks work
on the public tables, and `kit/schema_update.py --write` refuses to write the definition of any camera whose tables
hold entries the evidence completes (a `FRAME_PROOFS` hand proof, an `UNPROVED` reason's day, what shows a
`NOT_OFFERED` mark), which would lose them. A note's evidence is stored as its suffix, `"<field>+"`. The two passes
read the file differently ([below](#the-hand-evidence-file-how-each-hand-fact-was-proved)): the ILCE-1M2's own pass
puts it back into its tables (`kit/writer/hand_evidence.py`), where it only adds (a table key or index it names that
the table lacks is refused, and so is any public value it would replace, a string, a list, a number, a bool, unless it
holds the same; it adds a field an entry lacks and fills one that is empty, `null`; a note's suffix is read after the
public note); the plain pass, every other camera's, never puts it into the tables. A file of format 1,
which kept the whole note, is refused, naming `kit/writer/hand_evidence.py --convert`, which converts it once.

When the kit reads a definition with its evidence (`merge()` in `kit/camkit/definitions.py`), each piece of evidence
goes back only onto the public field it belongs to: a whole proof only where the public `proved` is its lean form, a
date only where the public `unproved_reason` or `unproved_sets` is there, a not-offered mark's evidence only on the mark
of its value, a layout's `note_evidence` only on the layout of its signature. What no longer fits (a contributor
changed or took out the public field, or the setting is gone) is warned about once, naming the setting's key and the
field, left out of the definition the kit reads, and kept in the evidence file's `"stale"` section; it is never
published. After a write `kit/schema_update.py --write` says in one line when that section is there, and
`kit/schema_update.py --drop-stale` lists it, by setting key and field, and `--drop-stale --write` removes it. Evidence
is compared by its lean form on both sides (the public proof's and the evidence's), so a later change to what the lean
form keeps does not set a proof aside. A newer piece set aside for a field that holds an older one there is kept beside
it under `"<field>#2"` (then `#3`, ...), never over it. A write stops before writing anything when evidence went stale
in that run's reading (a proof's, the newer piece of one held aside already among them, or more than five settings' or
layouts': a key renamed, or a merge that changed public proofs); `--accept-stale` writes it all the same, kept in the
section. A write leaves a marker beside the evidence file while it writes (`<evidence file>.writing`, holding the
sha256 of the definition it is about to write) and removes it once the definition is in place, so a marker left means
the last write was cut short between the two files: every write stops on it, and
`kit/schema_update.py --finish-write` writes the definition that write was writing (the evidence file's proofs' lean
forms put into it, nothing else), only when its sha256 is the marker's, and removes the marker; with no marker there
is nothing to finish. Which file is newer says nothing: a pull, a restored `private/` or a hand edit changes that. `write()` writes the evidence file before the public file, so a write that fails half way never
loses evidence, and refuses (nothing written) a definition read without its evidence, whole or in part: a lean proof
(also once a pass has put its names' sources on it, which says nothing of the run, day and rows the file keeps),
an `unproved_reason` or `unproved_sets` without its date, or a not-offered mark without its evidence, where the
evidence file holds them, but a day or a mark's evidence the writer says it took out on purpose (the plain pass, when
the hand evidence no longer gives it: [the hand tables file](#the-hand-tables-file-what-the-mapping-found-by-hand)).
The fields that are evidence whole (`source`, `note_evidence`, `in_sets_proved`,
`menu_blocked`) have no public part to check against, so only a definition with none of the evidence at all is refused
for them. A relative `CAMSET_EVIDENCE_DIR` is taken from the repository's root.

Beside it, `private/evidence/<model>_fw<fw>/` holds the camera's data files that are private (`kit/camkit/datafiles.py`):
the menu tree, the accepted rulings and the record shapes, each whole. A reset file the older kit kept in two halves
may have left its whole copy there too: `kit/tools/move_evidence.py` keeps it as an archive, which the kit never reads;
the public reset file is the only one it goes by.

The kit's passes, provers and tools and the proof viewer read the two put back together (`definitions.load()`), so
they work as on the whole file; with no evidence file (a fresh clone, CI) they read the lean file alone. The editor,
the docs site and the generated files read the public file only. `kit/tools/check_public.py` refuses a commit whose
definition carries any of the evidence, a run's name or a date.

### Where a setting sits on the camera (`row`, `row_at`, `under_option`, `row_tab`, `row_group`, `row_mode`)

`order` sorts a setting by the top row of its group its proof went through; one that went through none of them sorts
after those rows (the ILCE-1M2's hold numbers from 2000 to 9600 there), and a record the generic writer adds takes
the number after the definition's highest. The place says more, and the editor lays a tab out as the camera does from
it alone ("As on the camera"; "Flat list" sorts by `order`): `kit/schema_update.py` (its data-only part, so
`--from-data` writes it) hangs each setting on the row of the camera's menu tree (the mapper's own, in
`private/evidence/<model>_fw<fw>/`; without it, or without the evidence, the places stay as written) that its proof paths (`proved.menu`, in the evidence) lead to, with `kit/camkit/placement.py`, the placement the proof viewer hangs
its records with. A path steps into a row's submenu with ` > ` and names an option of the row with ` / `; a trailing
`[...]` is the proof's context. When every path to the row names one more label past it, and that label is an option
of the row's own setting (the setting named as the row), the setting is that option's sub-choice: `under_option`
(Drive Mode's continuous shooting speed, under its option Continuous Shooting).

A path that names an option of a row and then steps below it (` > `) is on the page that option opens: "Picture
Profile > PP2 > Black Gamma > Level" is the option PP2 of Picture Profile, then the page's Black Gamma > Level. The
option is one the row's own setting labels (else the menu tree lists for the row), named exactly. `row` is then the
row's labels, the option, and the page's rows down to the setting's (`["Picture Profile", "PP2", "Black Gamma",
"Level"]`); `row_at` is the row's numbers, the option's index, then each page row's place among its siblings, so one
key orders every option's pages; `under_option` is the option, so a setting whose `row` continues past its
`under_option` is on a page under that option. The option's index is the setting's column in its family (its group's
place among the family's groups: PP2 is 1) for a family's setting, else the option's place among the row's own
setting's labels. The page is the setting's own group, kept: `row_group` is absent (a profile's parameters stay in
"Picture Profile PP2", not Color/Tone), and `row_tab` is as for any row. Every option's page has the same rows: the
one the tree holds under a child named as the option (the walk opened PP1's) gives its rows to the pages it never
opened, and where the tree holds none, the paths' steps make that one page, in the order the definition lists the
settings. A family's setting no path places takes the place of its record's copy in another column (same area and
id), under the option its own group names, when the row offers that option; a column whose option the row never
offers stays unplaced (PP7-PP9, which no menu of the a1 II offers). A setting
the tree's own rows already place past the row (a child row named as an option with rows of its own: Recognition
Target > Animal) keeps that place.

The row may be in any group of the setting's tab. A screen the definition keeps as a group of its own sits on the row
that opens it: Recall Custom hold 1's settings on Reg. Custom Shoot Set (in Shooting Mode), Fn Menu's on Fn Menu
Settings (in Operation Customize). `row_group` then names the camera group whose page holds the row, by the
definition's name for it; it is absent when that is the setting's own `group`. The setting keeps its `group`, which
the flat list, Compare, the exports and the docs go on using; laid out as on the camera, the editor shows it in
`row_group`, so a definition group all of whose settings sit on another group's rows is not in that layout's groups
column, and every jump to a setting, every count by group and every order across a tab follow the layout in use.

Where the setting's tab has no row its paths lead to, in any menu, a row in another tab of the same tree places it:
the Stills menu's tabs in their order, then each mode's, by a path that leads to the row from one of that tab's top
rows (never by a label met anywhere in the tab), with the modes' rule for context as above. `row_tab` then names that
tab, and `row_group` the group there; `row_tab` is absent when the row is in the setting's own `tab`. The Custom Key
cells the definition keeps in Shooting sit on Setup's Custom Key/Dial Set., Movie's Exposure Ctrl Type, kept in
Exposure/Color, on the Movie menu's Shooting tab. Laid out as on the camera, the editor shows such a setting in
`row_tab`, in `row_group` (the tab's groups and counts follow, and every jump goes there); the flat list keeps `tab`.

The tree's `tabs` are the Stills menu; its `modes` hold the other shooting modes' menus (Movie, S&Q), each written by
`kit/tools/menu_tree.py --mode`. A setting the Stills menu has no row for hangs on a mode's row when a path's context
names the mode (`[Movie mode]`, `[movie]`), or, by a path with no context at all, when only that mode's menu has the
row; `row_mode` names the mode. A tab's top rows are numbered as one list for `row_at`: the Stills menu's in its order,
each mode's own rows slotted in where that mode's menu has them, after the Stills rows of that gap. So one number orders
a tab's groups too: as on the camera the editor lists a tab's groups by the first row each places (a group only the
Movie menu has, TC/UB, between Shutter/Silent and Image Stabilization, where the Movie menu has it), the groups it
places none of after them, in the definition's order. In a group, the rows only a mode's menu has come after the
Stills rows, under "In Movie mode" (the mode's name from the definition), in that mode's order.

Where the tree knows no rows under the row a path reaches (a submenu the walk never opened or could not read, a mode's
row read off its page scan alone), the path's further submenu steps (` > `, up to its first ` / `) are taken as the
rows, in the order the definition lists the settings proved through them; never past a screen the walk read (a list, a
dialog, number fields), whose steps are its options. A crawl that walks those rows later gives them the camera's order.

A setting gets none of the six when no path reaches a row: paths that name none (registered through Camera Set.
Memory, or set by hand), records the SDK names that no menu screen proved, the memory mirrors, and the families'
settings no option's page or indexed path places (which the editor draws as tables). The editor lists those after the
camera's rows, under "More settings in this group".

### The camera's options, nested (`option_tree`)

Some rows are a carousel whose options open a choice of their own on a second axis, in the same record: Focus Area's
Spot opens its sizes, Custom its three slots, Tracking its start areas. `values` lists every stored value flat, with
the flat labels the camera's screen shows ("Spot: M"), and stays what comparisons, exports, searches and the memories
use. `option_tree` lays the same values out as the camera does: the main options in the camera's order, each an
object with its `label` and either one `value` or the `options` of its own axis (`[value, label]` pairs, the label
under the option: "XL" for "Spot: XL"; a choice that would be only a number keeps its whole label, "Custom 1"). Every
value of `values` is in it exactly once, and at least one main option has `options`. An editor shows the main
options and, under the one the stored value belongs to, its choices; a definition without the field shows the flat
list.

`kit/schema_update.py` writes it from the run's pass-2 proofs, never from the labels alone (`kit/camkit/option_tree.py`;
`--option-trees` writes only it and prints the audit, every setting with a tree and every one on a carousel row or with
labels of the shape "Main: Sub" without one, with why). The dialog proofs of a row give its main options in the
camera's order; the axis proofs ("kind": "axis", the main option in "option") give each option's choices, in the order
the camera steps through them, from the one the setting lists first. A setting placed on that row (`row`) gets a tree
when its values are the row's whole choice: each main option holds at least one of its values, each value matches
exactly one option (by the camera's text for it, signs, spaces and the screen readers' slips aside), and one option
holds two or more. A list the camera shows flat stays flat however its labels read: White Balance's four Fluor.
options are four options of its list, Shoot. Timing Display's On: Type1 to Type4 four rows of its list, and a function
picker's names hold colons of their own. A setting that is an option's own choice in a record of its own
(`under_option`) is shown under that option already and gets none. A setting the proofs give no tree because no run
places it on a row the proofs speak for shares the tree of a setting that has one when its `values` are identical to
that setting's, number for number and label for label in the same order, and the two are in the same `tab` and the same
group family (their `group` up to its first ` › `), and every such setting gives the same tree: the same choice kept
in another record no run walked (Registered AF area's areas beside Focus Area memory). Values only alike (fewer of
them, or the same labels numbered otherwise) are another record's choice, which the camera may list flat (Tracking's
start areas), and share nothing. `--from-data` leaves the field as it is.

### What the editor offers outside Expert mode

Outside Expert mode the editor offers a setting's values only where a proof on the camera established them, read from
the setting's `proved` itself; of any other it says that it is not checked on the camera yet and the camera may refuse
a file holding it, and Expert mode's "Offer values…" brings those back. A setting with no `proved` offers every
value, for nothing is known of it. In a proved setting a value is established when:
- its scale was proved by samples on a straight line (`proved.sampled.linear`, the rule in [KIT_PLAN](KIT_PLAN.md),
  "Sampling long number ranges"), which establishes every value of the list, and every number of a range;
- or `proved.values` lists it: the values a proof chose, and those whose name has a source on the camera (two
  readers, one reader, the vision model, derived (a rule over proved values), sampled or a hand table; `ESTABLISHING`
  in `kit/camkit/definitions.py`). A name kept from the old schema (`schema kept`, a spelling of the old crawl mended
  by `LABEL_FIXES` among them) is not one, nor a value a rule or a table written by hand names that no proof chose
  (`counted`: the a1 II's hold Exposure Comp. codes, counted out in quarter stops, until the live table is proved in
  full; and in the plain pass, any camera's but the a1 II's, every value a hand table names that no proof covers and
  no held `not_offered` mark holds, [below](#the-hand-tables-file-what-the-mapping-found-by-hand)). Each name's
  source (`proved.names`) stays in the evidence.

A value the menus never offer (`not_offered`, below) is left out whatever its proof. There is no list of the values
camera files have held: the old schema's (`observed`) came from the camera's downloads, so beside the proofs' values
it held the owner's own settings
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)). `kit/schema_update.py`
takes it out of every setting it writes (`without_observed` in `kit/writer/proofs.py`), and the definition's schema
refuses a setting that carries one. Nor does a definition list which records a proof wrote together (`written_with`):
whatever rule pruned it, such a list would tell how the camera was set when the proofs were made (which of a family's
copies a choice wrote). That evidence stays in pass 2's report for whoever maps the camera; `without_written_with`
takes such a list out on every write, and the schema refuses the field.

Nor does a definition say which of a setting's proved values no option was seen to write: the option a row starts on
changes nothing, so such a mark would point at what the camera held
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)). Such a value is proved as
any value chosen on the camera is, its name's source the one its readers give (`with_names`); no `proved.inferred`
and no source "held" is written (`without_held` takes one out on every write), and the definition's schema refuses
`inferred`. Pass 2's report keeps the labels taken from
"nothing changed" for a person to read (`inferred` in `report.json`, in the camera's runs). A display proof (a list
offering one option, read off the screen) is named by its readers too. `not_offered[].held`, a factory value the menus
cannot choose back, is another thing and stays.

A proof made by a sample that starts from the option the camera held lists none of its values either: such a sample
steps from the held option a fixed way, so its values would tell that option to anyone who knows the camera's list
(decision 16). A table cell's list is numbered
from the option it opens on, the one the camera holds (`kit/table_walk.py`), and a row that chose only some of its
places is such a sample: `kit/pass2_report.py` (`sampled_from_start`) marks its records `sampled_from_start`, and
`kit/schema_update.py` writes the record's proof as a sample, `"sampled": {"linear": null}`, unless another row walked
it whole. Its readings name nothing, and each value is named by the slot its group proved in full ("derived"), so its
`values` are those and an editor offers what that proof established. How many lines chose an option (never a
put-back) and that the sample began where the list stood stay in the evidence; the values stay in the report, in the
camera's runs. A table walked whole credits its start, from the put-back line when nothing
else chose it, as one option among all of them. A prover that plans its own values whatever the camera held lists them.

Nor does a line that only shows what the session's start held credit anything. In a list or side list walked in part
(places left out between the first and the farthest), the line that is its session's first sight of the row or its
last choice (the lines diffed against one start download, in download order) and changes nothing proves no option:
its value is only what the start held, which would stand out among the options chosen. `kit/pass2_report.py`
(`start_lines`) leaves it out of the record's values and of the names' readers, as it leaves out a `"planned": false`
line, and keeps it apart in `report.json` (`start_only`); `kit/schema_update.py` keeps no such value from an older
definition unless a line proves it by a real change (`kept_proof`'s `gone`), and a hold's names do not count it among
the options its proofs chose. A list walked whole (every place chosen, refused ones too) keeps its start, one option
among all of them.

### Values the menus never offer (`not_offered`)

A value a setting lists that the camera's menus never offer is marked in `not_offered`, with why in plain words and the
menu whose list leaves it out (what shows it, the walk and its run, is in the evidence): the definitions of the first kit listed some codes as the union of
several pickers (a dial's functions beside a key's), and a few no list the kit walked ever showed. Which values, and
the words, are the camera's hand table (`NOT_OFFERED` in its [hand tables file](#the-hand-tables-file-what-the-mapping-found-by-hand)); its evidence, in the hand
evidence file (`private/evidence/<model>_fw<fw>.hand.json`, [above](#the-mappings-evidence)), says that each walk it
names went over the whole list; `kit/schema_update.py` (`kit/writer/offered.py`) writes a mark only while
that evidence holds: every row of the report the mark names (its walks of the setting's list, one per state) proves
the record and never wrote the value, or every picker list of one table-walk screen
(`runs/<model>_fw<fw>/kit2_tables/tables.json`) went round to its start (`wrapped`) and none lists the function. A
walk that writes the value later drops its mark on the next run. A value the camera writes itself although the list
cannot choose it back (ISO AUTO Minimum's ISO 64, the factory value, written by Camera Settings Reset and Initialize
and held until the minimum is changed) is `held`, and an editor keeps offering it. An option the camera offers but
refused under another setting is never this: the refusals the proof runs met (`menu_blocked`, each with the camera's
reason up to the blocking setting, `blocked` in `kit/schema_update.py`) depend on the state the camera stood in, so
they stay in the evidence. `--from-data` leaves the field as it is.

### Values offered under one video system (`video_system_values`)

Under PAL the camera's frame-rate lists offer the PAL rates, each stored one code above its NTSC counterpart, and
under NTSC the NTSC ones (the ILCE-1M2's model page, "Frame rates under PAL"), so a setting lists both systems' values
though a file's live settings hold only the system its header says. `video_system_values` (`{"NTSC": [...], "PAL":
[...]}`, both keys always) says which, for the live settings only: a value listed under one system is offered in the
live settings only when the file's header says that system (`camera.file.video_system`), and a value listed under
neither is offered under both; with the header's system unknown an editor offers every value. A memory set keeps the
rates it was registered under (every download the a1 II saved on PAL holds NTSC rates in its memory sets), so the field
says nothing of a memory set's values.

`kit/schema_update.py` (`with_video_systems` in `kit/writer/offered.py`, in any camera's pass) writes it from pass 2's
report: for each record
a row walked under a named video system (a context that says it: "Movie mode, PAL"), every row that proves the record
counts under the system all of its proofs' downloads say in their header, and the context's word must agree (a row
whose downloads say two systems, none, or another than its context is printed and left out). A value the setting lists
that rows of one system proved and rows of the other never did is that system's; one both proved, or neither, is under
neither. A setting gets the field when some value it lists is one system's; where every listed value is one system's,
the other's list is empty (the other system's rates, proved, are not among its values). The rows walked whole under
each system are what make a value absent from one system's list mean the list leaves it out (on the a1 II, pass 3's PAL entries of
2026-11-06 crawled each list afresh under PAL; `NOT_OFFERED`'s evidence, in the hand evidence file, says the same of
the HS 4K and S-I lists). A setting no proof walked under both systems takes its values from the camera's hand table
(`VIDEO_SYSTEM_VALUES` in its hand tables file, both keys; the evidence for each in the hand evidence file) only
where what the camera showed under the other
system speaks for it; a list never seen under the other system keeps its values under neither, however the one-code
rule reads them. Where the proofs speak, they stand. On the a1 II the proofs give it to Rec Frame Rate for each movie
File Format with a choice under both systems, S&Q's Rec Frame Rate and Frame Rate, Time-lapse's Rec Frame Rate and the
active format's Rec Frame Rate (its listed rates all NTSC's), and the hand table to XAVC HS 8K's Rec Frame Rate (under
PAL its one rate is none of those listed) and USB Streaming's Output Res/Frame Rate. 24p is NTSC's wherever a list was
walked under PAL, and S&Q's 2fps and 1fps are under neither.

Every write then checks the field against the camera's own downloads (`check_video_systems`): a value listed as one
system's only must not be held in the live settings of any download whose header says the other system, for the camera
wrote that file and an editor would flag it (the memory sets are not checked: they keep their registration's rates). The check reads up to 200 downloads of each system the download log lists,
spread over each system's own; a contradiction stops the write with exit 1, naming the setting and the file, never a
value, and a download that cannot be read is skipped and counted. `--from-data` leaves the field as it is.

### A value kept in more than one record (`copies`, `copy_of`, `copy_for`, `camera.live_mode`)

The camera keeps some values in a live record and per-mode copies beside it: each Picture Profile parameter in use
with its Stills and its Movie copy (a Stills edit writes the one in use and the Stills copy, a Movie edit the one in use
and the Movie copy, and either the other mode's copy too where the family's Different Set for Still/Mv box shares it),
the profile in use with its two copies, and the other settings Different Set for Still/Mv keeps
per mode (White Balance's fine-tune, A-B and G-M of each preset Movie mode offers, and its colour temperature among
them). `copies` on the live setting lists its copies' keys and `copy_of` on each copy names the live setting;
`copy_for` on a copy lists the shooting modes whose value it is, named as `camera.memory_sets.modes` names them (the
Stills copy "Stills"; the Movie copy "Movie", "S&Q" and "Time-lapse", which use the Movie set); and `camera.live_mode`
names the live record that says the mode a file was saved in, with the mode each of its values means (a memory set's
mode is the one `camera.memory_sets.modes` lists it under). In every section of a file the camera wrote, the setting
equals the copy for that section's mode: switching to Movie loads the Movie copies into the record in use, a Movie or
S&Q choice writes the record in use and the Movie copy, and a Stills choice it and the Stills copy (each the other
mode's copy too where the box shares them).

What follows an edit is the copies rule: an editor writes every copy that held the setting's old value with the new
one when the setting is edited; changing a copy that was in step with its setting in the file as opened changes the
setting and every copy in step with it, and changing one that was not in step changes that copy alone. Whether a
family's Stills and Movie values are shared or kept apart is the camera's own setting, Different Set for Still/Mv,
one box per family: with a box unticked a change in one mode moves both copies, with it ticked only that mode's. The
kit has not proved those boxes yet (the row opens on an information notice the walker stopped at, and no setting of
the definition holds them), so the copies rule, right in both states but for moving an equal copy when the box is
ticked, is what an editor follows; once the boxes are proved the definition will name each family's box. `copy_for`
and `camera.live_mode` are for checking a file, not for deciding what follows: where a section's mode is known and the
family's copies carry `copy_for`, a section in which the setting does not equal the copy for its mode is a counted
issue in the save and write windows, an edit or a Revert that would make it so is refused outside Expert mode, and
outside Expert mode a copy in step is reverted with its setting, never alone. Where the mode is not known (no
`camera.live_mode`, a value it does not name, copies without `copy_for`), the weaker check stands: a file where the
setting equals none of its copies is flagged (the editor's guide). A Main page's tile for such a setting reads the
copy of the page's own mode: the Stills page the Stills copy, the Movie and S&Q pages the Movie copy, for the record in
use holds the values of the mode the file was saved in (`main_tiles` in
`data/<model>_fw<fw>/camera_<model>_fw<fw>.json`).

The families and their modes are the camera's hand table (`COPIES` and `COPY_MODES` in its hand tables file), and
the rules were checked on the camera's own downloads before any was written (the download log,
`runs/<model>_fw<fw>/downloads.jsonl`, and the pass-2 run's downloads, NTSC and PAL). Exposure Comp.'s three records
are a family whose copies' modes are not known yet (`COPY_MODES_UNKNOWN`): its copies carry no `copy_for`, the write
checks the weaker rule (the setting equals one of its copies) in every section, and until the copies' modes are known
they are proved with their setting (its rows and values). A copy with `copy_for` keeps in its proof's menu rows (`proved.menu`, in
the evidence) only rows made in its own modes: `copies` and `copy_of` say they belong together, the same way whatever the proofs wrote, where which records a
proof wrote would say how the family's Different Set for Still/Mv box stood
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)). No copy shares its setting's
name, for an editor shows each copy in a row of its own: "… (stills)" and "… (movie)", or, where the copy's mode is not
known yet, "… (copy 1)" and "… (copy 2)" (a test checks it). `kit/schema_update.py` (`with_copies` in
`kit/writer/copies.py`) reads up to 200 of the downloads the log lists, spread over it, at every write, and checks
every section of each: a download whose live value equals none of its copies', or a section where the setting is not
the copy for that section's mode, stops the write with exit 1, naming the family, the file and the section, nothing
written; a download that cannot be read is skipped and counted, and so is a live section whose mode
`camera.live_mode` does not name (it gets the weaker check only), so a `live_mode` wrong for a camera shows; with no
downloads the definition's fields are left as they are. `copy_for` goes on every copy of every family whose modes the
hand table names, the modes it names for the copy's place (the Stills copy "Stills", the Movie copy "Movie", "S&Q" and "Time-lapse"), and the
write checks them against the camera's downloads as above. Keys and mode names only, never a value.
`--from-data` leaves the setting fields as they are; `camera.live_mode` is the camera file's.

### Why no proof can reach a setting (`unproved_reason`)

A setting no proof can reach says why instead of staying "not proved": its kind and its why in a photographer's words
(each kind is described in the `unproved_reason` row of [the setting's fields](#a-setting) above, from the definition
schema; the words the editor shows for each are in the editor's guide). `kit/schema_update.py` writes one only while the setting has no proof, and takes it
out once a proof reaches it: any camera's from its hand table (`UNPROVED` in its hand tables file, each
reason's date in the hand evidence file), and a memory set's own block of the memories' live copy says the same for
the sets whose live field has one (`unproved_sets`). The ILCE-1M2's table names the camera's
working values, the AF point copies only its own saves write, the HDMI RAW rows that need a recorder, the network
block, the two records every candidate row was tried on and the raw stop values memory sets 4-12 never write, and its
own pass adds by rule PP7-PP9, which its menus do not offer. A value only a reset writes (the Base Look copies) has no
place of its own: its note says so. The editor shows the kind in a few words and the why on hover (the editor's guide).

### The owner's word and a memory's copy (in the evidence)

A proof line made with the owner's word for a row the kit never opens (a volume, a brightness, Camera Set. Memory's
registration) carries it: `"allowance": "the owner allowed <row> remotely, <date>"`, written by `--allow` on
`kit/prove_run.py`, the scale prover and the memory provers, one row named at a time
([decision 2](decisions/0002-nothing-that-makes-sound-light-or-motion-is-changed-remotely.md) and the playbook's rule
1). `kit/pass2_report.py` gives the words to the records the line proved (`allowances` in `report.json`), and
`kit/schema_update.py` adds them once to each such setting's `note_evidence`, in the evidence file; a hand table's proof made that way says so in its own `allowance` (a camera's `FRAME_PROOFS` entries, in the
hand evidence file, `private/evidence/<model>_fw<fw>.hand.json`).

A registration mirror line (`"kind": "registration mirror"`) is a memory slot registered to see its copy take a value:
`kit/provers/memreg_run.py` changes a live setting in its own menu, then registers the slot (`"live"` names the live
record, `"record"` its copy in the set), and `kit/provers/framepos_run.py --zone-grid` registers a frame's place, which
no live record holds (`"record"` alone). Such a line is no row's proof: the report leaves it out of its rows, and the
writer reads the applied lines of the camera's proof runs. Each live setting whose copy took the new value gets
`in_sets_proved` (the run, the day, the memory slot) in the evidence file; the values a registration wrote into a
memory record no live record holds are that record's proved values in the definition, each under its own label (the
Zone's nine places). Neither names a value the camera held
([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).

## `data/<model>_fw<fw>/camera_<model>_fw<fw>.json`: the camera's own facts

Edited here, copied into the definition's `camera` section. Schema: `schemas/camera.schema.json`. The optional
`picture_profile_in_use` names the live records that say which Picture Profile is in use, which only the kit reads:
`kit/tools/upload_check.py` warns of a file that would change a profile in use, and says so when the camera file has
none.

{{ schema_fields("camera") }}

### The container block (`file`)

Where the parts of the camera's settings file sit, and which of the kinds the editor and the kit know apply
([decision 20](decisions/0020-the-editor-holds-no-camera-facts.md)). Offsets are hex strings as the docs write them
(`"0x3c"`), or `"end-N"` counted back from the end of the file; a range runs from its first offset up to, not
including, its second. A kind neither program knows refuses the block by name; a new checksum, framing or encoding is
a change to the programs, never to a block. `kit/tools/identify.py FILE.DAT` says which block reads a file, and for a
file none reads prints a draft to correct by hand: the block is right when the file reads and both checksums hold.

The editor reads a file by trial, once for each distinct block of the definitions it has (definitions of one
container share its block): the magic, then the model and the firmware, which pick the definition (the editor's
guide, "Definitions"), then the file framed with the block, which its trailer checksum must confirm. A file of a model
no definition covers is read with the first block whose magic matches and that frames it. Of a file whose first bytes
no block names, the editor says that no camera definition describes it; one a block names but cannot frame, or whose
trailer checksum fails, it calls damaged, or not saved by a camera.

`firmware` is what a file is matched to a definition by, with the model: only the bytes that are the firmware. A byte
that changes with a setting, such as the video system the camera was set to, goes in `video_system` (optional), never
in the firmware's span: the ILCE-1M2 writes `04 00 00` at 0x36-0x38 on NTSC and `04 00 01` on PAL, so its block reads
the firmware from 0x36-0x37 (`major_minor`, 4.00 for both) and the video system from 0x38 (2026-11-06; until then the
block read three firmware bytes, and a PAL file was firmware 4.01). The editor shows the video system beside the
firmware, notes in Compare when the files open differ in it, and writes a file only to a camera set to the same one
(the editor's guide, "The camera link"); the kit counts one firmware's files under every video system as one camera and
firmware. A block without `video_system` reads, matches and writes as before.
`docs/formats/sony_camset.ksy` describes the ILCE-1M2's container for Kaitai's tools and ImHex, tied to its block by
a test. The record names are generated, one file per definition (`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`),
and it imports the ILCE-1M2's.

{{ schema_fields("camera", "$defs/file_block") }}

The kinds the programs know are named in three of those fields.

A checksum (`header_checksum`, `trailer_checksum`):

{{ schema_fields("camera", "$defs/checksum") }}

The firmware (`firmware`):

{{ schema_fields("camera", "$defs/file_block/properties/firmware") }}

The records' framing (`records`):

{{ schema_fields("camera", "$defs/file_block/properties/records") }}

### Records that hold an owner's own data (`personal_records`)

The sample is the one settings file published, so `kit/tools/make_sample.py` zeroes in it every record whose value
reads as text (four printable characters or more: an owner's name, a copyright, a network or device name) and the
records the camera file lists here. The list holds every record that changes when the owner's own things change, text
or not: the text check catches some of them and misses others (a name packed against other bytes). They are each
body's own record ids, never another body's: on the ILCE-1M2, Preset Focus/Zoom's registered lens list (each slot's
lens name, serial number and the lens data registered with it; [its page](models/ILCE-1M2_fw4.00.md), "Lens list") is
zeroed, and the file-name prefix an owner chooses (three letters, often initials) is set back to the camera's default,
DSC. A record is named as the record keys write it and `kit/tools/upload_check.py --diff` prints it after `global:`,
`"0x167c"`, the one form the list takes, and both tools name records so. A record id holds in whichever section it is
in; the editor does not read the key.

Before it writes anything, `make_sample.py` refuses a camera file without `personal_records` (saying what to add and
how to find it), a list not shaped as the schema below says, a record listed twice (in one group or two), a record no
section of the file holds (a typo, or a decimal number written after `0x`) and a default of another length than its
record. `kit/tools/check_public.py` checks every published sample by its camera file's list (the tree's, or a pull
request's last commit's) in the same way, and names what it finds by the record and what the list says it holds, or a
text by its length, never by its value, and refuses a sample of another model or firmware than its definition's. A
pull request that weakens a camera's list is refused for the maintainer's eye, and its description says why: a record
taken out or newly kept from the text check, a default's bytes changed, a record moved to or newly set to a default,
or a new camera file for a model already mapped (another firmware) that lists less than that model's, each compared at
the range's own base and where its first commit started.

To find a body's: download; ask the owner to change one such thing on the camera, by their own hand (register a lens
to a preset slot they do not use: it needs a held custom key or the lens's ring, and overwrites the slot; set the
file-name prefix); download again and compare the two (`kit/tools/upload_check.py --diff REF TAG` lists the records
that differ). Every record that changed goes in: under `zeroed` when any value of it is the owner's, under `defaults`
with the camera's own default bytes when it has one. The bytes the diff prints are the owner's (a lens's name, its
serial number): copy them nowhere, not into notes, the camera file or a message; only the records' ids go into the
list. A default's bytes go into the published sample, so they are read from the file the camera wrote right after
Initialize, the one `make_sample.py` is given (the sample's own source), never from the owner's working file, where
the record holds the owner's own value:
`.venv/bin/python -c "import sys; sys.path.insert(0, 'kit'); from camkit import camset; print(camset.read('SRC.DAT').get(0, 0x0b5b).raw.hex())"`
prints them, with that file in place of `SRC.DAT` and the record's id in place of `0x0b5b` (on Windows
`.venv\Scripts\python`). If Initialize left the owner's value in that record, ask the owner to set the camera's own
default on the camera by hand, download, and read the record there. A pull request that changes a default's bytes,
moves a record from `zeroed` to `defaults` or sets a record to a new default is stopped for the maintainer's eye. What the model's Help Guide says Save/Load Settings keeps tells which things to try
([the playbook](REMAPPING_PLAYBOOK.md#16-new-model-first-day), section 16). `not_text` lists records of numbers the
text check would misread (a run of numbers between NUL bytes can look like four letters), and `keep_text` the camera's
own words a record may keep. A list that names no record to zero or set back is allowed only for a body on which
those things were tried and changed no other record; both tools say so in a note when they meet one, and the pull
request says what was tried.

{{ schema_fields("camera", "properties/personal_records") }}

Each entry of `zeroed` and of `not_text`:

{{ schema_fields("camera", "properties/personal_records/properties/zeroed/items") }}

Each entry of `defaults`:

{{ schema_fields("camera", "properties/personal_records/properties/defaults/items") }}

## The hand tables file: what the mapping found by hand

`data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json` holds what a camera's mapping found by hand and the rules the
writer applies to its definition, table by table: the records whose name or note the camera proved wrong
(`RECORD_FIXES`), the records the menus never write, found by hand (`NEW_RECORDS`, `NEW_LIKE`, and `FRAME_PROOFS` with
each one's note and value names), value names no proof can give (`CAROUSEL`, `VALUE_FIXES`, `KEEP_LABELS` and the
others), the values the menus never offer (`NOT_OFFERED`), the copies the camera keeps (`COPIES`), why a record cannot
be proved (`UNPROVED`), and the label fixes and proof-row rules. It is public and the same for any owner of that model
and firmware, and written and edited by hand: no kit step writes it, and the writer checks what it can against the
camera's own files at every write (a not-offered mark against the walks, the copies and the video systems against the
downloads). A fix to what a record means goes here and nowhere else, never into the definition by hand (the playbook,
Phase 6). Schema: `schemas/hand-tables.schema.json`, which the hooks and CI check; every table is optional, and an
entry holds no field of a proof's evidence.

How, when, in which run and from which state each hand fact was proved (a hand proof's values, run, day and menu row,
a sample's count, the owner's word, what shows a not-offered mark, the day a reason was settled) is the mapper's, in
`private/evidence/<model>_fw<fw>.hand.json` ([below](#the-hand-evidence-file-how-each-hand-fact-was-proved)), which `kit/writer/hand_tables.py` puts
back into the tables as it reads them, by table name, key and index; `kit/tools/check_public.py` refuses a hand tables
file that names a run or a day, as it does any file of a camera's data folder. The reader gives each table the shape
the writer reads (a list of keys as a set; `[key, value, label]` rows by key and value; a reason's `[kind, null, why]`
as one tuple), and refuses a file for another camera, a table it does not know, a key or a row given twice (JSON would
keep the last one without a word), a table out of its shape and a `NEW_RECORDS` `$ref` to anything but what the next
sentence says; the rest of an entry's shape is the schema's, which the hooks and CI check. The patterns a hand tables file holds (`CONTEXT_WORDS`' patterns and their words, `NOT_OFFERED`'s walks, `ORIENTED`) are Python's regular expressions that the writer runs: the reader refuses one that does not compile, and the maintainer reviews them in a pull request as code. `MY_MENU_EMPTY`'s line takes the camera file's empty code in place of `{code}`, put in as text, and the reader refuses any other brace in it. A `NEW_RECORDS` entry
`{"$ref": "#/FILTER_FLAGS/<key>"}` is `FILTER_FLAGS`' entry of the same key: one entry in both tables, so its evidence
is put on it once. A sentence several notes share (the frame positions, a Custom box's place) is said again in each,
and a test keeps the copies alike.

A camera without the file has every table empty. `kit/schema_update.py` applies the tables to the definition of the
camera it writes: the ILCE-1M2 firmware 4.00's own pass reads every table (its file is the pattern; the `FRAME_PROOFS`
entries of its Base Look copies, 0x0f9b and 0x0fbb, list no values, and that pass names them by the list of the look
in use, 0x0cbe, as it writes), and the plain pass, every other camera's, reads these (`kit/writer/hand_facts.py`):

- `RECORD_FIXES`: a setting's name, note, tab, group, range or unit, put on it at every write (one the definition
  does not hold yet is said, and waits);
- `NEW_RECORDS`, with the `FILTER_FLAGS` entries it takes in: a record the menus never write, added when the
  definition lacks it, laid out like the record `like` names and from the run's newest download (one whose `like` the
  definition lacks yet, or that the download does not hold, is said and left out), its name, values and note kept
  current;
- `NEW_LIKE` and `NEW_WHOLE_LABELS`: a record a proof found, laid out like its sibling from the run's start download
  (the newest `*_before.DAT` of the run the downloads manifest lists) once every row of the report is read, so the
  rows' order changes nothing, named by the table, its values by the proofs' labels after their colon (the whole label
  for a record `NEW_WHOLE_LABELS` lists), a gap at the start value filled from the sibling; a run whose definition
  lacks the sibling names the record by its menu row, said, and a later run lays it out (one neither of the run's
  downloads holds is said and left out); a record laid out like another `NEW_LIKE` record comes after it, whatever the
  file's order, and a cycle of them is refused;
- `FRAME_PROOFS`: what a record holds and its values' names, and its hand proof where the hand evidence gives one,
  which then names its run, day and menu row there (either pass stops on one that does not);
- `CAROUSEL`, `VALUE_FIXES`, `PP7_VALUES` and `KEEP_LABELS`: value names no proof gives; a `KEEP_LABELS` record keeps
  the names the definition holds (a hand table's where the camera read otherwise) and names a value it does not name
  yet by the camera's label, a conflict the report notes on it is an open question for the gate, and
  `kit/pass2_report.py` leaves a value carried over in it to that rule;
- `NOT_OFFERED`, `VIDEO_SYSTEM_VALUES`, `COPIES`, `COPY_MODES` and `COPY_MODES_UNKNOWN`: each checked against the walks
  and the camera's downloads at every write, as the sections above say;
- `UNPROVED`: why no proof reaches a setting, and `unproved_sets` on a memory set's block where the camera file names
  the memories' live copy;
- `CONTEXT_WORDS`: proof contexts in other words.

In the plain pass a value a hand table names (`VALUE_FIXES`, `CAROUSEL`, `PP7_VALUES`, `KEEP_LABELS`, the `values` of
`FRAME_PROOFS` and `NEW_RECORDS`) is named, not proved: its name counts as checked on the camera (source `hand table`,
which an editor offers outside Expert mode) only where a proof covers it, the report's or a hand proof with its
evidence, or a `NOT_OFFERED` mark says the camera holds it (`held`); any other is `counted`, offered in Expert mode
only. A record `NEW_LIKE` lays out takes that from its sibling: a value its own proofs do not cover, filled from the
sibling's labels, is `derived` only where the sibling's value is established (in the sibling's public proof), and
`counted` otherwise, so a counted value never becomes checked through the fill. A list a table gives whole (the
`values` of `FRAME_PROOFS` and `NEW_RECORDS`) is written with the record's own `VALUE_FIXES` names and `PP7_VALUES`, so
the tables say one thing on every run. The ILCE-1M2's own pass keeps its meaning, every name its tables give a hand
table's, until the two passes become one. An entry that cannot take effect (a setting the definition lacks, a value no
setting lists, a `CONTEXT_WORDS` pattern that matches no row) is said as the pass goes, "not applied", and the
definition is written all the same. What the tables or the hand evidence no longer give leaves the definition, each
said: a record `NEW_RECORDS` added that the table no longer holds and no row of the report names (a row that finds it
not one to one, or reads it out, keeps it), a hand proof the hand evidence no longer gives (the definition's evidence
marks a hand proof `by_hand`; the copies of a family whose modes are not known yet lose the one they took from their
live setting with it), and a reason's day or a mark's evidence the hand evidence no longer gives (the write is told it
was taken out on purpose, `check_write`'s `taken_out`, and is not refused as one that read the evidence away). A
second run on the same tables, runs and evidence changes nothing and says so. The ILCE-1M2's pass is unchanged there
too, but for a reason's day: it writes a reason whose day the hand evidence does not give without one, and takes an
earlier day out, said, as the plain pass does.

`ZONE` is a prover's, read by `kit/provers/framepos_run.py --zone-grid` for the camera the kit works on. The others
(`NEW_CHECK_NAMES`, `LATE_COPY`, `EV_DOWN_FROM_20`, `HOLD_TABLES`, `HOLD_BRACKET_COPIES`, `ISO_TABLE`, `LABEL_FIXES`,
`GROUP_NAMES`, `MY_MENU_ROW`, `MY_MENU_EMPTY`, `SHOOT_MODE_RECORDS` and `ORIENTED`) only the ILCE-1M2's own pass reads
so far, each tied to that pass's code (its checklist records, its Recall Custom holds, its My Menu, the first kit's
spellings), and no pass reads `FRAME_STEPS`. The plain pass stops, before anything is read or written, on a file that
fills one of them, or that holds an entry no table it reads would use (a `FILTER_FLAGS` entry no `NEW_RECORDS` `$ref`
takes in, `NEW_WHOLE_LABELS` for no `NEW_LIKE` record, `COPY_MODES` without `COPIES`, a `COPY_MODES_UNKNOWN` family
`COPIES` lacks, a `NEW_RECORDS` key that is no whole record, a `NEW_LIKE` key that is no whole live record), naming
each and saying which tables it reads: no table is filled in and believed to take effect. The rows below say which
tables those are. A camera whose tables are all empty gets the plain pass as it was before it read any.

{{ schema_fields("hand-tables") }}

A `RECORD_FIXES` entry:

{{ schema_fields("hand-tables", "$defs/record_fix") }}

A `NEW_RECORDS` or `FILTER_FLAGS` entry:

{{ schema_fields("hand-tables", "$defs/new_record") }}

A `FRAME_PROOFS` entry:

{{ schema_fields("hand-tables", "$defs/frame_proof") }}

A `NOT_OFFERED` mark:

{{ schema_fields("hand-tables", "$defs/not_offered") }}

## The hand evidence file: how each hand fact was proved

`private/evidence/<model>_fw<fw>.hand.json` is the mapper's own, beside the definition's evidence file, never
committed or sent ([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): for each
hand fact whose proof is evidence, by table name, then by the entry's key (by its place from 0 in `NOT_OFFERED`,
checked by `"$key"`, the mark's setting, and by `"$values"`, the mark's values, where the part gives them; by its
field in `MY_MENU_EMPTY`). A hand proof in `FRAME_PROOFS` is the values it chose
(`"proved"`, or `"sampled"`, how many samples, and `"linear"`), the `"run"` it was made in, its `"date"` and its
`"menu"` row, and the owner's word for a never-open row it opened (`"allowance"`); a note's evidence is `"note+"`; an
`UNPROVED` reason's day is its place `"1"` in `[kind, day, why]`; what shows a `NOT_OFFERED` mark is its `"evidence"`
(and a held value's downloads, `"files"`).

The two passes read it differently:

- **The ILCE-1M2's own pass** puts it back into its tables (`kit/writer/hand_evidence.py`, as
  `kit/writer/hand_tables.py` reads them): it only adds to the tables' entries (an entry the tables lack, or a public
  value it would replace, is refused in plain words, naming the file, the table and the key). A `"note+"` and an
  `"allowance"` are put after the public note, and the writer sets apart, into `note_evidence`, what names a run
  folder or a day (`split_evidence` in `kit/writer/notes.py`): evidence worded without either would stay in the note,
  so that file keeps the form the docs show (`"(seen on the camera, <day>)"`, `"the owner allowed <row> remotely,
  <day>"`).
- **The plain pass**, every other camera's, never puts it into the tables. It takes the file only as its JSON Schema
  allows (evidence fields only, table by table, so nothing in it sets a public fact such as a group, a tab, a value's
  name or a held mark), every part on an entry the public tables hold, a `NOT_OFFERED` part with its `"$key"` (and its
  `"$values"` too where the table gives the setting more than one mark, so a reorder or an insertion there never moves
  one mark's evidence onto another), and a `"note+"` only for an entry with a public note; it stops on anything else
  in plain words naming the table, the key and the field, never a value. A mark whose part no longer gives evidence
  loses it, said with the mark's value. Then it writes each piece only into a field the definition keeps as evidence, however
  it is worded: a hand proof's values, run, day and rows into the setting's proof, a `"note+"` (its parentheses aside)
  and an `"allowance"` into `note_evidence`, a reason's day into `unproved_reason`'s date, a mark's evidence into the
  mark's. A public note is the public table's note, word for word.

What the evidence adds goes, when the definition is written, into the definition's evidence file,
`private/evidence/<model>_fw<fw>.json`. `.venv/bin/python kit/writer/hand_evidence.py --check [--camera
<model>_fw<fw>]` says, read only, which parts of a camera's hand evidence the plain pass would refuse, by table, key and
field, never a value (exit 1 when there is any): the way to bring the ILCE-1M2's file in line before the two passes
become one.

For any camera, `kit/schema_update.py --write` stops, before it reads the definition, while the camera's hand tables
hold `FRAME_PROOFS`, `UNPROVED` or `NOT_OFFERED` entries and this file is not on the computer: a definition written
without it would lose those proofs; a look (no `--write`) says so before anything else, and goes on. A mapper who
proved none of those entries by hand says so with the file holding no evidence:

```json
{"$schema": "../../schemas/hand-evidence.schema.json", "hand_format": 2, "camera": "<model>_fw<fw>", "tables": {}}
```

Either pass also stops, before it reads the definition, on a hand proof that names no run, day or menu row: no
default stands in for them. Schema:
`schemas/hand-evidence.schema.json`; the kit's tests check the file against it where this computer holds it.

{{ schema_fields("hand-evidence") }}

A `FRAME_PROOFS` entry's evidence:

{{ schema_fields("hand-evidence", "properties/tables/properties/FRAME_PROOFS/additionalProperties") }}

## The menu tree: the camera's menus

`private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json` holds every row of the menus, page by page, as the
kit's walk read them: the Stills menu in `tabs`, and each other shooting mode's menu in `modes`. It is the mapper's
own: which rows the walk found greyed or could not read, and which option lists it read, are the state the camera
stood in. `kit/tools/menu_tree.py --crawl <crawl> [--crawl ...]` writes it from the page scan's page model and the
crawls' walks and maps (`--dry-run` first; an existing one is replaced only with `--replace`); `--mode Movie --scan
<scan> [--crawl <crawl>]` writes another mode's menu into `modes`, the Stills menu left as it is. A mode read off its
page scan alone has each page's top rows only, "seen"; the placement takes the rows under them from the proofs' own
paths. The proof viewer's rows come from it, and each setting's place in the definition, which is what is public of
the menus. Schema: `schemas/menu-tree.schema.json`.

{{ schema_fields("menu-tree") }}

## `data/<model>_fw<fw>/help_<model>_fw<fw>.json`: each setting's help

The project's own words for each setting and option, merged into the definition's `help` and `option_help` by
`kit/schema_update.py`. The camera's In-Camera Guide text, read off your camera, is kept in a file of the same shape
in your own `private/help/`, which the editor and the proof viewer show in place of the definition's when they find
it, text by text: a setting's help, and each option's by its value (decision 18). Schema:
`schemas/help-file.schema.json`.

A help file is used only for the camera it says it is for: its own `model` and `firmware` must be the definition's.
The file name is only where it is looked for; setting keys can be the same on two Sony bodies, so a file copied or
renamed for another camera, or for another firmware of the same model, would put that camera's text on the wrong
settings. The kit (`kit/camkit/help_files.py`), the editor and the proof viewer refuse such a file, and one that names
neither: its text is not merged or shown, and they say why (the kit in its output, the editor in Settings > Camera
support & web page). A definition merged from a refused file of its own gets no help, and `kit/tools/check_public.py`
refuses the commit. Help never passes from one camera's definition to another's: a new camera's first definition starts
with none.

{{ schema_fields("help-file") }}

## The reset file: what each reset puts back

`data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json` says, setting by setting, what Camera Settings Reset (`result`)
and Initialize (`initialize`) did on the owner's body: `resets`, the reset put the setting back; `keeps`, it left it as
it was. You write it by hand after the reset tests of the playbook's Phase 5, from the downloads before and after each
reset, and edit it there: it is the one file the kit reads, public, and the kit keeps no other copy of it. Schema:
`schemas/settings-reset.schema.json`, which the hooks and CI check; `kit/camkit/datafiles.py` (`reset_not_lean`) and
`kit/tools/check_public.py` hold it to the same lean shape.

It holds `about` (a sentence on what the file is) and `records`, by the definition's setting key, each with the
setting's `name` and `tab` as the definition has them and one reading or both. Nothing else: no date, count or note
about the tests, which go in your own notes in `private/`. Leave out a setting whose test value might have been the
value the reset gives (the factory value, say): its reading would only say the camera held another value before the
test, so it is not listed, as a setting not tested is not. `kit/schema_update.py --write` (and `--from-data --write`)
refreshes each listed setting's `name` and `tab` from the definition, where a name is corrected, and touches nothing
else. A file in the older whole shape (the tests' own words, dates, a reading such as "keeps (test value looks like the
default)") is never rewritten: the writer stops and `check_public.py` refuses it, each naming
`kit/tools/move_evidence.py`, which keeps the whole file once in `private/evidence/<model>_fw<fw>/` as an archive the
kit never reads and writes the lean one in its place.

{{ schema_fields("settings-reset") }}

### A setting's readings

{{ schema_fields("settings-reset", "$defs/record") }}

## The accepted file: what the report leaves open

`kit/schema_update.py --write` refuses to write the definition (exit 1, each question listed) while pass 2's report
holds something it does not settle and this file does not accept: a conflict whose label the writer keeps against the
camera's reading (a hand rule such as a camera's `KEEP_LABELS`, in its [hand tables file](#the-hand-tables-file-what-the-mapping-found-by-hand), or a picker reading
that is not sure), a new record it does not add, a record not one to one (it loses its proof and is marked
`disputed`), a name dispute (the bar's OCR or the vision model read another name than the map's) or a value a record
carried over from the option before outside a hand rule. A section the report lacks counts as empty. Each question is
settled with a proof, or looked at (report.md, the proof viewer) and accepted here with why; `--force` writes anyway
with a loud warning, never for a submission. The file, `private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json`,
is the mapper's own, for each entry is a ruling on one mapping's report; the pull request carries the gate's count
line instead.

An entry covers the report's questions of its kind and key, and of its value and label where it names them; one
without a value covers every value of the record. Every entry answers a question the report holds now: one that no
longer does (the question settled by a proof or by a writer rule) is taken out, so it cannot hide a later question on
the same record, and `--write` lists any such entry. A carried-over entry never names the value: the value a record kept
may be the camera's own setting ([decision 16](decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).
Schema: `schemas/accepted.schema.json`.

{{ schema_fields("accepted") }}

### An entry

{{ schema_fields("accepted", "properties/accepted/items") }}
