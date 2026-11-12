//! A camera job: the camera link program (camset_probe) run on a helper thread to read the camera, write a file
//! to it, read it back after the write, or search for cameras; and the checks a write passes before anything is
//! sent. What the window makes of the outcome is in `report`.

use crate::*;

/// A download from or upload to the camera running on another thread.
pub(crate) struct CameraJob {
    pub(crate) kind: JobKind,
    pub(crate) started: std::time::Instant,
    /// What the job's thread hands back once it is done.
    pub(crate) result: std::sync::Arc<std::sync::Mutex<Option<JobDone>>>,
    /// A write: the copy of the camera's settings read just before anything is written.
    pub(crate) backup: Option<PathBuf>,
    /// A read the person agreed may replace their unsaved edits: those edits (`edits_hash`). The read opens over
    /// them only while they are still the same; edits made during the read are asked about first.
    pub(crate) agreed: Option<u64>,
    /// A read the person asked to see beside their edits: it opens as file B, not over file A.
    pub(crate) as_b: bool,
    /// How long the camera link usually takes with this body (`App::job_timing`: the definition's `link_timing`, its
    /// read as this computer has timed it). A read-back tried again has a restart of 0: the camera restarted long ago.
    pub(crate) timing: LinkTiming,
}

/// How many of the last reads `Prefs::read_times` keeps per link.
pub(crate) const READ_TIMES_KEPT: usize = 5;

/// The median of the reads timed (`Prefs::read_times`), in whole seconds and at least 1; None before the first.
pub(crate) fn median_secs(times: &[f32]) -> Option<u32> {
    let mut v: Vec<f32> = times.iter().copied().filter(|t| t.is_finite() && *t > 0.0).collect();
    if v.is_empty() { return None; }
    v.sort_by(f32::total_cmp);
    let n = v.len();
    let m = if n % 2 == 1 { v[n / 2] } else { (v[n / 2 - 1] + v[n / 2]) / 2.0 };
    Some((m.round() as u32).max(1))
}

/// How long a search for cameras usually takes: the search's progress line and its button's hover say it.
pub(crate) const SEARCH_TIME: &str = "5 to 15 seconds";

/// The hover of 🔍 Search for cameras, the window's and the page's.
pub(crate) fn search_tip() -> String {
    format!("Looks for every camera this computer can reach: USB ones in PC Remote mode and network ones with remote control on (about {SEARCH_TIME})")
}

/// The read-back after a write, as a schedule: when its next try starts, in seconds after the upload ended, or None
/// when it gives up. `now`: seconds since the upload ended; `last`: when the last try began (it failed), None before
/// the first. The camera is usually back `restart_s` after the upload, so the first try starts then; the next starts
/// once `poll_s` has passed since the failed one began, at once when that try took longer itself; none starts once
/// `timeout_s` has passed (the first always does, at the latest then).
pub(crate) fn read_back_at(t: &LinkTiming, now: f32, last: Option<f32>) -> Option<f32> {
    let give_up = t.timeout_s as f32;
    match last {
        None => Some((t.restart_s as f32).min(give_up).max(now)),
        Some(began) => Some((began + t.poll_s.max(1) as f32).max(now)).filter(|at| *at < give_up),
    }
}

/// How long to leave the camera on after a write, in the Write window and the write's progress: until the check
/// after its restart has finished, which is the restart and then the usual read, counted from when it takes the file.
pub(crate) fn check_words(t: &LinkTiming) -> String {
    format!("Leave the camera on and connected until the check after the restart has finished, about {} after it takes the file", duration_words(t.restart_s + t.read_s))
}

/// A camera job's outcome: Ok, the file it produced (a read: the download; a write: the file sent) and the
/// helper's whole output; Err, that output. A write also says how it ended.
pub(crate) struct JobDone {
    pub(crate) res: Result<(PathBuf, String), String>,
    pub(crate) wrote: Option<Wrote>,
    /// A read (Read, BeforeWrite) that brought its file back: the link it went over ("usb", "network") and how long
    /// the helper took, in seconds, for `Prefs::read_times`.
    pub(crate) took: Option<(&'static str, f32)>,
}

/// How a write ended.
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum Wrote {
    /// The helper printed "Upload accepted." and ended without an error: the camera took the file.
    Confirmed,
    /// The upload ended with an error: the camera did not take the file.
    Refused,
    /// Anything else (no confirmation within the helper's wait, or the helper was stopped): the camera may have
    /// taken the file.
    Unconfirmed,
    /// The camera could not be read first, or its copy came back incomplete: nothing was sent.
    NotRead,
    /// The camera's copy is from another model, or its records are laid out differently from the file's (another
    /// firmware), or it was saved under another video system than the file: nothing was sent. The reason, in plain
    /// words.
    Mismatch(String),
}

/// The exit code the camera job gives a helper that could not be started at all (as a shell does).
pub(crate) const NOT_RUN: i32 = 127;

/// How many times the link's longest step one run of the camera link program may take (`helper_limit`), and the
/// least it is ever given, in seconds.
const HELPER_LIMIT_TIMES: u64 = 2;
const HELPER_LIMIT_MIN_S: u64 = 60;

/// How long one run of the camera link program may take before the camera job stops it (`run_helper`): twice the
/// longest step of the camera's link timing, which is the write's read-back window (`timeout_s`), and never less than
/// a minute. The helper gives up on its own well before that (kit/common/sdk_session.h waits a minute for a download
/// and two for an upload), so only a helper that hangs reaches it.
pub(crate) fn helper_limit(t: &LinkTiming) -> std::time::Duration {
    let longest = t.read_s.max(t.restart_s).max(t.poll_s).max(t.timeout_s);
    std::time::Duration::from_secs((u64::from(longest) * HELPER_LIMIT_TIMES).max(HELPER_LIMIT_MIN_S))
}

#[cfg(test)]
thread_local! {
    /// Under test: the limit for the camera jobs this thread starts, in place of `helper_limit`'s (a minute at the
    /// least), so a test of a helper that hangs ends in seconds.
    pub(crate) static TEST_HELPER_LIMIT: std::cell::Cell<Option<std::time::Duration>> = const { std::cell::Cell::new(None) };
}

/// How often `run_helper` looks whether the helper has ended, and how long it waits for what is still in the pipes
/// once it has.
const HELPER_POLL: std::time::Duration = std::time::Duration::from_millis(50);
const HELPER_GRACE: std::time::Duration = std::time::Duration::from_secs(2);

/// The line `run_helper` adds to the output of a helper it stopped, before the limit in whole seconds: the camera
/// report finds it (`helper_timeout`) and says what happened in plain words; the line itself shows in Expert mode.
pub(crate) const HELPER_TIMEOUT: &str = "editor: no answer from the camera link program within ";

/// `cmd`, set to start without a console window of its own. On Windows the released editor has no console (main.rs),
/// so a console program it starts, such as the camera link program, would get a new console window that shows for as
/// long as it runs: a window that flashes up on every search, read and write. CREATE_NO_WINDOW starts it without one;
/// what it prints still reaches the editor through the pipes `run_helper` gives it, and it can still be stopped. A
/// windowed program it is given to starts as before. Elsewhere it changes nothing. Every program the editor starts goes
/// through it (the test `every_program_started_has_no_console_window` holds to that).
pub(crate) fn no_console(cmd: &mut std::process::Command) -> &mut std::process::Command {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

/// Run the camera link program as `cmd` says: its exit code (None when it was stopped) and its output, standard
/// output then standard error. Each stream is read on a thread of its own, so a helper that fills one never waits on
/// the other. A helper still running after `limit` is stopped (killed, then waited for), and the output it gave so far
/// ends with the `HELPER_TIMEOUT` line. Err: it could not be started.
pub(crate) fn run_helper(cmd: &mut std::process::Command, limit: std::time::Duration) -> std::io::Result<(Option<i32>, String)> {
    use std::process::Stdio;
    use std::sync::{mpsc, Arc, Mutex};
    /// Read `from` to its end on a thread of its own into the buffer returned, and say so on `done`.
    fn pump(from: Option<impl std::io::Read + Send + 'static>, done: &mpsc::Sender<()>) -> Arc<Mutex<Vec<u8>>> {
        let got = Arc::new(Mutex::new(Vec::new()));
        let (into, done) = (got.clone(), done.clone());
        std::thread::spawn(move || {
            if let Some(mut from) = from {
                let mut buf = [0u8; 8192];
                loop {
                    match from.read(&mut buf) {
                        Ok(0) => break,
                        Ok(n) => if let Ok(mut v) = into.lock() { v.extend_from_slice(&buf[..n]); },
                        Err(e) if e.kind() == std::io::ErrorKind::Interrupted => {}
                        Err(_) => break,
                    }
                }
            }
            let _ = done.send(());
        });
        got
    }
    let mut child = no_console(cmd).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()?;
    let (done_tx, done_rx) = mpsc::channel();
    let (out, err) = (pump(child.stdout.take(), &done_tx), pump(child.stderr.take(), &done_tx));
    drop(done_tx);
    let started = std::time::Instant::now();
    let (mut ended, mut timed_out) = (0, false);   // the streams that have ended; stopped at the limit
    let code = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status.code(),
            // a stream that ends wakes the loop at once (the helper is ending); else it looks again shortly
            Ok(None) if started.elapsed() < limit => match done_rx.recv_timeout(HELPER_POLL) {
                Ok(()) => ended += 1,
                Err(mpsc::RecvTimeoutError::Disconnected) => std::thread::sleep(HELPER_POLL),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
            },
            // past the limit, or the helper can no longer be watched: it is stopped, and whether it did its work is not known
            waited => {
                timed_out = waited.is_ok();
                let _ = child.kill();
                let _ = child.wait();
                break None;
            }
        }
    };
    // what is still in the pipes, a moment longer, never for ever: a program the helper started may hold them open
    let grace = std::time::Instant::now() + HELPER_GRACE;
    while ended < 2 && done_rx.recv_timeout(grace.saturating_duration_since(std::time::Instant::now())).is_ok() {
        ended += 1;
    }
    let text = |b: &Arc<Mutex<Vec<u8>>>| b.lock().map(|v| String::from_utf8_lossy(&v).into_owned()).unwrap_or_default();
    let mut said = format!("{}{}", text(&out), text(&err));
    if timed_out {
        if !said.is_empty() && !said.ends_with('\n') { said.push('\n'); }
        said += &format!("{HELPER_TIMEOUT}{} s: the editor stopped it.\n", limit.as_secs());
    }
    Ok((code, said))
}

