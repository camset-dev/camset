# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import KaitaiStruct, KaitaiStream, BytesIO
from camkit.formats import sony_camset_ids_ilce_1m2_fw4_00
from enum import IntEnum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class SonyCamset(KaitaiStruct):
    """A Sony camera's settings as Save/Load Settings writes them to the card (PRIVATE/SONY/CAMSET), and as the
    Camera Remote SDK downloads them. Section 0 holds the live settings; sections 1 on hold the memory sets
    (on the ILCE-1M2: Stills, Movie, S&Q and Time-lapse memories 1-3 each), every set the same layout.
    Values are little-endian signed integers of the record's element size. Read and verified on the
    ILCE-1M2 (a1 II), firmware 4.00, layout 07a5b07a502c68f0; the record names are that body's.
    The two checksums are sums a writer recomputes: header_checksum over 0x00-0x38, body_checksum over
    0x3c to the end less four.
    """

    class VideoSystem(IntEnum):
        ntsc = 0
        pal = 1
    def __init__(self, _io, _parent=None, _root=None):
        super(SonyCamset, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self
        self._read()

    def _read(self):
        self.magic = self._io.read_bytes(5)
        if not self.magic == b"\x53\x4F\x4E\x59\x31":
            raise kaitaistruct.ValidationNotEqualError(b"\x53\x4F\x4E\x59\x31", self.magic, self._io, u"/seq/0")
        self.model = (KaitaiStream.bytes_terminate(self._io.read_bytes(16), 0, False)).decode(u"ASCII")
        self.saved = (KaitaiStream.bytes_terminate(self._io.read_bytes(32), 0, False)).decode(u"ASCII")
        self.reserved_35 = self._io.read_bytes(1)
        self.firmware = SonyCamset.FirmwareVersion(self._io, self, self._root)
        self.video_system = KaitaiStream.resolve_enum(SonyCamset.VideoSystem, self._io.read_u1())
        self.header_checksum = self._io.read_u1()
        self.reserved_3a = self._io.read_bytes(2)
        self.sections = []
        i = 0
        while True:
            _ = SonyCamset.Section(self._io, self, self._root)
            self.sections.append(_)
            if self._io.pos() >= self._io.size() - 4:
                break
            i += 1
        self.body_checksum = self._io.read_u4le()


    def _fetch_instances(self):
        pass
        self.firmware._fetch_instances()
        for i in range(len(self.sections)):
            pass
            self.sections[i]._fetch_instances()


    class FirmwareVersion(KaitaiStruct):
        """Read as the major version, then the minor shown with two digits, as the editor does (04 00 is 4.00,
        02 01 would be 2.01). Every file seen has a minor of 0, so whether a minor of 1 means .01 or .10 is
        not known yet.
        """
        def __init__(self, _io, _parent=None, _root=None):
            super(SonyCamset.FirmwareVersion, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.major = self._io.read_u1()
            self.minor = self._io.read_u1()


        def _fetch_instances(self):
            pass


    class RawElement(KaitaiStruct):
        """An element of a size no integer has (none seen on the ILCE-1M2)."""
        def __init__(self, len_data, _io, _parent=None, _root=None):
            super(SonyCamset.RawElement, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.len_data = len_data
            self._read()

        def _read(self):
            self.data = self._io.read_bytes(self.len_data)


        def _fetch_instances(self):
            pass


    class Record(KaitaiStruct):
        """One setting's storage, an array of num_elements elements of elem_size bytes each."""
        def __init__(self, _io, _parent=None, _root=None):
            super(SonyCamset.Record, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.id = KaitaiStream.resolve_enum(sony_camset_ids_ilce_1m2_fw4_00.SonyCamsetIdsIlce1m2Fw400.Setting, self._io.read_u2le())
            self.marker = self._io.read_bytes(2)
            if not self.marker == b"\xCF\x02":
                raise kaitaistruct.ValidationNotEqualError(b"\xCF\x02", self.marker, self._io, u"/types/record/seq/1")
            self.elem_size = self._io.read_u2le()
            self.num_elements = self._io.read_u2le()
            self.elements = []
            for i in range(self.num_elements):
                _on = self.elem_size
                if _on == 1:
                    pass
                    self.elements.append(self._io.read_s1())
                elif _on == 2:
                    pass
                    self.elements.append(self._io.read_s2le())
                elif _on == 4:
                    pass
                    self.elements.append(self._io.read_s4le())
                elif _on == 8:
                    pass
                    self.elements.append(self._io.read_s8le())
                else:
                    pass
                    self.elements.append(SonyCamset.RawElement(self.elem_size, self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.elements)):
                pass
                _on = self.elem_size
                if _on == 1:
                    pass
                elif _on == 2:
                    pass
                elif _on == 4:
                    pass
                elif _on == 8:
                    pass
                else:
                    pass
                    self.elements[i]._fetch_instances()



    class Section(KaitaiStruct):
        """A record count, then the records."""
        def __init__(self, _io, _parent=None, _root=None):
            super(SonyCamset.Section, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self._read()

        def _read(self):
            self.num_records = self._io.read_u4le()
            self.records = []
            for i in range(self.num_records):
                self.records.append(SonyCamset.Record(self._io, self, self._root))



        def _fetch_instances(self):
            pass
            for i in range(len(self.records)):
                pass
                self.records[i]._fetch_instances()




