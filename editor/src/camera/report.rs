//! What a camera job's outcome means for the open file, and the Camera link window that reports it.

use crate::*;

/// The outcome of a camera action, shown in its own window until dismissed.
pub(crate) struct CameraReport {
    pub(crate) title: String,
    pub(crate) ok: bool,
    /// (text, is a warning)
    pub(crate) lines: Vec<(String, bool)>,
    pub(crate) probe: String,
    /// A failed job that "Try again" restarts (kind, file to upload).
    pub(crate) retry: Option<(JobKind, Option<PathBuf>)>,
    /// Offer to switch the link to USB and read (a network link failed after a write).
    pub(crate) offer_usb: bool,
    /// Offer "Put the camera back": the report of a write, whose copy from just before is kept.
    pub(crate) put_back: bool,
}

impl App {
    /// How a camera report names the camera the helper connected to: the person's name for it and its model as the
    /// definitions name it ("Studio body (ILCE-1M2 · α1 II)"); None when it has neither.
    fn report_camera(&self, name: &str, model: Option<&str>) -> Option<String> {
        camera_words(name, model.map(|m| self.defs.model_words(m)).as_deref())
    }

    /// Finish a camera job whose thread has returned, and build the report window.
    pub(crate) fn poll_camera_job(&mut self) {
        let Some(job) = &self.camera_job else { return };
        let done = job.result.lock().ok().and_then(|mut r| r.take());
        let Some(JobDone { res, wrote, took }) = done else { return };
        let (kind, elapsed, agreed, as_b) = (job.kind, job.started.elapsed().as_secs(), job.agreed, job.as_b);
        let backup = job.backup.clone();
        self.camera_job = None;
        // a read that brought its file back: how long it took joins the reads this computer has timed
        if let Some((via, secs)) = took {
            self.prefs.note_read(via, secs);
            self.prefs.save();
        }
        let now = local_stamp();
        // a connection was made when the helper named the camera (it does after every connect): the known cameras learn it
        let known = match (&kind, &res) {
            (JobKind::Discover, _) => None,
            (_, Ok((_, text)) | Err(text)) => self.learn_camera(text),
        };
        let name = self.named(known);
        match (kind, res) {
            (JobKind::Discover, Ok((_, text))) => {
                self.discovered = text.lines().filter(|l| l.trim_start().starts_with('{'))
                    .filter_map(|l| serde_json::from_str::<Discovered>(l).ok()).collect();
                let direct_err = text.lines().find(|l| l.trim_start().starts_with("direct check of ")).map(|s| s.trim().to_string());
                self.link_state = if self.discovered.is_empty() { LinkState::Down { why: "no camera found".into() } } else { LinkState::Up { at: now.clone() } };
                let in_tmux = tmux_attributed();
                let tmux_note = if in_tmux {
                    " ⚠ Started inside tmux: macOS Local Network privacy immediately blocks LAN camera connections for programs started under tmux. Quit and launch Camset Editor from Finder or a regular Terminal.app tab outside tmux."
                } else {
                    ""
                };
                self.discover_detail = if self.discovered.is_empty() { direct_err.unwrap_or_default() } else { String::new() };
                self.discover_text = text.trim().to_string();
                self.discover_msg = if self.discovered.is_empty() {
                    let said = cause_words(&text).unwrap_or_else(|| "No camera found. Check the steps for the chosen link, then search again.".into());
                    format!("{said}{tmux_note}")
                } else { format!("{} camera(s) found.", self.discovered.len()) };
                if self.discovered.is_empty() { self.steps_shown = true; } else { self.connect_checks = vec![true; 16]; }
                self.status = self.discover_msg.clone();
            }
            (JobKind::Discover, Err(text)) => {
                self.discovered.clear();
                self.steps_shown = true;
                self.link_state = LinkState::Down { why: "search failed".into() };
                self.discover_detail = text.trim().to_string();
                self.discover_text = text.trim().to_string();
                self.discover_msg = cause_words(&text).unwrap_or_else(|| "The search could not run.".into());
                self.status = self.discover_msg.clone();
            }
            (JobKind::Read, Ok((p, _))) if as_b => {
                self.link_state = LinkState::Up { at: now.clone() };
                self.compare_with_read(p, now);
            }
            (JobKind::Read, Ok((p, text))) => {
                self.link_state = LinkState::Up { at: now.clone() };
                // edits made since the read was agreed to (or started) are not replaced without a question
                let edits = self.edits_hash();
                if edits.is_some() && edits != agreed {
                    self.status = "The camera was read. Your edits are not saved yet: choose what to do with them.".into();
                    self.guard(Replace::ReadDone { path: p, text, name, at: now });
                } else {
                    self.finish_read(p, text, name, now);
                }
            }
            (JobKind::Read, Err(text)) => {
                let shown = self.doc.as_ref().map(|d| d.path.file_name().unwrap_or_default().to_string_lossy().to_string());
                let mut own = Vec::new();
                if cause_words(&text).is_none() { own.push(("The camera could not be reached, so nothing was read.".to_string(), true)); }
                match shown {
                    Some(n) => own.push((format!("The file on screen is still {n}, loaded from disk. It is not the camera's current state."), true)),
                    None => own.push(("No file is open.".into(), false)),
                }
                if tmux_attributed() && self.prefs.link == "network" {
                    own.push(("⚠ Started inside tmux: macOS Local Network privacy blocks LAN connections (failing immediately with 'No route to host') for any program started inside tmux. Quit this window and launch Camset Editor from Finder or from a regular Terminal.app tab outside tmux.".to_string(), true));
                }
                let network = self.prefs.link == "network";
                let lines = failure_lines_with(&text, network, own, self.read_failed_hint(network).as_deref());
                self.status = "Camera: nothing read (see the Camera link window)".into();
                self.link_state = LinkState::Down { why: "not reached".into() };
                self.camera_report = Some(CameraReport { title: "✖ Nothing was read from the camera".into(), ok: false, lines, probe: text, retry: Some((JobKind::Read, None)), offer_usb: false, put_back: false });
            }
            (JobKind::BeforeWrite, Ok((p, text))) => {
                self.link_state = LinkState::Up { at: now.clone() };
                self.took_before_write(p, text, now);
            }
            (JobKind::BeforeWrite, Err(text)) => {
                // the window's Write window, or the page's Write, waits for this read
                let open = self.close_write_window() | self.web_write.is_some();
                self.link_state = LinkState::Down { why: "not reached".into() };
                let failed = "Nothing was written: the camera could not be read first. Before every write the editor reads the camera, to list what the write changes and to keep a copy for ↩ Put the camera back. The camera's settings are unchanged.";
                if self.web_write.is_some() {
                    self.web_write = Some(WebWrite::Failed(failed.to_string()));
                }
                if open {
                    let network = self.prefs.link == "network";
                    let own = vec![(failed.to_string(), true)];
                    let lines = failure_lines_with(&text, network, own, self.read_failed_hint(network).as_deref());
                    self.status = "Camera: nothing written (see the Camera link window)".into();
                    self.camera_report = Some(CameraReport { title: "✖ Nothing written".into(), ok: false, lines, probe: text, retry: Some((JobKind::BeforeWrite, None)), offer_usb: false, put_back: false });
                } else {
                    // the Write window was closed while the camera was read: nothing was asked of the camera
                    self.status = "The camera could not be read; nothing was written.".into();
                }
            }
            (JobKind::Send, Ok((p, text))) => {
                let (model, link) = probe_camera(&text);
                if let Some(b) = backup.filter(|b| b.is_file()) { self.camera_backup = Some((local_stamp(), b)); }
                self.status = format!("Wrote {} to the camera; it is restarting. Reading it back…", p.file_name().unwrap_or_default().to_string_lossy());
                let who = self.report_camera(&name, model.as_deref()).unwrap_or_else(|| "model not named".into());
                // the check: the camera's restart, then the usual read
                let t = self.job_timing();
                let lines = vec![
                    (format!("The camera ({who}, over {}) accepted {} and is restarting.", link.unwrap_or_else(|| "unknown link".into()), p.file_name().unwrap_or_default().to_string_lossy()), false),
                    (format!("It is usually back in about {}; the editor then reads its settings back and compares them with what was written, about {} from now.", duration_words(t.restart_s), duration_words(t.restart_s + t.read_s)), false),
                    ("The camera's settings from just before are kept: ↩ Put the camera back writes them again.".into(), false),
                ];
                self.camera_report = Some(CameraReport { title: "✔ Written, now checking".into(), ok: true, lines, probe: text, retry: None, offer_usb: false, put_back: true });
                self.link_state = LinkState::Up { at: now.clone() };
                self.start_job(JobKind::Verify, None);
            }
            (JobKind::Send, Err(text)) if wrote == Some(Wrote::Unconfirmed) => {
                // the camera may have taken the file: keep the copy from just before, offer it back, and read the camera
                let (model, link) = probe_camera(&text);
                if let Some(b) = backup.filter(|b| b.is_file()) { self.camera_backup = Some((local_stamp(), b)); }
                let file = self.sent.as_ref().map(|(p, _)| p.file_name().unwrap_or_default().to_string_lossy().to_string()).unwrap_or_else(|| "the file".into());
                let who = self.report_camera(&name, model.as_deref()).unwrap_or_else(|| "model not named".into());
                let mut lines = vec![
                    (format!("The camera ({who}, over {}) did not confirm that it took {file}. It may have been written, and the camera may be restarting.", link.unwrap_or_else(|| "unknown link".into())), true),
                    (format!("The editor reads the camera's settings back when a restarted camera is usually back, in about {}, and compares them with what was sent: wait for that check before you write again.", duration_words(self.link_timing().restart_s)), false),
                ];
                if self.camera_backup.is_some() {
                    lines.push(("The camera's settings from just before are kept: ↩ Put the camera back writes them again.".into(), false));
                }
                // a helper the job stopped: said first, without "try again", as the check that follows comes first
                if let Some(secs) = helper_timeout(&text) {
                    lines.insert(0, (format!("The camera helper did not answer within {secs} s, so the editor stopped it: the camera may have lost its link."), true));
                }
                self.status = "Camera: the file may have been written; checking what the camera holds…".into();
                self.camera_report = Some(CameraReport { title: "⚠ The file may have been written".into(), ok: false, lines, probe: text, retry: None, offer_usb: false, put_back: true });
                self.start_job(JobKind::Verify, None);
            }
            (JobKind::Send, Err(text)) => {
                self.status = "Camera: nothing written (see the Camera link window)".into();
                let retry = Some((JobKind::Send, self.sent.as_ref().map(|(p, _)| p.clone())));
                let (why, retry) = match &wrote {
                    Some(Wrote::Mismatch(why)) => {
                        // the camera answered and was read: the file is what does not fit it
                        self.link_state = LinkState::Up { at: now.clone() };
                        (format!("{why} The camera's settings are unchanged."), None)
                    }
                    Some(Wrote::NotRead) => {
                        self.link_state = LinkState::Down { why: "not reached".into() };
                        ("The camera could not be read first, so nothing was written: the editor keeps a copy of the camera's settings before every write. Its settings are unchanged.".into(), retry)
                    }
                    _ => {
                        self.link_state = LinkState::Down { why: "not reached".into() };
                        ("The camera did not accept the file, or was not reached. Its settings are unchanged.".into(), retry)
                    }
                };
                let lines = match &wrote {
                    Some(Wrote::Mismatch(_)) => vec![(why, true)],
                    _ => failure_lines_with(&text, self.prefs.link == "network", vec![(why, true)], self.read_failed_hint(self.prefs.link == "network").as_deref()),
                };
                self.camera_report = Some(CameraReport { title: "✖ Nothing written".into(), ok: false, lines, probe: text, retry, offer_usb: false, put_back: false });
            }
            (JobKind::Verify, Ok((p, text))) => {
                let (model, link) = probe_camera(&text);
                let link = link.unwrap_or_else(|| "unknown link".into());
                let who = self.report_camera(&name, model.as_deref()).unwrap_or_else(|| "model not named".into());
                let mut lines = vec![(format!("The camera ({who}, over {link}) answered {elapsed} s after the write."), false)];
                let mut ok = true;
                // the read-back, when it confirms the write (every record equal, or only the ones the camera changes on every load)
                let mut confirmed: Option<CamSet> = None;
                self.link_state = LinkState::Up { at: now.clone() };
                let back = self.load(&p);
                if let Ok(back) = &back { self.last_camera = Some((now.clone(), back.clone())); }
                match (back, &self.sent) {
                    (Ok(back), Some((_, sent))) => {
                        let diffs = self.record_diff(sent, &back);
                        if diffs.is_empty() {
                            lines.push((if self.prefs.expert { "Every record read back equals the file that was written." } else { "The camera holds exactly the file that was written." }.to_string(), false));
                            confirmed = Some(back);
                        } else {
                            let volatile = |sec: usize, id: u16| sec == 0 && self.schema.camera.volatile_records.contains(&id);
                            let flags: Vec<&(usize, u16, String)> = diffs.iter().filter(|(s, id, _)| volatile(*s, *id)).collect();
                            let real = diffs.len() - flags.len();
                            // the definition's own words for the values the camera resets are for Expert mode; plain words otherwise
                            let note = self.schema.camera.text.volatile_note.as_deref().filter(|t| !t.is_empty() && self.prefs.expert)
                                .unwrap_or("Only {n} values the camera resets on every start differ: it holds what was written.");
                            if real == 0 { lines.push((note.replace("{n}", &flags.len().to_string()), false)); confirmed = Some(back); }
                            else if self.prefs.expert { ok = false; lines.push((format!("{real} record(s) differ from the file that was written (plus {} the camera changes on every load):", flags.len()), true)); }
                            else { ok = false; lines.push((format!("{real} settings differ from what was written:"), true)); }
                            for (sec, id, name) in diffs.iter().filter(|d| !volatile(d.0, d.1)).take(20) {
                                let place = self.schema.camera.target_name(*sec);
                                let name = if name == "(unmapped)" { "a setting the editor does not know yet".to_string() } else { name.clone() };
                                // the record number is for Expert mode
                                lines.push((if self.prefs.expert { format!("    0x{id:04x} {place}: {name}") } else { format!("    {place}: {name}") }, true));
                            }
                        }
                    }
                    (Err(e), _) => {
                        ok = false;
                        lines.push(("The settings read back from the camera came back incomplete, so they could not be compared with what was written. Read the camera again.".into(), true));
                        if self.prefs.expert { lines.push((format!("    {e}"), true)); }
                    }
                    (_, None) => lines.push(("The editor kept no copy of what was written, so it cannot compare.".into(), true)),
                }
                // what the confirmation means for file A, and the report's line on it
                if let Some(back) = confirmed {
                    lines.extend(self.confirmed_write(&p, back, link, &now));
                }
                self.status = if ok { "Camera confirmed: it holds the file that was written".into() } else { "Camera read back with differences (see the Camera link window)".into() };
                self.camera_report = Some(CameraReport { title: if ok { "✔ Camera confirmed".into() } else { "⚠ Camera differs from what was written".into() }, ok, lines, probe: text, retry: None, offer_usb: false, put_back: true });
            }
            (JobKind::Verify, Err(text)) => {
                self.status = "Camera: no answer after the write (see the Camera link window)".into();
                self.link_state = LinkState::Down { why: "no answer after the write".into() };
                let network = self.prefs.link == "network";
                // the settings that cut the link, as the definition names them for this link
                let names: Vec<String> = self.schema.camera.link_records.iter().filter(|r| r.link == if network { "network" } else { "usb" } && !r.name.is_empty())
                    .map(|r| r.name.clone()).fold(Vec::new(), |mut v, n| { if !v.contains(&n) { v.push(n); } v });
                let what = match names.split_last() {
                    Some((last, [])) => format!("changes {last}"),
                    Some((last, rest)) => format!("changes {} or {last}", rest.join(", ")),
                    None => "turns the camera's network connection off or changes its USB mode".to_string(),
                };
                let said = format!("The file was sent, but the camera could not be reached for {} afterwards. If the written file {what}, the camera restarted with the link off: check it on the camera, then read the camera again.", duration_words(self.link_timing().timeout_s));
                self.camera_report = Some(CameraReport { title: "⚠ Written, but the camera did not answer afterwards".into(), ok: false,
                    lines: failure_lines_with(&text, network, vec![(said, true)], self.read_failed_hint(network).as_deref()), probe: text,
                    retry: Some((JobKind::Verify, None)), offer_usb: network, put_back: true });
            }
        }
    }

