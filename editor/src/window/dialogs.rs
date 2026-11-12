//! The file dialogs, run on a helper thread so the window never stalls, and what each answer does.

use crate::*;

/// What a file dialog asks for.
#[derive(Clone, Copy, Debug, PartialEq)]
enum Verb {
    /// a file to open
    Open,
    /// a name to save to
    Save,
}

/// The files a dialog lists: a name and the extensions (None: every file).
pub(crate) type Filter = (&'static str, &'static [&'static str]);

/// The files the dialogs that open or save camera settings list.
const DAT_FILTER: Filter = ("Settings files (CAMSET*.DAT)", &["DAT", "dat"]);

/// The files Add definition… lists.
const DEFINITION_FILTER: Filter = ("Camera definition", &["json", "JSON"]);

/// A file dialog the editor opened, carried to its answer (`App::ask`, then `App::on_dialog`).
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum DialogKind {
    /// The camera cards' camera link helper: the camset_probe program.
    ProbePath,
    /// Settings, Add definition…: a camera definition to copy into the user's folder.
    AddDefinition,
    /// Open…: file A, the one edited (Edit mode, Compare's A, the welcome page).
    OpenA,
    /// Compare's B: the file compared against A.
    OpenB,
    /// Compare's Base: the file A and B both started from.
    OpenBase,
    /// Save As and Save A As: the edited file, named by the path it was opened from.
    SaveAs(PathBuf),
    /// Export CSV.
    ExportCsv,
    /// Describe for support…: the file's record layout (JSON), built when it was asked for.
    ExportLayout(String),
}

impl DialogKind {
    /// What the dialog asks for, and the files it lists.
    fn spec(&self) -> (Verb, Option<Filter>) {
        match self {
            DialogKind::ProbePath => (Verb::Open, None),
            DialogKind::AddDefinition => (Verb::Open, Some(DEFINITION_FILTER)),
            DialogKind::OpenA | DialogKind::OpenB | DialogKind::OpenBase => (Verb::Open, Some(DAT_FILTER)),
            DialogKind::SaveAs(_) => (Verb::Save, Some(DAT_FILTER)),
            DialogKind::ExportCsv => (Verb::Save, Some(("CSV", &["csv"]))),
            DialogKind::ExportLayout(_) => (Verb::Save, None),
        }
    }
}

impl App {
    /// Open a file dialog without blocking the window: it is answered on a helper thread, and the
    /// answer reaches `on_dialog` on a later frame. A dialog that blocks the UI thread stalls the
    /// event loop, and GNOME then offers to force-quit the app. One dialog at a time.
    pub(crate) fn ask(&mut self, ctx: &egui::Context, kind: DialogKind, file_name: Option<String>) {
        self.ask_titled(ctx, kind, file_name, None);
    }

    /// `ask`, with a title (or message) the dialog shows. A dialog for a settings file starts in the folder
    /// `start_dir` picks.
    pub(crate) fn ask_titled(&mut self, ctx: &egui::Context, kind: DialogKind, file_name: Option<String>, title: Option<String>) {
        if self.dialog_open {
            self.status = "A file dialog is already open".into();
            return;
        }
        let (verb, filter) = kind.spec();
        let mut dialog = rfd::AsyncFileDialog::new();
        if let Some((name, extensions)) = filter {
            dialog = dialog.add_filter(name, extensions);
        }
        if let Some(dir) = self.start_dir(&kind) {
            dialog = dialog.set_directory(dir);
        }
        if let Some(t) = title {
            dialog = dialog.set_title(t);
        }
        if let Some(name) = file_name {
            dialog = dialog.set_file_name(name);
        }
        // built here and awaited on the helper thread, as rfd advises: on macOS it shows a sheet on
        // the window from this (the main) thread; on Linux and Windows the dialog starts when awaited
        let answer: std::pin::Pin<Box<dyn std::future::Future<Output = Option<rfd::FileHandle>> + Send>> = match verb {
            Verb::Open => Box::pin(dialog.pick_file()),
            Verb::Save => Box::pin(dialog.save_file()),
        };
        self.dialog_open = true;
        let tx = self.dialog_tx.clone();
        let ctx = ctx.clone();
        std::thread::spawn(move || {
            // a panic is an answer too (None), so the dialogs are not left waiting on it
            let path = std::panic::catch_unwind(std::panic::AssertUnwindSafe(move || pollster::block_on(answer)))
                .ok()
                .flatten()
                .map(|h| h.path().to_path_buf());
            let _ = tx.send((kind, path));
            ctx.request_repaint(); // wake the window, which may be idle
        });
    }

    /// A file dialog's answer (None: cancelled): what each request does with it.
    pub(crate) fn on_dialog(&mut self, kind: DialogKind, path: Option<PathBuf>) {
        self.dialog_open = false;
        match kind {
            DialogKind::ProbePath => {
                if let Some(p) = path {
                    self.prefs.probe_path = Some(p.display().to_string());
                    self.prefs.save();
                    self.helper_seen.set(None);
                }
            }
            DialogKind::AddDefinition => {
                if let Some(p) = path { self.add_definition(&p, false); }
            }
            DialogKind::OpenA => {
                if let Some(p) = path { self.open(p); }
            }
            DialogKind::OpenB => {
                if let Some(p) = path { self.open_compare(p); }
            }
            DialogKind::OpenBase => {
                if let Some(p) = path { self.open_base(p); }
            }
            DialogKind::SaveAs(from) => {
                let Some(p) = path else {
                    // cancelled: what was to follow a save does not happen
                    if self.after_save.take().is_some() { self.status = "Not saved: your edits stay open.".into(); }
                    return;
                };
                if self.doc.as_ref().is_some_and(|d| d.path == from) {
                    self.save_to(p);
                } else {
                    self.after_save = None;
                    self.status = "Not saved: another file was opened while the Save As dialog was open".into();
                }
            }
            DialogKind::ExportCsv => {
                if let Some(p) = path { self.export_csv_to(p); }
            }
            DialogKind::ExportLayout(text) => {
                self.status = match path {
                    None => "Description for support not saved".into(),
                    Some(p) => match std::fs::write(&p, text) {
                        Ok(()) => format!("Description for support saved to {}", p.display()),
                        Err(e) => format!("The description for support was not saved: {}{}", io_words(&e, true), details(self.prefs.expert, format_args!("{}: {e}", p.display()))),
                    },
                };
            }
        }
    }

    /// The folder a file dialog starts in. Open: a camera card's settings folder when a card is mounted, else the
    /// folder of the file last opened. Save As: the opened file's folder, unless it is one of the editor's own (a
    /// camera read or a kept copy, which it never saves into); then as Open does. Other dialogs: the system's choice.
    pub(crate) fn start_dir(&self, kind: &DialogKind) -> Option<PathBuf> {
        let last = || self.prefs.recent.iter().map(PathBuf::from).filter_map(|p| p.parent().map(Path::to_path_buf))
            .find(|d| d.is_dir() && !Self::is_own_folder(d));
        let card = || mounted_cards(&self.card_folder()).into_iter().next();
        match kind {
            DialogKind::OpenA | DialogKind::OpenB | DialogKind::OpenBase => card().or_else(last),
            DialogKind::SaveAs(from) => from.parent().filter(|d| d.is_dir() && !Self::is_own_folder(d)).map(Path::to_path_buf).or_else(card).or_else(last),
            _ => None,
        }
    }
}

#[cfg(test)]
pub(crate) mod dialog_tests {
    use super::*;

    /// Each dialog lists what it listed when it blocked the window: camera settings files to open
    /// and for Save As, CSV for that export, every file for the helper program and the layout.
    #[test]
    fn each_dialog_asks_for_what_it_did() {
        for k in [DialogKind::OpenA, DialogKind::OpenB, DialogKind::OpenBase] {
            assert_eq!(k.spec(), (Verb::Open, Some(DAT_FILTER)));
        }
        assert_eq!(DialogKind::SaveAs(PathBuf::new()).spec(), (Verb::Save, Some(DAT_FILTER)));
        assert_eq!(DialogKind::ExportCsv.spec(), (Verb::Save, Some(("CSV", &["csv"][..]))));
        assert_eq!(DialogKind::ExportLayout(String::new()).spec(), (Verb::Save, None));
        assert_eq!(DialogKind::ProbePath.spec(), (Verb::Open, None));
        assert_eq!(DialogKind::AddDefinition.spec(), (Verb::Open, Some(DEFINITION_FILTER)));
    }

    /// Answers are handled without a window: the layout is written, a cancel says so, and a Save
    /// As for a file no longer open writes nothing.
    #[test]
    fn answers_reach_their_handler() {
        let dir = std::env::temp_dir().join(format!("camset_dialog_test_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let mut app = App::new(vec![], Prefs::default());
        app.dialog_open = true;
        let out = dir.join("camera_layout.json");
        app.on_dialog(DialogKind::ExportLayout("{}".into()), Some(out.clone()));
        assert!(!app.dialog_open);
        assert_eq!(std::fs::read_to_string(&out).unwrap(), "{}");
        assert!(app.status.starts_with("Description for support saved to"), "{}", app.status);
        app.on_dialog(DialogKind::ExportLayout("{}".into()), None);
        assert_eq!(app.status, "Description for support not saved");
        let target = dir.join("NEWE1.DAT");
        app.on_dialog(DialogKind::SaveAs(PathBuf::from("closed.DAT")), Some(target.clone()));
        assert!(!target.exists());
        assert!(app.status.starts_with("Not saved"), "{}", app.status);
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The application id is the Mac bundle id and the Linux menu entry's window class.
    #[test]
    fn app_id_matches_packaging() {
        let desktop = include_str!("../../packaging/linux/camset-editor.desktop");
        assert!(desktop.lines().any(|l| l == format!("StartupWMClass={APP_ID}")));
        let mac = include_str!("../../packaging/build_macos_app.sh");
        assert!(mac.contains(&format!("CAMSET_BUNDLE_ID:-{APP_ID}}}")));
    }

    /// Settings and the page name the version from Cargo.toml, with the commit when there is one; the page's state
    /// carries it.
    #[test]
    fn version_shown() {
        let v = version_words();
        assert!(v.starts_with(env!("CARGO_PKG_VERSION")), "{v}");
        let hash = env!("CAMSET_GIT_HASH");
        assert!(hash.chars().all(|c| c.is_ascii_alphanumeric()));
        assert_eq!(v.contains(" (build "), !hash.is_empty(), "{v}");
        // in the same form as ever ("0.2.0" or "0.2.0 (build 1a2b3c4)"), made of its two parts; the short one alone
        // in the window's title
        let whole = if hash.is_empty() { env!("CARGO_PKG_VERSION").to_string() } else { format!("{} (build {hash})", env!("CARGO_PKG_VERSION")) };
        assert_eq!(v, whole);
        assert_eq!(version_short(), env!("CARGO_PKG_VERSION"));
        assert!(!version_short().contains("(build") && !version_short().contains(' '));
        assert_eq!(build_hash(), (!hash.is_empty()).then_some(hash));
        assert_eq!(window_title(), format!("Camset Editor {}", env!("CARGO_PKG_VERSION")));
        let app = App::new(vec![], Prefs::default());
        let st = app.web_state(0);
        assert_eq!(st["version"], serde_json::Value::String(v));
        assert_eq!(st["version_short"], version_short());
        assert_eq!(st["build"], build_hash().map_or(serde_json::Value::Null, |h| h.into()));
    }

    /// On Windows the release app opens with no console window behind it, but the tests' build keeps its console
    /// (`cargo test --release`, as CI runs it), so it prints its results and names a failing test.
    #[test]
    fn windows_tests_keep_their_console() {
        let main = include_str!("../main.rs");
        assert!(main.lines().any(|l| l == "#![cfg_attr(all(not(debug_assertions), not(test)), windows_subsystem = \"windows\")]"));
        assert_eq!(main.matches("windows_subsystem").count(), 1);
    }

    /// macOS's own About panel (the application menu's "About Camset Editor") shows the app's name, its version and
    /// a copyright line from the Info.plist the Mac package writes: the version is Cargo.toml's, the line the licence's
    /// copyright holders and the not-affiliated words, so none of them can go stale.
    #[test]
    fn mac_about_panel_names_the_version() {
        // read with LF line ends, as git checks it out with CRLF on Windows (the release workflow's Windows build runs
        // these tests too)
        let mac = include_str!("../../packaging/build_macos_app.sh").replace("\r\n", "\n");
        let plist = include_str!("../../packaging/macos/Info.plist").replace("\r\n", "\n");
        assert!(mac.contains("VERSION=$(sed -n 's/^version = \"\\(.*\\)\"/\\1/p' Cargo.toml | head -1)"));
        assert!(mac.contains("COPYRIGHT=$(sed -n 's/^Copyright (c) //p' ../LICENSE | head -1)"));
        assert!(mac.contains("-e \"s/@VERSION@/$VERSION/g\"") && mac.contains("-e \"s|@COPYRIGHT@|$COPYRIGHT|g\" packaging/macos/Info.plist > \"$APP/Contents/Info.plist\""));
        // what the script's sed finds: the package's own version, the first line of Cargo.toml that names one
        let cargo = include_str!("../../Cargo.toml");
        let first = cargo.lines().find_map(|l| l.strip_prefix("version = \"").and_then(|r| r.strip_suffix('"')));
        assert_eq!(first, Some(env!("CARGO_PKG_VERSION")));
        // the line goes into a sed replacement and the plist's XML as it is: the script refuses one that is empty or holds
        // & | \ < >, and the project's own holds none of them
        assert!(mac.contains("case \"$COPYRIGHT\" in\n  \"\"|*[\\&\\|\\\\\\<\\>]*) echo \"LICENSE needs a"), "the script refuses a line it cannot write");
        let refused = mac.find("case \"$COPYRIGHT\" in").unwrap();
        assert!(refused < mac.find("cargo build --release").unwrap(), "before anything is built");
        let licence = include_str!("../../../LICENSE");
        let holders = licence.lines().find_map(|l| l.strip_prefix("Copyright (c) ")).expect("LICENSE names its copyright holders");
        assert!(!holders.trim().is_empty() && !holders.contains(['&', '|', '\\', '<', '>']), "{holders}");
        for (key, value) in [("CFBundleName", "Camset Editor"), ("CFBundleShortVersionString", "@VERSION@"), ("CFBundleVersion", "@VERSION@"),
            ("NSHumanReadableCopyright", &format!("Copyright (c) @COPYRIGHT@. {NOT_SONY}"))] {
            assert!(plist.contains(&format!("<key>{key}</key>\n\t<string>{value}</string>")), "{key}");
        }
    }

    /// About's facts come from one place each: the links from Cargo.toml (the same two pages mkdocs.yml names, and the
    /// issues page under the repository), the licence from Cargo.toml and the copyright line from LICENSE, as the macOS
    /// and Windows packages take it (the page's About draws them from the editor's state: `the_page_has_the_windows_words`).
    #[test]
    fn about_facts_have_one_source() {
        let mkdocs = include_str!("../../../mkdocs.yml").replace("\r\n", "\n");
        assert!(mkdocs.lines().any(|l| l == format!("site_url: {DOCS_URL}")), "the docs site's address");
        assert!(mkdocs.lines().any(|l| l == format!("repo_url: {PROJECT_URL}")), "the repository's address");
        assert!(!PROJECT_URL.ends_with('/'), "the issues page is the repository's address and /issues");
        assert_eq!(ISSUES_URL, format!("{PROJECT_URL}/issues"));
        assert!([PROJECT_URL, DOCS_URL, ISSUES_URL].iter().all(|u| u.starts_with("https://")));
        assert_eq!(ABOUT_LINKS.map(|(w, u, _)| (w, u)), [("Project page", PROJECT_URL), ("Documentation", DOCS_URL), ("Report a problem", ISSUES_URL)]);
        let holders = crate::windows_resources::copyright_holders(include_str!("../../../LICENSE")).expect("LICENSE names its copyright holders");
        assert_eq!(licence_words(), format!("MIT licence. Copyright (c) {holders}."));
    }

    /// The system About names: the name and version from the file each system keeps them in (macOS's
    /// SystemVersion.plist, Linux's os-release), the name alone where there is none or it says nothing usable, and the
    /// processor the program was built for.
    #[test]
    fn about_names_the_system() {
        let plist = "<dict>\n\t<key>ProductName</key>\n\t<string>macOS</string>\n\t<key>ProductVersion</key>\n\t<string>15.2</string>\n</dict>";
        assert_eq!(system_name("macos", plist), "macOS 15.2");
        assert_eq!(system_name("macos", ""), "macOS");
        assert_eq!(system_name("macos", "<key>ProductVersion</key><string>/Users/you</string>"), "macOS", "a version is digits and dots");
        let os_release = "NAME=\"Ubuntu\"\nVERSION_ID=\"26.04\"\nPRETTY_NAME=\"Ubuntu 26.04 LTS\"\nID=ubuntu\n";
        assert_eq!(system_name("linux", os_release), "Ubuntu 26.04 LTS");
        assert_eq!(system_name("linux", "PRETTY_NAME='Fedora Linux 44'"), "Fedora Linux 44");
        assert_eq!(system_name("linux", "ID=arch\n"), "Linux");
        assert_eq!(system_name("linux", &format!("PRETTY_NAME=\"{}\"", "x".repeat(80))), "Linux", "too long to be a name");
        assert_eq!(system_name("windows", "anything"), "Windows");
        assert_eq!(system_name("freebsd", ""), "freebsd");
        let words = system_words();
        assert!(words.ends_with(&format!(" ({})", std::env::consts::ARCH)), "{words}");
        let name = match std::env::consts::OS { "macos" => "macOS", "windows" => "Windows", _ => "" };
        assert!(words.starts_with(name), "{words}");
    }

    /// Settings > Changes reads the changelog built in: releases and their parts as headings, each point whole (its
    /// following lines joined), Markdown's marks taken out.
    #[test]
    fn changes_from_the_changelog() {
        let md = "# Changelog\n\nWhat changed, newest first.\n\n## Unreleased\n\n### The editor\n\n- One point,\n  on two lines with `code`.\n- A [link](https://example.invalid/x) and [another](y.md).\n\n### The docs\n\n- Last.\n";
        let b = changelog_blocks(md);
        assert_eq!(b, vec![
            (0, "What changed, newest first.".to_string()),
            (2, "Unreleased".to_string()),
            (3, "The editor".to_string()),
            (1, "One point, on two lines with code.".to_string()),
            (1, "A link and another.".to_string()),
            (3, "The docs".to_string()),
            (1, "Last.".to_string()),
        ]);
        // the real one: a release heading first, then its parts, every point in plain words
        let real = changelog_blocks(CHANGELOG);
        assert!(real.iter().any(|(k, t)| *k == 2 && t == "Unreleased") && real.iter().any(|(k, t)| *k == 3 && t == "The editor"));
        assert!(real.iter().filter(|(k, _)| *k == 1).all(|(_, t)| !t.contains('`') && !t.contains("](")));
    }
}
