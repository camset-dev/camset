//! The preferences and the session the editor keeps between runs, in `prefs.json` in its own folder.

use crate::*;

fn default_zoom() -> f32 {
    1.0
}

fn default_density() -> u8 {
    1
}

fn default_true() -> bool {
    true
}

/// User preferences and session state, kept in the user's config folder.
#[derive(Clone, Serialize, Deserialize)]
pub(crate) struct Prefs {
    // (a "schema_dir" an older version wrote is ignored: the definitions are the shipped ones and the user's folder)
    #[serde(default)]
    pub(crate) reopen_last: bool,
    /// The window's theme: "system" (as the computer is set), "dark" or "light". Empty in a preferences file from
    /// before the choice existed: then `light` says which (`theme`).
    #[serde(default)]
    pub(crate) theme: String,
    /// Light or dark as last chosen, kept beside `theme` for an older editor reading the same file.
    #[serde(default)]
    pub(crate) light: bool,
    #[serde(default = "default_zoom")]
    pub(crate) zoom: f32,
    #[serde(default = "default_density")]
    pub(crate) density: u8,
    #[serde(default)]
    pub(crate) show_record_ids: bool,
    /// The line under a setting's name saying whether it was proved on the camera ("Proved on the camera (3/3)"):
    /// off unless turned on, and off from a prefs file that lacks it.
    #[serde(default)]
    pub(crate) show_proof: bool,
    #[serde(default)]
    pub(crate) show_raw: bool,
    #[serde(default)]
    pub(crate) allow_unobserved: bool,
    #[serde(default)]
    pub(crate) allow_raw_edits: bool,
    #[serde(default = "default_true")]
    pub(crate) backup_on_save: bool,
    #[serde(default = "default_true")]
    pub(crate) matrix_only_diff: bool,
    /// The Memories page shows only the rows where a memory differs from the live settings (on unless turned off).
    #[serde(default = "default_true")]
    pub(crate) memories_only_diff: bool,
    /// A group's rows as one flat list in the definition's order, instead of as on the camera (its rows in the
    /// camera's order, a submenu's rows under it), which is the default when the definition places its settings.
    #[serde(default)]
    pub(crate) flat_list: bool,
    #[serde(default)]
    pub(crate) all_memory_cols: bool,
    #[serde(default)]
    pub(crate) last_a: Option<String>,
    #[serde(default)]
    pub(crate) last_b: Option<String>,
    #[serde(default)]
    pub(crate) last_base: Option<String>,
    #[serde(default)]
    pub(crate) recent: Vec<String>,
    /// The window's size and the place of its top left corner, in the computer's own points (at 100% text).
    #[serde(default)]
    pub(crate) window: Option<[f32; 2]>,
    #[serde(default)]
    pub(crate) window_pos: Option<[f32; 2]>,
    #[serde(default)]
    pub(crate) compare_mode: bool,
    #[serde(default)]
    pub(crate) target: usize,
    #[serde(default)]
    pub(crate) view: Option<String>,
    /// Show unmapped records, derived copies, the other memory sets and raw values.
    #[serde(default)]
    pub(crate) expert: bool,
    /// Camera link: "usb" or "network".
    #[serde(default)]
    pub(crate) link: String,
    /// Camera link: the camset_probe executable and the camera's LAN address (empty = USB).
    #[serde(default)]
    pub(crate) probe_path: Option<String>,
    #[serde(default)]
    pub(crate) camera_ip: String,
    /// The chosen camera's MAC address: passed to the helper as CAMSET_MAC on every network job, so it uses that
    /// camera's own login even when its search misses the camera.
    #[serde(default)]
    pub(crate) camera_mac: String,
    /// Every camera this editor has met, with the person's own name for each.
    #[serde(default)]
    pub(crate) cameras: Vec<KnownCamera>,
    /// How long the last reads of the camera took on this computer, in seconds, per link ("usb", "network"): the
    /// helper's run of each download that brought its file back, oldest first, at most `READ_TIMES_KEPT`. Their
    /// median is what the editor names as a read's usual time (`App::usual_read_s`).
    #[serde(default)]
    pub(crate) read_times: std::collections::BTreeMap<String, Vec<f32>>,
    /// Web page: its port (None = the default), whether only this computer may open it, and whether it turns on when
    /// the editor starts (then for this computer only). It is always off until turned on. Its access code is made
    /// each time it is turned on and kept in memory only (a "web_code" an older version wrote is ignored).
    #[serde(default)]
    pub(crate) web_port: Option<u16>,
    #[serde(default)]
    pub(crate) web_local_only: bool,
    #[serde(default)]
    pub(crate) web_at_start: bool,
}

