//! The Settings window, its About tab among the others, its Changes window, the status bar's version (a click opens
//! Settings on the About tab), and the switches that only Expert mode shows.

use crate::*;

/// The editor's version alone, `version` in Cargo.toml ("0.2.0"): the window's title and the status bar give it, short.
pub(crate) fn version_short() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// The commit a build made in a git checkout was built from ("1a2b3c4"; build.rs); none for any other build.
pub(crate) fn build_hash() -> Option<&'static str> {
    match env!("CAMSET_GIT_HASH") {
        "" => None,
        hash => Some(hash),
    }
}

/// The editor's version as the status bar's hover, Changes, About's Copy details, the web page and a crash log give
/// it: `version_short` and, for a build made in a git checkout, its commit ("0.2.0 (build 1a2b3c4)").
pub(crate) fn version_words() -> String {
    match build_hash() {
        None => version_short().to_string(),
        Some(hash) => format!("{} (build {hash})", version_short()),
    }
}

/// The window's title: the editor's name and its short version ("Camset Editor 0.2.0").
pub(crate) fn window_title() -> String {
    format!("Camset Editor {}", version_short())
}

/// What the welcome page and Settings > About say, in the window and on the web page alike.
pub(crate) const NOT_SONY: &str = "Independent project; not affiliated with or endorsed by Sony.";

/// The project's pages, from Cargo.toml (`repository`, `homepage`; mkdocs.yml names the same, a test holds them
/// together): Settings > About links to them, in the window and on the web page, and problems are reported on the
/// issues page.
pub(crate) const PROJECT_URL: &str = env!("CARGO_PKG_REPOSITORY");
pub(crate) const DOCS_URL: &str = env!("CARGO_PKG_HOMEPAGE");
pub(crate) const ISSUES_URL: &str = concat!(env!("CARGO_PKG_REPOSITORY"), "/issues");

/// About's links, in the window and on the web page alike: (words, address, what it opens).
pub(crate) const ABOUT_LINKS: [(&str, &str, &str); 3] = [
    ("Project page", PROJECT_URL, "The editor's source code and releases, on GitHub"),
    ("Documentation", DOCS_URL, "How to use the editor, and how a camera is mapped"),
    ("Report a problem", ISSUES_URL, "Tell the project about a problem, on GitHub: Copy details first, to paste into it"),
];

/// The licence (Cargo.toml's `license`) and LICENSE's copyright line, as About gives them ("MIT licence. Copyright (c)
/// 2026 Camset contributors."): the macOS app's About panel and the Windows program's details take that same line from
/// LICENSE when they are built.
pub(crate) fn licence_words() -> String {
    const LICENSE: &str = include_str!("../../../LICENSE");
    let licence = env!("CARGO_PKG_LICENSE");
    match LICENSE.lines().map(str::trim).find(|l| l.starts_with("Copyright (c) ")) {
        Some(c) => format!("{licence} licence. {}.", c.trim_end_matches('.')),
        None => format!("{licence} licence."),
    }
}

/// The system the editor runs on, for About and a message about a problem: its name, its version where a file the
/// system keeps gives it (macOS, Linux; Windows keeps it where only a system call reaches, so it is left out there),
/// and the processor the program was built for ("macOS 15.2 (aarch64)", "Windows (x86_64)"). Read once.
pub(crate) fn system_words() -> &'static str {
    static WORDS: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    WORDS.get_or_init(|| {
        let os = std::env::consts::OS;
        // cfg! rather than #[cfg], so every system's build compiles all of it; on Linux /usr/lib/os-release when there
        // is no /etc/os-release, as the os-release specification has it
        let files: &[&str] = if cfg!(target_os = "macos") { &["/System/Library/CoreServices/SystemVersion.plist"] } else if cfg!(target_os = "linux") { &["/etc/os-release", "/usr/lib/os-release"] } else { &[] };
        let text = files.iter().find_map(|f| std::fs::read_to_string(f).ok()).unwrap_or_default();
        format!("{} ({})", system_name(os, &text), std::env::consts::ARCH)
    })
}

