//! Under test: the helpers the test modules of the Menu, a row's detail and the camera link share.

use crate::*;
use crate::definitions::definitions_tests::{a1_with, app_with, scratch};

/// An app with the sample open as a file on disk (so it may be written), and a definition without `strip`'s keys
/// in the user's folder when `strip` is given (then that one is in use).
pub(crate) fn sample_app(tag: &str, strip: Option<fn(&mut serde_json::Value)>) -> (App, PathBuf, PathBuf) {
    let (dir, user) = (scratch(&format!("facts_{tag}")), scratch(&format!("facts_{tag}_user")));
    if let Some(f) = strip {
        std::fs::write(user.join("ILCE-1M2_fw4.00.json"), a1_with(f)).unwrap();
    }
    let mut app = app_with(&user);
    let f = dir.join("CAMSET01.DAT");
    std::fs::write(&f, include_bytes!("../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
    app.open(f);
    (app, dir, user)
}

/// The camera's menus stubbed onto the shipped definition in memory, until its own carry them: `sample_app(tag,
/// Some(stub_menus))`. Three menus as the camera's switch has them: "Still" (the Stills mode), "Movie", and "S&Q" (the
/// S&Q and Time-lapse modes, with a hover), each with its Main tiles. Every setting placed on a row gets `row_menus`:
/// the rows only Movie mode's menu has (`row_mode`) and the settings named for Movie ("(Movie)") Movie's and S&Q's;
/// the ones named for stills ("(Still)"), and those on the same row as one named for Movie, Still's only; every other
/// placed setting all three. A copy (`copy_of`) and a setting placed nowhere get none; no `row_places`.
pub(crate) fn stub_menus(v: &mut serde_json::Value) {
    v["camera"]["menus"] = serde_json::json!([
        { "name": "Still", "modes": ["Stills"], "main_tiles": "Stills" },
        { "name": "Movie", "modes": ["Movie"], "main_tiles": "Movie" },
        { "name": "S&Q", "modes": ["S&Q", "Time-lapse"], "main_tiles": "S&Q", "hover": "Slow and quick motion, and time-lapse" },
    ]);
    let settings = v["settings"].as_array_mut().unwrap();
    let place = |s: &serde_json::Value| (s["row"].clone(), s["row_at"].clone(), s["row_tab"].clone(), s["row_group"].clone());
    let named = |s: &serde_json::Value, w: &str| s["name"].as_str().is_some_and(|n| n.contains(w));
    let movie: Vec<_> = settings.iter().filter(|s| s["copy_of"].is_null() && named(s, "(Movie)")).map(place).collect();
    for s in settings.iter_mut() {
        let placed = s["row"].as_array().is_some_and(|r| !r.is_empty());
        if !s["copy_of"].is_null() || !placed {
            continue;
        }
        let menus: &[&str] = if !s["row_mode"].is_null() || named(s, "(Movie)") {
            &["Movie", "S&Q"]
        } else if named(s, "(Still)") || movie.contains(&place(s)) {
            &["Still"]
        } else {
            &["Still", "Movie", "S&Q"]
        };
        s["row_menus"] = serde_json::json!(menus);
    }
}

/// `stub_menus`, and one setting placed in one menu otherwise than its own place says (`row_places`): Audio Recording
/// (global:0x02e9, a row of Movie mode's menu only, on its own row in Audio Recording) under a row "Audio Settings" in
/// S&Q's menu, in S&Q's alone of the two it has.
pub(crate) fn stub_menus_and_a_place(v: &mut serde_json::Value) {
    stub_menus(v);
    let s = v["settings"].as_array_mut().unwrap().iter_mut().find(|s| s["key"] == "global:0x02e9").unwrap();
    s["row_places"] = serde_json::json!({ "S&Q": { "row": ["Audio Settings", "Audio Recording"], "row_at": [52, 0] } });
}

/// The sample shipped beside the ILCE-1M2 firmware 4.00 definition.
pub(crate) const SAMPLE_BYTES: &[u8] = include_bytes!("../definitions/ILCE-1M2_fw4.00.DAT");

/// The sample with another save time in its header, both checksums worked out again: a file the editor takes for a
/// camera's own, which the tests that write need, as the sample itself, and any file saved from it, is never written
/// (`Definitions::is_sample`). The time is the sample's with its last character changed, so no time is written here.
pub(crate) fn camera_file() -> Vec<u8> {
    let mut c = test_parse(SAMPLE_BYTES).unwrap();
    let f = test_block();
    let (a, b) = (f.saved.at.at(c.header.len()).unwrap(), f.saved.to.at(c.header.len()).unwrap());
    let last = (a..b).rev().find(|&k| c.header[k] != 0).expect("the sample names a save time");
    c.header[last] = if c.header[last].is_ascii_digit() { b'0' + (c.header[last] - b'0' + 1) % 10 } else { b'0' };
    c.to_bytes()
}

/// The settings files in the checkout's private/camsets (git-ignored: absent in CI, and it may hold any files) that the
/// shipped ILCE-1M2 block reads and `keep` takes, given the file and the shipped definition, in name order. They are
/// chosen by what their headers say, never by their names: the files are their owners', and so are the names they gave
/// them.
pub(crate) fn private_files(keep: impl Fn(&CamSet, &Schema) -> bool) -> Vec<PathBuf> {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("private").join("camsets");
    let def = Schema::from_file(&Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json")).unwrap();
    let mut v: Vec<PathBuf> = std::fs::read_dir(dir)
        .map(|rd| rd.flatten().map(|e| e.path()).filter(|p| p.is_file() && p.extension().is_some_and(|e| e.eq_ignore_ascii_case("dat"))).collect())
        .unwrap_or_default();
    v.retain(|p| std::fs::read(p).ok().and_then(|d| CamSet::read(&d, &test_block()).ok()).is_some_and(|c| keep(&c, &def)));
    v.sort();
    v
}

/// Remove a test's folders: the file's and the user's definitions'.
pub(crate) fn done(dir: &Path, user: &Path) {
    let _ = std::fs::remove_dir_all(dir);
    let _ = std::fs::remove_dir_all(user);
}

/// The texts a frame draws.
pub(crate) fn texts(shapes: &[egui::epaint::ClippedShape]) -> Vec<String> {
    fn walk(s: &egui::Shape, out: &mut Vec<String>) {
        match s {
            egui::Shape::Text(t) => out.push(t.galley.text().to_string()),
            egui::Shape::Vec(v) => v.iter().for_each(|s| walk(s, out)),
            _ => {}
        }
    }
    let mut out = Vec::new();
    shapes.iter().for_each(|c| walk(&c.shape, &mut out));
    out
}