impl Default for Prefs {
    fn default() -> Self {
        Self {
            reopen_last: false,
            // a new user's window follows the computer's dark or light setting
            theme: "system".into(),
            light: false,
            zoom: 1.0,
            density: 1,
            show_record_ids: false,
            show_proof: false,
            show_raw: false,
            allow_unobserved: false,
            allow_raw_edits: false,
            backup_on_save: true,
            matrix_only_diff: true,
            memories_only_diff: true,
            flat_list: false,
            all_memory_cols: false,
            last_a: None,
            last_b: None,
            last_base: None,
            recent: Vec::new(),
            window: None,
            window_pos: None,
            compare_mode: false,
            target: 0,
            view: None,
            expert: false,
            link: String::new(),
            probe_path: None,
            camera_ip: String::new(),
            camera_mac: String::new(),
            cameras: Vec::new(),
            read_times: Default::default(),
            web_port: None,
            web_local_only: false,
            web_at_start: false,
        }
    }
}

impl Prefs {
    pub(crate) fn path() -> PathBuf {
        // tests keep their preferences, kept originals and camera files out of the user's folder
        if cfg!(test) {
            return std::env::temp_dir().join(format!("camset_editor_test_{}", std::process::id())).join("prefs.json");
        }
        camset_editor::schema::config_dir().join("prefs.json")
    }

    /// The preferences in `path`; the defaults when there are none. A damaged file is kept aside as
    /// `prefs.json.bad`, not written over by the next save: the known cameras and recent files are in it.
    pub(crate) fn read_from(path: &Path) -> Prefs {
        let text = std::fs::read_to_string(path).ok();
        let parsed = text.as_deref().map(serde_json::from_str::<Prefs>);
        if let Some(Err(_)) = &parsed {
            let _ = std::fs::rename(path, path.with_extension("json.bad"));
        }
        parsed.and_then(Result::ok).unwrap_or_default()
    }

