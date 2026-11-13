# Where each fact lives

Each fact is edited in one place (decision 14, `docs/decisions/0014-one-source-per-fact.md`). Pages are
rendered from their sources when the docs site is built (Zensical, `mkdocs.yml`), so none is committed; the few
generated files other tools read are rebuilt by the pre-commit hook, which stops a commit that left one stale. The
one exception is each camera's definition, `editor/definitions/<model>_fw<fw>.json`: only `kit/schema_update.py
--write` (or `kit/tools/build_docs.py --write-schema`) writes it, for the camera the kit works on and on the machine
that holds its runs, and `build_docs.py --definitions` its parts from `data/`; the hook never does.

| Fact | Edited in | Rendered or generated into |
|---|---|---|
| What each record means, and its proof | the proof runs in `runs/<model>_fw<fw>/`, and for the ILCE-1M2 its hand tables (`kit/writer/a1_tables.py`: names, value tables and facts; their proofs in the mapper's `private/evidence/<model>_fw<fw>.hand.json`) | the camera's definition, `editor/definitions/<model>_fw<fw>.json` (with `schema_update.py --write`); the Status and Memory map pages; the record names (`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`, one per definition); the proof viewer |
| The camera's own facts (the file's container, tabs, colours, memories, families, the records that hold an owner's own data, wording) | `data/<model>_fw<fw>/camera_<model>_fw<fw>.json` | its definition's `camera` section; the kit's reader and identify.py read the container block from it; `kit/tools/make_sample.py` and `kit/tools/check_public.py` read `personal_records` from it |
| The camera's menus | pass 1's runs (the page scan and the crawls), from which `kit/tools/menu_tree.py` writes the mapper's own `private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json` | the definition's places (`row`, `row_at`); the proof viewer's rows |
| Each setting's help | `data/<model>_fw<fw>/help_<model>_fw<fw>.json` (our own words); the camera's own text in your `private/help/` (decision 18) | the definition's `help` fields; the editor and the proof viewer show the private text when it is there |
| The file format | the camera file's container block (`file`, decision 20); for people and Kaitai's tools, `docs/formats/sony_camset.ksy` (by hand, the ILCE-1M2's, tied to its block by a test) | the editor's, the kit's and the proof viewer's readers, which read every file through its block; the Memory map's header; the Python reader a test generates from the `.ksy` (`kit/camkit/formats/`) |
| What the definition viewer shows (each camera's settings by name, its menu, the sample until a file is opened) | each camera's definition in `editor/definitions/`, and the sample beside it that the definition's camera section names (`<model>_fw<fw>.DAT`, `kit/tools/make_sample.py`); the page itself, `kit/tools/proof_viewer.html` | the definition viewer, built by `kit/tools/proof_viewer.py --public` from those files alone: the docs site's `viewer/` (`.github/workflows/docs.yml`) and each release's one-file `camset-viewer.html` (`--single`); never committed |
| The data files' shape | `schemas/*.schema.json` (JSON Schema) | the Data files page; checked by `check-jsonschema` |
| How a camera behaves, and what was measured on it | its page, `docs/models/<model>_fw<fw>.md` (named by its definition's `layouts[].doc`) | the page's measured block is rendered from its definition; its entry in the site's nav (`mkdocs.yml`) is written by `kit/tools/build_docs.py` |
| Why things are done as they are | each record in `docs/decisions/` (its title, date and status too) | the table in `docs/decisions/index.md`, written by `kit/tools/build_docs.py` |
| What the kit never sends to a camera (buttons, properties) | `kit/camkit/safety.py` | `kit/common/never_touch.h`, which camlink and the camera helper compile in, written by `kit/tools/build_docs.py` |
| How the kit works, and why | `docs/KIT_PLAN.md` | (nothing: link to it) |
| The rules for mapping someone else's camera | the playbook, section 1 (`docs/REMAPPING_PLAYBOOK.md`) | (nothing: link to it) |
| How long things take | the playbook, section 11 | (nothing: link to it) |
| Which data files a mapping delivers, and how each is made | `docs/DATA_CONTRACTS.md`, "What a mapping delivers" | (nothing: link to it) |
| Which login a camera gets | `kit/common/camera_net.h`; in words, `docs/EDITOR.md`, "The camera link" | (nothing: link to it) |
| What a body's SDK support allows, and how to check it | `docs/CAMERA_SUPPORT.md`; the table itself from one's own SDK (`kit/tools/sdk_support.py --json`, into `private/data/`) | `kit/tools/body_check.py` reads the table |
| The SDK's terms, what is fine to publish, and how a release is made | `docs/RELEASING.md` | (nothing: link to it) |
| The commands to install and run the kit | `kit/setup.py` (the install, one command); `docs/QUICKSTART.md` (the steps and the command cheat sheet); `docs/PORTING.md`, "Setup per OS" (the install by hand); each prover's options in the playbook, section 7 | (nothing: link to it) |
| What a session did | one's own notes, in one's own `private/` (never published) | (nothing) |
| Where the work stands | (nothing: rendered) | the Status page, a model page's measured block |
