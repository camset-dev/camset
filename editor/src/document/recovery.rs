//! Crash recovery: while the open file has edits that are not saved, a copy of the edited file is kept in
//! `<config>/recovery/` (a journal), so a crash, a power cut or a forced quit does not lose them. It is written a
//! couple of seconds after an edit (not on every frame of a drag), on a helper thread, whole and private (as the
//! preferences are: `write_private`), and removed once the edits are saved, the file is closed or the editor quits
//! as it should. At the next start the editor offers what it finds: "The editor closed with N unsaved edits to …".
//!
//! A journal is three files named `<file stem>_<time>`: `.DAT`, the edited file's bytes; `.original.DAT`, the file as
//! it was opened (or last saved), so the edits show as edits again; `.json`, what they are (`Meta`), written last, so
//! a journal with its `.json` always has its bytes. A fourth, `.baseline.DAT`, is there while the file as first opened
//! or read in that session is not the file as last saved (a Save As came between): what the edits are judged against
//! once recovered, as they were before.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

/// How long after an edit the journal is written: edits made meanwhile go into the same write.
pub const WAIT: Duration = Duration::from_secs(2);

/// What a journal says about the edits it keeps (its `.json`).
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Meta {
    /// The file the edits were made to, as the editor named it: its path (the sample's own name for the sample).
    pub source: String,
    /// Where that file came from: "disk", "sample", or "camera" (with the link and the time of the read).
    pub kind: String,
    pub link: String,
    pub read_at: String,
    /// The file was one the editor had saved (Save As), so saving over it again is allowed.
    pub saved: bool,
    /// Editing was turned on for a file from a firmware its definition was not checked on ("Edit anyway…").
    pub edit_anyway: bool,
    /// The definition it was read with, in words ("ILCE-1M2 firmware 4.00"), and that definition's file.
    pub definition: String,
    pub definition_file: String,
    /// When the journal was last written (local YYYYMMDD_HHMMSS) and how many edits it holds.
    pub time: String,
    pub edits: usize,
    /// The editor that wrote it (its process id): a journal of an editor still running is not offered to another.
    pub pid: u32,
}

/// A journal found in the folder.
#[derive(Clone, Debug)]
pub struct Found {
    /// Its name (`<file stem>_<time>`), and what it says.
    pub base: String,
    pub meta: Meta,
}

impl Found {
    /// The file name the edits were made to ("CAMSET01.DAT").
    pub fn name(&self) -> String {
        let p = Path::new(&self.meta.source);
        p.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_else(|| self.meta.source.clone())
    }
}

/// The edited file's bytes, the file as opened, and the description, for a journal named `base` in `dir`.
pub fn paths(dir: &Path, base: &str) -> [PathBuf; 3] {
    [dir.join(format!("{base}.DAT")), dir.join(format!("{base}.original.DAT")), dir.join(format!("{base}.json"))]
}

/// A journal's name for the file at `source`: its stem (letters, digits, - and _ only, at most 40) and the time of
/// the first write ("CAMSET01_2026-11-06_07-30-00").
pub fn base_for(source: &Path, stamp: &str) -> String {
    let stem: String = source.file_stem().unwrap_or_default().to_string_lossy().chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-').take(40).collect();
    let stem = if stem.is_empty() { "edits".to_string() } else { stem };
    format!("{stem}_{stamp}")
}

/// Write a journal: the edited bytes, the file as opened (when given: it changes only when the file is saved) with
/// the file as first opened in the session beside it when that is another (`baseline`; its file removed when it is
/// the same), then the description. Each file whole (a temporary file renamed into place) and readable by this user
/// only.
pub fn write(dir: &Path, base: &str, edited: &[u8], original: Option<(&[u8], Option<&[u8]>)>, meta: &Meta) -> std::io::Result<()> {
    let [dat, orig, json] = paths(dir, base);
    crate::write_private(&dat, edited)?;
    if let Some((o, first)) = original {
        crate::write_private(&orig, o)?;
        match first {
            Some(b) => crate::write_private(&baseline_path(dir, base), b)?,
            None => { let _ = std::fs::remove_file(baseline_path(dir, base)); }
        }
    }
    let text = serde_json::to_string_pretty(meta).map_err(std::io::Error::other)?;
    crate::write_private(&json, text)
}

