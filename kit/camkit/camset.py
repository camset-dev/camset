"""Sony CAMSET .DAT settings files: read, compare, write back.

Where the parts of a file sit (its first bytes, the model, the save time, the firmware, the video system, the two
checksums, where the sections start, how a record is framed) is the camera's container block, the "file" of its camera
section (data/<model>_fw<fw>/camera_<model>_fw<fw>.json, copied into its definition): Block below, never this file,
which holds only the vocabulary the block's words name, as the editor's editor/src/camset.rs does
(docs/decisions/0020).
docs/formats/sony_camset.ksy describes the ILCE-1M2's container for people and for Kaitai's tools; a test ties it to
that body's block.

The vocabulary: offsets "0x3c" from the start of the file and "end-4" back from its end, a range running from its
first offset up to, not including, its second; NUL-padded ASCII text; a major.minor firmware in two bytes (major_minor:
04 00 is 4.00, 02 01 is 2.01) or, as the ILCE-1M2's block read it until 2026-11-06, three (major_minor3: 04 00 00 is
4.00); a video system byte with a name per value (optional: the ILCE-1M2's at 0x38, 0 NTSC, 1 PAL); the checksums
shift_sum (the low byte of the sum of each byte shifted left by its offset mod 8) and byte_sum (a u32 sum); one record
framing, a u32 record count per section, then records of u16 id, u16 marker, u16 element size, u16 element count and
the value bytes, little-endian; and the project's layout signature fnv1a64. A kind the kit does not know refuses the
block by name; a new one is a change to the program.

A camera's firmware is the block's firmware bytes only: the ILCE-1M2 wrote 04 00 00 set to NTSC and 04 00 01 set to
PAL with nothing else changed (2026-11-06), so files of one firmware under either system are one camera and firmware
to every check that compares them (camkit.models).

read() tries every known block (every camera file's, and every definition's: the ILCE-1M2's first, so a caller that
names none reads that body's files as before) and keeps the one a file reads with; with_values() writes both checksums
at that block's sites.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from camkit import ROOT

# Records that change on every save without any setting changing, and 0x04e2, which follows the
# camera's position (1 level, 8 held vertically either way, 2026-10-30): a file that holds 1,
# uploaded with the camera held vertically, downloads as 8.
# The ids are in each camera's data/<model>_fw<fw>/camera_<model>_fw<fw>.json (volatile_records), which the editor reads through
# its definition; 2026-11-04. They are kept per model: a diff ignores only its own body's (one body's record id can be
# another's setting, 2026-11-05). A new body's are written into its camera file before Phase 1 (the playbook's
# "New model: first day").
CAMERA_FILES = sorted((ROOT / "data").glob("*/camera_*_fw*.json"))
VOLATILE_BY_MODEL: dict[str, set] = {}
for _f in CAMERA_FILES:
    _c = json.loads(_f.read_text(encoding="utf-8"))
    VOLATILE_BY_MODEL.setdefault(_c["model"], set()).update((0, rid) for rid in _c.get("volatile_records", []))
VOLATILE = set().union(*VOLATILE_BY_MODEL.values()) if VOLATILE_BY_MODEL else set()     # every body's, for reading


def volatile(model: str) -> set:
    """The (section, record) pairs that change on every save of this body's files."""
    return VOLATILE_BY_MODEL.get(model, set())


# ---------------------------------------------------------------- the container block's vocabulary

class BlockError(ValueError):
    """A container block the kit cannot use: an unknown kind or key, an offset it cannot read, a range out of place."""


class Offset(NamedTuple):
    """A place in a file: n bytes from its start, or (from_end) n bytes back from its end."""
    n: int
    from_end: bool = False

    def at(self, length: int) -> int | None:
        if not self.from_end:
            return self.n
        return length - self.n if self.n <= length else None

    def __str__(self):
        return f"end-{self.n}" if self.from_end else f"0x{self.n:02x}"


