# 20. The editor holds no camera facts

- **Date:** 2026-11-04; carried out 2026-11-06; changed 2026-11-13
- **Status:** accepted
- **Rule:** The editor holds no camera facts: each, the file's layout included, is in the definition, and an unknown
  kind is refused; the kit's move into the camera's data.

## Context

With definitions already files ([decision 19](0019-definitions-are-files-one-per-model-and-firmware.md)), an audit
found the ILCE-1M2's facts in 26 places of the editor's code (a rule that hid expert-only settings by their names among
them) and the file's container compiled in, in the kit too: a file that differed in one offset needed new programs.
The a1 II's facts in the kit's code kept another body's facts found by hand out of its definition, and could leave a
lens list, with serial numbers, in its published sample.

## Decision

Every camera-specific fact, the container layout included, is in the definition (`camera.file`, the container block;
other additive `camera` keys; a per-setting `expert` flag), so a definition can be made to match a camera without
changing the program. The editor holds only the vocabulary the block's words name and generic photography; it refuses
a kind it does not know by name, and reads a file by trial against every loaded block. The kit keeps a camera's facts
as its data (the camera file and the hand tables in `data/<model>_fw<fw>/`), but the safety lists, which guard every
body, stay code, extended with each body's names. The a1 II's tables still in the kit's code (`kit/camkit/models.py`)
apply to that body alone, each marked to move into its data.

Before 2026-11-13 the record spoke of the editor alone.

## Consequences

- A checksum, framing or encoding the vocabulary lacks needs a program change: a definition names an algorithm, never
  carries one.
- A file is edited only when both its checksums hold under its block. With no definition loaded, no file opens.
- `editor/src/no_camera_facts.rs` catches camera names in the editor's code, not behaviour: the rule rests on review.
- `docs/formats/sony_camset.ksy` is tied to the ILCE-1M2's block by a test until it is generated from it.
- Each body's sample is scrubbed by its own camera file's `personal_records`.