/// Where a journal keeps the file as first opened or read in its session, while that is not the file as last saved.
pub fn baseline_path(dir: &Path, base: &str) -> PathBuf {
    dir.join(format!("{base}.baseline.DAT"))
}

/// Remove a journal's files (those that are there).
pub fn remove(dir: &Path, base: &str) {
    for p in paths(dir, base).into_iter().chain([baseline_path(dir, base)]) {
        let _ = std::fs::remove_file(p);
    }
}

/// The journals in `dir` to offer, newest first: each with its description and its edited bytes, of an editor no
/// longer running (`running`, given its process id). One without its bytes, or whose description does not read, is
/// left where it is and not offered.
pub fn list(dir: &Path, running: &dyn Fn(u32) -> bool) -> Vec<Found> {
    let Ok(rd) = std::fs::read_dir(dir) else { return Vec::new() };
    let mut out: Vec<Found> = rd.flatten().filter_map(|e| {
        let name = e.file_name().to_string_lossy().to_string();
        let base = name.strip_suffix(".json")?.to_string();
        let meta: Meta = serde_json::from_str(&std::fs::read_to_string(e.path()).ok()?).ok()?;
        let [dat, ..] = paths(dir, &base);
        (dat.is_file() && !running(meta.pid)).then_some(Found { base, meta })
    }).collect();
    out.sort_by(|a, b| b.meta.time.cmp(&a.meta.time).then_with(|| b.base.cmp(&a.base)));
    out
}

/// Whether another editor with process id `pid` is still running: on Unix and macOS by asking the system (a signal
/// 0, which sends nothing); this editor's own id, and anywhere the system cannot be asked, counts as not running.
pub fn running(pid: u32) -> bool {
    pid != 0 && pid != std::process::id() && alive(pid)
}

#[cfg(unix)]
fn alive(pid: u32) -> bool {
    let Ok(p) = libc::pid_t::try_from(pid) else { return false };
    // 0: there is such a process; EPERM: there is, owned by another user
    let r = unsafe { libc::kill(p, 0) };
    r == 0 || std::io::Error::last_os_error().raw_os_error() == Some(libc::EPERM)
}

#[cfg(not(unix))]
fn alive(_pid: u32) -> bool {
    false
}

/// What the journal is to do on this frame (`Journal::step`).
#[derive(Debug, PartialEq)]
pub enum Step {
    /// Nothing: no edits, or the journal holds them as they are.
    Idle,
    /// Edits not in the journal yet: written once this much more time has passed.
    Wait(Duration),
    /// Write it now (`Journal::write`).
    Write,
}

/// One write or removal for the helper thread, done in the order sent.
enum Job {
    Write { dir: PathBuf, base: String, edited: Vec<u8>, original: Option<(Vec<u8>, Option<Vec<u8>>)>, meta: Box<Meta> },
    Remove { dir: PathBuf, base: String },
}

/// The journal of the open file's unsaved edits, and the helper thread that writes it.
pub struct Journal {
    /// The folder the journals are kept in.
    pub dir: PathBuf,
    /// The journal kept now (its name), while there is one.
    base: Option<String>,
    /// The opening of the file it belongs to (`Doc::opened`), the state of the file it holds (`Doc::rev`), and the
    /// state of the file as opened it holds (a hash: written again only when the file is saved).
    opened: u64,
    written: u64,
    original: Option<u64>,
    /// When edits not written yet were first seen.
    since: Option<Instant>,
    /// The state of the file last asked about, and whether it had edits (worked out once per state).
    pub seen: Option<((u64, u64), bool)>,
    tx: Option<std::sync::mpsc::Sender<Job>>,
    worker: Option<std::thread::JoinHandle<()>>,
}

