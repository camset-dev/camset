//! The Windows program's icon and version details (Explorer, the taskbar, shortcuts, Properties > Details), as a
//! compiled resource file (.res) that the MSVC linker takes as it is, so no resource compiler is needed.
//!
//! build.rs includes this file and, on a Windows build, writes the .res from assets/icon.png (the one picture the
//! window, the macOS app and the Linux menu entry use too), Cargo.toml's version and LICENSE's copyright line. The
//! editor's tests include it as well, so what build.rs links is tested on every system.
//!
//! The formats (Microsoft's documentation): an .ico is a directory of images; in a .res the same images are RT_ICON
//! resources and the directory an RT_GROUP_ICON one naming them by number; the version details are a VS_VERSIONINFO
//! tree of 16-bit-length nodes, each aligned to 4 bytes.

/// The icon's sizes in pixels: Explorer's lists and the title bar (16, 20 at 125 %), the taskbar (24, 32), the
/// desktop and Explorer's medium icons (32, 40, 48, 64), and its large ones and tiles, which Windows draws down from 256.
pub const ICON_SIZES: [u32; 8] = [16, 20, 24, 32, 40, 48, 64, 256];

/// The program's name, as Explorer, Task Manager and "Open with" show it (the File description), and its product.
pub const PRODUCT: &str = "Camset Editor";

/// The words after the copyright holders, as the macOS app's About panel has them (packaging/macos/Info.plist).
pub const NOT_SONY: &str = "Independent project; not affiliated with or endorsed by Sony.";

/// One of the icon's images: its size and its bytes as the .ico and the .res hold them (a 32-bit DIB with its
/// mask for the small sizes, a PNG for 256).
pub struct IconImage {
    pub size: u32,
    pub data: Vec<u8>,
}

/// The icon's images, each size drawn down from `png` (assets/icon.png), 32-bit with alpha: 256 from the picture
/// itself, the smaller ones from that 256 (alike to the eye, and a fraction of the time in a build script, which
/// cargo builds unoptimized: about half a second instead of three). The faint ring the filter leaves just outside
/// the rounded square (alpha 1 or 2 of 255, invisible) is cleared, so the corners are transparent, as drawn.
pub fn icon_images(png: &[u8]) -> Result<Vec<IconImage>, String> {
    let lanczos = image::imageops::FilterType::Lanczos3;
    let icon = image::load_from_memory_with_format(png, image::ImageFormat::Png).map_err(|e| format!("assets/icon.png does not read as a PNG: {e}"))?.to_rgba8();
    let large = image::imageops::resize(&icon, 256, 256, lanczos);
    let mut images = Vec::new();
    for size in ICON_SIZES {
        let mut small = if size == 256 { large.clone() } else { image::imageops::resize(&large, size, size, lanczos) };
        for p in small.pixels_mut().filter(|p| p.0[3] < 4) {
            p.0 = [0; 4];
        }
        let data = if size >= 256 {
            let mut out = Vec::new();
            image::ImageEncoder::write_image(image::codecs::png::PngEncoder::new(&mut out), small.as_raw(), size, size, image::ExtendedColorType::Rgba8)
                .map_err(|e| format!("the {size} px icon does not write as a PNG: {e}"))?;
            out
        } else {
            dib(small.as_raw(), size)
        };
        images.push(IconImage { size, data });
    }
    Ok(images)
}

