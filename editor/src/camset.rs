//! Camera settings file (CAMSET*.DAT) reader and writer.
//!
//! Where the parts of a file sit (its first bytes, the model, the save time, the firmware, the video system, the two
//! checksums, where the sections start, how a record is framed) is the camera definition's `camera.file` block,
//! `FileFormat`, never this file: it holds only the vocabulary the block's words name (docs/decisions/0020). The
//! ILCE-1M2's block, as an example: "SONY1" at 0x00, the model at 0x05-0x15 and the save time at 0x15-0x35 as
//! NUL-padded text, the firmware at 0x36-0x38 as major.minor (04 00 = 4.00), the video system at 0x38 (0 NTSC,
//! 1 PAL), a shift_sum header checksum of 0x00-0x39 at 0x39, the sections from 0x3c, each a u32 record count then
//! records of u16 id, u16 marker 0x02cf, u16 element size, u16 element count and the value bytes, little-endian, and a
//! byte_sum of 0x3c up to the last four bytes, which hold it.

use serde::Deserialize;
use std::fmt;
use std::sync::Arc;

/// Setting index flag: a 16-bit field at a byte offset inside a record (see Record::get). The project's own
/// encoding, not the camera's.
pub const FIELD: u16 = 0x8000;

/// A place in a settings file, as the docs write it: "0x3c" counts from the start of the file, "end-4" back from
/// its end. A range runs from its first offset up to, not including, its second.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Offset {
    Start(usize),
    End(usize),
}

impl Offset {
    /// "0x" and lower-case hex digits, or "end-" and a decimal count of bytes; nothing else.
    pub fn parse(t: &str) -> Result<Offset, String> {
        let hex = |h: &str| !h.is_empty() && h.len() <= 8 && h.chars().all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c));
        let dec = |n: &str| !n.is_empty() && n.len() <= 9 && n.chars().all(|c| c.is_ascii_digit());
        match (t.strip_prefix("0x"), t.strip_prefix("end-")) {
            (Some(h), _) if hex(h) => Ok(Offset::Start(usize::from_str_radix(h, 16).unwrap_or(0))),
            (_, Some(n)) if dec(n) => Ok(Offset::End(n.parse().unwrap_or(0))),
            _ => Err(format!("{t:?} is not an offset: write \"0x\" and lower-case hex digits (\"0x3c\"), or \"end-\" and a number of bytes (\"end-4\")")),
        }
    }

    /// Where it falls in a file of `len` bytes.
    pub fn at(self, len: usize) -> Option<usize> {
        match self {
            Offset::Start(o) => Some(o),
            Offset::End(n) => len.checked_sub(n),
        }
    }

    fn at_start(self) -> Option<usize> {
        match self {
            Offset::Start(o) => Some(o),
            Offset::End(_) => None,
        }
    }
}

impl fmt::Display for Offset {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Offset::Start(o) => write!(f, "0x{o:02x}"),
            Offset::End(n) => write!(f, "end-{n}"),
        }
    }
}

impl<'de> Deserialize<'de> for Offset {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        Offset::parse(&String::deserialize(d)?).map_err(serde::de::Error::custom)
    }
}

/// A 16-bit value written as hex ("0x02cf").
fn hex16<'de, D: serde::Deserializer<'de>>(d: D) -> Result<u16, D::Error> {
    let t = String::deserialize(d)?;
    match t.strip_prefix("0x").filter(|h| !h.is_empty() && h.len() <= 4 && h.chars().all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))) {
        Some(h) => u16::from_str_radix(h, 16).map_err(serde::de::Error::custom),
        None => Err(serde::de::Error::custom(format!("{t:?} is not a 16-bit hex value: write \"0x\" and up to four lower-case hex digits (\"0x1234\")"))),
    }
}

