//! The files the editor keeps besides the settings files it opens: whole-or-nothing writes, private files, kept
//! copies, the camera cards' folders, and paths as the person would type them.

use crate::*;

/// The third-party licences page the editor's packages carry (THIRD_PARTY_LICENSES.html, written by cargo about),
/// in one of `licences_places`, in the form the system's browser and file manager open (`plain_path`: on Windows the
/// program's folder resolved is `\\?\C:\…`, which Explorer does not open). None when this build has none: a build of
/// the repository's own (cargo build) has none until cargo about writes it into editor/target/dist.
pub(crate) fn licences_page() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let real = std::fs::canonicalize(&exe).ok();
    [real.as_deref(), Some(exe.as_path())].into_iter().flatten().filter_map(Path::parent)
        .flat_map(licences_places)
        .find(|p| p.is_file())
        .map(|p| plain_path(&p))
}

/// Where the licences page is looked for, from the program's folder: beside the program (the Linux tarball and
/// install, the Windows zip), in the app's Resources (macOS), and where a build in the repository writes it
/// (editor/target/dist, the program being editor/target/release/camset_editor).
pub(crate) fn licences_places(dir: &Path) -> [PathBuf; 3] {
    [dir.join("THIRD_PARTY_LICENSES.html"), dir.join("../Resources/THIRD_PARTY_LICENSES.html"), dir.join("../dist/THIRD_PARTY_LICENSES.html")]
}

/// A folder or file as the window and the web page name it (`path_words`, with this user's home folder): one form
/// for one folder, and no reply of the page names this computer's user.
pub(crate) fn shown_path(p: &Path) -> String {
    path_words(p, &home_folder())
}

/// `p` as the person would type it: no "." or ".." in it (the shipped definitions are found as
/// editor/target/release/../../definitions from a checkout), macOS's /private/var, /private/tmp and /private/etc as
/// /var, /tmp and /etc (where a path the system resolved leads), Windows's resolved `\\?\C:\…` as `C:\…`
/// (`plain_path`), and `home` as "~", spelled with the system's own separator (`~/x`, and `~\x` on Windows). A home
/// with no folder in it ("/", or a drive's root on Windows) names no one, and nothing is shortened by it.
pub(crate) fn path_words(p: &Path, home: &Path) -> String {
    use std::path::Component;
    let tidy = |p: &Path| -> PathBuf {
        let p = plain_path(p);
        let mut out = PathBuf::new();
        for c in p.components() {
            match c {
                Component::CurDir => {}
                Component::ParentDir => match out.components().next_back() {
                    Some(Component::Normal(_)) => { out.pop(); }
                    Some(Component::RootDir | Component::Prefix(_)) => {}
                    _ => out.push(".."),
                },
                other => out.push(other.as_os_str()),
            }
        }
        if cfg!(target_os = "macos") {
            for top in ["var", "tmp", "etc"] {
                if let Ok(rest) = out.strip_prefix(Path::new("/private").join(top)) {
                    return Path::new("/").join(top).join(rest);
                }
            }
        }
        out
    };
    let (p, home) = (tidy(p), tidy(home));
    match p.strip_prefix(&home) {
        Ok(rest) if home.components().any(|c| matches!(c, Component::Normal(_))) => if rest.as_os_str().is_empty() { "~".to_string() } else { Path::new("~").join(rest).display().to_string() },
        _ => p.display().to_string(),
    }
}