    pub(crate) fn load() -> Prefs {
        let mut p = Self::read_from(&Self::path());
        // the editor's folder (preferences, kept copies, the camera's files) is this user's only, as write_private keeps it
        if let Some(dir) = Self::path().parent().filter(|d| d.is_dir()) {
            let _ = private_dir(dir);
        }
        p.normalize_zoom();
        if !cfg!(test) && p.camera_ip.trim().is_empty() {
            let mut roots = vec![PathBuf::from("."), PathBuf::from("..")];
            if let Ok(exe) = std::env::current_exe() {
                for a in exe.ancestors().take(6) {
                    roots.push(a.to_path_buf());
                }
            }
            for r in roots {
                let cfg = r.join("private").join("config.json");
                if let Ok(t) = std::fs::read_to_string(&cfg) {
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&t) {
                        if let Some(ip) = v.get("camera_ip").and_then(|s| s.as_str()).filter(|s| !s.trim().is_empty()) {
                            p.camera_ip = ip.trim().to_string();
                            if p.link.is_empty() {
                                p.link = "network".into();
                            }
                            break;
                        }
                    }
                }
            }
        }
        p
    }

    /// The window's theme: "system", "dark" or "light" (an older preferences file's `light` when it names none).
    pub(crate) fn theme(&self) -> &str {
        match self.theme.as_str() {
            t @ ("system" | "dark" | "light") => t,
            _ if self.light => "light",
            _ => "dark",
        }
    }

    /// Choose the window's theme ("system", "dark" or "light").
    pub(crate) fn set_theme(&mut self, theme: &str) {
        self.theme = theme.into();
        if theme != "system" { self.light = theme == "light"; }
    }

    pub(crate) fn clean_zoom(&self) -> f32 {
        if (0.75..=1.75).contains(&self.zoom) {
            self.zoom
        } else {
            1.0
        }
    }

    fn normalize_zoom(&mut self) {
        self.zoom = self.clean_zoom();
    }

    /// The known camera the next camera action goes to, when the editor knows it: over the network the chosen one
    /// (by its MAC address, else the one last met at the address), over USB the one last met over USB.
    pub(crate) fn current_camera(&self) -> Option<usize> {
        let latest = |pick: &dyn Fn(&KnownCamera) -> bool| self.cameras.iter().enumerate().filter(|(_, k)| pick(k))
            .max_by(|a, b| a.1.last_seen.cmp(&b.1.last_seen)).map(|(i, _)| i);
        match self.link.as_str() {
            "network" => {
                let (mac, ip) = (norm_mac(&self.camera_mac), self.camera_ip.trim());
                latest(&|k| !mac.is_empty() && norm_mac(&k.mac) == mac).or_else(|| latest(&|k| !ip.is_empty() && k.ip.trim() == ip))
            }
            "usb" => latest(&|k| k.link == "usb"),
            _ => None,
        }
    }

    /// The model of the camera at the chosen address, when the editor has met it (the chosen camera over the network,
    /// else the one last met at the address); empty otherwise. The helper takes it as CAMSET_MODEL, for a camera its
    /// search misses and it reaches by the address.
    pub(crate) fn camera_model(&self) -> String {
        let ip = self.camera_ip.trim();
        let at = || self.cameras.iter().enumerate().filter(|(_, k)| !ip.is_empty() && k.ip.trim() == ip)
            .max_by(|a, b| a.1.last_seen.cmp(&b.1.last_seen)).map(|(i, _)| i);
        let chosen = if self.link == "network" { self.current_camera() } else { None };
        chosen.or_else(at).map(|i| self.cameras[i].model.trim().to_string()).unwrap_or_default()
    }

    /// After an address was typed: the chosen camera is the one last met at it, when the editor knows its MAC.
    pub(crate) fn address_typed(&mut self) {
        let ip = self.camera_ip.trim();
        self.camera_mac = self.cameras.iter().filter(|k| !ip.is_empty() && k.ip.trim() == ip && !norm_mac(&k.mac).is_empty())
            .max_by(|a, b| a.last_seen.cmp(&b.last_seen)).map(|k| norm_mac(&k.mac)).unwrap_or_default();
    }

    /// A read over `link` ("usb", "network") brought its file back in `secs`: kept with the last `READ_TIMES_KEPT`.
    pub(crate) fn note_read(&mut self, link: &str, secs: f32) {
        if !secs.is_finite() || secs <= 0.0 { return; }
        let v = self.read_times.entry(link.to_string()).or_default();
        v.push(secs);
        let over = v.len().saturating_sub(READ_TIMES_KEPT);
        v.drain(..over);
    }

    pub(crate) fn step_zoom(&mut self, delta: f32) {
        let cur = self.clean_zoom();
        self.zoom = (((cur + delta) * 20.0).round() / 20.0).clamp(0.8, 1.6);
    }

    pub(crate) fn reset_zoom(&mut self) {
        self.zoom = 1.0;
    }

    /// Write the preferences whole and private (`write_private`: a temporary file renamed into place, readable by this
    /// user only): they hold the web page's access code, the known cameras' serial numbers, MAC addresses and
    /// addresses, and the recent files' paths. Only when they changed since the last save.
    pub(crate) fn save(&self) {
        static LAST: std::sync::Mutex<Option<String>> = std::sync::Mutex::new(None);
        let Ok(t) = serde_json::to_string_pretty(self) else { return };
        let mut last = LAST.lock().unwrap_or_else(|e| e.into_inner());
        if last.as_deref() == Some(t.as_str()) && Self::path().is_file() {
            return;
        }
        if write_private(&Self::path(), &t).is_ok() {
            *last = Some(t);
        }
    }

    pub(crate) fn remember(&mut self, path: &Path) {
        let s = path.display().to_string();
        self.recent.retain(|r| r != &s);
        self.recent.insert(0, s);
        self.recent.truncate(12);
    }
}

#[cfg(test)]
pub(crate) mod prefs_tests {
    use super::*;