impl Journal {
    pub fn new(dir: PathBuf) -> Journal {
        Journal { dir, base: None, opened: 0, written: 0, original: None, since: None, seen: None, tx: None, worker: None }
    }

    /// The journal kept now, if any.
    #[cfg(test)]
    pub fn base(&self) -> Option<&str> {
        self.base.as_deref()
    }

    /// What to do on this frame, `now`, for the open file: `state` is (its opening, its state) while it has edits not
    /// saved, else None. Without edits the journal is removed; another file's journal gives way to this one's; edits
    /// not written yet are written `WAIT` after they were first seen.
    pub fn step(&mut self, now: Instant, state: Option<(u64, u64)>) -> Step {
        let Some((opened, rev)) = state else {
            self.drop_journal();
            self.since = None;
            return Step::Idle;
        };
        if opened != self.opened {
            self.drop_journal();
            self.opened = opened;
            self.written = 0;
            self.since = None;
        }
        if self.written == rev {
            return Step::Idle;
        }
        let since = *self.since.get_or_insert(now);
        match (since + WAIT).checked_duration_since(now) {
            Some(left) if !left.is_zero() => Step::Wait(left),
            _ => Step::Write,
        }
    }

    /// Write the journal for state `rev` of the file at `source` (named the first time: `base_for`), on the helper
    /// thread: the edited bytes, the file as opened, with the file as first opened in the session when that is another
    /// (`original`), when given and not in the journal yet (none for recovered edits whose file as opened was not kept),
    /// and the description.
    pub fn write(&mut self, rev: u64, source: &Path, stamp: &str, edited: Vec<u8>, original: Option<(&[u8], Option<&[u8]>)>, meta: Meta) {
        let base = self.base.get_or_insert_with(|| base_for(source, stamp)).clone();
        let hash = original.map(|(o, first)| crate::fnv1a(o) ^ first.map_or(0, |b| crate::fnv1a(b).rotate_left(1)));
        let original = original.filter(|_| hash != self.original).map(|(o, first)| (o.to_vec(), first.map(<[u8]>::to_vec)));
        self.original = hash;
        self.written = rev;
        self.since = None;
        self.send(Job::Write { dir: self.dir.clone(), base, edited, original, meta: Box::new(meta) });
    }

    /// Take over a journal found at start (`base`) for the file now open from it (`opened`): written again on the next
    /// step, with this editor's description.
    pub fn adopt(&mut self, base: String, opened: u64) {
        self.drop_journal();
        self.base = Some(base);
        self.opened = opened;
        self.written = 0;
        self.original = None;
        // due at once (a clock started less than `WAIT` ago, just after the computer started, cannot go back that far)
        let now = Instant::now();
        self.since = Some(now.checked_sub(WAIT).unwrap_or(now));
    }

    /// Remove the journal kept now (on the helper thread, after any write sent before).
    fn drop_journal(&mut self) {
        self.original = None;
        if let Some(base) = self.base.take() {
            self.send(Job::Remove { dir: self.dir.clone(), base });
        }
    }

    /// The editor quits as it should: the journal is removed, and every write and removal sent is done before this
    /// returns.
    pub fn close(&mut self) {
        self.drop_journal();
        self.finish();
    }

    /// Wait for the helper thread to do everything sent so far (the next job starts it again).
    pub fn finish(&mut self) {
        self.tx = None;
        if let Some(w) = self.worker.take() {
            let _ = w.join();
        }
    }

    fn send(&mut self, job: Job) {
        if self.tx.is_none() {
            let (tx, rx) = std::sync::mpsc::channel::<Job>();
            let worker = std::thread::Builder::new().name("recovery journal".into()).spawn(move || {
                for job in rx {
                    match job {
                        Job::Write { dir, base, edited, original, meta } => {
                            let _ = write(&dir, &base, &edited, original.as_ref().map(|(o, b)| (o.as_slice(), b.as_deref())), &meta);
                        }
                        Job::Remove { dir, base } => remove(&dir, &base),
                    }
                }
            });
            match worker {
                Ok(w) => {
                    self.tx = Some(tx);
                    self.worker = Some(w);
                }
                // no thread to be had: done here and now
                Err(_) => {
                    match job {
                        Job::Write { dir, base, edited, original, meta } => { let _ = write(&dir, &base, &edited, original.as_ref().map(|(o, b)| (o.as_slice(), b.as_deref())), &meta); }
                        Job::Remove { dir, base } => remove(&dir, &base),
                    }
                    return;
                }
            }
        }
        if let Some(tx) = &self.tx {
            let _ = tx.send(job);
        }
    }
}