def offset(t) -> Offset:
    """"0x" and lower-case hex digits, or "end-" and a decimal count of bytes; nothing else."""
    m = re.fullmatch(r"0x([0-9a-f]{1,8})|end-([0-9]{1,9})", t) if isinstance(t, str) else None
    if not m:
        raise BlockError(f"{t!r} is not an offset: write \"0x\" and lower-case hex digits (\"0x3c\"), or \"end-\" "
                         f"and a number of bytes (\"end-4\")")
    return Offset(int(m.group(1), 16)) if m.group(1) is not None else Offset(int(m.group(2)), True)


CHECKSUM_WIDTH = {"shift_sum": 1, "byte_sum": 4}


class Checksum(NamedTuple):
    kind: str
    over: tuple            # (Offset, Offset): the bytes it sums
    at: Offset             # where it is stored

    @property
    def width(self) -> int:
        return CHECKSUM_WIDTH[self.kind]

    def compute(self, b: bytes, start: int) -> int:
        """The checksum of b, which starts at offset `start` of the file."""
        if self.kind == "shift_sum":
            return sum(x << ((start + i) & 7) for i, x in enumerate(b)) & 0xFF
        return sum(b) & 0xFFFFFFFF

    def sites(self, length: int) -> tuple | None:
        """(from, to, site) in a file of `length` bytes; None when they do not fit."""
        a, b, s = self.over[0].at(length), self.over[1].at(length), self.at.at(length)
        if None in (a, b, s):
            return None
        w = self.width
        ok = a <= b <= length and s + w <= length and (s >= b or s + w <= a)
        return (a, b, s) if ok else None

    def stored(self, d: bytes) -> int | None:
        got = self.sites(len(d))
        return None if got is None else int.from_bytes(d[got[2]:got[2] + self.width], "little")

    def holds(self, d: bytes) -> bool:
        got = self.sites(len(d))
        return got is not None and self.stored(d) == self.compute(d[got[0]:got[1]], got[0])

    def written(self, d: bytearray) -> None:
        """Work the checksum out again and store it at its site."""
        got = self.sites(len(d))
        if got is not None:
            d[got[2]:got[2] + self.width] = self.compute(d[got[0]:got[1]], got[0]).to_bytes(self.width, "little")


# every key the block may hold, and the kinds each word may name: anything else refuses it, by name
BLOCK_KEYS = {"magic", "model", "saved", "firmware", "header_checksum", "sections_start", "records",
              "trailer_checksum", "signature"}
BLOCK_OPTIONAL = {"video_system"}          # keys a block may leave out: without them it reads as before
FIRMWARE_WIDTH = {"major_minor": 2, "major_minor3": 3}
KINDS = {"text": {"ascii_nul"}, "decode": set(FIRMWARE_WIDTH), "kind": set(CHECKSUM_WIDTH), "count": {"u32"},
         "framing": {"id_marker_size_count"}, "endian": {"le"}, "signature": {"fnv1a64"}}


def _keys(d, want: set, name: str, optional: set = frozenset()) -> dict:
    if not isinstance(d, dict):
        raise BlockError(f"{name} is not an object")
    extra, missing = set(d) - want - optional, want - set(d)
    if extra:
        raise BlockError(f"{name} has {', '.join(sorted(extra))}, which the kit does not know")
    if missing:
        raise BlockError(f"{name} lacks {', '.join(sorted(missing))}")
    return d


def _kind(word: str, value, name: str) -> str:
    if value not in KINDS[word]:
        raise BlockError(f"{name}: {value!r} is not a {word} the kit knows ({', '.join(sorted(KINDS[word]))})")
    return value


