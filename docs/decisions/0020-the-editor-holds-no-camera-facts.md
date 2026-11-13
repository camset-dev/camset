# 20. The editor holds no camera facts

- **Date:** 2026-11-04
- **Status:** accepted; amends [11](0011-the-editor-s-schema-is-the-contract-and-it-only-grows.md),
  [14](0014-one-source-per-fact.md) and [19](0019-definitions-are-files-one-per-model-and-firmware.md); carried out
  2026-11-06; its example block and vocabulary corrected on 2026-11-06 (the ILCE-1M2's byte 0x38 is the video
  system, not a firmware digit); trimmed 2026-11-08: its working notes moved to
  [the data files' page](../DATA_CONTRACTS.md#the-container-block-file)
- **Rule:** The editor knows nothing about any camera: every camera fact, the file's layout included, lives in the
  definition, and a kind it does not know is refused.

## Context

Decision 19 makes definitions files read at run time, yet an audit of `editor/src` found the ILCE-1M2's facts in 26
places (the memory mirrors and sets, the default compare columns, menu names, the link's timing, a rule that hides
expert-only settings by their names, the built-in sample), and the file's container compiled in as constants, in
`kit/camkit/camset.py` and `kit/tools/identify.py` too. As it stands, a camera whose file differs from the a1 II's in
one offset needs a new editor, and nobody can make a definition match their camera without changing the program.

## Decision

The editor knows nothing about any camera. Every camera-specific fact, the file's header and container layout
included, lives in the definition, so a definition can be made to match a camera without changing the program:
`camera.file` describes the whole container, and the other facts are additive `camera` keys and a per-setting
`expert` flag. The program holds only the vocabulary the block's words name and generic photography (APEX stops,
labels such as "F2.8" and "1/250"); a kind it does not know is refused by name, never guessed. A file is read by
trial against every loaded block. The kit reads the same block from the camera file.

## Consequences

- A camera whose file uses the known checksums and framing but places its fields elsewhere needs a block, not a new
  editor; whoever writes it learns at once whether it reads the file. A container that needs a checksum, framing or
  encoding the vocabulary lacks still needs a change to the program: a definition names an algorithm, never carries one.
- A file is edited only when both checksums verify under its block, its layout signature is the definition's and its
  section counts match; a wrong or guessed block leaves it view-only. With no definition loaded, no file opens.
- Decision 11 is amended: inside `camera.file`, a kind the editor does not know refuses the definition instead of
  being ignored; elsewhere new fields are still ignored. Decision 14 is amended: the container's one source is the
  block, which `docs/formats/sony_camset.ksy` describes, tied to it by a test until the `.ksy` is generated from the
  block. Decision 19 is amended: the header is read through each definition's block, and the sample is a file beside
  its definition.