/// The video system a file was saved under, in plain words, where its definition's container block says where it is:
/// the name the block gives the value ("PAL"), or the value with what is odd about it when the block names nothing
/// for it. None when the block does not say.
pub(crate) fn video_words(c: &CamSet) -> Option<String> {
    let (v, name) = c.video_system()?;
    Some(name.unwrap_or_else(|| format!("video system {v}, which the camera definition has no name for")))
}

/// The video system as a file's badge says it, after the firmware (" · PAL"; " · video system 7" for a value the block
/// names nothing for), and the line its hover adds; both empty when the block does not say where it is. The window's
/// badge and the web page's share it.
pub(crate) fn video_badge(c: &CamSet) -> (String, String) {
    match c.video_system() {
        Some((_, Some(name))) => (format!(" · {name}"), format!("\nSaved with the camera set to {name}.")),
        Some((v, None)) => (format!(" · video system {v}"), format!("\nSaved with the camera set to video system {v}, which the camera definition has no name for.")),
        None => (String::new(), String::new()),
    }
}

/// Whether a file saved under one video system may be written to a camera set to another (the values the container
/// block names, NTSC and PAL for example). Off, so such a write is refused (`write_check`): the two use different
/// frame rates, a camera numbers its frame-rate settings differently under each (docs/decisions/0008), and nobody has
/// tried what a camera does with a file from the other, so the editor fails closed. This is the one place the rule
/// lives, for the window and the web page alike; the owner may turn it on once a camera has been tried, and
/// docs/EDITOR.md ("The camera link") says so.
pub(crate) const WRITE_ACROSS_VIDEO_SYSTEMS: bool = false;

/// Before a write: the camera's settings read just now (`before`) and the file about to be sent (`sent`) must be
/// from the same model with the same record layout (the firmware included), else the file is not for this camera
/// as it is now, and, where the block says where the video system is, saved under the same one
/// (`WRITE_ACROSS_VIDEO_SYSTEMS`). The same rule holds for a file opened with "Edit anyway": the camera must hold that
/// layout too. Both are read with the container block the file was read with (`format`), and both checksums must
/// hold.
pub(crate) fn write_check(before: &[u8], sent: &[u8], format: Option<&std::sync::Arc<FileFormat>>) -> Result<(), Wrote> {
    let Some(format) = format else {
        return Err(Wrote::Mismatch("The file to be written could not be read back, so nothing was written.".into()));
    };
    let Ok(cam) = CamSet::parse(before, format) else { return Err(Wrote::NotRead) };
    let Ok(file) = CamSet::parse(sent, format) else {
        return Err(Wrote::Mismatch("The file to be written could not be read back, so nothing was written.".into()));
    };
    if cam.model() != file.model() {
        return Err(Wrote::Mismatch(format!("The camera is a {} but the file is from a {}, so nothing was written: a file goes only to the model that saved it.", cam.model(), file.model())));
    }
    if cam.layout_signature() != file.layout_signature() {
        let (c, f) = (cam.firmware(), file.firmware());
        let why = if c != f { format!("the camera has firmware {c} and the file is from firmware {f}") } else { "the camera holds its settings in another layout than the file".to_string() };
        return Err(Wrote::Mismatch(format!("Nothing was written: {why}, and a file goes only to a camera that holds the same layout. Read the camera, make the edits on that file, then write it.")));
    }
    if let (Some((c, _)), Some((f, _))) = (cam.video_system(), file.video_system()) {
        if c != f && !WRITE_ACROSS_VIDEO_SYSTEMS {
            let (c, f) = (video_words(&cam).unwrap_or_default(), video_words(&file).unwrap_or_default());
            return Err(Wrote::Mismatch(format!("Nothing was written: the camera is set to {c}, and this file was saved by a camera set to {f}. The two use different frame rates, and writing a file saved under one to a camera set to the other has not been tried, so the editor does not do it. Read the camera and make your edits on that file, or open a file saved while the camera was set to {c}.")));
        }
    }
    Ok(())
}

/// How an upload ended, from the helper's exit code (None: it was stopped) and output.
pub(crate) fn upload_outcome(code: Option<i32>, text: &str) -> Wrote {
    match code {
        Some(0) if text.lines().any(|l| l.trim() == "Upload accepted.") => Wrote::Confirmed,
        Some(c) if c != 0 => Wrote::Refused,
        _ => Wrote::Unconfirmed,
    }
}

/// The write job: read the camera first and keep that copy as `before` (`read_first`; else `before` is the copy the
/// Write window read a moment ago), check it against the file (`write_check`), then send the file. `run` runs the
/// camera link program with the given arguments: its exit code and output.
pub(crate) fn send_job(run: &mut dyn FnMut(Vec<std::ffi::OsString>) -> (Option<i32>, String), dir: &Path, before: &Path, read_first: bool, file: &Path, format: Option<&std::sync::Arc<FileFormat>>) -> JobDone {
    let read = if read_first {
        let tag = before.file_stem().unwrap_or_default().to_os_string();
        run(vec!["download".into(), tag, "--out".into(), dir.into()]).1
    } else {
        String::new()
    };
    let Ok(copy) = std::fs::read(before) else { return JobDone { res: Err(read), wrote: Some(Wrote::NotRead), took: None } };
    let sent = std::fs::read(file).unwrap_or_default();
    if let Err(why) = write_check(&copy, &sent, format) {
        return JobDone { res: Err(read), wrote: Some(why), took: None };
    }
    let (code, text) = run(vec!["upload".into(), file.into()]);
    let wrote = upload_outcome(code, &text);
    let res = if wrote == Wrote::Confirmed { Ok((file.to_path_buf(), text)) } else { Err(text) };
    JobDone { res, wrote: Some(wrote), took: None }
}

