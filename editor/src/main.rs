//! Camset Editor: view, edit and compare Sony camera settings files, as the camera definitions describe them.
//!
//! Usage: camset_editor [FILE.DAT [COMPARE.DAT]]
//!
//! This file holds the window's state (`App`) and its frame (`update`); each part of the window and of what the editor
//! does has a module of its own below, all of them adding to `App`. The web page (`web`) answers from the same state.
//!
//! The modules, in five groups:
//! - `camera`: the camera link: its jobs and their reports, the known cameras, Connect, Write, the definitions.
//! - `document`: the open file and what the editor keeps about it: edits, history, recovery, exports, its own files.
//! - `pages`: what the pages show: Main, Menu, a row's detail, Compare, Memories, My Menu, Exposure, Expert mode's.
//! - `window`: the window around the pages: top bar, status line, dialogs, keys, colours, preferences, Settings.
//! - `web`: the web page, a small HTTP server inside the editor that answers from the same state.
//!
//! Under test, `test_support` holds the helpers several test modules share.
// no console window behind the app on Windows; the tests' build (`cargo test --release`, as CI runs it) keeps its
// console, so it prints its results and names a failing test
#![cfg_attr(all(not(debug_assertions), not(test)), windows_subsystem = "windows")]

use eframe::egui::{self, Color32, FontFamily, FontId, RichText, TextStyle};
use camset_editor::camset::{self, CamSet, FileFormat};
use camset_editor::menu_rows::{self, Line};
use camset_editor::schema::{Camera, Definitions, LinkTiming, Match, Origin, Schema, Setting, Slot, Tile, TileKind};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

mod camera;
mod document;
mod pages;
mod window;
mod web;
#[cfg(test)]
pub(crate) mod test_support;   // the helpers several test modules share
#[cfg(test)]
mod no_camera_facts;   // the guard for decision 20: the editor's code names no camera
#[cfg(test)]
#[path = "../packaging/windows/resources.rs"]
mod windows_resources;   // the Windows program's icon and version details, which build.rs links: tested on every system

// what the modules define beside `App`'s methods, named here once so every module (`use crate::*`) has it at hand
use camera::*;
use document::*;
use pages::*;
use window::*;

fn main() -> eframe::Result {
    let args: Vec<String> = std::env::args().skip(1).collect();
    // an error that stops the editor leaves a short log and the journal of unsaved edits (`recovery`)
    recovery::crash_hook(camset_editor::schema::config_dir().join("crash.log"), version_words());
    let prefs = Prefs::load();
    if std::env::var_os("CAMSET_NETTEST").is_some() {
        net_test(&prefs);
        return Ok(());
    }
    let size = prefs.window.unwrap_or([1280.0, 860.0]);
    let mut viewport = egui::ViewportBuilder::default().with_inner_size(size).with_title(window_title()).with_app_id(APP_ID);
    if let Ok(icon) = eframe::icon_data::from_png_bytes(include_bytes!("../assets/icon.png")) {
        viewport = viewport.with_icon(std::sync::Arc::new(icon));    // the taskbar / dock icon when run unbundled
    }
    let options = eframe::NativeOptions { viewport, ..Default::default() };
    eframe::run_native("Camset Editor", options, Box::new(move |_cc| Ok(Box::new(App::new(args, prefs)))))
}

/// The application id: the compositor names the window by it and matches it to the menu entry
/// (Wayland; without one GNOME calls the app "Unknown"). The same string as the Mac bundle id
/// (packaging/build_macos_app.sh) and the Linux menu entry's StartupWMClass (packaging/linux).
const APP_ID: &str = "app.camset.editor";

/// Whether a window of `size` at `pos` (its top left corner) shows on a screen of `screen` whose corner is at 0, 0:
/// its title bar on the screen, and at least 100 points of it across.
fn place_on_screen(pos: [f32; 2], size: [f32; 2], screen: [f32; 2]) -> bool {
    pos.iter().chain(size.iter()).all(|v| v.is_finite())
        && pos[1] >= 0.0 && pos[1] <= screen[1] - 100.0
        && pos[0] + size[0] >= 100.0 && pos[0] <= screen[0] - 100.0
}

