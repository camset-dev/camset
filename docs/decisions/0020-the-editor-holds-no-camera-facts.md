# 20. The editor holds no camera facts

- **Date:** 2026-11-04; carried out 2026-11-06; changed 2026-11-13
- **Status:** accepted
- **Rule:** The editor holds no camera facts: each, the file's layout included, is in the definition, and an unknown
  kind is refused; the kit's move into the camera's data.

## Context

Decision 19 made definitions files read at run time, yet an audit of `editor/src` found the ILCE-1M2's facts in 26
places (the memory mirrors and sets, the default compare columns, menu names, the link's timing, a rule that hid
expert-only settings by their names, the built-in sample), and the file's container compiled in as constants, in
`kit/camkit/camset.py` and `kit/tools/identify.py` too. A camera whose file differed from the a1 II's in one offset
needed a new editor, and nobody could make a definition match their camera without changing the program. The kit,
built on the a1 II, held more of that body's facts in its code (its hand tables, the records that hold an owner's own
data, the record that names the shooting mode): a fact found by hand on another body could not reach its definition,
and that body's published sample could keep a lens list with its serial numbers.

## Decision

The editor knows nothing about any camera. Every camera-specific fact, the file's header and container layout
included, lives in the definition, so a definition can be made to match a camera without changing the program:
`camera.file` describes the whole container, and the other facts are additive `camera` keys and a per-setting
`expert` flag. The program holds only the vocabulary the block's words name and generic photography (APEX stops,
labels such as "F2.8" and "1/250"); a kind it does not know is refused by name, never guessed. A file is read by
trial against every loaded block.

The kit keeps a camera's facts as that camera's data, in `data/<model>_fw<fw>/`: the camera file (the container
block, which the kit reads files through as the editor does, the records that hold an owner's own data, the live
records its tools read), which the definition's `camera` section is copied from, and the hand tables (what the mapping
found by hand), which `kit/schema_update.py` applies to that camera's definition alone; each of the two has its JSON
Schema. How each hand fact was proved is the mapper's, in a private file whose shape is public
(`schemas/hand-evidence.schema.json`; [decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).
The safety lists stay code (`kit/camkit/safety.py`), extended with each body's names, since they guard every body;
camlink and the camera helper compile in their buttons and properties never sent (`kit/common/never_touch.h`). The a1
II's tables still in the kit's code (`kit/camkit/models.py` names them) apply to that body's files alone, left out or
refused on any other, and each is marked to move into its data.

Before 2026-11-13 the record spoke of the editor alone, and of the kit only that it reads the same block from the
camera file; it did not record Edit anyway…, which the editor had by 0.1.0 (2026-11-09).

## Consequences

- A camera whose file uses the known checksums and framing but places its fields elsewhere needs a block, not a new
  editor; whoever writes it learns at once whether it reads the file (`kit/tools/identify.py` drafts one for a file no
  block reads). A container that needs a checksum, framing or encoding the vocabulary lacks still needs a change to
  the programs: a definition names an algorithm, never carries one.
- A file is edited only when both its checksums hold under its block; one whose layout signature or section counts
  are not the definition's opens view-only (for the definition's model, Edit anyway… unlocks the settings kept where
  the editor expects them). With no definition loaded, no file opens.
- One of the editor's tests fails where its code or texts name a setting key, a record id, a camera model or a shipped
  definition's file (`editor/src/no_camera_facts.rs`); it catches names, not behaviour, so the rule still rests on
  review.
- The container's one source is the block; `docs/formats/sony_camset.ksy` describes the ILCE-1M2's for Kaitai's
  tools, tied to its block by a test until the `.ksy` is generated from it.
- Another body's mapping records what it finds by hand in its own hand tables, and its sample is scrubbed by its own
  camera file's `personal_records`, without which `kit/tools/make_sample.py` and `kit/tools/check_public.py` refuse it.

See also: [the data files' page](../DATA_CONTRACTS.md#the-container-block-file) (the container block, the camera file,
the hand tables and the hand evidence file) and [decision 14](0014-one-source-per-fact.md) (one source per fact).
