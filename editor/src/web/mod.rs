//! The web page: a small HTTP server inside the editor, off until turned on in Settings, so a
//! browser on another computer, a tablet or a phone can use this editor: read the camera, change
//! settings, send them, download or open a file. It is meant for a camera far from where you sit,
//! on the network with the computer that runs the editor. The page holds nothing of its own: the
//! editor answers every request from its open file, so the window and the page show the same file
//! and the same edits.
//!
//! Every request except the page itself needs the access code shown in Settings, a new one each time
//! the page is turned on and kept in memory only. The page sends it once, to `login`, for a session
//! token it sends in a header with each request after (never in the address); a session ends after
//! 12 hours without a request, at `logout`, and when the page is turned off. A request with the code
//! itself in its header is taken too. Wrong codes are counted per client address. The server answers
//! only requests sent to its own address or this computer's name (`Host`), and refuses one a page of
//! another site sent (`Origin`), so a site in a browser on the network cannot use it. It is plain
//! HTTP: across the internet, go through a VPN or an SSH tunnel rather than opening the port on a
//! router.
//!
//! The protocol, for editor/web/app.js: `POST /api/login` with the code in `X-Camset-Code` answers
//! `{"session": <token>, "idle_hours": 12}` (401 for a wrong code, 429 while that address has sent
//! too many); every other `POST /api/<name>` carries `X-Camset-Session: <token>`, and an ended one
//! answers 401 with `"session": "ended"`; `POST /api/logout` ends the session it carries. When the
//! page is turned off or the editor quits, waiting requests answer 503 with `"closed": true`.

use super::*;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::mpsc;
use std::time::{Duration, Instant};

mod server;
pub(super) use server::WebServer;
use server::*;

/// The preferences the page may change: how values are shown. Expert mode, its options (values no proof established, raw edits)
/// and Edit anyway open what can harm the camera, so they are set in the desktop app only; theme, text size and row
/// spacing are the page's own, kept in its browser.
const WEB_DISPLAY_PREFS: [&str; 6] = ["show_record_ids", "show_proof", "show_raw", "flat_list", "matrix_only_diff", "all_memory_cols"];
/// Files sent up from the page kept in the editor's camera/web folder (the latest; one open now is never removed).
const WEB_UPLOADS_KEPT: usize = 20;
/// Search results shown at most.
const MAX_HITS: usize = 300;
/// A colour as CSS writes it, #rrggbb.
fn css_color(c: Color32) -> String {
    format!("#{:02x}{:02x}{:02x}", c.r(), c.g(), c.b())
}

/// The status line as the web page is turned on, followed by its address; the page's own status line says it so.
const WEB_ON: &str = "Web page on at";
const WEB_ON_FOR_PAGE: &str = "Web page on (its address is shown in the desktop app's Settings)";

/// What the page says where only the desktop app can help: the login is entered there, and a camera is forgotten (so
/// it is trusted again) there; the page has no button for either.
const WEB_LOGIN_IN_DESKTOP: &str = "The camera's user name and password are entered on the computer that runs the editor: Connect to the camera, Network address and camera login. The page never sends them.";
const WEB_FORGET_IN_DESKTOP: &str = "Forget the camera in the desktop app (Connect to the camera, Known cameras): forgetting it on this page takes it off the list only.";

impl App {
    /// Turn the web page on or off. Each time it is turned on it gets a new access code, kept in memory only, so every
    /// browser that had the old one, and every session, is out. It opens to the network (on this computer's address
    /// there) only when the person turns it on (`by_hand`) with "from the network" chosen; turned on as the editor
    /// starts, it is for this computer only.
    pub(super) fn web_switch(&mut self, on: bool, by_hand: bool, ctx: &egui::Context) {
        if !on {
            if self.web.take().is_some() {
                self.status = "Web page off".into();
            }
            return;
        }
        if self.web.is_some() {
            return;
        }
        let everyone = by_hand && !self.prefs.web_local_only;
        let code = new_code();
        match WebServer::start(self.prefs.web_port.unwrap_or(DEFAULT_PORT), everyone, &code, ctx.clone()) {
            Ok(w) => {
                // test hook, for tests and screenshots only: CAMSET_WEB_CODE_FILE=path writes each new access code to
                // that file (readable by this user only), so a script can sign in to the page; otherwise the code is
                // kept nowhere but in memory and shown only in Settings
                if let Some(p) = std::env::var_os("CAMSET_WEB_CODE_FILE") {
                    let _ = write_private(Path::new(&p), &code);
                }
                self.status = format!("{WEB_ON} {}", w.url);
                self.web = Some(w);
                self.web_error.clear();
            }
            Err(e) => {
                let details = e.system_words().map(|w| details(self.prefs.expert, w)).unwrap_or_default();
                self.web_error = format!("The web page could not start: {}{details}", e.words());
                self.status = self.web_error.clone();
            }
        }
    }

    /// Answer the requests that came in since the last frame. Called every frame.
    pub(super) fn web_poll(&mut self, ctx: &egui::Context) {
        if self.web_start_pending {
            self.web_start_pending = false;
            self.web_switch(true, false, ctx);
        }
        let Some(w) = &self.web else { return };
        let requests: Vec<WebRequest> = w.requests.try_iter().collect();
        for r in requests {
            let reply = self.web_answer(&r);
            if let Some(w) = &mut self.web {
                w.last = Some((r.peer.clone(), local_stamp()));
            }
            let _ = r.reply.send(reply);
        }
    }

    /// The Web page section of Settings; true when a preference changed.
    pub(super) fn web_settings(&mut self, ui: &mut egui::Ui) -> bool {
        let mut changed = false;
        ui.label(RichText::new("Use this editor from a browser on another computer, a tablet or a phone: read the camera, change settings and send them. For a camera far away on a network, run the editor on a computer on that network and open the page from wherever you are. The page works on the file open here, so edits show in both.").small().color(tone::weak(ui.visuals())));
        let mut on = self.web.is_some();
        let mut switch = None;
        ui.horizontal(|ui| {
            if ui.checkbox(&mut on, "Web page on").changed() {
                switch = Some(on);
            }
            ui.add_enabled_ui(!on, |ui| {
                ui.label("Port:");
                let mut port = self.prefs.web_port.unwrap_or(DEFAULT_PORT);
                if crate::named(ui.add(egui::DragValue::new(&mut port).range(1024..=65535)), "Web page port").changed() {
                    self.prefs.web_port = Some(port).filter(|p| *p != DEFAULT_PORT);
                    changed = true;
                }
                if ui.radio(!self.prefs.web_local_only, "from the network").on_hover_text("Other computers and phones that can reach this one may open the page").clicked() {
                    self.prefs.web_local_only = false;
                    changed = true;
                }
                if ui.radio(self.prefs.web_local_only, "this computer only").on_hover_text("Only a browser on this computer, or one coming through an SSH tunnel to it").clicked() {
                    self.prefs.web_local_only = true;
                    changed = true;
                }
            });
        });
        if let Some((url, code, last, everyone)) = self.web.as_ref().map(|w| (w.url.clone(), w.code.clone(), w.last.clone(), w.everyone)) {
            let link = format!("{url}/#code={code}");
            ui.horizontal(|ui| {
                ui.label("Open");
                ui.label(RichText::new(&url).monospace().strong());
                ui.label("and enter the access code");
                ui.label(RichText::new(&code).monospace().strong());
            });
            if !everyone && !self.prefs.web_local_only {
                ui.label(RichText::new("Turned on as the editor started, so for this computer only. Turn it off and on again to open it to the network.").small());
            }
            ui.horizontal(|ui| {
                if ui.button("Copy link with the code").on_hover_text("The code goes after # in the link, which the browser does not send over the network; the page then removes it from the address").clicked() {
                    ui.ctx().copy_text(link);
                    self.status = "Web page link copied".into();
                }
                if ui.button("New code").on_hover_text("Every browser that has the old code, or is logged in with it, must enter the new one").clicked() {
                    switch = Some(true);
                    self.web = None;
                }
            });
            ui.label(RichText::new("A new code is made each time the page is turned on; it is not kept anywhere. A browser that entered it stays logged in until 12 hours pass without its use, or the page is turned off.").small().color(tone::weak(ui.visuals())));
            match &last {
                Some((peer, at)) => ui.label(RichText::new(format!("Last used from {peer} at {}", when_words(at))).small()),
                None => ui.label(RichText::new("Not used yet").small().color(tone::weak(ui.visuals()))),
            };
        }
        if !self.web_error.is_empty() {
            ui.label(RichText::new(&self.web_error).color(tone::bad(ui.visuals())));
        }
        ui.label(RichText::new("Anyone who can reach this computer and has the code can change the camera's settings and send them. The page is plain HTTP, so anyone on the same network can read the code as it is entered, and the settings: on a network you do not trust, or across the internet, use a VPN or an SSH tunnel, and do not open the port on a router.").small().color(tone::caution(ui.visuals())));
        if ui.checkbox(&mut self.prefs.web_at_start, "Turn the web page on when the editor starts (for this computer only)").changed() {
            changed = true;
        }
        if let Some(on) = switch {
            if changed {
                self.prefs.save();
            }
            self.web_switch(on, true, ui.ctx());
        }
        changed
    }

    fn web_answer(&mut self, r: &WebRequest) -> WebReply {
        let body: Value = serde_json::from_slice(&r.body).unwrap_or(Value::Null);
        let action = body["action"].as_str().unwrap_or(r.name.as_str());
        let target = body["target"].as_u64().unwrap_or(0) as usize;
        let needs_target = matches!(action, "tab" | "main" | "set" | "revert" | "restore" | "activate" | "unmapped" | "records" | "raw_set" | "csv");
        if needs_target && !self.shown_sections().contains(&target) {
            return WebReply::error(400, "This file has no such set.");
        }
        let needs_file = !matches!(action, "state" | "read" | "open" | "dismiss" | "retry" | "put_back" | "sample" | "backups" | "open_backup" | "prefs" | "changelog"
            | "open_recent" | "clear_recent" | "reload_schemas" | "camera_link" | "camera_search" | "camera_use" | "camera_name" | "camera_forget"
            | "camera_check" | "camera_steps" | "switch_usb" | "camera_cards" | "camera_report" | "send_cancel");
        if needs_file && self.doc.is_none() {
            return WebReply::error(409, "No file is open in the editor. Read the camera or open a file first.");
        }
        let idle = self.camera_job.is_none();
        // the status line every page reads names no address: who sent it shows in the desktop app's Settings only
        let from = "from the web page".to_string();
        // the page asked the person before a request that replaces file A over unsaved edits
        let discard = r.discard || body["discard"].as_bool() == Some(true);
        match action {
            // the menu's counts are for the set the page edits (the live settings when it names none it can show)
            "state" => WebReply::json(self.web_state(if self.shown_sections().contains(&target) { target } else { 0 })),
            "tab" => WebReply::json(self.web_tab(target, body["tab"].as_str(), body["q"].as_str().unwrap_or(""))),
            "main" => WebReply::json(self.web_main(target, body["set"].as_u64().unwrap_or(0) as usize)),
            "set" => self.web_set(target, &body, &from),
            "revert" => {
                let Some(linked) = self.web_linked(target, body["key"].as_str().unwrap_or("")) else { return WebReply::error(404, "No such setting here.") };
                // as the window's Revert: a copy in step with its setting takes the setting and its other copies back
                // along (`apply`); a step that would leave a setting held by none of its copies is refused, with why
                if let Some(why) = self.apply(linked.iter().map(|l| Action::Revert(target, l.slot())).collect()) {
                    return WebReply::error(409, &why);
                }
                self.status = format!("{} reverted {from}", linked[0].name);
                WebReply::json(json!({ "ok": true }))
            }
            // what the camera keeps, put back where the plain Revert changes nothing (`put_back_choice`): a value a Save
            // As kept, a copy back in step with its setting. A copy whose record has another shape than mapped is left,
            // and the status says so, as `apply` says it
            "restore" => {
                let Some(linked) = self.web_linked(target, body["key"].as_str().unwrap_or("")) else { return WebReply::error(404, "No such setting here.") };
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                let odd = linked.iter().filter(|l| l.copy_of.is_some() && !self.shape_ok_in(l, target) && self.put_back_value(l, target).is_some()).count();
                let Some((words, acts)) = self.put_back_choice(&linked, target) else {
                    if odd > 0 {
                        return WebReply::error(409, &left_alone(Left { copies_shape: odd, ..Default::default() }));
                    }
                    return WebReply::error(409, "Nothing to put back: this setting holds what the camera keeps here.");
                };
                if let Some(why) = self.apply(acts) {
                    return WebReply::error(409, &why);
                }
                self.status = with_left(&format!("{}: {} {from}", linked[0].name, words.to_lowercase()), Left { copies_shape: odd, ..Default::default() });
                WebReply::json(json!({ "ok": true }))
            }
            "revert_record" => {
                let si = body["section"].as_u64().and_then(|i| usize::try_from(i).ok()).unwrap_or(usize::MAX);
                let Some(id) = body["id"].as_u64().and_then(|i| u16::try_from(i).ok()) else { return WebReply::error(400, "Name a record.") };
                if si >= self.n_sections() {
                    return WebReply::error(400, "This file has no such set.");
                }
                if let Some(why) = self.apply(vec![Action::Revert(si, (id, None))]) {
                    return WebReply::error(409, &why);
                }
                self.status = format!("Record 0x{id:04x} reverted {from}");
                WebReply::json(json!({ "ok": true }))
            }
            "revert_flagged" => {
                // what the window's Revert all flagged puts back: each listed value's own fix (`issue_fix`)
                let fixes: Vec<Vec<Action>> = self.write_issues().iter().filter_map(|is| self.issue_fix(is).map(|(_, a)| a)).collect();
                let n = fixes.len();
                if let Some(why) = self.apply(fixes.into_iter().flatten().collect()) {
                    return WebReply::error(409, &why);
                }
                self.status = format!("{n} flagged value(s) reverted {from}");
                WebReply::json(json!({ "ok": true }))
            }
            "activate" => {
                let Some(linked) = self.web_linked(target, body["key"].as_str().unwrap_or("")) else { return WebReply::error(404, "No such setting here.") };
                let Some(rule) = linked[0].inactive_when.clone() else { return WebReply::error(400, "This setting is not greyed out.") };
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                // a refusal (the record view only outside Expert mode, a file left other than the camera keeps it) is
                // said, as every handler that changes the file says it, and the status keeps the reason
                if let Some(why) = self.apply(vec![Action::Set(target, (rule.record, None), rule.unlock)]) {
                    return WebReply::error(409, &why);
                }
                self.status = format!("{} set to {} {from}", rule.name, rule.unlock_label);
                WebReply::json(json!({ "ok": true }))
            }
            "undo" => {
                self.undo();
                WebReply::json(json!({ "ok": true }))
            }
            "redo" => {
                self.redo();
                WebReply::json(json!({ "ok": true }))
            }
            "memories" | "recall" | "register" | "memory_copy" if self.dial_sets().is_empty() => {
                WebReply::error(409, "This camera's definition names no mode-dial memories.")
            }
            "memories" => WebReply::json(self.web_memories(body["q"].as_str().unwrap_or(""), body["all"].as_bool(), body["only_diff"].as_bool())),
            "mymenu_page" if !self.has_mymenu_page() => WebReply::error(409, &format!("This camera's definition has no {}.", self.schema.camera.text.my_menu_name())),
            // the live settings whatever set the page edits, which only its note names
            "mymenu_page" => WebReply::json(self.web_mymenu(if self.shown_sections().contains(&target) { target } else { 0 })),
            "recall" | "register" => self.web_recall(action == "recall", &body, &from),
            "memory_copy" => self.web_memory_copy(&body, &from),
            "exposure" if self.schema.camera.exposure.is_none() => WebReply::error(409, "This camera's definition has no exposure page."),
            "exposure" => WebReply::json(self.web_exposure()),
            "changes" => WebReply::json(self.web_changes()),
            // Settings > About > Changes: the changelog built into this editor, as the window's Changes shows it
            "changelog" => WebReply::json(json!({ "blocks": changelog_blocks(CHANGELOG) })),
            "read" if !idle => WebReply::error(409, "The editor is busy with the camera; wait for it to finish."),
            "read" => {
                if let Some(no) = self.web_unsaved(discard) {
                    return no;
                }
                // agreed by the person on the page: the read replaces these edits, and only these
                let agreed = self.edits_hash();
                self.run_job(JobKind::Read, None, agreed, None);
                WebReply::json(json!({ "ok": true }))
            }
            // the Write window's contents, and the file they are for (`rev`): `send` writes only that file
            // the page's Write, as the window's: `read` starts the read of the camera the write is compared with (the
            // page waits while the state says the editor is busy with the camera); asked again once it is done, the
            // Write window's contents against the camera now, and the file they are for (`rev`): `send` writes only
            // that file, with that read as the copy from just before
            "send_check" => {
                let read = body["read"].as_bool() == Some(true);
                // the read Write started is still running: the page waits (the state names the job)
                if !read && self.camera_job.as_ref().is_some_and(|j| j.kind == JobKind::BeforeWrite) {
                    return WebReply::json(json!({ "reading": true }));
                }
                // (busy with another camera job too)
                if let Some(why) = self.send_blocked() {
                    self.web_write = None;
                    return WebReply::error(409, &why);
                }
                if read {
                    self.before_write = None;
                    self.web_write = Some(WebWrite::Reading);
                    self.run_job(JobKind::BeforeWrite, None, None, None);
                    if self.camera_job.is_none() {
                        // the link could not start (no camera link program, no address): its report says why
                        self.web_write = None;
                        return WebReply::error(409, &self.camera_report.as_ref().map_or_else(|| self.page_status(), |r| r.lines.first().map_or(r.title.clone(), |l| l.0.clone())));
                    }
                    return WebReply::json(json!({ "reading": true }));
                }
                if let Some(WebWrite::Failed(why)) = &self.web_write {
                    let why = why.clone();
                    self.web_write = None;
                    return WebReply::error(409, &why);
                }
                if !self.before_write.as_ref().is_some_and(|b| b.came.elapsed() <= BEFORE_WRITE_FRESH) {
                    return WebReply::error(409, "Press Write again: it reads the camera first, so the window can list what this write changes on the camera now.");
                }
                // the values the window lists, under what each is (`IssueKind::heading`), and its words over and under them
                let listed = self.write_issues();
                let issues: Vec<Value> = listed.iter().map(|is| {
                    let (head, line) = is.kind.heading();
                    let fix = self.issue_fix(is).map(|(w, _)| w);
                    json!({ "name": is.name, "value": is.value, "reason": is.reason, "kind": head, "kind_line": line, "edited": fix.is_some(), "fix": fix,
                        "camera_only": is.kind == IssueKind::CameraOnly })
                }).collect();
                // what only the camera's copy shows is no flagged value, though it keeps the all-clear away
                let theirs = listed.iter().filter(|is| is.kind == IssueKind::CameraOnly).count();
                let flagged = listed.len() - theirs;
                let words = json!({ "issues": (flagged > 0).then(|| Self::issues_words(flagged)), "todo": ISSUES_TODO, "all_clear": ALL_CLEAR,
                    "camera_only": (theirs > 0).then(|| camera_only_words(theirs)) });
                let summary: Vec<Value> = self.send_summary().into_iter().map(|(t, warn)| json!([t, warn])).collect();
                // the Write window's line on how long to leave the camera on (`write_warning_ui`)
                let leave_on = format!("{}.", check_words(&self.job_timing()));
                WebReply::json(json!({ "summary": summary, "warnings": self.link_warnings(), "issues": issues, "words": words, "rev": self.write_rev(), "leave_on": leave_on }))
            }
            // Cancel in the page's Write window while the camera is read: the read goes on, but no one waits for it
            "send_cancel" => {
                self.web_write = None;
                WebReply::json(json!({ "ok": true }))
            }
            "send" if !idle => WebReply::error(409, "The editor is busy with the camera; wait for it to finish."),
            "send" => {
                // the same rule as the window's Write button: a file the editor may edit, of the definition's model, not the sample
                if let Some(why) = self.send_blocked() {
                    return WebReply::error(409, &why);
                }
                if body["rev"].as_str() != Some(self.write_rev().as_str()) {
                    return WebReply::error(409, "Nothing written: the file changed since the Write window was opened (it was opened or edited elsewhere). Open Write again to check what will be written.");
                }
                // the read Write made a moment ago is the copy from just before; one grown old is made again first
                let Some(before) = self.before_write.take().filter(|b| b.came.elapsed() <= BEFORE_WRITE_FRESH) else {
                    self.web_write = None;
                    return WebReply::error(409, "Nothing written: the camera was read more than five minutes ago. Press Write again: it reads the camera first and lists what it holds now.");
                };
                self.web_write = None;
                match self.send_with(Some(before.path)) {
                    Ok(()) => WebReply::json(json!({ "ok": true })),
                    Err(why) => WebReply::error(409, &why),
                }
            }
            "put_back" if !idle => WebReply::error(409, "The editor is busy with the camera; wait for it to finish."),
            "put_back" => {
                if self.camera_backup.is_none() {
                    return WebReply::error(409, "No copy of the camera from before a write is kept in this session.");
                }
                self.camera_report = None;
                self.put_camera_back();
                WebReply::json(json!({ "ok": true }))
            }
            "dismiss" => {
                self.camera_report = None;
                WebReply::json(json!({ "ok": true }))
            }
            "retry" => match self.camera_report.as_ref().and_then(|c| c.retry.clone()) {
                Some((JobKind::BeforeWrite, _)) => WebReply::error(409, "Press Write again: it reads the camera first, then lists what the write changes."),
                Some((kind, upload)) if idle => {
                    self.camera_report = None;
                    // as the window's Try again: a read-back tried again reads at once
                    self.retry_job(kind, upload);
                    WebReply::json(json!({ "ok": true }))
                }
                _ => WebReply::error(409, "Nothing to try again now."),
            },
            // file B and the base, sent up from the page and opened as the window's B: Open… and Base: Open… open them
            "open_b" => {
                let path = match self.web_upload_path(r, "B_") { Ok(p) => p, Err(e) => return e };
                self.open_compare(path.clone());
                if !self.compare.as_ref().is_some_and(|(p, _)| *p == path) {
                    return WebReply::error(500, &self.page_status());
                }
                self.status = format!("{} {from}", self.status);
                WebReply::json(json!({ "ok": true }))
            }
            "open_base" if self.compare.is_none() => WebReply::error(409, "Open file B first: the base is the file A and B both started from."),
            "open_base" => {
                let path = match self.web_upload_path(r, "Base_") { Ok(p) => p, Err(e) => return e };
                self.open_base(path.clone());
                if !self.base.as_ref().is_some_and(|(p, _)| *p == path) {
                    return WebReply::error(500, &self.page_status());
                }
                self.status = format!("{} {from}", self.status);
                WebReply::json(json!({ "ok": true }))
            }
            "close_base" if self.base.is_none() => WebReply::error(409, "No base file is open."),
            "close_base" => {
                self.close_base();
                self.status = format!("Base file closed (back to a two-way compare) {from}");
                WebReply::json(json!({ "ok": true }))
            }
            // as the Compare bar's Swap A/B: open B as A, then A as B, both from the editor's computer
            "swap_ab" => {
                // the page's own words for edits left: it downloads where the window saves
                if self.doc.as_ref().is_some_and(|d| d.unsaved() > 0) {
                    return WebReply::error(409, "Download or revert the edits first: swapping opens both files again from the editor's computer.");
                }
                match self.swap_ab() {
                    Ok(()) => {
                        self.status = format!("A and B swapped {from}");
                        WebReply::json(json!({ "ok": true }))
                    }
                    Err(why) => WebReply::error(409, &why),
                }
            }
            "compare" | "compare_records" => {
                let cols = match self.web_cols(&body) { Ok(c) => c, Err(e) => return e };
                let q = body["q"].as_str().unwrap_or("").trim();
                let only_diff = body["only_diff"].as_bool().unwrap_or(self.matrix_only_diff);
                // the stored numbers are Expert mode's, whatever the page asks
                let raw = self.prefs.expert && body["raw"].as_bool().unwrap_or(self.show_raw);
                if action == "compare_records" {
                    return WebReply::json(self.web_compare_records(&cols, q, only_diff, raw));
                }
                let tab = body["tab"].as_str().filter(|t| !t.is_empty());
                let three = match body["three"].as_str().unwrap_or("all") {
                    "a" => ThreeFilter::AOnly,
                    "b" => ThreeFilter::BOnly,
                    "both" => ThreeFilter::Both,
                    "conflicts" => ThreeFilter::Conflicts,
                    _ => ThreeFilter::All,
                };
                // the row the page last changed from its compare (`keep`), kept shown as the window keeps it (`cmp_kept`)
                let keep = body["keep"].as_str().filter(|k| !k.is_empty());
                WebReply::json(self.web_compare(&cols, q, tab, (only_diff, keep), raw, three))
            }
            // a value of file A changed from the compare: the setting as the page's rows draw it, in the cell's set, for
            // the same picker (then "set", with the cell's column as `col`)
            "compare_cell" => {
                let target = body["target"].as_u64().unwrap_or(0) as usize;
                if !self.shown_sections().contains(&target) {
                    return WebReply::error(400, "This file has no such set.");
                }
                let Some(linked) = self.web_linked(target, body["key"].as_str().unwrap_or("")) else { return WebReply::error(404, "No such setting here.") };
                WebReply::json(json!({ "row": self.web_row(target, &linked) }))
            }
            // a value put into a column of file A (`to`: one column, or several for a cell's "All of A"):
            // one row (a cell's menu, an arrow) or every row shown (a column header's "Copy all shown
            // rows to …"), every record of each row, as one edit
            "copy" | "copy_rows" => {
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                let to = &body["to"];
                let dsts: Option<Vec<Col>> = if to.get(0).is_some_and(Value::is_array) {
                    to.as_array().and_then(|l| l.iter().map(|v| self.col_from_json(v)).collect())
                } else {
                    self.col_from_json(to).map(|c| vec![c])
                };
                let (Some(src), Some(dsts)) = (self.col_from_json(&body["from"]), dsts.filter(|d| !d.is_empty())) else {
                    return WebReply::error(400, "A column names a file that is not open, or a set this file does not show.");
                };
                if dsts.iter().any(|d| !d.editable() || *d == src) {
                    return WebReply::error(400, "Values only go into another column of file A: files B and Base are never changed.");
                }
                let keys: Vec<&str> = if action == "copy" {
                    vec![body["key"].as_str().unwrap_or("")]
                } else {
                    body["keys"].as_array().map(|a| a.iter().filter_map(Value::as_str).collect()).unwrap_or_default()
                };
                let rows = self.matrix_rows_for("", None);
                let (mut actions, mut n, mut name) = (Vec::new(), 0, String::new());
                for key in keys {
                    let Some((_, _, linked)) = rows.iter().find(|(_, _, l)| l.iter().any(|s| s.key == key)) else { return WebReply::error(404, "No such setting here.") };
                    for d in &dsts {
                        let row = self.copy_row(linked, src, *d);
                        n += usize::from(!row.is_empty());
                        actions.extend(row);
                    }
                    name.clone_from(&linked[0].name);
                }
                // every row shown: each takes its own value, a copy too (`pin_families`); one row is an edit of it
                if action == "copy_rows" {
                    for d in &dsts {
                        self.pin_families((src.src == Src::A).then_some(src.section), d.section, &mut actions);
                    }
                }
                let left = self.copy_skipped.get();
                if let Some(why) = self.apply(actions) {
                    return WebReply::error(409, &why);
                }
                let (f, t) = (self.col_name(src), dsts.iter().map(|d| self.col_name(*d)).collect::<Vec<_>>().join(", "));
                let said = if action == "copy" { format!("{name} copied from {f} into {t} {from}") } else { format!("{n} row(s) copied from {f} into {t} {from}") };
                self.status = with_left(&said, left);
                WebReply::json(json!({ "ok": true, "n": n, "left": left.total(), "message": left_alone(left) }))
            }
            // the three-way buttons: Merge B into A, Conflicts: take B, Conflicts: take Base, over the
            // rows the page's search and tab give, as the window's buttons work over its own
            "merge" => {
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                let col = |k: &str| self.col_from_json(&body[k]);
                let (Some(tb), Some(ta), Some(tbb)) = (col("base"), col("a"), col("b")) else {
                    return WebReply::error(400, "A merge takes a Base, an A and a B column that are open.");
                };
                if (tb.src, ta.src, tbb.src) != (Src::Base, Src::A, Src::B) {
                    return WebReply::error(400, "A merge takes a Base, an A and a B column, in that order.");
                }
                let (want, take, said) = match body["kind"].as_str().unwrap_or("") {
                    "b_into_a" => (Three::BOnly, tbb, "of B's changes merged into A"),
                    "conflicts_b" => (Three::Conflict, tbb, "conflicts resolved with B's values"),
                    "conflicts_base" => (Three::Conflict, tb, "conflicts reset to the base values"),
                    _ => return WebReply::error(400, "No such merge."),
                };
                let tab = body["tab"].as_str().filter(|t| !t.is_empty());
                let (mut actions, mut n) = (Vec::new(), 0);
                for (_, _, linked) in self.matrix_rows_for(body["q"].as_str().unwrap_or("").trim(), tab) {
                    if self.three_way((tb, ta, tbb), &linked[0]) == want {
                        n += 1;
                        actions.extend(self.copy_row(&linked, take, ta));
                    }
                }
                self.pin_families(None, ta.section, &mut actions);
                let left = self.copy_skipped.get();
                if let Some(why) = self.apply(actions) {
                    return WebReply::error(409, &why);
                }
                self.status = with_left(&format!("{n} {said} {from}"), left);
                WebReply::json(json!({ "ok": true, "n": n, "left": left.total(), "message": left_alone(left) }))
            }
            "file" => {
                let Some(doc) = &self.doc else { return WebReply::error(409, "No file is open.") };
                let (bytes, name) = (doc.edited.to_bytes(), safe_name(&self.suggested_name(doc)));
                if let Err(e) = CamSet::parse(&bytes, doc.edited.format()) {
                    // as the window's Save As says it (`save_to`)
                    return WebReply::error(500, &format!("Not downloaded: the edited file did not read back as a settings file. Undo the last edit, then download again.{}", details(self.prefs.expert, &e)));
                }
                self.status = format!("File downloaded {from}");
                if self.is_sample_doc() { self.status += &format!(". {SAMPLE_NOT_FOR_A_CAMERA}"); }
                WebReply { status: 200, content_type: "application/octet-stream", body: bytes, download: Some(name), keep: false }
            }
            "open" => {
                if let Some(no) = self.web_unsaved(discard) {
                    return no;
                }
                let path = match self.web_upload_path(r, "") { Ok(p) => p, Err(e) => return e };
                match self.open_now(path) {
                    Ok(()) => WebReply::json(json!({ "ok": true })),
                    Err(_) => WebReply::error(400, &self.page_status()),
                }
            }
            "unmapped" | "records" | "raw_set" | "prefs" | "backups" | "open_backup" | "history" | "revert_history" | "sample"
            | "open_recent" | "clear_recent" | "csv" | "layout" | "mymenu" | "mymenu_slot" | "switch_usb" | "reload_schemas"
            | "camera_link" | "camera_search" | "camera_use" | "camera_name" | "camera_forget" | "camera_check"
            | "camera_steps" | "camera_cards" | "camera_report" => self.web_answer_more(action, target, &body, &from),
            _ => WebReply::error(404, "The editor has no such request."),
        }
    }

    /// What the page shows of the file and of the editor's switches, as a hash: it changes whenever the page should
    /// fetch what it shows again. It is asked for every few seconds, so it serialises no file: file A by the state
    /// it is in (`Doc::rev`, new at every opening and change), B and the base, never changed once open, by their
    /// path, header (time stamp and checksums included) and size.
    pub(super) fn web_rev(&self) -> String {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        (self.prefs.expert, self.allow_unobserved, self.prefs.show_proof, self.show_raw, self.prefs.show_record_ids, self.allow_raw_edits, &self.schema.origin, self.schema_gen).hash(&mut h);
        self.prefs.flat_list.hash(&mut h);          // the rows' layout: as on the camera, or the flat list
        if let Some(d) = &self.doc {
            d.path.hash(&mut h);
            d.rev.hash(&mut h);
            d.unchecked_ok.hash(&mut h);
        }
        for (p, c) in self.compare.iter().chain(self.base.iter()) {
            p.hash(&mut h);
            c.header.hash(&mut h);
            c.sections.iter().map(|s| s.records.len()).collect::<Vec<_>>().hash(&mut h);
        }
        self.base.is_some().hash(&mut h);
        format!("{:x}", h.finish())
    }

    /// The frame of the page: the open file, the camera link, a camera job and its report, and the
    /// menu as the window's left column has it for `target` (each tab's colour, settings and edits).
    /// It is asked for every few seconds, so it names no path but file names, and nothing of the cameras
    /// (address, serial number, MAC address): those come in `camera_cards`, which Connect to the camera asks for.
    pub(super) fn web_state(&self, target: usize) -> Value {
        let file = self.doc.as_ref().map(|d| {
            // the link as the helper names it ("LAN", "USB"), without the camera's address
            let (source, link, read_at) = match &d.source {
                Source::Disk => ("disk", String::new(), String::new()),
                Source::Sample => ("sample", String::new(), String::new()),
                Source::Camera { link, read_at } => ("camera", link.split_whitespace().next().unwrap_or("").to_string(), self.stamp_words(read_at)),
            };
            let (badge, saved) = (self.web_badge(&d.edited, &d.signature, d.unchecked_ok), self.stamp_words(&d.edited.timestamp()));
            json!({
                "name": d.path.file_name().unwrap_or_default().to_string_lossy(),
                "source": source, "link": link, "read_at": read_at,
                "model": d.edited.model(),
                "firmware": self.schema.layout(&d.signature).map(|l| l.firmware.clone()),
                "badge": badge,
                // the definition the file is read with: model, firmware, built-in or yours (and how it was picked)
                "definition": self.definition_words().map(|(text, tip)| json!({ "text": text, "tip": tip, "model": self.schema.model, "firmware": self.schema.firmware(),
                    "source": self.schema.origin.word(), "chosen": d.override_def.is_some() })),
                "saved": saved,
                "editable": self.editable(),
                "changes": d.changes().len(),
                // the edits are the ones the camera confirmed, not saved to the file: what the question before they would
                // be lost starts with (`on_camera_words`), else null
                "on_camera": self.edits_on_camera().then(|| Self::on_camera_words(d.changes().len())),
                "issues": self.issue_count(),
                "undo": self.undo.len(), "redo": self.redo.len(),
                "can_undo": !self.undo.is_empty(), "can_redo": !self.redo.is_empty(),
                // Edit anyway is the desktop app's: the page says where it is, for a file that needs it
                "edit_anyway_in_desktop": self.offers_edit_anyway(d),
                // the sample, or a file made from it: what the page says as it downloads it (never for a camera), else null
                "sample_words": self.is_sample_doc().then_some(SAMPLE_NOT_FOR_A_CAMERA),
            })
        });
        // [section, name, a button of its own]: the live settings and the dial memories get one, the
        // other sets (expert mode) share a list, as in the window's Editing row
        let targets: Vec<Value> = self.shown_sections().into_iter()
            .map(|s| json!([s, self.schema.camera.target_name(s), s == 0 || self.schema.camera.is_dial(s)])).collect();
        // the window's Menu tabs (`menu_tabs`: Other gathers the tabs the definition does not list), as it shows them
        let sections = self.shown_sections();
        let menu_tabs = self.menu_tabs();
        let tabs: Vec<&String> = menu_tabs.iter()
            .filter(|t| sections.iter().any(|&si| self.settings_in(si, Some(t.as_str())).next().is_some()))
            .collect();
        // where a jump to a setting of a tab that has no entry of its own goes (`shown_view`): My Menu's page, or Other
        let mut routes = serde_json::Map::new();
        for s in &self.schema.settings {
            if !menu_tabs.contains(&s.tab) && !routes.contains_key(&s.tab) {
                routes.insert(s.tab.clone(), match self.shown_view(View::Tab(s.tab.clone())) {
                    View::MyMenu => json!({ "page": "mymenu" }),
                    _ => json!({ "page": "tab", "tab": self.menu_entry_of(&s.tab) }),
                });
            }
        }
        // the entry for what the camera's menus do not hold, while the flat list has none: the first tab, as the window
        let off = self.schema.camera.text.off_menu_name();
        if !menu_tabs.iter().any(|t| t == off) {
            if let View::Tab(first) = self.shown_view(View::Tab(off.to_string())) {
                routes.insert(off.to_string(), json!({ "page": "tab", "tab": first }));
            }
        }
        let edited = |s: &Setting| self.doc.as_ref().is_some_and(|d| d.value(target, s.slot()) != d.original_value(target, s.slot()));
        let tab_info: Vec<Value> = tabs.iter().map(|t| {
            let (mut count, mut changed) = (0, 0);
            for s in self.settings_in(target, Some(t.as_str())) {
                count += 1;
                // My Menu's places count on its own entry (`mymenu_edits`), as in the window
                changed += (edited(s) && !self.is_mymenu_place(s)) as usize;
            }
            let title = (t.as_str() == off).then(App::off_menu_hover);
            json!({ "name": t, "color": css_color(tab_color(&self.schema.camera, t)), "count": count, "edited": changed, "title": title })
        }).collect();
        let main_sets: Vec<&str> = self.schema.camera.main_tiles.as_ref().map(|m| m.0.iter().map(|s| s.name.as_str()).collect()).unwrap_or_default();
        let job = self.camera_job.as_ref().map(|j| {
            let (title, line, progress) = j.progress();
            json!({ "title": title, "line": line, "progress": progress })
        });
        let put_back = |r: &CameraReport| self.camera_backup.as_ref().filter(|_| r.put_back).map(|(at, _)| when_words(at));
        // as the window's report, how often it retried, and the ways on: Change connection, Switch to USB and read, Put
        // back. The link's own words (they name the camera's address, serial number and MAC address) are not in it:
        // in Expert mode `camera_report` gives them, else a line says where they are. What only the desktop app does
        // (enter the login, forget a camera so it is trusted again) is said in a line of its own, with no button.
        let expert = self.prefs.expert;
        let report = self.camera_report.as_ref().map(|r| {
            let cause = probe_cause(&r.probe);
            let mut lines = r.lines.clone();
            let desktop = match cause {
                Some("credentials_missing" | "credentials_rejected" | "credentials_file_open") => Some(WEB_LOGIN_IN_DESKTOP),
                Some("camera_changed") => Some(WEB_FORGET_IN_DESKTOP),
                _ => None,
            };
            if let Some(d) = desktop {
                lines.push((d.to_string(), false));
            }
            json!({ "title": r.title, "ok": r.ok, "lines": lines,
                "has_probe": expert && !r.probe.trim().is_empty(),
                "note": (!expert && !r.probe.trim().is_empty()).then_some(EXPERT_LINK_NOTE),
                "retries": if expert && r.ok { r.probe.lines().filter(|l| l.starts_with("note: connect attempt")).count() } else { 0 },
                "retry": r.retry.as_ref().is_some_and(|(k, _)| *k != JobKind::BeforeWrite), "put_back": put_back(r), "offer_usb": r.offer_usb,
                "in_desktop": desktop })
        });
        let (up, state) = match &self.link_state {
            LinkState::Up { at } => (Some(true), format!("read {}", when_words(at))),
            LinkState::Down { .. } => (Some(false), "disconnected".to_string()),
            LinkState::Untried => (None, "not checked".to_string()),
        };
        let link = match self.prefs.link.as_str() {
            "network" => "Network".to_string(),
            "usb" => "USB".to_string(),
            _ => "no link chosen".to_string(),
        };
        let mut out = json!({
            "rev": self.web_rev(),
            "file": file, "targets": targets, "tabs": tabs, "job": job, "report": report,
            "link": { "text": link, "state": state, "up": up },
            "status": self.page_status(),
            "prefs": self.web_prefs(),
            "settings_tabs": SettingsTab::ALL.iter().map(|t| [t.label(), t.subtitle()]).collect::<Vec<_>>(),
            // the editor's version in full ("0.2.0 (build 1a2b3c4)"), as the status bar's hover gives it; parts below
            "version": crate::version_words(),
            "row_hovers": self.web_row_hovers(),
            "history": self.undo.len(),
            // file names only ("path" repeats the name, for a page that shows it); open_recent takes the index
            "recent": self.prefs.recent.iter().map(|r| json!({ "name": file_name_of(r), "path": file_name_of(r) })).collect::<Vec<_>>(),
            "schemas": self.defs.list.iter().map(|s| json!({ "model": s.model, "firmwares": s.firmware(), "settings": s.settings.len(),
                "src": s.origin.path().map(|p| file_name_of(&p.to_string_lossy())).unwrap_or_default(), "active": s.origin == self.schema.origin,
                "help_refused": s.help_refusals() })).collect::<Vec<_>>(),
            "dirs": { "originals": shown_path(&Self::originals_dir()), "camera": shown_path(&Self::camera_dir()) },
            "sample": !self.defs.samples().is_empty(),
            // the Read card's words, the Read button's hover and how long a read usually takes, the window's
            "read_sub": self.read_sub(), "read_tip": self.read_tip(""), "read_time": self.read_words(),
            // the welcome page's words, the window's
            "open_sub": self.open_hint(), "not_sony": NOT_SONY,
            "camera": self.web_camera_button(),
            "web_url": self.web.as_ref().map(|w| w.url.clone()),
            "can_undo": !self.undo.is_empty(),
            "can_redo": !self.redo.is_empty(),
            "edits": self.doc.as_ref().map_or(0, |d| d.changes().len()),
            // the status bar's counter, in the window's words (`unsaved_words`)
            "edits_text": self.unsaved_words(self.unsaved()),
            "target": target,
            "tab_info": tab_info,
            "routes": routes,
            // My Menu's entry under Main, as the window's: its name and colour, its hover, the places that hold an item
            // and its edits (live settings); none without My Menu in the definition
            "my_menu": self.has_mymenu_page().then(|| {
                let (label, hover) = self.mymenu_entry_words();
                let name = self.schema.camera.text.my_menu_name();
                json!({ "name": name, "label": label, "title": hover, "color": css_color(tab_color(&self.schema.camera, name)), "edited": self.mymenu_edits() })
            }),
            "main_sets": main_sets,
            // the window's pages the page does not have, named as its menu names them
            "memories": (!self.dial_sets().is_empty()).then(|| self.memories_title()),
            "exposure": self.schema.camera.exposure.as_ref().map(|e| if e.title.is_empty() { "Exposure".to_string() } else { e.title.clone() }),
            "known": self.schema.settings.len(),
            "definition": self.schema.origin.path().map(|p| file_name_of(&p.to_string_lossy())).unwrap_or_default(),
            // the help file by its name alone: `help_src` is "path (the file's own source line)", and that line can hold a path too
            "help_src": if self.schema.help_src.is_empty() { String::new() } else { self.schema.help_file_name() },
            "save_load_path": self.schema.camera.text.save_load_path,
            "works_with": self.defs.works_with(),
            "compare": self.web_compare_state(),
        });
        // help files of the open definition's name not used (another camera's), by file name and in Settings' words;
        // set apart, as the object above is as large as the json! macro takes
        out["help_refused"] = self.schema.help_refused.iter().zip(self.schema.help_refusals())
            .map(|((p, _), text)| json!({ "file": file_name_of(&p.to_string_lossy()), "text": text })).collect();
        // the version's two parts, for Settings > About and the status bar: the short version ("0.2.0") and the build's
        // commit (null for a build made outside the repository)
        out["version_short"] = json!(version_short());
        out["build"] = json!(build_hash());
        out["about"] = self.web_about();
        out
    }

    /// Settings > About's other lines, in the window's words (`about_cards`): the system the editor runs on, whether
    /// the camera link program is there, the licence, the project's pages, and the details Copy details copies.
    fn web_about(&self) -> Value {
        json!({
            "system": format!("System: {}", system_words()),
            "helper": self.helper_words(),
            "licence": licence_words(),
            "links": ABOUT_LINKS.iter().map(|(text, url, title)| json!({ "text": text, "url": url, "title": title })).collect::<Vec<_>>(),
            "details": self.about_details(),
        })
    }

    /// The window's firmware badge beside a file's name (`firmware_badge`), in its words: checked,
    /// not checked with editing turned on anyway, or view only.
    fn web_badge(&self, c: &CamSet, signature: &str, unchecked_ok: bool) -> Value {
        let saved = self.stamp_words(&c.timestamp());
        // the video system the file was saved under, after the firmware, as the window's badge says it
        let (video, video_tip) = video_badge(c);
        match self.schema.layout(signature).filter(|_| self.schema.camera.knows(c)) {
            _ if !c.checksums_ok() => json!({ "kind": "bad", "text": "⚠ file looks damaged: view only",
                "tip": format!("{} · saved {saved}\nThe file's checksum does not match what its camera definition says: the file may be damaged, or the definition may not describe it. It is shown, but never edited.", c.model()) }),
            Some(l) => json!({ "kind": "ok", "text": format!("✔ firmware {}{video}", l.firmware),
                "tip": format!("{} · saved {saved}{video_tip}\nThis file's firmware has been checked: every setting is known (layout {signature}).\n{}", c.model(), l.note_shown(self.prefs.expert)).trim_end().to_string() }),
            None if unchecked_ok => json!({ "kind": "warn", "text": format!("⚠ firmware {} not checked: editing on{video}", c.firmware()),
                "tip": format!("{} · saved {saved}{video_tip}\nSettings are matched by record number. The ones this file does not hold in the shape they were mapped in stay view-only. Checked firmware: {}.", c.model(), self.schema.firmwares()) }),
            None => json!({ "kind": "bad", "text": format!("⚠ firmware not checked yet: view only{video}"),
                "tip": format!("{} · saved {saved}{video_tip}\nThis file comes from a firmware the editor has not checked yet (layout {signature}); a firmware update can move or resize settings. Settings are shown, but editing is off so the file cannot be damaged.", c.model()) }),
        }
    }

    /// The Main page for `target`, as the window's: the definition's pages (Stills, Movie, …),
    /// the tiles of page `set` with their values and, for a tile holding one setting that can be
    /// changed, that setting as a row; then every setting the tiles show, as rows.
    fn web_main(&self, target: usize, set: usize) -> Value {
        let pages = self.schema.camera.main_tiles.as_ref().map_or(&[][..], |m| m.0.as_slice());
        let set = if set < pages.len() { set } else { 0 };
        let names: Vec<&str> = pages.iter().map(|p| p.name.as_str()).collect();
        let Some(doc) = &self.doc else { return json!({ "sets": names, "set": set, "tiles": [], "rows": [] }) };
        let editable = self.editable();
        let (mut tiles, mut rows) = (Vec::new(), Vec::new());
        for tile in pages.get(set).map_or(&[][..], |p| p.tiles.as_slice()) {
            let caption = tile.caption.as_str();
            let settings: Vec<&Setting> = tile.keys_for(target).into_iter().filter_map(|k| self.schema.settings.iter().find(|s| s.key == k)).collect();
            let changed = settings.iter().any(|s| doc.value(target, s.slot()) != doc.original_value(target, s.slot()));
            // every record holding the setting, this one first, as a change on the page sets them all
            let linked = |s: &Setting| self.web_linked(target, &s.key).map(|mut l| {
                l.sort_by_key(|o| o.key != s.key);
                l
            });
            let mut t = json!({ "caption": caption, "text": self.web_tile_text(doc, target, tile, &settings), "changed": changed });
            // a number with no name yet says why on hover, and a value the camera keeps in more than one record what
            // changing it changes (`copy_note`), as the window's tile does
            let why: Vec<String> = settings.iter().filter_map(|s| self.unnamed_why(s, doc.value(target, s.slot())))
                .chain(settings.iter().filter_map(|s| self.copy_note(s, target).map(|(w, _)| w))).collect();
            if !why.is_empty() {
                t["why"] = json!(why.join("\n\n"));
            }
            // a tile with one plain setting (a list of values or a number) can be changed in place, unless it is view only
            // outside Expert mode (`locked_why`), as the window's tile
            if let [s] = settings.as_slice() {
                if editable && self.tile_changes_in_place(s, target) {
                    if let Some(l) = linked(s) {
                        t["edit"] = self.web_row(target, &l);
                    }
                }
            }
            tiles.push(t);
            for s in &settings {
                // several settings under one tile: each one's own name, without repeating the tile's
                let label = if settings.len() > 1 {
                    let n = s.name.trim_start_matches(&format!("{caption}: ")).replace(&format!(" ({caption})"), "");
                    if n.to_lowercase().starts_with(&caption.to_lowercase()) { n } else { format!("{caption} – {n}") }
                } else {
                    caption.to_string()
                };
                let mut row = match linked(s) {
                    Some(l) => self.web_row(target, &l),
                    None => {
                        let mut r = self.web_row(target, std::slice::from_ref(*s));
                        r["editable"] = json!(false);
                        r
                    }
                };
                row["name"] = json!(label);
                row["caption"] = json!(caption);
                rows.push(row);
            }
        }
        json!({ "sets": names, "set": set, "tiles": tiles, "rows": rows, "editable": editable })
    }

    /// A tile's value as the window's Main page shows it (`tile_text`), for the set `target`.
    fn web_tile_text(&self, doc: &Doc, target: usize, tile: &Tile, settings: &[&Setting]) -> String {
        if tile.kind == TileKind::Fraction {
            if target == 0 {
                return Self::live_text(tile).into();
            }
            let f = |k: &Option<String>| k.as_ref().and_then(|k| self.schema.settings.iter().find(|s| s.key == *k)).and_then(|s| doc.value(target, s.slot()));
            return match (f(&tile.numerator_key), f(&tile.denominator_key)) {
                (Some(n), Some(d)) if d > 1 => format!("{n}/{d}"),
                (Some(n), Some(1)) => format!("{n}\""),
                _ => "—".into(),
            };
        }
        if settings.is_empty() {
            return Self::live_text(tile).into();
        }
        let value = |s: &Setting| match s.text {
            Some(_) => doc.edited.sections.get(target).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default(),
            None => Self::describe(s, doc.value(target, s.slot())),
        };
        settings.iter().map(|s| value(s)).collect::<Vec<_>>().join(" · ")
    }

    /// The rows of one tab for `target`, by group; with `q`, the settings of every tab that match it.
    fn web_tab(&self, target: usize, tab: Option<&str>, q: &str) -> Value {
        let q = q.trim().to_lowercase();
        let tab_pos = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(usize::MAX);
        // groups in menu order (a group sorts by its first setting), rows by name within a group;
        // each group headed in its tab's colour
        let mut keys: BTreeMap<String, (usize, i64, String)> = BTreeMap::new();
        let mut tab_of: BTreeMap<String, String> = BTreeMap::new();
        let mut groups: BTreeMap<(usize, i64, String), Vec<Vec<Setting>>> = BTreeMap::new();
        let list = self.settings_in(target, if q.is_empty() { tab } else { None }).filter(|s| q.is_empty() || Self::matches_query(s, &q));
        // the entry for what the camera's menus do not hold names its groups by their tab too, as the window (`off_group`)
        let off = q.is_empty() && self.camera_layout() && tab == Some(self.schema.camera.text.off_menu_name());
        for s in list.take(if q.is_empty() { usize::MAX } else { MAX_HITS }) {
            // in the group that shows it in the layout in use, as the window has it (`layout_group`)
            let group = self.layout_group(s);
            // and in the tab that shows it, as the window has it (`layout_tab`)
            let tab = self.layout_tab(s);
            let title = if off { App::off_group(s) } else if q.is_empty() { group.to_string() } else { format!("{tab} › {group}") };
            tab_of.entry(title.clone()).or_insert_with(|| tab.to_string());
            let key = keys.entry(title.clone()).or_insert((tab_pos(tab), s.order, title)).clone();
            let rows = groups.entry(key).or_default();
            // one setting kept in several records: the same name in the same place on the camera, as the window has it
            match rows.iter_mut().find(|r| r[0].links_with(s)) {
                Some(r) => r.push(s.clone()),
                None => rows.push(vec![s.clone()]),
            }
        }
        // Picture Profiles and Creative Looks: the groups of each family as one table, first, as the window's tab has them
        // (as on the camera, a family's group that is the page an option opens stays a group too, as the window's)
        let mut families: Vec<Value> = Vec::new();
        if q.is_empty() {
            let camera = self.camera_layout();
            for f in self.schema.camera.families.iter().filter(|f| !f.prefix.is_empty()) {
                let keys: Vec<(usize, i64, String)> = groups.keys().filter(|k| k.2.starts_with(&f.prefix)).cloned().collect();
                let page = |rows: &Vec<Vec<Setting>>| camera && rows.iter().flatten().any(Setting::on_page);
                let pp: Vec<Setting> = keys.iter().filter_map(|k| if groups.get(k).is_some_and(page) { groups.get(k).cloned() } else { groups.remove(k) }).flatten().flatten().collect();
                if !pp.is_empty() {
                    families.push(self.web_family(target, &f.title, &pp));
                }
            }
        }
        let camera = self.camera_layout();
        let at = self.menu_at();
        // as on the camera, a tab's groups in the camera's order, as the window's (`menu_rows::group_key`)
        let mut groups: Vec<_> = groups.into_iter().collect();
        if camera {
            groups.sort_by_cached_key(|((t, order, name), rows)| (*t, menu_rows::group_key(*order, name, rows.iter().map(|r| &r[0]))));
        }
        let groups: Vec<Value> = groups.into_iter().map(|((_, _, name), mut rows)| {
            let tab = tab_of.get(&name).cloned().unwrap_or_default();
            // as on the camera: a tab's rows in the camera's order, laid out as the window lays them out (`layout`:
            // the camera's rows that are headings, each setting's depth, the settings it does not place last); a
            // search's in the camera's order, as the window's search lists them
            let mut layout = None;
            if camera && q.is_empty() {
                let lines = menu_rows::lay_out(&rows);
                if lines.iter().any(|l| !matches!(l, Line::Row { depth: 0, .. })) {
                    layout = Some(lines.iter().map(|l| match l {
                        Line::Heading { label, depth, path } => json!({ "head": label, "depth": depth, "path": path }),
                        Line::Row { index, depth } => json!({ "key": rows[*index][0].key, "depth": depth }),
                        Line::Mode(mode) => json!({ "mode": menu_rows::mode_words(mode), "name": mode }),
                        Line::More => json!({ "more": menu_rows::MORE }),
                    }).collect::<Vec<_>>());
                }
                let order = menu_rows::order(&lines);
                rows = order.into_iter().map(|i| rows[i].clone()).collect();
            } else if camera {
                rows.sort_by_key(|r| at(&r[0]));
            }
            let mut g = json!({ "name": name, "color": css_color(tab_color(&self.schema.camera, &tab)), "tab": tab,
                "rows": rows.iter().map(|r| self.web_row(target, r)).collect::<Vec<_>>() });
            if let Some(layout) = layout {
                g["layout"] = json!(layout);
            }
            // the page an option opens (Picture Profile's PP1), as the window's group column marks it: its option
            if camera && q.is_empty() {
                if let Some(o) = rows.iter().flatten().find(|s| s.on_page()).and_then(|s| s.under_option.clone()) {
                    g["page"] = json!(o);
                }
            }
            // the sub-choices are no rows here, only beside their owner's options: the page counts them in the group's
            // number, as the window counts its settings
            if camera && q.is_empty() {
                g["beside"] = json!(true);
            }
            g
        }).collect();
        let groups: Vec<Value> = families.into_iter().chain(groups).collect();
        // "places": the definition says where its settings sit on the camera, so the page offers the layout switch
        json!({ "groups": groups, "editable": self.editable(), "places": self.places(), "flat": self.prefs.flat_list })
    }

    /// Every record that stores the setting `key` in `target`, the leading one first.
    pub(crate) fn web_linked(&self, target: usize, key: &str) -> Option<Vec<Setting>> {
        let s = self.settings_in(target, None).find(|s| s.key == key)?;
        // of its own tab, whichever Menu entry shows it (a setting the camera's menus do not hold is under one of its own)
        Some(self.settings_in(target, None).filter(|o| self.same_row(o, s)).cloned().collect())
    }

    /// A compare column as the page names it, `["a" | "b" | "base", section]`: None unless that
    /// file is open and the section is one the window offers as a column (`shown_sections`).
    fn col_from_json(&self, v: &Value) -> Option<Col> {
        let src = match v.get(0)?.as_str()? {
            "a" => Src::A,
            "b" => Src::B,
            "base" => Src::Base,
            _ => return None,
        };
        let section = usize::try_from(v.get(1)?.as_u64()?).ok()?;
        (self.set_for(src).is_some() && self.shown_sections().contains(&section)).then_some(Col { src, section })
    }

    /// One setting as the page draws it: its value, how it may be changed, and what stands in the way.
    pub(crate) fn web_row(&self, target: usize, linked: &[Setting]) -> Value {
        let s = &linked[0];
        let Some(doc) = &self.doc else { return Value::Null };
        let (cur, orig) = (doc.value(target, s.slot()), doc.original_value(target, s.slot()));
        // every record in its mapped shape, and none view only outside Expert mode (a setting no menu writes:
        // `locked_why`, whose words the row carries)
        let locked = linked.iter().find_map(|l| self.locked_why(l, target));
        let shapes = linked.iter().all(|l| self.shape_ok_in(l, target)) && locked.is_none();
        let editable = self.editable();
        let mut row = json!({
            "key": s.key, "name": s.name,
            // the set the row shows and changes (the My Menu page's rows are the live settings', whatever set the page edits)
            "target": target,
            "changed": cur != orig,
            "label": Self::describe(s, cur), "original": Self::describe(s, orig),
        });
        // what puts it back where the camera keeps it, where the plain Revert changes nothing, in the window's words
        // (`put_back_choice`) and with its hover (`put_back_hover`), for the page's button ("restore")
        if let Some((words, _)) = self.put_back_choice(linked, target) {
            row["put_back_why"] = json!(Self::put_back_hover(&words));
            row["put_back"] = json!(words);
        }
        // a value the camera keeps in more than one record: what changing it changes, or that the file is out of step
        // there, in the window's words (`copy_note`), with its hover
        if let Some((note, hover)) = linked.iter().find_map(|l| self.copy_note(l, target)) {
            row["copy_note"] = json!(note);
            row["copy_note_why"] = json!(hover);
        }
        // a number with no name yet: why, for the value's hover and the row's details (`unnamed_why`)
        if let Some(why) = self.unnamed_why(s, cur) {
            row["unnamed"] = json!(why);
        }
        // the note is the mapping team's words, sent in Expert mode only
        if self.prefs.expert {
            row["note"] = json!(s.note);
        }
        // a setting whose proofs disagree, in Expert mode, in place of the proof line
        if self.prefs.expert && s.disputed {
            row["disputed"] = json!(DISPUTED);
        }
        // the line saying whether it was proved on the camera, unless Settings turns it off
        if self.shows_proof() {
            let (proof, proof_kind) = s.proof_badge_in(target);
            row["proof"] = json!(proof);
            row["proof_kind"] = json!(proof_kind);
            // its hover: why no proof reaches it, or what a proof is (`PROVED_HOVER`), as the window's proof line says
            row["proof_why"] = json!(s.unproved_in(target).map(|u| u.why.clone())
                .or_else(|| s.proved.as_ref().map(|_| PROVED_HOVER.to_string()))
                .or_else(|| s.unproved_reason.as_ref().map(|u| u.why.clone())).unwrap_or_default());
        } else if s.not_on_camera() {
            // with the proof line off, the one plain fact it carries: the camera's menu has no row for it
            row["not_on_camera"] = json!(true);
        }
        // view only outside Expert mode, and why, in the window's words (`locked_why`), with its hover
        if let Some((why, hover)) = &locked {
            row["locked"] = json!(why);
            row["locked_why"] = json!(hover);
        }
        if let Some(rule) = &s.text {
            let text_of = |c: &CamSet| c.sections.get(target).and_then(|sec| sec.get(s.id)).and_then(|r| r.text());
            let rec = doc.edited.sections.get(target).and_then(|sec| sec.get(s.id));
            let (text, orig_text) = (text_of(&doc.edited).unwrap_or_default(), text_of(&doc.original).unwrap_or_default());
            row["kind"] = json!("text");
            row["changed"] = json!(text != orig_text);
            row["label"] = json!(text);
            row["original"] = json!(orig_text);
            row["max_len"] = json!(rule.max_len);
            row["uppercase"] = json!(rule.uppercase);
            row["editable"] = json!(editable && rec.is_some() && shapes);
        } else {
            let can_edit = editable && s.scalar && cur.is_some() && shapes;
            row["editable"] = json!(can_edit);
            row["value"] = json!(cur);
            if let (Some((lo, hi)), Some(_)) = (s.range, cur) {
                row["kind"] = json!("range");
                row["lo"] = json!(lo);
                row["hi"] = json!(hi);
                row["step"] = json!(s.step.unwrap_or(1).max(1));
                row["unit"] = json!(s.unit);
                // shown other than as stored (`shown_as`): the page shows and takes value / divide, as the window
                if let Some(a) = s.shown_as.filter(|a| a.divide > 0) {
                    row["shown_as"] = json!({ "divide": a.divide, "decimals": a.decimals });
                }
            } else if s.values.len() >= 2 {
                // [value, label (with the raw code when Settings shows them), established by a proof on the camera
                // (`Setting::established`), its help]; null for a value the menus never offer (listed only while the
                // file holds it): the window draws it as the value held now with no mark, its hover saying why, and so
                // does the page; never another video system's than the file's (`offered_values`)
                let offered = self.offered_values(s, target);
                let label = |v: i64, l: String| if self.show_raw { format!("{l}  [{v}]") } else { l };
                let seen = |v: i64| if s.never_offered(v).is_some() { Value::Null } else { json!(s.established(v)) };
                let mut options: Vec<Value> = offered.iter().map(|(v, l)| json!([v, label(*v, l.clone()), seen(*v), self.web_option_help(s, *v)])).collect();
                if let Some(v) = cur.filter(|v| !options.iter().any(|o| o[0] == json!(v))) {
                    options.push(json!([v, label(v, Self::describe(s, cur)), seen(v), self.web_option_help(s, v)]));
                }
                row["kind"] = json!("choice");
                row["options"] = json!(options);
                // the values the camera refuses, which the page marks as the window does (`REFUSED_HOVER`)
                if s.refused.iter().any(|v| offered.iter().any(|(o, _)| o == v) || Some(*v) == cur) {
                    row["refused"] = json!(s.refused);
                    row["refused_why"] = json!(REFUSED_HOVER);
                }
                row["hidden"] = json!(s.hidden_unproved(self.allow_unobserved));
                // Expert mode's line for them in the window's words (`hidden_words`), which the page draws under the
                // setting and in Compare's in-place choice, as the window does
                if s.hidden_unproved(self.allow_unobserved) > 0 {
                    row["hidden_words"] = json!(hidden_words(s.hidden_unproved(self.allow_unobserved)));
                }
                // as the camera lays them out, when it nests them (`option_tree`): the main options, each one value or
                // the choices of its own axis ([value, label under the option, seen, help]), the values offered only
                if let Some(tree) = s.option_tree() {
                    let shown = |v: i64| offered.iter().any(|(o, _)| *o == v) || Some(v) == cur;
                    let nodes: Vec<Value> = tree.iter().filter_map(|n| match n.value {
                        Some(v) => shown(v).then(|| json!({ "label": label(v, s.label_for(v).unwrap_or(&n.label).to_string()), "value": v })),
                        None => {
                            let subs: Vec<Value> = n.options.iter().filter(|(v, _)| shown(*v))
                                .map(|(v, l)| json!([v, label(*v, l.clone()), seen(*v), self.web_option_help(s, *v)])).collect();
                            (!subs.is_empty()).then(|| json!({ "label": n.label, "options": subs }))
                        }
                    }).collect();
                    row["tree"] = json!(nodes);
                }
            } else {
                row["kind"] = json!("fixed");
                row["editable"] = json!(false);
            }
            if cur != orig {
                row["warn"] = json!(cur.and_then(|v| s.acceptance(v)));
            }
            // a value of another video system than the file's, edited or not, as the window's detail panel says it
            if let Some(why) = cur.and_then(|v| self.other_system_words(s, v, target)) {
                row["warn"] = json!(match row["warn"].as_str() { Some(w) => format!("{w}. {why}"), None => why });
            }
        }
        if let Some(r) = s.inactive_when.as_ref().filter(|r| r.inactive(doc.value(target, (r.record, None)))) {
            row["inactive"] = json!({
                "text": format!("Greyed out on the camera while {} = {}. The value is kept and takes effect when {} changes.",
                    r.name, Self::describe_record(&self.schema, r.record, doc.value(target, (r.record, None))), r.name),
                "unlock": if editable { Some(format!("Activate (set {} to {})", r.name, r.unlock_label)) } else { None },
            });
        }
        // the rest of the window's detail panel: help, where it applies and is kept, how it was mapped, what the camera
        // writes with it and refuses, the records it lives in, its raw value, My Menu, and file B's text
        row["help"] = json!(s.help);
        row["help_from_file"] = json!(s.help_from_file);
        row["modes"] = json!(s.modes);
        row["stored"] = json!(if s.in_sets { Some("sets") } else if s.area == "global" { Some("live") } else { None });
        // where it sits on the camera (the name's hover), and, as the window's detail panel has them, the options that
        // have a choice of their own and the choice of the option chosen now, a row of its own to change it with
        if let Some(w) = menu_rows::place_words(s) {
            row["place"] = json!(w);
        }
        let group = || self.settings_in(target, Some(self.layout_tab(s))).filter(|o| menu_rows::camera_group(o) == menu_rows::camera_group(s));
        if menu_rows::is_own(s) {
            // every choice beside its options (`menu_rows::sub_choices`), each a row of its own to change it with; the
            // page shows the chosen option's ("now"), and any other edited or opened from elsewhere, as the window
            let subs = menu_rows::sub_choices(s, group());
            if !subs.is_empty() {
                let mut options: Vec<&str> = subs.iter().map(|(_, o)| o.as_str()).collect();
                options.dedup();
                let rows: Vec<Value> = subs.iter().filter_map(|(sub, o)| {
                    let mut r = self.web_row(target, &self.web_linked(target, &sub.key)?);
                    r["option"] = json!(o);
                    // a family's setting (a look's parameter) is counted in its family's table, not again here
                    if self.family_of(std::slice::from_ref(*sub)).is_some() {
                        r["family"] = json!(true);
                    }
                    if let Some(m) = r.as_object_mut() {
                        m.remove("beside");
                    }
                    Some(r)
                }).collect();
                let edited = rows.iter().filter(|r| r["changed"] == json!(true)).count();
                row["subs"] = json!({ "options": options, "now": cur.and_then(|v| s.label_for(v)), "rows": rows, "edited": edited });
            }
            // the options that open a whole page of rows (`menu_rows::pages`), each with where its page is shown and
            // the link's words, as the window's option list has them
            let pages: Vec<Value> = menu_rows::pages(s, self.settings_in(target, None)).into_iter().filter_map(|p| {
                let on = self.settings_in(target, None).find(|o| o.key == p.key)?;
                Some(json!({ "option": p.option, "count": p.count, "key": p.key, "open_tab": self.entry_of(on), "open_group": self.shown_group_of(on),
                    "words": App::page_link_words(&p.option, self.camera_layout()) }))
            }).collect();
            if !pages.is_empty() {
                row["pages"] = json!(pages);
            }
        } else if self.camera_layout() {
            // as on the camera a sub-choice is no row of its own: its owner's row ("beside") opens it, where the Menu
            // shows it (a search lists it as a row, with a link there)
            if let Some(own) = menu_rows::beside_owner(group(), s) {
                row["beside"] = json!({ "owner": own.key, "name": own.name, "option": s.under_option, "tab": s.tab, "group": s.group,
                    // where its owner's row is (a family's setting is listed in its table, not there)
                    "open_tab": self.entry_of(own), "open_group": self.shown_group_of(own) });
            }
        }
        if self.prefs.expert {
            row["record"] = json!(format!("record 0x{:04x}", s.id));
        }
        if self.shows_record_ids() {
            row["record_id"] = json!(s.record_id_hex());
        }
        // the values its menus never offer, and a factory value the camera writes itself, in the window's words and hovers
        row["not_offered"] = json!(self.not_offered_lines(s).into_iter().map(|(text, title)| json!({ "text": text, "title": title })).collect::<Vec<_>>());
        row["display_rule"] = json!(s.display_rule);
        if self.prefs.expert {
            let ids: Vec<String> = linked.iter().map(|l| format!("0x{:04x}", l.id)).collect();
            row["records"] = json!(format!("{} {} ({}){}", if linked.len() > 1 { "Records" } else { "Record" }, ids.join(", "), s.area,
                if linked.len() > 1 { " · changing this updates all linked records together" } else { "" }));
        }
        row["record_hex"] = json!(format!("0x{:04x}", s.id));
        if self.show_raw && s.text.is_none() {
            if let Some(v) = cur {
                row["raw"] = json!(v);
            }
        }
        if self.web_has_mymenu() {
            row["mymenu_on"] = json!(true);
            row["menu_code"] = json!(s.menu_code.is_some());
            match s.menu_code {
                Some(c) => row["mymenu"] = json!(self.mymenu_find(c).map(|(p, i)| json!({ "page": p + 1, "item": i + 1 }))),
                None => {
                    let txt = &self.schema.camera.text;
                    let why = match txt.mymenu_excluded_tab.as_deref().filter(|t| !t.is_empty()) {
                        Some(t) if s.tab == t => txt.mymenu_excluded_reason.clone().filter(|w| !w.is_empty()).unwrap_or_else(|| format!("This camera does not allow {t} items in {}", txt.my_menu_name())),
                        _ => format!("This item has no {} entry on the camera (it is part of another item's screen)", txt.my_menu_name()),
                    };
                    row["mymenu_why"] = json!(why);
                }
            }
        }
        if let Some(t) = s.text.as_ref().and(self.compare.as_ref()).and_then(|(_, c)| c.sections.get(target)?.get(s.id)?.text()) {
            row["compare_text"] = json!(t);
        }
        row
    }

    /// Change one setting: a value from its list or range, or its text. Checked as the window
    /// checks it: editing on, the record's shape as mapped, and a value the setting offers. A refusal
    /// carries the row as it still is ("row", and "value"), so the page puts its control back; a change
    /// answers the row ("row"), every row it changes on the page ("rows": that one, then those it greys
    /// out or brings back), the new "rev" and the edit counts, so the page patches them in place.
    fn web_set(&mut self, target: usize, body: &Value, from: &str) -> WebReply {
        let Some(linked) = self.web_linked(target, body["key"].as_str().unwrap_or("")) else { return WebReply::error(404, "No such setting here.") };
        let s = &linked[0];
        let cur = self.doc.as_ref().and_then(|d| d.value(target, s.slot()));
        let refuse = |app: &Self, status: u16, why: &str| WebReply::refused(status, why, json!({ "row": app.web_row(target, &linked), "value": cur }));
        if !self.editable() {
            return refuse(self, 409, "View only: this firmware has not been checked yet, so editing is off.");
        }
        // from the compare: the cell's column, which must be the set changed in file A; file B and the base only compare
        if let Some(c) = body.get("col").filter(|c| !c.is_null()) {
            match self.col_from_json(c) {
                Some(col) if !col.editable() => return refuse(self, 409, "Only the open file, A, takes values: file B and the base file are compared, never changed."),
                Some(col) if col.section == target => {}
                _ => return refuse(self, 400, "This file has no such column."),
            }
        }
        if !linked.iter().all(|l| self.shape_ok_in(l, target)) {
            return refuse(self, 409, "This record does not have the shape it was mapped with, so it cannot be changed.");
        }
        // view only outside Expert mode: a setting no menu writes (`locked_why`)
        if let Some((why, _)) = self.locked_why(s, target) {
            return refuse(self, 409, &why);
        }
        // the records the camera keeps these settings' values in too (`copies`; for a copy, its setting and that
        // setting's other copies), and what they hold before the change: the reply carries the rows of those that move
        // with it, so the page shows them moved
        let mains: Vec<&Setting> = linked.iter().filter_map(|l| if l.copies.is_empty() { self.main_of(l) } else { Some(l) }).collect();
        let copies: Vec<(String, Slot, Option<i64>)> = mains.iter().flat_map(|m| std::iter::once(m.key.clone()).chain(m.copies.iter().cloned()))
            .filter_map(|k| self.schema.settings.iter().find(|c| c.key == k && kept_in(c, target)))
            .map(|c| (c.key.clone(), c.slot(), self.doc.as_ref().and_then(|d| d.value(target, c.slot())))).collect();
        let shown;
        if let Some(text) = body["text"].as_str() {
            let Some(rule) = &s.text else { return refuse(self, 400, "This setting is not a text.") };
            let text = if rule.uppercase { text.to_uppercase() } else { text.to_string() };
            if let Err(e) = rule.check(&text) {
                return refuse(self, 400, &e);
            }
            if let Some(why) = self.apply(vec![Action::SetText(target, s.id, text.clone())]) {
                return refuse(self, 409, &why);
            }
            shown = text;
        } else {
            let Some(v) = body["value"].as_i64() else { return refuse(self, 400, "No value given.") };
            if !s.scalar || cur.is_none() || s.text.is_some() {
                return refuse(self, 409, "This setting cannot be changed here.");
            }
            // a value the menus offer only under another video system than the file was saved under: why, and what to do
            if Some(v) != cur {
                if let Some(why) = self.other_system_words(s, v, target) {
                    return refuse(self, 400, &format!("Not changed: {why} Choose one of the values offered."));
                }
            }
            let ok = match s.range {
                Some((lo, hi)) => (lo..=hi).contains(&v) && (v - lo) % s.step.unwrap_or(1).max(1) == 0,
                None => self.offered_values(s, target).iter().any(|(o, _)| *o == v) || Some(v) == cur,
            };
            if !ok {
                return refuse(self, 400, "Not a value this setting offers.");
            }
            // a step that would leave a setting held by none of its copies is refused, with why (`apply`)
            if let Some(why) = self.apply(Self::set_linked(target, &linked, v)) {
                return refuse(self, 409, &why);
            }
            shown = Self::describe(s, Some(v));
        }
        self.status = format!("{} set to {shown} {from}", s.name);
        let row = self.web_row(target, &linked);
        // the rows greyed out (or no longer) by a record this change wrote, each once
        let ids: Vec<u16> = linked.iter().map(|l| l.id).collect();
        let mut keys: Vec<String> = Vec::new();
        for o in self.settings_in(target, None) {
            if o.inactive_when.as_ref().is_some_and(|r| ids.contains(&r.record)) && !linked.iter().any(|l| l.key == o.key) {
                let first = self.web_linked(target, &o.key).and_then(|l| l.first().map(|f| f.key.clone()));
                if let Some(k) = first.filter(|k| !keys.contains(k)) {
                    keys.push(k);
                }
            }
        }
        // the row whose option this setting is the choice for: its detail shows the choice
        if let Some(own) = menu_rows::owner(self.settings_in(target, Some(self.layout_tab(s))).filter(|o| menu_rows::camera_group(o) == menu_rows::camera_group(s)), s) {
            let first = self.web_linked(target, &own.key).and_then(|l| l.first().map(|f| f.key.clone()));
            if let Some(k) = first.filter(|k| !keys.contains(k)) {
                keys.push(k);
            }
        }
        // every copy that moved with it
        for (k, slot, was) in &copies {
            if self.doc.as_ref().and_then(|d| d.value(target, *slot)) != *was && !keys.contains(k) && !linked.iter().any(|l| &l.key == k) {
                keys.push(k.clone());
            }
        }
        let rows: Vec<Value> = std::iter::once(row.clone())
            .chain(keys.iter().filter_map(|k| self.web_linked(target, k)).map(|l| self.web_row(target, &l)))
            .collect();
        let edits = self.doc.as_ref().map_or(0, |d| d.changes().len());
        WebReply::json(json!({ "row": row, "rows": rows, "rev": self.web_rev(), "edits": edits,
            "can_undo": !self.undo.is_empty(), "can_redo": !self.redo.is_empty() }))
    }

    /// Every edited record: where, which setting, what it was and is.
    fn web_changes(&self) -> Value {
        let Some(doc) = &self.doc else { return json!({ "changes": [] }) };
        let changes: Vec<Value> = doc.changes().into_iter().map(|(si, id)| {
            let s = self.schema.find(si != 0, id);
            let fmt = |c: &CamSet| c.sections[si].get(id).map(|r| {
                if let Some(t) = s.filter(|s| s.text.is_some()).and_then(|_| r.text()) {
                    return t;
                }
                // as the window's All edits: the label with the number it is stored as
                let raw = r.display_value();
                s.and_then(|s| raw.parse::<i64>().ok().and_then(|v| s.label_for(v).map(|l| format!("{l} [{v}]")))).unwrap_or(raw)
            }).unwrap_or_default();
            let raw = |c: &CamSet| c.sections[si].get(id).map(|r| r.display_value()).unwrap_or_default();
            json!({
                "section": si, "id": id, "where": self.schema.camera.target_name(si),
                "name": s.map(|s| s.name.clone()).unwrap_or_else(|| format!("record 0x{id:04x}")),
                "was": fmt(&doc.original), "now": fmt(&doc.edited),
                "was_raw": raw(&doc.original), "now_raw": raw(&doc.edited),
            })
        }).collect();
        json!({ "changes": changes })
    }

    /// A file sent up from the page, checked to be a settings file the camera saved and kept in the
    /// editor's own folder (camera/web) under its own name, in a folder of its own named by the time it came and
    /// `tag` ("B_", "Base_" or none): the page and the window name it, and offer to save or download it, by the
    /// name it came with, never one with a time stamp.
    fn web_upload_path(&self, r: &WebRequest, tag: &str) -> Result<PathBuf, WebReply> {
        let given = percent_decode(&r.file_name);
        if let Err(e) = self.defs.open(&r.body, false) {
            // plain words; the parser's own (offsets, checksums) in Expert mode only
            let why = self.load_words(Path::new(&given), &LoadError::Parse(e));
            return Err(WebReply::error(400, &format!("Not opened: {why} Choose a settings file the camera saved.")));
        }
        let name = safe_name(given.rsplit(['/', '\\']).next().unwrap_or(""));
        let name = if name.is_empty() { "upload.DAT".to_string() } else { name };
        let dir = Self::camera_dir().join("web");
        let tag = tag.trim_end_matches('_');
        let stem = if tag.is_empty() { file_stamp() } else { format!("{}_{tag}", file_stamp()) };
        // two files in the same second each get a folder of their own: the first name free is claimed by making it
        // (another editor writing there at the same moment gets the next)
        let claimed = std::fs::create_dir_all(&dir).and_then(|_| {
            (1..1000).map(|n| if n == 1 { dir.join(&stem) } else { dir.join(format!("{stem}_{n}")) })
                .find(|f| std::fs::create_dir(f).is_ok())
                .ok_or_else(|| std::io::Error::other("no free folder name for the upload"))
        });
        let path = claimed.as_ref().map(|f| f.join(&name)).unwrap_or_default();
        claimed.and_then(|_| write_atomic(&path, &r.body)).map_err(|e| {
            let details = details(self.prefs.expert, &e);
            WebReply::error(500, &format!("The file could not be kept on the editor's computer: {}{details}", io_words(&e, true)))
        })?;
        self.prune_uploads(&dir, &path);
        Ok(path)
    }

    /// What the page sent up is kept for the latest `WEB_UPLOADS_KEPT` (each file in a folder of its own; a file an
    /// older editor kept directly in `dir` counts as one); older ones are removed, except one that holds a file open
    /// now (A, B or the base) or `new`, the one just kept.
    fn prune_uploads(&self, dir: &Path, new: &Path) {
        let Ok(rd) = std::fs::read_dir(dir) else { return };
        let open: Vec<&Path> = self.doc.iter().map(|d| d.path.as_path())
            .chain(self.compare.iter().chain(self.base.iter()).map(|(p, _)| p.as_path())).chain(std::iter::once(new)).collect();
        let mut kept: Vec<(std::time::SystemTime, PathBuf)> = rd.flatten()
            .filter(|e| e.file_type().is_ok_and(|t| t.is_file() || t.is_dir()))
            .map(|e| (e.metadata().and_then(|m| m.modified()).unwrap_or(std::time::UNIX_EPOCH), e.path()))
            .collect();
        // newest first (by time, then by name: the names start with the time they were kept)
        kept.sort_by(|a, b| b.cmp(a));
        for (_, p) in kept.into_iter().skip(WEB_UPLOADS_KEPT) {
            if open.iter().any(|o| o.starts_with(&p)) {
                continue;
            }
            let _ = if p.is_dir() { std::fs::remove_dir_all(&p) } else { std::fs::remove_file(&p) };
        }
    }

    /// A column's file as the page names it.
    fn web_src(src: Src) -> &'static str {
        match src {
            Src::A => "a",
            Src::B => "b",
            Src::Base => "base",
        }
    }

    /// The columns the page asks for (`cols`: `[file, set]` each, the first the baseline), each
    /// checked as `col_from_json` checks it; with none named, the window's own columns, less those
    /// whose file is not open or whose set is not shown (`prune_cols`). The page keeps its own
    /// columns, so it never moves the window's.
    fn web_cols(&self, body: &Value) -> Result<Vec<Col>, WebReply> {
        match body.get("cols") {
            None | Some(Value::Null) => {
                let shown = self.shown_sections();
                Ok(self.cols.iter().copied().filter(|c| self.set_for(c.src).is_some() && shown.contains(&c.section)).collect())
            }
            Some(Value::Array(list)) => list.iter()
                .map(|v| self.col_from_json(v).ok_or_else(|| WebReply::error(400, "A column names a file that is not open, or a set this file does not show.")))
                .collect(),
            Some(_) => Err(WebReply::error(400, "The columns are a list of [file, set].")),
        }
    }

    /// The files of the compare as its bar shows them: A, B and the base, each with its name and
    /// firmware badge (B and the base also with their model and save date); null when not open.
    fn web_compare_files(&self) -> Value {
        let other = |f: &Option<(PathBuf, CamSet)>| f.as_ref().map(|(p, c)| json!({
            "name": p.file_name().unwrap_or_default().to_string_lossy(),
            "saved": self.stamp_words(&c.timestamp()), "model": c.model(),
            "badge": self.web_badge(c, &c.layout_signature(), false),
        }));
        json!({
            "a": self.doc.as_ref().map(|d| json!({
                "name": d.path.file_name().unwrap_or_default().to_string_lossy(),
                "badge": self.web_badge(&d.edited, &d.signature, d.unchecked_ok),
            })),
            "b": other(&self.compare),
            "base": other(&self.base),
        })
    }

    /// The state's "compare": file B and the base (null when not open), the window's columns as
    /// the page's first ones, the window's "Only rows that differ" and "Show raw values" as the
    /// page's first choices, and the tabs its tab list offers.
    fn web_compare_state(&self) -> Value {
        let files = self.web_compare_files();
        let cols: Vec<Value> = self.web_cols(&Value::Null).unwrap_or_default().iter().map(|c| json!([Self::web_src(c.src), c.section])).collect();
        json!({
            "b": files["b"], "base": files["base"], "cols": cols,
            "only_diff_default": self.prefs.matrix_only_diff, "show_raw": self.show_raw,
            "tabs": self.schema.tabs,
            // the window's line under the files when they were saved under different video systems; null when not
            "video_note": self.video_systems_note(),
        })
    }

    /// What the compare page and the record map share: the columns as headed (`col_name`, the
    /// file's letter and whether it takes values; the page colours a file by its letter), the files,
    /// the sets a column can show (`shown_sections`: [set, short name, name]) and the dial memories
    /// for the Whole sets row.
    fn web_compare_frame(&self, cols: &[Col]) -> Value {
        let cols: Vec<Value> = cols.iter().map(|c| json!({
            "src": Self::web_src(c.src), "section": c.section, "name": self.col_name(*c), "letter": c.src.letter(),
            "short": self.schema.camera.short_name(c.section), "editable": c.editable(),
        })).collect();
        let sections: Vec<Value> = self.shown_sections().into_iter()
            .map(|s| json!([s, self.schema.camera.short_name(s), self.schema.camera.target_name(s)])).collect();
        let dial: Vec<Value> = self.dial_sets().into_iter().map(|s| json!([s, self.schema.camera.target_name(s)])).collect();
        // in the window's words; the page's own "Only the rows shown" box says when a copy is narrowed
        json!({ "cols": cols, "files": self.web_compare_files(), "sections": sections, "dial": dial, "editable": self.editable(),
            "whole_sets": self.web_whole_sets(false) })
    }

    /// The three-way columns among the page's: the first Base, A and B column, when a base is open
    /// (`three_cols` for the window's columns).
    fn web_three_cols(&self, cols: &[Col]) -> Option<(Col, Col, Col)> {
        self.base.as_ref()?;
        let find = |src: Src| cols.iter().copied().find(|c| c.src == src);
        Some((find(Src::Base)?, find(Src::A)?, find(Src::B)?))
    }

    /// The compare matrix as the window's `matrix_view` draws it for the page's columns (the first
    /// is the baseline), search `q`, tab, "Only rows that differ", "Show raw values" and three-way
    /// filter: the counts over the table, the three-way summary, and each row shown with its cells
    /// (text, highlights, whether it takes a value in place), the arrows between its columns and its mark on the
    /// change map. The row of setting `keep` (the one last changed from the page's compare) stays shown whatever
    /// "Only rows that differ" and the three-way filter say, as the window's does (`cmp_kept`), so the rows and the
    /// cursor do not move under the person's hand.
    fn web_compare(&self, cols: &[Col], q: &str, tab: Option<&str>, (only_diff, keep): (bool, Option<&str>), raw: bool, three_filter: ThreeFilter) -> Value {
        let mut out = self.web_compare_frame(cols);
        for (k, v) in [("total", json!(0)), ("shown", json!(0)), ("diffs", json!(0)), ("three", Value::Null), ("counts", json!([])), ("rows", json!([]))] {
            out[k] = v;
        }
        let Some(doc) = &self.doc else { return out };
        if cols.len() < 2 {
            return out;
        }
        let base = cols[0];
        let rows = self.matrix_rows_for(q, tab);
        let stored = |c: &Col, s: &Setting| c.section == 0 || s.in_sets;
        let differs = |s: &Setting| {
            let b = self.col_value(base, s);
            cols[1..].iter().any(|c| self.col_value(*c, s) != b && stored(c, s))
        };
        let counts: Vec<usize> = cols.iter().map(|c| rows.iter().filter(|r| {
            let s = &r.2[0];
            stored(c, s) && self.col_value(*c, s) != self.col_value(base, s)
        }).count()).collect();
        let three = self.web_three_cols(cols);
        let word = |t: Three| match t {
            Three::Same => "same",
            Three::AOnly => "a",
            Three::BOnly => "b",
            Three::Both => "both",
            Three::Conflict => "conflict",
        };
        if let Some(tc) = three {
            let classes: Vec<Three> = rows.iter().map(|r| self.three_way(tc, &r.2[0])).collect();
            let count = |k: Three| classes.iter().filter(|c| **c == k).count();
            let tags: serde_json::Map<String, Value> = [Three::AOnly, Three::BOnly, Three::Both, Three::Conflict, Three::Same].into_iter()
                .map(|t| (word(t).to_string(), json!([t.tag().0, t.tag().1]))).collect();
            let filters: Vec<Value> = [(ThreeFilter::All, "all"), (ThreeFilter::AOnly, "a"), (ThreeFilter::BOnly, "b"), (ThreeFilter::Both, "both"), (ThreeFilter::Conflicts, "conflicts")]
                .into_iter().map(|(f, w)| json!([w, f.label()])).collect();
            let (tb, ta, tbb) = tc;
            out["three"] = json!({
                "a": count(Three::AOnly), "b": count(Three::BOnly), "both": count(Three::Both), "conflict": count(Three::Conflict),
                "cols": [[Self::web_src(tb.src), tb.section], [Self::web_src(ta.src), ta.section], [Self::web_src(tbb.src), tbb.section]],
                "against": format!("{} against {} and {}", self.col_name(tb), self.col_name(ta), self.col_name(tbb)),
                "tags": tags, "filters": filters,
            });
        }
        let kept = |s: &Setting| keep == Some(s.key.as_str());
        let shown: Vec<&(String, String, Vec<Setting>)> = rows.iter()
            .filter(|r| !only_diff || differs(&r.2[0]) || kept(&r.2[0]))
            .filter(|r| three.is_none_or(|tc| three_filter.keeps(self.three_way(tc, &r.2[0]))) || kept(&r.2[0]))
            .collect();
        let mut diffs = 0;
        let list: Vec<Value> = shown.iter().map(|(t, g, linked)| {
            let s = &linked[0];
            let b = self.col_value(base, s);
            let class = three.map(|tc| self.three_way(tc, s));
            let mut mark = "same";
            let cells: Vec<Value> = cols.iter().enumerate().map(|(i, c)| {
                let v = self.col_value(*c, s);
                let st = stored(c, s);
                let mut text = if !st { "—".to_string() } else if s.text.is_some() { self.col_text(*c, s).unwrap_or_default() } else { Self::describe(s, v) };
                if let Some(v) = v.filter(|_| raw) {
                    text = format!("{}  [{v}]", Self::describe(s, Some(v)));
                }
                let edited = c.editable() && st && doc.original_value(c.section, s.slot()) != v;
                let differs_here = i > 0 && st && v != b;
                if edited {
                    mark = "edited";
                } else if differs_here && mark == "same" {
                    mark = "differs";
                }
                let mut cell = json!({ "text": text, "value": v, "stored": st, "differs": differs_here, "edited": edited });
                // a value of file A that can change opens the picker in place (`cell_editable`); an edit says what it was
                if self.cell_editable(*c, linked) {
                    cell["editable"] = json!(true);
                }
                if edited {
                    cell["was"] = json!(self.col_was(*c, s));
                }
                // what puts it back where the camera keeps it, where the plain Revert does not serve (`put_back_choice`)
                if c.editable() && st {
                    if let Some((words, _)) = self.put_back_choice(linked, c.section) {
                        cell["put_back"] = json!(words);
                    }
                }
                // the window cuts a long value short and shows it whole on hover
                if text.chars().count() > 30 {
                    cell["text_full"] = json!(text);
                }
                // a number with no name yet says why on hover (`unnamed_why`), a value of file A that is view only
                // outside Expert mode why it takes none (`locked_why`), and one the camera keeps in more than one record
                // what changing it changes (`copy_note`), as the window's cell
                let file_a = st && c.editable();
                let why: Vec<String> = self.unnamed_why(s, v).filter(|_| st).into_iter()
                    .chain(self.locked_why(s, c.section).filter(|_| file_a).map(|(w, _)| w))
                    .chain(self.copy_note(s, c.section).filter(|_| file_a).map(|(w, _)| w)).collect();
                if !why.is_empty() {
                    cell["why"] = json!(why.join("\n\n"));
                }
                cell
            }).collect();
            if class == Some(Three::Conflict) && mark != "edited" {
                mark = "conflict";
            }
            let arrows: Vec<Value> = (1..cols.len()).map(|i| {
                let (l, r) = self.arrows_between(cols[i - 1], cols[i], s);
                json!([l, r])
            }).collect();
            let d = differs(s);
            diffs += usize::from(d);
            // the sets of file A where the setting is view only outside Expert mode (`locked_why`): no copy goes there,
            // as the window's right-click menu offers none (`copy_targets`)
            let locked: Vec<usize> = (0..self.n_sections()).filter(|&si| self.locked(s, si)).collect();
            json!({
                "tab": t, "group": g, "open_group": self.shown_group_of(s), "open_tab": self.entry_of(s), "color": css_color(tab_color(&self.schema.camera, t)),
                "key": s.key, "name": self.setting_title(s), "record": format!("0x{:04x}", s.id), "in_sets": s.in_sets, "locked": locked,
                // the name's hover, as the window's (the record number in Expert mode only)
                "where": self.where_kept(s),
                "three": class.map(word), "differs": d, "mark": mark, "arrows": arrows, "cells": cells,
            })
        }).collect();
        out["total"] = json!(rows.len());
        out["shown"] = json!(list.len());
        out["diffs"] = json!(diffs);
        out["counts"] = json!(counts);
        out["rows"] = json!(list);
        out
    }

    /// The compare's record map as the window's `records_matrix` draws it: every record of the
    /// baseline column's set in file order, with its offset in the file, shape and setting (null
    /// for one not mapped), and each column's value, marked where it differs from the baseline.
    fn web_compare_records(&self, cols: &[Col], q: &str, only_diff: bool, raw: bool) -> Value {
        let mut out = self.web_compare_frame(cols);
        out["total"] = json!(0);
        out["rows"] = json!([]);
        let Some(&base) = cols.first() else { return out };
        let Some(base_set) = self.set_for(base.src) else { return out };
        let Some(base_sec) = base_set.sections.get(base.section) else { return out };
        // where each record starts, by the framing of the file's container block
        let offsets = base_set.record_offsets(base.section);
        let in_set = base.section != 0;
        let q = q.to_lowercase();
        let mut rows = Vec::new();
        for (ri, r) in base_sec.records.iter().enumerate() {
            let off = offsets.get(ri).copied().unwrap_or_default();
            let setting = self.schema.find(in_set, r.id);
            let cell = |rec: Option<&camset_editor::camset::Record>| -> String {
                match rec {
                    None => "—".into(),
                    Some(rec) => match setting {
                        Some(s) if s.text.is_some() => rec.text().unwrap_or_default(),
                        Some(s) if s.scalar => if raw { format!("{} [{}]", Self::describe(s, rec.as_int()), rec.display_value()) } else { Self::describe(s, rec.as_int()) },
                        _ => rec.display_value(),
                    },
                }
            };
            let values: Vec<(String, bool)> = cols.iter().map(|c| {
                let rec = self.set_for(c.src).and_then(|s| s.sections.get(c.section)).and_then(|s| s.get(r.id));
                (cell(rec), rec.is_some_and(|x| x.value != r.value))
            }).collect();
            if only_diff && !values.iter().any(|(_, d)| *d) {
                continue;
            }
            let id = format!("0x{:04x}", r.id);
            if !q.is_empty() && !id.contains(&q) && !setting.is_some_and(|s| s.name.to_lowercase().contains(&q) || s.group.to_lowercase().contains(&q))
                && !values.iter().any(|(v, _)| v.to_lowercase().contains(&q))
            {
                continue;
            }
            rows.push(json!({
                "offset": format!("{off:06x}"), "id": id, "shape": format!("{}×{}", r.elem_size, r.count),
                "setting": setting.map(|s| json!({ "key": s.key, "name": s.name, "tab": s.tab, "group": s.group, "open_group": self.shown_group_of(s), "open_tab": self.entry_of(s), "note": s.note_shown(self.prefs.expert) })),
                "cells": values.iter().map(|(v, d)| json!({ "text": v, "differs": d })).collect::<Vec<_>>(),
            }));
        }
        out["total"] = json!(base_sec.records.len());
        out["rows"] = json!(rows);
        out
    }

    /// The settings the memory sets keep, as the window's Memories page lists them (`matrix_rows`,
    /// the rows whose setting is in the sets), for a search `q` of the page's own (empty: all).
    fn web_memory_rows(&self, q: &str) -> Vec<(String, String, Vec<Setting>)> {
        self.matrix_rows_for(q.trim(), None).into_iter().filter(|r| r.2[0].in_sets).collect()
    }

    /// The Memories page as the window's (`memories_view`): the mode-dial memories beside the live
    /// settings, with the buttons that recall or register a whole memory and their hover texts in
    /// the camera's words. With `all` (the editor's "all memory columns" preference when the page
    /// does not say) the file's other memory sets (Movie, S&Q, …) are columns too; recall and
    /// register stay with the dial's memories, as in the window. With `only_diff` (the window's "Only rows that differ
    /// from Live" when the page does not say) only the rows where a shown memory differs from the live settings.
    fn web_memories(&self, q: &str, all: Option<bool>, only_diff: Option<bool>) -> Value {
        let cam = &self.schema.camera;
        let dial = self.dial_sets();
        let others: Vec<usize> = (1..self.n_sections()).filter(|s| !dial.contains(s)).collect();
        let all = all.unwrap_or(self.prefs.all_memory_cols) && !others.is_empty();
        let shown: Vec<usize> = dial.iter().chain(others.iter().filter(|_| all)).copied().collect();
        let named = |list: &[usize]| list.iter().map(|&m| json!([m, cam.target_name(m)])).collect::<Vec<_>>();
        let dial_hint = cam.text.memory_dial_hint.clone().filter(|t| !t.is_empty());
        let register_menu = cam.text.memory_register_menu.clone().filter(|t| !t.is_empty());
        let only_diff = only_diff.unwrap_or(self.prefs.memories_only_diff);
        // the window's buttons and hover texts (`recall_words`, `register_words`), word for word: they copy every
        // setting the memories keep, whatever the search shows
        let buttons = self.web_whole_sets(!q.trim().is_empty());
        let live = Col::a(0);
        let text = |c: Col, s: &Setting| if s.text.is_some() { self.col_text(c, s).unwrap_or_default() } else { Self::describe(s, self.col_value(c, s)) };
        let mut groups: Vec<Value> = Vec::new();
        for (tab, group, linked) in self.web_memory_rows(q) {
            let s = &linked[0];
            let lv = self.col_value(live, s);
            if only_diff && !shown.iter().any(|&m| self.memory_differs(Col::a(m), s)) {
                continue;
            }
            // an edit is orange with a pencil, a difference from the live settings a pale fill, as in the window
            let edited = |c: Col| self.doc.as_ref().is_some_and(|d| d.original_value(c.section, s.slot()) != self.col_value(c, s));
            let cells: Vec<Value> = shown.iter().map(|&m| {
                let v = self.col_value(Col::a(m), s);
                json!({ "section": m, "text": text(Col::a(m), s), "value": v, "differs": self.memory_differs(Col::a(m), s), "edited": edited(Col::a(m)),
                    "why": self.unnamed_why(s, v),
                    // a value the camera keeps in more than one record: what a copy into this memory changes (`copy_note`)
                    "copies": self.copy_note(s, m).map(|(w, _)| w),
                    // whether the live settings, and this memory, take a value of it: not where it is view only outside
                    // Expert mode (`locked_why`), as the window's arrows
                    "takes": [!self.locked(s, 0), !self.locked(s, m)],
                    "into_live": Self::arrow_words(&cam.target_name(m), &cam.target_name(0)),
                    "from_live": Self::arrow_words(&cam.target_name(0), &cam.target_name(m)) })
            }).collect();
            let row = json!({
                "key": s.key, "name": self.setting_title(s),
                "record_id": self.shows_record_ids().then(|| s.record_id_hex()),
                "live": { "text": text(live, s), "value": lv, "edited": edited(live), "why": self.unnamed_why(s, lv), "copies": self.copy_note(s, 0).map(|(w, _)| w) },
                "cells": cells,
            });
            // a new heading whenever the tab and group change, as the window's grid has it
            let same = groups.last().is_some_and(|g| g["tab"] == tab.as_str() && g["group"] == group.as_str());
            if !same {
                groups.push(json!({ "tab": tab, "group": group, "color": css_color(tab_color(cam, &tab)), "rows": [] }));
            }
            if let Some(rows) = groups.last_mut().and_then(|g| g["rows"].as_array_mut()) {
                rows.push(row);
            }
        }
        json!({
            "title": self.memories_title(),
            "intro": self.memories_lead(),
            "dial": named(&dial),
            "others": named(&others),
            "all": all,
            "cols": named(&shown),
            "editable": self.editable(),
            "only_diff": only_diff,
            "hints": { "recall": dial_hint, "register": register_menu },
            "buttons": buttons,
            "groups": groups,
        })
    }

    /// The Whole sets buttons of Compare and the Memories page, in the window's words (`recall_words`,
    /// `register_words`): each dial memory's section, buttons and hovers; `narrowed`: a search or a tab narrows the
    /// rows shown, which the hovers say does not narrow the copy.
    fn web_whole_sets(&self, narrowed: bool) -> Vec<Value> {
        let every = self.whole_set_note(narrowed);
        self.dial_sets().into_iter().map(|m| {
            let (recall, recall_tip, _) = self.recall_words(m, &every, "");
            let (register, register_tip, _) = self.register_words(m, &every, "");
            json!({ "section": m, "recall": recall, "recall_tip": recall_tip, "register": register, "register_tip": register_tip })
        }).collect()
    }

    /// Recall a dial memory into the live settings, or register the live settings into it, as the
    /// window's buttons do: every setting the memories keep, whatever the page's search and tab show
    /// (`memory_rows`), through `copy_row` and `apply`, so it is one step to undo and shows in All
    /// edits. Only a request that says `shown: true` copies just the rows its search `q` and `tab` leave.
    fn web_recall(&mut self, recall: bool, body: &Value, from: &str) -> WebReply {
        if !self.editable() {
            return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
        }
        let Some(m) = body["memory"].as_u64().map(|m| m as usize).filter(|m| self.dial_sets().contains(m)) else {
            return WebReply::error(400, "Not one of the mode dial's memories.");
        };
        let (live, memory) = (Col::a(0), Col::a(m));
        let (src, dst) = if recall { (memory, live) } else { (live, memory) };
        let rows = if body["shown"].as_bool() == Some(true) {
            let tab = body["tab"].as_str().filter(|t| !t.is_empty());
            self.matrix_rows_for(body["q"].as_str().unwrap_or("").trim(), tab).into_iter().filter(|r| r.2[0].in_sets).collect()
        } else {
            self.memory_rows()
        };
        let mut actions: Vec<Action> = rows.iter().flat_map(|r| self.copy_row(&r.2, src, dst)).collect();
        let n = actions.len();
        self.pin_families(Some(src.section), dst.section, &mut actions);
        let left = self.copy_skipped.get();
        if let Some(why) = self.apply(actions) {
            return WebReply::error(409, &why);
        }
        let from = format!(" {from}");
        let (_, _, said) = if recall { self.recall_words(m, "", &from) } else { self.register_words(m, "", &from) };
        self.status = with_left(&said, left);
        WebReply::json(json!({ "ok": true, "n": n, "left": left.total(), "message": left_alone(left) }))
    }

    /// One row's arrow on the Memories page: a memory's value into the live settings (⬅) or the live
    /// value into the memory (➡), every record of the setting, through `copy_row` and `apply`.
    fn web_memory_copy(&mut self, body: &Value, from: &str) -> WebReply {
        let section = |k: &str| body[k].as_u64().map_or(usize::MAX, |v| v as usize);
        let (a, b) = (section("from"), section("to"));
        let memory = |s: usize| s >= 1 && s < self.n_sections();
        if !(a == 0 && memory(b) || b == 0 && memory(a)) {
            return WebReply::error(400, "A value goes between the live settings and one memory.");
        }
        let key = body["key"].as_str().unwrap_or("");
        let Some((_, _, linked)) = self.web_memory_rows("").into_iter().find(|r| r.2.iter().any(|s| s.key == key)) else {
            return WebReply::error(404, "No such setting in the memories.");
        };
        if !self.editable() {
            return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
        }
        let actions = self.copy_row(&linked, Col::a(a), Col::a(b));
        let n = actions.len();
        let left = self.copy_skipped.get();
        if let Some(why) = self.apply(actions) {
            return WebReply::error(409, &why);
        }
        let cam = &self.schema.camera;
        let said = format!("{}: the value from {} put into {} {from}", linked[0].name, cam.target_name(a), cam.target_name(b));
        self.status = with_left(&said, left);
        WebReply::json(json!({ "ok": true, "n": n, "left": left.total(), "message": left_alone(left) }))
    }

    /// The Exposure page as the window's (`exposure_view`, from the same helpers): per column (the
    /// live settings and each dial memory) the exposure mode and who sets what, the three sides with
    /// what the page draws their stop scales from, compensation and the EV they expose for; then the
    /// "What decides …" lists. Whether each of those settings was proved comes only while the
    /// proof lines are on (Settings), as in the window.
    fn web_exposure(&self) -> Value {
        use super::exposure::{EFFECTS, EV_HOVER, INTRO, SIDES};
        use camset_editor::stops::Side;
        let Some(ex) = self.schema.camera.exposure.clone() else { return Value::Null };
        let word = |side: Side| match side { Side::Aperture => "aperture", Side::Shutter => "shutter", Side::Iso => "iso" };
        let sections = self.ex_sections();
        let modes: Vec<Option<String>> = sections.iter().map(|&s| self.ex_mode(&ex, s)).collect();
        let cells = self.ex_cells(&ex, &sections, &modes);
        let columns: Vec<Value> = sections.iter().zip(&modes).zip(&cells).map(|((&sec, mode), row)| {
            let mut sides = serde_json::Map::new();
            for (k, (side, name)) in SIDES.iter().enumerate() {
                sides.insert(word(*side).into(), Self::web_cell(&row[k], name));
            }
            json!({
                "section": sec, "name": self.schema.camera.target_name(sec),
                "mode": mode,
                "control": mode.as_ref().and_then(|m| ex.control.get(m)).map(Self::ex_control),
                "mode_note": Some(&ex.mode_note).filter(|n| sec == 0 && !n.is_empty()),
                "cells": sides,
                "comp": { "text": self.ex_comp(&ex, sec), "note": Self::ex_comp_note(row) },
                "exposes": Self::ex_exposes(row).map(|ev| format!("EV {ev:.1} at ISO 100")),
                "exposes_hover": EV_HOVER,
            })
        }).collect();
        let mut scales = serde_json::Map::new();
        for (side, _) in SIDES {
            let scale = self.ex_scale(side, &Self::ex_side(&ex, side).scale_key).map(|((lo, lo_label), (hi, hi_label))| json!({
                "lo": lo, "hi": hi, "lo_label": lo_label, "hi_label": hi_label,
                // one tick per whole stop, as the window draws them
                "ticks": ((lo.ceil() as i64)..=(hi.floor() as i64)).collect::<Vec<_>>(),
            }));
            scales.insert(word(side).into(), scale.unwrap_or(Value::Null));
        }
        let decides: Vec<Value> = EFFECTS.iter().map(|(side, name, effect)| json!({
            "side": word(*side), "name": name, "effect": effect,
            "settings": self.ex_decides(&ex, *side).iter().map(|s| json!({
                "key": s.key, "name": s.name, "tab": s.tab, "group": s.group, "open_group": self.shown_group_of(s), "open_tab": self.entry_of(s),
                // a setting the memory sets only keep shows in the menu while a memory is edited
                "live": s.area == "global",
                "proved": self.shows_proof().then_some(s.proved.is_some()),
            })).collect::<Vec<_>>(),
        })).collect();
        json!({
            "title": Self::ex_title(&ex), "intro": INTRO,
            "columns": columns,
            "scales": scales,
            "sides": SIDES.iter().map(|(side, name)| json!([word(*side), name])).collect::<Vec<_>>(),
            "decides": decides,
            "show_proof": self.shows_proof(),
        })
    }

    /// One side of one column on the Exposure page: who sets it, its value (in stops too), the band
    /// and bound the limits leave the camera, the limits in words, and the scale's hover text.
    fn web_cell(c: &super::exposure::Cell, name: &str) -> Value {
        json!({
            "who": c.who.word(), "text": c.text, "at": c.at,
            "band": c.band.map(|(a, b)| json!([a, b])),
            "bound": c.bound.as_ref().map(|(x, how)| json!([x, how])),
            "notes": c.notes,
            "hover": Self::ex_hover(name, c),
        })
    }

    /// The requests for the rest of the window's controls; each does what the window's control does.
    fn web_answer_more(&mut self, action: &str, target: usize, body: &Value, from: &str) -> WebReply {
        let ok = || WebReply::json(json!({ "ok": true }));
        // the page asked the person before a request that replaces file A over unsaved edits
        let discard = body["discard"].as_bool() == Some(true);
        // a camera request's answer: done, and the camera cards as they are now (`web_camera`)
        let cards = |app: &Self| WebReply::json(json!({ "ok": true, "camera": app.web_camera() }));
        let busy = self.camera_job.is_some();
        let q = body["q"].as_str().unwrap_or("").trim().to_lowercase();
        let index = |k: &str| body[k].as_u64().and_then(|i| usize::try_from(i).ok());
        match action {
            "unmapped" | "records" if !self.prefs.expert => {
                WebReply::error(409, "Unmapped records and the record map are shown in Expert mode (⚙ Settings, Editing & Compare).")
            }
            "unmapped" => WebReply::json(self.web_unmapped(target, &q, body["only"].as_bool().unwrap_or(false))),
            "records" => {
                let open: Option<Vec<u16>> = body["open"].as_array().map(|a| a.iter().filter_map(|v| v.as_u64().and_then(|i| u16::try_from(i).ok())).collect());
                let (unmapped, edited) = (body["only_unmapped"].as_bool().unwrap_or(false), body["only_edited"].as_bool().unwrap_or(false));
                WebReply::json(self.web_records(target, &q, unmapped, edited, open.as_deref()))
            }
            "raw_set" => {
                let (Some(id), Some(v)) = (body["id"].as_u64().and_then(|i| u16::try_from(i).ok()), body["value"].as_i64()) else {
                    return WebReply::error(400, "Name a record and a number.");
                };
                if !self.editable() || !self.allow_raw_edits {
                    return WebReply::error(409, "Raw edits are off: tick Allow raw edits on the Unmapped records page (Expert mode).");
                }
                let Some(size) = self.doc.as_ref().and_then(|d| d.edited.sections.get(target)?.get(id)).map(|r| (r.as_int(), r.elem_size)) else {
                    return WebReply::error(404, "This set has no such record.");
                };
                if self.schema.find(target != 0, id).is_some() {
                    return WebReply::error(400, "This record is mapped: change it as its setting.");
                }
                if size.0.is_none() {
                    return WebReply::error(400, "This record does not hold one number, so it cannot be changed here.");
                }
                if let Some(why) = self.apply(vec![Action::Set(target, (id, None), v)]) {
                    return WebReply::error(409, &why);
                }
                if self.doc.as_ref().and_then(|d| d.value(target, (id, None))) != Some(v) {
                    return WebReply::error(400, &format!("{v} does not fit record 0x{id:04x} ({} byte(s)).", size.1));
                }
                self.status = format!("Record 0x{id:04x} set to {v} {from}");
                ok()
            }
            "prefs" => match self.web_set_pref(body["name"].as_str().unwrap_or(""), &body["value"]) {
                Ok(said) => {
                    self.status = format!("{said} {from}");
                    WebReply::json(json!({ "ok": true, "prefs": self.web_prefs() }))
                }
                Err((status, why)) => WebReply::error(status, &why),
            },
            "backups" => WebReply::json(self.web_backups()),
            "open_backup" => match Self::listed_backup(Self::list_backups(), body["folder"].as_str(), body["name"].as_str()) {
                Ok(b) => self.web_open(b.path, discard),
                Err(no) => no,
            },
            "history" => WebReply::json(self.web_history()),
            "revert_history" => {
                let (Some(step), Some(si), Some(id)) = (index("step"), index("section"), body["id"].as_u64().and_then(|i| u16::try_from(i).ok())) else {
                    return WebReply::error(400, "Name the edit: its step, set and record.");
                };
                let Some(rec) = self.undo.get(step).and_then(|c| c.sections.get(si)).and_then(|sec| sec.get(id)).cloned() else {
                    return WebReply::error(400, "The history has no such edit.");
                };
                // the rule every edit keeps, checked here rather than left to whoever asks
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                if let Some(why) = self.apply(vec![Action::SetRecord(si, rec)]) {
                    return WebReply::error(409, &why);
                }
                self.status = format!("Record 0x{id:04x} put back as it was before edit {} {from}", step + 1);
                ok()
            }
            "sample" => {
                if let Some(no) = self.web_unsaved(discard) {
                    return no;
                }
                if self.defs.samples().is_empty() {
                    return WebReply::error(409, "There is no sample to explore: no camera definition found names one.");
                }
                self.open_sample_now();
                ok()
            }
            "open_recent" => match index("index").and_then(|i| self.prefs.recent.get(i)).cloned() {
                Some(p) => self.web_open(PathBuf::from(p), discard),
                None => WebReply::error(400, "No such recent file."),
            },
            "clear_recent" => {
                self.prefs.recent.clear();
                self.prefs.save();
                self.status = format!("Recent files cleared {from}");
                ok()
            }
            "csv" => self.web_csv(target, &q, body, from),
            "layout" => {
                let src = match body["src"].as_str().unwrap_or("a") {
                    "a" => Src::A,
                    "b" => Src::B,
                    "base" => Src::Base,
                    _ => return WebReply::error(400, "Name file a, b or base."),
                };
                let Some(c) = self.set_for(src) else { return WebReply::error(409, "That file is not open.") };
                let text = Self::layout_json(c);
                self.status = format!("Layout downloaded {from}");
                WebReply { status: 200, content_type: "application/octet-stream", body: text.into_bytes(), download: Some("camera_layout.json".into()), keep: false }
            }
            "mymenu" => {
                let Some(s) = self.schema.settings.iter().find(|s| Some(s.key.as_str()) == body["key"].as_str()).cloned() else {
                    return WebReply::error(404, "No such setting.");
                };
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                if !self.web_has_mymenu() {
                    return WebReply::error(409, &format!("This file has no {} records", self.schema.camera.text.my_menu_name()));
                }
                let Some(code) = s.menu_code else {
                    return WebReply::error(400, &format!("This item has no {} entry on the camera (it is part of another item's screen)", self.schema.camera.text.my_menu_name()));
                };
                let done = if body["add"].as_bool().unwrap_or(true) {
                    self.mymenu_add(code)
                } else {
                    self.mymenu_remove(code).ok_or_else(|| format!("Not in {}", self.schema.camera.text.my_menu_name()))
                };
                match done {
                    Ok((actions, message)) => {
                        if let Some(why) = self.apply(actions) {
                            return WebReply::error(409, &why);
                        }
                        self.status = format!("{}: {message}; {from}", s.name);
                        WebReply::json(json!({ "ok": true, "message": message }))
                    }
                    Err(why) => WebReply::error(400, &why),
                }
            }
            // a place of the My Menu page: its item taken out, moved up or down its page, or another item put in it
            // ("set", with the item's code in `to`: `mymenu_set`, an empty place's item going after its page's items),
            // as the window's buttons and picker; the page names the item it showed there (`code`), so a page drawn
            // before another change does not act on the item now in that place
            "mymenu_slot" => {
                let name = self.schema.camera.text.my_menu_name().to_string();
                if !self.editable() {
                    return WebReply::error(409, "View only: this firmware has not been checked yet, so editing is off.");
                }
                if !self.web_has_mymenu() {
                    return WebReply::error(409, &format!("This file has no {name} records"));
                }
                let (p, i) = (body["page"].as_u64().unwrap_or(u64::MAX) as usize, body["item"].as_u64().unwrap_or(u64::MAX) as usize);
                let held = self.mymenu_pages().and_then(|pages| pages.get(p)?.get(i).copied());
                let Some(code) = held.filter(|c| Some(*c) == body["code"].as_i64()) else {
                    return WebReply::error(409, &format!("{name} changed since the page showed it; look at it again and try once more."));
                };
                let done = match body["do"].as_str() {
                    Some("remove") => self.mymenu_remove(code).ok_or_else(|| format!("Not in {name}")),
                    Some("up") => self.mymenu_move(p, i, -1).ok_or_else(|| "This item cannot move up: it is the first on its page.".to_string()),
                    Some("down") => self.mymenu_move(p, i, 1).ok_or_else(|| "This item cannot move down: it is the last on its page.".to_string()),
                    Some("set") => match body["to"].as_i64() {
                        Some(to) => self.mymenu_set(p, i, to),
                        None => return WebReply::error(400, "Choose the item to put in this place."),
                    },
                    _ => return WebReply::error(400, &format!("A place of {name} can only have its item taken out, moved up or down, or another item put in it.")),
                };
                match done {
                    Ok((actions, message)) => {
                        if let Some(why) = self.apply(actions) {
                            return WebReply::error(409, &why);
                        }
                        self.status = format!("{message}; {from}");
                        WebReply::json(json!({ "ok": true, "message": message }))
                    }
                    Err(why) => WebReply::error(400, &why),
                }
            }
            "switch_usb" | "camera_search" if busy => WebReply::error(409, "The editor is busy with the camera; wait for it to finish."),
            "switch_usb" => {
                // a read: it replaces file A, so unsaved edits are asked about first, as for "read"
                if let Some(no) = self.web_unsaved(discard) {
                    return no;
                }
                self.prefs.link = "usb".into();
                self.prefs.save();
                self.camera_report = None;
                let agreed = self.edits_hash();
                self.run_job(JobKind::Read, None, agreed, None);
                ok()
            }
            "camera_search" => {
                self.start_job(JobKind::Discover, None);
                cards(self)
            }
            // the camera cards (Connect to the camera), with what the state leaves out: the address, the cameras found
            // and known with their serial numbers and MAC addresses, the setup steps, the login note
            "camera_cards" => cards(self),
            // the camera link's own words in the report, in Expert mode only (they name the camera's address, serial
            // number and MAC address)
            "camera_report" => match &self.camera_report {
                _ if !self.prefs.expert => WebReply::error(409, "The camera link's own messages are shown in Expert mode, set in the desktop app."),
                Some(r) => WebReply::json(json!({ "probe": if r.probe.trim().is_empty() { "(nothing)" } else { r.probe.trim() } })),
                None => WebReply::error(409, "No camera report is open."),
            },
            "reload_schemas" => {
                self.reload_definitions();
                self.status = format!("{} {from}", self.definitions_loaded());
                WebReply::json(json!({ "ok": true, "n": self.defs.list.len() }))
            }
            "camera_link" => {
                let link = body["link"].as_str().unwrap_or("");
                if !matches!(link, "usb" | "network") {
                    return WebReply::error(400, "Choose usb or network.");
                }
                let ip = body["ip"].as_str().map(str::trim);
                if ip.is_some_and(|ip| ip.len() > 64 || !ip.chars().all(|c| c.is_ascii_alphanumeric() || ".:-_%".contains(c))) {
                    return WebReply::error(400, "That is not a network address: type it as the camera shows it, e.g. 192.168.1.50.");
                }
                // the page may go back to an address the editor has met a camera at, or the one set; a new one is typed
                // in the desktop app (or found with Search), so the page cannot send the camera's login to any address
                let met = |ip: &str| ip == self.prefs.camera_ip.trim() || self.prefs.cameras.iter().any(|k| k.ip.trim() == ip);
                if ip.is_some_and(|ip| !ip.is_empty() && !met(ip)) {
                    return WebReply::error(409, "The page can choose an address the editor has met a camera at. Search for the camera, or type a new address in the desktop app.");
                }
                if link != self.prefs.link {
                    self.connect_checks.clear();
                }
                self.prefs.link = link.into();
                if let Some(ip) = ip {
                    self.prefs.camera_ip = ip.to_string();
                    self.prefs.address_typed();
                }
                self.prefs.save();
                self.status = format!("Camera link: {} {from}", if link == "usb" { "USB" } else { "network" });
                cards(self)
            }
            "camera_use" => match index("index").and_then(|i| self.discovered.get(i)).cloned() {
                Some(d) => {
                    self.use_found_camera(&d);
                    cards(self)
                }
                None => WebReply::error(400, "No such camera in the search's list."),
            },
            "camera_name" => {
                let name: String = body["name"].as_str().unwrap_or("").chars().filter(|c| !c.is_control()).take(60).collect();
                if let Some(i) = index("known") {
                    let Some(k) = self.prefs.cameras.get_mut(i) else { return WebReply::error(400, "No such known camera.") };
                    k.name = name;
                } else if let Some(i) = index("found") {
                    let Some(d) = self.discovered.get(i).cloned() else { return WebReply::error(400, "No such camera in the search's list.") };
                    let k = known_index(&self.prefs.cameras, &d);
                    if k.is_none() && d.serial().is_empty() && norm_mac(&d.mac).is_empty() && !d.is_network() {
                        return WebReply::error(400, "This camera cannot be told apart yet: name it once the editor has connected to it.");
                    }
                    let i = k.unwrap_or_else(|| remember_camera(&mut self.prefs.cameras, &d.as_known(&local_stamp())));
                    self.prefs.cameras[i].name = name;
                } else {
                    return WebReply::error(400, "Name a known camera or a found one.");
                }
                // the name is kept in the preferences only: the page never writes the credentials file (the desktop app
                // copies names into it when a name field there is left)
                self.prefs.save();
                self.status = format!("Camera name saved {from}");
                cards(self)
            }
            // off the list only: its user name and password, and the fingerprint this computer trusts for it, stay
            // until it is forgotten in the desktop app
            "camera_forget" => match index("index").filter(|&i| i < self.prefs.cameras.len()) {
                Some(i) => {
                    let k = self.prefs.cameras.remove(i);
                    if !norm_mac(&k.mac).is_empty() && norm_mac(&self.prefs.camera_mac) == norm_mac(&k.mac) {
                        self.prefs.camera_mac.clear();
                    }
                    self.prefs.save();
                    self.status = format!("{} taken off the list {from}", if k.label().is_empty() { "The camera" } else { k.label() });
                    cards(self)
                }
                None => WebReply::error(400, "No such known camera."),
            },
            "camera_check" => {
                let n = self.setup_steps().0.len();
                let Some(i) = index("index").filter(|&i| i < n) else { return WebReply::error(400, "No such step.") };
                if self.connect_checks.len() < n {
                    self.connect_checks.resize(n, false);
                }
                self.connect_checks[i] = body["value"].as_bool().unwrap_or(false);
                cards(self)
            }
            "camera_steps" => {
                self.follow_steps_rule();
                self.steps_shown = body["open"].as_bool().unwrap_or(!self.steps_shown);
                cards(self)
            }
            _ => WebReply::error(404, "The editor has no such request."),
        }
    }

    /// Open a file the editor keeps or opened before, as the window's Backups and Recent do; over unsaved edits
    /// only when the page says to discard them (`web_unsaved`).
    fn web_open(&mut self, path: PathBuf, discard: bool) -> WebReply {
        if let Some(no) = self.web_unsaved(discard) {
            return no;
        }
        match self.open_now(path) {
            Ok(()) => WebReply::json(json!({ "ok": true })),
            Err(_) => WebReply::error(400, &self.page_status()),
        }
    }

    /// The status line as the page gets it: the window's may name a file's folder and the camera's address or MAC
    /// address; the page's names the open files by name, any other folder of this user's from "~", and no address.
    fn page_status(&self) -> String {
        // the page's own address is shown in the desktop app's Settings, never in a reply
        if self.status.starts_with(WEB_ON) {
            return WEB_ON_FOR_PAGE.to_string();
        }
        let mut s = self.status.clone();
        let mut known: Vec<&Path> = self.doc.iter().map(|d| d.path.as_path())
            .chain(self.compare.iter().chain(self.base.iter()).map(|(p, _)| p.as_path())).collect();
        known.sort_by_key(|p| std::cmp::Reverse(p.as_os_str().len()));
        for p in known {
            if let Some(name) = p.file_name().filter(|_| p.is_absolute()) {
                s = s.replace(&p.display().to_string(), &name.to_string_lossy());
            }
            if let Some(dir) = p.parent().filter(|d| d.is_absolute() && d.parent().is_some()) {
                s = s.replace(&dir.display().to_string(), &dir.file_name().unwrap_or_default().to_string_lossy());
            }
        }
        let home = home_folder();
        if !home.as_os_str().is_empty() {
            s = s.replace(&home.display().to_string(), "~");
        }
        without_addresses(&s)
    }

    /// A request that replaces file A while it has unsaved edits: refused (409) unless the page says to discard them,
    /// which it does only after asking the person (app.js `ask`).
    fn web_unsaved(&self, discard: bool) -> Option<WebReply> {
        let n = self.unsaved();
        let camera = if self.edits_on_camera() { ", written to the camera but not saved to a file," } else { "," };
        (n > 0 && !discard).then(|| WebReply::error(409, &format!(
            "The editor has unsaved edits ({n}){camera} and this would replace them. Download the file to keep them, or try again and choose to discard them.")))
    }

    /// `revision` as the page carries it (a JSON number would lose digits): the file the Write window checked. Not the
    /// state's "rev" (`web_rev`), which changes with whatever the page shows.
    fn write_rev(&self) -> String {
        self.revision().map(|r| format!("{r:016x}")).unwrap_or_default()
    }

    /// Export CSV: Edit mode's set with the page's search and Only edited, or (`compare`) the columns the page's
    /// Compare shows, its search and tab, only the rows that differ and the raw values as asked; named as the
    /// window names it.
    fn web_csv(&mut self, target: usize, q: &str, body: &Value, from: &str) -> WebReply {
        let compare = body["compare"].as_bool().unwrap_or(false);
        let cols: Vec<Col> = match body["cols"].as_array() {
            Some(a) if compare => match a.iter().map(|v| self.col_from_json(v)).collect::<Option<Vec<Col>>>() {
                Some(c) => c,
                None => return WebReply::error(400, "A column names a file that is not open or a set that is not shown."),
            },
            // the window's own columns, without the files no longer open
            _ => self.cols.iter().copied().filter(|c| self.set_for(c.src).is_some()).collect(),
        };
        if compare && cols.len() < 2 {
            return WebReply::error(400, "Show at least two columns to export a comparison.");
        }
        let (only_diff, raw) = (body["only_diff"].as_bool().unwrap_or(self.matrix_only_diff), self.prefs.expert && body["raw"].as_bool().unwrap_or(self.show_raw));
        let tab = body["tab"].as_str().filter(|t| compare && !t.is_empty());
        let only = !compare && body["only"].as_bool().unwrap_or(false);
        let (text, n) = self.csv_text(compare.then_some((cols.as_slice(), only_diff, raw)), target, q, tab, only);
        let stem = self.doc.as_ref().and_then(|d| d.path.file_stem()).map_or_else(|| "CAMSET".into(), |s| s.to_string_lossy().to_string());
        let name = if compare { format!("{stem}_compare.csv") } else { format!("{stem}_{}.csv", self.schema.camera.target_name(target).replace(' ', "_").to_lowercase()) };
        self.status = format!("Exported {n} rows as {name} {from}");
        WebReply { status: 200, content_type: "text/csv", body: text.into_bytes(), download: Some(safe_name(&name)), keep: false }
    }

    /// The editor's preferences the page shows in its Settings. The page changes only how values are shown
    /// (`WEB_DISPLAY_PREFS`); the rest are shown as set in the desktop app, named in "desktop": Expert mode and its
    /// two options, which open what can harm the camera, the backup before a save, the window's own and the web page's.
    fn web_prefs(&self) -> Value {
        let p = &self.prefs;
        json!({
            "expert": p.expert, "show_raw": p.show_raw, "show_record_ids": p.show_record_ids, "show_proof": p.show_proof,
            "flat_list": p.flat_list,
            "allow_unobserved": p.allow_unobserved, "allow_raw_edits": p.allow_raw_edits,
            "matrix_only_diff": p.matrix_only_diff, "all_memory_cols": p.all_memory_cols, "backup_on_save": p.backup_on_save,
            "reopen_last": p.reopen_last, "definitions_dir": shown_path(&self.defs.user_dir),
            "prefs_path": "the editor's settings folder",
            "theme": p.theme(), "light": p.light, "zoom": p.clean_zoom(), "density": p.density,
            "web_at_start": p.web_at_start, "web_local_only": p.web_local_only, "web_port": p.web_port.unwrap_or(DEFAULT_PORT),
            "page_sets": WEB_DISPLAY_PREFS,
            "desktop": ["expert", "allow_unobserved", "allow_raw_edits", "backup_on_save", "reopen_last", "definitions_dir", "probe_path",
                        "theme", "light", "zoom", "density", "web_at_start", "web_local_only", "web_port"],
        })
    }

    /// Change one of the switches of how values are shown (`WEB_DISPLAY_PREFS`) from the page's Settings, as the
    /// window's Settings does. Every other one is refused: it is set in the desktop app. What changed, in words.
    fn web_set_pref(&mut self, name: &str, value: &Value) -> Result<String, (u16, String)> {
        if !WEB_DISPLAY_PREFS.contains(&name) {
            return Err((400, "That is set in the desktop app.".into()));
        }
        let Some(v) = value.as_bool() else { return Err((400, "Send true or false.".into())) };
        let said = match name {
            "show_record_ids" => {
                self.prefs.show_record_ids = v;
                "Record IDs beside setting names"
            }
            "show_proof" => {
                self.prefs.show_proof = v;
                "Whether each setting was proved"
            }
            "show_raw" => {
                // kept for Expert mode, drawn only in it, as the window's switch is (`expert_off`)
                self.prefs.show_raw = v;
                self.show_raw = v && self.prefs.expert;
                "Raw numeric codes"
            }
            "flat_list" => {
                self.set_flat_list(v);
                "A group's settings as one flat list"
            }
            "matrix_only_diff" => {
                self.prefs.matrix_only_diff = v;
                self.matrix_only_diff = v;
                "Compare starts with only the differences"
            }
            "all_memory_cols" => {
                self.prefs.all_memory_cols = v;
                if self.doc.is_some() && self.cols.iter().all(|c| c.src == Src::A) {
                    self.cols = self.start_cols();
                }
                "A second shooting mode's memories in the default columns"
            }
            _ => return Err((400, "That is set in the desktop app.".into())),
        };
        self.prefs.save();
        Ok(format!("{said}: {}", if v { "on" } else { "off" }))
    }

    /// The hover texts of a row's detail lines, the same for every row, so they are sent once.
    fn web_row_hovers(&self) -> Value {
        json!({
            // the window's hover of a setting's help (`help_hover`): the camera's own, or the project's own words
            "help": self.help_hover(true, &self.schema.help_file_name()),
            "help_own": self.help_hover(false, ""),
            "modes": self.modes_hover(),
            "sets": self.memories_hover(),
            "live": "The memories don't keep it",
            "record": "How the meaning was established: SDK (a Camera Remote SDK property), Menu (stepped on the camera), Derived (from file comparisons), User",
            "record_map": "The record and its neighbours in file order",
        })
    }

    /// An option's hover text in the window's list: its help and whose words it is (the camera's own or Camset's,
    /// value by value, as the window's), and the window's warning when no proof on the camera established it.
    fn web_option_help(&self, s: &Setting, v: i64) -> Option<String> {
        let whose = |h: &str| format!("{h}\n\n{}", self.help_hover(s.option_help_from_file.contains(&v), &self.schema.help_file_name()));
        // a value the menus never offer, listed while the file holds it, says why, as the window's option does
        let never = s.never_offered(v).map(|n| format!("The camera's menus never offer this value: {}", n.why));
        let unseen = never.clone().unwrap_or_else(|| UNPROVED_HOVER.to_string());
        match (s.option_help(v), s.established(v) && never.is_none()) {
            (Some(h), true) => Some(whose(h)),
            (Some(h), false) => Some(format!("{}\n\n{unseen}", whose(h))),
            (None, true) => None,
            (None, false) => Some(unseen),
        }
    }

    /// The open file holds this camera's My Menu (`mymenu_pages`), so its items can be added and removed.
    fn web_has_mymenu(&self) -> bool {
        let Some(mm) = self.schema.camera.my_menu.as_ref().filter(|m| !m.records.is_empty()) else { return false };
        self.doc.as_ref().and_then(|d| d.edited.sections.first()).is_some_and(|sec| mm.records.iter().all(|&id| sec.get(id).is_some()))
    }

    /// The My Menu page as the window's (`mymenu_view`), always for the live settings (`target` names the set the page
    /// edits, for its note only): each page's places in order, an item by the camera's name for it, with the setting
    /// it opens (where to open it, and its value), the others it holds, whether the place was edited and what it held,
    /// and whether it can move up or down, and whether it has the item picker (an item's place, and the place a new
    /// item goes to: on a packed page its first empty one); every item a place can hold (`mymenu_items`), with the
    /// tab of the setting that carries it and where it is in My Menu, and what the picker says of the items it leaves
    /// out; then the settings of My Menu's own tab by group, as rows.
    fn web_mymenu(&self, target: usize) -> Value {
        let name = self.schema.camera.text.my_menu_name();
        let doc = self.doc.as_ref();
        let packed = self.schema.camera.my_menu.as_ref().is_some_and(|m| m.packed);
        let place = |p: usize, i: usize, x: &MyMenuPlace, first_empty: Option<usize>| {
            let opens = x.settings.first().map(|s| {
                let held = s.text.is_some() || doc.is_some_and(|d| d.value(0, s.slot()).is_some());
                json!({ "key": s.key, "name": s.name, "tab": s.tab, "group": self.shown_group_of(s), "open_group": self.shown_group_of(s), "open_tab": self.entry_of(s), "where": self.where_shown(s),
                    "value": if held { self.row_value_in(0, s) } else { "not held in this file".to_string() }, "held": held })
            });
            json!({ "code": x.code, "empty": x.empty, "name": x.name, "edited": x.edited, "was": x.edited.then_some(&x.was), "opens": opens,
                "more": x.settings.iter().skip(1).map(|s| format!("{} > {} > {}", s.tab, s.group, s.name)).collect::<Vec<_>>(),
                "up": self.mymenu_move(p, i, -1).is_some(), "down": self.mymenu_move(p, i, 1).is_some(),
                "pick": !x.empty || !packed || first_empty == Some(i) })
        };
        let pages = self.mymenu_places().map(|pages| pages.iter().enumerate().map(|(p, places)| {
            let first_empty = places.iter().position(|x| x.empty);
            json!({
                "name": format!("{name} {}", p + 1),
                "held": places.iter().filter(|x| !x.empty).count(),
                "places": places.iter().enumerate().map(|(i, x)| place(p, i, x, first_empty)).collect::<Vec<_>>(),
            })
        }).collect::<Vec<_>>());
        let at = |code: i64| self.mymenu_find(code).map(|(p, i)| json!({ "page": p + 1, "item": i + 1 }));
        let items: Vec<Value> = self.mymenu_items().into_iter().map(|x| json!({ "code": x.code, "name": x.name, "tab": x.tab, "in": at(x.code) })).collect();
        let groups: Vec<Value> = self.mymenu_groups().into_iter().map(|(g, rows)| json!({
            "name": g, "color": css_color(tab_color(&self.schema.camera, name)), "tab": name,
            "rows": rows.iter().map(|r| self.web_row(0, r)).collect::<Vec<_>>(),
        })).collect();
        json!({
            "name": name, "pages": pages, "groups": groups, "editable": self.editable(),
            "items": items, "excluded": self.mymenu_excluded_words(),
            "lead": self.mymenu_lead(false), "memory": self.mymenu_memory_note(target),
            "missing": self.mymenu_missing(),
        })
    }

    /// One family (Picture Profiles, Creative Looks) as the window's table (`pp_table`): a row per parameter, a
    /// column per profile; each cell is a row of the page (`rows`), named by its key.
    fn web_family(&self, target: usize, title: &str, pp: &[Setting]) -> Value {
        let mut params: Vec<&str> = Vec::new();
        for s in pp {
            if !params.contains(&s.name.as_str()) {
                params.push(&s.name);
            }
        }
        let n = pp.iter().filter_map(|s| s.index).filter(|i| i & camset::FIELD == 0).max().map_or(0, |m| m as usize + 1);
        // column titles from the group names, as the family says ("Picture Profile PP3" -> "PP3" with group_suffix)
        let profiles: Vec<String> = (0..n).map(|i| pp.iter().find(|s| s.index == Some(i as u16)).map(|s| self.family_column(pp, &s.group)).unwrap_or_default()).collect();
        let (mut rows, mut cells) = (Vec::new(), Vec::new());
        for name in &params {
            let line: Vec<Option<String>> = (0..n).map(|i| {
                let linked: Vec<Setting> = pp.iter().filter(|s| s.name == *name && s.index == Some(i as u16)).cloned().collect();
                let (id, key) = linked.first().map(|s| (s.id, s.key.clone()))?;
                let mut row = self.web_row(target, &linked);
                row["cell_title"] = json!(format!("{} {name}: record 0x{id:04x}[{i}]", profiles[i]));
                rows.push(row);
                Some(key)
            }).collect();
            cells.push(line);
        }
        let tab = pp.first().map_or("", |s| s.tab.as_str());
        json!({ "name": title, "family": true, "tab": tab, "color": css_color(tab_color(&self.schema.camera, tab)),
            "note": format!("{}Values the camera never produces are not offered.", self.family_note(pp)),
            "params": params, "profiles": profiles, "cells": cells, "rows": rows })
    }

    /// The Unmapped records page (`unmapped_view`): every record of the set no setting names, its shape and value,
    /// changeable as a number while Allow raw edits is on. `q` matches the record id, `only` keeps the edited ones.
    fn web_unmapped(&self, target: usize, q: &str, only: bool) -> Value {
        // a file of no sections (a damaged or hand-made one) has no rows
        let Some((section, orig)) = self.doc.as_ref().and_then(|d| d.edited.sections.get(target).zip(d.original.sections.get(target))) else {
            return json!({ "rows": [] });
        };
        let in_set = target != 0;
        let rows: Vec<Value> = section.records.iter()
            .filter(|r| self.schema.find(in_set, r.id).is_none())
            .filter_map(|r| {
                let hex = format!("0x{:04x}", r.id);
                let changed = orig.get(r.id).is_some_and(|o| o.value != r.value);
                ((q.is_empty() || hex.contains(q)) && (!only || changed)).then(|| json!({
                    "id": r.id, "hex": hex, "shape": format!("{}×{}", r.elem_size, r.count), "value": r.display_value(), "int": r.as_int(), "changed": changed,
                }))
            }).collect();
        json!({ "allow_raw_edits": self.allow_raw_edits, "editable": self.editable() && self.allow_raw_edits, "rows": rows })
    }

    /// The record map (`records_view`): every record of the set in file order with its byte offset, shape, the
    /// setting it belongs to and its value; a record longer than 8 bytes carries its bytes (all of them, or those
    /// in `open`) with the fields the definition knows in it.
    fn web_records(&self, target: usize, q: &str, only_unmapped: bool, only_edited: bool, open: Option<&[u16]>) -> Value {
        let Some(doc) = &self.doc else { return json!({ "rows": [] }) };
        let in_set = target != 0;
        // fields the definition knows inside array records (16-bit fields at byte offsets): id -> [(offset, name, index)]
        let mut fields: BTreeMap<u16, Vec<(u16, String, u16)>> = BTreeMap::new();
        for s in &self.schema.settings {
            if let Some(ix) = s.index.filter(|ix| ix & camset::FIELD != 0) {
                if (in_set && s.in_sets) || (!in_set && s.area == "global") {
                    fields.entry(s.id).or_default().push((ix & !camset::FIELD, s.name.clone(), ix));
                }
            }
        }
        // where each record starts, by the framing of the file's container block
        let offsets = doc.edited.record_offsets(target);
        // a file of no sections (a damaged or hand-made one) has no rows
        let (Some(section), Some(orig)) = (doc.edited.sections.get(target), doc.original.sections.get(target)) else { return json!({ "rows": [] }) };
        let mut rows = Vec::new();
        for (ri, r) in section.records.iter().enumerate() {
            let off = offsets.get(ri).copied().unwrap_or_default();
            let setting = self.schema.find(in_set, r.id);
            let edited = orig.get(r.id).is_some_and(|o| o.value != r.value);
            let value = match setting {
                Some(s) if s.text.is_some() => r.text().unwrap_or_default(),
                Some(s) if s.scalar => Self::describe(s, r.as_int()),
                Some(_) => r.display_value(),
                None => String::new(),
            };
            let hex = format!("0x{:04x}", r.id);
            if (only_unmapped && setting.is_some()) || (only_edited && !edited) {
                continue;
            }
            if !q.is_empty() && !hex.contains(q) && !setting.is_some_and(|s| s.name.to_lowercase().contains(q) || s.group.to_lowercase().contains(q)) && !value.to_lowercase().contains(q) {
                continue;
            }
            let big = r.value.len() > 8;
            let bytes = (big && open.is_none_or(|o| o.contains(&r.id))).then(|| {
                let mut dump = String::new();
                for (n, chunk) in r.value.chunks(16).enumerate() {
                    let hex: Vec<String> = chunk.iter().map(|b| format!("{b:02x}")).collect();
                    let asc: String = chunk.iter().map(|&b| if (32..127).contains(&b) { b as char } else { '.' }).collect();
                    dump += &format!("{:04x}  {:<47}  {}\n", n * 16, hex.join(" "), asc);
                }
                let mut known = Vec::new();
                if let Some(fs) = fields.get(&r.id) {
                    dump += "fields:\n";
                    let mut fs = fs.clone();
                    fs.sort();
                    for (off, name, ix) in fs {
                        let v = r.get(Some(ix)).map(|v| v.to_string()).unwrap_or_default();
                        dump += &format!("  @{off:<4} {name} = {v}\n");
                        known.push(json!([off, name, v]));
                    }
                }
                json!({ "dump": dump.trim_end(), "fields": known })
            });
            let raw = r.display_value();
            let short = if raw.chars().count() > 24 { format!("{}…", raw.chars().take(24).collect::<String>()) } else { raw.clone() };
            let setting = setting.map(|s| json!({ "key": s.key, "name": s.name, "tab": s.tab, "group": s.group, "open_group": self.shown_group_of(s), "open_tab": self.entry_of(s), "note": s.note_shown(self.prefs.expert),
                "title": match fields.get(&r.id) { Some(fs) if fs.len() > 1 => format!("{} known fields ({}, …)", fs.len(), s.name), _ => s.name.clone() } }));
            rows.push(json!({ "offset": format!("{off:06x}"), "id": r.id, "hex": hex, "shape": format!("{}×{}", r.elem_size, r.count), "big": big,
                "setting": setting, "value": value, "raw": short, "raw_full": raw, "edited": edited, "bytes": bytes }));
        }
        let name = self.schema.camera.target_name(target);
        json!({ "name": name, "title": format!("{name}: records in file order"), "rows": rows })
    }

    /// The Backups window's list (`list_backups`), newest first, and the two folders it comes from (home as "~").
    /// Each copy by its folder ("originals" or "camera") and its file name, which `open_backup` takes: no folder of
    /// this computer.
    fn web_backups(&self) -> Value {
        let list: Vec<Value> = Self::list_backups().iter().map(|b| json!({ "when": b.when, "kind": b.kind, "folder": b.folder,
            "name": b.path.file_name().unwrap_or_default().to_string_lossy() })).collect();
        json!({ "dirs": { "originals": shown_path(&Self::originals_dir()), "camera": shown_path(&Self::camera_dir()) }, "list": list })
    }

    /// The copy `open_backup` opens, out of the Backups list as it is now (`list`): only a copy it holds, which the page
    /// names by its folder ("originals" or "camera") and its file name, the copy's own within its folder. The list may
    /// have changed since the page was given it (a read, a write or a file opened adds copies at the top and moves the
    /// rest down, and the other folder may hold a copy of the same name): the copy named is opened wherever it is in
    /// the list now, or none. A page older than the editor names no folder and is asked to reload. Two names in one
    /// folder that read the same as text (a name that is not valid Unicode) are refused rather than either opened.
    fn listed_backup(list: Vec<Backup>, folder: Option<&str>, name: Option<&str>) -> Result<Backup, WebReply> {
        let not_kept = || WebReply::error(400, "That is not one of the copies the editor keeps.");
        let Some(name) = name else { return Err(not_kept()) };
        let Some(folder) = folder else {
            return Err(WebReply::error(400, "This page is older than the editor: reload the page, then open the copy again."));
        };
        let mut same = list.into_iter().filter(|b| b.folder == folder && b.path.file_name().is_some_and(|f| f.to_string_lossy() == name));
        match (same.next(), same.next()) {
            (Some(b), None) => Ok(b),
            (None, _) => Err(not_kept()),
            (Some(_), Some(_)) => Err(WebReply::error(409, "Two copies in that folder have names the page cannot tell apart: open the copy from Backups in the desktop app.")),
        }
    }

    /// The Edit history window: every record each edit of the session changed, with its value before and after
    /// (snapshot i is the file before edit i; the file after it is snapshot i+1, or the file as it is now).
    fn web_history(&self) -> Value {
        let Some(doc) = &self.doc else { return json!({ "steps": [] }) };
        let mut steps = Vec::new();
        for (i, before) in self.undo.iter().enumerate() {
            let after: &CamSet = self.undo.get(i + 1).unwrap_or(&doc.edited);
            for (si, id, name) in self.record_diff(before, after) {
                let s = self.schema.find(si != 0, id);
                let fmt = |c: &CamSet| c.sections.get(si).and_then(|sec| sec.get(id)).map(|r| {
                    let raw = r.display_value();
                    s.and_then(|s| raw.parse::<i64>().ok().and_then(|v| s.label_for(v).map(|l| format!("{l} [{v}]")))).unwrap_or(raw)
                }).unwrap_or_default();
                let place = if si == 0 { String::new() } else { format!("{} · ", self.schema.camera.target_name(si)) };
                steps.push(json!({ "step": i, "section": si, "id": id, "name": format!("{place}{name}"), "before": fmt(before), "after": fmt(after),
                    "revert": self.editable() }));
            }
        }
        json!({ "steps": steps })
    }

    /// What the state carries of the camera for the top bar's 📷 button and the welcome page, every few seconds: the
    /// link as a word, whether the editor is busy with the camera, and the button's text, colour and hover text,
    /// naming the camera by the person's name for it, never by its address.
    fn web_camera_button(&self) -> Value {
        let p = &self.prefs;
        let (state, up) = match &self.link_state {
            LinkState::Up { at } => (format!("last read {}", when_words(at)), Some(true)),
            LinkState::Down { .. } => ("disconnected".to_string(), Some(false)),
            LinkState::Untried => ("not checked".to_string(), None),
        };
        // the window's words (`camera_button_text`), without the address
        let text = self.camera_button_text(false);
        let which = p.current_camera().and_then(|i| camera_words(&p.cameras[i].name, Some(&self.defs.model_words(&p.cameras[i].model)))).map(|w| format!("{w}\n")).unwrap_or_default();
        json!({
            "link": p.link, "busy": self.camera_job.is_some(),
            "button": { "text": text, "up": up, "tip": format!("{which}{text} · {state}\nClick to open Connect to the camera") },
        })
    }

    /// The camera cards of Connect to the camera and Settings > Camera link (`camera_cards`, and the answer of every
    /// camera request): the link, the last search and what it found, the setup steps and their ticks, the known
    /// cameras, the address and whether a login is saved for the camera, the helper's file name; and the top bar's
    /// 📷 button.
    fn web_camera(&self) -> Value {
        let (p, expert) = (&self.prefs, self.prefs.expert);
        let cams = &p.cameras;
        let found: Vec<Value> = self.discovered.iter().enumerate().map(|(i, d)| {
            let k = known_index(cams, d);
            let (link, second) = d.link_lines();
            let serial = if d.serial().is_empty() { k.map(|i| cams[i].serial.clone()).unwrap_or_default() } else { d.serial().to_string() };
            let mac = Some(norm_mac(&d.mac)).filter(|m| !m.is_empty()).or_else(|| k.map(|i| norm_mac(&cams[i].mac))).unwrap_or_default();
            json!({ "index": i, "model": d.model, "own_name": d.name.trim(), "link": link, "link_note": second, "link_hover": d.link_hover(),
                "name": k.map(|i| cams[i].name.clone()).unwrap_or_default(),
                "can_name": k.is_some() || !d.serial().is_empty() || !norm_mac(&d.mac).is_empty() || d.is_network(),
                "serial": serial, "serial_why": serial_why(d, expert), "mac": mac,
                "mac_why": if d.by_address() { "This computer's network table held no MAC address for the camera's address. Learned when the editor first connects to it" } else { LEARNED_ON_CONNECT } })
        }).collect();
        let known: Vec<Value> = cams.iter().enumerate().map(|(i, k)| json!({ "index": i, "name": k.name, "model": k.model, "serial": k.serial,
            "mac": k.mac, "link": k.link_text(), "last_seen": when_words(&k.last_seen) })).collect();
        let named = self.found_name();
        let (steps, note) = self.setup_steps();
        let checks: Vec<bool> = (0..steps.len()).map(|i| self.connect_checks.get(i).copied().unwrap_or(false)).collect();
        // the steps follow their rule when it changes (`follow_steps_rule`), else stay as they were left
        let rule = steps_open(cams.len(), self.discovered.len());
        let helper = match (&p.probe_path, self.probe_path()) {
            (Some(chosen), _) => file_name_of(chosen),
            (None, Some(f)) => format!("(found) {}", file_name_of(&f.display().to_string())),
            (None, None) => "(not found)".into(),
        };
        // whether a login is saved for the camera the next action goes to: never the file's place, never the pair
        let (own, default) = credentials_state(&Self::read_credentials().unwrap_or_default(), &p.camera_mac);
        let login_note = match (own, default) {
            (true, _) => "A user name and password are saved on the editor's computer for this camera.",
            (false, true) => "This camera has no user name and password of its own on the editor's computer; the default pair saved there is used.",
            (false, false) => "No user name and password are saved yet. They are entered in the desktop app, on the computer that runs the editor.",
        };
        // the top bar's camera button, its colour and its hover text
        let (state, said, up) = match &self.link_state {
            LinkState::Up { at } => (format!("last read {}", when_words(at)), format!("The camera answered at {}", self.stamp_words(at)), Some(true)),
            LinkState::Down { why } => ("disconnected".to_string(), format!("Camera action failed: {why}"), Some(false)),
            LinkState::Untried => ("not checked".to_string(), "No camera action yet this session".to_string(), None),
        };
        let text = self.camera_button_text(true);
        let which = p.current_camera().and_then(|i| camera_words(&cams[i].name, Some(&self.defs.model_words(&cams[i].model)))).map(|w| format!("{w}\n")).unwrap_or_default();
        json!({
            "link": p.link, "ip": p.camera_ip, "address_hint": self.schema.camera.text.address_hint.as_deref().filter(|h| !h.is_empty()),
            "busy": self.camera_job.is_some(), "msg": self.discover_msg, "search_tip": search_tip(),
            "detail": if expert && self.discover_detail != self.discover_text { self.discover_detail.as_str() } else { "" },
            "detail_note": (!expert && !self.discover_detail.is_empty()).then_some(EXPERT_LINK_NOTE),
            "text": if expert { self.discover_text.as_str() } else { "" },
            "found": found,
            "found_line": if named.is_empty() { "Camera found: the setup is complete.".to_string() } else { format!("{named} found: the setup is complete.") },
            "known": known, "learned": LEARNED_ON_CONNECT, "steps": steps, "steps_note": note.filter(|n| !n.is_empty()), "checks": checks,
            "steps_open": if rule != self.steps_rule { rule } else { self.steps_shown },
            "helper": helper,
            "credentials_note": (p.link == "network").then_some(login_note),
            "login_saved": own || default,
            "button": { "text": text, "up": up, "tip": format!("{which}{text} · {state}\n{said}\nClick to open Connect to the camera") },
        })
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    /// What the page asks the editor (`api` in app.js), answered as a request from the page is,
    /// whatever the answer's status: for a request that should be refused.
    pub(crate) fn answer(app: &mut App, name: &str, body: Value) -> WebReply {
        let (reply, _rx) = mpsc::channel();
        let r = WebRequest { name: name.into(), body: body.to_string().into_bytes(), file_name: String::new(), discard: false, peer: "test".into(), reply };
        app.web_answer(&r)
    }

    /// What the page asks the editor, answered as a request from the page is; the answer must be a 200.
    fn ask(app: &mut App, name: &str, body: Value) -> Value {
        let a = answer(app, name, body);
        assert_eq!(a.status, 200, "{name}: {}", String::from_utf8_lossy(&a.body));
        serde_json::from_slice(&a.body).unwrap()
    }

    /// About's Changes on the page: the changelog built in, as the window's Changes reads it, with or without a file open.
    #[test]
    fn the_page_reads_the_changelog() {
        let mut app = App::new(vec![], Prefs::default());
        let blocks = |v: &Value| serde_json::from_value::<Vec<(u8, String)>>(v["blocks"].clone()).unwrap();
        assert_eq!(blocks(&ask(&mut app, "changelog", json!({}))), changelog_blocks(CHANGELOG));
        app.open_sample_now();
        assert_eq!(blocks(&ask(&mut app, "changelog", json!({}))), changelog_blocks(CHANGELOG));
    }

    /// A file the page sends up (`api(name, {}, file)` in app.js): its bytes as the body, its name as
    /// the page sends it (percent-encoded); the answer must be a 200.
    fn ask_upload(app: &mut App, name: &str, bytes: &[u8], file_name: &str) -> Value {
        let (reply, _rx) = mpsc::channel();
        let r = WebRequest { name: name.into(), body: bytes.to_vec(), file_name: file_name.into(), discard: false, peer: "test".into(), reply };
        let a = app.web_answer(&r);
        assert_eq!(a.status, 200, "{name}: {}", String::from_utf8_lossy(&a.body));
        serde_json::from_slice(&a.body).unwrap()
    }

    /// A file sent up from the page is kept in the editor's own folder and opened there; a request
    /// that needs a file is refused until one is open, and one the editor does not have is refused.
    #[test]
    fn a_file_sent_up_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        assert_eq!(answer(&mut app, "tab", json!({ "target": 0 })).status, 409);
        assert_eq!(ask_upload(&mut app, "open", include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT"), "My%20CAMSET01.DAT")["ok"], true);
        let path = app.doc.as_ref().map(|d| d.path.clone()).unwrap();
        assert!(path.starts_with(App::camera_dir().join("web")), "kept at {}", path.display());
        // W-17: under its own name, in a folder named by the time it came, so a download is named as the file was
        assert_eq!(path.file_name().unwrap(), "My_CAMSET01.DAT", "kept as {}", path.display());
        assert_eq!(path.parent().and_then(Path::parent), Some(App::camera_dir().join("web").as_path()));
        assert_eq!(ask(&mut app, "state", json!({}))["file"]["name"], "My_CAMSET01.DAT");
        let offered = app.suggested_name(app.doc.as_ref().unwrap());
        assert!(offered.to_uppercase().starts_with("MY_") && !offered.contains("2026"), "no time stamp in the name offered: {offered}");
        assert_eq!(answer(&mut app, "no_such_request", json!({})).status, 404);
    }

    /// What the page's Compare and Memories requests build on: a column named as the page names it,
    /// checked against the files open and the sets shown, and the compare matrix's rows for a search
    /// and a tab of the page's own, as the window's search and tab filter give them.
    #[test]
    fn columns_and_rows_for_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert_eq!(app.col_from_json(&json!(["a", 0])), Some(Col::a(0)));
        for bad in [json!(["b", 0]), json!(["base", 0]), json!(["a", 99]), json!(["a", -1]), json!(["c", 0]), json!(["a"]), json!("a"), Value::Null] {
            assert_eq!(app.col_from_json(&bad), None, "{bad}");
        }
        let sample = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.compare = Some((PathBuf::from("B.DAT"), sample));
        assert_eq!(app.col_from_json(&json!(["b", 0])), Some(Col::b(0)));
        if let Some(&m) = app.dial_sets().first() {
            assert_eq!(app.col_from_json(&json!(["b", m])), Some(Col::b(m)));
        }
        let names = |rows: Vec<(String, String, Vec<Setting>)>| rows.into_iter().map(|(t, g, l)| (t, g, l.iter().map(|s| s.key.clone()).collect::<Vec<_>>())).collect::<Vec<_>>();
        let rows = app.matrix_rows_for("", None);
        let (tab, word) = (rows[0].0.clone(), rows[0].2[0].name.split(' ').next().unwrap().to_uppercase());
        let all = names(rows);
        assert_eq!(names(app.matrix_rows()), all, "the window's rows with no search and every tab");
        (app.search, app.compare_tab) = (word.clone(), Some(tab.clone()));
        let some = names(app.matrix_rows_for(&word, Some(&tab)));
        assert!(!some.is_empty() && some.len() < all.len());
        assert!(some.iter().all(|(t, _, _)| *t == tab));
        assert_eq!(names(app.matrix_rows()), some, "the window's rows for its search and tab");
    }

    /// A file the page sends up, answered whatever the answer's status: for an upload that should be refused.
    fn upload(app: &mut App, name: &str, bytes: &[u8], file_name: &str) -> WebReply {
        let (reply, _rx) = mpsc::channel();
        let r = WebRequest { name: name.into(), body: bytes.to_vec(), file_name: file_name.into(), discard: false, peer: "test".into(), reply };
        app.web_answer(&r)
    }

    /// The built-in sample with one live value changed, as a file B: a setting kept in the
    /// memories too, that heads a row of the compare and offers at least three values; the bytes,
    /// the setting and its value in them.
    fn changed_sample(app: &App) -> (Vec<u8>, Setting, i64) {
        let (s, other) = app.matrix_rows_for("", None).into_iter().map(|r| r.2[0].clone())
            .filter(|s| s.in_sets && s.scalar && s.text.is_none() && s.range.is_none() && s.offered(false).len() >= 3)
            .filter(|s| app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none() && s.id != 0x018c && s.id != 0x0180)
            .find_map(|s| {
                let cur = app.col_value(Col::a(0), &s)?;
                let other = s.offered(false).into_iter().map(|(v, _)| v).find(|v| *v != cur)?;
                Some((s, other))
            })
            .expect("a setting of the sample with three values");
        let mut c = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        c.sections[0].get_mut(s.id).unwrap().put(s.index, other).unwrap();
        (c.to_bytes(), s, other)
    }

    /// A file saved with the camera on PAL: the page's badge says it after the firmware, checked, as the window's
    /// does; with a file B saved on NTSC, the compare state carries the window's line saying which is which.
    #[test]
    fn a_pal_file_says_so_on_the_page() {
        use crate::write::safety_tests::with_video_system;
        let mut app = App::new(vec![], Prefs::default());
        ask_upload(&mut app, "open", &with_video_system(1).to_bytes(), "wsa_pal_A.DAT");
        let s = ask(&mut app, "state", json!({}));
        assert_eq!((s["file"]["badge"]["kind"].as_str(), s["file"]["badge"]["text"].as_str()), (Some("ok"), Some("✔ firmware 4.00 · PAL")));
        assert!(s["file"]["badge"]["tip"].as_str().unwrap().contains("Saved with the camera set to PAL."), "{}", s["file"]["badge"]);
        assert!(s["file"]["editable"].as_bool().unwrap());
        assert!(s["compare"]["video_note"].is_null());
        ask_upload(&mut app, "open_b", &with_video_system(0).to_bytes(), "wsa_ntsc_B.DAT");
        let t = ask(&mut app, "state", json!({}));
        assert_eq!(t["compare"]["b"]["badge"]["text"].as_str(), Some("✔ firmware 4.00 · NTSC"));
        assert_eq!(t["compare"]["video_note"].as_str(), app.video_systems_note().as_deref());
        assert!(t["compare"]["video_note"].as_str().unwrap().contains("(A on PAL, B on NTSC)"));
    }

    /// File B and the base come up from the page and open as the window's B: Open… and Base:
    /// Open… open them: B needs a file A, the base needs B, and the state says which are open.
    #[test]
    fn file_b_and_base_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        let sample: &[u8] = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        assert_eq!(upload(&mut app, "open_b", sample, "wsa_first_B.DAT").status, 409, "no file A yet");
        ask_upload(&mut app, "open", sample, "wsa_first_A.DAT");
        let s = ask(&mut app, "state", json!({}));
        assert!(s["compare"]["b"].is_null() && s["compare"]["base"].is_null());
        assert_eq!(upload(&mut app, "open_base", sample, "wsa_first_Base.DAT").status, 409, "the base before file B");
        assert_eq!(upload(&mut app, "open_b", b"not a settings file", "wsa_bad.DAT").status, 400);
        let (b, _, _) = changed_sample(&app);
        ask_upload(&mut app, "open_b", &b, "wsa_first_B.DAT");
        assert!(app.compare.is_some());
        assert!(app.mode == Mode::Compare, "the window compares too, as when it opens file B");
        let t = ask(&mut app, "state", json!({}));
        assert_ne!(t["rev"], s["rev"], "the page would not notice file B");
        let path = app.compare.as_ref().map(|(p, _)| p.clone()).unwrap();
        assert!(path.starts_with(App::camera_dir().join("web")), "kept at {}", path.display());
        assert_eq!(t["compare"]["b"]["name"], "wsa_first_B.DAT");
        assert!(path.parent().unwrap().file_name().unwrap().to_string_lossy().contains("_B"), "{}", path.display());
        assert_eq!(t["compare"]["b"]["badge"]["kind"], "ok");
        assert_eq!(t["compare"]["cols"], json!([["a", 0], ["b", 0]]), "this file against the other, as the window opens B");
        assert_eq!(t["compare"]["only_diff_default"], app.prefs.matrix_only_diff);
        ask_upload(&mut app, "open_base", sample, "wsa_first_Base.DAT");
        let u = ask(&mut app, "state", json!({}));
        assert_ne!(u["rev"], t["rev"]);
        assert_eq!(u["compare"]["base"]["name"], "wsa_first_Base.DAT");
        assert_eq!(u["compare"]["cols"][0], json!(["base", 0]), "the base is the baseline");
        ask(&mut app, "close_base", json!({}));
        let v = ask(&mut app, "state", json!({}));
        assert!(v["compare"]["base"].is_null());
        assert_eq!(v["compare"]["cols"], json!([["a", 0], ["b", 0]]));
        assert_eq!(answer(&mut app, "close_base", json!({})).status, 409);
    }

    /// The compare page's rows are the window's: the rows that differ, the baseline's counts, the
    /// arrows into file A, and the search and tab filters; columns of files not open are refused.
    #[test]
    fn compare_rows_as_the_window_has_them() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (b, s, other) = changed_sample(&app);
        ask_upload(&mut app, "open_b", &b, "wsa_rows_B.DAT");
        let cols = json!([["a", 0], ["b", 0]]);
        let j = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true }));
        assert_eq!((j["cols"][0]["name"].as_str(), j["cols"][1]["name"].as_str()), (Some("A · Live"), Some("B · Live")));
        assert_eq!((&j["cols"][0]["editable"], &j["cols"][1]["editable"]), (&json!(true), &json!(false)));
        assert!(j["three"].is_null(), "no base, no three-way");
        let rows = j["rows"].as_array().unwrap();
        let record = format!("0x{:04x}", s.id);
        assert!(!rows.is_empty());
        for r in rows {
            assert_eq!(r["record"], record.as_str(), "{} differs, but only {} was changed", r["name"], s.name);
            assert_eq!((&r["differs"], &r["cells"][0]["differs"], &r["cells"][1]["differs"]), (&json!(true), &json!(false), &json!(true)));
        }
        let row = rows.iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!(row["cells"][1]["value"], other);
        assert_eq!(row["cells"][1]["text"], App::describe(&s, Some(other)).as_str());
        assert_eq!(row["arrows"], json!([[true, false]]), "the arrow points into A only");
        assert_eq!(row["mark"], "differs");
        assert_eq!((j["counts"][1].as_u64(), j["diffs"].as_u64()), (Some(rows.len() as u64), Some(rows.len() as u64)));
        let raw = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true, "raw": true }));
        let r = raw["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!(r["cells"][1]["text"], App::describe(&s, Some(other)).as_str(), "the stored number outside Expert mode");
        app.prefs.expert = true;
        let raw = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true, "raw": true }));
        let r = raw["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!(r["cells"][1]["text"], format!("{}  [{other}]", App::describe(&s, Some(other))).as_str());
        // every row, then the window's tab filter and search
        let all = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": false }));
        assert_eq!(all["total"], app.matrix_rows_for("", None).len());
        assert_eq!(all["shown"], all["total"]);
        let t = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": false, "tab": s.tab }));
        assert_eq!(t["total"], app.matrix_rows_for("", Some(&s.tab)).len());
        assert!(t["rows"].as_array().unwrap().iter().all(|r| r["tab"] == s.tab.as_str()));
        let word = s.name.split(' ').next().unwrap().to_uppercase();
        let q = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": false, "q": word }));
        assert_eq!(q["total"], app.matrix_rows_for(&word, None).len());
        assert!(q["rows"].as_array().unwrap().iter().any(|r| r["key"] == s.key.as_str()));
        // the window's own columns when the page names none; a file not open, a set not shown
        assert_eq!(ask(&mut app, "compare", json!({}))["cols"].as_array().unwrap().len(), app.cols.len());
        for bad in [json!([["a", 0], ["base", 0]]), json!([["a", 0], ["b", 99]]), json!("a")] {
            assert_eq!(answer(&mut app, "compare", json!({ "cols": bad })).status, 400, "{bad}");
        }
        // one column: the window asks for two, and shows no rows
        assert!(ask(&mut app, "compare", json!({ "cols": [["a", 0]] }))["rows"].as_array().unwrap().is_empty());
    }

    /// The page's compare changes a value of file A in place, as the window's does: the cells of file A that can
    /// change say so (`editable`), never file B's; the picker's row is the page's row in the cell's set
    /// (`compare_cell`); "set" from the compare (with the cell's column) marks the edit, sets the linked records, is
    /// undone and reverted, and is refused for a column of file B. The row changed stays shown while asked (`keep`).
    #[test]
    fn the_page_changes_a_value_of_file_a_in_compare() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (b, s, other) = changed_sample(&app);
        ask_upload(&mut app, "open_b", &b, "wsa_pick_B.DAT");
        let cols = json!([["a", 0], ["b", 0]]);
        let row_of = |j: &Value, key: &str| j["rows"].as_array().unwrap().iter().find(|r| r["key"] == key).cloned();
        let j = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true }));
        let r = row_of(&j, &s.key).unwrap();
        assert_eq!((&r["cells"][0]["editable"], &r["cells"][1]["editable"]), (&json!(true), &Value::Null), "A takes a value, B never");
        assert!(j["rows"].as_array().unwrap().iter().all(|r| r["cells"][1]["editable"].is_null()));
        // the picker: the setting as the page's rows draw it, in the cell's set
        let pick = ask(&mut app, "compare_cell", json!({ "target": 0, "key": s.key }));
        let linked = app.web_linked(0, &s.key).unwrap();
        assert_eq!(pick["row"], app.web_row(0, &linked));
        assert_eq!((pick["row"]["kind"].as_str(), &pick["row"]["editable"]), (Some("choice"), &json!(true)));
        assert_eq!(answer(&mut app, "compare_cell", json!({ "target": 99, "key": s.key })).status, 400);
        assert_eq!(answer(&mut app, "compare_cell", json!({ "target": 0, "key": "no such key" })).status, 404);
        // a column of file B never takes the value, nor a column that is not the set named
        let was = app.doc.as_ref().unwrap().value(0, s.slot());
        for (col, status) in [(json!(["b", 0]), 409), (json!(["a", 99]), 400)] {
            let no = answer(&mut app, "set", json!({ "target": 0, "key": s.key, "value": other, "col": col }));
            assert_eq!(no.status, status, "{col}");
            assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), was, "{col}");
        }
        // B's value into A, from the compare: an edit of every linked record, as from Edit
        let set = ask(&mut app, "set", json!({ "target": 0, "key": s.key, "value": other, "col": ["a", 0] }));
        assert_eq!(set["row"]["changed"], true);
        for a in App::set_linked(0, &linked, other) {
            if let Action::Set(si, slot, v) = a { assert_eq!(app.doc.as_ref().unwrap().value(si, slot), Some(v)); }
        }
        assert_eq!(app.col_value(Col::b(0), &s), Some(other), "file B unchanged");
        // the row no longer differs: kept while the page asks, gone when it does not
        let kept = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true, "keep": s.key }));
        let r = row_of(&kept, &s.key).expect("kept shown");
        assert_eq!((&r["cells"][0]["edited"], &r["cells"][0]["was"], &r["mark"]), (&json!(true), &json!(App::describe(&s, was)), &json!("edited")));
        assert!(row_of(&ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true })), &s.key).is_none());
        // undone, redone, then reverted as from Edit
        ask(&mut app, "undo", json!({}));
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), was);
        ask(&mut app, "redo", json!({}));
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), Some(other));
        ask(&mut app, "revert", json!({ "target": 0, "key": s.key }));
        assert!(linked.iter().all(|l| { let d = app.doc.as_ref().unwrap(); d.value(0, l.slot()) == d.original_value(0, l.slot()) }));
        // the script: a cell of A that can change opens the picker, and its change carries the cell's column
        assert!(SCRIPT.contains("c.editable ? \" take\"") && SCRIPT.contains("api(\"compare_cell\"") && SCRIPT.contains("col: r.col"));
    }

    /// A number a setting has no name for says why wherever the page shows it (a compare cell, a row of a tab, the
    /// Memories page), as the window's hover does; the compare's setting names carry the window's hover, the record
    /// number in Expert mode only.
    #[test]
    fn the_page_says_why_a_number_has_no_name() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (b, s, _) = changed_sample(&app);
        let v = (0..100).find(|v| s.label_for(*v).is_none()).unwrap();
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), Some(v));
        ask_upload(&mut app, "open_b", &b, "wsa_unnamed_B.DAT");
        let j = ask(&mut app, "compare", json!({ "cols": [["a", 0], ["b", 0]], "only_diff": false }));
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap().clone();
        assert_eq!(row["cells"][0]["text"], format!("{v} (no name yet)").as_str());
        assert_eq!(row["cells"][0]["why"], format!("The camera holds {v} here, a value Camset has no name for yet.").as_str());
        assert!(row["cells"][1]["why"].is_null(), "B's value has a name");
        assert_eq!(row["where"], app.where_kept(&s).as_str());
        assert!(!row["where"].as_str().unwrap().contains("0x"));
        let rows = |j: &Value| -> Vec<Value> { j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).collect() };
        let t = ask(&mut app, "tab", json!({ "target": 0, "tab": s.tab }));
        let r = rows(&t).into_iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!(r["unnamed"], app.unnamed_why(&s, Some(v)).unwrap().as_str());
        let m = ask(&mut app, "memories", json!({ "only_diff": false }));
        if let Some(r) = rows(&m).into_iter().find(|r| r["key"] == s.key.as_str()) {
            assert!(r["live"]["why"].as_str().unwrap().contains("a value Camset has no name for yet"));
        }
        app.prefs.expert = true;
        let j = ask(&mut app, "compare", json!({ "cols": [["a", 0], ["b", 0]], "only_diff": false }));
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap().clone();
        assert!(row["where"].as_str().unwrap().contains(&format!("record 0x{:04x}", s.id)));
    }

    /// A copy and a merge from the page are edits of file A as the window's are (one undo step
    /// each), never of B; swapping A and B waits until A's edits are undone.
    #[test]
    fn copy_and_merge() {
        let mut app = App::new(vec![], Prefs::default());
        let sample: &[u8] = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        ask_upload(&mut app, "open", sample, "wsa_copy_A.DAT");
        let (b, s, other) = changed_sample(&app);
        let was = app.col_value(Col::a(0), &s);
        ask_upload(&mut app, "open_b", &b, "wsa_copy_B.DAT");
        let cols = json!([["a", 0], ["b", 0]]);
        assert_eq!(answer(&mut app, "copy", json!({ "from": ["a", 0], "to": ["b", 0], "key": s.key })).status, 400, "B is never changed");
        assert_eq!(answer(&mut app, "copy", json!({ "from": ["b", 0], "to": ["a", 0], "key": "no_such_setting" })).status, 404);
        assert_eq!(ask(&mut app, "copy", json!({ "from": ["b", 0], "to": ["a", 0], "key": s.key }))["n"], 1);
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        assert_eq!(app.undo.len(), 1);
        assert!(ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true }))["rows"].as_array().unwrap().is_empty());
        assert_eq!(answer(&mut app, "swap_ab", json!({})).status, 409, "A has an edit");
        ask(&mut app, "undo", json!({}));
        assert_eq!(app.col_value(Col::a(0), &s), was);
        // a cell's "All of A": into every column of file A shown, as one edit
        if let Some(&m) = app.dial_sets().first() {
            let j = ask(&mut app, "copy", json!({ "from": ["b", 0], "to": [["a", 0], ["a", m]], "key": s.key }));
            assert!(j["n"].as_u64().unwrap() >= 1);
            assert_eq!((app.col_value(Col::a(0), &s), app.col_value(Col::a(m), &s)), (Some(other), Some(other)));
            assert_eq!(app.undo.len(), 1, "All of A is one edit");
            ask(&mut app, "undo", json!({}));
            assert_eq!(answer(&mut app, "copy", json!({ "from": ["b", 0], "to": [["a", 0], ["b", 0]], "key": s.key })).status, 400);
        }
        // "Copy all shown rows" from B into A: the rows that differ
        let keys: Vec<Value> = ask(&mut app, "compare", json!({ "cols": cols, "only_diff": true }))["rows"].as_array().unwrap().iter().map(|r| r["key"].clone()).collect();
        assert_eq!(ask(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": keys }))["n"], keys.len());
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        ask(&mut app, "undo", json!({}));
        // three-way: base and A are the sample, B changed one setting; merged into A as one edit
        ask_upload(&mut app, "open_base", sample, "wsa_copy_Base.DAT");
        let three = json!([["base", 0], ["a", 0], ["b", 0]]);
        let j = ask(&mut app, "compare", json!({ "cols": three, "only_diff": false }));
        let n = j["three"]["b"].as_u64().unwrap();
        assert!(n >= 1);
        assert_eq!((&j["three"]["a"], &j["three"]["both"], &j["three"]["conflict"]), (&json!(0), &json!(0), &json!(0)));
        assert_eq!(j["three"]["cols"], three);
        assert_eq!(j["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap()["three"], "b");
        assert_eq!(ask(&mut app, "compare", json!({ "cols": three, "only_diff": false, "three": "b" }))["shown"], n);
        let merge = |kind: &str| json!({ "base": ["base", 0], "a": ["a", 0], "b": ["b", 0], "kind": kind });
        assert_eq!(answer(&mut app, "merge", json!({ "base": ["a", 0], "a": ["a", 0], "b": ["b", 0], "kind": "b_into_a" })).status, 400);
        assert_eq!(answer(&mut app, "merge", merge("everything")).status, 400);
        assert_eq!(ask(&mut app, "merge", merge("b_into_a"))["n"], n);
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        assert_eq!(app.undo.len(), 1, "a merge is one edit");
        let j = ask(&mut app, "compare", json!({ "cols": three }));
        assert_eq!((&j["three"]["b"], j["three"]["both"].as_u64()), (&json!(0), Some(n)), "A and B now made the same change");
        ask(&mut app, "undo", json!({}));
        // a conflict: A takes a third value; then B's value, or the base's
        let third = s.offered(false).into_iter().map(|(v, _)| v).find(|v| Some(*v) != was && *v != other).unwrap();
        ask(&mut app, "set", json!({ "target": 0, "key": s.key, "value": third }));
        let j = ask(&mut app, "compare", json!({ "cols": three, "three": "conflicts" }));
        assert!(j["three"]["conflict"].as_u64().unwrap() >= 1);
        let row = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!((&row["three"], &row["mark"], &row["cells"][1]["edited"]), (&json!("conflict"), &json!("edited"), &json!(true)));
        ask(&mut app, "merge", merge("conflicts_b"));
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        ask(&mut app, "merge", merge("conflicts_base"));
        assert_eq!(app.col_value(Col::a(0), &s), Some(other), "no conflict left");
        ask(&mut app, "undo", json!({}));
        ask(&mut app, "merge", merge("conflicts_base"));
        assert_eq!(app.col_value(Col::a(0), &s), was);
        ask(&mut app, "undo", json!({}));
        ask(&mut app, "undo", json!({}));
        // swap: A and B change places, both opened again from the editor's folder
        assert!(app.doc.as_ref().unwrap().changes().is_empty());
        let st = ask(&mut app, "state", json!({}));
        let (a_name, b_name) = (st["file"]["name"].clone(), st["compare"]["b"]["name"].clone());
        ask(&mut app, "swap_ab", json!({}));
        let st = ask(&mut app, "state", json!({}));
        assert_eq!((&st["file"]["name"], &st["compare"]["b"]["name"]), (&b_name, &a_name));
        assert_eq!(app.col_value(Col::a(0), &s), Some(other), "A is the changed copy now");
        // the built-in sample is no file on disk, so it cannot become B
        app.open_sample();
        assert_eq!(answer(&mut app, "swap_ab", json!({})).status, 409);
    }

    /// The compare's record map: each record at its offset in the file (the live settings' first
    /// at 0x40), and with "Only rows that differ" the one record file B changed.
    #[test]
    fn compare_records_offsets() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (b, s, _) = changed_sample(&app);
        ask_upload(&mut app, "open_b", &b, "wsa_records_B.DAT");
        let cols = json!([["a", 0], ["b", 0]]);
        let j = ask(&mut app, "compare_records", json!({ "cols": cols, "only_diff": false }));
        let rows = j["rows"].as_array().unwrap();
        let live = app.doc.as_ref().unwrap().edited.sections[0].clone();
        assert_eq!((rows.len(), j["total"].as_u64()), (live.records.len(), Some(live.records.len() as u64)));
        assert_eq!(rows[0]["offset"], "000040");
        assert_eq!(rows[1]["offset"], format!("{:06x}", 0x40 + 8 + live.records[0].value.len()).as_str());
        assert_eq!(rows[0]["shape"], format!("{}×{}", live.records[0].elem_size, live.records[0].count).as_str());
        let d = ask(&mut app, "compare_records", json!({ "cols": cols, "only_diff": true }));
        let id = format!("0x{:04x}", s.id);
        assert_eq!(d["rows"].as_array().unwrap().len(), 1);
        assert_eq!((&d["rows"][0]["id"], &d["rows"][0]["cells"][1]["differs"]), (&json!(id), &json!(true)));
        assert!(d["rows"][0]["setting"]["key"].is_string());
        let q = ask(&mut app, "compare_records", json!({ "cols": cols, "only_diff": false, "q": id }));
        assert!(q["rows"].as_array().unwrap().iter().any(|r| r["id"] == id.as_str()));
        // a memory as the baseline: its records start after the live settings'
        if let Some(&m) = app.dial_sets().first() {
            let want = 0x3c + 4 + live.records.iter().map(|r| 8 + r.value.len()).sum::<usize>() + 4;
            let j = ask(&mut app, "compare_records", json!({ "cols": [["a", m]], "only_diff": false }));
            assert_eq!(j["rows"][0]["offset"], format!("{want:06x}").as_str());
        }
        assert!(ask(&mut app, "compare_records", json!({ "cols": [] }))["rows"].as_array().unwrap().is_empty());
    }

    /// The state holds what the page draws the window's frame with: the menu's tabs with their
    /// colours, settings and edits, the Main page's sets, the definition, the firmware badge.
    #[test]
    fn state_for_the_frame() {
        let mut app = App::new(vec![], Prefs::default());
        let s = ask(&mut app, "state", json!({}));
        assert!(s["file"].is_null());
        assert_eq!(s["edits"], 0);
        app.open_sample();
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        assert_eq!(s["target"], 0);
        assert_eq!(s["known"], app.schema.settings.len());
        assert_eq!(s["definition"], "ILCE-1M2_fw4.00.json");
        // the definition in use, named where the file is
        let def = &s["file"]["definition"];
        assert_eq!((def["text"].as_str(), def["model"].as_str(), def["firmware"].as_str(), def["source"].as_str(), def["chosen"].as_bool()),
            (Some("ILCE-1M2 firmware 4.00, built-in"), Some("ILCE-1M2"), Some("4.00"), Some("built-in"), Some(false)));
        assert!(def["tip"].as_str().unwrap().starts_with("Read with the ILCE-1M2 firmware 4.00 definition (ILCE-1M2_fw4.00.json)."), "{def}");
        assert_eq!(s["file"]["badge"]["kind"], "ok", "the sample's firmware is a checked one");
        let fw = s["file"]["firmware"].as_str().unwrap();
        // the video system after the firmware, as the window's badge says it (the sample's block says where it is)
        let video = video_badge(&app.doc.as_ref().unwrap().edited).0;
        assert!(video.starts_with(" · ") && video.len() > 3, "{video:?}");
        assert_eq!(s["file"]["badge"]["text"], format!("✔ firmware {fw}{video}").as_str());
        assert_eq!(s["targets"][0], json!([0, app.schema.camera.target_name(0), true]));
        let names: Vec<&str> = app.schema.camera.main_tiles.as_ref().map(|m| m.0.iter().map(|t| t.name.as_str()).collect()).unwrap_or_default();
        assert_eq!(s["main_sets"], json!(names));
        let tabs = s["tabs"].as_array().unwrap();
        let info = s["tab_info"].as_array().unwrap();
        assert_eq!(info.len(), tabs.len());
        for (t, name) in info.iter().zip(tabs) {
            let n = name.as_str().unwrap();
            assert_eq!(t["name"], n);
            assert_eq!(t["count"], app.settings_in(0, Some(n)).count());
            assert_eq!(t["edited"], 0);
            // the definition's colour, grey for a tab it gives none
            let want = app.schema.camera.tab_colors.get(n).map_or("#a0a0a0".to_string(), |[r, g, b]| format!("#{r:02x}{g:02x}{b:02x}"));
            assert_eq!(t["color"], want.as_str());
        }
        // an edit counts in the file and in its tab
        let doc = app.doc.as_ref().unwrap();
        let st = app.settings_in(0, None)
            .find(|x| x.scalar && x.range.is_none() && x.offered(false).len() >= 2 && app.shape_ok_in(x, 0) && doc.value(0, x.slot()).is_some())
            .cloned().unwrap();
        let cur = doc.value(0, st.slot()).unwrap();
        let other = st.offered(false).into_iter().map(|(v, _)| v).find(|v| *v != cur).unwrap();
        ask(&mut app, "set", json!({ "target": 0, "key": st.key, "value": other }));
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        assert!(s["edits"].as_u64().unwrap() >= 1);
        let t = s["tab_info"].as_array().unwrap().iter().find(|t| t["name"] == st.tab.as_str()).unwrap();
        assert!(t["edited"].as_u64().unwrap() >= 1, "{} edited, but not counted in {}", st.name, st.tab);
        // a set the page cannot show is counted as the live settings
        assert_eq!(ask(&mut app, "state", json!({ "target": 99 }))["target"], 0);
        if let Some(&m) = app.dial_sets().first() {
            let s = ask(&mut app, "state", json!({ "target": m }));
            assert_eq!(s["target"], m);
            assert_eq!(s["targets"].as_array().unwrap().iter().find(|t| t[0] == m).unwrap()[2], true);
        }
    }

    /// The Main page as the window draws it: each page's tiles with their values, the tiles that
    /// can be changed in place, and the settings under them as rows.
    #[test]
    fn main_page_as_the_window_has_it() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let Some(pages) = app.schema.camera.main_tiles.clone() else { return };
        for (i, page) in pages.0.iter().enumerate() {
            let m = ask(&mut app, "main", json!({ "target": 0, "set": i }));
            assert_eq!(m["set"], i);
            let tiles = m["tiles"].as_array().unwrap();
            assert_eq!(tiles.len(), page.tiles.len());
            let mut rows = 0;
            for (t, tile) in tiles.iter().zip(&page.tiles) {
                assert_eq!(t["caption"], tile.caption.as_str());
                assert!(!t["text"].as_str().unwrap().is_empty());
                let keys: Vec<&str> = tile.keys_for(0).into_iter().filter(|k| app.schema.settings.iter().any(|s| s.key == *k)).collect();
                rows += keys.len();
                if let Some(e) = t.get("edit") {
                    assert_eq!(keys, [e["key"].as_str().unwrap()], "{}: only a tile with one setting is changed in place", tile.caption);
                    assert_eq!(e["editable"], true);
                    assert!(matches!(e["kind"].as_str(), Some("choice" | "range")));
                }
            }
            assert_eq!(m["rows"].as_array().unwrap().len(), rows);
        }
        assert_eq!(ask(&mut app, "main", json!({ "target": 0, "set": 99 }))["set"], 0);
        // a change made on a tile shows on it, as edited
        let m = ask(&mut app, "main", json!({ "target": 0, "set": 0 }));
        let Some(t) = m["tiles"].as_array().unwrap().iter().find(|t| t["edit"]["kind"] == "choice").cloned() else { return };
        let e = &t["edit"];
        assert_eq!(t["changed"], false);
        let other = e["options"].as_array().unwrap().iter().map(|o| o[0].clone()).find(|v| *v != e["value"]).unwrap();
        ask(&mut app, "set", json!({ "target": 0, "key": e["key"], "value": other }));
        let m = ask(&mut app, "main", json!({ "target": 0, "set": 0 }));
        let t = m["tiles"].as_array().unwrap().iter().find(|x| x["caption"] == t["caption"]).unwrap();
        assert_eq!(t["changed"], true);
        assert_eq!(t["edit"]["value"], other);
        let row = m["rows"].as_array().unwrap().iter().find(|r| r["key"] == e["key"]).unwrap();
        assert_eq!((&row["changed"], &row["caption"]), (&json!(true), &t["caption"]));
    }

    /// The Memories page as the window's: the dial's memories beside the live settings, the rows the
    /// memories keep in the window's order, and recall, register and the row arrows changing the
    /// open file through the editor's own edits (one step to undo each).
    #[test]
    fn memories_page_and_recall() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let dial = app.dial_sets();
        if dial.is_empty() {
            return;
        }
        // U-30: by default only the rows where a memory differs from the live settings, as the window's page
        let d = ask(&mut app, "memories", json!({}));
        assert_eq!(d["only_diff"], true);
        let rows = |j: &Value| -> Vec<Value> { j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).collect() };
        assert!(rows(&d).iter().all(|r| r["cells"].as_array().unwrap().iter().any(|c| c["differs"] == true)));
        let j = ask(&mut app, "memories", json!({ "only_diff": false }));
        assert!(rows(&j).len() > rows(&d).len());
        assert_eq!(j["title"], app.memories_title().as_str());
        let names: Vec<Value> = dial.iter().map(|&m| json!([m, app.schema.camera.target_name(m)])).collect();
        assert_eq!(j["dial"], json!(names));
        assert_eq!((&j["cols"], &j["all"], &j["editable"]), (&json!(names), &json!(false), &json!(true)), "the dial's memories only, by default");
        let keys: Vec<String> = rows(&j).iter().map(|r| r["key"].as_str().unwrap().to_string()).collect();
        let want: Vec<String> = app.web_memory_rows("").iter().map(|r| r.2[0].key.clone()).collect();
        assert!(!keys.is_empty());
        assert_eq!(keys, want, "the window's rows, in its order");
        assert!(keys.iter().all(|k| app.schema.settings.iter().any(|s| s.key == *k && s.in_sets)));
        assert!(j["buttons"].as_array().unwrap().iter().all(|b| b["recall"].as_str().unwrap().starts_with("Recall ") && !b["recall_tip"].as_str().unwrap().is_empty()));
        // U-37: the window's words for the whole sets, on Memories and in Compare alike
        let (label, hover, _) = app.recall_words(dial[0], "", "");
        assert_eq!((&j["buttons"][0]["recall"], &j["buttons"][0]["recall_tip"]), (&json!(label), &json!(hover)));
        let frame = app.web_compare_frame(&[Col::a(0), Col::a(dial[0])]);
        assert_eq!(frame["whole_sets"][0]["recall"], json!(label));
        assert_eq!(frame["whole_sets"][0]["register"], j["buttons"][0]["register"]);
        // a setting kept in the memories, made to differ in the first memory
        let m = dial[0];
        let s = app.web_memory_rows("").into_iter().map(|r| r.2[0].clone())
            .find(|s| s.scalar && s.range.is_none() && s.text.is_none() && s.offered(false).len() >= 2 && app.shape_ok_in(s, m) && app.col_value(Col::a(m), s).is_some())
            .unwrap();
        let live = app.col_value(Col::a(0), &s).unwrap();
        let other = s.offered(false).into_iter().map(|(v, _)| v).find(|v| *v != live).unwrap();
        ask(&mut app, "set", json!({ "target": m, "key": s.key, "value": other }));
        let j = ask(&mut app, "memories", json!({}));
        let row = rows(&j).into_iter().find(|r| r["key"] == s.key.as_str()).expect("a row that differs is shown");
        assert_eq!(row["live"]["value"], live);
        assert_eq!(row["live"]["text"], App::describe(&s, Some(live)).as_str());
        let cell = row["cells"].as_array().unwrap().iter().find(|c| c["section"] == m).unwrap().clone();
        assert_eq!((&cell["value"], &cell["differs"]), (&json!(other), &json!(true)));
        assert_eq!(cell["text"], App::describe(&s, Some(other)).as_str());
        // the memory's value is an edit (orange on the page), the live one is not: a difference alone is a pale fill
        assert_eq!((&cell["edited"], &row["live"]["edited"]), (&json!(true), &json!(false)));
        assert_eq!(j["intro"], app.memories_lead().as_str(), "the window's words under the heading");
        // the row's ⬅: the memory's value into the live settings, one step to undo
        let undo = app.undo.len();
        assert_eq!(ask(&mut app, "memory_copy", json!({ "key": s.key, "from": m, "to": 0 }))["ok"], true);
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        assert_eq!(app.undo.len(), undo + 1);
        assert!(app.status.ends_with("from the web page"), "{}", app.status);
        // the row's ➡ the other way, after the memory changes again
        ask(&mut app, "set", json!({ "target": m, "key": s.key, "value": live }));
        ask(&mut app, "memory_copy", json!({ "key": s.key, "from": 0, "to": m }));
        assert_eq!(app.col_value(Col::a(m), &s), Some(other));
        // between two memories, a set the file does not hold, a setting the memories do not keep: refused
        assert_eq!(answer(&mut app, "memory_copy", json!({ "key": s.key, "from": 1, "to": 2 })).status, 400);
        assert_eq!(answer(&mut app, "memory_copy", json!({ "key": s.key, "from": 0, "to": 99 })).status, 400);
        assert_eq!(answer(&mut app, "memory_copy", json!({ "key": s.key, "from": 0, "to": 0 })).status, 400);
        assert_eq!(answer(&mut app, "memory_copy", json!({ "key": "no-such-key", "from": 0, "to": m })).status, 404);
        // agree: every stored value of the memory equals the live one, for every row the memories keep
        let same = |app: &App, m: usize| app.web_memory_rows("").iter().flat_map(|r| r.2.clone()).all(|l| match (app.col_value(Col::a(0), &l), app.col_value(Col::a(m), &l)) {
            (Some(a), Some(b)) => a == b,
            _ => true,
        });
        // register: the live settings into the memory, in one step
        ask(&mut app, "set", json!({ "target": 0, "key": s.key, "value": live }));
        assert!(!same(&app, m));
        let undo = app.undo.len();
        let n = ask(&mut app, "register", json!({ "memory": m }))["n"].as_u64().unwrap();
        assert!(n >= 1);
        assert!(same(&app, m), "the memory holds the live settings after Register");
        assert_eq!(app.undo.len(), undo + 1);
        assert!(app.status.starts_with("Live settings registered into"), "{}", app.status);
        // recall: a memory into the live settings, in one step
        let last = *dial.last().unwrap();
        ask(&mut app, "set", json!({ "target": last, "key": s.key, "value": other }));
        assert!(!same(&app, last));
        ask(&mut app, "recall", json!({ "memory": last }));
        assert!(same(&app, last), "the live settings hold the memory after Recall");
        assert_eq!(app.col_value(Col::a(0), &s), Some(other));
        assert!(app.status.contains("recalled into the live settings"), "{}", app.status);
        // undo takes the whole recall back
        ask(&mut app, "undo", json!({}));
        assert_eq!(app.col_value(Col::a(0), &s), Some(live));
        for bad in [json!({ "memory": 0 }), json!({ "memory": 99 }), json!({})] {
            assert_eq!(answer(&mut app, "recall", bad.clone()).status, 400, "{bad}");
            assert_eq!(answer(&mut app, "register", bad.clone()).status, 400, "{bad}");
        }
        // the page's own search narrows the rows, as the window's does
        let word = s.name.split(' ').next().unwrap().to_lowercase();
        let found = rows(&ask(&mut app, "memories", json!({ "q": word })));
        assert!(!found.is_empty() && found.len() <= keys.len());
        assert!(found.iter().any(|r| r["key"] == s.key.as_str()));
        // the file's other memory sets as columns too, when asked for
        let others: Vec<usize> = (1..app.n_sections()).filter(|x| !dial.contains(x)).collect();
        let j = ask(&mut app, "memories", json!({ "all": true }));
        assert_eq!(j["all"], !others.is_empty());
        let cols = dial.len() + others.len();
        assert_eq!(j["cols"].as_array().unwrap().len(), cols);
        assert!(rows(&j).iter().all(|r| r["cells"].as_array().unwrap().len() == cols));
        if let Some(&o) = others.first() {
            ask(&mut app, "memory_copy", json!({ "key": s.key, "from": 0, "to": o }));
            assert_eq!(app.col_value(Col::a(o), &s), app.col_value(Col::a(0), &s));
            assert_eq!(answer(&mut app, "recall", json!({ "memory": o })).status, 400, "recall stays with the dial's memories");
        }
        // view only: nothing changes
        if let Some(d) = app.doc.as_mut() {
            (d.signature, d.unchecked_ok) = ("not-a-checked-layout".into(), false);
        }
        assert_eq!(ask(&mut app, "memories", json!({}))["editable"], false);
        assert_eq!(answer(&mut app, "recall", json!({ "memory": m })).status, 409);
        assert_eq!(answer(&mut app, "register", json!({ "memory": m })).status, 409);
        assert_eq!(answer(&mut app, "memory_copy", json!({ "key": s.key, "from": m, "to": 0 })).status, 409);
    }

    /// The Exposure page as the window's: a column for the live settings and each dial memory, the
    /// three sides with who sets them, the stop scales with a tick per whole stop, the EV only when you
    /// set all three, and the settings that decide each side, their proof only while it is shown.
    #[test]
    fn exposure_page_as_the_window_has_it() {
        use camset_editor::stops::{self, Side};
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let Some(ex) = app.schema.camera.exposure.clone() else { return };
        let j = ask(&mut app, "exposure", json!({}));
        assert_eq!(j["title"], App::ex_title(&ex));
        let columns = j["columns"].as_array().unwrap();
        assert_eq!(columns.len(), 1 + app.dial_sets().len());
        assert_eq!(j["sides"], json!([["aperture", "Aperture"], ["shutter", "Shutter speed"], ["iso", "ISO"]]));
        // the scales: the lowest and highest stops among the scale record's labels, a tick per whole stop
        for (side, word) in [(Side::Aperture, "aperture"), (Side::Shutter, "shutter"), (Side::Iso, "iso")] {
            let sc = &j["scales"][word];
            let s = app.schema.settings.iter().find(|s| s.key == App::ex_side(&ex, side).scale_key).unwrap();
            let st: Vec<f64> = s.values.iter().filter_map(|(_, l)| stops::stops(side, l)).collect();
            let (lo, hi) = (st.iter().copied().fold(f64::MAX, f64::min), st.iter().copied().fold(f64::MIN, f64::max));
            // (serde_json reads a float back to within its last bit)
            let near = |v: &Value, want: f64| v.as_f64().is_some_and(|x| (x - want).abs() < 1e-9);
            assert!(near(&sc["lo"], lo) && near(&sc["hi"], hi), "{word}: {sc} for {lo}..{hi}");
            let ticks: Vec<i64> = ((lo.ceil() as i64)..=(hi.floor() as i64)).collect();
            assert!(ticks.len() >= 3, "{word}: {} ticks", ticks.len());
            assert_eq!(sc["ticks"], json!(ticks), "{word}");
            assert!(!sc["lo_label"].as_str().unwrap().is_empty() && !sc["hi_label"].as_str().unwrap().is_empty());
        }
        for (c, &sec) in columns.iter().zip(&app.ex_sections()) {
            assert_eq!(c["section"], sec);
            assert_eq!(c["name"], app.schema.camera.target_name(sec).as_str());
            let cells = c["cells"].as_object().unwrap();
            assert_eq!(cells.len(), 3, "three sides in every column");
            for (word, name) in [("aperture", "Aperture"), ("shutter", "Shutter speed"), ("iso", "ISO")] {
                let cell = &cells[word];
                assert!(matches!(cell["who"].as_str(), Some("you" | "camera" | "unknown")), "{word}: {}", cell["who"]);
                assert!(cell["hover"].as_str().unwrap().starts_with(&format!("{name}: {}", cell["text"].as_str().unwrap())));
                if let Some([a, b]) = cell["band"].as_array().map(|b| [b[0].as_f64().unwrap(), b[1].as_f64().unwrap()]) {
                    assert!(a <= b, "{word}: band {a}..{b}");
                }
            }
            // the mode and who sets what in it, in the window's words
            match c["mode"].as_str().and_then(|m| ex.control.get(m)) {
                Some(ctl) => assert_eq!(c["control"], App::ex_control(ctl).as_str()),
                None => assert!(c["control"].is_null()),
            }
            assert_eq!(c["mode_note"].is_string(), sec == 0 && !ex.mode_note.is_empty());
            assert!(!c["comp"]["text"].as_str().unwrap().is_empty() && !c["comp"]["note"].as_str().unwrap().is_empty());
            // the EV only when you set all three and each has a value in stops
            let all_you = ["aperture", "shutter", "iso"].iter().all(|w| cells[*w]["who"] == "you" && cells[*w]["at"].is_f64());
            assert_eq!(c["exposes"].is_string(), all_you, "column {sec}");
            if all_you {
                let at = |w: &str| cells[w]["at"].as_f64().unwrap();
                assert_eq!(c["exposes"], format!("EV {:.1} at ISO 100", stops::ev100(at("aperture"), at("shutter"), at("iso"))).as_str());
            }
        }
        // What decides …: settings of the definition, their proof only while the proof lines are on
        let decides = j["decides"].as_array().unwrap();
        assert_eq!(decides.len(), 3);
        assert_eq!(j["show_proof"], false);
        for d in decides {
            let list = d["settings"].as_array().unwrap();
            assert!(!list.is_empty(), "{}", d["name"]);
            for s in list {
                let found = app.schema.settings.iter().find(|x| x.key == s["key"].as_str().unwrap()).unwrap();
                assert_eq!((&s["name"], &s["tab"], &s["group"]), (&json!(found.name), &json!(found.tab), &json!(found.group)));
                assert!(s["proved"].is_null(), "proof shown while the proof lines are off");
            }
        }
        app.prefs.show_proof = true;
        assert_eq!(ask(&mut app, "exposure", json!({}))["show_proof"], false, "the proof lines are for Expert mode");
        app.prefs.expert = true;
        let j = ask(&mut app, "exposure", json!({}));
        assert_eq!(j["show_proof"], true);
        assert!(j["decides"].as_array().unwrap().iter().flat_map(|d| d["settings"].as_array().unwrap().clone()).all(|s| s["proved"].is_boolean()));
        // a definition with no exposure page
        app.schema.camera.exposure = None;
        assert_eq!(answer(&mut app, "exposure", json!({})).status, 409);
    }

    /// The line saying whether a setting was proved on the camera comes with each row while Settings
    /// turns it on (it is off by default), and turning it off changes the state, so the page draws again.
    #[test]
    fn proof_line_follows_the_setting() {
        let mut app = App::new(vec![], Prefs { show_proof: true, expert: true, ..Prefs::default() });
        app.open_sample();
        let first = app.schema.tabs[0].clone();
        let rows = |j: &Value| -> Vec<Value> {
            j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).collect()
        };
        let rev_on = ask(&mut app, "state", json!({ "target": 0 }))["rev"].clone();
        let on = rows(&ask(&mut app, "tab", json!({ "target": 0, "tab": first })));
        assert!(!on.is_empty());
        for r in &on {
            assert!(r["proof"].as_str().is_some_and(|p| !p.is_empty()), "{}: no proof line", r["name"]);
            assert!(r.get("proof_kind").is_some() && r.get("proof_why").is_some());
        }
        app.prefs.show_proof = false;
        assert_ne!(ask(&mut app, "state", json!({ "target": 0 }))["rev"], rev_on, "the page would not notice the switch");
        let off = rows(&ask(&mut app, "tab", json!({ "target": 0, "tab": first })));
        assert_eq!(off.len(), on.len());
        for r in &off {
            assert!(r.get("proof").is_none() && r.get("proof_kind").is_none() && r.get("proof_why").is_none(), "{}: proof line shown while off", r["name"]);
        }
    }

    /// Each group of a tab, and of a search across the tabs, comes with its tab and that tab's colour.
    #[test]
    fn groups_in_their_tab_colour() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let first = app.schema.tabs[0].clone();
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": first }));
        let groups = j["groups"].as_array().unwrap();
        assert!(!groups.is_empty());
        let color = css_color(tab_color(&app.schema.camera, &first));
        assert!(groups.iter().all(|g| g["tab"] == first.as_str() && g["color"] == color.as_str()));
        let word = app.schema.settings[0].name.split(' ').next().unwrap().to_string();
        let j = ask(&mut app, "tab", json!({ "target": 0, "q": word }));
        for g in j["groups"].as_array().unwrap() {
            let tab = g["tab"].as_str().unwrap();
            assert!(g["name"].as_str().unwrap().starts_with(&format!("{tab} › ")));
            assert_eq!(g["color"], css_color(tab_color(&app.schema.camera, tab)).as_str());
        }
    }

    /// The rows of one tab, the family tables' cells among them.
    fn tab_rows(app: &mut App, tab: &str) -> Vec<Value> {
        let j = ask(app, "tab", json!({ "target": 0, "tab": tab }));
        j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).collect()
    }

    /// A setting of the live settings that can be set to another value from its list: (setting, value, another).
    fn changeable(app: &App) -> (Setting, i64, i64) {
        let doc = app.doc.as_ref().unwrap();
        let s = app.settings_in(0, None)
            .find(|x| x.scalar && x.range.is_none() && x.offered(false).len() >= 2 && app.shape_ok_in(x, 0) && app.locked_why(x, 0).is_none() && doc.value(0, x.slot()).is_some())
            .cloned().unwrap();
        let cur = doc.value(0, s.slot()).unwrap();
        let other = s.offered(false).into_iter().map(|(v, _)| v).find(|v| *v != cur).unwrap();
        (s, cur, other)
    }

    /// Expert mode and its two options, and Edit anyway, are the desktop app's: they open what can harm the camera,
    /// so the page cannot turn them on (it shows them as set in the desktop app). The Expert pages answer only while
    /// the desktop has Expert mode on, every set becomes one to edit, and the page notices the switch.
    #[test]
    fn expert_pages_follow_the_pref() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let s = ask(&mut app, "state", json!({}));
        assert_eq!(s["prefs"]["expert"], false);
        for name in ["expert", "allow_raw_edits", "allow_unobserved", "backup_on_save"] {
            assert_eq!(answer(&mut app, "prefs", json!({ "name": name, "value": true })).status, 400, "{name} from the page");
            assert!(s["prefs"]["desktop"].as_array().unwrap().contains(&json!(name)), "{name} shown as the desktop's");
        }
        assert!(!app.prefs.expert && !app.allow_raw_edits && !app.allow_unobserved && app.prefs.backup_on_save);
        for page in ["unmapped", "records"] {
            assert_eq!(answer(&mut app, page, json!({ "target": 0 })).status, 409, "{page} outside Expert mode");
        }
        // the desktop turns Expert mode on
        app.prefs.expert = true;
        let on = ask(&mut app, "state", json!({}));
        assert_ne!(on["rev"], s["rev"], "the page would not notice the switch");
        assert_eq!(on["targets"].as_array().unwrap().len(), app.n_sections());
        for page in ["unmapped", "records"] {
            ask(&mut app, page, json!({ "target": 0 }));
        }
        assert_eq!(answer(&mut app, "prefs", json!({ "name": "expert", "value": false })).status, 400);
        assert!(app.prefs.expert);
        // the switches of how values are shown are the page's to change
        for name in WEB_DISPLAY_PREFS {
            assert_eq!(ask(&mut app, "prefs", json!({ "name": name, "value": true }))["ok"], true, "{name}");
        }
    }

    /// The Unmapped records page: every record no setting names, changed as a number only while Allow raw edits
    /// is on, with the search and Only edited; a mapped record is changed as its setting.
    #[test]
    fn unmapped_and_raw_edits() {
        let mut app = App::new(vec![], Prefs { expert: true, ..Prefs::default() });
        app.open_sample();
        let j = ask(&mut app, "unmapped", json!({ "target": 0 }));
        let doc = app.doc.as_ref().unwrap();
        let want: Vec<u64> = doc.edited.sections[0].records.iter().filter(|r| app.schema.find(false, r.id).is_none()).map(|r| u64::from(r.id)).collect();
        let rows = j["rows"].as_array().unwrap();
        assert_eq!(rows.iter().map(|r| r["id"].as_u64().unwrap()).collect::<Vec<_>>(), want);
        assert_eq!((&j["allow_raw_edits"], &j["editable"]), (&json!(false), &json!(false)));
        let row = rows.iter().find(|r| r["int"].is_i64()).cloned().expect("an unmapped record holding one number");
        let id = row["id"].as_u64().unwrap() as u16;
        let new = if row["int"] == 0 { 1 } else { 0 };
        assert_eq!(answer(&mut app, "raw_set", json!({ "target": 0, "id": id, "value": new })).status, 409);
        assert_eq!(answer(&mut app, "prefs", json!({ "name": "allow_raw_edits", "value": true })).status, 400, "the desktop's to turn on");
        app.allow_raw_edits = true;   // turned on in the desktop app
        assert_eq!(ask(&mut app, "unmapped", json!({ "target": 0 }))["editable"], true);
        ask(&mut app, "raw_set", json!({ "target": 0, "id": id, "value": new }));
        assert_eq!(app.doc.as_ref().unwrap().value(0, (id, None)), Some(new));
        assert_eq!(app.undo.len(), 1);
        let only = ask(&mut app, "unmapped", json!({ "target": 0, "only": true }));
        assert_eq!(only["rows"].as_array().unwrap().iter().map(|r| r["id"].as_u64().unwrap()).collect::<Vec<_>>(), [u64::from(id)]);
        let hex = format!("0x{id:04x}");
        let found = ask(&mut app, "unmapped", json!({ "target": 0, "q": hex }));
        assert!(found["rows"].as_array().unwrap().iter().all(|r| r["hex"].as_str().unwrap().contains(&hex)));
        let doc = app.doc.as_ref().unwrap();
        let mapped = app.schema.settings.iter().find(|s| s.area == "global" && s.index.is_none() && doc.value(0, s.slot()).is_some()).unwrap().id;
        assert_eq!(answer(&mut app, "raw_set", json!({ "target": 0, "id": mapped, "value": 0 })).status, 400);
        assert_eq!(answer(&mut app, "raw_set", json!({ "target": 0, "id": 0xffff, "value": 0 })).status, 404);
    }

    /// The record map: every record in file order from the first after the header (0x3c, then the set's count),
    /// each offset the one before plus the record's head and value, the bytes of a long record (all, or those asked
    /// for), and the filters.
    #[test]
    fn record_map_offsets_and_dump() {
        let mut app = App::new(vec![], Prefs { expert: true, ..Prefs::default() });
        app.open_sample();
        let j = ask(&mut app, "records", json!({ "target": 0 }));
        assert_eq!(j["name"], app.schema.camera.target_name(0).as_str());
        let rows = j["rows"].as_array().unwrap();
        assert_eq!(rows[0]["offset"], "000040");
        let recs = app.doc.as_ref().unwrap().edited.sections[0].records.clone();
        assert_eq!(rows.iter().map(|r| r["id"].as_u64().unwrap()).collect::<Vec<_>>(), recs.iter().map(|r| u64::from(r.id)).collect::<Vec<_>>());
        let at = |r: &Value| usize::from_str_radix(r["offset"].as_str().unwrap(), 16).unwrap();
        for (w, r) in rows.windows(2).zip(&recs) {
            assert_eq!(at(&w[1]) - at(&w[0]), 8 + r.value.len());
        }
        let big = rows.iter().find(|r| r["big"] == true).expect("a record of more than 8 bytes").clone();
        let dump = big["bytes"]["dump"].as_str().unwrap();
        let first = dump.lines().next().unwrap();
        assert!(first.starts_with("0000  ") && first.len() <= 6 + 47 + 2 + 16, "{first}");
        let id = big["id"].as_u64().unwrap();
        let some = ask(&mut app, "records", json!({ "target": 0, "open": [id] }));
        assert!(some["rows"].as_array().unwrap().iter().all(|r| r["bytes"].is_null() == (r["id"] != id)));
        let one = ask(&mut app, "records", json!({ "target": 0, "q": big["hex"] }));
        assert_eq!(one["rows"].as_array().unwrap().len(), 1);
        let unmapped = ask(&mut app, "records", json!({ "target": 0, "only_unmapped": true }));
        let unmapped = unmapped["rows"].as_array().unwrap();
        assert!(!unmapped.is_empty() && unmapped.iter().all(|r| r["setting"].is_null()));
        assert_eq!(unmapped.len(), recs.iter().filter(|r| app.schema.find(false, r.id).is_none()).count());
        assert!(ask(&mut app, "records", json!({ "target": 0, "only_edited": true }))["rows"].as_array().unwrap().is_empty());
        let mapped = rows.iter().find(|r| !r["setting"].is_null()).unwrap();
        let s = app.schema.find(false, mapped["id"].as_u64().unwrap() as u16).unwrap();
        assert_eq!((&mapped["setting"]["key"], &mapped["setting"]["tab"]), (&json!(s.key), &json!(s.tab)));
    }

    /// Each row carries what the window's detail panel shows: help, the modes it applies in, where it is kept, and
    /// (as Settings asks) the record id, the raw value and, in Expert mode, how it was mapped; each switch changes
    /// the state's `rev`, and the switches that shape the window or the page itself are the desktop app's.
    #[test]
    fn rows_carry_the_detail_panel() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let tab = app.schema.tabs[0].clone();
        let rows = tab_rows(&mut app, &tab);
        assert!(!rows.is_empty());
        for r in &rows {
            let s = app.schema.settings.iter().find(|s| s.key == r["key"]).unwrap();
            assert_eq!((&r["help"], &r["modes"]), (&json!(s.help), &json!(s.modes)));
            let stored = if s.in_sets { json!("sets") } else if s.area == "global" { json!("live") } else { Value::Null };
            assert_eq!(r["stored"], stored, "{}", s.name);
            assert!(r.get("records").is_none(), "the records line is for Expert mode");
            assert!(r.get("record_id").is_none() && r.get("raw").is_none() && r.get("record").is_none());
        }
        let mut rev = ask(&mut app, "state", json!({}))["rev"].clone();
        for name in ["expert", "show_record_ids", "show_raw"] {
            if name == "expert" {
                app.prefs.expert = true;   // set in the desktop app
            } else {
                ask(&mut app, "prefs", json!({ "name": name, "value": true }));
            }
            let now = ask(&mut app, "state", json!({}))["rev"].clone();
            assert_ne!(now, rev, "{name}: the page would not notice");
            rev = now;
        }
        assert!(app.prefs.show_raw && app.show_raw);
        let doc_value = |app: &App, s: &Setting| app.doc.as_ref().unwrap().value(0, s.slot());
        for r in tab_rows(&mut app, &tab) {
            let s = app.schema.settings.iter().find(|s| s.key == r["key"]).unwrap();
            assert_eq!(r["record_id"], s.record_id_hex().as_str());
            assert_eq!(r["record"], format!("record 0x{:04x}", s.id).as_str());
            assert!(r["records"].as_str().unwrap().contains(&format!("0x{:04x}", s.id)));
            if s.text.is_none() {
                assert_eq!(r["raw"], json!(doc_value(&app, s)));
            }
            if r["kind"] == "choice" {
                for o in r["options"].as_array().unwrap() {
                    assert!(o[1].as_str().unwrap().ends_with(&format!("  [{}]", o[0])), "{o}");
                }
            }
        }
        for name in ["probe_path", "definitions_dir", "reopen_last", "theme", "light", "zoom", "density", "web_at_start", "web_port", "web_code", "expert", "allow_raw_edits", "allow_unobserved", "backup_on_save", "no_such"] {
            assert_eq!(answer(&mut app, "prefs", json!({ "name": name, "value": true })).status, 400, "{name}");
        }
        assert_eq!(answer(&mut app, "prefs", json!({ "name": "show_raw", "value": "yes" })).status, 400);
    }

    /// Each row says whose words its help is (`help_from_file`), and the hovers sent with the rows say it as the
    /// window's does (`help_hover`): the camera's own help, named in Expert mode, or Camset's own description.
    #[test]
    fn rows_say_whose_help_they_show() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let tab = app.schema.tabs[0].clone();
        let keys: Vec<String> = tab_rows(&mut app, &tab).iter().take(2).map(|r| r["key"].as_str().unwrap().to_string()).collect();
        for (i, k) in keys.iter().enumerate() {
            let s = app.schema.settings.iter_mut().find(|s| &s.key == k).unwrap();
            s.help = format!("Help {i}.");
            s.help_from_file = i == 0;
        }
        let rows = tab_rows(&mut app, &tab);
        for (i, k) in keys.iter().enumerate() {
            let r = rows.iter().find(|r| r["key"] == k.as_str()).unwrap();
            assert_eq!((&r["help"], &r["help_from_file"]), (&json!(format!("Help {i}.")), &json!(i == 0)));
        }
        let hovers = ask(&mut app, "state", json!({}))["row_hovers"].clone();
        assert_eq!((hovers["help"].as_str(), hovers["help_own"].as_str()), (Some("From the camera's own help"), Some("Camset's own description (not the camera's own help)")));
        app.prefs.expert = true;   // set in the desktop app
        let hovers = ask(&mut app, "state", json!({}))["row_hovers"].clone();
        assert_eq!(hovers["help"], format!("From the camera's own help ({})", app.schema.help_file_name()).as_str());
        assert!(hovers["help_own"].as_str().unwrap().starts_with("Camset's own description, from the definition"), "{}", hovers["help_own"]);
    }

    /// The owner's rule in the window and on the page ("a new user with a different camera shouldn't get the a1 II
    /// help"): a made-up second camera's definition, chosen in Expert mode to read the file with, shows none of the
    /// ILCE-1M2's help, even with a copy of the ILCE-1M2's help file renamed for it, which is refused and named in what
    /// the page's Settings and Expert line show. Back on the ILCE-1M2's own definition the camera's help is shown, and
    /// each option's hover says whose words it is, value by value.
    #[test]
    fn another_cameras_definition_shows_none_of_the_a1s_help() {
        use crate::definitions::definitions_tests::{a1_with, app_with, scratch, shipped};
        let (dir, user, help) = (scratch("web_help_file"), scratch("web_help_user"), scratch("web_help_dir"));
        std::fs::write(user.join("ILCE-0X0_fw4.00.json"), a1_with(|v| {
            v["model"] = "ILCE-0X0".into(); v["layouts"][0]["model"] = "ILCE-0X0".into(); v["camera"]["model"] = "ILCE-0X0".into();
            for s in v["settings"].as_array_mut().unwrap() {
                let o = s.as_object_mut().unwrap();
                o.remove("help");
                o.remove("option_help");
            }
        })).unwrap();
        let mut app = app_with(&user);
        let all: serde_json::Map<String, Value> = app.defs.shipped("ILCE-1M2", "4.00").unwrap().settings.iter()
            .map(|s| (s.key.clone(), json!({"help": "The a1 II's words.", "option_help": [[0, "An a1 II option."]]}))).collect();
        let a1s = json!({"model": "ILCE-1M2", "firmware": "4.00", "source": "a test", "settings": all}).to_string();
        std::fs::write(help.join("help_ILCE-1M2_fw4.00.json"), &a1s).unwrap();
        std::fs::write(help.join("help_ILCE-0X0_fw4.00.json"), &a1s).unwrap();
        app.defs = Definitions::load(Some(shipped()), vec![shipped()], user.clone(), std::slice::from_ref(&help));
        app.prefs.expert = true;   // set in the desktop app
        let f = dir.join("CAMSET01.DAT");
        std::fs::write(&f, include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        app.open(f);
        let other = app.defs.find("ILCE-0X0", "4.00").unwrap().origin.clone();
        app.override_definition(Some(other));
        assert_eq!(app.schema.model, "ILCE-0X0");
        // the window's state: no help at all, and the refused file with why
        assert!(app.schema.settings.iter().all(|s| s.help.is_empty() && s.option_help.is_empty() && !s.help_from_file && s.option_help_from_file.is_empty()));
        let why = "Help file not used: help_ILCE-0X0_fw4.00.json: it is for the ILCE-1M2 firmware 4.00, not the ILCE-0X0 firmware 4.00. The help shown is Camset's own, from the definition, where it has some.";
        assert_eq!(app.schema.help_refusals(), vec![why.to_string()]);
        // the page's rows: no help, and no option's hover holds any
        for tab in app.schema.tabs.clone() {
            for r in tab_rows(&mut app, &tab) {
                assert_eq!((&r["help"], &r["help_from_file"]), (&json!(""), &json!(false)), "{}", r["key"]);
                for o in r["options"].as_array().into_iter().flatten() {
                    assert!(o[3].is_null() || o[3] == json!(UNPROVED_HOVER), "{}: {}", r["key"], o[3]);
                }
            }
        }
        // what the page's Settings and Expert line show: the file by its name, never its folder
        let st = ask(&mut app, "state", json!({}));
        assert_eq!(st["help_src"], "");
        assert_eq!(st["help_refused"], json!([{ "file": "help_ILCE-0X0_fw4.00.json", "text": why }]));
        let listed = st["schemas"].as_array().unwrap().iter().find(|d| d["model"] == "ILCE-0X0").unwrap();
        assert_eq!(listed["help_refused"], json!([why]));
        assert!(!st.to_string().contains(&help.to_string_lossy().to_string()), "no folder on the page");
        // the ILCE-1M2's own definition: the camera's help, and each option's hover says whose it is
        app.override_definition(None);
        assert_eq!(app.schema.model, "ILCE-1M2");
        assert!(app.schema.settings.iter().all(|s| s.help == "The a1 II's words." && s.help_from_file) && app.schema.help_refused.is_empty());
        let tab = app.schema.tabs[0].clone();
        let rows = tab_rows(&mut app, &tab);
        assert!(rows.iter().all(|r| r["help"] == "The a1 II's words." && r["help_from_file"] == true));
        let opts: Vec<(i64, String)> = rows.iter().flat_map(|r| r["options"].as_array().cloned().unwrap_or_default())
            .filter_map(|o| Some((o[0].as_i64()?, o[3].as_str()?.to_string()))).collect();
        let camera = "From the camera's own help (help_ILCE-1M2_fw4.00.json)";
        assert!(opts.iter().any(|(v, h)| *v == 0 && h.starts_with(&format!("An a1 II option.\n\n{camera}"))), "{opts:?}");
        assert!(opts.iter().filter(|(v, _)| *v == 0).all(|(_, h)| h.contains(camera)));
        assert!(opts.iter().filter(|(v, _)| *v != 0).all(|(_, h)| !h.contains(camera)), "the definition's own words for the other values");
        let own: Vec<&String> = opts.iter().filter(|(v, h)| *v != 0 && h.as_str() != UNPROVED_HOVER).map(|(_, h)| h).collect();
        assert!(own.iter().all(|h| h.contains("\n\nCamset's own description, from the definition ILCE-1M2_fw4.00.json (not the camera's own help)")), "{own:?}");
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::remove_dir_all(&user);
        let _ = std::fs::remove_dir_all(&help);
    }

    /// The page draws Focus Area's options as the window's detail panel does, from the definition's `option_tree`: the
    /// row carries the main options, Spot with its sizes ([value, label under Spot, seen, help]) beside the flat list
    /// the other controls use; a size is set as any value is, and the row's label stays the flat one ("Spot: M"). A
    /// setting the camera lists flat, or a definition without the field, carries no tree.
    #[test]
    fn options_nested_as_on_the_camera() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        app.allow_unobserved = true;
        let fa = app.schema.settings.iter().find(|s| s.key == "global:0x0f46").unwrap().clone();
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": fa.tab }));
        let rows: Vec<Value> = j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).collect();
        let row = rows.iter().find(|r| r["key"] == fa.key).expect("Focus Area's row").clone();
        let tree = row["tree"].as_array().expect("the option tree");
        let mains: Vec<&str> = tree.iter().map(|n| n["label"].as_str().unwrap()).collect();
        assert_eq!(mains, ["Wide", "Zone", "Center Fix", "Spot", "Expand Spot", "Custom", "Tracking"]);
        let spot = tree.iter().find(|n| n["label"] == "Spot").unwrap();
        let sizes: Vec<&str> = spot["options"].as_array().unwrap().iter().map(|o| o[1].as_str().unwrap()).collect();
        assert_eq!(sizes, ["XL", "L", "M", "S", "XS"]);
        assert_eq!(row["options"].as_array().unwrap().len(), 24, "the flat list stays");
        let m = spot["options"].as_array().unwrap().iter().find(|o| o[1] == "M").unwrap()[0].as_i64().unwrap();
        let j = ask(&mut app, "set", json!({ "target": 0, "key": fa.key, "value": m }));
        assert_eq!((j["row"]["value"].as_i64(), j["row"]["label"].as_str()), (Some(m), Some("Spot: M")));
        assert!(j["row"]["tree"].is_array());
        let wb = app.schema.settings.iter().find(|s| s.key == "global:0x0367").unwrap().clone();
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": wb.tab }));
        let flat = j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).find(|r| r["key"] == wb.key).unwrap();
        assert!(flat.get("tree").is_none() && flat["kind"] == "choice", "White Balance: the camera's list, flat");
        for s in app.schema.settings.iter_mut() {
            s.option_tree.clear();
        }
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": fa.tab }));
        let row = j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).find(|r| r["key"] == fa.key).unwrap();
        assert!(row.get("tree").is_none(), "no option_tree: the flat list only");
    }

    /// A number shown other than as stored (`shown_as`) carries how with its row; a disputed setting is sent in Expert
    /// mode only, as the window shows it. Nothing of how a proof was made reaches a row: no name sources, no proof of
    /// the memories keeping it (the lean definition holds none, docs/decisions/0016).
    #[test]
    fn shown_as_and_disputed_in_the_row() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let doc = app.doc.as_ref().unwrap();
        let ranged = app.schema.settings.iter().position(|s| s.range.is_some() && s.text.is_none() && s.area == "global" && s.scalar && doc.value(0, s.slot()).is_some()).unwrap();
        let choice = app.schema.settings.iter().position(|s| s.values.len() >= 3 && s.range.is_none() && s.text.is_none() && s.area == "global" && doc.value(0, s.slot()).is_some()).unwrap();
        {
            let s = &mut app.schema.settings[ranged];
            s.shown_as = Some(camset_editor::schema::ShownAs { divide: 100, decimals: 0 });
        }
        app.schema.settings[choice].disputed = true;
        let (rk, ck) = (app.schema.settings[ranged].key.clone(), app.schema.settings[choice].key.clone());
        let row_of = |app: &mut App, key: &str| {
            let linked = app.web_linked(0, key).unwrap();
            app.web_row(0, &linked)
        };
        let r = row_of(&mut app, &rk);
        assert_eq!(r["shown_as"], json!({ "divide": 100, "decimals": 0 }));
        let c = row_of(&mut app, &ck);
        assert!(c.get("disputed").is_none(), "nothing of it outside Expert mode");
        app.prefs.expert = true;
        let c = row_of(&mut app, &ck);
        assert_eq!(c["disputed"], json!(DISPUTED));
        for k in ["names", "stored_proof", "evidence", "blocked"] {
            assert!(c.get(k).is_none(), "{k}");
        }
        assert!(SCRIPT.contains("r.disputed && expert"));
        for gone in ["r.names", "r.stored_proof", "r.evidence", "r.blocked"] {
            assert!(!SCRIPT.contains(gone), "the page still reads {gone}");
        }
    }

    /// The page lays a tab out as the window does: as on the camera (`layout`: Drive Mode's row, the choices of its
    /// options under it, the camera's submenus as headings), with the switch the page offers ("places", "flat"), and
    /// the flat list once it asks for it (the editor keeps the choice). Drive Mode's row carries the choice of the
    /// option chosen now, and a change to that choice answers Drive Mode's row too.
    #[test]
    fn rows_as_on_the_camera() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": "Shooting" }));
        assert_eq!((j["places"].as_bool(), j["flat"].as_bool()), (Some(true), Some(false)));
        let drive = j["groups"].as_array().unwrap().iter().find(|g| g["name"] == "Drive Mode").unwrap().clone();
        let (layout, rows) = (drive["layout"].as_array().unwrap(), drive["rows"].as_array().unwrap());
        let keys: Vec<&Value> = layout.iter().filter_map(|l| l.get("key")).collect();
        assert_eq!(keys, rows.iter().map(|r| &r["key"]).collect::<Vec<_>>(), "the rows in the order the layout draws them");
        assert_eq!(rows[0]["name"], "Drive Mode");
        assert_eq!(layout[0]["depth"].as_u64(), Some(0));
        assert!(layout.iter().any(|l| l["head"] == "Cont. Shooting Speed" && l["depth"] == 0));
        // the choices of Drive Mode's options are no rows here, only beside them in its details; the group counts them
        assert!(!rows.iter().any(|r| r["name"].as_str().unwrap().starts_with("Drive memory")), "no sub-choice rows as on the camera");
        assert_eq!(drive["beside"], json!(true));
        let subs = rows[0]["subs"]["rows"].as_array().unwrap();
        assert_eq!(subs.len(), 7);
        assert!(subs[0]["place"].as_str().unwrap().starts_with("On the camera: Drive Mode, the choice for its option "));
        assert!(subs.iter().all(|r| r.get("beside").is_none()), "no link to its owner inside its owner");
        // the options with a choice of their own; set to Continuous Shooting, Drive Mode's row shows the speed
        let options: Vec<&str> = rows[0]["subs"]["options"].as_array().unwrap().iter().map(|o| o.as_str().unwrap()).collect();
        assert!(options.contains(&"Continuous Shooting") && options.contains(&"DRO Bracket"), "{options:?}");
        let drive_s = app.schema.settings.iter().find(|s| s.key == rows[0]["key"]).unwrap().clone();
        let cont = drive_s.values.iter().find(|(_, l)| l == "Continuous Shooting").unwrap().0;
        let j = ask(&mut app, "set", json!({ "target": 0, "key": drive_s.key, "value": cont }));
        let now = j["row"]["subs"]["now"].clone();
        assert_eq!(now, json!("Continuous Shooting"));
        let shown: Vec<Value> = j["row"]["subs"]["rows"].as_array().unwrap().iter().filter(|r| r["option"] == now).cloned().collect();
        assert_eq!(shown.len(), 1);
        assert_eq!((&shown[0]["option"], &shown[0]["name"]), (&json!("Continuous Shooting"), &json!("Drive memory - continuous shooting speed")));
        let other = shown[0]["options"].as_array().unwrap().iter().map(|o| o[0].as_i64().unwrap()).find(|v| Some(*v) != shown[0]["value"].as_i64()).unwrap();
        let j = ask(&mut app, "set", json!({ "target": 0, "key": shown[0]["key"], "value": other }));
        let back: Vec<&Value> = j["rows"].as_array().unwrap().iter().map(|r| &r["key"]).collect();
        assert!(back.contains(&&json!(drive_s.key)), "Drive Mode's row comes back with its choice: {back:?}");
        let back = j["rows"].as_array().unwrap().iter().find(|r| r["key"] == drive_s.key.as_str()).unwrap()["subs"].clone();
        assert_eq!(back["rows"].as_array().unwrap().iter().find(|r| r["key"] == shown[0]["key"]).unwrap()["value"], other);
        assert_eq!(back["edited"], json!(1), "an edited choice, for Only edited and the group's badge");
        // a search lists a choice as a row, with the way to its owner's row; the flat list (below) has no such link
        let hit = ask(&mut app, "tab", json!({ "target": 0, "tab": "Shooting", "q": "continuous shooting speed" }));
        let hit = hit["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().clone()).find(|r| r["key"] == shown[0]["key"]).unwrap();
        assert_eq!((&hit["beside"]["owner"], &hit["beside"]["option"]), (&json!(drive_s.key), &json!("Continuous Shooting")));
        assert!(hit["beside"]["open_group"].is_string());
        // the flat list: no layout, and the page notices
        let rev = ask(&mut app, "state", json!({}))["rev"].clone();
        ask(&mut app, "prefs", json!({ "name": "flat_list", "value": true }));
        assert!(app.prefs.flat_list);
        assert_ne!(ask(&mut app, "state", json!({}))["rev"], rev, "the page would not notice");
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": "Shooting" }));
        assert!(j["groups"].as_array().unwrap().iter().all(|g| g.get("layout").is_none() && g.get("beside").is_none()));
        let flat = j["groups"].as_array().unwrap().iter().find(|g| g["name"] == "Drive Mode").unwrap()["rows"].as_array().unwrap().clone();
        let speed = flat.iter().find(|r| r["key"] == shown[0]["key"]).expect("the flat list keeps the choice as a row");
        assert!(speed.get("beside").is_none());
        assert_eq!((j["places"].as_bool(), j["flat"].as_bool()), (Some(true), Some(true)));
        assert_eq!(ask(&mut app, "state", json!({}))["prefs"]["flat_list"], true);
        app.set_flat_list(false);
    }

    /// The page follows the layout in use as the window does: as on the camera, Recall Custom hold 1's settings are in
    /// Shooting Mode under Reg. Custom Shoot Set (the hold's own group gone from the tab), TC/UB opens with "In Movie
    /// mode" and comes where the Movie menu has it, and every link to a setting (the record map, Compare, My Menu)
    /// names the group that shows it now ("open_group"); in the flat list, the setting's own group, as before.
    #[test]
    fn the_page_follows_the_layout_in_its_groups_and_links() {
        let mut app = App::new(vec![], Prefs { expert: true, ..Prefs::default() });
        app.open_sample();
        let hold = app.schema.settings.iter().find(|s| s.group == "Recall Custom hold 1" && s.name == "Shoot Mode" && s.area == "global").unwrap().clone();
        let fn1 = app.schema.settings.iter().find(|s| s.group == "Fn Menu" && s.area == "global" && s.row_group.is_some()).unwrap().clone();
        let names = |j: &Value| j["groups"].as_array().unwrap().iter().map(|g| g["name"].as_str().unwrap().to_string()).collect::<Vec<_>>();
        let link = |app: &mut App| {
            let rec = ask(app, "records", json!({ "target": 0, "q": format!("0x{:04x}", fn1.id) }));
            let rec = rec["rows"].as_array().unwrap().iter().find(|r| r["setting"]["key"] == fn1.key.as_str()).unwrap()["setting"]["open_group"].clone();
            let cmp = ask(app, "compare", json!({ "cols": [["a", 0], ["a", 1]], "only_diff": false, "q": fn1.name }));
            let cmp = cmp["rows"].as_array().unwrap().iter().find(|r| r["key"] == fn1.key.as_str()).map(|r| (r["group"].clone(), r["open_group"].clone()));
            (rec, cmp)
        };
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": "Shooting" }));
        let shown = names(&j);
        assert!(!shown.iter().any(|g| g.starts_with("Recall Custom hold")), "{shown:?}");
        let at = |n: &str| shown.iter().position(|x| x == n).unwrap();
        assert!(at("Audio Recording") < at("TC/UB") && at("TC/UB") < at("Image Stabilization"), "{shown:?}");
        let groups = j["groups"].as_array().unwrap();
        let mode = groups.iter().find(|g| g["name"] == "Shooting Mode").unwrap();
        assert!(mode["rows"].as_array().unwrap().iter().any(|r| r["key"] == hold.key.as_str()));
        assert!(mode["layout"].as_array().unwrap().iter().any(|l| l["head"] == "Recall Custom hold 1" && l["path"][0] == "Reg. Custom Shoot Set"));
        let tc = groups.iter().find(|g| g["name"] == "TC/UB").unwrap();
        assert_eq!((&tc["layout"][0]["mode"], &tc["layout"][0]["name"]), (&json!("In Movie mode"), &json!("Movie")));
        let (rec, cmp) = link(&mut app);
        assert_eq!(rec, "Operation Customize");
        let (group, open) = cmp.expect("an Fn Menu setting in Compare");
        assert_eq!((group.as_str(), open.as_str()), (Some("Fn Menu"), Some("Operation Customize")), "Compare keeps the setting's group, and opens it where Edit shows it");
        // the flat list: the hold's own group, in the tab and in the links
        ask(&mut app, "prefs", json!({ "name": "flat_list", "value": true }));
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": "Shooting" }));
        assert!(names(&j).contains(&"Recall Custom hold 1".to_string()));
        assert_eq!(link(&mut app).0, "Fn Menu");
        app.set_flat_list(false);
    }

    /// A setting whose row is in another tab (`row_tab`) is on that tab's page as on the camera, in the row's group
    /// under its row, and every link to it opens that tab ("open_tab") and group, as the window's; the flat list keeps
    /// it in its own tab and group.
    #[test]
    fn the_page_shows_a_row_in_another_tab_there() {
        let mut app = App::new(vec![], Prefs { expert: true, ..Prefs::default() });          // the record map's links
        app.open_sample();
        let key = app.schema.settings.iter().find(|s| s.area == "global" && !s.expert && s.row_mode.is_none() && s.row_tab.as_deref() == Some("Setup") && s.tab != "Setup").unwrap().clone();
        let group = key.row_group.clone().unwrap();
        let on_page = |app: &mut App, tab: &str| -> Option<(String, Value)> {
            let j = ask(app, "tab", json!({ "target": 0, "tab": tab }));
            j["groups"].as_array().unwrap().iter().find(|g| g["rows"].as_array().unwrap().iter().any(|r| r["key"] == key.key.as_str()))
                .map(|g| (g["name"].as_str().unwrap().to_string(), g["layout"].clone()))
        };
        let link = |app: &mut App| {
            let rec = ask(app, "records", json!({ "target": 0, "q": format!("0x{:04x}", key.id) }));
            let s = rec["rows"].as_array().unwrap().iter().find(|r| r["setting"]["key"] == key.key.as_str()).unwrap()["setting"].clone();
            (s["open_tab"].as_str().unwrap().to_string(), s["open_group"].as_str().unwrap().to_string())
        };
        let (g, layout) = on_page(&mut app, "Setup").expect("on Setup's page as on the camera");
        assert_eq!(g, group);
        let at = layout.as_array().unwrap().iter().position(|l| l["key"] == key.key.as_str()).unwrap();
        assert_eq!((&layout[at]["depth"], &layout[at - 1]["head"]), (&json!(1), &json!(key.row[0])), "under its row");
        assert!(on_page(&mut app, &key.tab).is_none(), "not on its own tab's page too");
        assert_eq!(link(&mut app), ("Setup".to_string(), group));
        ask(&mut app, "prefs", json!({ "name": "flat_list", "value": true }));
        assert_eq!(on_page(&mut app, &key.tab).map(|x| x.0), Some(key.group.clone()));
        assert!(on_page(&mut app, "Setup").is_none());
        assert_eq!(link(&mut app), (key.tab.clone(), key.group.clone()));
        app.set_flat_list(false);
    }

    /// The sample from the welcome page, the Edit history with a Revert per record, the Backups window's copies
    /// (opened only from its list) and the recent files.
    #[test]
    fn backups_history_sample_recent() {
        let mut app = App::new(vec![], Prefs::default());
        assert_eq!(answer(&mut app, "history", json!({})).status, 409);
        ask(&mut app, "sample", json!({}));
        assert_eq!(ask(&mut app, "state", json!({}))["file"]["source"], "sample");
        let (st, cur, other) = changeable(&app);
        ask(&mut app, "set", json!({ "target": 0, "key": st.key, "value": other }));
        assert_eq!(ask(&mut app, "state", json!({}))["history"], 1);
        let h = ask(&mut app, "history", json!({}));
        let steps = h["steps"].as_array().unwrap();
        assert!(!steps.is_empty() && steps.iter().all(|x| x["step"] == 0 && x["before"] != x["after"]));
        let mine = steps.iter().find(|x| x["id"] == st.id && x["section"] == 0).expect("the edit's record");
        assert!(mine["after"].as_str().unwrap().ends_with(&format!("[{other}]")));
        assert_eq!(answer(&mut app, "revert_history", json!({ "step": 9, "section": 0, "id": st.id })).status, 400);
        ask(&mut app, "revert_history", json!({ "step": 0, "section": 0, "id": st.id }));
        assert_eq!(app.doc.as_ref().unwrap().value(0, st.slot()), Some(cur));
        assert_eq!(app.undo.len(), 2, "a revert is an edit of its own");
        // a file on disk (a recent one), opened: the editor keeps a copy of it as first opened, which the Backups
        // window lists and opens; a path the list does not hold is refused
        let dir = std::env::temp_dir().join(format!("camset_web_test_files_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let mut c = test_parse(include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT")).unwrap();
        let free = c.sections[0].records.iter().find(|r| r.elem_size == 1 && r.count == 1 && app.schema.find(false, r.id).is_none()).unwrap().id;
        c.sections[0].get_mut(free).unwrap().put(None, 77).unwrap();
        let file = dir.join("WEBTEST1.DAT");
        std::fs::write(&file, c.to_bytes()).unwrap();
        app.prefs.recent = vec![file.display().to_string()];
        assert_eq!(answer(&mut app, "open_recent", json!({ "index": 99 })).status, 400);
        ask(&mut app, "open_recent", json!({ "index": 0 }));
        assert_eq!(app.doc.as_ref().unwrap().path, file);
        let b = ask(&mut app, "backups", json!({}));
        assert_eq!(b["dirs"]["originals"], shown_path(&App::originals_dir()).as_str());
        let list = b["list"].as_array().unwrap();
        let kinds = ["Original, as first opened", "Camera, just before a write", "Camera, read back after a write", "Written to the camera", "Camera, read"];
        assert!(list.iter().all(|x| kinds.contains(&x["kind"].as_str().unwrap())));
        let kept = list.iter().find(|x| x["name"].as_str().unwrap().starts_with("WEBTEST1_")).expect("the copy kept on opening").clone();
        assert_eq!((&kept["kind"], &kept["folder"]), (&json!("Original, as first opened"), &json!("originals")));
        assert!(list.iter().all(|x| x.get("path").is_none() && ["originals", "camera"].contains(&x["folder"].as_str().unwrap())), "no folder of this computer in the list");
        let name = kept["name"].as_str().unwrap();
        for bad in [json!({ "path": file.to_str().unwrap() }), json!({}), json!({ "index": 9999 }), json!({ "folder": "originals" }),
            json!({ "folder": "originals", "name": 7 }), json!({ "folder": "originals", "name": "WEBTEST1.DAT" }), json!({ "folder": "camera", "name": name }),
            json!({ "folder": "..", "name": name }), json!({ "folder": "originals", "name": format!("../originals/{name}") })] {
            assert_eq!(answer(&mut app, "open_backup", bad.clone()).status, 400, "{bad}");
        }
        // a page older than the editor (a place in the list and a name, no folder) is asked to reload
        let old = answer(&mut app, "open_backup", json!({ "index": 0, "name": name }));
        assert!(old.status == 400 && String::from_utf8_lossy(&old.body).contains("reload the page"), "{}", String::from_utf8_lossy(&old.body));
        // since the list was shown, a copy of the same name kept in the camera folder (by a read, or by another test of
        // this run: the editor's folders are the whole run's), newer, so at the top: the copy shown moved down and its
        // name is in the list twice. Each opens from the folder named, never the other folder's
        /// A file this test put in the editor's folders, removed however the test ends.
        struct RemovedAtEnd(PathBuf);
        impl Drop for RemovedAtEnd {
            fn drop(&mut self) {
                let _ = std::fs::remove_file(&self.0);
            }
        }
        std::fs::create_dir_all(App::camera_dir()).unwrap();
        let twin = App::camera_dir().join(name);
        std::fs::write(&twin, c.to_bytes()).unwrap();
        let _twin = RemovedAtEnd(twin.clone());
        let later = std::time::SystemTime::now() + std::time::Duration::from_secs(3600);
        std::fs::File::options().write(true).open(&twin).unwrap().set_modified(later).unwrap();
        let now = App::list_backups();
        let at = |folder: &str| now.iter().position(|b| b.folder == folder && b.path.file_name().is_some_and(|f| f.to_string_lossy() == name));
        assert!(at("camera").is_some_and(|t| at("originals").is_some_and(|k| t < k)), "the twin above the copy: {:?} {:?}", at("camera"), at("originals"));
        ask(&mut app, "open_backup", json!({ "folder": "camera", "name": name }));
        assert_eq!(app.doc.as_ref().unwrap().path, twin);
        ask(&mut app, "open_backup", json!({ "folder": kept["folder"], "name": name }));
        assert_eq!(app.doc.as_ref().unwrap().path, App::originals_dir().join(name));
        let s = ask(&mut app, "state", json!({}));
        assert_eq!(s["file"]["name"], kept["name"]);
        assert_eq!(s["recent"][0]["name"], kept["name"], "the copy opened is now the latest recent file");
        // the state names files, never the folders they are in
        assert!(s["file"].get("path").is_none() && s["recent"][0]["path"] == kept["name"]);
        ask(&mut app, "clear_recent", json!({}));
        assert!(app.prefs.recent.is_empty());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The copy the page names (its folder and its name) out of the list as it is now: found wherever it moved, the copy
    /// of that name in the other folder never taken for it; a page older than the editor (no folder) asked to reload; no
    /// name, or a name or folder the list does not hold, refused; two names in one folder that read the same as text
    /// refused rather than either opened.
    #[test]
    fn a_copy_named_from_the_page_is_found_where_it_is_now() {
        let (o, c) = ("originals", "camera");
        let list = |names: &[(&'static str, &str)]| names.iter().map(|&(d, n)| Backup { when: String::new(), kind: "", folder: d, path: Path::new(d).join(n) }).collect::<Vec<_>>();
        let pick = |l: Vec<Backup>, folder: Option<&str>, name: Option<&str>| App::listed_backup(l, folder, name).map(|b| b.path).map_err(|e| e.status);
        let (ob, cb) = (Path::new(o).join("B.DAT"), Path::new(c).join("B.DAT"));
        // shown as B (originals), A, B (camera): each B from its own folder
        let shown = [(o, "B.DAT"), (o, "A.DAT"), (c, "B.DAT")];
        assert_eq!(pick(list(&shown), Some(o), Some("B.DAT")), Ok(ob.clone()));
        assert_eq!(pick(list(&shown), Some(c), Some("B.DAT")), Ok(cb.clone()));
        // since, a read put N at the top and the camera's B is gone: the page's first row is the second now, and the only
        // B left is the other folder's, which is not the one asked for
        let now = [(c, "N.DAT"), (o, "B.DAT"), (o, "A.DAT")];
        assert_eq!(pick(list(&now), Some(o), Some("B.DAT")), Ok(ob.clone()));
        assert_eq!(pick(list(&now), Some(c), Some("B.DAT")), Err(400), "the camera's B is gone");
        // a B kept in the camera folder since, at the top: the originals' B moved down, still the one asked for
        let twin = [(c, "B.DAT"), (o, "B.DAT"), (o, "A.DAT")];
        assert_eq!(pick(list(&twin), Some(o), Some("B.DAT")), Ok(ob.clone()));
        assert_eq!(pick(list(&twin), Some(c), Some("B.DAT")), Ok(cb.clone()));
        for (folder, name) in [(Some(o), None), (None, None), (Some("elsewhere"), Some("A.DAT")), (Some(c), Some("A.DAT")), (Some(o), Some("Z.DAT")), (Some(o), Some("originals/A.DAT"))] {
            assert_eq!(pick(list(&now), folder, name), Err(400), "{folder:?} {name:?}");
        }
        let old = App::listed_backup(list(&now), None, Some("A.DAT")).err().unwrap();
        assert!(old.status == 400 && String::from_utf8_lossy(&old.body).contains("reload the page"), "a page older than the editor names no folder");
        // names that are not valid Unicode read alike as text: one alone opens, two are refused
        #[cfg(unix)]
        {
            use std::os::unix::ffi::OsStrExt;
            let odd_name = |b: &[u8]| Path::new(o).join(std::ffi::OsStr::from_bytes(b));
            let odd = |b: &[u8]| Backup { when: String::new(), kind: "", folder: o, path: odd_name(b) };
            assert_eq!(pick(vec![odd(b"B\xff.DAT")], Some(o), Some("B\u{fffd}.DAT")), Ok(odd_name(b"B\xff.DAT")));
            assert_eq!(pick(vec![odd(b"B\xff.DAT"), odd(b"B\xfe.DAT")], Some(o), Some("B\u{fffd}.DAT")), Err(409));
        }
    }

    /// Export CSV as a download: Edit mode's set, one line per setting shown (the page's search and Only edited
    /// apply), or the columns of a comparison; Export layout; Edit anyway only for a file that needs it.
    #[test]
    fn csv_and_layout_downloads() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let a = answer(&mut app, "csv", json!({ "target": 0 }));
        assert_eq!((a.status, a.content_type), (200, "text/csv"));
        assert!(a.download.as_deref().unwrap().ends_with("_live_settings.csv"));
        let text = String::from_utf8(a.body).unwrap();
        assert!(text.starts_with("\u{feff}Tab,Group,Setting,Record,Value,Raw,Original,Note\n"));
        let (want, n) = app.csv_text(None, 0, "", None, false);
        assert_eq!(text, want);
        let mut seen = std::collections::HashSet::new();
        assert_eq!(n, app.settings_in(0, None).filter(|s| seen.insert((s.tab.clone(), s.name.clone()))).count(), "one line per setting shown");
        assert_eq!(text.matches("\n\"").count(), n);
        let word = app.schema.settings[0].name.split(' ').next().unwrap().to_string();
        let some = String::from_utf8(answer(&mut app, "csv", json!({ "target": 0, "q": word })).body).unwrap();
        assert!(some.matches("\n\"").count() < n);
        let edited = String::from_utf8(answer(&mut app, "csv", json!({ "target": 0, "only": true })).body).unwrap();
        assert_eq!(edited.matches("\n\"").count(), 0, "nothing edited yet");
        // a comparison: the columns given, each open and shown
        assert_eq!(answer(&mut app, "csv", json!({ "compare": true, "cols": [["a", 0]] })).status, 400);
        assert_eq!(answer(&mut app, "csv", json!({ "compare": true, "cols": [["a", 0], ["b", 0]] })).status, 400);
        if let Some(&m) = app.dial_sets().first() {
            let c = answer(&mut app, "csv", json!({ "compare": true, "cols": [["a", 0], ["a", m]], "only_diff": false }));
            assert!(c.download.as_deref().unwrap().ends_with("_compare.csv"));
            let t = String::from_utf8(c.body).unwrap();
            assert_eq!(t, app.csv_text(Some((&[Col::a(0), Col::a(m)], false, app.show_raw)), 0, "", None, false).0);
            assert_eq!(t.matches("\n\"").count(), app.matrix_rows_for("", None).len());
        }
        let l = answer(&mut app, "layout", json!({}));
        assert_eq!(l.status, 200);
        let j: Value = serde_json::from_slice(&l.body).unwrap();
        assert_eq!(j["signature"], app.doc.as_ref().unwrap().signature.as_str());
        assert_eq!(answer(&mut app, "layout", json!({ "src": "b" })).status, 409);
        // Edit anyway is turned on in the desktop app only: the page has no request for it, and says where it is for a
        // file that needs it
        assert_eq!(answer(&mut app, "edit_anyway", json!({})).status, 404);
        app.doc.as_mut().unwrap().signature = "unchecked".into();
        let f = ask(&mut app, "state", json!({}))["file"].clone();
        assert_eq!((&f["editable"], &f["edit_anyway_in_desktop"]), (&json!(false), &json!(true)));
        assert!(f.get("can_edit_anyway").is_none() && f.get("unchecked").is_none(), "nothing the page has no window for");
        assert!(!app.doc.as_ref().unwrap().unchecked_ok && !app.editable(), "still view only");
        app.doc.as_mut().unwrap().unchecked_ok = true;   // Edit anyway, in the desktop app
        let f = ask(&mut app, "state", json!({}))["file"].clone();
        assert_eq!((&f["editable"], &f["edit_anyway_in_desktop"]), (&json!(true), &json!(false)));
    }

    /// One record put back from the page's record map: a record of the file, as it was opened. A number past the
    /// record numbers, or a request that names no set or no record, is refused, never taken for another record.
    #[test]
    fn revert_record_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (s, v) = crate::write::safety_tests::changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!(app.unsaved(), 1);
        let wrapped = u64::from(s.id) + 65536;
        assert_eq!(answer(&mut app, "revert_record", json!({ "section": 0, "id": wrapped })).status, 400, "0x{wrapped:x} is no record");
        assert_eq!(answer(&mut app, "revert_record", json!({ "id": s.id })).status, 400, "no set named");
        assert_eq!(answer(&mut app, "revert_record", json!({ "section": 0 })).status, 400, "no record named");
        assert_eq!(answer(&mut app, "revert_record", json!({ "section": 99, "id": s.id })).status, 400, "a set the file does not hold");
        assert_eq!(app.unsaved(), 1, "nothing put back by a refused request");
        assert_eq!(answer(&mut app, "revert_record", json!({ "section": 0, "id": s.id })).status, 200);
        assert_eq!(app.unsaved(), 0);
    }

    /// All edits as the window lists them: each value with the number it is stored as.
    #[test]
    fn all_edits_with_their_numbers() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (st, cur, other) = changeable(&app);
        ask(&mut app, "set", json!({ "target": 0, "key": st.key, "value": other }));
        let c = ask(&mut app, "changes", json!({}));
        let row = c["changes"].as_array().unwrap().iter().find(|x| x["id"] == st.id && x["section"] == 0).unwrap().clone();
        assert_eq!(row["was"], format!("{} [{cur}]", st.label_for(cur).unwrap()).as_str());
        assert_eq!(row["now"], format!("{} [{other}]", st.label_for(other).unwrap()).as_str());
        assert_eq!((&row["was_raw"], &row["now_raw"]), (&json!(cur.to_string()), &json!(other.to_string())));
    }

    /// My Menu from a row: added to the first page with room, shown on the row, removed again; a setting the
    /// camera's My Menu cannot hold is refused.
    #[test]
    fn mymenu_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        if app.mymenu_pages().is_none() {
            return;
        }
        // make room when the sample's My Menu is full
        let held = app.schema.settings.iter().find(|s| s.area == "global" && s.menu_code.is_some_and(|c| app.mymenu_find(c).is_some())).cloned();
        if let Some(h) = held {
            ask(&mut app, "mymenu", json!({ "key": h.key, "add": false }));
            assert!(app.mymenu_find(h.menu_code.unwrap()).is_none());
        }
        let s = app.schema.settings.iter().find(|s| s.area == "global" && s.menu_code.is_some_and(|c| app.mymenu_find(c).is_none())).cloned().unwrap();
        let code = s.menu_code.unwrap();
        let r = ask(&mut app, "mymenu", json!({ "key": s.key, "add": true }));
        assert!(r["message"].as_str().unwrap().starts_with("Added to My Menu"));
        let (page, item) = app.mymenu_find(code).unwrap();
        let row = tab_rows(&mut app, &s.tab).into_iter().find(|r| r["key"] == s.key.as_str()).unwrap();
        assert_eq!((&row["mymenu_on"], &row["menu_code"]), (&json!(true), &json!(true)));
        assert_eq!(row["mymenu"], json!({ "page": page + 1, "item": item + 1 }));
        assert_eq!(answer(&mut app, "mymenu", json!({ "key": s.key, "add": true })).status, 400, "already there");
        ask(&mut app, "mymenu", json!({ "key": s.key, "add": false }));
        assert!(app.mymenu_find(code).is_none());
        if let Some(none) = app.schema.settings.iter().find(|s| s.area == "global" && s.menu_code.is_none()).cloned() {
            assert_eq!(answer(&mut app, "mymenu", json!({ "key": none.key, "add": true })).status, 400);
            let row = tab_rows(&mut app, &none.tab).into_iter().find(|r| r["key"] == none.key.as_str());
            assert!(row.is_none_or(|r| r["mymenu_why"].as_str().is_some_and(|w| !w.is_empty())));
        }
        assert_eq!(answer(&mut app, "mymenu", json!({ "key": "no_such_key", "add": true })).status, 404);
    }

    /// The My Menu page as the window's: its entry under Main with the places that hold an item, each page's places
    /// with the item's name and the setting it opens; an item moved and taken out from its place (refused for a place
    /// the page showed holding another item); the settings of My Menu's own tab as rows of the live settings, with a
    /// note, while a memory is edited. Every setting the page's Menu shows is reachable from an entry of it, and
    /// without My Menu in the definition its tab's settings are under Other.
    #[test]
    fn mymenu_page_as_the_window_has_it() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let name = app.schema.camera.text.my_menu_name().to_string();
        // two items at the top of the first page (added when the sample holds fewer), taken as the file opened
        while app.mymenu_pages().unwrap()[0].iter().filter(|&&c| c != mm.empty).count() < 2 {
            let code = app.schema.settings.iter().filter_map(|s| s.menu_code).find(|&c| app.mymenu_find(c).is_none()).unwrap();
            let (acts, _) = app.mymenu_add(code).unwrap();
            app.apply(acts);
        }
        let doc = app.doc.as_mut().unwrap();
        doc.original = doc.edited.clone();
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        let (label, _) = app.mymenu_entry_words();
        assert_eq!((&s["my_menu"]["name"], &s["my_menu"]["label"]), (&json!(name), &json!(label)));
        assert_eq!(s["routes"][&name], json!({ "page": "mymenu" }));
        assert!(!s["tabs"].as_array().unwrap().contains(&json!(name)));
        let j = ask(&mut app, "mymenu_page", json!({ "target": 0 }));
        assert!(j["memory"].is_null() && j["lead"].as_str().unwrap().contains(&format!("choose Add to {name}")));
        let pages = j["pages"].as_array().unwrap();
        assert_eq!(pages.len(), mm.records.len());
        assert_eq!(pages[0]["name"], format!("{name} 1").as_str());
        let places = app.mymenu_places().unwrap();
        for (pg, ours) in pages.iter().zip(&places) {
            let shown = pg["places"].as_array().unwrap();
            assert_eq!(shown.len(), ours.len());
            for (x, o) in shown.iter().zip(ours) {
                assert_eq!((&x["code"], &x["name"], &x["empty"]), (&json!(o.code), &json!(o.name), &json!(o.empty)));
                match o.settings.first() {
                    Some(set) => assert_eq!((&x["opens"]["key"], &x["opens"]["tab"]), (&json!(set.key), &json!(set.tab))),
                    None => assert!(x["opens"].is_null()),
                }
                assert_eq!(x["more"].as_array().unwrap().len(), o.settings.len().saturating_sub(1));
            }
        }
        // the first item moved down, then taken out; a place the page showed holding another item is refused
        let (a, b) = (places[0][0].code, places[0][1].code);
        assert_eq!(pages[0]["places"][0]["up"], false);
        let r = ask(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": a, "do": "down" }));
        assert!(r["message"].as_str().unwrap().starts_with(&format!("Moved to {name} page 1, item 2")));
        assert_eq!(&app.mymenu_pages().unwrap()[0][..2], &[b, a]);
        let x = &ask(&mut app, "mymenu_page", json!({}))["pages"][0]["places"][0];
        assert_eq!((&x["code"], &x["edited"], &x["was"]), (&json!(b), &json!(true), &json!(places[0][0].name)));
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": a, "do": "remove" })).status, 409, "the page showed another item there");
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": b, "do": "up" })).status, 400, "the first item does not move up");
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 99, "item": 0, "code": b, "do": "remove" })).status, 409);
        ask(&mut app, "mymenu_slot", json!({ "page": 0, "item": 1, "code": a, "do": "remove" }));
        assert!(app.mymenu_find(a).is_none());
        // My Menu's own tab: rows of the live settings, also while a memory is edited, with the note
        let own = app.settings_in(0, Some(&name)).next().cloned().unwrap();
        let j = ask(&mut app, "mymenu_page", json!({ "target": 1 }));
        assert!(j["memory"].as_str().unwrap().starts_with(&format!("{name} is part of the live settings")));
        let rows: Vec<&Value> = j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap()).collect();
        let row = rows.iter().find(|r| r["key"] == own.key.as_str()).unwrap();
        assert_eq!(row["target"], 0);
        // every setting the Menu shows has an entry that lists it: a tab of `tabs`, a route to one, or the My Menu page
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        let tabs: Vec<&str> = s["tabs"].as_array().unwrap().iter().map(|t| t.as_str().unwrap()).collect();
        let keys: Vec<&str> = rows.iter().map(|r| r["key"].as_str().unwrap()).collect();
        for x in app.settings_in(0, None) {
            // the entry that shows it (`entry_of`: the one for what the menus do not hold, as on the camera, else its tab's)
            let e = app.entry_of(x);
            match tabs.iter().find(|t| **t == e).copied().or_else(|| s["routes"][&e]["tab"].as_str()) {
                Some(t) => assert!(tabs.contains(&t) && app.settings_in(0, Some(t)).any(|o| o.key == x.key), "{} is under no tab", x.name),
                None => assert!(s["routes"][&e]["page"] == "mymenu" && keys.contains(&x.key.as_str()), "{} is on no page", x.name),
            }
        }
        // a definition without My Menu: no entry, no page, its tab's settings under Other
        app.schema.camera.my_menu = None;
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        assert!(s["my_menu"].is_null());
        assert_eq!(s["routes"][&name], json!({ "page": "tab", "tab": OTHER_TAB }));
        assert!(s["tabs"].as_array().unwrap().contains(&json!(OTHER_TAB)));
        assert!(tab_rows(&mut app, OTHER_TAB).iter().any(|r| r["key"] == own.key.as_str()));
        assert_eq!(answer(&mut app, "mymenu_page", json!({})).status, 409);
    }

    /// The page's My Menu places take any item, as the window's pickers: the page lists every item a place can hold
    /// (with the tab of a setting that carries it and where it is in My Menu), which places have the picker (an item's,
    /// and on a packed page the first empty one), and "set" puts an item in a place by `mymenu_set`'s rules, refused
    /// and said as there; the places are Expert-only, so the page reads them from the records, and their edits count
    /// on My Menu's entry, not on a tab's.
    #[test]
    fn mymenu_places_take_any_item_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let mm = app.schema.camera.my_menu.clone().unwrap();
        let name = app.schema.camera.text.my_menu_name().to_string();
        let empty_page: Vec<Action> = (0..7u16).map(|i| Action::Set(0, (mm.records[0], Some(i)), mm.empty)).collect();
        app.apply(empty_page);
        let doc = app.doc.as_mut().unwrap();
        doc.original = doc.edited.clone();
        let j = ask(&mut app, "mymenu_page", json!({ "target": 0 }));
        let items = j["items"].as_array().unwrap();
        assert_eq!(items.len(), app.mymenu_items().len());
        assert!(items.iter().all(|x| x["code"] != mm.empty && x["name"].as_str().is_some_and(|n| !n.is_empty())));
        assert_eq!(j["excluded"], json!(app.mymenu_excluded_words()));
        let picks: Vec<bool> = j["pages"][0]["places"].as_array().unwrap().iter().map(|x| x["pick"].as_bool().unwrap()).collect();
        assert_eq!(picks, [true, false, false, false, false, false, false], "an empty packed page: its first place only");
        let carried: std::collections::HashSet<i64> = app.schema.settings.iter().filter_map(|s| s.menu_code).collect();
        let free = items.iter().find(|x| !carried.contains(&x["code"].as_i64().unwrap()) && x["in"].is_null()).unwrap();
        let code = free["code"].as_i64().unwrap();
        assert!(free["tab"].is_null());
        // an item no setting carries, into the page's first place: shown by its name, with no setting to open
        let r = ask(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": mm.empty, "do": "set", "to": code }));
        assert!(r["message"].as_str().unwrap().starts_with(&format!("Added {} to {name} page 1, item 1", free["name"].as_str().unwrap())));
        let j = ask(&mut app, "mymenu_page", json!({}));
        let x = &j["pages"][0]["places"][0];
        assert_eq!((&x["code"], &x["name"], &x["edited"], &x["opens"], &x["pick"]), (&json!(code), &free["name"], &json!(true), &Value::Null, &json!(true)));
        assert_eq!(j["pages"][0]["places"][1]["pick"], true, "the next empty place takes the next item");
        assert!(j["items"].as_array().unwrap().iter().any(|x| x["code"] == code && x["in"] == json!({ "page": 1, "item": 1 })));
        // refused, and said: already there, a place the page showed holding another item, no item named
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 0, "item": 1, "code": mm.empty, "do": "set", "to": code })).status, 400);
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": mm.empty, "do": "set", "to": code })).status, 409);
        assert_eq!(answer(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": code, "do": "set" })).status, 400);
        // replaced where it stands
        let other = items.iter().map(|x| x["code"].as_i64().unwrap()).find(|&c| c != code && carried.contains(&c)).unwrap();
        ask(&mut app, "mymenu_slot", json!({ "page": 0, "item": 0, "code": code, "do": "set", "to": other }));
        assert_eq!(&app.mymenu_pages().unwrap()[0][..2], &[other, mm.empty]);
        // its edits count on My Menu's entry, not on the tab of its places
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        assert_eq!(s["my_menu"]["edited"], 1);
        let slot_tab = app.schema.settings.iter().find(|s| s.area == "global" && s.id == mm.records[0]).unwrap().tab.clone();
        assert!(s["tab_info"].as_array().unwrap().iter().all(|t| t["edited"] == 0), "{slot_tab} counts no place");
        // the page's picker asks for it so, and draws the places the editor gives the picker
        assert!(SCRIPT.contains(r#"do: "set", to: code"#) && SCRIPT.contains("x.pick ?") && SCRIPT.contains("j.items.filter"));
    }

    /// The entry for the settings the camera's menus do not hold, on the page as in the window: listed after the tabs
    /// as on the camera, with its hover, its groups named by tab and group, every setting reachable through the
    /// `open_tab` a link carries; the flat list has no such entry, and a page left on it goes to the first tab.
    #[test]
    fn off_menu_entry_on_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let off = app.schema.camera.text.off_menu_name().to_string();
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        let tabs: Vec<&str> = s["tabs"].as_array().unwrap().iter().map(|t| t.as_str().unwrap()).collect();
        assert_eq!(tabs.last(), Some(&off.as_str()));
        let info = s["tab_info"].as_array().unwrap().iter().find(|t| t["name"] == off.as_str()).unwrap();
        assert_eq!(info["title"], App::off_menu_hover());
        let away: Vec<Setting> = app.settings_in(0, Some(&off)).cloned().collect();
        assert!(!away.is_empty() && away.iter().all(|s| app.off_menu(s) && !s.placed()));
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": off }));
        let groups = j["groups"].as_array().unwrap();
        for g in groups {
            let first = away.iter().find(|s| g["rows"][0]["key"] == s.key.as_str()).unwrap();
            assert_eq!((&g["name"], &g["tab"]), (&json!(App::off_group(first)), &json!(first.tab)));
        }
        // a link to one opens that entry, in its group
        let one = away[0].clone();
        app.prefs.expert = true;          // the record map is Expert mode's
        let j = ask(&mut app, "records", json!({ "target": 0, "q": format!("0x{:04x}", one.id) }));
        app.prefs.expert = false;
        let link = j["rows"].as_array().unwrap().iter().find_map(|r| (r["setting"]["key"] == one.key.as_str()).then(|| r["setting"].clone())).unwrap();
        assert_eq!((&link["open_tab"], &link["open_group"]), (&json!(off), &json!(App::off_group(&one))));
        // the flat list: no such entry, every setting in its tab, and a route to the first tab
        app.prefs.flat_list = true;
        let s = ask(&mut app, "state", json!({ "target": 0 }));
        assert!(!s["tabs"].as_array().unwrap().contains(&json!(off)));
        assert_eq!(s["routes"][&off], json!({ "page": "tab", "tab": app.schema.tabs[0] }));
        assert!(tab_rows(&mut app, &one.tab).iter().any(|r| r["key"] == one.key.as_str()));
        assert_eq!(app.entry_of(&one), one.tab);
        // the page's links go by `open_tab`, and the entry's hover is drawn
        assert!(SCRIPT.contains("menuPlace(s.open_tab || s.tab)") && SCRIPT.contains("t.title || undefined"));
    }

    /// The page an option opens (Picture Profile's PP1), as the window's: the owner's row carries `pages` (where each
    /// page is shown, the link's words), the page is a group of its own marked with its option and laid out with its
    /// headings, the family's table stays. Skipped while the definition puts no setting on a page.
    #[test]
    fn an_option_opens_its_page_on_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let Some(own) = app.settings_in(0, None).find(|s| !app.option_pages(s).is_empty()).cloned() else { return };
        let p = app.option_pages(&own)[0].clone();
        let row = app.web_row(0, std::slice::from_ref(&own));
        let first = &row["pages"][0];
        assert_eq!((&first["option"], &first["open_group"], &first["key"]), (&json!(p.option), &json!(p.group), &json!(p.key)));
        assert_eq!(first["words"], json!(format!("Open the {} page", p.option)));
        assert!(row["subs"]["rows"].as_array().into_iter().flatten().all(|r| r["key"] != json!(p.key)), "no box for a page's setting");
        let on = app.schema.settings.iter().find(|s| s.key == p.key).cloned().unwrap();
        let tab = app.layout_tab(&on).to_string();
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": tab }));
        let groups = j["groups"].as_array().unwrap();
        let g = groups.iter().find(|g| g["name"] == p.group.as_str()).expect("the page's group");
        assert_eq!(g["page"], json!(p.option));
        let layout = g["layout"].as_array().expect("laid out as the page");
        assert!(layout.iter().any(|l| l["head"].is_string() && l["depth"] == 0) && layout.iter().all(|l| l["head"] != json!(p.option)));
        assert!(groups.iter().any(|g| g["family"] == true && g["rows"].as_array().unwrap().iter().any(|r| r["key"] == json!(p.key))), "the table keeps it");
        assert!(SCRIPT.contains("function pageLinks(r)") && SCRIPT.contains("r.pages"));
    }

    /// Picture Profiles and Creative Looks as the window's tables: each family one group, first in its tab, a row
    /// per parameter and a column per profile; a change in a cell marks that cell.
    #[test]
    fn families_as_tables() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let Some(f) = app.schema.camera.families.iter().find(|f| !f.prefix.is_empty()).cloned() else { return };
        let Some(tab) = app.settings_in(0, None).find(|s| s.group.starts_with(&f.prefix)).map(|s| s.tab.clone()) else { return };
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": tab }));
        let groups = j["groups"].as_array().unwrap();
        assert_eq!(groups[0]["family"], true, "the families come first, as in the window");
        // as on the camera, the page an option opens (a profile's PP1) is a group too, marked with its option
        assert!(groups.iter().all(|g| g["family"] == true || g["page"].is_string() || !g["name"].as_str().unwrap().starts_with(&f.prefix)), "no group of a family on its own");
        let fam = groups.iter().find(|g| g["name"] == f.title.as_str()).expect("the family as one group").clone();
        let (params, profiles, cells, rows) = (fam["params"].as_array().unwrap(), fam["profiles"].as_array().unwrap(), fam["cells"].as_array().unwrap(), fam["rows"].as_array().unwrap());
        assert_eq!(cells.len(), params.len());
        assert!(!profiles.is_empty() && cells.iter().all(|c| c.as_array().unwrap().len() == profiles.len()));
        let keys: Vec<&Value> = cells.iter().flat_map(|c| c.as_array().unwrap()).filter(|k| !k.is_null()).collect();
        assert_eq!(keys.len(), rows.len(), "each row is one cell");
        for (p, line) in params.iter().zip(cells) {
            for k in line.as_array().unwrap().iter().filter(|k| !k.is_null()) {
                assert_eq!(rows.iter().find(|r| r["key"] == *k).unwrap()["name"], *p);
            }
        }
        let Some(cell) = rows.iter().find(|r| r["editable"] == true && r["kind"] == "choice" && r["options"].as_array().unwrap().len() >= 2).cloned() else { return };
        let other = cell["options"].as_array().unwrap().iter().map(|o| o[0].clone()).find(|v| *v != cell["value"]).unwrap();
        ask(&mut app, "set", json!({ "target": 0, "key": cell["key"], "value": other }));
        let j = ask(&mut app, "tab", json!({ "target": 0, "tab": tab }));
        let fam = j["groups"].as_array().unwrap().iter().find(|g| g["name"] == f.title.as_str()).unwrap().clone();
        let changed: Vec<&Value> = fam["rows"].as_array().unwrap().iter().filter(|r| r["changed"] == true).collect();
        assert!(changed.iter().any(|r| r["key"] == cell["key"]));
        // with it, only the copies the camera keeps of it (`copies`), which follow it
        let copies = app.schema.settings.iter().find(|s| s.key == cell["key"].as_str().unwrap()).map(|s| s.copies.clone()).unwrap_or_default();
        assert!(changed.iter().all(|r| r["key"] == cell["key"] || copies.iter().any(|k| r["key"] == k.as_str())), "{changed:?}");
    }

    /// The camera cards on the page, without a camera: the link and the address, the setup steps with their ticks
    /// and their fold, the 📷 button, and the requests refused for a camera the editor does not know, and a login, which
    /// the page cannot send. (Nothing here searches or reads: those reach the camera helper.)
    #[test]
    fn camera_cards_from_the_page() {
        let mut app = App::new(vec![], Prefs::default());
        let c = ask(&mut app, "state", json!({}))["camera"].clone();
        assert_eq!((&c["link"], &c["button"]["text"]), (&json!(""), &json!("📷 Not set up")), "no camera link program");
        // a program there, never run here: a file of the test's own, as every system has one (Windows has no /bin/sh)
        let dir = crate::definitions::definitions_tests::scratch("web_camera_cards");
        let stand_in = dir.join("not_a_program");
        std::fs::write(&stand_in, "").unwrap();
        app.prefs.probe_path = Some(stand_in.display().to_string());
        app.helper_seen.set(None);
        let c = ask(&mut app, "state", json!({}))["camera"].clone();
        assert_eq!((&c["link"], &c["button"]["text"]), (&json!(""), &json!("📷 Set up the camera…")), "the window's words");
        let c = ask(&mut app, "camera_cards", json!({}))["camera"].clone();
        assert_eq!(c["checks"].as_array().unwrap().len(), c["steps"].as_array().unwrap().len());
        assert_eq!(c["steps_open"], true, "no camera known and none found");
        // a known camera (made up) at an address: the page may choose that address, not a new one
        app.prefs.cameras.push(KnownCamera { model: "ILCE-1M2".into(), mac: "02:00:00:00:00:01".into(), ip: "192.0.2.10".into(), serial: "TEST0001".into(),
            link: "network".into(), last_seen: "20260101_120000".into(), ..Default::default() });
        let r = ask(&mut app, "camera_link", json!({ "link": "network", "ip": "192.0.2.10" }));
        assert_eq!((app.prefs.link.as_str(), app.prefs.camera_ip.as_str()), ("network", "192.0.2.10"));
        assert_eq!(r["camera"]["button"]["text"], "📷 Network 192.0.2.10", "every camera request answers with the cards");
        assert_eq!(answer(&mut app, "camera_link", json!({ "link": "network", "ip": "192.0.2.99" })).status, 409, "an address typed on the page");
        assert_eq!(app.prefs.camera_ip, "192.0.2.10");
        // the state, asked every few seconds, names no address, serial number or MAC address; the cards do
        let s = ask(&mut app, "state", json!({}));
        assert_eq!(s["camera"]["button"]["text"], "📷 Network");
        assert_eq!(s["link"]["text"], "Network");
        for secret in ["192.0.2.10", "02:00:00:00:00:01", "TEST0001"] {
            assert!(!s.to_string().contains(secret), "the state carries {secret}");
        }
        // nor this computer's home folder (which names its user): the editor's own (%USERPROFILE% on Windows, where
        // $HOME is seldom set), as the state's JSON writes it (each "\" of a Windows path doubled)
        let home = home_folder().display().to_string();
        let written = serde_json::to_string(&home).unwrap();
        let written = written.trim_matches('"');
        assert!(home.len() < 2 || !s.to_string().contains(written), "the state names {home}");
        let c = ask(&mut app, "camera_cards", json!({}))["camera"].clone();
        assert_eq!((&c["ip"], &c["known"][0]["serial"]), (&json!("192.0.2.10"), &json!("TEST0001")));
        assert_eq!(c["steps"], json!(app.setup_steps().0));
        // whether a login is saved, in words; never where
        let note = c["credentials_note"].as_str().unwrap();
        assert!(!note.contains(".config") && !note.contains("network.json"), "{note}");
        assert!(c["login_saved"].is_boolean());
        assert_eq!(ask(&mut app, "camera_check", json!({ "index": 0, "value": true }))["camera"]["checks"][0], true);
        assert_eq!(answer(&mut app, "camera_check", json!({ "index": 99, "value": true })).status, 400);
        assert_eq!(ask(&mut app, "camera_steps", json!({ "open": false }))["camera"]["steps_open"], false);
        ask(&mut app, "camera_link", json!({ "link": "usb" }));
        assert!(app.connect_checks.is_empty(), "another link: its own steps, none ticked");
        assert_eq!(answer(&mut app, "camera_link", json!({ "link": "pigeon" })).status, 400);
        assert_eq!(answer(&mut app, "camera_link", json!({ "link": "network", "ip": "192.0.2.1; x" })).status, 400);
        // named and taken off the list from the page (its login and the trust in it stay: the desktop app's Forget)
        app.prefs.cameras[0].link = "usb".into();
        ask(&mut app, "camera_name", json!({ "known": 0, "name": "Test body" }));
        assert_eq!(app.prefs.cameras[0].name, "Test body");
        assert_eq!(ask(&mut app, "camera_cards", json!({}))["camera"]["known"][0]["name"], "Test body");
        assert_eq!(ask(&mut app, "state", json!({}))["read_sub"], "Test body over USB. Usually about 5 seconds.");
        // once this computer has timed reads over the link: their median, in the card, the Read button's hover and
        // the Write window's line, as the window says it
        for s in [8.3, 9.4, 9.8] { app.prefs.note_read("usb", s); }
        let s = ask(&mut app, "state", json!({}));
        assert_eq!((s["read_sub"].as_str(), s["read_time"].as_str()), (Some("Test body over USB. Usually about 9 seconds."), Some("9 seconds")));
        assert_eq!(s["read_tip"], "Read the camera's current settings over USB or the network (usually about 9 seconds)");
        app.prefs.read_times.clear();
        // the search's hover says what its progress line says
        assert_eq!(ask(&mut app, "camera_cards", json!({}))["camera"]["search_tip"], search_tip());
        assert!(search_tip().ends_with(&format!("(about {SEARCH_TIME})")));
        ask(&mut app, "camera_forget", json!({ "index": 0 }));
        assert!(app.prefs.cameras.is_empty());
        assert!(app.status.contains("taken off the list"), "{}", app.status);
        assert_eq!(ask(&mut app, "state", json!({}))["read_sub"], "Over USB or the network. Usually about 5 seconds.");
        for (name, body) in [("camera_use", json!({ "index": 0 })), ("camera_forget", json!({ "index": 0 })), ("camera_name", json!({ "found": 0, "name": "x" })),
                             ("camera_name", json!({ "name": "x" }))] {
            assert_eq!(answer(&mut app, name, body).status, 400, "{name}");
        }
        // the camera's login is entered in the desktop app only: the page has no request that takes one
        assert_ne!(answer(&mut app, "camera_login", json!({ "user": "u", "password": "p" })).status, 200);
        assert!(app.net_user.is_empty() && app.net_pass.is_empty());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The report window as the window has it: the camera link's own words only in Expert mode and only on request
    /// (else a line saying where they are), and the ways on it offers; what only the desktop app does (the login,
    /// forgetting a camera so it is trusted again) in a line of its own, with no button.
    #[test]
    fn report_as_the_window_has_it() {
        let mut app = App::new(vec![], Prefs::default());
        app.camera_report = Some(CameraReport { title: "✖ Test".into(), ok: false, lines: vec![("A line.".into(), true)],
            probe: "cause: credentials_rejected\nmac: 02:00:00:00:00:01\n".into(), retry: None, offer_usb: true, put_back: false });
        let r = ask(&mut app, "state", json!({}))["report"].clone();
        assert_eq!((r.get("probe"), &r["note"], &r["has_probe"]), (None, &json!(EXPERT_LINK_NOTE), &json!(false)));
        assert_eq!((&r["offer_usb"], &r["in_desktop"]), (&json!(true), &json!(WEB_LOGIN_IN_DESKTOP)));
        assert_eq!(r["lines"][1][0], WEB_LOGIN_IN_DESKTOP);
        assert_eq!(answer(&mut app, "camera_report", json!({})).status, 409, "the link's words are Expert mode's");
        app.prefs.expert = true;   // set in the desktop app
        let s = ask(&mut app, "state", json!({}));
        assert_eq!((s["report"].get("probe"), &s["report"]["has_probe"]), (None, &json!(true)));
        assert!(!s.to_string().contains("02:00:00:00:00:01"), "the state carries the link's words");
        assert_eq!(ask(&mut app, "camera_report", json!({}))["probe"], "cause: credentials_rejected\nmac: 02:00:00:00:00:01");
        app.camera_report.as_mut().unwrap().probe = "cause: camera_changed\n".into();
        assert_eq!(ask(&mut app, "state", json!({}))["report"]["in_desktop"], WEB_FORGET_IN_DESKTOP);
        ask(&mut app, "dismiss", json!({}));
        assert!(app.camera_report.is_none());
    }

    /// The files sent up from the page are kept for the latest twenty; one open now stays whatever its age.
    #[test]
    fn uploads_kept_for_the_latest() {
        let dir = std::env::temp_dir().join(format!("camset_uploads_test_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let sample = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");
        let files: Vec<PathBuf> = (0..WEB_UPLOADS_KEPT + 5).map(|i| {
            let p = dir.join(format!("20260101_0000{i:02}_T.DAT"));
            std::fs::write(&p, sample).unwrap();
            p
        }).collect();
        let mut app = App::new(vec![], Prefs::default());
        app.open(files[1].clone());
        app.prune_uploads(&dir, files.last().unwrap());
        let left: Vec<PathBuf> = files.iter().filter(|p| p.exists()).cloned().collect();
        assert_eq!(left.len(), WEB_UPLOADS_KEPT + 1, "the latest, and the one open");
        assert!(files[1].exists() && !files[0].exists() && files.last().unwrap().exists());
        // W-17: each upload in a folder of its own; a folder holding a file open stays, the older ones go whole
        let folders: Vec<PathBuf> = (0..WEB_UPLOADS_KEPT + 3).map(|i| {
            let d = dir.join(format!("2026-01-02_00-00-{i:02}"));
            std::fs::create_dir_all(&d).unwrap();
            std::fs::write(d.join("CAMSET01.DAT"), sample).unwrap();
            std::thread::sleep(std::time::Duration::from_millis(5));
            d
        }).collect();
        app.open(folders[0].join("CAMSET01.DAT"));
        app.prune_uploads(&dir, &folders.last().unwrap().join("CAMSET01.DAT"));
        assert!(folders[0].join("CAMSET01.DAT").exists(), "open now");
        assert!(!folders[1].exists() && folders.last().unwrap().join("CAMSET01.DAT").exists());
        let left = std::fs::read_dir(&dir).unwrap().count();
        assert_eq!(left, WEB_UPLOADS_KEPT + 1);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Values the camera's menus never offer (`not_offered`): the page offers none of them, even while it offers the
    /// values no proof established, and refuses one sent as a change; it lists the one the file holds now, saying
    /// why on its hover. A held one (the factory value) stays offered. The row carries the window's lines
    /// (`not_offered_lines`: the menu on the hover), which the page shows under the
    /// setting and in Compare's in-place choice, as the window does.
    #[test]
    fn values_the_menus_never_offer_are_left_out_and_said() {
        use camset_editor::schema::NotOffered;
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (st, cur, other) = changeable(&app);
        let held = st.values.iter().map(|(v, _)| *v).find(|v| *v != cur && *v != other).expect("a third value");
        let mark = |value, label: &str, why: &str, held| NotOffered { value, label: label.into(), why: why.into(), menu: "Some Menu".into(), held };
        for s in app.schema.settings.iter_mut().filter(|s| s.key == st.key) {
            s.not_offered = vec![mark(other, "Other", "Not on its list.", false), mark(held, "Held", "The factory value.", true)];
        }
        app.allow_unobserved = true;
        let row = |app: &mut App| { let linked = app.web_linked(0, &st.key).unwrap(); app.web_row(0, &linked) };
        let r = row(&mut app);
        let offered: Vec<i64> = r["options"].as_array().unwrap().iter().map(|o| o[0].as_i64().unwrap()).collect();
        assert!(!offered.contains(&other), "never offered, though every value no file has held is asked for: {offered:?}");
        assert!(offered.contains(&held) && offered.contains(&cur), "{offered:?}");
        assert_eq!(r["not_offered"], json!([{ "text": "Not on the camera's list: Other. Not on its list.", "title": "In Some Menu" },
                                            { "text": "Held: The factory value.", "title": "In Some Menu" }]));
        let refused = answer(&mut app, "set", json!({ "target": 0, "key": st.key, "value": other }));
        assert_eq!((refused.status, &body(&refused)["error"]), (400, &json!("Not a value this setting offers.")));
        // the file holds it now (an edit made elsewhere): listed as the value held now, with no "not checked" beside it
        // (null: the window draws no mark either), why on its hover
        let linked = app.web_linked(0, &st.key).unwrap();
        app.apply(App::set_linked(0, &linked, other));
        let r = row(&mut app);
        let o = r["options"].as_array().unwrap().iter().find(|o| o[0] == json!(other)).expect("the value held now is listed").clone();
        assert_eq!(o[2], Value::Null, "neither established nor not: the menus never offer it");
        assert!(o[3].as_str().unwrap().contains("The camera's menus never offer this value: Not on its list."), "{o}");
        assert!(!o[3].as_str().unwrap().contains(UNPROVED_HOVER), "its hover gives the menus' reason, not the gate's: {o}");
        assert!(SCRIPT.contains("optionWords(r, v, label, seen === false && v !== r.value, help)")
            && SCRIPT.contains("seen === false && v !== e.value ? `${label} (not checked)` : label"),
            "the page marks only a value not checked on the camera that is not the value held now, so a null (never offered) gets no mark");
        app.prefs.expert = true;
        assert_eq!(row(&mut app)["not_offered"][0]["title"], json!("In Some Menu"), "what showed it is the mapping's evidence, in no definition");
        assert!(SCRIPT.contains("r.not_offered || []") && SCRIPT.contains("j.row.not_offered || []"), "the page shows them in the detail and in Compare's choice");
    }

    /// The page's gate outside Expert mode is the window's (`Setting::established`, read from the proofs): on every list
    /// setting of the sample, the page offers what the window offers (`offered`), each option's flag says whether a
    /// proof established it, its hover says the camera may refuse a file holding one that is not, and the hidden count
    /// is the window's; "Offer values…" brings the rest back on both. The shipped definition holds back values no
    /// proof established in proved settings (the Fn Menu's functions no slot proved), and nothing in unproved ones.
    #[test]
    fn the_page_offers_what_a_proof_established_as_the_window_does() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let keys: Vec<String> = app.settings_in(0, None).filter(|s| s.range.is_none() && s.values.len() >= 2).map(|s| s.key.clone()).collect();
        let (mut held_back, mut unproved_rows) = (0, 0);
        for all in [false, true] {
            app.allow_unobserved = all;
            for key in &keys {
                let Some(linked) = app.web_linked(0, key) else { continue };
                let s = linked[0].clone();
                let r = app.web_row(0, &linked);
                if r["kind"] != "choice" {
                    continue;
                }
                let cur = r["value"].as_i64();
                let page: Vec<i64> = r["options"].as_array().unwrap().iter().filter_map(|o| o[0].as_i64()).filter(|v| Some(*v) != cur).collect();
                // the window offers `offered_values`: the proofs' gate, less another video system's values than the file's
                let window: Vec<i64> = app.offered_values(&s, 0).into_iter().map(|(v, _)| v).filter(|v| Some(*v) != cur).collect();
                assert_eq!(page, window, "{key}: the page offers what the window offers");
                assert_eq!(r["hidden"], json!(s.hidden_unproved(all)), "{key}");
                let words = if s.hidden_unproved(all) > 0 { json!(hidden_words(s.hidden_unproved(all))) } else { Value::Null };
                assert_eq!(r["hidden_words"], words, "{key}: the window's line for the values held back");
                for o in r["options"].as_array().unwrap() {
                    let v = o[0].as_i64().unwrap();
                    if s.never_offered(v).is_none() {
                        assert_eq!(o[2], json!(s.established(v)), "{key} {v}");
                        assert_eq!(o[2] == json!(false), o[3].as_str().is_some_and(|h| h.ends_with(UNPROVED_HOVER)), "{key} {v}: {}", o[3]);
                    }
                }
                if !all {
                    held_back += s.hidden_unproved(false);
                    unproved_rows += usize::from(s.proved.is_none());
                    assert!(s.proved.is_some() || s.hidden_unproved(false) == 0, "{key}: no proof, nothing held back");
                }
            }
        }
        assert!(held_back > 0 && unproved_rows > 0, "the sample has both kinds ({held_back} held back)");
        assert!(SCRIPT.contains("out.push(el(\"div\", { class: \"weak\" }, r.hidden_words))") && SCRIPT.contains("j.row.hidden_words"),
            "the page draws the window's line under the setting and in Compare's in-place choice");
    }

    /// A change answers the rows it changes, the new rev and the edit counts, so the page patches them in place; a
    /// refused one answers 4xx with the reason and the row as it still is, so the page puts its control back.
    #[test]
    fn set_answers_rows_or_the_row_as_it_is() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let (st, cur, other) = changeable(&app);
        let r = ask(&mut app, "set", json!({ "target": 0, "key": st.key, "value": other }));
        assert_eq!((&r["row"]["value"], &r["rows"][0]["key"], &r["edits"], &r["can_undo"]), (&json!(other), &json!(st.key), &json!(app.doc.as_ref().unwrap().changes().len()), &json!(true)));
        assert_eq!(r["rev"], ask(&mut app, "state", json!({}))["rev"], "the rev the state now has");
        let refused = answer(&mut app, "set", json!({ "target": 0, "key": st.key, "value": 999_999 }));
        let b = body(&refused);
        assert_eq!((refused.status, &b["error"], &b["value"], &b["row"]["value"]), (400, &json!("Not a value this setting offers."), &json!(other), &json!(other)));
        // a setting that greys others out: those rows come with the change
        let rule_row = app.settings_in(0, None).find_map(|s| s.inactive_when.clone()).and_then(|rule| {
            let owner = app.settings_in(0, None).find(|o| o.id == rule.record && o.index.is_none() && o.scalar)?.clone();
            Some((rule, owner))
        });
        if let Some((rule, owner)) = rule_row {
            let r = answer(&mut app, "set", json!({ "target": 0, "key": owner.key, "value": rule.unlock }));
            if r.status == 200 {
                let greyed = app.settings_in(0, None).filter(|s| s.inactive_when.as_ref().is_some_and(|w| w.record == rule.record) && s.name != owner.name).count();
                assert!(body(&r)["rows"].as_array().unwrap().len() > usize::from(greyed > 0), "the greyed rows of {}", owner.name);
            }
        }
        ask(&mut app, "set", json!({ "target": 0, "key": st.key, "value": cur }));
    }

    /// The page's status line names no folder of this computer and no address, whatever the window's says.
    #[test]
    fn the_page_status_names_no_folder_or_address() {
        assert_eq!(without_addresses("Read from Studio over LAN 192.168.1.50 at 17:44:02."), "Read from Studio over LAN (its address) at 17:44:02.");
        assert_eq!(without_addresses("at http://192.168.1.20:8642 now"), "at http://(its address) now");
        assert_eq!(without_addresses("MAC 00:11:22:33:44:55, or 00-11-22-33-44-55"), "MAC (its MAC address), or (its MAC address)");
        assert_eq!(without_addresses("firmware 4.00, 2026-11-05, 1.2.3, CAMSET01.DAT"), "firmware 4.00, 2026-11-05, 1.2.3, CAMSET01.DAT");
        let mut app = App::new(vec![], Prefs::default());
        let dir = home_folder().join("Cards").join("CAMSET");
        app.status = format!("Saved as CAMSET02.DAT in {} over LAN 192.168.1.50", dir.display());
        let shown = app.page_status();
        assert!(!shown.contains(&home_folder().display().to_string()) && !shown.contains("192.168"), "{shown}");
        assert!(shown.contains("CAMSET02.DAT") && shown.contains("~"), "{shown}");
        assert_eq!(ask(&mut app, "state", json!({}))["status"], shown.as_str());
        // the page's own address: shown in the desktop app's Settings, and the page's status line says so
        app.status = format!("{WEB_ON} http://192.168.1.20:8642");
        assert_eq!(app.page_status(), WEB_ON_FOR_PAGE);
        assert!(!app.page_status().contains("http"));
    }

    /// The welcome page and Settings > About say what the window's do, word for word: About's lines, links and copied
    /// details come with the state, and the page draws them from there. About is Settings' last tab on the page as in
    /// the window, the same tabs in the same order, and the status bar's version opens Settings on it; there is no
    /// About window of its own, and Settings' foot has no way into About.
    #[test]
    fn the_page_has_the_windows_words() {
        let mut app = App::new(vec![], Prefs::default());
        let st = ask(&mut app, "state", json!({}));
        assert_eq!(st["open_sub"], app.open_hint().as_str());
        assert_eq!(st["not_sony"], NOT_SONY);
        assert!(NOT_SONY.contains("not affiliated with or endorsed by Sony"));
        assert_eq!(st["about"]["details"], app.about_details().as_str());
        assert_eq!(st["about"]["licence"], licence_words().as_str());
        assert_eq!(st["about"]["links"][2]["url"], ISSUES_URL);
        assert!(SCRIPT.contains("const a = s.about || {};") && SCRIPT.contains("(a.links || []).map") && SCRIPT.contains("copyText(a.details)"));
        assert!(SCRIPT.contains("rel: \"noopener noreferrer\""), "the project's pages open in a new tab, told nothing of the page");
        // the tabs the page draws, in the window's order, About the last; the page's SETTINGS_ABOUT is its place (read
        // with LF line ends, as git checks the script out with CRLF on Windows)
        let script = SCRIPT.replace("\r\n", "\n");
        let tabs: Vec<(String, String)> = serde_json::from_value(st["settings_tabs"].clone()).unwrap();
        assert_eq!(tabs, SettingsTab::ALL.iter().map(|t| (t.label().to_string(), t.subtitle().to_string())).collect::<Vec<_>>());
        let about = SettingsTab::ALL.iter().position(|t| *t == SettingsTab::About).unwrap();
        assert_eq!(about, SettingsTab::ALL.len() - 1, "About is the last tab");
        assert!(script.contains(&format!("\nconst SETTINGS_ABOUT = {about};\n")), "the page's About tab is the window's");
        assert!(script.contains("[settingsAppearance, () => cameraCards(\"settings\"), settingsEditing, settingsFiles, settingsDefinitions, settingsAbout][tab]"));
        // the one way in from outside Settings: the status bar's version
        assert_eq!(script.matches("openSettings(SETTINGS_ABOUT)").count(), 1);
        assert!(script.contains("$(\"foot-version\").addEventListener(\"click\", (e) => {\n  e.stopPropagation();\n  openSettings(SETTINGS_ABOUT);\n});"));
        for gone in ["openWindow(\"about\")", "drawAbout", "About Camset Editor…", "about: false"] {
            assert!(!script.contains(gone), "no About window or button on the page: {gone}");
        }
    }

    /// A note reaches the page in Expert mode only, as in the window; no evidence goes with it (the lean definition
    /// holds none: the runs and the days that prove a note stay with whoever mapped the camera).
    #[test]
    fn a_note_in_expert_mode_only() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let s = app.schema.settings.iter().find(|s| !s.note.is_empty() && !s.expert && s.area == "global").cloned().expect("a note");
        assert!(!s.note.contains("runs/"));
        let row = app.web_row(0, std::slice::from_ref(&s));
        assert_eq!((row.get("note"), row.get("evidence")), (None, None));
        app.prefs.expert = true;
        let row = app.web_row(0, std::slice::from_ref(&s));
        assert_eq!((&row["note"], row.get("evidence")), (&json!(s.note), None));
        assert_eq!(s.note_shown(true), s.note);
        assert_eq!(s.note_shown(false), "");
    }

    /// The page's switches of the mapping team's lines follow the window's rule: set while Expert mode is off, they are
    /// kept for it and draw nothing; Expert mode turned on in the desktop app brings them back as they were.
    #[test]
    fn page_display_prefs_need_expert_mode() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(!app.prefs.expert);
        for name in ["show_record_ids", "show_proof", "show_raw"] {
            assert_eq!(answer(&mut app, "prefs", json!({ "name": name, "value": true })).status, 200, "{name}");
        }
        assert!(app.prefs.show_raw && app.prefs.show_record_ids && app.prefs.show_proof, "kept for Expert mode");
        assert!(!app.show_raw && !app.shows_proof() && !app.shows_record_ids(), "drawn with Expert mode off");
        let s = app.schema.settings.iter().find(|s| !s.expert && s.area == "global" && s.text.is_none() && !app.web_row(0, std::slice::from_ref(*s)).is_null()).cloned().unwrap();
        let row = app.web_row(0, std::slice::from_ref(&s));
        for f in ["raw", "record_id", "proof", "proof_kind"] {
            assert!(row.get(f).is_none(), "{f} sent outside Expert mode");
        }
        app.prefs.expert = true;   // set in the desktop app, which brings the raw numbers back
        app.show_raw = app.prefs.show_raw;
        let row = app.web_row(0, std::slice::from_ref(&s));
        for f in ["raw", "record_id", "proof"] {
            assert!(row.get(f).is_some(), "{f} missing in Expert mode");
        }
    }

    /// The mapping team's lines (the note, the records a setting lives in, what the camera writes with it) reach the
    /// page in Expert mode only, for every row of the shipped definition; a setting the camera's menu does not show
    /// says so in plain words while the proof line is off.
    #[test]
    fn mapping_lines_in_expert_mode_only() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        assert!(!app.prefs.expert && !app.prefs.show_proof);
        let settings: Vec<Setting> = app.schema.settings.iter().filter(|s| !s.expert && s.area == "global").cloned().collect();
        assert!(settings.iter().any(|s| !s.note.is_empty()));
        let mut seen = 0;
        for s in &settings {
            let row = app.web_row(0, std::slice::from_ref(s));
            if row.is_null() {
                continue;
            }
            seen += 1;
            for f in ["note", "records", "evidence", "record"] {
                assert!(row.get(f).is_none(), "{}: {f} sent outside Expert mode", s.key);
            }
            assert_eq!(row.get("not_on_camera").is_some(), s.not_on_camera(), "{}", s.key);
        }
        assert!(seen > 100, "{seen} rows");
        app.prefs.expert = true;
        for s in &settings {
            let row = app.web_row(0, std::slice::from_ref(s));
            if row.is_null() {
                continue;
            }
            for f in ["note", "records"] {
                assert!(row.get(f).is_some(), "{}: {f} missing in Expert mode", s.key);
            }
        }
        // the plain line stands in for the proof line, so it goes when the proof line is on
        app.prefs.show_proof = true;
        let s = settings.iter().find(|s| s.not_on_camera()).expect("a setting not on the camera's menu");
        assert!(app.web_row(0, std::slice::from_ref(s)).get("not_on_camera").is_none());
    }
}

/// Safety from the page: the window's rules for writing to the camera, for replacing unsaved edits and for copying
/// whole memories, answered as the page's requests are.
#[cfg(test)]
mod safety_tests {
    use super::*;
    use crate::write::safety_tests::{changeable, other_firmware, other_model};
    use crate::test_support::camera_file;

    const SAMPLE: &[u8] = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");

    /// A request from the page: JSON, or a file sent up (`upload`: its bytes, and whether the page says to discard
    /// unsaved edits, as the X-Camset-Discard header does).
    fn request(app: &mut App, name: &str, body: Value, upload: Option<(&[u8], bool)>) -> WebReply {
        let (reply, _rx) = mpsc::channel();
        let (body, file_name, discard) = match upload {
            Some((bytes, discard)) => (bytes.to_vec(), "CAMSET09.DAT".to_string(), discard),
            None => (body.to_string().into_bytes(), String::new(), false),
        };
        let r = WebRequest { name: name.into(), body, file_name, discard, peer: "test".into(), reply };
        app.web_answer(&r)
    }

    fn json_of(r: &WebReply) -> Value {
        serde_json::from_slice(&r.body).unwrap()
    }

    fn said(r: &WebReply) -> String {
        json_of(r)["error"].as_str().unwrap_or("").to_string()
    }

    /// E-01, the review's test 1: the page's Write refuses what the window's Write button would, and a file that
    /// changed after the Write window checked it.
    #[test]
    fn the_page_writes_only_what_the_window_would() {
        let mut app = App::new(vec![], Prefs::default());
        // a firmware not checked yet: view only, so never written
        assert_eq!(request(&mut app, "open", json!({}), Some((&other_firmware().to_bytes(), false))).status, 200);
        let r = request(&mut app, "send_check", json!({}), None);
        assert!(r.status == 409 && said(&r).contains("view only"), "{}", said(&r));
        let rev = app.write_rev();
        let r = request(&mut app, "send", json!({ "rev": rev }), None);
        assert_eq!(r.status, 409);
        assert!(app.sent.is_none());
        // another model, even with "Edit anyway" forced on
        assert_eq!(request(&mut app, "open", json!({}), Some((&other_model().to_bytes(), false))).status, 200);
        app.doc.as_mut().unwrap().unchecked_ok = true;
        let rev = app.write_rev();
        let r = request(&mut app, "send", json!({ "rev": rev }), None);
        assert!(r.status == 409 && said(&r).contains("ILCE-0TEST"), "{}", said(&r));
        assert!(app.sent.is_none());
        // the sample sent up from the page: a file on the editor's computer, which it can edit but never writes
        assert_eq!(request(&mut app, "open", json!({}), Some((SAMPLE, false))).status, 200);
        assert!(app.editable());
        let r = request(&mut app, "send_check", json!({}), None);
        assert!(r.status == 409 && said(&r) == SAMPLE_NOT_WRITTEN, "{}", said(&r));
        let rev = app.write_rev();
        assert_eq!(request(&mut app, "send", json!({ "rev": rev }), None).status, 409);
        assert!(app.sent.is_none());
        // a checked file: the camera is read first (below), and the file is written only as the Write window saw it
        assert_eq!(request(&mut app, "open", json!({}), Some((&camera_file(), false))).status, 200);
        let dir = std::env::temp_dir().join(format!("camset_web_write_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let copy = dir.join("before_write_page.DAT");
        std::fs::write(&copy, SAMPLE).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Ok((copy.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        app.web_write = Some(WebWrite::Read);
        let check = json_of(&request(&mut app, "send_check", json!({}), None));
        let rev = check["rev"].as_str().unwrap().to_string();
        // the window's line on how long to leave the camera on: its restart, then the usual read
        assert_eq!(check["leave_on"], format!("{}.", check_words(&app.job_timing())));
        let (s, v) = changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        let r = request(&mut app, "send", json!({ "rev": rev }), None);
        assert!(r.status == 409 && said(&r).contains("changed"), "{}", said(&r));
        assert!(app.sent.is_none(), "nothing written");
        assert_eq!(request(&mut app, "send", json!({}), None).status, 409, "no Write window, no write");
        let rev = json_of(&request(&mut app, "send_check", json!({}), None))["rev"].as_str().unwrap().to_string();
        assert_eq!(request(&mut app, "send", json!({ "rev": rev }), None).status, 200);
        assert!(app.sent.is_some(), "the file the window checked goes to the camera");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// U-14 on the page: Write reads the camera first (`send_check` with `read`), the page waits while the editor is
    /// busy with the camera, then the window lists what the write changes against the camera now, and Write keeps
    /// that read as the copy from just before. A read that fails ends the write with the plain report; one job at a
    /// time, and no write without a read.
    #[test]
    fn the_page_reads_the_camera_before_it_writes() {
        let dir = std::env::temp_dir().join(format!("camset_web_read_first_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        assert_eq!(request(&mut app, "open", json!({}), Some((&camera_file(), false))).status, 200);
        // without the camera link program nothing starts: the report's words say why
        let r = request(&mut app, "send_check", json!({ "read": true }), None);
        assert!(r.status == 409 && app.camera_job.is_none() && app.web_write.is_none(), "{}", said(&r));
        app.camera_report = None;
        // a stand-in for the camera link program that cannot run: the jobs below talk to no camera
        let stand_in = dir.join("not_a_program");
        std::fs::write(&stand_in, "").unwrap();
        app.prefs.probe_path = Some(stand_in.display().to_string());
        app.prefs.link = "usb".into();
        // no read yet: nothing to list and nothing written
        let r = request(&mut app, "send_check", json!({}), None);
        assert!(r.status == 409 && said(&r).contains("reads the camera first"), "{}", said(&r));
        let (s, v) = changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        let rev = app.write_rev();
        let r = request(&mut app, "send", json!({ "rev": rev }), None);
        assert!(r.status == 409 && app.sent.is_none(), "no write without the read: {}", said(&r));
        // Write: the read starts, and the state says the editor is busy with the camera until it is done
        assert_eq!(json_of(&request(&mut app, "send_check", json!({ "read": true }), None))["reading"], true);
        assert_eq!(app.camera_job.as_ref().map(|j| j.kind), Some(JobKind::BeforeWrite));
        assert!(!app.web_state(0)["job"].is_null(), "busy");
        assert_eq!(json_of(&request(&mut app, "send_check", json!({}), None))["reading"], true, "still reading");
        assert_eq!(request(&mut app, "send_check", json!({ "read": true }), None).status, 409, "one job at a time");
        assert_eq!(request(&mut app, "send", json!({ "rev": rev }), None).status, 409, "no write while it reads");
        // the read comes back: the window lists what the write changes against the camera now
        let copy = dir.join("before_write_page.DAT");
        std::fs::write(&copy, SAMPLE).unwrap();
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Ok((copy.clone(), "Camera: USB\n".into())), None));
        app.poll_camera_job();
        assert!(app.web_state(0)["job"].is_null() && app.camera_report.is_none());
        assert!(app.pending.is_none(), "the desktop's Write window stays closed");
        let j = json_of(&request(&mut app, "send_check", json!({}), None));
        let first = j["summary"][0][0].as_str().unwrap();
        assert!(first.starts_with("Compared with the camera now, this changes 1 setting:"), "{j}");
        assert!(j["summary"].as_array().unwrap().iter().any(|l| l[0].as_str().unwrap().contains(&s.name)), "{j}");
        // Write to camera: that read is the copy from just before, and the write does not read again
        let rev = j["rev"].as_str().unwrap().to_string();
        assert_eq!(request(&mut app, "send", json!({ "rev": rev }), None).status, 200);
        let job = app.camera_job.as_ref().unwrap();
        assert_eq!((job.kind, job.backup.clone()), (JobKind::Send, Some(copy.clone())));
        assert!(app.sent.is_some() && app.before_write.is_none() && app.web_write.is_none());
        // a read that fails: the write ends there, with the report in plain words, and nothing is written
        (app.camera_job, app.sent) = (None, None);
        assert_eq!(json_of(&request(&mut app, "send_check", json!({ "read": true }), None))["reading"], true);
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Err("cause: no_usb_camera\n".into()), None));
        app.poll_camera_job();
        let r = request(&mut app, "send_check", json!({}), None);
        assert!(r.status == 409 && said(&r).contains("could not be read first"), "{}", said(&r));
        let report = app.web_state(0)["report"].clone();
        assert_eq!(report["title"], "✖ Nothing written");
        assert!(report["lines"].as_array().unwrap().iter().any(|l| l[0].as_str().unwrap().contains("No camera was found on USB")), "{report}");
        assert_eq!(report["retry"], false, "Try again is Write again");
        assert!(app.sent.is_none() && app.web_write.is_none());
        // Cancel while the camera is read: the read goes on, and its end is only said in the status line
        app.camera_report = None;
        assert_eq!(json_of(&request(&mut app, "send_check", json!({ "read": true }), None))["reading"], true);
        assert_eq!(request(&mut app, "send_cancel", json!({}), None).status, 200);
        app.camera_job = Some(CameraJob::finished(JobKind::BeforeWrite, Err("cause: no_usb_camera\n".into()), None));
        app.poll_camera_job();
        assert!(app.camera_report.is_none() && app.status.contains("nothing was written"), "{}", app.status);
        assert!(app.sent.is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-06: what replaces file A from the page is refused while it has unsaved edits, unless the page says the
    /// person agreed to discard them.
    #[test]
    fn the_page_keeps_unsaved_edits() {
        let mut app = App::new(vec![], Prefs::default());
        assert_eq!(request(&mut app, "sample", json!({}), None).status, 200, "nothing to lose yet");
        let (s, v) = changeable(&app);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        let dir = std::env::temp_dir().join(format!("camset_web_unsaved_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let kept = dir.join("KEPT.DAT");
        std::fs::write(&kept, SAMPLE).unwrap();
        app.prefs.recent = vec![kept.display().to_string()];
        // an original: no test removes one, where a copy a test put in the camera folder may be gone when it is asked for
        let backup = App::list_backups().into_iter().find(|b| b.folder == "originals")
            .map(|b| json!({ "folder": b.folder, "name": b.path.file_name().unwrap_or_default().to_string_lossy() }));
        let link = app.prefs.link.clone();
        let mut refused = vec![
            ("sample", request(&mut app, "sample", json!({}), None)),
            ("read", request(&mut app, "read", json!({}), None)),
            ("switch_usb", request(&mut app, "switch_usb", json!({}), None)),
            ("open", request(&mut app, "open", json!({}), Some((SAMPLE, false)))),
            ("open_recent", request(&mut app, "open_recent", json!({ "index": 0 }), None)),
        ];
        if let Some(b) = &backup {
            refused.push(("open_backup", request(&mut app, "open_backup", b.clone(), None)));
        }
        for (name, r) in refused {
            assert!(r.status == 409 && said(&r).contains("unsaved edits"), "{name}: {} {}", r.status, said(&r));
        }
        assert_eq!(app.unsaved(), 1, "the edit is still there");
        assert!(app.camera_job.is_none() && app.prefs.link == link, "no read started, the link left as it was");
        // the person agreed on the page
        assert_eq!(request(&mut app, "open_recent", json!({ "index": 0, "discard": true }), None).status, 200);
        assert_eq!(app.doc.as_ref().unwrap().path, kept);
        app.apply(vec![Action::Set(0, s.slot(), v)]);
        assert_eq!(request(&mut app, "open", json!({}), Some((SAMPLE, true))).status, 200);
        assert_eq!(app.unsaved(), 0);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// E-17: a file sent up that is not a settings file is refused in plain words; the parser's own in Expert mode.
    #[test]
    fn the_page_refuses_a_damaged_file_in_plain_words() {
        let mut app = App::new(vec![], Prefs::default());
        let mut damaged = SAMPLE.to_vec();
        damaged[0x100] ^= 0xff;
        let r = request(&mut app, "open", json!({}), Some((&damaged, false)));
        assert!(r.status == 400 && said(&r).contains("damaged") && !said(&r).contains("0x"), "{}", said(&r));
        app.prefs.expert = true;
        let r = request(&mut app, "open", json!({}), Some((&damaged, false)));
        assert!(said(&r).contains("checksum"), "{}", said(&r));
        assert!(app.doc.is_none());
    }

    /// E-08: the page's Recall and Register copy the whole memory whatever its search and tab, unless it asks for
    /// the rows shown.
    #[test]
    fn the_page_recalls_the_whole_memory() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let m = app.dial_sets()[0];
        let tab = app.memory_rows()[0].0.clone();
        let differ = |app: &App| app.memory_rows().iter().flat_map(|r| r.2.clone())
            .filter(|l| app.shape_ok_in(l, 0) && app.shape_ok_in(l, m) && app.locked_why(l, 0).is_none() && app.col_value(Col::a(0), l) != app.col_value(Col::a(m), l)).count();
        assert!(differ(&app) > 0, "Memory 1 differs from the live settings in the sample");
        let r = json_of(&request(&mut app, "recall", json!({ "memory": m, "shown": true, "q": "no such setting anywhere", "tab": tab }), None));
        assert_eq!(r["n"], 0, "asked for the rows shown, and none are");
        let r = json_of(&request(&mut app, "recall", json!({ "memory": m, "q": "no such setting anywhere", "tab": tab }), None));
        assert!(r["n"].as_u64().unwrap() > 0);
        assert_eq!(differ(&app), 0, "the whole memory recalled");
    }

    /// E-02 from the page: copying B's rows and recalling a memory under "Edit anyway" leave a record of another
    /// shape as it was, and say how many settings they left.
    #[test]
    fn the_page_leaves_other_shapes_alone() {
        let mut app = App::new(vec![], Prefs::default());
        let mut older = other_firmware();
        for b in older.sections[1].get_mut(0x0cde).unwrap().value.iter_mut() { *b = b.wrapping_add(1); }
        assert_eq!(request(&mut app, "open", json!({}), Some((&older.to_bytes(), false))).status, 200);
        app.doc.as_mut().unwrap().unchecked_ok = true;   // Edit anyway, in the desktop app (the page may not turn it on)
        // file B: a checked firmware whose live Creative Look differs from A's
        let mut b = test_parse(SAMPLE).unwrap();
        for x in b.sections[0].get_mut(0x0cde).unwrap().value.iter_mut() { *x = x.wrapping_add(1); }
        assert_eq!(request(&mut app, "open_b", json!({}), Some((&b.to_bytes(), false))).status, 200);
        let look = |app: &App| app.doc.as_ref().unwrap().edited.sections[0].get(0x0cde).unwrap().value.clone();
        let before = look(&app);
        let keys: Vec<String> = app.matrix_rows_for("", None).iter().map(|r| r.2[0].key.clone()).collect();
        let r = json_of(&request(&mut app, "copy_rows", json!({ "from": ["b", 0], "to": ["a", 0], "keys": keys }), None));
        assert!(r["left"].as_u64().unwrap() > 0 && r["message"].as_str().unwrap().contains("left alone"), "{r}");
        assert!(app.status.contains("left alone"), "{}", app.status);
        assert_eq!(look(&app), before);
        let m = app.dial_sets()[0];
        let r = json_of(&request(&mut app, "recall", json!({ "memory": m }), None));
        assert!(r["left"].as_u64().unwrap() > 0, "{r}");
        assert_eq!(look(&app), before);
    }
}

/// Odd files a camera never writes, but a damaged card or a hand-made file can hold, open without a panic, and every
/// page of the window and of the web page draws them.
#[cfg(test)]
mod odd_file_tests {
    use super::*;
    use eframe::App as _;

    const SAMPLE: &[u8] = include_bytes!("../../definitions/ILCE-1M2_fw4.00.DAT");

    /// The sample changed by `f`, written back whole (the checksums worked out again, as a hand-made file would have).
    fn made(f: impl FnOnce(&mut CamSet)) -> Vec<u8> {
        let mut c = crate::test_parse(SAMPLE).unwrap();
        f(&mut c);
        c.to_bytes()
    }

    /// How much `draw_everything` draws: every page in and out of Expert mode, every page in Expert mode, or the pages
    /// edits and a file B change most (Main, All edits, Memories, the Record map, Compare) for the live settings.
    #[derive(Clone, Copy, PartialEq)]
    enum Depth { Both, Expert, Light }

    /// Every page of the window, Edit and Compare, and what the page asks for, for the live settings, the first and
    /// last memory and a set the file does not hold (as much as `depth` says); `what` names the file when something
    /// panics.
    fn draw_everything(app: &mut App, what: &str, depth: Depth) {
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        let mut views = vec![View::Main, View::Changes, View::Memories, View::MyMenu, View::Records];
        if depth != Depth::Light {
            views.extend([View::Unmapped, View::Exposure, View::Search]);
            views.extend(app.schema.tabs.iter().cloned().map(View::Tab));
        }
        let mut frame_of = |app: &mut App, how: &str| {
            let ok = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { let _ = ctx.run(egui::RawInput::default(), |ctx| app.update(ctx, &mut frame)); }));
            assert!(ok.is_ok(), "{what}: the window panicked on {how}");
        };
        let n = app.n_sections();
        let mut targets = if depth == Depth::Light { vec![0] } else { vec![0, 1, n - 1, n] };
        targets.dedup();
        for expert in if depth == Depth::Both { vec![false, true] } else { vec![true] } {
            app.prefs.expert = expert;
            for v in &views {
                (app.mode, app.view, app.search) = (Mode::Edit, v.clone(), if *v == View::Search { "a".into() } else { String::new() });
                frame_of(app, &format!("{v:?} (Expert {expert})"));
            }
            app.mode = Mode::Compare;
            for records in [false, true] {
                app.compare_records = records;
                frame_of(app, &format!("Compare (records {records}, Expert {expert})"));
            }
            (app.compare_records, app.mode) = (false, Mode::Edit);
            for &target in &targets {
                app.target = target;
                for (name, body) in [
                    ("state", json!({ "target": target })),
                    ("main", json!({ "target": target, "set": 0 })),
                    ("main", json!({ "target": target, "set": 1 })),
                    ("memories", json!({})),
                    ("mymenu_page", json!({ "target": target })),
                    ("exposure", json!({})),
                    ("changes", json!({})),
                    ("unmapped", json!({ "target": target })),
                    ("records", json!({ "target": target })),
                    ("history", json!({})),
                    ("layout", json!({})),
                ] {
                    let (reply, _rx) = mpsc::channel();
                    let r = WebRequest { name: name.into(), body: body.to_string().into_bytes(), file_name: String::new(), discard: false, peer: "test".into(), reply };
                    let ok = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { let _ = app.web_answer(&r); }));
                    assert!(ok.is_ok(), "{what}: the page's {name} panicked (section {target})");
                }
                for tab in app.schema.tabs.clone() {
                    let (reply, _rx) = mpsc::channel();
                    let body = json!({ "target": target, "tab": tab }).to_string().into_bytes();
                    let r = WebRequest { name: "tab".into(), body, file_name: String::new(), discard: false, peer: "test".into(), reply };
                    let ok = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { let _ = app.web_answer(&r); }));
                    assert!(ok.is_ok(), "{what}: the page's tab {tab} panicked (section {target})");
                }
            }
        }
        app.prefs.expert = false;
    }

    /// Each file opened, drawn, edited and drawn, then compared with the sample and drawn (`tag`: a folder of its own).
    fn open_and_draw(tag: &str, files: Vec<(&str, Vec<u8>)>) {
        let dir = std::env::temp_dir().join(format!("camset_odd_files_{tag}_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        for (what, bytes) in files {
            let p = dir.join("CAMSET01.DAT");
            std::fs::write(&p, &bytes).unwrap();
            let mut app = App::new(vec![], Prefs::default());
            let opened = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| app.open_now(p.clone())));
            assert!(opened.is_ok(), "{what}: opening panicked");
            assert!(app.doc.is_some(), "{what}: it opens ({})", app.status);
            draw_everything(&mut app, what, if what == "no sections at all" { Depth::Both } else { Depth::Expert });
            // with editing forced on, as Edit anyway… does for a firmware not checked, and a few edits made
            app.doc.as_mut().unwrap().unchecked_ok = true;
            let edits = app.demo_edits();
            app.apply(edits);
            draw_everything(&mut app, &format!("{what}, edited"), Depth::Light);
            // and compared with the sample
            let sample = dir.join("CAMSET02.DAT");
            std::fs::write(&sample, SAMPLE).unwrap();
            app.open_compare(sample);
            draw_everything(&mut app, &format!("{what}, beside the sample"), Depth::Light);
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// Fewer sections than the definition names, none at all, or more.
    #[test]
    fn odd_sections_open_and_every_page_draws() {
        open_and_draw("sections", vec![
            ("no sections at all", made(|c| c.sections.clear())),
            ("one section with no records", made(|c| c.sections = vec![camset::Section::new(Vec::new())])),
            ("the live settings only", made(|c| c.sections.truncate(1))),
            ("one memory more", made(|c| { let last = c.sections.last().unwrap().clone(); c.sections.push(last); })),
        ]);
    }

    /// A header naming another firmware or model, with odd bytes, or failing its checksum.
    #[test]
    fn odd_headers_open_and_every_page_draws() {
        open_and_draw("headers", vec![
            ("firmware 255.255, a video system the definition names nothing for", made(|c| c.header[0x36..0x39].fill(0xff))),
            ("another model, and a name of odd bytes", made(|c| { c.header[5..0x15].fill(0xfe); c.header[0x15..0x35].fill(0x80); })),
            ("a damaged header checksum", { let mut d = SAMPLE.to_vec(); d[0x39] ^= 0xff; d }),
        ]);
    }

    /// Records of other shapes than the definition knows, left out or doubled.
    #[test]
    fn odd_records_open_and_every_page_draws() {
        let mut rng = 0x1234_5678_u64;
        let mut next = move || { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; rng };
        open_and_draw("records", vec![
            ("records reshaped", made(|c| {
                // one record in twenty of each section a different shape (its size and count), still framed whole
                for s in &mut c.sections {
                    let mut recs = s.records.clone();
                    for r in recs.iter_mut().step_by(20) {
                        let (size, count) = [(1, 1), (2, 1), (4, 1), (8, 1), (1, 3), (2, 7), (3, 1), (0, 0), (2, 0), (16, 2)][(next() % 10) as usize];
                        (r.elem_size, r.count) = (size, count);
                        r.value = (0..size as usize * count as usize).map(|_| next() as u8).collect();
                    }
                    *s = camset::Section::new(recs);
                }
            })),
            ("records left out and doubled", made(|c| {
                let mut recs = c.sections[0].records.clone();
                recs.retain(|r| r.id % 3 != 0);
                let first = recs[0].clone();
                recs.push(first);
                c.sections[0] = camset::Section::new(recs);
            })),
        ]);
    }
}