struct App {
    /// The camera definition the open file is read with (`Schema::default()`, no definition, before one is picked).
    schema: Schema,
    /// Every definition found, the shipped ones and the user's, to pick from per file.
    defs: Definitions,
    /// Add definition…: a definition whose file name the user's folder holds already (its path, and the name it
    /// goes by), waiting for the answer to "Replace it?".
    def_replace: Option<(PathBuf, String)>,
    prefs: Prefs,
    show_settings: bool,
    settings_tab: SettingsTab,
    /// Snapshots of the edited file before each edit (undo) and after each undo (redo).
    undo: Vec<CamSet>,
    redo: Vec<CamSet>,
    focus: Focus,
    /// The window before a save or a write (`Review`), with the edited values the camera may refuse.
    pending: Option<(Review, Vec<Issue>)>,
    camera_job: Option<CameraJob>,
    /// Outcome of the last camera action, shown until dismissed.
    camera_report: Option<CameraReport>,
    show_connect: bool,
    /// The setup steps ticked off (all set once a search finds a camera).
    connect_checks: Vec<bool>,
    /// The setup steps' card, the same in both windows that show the camera cards: open or folded, and the value of
    /// `steps_open` it last followed. It follows that rule when the rule changes, opens after a search that finds
    /// nothing, and otherwise stays as the person left it.
    steps_shown: bool,
    steps_rule: bool,
    link_state: LinkState,
    /// The camera's settings as last read (or read back), for the plain-language send summary.
    last_camera: Option<(String, CamSet)>,
    /// The Write window's read of the camera, made when it opens: what the write is compared with, and the copy kept
    /// for "Put the camera back" (`JobKind::BeforeWrite`).
    before_write: Option<BeforeWrite>,
    /// The camera's settings read just before the last write (local stamp, file): "Put the camera back".
    camera_backup: Option<(String, PathBuf)>,
    show_history: bool,
    show_backups: bool,
    /// The window that turns editing on for a file from a firmware not checked.
    show_unchecked: bool,
    /// The Backups window's list, read when it opens.
    backups: Vec<Backup>,
    discovered: Vec<Discovered>,
    discover_msg: String,
    /// The helper's own words about the last search when it found nothing or failed (shown in Expert mode).
    discover_detail: String,
    /// The helper's whole output from the last search, found rows included (shown in Expert mode only).
    discover_text: String,
    net_user: String,
    net_pass: String,
    /// The file last sent to the camera, for the read-back check after it restarts.
    sent: Option<(PathBuf, CamSet)>,
    /// A file from disk whose edits the camera's read-back confirmed (its opening, its state, the file sent): while it
    /// stays in that state and nothing else is sent, its edits are on the camera but not saved to it (`edits_on_camera`).
    on_camera: Option<(u64, u64, PathBuf)>,
    /// The question asked before unsaved edits would be lost (`guard`): what happens once they are dealt with.
    unsaved_ask: Option<Replace>,
    /// The next read opens as file B beside the edits ("Compare with what the camera holds"); `run_job` takes it.
    read_as_b: bool,
    /// The read-back after a write is tried again (`retry_job`): `run_job` reads at once, with no wait for a restart.
    read_back_now: bool,
    /// Save As was chosen in that question: what happens once the save has succeeded.
    after_save: Option<Replace>,
    /// The window may close: the question was answered, or nothing would be lost.
    close_ok: bool,
    /// The file as the Write window checked it (`revision`): Write to camera refuses any other.
    review_rev: Option<u64>,
    /// Settings a copy left alone, by why (`copy_row`, `Left`); `apply` says how many.
    copy_skipped: std::cell::Cell<Left>,
    /// The actions `apply` takes next are a copy of several rows at once (`pin_families`), from another file (`Some(None)`)
    /// or from a set of file A (`Some(Some(set))`: a memory recalled or registered): only then does a Set to the value a
    /// record holds pass the lock guard, and a refusal says what to do about the copy.
    rows_copied: std::cell::Cell<Option<Option<usize>>>,
    /// The last edit that the next may join (a value being dragged): its slots and when, so a drag is one undo step.
    last_edit: Option<(Vec<(usize, Slot)>, std::time::Instant)>,
    /// When the window's size last changed, while that size is not saved yet (it is once it stays put a second).
    window_changed: Option<std::time::Instant>,
    /// The window's place from the last session, put back on one of the first frames (`restore_place`).
    place_to_restore: Option<([f32; 2], u32)>,
    doc: Option<Doc>,
    compare: Option<(PathBuf, CamSet)>,
    /// Three-way compare: the file both A and B started from.
    base: Option<(PathBuf, CamSet)>,
    three_filter: ThreeFilter,
    /// Compare view: the row the difference cursor is on (index into the rows shown), a row to
    /// scroll into view on the next frame, and a pending Next/Previous step from the keyboard.
    diff_cursor: Option<usize>,
    scroll_to_row: Option<usize>,
    diff_step: i32,
    /// Compare's "Open in Edit" (`open_in_edit_from_compare`): where it went and the row it came from, while Edit
    /// offers "← Back to Compare"; and the row (tab, setting key) that Back puts under the difference cursor.
    from_compare: Option<FromCompare>,
    compare_row_to: Option<(String, String)>,
    /// The Compare row (tab, setting key) last changed with Compare's picker (`compare_picker`): kept shown while
    /// "Only rows that differ" or the three-way filter would now leave it out, so the rows and the difference cursor
    /// stay where they were; let go when one of those filters changes.
    cmp_kept: Option<(String, String)>,
    /// Compare view: one mark per row shown (for the minimap) and the rows currently on screen.
    mm_rows: Vec<RowMark>,
    mm_visible: Option<(usize, usize)>,
    /// Compare view: the tabs (tab, "") and groups (tab, group) folded shut.
    matrix_closed: std::collections::HashSet<(String, String)>,
    target: usize,
    mode: Mode,
    view: View,
    /// Compare mode: show only this tab (None = all tabs).
    compare_tab: Option<String>,
    /// Main page: movie tiles instead of stills, and the tile last clicked.
    main_set: usize,
    main_focus: Option<String>,
    /// Selected group and item in the menu columns (item = setting name within the group).
    group: Option<String>,
    item: Option<String>,
    /// Which of the rows named `item` is meant when its group holds two of that name in different places on the
    /// camera ("Fixed Speed REC" under Remote Zoom Speed and under Custom Key Z. Speed): a key of one of its
    /// settings. Ignored when only one row bears the name, so a jump that sets `item` alone still lands.
    item_key: Option<String>,
    /// The camera's rows folded in the "As on the camera" layout, by tab, group and labels (`fold_key`).
    folded: std::collections::HashSet<String>,
    /// The sub-choice opened from a search, F3, All edits, Compare or the history while the rows are laid out as on
    /// the camera (`menu_rows::beside_owner`): its owner's row is chosen and the detail panel marks its box, by key.
    sub_focus: Option<String>,
    /// The detail panel is still to scroll to `sub_focus`'s box (once, the frame it is drawn).
    sub_scroll: std::cell::Cell<bool>,
    /// The page an option's link asked to open ("Open the PP1 page", `option_choice_ui`), by a setting on it: opened
    /// by `apply`, after the frame that drew the link (`open_page_of`).
    open_page: std::cell::RefCell<Option<String>>,
    search: String,
    only_changed: bool,
    show_raw: bool,
    allow_raw_edits: bool,
    /// Offer values no proof on the camera established (`Setting::established`; the camera may refuse a file holding one).
    allow_unobserved: bool,
    status: String,
    /// Compare view: columns (the first is the baseline) and whether to hide identical rows.
    cols: Vec<Col>,
    matrix_only_diff: bool,
    /// Compare view: show every record in file order (mapped or not) instead of the settings list.
    compare_records: bool,
    /// Test hook: CAMSET_SCREENSHOT=out.png saves a screenshot of the window and quits.
    screenshot: Option<(String, u32)>,
    /// The web page's server while it is on, why it last failed to start, and a start waiting for
    /// the first frame (it needs the window's context).
    web: Option<web::WebServer>,
    web_error: String,
    web_start_pending: bool,
    /// The web page's Write, from its read of the camera until it writes or the read ends it (`WebWrite`).
    web_write: Option<WebWrite>,
    /// File dialogs run on a helper thread (`ask`) and their answers come back here; one is open
    /// while `dialog_open` is set, and further requests wait for it.
    dialog_tx: std::sync::mpsc::Sender<(DialogKind, Option<PathBuf>)>,
    dialog_rx: std::sync::mpsc::Receiver<(DialogKind, Option<PathBuf>)>,
    dialog_open: bool,
    /// Counts each change of camera definition, so what was worked out from one is not reused for another.
    schema_gen: u64,
    /// Compare rows worked out for a (definition, search, tab, Expert mode), newest last: they are kept until one
    /// of those changes, not worked out again on every frame.
    rows_cache: std::cell::RefCell<Vec<(RowsKey, std::rc::Rc<Vec<Row>>)>>,
    /// Each setting's position in the camera's order (`menu_rank`), worked out once per definition (its generation).
    rank_cache: std::cell::RefCell<Option<(u64, MenuRank)>>,
    /// The groups the camera's menus hold (`placed_groups`), worked out once per definition (its generation).
    placed_cache: std::cell::RefCell<Option<(u64, PlacedGroups)>>,
    /// The Record map's and the Unmapped page's rows, worked out once per state of the file, not on every frame.
    records_cache: std::cell::RefCell<Option<(RecordsKey, std::rc::Rc<Vec<RecordRow>>)>>,
    /// Each record's setting by (memory set, record number), and the fields known inside array records, worked out
    /// once per definition (its generation) in place of a search through every setting for each record.
    setting_index: std::cell::RefCell<Option<(u64, SettingIndex)>>,
    /// Each setting's index among the definition's settings by its key (`App::index_of_key`), made once per definition
    /// (its generation).
    key_index: std::cell::RefCell<Option<(u64, std::collections::HashMap<String, usize>)>>,
    fields_cache: std::cell::RefCell<Option<FieldsEntry>>,
    /// The number of edited values the camera may not take (`acceptance_issues`), for a state of the file and a
    /// definition: the page asks for it every few seconds.
    issues_count: std::cell::Cell<Option<((u64, u64), usize)>>,
    /// Compare: the height of a row as last drawn, for the rows off screen, which only keep their place.
    matrix_row_h: std::cell::Cell<f32>,
    /// History window: the lines of each undo step, worked out once per step (index = step).
    history_cache: std::cell::RefCell<Vec<(HistKey, std::rc::Rc<Vec<HistRow>>)>>,
    /// Whether the camera link program was found, and when it was last looked for (`have_helper`).
    helper_seen: std::cell::Cell<Option<(std::time::Instant, bool)>>,
    /// The file from a camera no definition covers that the status line last spoke about (`note_foreign`).
    foreign_noted: Option<PathBuf>,
    /// The status line's last messages, oldest first (local time, text), at most `STATUS_LOG` of them, the last
    /// one logged, and whether the window listing them is open. A message that matters also shows as a toast
    /// for a while (`toast`, with when it came).
    status_log: Vec<(String, String)>,
    status_seen: String,
    show_log: bool,
    toast: Option<(String, std::time::Instant)>,
    /// The journal of the open file's unsaved edits (`recovery`), kept while they are not saved.
    journal: recovery::Journal,
    /// Journals an earlier session left (it stopped with edits not saved), offered one at a time, newest first.
    recovered: Vec<recovery::Found>,
    /// Settings > Changes: the changelog's window is open.
    show_changes: bool,
    /// The About window is open (the status bar's version, or the one at the foot of Settings, opens it).
    show_about: bool,
}

