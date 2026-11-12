//! The window's side of crash recovery (`recovery`): the journal of the open file's unsaved edits kept up to date,
//! and the edits an earlier session left offered at start.

use crate::*;

impl App {
    /// Where the journals of unsaved edits are kept (`recovery`): `recovery/` beside the preferences.
    pub(crate) fn recovery_dir() -> PathBuf {
        Prefs::path().parent().map_or_else(|| PathBuf::from("recovery"), |d| d.join("recovery"))
    }

    /// After each frame: the journal of the open file's unsaved edits kept up to date (`recovery`), a frame asked for
    /// when the next write is due.
    pub(crate) fn journal_tick(&mut self, ctx: &egui::Context) {
        if let Some(wait) = self.journal_at(std::time::Instant::now()) {
            ctx.request_repaint_after(wait);
        }
    }

    /// `journal_tick` at `now`: how long until the next write, while one waits.
    pub(crate) fn journal_at(&mut self, now: std::time::Instant) -> Option<std::time::Duration> {
        let key = self.doc.as_ref().map(|d| (d.opened, d.rev));
        // whether the file has edits, worked out once per state of it
        let edits = match (key, self.journal.seen) {
            (None, _) => false,
            (Some(k), Some((seen, e))) if k == seen => e,
            (Some(k), _) => {
                let e = self.unsaved() > 0;
                self.journal.seen = Some((k, e));
                e
            }
        };
        match self.journal.step(now, key.filter(|_| edits)) {
            recovery::Step::Idle => None,
            recovery::Step::Wait(left) => Some(left),
            recovery::Step::Write => {
                let d = self.doc.as_ref()?;
                let (kind, link, read_at) = match &d.source {
                    Source::Disk => ("disk", "", ""),
                    Source::Sample => ("sample", "", ""),
                    Source::Camera { link, read_at } => ("camera", link.as_str(), read_at.as_str()),
                };
                let s = &self.schema;
                let meta = recovery::Meta {
                    source: d.path.display().to_string(),
                    kind: kind.into(),
                    link: link.into(),
                    read_at: read_at.into(),
                    saved: d.saved,
                    edit_anyway: d.unchecked_ok,
                    definition: if s.model.is_empty() { String::new() } else { format!("{} firmware {}", s.model, s.firmware()) },
                    definition_file: s.origin.path().map(|p| p.display().to_string()).unwrap_or_default(),
                    time: local_stamp(),
                    edits: d.unsaved(),
                    pid: std::process::id(),
                };
                // recovered edits whose file as opened was not kept: no copy of it either, so the next start knows that too;
                // the file as first opened or read beside it, when a Save As came between (what the edits are judged against)
                let original = (d.recovered == 0).then(|| d.original.to_bytes());
                let first = (d.recovered == 0 && !Self::same_records(&d.baseline, &d.original)).then(|| d.baseline.to_bytes());
                let (rev, path, edited) = (d.rev, d.path.clone(), d.edited.to_bytes());
                self.journal.write(rev, &path, &file_stamp(), edited, original.as_deref().map(|o| (o, first.as_deref())), meta);
                None
            }
        }
    }

    /// The editor quits as it should: its journal goes (it stays when the editor stopped on an error).
    pub(crate) fn end_session(&mut self) {
        if recovery::CRASHED.load(std::sync::atomic::Ordering::SeqCst) {
            self.journal.finish();
        } else {
            self.journal.close();
        }
    }