@dataclass(frozen=True)
class Block:
    """A camera's container block, as its camera file's "file" holds it (docs/decisions/0020)."""
    magic_at: Offset
    magic: bytes
    model: tuple             # (Offset, Offset)
    saved: tuple
    firmware: tuple
    decode: str
    video_system: tuple      # (Offset, ((value, name), ...)), or None when the block does not say where it is
    header_checksum: Checksum
    sections_start: Offset
    marker: int
    trailer_checksum: Checksum
    signature: str
    source: dict = field(default=None, compare=False, hash=False, repr=False)       # the block as written

    @classmethod
    def parse(cls, d: dict) -> "Block":
        """The block read and checked, or BlockError naming what is wrong."""
        d = _keys(d, BLOCK_KEYS, "file", BLOCK_OPTIONAL)
        mg = _keys(d["magic"], {"at", "bytes"}, "magic")
        if not isinstance(mg["bytes"], str) or not mg["bytes"]:
            raise BlockError("magic.bytes is empty")
        if not mg["bytes"].isascii():
            raise BlockError(f"magic.bytes {mg['bytes']!r} is not ASCII text")

        def text(name):
            f = _keys(d[name], {"at", "to", "text"}, name)
            _kind("text", f["text"], name)
            return offset(f["at"]), offset(f["to"])

        fw = _keys(d["firmware"], {"at", "to", "decode"}, "firmware")

        def video():
            if "video_system" not in d:
                return None
            v = _keys(d["video_system"], {"at", "names"}, "video_system")
            names = v["names"]
            if not isinstance(names, dict) or not names:
                raise BlockError("video_system.names names no value")
            pairs = []
            for k, name in names.items():
                if not re.fullmatch(r"0|[1-9][0-9]{0,2}", str(k)) or int(k) > 255:
                    raise BlockError(f"video_system.names: {k!r} is not a byte value: write it in decimal, 0 to 255 "
                                     f"(\"1\")")
                if not isinstance(name, str) or not name.strip():
                    raise BlockError(f"video_system.names gives {k} no name")
                pairs.append((int(k), name))
            return offset(v["at"]), tuple(sorted(pairs))

        def checksum(name):
            c = _keys(d[name], {"kind", "over", "at"}, name)
            if not isinstance(c["over"], list) or len(c["over"]) != 2:
                raise BlockError(f"{name}.over is two offsets")
            return Checksum(_kind("kind", c["kind"], name), (offset(c["over"][0]), offset(c["over"][1])),
                            offset(c["at"]))

        rec = _keys(d["records"], {"count", "framing", "marker", "endian"}, "records")
        for w in ("count", "framing", "endian"):
            _kind(w, rec[w], f"records.{w}")
        if not re.fullmatch(r"0x[0-9a-f]{1,4}", str(rec["marker"])):
            raise BlockError(f"records.marker {rec['marker']!r} is not a 16-bit hex value (\"0x02cf\")")
        b = cls(magic_at=offset(mg["at"]), magic=mg["bytes"].encode("ascii"), model=text("model"),
                saved=text("saved"), firmware=(offset(fw["at"]), offset(fw["to"])),
                decode=_kind("decode", fw["decode"], "firmware"), video_system=video(),
                header_checksum=checksum("header_checksum"),
                sections_start=offset(d["sections_start"]), marker=int(rec["marker"], 16),
                trailer_checksum=checksum("trailer_checksum"), signature=_kind("signature", d["signature"], "signature"),
                source=d)
        b.check()
        return b

    def check(self) -> None:
        """What the typed reading does not check, as the editor's FileFormat::check: every range but the trailer's in
        the header (before sections_start) and running forward, the firmware as long as its decode reads, the video
        system's byte in the header apart from the firmware and the header checksum's site, each checksum's site outside
        the bytes it sums, the trailer's site counted from the end of the file."""
        if self.sections_start.from_end:
            raise BlockError("sections_start counts from the start of the file (\"0x3c\")")
        start = self.sections_start.n

        def head(name, at, to):
            if at.from_end or to.from_end:
                raise BlockError(f"{name} is in the header: its offsets count from the start of the file (\"0x05\")")
            if to.n <= at.n:
                raise BlockError(f"{name} runs from {at} up to {to}: its end must come after its start")
            if to.n > start:
                raise BlockError(f"{name} runs up to {to}, past sections_start {self.sections_start}")
            return at.n, to.n

        head("magic", self.magic_at, Offset(self.magic_at.n + len(self.magic)))
        head("model", *self.model)
        head("saved", *self.saved)
        fa, fb = head("firmware", *self.firmware)
        want = FIRMWARE_WIDTH[self.decode]
        if fb - fa != want:
            raise BlockError(f"firmware decode {self.decode} reads {'two' if want == 2 else 'three'} bytes, but "
                             f"{self.firmware[0]} to {self.firmware[1]} holds {fb - fa}")
        h = self.header_checksum
        if self.video_system is not None:
            at = self.video_system[0]
            if at.from_end:
                raise BlockError("video_system is in the header: its offset counts from the start of the file "
                                 "(\"0x38\")")
            head("video_system", at, Offset(at.n + 1))
            if fa <= at.n < fb:
                raise BlockError(f"video_system at {at} lies inside the firmware ({self.firmware[0]} to "
                                 f"{self.firmware[1]})")
            if not h.at.from_end and h.at.n <= at.n < h.at.n + h.width:
                raise BlockError(f"video_system at {at} is the header checksum's site")
        a, b = head("header_checksum.over", *h.over)
        if h.at.from_end:
            raise BlockError("the header checksum is in the header: its offset counts from the start of the file")
        if h.at.n + h.width > start:
            raise BlockError(f"the header checksum at {h.at} runs past sections_start {self.sections_start}")
        if h.at.n < b and h.at.n + h.width > a:
            raise BlockError(f"the header checksum at {h.at} lies inside the bytes it sums ({h.over[0]} to {h.over[1]})")
        t = self.trailer_checksum
        if not t.at.from_end:
            raise BlockError("the trailer checksum's site counts back from the end of the file (\"end-4\")")
        if t.at.n < t.width:
            raise BlockError(f"the trailer checksum at {t.at} has no room for its {t.width} byte(s)")
        if t.over[1].from_end and t.over[1].n < t.at.n:
            raise BlockError(f"the trailer checksum at {t.at} lies inside the bytes it sums ({t.over[0]} to {t.over[1]})")

    def magic_matches(self, d: bytes) -> bool:
        return d[self.magic_at.n:self.magic_at.n + len(self.magic)] == self.magic

    def text(self, d: bytes, which: str) -> str:
        """A NUL-padded text field ("model", "saved"), as far as its first NUL."""
        a, b = getattr(self, which)
        return d[a.n:b.n].split(b"\0", 1)[0].decode("ascii", "replace")

    def firmware_bytes(self, d: bytes) -> bytes:
        return d[self.firmware[0].n:self.firmware[1].n]

    def firmware_text(self, d: bytes) -> str:
        """The firmware that saved the file, as the block decodes it ("4.00": 04 00 under major_minor, 04 00 00 under
        major_minor3)."""
        v = self.firmware_bytes(d)
        if len(v) != FIRMWARE_WIDTH[self.decode]:
            return ""
        return f"{v[0]}.{v[1]:02d}" if self.decode == "major_minor" else f"{v[0]}.{v[1] * 10 + v[2]:02d}"

    def video_system_of(self, d: bytes) -> tuple | None:
        """(the byte, the name the block gives it, or None when it gives that value none) of the video system the
        camera was set to when it saved the file; None when the block does not say where it is."""
        if self.video_system is None or len(d) <= self.video_system[0].n:
            return None
        v = d[self.video_system[0].n]
        return v, dict(self.video_system[1]).get(v)

    def video_system_text(self, d: bytes) -> str:
        """The video system in words ("PAL"; "video system 7, which the block names nothing for"), "" when the block
        does not say where it is."""
        got = self.video_system_of(d)
        if got is None:
            return ""
        return got[1] if got[1] is not None else f"video system {got[0]}, which the block names nothing for"

    def header_length(self) -> int:
        return self.sections_start.n

    def trailer_site(self, length: int) -> int | None:
        return self.trailer_checksum.at.at(length)

    def checksums_ok(self, d: bytes) -> bool:
        return self.header_checksum.holds(d) and self.trailer_checksum.holds(d)

    def sealed(self, d) -> bytes:
        """d with both checksums worked out again at the block's sites."""
        out = bytearray(d)
        self.header_checksum.written(out)
        self.trailer_checksum.written(out)
        return bytes(out)

    def with_text(self, d, which: str, text) -> bytes:
        """d with a text field ("model", "saved") replaced, NUL padded (the checksums are not worked out again)."""
        a, b = getattr(self, which)
        raw = text.encode("ascii") if isinstance(text, str) else bytes(text)
        if len(raw) > b.n - a.n:
            raise ValueError(f"{which}: {len(raw)} bytes do not fit {b.n - a.n}")
        out = bytearray(d)
        out[a.n:b.n] = raw.ljust(b.n - a.n, b"\0")
        return bytes(out)

    def frame(self, d: bytes) -> list:
        """The sections between sections_start and the trailer checksum's site, framed as the one framing says:
        [[(record id, element size, element count, offset of its header), ...] per section], in file order;
        ValueError when they do not frame."""
        start, end = self.sections_start.n, self.trailer_site(len(d))
        if end is None or end < start or len(d) < start:
            raise ValueError("shorter than its header and trailer")
        off, out = start, []
        while off < end:
            if end - off < 4:
                raise ValueError(f"{end - off} stray bytes before the checksum")
            n = int.from_bytes(d[off:off + 4], "little")
            off += 4
            recs = []
            for _ in range(n):
                if off + 8 > end:
                    raise ValueError(f"the file ends early at 0x{off:x}")
                rid, marker, size, count = (int.from_bytes(d[off + i:off + i + 2], "little") for i in (0, 2, 4, 6))
                if marker != self.marker:
                    raise ValueError(f"unexpected record marker 0x{marker:04x} at 0x{off + 2:x}")
                if off + 8 + size * count > end:
                    raise ValueError(f"the record at 0x{off:x} runs past the checksum")
                recs.append((rid, size, count, off))
                off += 8 + size * count
            out.append(recs)
        if off != end:
            raise ValueError(f"{end - off} stray bytes before the checksum")
        return out

    def describes(self, d: bytes) -> bool:
        """The file starts with the block's magic and its records frame as the block says."""
        if not self.magic_matches(d):
            return False
        try:
            self.frame(d)
        except ValueError:
            return False
        return True

    def as_json(self) -> dict:
        return self.source