impl App {
    fn new(args: Vec<String>, prefs: Prefs) -> Self {
        // no definition until a file picks one (`use_definition`)
        let schema = Schema::default();
        let first_tab = schema.tabs.first().cloned().unwrap_or_default();
        let show_raw = prefs.expert && prefs.show_raw;
        let allow_raw_edits = prefs.expert && prefs.allow_raw_edits;
        let allow_unobserved = prefs.expert && prefs.allow_unobserved;
        let matrix_only_diff = prefs.matrix_only_diff;
        let steps = steps_open(prefs.cameras.len(), 0);
        let place_to_restore = prefs.window_pos.map(|p| (p, 0));
        let cols = vec![Col::a(0)];   // the definition picked for a file names the rest (`start_cols`)
        let (dialog_tx, dialog_rx) = std::sync::mpsc::channel();
        let mut app = App {
            schema,
            defs: Self::find_definitions(),
            def_replace: None,
            prefs,
            show_settings: false,
            settings_tab: SettingsTab::Appearance,
            undo: Vec::new(),
            redo: Vec::new(),
            focus: Focus::Items,
            pending: None,
            camera_job: None,
            camera_report: None,
            show_connect: false,
            connect_checks: Vec::new(),
            steps_shown: steps,
            steps_rule: steps,
            link_state: LinkState::Untried,
            last_camera: None,
            before_write: None,
            camera_backup: None,
            show_history: false,
            show_backups: false,
            show_unchecked: false,
            backups: Vec::new(),
            discovered: Vec::new(),
            discover_msg: String::new(),
            discover_detail: String::new(),
            discover_text: String::new(),
            net_user: String::new(),
            net_pass: String::new(),
            sent: None,
            on_camera: None,
            unsaved_ask: None,
            read_as_b: false,
            read_back_now: false,
            after_save: None,
            close_ok: false,
            review_rev: None,
            copy_skipped: Default::default(),
            rows_copied: Default::default(),
            last_edit: None,
            window_changed: None,
            place_to_restore,
            doc: None,
            compare: None,
            base: None,
            three_filter: ThreeFilter::All,
            diff_cursor: None,
            scroll_to_row: None,
            diff_step: 0,
            from_compare: None,
            compare_row_to: None,
            cmp_kept: None,
            mm_rows: Vec::new(),
            mm_visible: None,
            matrix_closed: Default::default(),
            target: 0,
            mode: Mode::Edit,
            view: View::Tab(first_tab),
            compare_tab: None,
            main_set: 0,
            main_focus: None,
            group: None,
            item: None,
            item_key: None,
            folded: Default::default(),
            sub_focus: None,
            sub_scroll: Default::default(),
            open_page: Default::default(),
            search: String::new(),
            only_changed: false,
            show_raw,
            allow_raw_edits,
            allow_unobserved,
            status: String::new(),
            cols,
            matrix_only_diff,
            compare_records: std::env::var("CAMSET_VIEW").is_ok_and(|v| v == "compare_records"),
            screenshot: std::env::var("CAMSET_SCREENSHOT").ok().map(|p| (p, 0)),
            web: None,
            web_error: String::new(),
            web_start_pending: false,
            web_write: None,
            dialog_tx,
            dialog_rx,
            dialog_open: false,
            schema_gen: 0,
            rows_cache: Default::default(),
            rank_cache: Default::default(),
            placed_cache: Default::default(),
            records_cache: Default::default(),
            setting_index: Default::default(),
            key_index: Default::default(),
            fields_cache: Default::default(),
            issues_count: Default::default(),
            matrix_row_h: std::cell::Cell::new(22.0),
            history_cache: Default::default(),
            helper_seen: std::cell::Cell::new(None),
            foreign_noted: None,
            status_log: Vec::new(),
            status_seen: String::new(),
            show_log: false,
            toast: None,
            journal: recovery::Journal::new(Self::recovery_dir()),
            recovered: recovery::list(&Self::recovery_dir(), &recovery::running),
            show_changes: false,
            show_about: false,
        };
        app.web_start_pending = app.prefs.web_at_start;
        if let Ok(v) = std::env::var("CAMSET_VIEW") {
            match v.as_str() {
                "main" => app.view = View::Main,
                "changes" => app.view = View::Changes,
                "unmapped" => app.view = View::Unmapped,
                "records" => app.view = View::Records,
                "exposure" => app.view = View::Exposure,
                "memories" => app.view = View::Memories,
                "mymenu" => app.view = View::MyMenu,
                "settings" => app.show_settings = true,
                "about" => app.show_about = true,
                "settings_definitions" => { app.show_settings = true; app.settings_tab = SettingsTab::Definitions; }
                "settings_camera" => { app.show_settings = true; app.settings_tab = SettingsTab::Camera; }
                "write" | "write_reading" | "history" | "backups" | "connect" | "statuslog" => app.view = View::Main,
                "matrix" | "compare" | "compare_records" => app.mode = Mode::Compare,
                t => app.view = View::Tab(t.to_string()),
            }
        }
        if let Ok(t) = std::env::var("CAMSET_TARGET") { app.target = t.parse().unwrap_or(0); }
        if let Ok(q) = std::env::var("CAMSET_SEARCH") { app.search = q; }
        if let Some(p) = args.first() {
            app.open(PathBuf::from(p));
        } else if app.prefs.reopen_last {
            // last session: files, mode, set being edited and the page shown
            let p = app.prefs.clone();
            if let Some(a) = p.last_a.as_ref().map(PathBuf::from).filter(|a| a.exists()) {
                app.open(a);
                if let Some(b) = p.last_b.as_ref().map(PathBuf::from).filter(|b| b.exists()) {
                    app.open_compare(b);
                    if let Some(x) = p.last_base.as_ref().map(PathBuf::from).filter(|x| x.exists()) {
                        app.open_base(x);
                    }
                }
                app.mode = if p.compare_mode { Mode::Compare } else { Mode::Edit };
                app.target = p.target.min(app.n_sections() - 1);
                if let Some(v) = p.view.as_deref().and_then(|k| View::from_key(k, p.expert, &app.schema.tabs)) {
                    app.view = v;
                }
            }
        }
        if let Some(p) = args.get(1) {
            app.open_compare(PathBuf::from(p));
        }
        if let Some(p) = args.get(2) {
            app.open_base(PathBuf::from(p));
        }
        // test hook: CAMSET_DEMO_EDITS=1 edits a few settings of file A, so a screenshot shows how edits look
        if std::env::var_os("CAMSET_DEMO_EDITS").is_some() {
            let edits = app.demo_edits();
            app.apply(edits);
        }
        // test hook: some CAMSET_VIEW values also open a window over the file, for a screenshot of it
        match std::env::var("CAMSET_VIEW").as_deref() {
            Ok("write") => app.write_window_shot(false),
            Ok("write_reading") => app.write_window_shot(true),
            Ok("history") => app.show_history = true,
            Ok("backups") => { app.show_backups = true; app.backups = Self::list_backups(); }
            Ok("connect") => app.show_connect = true,
            Ok("statuslog") => {
                app.log_status();
                app.status = "Saved /Volumes/CARD/PRIVATE/SONY/CAMSET/CAMSET02.DAT with 4 change(s) (warning: 11 settings files in that folder; the camera lists only 10)".into();
                app.log_status();
                app.show_log = true;
            }
            _ => {}
        }
        app
    }