impl CameraJob {
    /// What the job is doing, a line under it, and how far along it is when that is known.
    pub(crate) fn progress(&self) -> (&'static str, String, Option<f32>) {
        let secs = self.started.elapsed().as_secs_f32();
        let s = secs as u64;
        let t = self.timing;
        let read = duration_words(t.read_s);
        match self.kind {
            JobKind::Read => ("Reading the camera…", format!("Usually about {read} · {s} s"), None),
            JobKind::BeforeWrite => ("Reading the camera before the write…", format!("Nothing is written yet · usually about {read} · {s} s"), None),
            JobKind::Discover => ("Looking for cameras…", format!("About {SEARCH_TIME} · {s} s"), None),
            JobKind::Send => ("Writing to the camera…", format!("It takes the file and restarts; its settings from just before are kept. {} · {s} s", check_words(&t)), None),
            JobKind::Verify if secs < t.restart_s as f32 => {
                // counted down to the first try, when the camera is usually back
                let left = (u64::from(t.restart_s).saturating_sub(s)).max(1) as u32;
                ("Camera restarting…", format!("Leave the camera on and connected: the editor reads it back in about {}", duration_words(left)), Some(secs / t.restart_s as f32))
            }
            JobKind::Verify => ("Checking what the camera holds…", format!("Leave the camera on and connected · {s} s"), Some(1.0)),
        }
    }
}

/// Under test: the shipped ILCE-1M2 firmware 4.00 definition's container block (`camera.file`).
#[cfg(test)]
pub(crate) fn test_block() -> std::sync::Arc<FileFormat> {
    static BLOCK: std::sync::OnceLock<std::sync::Arc<FileFormat>> = std::sync::OnceLock::new();
    BLOCK.get_or_init(|| {
        let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("definitions").join("ILCE-1M2_fw4.00.json");
        let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap();
        std::sync::Arc::new(serde_json::from_value(v["camera"]["file"].clone()).unwrap())
    }).clone()
}

/// Under test: a settings file read with the ILCE-1M2's block, both checksums holding.
#[cfg(test)]
pub(crate) fn test_parse(d: &[u8]) -> Result<CamSet, camset::CamSetError> {
    CamSet::parse(d, &test_block())
}

#[cfg(test)]
impl CameraJob {
    /// A job whose thread is done, for tests of what `poll_camera_job` makes of its outcome.
    pub(crate) fn finished(kind: JobKind, res: Result<(PathBuf, String), String>, wrote: Option<Wrote>) -> CameraJob {
        let result = std::sync::Arc::new(std::sync::Mutex::new(Some(JobDone { res, wrote, took: None })));
        CameraJob { kind, started: std::time::Instant::now(), result, backup: None, agreed: None, as_b: false, timing: LinkTiming::default() }
    }
}

/// A camera job: a read (it opens as file A), the read the Write window makes before a write (`BeforeWrite`: it lists
/// what the write changes and is kept for "Put the camera back"), a write, the read-back check after it, a search.
#[derive(Clone, Copy, PartialEq, Debug)]
pub(crate) enum JobKind { Read, BeforeWrite, Send, Verify, Discover }

/// The camera's settings the Write window read before asking (`JobKind::BeforeWrite`): when the read came back, its
/// file and what it holds. The window lists what the write changes against it, and the write keeps it as the copy
/// from just before, while it is fresh (`BEFORE_WRITE_FRESH`).
pub(crate) struct BeforeWrite {
    pub(crate) came: std::time::Instant,
    pub(crate) path: PathBuf,
    pub(crate) cam: CamSet,
}

/// How long the Write window's read of the camera stands for "the camera now": a write after that reads it again.
pub(crate) const BEFORE_WRITE_FRESH: std::time::Duration = std::time::Duration::from_secs(300);

/// The web page's Write (`send_check` with `read`, web/mod.rs): its read of the camera runs, came back fitting the file
/// (`before_write` holds it), or ended the write (why, in plain words; the camera report says more).
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum WebWrite { Reading, Read, Failed(String) }

/// The camera link as of the last camera action.
#[derive(Clone, PartialEq)]
pub(crate) enum LinkState { Untried, Up { at: String }, Down { why: String } }

/// What the probe reported about the camera it connected to: (model, link). The model is the one the helper names
/// once connected (`model:`), else the one it listed at the address, else the first it listed.
pub(crate) fn probe_camera(text: &str) -> (Option<String>, Option<String>) {
    let mut found: Vec<(String, String)> = Vec::new();   // (model, address) of each camera the helper listed
    let (mut model, mut link, mut addr) = (None, None, None);
    let named = text.lines().find_map(|l| l.trim().strip_prefix("model:")).map(str::trim).filter(|m| !m.is_empty()).map(str::to_string);
    for l in text.lines() {
        // the helper writes "found:"; older helpers wrote "Found:"
        if let Some(r) = l.strip_prefix("found: ").or_else(|| l.strip_prefix("Found: ")) {
            let at = r.split(" at ").nth(1).and_then(|a| a.split_whitespace().next()).unwrap_or("");
            found.push((r.split(" via").next().unwrap_or(r).trim().to_string(), at.to_string()));
        } else if let Some(r) = l.strip_prefix("Camera: ") {
            if let Some(n) = r.strip_prefix("network ") {
                link = Some(format!("LAN {}", n.trim()));
                addr = n.split_whitespace().next().map(str::to_string);
            } else { model.get_or_insert(r.trim().to_string()); link.get_or_insert("USB".to_string()); }
        }
    }
    // the helper lists every camera it sees: the one at the address it connected to, else the first
    let listed = found.iter().find(|(_, at)| addr.as_deref() == Some(at.as_str())).or(found.first()).map(|(m, _)| m.clone());
    (named.or(listed).or(model), link)
}

/// True when macOS will attribute this process's network use to tmux (started from a tmux pane,
/// not by launchd as an app): Local Network privacy then refuses LAN connections at once.
pub(crate) fn tmux_attributed() -> bool {
    #[cfg(target_os = "macos")]
    {
        // an app opened from Finder or `open` has launchd (pid 1) as its parent, whatever env it inherited
        return std::env::var_os("TMUX").is_some() && unsafe { libc::getppid() } != 1;
    }
    #[allow(unreachable_code)]
    false
}

/// Append one probe run to the camera folder's probe.log, so a failed camera action can be read afterwards.
/// It holds the camera's address, serial number and MAC address: readable by this user only, and kept to
/// `PROBE_LOG_MAX` bytes and one older file (`rotate_log`).
fn log_probe(args: &[std::ffi::OsString], ip: &str, ok: bool, secs: f32, text: &str) {
    use std::io::Write;
    let dir = App::camera_dir();
    let _ = std::fs::create_dir_all(&dir);
    let log = dir.join("probe.log");
    rotate_log(&log, PROBE_LOG_MAX);
    let mut o = std::fs::OpenOptions::new();
    o.create(true).append(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        o.mode(0o600);
    }
    if let Ok(mut f) = o.open(&log) {
        let a: Vec<String> = args.iter().map(|s| s.to_string_lossy().to_string()).collect();
        let _ = writeln!(f, "=== {} camset_probe {} (CAMSET_IP={}) -> {} in {:.1} s\n{}", local_stamp(), a.join(" "),
            if ip.is_empty() { "-" } else { ip }, if ok { "ok" } else { "failed" }, secs, text.trim_end());
    }
}