/// A square RGBA picture (rows top down) as an icon's DIB: a BITMAPINFOHEADER whose height counts the colour rows
/// and the mask's, the colour rows bottom up as BGRA (alpha not premultiplied), then the 1-bit mask, bottom up too,
/// each row padded to 4 bytes, set where the picture is fully transparent (for anything that ignores the alpha).
fn dib(rgba: &[u8], size: u32) -> Vec<u8> {
    let s = size as usize;
    let mask_row = s.div_ceil(32) * 4;
    let mut out = Vec::with_capacity(40 + s * s * 4 + mask_row * s);
    for v in [40u32, size, size * 2] {
        out.extend(v.to_le_bytes());
    }
    out.extend(1u16.to_le_bytes());     // planes
    out.extend(32u16.to_le_bytes());    // bits per pixel
    for v in [0u32, (s * s * 4 + mask_row * s) as u32, 0, 0, 0, 0] {
        out.extend(v.to_le_bytes());    // BI_RGB, the image's size, resolution x and y, colours used and important
    }
    for row in rgba.chunks_exact(s * 4).rev() {
        for p in row.chunks_exact(4) {
            out.extend([p[2], p[1], p[0], p[3]]);
        }
    }
    for row in rgba.chunks_exact(s * 4).rev() {
        let mut bits = vec![0u8; mask_row];
        for (x, p) in row.chunks_exact(4).enumerate() {
            if p[3] == 0 {
                bits[x / 8] |= 0x80 >> (x % 8);
            }
        }
        out.extend(bits);
    }
    out
}

/// The first byte of a size in an icon directory: the size, or 0 for 256.
fn dir_size(size: u32) -> u8 {
    if size >= 256 { 0 } else { size as u8 }
}

/// An .ico file of `images`: the directory (each entry's size, 32 bits per pixel, its length and where it starts),
/// then the images in that order.
pub fn ico_file(images: &[IconImage]) -> Vec<u8> {
    let mut out = Vec::new();
    for v in [0u16, 1, images.len() as u16] {
        out.extend(v.to_le_bytes());    // reserved, an icon, how many
    }
    let mut offset = 6 + 16 * images.len();
    for img in images {
        out.extend([dir_size(img.size), dir_size(img.size), 0, 0]);
        out.extend(1u16.to_le_bytes());
        out.extend(32u16.to_le_bytes());
        out.extend((img.data.len() as u32).to_le_bytes());
        out.extend((offset as u32).to_le_bytes());
        offset += img.data.len();
    }
    for img in images {
        out.extend(&img.data);
    }
    out
}

const RT_ICON: u16 = 3;
const RT_GROUP_ICON: u16 = 14;
const RT_VERSION: u16 = 16;
/// The resources' language: English (United States), as the version details' Translation names it.
const LANGUAGE: u16 = 0x0409;
/// The version details' code page: Unicode (UTF-16), as their string table's name says ("040904B0").
const CODE_PAGE: u16 = 1200;

/// The bytes up to a multiple of 4.
fn pad4(out: &mut Vec<u8>) {
    while out.len() % 4 != 0 {
        out.push(0);
    }
}

/// One resource of a .res file, its type and name both numbers: the header (data size, header size, type, name,
/// data version, memory flags, language, version, characteristics), the data, padding to 4 bytes.
fn resource(out: &mut Vec<u8>, kind: u16, name: u16, flags: u16, data: &[u8]) {
    out.extend((data.len() as u32).to_le_bytes());
    out.extend(32u32.to_le_bytes());
    for v in [0xFFFF, kind, 0xFFFF, name] {
        out.extend(u16::to_le_bytes(v));
    }
    out.extend(0u32.to_le_bytes());
    out.extend(flags.to_le_bytes());
    out.extend(if kind == 0 { 0u16 } else { LANGUAGE }.to_le_bytes());
    out.extend([0u8; 8]);
    out.extend(data);
    pad4(out);
}

/// The .res file the linker takes: the icon (`images` as RT_ICON 1, 2, …, and the group RT_GROUP_ICON 1 that names
/// them, the one Explorer shows for the program) and the version details (`version_info`, RT_VERSION 1). The memory
/// flags are the ones rc.exe writes (moveable, pure, discardable); Windows reads none of them.
pub fn res_file(images: &[IconImage], version_info: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    resource(&mut out, 0, 0, 0, &[]);     // the empty first entry that marks a 32-bit .res file
    let mut group = Vec::new();
    for v in [0u16, 1, images.len() as u16] {
        group.extend(v.to_le_bytes());
    }
    for (i, img) in images.iter().enumerate() {
        let id = i as u16 + 1;
        resource(&mut out, RT_ICON, id, 0x1010, &img.data);
        group.extend([dir_size(img.size), dir_size(img.size), 0, 0]);
        group.extend(1u16.to_le_bytes());
        group.extend(32u16.to_le_bytes());
        group.extend((img.data.len() as u32).to_le_bytes());
        group.extend(id.to_le_bytes());
    }
    resource(&mut out, RT_GROUP_ICON, 1, 0x1030, &group);
    resource(&mut out, RT_VERSION, 1, 0x0030, version_info);
    out
}

