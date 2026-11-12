# The container block the ILCE-1M2 writes, for people and for Kaitai's tools and ImHex: the "file" block of its camera
# file (data/ILCE-1M2_fw4.00/camera_ILCE-1M2_fw4.00.json, its definition's camera.file). One such spec per container
# block: a body whose block differs gets a spec of its own beside this one when it appears. Written by hand. The
# contract the kit and the editor read a file with is the camera's container block (docs/decisions/0020);
# kit/tests/test_definitions.py ties this file to the ILCE-1M2's block, reading the sample both ways with the Python
# reader generated from it (kit/camkit/formats/, kit/tools/build_docs.py runs kaitai-struct-compiler). The record names
# it imports (sony_camset_ids_ILCE-1M2_fw4.00.ksy) are generated from editor/definitions/ILCE-1M2_fw4.00.json, one
# such file per definition.
meta:
  id: sony_camset
  title: Sony camera settings file (Save/Load Settings, CAMSET .DAT)
  file-extension: dat
  endian: le
  encoding: ASCII
  imports:
    - sony_camset_ids_ILCE-1M2_fw4.00
doc: |
  A Sony camera's settings as Save/Load Settings writes them to the card (PRIVATE/SONY/CAMSET), and as the
  Camera Remote SDK downloads them. Section 0 holds the live settings; sections 1 on hold the memory sets
  (on the ILCE-1M2: Stills, Movie, S&Q and Time-lapse memories 1-3 each), every set the same layout.
  Values are little-endian signed integers of the record's element size. Read and verified on the
  ILCE-1M2 (a1 II), firmware 4.00, layout 07a5b07a502c68f0; the record names are that body's.
  The two checksums are sums a writer recomputes: header_checksum over 0x00-0x38, body_checksum over
  0x3c to the end less four.
seq:
  - id: magic
    contents: SONY1
  - id: model
    type: strz
    size: 16
    doc: The model, NUL padded (ILCE-1M2).
  - id: saved
    type: strz
    size: 32
    doc: The save time, YYYYMMDD_HHMMSS, NUL padded.
  - id: reserved_35
    size: 1
  - id: firmware
    type: firmware_version
    doc: |
      The firmware of the camera that saved the file: 04 00 from 4.00 (proved on the camera), and 02 00 and
      03 00 in ILCE-1M2 files from two other bodies, so 2.00 and 3.00. The editor's layout signature feeds
      these two bytes.
  - id: video_system
    type: u1
    enum: video_system
    doc: |
      The video system the camera was set to (NTSC/PAL Selector): the ILCE-1M2 at firmware 4.00 wrote 0 on
      NTSC and 1 on PAL, with nothing else in the header changed but the save time and the checksum
      (2026-11-06). Until then this byte was read as the firmware's last digit, which made a PAL file
      another firmware (x.01).
  - id: header_checksum
    type: u1
    doc: Low byte of the sum of byte[p] << (p mod 8) over offsets 0x00-0x38.
  - id: reserved_3a
    size: 2
  - id: sections
    type: section
    repeat: until
    repeat-until: _io.pos >= _io.size - 4
  - id: body_checksum
    type: u4
    doc: The sum of every byte from 0x3c to the end less these four.
types:
  section:
    doc: A record count, then the records.
    seq:
      - id: num_records
        type: u4
      - id: records
        type: record
        repeat: expr
        repeat-expr: num_records
  record:
    doc: One setting's storage, an array of num_elements elements of elem_size bytes each.
    seq:
      - id: id
        type: u2
        enum: sony_camset_ids_ilce_1m2_fw4_00::setting
      - id: marker
        contents: [0xcf, 0x02]
      - id: elem_size
        type: u2
      - id: num_elements
        type: u2
      - id: elements
        repeat: expr
        repeat-expr: num_elements
        type:
          switch-on: elem_size
          cases:
            1: s1
            2: s2
            4: s4
            8: s8
            _: raw_element(elem_size)
  firmware_version:
    doc: |
      Read as the major version, then the minor shown with two digits, as the editor does (04 00 is 4.00,
      02 01 would be 2.01). Every file seen has a minor of 0, so whether a minor of 1 means .01 or .10 is
      not known yet.
    seq:
      - id: major
        type: u1
      - id: minor
        type: u1
  raw_element:
    doc: An element of a size no integer has (none seen on the ILCE-1M2).
    params:
      - id: len_data
        type: u2
    seq:
      - id: data
        size: len_data
enums:
  video_system:
    0: ntsc
    1: pal