/// The size probe.log grows to before it is started again.
const PROBE_LOG_MAX: u64 = 2 << 20;

/// CAMSET_NETTEST=1: check the network path to the camera without a window, write the result to
/// <camera folder>/nettest.txt and exit. Run it as the app (`open --env CAMSET_NETTEST=1 "Camset Editor.app"`)
/// so macOS applies the app's own Local Network permission.
pub(crate) fn net_test(prefs: &Prefs) {
    let mut out = String::new();
    let ip = prefs.camera_ip.trim().to_string();
    out += &format!("time: {}\nexe: {}\nparent pid: {}\ntmux attributed: {}\nlink: {}\ncamera_ip: {ip}\n",
        local_stamp(), std::env::current_exe().map(|p| p.display().to_string()).unwrap_or_default(),
        { #[cfg(unix)] { unsafe { libc::getppid() } } #[cfg(not(unix))] { 0 } }, tmux_attributed(), prefs.link);
    if let Ok(addr) = format!("{ip}:22").parse::<std::net::SocketAddr>() {
        let t = std::time::Instant::now();
        let r = std::net::TcpStream::connect_timeout(&addr, std::time::Duration::from_secs(5));
        out += &format!("tcp {addr}: {} ({:.2} s)\n", match &r { Ok(_) => "connected".to_string(), Err(e) => format!("error: {e}") }, t.elapsed().as_secs_f32());
    }
    match find_probe(prefs) {
        None => out += "probe: not found\n",
        Some(p) => {
            out += &format!("probe: {}\n", p.display());
            let t = std::time::Instant::now();
            let mut cmd = std::process::Command::new(&p);
            if let Some(d) = p.parent() { cmd.current_dir(d); }
            if !ip.is_empty() { cmd.env("CAMSET_IP", &ip).env("CAMSET_MODEL", prefs.camera_model()); }
            match run_helper(cmd.arg("discover"), helper_limit(&LinkTiming::default())) {
                Err(e) => out += &format!("discover: could not run: {e}\n"),
                Ok((code, text)) => out += &format!("discover ({:.1} s, {}):\n{text}\n", t.elapsed().as_secs_f32(),
                    code.map_or_else(|| "stopped".to_string(), |c| format!("exit code {c}"))),
            }
        }
    }
    let dir = App::camera_dir();
    let _ = std::fs::create_dir_all(&dir);
    let _ = std::fs::write(dir.join("nettest.txt"), out);
}

/// The probe executable: the one chosen in Settings, else the first of `probe_candidates` that exists.
fn find_probe(prefs: &Prefs) -> Option<PathBuf> {
    if let Some(p) = prefs.probe_path.as_ref().map(PathBuf::from).filter(|p| p.is_file()) {
        return Some(p);
    }
    let exe = std::env::current_exe().ok()?;
    probe_candidates(&exe).into_iter().find(|p| p.is_file())
}

/// Where `find_probe` looks for the helper, for the program at `exe`: beside it (in the macOS app, Contents/MacOS),
/// then, when the program runs from a checkout of this repository (editor/target/[<target>/]<profile>/, or an app
/// built into editor/target/dist…/), the kit's build of it (cmake -S kit/probe -B kit/probe/build, with the Sony SDK
/// in kit/sdk). Never the current folder or any other folder above the program, where anyone may have left a program
/// of that name.
pub(crate) fn probe_candidates(exe: &Path) -> Vec<PathBuf> {
    let name = format!("camset_probe{}", std::env::consts::EXE_SUFFIX);
    let Some(dir) = exe.parent() else { return Vec::new() };
    let mut found = vec![dir.join(&name)];
    let named = |p: &Path, n: &str| p.file_name().is_some_and(|f| f == n);
    // editor/target/release, editor/target/<target>/release, editor/target/dist/X.app/Contents/MacOS
    let repo = dir.ancestors().take(5).find(|a| named(a, "target")).and_then(Path::parent).filter(|e| named(e, "editor")).and_then(Path::parent);
    if let Some(repo) = repo {
        // as kit/setup.py's built(): camset_probe, or on Windows camset_probe.exe, in Release/ after a Visual Studio build
        let build = repo.join("kit").join("probe").join("build");
        found.push(build.join(&name));
        if cfg!(windows) {
            found.push(build.join("Release").join(&name));
        }
    }
    found
}

impl App {
    /// The probe executable: from the preferences, else next to the program or in the kit tree.
    pub(crate) fn probe_path(&self) -> Option<PathBuf> {
        // tests never run the camera link program they might find next to the build: only one a test names
        if cfg!(test) {
            return self.prefs.probe_path.as_ref().map(PathBuf::from).filter(|p| p.is_file());
        }
        find_probe(&self.prefs)
    }

    /// The camera button's words, as the top bar and the web page show them: the link, with the camera's address when
    /// `address`, and its state in words too, not by colour alone ("📷 USB · read 17:44", "📷 Network · not reached");
    /// "📷 Not set up" without the camera link program.
    pub(crate) fn camera_button_text(&self, address: bool) -> String {
        let helper = self.have_helper();
        let ip = self.prefs.camera_ip.trim();
        let link = match self.prefs.link.as_str() {
            _ if !helper => "Not set up".to_string(),
            "network" if address && !ip.is_empty() => format!("Network {ip}"),
            "network" => "Network".to_string(),
            "usb" => "USB".to_string(),
            _ => "Set up the camera…".to_string(),
        };
        let state = match &self.link_state {
            _ if !helper => String::new(),
            LinkState::Up { at } => format!(" · read {}", when_words(at)),
            LinkState::Down { .. } => " · not reached".to_string(),
            LinkState::Untried => String::new(),
        };
        format!("📷 {link}{state}")
    }

    /// Whether the camera link program is there (looked for again every few seconds, not on every frame). Without
    /// it the window offers files only: Read and Write are not shown, and the camera button says how to set it up.
    pub(crate) fn have_helper(&self) -> bool {
        match self.helper_seen.get() {
            Some((at, found)) if at.elapsed() < std::time::Duration::from_secs(3) => found,
            _ => {
                let found = self.probe_path().is_some();
                self.helper_seen.set(Some((std::time::Instant::now(), found)));
                found
            }
        }
    }

    pub(crate) fn camera_dir() -> PathBuf {
        Prefs::path().parent().map(|p| p.join("camera")).unwrap_or_else(|| PathBuf::from("camera"))
    }

    /// Write back the camera's settings read just before the last write (the camera restarts).
    pub(crate) fn put_camera_back(&mut self) {
        if self.link_busy() { return; }
        let Some((at, p)) = self.camera_backup.clone() else { return };
        match self.read_file(&p) {
            Ok(c) => {
                self.sent = Some((p.clone(), c));
                self.start_camera_job(Some(p));
                self.status = format!("Putting the camera back as it was at {}…", when_words(&at));
            }
            Err(e) => self.status = format!("The copy of the camera's settings kept from {} could not be read: {}", when_words(&at), self.load_words(&p, &e)),
        }
    }

    /// Run the probe on another thread: `download` fetches the live settings into the camera folder,
    /// `upload` sends a file (the camera restarts). The result lands in `camera_job`.
    pub(crate) fn start_camera_job(&mut self, upload: Option<PathBuf>) {
        self.start_job(if upload.is_some() { JobKind::Send } else { JobKind::Read }, upload);
    }

    /// True (and says so) while a camera job runs: one camera action at a time.
    fn link_busy(&mut self) -> bool {
        if self.camera_job.is_some() {
            self.status = "The camera link is busy: wait for the current camera action to finish, then try again.".into();
        }
        self.camera_job.is_some()
    }

    /// Start a camera job, one at a time. A read that would replace unsaved edits asks first (`guard`).
    pub(crate) fn start_job(&mut self, kind: JobKind, upload: Option<PathBuf>) {
        if self.link_busy() { return; }
        if kind == JobKind::Read && self.unsaved() > 0 {
            self.guard(Replace::Read);
            return;
        }
        self.run_job(kind, upload, None, None);
    }

    /// Start a camera job on another thread; `agreed`: a read the person agreed may replace these edits; `before`: a
    /// write's copy of the camera's settings the Write window read a moment ago (else the write reads the camera
    /// first).
    pub(crate) fn run_job(&mut self, kind: JobKind, upload: Option<PathBuf>, agreed: Option<u64>, before: Option<PathBuf>) {
        if self.link_busy() { return; }
        let Some(probe) = self.probe_path() else {
            self.camera_report = Some(CameraReport { title: "✖ Camera link program not found".into(), ok: false,
                lines: vec![("Choose the camera link program under ⚙ Settings. Nothing was read or written.".into(), true)], probe: String::new(), retry: None, offer_usb: false, put_back: false });
            self.status = "Camera link program not found: choose it in Settings".into();
            return;
        };
        let network = self.prefs.link == "network";
        let ip = if network || kind == JobKind::Discover { self.prefs.camera_ip.trim().to_string() } else { String::new() };
        // the chosen camera's MAC: the helper picks that camera's own login by it, even when its search misses the camera
        let mac = if network && kind != JobKind::Discover { norm_mac(&self.prefs.camera_mac) } else { String::new() };
        // a write checks the camera's copy and the file with the container block the file was read with
        let format = self.sent.as_ref().map(|(_, c)| c.format().clone());
        let model = if ip.is_empty() { String::new() } else { self.prefs.camera_model() };
        if network && ip.is_empty() && kind != JobKind::Discover {
            self.camera_report = Some(CameraReport { title: "✖ No camera address".into(), ok: false,
                lines: vec![("The link is set to Network but no address is given. Open Connect to the camera, search for the camera or type its address.".into(), true)], probe: String::new(), retry: None, offer_usb: false, put_back: false });
            self.status = "Camera: no address set".into();
            return;
        }
        let dir = Self::camera_dir();
        let _ = std::fs::create_dir_all(&dir);
        // a write keeps the camera's settings from just before it, which "Put the camera back" writes: the copy the
        // Write window read (`before`), else it reads the camera first
        let read_first = kind == JobKind::Send && before.is_none();
        let backup = match kind {
            JobKind::Send | JobKind::BeforeWrite => Some(before.unwrap_or_else(|| dir.join(format!("before_write_{}.DAT", file_stamp())))),
            _ => None,
        };
        let before = backup.clone().unwrap_or_default();
        let result = std::sync::Arc::new(std::sync::Mutex::new(None));
        // a read-back tried again (`read_back_now`) reads at once: the camera restarted long ago
        let timing = match self.job_timing() {
            t if kind == JobKind::Verify && self.read_back_now => LinkTiming { restart_s: 0, ..t },
            t => t,
        };
        // how long one run of the helper may take before it is stopped: no job runs until the editor quits
        let limit = helper_limit(&timing);
        #[cfg(test)]
        let limit = TEST_HELPER_LIMIT.with(|l| l.get()).unwrap_or(limit);
        // the link a read goes over, for the reads this computer has timed (`Prefs::read_times`)
        let via = if network { "network" } else { "usb" };
        let r2 = result.clone();
        let what = match kind {
            JobKind::Send if read_first => "Reading the camera, then writing to it… (it restarts afterwards)",
            JobKind::Send => "Writing to the camera… (it restarts afterwards)",
            JobKind::Read => "Reading the camera's settings…",
            JobKind::BeforeWrite => "Reading the camera, to list what the write changes…",
            JobKind::Verify if timing.restart_s == 0 => "Reading back what the camera holds…",
            JobKind::Verify => "Waiting for the camera to restart, then reading back what it holds…",
            JobKind::Discover => "Searching for cameras on USB and the network…",
        }.to_string();
        std::thread::spawn(move || {
            let mut run = |args: Vec<std::ffi::OsString>| -> (Option<i32>, String) {
                let mut cmd = std::process::Command::new(&probe);
                if let Some(d) = probe.parent() { cmd.current_dir(d); }
                if !ip.is_empty() { cmd.env("CAMSET_IP", &ip); }
                if !mac.is_empty() { cmd.env("CAMSET_MAC", &mac); }
                if !model.is_empty() { cmd.env("CAMSET_MODEL", &model); }
                cmd.args(&args);
                let t = std::time::Instant::now();
                let (code, text) = match run_helper(&mut cmd, limit) {
                    Err(e) => (Some(NOT_RUN), format!("could not run {}: {e}", probe.display())),
                    Ok(done) => done,
                };
                log_probe(&args, &ip, code == Some(0), t.elapsed().as_secs_f32(), &text);
                (code, text)
            };
            // a panic is an answer too, so the job never stays "running" for ever; a write that stopped
            // after sending may have reached the camera
            let job = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| match (kind, &upload) {
                (JobKind::Discover, _) => {
                    let (code, text) = run(vec!["discover".into()]);
                    let res = if code == Some(0) || text.contains("found ") { Ok((PathBuf::new(), text)) } else { Err(text) };
                    JobDone { res, wrote: None, took: None }
                }
                (JobKind::Send, Some(f)) => send_job(&mut run, &dir, &before, read_first, f, format.as_ref()),
                (JobKind::BeforeWrite, _) => {
                    let tag = before.file_stem().unwrap_or_default().to_os_string();
                    let t = std::time::Instant::now();
                    let (_, text) = run(vec!["download".into(), tag, "--out".into(), dir.clone().into()]);
                    let took = before.is_file().then(|| (via, t.elapsed().as_secs_f32()));
                    JobDone { res: if before.is_file() { Ok((before.clone(), text)) } else { Err(text) }, wrote: None, took }
                }
                (JobKind::Verify, _) => {
                    // the camera restarts after an upload (the job starts as it ends): each try when `read_back_at` says,
                    // from the definition's link_timing
                    let t0 = std::time::Instant::now();
                    let (mut last, mut text) = (None, String::new());
                    let res = loop {
                        let Some(at) = read_back_at(&timing, t0.elapsed().as_secs_f32(), last) else { break Err(text) };
                        std::thread::sleep(std::time::Duration::from_secs_f32((at - t0.elapsed().as_secs_f32()).max(0.0)));
                        last = Some(t0.elapsed().as_secs_f32());
                        let tag = format!("verify_{}", file_stamp());
                        text = run(vec!["download".into(), tag.clone().into(), "--out".into(), dir.clone().into()]).1;
                        let f = dir.join(format!("{tag}.DAT"));
                        if f.is_file() { break Ok((f, text)); }
                    };
                    JobDone { res, wrote: None, took: None }
                }
                _ => {
                    let tag = format!("camera_{}", file_stamp());
                    let t = std::time::Instant::now();
                    let (_, text) = run(vec!["download".into(), tag.clone().into(), "--out".into(), dir.clone().into()]);
                    let f = dir.join(format!("{tag}.DAT"));
                    let took = (kind == JobKind::Read && f.is_file()).then(|| (via, t.elapsed().as_secs_f32()));
                    JobDone { res: if f.is_file() { Ok((f, text)) } else { Err(text) }, wrote: None, took }
                }
            }));
            let done = job.unwrap_or_else(|_| JobDone {
                res: Err("The camera link stopped unexpectedly.".into()),
                wrote: (kind == JobKind::Send).then_some(Wrote::Unconfirmed),
                took: None,
            });
            if let Ok(mut r) = r2.lock() { *r = Some(done); }
        });
        self.status = what;
        let as_b = kind == JobKind::Read && std::mem::take(&mut self.read_as_b);
        self.camera_job = Some(CameraJob { kind, started: std::time::Instant::now(), result, backup, agreed, as_b, timing });
    }

    /// "Try again" on a camera report: the job again; a read before a write opens the Write window again; the
    /// read-back after a write reads at once (`read_back_now`), the camera having restarted long ago.
    pub(crate) fn retry_job(&mut self, kind: JobKind, upload: Option<PathBuf>) {
        if kind == JobKind::BeforeWrite {
            self.send_to_camera();
            return;
        }
        self.read_back_now = kind == JobKind::Verify;
        self.start_job(kind, upload);
        self.read_back_now = false;
    }

    /// How long the camera link usually takes: as the open file's definition says, else the definition of the
    /// camera the link is set to (by its model), else the link's usual times.
    pub(crate) fn link_timing(&self) -> LinkTiming {
        let model = self.prefs.camera_model();
        self.schema.camera.link_timing
            .or_else(|| self.defs.in_use().find(|s| !model.is_empty() && s.model == model).and_then(|s| s.camera.link_timing))
            .unwrap_or_default()
    }

    /// How long a read of the camera usually takes, in whole seconds: the median of the last reads this computer
    /// timed over the link in use (`Prefs::read_times`), else the definition's `read_s`.
    pub(crate) fn usual_read_s(&self) -> u32 {
        self.prefs.read_times.get(&self.prefs.link).and_then(|t| median_secs(t.as_slice())).unwrap_or_else(|| self.link_timing().read_s)
    }

    /// How long a read usually takes, in words ("9 seconds"): what every place that names it says (`usual_read_s`).
    pub(crate) fn read_words(&self) -> String {
        duration_words(self.usual_read_s())
    }

    /// The ⬇ Read button's hover, the window's (with its `shortcut`) and the page's.
    pub(crate) fn read_tip(&self, shortcut: &str) -> String {
        format!("Read the camera's current settings over USB or the network (usually about {}{shortcut})", self.read_words())
    }

    /// The link's times as a camera job expects them: the definition's (`link_timing`), with the read as this
    /// computer has timed it (`usual_read_s`).
    pub(crate) fn job_timing(&self) -> LinkTiming {
        LinkTiming { read_s: self.usual_read_s(), ..self.link_timing() }
    }

    /// The welcome page's Read card, under its title, the window's and the page's: the camera the read goes to, when
    /// the editor knows it ("Studio body over the network"), and how long a read usually takes.
    pub(crate) fn read_sub(&self) -> String {
        let usual = format!("Usually about {}.", self.read_words());
        match self.prefs.current_camera().map(|i| self.prefs.cameras[i].label().to_string()).filter(|l| !l.is_empty()) {
            Some(l) => format!("{l} {}. {usual}", if self.prefs.link == "network" { "over the network" } else { "over USB" }),
            None => format!("Over USB or the network. {usual}"),
        }
    }

    /// What to check after a failed read, when the camera link names no cause: the definition's words for the link
    /// (`text.read_failed_usb` / `read_failed_network`), else None (the editor's own).
    pub(crate) fn read_failed_hint(&self, network: bool) -> Option<String> {
        let t = &self.schema.camera.text;
        if network { t.read_failed_network.clone() } else { t.read_failed_usb.clone() }.filter(|h| !h.is_empty())
    }
}