/// `p` in the form a person types and other programs open: on Windows, the long form the system resolves a path to
/// (std::fs::canonicalize gives `\\?\C:\…` and `\\?\UNC\server\share\…`) as `C:\…` and `\\server\share\…`. Any other
/// path, and every path on macOS and Linux, is returned as it is.
pub(crate) fn plain_path(p: &Path) -> PathBuf {
    use std::path::{Component, Prefix};
    let mut parts = p.components();
    let mut out = match parts.next() {
        Some(Component::Prefix(x)) => match x.kind() {
            Prefix::VerbatimDisk(drive) => PathBuf::from(format!("{}:", char::from(drive))),
            Prefix::VerbatimUNC(server, share) => {
                let mut s = std::ffi::OsString::from(r"\\");
                s.push(server);
                s.push(r"\");
                s.push(share);
                PathBuf::from(s)
            }
            _ => return p.to_path_buf(),
        },
        _ => return p.to_path_buf(),
    };
    out.extend(parts);   // the root, then each folder
    out
}

/// This user's home folder (empty when the system names none): %USERPROFILE% on Windows, where $HOME, when it is set
/// at all, is a Unix shell's (Git Bash's, MSYS2's) and may be spelled its way (/c/Users/you); $HOME elsewhere.
pub(crate) fn home_folder() -> PathBuf {
    let names = if cfg!(windows) { ["USERPROFILE", "HOME"] } else { ["HOME", "USERPROFILE"] };
    names.into_iter().filter_map(std::env::var_os).find(|v| !v.is_empty()).map(PathBuf::from).unwrap_or_default()
}

/// Make one of the editor's own folders (the preferences folder, ~/.config/camset) and its parents, and keep it readable
/// by this user only: mode 700 on Unix and macOS, whatever it had. Elsewhere it is only made (on Windows the user's
/// profile folder already keeps other users out).
pub(crate) fn private_dir(d: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(d)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = std::fs::metadata(d)?.permissions().mode() & 0o777;
        if mode & 0o077 != 0 {
            std::fs::set_permissions(d, std::fs::Permissions::from_mode(mode & 0o700))?;
        }
    }
    Ok(())
}

/// Write one of the editor's private files whole (the credentials file, the cameras this computer trusts, the
/// preferences, the journal of unsaved edits), readable by this user only (mode 600 from the start on Unix and macOS)
/// in a folder only this user may open (`private_dir`): a temporary file beside it, renamed over it.
pub(crate) fn write_private(p: &Path, contents: impl AsRef<[u8]>) -> std::io::Result<()> {
    use std::io::Write;
    if let Some(d) = p.parent() { private_dir(d)?; }
    // a temporary file of this write's own, so two writes at once never write into one
    static WRITES: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let n = WRITES.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let tmp = p.with_file_name(format!(".{}.{}-{n}.part", p.file_name().unwrap_or_default().to_string_lossy(), std::process::id()));
    let mut o = std::fs::OpenOptions::new();
    o.write(true).create(true).truncate(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        o.mode(0o600);
    }
    let written = o.open(&tmp).and_then(|mut f| {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            f.set_permissions(std::fs::Permissions::from_mode(0o600))?;   // a leftover temporary file kept its mode
        }
        f.write_all(contents.as_ref())?;
        f.sync_all()
    });
    written.and_then(|_| std::fs::rename(&tmp, p)).inspect_err(|_| { let _ = std::fs::remove_file(&tmp); })?;
    sync_folder(p);
    Ok(())
}

/// Whether two paths name one file: the same path, or, both being there, the same file on the disk however it was
/// reached (a link, or on macOS and Windows another case of the same name, which name one file there).
pub(crate) fn same_file(a: &Path, b: &Path) -> bool {
    if a == b {
        return true;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if let (Ok(x), Ok(y)) = (std::fs::metadata(a), std::fs::metadata(b)) {
            return x.dev() == y.dev() && x.ino() == y.ino();
        }
    }
    matches!((std::fs::canonicalize(a), std::fs::canonicalize(b)), (Ok(x), Ok(y)) if x == y)
}

/// FNV-1a 64 of a file's bytes: names a kept original by its content.
pub(crate) fn fnv1a(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf29ce484222325, |h, &b| (h ^ b as u64).wrapping_mul(0x100000001b3))
}