/// A system's name and version from `std::env::consts::OS` and the file `system_words` read: macOS's
/// SystemVersion.plist (its ProductVersion), Linux's os-release (its PRETTY_NAME, "Ubuntu 26.04 LTS"); the name alone
/// when the file says nothing usable. Short and printable only, as it goes into About and a copied report.
pub(crate) fn system_name(os: &str, text: &str) -> String {
    let fit = |v: &str| -> Option<String> {
        let v = v.trim().trim_matches(|c| c == '"' || c == '\'').trim();
        (!v.is_empty() && v.len() <= 60 && v.chars().all(|c| !c.is_control())).then(|| v.to_string())
    };
    match os {
        "macos" => {
            let version = text.split_once("<key>ProductVersion</key>").and_then(|(_, rest)| rest.split_once("<string>")).and_then(|(_, rest)| rest.split_once("</string>")).map(|(v, _)| v)
                .filter(|v| !v.is_empty() && v.chars().all(|c| c.is_ascii_digit() || c == '.'));
            version.map_or_else(|| "macOS".to_string(), |v| format!("macOS {v}"))
        }
        "linux" => text.lines().find_map(|l| l.strip_prefix("PRETTY_NAME=")).and_then(fit).unwrap_or_else(|| "Linux".to_string()),
        "windows" => "Windows".to_string(),
        other => other.to_string(),
    }
}

/// The third-party licences button of Settings > About: it opens the licences page the packages carry in the browser,
/// and says so greyed out in a build that has none.
fn licences_button(ui: &mut egui::Ui) {
    let licences = licences_page();
    let (label, hover) = match &licences {
        Some(p) => ("Third-party licences", format!("The licences of the crates and fonts built into the editor, in your browser ({})", shown_path(p))),
        None => ("Third-party licences: not in a development build", "The editor's packages carry the licences page (THIRD_PARTY_LICENSES.html); a build of your own has it once cargo about writes it into editor/target/dist (see editor/about.toml).".to_string()),
    };
    if ui.add_enabled(licences.is_some(), egui::Button::new(label)).on_hover_text(&hover).on_disabled_hover_text(&hover).clicked() {
        if let Some(p) = &licences { open_in_file_manager(p); }
    }
}

/// What changed, release by release (CHANGELOG.md), built into the program: Settings > About > Changes shows it.
pub(crate) const CHANGELOG: &str = include_str!("../../../CHANGELOG.md");

/// The changelog as Settings > About > Changes shows it: (kind, text), kind 2 a release's heading ("## …"), 3 a
/// part's ("### …"), 1 a point ("- …", its following lines joined), 0 a paragraph. Markdown's marks are taken out:
/// code's backticks, a link's address (its words stay), and the title.
pub(crate) fn changelog_blocks(md: &str) -> Vec<(u8, String)> {
    fn plain(t: &str) -> String {
        let mut out = String::new();
        let mut rest = t.replace('`', "");
        // [words](address) → words
        while let Some(open) = rest.find('[') {
            let Some(mid) = rest[open..].find("](").map(|m| open + m) else { break };
            let Some(close) = rest[mid..].find(')').map(|c| mid + c) else { break };
            out.push_str(&rest[..open]);
            out.push_str(&rest[open + 1..mid]);
            rest = rest[close + 1..].to_string();
        }
        out.push_str(&rest);
        out
    }
    let mut blocks: Vec<(u8, String)> = Vec::new();
    let mut joining = false;
    for line in md.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with("# ") {
            joining = false;
            continue;
        }
        if let Some(h) = t.strip_prefix("### ") {
            blocks.push((3, plain(h)));
            joining = false;
        } else if let Some(h) = t.strip_prefix("## ") {
            blocks.push((2, plain(h)));
            joining = false;
        } else if let Some(p) = t.strip_prefix("- ") {
            blocks.push((1, plain(p)));
            joining = true;
        } else if joining {
            // the next line of a point or a paragraph
            if let Some(b) = blocks.last_mut() {
                b.1.push(' ');
                b.1.push_str(&plain(t));
            }
        } else {
            blocks.push((0, plain(t)));
            joining = true;
        }
    }
    blocks
}

/// The Settings window's id: its title's, as egui gives a window by default, named here so that what brings it to the
/// front and unfolds it (`open_about`) finds the same window. Its fold state is egui's, under `.with("collapsing")`.
pub(crate) fn settings_window_id() -> egui::Id {
    egui::Id::new("Settings")
}

/// The Changes window's id, as `settings_window_id` names Settings'.
pub(crate) fn changes_window_id() -> egui::Id {
    egui::Id::new("Changes")
}

/// Whether Settings is over Changes, by their places in egui's order of the windows (back to front): Changes opens
/// over Settings, and the status bar's version (`open_about`) or a click brings Settings back over it. Changes is
/// taken to be on top when it cannot be told (either not drawn yet).
pub(crate) fn settings_over_changes(ctx: &egui::Context) -> bool {
    let at = |id: egui::Id| ctx.memory(|m| m.layer_ids().position(|l| l == egui::LayerId::new(egui::Order::Middle, id)));
    matches!((at(settings_window_id()), at(changes_window_id())), (Some(s), Some(c)) if s > c)
}

