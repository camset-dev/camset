# 14. One source per fact

- **Date:** 2026-11-03; changed 2026-11-06
- **Status:** accepted
- **Rule:** Each fact is edited in one place; pages are rendered from their sources, and the few generated files
  committed are rebuilt by their tool, never by hand.

## Context

The same facts had drifted in several places: the camera facts in two files, counts in four documents, generated documents from a retired kit, a README pointing at removed commands.

## Decision

Each fact is edited in one place; [Where each fact lives](../WHERE_FACTS_LIVE.md) says which. Pages are rendered
from their sources when the docs site is built ([decision 17](0017-the-docs-are-built-with-zensical.md)), so no
generated page is committed. The settings file's container has one source, the camera file's container block
([decision 20](0020-the-editor-holds-no-camera-facts.md)), which `docs/formats/sony_camset.ksy` describes for
Kaitai's tools, tied to it by a test until the `.ksy` is generated from the block. The data files have JSON Schemas.
The generated files other tools read as files stay committed (each definition's record names, the Python reader
compiled from the `.ksy`, the C++ safety lists), as do two lists in files written by hand (the decisions table, the
nav's model pages): `kit/tools/build_docs.py` writes them, and the pre-commit hook runs it. A camera's definition is
written only by `kit/schema_update.py --write`, never by the hook
([decision 19](0019-definitions-are-files-one-per-model-and-firmware.md)).

Before 2026-11-06 the file format's one source was the Kaitai spec; the record first named MkDocs (mkdocs-macros) as
the renderer, which Zensical replaced on 2026-11-03.

## Consequences

- A new generated file goes into `kit/tools/build_docs.py` and the pre-commit hook's list; CI's `build_docs.py
  --check` and a test (`kit/tests/test_build_docs.py`) fail when a committed one differs from what its source gives.
- What a definition takes from `data/` alone is held to the same: `kit/schema_update.py --from-data` gives the
  committed definitions byte for byte (`kit/tests/test_definitions.py`), and `kit/tools/build_docs.py --definitions`
  brings them up to date after a camera file or help file is edited.