/// Set when the editor has stopped on an error (`crash_hook`): its journal stays for the next start, even if the
/// window still gets to close.
pub static CRASHED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Keep a short log at `log` when the editor stops on an error, and leave the journal for the next start; then the
/// usual message on the terminal.
pub fn crash_hook(log: PathBuf, version: String) {
    let default = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let window = std::thread::current().name() == Some("main");
        if window {
            CRASHED.store(true, std::sync::atomic::Ordering::SeqCst);
        }
        let place = info.location().map(|l| format!("{} line {}", tidy(l.file()), l.line())).unwrap_or_default();
        let what = info.payload().downcast_ref::<&str>().map(|s| s.to_string())
            .or_else(|| info.payload().downcast_ref::<String>().cloned()).unwrap_or_default();
        let _ = crate::write_private(&log, crash_text(&version, &crate::local_stamp(), window, &place, &what, &home_words()));
        default(info);
    }));
}

/// The home folder and the user's name, as they could appear in a message: left out of the log.
fn home_words() -> Vec<String> {
    ["HOME", "USERPROFILE", "USER", "USERNAME", "LOGNAME"].iter()
        .filter_map(|k| std::env::var(k).ok()).map(|v| v.trim().to_string()).filter(|v| v.len() >= 3).collect()
}

/// A source file's place as the log gives it: from the crate's folder on ("egui-0.31.1/src/context.rs",
/// "src/main.rs"), not the folders of the computer it was built on.
fn tidy(file: &str) -> String {
    let f = file.replace('\\', "/");
    if let Some(i) = f.find("/registry/src/") {
        let rest = &f[i + "/registry/src/".len()..];
        return rest.split_once('/').map_or(rest, |(_, r)| r).to_string();
    }
    match f.rfind("/src/") {
        Some(i) => f[i + 1..].to_string(),
        None => f,
    }
}