#[derive(Clone, Copy, PartialEq, Eq, Default, Debug)]
pub(crate) enum SettingsTab {
    #[default]
    Appearance,
    Camera,
    Editing,
    Files,
    Definitions,
    /// Which editor this is, the last tab: the status bar's version opens Settings on it (`open_about`).
    About,
}

impl SettingsTab {
    pub(crate) const ALL: [SettingsTab; 6] = [
        SettingsTab::Appearance,
        SettingsTab::Camera,
        SettingsTab::Editing,
        SettingsTab::Files,
        SettingsTab::Definitions,
        SettingsTab::About,
    ];

    pub(crate) fn label(&self) -> &'static str {
        match self {
            SettingsTab::Appearance => "🎨 Appearance",
            SettingsTab::Camera => "📷 Camera link",
            SettingsTab::Editing => "⚙ Editing & Compare",
            SettingsTab::Files => "📂 Backups & start-up",
            SettingsTab::Definitions => "📐 Camera support & web page",
            // U+2139, which egui's built-in emoji font (NotoEmoji) draws
            SettingsTab::About => "ℹ About",
        }
    }

    pub(crate) fn subtitle(&self) -> &'static str {
        match self {
            SettingsTab::Appearance => "Theme, text size, row spacing, keyboard shortcuts, and how setting names and values are shown.",
            SettingsTab::Camera => "USB or network connection, camera search and setup steps, known cameras, the camera login, and the camera link program.",
            SettingsTab::Editing => "How Compare and Memories start, and Expert mode for mapping work.",
            SettingsTab::Files => "The copies kept before saving or writing, what opens at start, and recent files.",
            SettingsTab::Definitions => "The files that tell the editor what each camera's settings mean, and the web page for a phone or tablet.",
            SettingsTab::About => "Which editor this is: its version, the system it runs on, the cameras it works with, the licence, the project's pages, what changed, and Copy details for a message about a problem.",
        }
    }
}

impl App {
    /// The proof line and badges are drawn only in Expert mode, with Settings' switch on (the window's and the page's rule).
    pub(crate) fn shows_proof(&self) -> bool { self.prefs.expert && self.prefs.show_proof }

    /// Record numbers beside setting names, likewise in Expert mode only.
    pub(crate) fn shows_record_ids(&self) -> bool { self.prefs.expert && self.prefs.show_record_ids }

    /// What turning Expert mode off hides again: its pages, the other memory sets, the raw switches, and a
    /// definition chosen by hand for the open file (the file is read with the one its header picks again).
    pub(crate) fn expert_off(&mut self) {
        if matches!(self.view, View::Unmapped | View::Records) { self.view = View::Main; }
        self.compare_records = false;
        if self.doc.as_ref().is_some_and(|d| d.override_def.is_some()) {
            self.override_definition(None);
        }
        if self.target != 0 && !self.schema.camera.is_dial(self.target) { self.target = 0; }
        let cam = &self.schema.camera;
        self.cols.retain(|c| c.section == 0 || cam.is_dial(c.section));
        self.allow_unobserved = false;
        self.allow_raw_edits = false;
        // the mapping team's switches draw nothing with Expert mode off; they come back with it as they were
        self.show_raw = false;
    }