    /// A read is done and may replace file A: open the download, and carry on as "read from the camera" only when
    /// it is the file that opened. A download that does not open leaves file A as it was, says so, and is never
    /// taken as the camera's settings.
    pub(crate) fn finish_read(&mut self, p: PathBuf, text: String, name: String, now: String) {
        let (model, link) = probe_camera(&text);
        let link = link.unwrap_or_else(|| "unknown link".into());
        let before = self.doc.as_ref().map(|d| d.path.file_name().unwrap_or_default().to_string_lossy().to_string());
        if let Err(e) = self.open_now(p.clone()) {
            let mut lines = vec![("The camera was reached and its settings were read, but the file it gave could not be opened, so nothing was taken as the camera's settings. Read the camera again.".to_string(), true)];
            lines.push(match before {
                Some(n) => (format!("The file on screen is still {n}. It is not the camera's current state."), true),
                None => ("No file is open.".into(), false),
            });
            if self.prefs.expert { lines.push((format!("Details: {e}"), true)); }
            self.status = "Camera: the file read from the camera could not be opened (see the Camera link window)".into();
            self.camera_report = Some(CameraReport { title: "✖ The file read from the camera could not be opened".into(), ok: false, lines, probe: text, retry: Some((JobKind::Read, None)), offer_usb: false, put_back: false });
            return;
        }
        let mut lines = Vec::new();
        let mut ok = true;
        let checksum_name = self.doc.as_ref().map(|d| Self::header_checksum_name(&d.edited)).unwrap_or_default();
        let expert = self.prefs.expert;
        let who = self.report_camera(&name, model.as_deref());
        if let Some(d) = &mut self.doc {
            d.source = Source::Camera { link: link.clone(), read_at: now.clone() };
            let file_model = d.edited.model();
            lines.push((format!("Connected over {link} to {}.", who.unwrap_or_else(|| "a camera it did not name".into())), model.is_none()));
            match &model {
                Some(m) if *m == file_model => {}
                Some(m) => { ok = false; lines.push((format!("The file names {file_model} but the camera link found {m}."), true)); }
                None => {}
            }
            let ts = d.edited.timestamp();
            match (stamp_minutes(&ts), stamp_minutes(&now)) {
                (Some(a), Some(b)) => {
                    let diff = (b - a).abs();
                    if diff <= 10 { lines.push((format!("The camera's clock and this computer's agree ({}): a fresh read.", when_words(&ts)), false)); }
                    else {
                        // the helper has just downloaded the file, so the read is fresh whatever the stamp says: a gap is the
                        // camera's clock (a reset leaves it at a default, or AM for PM), said as a caution, not as a doubt
                        lines.push((format!("The camera's clock and this computer's differ by {}: the file is stamped {}, this computer says {}. The read itself is fine. If the camera's clock is wrong, set its date and time on the camera.", minutes_words(diff), stamp_in_words(&ts, expert), when_words(&now)), true));
                    }
                }
                _ => lines.push((format!("The file's time ({ts}) could not be compared with this computer's clock."), true)),
            }
            if !d.edited.header_checksum_ok() { ok = false; lines.push((format!("The file looks damaged ({checksum_name} does not match)."), true)); }
            if !self.schema.camera.knows(&d.edited) { lines.push(("This camera's firmware has not been checked yet, so editing is off; \"Edit anyway…\" next to the file name turns it on.".into(), true)); }
        }
        self.status = format!("Read from {} over {link} at {}", if name.is_empty() { "the camera" } else { &name }, when_words(&now));
        self.link_state = LinkState::Up { at: now.clone() };
        if let Some(d) = &self.doc { self.last_camera = Some((now.clone(), d.original.clone())); }
        self.camera_report = Some(CameraReport { title: if ok { "✔ Read from the camera".into() } else { "⚠ Read from the camera, with doubts".into() }, ok, lines, probe: text, retry: None, offer_usb: false, put_back: false });
    }