/// The crash log: what stopped, where and when, in plain words, with what the person can do. No settings, no camera
/// and no file of theirs: the message is cut short, and the home folder and the user's name (`private`) are taken out.
pub fn crash_text(version: &str, stamp: &str, window: bool, place: &str, what: &str, private: &[String]) -> String {
    // the home folder and the user's name out first, then cut short: cut first, a name the cut runs through would
    // keep its first letters
    let mut what = what.to_string();
    for p in private {
        what = what.replace(p.as_str(), "…");
    }
    let what: String = what.chars().map(|c| if c.is_control() { ' ' } else { c }).take(300).collect();
    let when = crate::when_words_at(stamp, "");
    let who = if window { "Camset Editor stopped" } else { "A helper task of Camset Editor stopped" };
    let place = if place.is_empty() { "not known".to_string() } else { place.to_string() };
    format!("{who} on an error on {when}.\n\
        Version: {version}\n\
        Where: {place}\n\
        What: {what}\n\
        \n\
        Edits that were not saved are kept: the editor offers them when it starts again.\n\
        To report this, send this file with a few words on what you were doing. It holds the lines above only:\n\
        no settings, no camera details and no file names of yours.\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("camset_recovery_{name}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    fn meta(source: &str, time: &str, pid: u32) -> Meta {
        Meta { source: source.into(), kind: "disk".into(), definition: "ILCE-0000 firmware 1.00".into(), time: time.into(), edits: 3, pid, ..Meta::default() }
    }

    /// A journal written is found again with what it said and its bytes; written whole and private; removed whole.
    #[test]
    fn journal_round_trip() {
        let dir = scratch("round");
        let never = |_: u32| false;
        let base = base_for(Path::new("/media/card/PRIVATE/CAMSET01.DAT"), "2026-01-02_03-04-05");
        assert_eq!(base, "CAMSET01_2026-01-02_03-04-05");
        let m = meta("/media/card/PRIVATE/CAMSET01.DAT", "20260102_030405", 0);
        write(&dir, &base, b"edited bytes", Some((b"original bytes".as_slice(), None)), &m).unwrap();
        let found = list(&dir, &never);
        assert_eq!(found.len(), 1);
        assert_eq!((found[0].base.as_str(), &found[0].meta, found[0].name().as_str()), (base.as_str(), &m, "CAMSET01.DAT"));
        let [dat, orig, json] = paths(&dir, &base);
        assert_eq!(std::fs::read(&dat).unwrap(), b"edited bytes");
        assert_eq!(std::fs::read(&orig).unwrap(), b"original bytes");
        assert!(json.is_file(), "the description is written beside the bytes: {}", json.display());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            for p in [&dat, &orig, &json] {
                assert_eq!(std::fs::metadata(p).unwrap().permissions().mode() & 0o777, 0o600, "{}", p.display());
            }
            assert_eq!(std::fs::metadata(&dir).unwrap().permissions().mode() & 0o077, 0);
        }
        // written again without the original: the one there stays; no temporary file is left behind
        write(&dir, &base, b"edited again", None, &m).unwrap();
        assert_eq!(std::fs::read(&orig).unwrap(), b"original bytes");
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 3);
        // a second, newer journal comes first; one of an editor still running is not offered
        let newer = base_for(Path::new("CAMSET02.DAT"), "2026-01-03_00-00-00");
        write(&dir, &newer, b"x", None, &meta("CAMSET02.DAT", "20260103_000000", 4242)).unwrap();
        let names: Vec<String> = list(&dir, &never).into_iter().map(|f| f.base).collect();
        assert_eq!(names, [newer.clone(), base.clone()]);
        assert_eq!(list(&dir, &|pid| pid == 4242).len(), 1);
        // a description without its bytes, or one that does not read, is not offered
        std::fs::remove_file(&dat).unwrap();
        std::fs::write(dir.join("broken.json"), "{not json").unwrap();
        std::fs::write(dir.join("broken.DAT"), "x").unwrap();
        assert_eq!(list(&dir, &never).len(), 1);
        remove(&dir, &newer);
        remove(&dir, &base);
        assert!(paths(&dir, &newer).iter().chain(paths(&dir, &base).iter()).all(|p| !p.exists()));
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Written a little after the first edit not yet in it, with the edits made meanwhile; removed when the edits are
    /// gone (saved, undone, the file closed) or another file opens; on the helper thread, in the order asked.
    #[test]
    fn written_after_a_wait_and_removed_with_the_edits() {
        let dir = scratch("steps");
        let mut j = Journal::new(dir.clone());
        let t0 = Instant::now();
        assert_eq!(j.step(t0, None), Step::Idle);
        assert!(matches!(j.step(t0, Some((1, 10))), Step::Wait(_)));
        // more edits within the wait: still the same wait, counted from the first
        assert_eq!(j.step(t0 + Duration::from_millis(1500), Some((1, 11))), Step::Wait(Duration::from_millis(500)));
        assert_eq!(j.step(t0 + WAIT, Some((1, 11))), Step::Write);
        j.write(11, Path::new("/x/CAMSET01.DAT"), "2026-01-02_03-04-05", b"v11".to_vec(), Some((b"orig".as_slice(), None)), meta("/x/CAMSET01.DAT", "20260102_030405", 0));
        assert_eq!(j.step(t0 + WAIT, Some((1, 11))), Step::Idle);
        j.finish();
        let base = j.base().unwrap().to_string();
        assert_eq!(std::fs::read(&paths(&dir, &base)[0]).unwrap(), b"v11");
        // the next edit: written again, the original not again
        assert!(matches!(j.step(t0 + WAIT * 2, Some((1, 12))), Step::Wait(_)));
        assert_eq!(j.step(t0 + WAIT * 3, Some((1, 12))), Step::Write);
        std::fs::remove_file(&paths(&dir, &base)[1]).unwrap();
        j.write(12, Path::new("/x/CAMSET01.DAT"), "later", b"v12".to_vec(), Some((b"orig".as_slice(), None)), meta("/x/CAMSET01.DAT", "20260102_030409", 0));
        j.finish();
        assert_eq!(j.base(), Some(base.as_str()), "the same journal");
        assert_eq!(std::fs::read(&paths(&dir, &base)[0]).unwrap(), b"v12");
        assert!(!paths(&dir, &base)[1].exists());
        // another file opened: the first one's journal goes
        assert!(matches!(j.step(t0 + WAIT * 3, Some((2, 20))), Step::Wait(_)));
        j.finish();
        assert!(j.base().is_none() && !paths(&dir, &base)[2].exists());
        // no edits any more: nothing to write, nothing kept
        assert_eq!(j.step(t0 + WAIT * 5, Some((2, 21))), Step::Write);
        j.write(21, Path::new("/x/CAMSET02.DAT"), "s", b"v21".to_vec(), Some((b"o2".as_slice(), None)), meta("/x/CAMSET02.DAT", "20260102_030500", 0));
        assert_eq!(j.step(t0 + WAIT * 5, None), Step::Idle);
        j.finish();
        assert_eq!(std::fs::read_dir(&dir).map(|d| d.count()).unwrap_or(0), 0);
        // a clean quit removes it too
        assert_eq!(j.step(t0 + WAIT * 8, Some((3, 30))), Step::Wait(WAIT));
        assert_eq!(j.step(t0 + WAIT * 9, Some((3, 30))), Step::Write);
        j.write(30, Path::new("/x/A.DAT"), "s", b"v".to_vec(), Some((b"o".as_slice(), None)), meta("/x/A.DAT", "20260102_030600", 0));
        j.close();
        assert_eq!(std::fs::read_dir(&dir).map(|d| d.count()).unwrap_or(0), 0);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The crash log: plain words, where in the source and not on whose computer, the message cut short and without
    /// the home folder or the user's name.
    #[test]
    fn crash_log_in_plain_words() {
        assert_eq!(tidy("/home/user/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/egui-0.31.1/src/context.rs"), "egui-0.31.1/src/context.rs");
        assert_eq!(tidy("C:\\Users\\user\\camset\\editor\\src\\main.rs"), "src/main.rs");
        assert_eq!(tidy("src/main.rs"), "src/main.rs");
        let long = "x".repeat(1000);
        let t = crash_text("0.1.0 (build abc1234)", "20260102_030405", true, "src/main.rs line 12", &format!("no file at /home/user/cards/A.DAT\n{long}"), &["/home/user".into(), "user".into()]);
        assert!(t.starts_with("Camset Editor stopped on an error on 2 Jan 2026 at 03:04."), "{t}");
        assert!(t.contains("Version: 0.1.0 (build abc1234)") && t.contains("Where: src/main.rs line 12") && t.contains("offers them when it starts again"));
        assert!(!t.contains("/home/user") && t.contains("What: no file at …/cards/A.DAT"));
        assert!(t.len() < 1000, "cut short");
        // a home folder the cut would run through: taken out whole, never its first letters
        let at_the_cut = format!("{}/home/user/cards", "x".repeat(293));
        let t = crash_text("0.1.0", "20260102_030405", true, "", &at_the_cut, &["/home/user".into()]);
        // no part of the folder left: not even "/home" with the first letters of the name after it
        assert!(!t.contains("/home") && t.contains("…/cards"), "{t}");
        let helper = crash_text("0.1.0", "20260102_030405", false, "", "", &[]);
        assert!(helper.starts_with("A helper task of Camset Editor stopped") && helper.contains("Where: not known"));
    }
}