    pub(crate) fn settings_card<R>(ui: &mut egui::Ui, title: &str, add_contents: impl FnOnce(&mut egui::Ui) -> R) -> R {
        let ret = egui::Frame::group(ui.style())
            .inner_margin(egui::Margin::same(12))
            .corner_radius(6.0)
            .show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                ui.label(RichText::new(title).strong().size(14.0));
                ui.add_space(6.0);
                add_contents(ui)
            })
            .inner;
        ui.add_space(8.0);
        ret
    }

    /// A card like `settings_card` that folds: a click on its title opens or folds it, and `open` says which.
    pub(crate) fn settings_card_folding(ui: &mut egui::Ui, title: &str, open: &mut bool, add_contents: impl FnOnce(&mut egui::Ui)) {
        egui::Frame::group(ui.style())
            .inner_margin(egui::Margin::same(12))
            .corner_radius(6.0)
            .show(ui, |ui| {
                ui.set_min_width(ui.available_width());
                let r = egui::CollapsingHeader::new(RichText::new(title).strong().size(14.0))
                    .open(Some(*open))
                    .show_unindented(ui, |ui| {
                        ui.add_space(2.0);
                        add_contents(ui)
                    });
                if r.header_response.clicked() {
                    *open = !*open;
                    ui.ctx().request_repaint();
                }
            });
        ui.add_space(8.0);
    }

    pub(crate) fn settings_window(&mut self, ctx: &egui::Context) {
        let mut open = self.show_settings;
        let mut changed = false;
        let mut reload = false;
        let mut open_file: Option<PathBuf> = None;
        let mut cards = CameraCardsOutcome::default();
        let id = settings_window_id();
        if std::mem::take(&mut self.raise_settings) && open {
            // opened from the status bar's version: over the other windows, and unfolded if its title bar folded it
            ctx.move_to_top(egui::LayerId::new(egui::Order::Middle, id));
            let mut fold = egui::collapsing_header::CollapsingState::load_with_default_open(ctx, id.with("collapsing"), true);
            fold.set_open(true);
            fold.store(ctx);
        }
        egui::Window::new("Settings")
            .id(id)
            .open(&mut open)
            .resizable(true)
            .default_width(860.0)
            .min_width(660.0)
            .show(ctx, |ui| {
                ui.horizontal_wrapped(|ui| {
                    ui.spacing_mut().button_padding = egui::vec2(8.0, 5.0);
                    for tab in SettingsTab::ALL {
                        ui.selectable_value(&mut self.settings_tab, tab, RichText::new(tab.label()).size(14.0).strong());
                    }
                });
                ui.separator();
                ui.label(RichText::new(self.settings_tab.subtitle()).small().color(tone::weak(ui.visuals())));
                ui.add_space(6.0);

                egui::ScrollArea::vertical()
                    .max_height(460.0)
                    .auto_shrink([false, true])
                    .show(ui, |ui| {
                        match self.settings_tab {
                            SettingsTab::Appearance => {
                                Self::settings_card(ui, "Theme and text size", |ui| {
                                    ui.horizontal(|ui| {
                                        ui.label("Theme:");
                                        for (t, label, hover) in [("system", "Follow the system", Some("Dark or light as this computer is set, changing when it does")), ("dark", "Dark", None), ("light", "Light", None)] {
                                            let r = ui.selectable_label(self.prefs.theme() == t, label);
                                            let r = match hover { Some(h) => r.on_hover_text(h), None => r };
                                            if r.clicked() {
                                                self.prefs.set_theme(t);
                                                changed = true;
                                            }
                                        }
                                    });
                                    ui.add_space(4.0);
                                    ui.horizontal(|ui| {
                                        ui.label("Text size:");
                                        let presets = [(0.9, "90%"), (1.0, "100%"), (1.15, "115%"), (1.3, "130%"), (1.5, "150%")];
                                        for (val, label) in presets {
                                            let active = (self.prefs.clean_zoom() - val).abs() < 0.02;
                                            if ui.selectable_label(active, label).clicked() {
                                                self.prefs.zoom = val;
                                                ctx.set_zoom_factor(val);
                                                changed = true;
                                            }
                                        }
                                        if named(ui.button("−"), "Smaller text").on_hover_text("Smaller text (Cmd/Ctrl −)").clicked() {
                                            self.prefs.step_zoom(-0.1);
                                            ctx.set_zoom_factor(self.prefs.clean_zoom());
                                            changed = true;
                                        }
                                        if named(ui.button("+"), "Larger text").on_hover_text("Larger text (Cmd/Ctrl +)").clicked() {
                                            self.prefs.step_zoom(0.1);
                                            ctx.set_zoom_factor(self.prefs.clean_zoom());
                                            changed = true;
                                        }
                                    });
                                    ui.label(RichText::new("Shortcut: Cmd/Ctrl + and −, or Cmd/Ctrl 0 for 100%.").small().color(tone::weak(ui.visuals())));
                                    ui.add_space(4.0);
                                    ui.horizontal(|ui| {
                                        ui.label("Row spacing:");
                                        if ui.selectable_label(self.prefs.density == 0, "Compact").clicked() {
                                            self.prefs.density = 0;
                                            changed = true;
                                        }
                                        if ui.selectable_label(self.prefs.density == 1, "Comfortable").clicked() {
                                            self.prefs.density = 1;
                                            changed = true;
                                        }
                                        if ui.selectable_label(self.prefs.density == 2, "Spacious").clicked() {
                                            self.prefs.density = 2;
                                            changed = true;
                                        }
                                    });
                                });

                                Self::settings_card(ui, "Keyboard shortcuts", |ui| {
                                    let f = |s: &egui::KeyboardShortcut| ctx.format_shortcut(s);
                                    let undo = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND, egui::Key::Z);
                                    let redo = egui::KeyboardShortcut::new(egui::Modifiers::COMMAND | egui::Modifiers::SHIFT, egui::Key::Z);
                                    let rows: Vec<(String, &str)> = vec![
                                        (f(&KEY_OPEN), "Open a settings file"),
                                        (f(&KEY_SAVE), "Save As"),
                                        (f(&KEY_FIND), "Search"),
                                        (f(&KEY_CLOSE), "Close the file (with unsaved edits it asks first)"),
                                        (f(&KEY_READ), "Read the camera (with the camera link program)"),
                                        (f(&KEY_SETTINGS), "Settings"),
                                        (format!("{} / {}", f(&undo), f(&redo)), "Undo / Redo"),
                                        ("F3 / Shift+F3".into(), "Edit: the next / previous edit. Compare: the next / previous difference (also Alt+Down / Alt+Up)"),
                                        ("← → ↑ ↓".into(), "Edit: move through the menu's columns, as on the camera"),
                                        ("Esc".into(), "Close the window on top, or clear the search"),
                                        ("Cmd/Ctrl + / − / 0".into(), "Larger / smaller text / 100%"),
                                    ];
                                    egui::Grid::new("shortcuts").num_columns(2).spacing([16.0, 3.0]).show(ui, |ui| {
                                        for (keys, what) in rows {
                                            ui.label(RichText::new(keys).monospace());
                                            ui.label(what);
                                            ui.end_row();
                                        }
                                    });
                                });

                            }

                            SettingsTab::Camera => {
                                cards = self.camera_cards(ui);
                            }

                            SettingsTab::Editing => {
                                Self::settings_card(ui, "Compare and Memories", |ui| {
                                    if ui.checkbox(&mut self.prefs.matrix_only_diff, "Compare starts with only the rows that differ").changed() {
                                        self.matrix_only_diff = self.prefs.matrix_only_diff;
                                        changed = true;
                                    }
                                    // the first two shooting modes the definition names (Stills, Movie, …)
                                    let label = match self.schema.camera.more_columns_modes() {
                                        Some((first, second)) => format!("Compare starts with the {second} memories too, beside the live settings and the {first} memories"),
                                        None => "Compare starts with a second shooting mode's memories too".to_string(),
                                    };
                                    if ui.checkbox(&mut self.prefs.all_memory_cols, label).changed() {
                                        changed = true;
                                        if self.doc.is_some() && self.cols.iter().all(|c| c.src == Src::A) {
                                            self.cols = self.start_cols();
                                        }
                                    }
                                });

                                Self::settings_card(ui, "Expert mode", |ui| {
                                    if ui.checkbox(&mut self.prefs.expert, "Expert mode: also show the settings without a name yet, the duplicate copies the camera keeps, and every memory").on_hover_text("For mapping work and support: record numbers and the record map, the settings the editor cannot name yet, the copies the camera keeps twice, every memory in the file, and the numbers the camera stores").changed() {
                                        changed = true;
                                        if !self.prefs.expert {
                                            self.expert_off();
                                        } else {
                                            self.allow_unobserved = self.prefs.allow_unobserved;
                                            self.allow_raw_edits = self.prefs.allow_raw_edits;
                                            self.show_raw = self.prefs.show_raw;
                                        }
                                    }
                                    ui.indent("expert_indented", |ui| {
                                        ui.add_enabled_ui(self.prefs.expert, |ui| {
                                            if ui.checkbox(&mut self.prefs.allow_unobserved, "Offer values not checked on the camera yet (the camera may refuse a file holding one)").changed() {
                                                self.allow_unobserved = self.prefs.allow_unobserved;
                                                changed = true;
                                            }
                                            if ui.checkbox(&mut self.prefs.allow_raw_edits, "Allow changing the stored number of the settings without a name yet").changed() {
                                                self.allow_raw_edits = self.prefs.allow_raw_edits;
                                                changed = true;
                                            }
                                        });
                                        // the mapping team's names and values, shown only while Expert mode is on
                                        if self.prefs.expert {
                                            if ui.checkbox(&mut self.prefs.show_record_ids, "Show each setting's record number beside its name (for mapping work)").changed() {
                                                changed = true;
                                            }
                                            if ui.checkbox(&mut self.prefs.show_proof, "Show whether each setting was proved on the camera (e.g. Proved on the camera (3/3))").changed() {
                                                changed = true;
                                            }
                                            if ui.checkbox(&mut self.prefs.show_raw, "Show the number the camera stores beside each value's name").changed() {
                                                self.show_raw = self.prefs.show_raw;
                                                changed = true;
                                            }
                                        }
                                    });
                                });
                            }

                            SettingsTab::Files => {
                                Self::settings_card(ui, "Copies kept", |ui| {
                                    ui.add(egui::Label::new(RichText::new(format!("Kept copies: files as first opened in {}, the camera's settings in {}", shown_path(&Self::originals_dir()), shown_path(&Self::camera_dir()))).small().color(tone::weak(ui.visuals()))).wrap());
                                    if ui.checkbox(&mut self.prefs.backup_on_save, "Keep a copy of a file before Save As replaces it").changed() {
                                        changed = true;
                                    }
                                    ui.horizontal(|ui| {
                                        if ui.button("📂 View backups…").clicked() {
                                            self.show_backups = true;
                                            self.backups = Self::list_backups();
                                        }
                                        if ui.button("Open backups folder").clicked() {
                                            let dir = Self::originals_dir();
                                            let _ = std::fs::create_dir_all(&dir);
                                            open_in_file_manager(&dir);
                                        }
                                    });
                                });

                                Self::settings_card(ui, "Start-up and recent files", |ui| {
                                    if ui.checkbox(&mut self.prefs.reopen_last, "Reopen the last files, mode and page at start").changed() {
                                        changed = true;
                                    }
                                    ui.add_space(4.0);
                                    ui.label(RichText::new("Recent files:").strong());
                                    if self.prefs.recent.is_empty() {
                                        ui.label(RichText::new("none yet").color(tone::weak(ui.visuals())));
                                    } else {
                                        for r in self.prefs.recent.clone() {
                                            ui.horizontal(|ui| {
                                                if ui.small_button("Open").clicked() {
                                                    open_file = Some(PathBuf::from(&r));
                                                }
                                                ui.add(egui::Label::new(RichText::new(shown_path(Path::new(&r))).monospace().small()).wrap());
                                            });
                                        }
                                        if ui.small_button("Clear list").clicked() {
                                            self.prefs.recent.clear();
                                            changed = true;
                                        }
                                    }
                                });
                            }

                            SettingsTab::Definitions => {
                                Self::settings_card(ui, "Camera definitions", |ui| {
                                    ui.label(RichText::new("A camera definition tells the editor what every setting of one camera model and firmware means. The built-in ones come with the editor. Add your own, such as one for a camera you mapped with the kit, and the editor uses it for that camera's files, in place of a built-in one of the same model and firmware.").small().color(tone::weak(ui.visuals())));
                                    ui.horizontal(|ui| {
                                        if ui.button("Add definition…").on_hover_text("Choose a definition file (.json): it is checked, then copied into your definitions folder").clicked() {
                                            self.ask(ui.ctx(), DialogKind::AddDefinition, None);
                                        }
                                        if ui.button("Open folder").on_hover_text("Your definitions folder, where Add definition… copies them: remove one there, then Reload").clicked() {
                                            let dir = self.defs.user_dir.clone();
                                            match std::fs::create_dir_all(&dir) {
                                                Ok(()) => open_in_file_manager(&dir),
                                                Err(e) => self.status = format!("Your definitions folder could not be made: {}", io_words(&e, true)),
                                            }
                                        }
                                        if ui.button("Reload").on_hover_text("Read every definition again").clicked() {
                                            reload = true;
                                        }
                                    });
                                    if self.defs.shipped_dir.is_none() {
                                        let looked: Vec<String> = self.defs.looked_in.iter().map(|d| shown_path(d)).collect();
                                        ui.label(RichText::new("The definitions that come with the editor were not found: the program may have been moved without its definitions folder. Reinstall the editor, or add a definition.").color(tone::bad(ui.visuals())))
                                            .on_hover_text(format!("Looked in:\n{}", looked.join("\n")));
                                    }
                                    ui.add_space(4.0);
                                    let in_use = self.schema.origin.clone();
                                    // the Proved column is mapping work: Expert mode only
                                    let expert = self.prefs.expert;
                                    egui::Grid::new("schema_list").striped(true).num_columns(if expert { 6 } else { 5 }).spacing([14.0, 4.0]).show(ui, |ui| {
                                        for h in ["Model", "Firmware", "Source", "Settings", "Proved", "File"] {
                                            if expert || h != "Proved" { ui.strong(h); }
                                        }
                                        ui.end_row();
                                        for s in &self.defs.list {
                                            let active = s.origin == in_use;
                                            let (ok, weak) = (tone::ok(ui.visuals()), tone::weak(ui.visuals()));
                                            let mark = |t: String| if active { RichText::new(t).strong().color(ok) } else if s.overridden { RichText::new(t).color(weak) } else { RichText::new(t) };
                                            let source = match (&s.origin, s.overrides, s.overridden) {
                                                (_, true, _) => "yours, in place of the built-in one".to_string(),
                                                (_, _, true) => "built-in, not used: yours is".to_string(),
                                                (o, _, _) => o.word().to_string(),
                                            };
                                            ui.label(mark(s.model.clone()));
                                            ui.label(mark(s.firmware().to_string()));
                                            ui.label(mark(source));
                                            ui.label(mark(s.settings.len().to_string()));
                                            if expert {
                                                ui.label(mark(s.proved().to_string())).on_hover_text("Settings proved on the camera: each option chosen in its menu and the file compared");
                                            }
                                            let file = s.origin.path().and_then(Path::file_name).unwrap_or_default().to_string_lossy().to_string();
                                            let path = s.origin.path().map(shown_path).unwrap_or_default();
                                            ui.label(mark(file)).on_hover_text(if active { format!("{path}\nIn use for the open file") } else { path });
                                            ui.end_row();
                                        }
                                    });
                                    for (p, why) in &self.defs.rejected {
                                        let name = p.file_name().unwrap_or_default().to_string_lossy();
                                        ui.label(RichText::new(format!("Not used: {name}: {why}.")).small().color(tone::caution(ui.visuals())))
                                            .on_hover_text(shown_path(p));
                                    }
                                    for (p, name) in &self.defs.misnamed {
                                        let file = p.file_name().unwrap_or_default().to_string_lossy();
                                        ui.label(RichText::new(format!("{file} is used, but its name should be {name}.")).small().color(tone::weak(ui.visuals()))).on_hover_text(shown_path(p));
                                    }
                                    ui.add(egui::Label::new(RichText::new(format!("Yours: {}", shown_path(&self.defs.user_dir))).monospace().small().color(tone::weak(ui.visuals()))).wrap());
                                    if let Some(d) = &self.defs.shipped_dir {
                                        ui.add(egui::Label::new(RichText::new(format!("Built in: {}", shown_path(d))).monospace().small().color(tone::weak(ui.visuals()))).wrap());
                                    }
                                    if !self.schema.help_src.is_empty() {
                                        // the file's name; its folder and who wrote it in Expert mode
                                        let src = if self.prefs.expert { self.schema.help_src.clone() } else { self.schema.help_file_name() };
                                        ui.add(egui::Label::new(RichText::new(format!("The camera's own help text: {src}")).small().color(tone::weak(ui.visuals()))).wrap());
                                    }
                                    // a help file of a definition's name that is another camera's (or not a help file): not used, and why
                                    for s in &self.defs.list {
                                        for ((p, _), line) in s.help_refused.iter().zip(s.help_refusals()) {
                                            let l = ui.add(egui::Label::new(RichText::new(line).small().color(tone::caution(ui.visuals()))).wrap());
                                            if self.prefs.expert {
                                                l.on_hover_text(shown_path(p));
                                            }
                                        }
                                    }
                                });

                                Self::settings_card(ui, "Web page for a phone or tablet", |ui| {
                                    if self.web_settings(ui) {
                                        changed = true;
                                    }
                                });
                            }

                            SettingsTab::About => {
                                self.about_cards(ui);
                            }
                        }
                    });

                // where the settings are kept; the version, the not-affiliated line, Changes and the licences are the
                // About tab's alone (the status bar's version, under this window, opens it)
                ui.separator();
                ui.label(RichText::new("⚙ Settings are kept on this computer").small().color(tone::weak(ui.visuals())))
                    .on_hover_text(format!("Preferences file: {}", shown_path(&Prefs::path())));
            });
        self.show_settings = open;
        if reload {
            self.reload_definitions();
            self.status = self.definitions_loaded();
        }
        if changed {
            self.prefs.save();
        }
        self.camera_cards_done(cards);
        if let Some(p) = open_file {
            self.open(p);
            self.show_settings = false;
        }
    }

    /// Settings > About > Changes: the changelog built into this editor, release by release.
    pub(crate) fn changes_window(&mut self, ctx: &egui::Context) {
        if !self.show_changes { return; }
        let mut open = true;
        egui::Window::new("Changes").id(changes_window_id()).open(&mut open).resizable(true).default_width(640.0).default_height(520.0).show(ctx, |ui| {
            ui.label(RichText::new(format!("Camset Editor {}", version_words())).color(tone::weak(ui.visuals())));
            ui.add_space(4.0);
            egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
                for (kind, text) in changelog_blocks(CHANGELOG) {
                    match kind {
                        2 => { ui.add_space(6.0); ui.heading(text); }
                        3 => { ui.add_space(4.0); ui.label(RichText::new(text).strong()); }
                        1 => { ui.horizontal_top(|ui| { ui.label("•"); ui.add(egui::Label::new(text).wrap()); }); }
                        _ => { ui.add(egui::Label::new(text).wrap()); }
                    }
                }
            });
        });
        self.show_changes = open;
    }

    /// Settings, open on its About tab: what the status bar's version opens, the one version that can be clicked. Open
    /// already, it comes over the other windows and unfolds (`raise_settings`).
    pub(crate) fn open_about(&mut self) {
        self.show_settings = true;
        self.settings_tab = SettingsTab::About;
        self.raise_settings = true;
    }

    /// The status bar's version, at its right end: the editor's name and short version, weak and small, the whole
    /// version on hover; a click opens Settings on its About tab (`open_about`).
    pub(crate) fn version_label(&mut self, ui: &mut egui::Ui) {
        let words = format!("Camset Editor {}", version_short());
        if ui.add(egui::Button::new(RichText::new(words).small().color(tone::weak(ui.visuals()))).frame(false))
            .on_hover_text(format!("Camset Editor {}\nClick for Settings > About", version_words())).clicked() {
            self.open_about();
        }
    }

    /// How wide the status bar's version is (`version_label`), so the status line leaves it room.
    pub(crate) fn version_label_width(ui: &egui::Ui) -> f32 {
        let words = format!("Camset Editor {}", version_short());
        let w = ui.fonts(|f| f.layout_no_wrap(words, egui::TextStyle::Small.resolve(ui.style()), Color32::PLACEHOLDER)).size().x;
        w + 2.0 * ui.spacing().button_padding.x + 2.0 * ui.spacing().item_spacing.x
    }

    /// Whether the camera link program is there, in About's words (`have_helper`, which looks again every few seconds).
    pub(crate) fn helper_words(&self) -> &'static str {
        if self.have_helper() { "Camera link program: found" } else { "Camera link program: not found (files only)" }
    }

    /// What About's Copy details copies, for a message about a problem: the editor's version and build, the system,
    /// the cameras it works with by model and firmware (with the names the definitions in use give them, which for a
    /// definition the person added are that file's words), and whether the camera link program is there. No file,
    /// folder, user name, network address or camera serial.
    pub(crate) fn about_details(&self) -> String {
        let models = self.defs.works_with();
        let cameras = if models.is_empty() { "no camera definition".to_string() } else { models.join(", ") };
        format!("Camset Editor {}\nSystem: {}\nWorks with: {cameras}\n{}", version_words(), system_words(), self.helper_words())
    }

    /// Settings > About, the last tab: which editor this is (its version, and the commit of a build made from the
    /// repository), the system it runs on, the cameras it works with, whether the camera link program is there, the
    /// licence, the project's pages, and the ways to what changed, to the licences and to a copy of these details for a
    /// message about a problem. The status bar's version opens Settings on it (`open_about`), on every system: Windows
    /// and Linux have no menu bar, and macOS's application menu opens the system's own About panel instead (the
    /// Info.plist's name, version and copyright line).
    pub(crate) fn about_cards(&mut self, ui: &mut egui::Ui) {
        let weak = tone::weak(ui.visuals());
        Self::settings_card(ui, "Camset Editor", |ui| {
            ui.label(format!("Version {}", version_short()));
            if let Some(hash) = build_hash() {
                ui.label(format!("Build {hash}")).on_hover_text("The commit it was built from, in the project's repository");
            }
            ui.label(format!("System: {}", system_words())).on_hover_text("The computer the editor runs on, and the processor the program was built for");
            let models = self.defs.works_with();
            if !models.is_empty() {
                ui.label(RichText::new(format!("Works with: {}", models.join(", "))).color(weak))
                    .on_hover_text("The cameras and firmware the editor has a definition for: built in, or added in Settings > Camera support & web page");
            }
            ui.label(RichText::new(self.helper_words()).color(weak))
                .on_hover_text("The program that reads and writes a camera over USB or the network; without it the editor opens files only");
            ui.add_space(4.0);
            ui.horizontal_wrapped(|ui| {
                let details = self.about_details();
                if ui.button("Copy details").on_hover_text(format!("Copies these lines, to paste into a message about a problem:\n{details}")).clicked() {
                    ui.ctx().copy_text(details);
                    self.status = "About's details copied, to paste into a message about a problem".into();
                }
                if ui.button("Changes").on_hover_text("What changed, release by release").clicked() {
                    self.show_changes = true;
                    // an open Changes that Settings covers comes back over it (a new one is on top anyway)
                    ui.ctx().move_to_top(egui::LayerId::new(egui::Order::Middle, changes_window_id()));
                }
            });
        });
        Self::settings_card(ui, "The project's pages", |ui| {
            // in the browser (egui opens a link with the system's own handler)
            ui.horizontal_wrapped(|ui| {
                // a link whose words can be selected is told to a screen reader as plain text (egui 0.31's text
                // selection sets its role to Label); not selectable, it is a link, reached with Tab
                ui.style_mut().interaction.selectable_labels = false;
                for (words, url, what) in ABOUT_LINKS {
                    ui.hyperlink_to(words, url).on_hover_text(format!("{what}\n{url}"));
                }
            });
        });
        Self::settings_card(ui, "Licence", |ui| {
            ui.label(RichText::new(licence_words()).color(weak));
            ui.label(RichText::new(NOT_SONY).color(weak));
            ui.add_space(4.0);
            licences_button(ui);
        });
    }
}