    /// The Write window's read of the camera is back. When the camera holds the layout of the file to be written
    /// (`write_check`: the same model and record layout, and the same video system where the block says where it
    /// is), the window lists what the write changes against it;
    /// otherwise the write ends here, with the reason. Either way the read is what the camera holds now.
    fn took_before_write(&mut self, p: PathBuf, text: String, now: String) {
        // the window's Write window, or the page's Write, waits for this read
        let page = self.web_write.is_some();
        let open = matches!(&self.pending, Some((Review::Send, _))) || page;
        let Some(doc) = &self.doc else {
            self.close_write_window();
            if page { self.web_write = Some(WebWrite::Failed("Nothing was written: no file is open in the editor any more.".into())); }
            return;
        };
        let format = doc.edited.format().clone();
        let copy = std::fs::read(&p).unwrap_or_default();
        let fits = write_check(&copy, &doc.edited.to_bytes(), Some(&format));
        let cam = CamSet::parse(&copy, &format).ok();
        if let Some(c) = &cam { self.last_camera = Some((now.clone(), c.clone())); }
        match (fits, cam) {
            (Ok(()), Some(cam)) => {
                self.before_write = Some(BeforeWrite { came: std::time::Instant::now(), path: p, cam });
                // the Write window lists again, now judging every record that differs from what the camera holds too
                if let Some((Review::Send, _)) = &self.pending {
                    self.pending = Some((Review::Send, self.write_issues()));
                }
                if page { self.web_write = Some(WebWrite::Read); }
                self.status = if open { "The camera was read: the Write window lists what the write changes.".into() } else { "The camera was read; nothing was written.".into() };
            }
            (fits, _) => {
                self.close_write_window();
                let (why, retry) = match fits {
                    Err(Wrote::Mismatch(why)) => (format!("{why} The camera's settings are unchanged."), None),
                    _ => ("Nothing was written: the camera's settings came back incomplete, so they could not be compared with the file. Its settings are unchanged; try again.".to_string(), Some((JobKind::BeforeWrite, None))),
                };
                if page { self.web_write = Some(WebWrite::Failed(why.clone())); }
                if open {
                    self.status = "Camera: nothing written (see the Camera link window)".into();
                    self.camera_report = Some(CameraReport { title: "✖ Nothing written".into(), ok: false, lines: vec![(why, true)], probe: text, retry, offer_usb: false, put_back: false });
                } else {
                    self.status = why;
                }
            }
        }
    }