/// The camera link's times as a job keeps them: the read-back's schedule and its words, the reads this computer
/// timed, a read-back tried again.
#[cfg(test)]
mod link_timing_tests {
    use super::*;
    use crate::test_support::{done, sample_app};

    /// The read-back after a write: its first try when the camera is usually back (`restart_s` after the upload), the
    /// next `poll_s` after a failed one began (at once when that took longer), none once `timeout_s` has passed; a
    /// restart past the timeout still tries once, and a read-back tried again (restart 0) reads at once.
    #[test]
    fn read_back_schedule() {
        let t = LinkTiming { read_s: 9, restart_s: 30, poll_s: 8, timeout_s: 180 };
        assert_eq!(read_back_at(&t, 0.0, None), Some(30.0));
        assert_eq!(read_back_at(&t, 40.0, None), Some(40.0), "started late: at once");
        assert_eq!(read_back_at(&t, 31.0, Some(30.0)), Some(38.0), "a try that failed at once: the next 8 s after it began");
        assert_eq!(read_back_at(&t, 47.0, Some(30.0)), Some(47.0), "one that took 17 s: the next at once");
        assert_eq!(read_back_at(&t, 179.0, Some(170.0)), Some(179.0));
        assert_eq!(read_back_at(&t, 173.0, Some(172.0)), None, "none starts at the timeout");
        assert_eq!(read_back_at(&t, 185.0, Some(170.0)), None);
        assert_eq!(read_back_at(&LinkTiming { restart_s: 0, ..t }, 0.0, None), Some(0.0));
        let slow = LinkTiming { restart_s: 300, ..t };
        assert_eq!(read_back_at(&slow, 0.0, None), Some(180.0));
        assert_eq!(read_back_at(&slow, 181.0, Some(180.0)), None);
        // a camera back 28 s after the upload whose reads take 9 s, and fail after 17 s while it is away: one try,
        // at 30 s, done at 39 s
        let (mut now, mut last, mut tries) = (0.0, None, 0);
        while let Some(at) = read_back_at(&t, now, last) {
            tries += 1;
            last = Some(at);
            if at >= 28.0 { now = at + 9.0; break; }
            now = at + 17.0;
        }
        assert_eq!((tries, now), (1, 39.0));
    }