    /// E-22, E-24: the Expert pages' rows and the page's revision are worked out once per state of the file, and
    /// change with it: an edit, Undo and a save each give a new state; the rows name what `Schema::find` names.
    #[test]
    fn rows_and_revision_follow_the_file() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let rows = app.record_rows();
        assert!(std::rc::Rc::ptr_eq(&rows, &app.record_rows()), "worked out once, not on every frame");
        let in_set = app.target != 0;
        for r in rows.iter() {
            assert_eq!(r.setting.map(|i| app.schema.settings[i].key.clone()), app.schema.find(in_set, r.id).map(|s| s.key.clone()), "0x{:04x}", r.id);
        }
        app.target = 1;
        let set_rows = app.record_rows();
        assert!(!std::rc::Rc::ptr_eq(&rows, &set_rows), "another set, other rows");
        for r in set_rows.iter() {
            assert_eq!(r.setting.map(|i| app.schema.settings[i].key.clone()), app.schema.find(true, r.id).map(|s| s.key.clone()), "0x{:04x}", r.id);
        }
        app.target = 0;
        let (rev, issues) = (app.web_rev(), app.issue_count());
        assert_eq!(issues, app.acceptance_issues().len());
        let s = app.schema.settings.iter().find(|s| s.area == "global" && s.scalar && s.text.is_none() && s.values.len() >= 2 && app.shape_ok_in(s, 0) && app.locked_why(s, 0).is_none()).unwrap().clone();
        let cur = app.col_value(Col::a(0), &s).unwrap();
        let other = s.values.iter().map(|(v, _)| *v).find(|v| *v != cur).unwrap();
        app.apply(vec![Action::Set(0, s.slot(), other)]);
        let after = app.record_rows();
        assert!(!std::rc::Rc::ptr_eq(&rows, &after) && after.iter().any(|r| r.id == s.id && r.edited), "an edit is seen");
        assert_ne!(app.web_rev(), rev);
        assert_eq!(app.issue_count(), app.acceptance_issues().len());
        app.undo();
        assert!(app.record_rows().iter().all(|r| !r.edited), "Undo is seen");
        assert_ne!(app.web_rev(), rev, "a new state, though the bytes are the same again");
    }

    /// E-31: a value put on its steps never goes past the range's top, even when the range is not a whole number of
    /// steps, nor below its bottom.
    #[test]
    fn steps_capped_at_the_range() {
        assert_eq!(snap_to_step(11, 0, 11, 4), 8, "the nearest step, 12, is past the top: the last step below it");
        assert_eq!(snap_to_step(10, 0, 10, 3), 9);
        assert_eq!(snap_to_step(5, 0, 10, 2), 6, "half way rounds up");
        assert_eq!(snap_to_step(-5, 0, 10, 2), 0);
        assert_eq!(snap_to_step(7, -6, 6, 4), 6);
        assert_eq!(snap_to_step(3, 1, 3, 5), 1, "a range shorter than a step holds its bottom only");
        assert_eq!(snap_to_step(3, 0, 10, 0), 3, "a step of 0 counts as 1");
    }

    /// U-39: the window's place is kept with its size, and put back only where it shows on the screen.
    #[test]
    fn window_place_kept_and_put_back_on_screen() {
        let p: Prefs = serde_json::from_str(r#"{"window": [1280.0, 860.0], "window_pos": [40.0, 60.0]}"#).unwrap();
        assert_eq!(p.window_pos, Some([40.0, 60.0]));
        let screen = [1920.0, 1080.0];
        assert!(place_on_screen([40.0, 60.0], [1280.0, 860.0], screen));
        assert!(place_on_screen([-200.0, 30.0], [1280.0, 860.0], screen), "partly off the left edge, still reachable");
        assert!(!place_on_screen([2500.0, 60.0], [1280.0, 860.0], screen), "on a screen to the right, maybe gone");
        assert!(!place_on_screen([40.0, -20.0], [1280.0, 860.0], screen), "title bar above the screen");
        assert!(!place_on_screen([40.0, 1050.0], [1280.0, 860.0], screen));
        assert!(!place_on_screen([f32::NAN, 0.0], [1280.0, 860.0], screen));
        assert_eq!(Prefs::default().window_pos, None);
    }

    /// U-18: a new user's window follows the computer's dark or light setting; a preferences file from before the
    /// choice keeps the theme it had; Dark and Light can still be chosen, and an older editor still reads `light`.
    #[test]
    fn theme_follows_the_system_for_a_new_user() {
        assert_eq!(Prefs::default().theme(), "system");
        let old_dark: Prefs = serde_json::from_str(r#"{"light": false}"#).unwrap();
        let old_light: Prefs = serde_json::from_str(r#"{"light": true}"#).unwrap();
        assert_eq!((old_dark.theme(), old_light.theme()), ("dark", "light"), "an existing user keeps their theme");
        let mut p = Prefs::default();
        p.set_theme("light");
        assert!(p.theme() == "light" && p.light);
        p.set_theme("system");
        assert!(p.theme() == "system" && p.light, "the last light or dark stays for an older editor");
        let back: Prefs = serde_json::from_str(&serde_json::to_string(&p).unwrap()).unwrap();
        assert_eq!(back.theme(), "system");
        let odd: Prefs = serde_json::from_str(r#"{"theme": "purple"}"#).unwrap();
        assert_eq!(odd.theme(), "dark");
    }

    #[test]
    fn test_prefs_zoom_normalization_and_serialization() {
        // 0.0 normalizes to 1.0
        let p_zero = Prefs { zoom: 0.0, ..Default::default() };
        assert_eq!(p_zero.clean_zoom(), 1.0);

        // Deserializing JSON with missing zoom uses default 1.0
        let p_missing: Prefs = serde_json::from_str("{}").expect("parse empty prefs");
        assert_eq!(p_missing.clean_zoom(), 1.0);
        assert_eq!(p_missing.zoom, 1.0);

        // Deserializing JSON with zoom = 0.0 normalizes to 1.0
        let mut p_json_zero: Prefs = serde_json::from_str(r#"{"zoom": 0.0}"#).expect("parse zero zoom");
        assert_eq!(p_json_zero.clean_zoom(), 1.0);
        p_json_zero.normalize_zoom();
        assert_eq!(p_json_zero.zoom, 1.0);

        // Deserializing JSON with out-of-range zoom normalizes to 1.0
        let mut p_out_of_range: Prefs = serde_json::from_str(r#"{"zoom": 5.0}"#).expect("parse high zoom");
        assert_eq!(p_out_of_range.clean_zoom(), 1.0);
        p_out_of_range.normalize_zoom();
        assert_eq!(p_out_of_range.zoom, 1.0);

        // Valid values like 1.15 are preserved
        let mut p_valid = Prefs { zoom: 1.15, ..Default::default() };
        assert_eq!(p_valid.clean_zoom(), 1.15);
        p_valid.normalize_zoom();
        assert_eq!(p_valid.zoom, 1.15);

        // Serialization and deserialization roundtrip preserves 1.15
        let serialized = serde_json::to_string(&p_valid).expect("serialize");
        let mut loaded: Prefs = serde_json::from_str(&serialized).expect("deserialize");
        assert_eq!(loaded.clean_zoom(), 1.15);
        loaded.normalize_zoom();
        assert_eq!(loaded.zoom, 1.15);

        // Stepping zoom
        let mut p_step = Prefs { zoom: 1.0, ..Default::default() };
        p_step.step_zoom(0.1);
        assert_eq!(p_step.zoom, 1.1);
        p_step.step_zoom(-0.1);
        assert_eq!(p_step.zoom, 1.0);
        p_step.zoom = 1.15;
        p_step.step_zoom(0.1);
        assert_eq!(p_step.zoom, 1.25);
    }

    #[test]
    fn test_new_prefs_defaults_and_roundtrip() {
        // Defaults on Prefs::default()
        let p_default = Prefs::default();
        assert_eq!(p_default.density, 1);
        assert!(!p_default.show_record_ids);
        assert!(!p_default.show_proof);
        assert!(!p_default.show_raw);
        assert!(!p_default.allow_unobserved);
        assert!(!p_default.allow_raw_edits);
        assert!(p_default.backup_on_save);
        assert!(p_default.matrix_only_diff);
        assert!(!p_default.all_memory_cols);

        // Deserializing empty JSON uses all defaults
        let p_empty: Prefs = serde_json::from_str("{}").expect("parse empty json");
        assert_eq!(p_empty.density, 1);
        assert!(!p_empty.show_record_ids);
        assert!(!p_empty.show_proof, "a prefs file without the switch comes up with the proof line off");
        assert!(!p_empty.show_raw);
        assert!(!p_empty.allow_unobserved);
        assert!(!p_empty.allow_raw_edits);
        assert!(p_empty.backup_on_save);
        assert!(p_empty.matrix_only_diff);
        assert!(!p_empty.flat_list, "a prefs file without the switch lays the rows out as on the camera");
        assert!(!p_empty.all_memory_cols);

        // Roundtrip with custom values
        let p_custom = Prefs {
            density: 2,
            show_record_ids: true,
            show_proof: true,
            show_raw: true,
            allow_unobserved: true,
            allow_raw_edits: true,
            backup_on_save: false,
            matrix_only_diff: false,
            all_memory_cols: true,
            ..Default::default()
        };
        let serialized = serde_json::to_string(&p_custom).expect("serialize");
        let loaded: Prefs = serde_json::from_str(&serialized).expect("deserialize");
        assert_eq!(loaded.density, 2);
        assert!(loaded.show_record_ids);
        assert!(loaded.show_proof);
        assert!(loaded.show_raw);
        assert!(loaded.allow_unobserved);
        assert!(loaded.allow_raw_edits);
        assert!(!loaded.backup_on_save);
        assert!(!loaded.matrix_only_diff);
        assert!(loaded.all_memory_cols);
    }

    #[test]
    fn test_app_init_from_prefs() {
        let prefs = Prefs {
            show_raw: true,
            expert: true,
            allow_unobserved: true,
            allow_raw_edits: true,
            matrix_only_diff: false,
            all_memory_cols: true,
            ..Default::default()
        };
        let mut app = App::new(vec![], prefs);
        assert_eq!(app.cols.len(), 1, "no definition yet: the live settings only");
        app.open_sample();
        assert!(app.show_raw);
        assert!(app.allow_unobserved);
        assert!(app.allow_raw_edits);
        assert!(!app.matrix_only_diff);
        assert_eq!(app.cols.len(), 7, "the definition's default columns and the Movie memories (0..=6)");

        // Non-expert disables raw edits and unobserved values
        let prefs_non_expert = Prefs {
            expert: false,
            allow_unobserved: true,
            allow_raw_edits: true,
            all_memory_cols: false,
            ..Default::default()
        };
        let mut app2 = App::new(vec![], prefs_non_expert);
        app2.open_sample();
        assert!(!app2.allow_unobserved);
        assert!(!app2.allow_raw_edits);
        assert_eq!(app2.cols.len(), 4, "the definition's default columns (0..=3)");
    }

    #[test]
    fn test_setting_title_show_record_ids() {
        let mut app = App::new(vec![], Prefs::default());
        if let Some(s) = app.schema.settings.first() {
            assert_eq!(app.setting_title(s), s.name);
            app.prefs.show_record_ids = true;
            assert_eq!(app.setting_title(s), s.name, "the switch draws nothing with Expert mode off");
            app.prefs.expert = true;
            assert!(app.setting_title(s).contains(&format!("0x{:04x}", s.id)));
        }
    }

    /// The mapping team's switches, turned on earlier, draw nothing while Expert mode is off, and come back with it.
    #[test]
    fn raw_numbers_only_in_expert_mode() {
        let app = App::new(vec![], Prefs { show_raw: true, expert: false, ..Default::default() });
        assert!(!app.show_raw, "kept off from the start");
        let mut app = App::new(vec![], Prefs { show_raw: true, expert: true, ..Default::default() });
        assert!(app.show_raw);
        app.prefs.expert = false;
        app.expert_off();
        assert!(!app.show_raw && app.prefs.show_raw, "off while Expert mode is, still asked for");
    }

    /// `shown_as`: a number shown divided, with its decimals and unit, everywhere the stored number is shown; typed in
    /// those terms and stored multiplied back; the range and its step in shown terms. Without it, as before.
    #[test]
    fn numbers_shown_as_the_definition_says() {
        let mut s: Setting = serde_json::from_value(serde_json::json!({
            "key": "global:0x0001", "area": "global", "id": 1, "name": "Level", "tab": "Shooting", "group": "G",
            "order": 1, "in_sets": false, "scalar": true, "values": [], "range": [0, 10000], "step": 100, "unit": "%",
            "shown_as": { "divide": 100, "decimals": 0 },
        })).unwrap();
        assert_eq!(App::describe(&s, Some(7500)), "75 %");
        assert_eq!((s.shown_number(7500), s.shown_value(7500)), ("75".to_string(), "75 %".to_string()));
        assert_eq!(range_words(&s, 0, 10000, 100), "0 – 100 %, in steps of 1");
        assert_eq!((App::describe(&s, Some(9250)), range_words(&s, 9000, 10000, 250)), ("92.5 %".to_string(), "90 – 100 %, in steps of 2.5".to_string()), "never rounded away");
        assert_eq!([s.stored_number("75"), s.stored_number("75 %"), s.stored_number(" 12.5 "), s.stored_number("x")], [Some(7500), Some(7500), Some(1250), None]);
        s.shown_as = Some(camset_editor::schema::ShownAs { divide: 10, decimals: 1 });
        s.unit.clear();
        assert_eq!((App::describe(&s, Some(3)).trim(), s.shown_value(3)), ("0.3", "0.3".to_string()));
        assert_eq!((s.stored_number("0.3"), s.stored_number("0,3"), s.stored_number("-1.5")), (Some(3), Some(3), Some(-15)));
        assert_eq!(range_words(&s, -50, 50, 1), "-5.0 – 5.0 , in steps of 0.1");
        // no shown_as: the number as stored, the step only when more than one
        s.shown_as = None;
        s.unit = "ms".into();
        assert_eq!((App::describe(&s, Some(3)), s.stored_number("3 ms")), ("3 ms".to_string(), Some(3)));
        assert_eq!(range_words(&s, 0, 10, 1), "0 – 10 ms");
        // the list's value, with the number the camera stores beside it while Expert mode shows it
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample();
        let doc = app.doc.as_ref().unwrap();
        let mut real = app.schema.settings.iter().find(|x| x.range.is_some() && x.text.is_none() && x.area == "global" && doc.value(0, x.slot()).is_some_and(|v| x.label_for(v).is_none())).unwrap().clone();
        let v = doc.value(0, real.slot()).unwrap();
        real.shown_as = Some(camset_editor::schema::ShownAs { divide: 10, decimals: 1 });
        let shown = app.row_value(&real);
        assert_eq!(shown, App::describe(&real, Some(v)));
        app.show_raw = true;
        assert_eq!(app.row_value(&real), format!("{shown}  [{v}]"));
    }

    #[test]
    fn test_settings_tab_definitions_and_app_init() {
        assert_eq!(SettingsTab::default(), SettingsTab::Appearance);
        assert_eq!(SettingsTab::ALL.len(), 6);
        assert_eq!(SettingsTab::ALL.last(), Some(&SettingsTab::About), "About is the last tab");

        assert_eq!(SettingsTab::Appearance.label(), "🎨 Appearance");
        assert_eq!(SettingsTab::Camera.label(), "📷 Camera link");
        assert_eq!(SettingsTab::Editing.label(), "⚙ Editing & Compare");
        assert_eq!(SettingsTab::Files.label(), "📂 Backups & start-up");
        assert_eq!(SettingsTab::Definitions.label(), "📐 Camera support & web page");
        assert_eq!(SettingsTab::About.label(), "ℹ About");
        // each tab's symbol is one egui's built-in fonts draw (About's U+2139 is NotoEmoji's), not a look-alike letter
        assert_eq!(SettingsTab::About.label().chars().next(), Some('\u{2139}'));
        let ctx = egui::Context::default();
        let _ = ctx.run(egui::RawInput::default(), |_| {});
        for tab in SettingsTab::ALL {
            assert!(ctx.fonts(|f| f.has_glyphs(&egui::FontId::proportional(14.0), tab.label())), "{tab:?}: {}", tab.label());
        }

        for tab in SettingsTab::ALL {
            assert!(!tab.subtitle().is_empty());
        }
        assert!(SettingsTab::About.subtitle().contains("version") && SettingsTab::About.subtitle().contains("Copy details"));

        let app = App::new(vec![], Prefs::default());
        assert_eq!(app.settings_tab, SettingsTab::Appearance);
    }
}