    /// Close the Write window, if it is open (and say whether it was).
    pub(crate) fn close_write_window(&mut self) -> bool {
        let open = matches!(&self.pending, Some((Review::Send, _)));
        if open {
            self.pending = None;
            self.review_rev = None;
        }
        open
    }

    /// (section, id, name) of every record whose bytes differ between two files (header left out).
    pub(crate) fn record_diff(&self, a: &CamSet, b: &CamSet) -> Vec<(usize, u16, String)> {
        let mut out = Vec::new();
        for (si, (x, y)) in a.sections.iter().zip(b.sections.iter()).enumerate() {
            for r in &x.records {
                let other = y.get(r.id);
                if other.map(|o| o.value != r.value || o.elem_size != r.elem_size || o.count != r.count).unwrap_or(true) {
                    let name = self.schema.settings.iter()
                        .find(|s| s.id == r.id && if si == 0 { s.area == "global" } else { s.in_sets })
                        .map(|s| s.name.clone()).unwrap_or_else(|| "(unmapped)".into());
                    out.push((si, r.id, name));
                }
            }
        }
        out
    }

    /// Whether two files hold the same records, section by section, with the same values (header left out).
    pub(crate) fn same_records(a: &CamSet, b: &CamSet) -> bool {
        a.sections.len() == b.sections.len() && a.sections.iter().zip(&b.sections).all(|(x, y)| x.records == y.records)
    }