    /// The words of a write and its read-back under the link's times: "Camera restarting…" counted down to the first
    /// try, then "Checking what the camera holds…"; a write, its report and the Write window promise the end of the
    /// check as the restart and then the usual read; the search's progress line and its hover name the same time.
    #[test]
    fn read_back_words() {
        let t = LinkTiming { read_s: 9, restart_s: 30, poll_s: 8, timeout_s: 180 };
        let back = |restart_s: u32, ago: u64| {
            let mut job = CameraJob { timing: LinkTiming { restart_s, ..t }, ..CameraJob::finished(JobKind::Verify, Err(String::new()), None) };
            job.started = std::time::Instant::now().checked_sub(std::time::Duration::from_secs(ago)).unwrap();
            job.progress()
        };
        let (title, line, bar) = back(30, 0);
        assert_eq!((title, line.as_str()), ("Camera restarting…", "Leave the camera on and connected: the editor reads it back in about 30 seconds"));
        assert!(bar.is_some_and(|b| b < 0.1));
        let (title, line, bar) = back(30, 25);
        assert_eq!((title, line.as_str()), ("Camera restarting…", "Leave the camera on and connected: the editor reads it back in about 5 seconds"));
        assert!(bar.is_some_and(|b| (0.8..1.0).contains(&b)));
        let (title, line, bar) = back(30, 33);
        assert_eq!((title, bar), ("Checking what the camera holds…", Some(1.0)));
        assert!(line.starts_with("Leave the camera on and connected · 33 s"), "{line}");
        assert_eq!(back(0, 0).0, "Checking what the camera holds…", "a read-back tried again: no restart");
        let send = CameraJob { kind: JobKind::Send, timing: t, ..CameraJob::finished(JobKind::Send, Err(String::new()), None) };
        assert!(send.progress().1.contains("Leave the camera on and connected until the check after the restart has finished, about 39 seconds after it takes the file"), "{}", send.progress().1);
        let search = CameraJob::finished(JobKind::Discover, Err(String::new()), None).progress().1;
        assert!(search.starts_with(&format!("About {SEARCH_TIME}")) && search_tip().contains(&format!("(about {SEARCH_TIME})")), "{search}");
        // a write the camera took: when it is usually back, and when the check is done, with this computer's reads
        let (mut app, dir, user) = sample_app("read_back", None);
        app.prefs.link = "usb".into();
        for s in [8.6, 9.2, 9.0] { app.prefs.note_read("usb", s); }
        app.prefs.probe_path = Some(dir.join("CAMSET01.DAT").display().to_string());   // cannot run: no camera is reached
        app.sent = Some((dir.join("SEND.DAT"), test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap()));
        app.camera_job = Some(CameraJob::finished(JobKind::Send, Ok((dir.join("SEND.DAT"), "Camera: USB\nUpload accepted.\n".into())), Some(Wrote::Confirmed)));
        app.poll_camera_job();
        let r = app.camera_report.as_ref().unwrap();
        assert_eq!(r.title, "✔ Written, now checking");
        assert!(r.lines.iter().any(|(l, _)| l == "It is usually back in about 30 seconds; the editor then reads its settings back and compares them with what was written, about 39 seconds from now."), "{:?}", r.lines);
        let job = app.camera_job.as_ref().unwrap();
        assert_eq!((job.kind, job.timing, job.progress().0), (JobKind::Verify, LinkTiming { read_s: 9, ..app.link_timing() }, "Camera restarting…"));
        assert_eq!(app.status, "Waiting for the camera to restart, then reading back what it holds…");
        done(&dir, &user);
    }