/// A copy of `bytes` in `dir`, named after `path` and the content's hash, written only when no copy of
/// that content is there yet: the copy's path.
pub(crate) fn keep_copy(dir: &Path, path: &Path, bytes: &[u8]) -> std::io::Result<PathBuf> {
    let hash = format!("{:016x}", fnv1a(bytes));
    if let Some(e) = std::fs::read_dir(dir).ok().and_then(|it| it.flatten().find(|e| e.file_name().to_string_lossy().contains(&hash))) {
        return Ok(e.path());
    }
    let stem: String = path.file_stem().unwrap_or_default().to_string_lossy().chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-').take(40).collect();
    std::fs::create_dir_all(dir)?;
    let copy = dir.join(format!("{stem}_{hash}.DAT"));
    write_atomic(&copy, bytes)?;
    Ok(copy)
}

/// Write a file whole or not at all: a temporary file beside it, read back and compared, then
/// renamed over the target, so a crash or a card pulled mid-save never leaves half a file. The temporary file's name
/// is this write's own (`part_name`), made new, never an existing file opened: two writes of one file at once (the
/// window and the page, two editors) each keep to their own, and a failed write removes its own and only its own.
pub(crate) fn write_atomic(p: &Path, bytes: &[u8]) -> std::io::Result<()> {
    use std::io::Write;
    let (tmp, file) = (0..100).find_map(|_| {
        let tmp = p.with_file_name(part_name(p));
        match std::fs::OpenOptions::new().write(true).create_new(true).open(&tmp) {
            Ok(f) => Some(Ok((tmp, f))),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => None,
            Err(e) => Some(Err(e)),
        }
    }).unwrap_or_else(|| Err(std::io::Error::other("no free name for the temporary file")))?;
    // flushed to the disk or card before it is renamed into place: a card pulled right after "Saved" holds the file
    let written = { let mut f = file; f.write_all(bytes).and_then(|_| f.sync_all()) };
    if let Err(e) = written {
        let _ = std::fs::remove_file(&tmp);
        return Err(e);
    }
    let back = std::fs::read(&tmp);
    if back.as_deref().ok() != Some(bytes) {
        let _ = std::fs::remove_file(&tmp);
        return Err(back.err().unwrap_or_else(|| std::io::Error::other("the file read back differs from what was written")));
    }
    std::fs::rename(&tmp, p).inspect_err(|_| { let _ = std::fs::remove_file(&tmp); })?;
    sync_folder(p);
    Ok(())
}

/// A name for one write's temporary file beside `p` (`write_atomic`): hidden, after the file's own name, then this
/// process and a count of its writes, so no two writes share one.
fn part_name(p: &Path) -> String {
    static WRITES: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    let n = WRITES.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    format!(".{}.{}-{n}.part", p.file_name().unwrap_or_default().to_string_lossy(), std::process::id())
}

/// After a rename into a folder: flush the folder too, so the new name is on the disk or card (Unix; elsewhere the
/// rename itself is enough).
fn sync_folder(p: &Path) {
    #[cfg(unix)]
    if let Some(d) = p.parent().filter(|d| !d.as_os_str().is_empty()) {
        if let Ok(f) = std::fs::File::open(d) { let _ = f.sync_all(); }
    }
    #[cfg(not(unix))]
    let _ = p;
}

/// The volumes a camera card may be mounted as: /Volumes/* on macOS, /media/$USER/*, /run/media/$USER/* and
/// /media/* on Linux, the drive letters D: to Z: on Windows.
fn card_volumes() -> Vec<PathBuf> {
    let mut roots: Vec<PathBuf> = Vec::new();
    if cfg!(target_os = "windows") {
        return (b'D'..=b'Z').map(|l| PathBuf::from(format!("{}:\\", l as char))).collect();
    }
    let mut parents = vec![PathBuf::from("/Volumes")];
    if let Some(user) = std::env::var_os("USER").or_else(|| std::env::var_os("LOGNAME")) {
        parents.push(PathBuf::from("/media").join(&user));
        parents.push(PathBuf::from("/run/media").join(&user));
    }
    parents.push(PathBuf::from("/media"));
    for p in parents {
        if let Ok(rd) = std::fs::read_dir(&p) {
            roots.extend(rd.flatten().map(|e| e.path()));
        }
    }
    roots
}