    /// The records the camera changes on every load (`ids`, of the live section) of `to`, made `from`'s.
    fn carry_volatile(to: &mut CamSet, from: &CamSet, ids: &[u16]) {
        let (Some(dst), Some(src)) = (to.sections.get_mut(0), from.sections.first()) else { return };
        for id in ids {
            if let (Some(r), Some(o)) = (dst.get_mut(*id), src.get(*id)) {
                if r.elem_size == o.elem_size && r.count == o.count { r.value = o.value.clone(); }
            }
        }
    }

    /// The camera's read-back (`back`, the file `p`) confirmed the write of `sent`: what that means for file A, and the
    /// confirmed report's line on it.
    ///
    /// File A read from the camera starts from the read-back now, as a camera read just now over `link`: the edits the
    /// camera took are edits no longer, and only edits it does not hold stay edits (made while the check ran, or, after
    /// ↩ Put the camera back, the ones on screen). The records the camera changes on every load take the read-back's
    /// values in the file and in the Undo and Redo steps, so they never show as edits. Undo and Redo stay, as after
    /// Save As: a step back is an edit against what the camera holds, and ↩ Put the camera back undoes the write
    /// itself. With no edits left, the journal of unsaved edits goes (`journal_at`, on the next frame).
    ///
    /// A file from disk is unchanged, so its edits stay edits; while they are the ones the camera holds, the counter
    /// and the question before they would be lost say so (`on_camera`).
    fn confirmed_write(&mut self, p: &Path, back: CamSet, link: String, now: &str) -> Vec<(String, bool)> {
        let (Some((sent_path, sent)), Some(d)) = (&self.sent, self.doc.as_mut()) else { return Vec::new() };
        let same = Self::same_records(&d.edited, sent);
        let had = d.changes().len();
        let fits = back.sections.len() == d.edited.sections.len() && back.model() == d.edited.model() && back.layout_signature() == d.signature;
        let undo = "↩ Put the camera back undoes the write.";
        if matches!(d.source, Source::Camera { .. }) && fits {
            let volatile = &self.schema.camera.volatile_records;
            if same { d.edited = back.clone(); } else { Self::carry_volatile(&mut d.edited, &back, volatile); }
            for step in self.undo.iter_mut().chain(self.redo.iter_mut()) {
                Self::carry_volatile(step, &back, volatile);
            }
            d.signature = back.layout_signature();
            // what the camera holds now is what it wrote: the baseline the edits are judged against, as after a read
            d.baseline = back.clone();
            d.original = back;
            d.recovered = 0;   // recovered edits the file as opened did not show: the camera holds them now
            d.path = p.to_path_buf();
            d.source = Source::Camera { link, read_at: now.to_string() };
            d.saved = false;
            d.rev = next_open();
            let n = d.changes().len();
            self.history_cache.borrow_mut().clear();
            self.last_edit = None;
            self.on_camera = None;
            self.remember_session();
            let line = match (n, had) {
                (0, 0) => "The camera holds what is on screen.".to_string(),
                (0, _) => "Your edits are on the camera now, so none are left unsaved: file A starts from what the camera holds.".to_string(),
                (1, _) => "File A now starts from what the camera holds. 1 edit on screen differs from it: it is not on the camera.".to_string(),
                (n, _) => format!("File A now starts from what the camera holds. {n} edits on screen differ from it: they are not on the camera."),
            };
            return vec![(format!("{line} {undo}"), false)];
        }
        if same && had > 0 {
            let name = d.path.file_name().unwrap_or_default().to_string_lossy().to_string();
            self.on_camera = Some((d.opened, d.rev, sent_path.clone()));
            let edits = if had == 1 { "Your edit is".to_string() } else { format!("Your {had} edits are") };
            return vec![(format!("{edits} on the camera now, but not saved to {name}: Save As… keeps them in a file. {undo}"), false)];
        }
        Vec::new()
    }