    /// The reads this computer timed: the last five per link, whose median in whole seconds is what the editor names
    /// as a read's usual time (the job's line, the Read card and button, the Write window); before the first over
    /// the link in use, the definition's. A read that brought its file back adds its time.
    #[test]
    fn read_time_from_this_computer() {
        assert_eq!(median_secs(&[]), None);
        assert_eq!(median_secs(&[8.3]), Some(8));
        assert_eq!(median_secs(&[9.8, 8.3, 8.6]), Some(9));
        assert_eq!(median_secs(&[8.0, 9.0, 10.0, 30.0]), Some(10), "an even count: the middle two's mean, 9.5");
        assert_eq!(median_secs(&[0.2, f32::NAN]), Some(1));
        let (mut app, dir, user) = sample_app("read_time", None);
        for s in [20.0, 8.3, 9.1, 8.7, 9.8, 8.5, f32::NAN, -1.0] { app.prefs.note_read("network", s); }
        assert_eq!(app.prefs.read_times["network"], vec![8.3, 9.1, 8.7, 9.8, 8.5], "the last five, nothing odd");
        app.prefs.link = "usb".into();
        assert_eq!(app.usual_read_s(), app.link_timing().read_s, "no read timed over USB yet: the definition's");
        app.prefs.link = "network".into();
        assert_eq!((app.usual_read_s(), app.read_words()), (9, "9 seconds".to_string()));
        assert_eq!(app.read_sub(), "Over USB or the network. Usually about 9 seconds.");
        assert_eq!(app.read_tip("; Cmd/Ctrl+R"), "Read the camera's current settings over USB or the network (usually about 9 seconds; Cmd/Ctrl+R)");
        assert_eq!(app.job_timing(), LinkTiming { read_s: 9, ..app.link_timing() });
        let job = CameraJob { timing: app.job_timing(), ..CameraJob::finished(JobKind::BeforeWrite, Err(String::new()), None) };
        assert!(job.progress().1.starts_with("Nothing is written yet · usually about 9 seconds"), "{}", job.progress().1);
        // a read that brought its file back over USB: its time is kept for that link
        let job = CameraJob::finished(JobKind::Read, Err(String::new()), None);
        *job.result.lock().unwrap() = Some(JobDone { res: Err("no camera\n".into()), wrote: None, took: Some(("usb", 6.4)) });
        app.camera_job = Some(job);
        app.poll_camera_job();
        assert_eq!(app.prefs.read_times["usb"], vec![6.4]);
        app.prefs.link = "usb".into();
        assert_eq!(app.read_words(), "6 seconds");
        done(&dir, &user);
    }

    /// "Try again" after a read-back the camera did not answer reads at once, the window's and the page's; the
    /// read-back after a write waits for the restart.
    #[test]
    fn a_retried_read_back_reads_at_once() {
        let (mut app, dir, user) = sample_app("retry_back", None);
        app.prefs.link = "usb".into();
        app.prefs.probe_path = Some(dir.join("CAMSET01.DAT").display().to_string());   // cannot run: no camera is reached
        app.start_job(JobKind::Verify, None);
        let job = app.camera_job.take().unwrap();
        assert_eq!((job.timing.restart_s, job.progress().0), (30, "Camera restarting…"));
        app.retry_job(JobKind::Verify, None);
        let job = app.camera_job.take().unwrap();
        assert_eq!((job.timing.restart_s, job.progress().0), (0, "Checking what the camera holds…"));
        assert_eq!(app.status, "Reading back what the camera holds…");
        assert!(!app.read_back_now, "only that job");
        app.start_job(JobKind::Verify, None);
        assert_eq!(app.camera_job.take().map(|j| j.timing.restart_s), Some(30));
        done(&dir, &user);
    }
}

/// A camera helper that does not end: the job stops it at a limit from the definition's link timing, and the report
/// says so in plain words, the helper's own output in Expert mode only.
#[cfg(test)]
mod helper_limit_tests {
    use super::*;

    /// The limit: twice the link's longest step (the read-back window), never less than a minute.
    #[test]
    fn the_limit_comes_from_the_link_timing() {
        assert_eq!(helper_limit(&LinkTiming::default()), std::time::Duration::from_secs(360), "twice the 180 s read-back window");
        assert_eq!(helper_limit(&LinkTiming { read_s: 5, restart_s: 5, poll_s: 5, timeout_s: 5 }), std::time::Duration::from_secs(60), "never less than a minute");
        assert_eq!(helper_limit(&LinkTiming { read_s: 9, restart_s: 400, poll_s: 8, timeout_s: 180 }), std::time::Duration::from_secs(800), "the longest step, whichever it is");
    }