/// The settings folders (`rel`, e.g. PRIVATE/SONY/CAMSET) of the camera cards mounted now. On Windows the scan of D:
/// to Z: runs with the system's "There is no disk in the drive" dialog off (`without_drive_dialogs`): an empty card
/// reader is then a drive with no card, not a question in front of the person.
pub(crate) fn mounted_cards(rel: &str) -> Vec<PathBuf> {
    without_drive_dialogs(|| cards_under(&card_volumes(), rel))
}

/// Run `scan` with this thread's error mode set so that a drive with no disk in it fails quietly instead of asking the
/// person (SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX), and put the mode back as it was after, also when `scan`
/// panics. Only Windows asks; elsewhere `scan` just runs.
#[cfg(windows)]
pub(crate) fn without_drive_dialogs<T>(scan: impl FnOnce() -> T) -> T {
    // kernel32's SetThreadErrorMode (Windows 7 and later), declared here: no crate for one call
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn SetThreadErrorMode(new_mode: u32, old_mode: *mut u32) -> i32;
    }
    const SEM_FAILCRITICALERRORS: u32 = 0x0001;
    const SEM_NOOPENFILEERRORBOX: u32 = 0x8000;
    /// The mode found before the scan, put back when dropped.
    struct Restore(u32);
    impl Drop for Restore {
        fn drop(&mut self) {
            // SAFETY: a plain Win32 call; the old mode's pointer may be null
            unsafe { SetThreadErrorMode(self.0, std::ptr::null_mut()) };
        }
    }
    let mut old = 0u32;
    // SAFETY: `old` is a u32 the call writes the mode it replaces into
    let set = unsafe { SetThreadErrorMode(SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX, &mut old) } != 0;
    let _restore = if set { Some(Restore(old)) } else { None };
    scan()
}

/// Elsewhere than on Windows no dialog asks for a disk: the scan just runs.
#[cfg(not(windows))]
pub(crate) fn without_drive_dialogs<T>(scan: impl FnOnce() -> T) -> T {
    scan()
}

/// The folders `rel` that exist under any of `volumes`.
fn cards_under(volumes: &[PathBuf], rel: &str) -> Vec<PathBuf> {
    volumes.iter().map(|v| rel.split('/').filter(|p| !p.is_empty()).fold(v.clone(), |d, p| d.join(p))).filter(|d| d.is_dir()).collect()
}

/// How many settings files (named *.DAT and starting as one of `defs`' containers does, by their first bytes) a
/// folder holds.
pub(crate) fn settings_files_in(dir: &Path, defs: &Definitions) -> usize {
    use std::io::Read;
    let Ok(rd) = std::fs::read_dir(dir) else { return 0 };
    // as far as the furthest container's first bytes run (`Definitions::magic_len`), not the whole file
    let head_len = defs.magic_len().max(256) as u64;
    rd.flatten()
        .filter(|e| e.path().extension().is_some_and(|x| x.eq_ignore_ascii_case("dat")))
        .filter(|e| {
            let mut head = Vec::new();
            std::fs::File::open(e.path()).and_then(|f| f.take(head_len).read_to_end(&mut head)).is_ok() && defs.is_settings_file(&head)
        })
        .count()
}

/// Open a folder in the system file manager (Finder on macOS, Explorer on Windows, file manager on Linux).
pub(crate) fn open_in_file_manager(path: &Path) {
    #[cfg(target_os = "macos")]
    let cmd = "open";
    #[cfg(target_os = "windows")]
    let cmd = "explorer";
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let cmd = "xdg-open";

    // Explorer is a windowed program, so no console would show; it goes through `no_console` as every start does
    let _ = no_console(&mut std::process::Command::new(cmd)).arg(path).spawn();
}