def camera_blocks() -> list:
    """[(Block, [the camera keys that use it])] of every camera file and definition that holds a block, each block once:
    the ILCE-1M2's first (the body the kit was built on), then by key. A block that does not parse is left out here
    (identify.py and the tests name it)."""
    from camkit import paths
    found = {}
    sources = [(f.parent.name, json.loads(f.read_text(encoding="utf-8"))) for f in CAMERA_FILES]
    for p in sorted((ROOT / "editor" / "definitions").glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        sources.append((p.stem, doc.get("camera") or {}))
    for key, cam in sources:
        try:
            b = Block.parse(cam.get("file"))
        except (BlockError, TypeError):
            continue
        found.setdefault(b, [])
        if key not in found[b]:
            found[b].append(key)
    return sorted(found.items(), key=lambda kv: (paths.A1II not in kv[1], sorted(kv[1])))


_BLOCKS = None


def blocks() -> list:
    """The known blocks, read once."""
    global _BLOCKS
    if _BLOCKS is None:
        _BLOCKS = [b for b, _ in camera_blocks()]
    return _BLOCKS


def block_of(camera: str) -> Block:
    """The block of a camera's key, from its camera file (else its definition)."""
    for b, keys in camera_blocks():
        if camera in keys:
            return b
    raise ValueError(f"no camera file or definition of {camera} holds a container block (\"file\")")


def pick(d: bytes, check: bool = True) -> Block:
    """The known block a file reads with: the first that describes it under which both checksums hold, else (check
    False) the first that describes it."""
    fits = [b for b in blocks() if b.describes(d)]
    for b in fits:
        if b.checksums_ok(d):
            return b
    if fits and not check:
        return fits[0]
    if fits:
        raise ValueError("checksum mismatch")
    if not blocks():
        raise ValueError("no camera file in data/ holds a container block, so no file can be read")
    raise ValueError("not a settings file any known container block describes")


def peek(d: bytes) -> tuple:
    """(model, firmware) a file's header names, through the first known block whose magic matches it, without
    framing its records; ValueError when none does. The video system is not part of it: files of one firmware saved
    under NTSC and under PAL are one camera and firmware (peek_video_system says which)."""
    for b in blocks():
        if len(d) >= b.header_length() and b.magic_matches(d):
            return b.text(d, "model"), b.firmware_text(d)
    raise ValueError("not a settings file any known container block describes")


def peek_video_system(d: bytes) -> str:
    """The video system a file's header names, in words, through the block peek() reads it with; "" when that block
    does not say where it is. ValueError when no known block's magic matches."""
    for b in blocks():
        if len(d) >= b.header_length() and b.magic_matches(d):
            return b.video_system_text(d)
    raise ValueError("not a settings file any known container block describes")


# ---------------------------------------------------------------- a file

@dataclass
class Record:
    id: int
    size: int
    count: int
    raw: bytes
    offset: int

    def values(self) -> list[int]:
        s = self.size
        if s not in (1, 2, 4, 8):
            return list(self.raw)
        return [int.from_bytes(self.raw[i:i + s], "little", signed=True) for i in range(0, len(self.raw), s)]

    def value(self):
        """A scalar for one-element records, else the element list."""
        v = self.values()
        return v[0] if self.count == 1 and len(v) == 1 else v


@dataclass
class Camset:
    model: str
    saved: str
    sections: list[dict[int, Record]] = field(default_factory=list)
    data: bytes = b""
    block: Block = None
    firmware: str = ""
    video_system: str = ""          # in words, as Block.video_system_text gives it; "" when the block does not say
    # (section, record id) framed more than once in its section, in file order: sections keeps the last of each, so a
    # comparison sees only that one (parse; duplicates_note says it in one line). No camera download has shown one yet
    duplicates: list[tuple[int, int]] = field(default_factory=list)

    def get(self, section: int, rid: int) -> Record | None:
        return self.sections[section].get(rid)

    @property
    def checksums_ok(self) -> bool:
        return self.block.checksums_ok(self.data)

    @property
    def header_ok(self) -> bool:
        return self.block.header_checksum.holds(self.data)

    @property
    def trailer_ok(self) -> bool:
        """The checksum over the records: when it fails, the records themselves cannot be trusted."""
        return self.block.trailer_checksum.holds(self.data)

    def signature(self) -> str:
        """The record layout's fingerprint, the block's signature (fnv1a64): FNV-1a 64 over the model, the first two
        firmware bytes, and each section's record count and each record's id and shape. The editor's
        CamSet::layout_signature computes the same."""
        h = 0xCBF29CE484222325

        def feed(bs):
            nonlocal h
            for x in bs:
                h ^= x
                h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        feed(self.model.encode("ascii", "replace"))
        feed(self.block.firmware_bytes(self.data)[:2])
        for sec in self.block.frame(self.data):           # every record as framed, a repeated id too
            feed(len(sec).to_bytes(4, "little"))
            for rid, size, count, _ in sec:
                feed(rid.to_bytes(2, "little") + size.to_bytes(2, "little") + count.to_bytes(2, "little"))
        return f"{h:016x}"


def parse(d: bytes, *, check: bool = True, block: Block = None, name="the file") -> Camset:
    """A file's bytes read with a block (by default the known one that describes it: pick())."""
    try:
        b = block or pick(d, check)
    except ValueError as e:
        raise ValueError(f"{name}: {e}") from None
    if not b.magic_matches(d):
        raise ValueError(f"{name}: does not start with {b.magic.decode('ascii', 'replace')!r}, as its block says")
    try:
        framed = b.frame(d)
    except ValueError as e:
        raise ValueError(f"{name}: not a settings file its block describes ({e})") from None
    cs = Camset(model=b.text(d, "model"), saved=b.text(d, "saved"), data=d, block=b, firmware=b.firmware_text(d),
                video_system=b.video_system_text(d))
    for s, recs in enumerate(framed):
        cs.sections.append({rid: Record(rid, size, count, d[off + 8:off + 8 + size * count], off)
                            for rid, size, count, off in recs})
        if check and len(cs.sections[-1]) != len(recs):      # the kit's read: an id framed twice is noted, never refused
            seen = set()
            for rid, *_ in recs:
                if rid in seen:
                    cs.duplicates.append((s, rid))
                seen.add(rid)
    if check and not cs.checksums_ok:
        raise ValueError(f"{name}: checksum mismatch")
    return cs


def duplicates_note(files: dict) -> str:
    """One warning line naming the record ids a file frames twice in one section ({name: Camset}, Camset.duplicates),
    or "" when no file does: the kit compares the last of each, so a change in an earlier copy goes unseen."""
    said = []
    for name, cs in files.items():
        keys = [Change(s, rid, None, None).key for s, rid in dict.fromkeys(cs.duplicates)]
        if keys:
            said.append(f"{name} ({', '.join(keys[:6])}{f' and {len(keys) - 6} more' if len(keys) > 6 else ''})")
    if not said:
        return ""
    return (f"warning: a record id appears twice in one section of {'; '.join(said)}: the comparison reads the last "
            f"copy only, so a change in the first goes unseen. A camera's file has not done this before: keep the "
            f"file and say so in the report.")


def read(path: str | Path, *, check: bool = True, block: Block = None) -> Camset:
    return parse(Path(path).read_bytes(), check=check, block=block, name=str(path))


@dataclass
class Change:
    section: int
    id: int
    before: object
    after: object

    @property
    def key(self) -> str:
        return f"{'global' if self.section == 0 else f'set{self.section}'}:0x{self.id:04x}"


def diff(a: Camset, b: Camset, sections=None, include_volatile=False) -> list[Change]:
    """Records whose bytes differ, in file order. Both files must be one body's, with one layout: two bodies' files,
    or two section counts, are refused rather than compared in part.

    The checksums, as the editor's rules have them (editor/src/camset.rs): a file whose records' (trailer) checksum
    fails is refused, since its records cannot be trusted, as the editor will not open it; one whose header checksum
    alone fails is compared, as the editor opens it and flags the header (it refuses to write such a file, which the
    kit never does). read() with check=True, the default, refuses either failure, since the kit reads only what the
    camera wrote; a file read with check=False reaches here, and this is where the two rules meet."""
    if a.model != b.model:
        raise ValueError(f"a {a.model} file and a {b.model} file: settings files of two bodies are not compared")
    if len(a.sections) != len(b.sections):
        raise ValueError(f"{len(a.sections)} sections against {len(b.sections)}: the layouts differ")
    for which, cs in (("first", a), ("second", b)):
        if cs.block is not None and cs.data and not cs.trailer_ok:
            raise ValueError(f"the {which} file's records checksum does not hold: its records cannot be trusted, so "
                             f"the files are not compared")
    noisy = volatile(a.model)
    out = []
    for s, (ra, rb) in enumerate(zip(a.sections, b.sections, strict=True)):
        if sections is not None and s not in sections:
            continue
        if ra.keys() != rb.keys():
            raise ValueError(f"section {s}: record layouts differ")
        for rid, x in ra.items():
            y = rb[rid]
            if x.raw != y.raw and (include_volatile or (s, rid) not in noisy):
                out.append(Change(s, rid, x.value(), y.value()))
    return out


def with_values(cs: Camset, changes: dict[tuple[int, int], bytes]) -> bytes:
    """A copy of the file with records replaced (same length) and both checksums recomputed at its block's sites."""
    d = bytearray(cs.data)
    for (s, rid), raw in changes.items():
        r = cs.sections[s][rid]
        if len(raw) != len(r.raw):
            raise ValueError(f"section {s} 0x{rid:04x}: {len(raw)} bytes given, record holds {len(r.raw)}")
        d[r.offset + 8: r.offset + 8 + len(raw)] = raw
    return cs.block.sealed(d)
