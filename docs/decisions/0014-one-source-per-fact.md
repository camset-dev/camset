# 14. One source per fact

- **Date:** 2026-11-03; changed 2026-11-06
- **Status:** accepted
- **Rule:** Each fact is edited in one place; pages are rendered from their sources, and the few generated files
  committed are rebuilt by their tool, never by hand.

## Context

The same facts had drifted in several places: the camera facts in two files, counts in four documents, generated documents from a retired kit, a README pointing at removed commands.

## Decision

Each fact is edited in one place, as the table below says. Pages are rendered from their sources when the docs site is
built ([decision 17](0017-the-docs-are-built-with-zensical.md)), so no generated page is committed. The settings
file's container has one source, the camera file's container block
([decision 20](0020-the-editor-holds-no-camera-facts.md)), which `docs/formats/sony_camset.ksy` describes for
Kaitai's tools, tied to it by a test until the `.ksy` is generated from the block. The data files have JSON Schemas.
The generated files other tools read as files stay committed (each definition's record names, the Python reader
compiled from the `.ksy`, the C++ safety lists), as do two lists in files written by hand (the decisions table, the
nav's model pages): `kit/tools/build_docs.py` writes them, and the pre-commit hook runs it. A camera's definition is
written only by `kit/schema_update.py --write`, never by the hook
([decision 19](0019-definitions-are-files-one-per-model-and-firmware.md)).

| Fact | Edited in | Rendered or generated into |
|---|---|---|
| What each record means, and its proof | the proof runs; the hand tables (`data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json`), their proofs in `private/evidence/` | the definition; the Status and Memory map pages; the record names (`docs/formats/sony_camset_ids_<model>_fw<fw>.ksy`); the proof viewer |
| The camera's own facts (container, tabs, memories, `personal_records`, wording) | `data/<model>_fw<fw>/camera_<model>_fw<fw>.json` | the definition's `camera` section; read by the kit's reader, `identify.py`, `make_sample.py` and `check_public.py` |
| The camera's menus | pass 1's runs, which `kit/tools/menu_tree.py` turns into the mapper's `private/evidence/` menu tree | the definition's `row` and `row_at`; the proof viewer's rows |
| Each setting's help | `data/<model>_fw<fw>/help_<model>_fw<fw>.json`; the camera's own text in `private/help/` | the definition's `help`; the editor and the proof viewer show the private text where it is |
| The file format | the container block; `docs/formats/sony_camset.ksy` | every reader; the Memory map's header; `kit/camkit/formats/` |
| The definition viewer | the definitions, their samples (`kit/tools/make_sample.py`), `kit/tools/proof_viewer.html` | `proof_viewer.py --public`: the site's `viewer/`, each release's `camset-viewer.html` |
| The data files' shape | `schemas/*.schema.json` | the Data files page; `check-jsonschema` |
| How a camera behaves | `docs/models/<model>_fw<fw>.md` | its measured block, from the definition; its nav entry |
| Why things are done as they are | each record here | `docs/decisions/index.md`'s table |
| What the kit never sends | `kit/camkit/safety.py` | `kit/common/never_touch.h` |
| How the kit works | `docs/KIT_PLAN.md` | |
| The mapping rules; how long things take | the playbook, sections 1 and 11 | |
| What a mapping delivers | `docs/DATA_CONTRACTS.md` | |
| Which login a camera gets | `kit/common/camera_net.h`; in words, `docs/EDITOR.md` | |
| What the kit can do with a body | the SDK table, `kit/tools/sdk_support.py --json` into `private/data/` | `kit/tools/body_check.py` reads it |
| The SDK's terms; releases | `docs/RELEASING.md` | |
| Installing and running the kit | `kit/setup.py`; `docs/QUICKSTART.md`; `docs/PORTING.md`; each tool's `--help` | |

Before 2026-11-06 the file format's one source was the Kaitai spec; the record first named MkDocs (mkdocs-macros) as
the renderer, which Zensical replaced on 2026-11-03. Before 2026-11-14 the table was its own page, Where each fact
lives.

## Consequences

- A new generated file goes into `kit/tools/build_docs.py` and the pre-commit hook's list; CI's `build_docs.py
  --check` and a test (`kit/tests/test_build_docs.py`) fail when a committed one differs from what its source gives.
- What a definition takes from `data/` alone is held to the same: `kit/schema_update.py --from-data` gives the
  committed definitions byte for byte (`kit/tests/test_definitions.py`), and `kit/tools/build_docs.py --definitions`
  brings them up to date after a camera file or help file is edited.