    /// Open the edits an earlier session left unsaved (the journal `base`) as file A: the file as it was opened, with
    /// those edits on it, not saved yet, under the name it had. This session's journal takes them over. Err: why not,
    /// for Expert mode; the status says it in plain words.
    pub(crate) fn open_recovered(&mut self, base: &str) -> Result<(), String> {
        let [dat, orig, json] = recovery::paths(&self.journal.dir, base);
        let meta: recovery::Meta = std::fs::read_to_string(&json).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default();
        let sample = meta.kind == "sample";
        let read = std::fs::read(&dat).map_err(LoadError::Io).and_then(|b| self.defs.open(&b, sample).map_err(LoadError::Parse));
        let o = match read {
            Ok(o) => o,
            Err(e) => {
                self.status = format!("The recovered edits could not be opened: {} They are kept; open them again from the next start, or discard them then.", self.load_words(&dat, &e));
                return Err(format!("{}: {e}", dat.display()));
            }
        };
        // the file as it was opened, so the edits show as edits; without it, the recovered file stands for both, and its
        // edits count as unsaved all the same (`Doc::recovered`), so nothing lets them go without a question
        let original = std::fs::read(&orig).ok().and_then(|b| self.defs.open(&b, sample).ok()).map(|x| x.set)
            .filter(|c| c.sections.len() == o.set.sections.len() && c.model() == o.set.model());
        let kept_original = original.is_some();
        let original = original.unwrap_or_else(|| o.set.clone());
        // the file as first opened or read in that session, when a Save As came between: what its edits were judged against
        let baseline = std::fs::read(recovery::baseline_path(&self.journal.dir, base)).ok().and_then(|b| self.defs.open(&b, sample).ok()).map(|x| x.set)
            .filter(|c| kept_original && c.sections.len() == o.set.sections.len() && c.model() == o.set.model())
            .unwrap_or_else(|| original.clone());
        let signature = original.layout_signature();
        let source = match meta.kind.as_str() {
            "sample" => Source::Sample,
            "camera" => Source::Camera { link: meta.link.clone(), read_at: meta.read_at.clone() },
            _ => Source::Disk,
        };
        let path = if meta.source.is_empty() { dat.clone() } else { PathBuf::from(&meta.source) };
        let name = path.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_else(|| path.display().to_string());
        self.adopt(o.def);
        self.undo.clear();
        self.redo.clear();
        self.target = self.target.min(o.set.sections.len().saturating_sub(1));
        self.fit_cols(o.set.sections.len());
        let opened = next_open();
        let recovered = if kept_original { 0 } else { meta.edits.max(1) };
        self.doc = Some(Doc { path, baseline, original, edited: o.set, signature, source, unchecked_ok: meta.edit_anyway, how: o.how, override_def: None, opened, rev: next_open(), saved: meta.saved, recovered });
        self.last_edit = None;
        self.remember_session();
        self.journal.adopt(base.to_string(), opened);
        let n = self.unsaved();
        self.status = if kept_original {
            format!("Recovered {n} unsaved {} to {name}. Save them with Save As….", if n == 1 { "edit" } else { "edits" })
        } else {
            format!("Recovered the edits to {name}. The file as it was opened was not kept with them, so they do not show as edits; save them with Save As….")
        };
        Ok(())
    }

    /// The answer to the offer of recovered edits (the first in `recovered`): open them (after asking when that
    /// replaces edits open now), or throw them away.
    fn answer_recovered(&mut self, open: bool) {
        if self.recovered.is_empty() { return; }
        let f = self.recovered.remove(0);
        if open {
            self.guard(Replace::Recover(f.base));
        } else {
            recovery::remove(&self.journal.dir, &f.base);
            self.status = format!("The recovered edits to {} were thrown away.", f.name());
        }
    }

    /// At start, edits an earlier session left unsaved (`recovered`, the newest first), one at a time: "The editor
    /// closed with N unsaved edits to CAMSET01.DAT." Open the recovered edits, or Discard.
    pub(crate) fn recovery_window(&mut self, ctx: &egui::Context) {
        let Some(f) = self.recovered.first() else { return };
        let n = f.meta.edits;
        let when = when_words(&f.meta.time);
        let when = if when.contains(" at ") { format!("on {when}") } else { format!("at {when}") };
        let detail = self.prefs.expert.then(|| {
            let def = if f.meta.definition.is_empty() { "no definition".to_string() } else { format!("the {} definition", f.meta.definition) };
            format!("Made to {}, read with {def}. Kept in {}.", f.meta.source, recovery::paths(&self.journal.dir, &f.base)[0].display())
        });
        let (mut open, mut discard) = (false, false);
        egui::Window::new("Recovered edits").collapsible(false).resizable(false).anchor(egui::Align2::CENTER_CENTER, [0.0, 0.0]).show(ctx, |ui| {
            ui.label(format!("The editor closed with {n} unsaved {} to {}.", if n == 1 { "edit" } else { "edits" }, f.name()));
            ui.label(RichText::new(format!("They were kept {when}. Opening them shows the file with the edits, not saved yet.")).color(tone::weak(ui.visuals())));
            if let Some(d) = &detail {
                ui.label(RichText::new(d).color(tone::weak(ui.visuals())).small());
            }
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui.button("Open the recovered edits").on_hover_text("Open the file with these edits on it, not saved yet: save them with Save As…").clicked() { open = true; }
                if ui.button("Discard").on_hover_text("Throw these edits away. The file they were made to is not changed.").clicked() { discard = true; }
            });
        });
        if open || discard {
            self.answer_recovered(open);
        }
    }
}

#[cfg(test)]
pub(crate) mod recovery_tests {
    use super::*;

    /// The journal as it stands once the wait after the last edit is over, the helper thread done.
    fn journal_written(app: &mut App) {
        let now = std::time::Instant::now();
        app.journal_at(now);
        app.journal_at(now + recovery::WAIT);
        app.journal.finish();
    }