/// A log of `max` bytes or more becomes <name>.1 (replacing the one before), so the next line starts a new one.
pub(crate) fn rotate_log(log: &Path, max: u64) {
    if std::fs::metadata(log).is_ok_and(|m| m.len() >= max) {
        let mut old = log.as_os_str().to_os_string();
        old.push(".1");
        let _ = std::fs::rename(log, old);
    }
}

#[cfg(test)]
pub(crate) mod backup_tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_backup_test_{name}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// A save writes the whole file over the old one and leaves no temporary file behind.
    #[test]
    fn write_whole() {
        let d = scratch("write");
        let f = d.join("CAMSET01.DAT");
        std::fs::write(&f, b"old").unwrap();
        write_atomic(&f, b"new contents").unwrap();
        assert_eq!(std::fs::read(&f).unwrap(), b"new contents");
        assert_eq!(std::fs::read_dir(&d).unwrap().count(), 1);
        let _ = std::fs::remove_dir_all(&d);
    }

    /// Each write has a temporary file of its own beside the target, never one already there: a temporary file another
    /// write left (an older editor's fixed name, say) is not touched, and a write that fails removes its own and only
    /// its own.
    #[test]
    fn each_write_has_a_temporary_file_of_its_own() {
        let d = scratch("parts");
        let f = d.join("CAMSET01.DAT");
        let stale = d.join(".CAMSET01.DAT.part");
        std::fs::write(&stale, b"another write's").unwrap();
        assert_ne!(part_name(&f), part_name(&f), "one name per write");
        write_atomic(&f, b"first").unwrap();
        write_atomic(&f, b"second").unwrap();
        assert_eq!(std::fs::read(&f).unwrap(), b"second");
        assert_eq!(std::fs::read(&stale).unwrap(), b"another write's", "left as it was");
        let names = |d: &Path| { let mut v: Vec<String> = std::fs::read_dir(d).unwrap().flatten().map(|e| e.file_name().to_string_lossy().to_string()).collect(); v.sort(); v };
        assert_eq!(names(&d), vec![".CAMSET01.DAT.part".to_string(), "CAMSET01.DAT".to_string()]);
        // a target that is a folder: the rename fails, and the write's own temporary file goes with it
        let folder = d.join("CAMSET02.DAT");
        std::fs::create_dir(&folder).unwrap();
        std::fs::write(folder.join("inside"), b"x").unwrap();
        assert!(write_atomic(&folder, b"third").is_err());
        assert_eq!(names(&d), vec![".CAMSET01.DAT.part".to_string(), "CAMSET01.DAT".to_string(), "CAMSET02.DAT".to_string()]);
        let _ = std::fs::remove_dir_all(&d);
    }

    /// An original is kept once per content, under its own name.
    #[test]
    fn originals_kept_once() {
        let d = scratch("keep");
        let a = keep_copy(&d, Path::new("/card/CAMSET01.DAT"), b"first").unwrap();
        assert_eq!(keep_copy(&d, Path::new("/other/CAMSET09.DAT"), b"first").unwrap(), a);
        let b = keep_copy(&d, Path::new("/card/CAMSET01.DAT"), b"second").unwrap();
        assert_ne!(a, b);
        assert!(a.file_name().unwrap().to_string_lossy().starts_with("CAMSET01_"));
        assert_eq!(std::fs::read(&a).unwrap(), b"first");
        assert_eq!(std::fs::read_dir(&d).unwrap().count(), 2);
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn clock_reading() {
        // U-31: times in words, the day left out when it is today
        assert_eq!(when_words_at("20261031_143205", "20261031_235959"), "14:32");
        assert_eq!(when_words_at("20260101_000000", "20261105_174400"), "1 Jan 2026 at 00:00");
        assert_eq!(when_words_at("20261231_235900", "20270101_000000"), "31 Dec 2026 at 23:59");
        for odd in ["garbage", "", "2026103_143205", "20261331_143205", "20261031-143205", "2026103é_143205", "20261031_2561"] {
            assert_eq!(when_words_at(odd, "20261031_120000"), odd, "shown as it is");
        }
        assert_eq!(stamp_in_words("20260101_000000", true), format!("{} (20260101_000000)", when_words("20260101_000000")));
        assert_eq!(stamp_in_words("garbage", true), "garbage");
        let f = file_stamp();
        assert!(f.len() == 19 && f.bytes().all(|c| c.is_ascii_digit() || c == b'-' || c == b'_'), "{f}");
        assert_eq!(stamp_of(std::time::SystemTime::now()).len(), 15);
    }
}