    /// The report window for the last camera action.
    pub(crate) fn camera_report_window(&mut self, ctx: &egui::Context) {
        let Some(r) = &self.camera_report else { return };
        let mut close = false;
        let (retry, offer_usb, failed) = (r.retry.clone(), r.offer_usb, !r.ok);
        let put_back = self.camera_backup.as_ref().filter(|_| r.put_back).map(|(at, _)| when_words(at));
        let (mut do_retry, mut do_connect, mut do_usb, mut do_put_back) = (false, false, false, false);
        let v = ctx.style().visuals.clone();
        let color = if r.ok { tone::ok(&v) } else { tone::bad(&v) };
        egui::Window::new("Camera link").collapsible(false).resizable(true).default_width(620.0).show(ctx, |ui| {
            ui.label(RichText::new(&r.title).size(18.0).strong().color(color));
            ui.add_space(6.0);
            for (text, warn) in &r.lines {
                if *warn { ui.label(RichText::new(text).color(tone::caution(&v))); } else { ui.label(text); }
            }
            ui.add_space(6.0);
            if self.prefs.expert {
                let retries = r.probe.lines().filter(|l| l.starts_with("note: connect attempt")).count();
                if retries > 0 && r.ok {
                    ui.label(RichText::new(format!("The link retried {retries} time(s) before connecting; that is normal when the computer's own camera service grabs the camera first.")).small().color(tone::weak(ui.visuals())));
                }
                egui::CollapsingHeader::new("Details from the camera link").show(ui, |ui| {
                    egui::ScrollArea::vertical().max_height(240.0).show(ui, |ui| {
                        ui.label(RichText::new(if r.probe.trim().is_empty() { "(nothing)" } else { r.probe.trim() }).monospace().small());
                    });
                });
            } else if !r.probe.trim().is_empty() {
                ui.label(RichText::new(EXPERT_LINK_NOTE).small().color(tone::weak(ui.visuals())));
            }
            let credentials = matches!(probe_cause(&r.probe), Some("credentials_missing" | "credentials_rejected"));
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui.button("Close").clicked() { close = true; }
                if retry.is_some() && ui.add_enabled(self.camera_job.is_none(), egui::Button::new("Try again")).clicked() { do_retry = true; }
                let (label, hover) = if credentials { ("Enter user name and password", "Open Connect to the camera: enter the user name and password set on the camera, and press Save") }
                    else { ("Change connection", "Open Connect to the camera: choose USB or network and find the camera") };
                if failed && ui.button(label).on_hover_text(hover).clicked() { do_connect = true; }
                if offer_usb && ui.add_enabled(self.camera_job.is_none(), egui::Button::new("Switch to USB and read")).on_hover_text("Set the link to USB (camera in PC Remote) and read the camera").clicked() { do_usb = true; }
                if let Some(at) = &put_back {
                    if ui.add_enabled(self.camera_job.is_none(), egui::Button::new(format!("↩ Put the camera back as it was at {at}")))
                        .on_hover_text(format!("Write the camera's settings read at {at}, just before the last write; the camera restarts")).clicked() { do_put_back = true; }
                }
            });
        });
        if close || do_retry || do_connect || do_usb || do_put_back { self.camera_report = None; }
        if do_put_back { self.put_camera_back(); }
        if do_retry {
            if let Some((kind, upload)) = retry { self.retry_job(kind, upload); }
        }
        if do_connect { self.show_connect = true; }
        if do_usb {
            self.prefs.link = "usb".into();
            self.prefs.save();
            self.start_camera_job(None);
        }
    }
}

