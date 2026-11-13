# Contributing

A pull request here is one of two kinds:

- **A camera's data,** made with the mapping kit on that camera: a `data/<model>_fw<fw>/` folder for one body and
  firmware. Start with [AGENTS.md](AGENTS.md); an AI agent walks you through the mapping.
  If you are mapping with an older clone, [update it first](docs/UPDATING.md): every clone moves to the lean files
  once; in one made before the history was replaced by a single commit `git pull` no longer works, and a definition
  the older kit wrote is not to be sent.
- **Code and docs:** the editor (`editor/`), the kit (`kit/`) and the docs site (`docs/`). The commands are in the
  README, [Develop](README.md#develop).

Everyone taking part keeps to the [Code of Conduct](CODE_OF_CONDUCT.md).

## What "verified" means here

The kit proves every record by a differential proof: it chooses one option on the camera, downloads the settings file
before and after, and keeps the frames that show the option, so each value comes with its evidence. Pass 1 maps the
menus read-only, pass 2 proves each option and pass 3 the settings another one greys out
([the kit's design](docs/KIT_PLAN.md#how-a-value-is-proved)). A camera is done when the playbook's
[section 15](docs/REMAPPING_PLAYBOOK.md#15-what-done-looks-like) holds: among other things, `kit/pass2_report.py`
shows no unexplained conflict or missing value.

The docs use two levels. A camera **mapped and proved by the kit** (so far the ILCE-1M2, firmware 4.00) has files the
editor can edit; any other camera is **not mapped yet**, and the README's
[Supported cameras](README.md#supported-cameras) says how far its files open.

## What the maintainer checks

- **On every pull request, automatically:** the kit's tests, the publish guard over every tracked file
  (`kit/tools/check_public.py --all`) and, by the same rules, over every file each commit of the pull request adds or changes (`--commits`), the camera helpers' own test and every data file, a new camera's folder
  included, against its JSON Schema (`.github/workflows/kit-ci.yml`); the editor's build, tests and lints on macOS,
  Windows and Linux (`.github/workflows/editor-ci.yml`); and the sign-offs (`.github/workflows/dco.yml`). The docs
  site's build (`zensical build --strict`) is checked by the pre-commit hooks, which the template asks you to run; it
  does not run on the pull request yet.
- **By hand:** the pass-2 report's counts and conflicts and the writer's gate line (`kit/schema_update.py` without
  `--write` prints "gate: … open questions …"; the report stays in your `runs/`, so the template asks you to paste
  both); the personal records listed in your camera file and how each was found, or what was tried before an empty
  list (the template asks for it: the records' ids only, never the bytes a diff printed), and any record a pull
  request takes out of a camera's list or whose default bytes it changes, which the publish guard stops for this
  look. For a new camera the maintainer reads every `keep_text` entry as text that will be published and every
  default's bytes as bytes that will be published: the guard has no older list to compare them with. And spot checks. The maintainer does not go through your runs, and the proof viewer is yours: it is
  built only from the runs on your computer, to check each value against your camera's screens, and is never sent. A camera of the maintainer's own model, the ILCE-1M2, can be re-checked on the
  maintainer's body.

## What a contribution must keep

- No text from Sony's In-Camera Guide or Help Guide: help is written in your own words
  ([decision 13](docs/decisions/0013-sony-s-help-text-stays-private.md)).
- No values or names from anyone's camera ([decision 16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)):
  the only settings files published are the definitions' samples, which `kit/tools/make_sample.py` scrubs of text and
  of the records your camera file lists in `personal_records` (a lens list with serial numbers, a file-name prefix;
  [DATA_CONTRACTS](docs/DATA_CONTRACTS.md#records-that-hold-an-owners-own-data-personal_records)).
  `kit/tools/check_public.py` refuses a commit that tracks `private/`, `runs/`, a file of Sony's SDK, a settings file
  no definition names as its sample or another binary file, and any MAC address, private network address, serial-number value, e-mail address or home
  folder but the placeholders the docs use, or a path in `private/` other than the places
  [decision 18](docs/decisions/0018-one-public-codebase-with-a-private-overlay.md) names. It finds your name only when
  your `private/config.json` lists it under `"private_strings"` or your `private/` holds the camera's properties
  (`private/data/picture_profile/properties.json`), a public address of yours only when it is in your
  `private/config.json`, and help text too close to the camera's only with your `private/help/`. So before the pull
  request, also search your diff for your name, your camera's serial number where nothing labels it as one, and any
  public address of yours.
- Your camera's definition as `kit/schema_update.py --write` wrote it, never edited by hand, and no other camera's
  definition changed. It is lean: how, when and in which run each thing was proved is in your evidence file,
  `private/evidence/<model>_fw<fw>.json`, which is never sent, and `kit/tools/check_public.py` refuses a definition
  that carries any of it ([decision 16](docs/decisions/0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)). What your mapping found by hand
  goes into your camera's hand tables file, `data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json` (the playbook,
  Phase 6: names, value tables and facts, only the tables your camera's pass reads, which
  [Data files](docs/DATA_CONTRACTS.md#the-hand-tables-file-what-the-mapping-found-by-hand) lists), sent with the
  `data/` folder; how each was proved stays in your `private/evidence/<model>_fw<fw>.hand.json`, never sent. A fix to
  what one of the ILCE-1M2's records means goes into its hand tables file,
  `data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json` (the hand proofs are the
  maintainer's, in `private/evidence/`), and the maintainer rewrites that definition from them
  (`kit/tools/build_docs.py --write-schema`, which needs the camera runs and the hand evidence only the maintainer has); a fix to a camera
  file in `data/` reaches its definition with `kit/tools/build_docs.py --definitions`, which needs no runs.
- The camera set to English while you map it: the kit's readers and menu trees were built on English menus, and
  [decision 8](docs/decisions/0008-by-hand-only-usb-language-region-and-network-identity.md) leaves the language to your
  hand ([Camera support](docs/CAMERA_SUPPORT.md#the-cameras-menus-must-be-in-english)).
- No files from `private/`, `runs/` or Sony's SDK (`kit/sdk/`)
  ([decision 18](docs/decisions/0018-one-public-codebase-with-a-private-overlay.md); the SDK's terms:
  [RELEASING](docs/RELEASING.md)).
- None of them in any commit either: a pull request publishes its branch's whole history, so open it from a fresh
  branch cut from the updated `main` with one commit of your final files, as
  [UPDATING](docs/UPDATING.md#your-pull-request-one-commit-on-a-fresh-branch) shows.

You do not need a background in verification: the kit does the proving. You need patience (how long it takes: the
playbook's [section 11](docs/REMAPPING_PLAYBOOK.md#11-time-power-and-heat)), the camera, and the hardware
[QUICKSTART](docs/QUICKSTART.md#what-you-need) lists.

## Sign off every commit

Commit with `git commit -s` (or `git commit --amend -s` for the last commit). It adds a `Signed-off-by:` line with your
name and email, which certifies the [Developer Certificate of Origin](https://developercertificate.org/): that you have
the right to submit the work under the project's MIT licence. It is the project's lightweight stand-in for a
contributor licence agreement. `.github/workflows/dco.yml` runs `dco-check` on each pull request and fails it when a
commit is not signed off. The sign-off carries the name and email in your git settings (`git config user.name`,
`user.email`), and they become public with the commit.