/// The container a camera writes its settings in, as its definition's `camera.file` describes it. Every kind is
/// one the program knows by name; an unknown kind, or an unknown key, refuses the definition as it loads.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FileFormat {
    /// The bytes every such file starts with, and where.
    pub magic: Magic,
    /// The model the file names, and when it was saved, as text.
    pub model: TextField,
    pub saved: TextField,
    /// The firmware that saved the file.
    pub firmware: FirmwareField,
    /// The video system the camera was set to when it saved the file, when the block says where it is: a file is
    /// written only to a camera set to the same one (`write_check` in the editor's camera/job.rs).
    #[serde(default)]
    pub video_system: Option<VideoSystemField>,
    pub header_checksum: Checksum,
    /// Where the first section's record count is.
    pub sections_start: Offset,
    pub records: Records,
    /// The checksum after the records; the records run up to its site.
    pub trailer_checksum: Checksum,
    /// The layout signature's algorithm.
    pub signature: SignatureKind,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Magic {
    pub at: Offset,
    pub bytes: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TextField {
    pub at: Offset,
    pub to: Offset,
    pub text: TextKind,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TextKind {
    /// ASCII text, padded with NUL bytes.
    AsciiNul,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FirmwareField {
    pub at: Offset,
    pub to: Offset,
    pub decode: FirmwareKind,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FirmwareKind {
    /// Two bytes: the major version, then the minor, shown with two digits (04 00 = 4.00, 02 01 = 2.01).
    MajorMinor,
    /// Three bytes: the major version, then the minor's two digits (04 00 00 = 4.00, 03 00 01 = 3.01). The
    /// ILCE-1M2's block named it until its third byte proved to be the video system (2026-11-06); kept for a block
    /// that names it.
    MajorMinor3,
}

impl FirmwareKind {
    /// How many bytes it reads.
    pub fn width(self) -> usize {
        match self {
            FirmwareKind::MajorMinor => 2,
            FirmwareKind::MajorMinor3 => 3,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            FirmwareKind::MajorMinor => "major_minor",
            FirmwareKind::MajorMinor3 => "major_minor3",
        }
    }
}

/// Where the header holds the video system the camera was set to (one byte), and what each value is called, by the
/// value in decimal ("0": "NTSC"), as the camera's menu says it.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VideoSystemField {
    pub at: Offset,
    pub names: std::collections::BTreeMap<String, String>,
}

impl VideoSystemField {
    /// The name the block gives a value of the byte; None when it gives none.
    pub fn name_of(&self, v: u8) -> Option<&str> {
        self.names.get(&v.to_string()).map(String::as_str)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Checksum {
    pub kind: ChecksumKind,
    /// The bytes it sums, from the first offset up to the second.
    pub over: [Offset; 2],
    /// Where it is stored.
    pub at: Offset,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ChecksumKind {
    /// One byte: the low byte of the sum of each byte shifted left by its offset mod 8.
    ShiftSum,
    /// A u32: the sum of the bytes.
    ByteSum,
}

impl ChecksumKind {
    /// How many bytes it is stored in.
    pub fn width(self) -> usize {
        match self {
            ChecksumKind::ShiftSum => 1,
            ChecksumKind::ByteSum => 4,
        }
    }

    /// The checksum of `bytes`, which start at offset `from` of the file.
    pub fn compute(self, bytes: &[u8], from: usize) -> u32 {
        match self {
            ChecksumKind::ShiftSum => bytes.iter().enumerate().fold(0u32, |acc, (i, &b)| acc.wrapping_add((b as u32) << ((from + i) & 7))) & 0xff,
            ChecksumKind::ByteSum => bytes.iter().fold(0u32, |a, &b| a.wrapping_add(b as u32)),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            ChecksumKind::ShiftSum => "shift_sum",
            ChecksumKind::ByteSum => "byte_sum",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Records {
    /// How each section says how many records it holds.
    pub count: CountKind,
    pub framing: FramingKind,
    /// The value every record header carries after its id.
    #[serde(deserialize_with = "hex16")]
    pub marker: u16,
    pub endian: Endian,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CountKind {
    U32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FramingKind {
    /// u16 id, u16 marker, u16 element size, u16 element count, then the value bytes. Section 0 is the live
    /// settings, the others the memory sets.
    IdMarkerSizeCount,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Endian {
    Le,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SignatureKind {
    /// The project's own layout signature: FNV-1a 64 over the model, the first two firmware bytes, and each
    /// section's record count and each record's id and shape.
    Fnv1a64,
}

/// NUL-padded text, as far as the first NUL.
fn text_of(b: &[u8]) -> String {
    let end = b.iter().position(|&c| c == 0).unwrap_or(b.len());
    String::from_utf8_lossy(&b[..end]).into_owned()
}

impl FileFormat {
    /// What the typed reading does not check: every range but the trailer's in the header (before
    /// `sections_start`) and running forward, the firmware as long as its decode reads, the video system's byte in the
    /// header apart from the firmware and the header checksum's site, with a name for at least one value and every
    /// value a byte, each checksum's site outside the bytes it sums, the trailer's site counted from the end of the
    /// file.
    pub fn check(&self) -> Result<(), String> {
        let start = self.sections_start.at_start().ok_or("sections_start counts from the start of the file (\"0x3c\")")?;
        let head = |name: &str, at: Offset, to: Offset| -> Result<(usize, usize), String> {
            let (Some(a), Some(b)) = (at.at_start(), to.at_start()) else {
                return Err(format!("{name} is in the header: its offsets count from the start of the file (\"0x05\")"));
            };
            if b <= a {
                return Err(format!("{name} runs from {at} up to {to}: its end must come after its start"));
            }
            if b > start {
                return Err(format!("{name} runs up to {to}, past sections_start {}", self.sections_start));
            }
            Ok((a, b))
        };
        if self.magic.bytes.is_empty() {
            return Err("magic.bytes is empty".into());
        }
        // an offset and a width added, checked: an offset of eight hex digits does not fit a 32-bit usize with room
        let past = |name: &str, at: usize, n: usize| at.checked_add(n).ok_or_else(|| format!("{name}'s offset is too large"));
        let m = self.magic.at.at_start().ok_or("magic is in the header: its offset counts from the start of the file")?;
        head("magic", self.magic.at, Offset::Start(past("magic", m, self.magic.bytes.len())?))?;
        head("model", self.model.at, self.model.to)?;
        head("saved", self.saved.at, self.saved.to)?;
        let (fa, fb) = head("firmware", self.firmware.at, self.firmware.to)?;
        let want = self.firmware.decode.width();
        if fb - fa != want {
            let words = if want == 2 { "two" } else { "three" };
            return Err(format!("firmware decode {} reads {words} bytes, but {} to {} holds {}", self.firmware.decode.name(), self.firmware.at, self.firmware.to, fb - fa));
        }
        if let Some(v) = &self.video_system {
            let at = v.at.at_start().ok_or("video_system is in the header: its offset counts from the start of the file (\"0x38\")")?;
            head("video_system", v.at, Offset::Start(past("video_system", at, 1)?))?;
            if at >= fa && at < fb {
                return Err(format!("video_system at {} lies inside the firmware ({} to {})", v.at, self.firmware.at, self.firmware.to));
            }
            if self.header_checksum.at.at_start().is_some_and(|s| at >= s && at < s.saturating_add(self.header_checksum.kind.width())) {
                return Err(format!("video_system at {} is the header checksum's site", v.at));
            }
            if v.names.is_empty() {
                return Err("video_system.names names no value".into());
            }
            for (k, name) in &v.names {
                if k.parse::<u8>().ok().map(|n| n.to_string()).as_deref() != Some(k.as_str()) {
                    return Err(format!("video_system.names: {k:?} is not a byte value: write it in decimal, 0 to 255 (\"1\")"));
                }
                if name.trim().is_empty() {
                    return Err(format!("video_system.names gives {k} no name"));
                }
            }
        }
        let h = &self.header_checksum;
        let (a, b) = head("header_checksum.over", h.over[0], h.over[1])?;
        let site = h.at.at_start().ok_or("the header checksum is in the header: its offset counts from the start of the file")?;
        let site_end = past("the header checksum", site, h.kind.width())?;
        if site_end > start {
            return Err(format!("the header checksum at {} runs past sections_start {}", h.at, self.sections_start));
        }
        if site < b && site_end > a {
            return Err(format!("the header checksum at {} lies inside the bytes it sums ({} to {})", h.at, h.over[0], h.over[1]));
        }
        let t = &self.trailer_checksum;
        let Offset::End(n) = t.at else {
            return Err("the trailer checksum's site counts back from the end of the file (\"end-4\")".into());
        };
        if n < t.kind.width() {
            return Err(format!("the trailer checksum at {} has no room for its {} byte(s)", t.at, t.kind.width()));
        }
        if let Offset::End(m) = t.over[1] {
            if m < n {
                return Err(format!("the trailer checksum at {} lies inside the bytes it sums ({} to {})", t.at, t.over[0], t.over[1]));
            }
        }
        Ok(())
    }

    /// Where the magic bytes end, counted from the start of the file: how much of a file `magic_matches` reads.
    pub fn magic_end(&self) -> Option<usize> {
        self.magic.at.at_start()?.checked_add(self.magic.bytes.len())
    }

    /// Whether `d` starts as this block says every such file does.
    pub fn magic_matches(&self, d: &[u8]) -> bool {
        let Some(at) = self.magic.at.at_start() else { return false };
        at.checked_add(self.magic.bytes.len()).and_then(|end| d.get(at..end)) == Some(self.magic.bytes.as_bytes())
    }

    /// A text field read from the start of a file, before its records are framed.
    fn peek_text(&self, d: &[u8], f: &TextField) -> Option<String> {
        let (a, b) = (f.at.at_start()?, f.to.at_start()?);
        d.get(a..b).map(text_of)
    }

    /// The model a file names, read before its records are framed (to pick its definition).
    pub fn peek_model(&self, d: &[u8]) -> Option<String> {
        self.peek_text(d, &self.model)
    }

    /// When a file says it was saved, as its text, read before its records are framed.
    pub fn peek_saved(&self, d: &[u8]) -> Option<String> {
        self.peek_text(d, &self.saved)
    }

    /// The firmware a file names ("4.00"), read before its records are framed.
    pub fn peek_firmware(&self, d: &[u8]) -> Option<String> {
        let (a, b) = (self.firmware.at.at_start()?, self.firmware.to.at_start()?);
        d.get(a..b).map(|v| self.decode_firmware(v))
    }

    fn decode_firmware(&self, v: &[u8]) -> String {
        match self.firmware.decode {
            FirmwareKind::MajorMinor => format!("{}.{:02}", v[0], v[1]),
            FirmwareKind::MajorMinor3 => format!("{}.{:02}", v[0], v[1] as u32 * 10 + v[2] as u32),
        }
    }

    /// A checksum's bytes in a file of `len` bytes: (from, to, site); None when they do not fit.
    fn sites(c: &Checksum, len: usize) -> Option<(usize, usize, usize)> {
        let (a, b, s) = (c.over[0].at(len)?, c.over[1].at(len)?, c.at.at(len)?);
        // checked: an offset from a definition can be as large as a usize holds
        let end = s.checked_add(c.kind.width())?;
        (a <= b && b <= len && end <= len && (s >= b || end <= a)).then_some((a, b, s))
    }
}

/// A firmware ("3.01") as a number to compare (301), so 3.01 < 4.00; None for one that does not read as major.minor.
pub fn firmware_number(fw: &str) -> Option<u32> {
    let (major, minor) = fw.split_once('.')?;
    major.parse::<u32>().ok()?.checked_mul(100)?.checked_add(minor.parse::<u32>().ok()?)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Record {
    pub id: u16,
    pub elem_size: u16,
    pub count: u16,
    pub value: Vec<u8>,
}

impl Record {
    /// Scalar value for single-element records of 1, 2, 4 or 8 bytes.
    pub fn as_int(&self) -> Option<i64> {
        if self.count != 1 {
            return None;
        }
        let b = &self.value;
        Some(match self.elem_size {
            1 => b[0] as i8 as i64,
            2 => i16::from_le_bytes([b[0], b[1]]) as i64,
            4 => i32::from_le_bytes([b[0], b[1], b[2], b[3]]) as i64,
            8 => i64::from_le_bytes(b[..8].try_into().ok()?),
            _ => return None,
        })
    }

    /// Unsigned reading, which is how the mapping tools print single bytes.
    pub fn as_uint(&self) -> Option<u64> {
        if self.count != 1 {
            return None;
        }
        let b = &self.value;
        Some(match self.elem_size {
            1 => b[0] as u64,
            2 => u16::from_le_bytes([b[0], b[1]]) as u64,
            4 => u32::from_le_bytes([b[0], b[1], b[2], b[3]]) as u64,
            8 => u64::from_le_bytes(b[..8].try_into().ok()?),
            _ => return None,
        })
    }

    /// Value as the analysis scripts print it: signed for scalars, so it matches schema values.
    pub fn display_value(&self) -> String {
        if let Some(v) = self.as_int() {
            return v.to_string();
        }
        let n = self.elem_size as usize;
        if matches!(n, 1 | 2 | 4 | 8) && self.count <= 24 {
            let parts: Vec<String> = self
                .value
                .chunks(n)
                .map(|c| match n {
                    1 => (c[0] as i8).to_string(),
                    2 => i16::from_le_bytes([c[0], c[1]]).to_string(),
                    4 => i32::from_le_bytes([c[0], c[1], c[2], c[3]]).to_string(),
                    _ => i64::from_le_bytes(c[..8].try_into().unwrap_or([0; 8])).to_string(),
                })
                .collect();
            return format!("[{}]", parts.join(","));
        }
        let text: Vec<u8> = self.value.iter().copied().take_while(|&b| b != 0).collect();
        if text.len() > 2 && text.iter().all(|b| (32..127).contains(b)) {
            return format!("\"{}\"", String::from_utf8_lossy(&text));
        }
        let hex: Vec<String> = self.value.iter().take(16).map(|b| format!("{b:02x}")).collect();
        format!("{}{} ({} bytes)", hex.join(" "), if self.value.len() > 16 { " …" } else { "" }, self.value.len())
    }

    /// One element of an array record (e.g. one Picture Profile of PP1-PP11).
    pub fn elem(&self, i: usize) -> Option<i64> {
        if i >= self.count as usize {
            return None;
        }
        let n = self.elem_size as usize;
        let b = self.value.get(i * n..(i + 1) * n)?;
        Some(match n {
            1 => b[0] as i8 as i64,
            2 => i16::from_le_bytes([b[0], b[1]]) as i64,
            4 => i32::from_le_bytes([b[0], b[1], b[2], b[3]]) as i64,
            8 => i64::from_le_bytes(b[..8].try_into().ok()?),
            _ => return None,
        })
    }

    pub fn set_elem(&mut self, i: usize, v: i64) -> Result<(), CamSetError> {
        let n = self.elem_size as usize;
        let fits = match n {
            1 => (i8::MIN as i64..=u8::MAX as i64).contains(&v),
            2 => (i16::MIN as i64..=u16::MAX as i64).contains(&v),
            4 => (i32::MIN as i64..=u32::MAX as i64).contains(&v),
            8 => true,
            _ => false,
        };
        if i >= self.count as usize || !fits || (i + 1) * n > self.value.len() {
            return Err(CamSetError::OutOfRange { id: self.id, value: v });
        }
        self.value[i * n..(i + 1) * n].copy_from_slice(&v.to_le_bytes()[..n]);
        Ok(())
    }

    /// Text stored in the record's bytes (NUL padded), if it is printable ASCII.
    pub fn text(&self) -> Option<String> {
        let t: Vec<u8> = self.value.iter().copied().take_while(|&b| b != 0).collect();
        t.iter().all(|b| (32..127).contains(b)).then(|| String::from_utf8_lossy(&t).into_owned())
    }

    /// Write text into the record's bytes, NUL padded; it must leave room for the terminator.
    pub fn set_text(&mut self, t: &str) -> Result<(), CamSetError> {
        let b = t.as_bytes();
        if b.len() >= self.value.len() || !b.iter().all(|c| (32..127).contains(c)) {
            return Err(CamSetError::OutOfRange { id: self.id, value: b.len() as i64 });
        }
        self.value.iter_mut().for_each(|x| *x = 0);
        self.value[..b.len()].copy_from_slice(b);
        Ok(())
    }

    /// Value of a scalar record, or of element `index` of an array record. An index with
    /// FIELD set addresses a little-endian signed 16-bit field at byte offset `index - FIELD`
    /// inside a structured record (e.g. the per-memory exposure block).
    pub fn get(&self, index: Option<u16>) -> Option<i64> {
        match index {
            None => self.as_int(),
            Some(i) if i & FIELD != 0 => {
                let o = (i & !FIELD) as usize;
                self.value.get(o..o + 2).map(|b| i16::from_le_bytes([b[0], b[1]]) as i64)
            }
            Some(i) => self.elem(i as usize),
        }
    }

    pub fn put(&mut self, index: Option<u16>, v: i64) -> Result<(), CamSetError> {
        match index {
            None => self.set_int(v),
            Some(i) if i & FIELD != 0 => {
                let o = (i & !FIELD) as usize;
                if o + 2 > self.value.len() || !(i16::MIN as i64..=u16::MAX as i64).contains(&v) {
                    return Err(CamSetError::OutOfRange { id: self.id, value: v });
                }
                self.value[o..o + 2].copy_from_slice(&v.to_le_bytes()[..2]);
                Ok(())
            }
            Some(i) => self.set_elem(i as usize, v),
        }
    }

    /// Set a scalar value; fails if it does not fit the element size.
    pub fn set_int(&mut self, v: i64) -> Result<(), CamSetError> {
        if self.count != 1 {
            return Err(CamSetError::NotScalar(self.id));
        }
        let fits = match self.elem_size {
            1 => (i8::MIN as i64..=u8::MAX as i64).contains(&v),
            2 => (i16::MIN as i64..=u16::MAX as i64).contains(&v),
            4 => (i32::MIN as i64..=u32::MAX as i64).contains(&v),
            8 => true,
            _ => false,
        };
        if !fits {
            return Err(CamSetError::OutOfRange { id: self.id, value: v });
        }
        let bytes = v.to_le_bytes();
        let n = self.elem_size as usize;
        self.value[..n].copy_from_slice(&bytes[..n]);
        Ok(())
    }
}

#[derive(Clone, Debug, Default)]
pub struct Section {
    pub records: Vec<Record>,
    /// (id, position) of every record, sorted by id and then position, so `get` finds a record by binary search
    /// instead of reading the whole section. Built once by `parse` (or `Section::new`) and shared by every copy of
    /// the section (an edit changes values, never which record sits where). A position it cannot confirm, after
    /// `records` was changed by hand, falls back to reading the records in order, so a lookup is always right.
    index: std::sync::Arc<[(u16, u16)]>,
}

impl Section {
    /// A section holding `records`, indexed for `get`.
    pub fn new(records: Vec<Record>) -> Self {
        let mut index: Vec<(u16, u16)> = Vec::new();
        if records.len() <= u16::MAX as usize {
            index = records.iter().enumerate().map(|(i, r)| (r.id, i as u16)).collect();
            index.sort_unstable();
        }
        Section { records, index: index.into() }
    }

    /// Where the first record with this id sits.
    fn position(&self, id: u16) -> Option<usize> {
        let i = self.index.partition_point(|(x, _)| *x < id);
        if let Some(&(x, p)) = self.index.get(i) {
            if x == id && self.records.get(p as usize).is_some_and(|r| r.id == id) {
                return Some(p as usize);
            }
        }
        self.records.iter().position(|r| r.id == id)
    }

    pub fn get(&self, id: u16) -> Option<&Record> {
        self.position(id).map(|p| &self.records[p])
    }
    pub fn get_mut(&mut self, id: u16) -> Option<&mut Record> {
        self.position(id).map(|p| &mut self.records[p])
    }
}

/// A settings file read through its definition's container block: the header as read, the records of each section,
/// and the bytes after the records (the trailer checksum's site and anything beside it), with whether each checksum
/// held when it was read.
#[derive(Clone, Debug)]
pub struct CamSet {
    pub header: Vec<u8>,
    pub sections: Vec<Section>,
    tail: Vec<u8>,
    format: Arc<FileFormat>,
    header_ok: bool,
    trailer_ok: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum CamSetError {
    NotCamSet,
    Truncated(usize),
    BadMarker(usize),
    BadChecksum { stored: u32, computed: u32 },
    BadHeaderChecksum { stored: u32, computed: u32 },
    TrailingData(usize),
    NotScalar(u16),
    OutOfRange { id: u16, value: i64 },
}

impl fmt::Display for CamSetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotCamSet => write!(f, "not a camera settings file any definition describes (its first bytes are not the ones a definition names)"),
            Self::Truncated(o) => write!(f, "file ends early at offset 0x{o:x}"),
            Self::BadMarker(o) => write!(f, "unexpected record marker at offset 0x{o:x}"),
            Self::BadChecksum { stored, computed } => {
                write!(f, "checksum mismatch (stored 0x{stored:08x}, computed 0x{computed:08x})")
            }
            Self::BadHeaderChecksum { stored, computed } => {
                write!(f, "header checksum mismatch (stored 0x{stored:02x}, computed 0x{computed:02x})")
            }
            Self::TrailingData(n) => write!(f, "{n} unexpected bytes before the checksum"),
            Self::NotScalar(id) => write!(f, "record 0x{id:04x} is not a single value"),
            Self::OutOfRange { id, value } => write!(f, "{value} does not fit record 0x{id:04x}"),
        }
    }
}

impl std::error::Error for CamSetError {}

fn u16_at(d: &[u8], o: usize) -> Result<u16, CamSetError> {
    d.get(o..o + 2).map(|b| u16::from_le_bytes([b[0], b[1]])).ok_or(CamSetError::Truncated(o))
}
fn u32_at(d: &[u8], o: usize) -> Result<u32, CamSetError> {
    d.get(o..o + 4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]])).ok_or(CamSetError::Truncated(o))
}

/// A checksum as stored: one byte, or a little-endian u32.
fn stored_at(d: &[u8], at: usize, width: usize) -> Option<u32> {
    let b = d.get(at..at.checked_add(width)?)?;
    Some(match width {
        1 => b[0] as u32,
        _ => u32::from_le_bytes([b[0], b[1], b[2], b[3]]),
    })
}

/// A checksum written at its site.
fn store_at(out: &mut [u8], at: usize, width: usize, v: u32) {
    if let Some(b) = at.checked_add(width).and_then(|end| out.get_mut(at..end)) {
        b.copy_from_slice(&v.to_le_bytes()[..width]);
    }
}

impl CamSet {
    /// Read a file with a container block: its first bytes must be the block's magic and its records must frame
    /// as the block says; whether each checksum holds is kept (`checksums_ok`), not refused here.
    pub fn read(d: &[u8], format: &Arc<FileFormat>) -> Result<Self, CamSetError> {
        let f = &**format;
        let start = f.sections_start.at(d.len()).ok_or(CamSetError::NotCamSet)?;
        if !f.magic_matches(d) || d.len() < start {
            return Err(CamSetError::NotCamSet);
        }
        let t = &f.trailer_checksum;
        let end = t.at.at(d.len()).filter(|&e| e >= start).ok_or(CamSetError::NotCamSet)?;
        let check = |c: &Checksum| {
            FileFormat::sites(c, d.len()).and_then(|(a, b, s)| Some((stored_at(d, s, c.kind.width())?, c.kind.compute(&d[a..b], a))))
        };
        // records that do not frame in a file whose trailer checksum fails: the damage is the cause to name
        let trailer = check(t);
        let framed = Self::frame(d, start, end, f.records.marker).map_err(|e| match trailer {
            Some((stored, computed)) if stored != computed => CamSetError::BadChecksum { stored, computed },
            _ => e,
        })?;
        let (header_ok, trailer_ok) = (check(&f.header_checksum).is_some_and(|(s, c)| s == c), trailer.is_some_and(|(s, c)| s == c));
        Ok(CamSet { header: d[..start].to_vec(), sections: framed, tail: d[end..].to_vec(), format: format.clone(), header_ok, trailer_ok })
    }

    /// The sections between `start` and `end`, framed as the vocabulary's one framing says: a u32 record count, then
    /// records of u16 id, u16 marker, u16 element size, u16 element count and the value bytes.
    fn frame(d: &[u8], start: usize, end: usize, marker: u16) -> Result<Vec<Section>, CamSetError> {
        let mut off = start;
        let mut sections = Vec::new();
        while off < end {
            if end - off < 4 {
                return Err(CamSetError::TrailingData(end - off));
            }
            let n = u32_at(&d[..end], off)? as usize;
            off += 4;
            let mut records = Vec::with_capacity(n.min((end - off) / 8));
            for _ in 0..n {
                let id = u16_at(&d[..end], off)?;
                if u16_at(&d[..end], off + 2)? != marker {
                    return Err(CamSetError::BadMarker(off));
                }
                let elem_size = u16_at(&d[..end], off + 4)?;
                let count = u16_at(&d[..end], off + 6)?;
                let len = (elem_size as usize)
                    .checked_mul(count as usize)
                    .filter(|&l| off.checked_add(8).and_then(|o| o.checked_add(l)).is_some_and(|e| e <= end))
                    .ok_or(CamSetError::Truncated(off))?;
                let value = d.get(off + 8..off + 8 + len).ok_or(CamSetError::Truncated(off))?.to_vec();
                records.push(Record { id, elem_size, count, value });
                off += 8 + len;
            }
            sections.push(Section::new(records));
        }
        Ok(sections)
    }

    /// Read a file whose checksums must both hold under the block (a file the editor wrote, or is about to write).
    pub fn parse(d: &[u8], format: &Arc<FileFormat>) -> Result<Self, CamSetError> {
        let c = Self::read(d, format)?;
        let sums = |k: &Checksum| FileFormat::sites(k, d.len()).and_then(|(a, b, s)| Some((stored_at(d, s, k.kind.width())?, k.kind.compute(&d[a..b], a))));
        if !c.trailer_ok {
            let (stored, computed) = sums(&format.trailer_checksum).unwrap_or((0, 0));
            return Err(CamSetError::BadChecksum { stored, computed });
        }
        if !c.header_ok {
            let (stored, computed) = sums(&format.header_checksum).unwrap_or((0, 0));
            return Err(CamSetError::BadHeaderChecksum { stored, computed });
        }
        Ok(c)
    }

    /// The file's bytes, both checksums worked out again at the block's sites.
    pub fn to_bytes(&self) -> Vec<u8> {
        let f = &*self.format;
        let mut out = self.header.clone();
        for s in &self.sections {
            out.extend_from_slice(&(s.records.len() as u32).to_le_bytes());
            for r in &s.records {
                out.extend_from_slice(&r.id.to_le_bytes());
                out.extend_from_slice(&f.records.marker.to_le_bytes());
                out.extend_from_slice(&r.elem_size.to_le_bytes());
                out.extend_from_slice(&r.count.to_le_bytes());
                out.extend_from_slice(&r.value);
            }
        }
        out.extend_from_slice(&self.tail);
        for c in [&f.header_checksum, &f.trailer_checksum] {
            if let Some((a, b, s)) = FileFormat::sites(c, out.len()) {
                let v = c.kind.compute(&out[a..b], a);
                store_at(&mut out, s, c.kind.width(), v);
            }
        }
        out
    }

    /// The container block the file was read with.
    pub fn format(&self) -> &Arc<FileFormat> {
        &self.format
    }

    fn header_text(&self, f: &TextField) -> String {
        match (f.at.at_start(), f.to.at_start()) {
            (Some(a), Some(b)) => self.header.get(a..b).map(text_of).unwrap_or_default(),
            _ => String::new(),
        }
    }
    pub fn model(&self) -> String {
        self.header_text(&self.format.model)
    }
    pub fn timestamp(&self) -> String {
        self.header_text(&self.format.saved)
    }

    /// The firmware that saved the file, as its block decodes it ("4.00").
    pub fn firmware(&self) -> String {
        self.format.decode_firmware(self.firmware_bytes())
    }

    /// The firmware field's bytes as stored.
    pub fn firmware_bytes(&self) -> &[u8] {
        let f = &self.format.firmware;
        match (f.at.at_start(), f.to.at_start()) {
            (Some(a), Some(b)) => self.header.get(a..b).unwrap_or(&[0, 0, 0]),
            _ => &[0, 0, 0],
        }
    }

    /// The video system the camera was set to when it saved the file: the byte as stored and the name its block
    /// gives it (None when the block names none for that value). None when the block does not say where it is.
    pub fn video_system(&self) -> Option<(u8, Option<String>)> {
        let v = self.format.video_system.as_ref()?;
        let b = *self.header.get(v.at.at_start()?)?;
        Some((b, v.name_of(b).map(str::to_string)))
    }

    /// Whether the header checksum held as the file was read.
    pub fn header_checksum_ok(&self) -> bool {
        self.header_ok
    }
    /// Whether the trailer checksum held as the file was read.
    pub fn trailer_checksum_ok(&self) -> bool {
        self.trailer_ok
    }
    /// Both: only such a file is ever edited (docs/decisions/0020).
    pub fn checksums_ok(&self) -> bool {
        self.header_ok && self.trailer_ok
    }

    /// Where each record of a section starts in the file, by the block's framing.
    pub fn record_offsets(&self, section: usize) -> Vec<usize> {
        let mut off = self.header.len();
        for s in self.sections.iter().take(section) {
            off += 4 + s.records.iter().map(|r| 8 + r.value.len()).sum::<usize>();
        }
        off += 4;
        let Some(s) = self.sections.get(section) else { return Vec::new() };
        s.records.iter().map(|r| { let at = off; off += 8 + r.value.len(); at }).collect()
    }

    /// Record layout fingerprint: section sizes. The editor only edits layouts it knows.
    pub fn layout(&self) -> Vec<usize> {
        self.sections.iter().map(|s| s.records.len()).collect()
    }
    /// Fingerprint of the record layout (the block's `signature`, FNV-1a 64): the model, the first two firmware bytes
    /// and every record's id and shape in order. A firmware update that adds, removes, reorders or resizes records
    /// changes it. Must match kit/tools/identify.py.
    pub fn layout_signature(&self) -> String {
        match self.format.signature {
            SignatureKind::Fnv1a64 => {
                let mut h: u64 = 0xcbf29ce484222325;
                let mut feed = |bytes: &[u8]| {
                    for &b in bytes {
                        h ^= b as u64;
                        h = h.wrapping_mul(0x100000001b3);
                    }
                };
                feed(self.model().as_bytes());
                feed(&self.firmware_bytes()[..2]);
                for s in &self.sections {
                    feed(&(s.records.len() as u32).to_le_bytes());
                    for r in &s.records {
                        feed(&r.id.to_le_bytes());
                        feed(&r.elem_size.to_le_bytes());
                        feed(&r.count.to_le_bytes());
                    }
                }
                format!("{h:016x}")
            }
        }
    }

    /// The magic bytes the file starts with, as its block names them.
    pub fn magic(&self) -> String {
        self.format.magic.bytes.clone()
    }

    /// Whether the file is from `model` with exactly these section record counts. A `None`
    /// model or empty counts are not checked. The camera's definition file supplies both.
    pub fn is_known_layout_for(&self, model: Option<&str>, counts: &[usize]) -> bool {
        model.is_none_or(|m| self.model() == m) && (counts.is_empty() || self.layout() == counts)
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    /// The shipped ILCE-1M2 firmware 4.00 definition's `camera.file`, as JSON.
    fn a1_block_json() -> serde_json::Value {
        static TEXT: std::sync::OnceLock<serde_json::Value> = std::sync::OnceLock::new();
        TEXT.get_or_init(|| {
            let p = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json");
            let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
            v["camera"]["file"].clone()
        })
        .clone()
    }

    /// A block read and checked, or why not.
    fn block(v: serde_json::Value) -> Result<Arc<FileFormat>, String> {
        let f: FileFormat = serde_json::from_value(v).map_err(|e| e.to_string())?;
        f.check()?;
        Ok(Arc::new(f))
    }

    fn a1() -> Arc<FileFormat> {
        block(a1_block_json()).expect("the shipped block is valid")
    }

    fn parse(d: &[u8]) -> Result<CamSet, CamSetError> {
        CamSet::parse(d, &a1())
    }

    #[test]
    fn byte_offset_fields() {
        let mut r = Record { id: 0x0180, elem_size: 320, count: 1, value: vec![0; 320] };
        r.value[288..290].copy_from_slice(&400u16.to_le_bytes());
        assert_eq!(r.get(Some(FIELD | 288)), Some(400));
        r.put(Some(FIELD | 292), 500).unwrap();
        assert_eq!(&r.value[292..294], &500u16.to_le_bytes());
        assert!(r.put(Some(FIELD | 319), 1).is_err());              // would run past the end
        assert_eq!(r.get(Some(FIELD | 400)), None);
    }

    /// The shipped definition's model and firmware, as its file says them.
    fn a1_model_and_firmware() -> (String, String) {
        let p = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json");
        let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
        (v["model"].as_str().unwrap().to_string(), v["layouts"][0]["firmware"].as_str().unwrap().to_string())
    }

    /// The settings files in the checkout's private/camsets (git-ignored: absent in CI, and it may hold any files) whose
    /// bytes `keep` takes, in name order. They are chosen by what their headers say, never by their names: the files
    /// are their owners', and so are the names they gave them.
    pub(crate) fn private_files(keep: impl Fn(&[u8]) -> bool) -> Vec<std::path::PathBuf> {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("private").join("camsets");
        let mut v: Vec<std::path::PathBuf> = std::fs::read_dir(dir)
            .map(|rd| rd.flatten().map(|e| e.path()).filter(|p| p.is_file() && p.extension().is_some_and(|e| e.eq_ignore_ascii_case("dat"))).collect())
            .unwrap_or_default();
        v.retain(|p| std::fs::read(p).is_ok_and(|d| keep(&d)));
        v.sort();
        v
    }

    /// Whether a file's header, read with the shipped block, names the shipped definition's model and firmware: a file
    /// of the body and firmware these tests read with.
    pub(crate) fn of_the_definition(d: &[u8]) -> bool {
        let (model, fw) = a1_model_and_firmware();
        let f = a1();
        f.magic_matches(d) && f.peek_model(d) == Some(model) && f.peek_firmware(d) == Some(fw)
    }

    fn samples() -> Vec<std::path::PathBuf> {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("..");
        // the files bodies of this model and firmware wrote, in private/ when it is there; the built-in sample (one of
        // them, personal text removed) always
        let mut v = private_files(of_the_definition);
        v.push(root.join("editor").join("definitions").join("ILCE-1M2_fw4.00.DAT"));
        // the camera's own downloads, in runs/ILCE-1M2_fw4.00/probe_out/ when runs/ is there (CI has none): the body
        // and firmware these tests read with, in name order so the same 20 are taken each time
        if let Ok(rd) = std::fs::read_dir(root.join("runs").join("ILCE-1M2_fw4.00").join("probe_out")) {
            let mut runs: Vec<_> = rd.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|e| e == "DAT")).collect();
            runs.sort();
            v.extend(runs.into_iter().take(20));
        }
        v
    }

    #[test]
    fn round_trip_is_byte_identical() {
        let files = samples();
        assert!(!files.is_empty(), "no sample files found");
        for f in files {
            let d = std::fs::read(&f).unwrap();
            let c = parse(&d).unwrap_or_else(|e| panic!("{}: {e}", f.display()));
            assert_eq!(c.magic(), "SONY1");
            assert!(c.checksums_ok());
            assert!(c.is_known_layout_for(None, &[]));
            assert!(c.is_known_layout_for(Some(&c.model()), &c.layout()), "{}", f.display());
            assert!(!c.is_known_layout_for(Some("not-this-model"), &[]));
            assert!(!c.is_known_layout_for(None, &[1]));
            assert_eq!(c.to_bytes(), d, "{}", f.display());
        }
    }

    /// The header read through the block: the model, the save time and the firmware where it says they are.
    #[test]
    fn header_fields_through_the_block() {
        let d = std::fs::read(samples().last().unwrap()).unwrap();
        let c = parse(&d).unwrap();
        assert_eq!(c.model(), "ILCE-1M2");
        assert_eq!(c.firmware(), "4.00");
        assert_eq!(c.firmware_bytes(), &[4, 0]);
        assert_eq!(c.timestamp().len(), 15, "{}", c.timestamp());
        let f = a1();
        assert!(f.magic_matches(&d) && !f.magic_matches(b"SONY2"));
        assert_eq!((f.peek_model(&d).as_deref(), f.peek_firmware(&d).as_deref()), (Some("ILCE-1M2"), Some("4.00")));
        // the record map's offsets follow the framing: the first record after the first section's count
        assert_eq!(c.record_offsets(0)[0], 0x3c + 4);
        let last = c.record_offsets(c.sections.len() - 1);
        let r = c.sections.last().unwrap().records.last().unwrap();
        assert_eq!(last.last().unwrap() + 8 + r.value.len(), d.len() - 4, "the records run up to the trailer checksum");
    }

    /// The video system is a byte of its own beside the firmware, where the block says: the sample saved with that
    /// byte at 1 is the same firmware with the same layout, under the name the block gives 1; a value the block names
    /// nothing for reads as its number. The old reading (three firmware bytes, no video system) took the same file
    /// for another firmware, which is what the block's change undoes.
    #[test]
    fn the_video_system_is_its_own_byte() {
        let d = std::fs::read(samples().last().unwrap()).unwrap();
        let f = a1();
        let at = f.video_system.as_ref().unwrap().at.at_start().unwrap();
        let with = |v: u8| { let mut e = d.clone(); e[at] = v; resealed(&f, e) };
        let ntsc = parse(&d).unwrap();
        let pal = parse(&with(1)).unwrap();
        assert_eq!((pal.firmware(), pal.video_system()), ("4.00".to_string(), Some((1, Some("PAL".to_string())))));
        assert_eq!(ntsc.firmware(), pal.firmware());
        assert_eq!(pal.layout_signature(), ntsc.layout_signature(), "the layout signature feeds the firmware's bytes only");
        assert_eq!(f.peek_firmware(&with(1)).as_deref(), Some("4.00"));
        assert_eq!(parse(&with(0)).unwrap().video_system(), Some((0, Some("NTSC".to_string()))));
        assert_eq!(parse(&with(7)).unwrap().video_system(), Some((7, None)), "a value the block names nothing for");
        // the reading before 2026-11-06: the PAL file was "4.01"
        let mut old = a1_block_json();
        old["firmware"] = serde_json::json!({ "at": "0x36", "to": "0x39", "decode": "major_minor3" });
        old.as_object_mut().unwrap().remove("video_system");
        let old = block(old).unwrap();
        let c = CamSet::parse(&with(1), &old).unwrap();
        assert_eq!((c.firmware(), c.video_system()), ("4.01".to_string(), None));
    }

    #[test]
    fn edit_updates_checksum_and_value() {
        let f = samples().into_iter().next().unwrap();
        let mut c = parse(&std::fs::read(f).unwrap()).unwrap();
        let r = c.sections[0].get_mut(0x01fe).unwrap();
        let old = r.as_int().unwrap();
        r.set_int(if old == 0 { 1 } else { 0 }).unwrap();
        let bytes = c.to_bytes();
        let back = parse(&bytes).expect("edited file must parse with a valid checksum");
        assert_ne!(back.sections[0].get(0x01fe).unwrap().as_int().unwrap(), old);
    }

    #[test]
    fn rejects_corruption() {
        let f = samples().into_iter().next().unwrap();
        let mut d = std::fs::read(f).unwrap();
        d[0x100] ^= 0xff;
        assert!(matches!(parse(&d), Err(CamSetError::BadChecksum { .. }) | Err(CamSetError::BadMarker(_))));
        assert_eq!(parse(b"nope").unwrap_err(), CamSetError::NotCamSet);
        // a damaged header: read, with its checksum named as failing; refused where both must hold
        let mut d = std::fs::read(samples().last().unwrap()).unwrap();
        d[0x20] ^= 0x01;
        let c = CamSet::read(&d, &a1()).unwrap();
        assert!(!c.header_checksum_ok() && c.trailer_checksum_ok() && !c.checksums_ok());
        assert!(matches!(parse(&d), Err(CamSetError::BadHeaderChecksum { .. })));
    }

    #[test]
    fn layout_signature_matches_python() {
        for f in samples() {
            let c = parse(&std::fs::read(&f).unwrap()).unwrap();
            assert_eq!(c.layout_signature(), "07a5b07a502c68f0", "{}", f.display());
        }
    }

    #[test]
    fn text_round_trip() {
        let f = samples().into_iter().next().unwrap();
        let mut c = parse(&std::fs::read(f).unwrap()).unwrap();
        let r = c.sections[0].get_mut(0x0b5b).unwrap();
        assert!(r.set_text("ABCD").is_err(), "no room for the terminator");
        r.set_text("XYZ").unwrap();
        let back = parse(&c.to_bytes()).unwrap();
        assert_eq!(back.sections[0].get(0x0b5b).unwrap().text().as_deref(), Some("XYZ"));
    }

    /// Records found by id through the index are the ones a scan finds, also after records were removed or added
    /// by hand (the index is then out of date and a lookup reads the records instead).
    #[test]
    fn index_finds_what_a_scan_finds() {
        let f = samples().into_iter().next().unwrap();
        let mut c = parse(&std::fs::read(f).unwrap()).unwrap();
        let scan = |s: &Section, id: u16| s.records.iter().position(|r| r.id == id);
        for s in &c.sections {
            for id in (0..=0x2000u16).step_by(7).chain(s.records.iter().map(|r| r.id)) {
                assert_eq!(s.get(id).map(|r| r as *const Record), scan(s, id).map(|p| &s.records[p] as *const Record), "id 0x{id:04x}");
            }
        }
        let live = &mut c.sections[0];
        let gone = live.records[3].id;
        let kept = live.records[10].id;
        live.records.retain(|r| r.id != gone);
        live.records.push(Record { id: 0xfffe, elem_size: 1, count: 1, value: vec![7] });
        assert!(live.get(gone).is_none());
        assert_eq!(live.get(kept).map(|r| r.id), Some(kept));
        assert_eq!(live.get_mut(0xfffe).and_then(|r| r.as_int()), Some(7));
    }

    #[test]
    fn set_int_range_checks() {
        let mut r = Record { id: 1, elem_size: 1, count: 1, value: vec![0] };
        assert!(r.set_int(300).is_err());
        r.set_int(255).unwrap();
        assert_eq!(r.as_uint(), Some(255));
    }

    #[test]
    fn rejects_huge_record_count_without_oom() {
        let mut d = vec![0u8; 0x3c];
        d[..5].copy_from_slice(b"SONY1");
        d.extend_from_slice(&u32::MAX.to_le_bytes());
        let sum = ChecksumKind::ByteSum.compute(&d[0x3c..], 0x3c);
        d.extend_from_slice(&sum.to_le_bytes());
        assert_eq!(CamSet::read(&d, &a1()).unwrap_err(), CamSetError::Truncated(0x3c + 4));
    }

    #[test]
    fn elem_eight_byte_array() {
        let mut r = Record { id: 2, elem_size: 8, count: 2, value: vec![0; 16] };
        r.set_elem(0, -123_456_789_012).unwrap();
        r.set_elem(1, 987_654_321_098).unwrap();
        assert_eq!(r.elem(0), Some(-123_456_789_012));
        assert_eq!(r.elem(1), Some(987_654_321_098));
        assert_eq!(r.display_value(), "[-123456789012,987654321098]");
    }

    /// A kind the vocabulary lacks is refused by name; an offset is "0x…" or "end-N" and nothing else; an unknown
    /// key in the block is refused.
    #[test]
    fn a_block_names_only_known_kinds() {
        let with = |path: &[&str], v: serde_json::Value| {
            let mut b = a1_block_json();
            let mut at = &mut b;
            for p in &path[..path.len() - 1] { at = &mut at[*p]; }
            at[path[path.len() - 1]] = v;
            block(b)
        };
        let e = with(&["trailer_checksum", "kind"], "crc32".into()).unwrap_err();
        assert!(e.contains("unknown variant `crc32`") && e.contains("shift_sum"), "{e}");
        assert!(with(&["records", "endian"], "be".into()).unwrap_err().contains("unknown variant `be`"));
        assert!(with(&["records", "framing"], "x".into()).unwrap_err().contains("unknown variant `x`"));
        assert!(with(&["signature"], "sha1".into()).unwrap_err().contains("unknown variant `sha1`"));
        for bad in ["0x3c ", "60", "end+4", "0X3C", "0x3C", "end-", ""] {
            let e = with(&["sections_start"], bad.into()).unwrap_err();
            assert!(e.contains("is not an offset"), "{bad:?}: {e}");
        }
        assert!(with(&["records", "marker"], "2cf".into()).unwrap_err().contains("not a 16-bit hex value"));
        assert!(with(&["model", "colour"], "red".into()).unwrap_err().contains("unknown field `colour`"));
        // what the typed reading lets through but does not hold together
        assert!(with(&["model", "to"], "0x05".into()).unwrap_err().contains("must come after its start"));
        assert!(with(&["saved", "to"], "0x40".into()).unwrap_err().contains("past sections_start"));
        assert!(with(&["firmware", "to"], "0x3a".into()).unwrap_err().contains("major_minor reads two bytes"));
        assert!(with(&["firmware", "decode"], "major_minor3".into()).unwrap_err().contains("major_minor3 reads three bytes"));
        assert!(with(&["firmware", "decode"], "bcd".into()).unwrap_err().contains("unknown variant `bcd`"));
        // the video system: one byte in the header, apart from the firmware and the header checksum, its values named
        assert!(with(&["video_system", "at"], "0x37".into()).unwrap_err().contains("inside the firmware"));
        assert!(with(&["video_system", "at"], "0x39".into()).unwrap_err().contains("header checksum's site"));
        assert!(with(&["video_system", "at"], "0x3c".into()).unwrap_err().contains("past sections_start"));
        assert!(with(&["video_system", "at"], "end-1".into()).unwrap_err().contains("counts from the start"));
        assert!(with(&["video_system", "names"], serde_json::json!({})).unwrap_err().contains("names no value"));
        for bad in ["256", "01", "-1", "x", ""] {
            let e = with(&["video_system", "names"], serde_json::json!({ bad: "PAL" })).unwrap_err();
            assert!(e.contains("is not a byte value"), "{bad:?}: {e}");
        }
        assert!(with(&["video_system", "names"], serde_json::json!({ "1": " " })).unwrap_err().contains("gives 1 no name"));
        assert!(with(&["video_system", "colour"], "red".into()).unwrap_err().contains("unknown field `colour`"));
        let mut none = a1_block_json();
        none.as_object_mut().unwrap().remove("video_system");
        assert!(block(none).is_ok(), "a block without it reads as before");
        assert!(with(&["header_checksum", "at"], "0x10".into()).unwrap_err().contains("inside the bytes it sums"));
        assert!(with(&["trailer_checksum", "at"], "0x10".into()).unwrap_err().contains("counts back from the end"));
        assert!(with(&["trailer_checksum", "at"], "end-2".into()).unwrap_err().contains("no room"));
        assert!(with(&["trailer_checksum", "at"], "end-8".into()).unwrap_err().contains("inside the bytes it sums"));
        assert!(with(&["magic", "bytes"], "".into()).unwrap_err().contains("empty"));
        // the largest offset an offset may be written as: refused as a place, never an overflow (on any target)
        for field in [&["magic", "at"][..], &["video_system", "at"][..], &["header_checksum", "at"][..]] {
            assert!(with(field, "0xffffffff".into()).is_err(), "{field:?}");
        }
    }

    /// A made-up container: the a1 II's records, but the model at 0x08, the save time at 0x18 and the firmware at
    /// 0x30 in three bytes, no video system, the header checksum at 0x2f summing 0x00-0x2f, the sections from 0x40 and
    /// an 8-byte trailer (the sum, then four bytes of the camera's own). The block that says so reads it and writes it
    /// back as it was; the ILCE-1M2's block does not read it.
    #[test]
    fn another_block_reads_another_container() {
        let sample = parse(&std::fs::read(samples().last().unwrap()).unwrap()).unwrap();
        let mut b = a1_block_json();
        b["magic"]["bytes"] = "XAMPL".into();
        b["model"] = serde_json::json!({ "at": "0x08", "to": "0x18", "text": "ascii_nul" });
        b["saved"] = serde_json::json!({ "at": "0x18", "to": "0x28", "text": "ascii_nul" });
        b["firmware"] = serde_json::json!({ "at": "0x30", "to": "0x33", "decode": "major_minor3" });
        b.as_object_mut().unwrap().remove("video_system");
        b["header_checksum"] = serde_json::json!({ "kind": "shift_sum", "over": ["0x00", "0x2f"], "at": "0x2f" });
        b["sections_start"] = "0x40".into();
        b["trailer_checksum"] = serde_json::json!({ "kind": "byte_sum", "over": ["0x40", "end-8"], "at": "end-8" });
        let other = block(b).unwrap();
        // the file, built by hand: a made-up model, firmware 1.02
        let mut d = vec![0u8; 0x40];
        d[..5].copy_from_slice(b"XAMPL");
        d[0x08..0x08 + 8].copy_from_slice(b"XMPL-100");
        d[0x18..0x18 + 15].copy_from_slice(b"20260102_030405");
        d[0x30..0x33].copy_from_slice(&[1, 0, 2]);
        for s in &sample.sections {
            d.extend_from_slice(&(s.records.len() as u32).to_le_bytes());
            for r in &s.records {
                for v in [r.id, 0x02cf, r.elem_size, r.count] { d.extend_from_slice(&v.to_le_bytes()); }
                d.extend_from_slice(&r.value);
            }
        }
        let body = ChecksumKind::ByteSum.compute(&d[0x40..], 0x40);
        d.extend_from_slice(&body.to_le_bytes());
        d.extend_from_slice(&[9, 8, 7, 6]);
        d[0x2f] = ChecksumKind::ShiftSum.compute(&d[..0x2f], 0) as u8;
        let c = CamSet::parse(&d, &other).unwrap();
        assert_eq!((c.model().as_str(), c.firmware().as_str(), c.timestamp().as_str()), ("XMPL-100", "1.02", "20260102_030405"));
        assert_eq!(c.video_system(), None, "a block that does not say where it is");
        assert_eq!(c.layout(), sample.layout());
        assert_eq!(c.to_bytes(), d, "written back byte for byte, the camera's own trailer bytes kept");
        assert!(CamSet::read(&d, &a1()).is_err(), "the ILCE-1M2's block does not read it");
        // an edit: both sums at the block's sites
        let mut e = c.clone();
        e.sections[0].records[0].value[0] ^= 1;
        let back = CamSet::parse(&e.to_bytes(), &other).unwrap();
        assert_eq!(back.sections[0].records[0].value[0], d[0x40 + 4 + 8] ^ 1);
    }

    /// A block that names a wrong place for a checksum reads the file, but that checksum fails: such a file is never
    /// edited. A trailer checksum placed wrong does not even frame the records.
    #[test]
    fn a_wrong_checksum_site_fails() {
        let d = std::fs::read(samples().last().unwrap()).unwrap();
        let mut b = a1_block_json();
        b["header_checksum"]["over"] = serde_json::json!(["0x01", "0x39"]);
        let c = CamSet::read(&d, &block(b).unwrap()).unwrap();
        assert!(!c.header_checksum_ok() && !c.checksums_ok());
        let mut b = a1_block_json();
        b["header_checksum"]["at"] = "0x3a".into();
        b["header_checksum"]["over"] = serde_json::json!(["0x00", "0x3a"]);
        assert!(!CamSet::read(&d, &block(b).unwrap()).unwrap().checksums_ok());
        let mut b = a1_block_json();
        b["trailer_checksum"] = serde_json::json!({ "kind": "byte_sum", "over": ["0x3c", "end-8"], "at": "end-8" });
        assert!(CamSet::read(&d, &block(b).unwrap()).is_err());
    }

    /// A small random source (xorshift64*) with a fixed seed: the same cases on every run, so a failure comes back.
    pub(crate) struct Rng(pub u64);

    impl Rng {
        pub fn next(&mut self) -> u64 {
            self.0 ^= self.0 >> 12;
            self.0 ^= self.0 << 25;
            self.0 ^= self.0 >> 27;
            self.0.wrapping_mul(0x2545_f491_4f6c_dd1d)
        }

        pub fn below(&mut self, n: usize) -> usize {
            (self.next() % n.max(1) as u64) as usize
        }

        pub fn bytes(&mut self, n: usize) -> Vec<u8> {
            (0..n).map(|_| self.next() as u8).collect()
        }
    }

    /// `d` with both checksums worked out again at the block's sites: damage a checksum no longer gives away, as a
    /// file made by hand could carry.
    pub(crate) fn resealed(f: &FileFormat, mut d: Vec<u8>) -> Vec<u8> {
        for c in [&f.header_checksum, &f.trailer_checksum] {
            if let Some((a, b, s)) = FileFormat::sites(c, d.len()) {
                let v = c.kind.compute(&d[a..b], a);
                store_at(&mut d, s, c.kind.width(), v);
            }
        }
        d
    }

    /// The ways one byte is damaged: a low bit, a high bit, cleared, set.
    pub(crate) const DAMAGE: [fn(u8) -> u8; 4] = [|b| b ^ 0x01, |b| b ^ 0x80, |_| 0x00, |_| 0xff];

    /// Everything the editor asks of a file once read; none of it may panic either.
    pub(crate) fn use_all(c: &CamSet) {
        let _ = (c.model(), c.timestamp(), c.firmware(), c.video_system(), c.layout_signature(), c.layout(), c.magic(), c.checksums_ok());
        for (i, s) in c.sections.iter().enumerate() {
            let _ = c.record_offsets(i);
            for r in &s.records {
                let _ = (r.as_int(), r.as_uint(), r.display_value(), r.text(), r.elem(0), r.get(None), r.get(Some(FIELD | 2)), r.get(Some(1)));
                let _ = s.get(r.id);
            }
        }
        let _ = c.is_known_layout_for(Some("ILCE-1M2"), &[1, 2]);
        let back = c.to_bytes();
        // what reads writes back framed the same way
        let again = CamSet::read(&back, c.format()).expect("a file written back reads again");
        assert_eq!(again.layout(), c.layout());
    }

    /// One damaged file through the block: `CamSet::read` and `CamSet::parse` return, never panic, and agree (parse
    /// only where both checksums hold). `what` names the case when one does panic. Ok: what parse read.
    pub(crate) fn survives(what: &str, d: &[u8], f: &Arc<FileFormat>) -> Result<CamSet, CamSetError> {
        let out = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let read = CamSet::read(d, f);
            let Ok(c) = &read else { return Err(read.err().unwrap_or(CamSetError::NotCamSet)) };
            use_all(c);
            let parsed = CamSet::parse(d, f);
            assert_eq!(parsed.is_ok(), c.checksums_ok(), "{what}: parse refuses only for a checksum");
            parsed
        }));
        out.unwrap_or_else(|_| panic!("the parser panicked on {what}"))
    }

    /// The parser on hostile input never panics: random bytes (some starting as a settings file does), the sample cut
    /// short anywhere, and the sample with one byte damaged in its header, its sections' record counts and its records'
    /// element sizes and counts, with the checksums as they were and worked out again. A file cut short or with a count
    /// or size damaged is refused. Capped in time, so a slow build runs fewer cases, never forever.
    #[test]
    fn hostile_files_never_panic() {
        let started = std::time::Instant::now();
        let budget = std::time::Duration::from_secs(20);
        let over = || started.elapsed() > budget;
        // a firmware too large to count is none, not an overflow
        assert_eq!(firmware_number("99999999.0"), None);
        assert_eq!(firmware_number("255.2805"), Some(28305));
        assert_eq!(firmware_number("255.255"), Some(25755));
        let f = a1();
        let sample = std::fs::read(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.DAT")).unwrap();
        let start = 0x3c;
        let mut rng = Rng(0x0c0f_fee0_dead_beef);
        let mut cases = 0usize;
        // random bytes: plain, behind the magic, and behind the sample's own header (checksums worked out again)
        for i in 0..1500 {
            let len = rng.below(if i % 10 == 0 { 70_000 } else { 600 });
            let mut d = rng.bytes(len);
            match i % 3 {
                0 => {}
                1 => if d.len() >= 5 { d[..5].copy_from_slice(b"SONY1") },
                _ => {
                    let mut h = sample[..start].to_vec();
                    h.extend_from_slice(&d);
                    d = if i % 2 == 0 { resealed(&f, h) } else { h };
                }
            }
            let _ = survives(&format!("random bytes #{i} ({len} bytes)"), &d, &f);
            cases += 1;
        }
        // cut short: every length through the header and the first records, then spread over the file, then the end
        let mut lengths: Vec<usize> = (0..start + 512).collect();
        lengths.extend((start + 512..sample.len()).step_by(997));
        lengths.extend(sample.len() - 64..sample.len());
        for n in lengths {
            assert!(survives(&format!("the sample cut to {n} bytes"), &sample[..n], &f).is_err(), "cut to {n} bytes: refused");
            cases += 1;
        }
        let c = CamSet::parse(&sample, &f).unwrap();
        // one byte of the header damaged: any outcome but a panic (a changed name or time still reads)
        for at in 0..start {
            for (k, damage) in DAMAGE.iter().enumerate() {
                let mut d = sample.clone();
                d[at] = damage(d[at]);
                if d[at] == sample[at] { continue; }
                let _ = survives(&format!("header byte 0x{at:02x} damaged ({k})"), &d, &f);
                let _ = survives(&format!("header byte 0x{at:02x} damaged ({k}), resealed"), &resealed(&f, d), &f);
                cases += 2;
            }
        }
        // a section's record count damaged: refused while the checksum holds the record bytes; resealed, no panic
        // (each count sits just before its section's first record)
        let counts: Vec<usize> = (0..c.sections.len()).map(|si| c.record_offsets(si)[0] - 4).collect();
        assert_eq!(counts[0], start);
        for (si, at) in counts.iter().enumerate() {
            assert_eq!(u32_at(&sample, *at).unwrap() as usize, c.sections[si].records.len(), "the count of section {si} is at 0x{at:x}");
            for b in 0..4 {
                for (k, damage) in DAMAGE.iter().enumerate() {
                    let mut d = sample.clone();
                    d[at + b] = damage(d[at + b]);
                    if d[at + b] == sample[at + b] { continue; }
                    let what = format!("section {si}'s record count, byte {b} damaged ({k})");
                    assert!(survives(&what, &d, &f).is_err(), "{what}: refused");
                    let _ = survives(&format!("{what}, resealed"), &resealed(&f, d), &f);
                    cases += 2;
                }
            }
        }
        // a record's element size or element count damaged, in records picked at random over every section
        let offsets: Vec<(usize, usize)> = (0..c.sections.len()).flat_map(|si| c.record_offsets(si).into_iter().map(move |o| (si, o))).collect();
        for n in 0..1500 {
            if over() { break; }
            let (si, o) = offsets[rng.below(offsets.len())];
            let field = 4 + rng.below(4);   // the size's two bytes, then the count's
            let at = o + field;
            let damage = DAMAGE[rng.below(DAMAGE.len())];
            let mut d = sample.clone();
            d[at] = damage(d[at]);
            if d[at] == sample[at] { continue; }
            let what = format!("case {n}: record at 0x{o:x} (section {si}), header byte {field} damaged");
            assert!(survives(&what, &d, &f).is_err(), "{what}: refused");
            let _ = survives(&format!("{what}, resealed"), &resealed(&f, d), &f);
            cases += 2;
        }
        assert!(cases > 5000 || over(), "{cases} cases in {:?}", started.elapsed());
    }
}