/// What a camera job's report says with the definition's link timing and words: a gap between the clocks, the
/// hints after a failed read and after a write the camera did not answer, the records it changes on every load.
#[cfg(test)]
mod link_report_tests {
    use super::*;
    use crate::test_support::{done, sample_app};

    /// A camera whose clock is off (12 hours after a reset) still gives a read that counts: the report says the gap
    /// as a caution and stays "✔", since the helper has just made the download.
    #[test]
    fn a_clock_gap_is_a_caution_not_a_doubt() {
        assert_eq!((minutes_words(35), minutes_words(720), minutes_words(1), minutes_words(2 * 1440 + 180)), ("35 minutes".into(), "12 hours".into(), "1 minute".into(), "2 days and 3 hours".into()));
        let (mut app, dir, user) = sample_app("clock", None);
        let f = dir.join("CAMSET01.DAT");
        let text = "found: ILCE-1M2 via IP at 192.0.2.1 (SSH)\nCamera: network 192.0.2.1 (authenticated)\nmodel: ILCE-1M2\n".to_string();
        // the sample's stamp against a clock twelve hours later than it
        let ts = app.doc.as_ref().unwrap().edited.timestamp();
        let later = stamp_minutes(&ts).unwrap() + 720;
        let (days, rest) = (later / 1440, later % 1440);
        let now = format!("{}_{:02}{:02}00", &ts[..8], rest / 60, rest % 60);
        let _ = days;
        app.finish_read(f, text, String::new(), now);
        let r = app.camera_report.as_ref().unwrap();
        assert!(r.ok && r.title.starts_with("✔"), "{} {:?}", r.title, r.lines);
        assert!(r.lines.iter().any(|(l, warn)| *warn && l.contains("differ by 12 hours") && l.contains("The read itself is fine")), "{:?}", r.lines);
        done(&dir, &user);
    }