    /// An edit is kept in a journal a moment after it is made; a start after a session that ended without saving it
    /// offers it; opening it brings back the file under the name it had, with the edit as an edit; Discard throws one
    /// away; saving, closing or a clean quit removes the journal.
    #[test]
    fn start_up_offers_the_recovered_edits() {
        let sample = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        let dir = std::env::temp_dir().join(format!("camset_recovery_start_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let src = dir.join("CAMSET07.DAT");
        std::fs::write(&src, sample).unwrap();
        // a session that edits the file and stops before saving it
        let mut first = App::new(vec![src.display().to_string()], Prefs::default());
        let (s, v) = crate::write::safety_tests::changeable(&first);
        first.apply(vec![Action::Set(0, s.slot(), v)]);
        let now = std::time::Instant::now();
        assert!(first.journal_at(now).is_some(), "written a moment later");
        assert!(first.journal_at(now + recovery::WAIT).is_none());
        first.journal.finish();
        let base = first.journal.base().expect("a journal").to_string();
        assert!(base.starts_with("CAMSET07_"));
        let files = recovery::paths(&App::recovery_dir(), &base);
        assert!(files.iter().all(|p| p.is_file()));
        drop(first);   // no clean quit: the journal stays

        // the next start offers it (the journal was this process's, which counts as not running)
        let mut next = App::new(vec![], Prefs::default());
        let at = next.recovered.iter().position(|f| f.base == base).expect("offered");
        assert_eq!((next.recovered[at].meta.edits, next.recovered[at].name().as_str()), (1, "CAMSET07.DAT"));
        next.recovered.swap(0, at);
        next.answer_recovered(true);
        let d = next.doc.as_ref().expect("opened");
        assert_eq!((d.path.as_path(), d.source == Source::Disk, d.saved), (src.as_path(), true, false));
        assert_eq!(next.unsaved(), 1, "the edit shows as an edit");
        assert_eq!(next.doc.as_ref().unwrap().value(0, s.slot()), Some(v));
        assert!(next.status.contains("Recovered 1 unsaved edit to CAMSET07.DAT"), "{}", next.status);
        // this session takes the journal over, under the same name; saving removes it
        assert_eq!(next.journal.base(), Some(base.as_str()));
        assert!(next.journal_at(std::time::Instant::now()).is_none(), "written again at once");
        next.journal.finish();
        let saved = dir.join("CAMSET08.DAT");
        next.save_to(saved.clone());
        assert!(saved.is_file() && next.unsaved() == 0);
        next.journal_at(std::time::Instant::now());
        next.journal.finish();
        assert!(files.iter().all(|p| !p.exists()), "removed once saved");

        // another session's edits: offered, then thrown away
        let u = crate::write::safety_tests::changeable(&next).1;
        next.apply(vec![Action::Set(0, s.slot(), u)]);
        journal_written(&mut next);
        let other = next.journal.base().expect("a journal").to_string();
        assert!(other.starts_with("CAMSET08_"));
        let mut third = App::new(vec![], Prefs::default());
        let at = third.recovered.iter().position(|f| f.base == other).expect("offered");
        third.recovered.swap(0, at);
        third.answer_recovered(false);
        assert!(third.doc.is_none() && recovery::paths(&App::recovery_dir(), &other).iter().all(|p| !p.exists()));
        assert!(third.status.contains("thrown away"));

        // closing the file removes its journal, and so does a clean quit
        // (undone and made again: a new state of the file, written again)
        next.apply(vec![Action::Revert(0, (s.slot().0, None))]);
        journal_written(&mut next);
        assert!(next.journal.base().is_none(), "no edits, no journal");
        next.apply(vec![Action::Set(0, s.slot(), u)]);
        journal_written(&mut next);
        let again = next.journal.base().expect("written again").to_string();
        assert!(recovery::paths(&App::recovery_dir(), &again)[0].is_file());
        next.close_file_now();
        next.journal_at(std::time::Instant::now());
        next.journal.finish();
        assert!(recovery::paths(&App::recovery_dir(), &again).iter().all(|p| !p.exists()), "removed on close");
        next.open(saved.clone());
        next.apply(vec![Action::Set(0, s.slot(), crate::write::safety_tests::changeable(&next).1)]);
        let now = std::time::Instant::now();
        next.journal_at(now);
        next.journal_at(now + recovery::WAIT);
        let last = next.journal.base().expect("a journal").to_string();
        next.end_session();
        assert!(recovery::paths(&App::recovery_dir(), &last).iter().all(|p| !p.exists()), "removed on a clean quit");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Recovered edits whose journal kept no copy of the file as opened (`Doc::recovered`): no record shows them as
    /// edits, yet they count as unsaved, as many as the journal held. Close asks first, as quitting does, Save As is
    /// offered and Swap A/B refused; the journal stays, still without a copy of the file as opened, so a start after
    /// another crash counts them again; a save ends it, and Close then closes without asking.
    #[test]
    fn recovered_edits_without_their_original_are_unsaved_work() {
        let sample = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        let dir = std::env::temp_dir().join(format!("camset_recovery_no_original_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let src = dir.join("CAMSET31.DAT");
        std::fs::write(&src, sample).unwrap();
        // a session that edits the file and stops before saving it; its copy of the file as opened is then lost
        let mut first = App::new(vec![src.display().to_string()], Prefs::default());
        first.apply(first.demo_edits());
        let n = first.unsaved();
        assert!(n > 1, "{n} edits");
        journal_written(&mut first);
        let base = first.journal.base().expect("a journal").to_string();
        let [_, orig, json] = recovery::paths(&App::recovery_dir(), &base);
        std::fs::remove_file(&orig).unwrap();
        drop(first);   // no clean quit: the journal stays
        let open = |base: &str| {
            let mut app = App::new(vec![], Prefs::default());
            let at = app.recovered.iter().position(|f| f.base == base).expect("offered");
            app.recovered.swap(0, at);
            app.answer_recovered(true);
            app
        };
        // the next start: no record shows an edit, but the edits the journal held count as unsaved
        let mut app = open(&base);
        let d = app.doc.as_ref().expect("opened");
        assert!(d.changes().is_empty() && d.recovered == n && d.unsaved() == n, "{} {}", d.changes().len(), d.recovered);
        assert_eq!(app.unsaved(), n);
        assert!(app.status.contains("was not kept with them"), "{}", app.status);
        assert!(app.edits_hash().is_some(), "a read agreed to replace them names them");
        assert!(app.can_save_as(), "Save As is offered");
        // Close asks first, and so does closing the editor
        app.close_file();
        assert!(app.doc.is_some() && matches!(app.unsaved_ask, Some(Replace::Close)), "Close asks");
        app.unsaved_ask = None;
        app.guard(Replace::Quit);
        assert!(!app.close_ok && matches!(app.unsaved_ask, Some(Replace::Quit)), "closing the editor asks");
        app.unsaved_ask = None;
        app.open_compare(src.clone());
        assert!(app.swap_ab().is_err_and(|e| e.starts_with("Save or revert the edits first")), "Swap A/B would drop them");
        let page = crate::web::tests::answer(&mut app, "swap_ab", serde_json::json!({}));
        let words = String::from_utf8_lossy(&page.body).to_string();
        assert!(page.status == 409 && words.contains("Download or revert the edits first"), "the page's own words: {words}");
        // the journal stays, the count in it, and still no copy of the file as opened
        journal_written(&mut app);
        assert_eq!(app.journal.base(), Some(base.as_str()), "kept");
        assert!(!orig.exists(), "no copy of the file as opened written from the recovered file");
        let meta: recovery::Meta = serde_json::from_str(&std::fs::read_to_string(&json).unwrap()).unwrap();
        assert_eq!(meta.edits, n);
        drop(app);   // another crash
        let mut app = open(&base);
        assert_eq!((app.unsaved(), app.doc.as_ref().unwrap().recovered), (n, n), "counted again after another crash");
        // a save ends it: nothing is unsaved, Close closes without asking, and the journal goes
        let saved = dir.join("CAMSET32.DAT");
        app.save_to(saved.clone());
        assert!(saved.is_file() && app.unsaved() == 0 && app.doc.as_ref().unwrap().recovered == 0, "{}", app.status);
        assert!(!app.can_save_as(), "nothing left to save");
        app.close_file();
        assert!(app.doc.is_none() && app.unsaved_ask.is_none(), "closed without asking");
        app.journal_at(std::time::Instant::now());
        app.journal.finish();
        assert!(recovery::paths(&App::recovery_dir(), &base).iter().all(|p| !p.exists()), "the journal goes");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The journal keeps the file as first opened beside the file as last saved, when a Save As came between: recovered,
    /// the edits are judged against the file first opened as before, so an edit saved before the crash is still listed,
    /// and the window offers to put it back to what the camera wrote. Without a Save As no such copy is kept.
    #[test]
    fn a_recovered_session_keeps_the_file_first_opened() {
        let dir = std::env::temp_dir().join(format!("camset_recovery_baseline_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let src = dir.join("CAMSET41.DAT");
        std::fs::write(&src, crate::test_support::camera_file()).unwrap();
        let mut first = App::new(vec![src.display().to_string()], Prefs::default());
        first.prefs.expert = true;
        let (u, w) = first.schema.settings.iter().filter(|s| s.area == "global" && s.scalar && s.text.is_none() && s.copies.is_empty() && s.copy_of.is_none() && s.proved.is_none() && s.values.len() >= 2 && first.shape_ok_in(s, 0))
            .find_map(|s| { let cur = first.col_value(Col::a(0), s)?; s.values.iter().map(|(x, _)| *x).find(|x| *x != cur).map(|x| (s.clone(), x)) })
            .expect("a setting with no proof");
        first.apply(vec![Action::Set(0, u.slot(), w)]);
        journal_written(&mut first);
        let base = first.journal.base().expect("a journal").to_string();
        assert!(!recovery::baseline_path(&App::recovery_dir(), &base).exists(), "no Save As yet: the file as opened is the file first opened");
        first.save_to(dir.join("CAMSET42.DAT"));
        let (s, v) = crate::write::safety_tests::changeable(&first);
        first.last_edit = None;
        first.apply(vec![Action::Set(0, s.slot(), v)]);
        journal_written(&mut first);
        let base = first.journal.base().expect("a journal").to_string();
        assert!(recovery::baseline_path(&App::recovery_dir(), &base).is_file(), "the file first opened, kept beside the file as saved");
        drop(first);   // no clean quit: the journal stays
        let mut app = App::new(vec![], Prefs::default());
        let at = app.recovered.iter().position(|f| f.base == base).expect("offered");
        app.recovered.swap(0, at);
        app.answer_recovered(true);
        let issues = app.acceptance_issues();
        let one = issues.iter().find(|i| i.slot == u.slot()).expect("the edit saved before the crash is still judged");
        assert_eq!(app.issue_fix(one).map(|(w, _)| w).as_deref(), Some(crate::write::REVERT_TO_CAMERA));
        app.journal.close();
        assert!(!recovery::baseline_path(&App::recovery_dir(), &base).exists(), "removed with the journal");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Recovered edits to a file read from the camera, whose journal kept no copy of it as read: once the camera's
    /// read-back confirms a write of them, file A starts from what the camera holds, nothing is left unsaved, Close
    /// closes without asking, and the journal goes.
    #[test]
    fn a_confirmed_write_of_recovered_edits_leaves_none_unsaved() {
        let sample = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        let dir = std::env::temp_dir().join(format!("camset_recovery_written_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let src = dir.join("CAMSET33.DAT");
        std::fs::write(&src, sample).unwrap();
        let mut first = App::new(vec![src.display().to_string()], Prefs::default());
        first.apply(first.demo_edits());
        let n = first.unsaved();
        journal_written(&mut first);
        let base = first.journal.base().expect("a journal").to_string();
        std::fs::remove_file(&recovery::paths(&App::recovery_dir(), &base)[1]).unwrap();
        drop(first);   // no clean quit: the journal stays
        let mut app = App::new(vec![], Prefs::default());
        let at = app.recovered.iter().position(|f| f.base == base).expect("offered");
        app.recovered.swap(0, at);
        app.answer_recovered(true);
        assert_eq!((app.unsaved(), app.doc.as_ref().unwrap().recovered), (n, n));
        // as a file read from the camera, written to it, and read back holding exactly that
        let d = app.doc.as_mut().unwrap();
        d.source = Source::Camera { link: "USB".into(), read_at: "20260101_000000".into() };
        let edited = d.edited.clone();
        let sent = dir.join("SEND.DAT");
        std::fs::write(&sent, edited.to_bytes()).unwrap();
        app.sent = Some((sent, edited.clone()));
        let back = dir.join("verify_recovered.DAT");
        std::fs::write(&back, edited.to_bytes()).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::Verify, Ok((back.clone(), String::new())), None));
        app.poll_camera_job();
        assert_eq!(app.camera_report.as_ref().map(|r| r.title.as_str()), Some("✔ Camera confirmed"));
        let d = app.doc.as_ref().unwrap();
        assert_eq!((d.path.as_path(), d.recovered, app.unsaved()), (back.as_path(), 0, 0), "file A is what the camera holds");
        assert!(!app.can_save_as());
        app.close_file();
        assert!(app.doc.is_none() && app.unsaved_ask.is_none(), "closed without asking");
        app.journal_at(std::time::Instant::now());
        app.journal.finish();
        assert!(recovery::paths(&App::recovery_dir(), &base).iter().all(|p| !p.exists()), "the journal goes");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