    /// Test hook for a screenshot (CAMSET_VIEW=write or write_reading, with CAMSET_SCREENSHOT): the Write window as it
    /// shows once the camera was read, the camera stood for by the file as it was opened (before the demo edits), or
    /// while it is read. Nothing is read or written, and without a screenshot to take it does nothing.
    fn write_window_shot(&mut self, reading: bool) {
        let Some(d) = self.doc.as_ref().filter(|_| self.screenshot.is_some()) else { return };
        let (cam, path) = (d.original.clone(), d.path.clone());
        self.pending = Some((Review::Send, self.write_issues()));
        self.review_rev = self.revision();
        if reading {
            let result = std::sync::Arc::new(std::sync::Mutex::new(None));
            self.camera_job = Some(CameraJob { kind: JobKind::BeforeWrite, started: std::time::Instant::now(), result, backup: None, agreed: None, as_b: false, timing: self.job_timing() });
        } else {
            self.before_write = Some(BeforeWrite { came: std::time::Instant::now(), path, cam });
        }
    }

    /// A few edits for the CAMSET_DEMO_EDITS test hook: the next offered value of the first Main page settings
    /// that can be edited, in the live settings and in the first memory: one row each (none the camera keeps in more
    /// than one record, whose edit takes others with it).
    fn demo_edits(&self) -> Vec<Action> {
        let Some(doc) = &self.doc else { return Vec::new() };
        let keys: Vec<String> = self.schema.camera.main_tiles.as_ref().and_then(|t| t.0.first())
            .map(|s| s.tiles.iter().flat_map(|t| t.keys_for(0)).map(str::to_string).collect()).unwrap_or_default();
        let mut out = Vec::new();
        for (section, n) in [(0, 3), (1, 1)] {
            let picked = keys.iter().filter_map(|k| self.schema.settings.iter().find(|s| s.key == *k))
                .filter(|s| s.scalar && s.values.len() >= 2 && (section == 0 || s.in_sets) && self.shape_ok_in(s, section) && self.locked_why(s, section).is_none() && s.copies.is_empty() && s.copy_of.is_none())
                .filter_map(|s| {
                    let cur = doc.value(section, s.slot())?;
                    let offered = s.offered(false);
                    let next = offered.iter().map(|(v, _)| *v).find(|v| *v != cur)?;
                    Some(Action::Set(section, s.slot(), next))
                })
                .take(n);
            out.extend(picked);
        }
        out
    }