    /// A stopped helper in the report of each kind of job: the plain sentence first, with what to do; the line the
    /// job added and the helper's own words only in the details, which Expert mode shows.
    #[test]
    fn a_stopped_helper_in_plain_words() {
        let said = format!("Camera: USB\n{HELPER_TIMEOUT}360 s: the editor stopped it.\n");
        assert_eq!(helper_timeout(&said), Some(360));
        assert_eq!((helper_timeout("Camera: USB\n"), helper_timeout("cause: no_answer\n")), (None, None));
        let plain = "The camera helper did not answer within 360 s: the camera may have lost its link. Check it, then try again.";
        assert_eq!(cause_words(&said).as_deref(), Some(plain));
        // a read
        let mut app = App::new(vec![], Prefs::default());
        app.prefs.link = "usb".into();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Err(said.clone()), None));
        app.poll_camera_job();
        let r = app.camera_report.as_ref().unwrap();
        assert_eq!((r.title.as_str(), r.lines[0].clone()), ("✖ Nothing was read from the camera", (plain.to_string(), true)));
        assert!(r.lines.iter().all(|(l, _)| !l.contains(HELPER_TIMEOUT) && !l.contains("could not be reached")), "{:?}", r.lines);
        assert!(r.probe.contains(HELPER_TIMEOUT));
        let page = app.web_state(0)["report"].clone();
        assert_eq!((&page["has_probe"], &page["note"]), (&serde_json::json!(false), &serde_json::json!(EXPERT_LINK_NOTE)), "{page}");
        // a search
        app.camera_job = Some(CameraJob::finished(JobKind::Discover, Err(said.clone()), None));
        app.poll_camera_job();
        assert_eq!(app.discover_msg, plain);
        // a write the helper did not finish: it may have reached the camera, so no "try again" before the check
        let dir = crate::definitions::definitions_tests::scratch("helper_limit_write");
        let stand_in = dir.join("not_a_program");
        std::fs::write(&stand_in, "").unwrap();
        app.prefs.probe_path = Some(stand_in.display().to_string());   // cannot run: the check started below talks to no camera
        let sent = dir.join("SEND.DAT");
        std::fs::write(&sent, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.sent = Some((sent.clone(), test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap()));
        assert_eq!(upload_outcome(None, &said), Wrote::Unconfirmed, "a helper stopped during the upload");
        app.camera_job = Some(CameraJob::finished(JobKind::Send, Err(said.clone()), Some(Wrote::Unconfirmed)));
        app.poll_camera_job();
        let r = app.camera_report.as_ref().unwrap();
        assert_eq!(r.title, "⚠ The file may have been written");
        assert_eq!(r.lines[0], ("The camera helper did not answer within 360 s, so the editor stopped it: the camera may have lost its link.".to_string(), true));
        assert!(r.lines[1].0.contains("did not confirm that it took SEND.DAT"), "{:?}", r.lines);
        assert_eq!(app.camera_job.take().map(|j| j.kind), Some(JobKind::Verify), "the check starts");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// A helper standing in for the camera link program: `quick` answers at once; `orphan` leaves a program of its own
    /// holding the output open; anything else prints a line on each stream and then hangs.
    #[cfg(unix)]
    fn hanging_helper(dir: &Path) -> PathBuf {
        use std::os::unix::fs::PermissionsExt;
        let p = dir.join("hanging_probe");
        std::fs::write(&p, "#!/bin/sh\ncase \"$1\" in\n  quick) echo ready; exit 3;;\n  orphan) echo started; sleep 20;;\n  *) echo started; echo waiting >&2; exec sleep 20;;\nesac\n").unwrap();
        std::fs::set_permissions(&p, std::fs::Permissions::from_mode(0o755)).unwrap();
        // a program written just now may not start while another test's process still holds it open for writing
        // (ETXTBSY on Linux): the first run waits for that, so the runs under test start at once
        for _ in 0..50 {
            match run_helper(std::process::Command::new(&p).arg("quick"), std::time::Duration::from_secs(10)) {
                Err(e) if e.raw_os_error() == Some(26) => std::thread::sleep(std::time::Duration::from_millis(100)),
                r => { assert_eq!(r.unwrap(), (Some(3), "ready\n".to_string()), "a helper that ends: its code and output"); break; }
            }
        }
        p
    }

    /// A helper that hangs is stopped at the limit (killed and waited for), with what it said so far and the line the
    /// job adds, also when a program it started holds its output open; one that cannot start is an error.
    #[cfg(unix)]
    #[test]
    fn a_helper_that_hangs_is_stopped() {
        let dir = crate::definitions::definitions_tests::scratch("helper_limit_run");
        let helper = hanging_helper(&dir);
        let limit = std::time::Duration::from_secs(1);
        for arg in ["download", "orphan"] {
            let t = std::time::Instant::now();
            let (code, text) = run_helper(std::process::Command::new(&helper).arg(arg), limit).unwrap();
            let took = t.elapsed();
            assert!(took >= limit && took < limit + HELPER_GRACE + std::time::Duration::from_secs(3), "{arg}: stopped in {took:?}");
            assert_eq!(code, None, "{arg}: stopped, so no exit code");
            assert!(text.starts_with("started\n") && text.ends_with(&format!("{HELPER_TIMEOUT}1 s: the editor stopped it.\n")), "{arg}: {text:?}");
            assert_eq!(helper_timeout(&text), Some(1));
        }
        let none = run_helper(&mut std::process::Command::new(dir.join("no_such_program")), limit);
        assert!(none.is_err(), "a helper that is not there does not start");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Every program the editor starts goes through `no_console`, so none opens a console window on Windows: in the
    /// code of every source under src/ (comments and strings left out, tests in), a program is started only on a line
    /// that has `no_console` on it, and only in two places, the camera link program's (`run_helper`, which every
    /// search, read and write goes through) and the file manager's.
    #[test]
    fn every_program_started_has_no_console_window() {
        let mut files = Vec::new();
        crate::no_camera_facts::rust_files(&Path::new(env!("CARGO_MANIFEST_DIR")).join("src"), &mut files);
        let (mut starts, mut flags) = (Vec::new(), 0);
        for f in &files {
            let name = f.file_name().unwrap().to_string_lossy().into_owned();
            for l in crate::no_camera_facts::rust_lines(&std::fs::read_to_string(f).unwrap()) {
                let code: String = l.code.chars().filter(|c| !c.is_whitespace()).collect();
                flags += code.matches("creation_flags(").count();
                if [".spawn()", ".output()", ".status()", "::exec("].iter().any(|s| code.contains(s)) {
                    assert!(code.contains("no_console("), "{name}:{} starts a program without no_console", l.no);
                    starts.push(name.clone());
                }
            }
        }
        starts.sort();
        assert_eq!(starts, ["files.rs", "job.rs"], "the places that start a program");
        assert_eq!(flags, 1, "the Windows creation flags are set in no_console alone");
    }

    /// On Windows, a console program started as the camera link program is (`run_helper`, through `no_console`) still
    /// gives its exit code and its output through the pipes, and one that hangs is still stopped at the limit.
    #[cfg(windows)]
    #[test]
    fn a_console_program_without_a_window_answers_and_can_be_stopped() {
        let limit = std::time::Duration::from_secs(10);
        assert_eq!(run_helper(std::process::Command::new("cmd").args(["/c", "exit", "3"]), limit).unwrap().0, Some(3));
        assert_eq!(run_helper(std::process::Command::new("cmd").args(["/c", "echo", "ready"]), limit).unwrap(), (Some(0), "ready\r\n".to_string()));
        let limit = std::time::Duration::from_secs(1);
        let t = std::time::Instant::now();
        let (code, text) = run_helper(std::process::Command::new("ping").args(["-n", "30", "127.0.0.1"]), limit).unwrap();
        assert!(t.elapsed() < limit + HELPER_GRACE + std::time::Duration::from_secs(3), "stopped in {:?}", t.elapsed());
        assert_eq!(code, None, "stopped, so no exit code");
        assert!(text.ends_with(&format!("{HELPER_TIMEOUT}1 s: the editor stopped it.\n")), "{text:?}");
    }

    /// The whole way, as the window runs it: a read whose helper hangs ends at the limit, and the report and the
    /// status line say what happened in plain words.
    #[cfg(unix)]
    #[test]
    fn a_read_whose_helper_hangs_ends_with_a_report() {
        let dir = crate::definitions::definitions_tests::scratch("helper_limit_job");
        let helper = hanging_helper(&dir);
        let mut app = App::new(vec![], Prefs::default());
        app.prefs.link = "usb".into();
        app.prefs.probe_path = Some(helper.display().to_string());
        TEST_HELPER_LIMIT.with(|l| l.set(Some(std::time::Duration::from_secs(1))));
        let t = std::time::Instant::now();
        app.start_camera_job(None);
        TEST_HELPER_LIMIT.with(|l| l.set(None));
        assert_eq!(app.camera_job.as_ref().map(|j| j.kind), Some(JobKind::Read));
        while app.camera_job.is_some() && t.elapsed() < std::time::Duration::from_secs(20) {
            std::thread::sleep(std::time::Duration::from_millis(50));
            app.poll_camera_job();
        }
        assert!(app.camera_job.is_none() && t.elapsed() < std::time::Duration::from_secs(10), "the job ended at the limit: {:?}", t.elapsed());
        let r = app.camera_report.as_ref().expect("a report");
        assert_eq!(r.title, "✖ Nothing was read from the camera");
        assert_eq!(r.lines[0], ("The camera helper did not answer within 1 s: the camera may have lost its link. Check it, then try again.".to_string(), true));
        assert!(r.lines.iter().all(|(l, _)| !l.contains("started") && !l.contains("waiting") && !l.contains(HELPER_TIMEOUT)), "the helper's own words are not in the plain lines: {:?}", r.lines);
        assert!(r.probe.contains("started\n") && r.probe.contains("waiting\n") && r.probe.contains(HELPER_TIMEOUT), "{:?}", r.probe);
        assert_eq!(app.status, "Camera: nothing read (see the Camera link window)");
        assert!(matches!(app.link_state, LinkState::Down { .. }));
        assert_eq!(r.retry.as_ref().map(|(k, _)| *k), Some(JobKind::Read), "Try again");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