    /// Link timing, the hints after a failed read and after a write that was not answered, and the note on the
    /// records the camera changes on every load.
    #[test]
    fn link_words_and_timing() {
        let (mut app, dir, user) = sample_app("link", None);
        assert_eq!(app.link_timing(), LinkTiming { read_s: 5, restart_s: 30, poll_s: 8, timeout_s: 180 });
        let job = CameraJob { timing: LinkTiming { read_s: 7, restart_s: 113, poll_s: 4, timeout_s: 300 }, ..CameraJob::finished(JobKind::Read, Err(String::new()), None) };
        assert!(job.progress().1.starts_with("Usually about 7 seconds"));
        // a write: leave the camera on for its restart and then the usual read
        let send = CameraJob { kind: JobKind::Send, ..job };
        assert!(send.progress().1.contains("until the check after the restart has finished, about two minutes after it takes the file"), "{}", send.progress().1);
        assert_eq!((duration_words(60), duration_words(180), duration_words(90), duration_words(1)), ("a minute".into(), "three minutes".into(), "90 seconds".into(), "1 second".into()));
        // a read that failed with no cause named: the definition's words for the link
        app.prefs.link = "usb".into();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Err("no camera\n".into()), None));
        app.poll_camera_job();
        let lines = &app.camera_report.as_ref().unwrap().lines;
        assert!(lines.iter().any(|(l, _)| l.contains("USB Connection Mode on PC Remote")), "{lines:?}");
        // a write the camera did not answer after: the settings that cut the link, by the definition's names
        app.prefs.link = "network".into();
        app.camera_job = Some(CameraJob::finished(JobKind::Verify, Err(String::new()), None));
        app.poll_camera_job();
        let lines = &app.camera_report.as_ref().unwrap().lines;
        assert!(lines.iter().any(|(l, _)| l.contains("for three minutes afterwards. If the written file changes Wired LAN Connect, Wi-Fi Connect or Remote Shooting,")), "{lines:?}");
        // the read-back differs only in a record the camera changes on every load
        let sample = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        let mut back = sample.clone();
        let id = app.schema.camera.volatile_records[0];
        back.sections[0].get_mut(id).unwrap().value[0] ^= 1;
        let p = dir.join("verify.DAT");
        std::fs::write(&p, back.to_bytes()).unwrap();
        // plain words outside Expert mode, the definition's own in Expert mode
        app.sent = Some((dir.join("SEND.DAT"), sample.clone()));
        app.camera_job = Some(CameraJob::finished(JobKind::Verify, Ok((p.clone(), String::new())), None));
        app.poll_camera_job();
        let lines = &app.camera_report.as_ref().unwrap().lines;
        assert!(lines.iter().any(|(l, _)| l == "Only 1 values the camera resets on every start differ: it holds what was written."), "{lines:?}");
        app.prefs.expert = true;
        app.sent = Some((dir.join("SEND.DAT"), sample));
        app.camera_job = Some(CameraJob::finished(JobKind::Verify, Ok((p, String::new())), None));
        app.poll_camera_job();
        app.prefs.expert = false;
        let lines = &app.camera_report.as_ref().unwrap().lines;
        assert!(lines.iter().any(|(l, _)| l == "Only the 1 load toggle flag(s) differ, which flip on every load: the camera holds what was written."), "{lines:?}");
        done(&dir, &user);
        // without them: the link's usual times and the editor's own words
        let (mut app, dir, user) = sample_app("link_bare", Some(|v| {
            let c = v["camera"].as_object_mut().unwrap();
            c.remove("link_timing");
            for k in ["read_failed_usb", "read_failed_network", "volatile_note"] { c["text"].as_object_mut().unwrap().remove(k); }
        }));
        assert_eq!(app.link_timing(), LinkTiming::default());
        assert!(app.read_failed_hint(true).is_none());
        app.prefs.link = "usb".into();
        app.camera_job = Some(CameraJob::finished(JobKind::Read, Err("no camera\n".into()), None));
        app.poll_camera_job();
        assert!(app.camera_report.as_ref().unwrap().lines.iter().any(|(l, _)| l.contains("set to remote control over USB")));
        done(&dir, &user);
    }
}