    /// Put the window back where the last session left it, on one of the first frames, once the window knows the
    /// screen it opened on: only when that place shows it on that screen (a place on a second screen, or on a screen
    /// no longer there, is left for the window's own).
    fn restore_place(&mut self, ctx: &egui::Context) {
        let Some((pos, tries)) = self.place_to_restore else { return };
        let zoom = ctx.zoom_factor();
        let screen = ctx.input(|i| i.viewport().monitor_size).map(|s| [s.x * zoom, s.y * zoom]);
        let size = self.prefs.window.unwrap_or([1280.0, 860.0]);
        match screen {
            Some(screen) => {
                if place_on_screen(pos, size, screen) {
                    ctx.send_viewport_cmd(egui::ViewportCommand::OuterPosition(egui::pos2(pos[0] / zoom, pos[1] / zoom)));
                }
                self.place_to_restore = None;
            }
            None if tries >= 10 => self.place_to_restore = None,
            None => self.place_to_restore = Some((pos, tries + 1)),
        }
    }
}

impl eframe::App for App {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        let light = match self.prefs.theme() {
            "light" => true,
            "dark" => false,
            // as the computer is set (dark until it says)
            _ => ctx.system_theme() == Some(egui::Theme::Light),
        };
        ctx.set_visuals(tone::visuals(light));
        // the page an option's link asked for, the frame before
        let page = self.open_page.take();
        if let Some(key) = page {
            self.open_page_of(&key);
        }