/// A node's value in the version details: binary (its length in bytes), text (its length in UTF-16 units, the
/// closing zero counted) or none.
enum Value<'a> {
    Binary(&'a [u8]),
    Text(&'a str),
    None,
}

fn utf16z(text: &str) -> Vec<u8> {
    text.encode_utf16().chain([0]).flat_map(u16::to_le_bytes).collect()
}

/// One node of the version details: its length (to the end of its last child), its value's length, its type (0
/// binary, 1 text), its key, padding, its value, then its children, each starting on a multiple of 4.
fn node(key: &str, value: Value, children: &[Vec<u8>]) -> Vec<u8> {
    let (value_len, kind, bytes) = match value {
        Value::Binary(b) => (b.len(), 0u16, b.to_vec()),
        Value::Text(t) => (t.encode_utf16().count() + 1, 1, utf16z(t)),
        Value::None => (0, 1, Vec::new()),
    };
    let mut out = vec![0u8; 2];
    out.extend((value_len as u16).to_le_bytes());
    out.extend(kind.to_le_bytes());
    out.extend(utf16z(key));
    pad4(&mut out);
    out.extend(bytes);
    for child in children {
        pad4(&mut out);
        out.extend(child);
    }
    let len = out.len() as u16;
    out[..2].copy_from_slice(&len.to_le_bytes());
    out
}

/// Cargo.toml's version as Windows' four numbers ("0.2.0" → 0, 2, 0, 0; "1.4.2-beta.1" → 1, 4, 2, 0): one that is
/// not a number, or does not fit 16 bits, is 0.
pub fn version_numbers(version: &str) -> [u16; 4] {
    let core = version.split(['-', '+']).next().unwrap_or("");
    let mut out = [0u16; 4];
    for (slot, part) in out.iter_mut().zip(core.split('.')) {
        *slot = part.parse().unwrap_or(0);
    }
    out
}

/// The copyright holders LICENSE names, the words after its first "Copyright (c) " line's prefix, as
/// packaging/build_macos_app.sh reads them for the macOS app.
pub fn copyright_holders(license: &str) -> Option<String> {
    license.lines().find_map(|l| l.strip_prefix("Copyright (c) ")).map(str::trim).filter(|h| !h.is_empty()).map(str::to_string)
}

/// The version details' words, in the order Properties > Details lists most of them: the program's name and
/// description, its version (Cargo.toml's, as written), the copyright line the macOS app shows (when LICENSE has
/// one), the names it was built under.
pub fn version_strings(version: &str, holders: Option<&str>) -> Vec<(&'static str, String)> {
    let mut out = vec![("FileDescription", PRODUCT.to_string()), ("FileVersion", version.to_string()), ("InternalName", "camset_editor".to_string())];
    if let Some(h) = holders {
        out.push(("LegalCopyright", format!("Copyright (c) {h}. {NOT_SONY}")));
    }
    out.extend([("OriginalFilename", "camset_editor.exe".to_string()), ("ProductName", PRODUCT.to_string()), ("ProductVersion", version.to_string())]);
    out
}

/// The version details (VS_VERSIONINFO): the fixed part (the file's and product's version numbers, a program for
/// 32- and 64-bit Windows, no flags), the English string table of `version_strings` and the Translation that names it.
pub fn version_info(version: &str, holders: Option<&str>) -> Vec<u8> {
    let [a, b, c, d] = version_numbers(version).map(u32::from);
    let (ms, ls) = ((a << 16) | b, (c << 16) | d);
    let mut fixed = Vec::new();
    // signature, structure version, file version, product version, flags mask, flags, VOS_NT_WINDOWS32, VFT_APP,
    // subtype, date
    for v in [0xFEEF04BDu32, 0x0001_0000, ms, ls, ms, ls, 0x3F, 0, 0x0004_0004, 1, 0, 0, 0] {
        fixed.extend(v.to_le_bytes());
    }
    let strings: Vec<Vec<u8>> = version_strings(version, holders).iter().map(|(k, v)| node(k, Value::Text(v), &[])).collect();
    let table = node(&format!("{LANGUAGE:04X}{CODE_PAGE:04X}"), Value::None, &strings);
    let string_info = node("StringFileInfo", Value::None, &[table]);
    let translation: Vec<u8> = [LANGUAGE, CODE_PAGE].iter().flat_map(|v| v.to_le_bytes()).collect();
    let var_info = node("VarFileInfo", Value::None, &[node("Translation", Value::Binary(&translation), &[])]);
    node("VS_VERSION_INFO", Value::Binary(&fixed), &[string_info, var_info])
}

/// What build.rs links, read back the way Windows reads it. These tests are the editor's (src/main.rs includes this
/// file under test); build.rs never compiles them.
#[cfg(test)]
mod tests {
    use super::*;

    const ICON: &[u8] = include_bytes!("../../assets/icon.png");

    fn u16_at(b: &[u8], at: usize) -> u16 {
        u16::from_le_bytes([b[at], b[at + 1]])
    }

    fn u32_at(b: &[u8], at: usize) -> u32 {
        u32::from_le_bytes([b[at], b[at + 1], b[at + 2], b[at + 3]])
    }

    fn align4(at: usize) -> usize {
        at.div_ceil(4) * 4
    }

    /// An .ico's images as a reader finds them through its directory, (size, bytes), checking that the directory is
    /// an icon's, every entry 32 bits per pixel, and that the images follow it one after another to the file's end.
    fn read_ico(ico: &[u8]) -> Vec<(u32, &[u8])> {
        assert_eq!((u16_at(ico, 0), u16_at(ico, 2)), (0, 1), "reserved, and 1 for an icon");
        let count = u16_at(ico, 4) as usize;
        let mut end = 6 + 16 * count;
        let mut out = Vec::new();
        for i in 0..count {
            let e = &ico[6 + 16 * i..6 + 16 * (i + 1)];
            assert_eq!(e[0], e[1], "square");
            assert_eq!((e[2], e[3], u16_at(e, 4), u16_at(e, 6)), (0, 0, 1, 32), "no palette, one plane, 32 bits per pixel");
            let (len, offset) = (u32_at(e, 8) as usize, u32_at(e, 12) as usize);
            assert_eq!(offset, end, "image {i} starts where the one before it ends");
            end += len;
            out.push((if e[0] == 0 { 256 } else { u32::from(e[0]) }, &ico[offset..offset + len]));
        }
        assert_eq!(end, ico.len(), "the last image ends the file");
        out
    }

    /// An icon image decoded as Windows decodes it: its RGBA rows top down, and for a DIB its mask (true where
    /// transparent), after checking the DIB's header against `size`.
    fn decode(size: u32, data: &[u8]) -> (Vec<u8>, Option<Vec<bool>>) {
        let s = size as usize;
        if data.starts_with(b"\x89PNG\r\n\x1a\n") {
            let img = image::load_from_memory_with_format(data, image::ImageFormat::Png).unwrap();
            assert_eq!((img.width(), img.height(), img.color()), (size, size, image::ColorType::Rgba8));
            return (img.to_rgba8().into_raw(), None);
        }
        let mask_row = s.div_ceil(32) * 4;
        assert_eq!((u32_at(data, 0), u32_at(data, 4), u32_at(data, 8)), (40, size, size * 2), "header size, width, colour and mask rows");
        assert_eq!((u16_at(data, 12), u16_at(data, 14), u32_at(data, 16)), (1, 32, 0), "one plane, 32 bits, BI_RGB");
        assert_eq!(data.len(), 40 + s * s * 4 + mask_row * s, "the colour rows and the mask, nothing more");
        let (colour, mask) = data[40..].split_at(s * s * 4);
        let mut rgba = Vec::new();
        for row in colour.chunks_exact(s * 4).rev() {
            for p in row.chunks_exact(4) {
                rgba.extend([p[2], p[1], p[0], p[3]]);
            }
        }
        let bits = mask.chunks_exact(mask_row).rev().flat_map(|row| (0..s).map(move |x| row[x / 8] & (0x80 >> (x % 8)) != 0)).collect();
        (rgba, Some(bits))
    }

    /// The .ico holds every size Explorer, the taskbar and the tiles ask for, 32-bit with alpha: a DIB below 256 (what
    /// every Windows reads), a PNG at 256 (what Windows Vista and later read there); each decodes to its size, the
    /// rounded square opaque in the middle and clear in the corner, the mask clear where the alpha is.
    #[test]
    fn the_icon_holds_every_size_with_alpha() {
        let images = icon_images(ICON).unwrap();
        let ico = ico_file(&images);
        let found = read_ico(&ico);
        assert_eq!(found.iter().map(|(s, _)| *s).collect::<Vec<_>>(), ICON_SIZES);
        for needed in [16, 24, 32, 48, 64, 256] {
            assert!(ICON_SIZES.contains(&needed), "{needed} px");
        }
        for ((size, data), img) in found.iter().zip(&images) {
            assert_eq!((*size, *data), (img.size, img.data.as_slice()));
            let (rgba, mask) = decode(*size, data);
            assert_eq!(rgba.len(), (size * size * 4) as usize);
            assert_eq!(data.starts_with(b"\x89PNG"), *size == 256, "PNG at 256 only");
            let alpha = |x: u32, y: u32| rgba[((y * size + x) * 4 + 3) as usize];
            assert_eq!(alpha(size / 2, size / 2), 255, "{size} px: opaque in the middle");
            assert_eq!(alpha(0, 0), 0, "{size} px: clear in the corner");
            if let Some(mask) = mask {
                assert!(mask.iter().zip(rgba.chunks_exact(4)).all(|(m, p)| *m == (p[3] == 0)), "{size} px: the mask is the alpha's");
                assert!(mask[0] && !mask[mask.len() / 2 + *size as usize / 2]);
            }
        }
    }

    /// The icon is the picture the window, the macOS app and the Linux menu entry show: drawn from the same file,
    /// assets/icon.png (build.rs reads it, as the window includes it and the packaging scripts copy it), and each size
    /// matches that picture drawn down directly with another filter, while the same picture upside down does not.
    #[test]
    fn the_icon_is_the_window_s_picture() {
        let build = include_str!("../../build.rs");
        assert!(build.contains("std::fs::read(dir.join(\"assets/icon.png\"))") && build.contains("resources::icon_images(&png)"));
        assert!(include_str!("../../src/main.rs").contains("eframe::icon_data::from_png_bytes(include_bytes!(\"../assets/icon.png\"))"));
        assert!(include_str!("../build_macos_app.sh").contains("sips -z $s $s assets/icon.png"));
        assert!(include_str!("../build_linux.sh").contains("cp assets/icon.png"));
        let picture = image::load_from_memory(ICON).unwrap().to_rgba8();
        for img in icon_images(ICON).unwrap() {
            let (rgba, _) = decode(img.size, &img.data);
            // how far apart two pictures are: the root mean square of their channels' differences, in levels of 255
            let apart = |other: &[u8]| (rgba.iter().zip(other).map(|(a, b)| (f64::from(*a) - f64::from(*b)).powi(2)).sum::<f64>() / rgba.len() as f64).sqrt();
            let direct = image::imageops::resize(&picture, img.size, img.size, image::imageops::FilterType::Triangle);
            let (same, flipped) = (apart(direct.as_raw()), apart(image::imageops::flip_vertical(&direct).as_raw()));
            assert!(same < LEVELS_APART, "{} px: {same:.1} levels apart", img.size);
            assert!(flipped > 1.5 * LEVELS_APART, "{} px: upside down only {flipped:.1} levels apart", img.size);
        }
    }

    /// One resource of a .res file as the linker reads it.
    struct Resource {
        kind: u16,
        name: u16,
        flags: u16,
        language: u16,
        data: Vec<u8>,
    }

    /// A .res file's resources, checking each header (32 bytes: type and name as numbers, no data or resource
    /// version, no characteristics) and that each starts on a multiple of 4, to the file's end.
    fn read_res(res: &[u8]) -> Vec<Resource> {
        let (mut at, mut out) = (0, Vec::new());
        while at < res.len() {
            let size = u32_at(res, at) as usize;
            assert_eq!((u32_at(res, at + 4), u16_at(res, at + 8), u16_at(res, at + 12)), (32, 0xFFFF, 0xFFFF), "a header of numbers");
            assert_eq!((u32_at(res, at + 16), u32_at(res, at + 24), u32_at(res, at + 28)), (0, 0, 0));
            out.push(Resource { kind: u16_at(res, at + 10), name: u16_at(res, at + 14), flags: u16_at(res, at + 20), language: u16_at(res, at + 22), data: res[at + 32..at + 32 + size].to_vec() });
            at = align4(at + 32 + size);
        }
        assert_eq!(at, res.len());
        out
    }

    /// A node of the version details: key, type, value, children.
    struct Node {
        key: String,
        kind: u16,
        value: Vec<u8>,
        children: Vec<Node>,
    }

    /// The version details read back node by node, checking every length: a node's ends where its last child (or
    /// its value) ends, and each child starts on a multiple of 4.
    fn read_node(b: &[u8]) -> Node {
        let (len, value_len, kind) = (u16_at(b, 0) as usize, u16_at(b, 2) as usize, u16_at(b, 4));
        assert!(len <= b.len() && kind <= 1);
        let mut at = 6;
        let mut key = Vec::new();
        while u16_at(b, at) != 0 {
            key.push(u16_at(b, at));
            at += 2;
        }
        at = align4(at + 2);
        let value_bytes = if kind == 1 { value_len * 2 } else { value_len };
        let value = b[at..at + value_bytes].to_vec();
        at += value_bytes;
        let mut children = Vec::new();
        while at < len {
            at = align4(at);
            let child = read_node(&b[at..len]);
            at += u16_at(b, at) as usize;
            children.push(child);
        }
        assert_eq!(at, len, "{}: its length ends at its last child", String::from_utf16_lossy(&key));
        Node { key: String::from_utf16(&key).unwrap(), kind, value, children }
    }

    /// A text value's words: UTF-16 with its closing zero.
    fn text(value: &[u8]) -> String {
        let units: Vec<u16> = value.chunks_exact(2).map(|c| u16::from_le_bytes([c[0], c[1]])).collect();
        assert_eq!(units.last(), Some(&0), "a closing zero, counted in the length");
        String::from_utf16(&units[..units.len() - 1]).unwrap()
    }

    /// The .res holds the icon (each image an RT_ICON, numbered from 1; the one group, RT_GROUP_ICON 1, naming them
    /// with their sizes and lengths) and the version details (RT_VERSION 1), in English, after the empty entry that
    /// starts every 32-bit .res file. Its bytes were compared with what llvm-rc writes for the same .rc (ICON and
    /// VERSIONINFO) once, when this was written: the same, byte for byte.
    #[test]
    fn the_res_holds_the_icon_and_the_version() {
        let images = icon_images(ICON).unwrap();
        let info = version_info("0.2.0", Some("2026 Camset contributors"));
        let found = read_res(&res_file(&images, &info));
        assert_eq!((found[0].kind, found[0].name, found[0].flags, found[0].language, found[0].data.len()), (0, 0, 0, 0, 0), "the empty first entry");
        let icons: Vec<&Resource> = found.iter().filter(|r| r.kind == RT_ICON).collect();
        assert_eq!(icons.len(), images.len());
        for (i, (r, img)) in icons.iter().zip(&images).enumerate() {
            assert_eq!((r.name as usize, r.language, r.flags), (i + 1, 0x0409, 0x1010));
            assert!(r.data == img.data, "icon {} holds the {} px image", i + 1, img.size);
        }
        let groups: Vec<&Resource> = found.iter().filter(|r| r.kind == RT_GROUP_ICON).collect();
        assert_eq!(groups.len(), 1, "one icon, the one Explorer shows");
        let g = &groups[0].data;
        assert_eq!((groups[0].name, groups[0].language, groups[0].flags), (1, 0x0409, 0x1030));
        assert_eq!((u16_at(g, 0), u16_at(g, 2), u16_at(g, 4) as usize, g.len()), (0, 1, images.len(), 6 + 14 * images.len()));
        for (i, img) in images.iter().enumerate() {
            let e = &g[6 + 14 * i..6 + 14 * (i + 1)];
            let size = if e[0] == 0 { 256 } else { u32::from(e[0]) };
            assert_eq!((size, e[1], e[2], e[3], u16_at(e, 4), u16_at(e, 6)), (img.size, e[0], 0, 0, 1, 32));
            assert_eq!((u32_at(e, 8) as usize, u16_at(e, 12) as usize), (img.data.len(), i + 1), "its length, and the RT_ICON it names");
        }
        let versions: Vec<&Resource> = found.iter().filter(|r| r.kind == RT_VERSION).collect();
        assert_eq!(versions.len(), 1);
        assert_eq!((versions[0].name, versions[0].language, versions[0].flags), (1, 0x0409, 0x0030));
        assert!(versions[0].data == info);
        assert_eq!(found.len(), 1 + images.len() + 2, "nothing else");
    }

    /// Properties > Details: the version (Cargo.toml's, as numbers and as written), the program's name, the copyright
    /// line the macOS app's About panel shows (LICENSE's holders, the words after them the editor's own), and the
    /// file's name; in the English (Unicode) string table the Translation names.
    #[test]
    fn the_version_details_come_from_cargo_and_the_licence() {
        let version = env!("CARGO_PKG_VERSION");
        let licence = include_str!("../../../LICENSE");
        let holders = copyright_holders(licence);
        // what packaging/build_macos_app.sh reads (sed -n 's/^Copyright (c) //p' ../LICENSE | head -1)
        let mac_words = licence.lines().find_map(|l| l.strip_prefix("Copyright (c) ")).map(str::trim);
        assert!(holders.is_some() && holders.as_deref() == mac_words, "{holders:?}");
        assert_eq!(NOT_SONY, crate::NOT_SONY);
        let plist = include_str!("../macos/Info.plist");
        let mac_line = format!("Copyright (c) @COPYRIGHT@. {NOT_SONY}");
        assert!(plist.contains(&format!("<string>{mac_line}</string>")), "the line the macOS app shows");
        let root = read_node(&version_info(version, holders.as_deref()));
        assert_eq!((root.key.as_str(), root.kind, root.value.len()), ("VS_VERSION_INFO", 0, 52));
        let fixed: Vec<u32> = root.value.chunks_exact(4).map(|c| u32::from_le_bytes([c[0], c[1], c[2], c[3]])).collect();
        let [a, b, c, d] = version_numbers(version).map(u32::from);
        assert_eq!(fixed, [0xFEEF04BD, 0x0001_0000, a << 16 | b, c << 16 | d, a << 16 | b, c << 16 | d, 0x3F, 0, 0x0004_0004, 1, 0, 0, 0]);
        assert_eq!(root.children.iter().map(|n| n.key.as_str()).collect::<Vec<_>>(), ["StringFileInfo", "VarFileInfo"]);
        let table = &root.children[0].children[0];
        assert_eq!((root.children[0].children.len(), table.key.as_str(), table.kind), (1, "040904B0", 1));
        let strings: Vec<(String, String)> = table.children.iter().map(|n| { assert_eq!(n.kind, 1); (n.key.clone(), text(&n.value)) }).collect();
        let copyright = mac_line.replace("@COPYRIGHT@", mac_words.unwrap());
        let expected = [("FileDescription", "Camset Editor"), ("FileVersion", version), ("InternalName", "camset_editor"), ("LegalCopyright", copyright.as_str()),
            ("OriginalFilename", "camset_editor.exe"), ("ProductName", "Camset Editor"), ("ProductVersion", version)];
        assert_eq!(strings, expected.map(|(k, v)| (k.to_string(), v.to_string())));
        let translation = &root.children[1].children[0];
        assert_eq!((translation.key.as_str(), translation.kind, translation.value.as_slice()), ("Translation", 0, &[0x09, 0x04, 0xB0, 0x04][..]));
        // a LICENSE without the line: the details go without a copyright, the rest as they are
        assert_eq!(copyright_holders("MIT License\n\nPermission is hereby granted"), None);
        assert_eq!(copyright_holders("Copyright (c)   \n"), None);
        assert!(!version_strings(version, None).iter().any(|(k, _)| *k == "LegalCopyright"));
        assert_eq!(version_strings(version, None).len(), 6);
    }

    /// Windows' four version numbers from Cargo.toml's version: a pre-release or build suffix drops, what is not a
    /// 16-bit number is 0.
    #[test]
    fn version_numbers_from_cargo_s_version() {
        assert_eq!(version_numbers("0.2.0"), [0, 2, 0, 0]);
        assert_eq!(version_numbers("1.4.2-beta.1"), [1, 4, 2, 0]);
        assert_eq!(version_numbers("3.0.11+build.5"), [3, 0, 11, 0]);
        assert_eq!(version_numbers("70000.1.2"), [0, 1, 2, 0]);
        let [a, b, c, _] = version_numbers(env!("CARGO_PKG_VERSION"));
        assert_eq!([a, b, c].map(|n| n.to_string()), [env!("CARGO_PKG_VERSION_MAJOR"), env!("CARGO_PKG_VERSION_MINOR"), env!("CARGO_PKG_VERSION_PATCH")]);
    }

    /// build.rs links the icon and the version details into the Windows program: on a build for Windows (the
    /// target's system, not the computer's) with Microsoft's linker, from this file, the picture, Cargo.toml's version
    /// and LICENSE, into the program only (`-bins`); Cargo gives it the image crate on a Windows computer only, and a
    /// build that cannot link them goes on, saying so. The release build keeps no console window, the tests' build
    /// keeps its own.
    #[test]
    fn build_rs_links_them_into_the_windows_program() {
        // read with LF line ends, as git checks them out with CRLF on Windows (where these tests run too)
        let build = include_str!("../../build.rs").replace("\r\n", "\n");
        for needed in ["#[cfg(windows)]\n#[allow(dead_code)]\n#[path = \"packaging/windows/resources.rs\"]\nmod resources;",
            "if std::env::var(\"CARGO_CFG_TARGET_OS\").is_ok_and(|os| os == \"windows\") {\n        windows_resources();",
            "std::env::var(\"CARGO_CFG_TARGET_ENV\").is_ok_and(|env| env != \"msvc\")",
            "Ok(res) => println!(\"cargo:rustc-link-arg-bins={}\", res.display()),",
            "Err(e) => println!(\"cargo:warning={without}: {e}\"),",
            "let images = resources::icon_images(&png)?;",
            "resources::copyright_holders(&l)",
            "std::env::var(\"CARGO_PKG_VERSION\")",
            "resources::version_info(&version, holders.as_deref())",
            "std::fs::write(&res, resources::res_file(&images, &info))",
            "for path in [\"assets/icon.png\", \"../LICENSE\", \"packaging/windows/resources.rs\"] {\n        println!(\"cargo:rerun-if-changed={path}\");"] {
            assert!(build.contains(needed), "build.rs: {needed}");
        }
        let cargo = include_str!("../../Cargo.toml").replace("\r\n", "\n");
        assert!(cargo.contains("[target.'cfg(windows)'.build-dependencies]\nimage = { version = \"0.25\", default-features = false, features = [\"png\"] }"));
        let main = include_str!("../../src/main.rs");
        assert!(main.contains("#![cfg_attr(all(not(debug_assertions), not(test)), windows_subsystem = \"windows\")]"));
    }

    /// How far apart (root mean square, levels of 255) the sizes may be from the picture drawn down directly with
    /// another filter: 6.5 at 24 px down to 2.6 at 256 when this was written, where the picture upside down was 17.5
    /// (16 px) to 31 (256 px) apart.
    const LEVELS_APART: f64 = 10.0;
}