#[cfg(test)]
pub(crate) mod card_tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_card_test_{}_{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    /// A card is found by its settings folder under a mounted volume; a volume without one is not a card.
    #[test]
    fn cards_found_by_their_settings_folder() {
        let root = scratch("volumes");
        let (card, other) = (root.join("CARD_A"), root.join("USB_STICK"));
        std::fs::create_dir_all(card.join("PRIVATE").join("SONY").join("CAMSET")).unwrap();
        std::fs::create_dir_all(&other).unwrap();
        let found = cards_under(&[card.clone(), other], "PRIVATE/SONY/CAMSET");
        assert_eq!(found, vec![card.join("PRIVATE").join("SONY").join("CAMSET")]);
        let _ = std::fs::remove_dir_all(&root);
    }

    /// Save As offers the next free name the camera gives its files, and counts only settings files.
    #[test]
    fn next_free_name_and_count() {
        let app = App::new(vec![], Prefs::default());
        let dir = scratch("names");
        assert_eq!(app.card_folder(), "PRIVATE/SONY/CAMSET");
        assert_eq!(app.free_card_name(&dir).as_deref(), Some("CAMSET01.DAT"));
        let sample = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        std::fs::write(dir.join("CAMSET01.DAT"), sample).unwrap();
        std::fs::write(dir.join("camset02.dat"), sample).unwrap();
        std::fs::write(dir.join("NOTES.DAT"), b"not a settings file").unwrap();
        assert_eq!(app.free_card_name(&dir).as_deref(), Some("CAMSET03.DAT"));
        assert_eq!(settings_files_in(&dir, &app.defs), 2);
        // a camera read or a kept copy is never the folder Save As starts in
        let kept = DialogKind::SaveAs(App::camera_dir().join("camera_20260101_000000.DAT"));
        assert!(app.start_dir(&kept).is_none_or(|d| !d.starts_with(App::camera_dir())));
        assert_eq!(app.start_dir(&DialogKind::SaveAs(dir.join("CAMSET01.DAT"))), Some(dir.clone()));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The card scan runs inside `without_drive_dialogs`, which gives back what the scan found and lets a panic
    /// through. On Windows (the owner's run: this computer cannot) the thread's error mode holds both flags during the
    /// scan and is the one from before after it, also after a panic.
    #[test]
    fn the_card_scan_asks_for_no_disk() {
        #[cfg(windows)]
        unsafe extern "system" {
            fn GetThreadErrorMode() -> u32;
        }
        // SAFETY: a plain Win32 call with no arguments
        #[cfg(windows)]
        let mode = || unsafe { GetThreadErrorMode() };
        #[cfg(not(windows))]
        let mode = || 0u32;
        let before = mode();
        let during = without_drive_dialogs(mode);
        if cfg!(windows) {
            assert_eq!(during & 0x8001, 0x8001, "SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX during the scan");
        }
        assert_eq!(mode(), before, "put back after it");
        assert!(std::panic::catch_unwind(|| without_drive_dialogs(|| panic!("a scan that fails"))).is_err());
        assert_eq!(mode(), before, "put back after a panic too");
        assert_eq!(without_drive_dialogs(|| mounted_cards("NO/SUCH/FOLDER/FOR/A/TEST")), Vec::<PathBuf>::new());
    }
}