        ctx.style_mut(|style| {
            match self.prefs.density {
                0 => {
                    style.spacing.item_spacing = egui::vec2(6.0, 3.0);
                    style.spacing.button_padding = egui::vec2(5.0, 2.0);
                }
                1 => {
                    style.spacing.item_spacing = egui::vec2(8.0, 6.0);
                    style.spacing.button_padding = egui::vec2(7.0, 4.0);
                }
                _ => {
                    style.spacing.item_spacing = egui::vec2(10.0, 9.0);
                    style.spacing.button_padding = egui::vec2(9.0, 6.0);
                }
            }
            style.text_styles = [
                (TextStyle::Small, FontId::new(12.0, FontFamily::Proportional)),
                (TextStyle::Body, FontId::new(14.0, FontFamily::Proportional)),
                (TextStyle::Button, FontId::new(14.0, FontFamily::Proportional)),
                (TextStyle::Monospace, FontId::new(13.0, FontFamily::Monospace)),
                (TextStyle::Heading, FontId::new(19.0, FontFamily::Proportional)),
            ]
            .into();
        });

        ctx.options_mut(|o| o.zoom_with_keyboard = false);
        ctx.set_zoom_factor(self.prefs.clean_zoom());

        // shortcuts: zoom in, out, reset
        let reset_zoom = ctx.input_mut(|i| i.consume_shortcut(&egui::gui_zoom::kb_shortcuts::ZOOM_RESET));
        let inc_zoom = ctx.input_mut(|i| {
            i.consume_shortcut(&egui::gui_zoom::kb_shortcuts::ZOOM_IN)
                || i.consume_shortcut(&egui::gui_zoom::kb_shortcuts::ZOOM_IN_SECONDARY)
        });
        let dec_zoom = ctx.input_mut(|i| i.consume_shortcut(&egui::gui_zoom::kb_shortcuts::ZOOM_OUT));
        if reset_zoom {
            self.prefs.reset_zoom();
            self.prefs.save();
            ctx.set_zoom_factor(self.prefs.clean_zoom());
        } else if inc_zoom {
            self.prefs.step_zoom(0.1);
            self.prefs.save();
            ctx.set_zoom_factor(self.prefs.clean_zoom());
        } else if dec_zoom {
            self.prefs.step_zoom(-0.1);
            self.prefs.save();
            ctx.set_zoom_factor(self.prefs.clean_zoom());
        }

