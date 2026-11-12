"""The reader kaitai-struct-compiler generates from docs/formats/sony_camset.ksy and the record names it imports
(sony_camset_ids_ILCE-1M2_fw4.00.ksy, here sony_camset_ids_ilce_1m2_fw4_00.py), written by kit/tools/build_docs.py;
do not edit. SOURCES.json holds the SHA-256 of what each .ksy it was compiled from gave it (build_docs.reader_part:
no comments, no record docs), which build_docs.py --check compares with no compiler. The kit reads files through the
camera's container block (camkit.camset); this reader is read beside it by a test, which ties the .ksy to the
ILCE-1M2's block (docs/decisions/0020)."""
