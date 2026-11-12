# The file format

`sony_camset.ksy` describes a Sony camera settings file as the ILCE-1M2 writes it, in
[Kaitai Struct](https://kaitai.io/), an open, declarative language for binary formats, for people and for the tools
that read files with it: Kaitai's Web IDE, its compiler and ImHex open a `.DAT` with it. It is written by hand, and it
is the container block the ILCE-1M2 writes: the `file` block of its camera file and definition
([the container block](../DATA_CONTRACTS.md#the-container-block-file);
[decision 20](../decisions/0020-the-editor-holds-no-camera-facts.md)), the contract the editor, the kit and the proof
viewer read a file with. There is one such spec per container block: a body whose block differs gets one of its own
beside it. A test ties this file to the ILCE-1M2's block and reads the sample both ways, with the Python reader
`kaitai-struct-compiler` generates from it (`kit/camkit/formats/`, with `SOURCES.json`, the SHA-256 of what each `.ksy`
gave the reader, its comments and the record names' docs left out, so that `kit/tools/build_docs.py --check` sees a
`.ksy` changed since in what the reader holds, with no compiler).

The record names are generated, one file per definition (`kit/tools/build_docs.py`):
`sony_camset_ids_<model>_fw<fw>.ksy`, with the Kaitai id `sony_camset_ids_<model>_fw<fw>` in lower case and `_` for
anything else. `sony_camset.ksy` imports the ILCE-1M2's, `sony_camset_ids_ILCE-1M2_fw4.00.ksy` (Kaitai id
`sony_camset_ids_ilce_1m2_fw4_00`); Kaitai's tools find an import by its file name, so in the Web IDE upload both
files. A second camera's definition gets its own file the next time the generated files are built.

The container (the header, the sections of records and the two checksums) is taken to be shared by Sony bodies,
and so far it is verified on one, the ILCE-1M2: by the camera runs on firmware 4.00, and on two files from other
bodies saved, by their header bytes, by firmware 2.00 and 3.00, which it reads with every shared record in the
same order ([its page](../models/ILCE-1M2_fw4.00.md), "Other firmware", 2026-10-31). The header's firmware is two
bytes, the major and the minor version; the byte after them is the video system the camera was set to (0 NTSC, 1 PAL),
proved on the ILCE-1M2 at firmware 4.00 on 2026-11-06. Until then the three were read as one firmware, which made a
file saved on PAL another firmware (x.01). A body whose container
differs in where its parts sit needs a block of its own, not a new program; `sony_camset_ids_ILCE-1M2_fw4.00.ksy` holds
the ILCE-1M2's record names only.

The editor's reader (`editor/src/camset.rs`) and the kit's (`kit/camkit/camset.py`) hold the same vocabulary the
block's words name; both compute the same layout signature, which their tests check on the sample.

```yaml
--8<-- "docs/formats/sony_camset.ksy"
```

[The memory map](../MEMORY_MAP.md) lists every record of a file.