        // drag and drop: first file opens, a second one (or one dropped later) compares
        let dropped: Vec<PathBuf> = ctx.input(|i| i.raw.dropped_files.iter().filter_map(|f| f.path.clone()).collect());
        for p in dropped {
            if self.doc.is_none() { self.open(p) } else { self.open_compare(p) }
        }
        // a file dialog's answer (they run on a helper thread: `ask`)
        while let Ok((kind, path)) = self.dialog_rx.try_recv() {
            self.on_dialog(kind, path);
        }
        // shortcuts: undo / redo, and arrow keys between the menu columns
        if !ctx.wants_keyboard_input() {
            let (undo, redo) = ctx.input(|i| (
                i.modifiers.command && !i.modifiers.shift && i.key_pressed(egui::Key::Z),
                (i.modifiers.command && i.modifiers.shift && i.key_pressed(egui::Key::Z)) || (i.modifiers.command && i.key_pressed(egui::Key::Y)),
            ));
            if undo { self.undo(); }
            if redo { self.redo(); }
        }
        self.keyboard_nav(ctx);
        // compare view: F3 / Shift+F3 (also Alt+Down / Alt+Up) step through the differences
        if self.mode == Mode::Compare && !ctx.wants_keyboard_input() {
            let (next, prev) = ctx.input(|i| (
                (i.key_pressed(egui::Key::F3) && !i.modifiers.shift) || (i.modifiers.alt && i.key_pressed(egui::Key::ArrowDown)),
                (i.key_pressed(egui::Key::F3) && i.modifiers.shift) || (i.modifiers.alt && i.key_pressed(egui::Key::ArrowUp)),
            ));
            if next { self.diff_step = 1; }
            if prev { self.diff_step = -1; }
        }
        // remember the window size and the session (files, mode, page) for the next start
        // (the window reports them in the editor's points, which the text size scales: kept at 100%, as it opens)
        self.restore_place(ctx);
        let zoom = ctx.zoom_factor();
        if let Some(r) = ctx.input(|i| i.viewport().inner_rect) {
            let size = [(r.width() * zoom).round(), (r.height() * zoom).round()];
            if self.prefs.window != Some(size) && size[0] > 200.0 && size[1] > 200.0 {
                self.prefs.window = Some(size);
                self.window_changed = Some(std::time::Instant::now());
            }
        }
        // the place once it is put back (or there is none to put back), so the first frame's default place is not kept
        if let (None, Some(r)) = (self.place_to_restore, ctx.input(|i| i.viewport().outer_rect)) {
            let pos = [(r.min.x * zoom).round(), (r.min.y * zoom).round()];
            if self.prefs.window_pos != Some(pos) {
                self.prefs.window_pos = Some(pos);
                self.window_changed = Some(std::time::Instant::now());
            }
        }
        // saved once the size has stayed put for a second, not on every frame of a resize
        if let Some(at) = self.window_changed {
            let wait = std::time::Duration::from_secs(1);
            if at.elapsed() >= wait {
                self.window_changed = None;
                self.prefs.save();
            } else {
                ctx.request_repaint_after(wait - at.elapsed());
            }
        }
        // closing: unsaved edits, or a camera write and its check, are not given up without a question (`guard`)
        let closing = ctx.input(|i| i.viewport().close_requested());
        if closing && !self.close_ok && self.screenshot.is_none() && (self.unsaved() > 0 || self.writing()) {
            ctx.send_viewport_cmd(egui::ViewportCommand::CancelClose);
            self.guard(Replace::Quit);
        }
        if self.close_ok && !closing {
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
        }
        // a jump to a setting names its tab: the page that shows that tab's settings is the one shown (`shown_view`)
        let view = std::mem::replace(&mut self.view, View::Main);
        self.view = self.shown_view(view);
        let session = (self.mode == Mode::Compare, self.target, self.view.clone());
        if closing || (self.prefs.compare_mode, self.prefs.target) != (session.0, session.1)
            || self.prefs.view.as_deref() != Some(session.2.key())
        {
            self.remember_session();
        }
        self.settings_window(ctx);
        self.pending_window(ctx);
        self.camera_report_window(ctx);
        self.connect_window(ctx);
        self.history_window(ctx);
        self.backups_window(ctx);
        self.unchecked_window(ctx);
        self.def_replace_window(ctx);
        self.recovery_window(ctx);
        self.about_window(ctx);
        self.changes_window(ctx);
        self.unsaved_window(ctx);
        self.shortcuts(ctx);
        self.poll_camera_job();
        self.note_foreign();
        self.web_poll(ctx);
        if self.camera_job.is_some() {
            ctx.request_repaint_after(std::time::Duration::from_millis(300));
        }

        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.add_space(4.0);
            self.top_bar(ui);
            ui.add_space(4.0);
        });
        self.log_status();
        self.log_window(ctx);
        self.toast_ui(ctx);
        egui::TopBottomPanel::bottom("status").show(ctx, |ui| {
            ui.horizontal(|ui| {
                let n = self.doc.as_ref().map(|d| d.changes().len()).unwrap_or(0);
                ui.label(if n > 0 { RichText::new(format!("{EDIT_MARK} {}", self.unsaved_words(n))).color(tone::edit(ui.visuals())) } else { RichText::new("No edits") });
                ui.separator();
                // the room the right end keeps: the editor's version always, the web page's address while it is on
                let room = ui.available_width() - Self::version_label_width(ui) - if self.web.is_some() { 280.0 } else { 0.0 };
                self.status_line(ui, room);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    self.version_label(ui);
                    if let Some(w) = &self.web {
                        if ui.link(format!("Web page on · {}", w.url)).on_hover_text("Open in a browser on another computer or a phone; the access code is in Settings").clicked() {
                            self.show_settings = true;
                            self.settings_tab = SettingsTab::Definitions;
                        }
                    }
                });
            });
        });
        if self.mode == Mode::Edit && self.doc.is_some() {
            egui::SidePanel::left("tabs").resizable(true).default_width(190.0).show(ctx, |ui| self.side_bar(ui));
        }
        if self.mode == Mode::Compare && !self.compare_records && self.doc.is_some() && self.cols.len() >= 2 {
            egui::SidePanel::right("minimap").resizable(false).exact_width(20.0).show_separator_line(false)
                .frame(egui::Frame::new().inner_margin(egui::Margin::symmetric(3, 4)).fill(ctx.style().visuals.panel_fill))
                .show(ctx, |ui| self.minimap(ui));
        }
        let actions = egui::CentralPanel::default()
            .show(ctx, |ui| {
                if let Some(job) = &self.camera_job {
                    let (title, line, bar) = job.progress();
                    let bg = tone::raised(&ctx.style().visuals);
                    egui::Frame::new().fill(bg).corner_radius(6).inner_margin(12).show(ui, |ui| {
                        ui.set_width(ui.available_width());
                        ui.horizontal(|ui| {
                            ui.spinner();
                            ui.label(RichText::new(title).strong().size(16.0));
                        });
                        match bar {
                            Some(f) => { ui.add(egui::ProgressBar::new(f.clamp(0.0, 1.0)).text(line)); }
                            None => { ui.label(RichText::new(line).color(tone::weak(ui.visuals()))); }
                        }
                    });
                    ui.add_space(6.0);
                }
                if self.doc.is_none() {
                    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| self.welcome_view(ui));
                    return Vec::new();
                }
                match (self.mode, self.view.clone()) {
                    (Mode::Compare, _) => egui::ScrollArea::both().auto_shrink([false, false]).show(ui, |ui| if self.compare_records { self.records_matrix(ui) } else { self.matrix_view(ui) }).inner,
                    (Mode::Edit, View::Tab(t)) => self.menu_view(ui, &t),
                    (Mode::Edit, v) => egui::ScrollArea::both().auto_shrink([false, false]).show(ui, |ui| match v {
                        View::Main => self.main_view(ui),
                        View::Changes => self.changes_view(ui),
                        View::Memories => self.memories_view(ui),
                        View::MyMenu => self.mymenu_view(ui),
                        View::Exposure => self.exposure_view(ui),
                        View::Search => self.search_view(ui),
                        View::Records => self.records_view(ui),
                        _ => self.unmapped_view(ui),
                    }).inner,
                }
            })
            .inner;
        self.apply(actions);
        self.journal_tick(ctx);

        if let Some((path, frames)) = &mut self.screenshot {
            *frames += 1;
            if *frames == 15 {
                ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(Default::default()));
            }
            let shot = ctx.input(|i| i.raw.events.iter().find_map(|e| if let egui::Event::Screenshot { image, .. } = e { Some(image.clone()) } else { None }));
            if let Some(img) = shot {
                let [w, h] = img.size;
                let rgba: Vec<u8> = img.pixels.iter().flat_map(|c| c.to_array()).collect();
                let _ = image::save_buffer(&*path, &rgba, w as u32, h as u32, image::ExtendedColorType::Rgba8);
                ctx.send_viewport_cmd(egui::ViewportCommand::Close);
            }
            ctx.request_repaint();
        }
    }

    /// The window closes as it should: the journal of unsaved edits goes (they were saved, or thrown away when asked).
    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        self.end_session();
    }
}
