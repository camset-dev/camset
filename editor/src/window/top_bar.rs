//! The top bar: the file's badge and its firmware, the File menu, and the buttons for the camera and the pages.

use crate::*;

impl App {
    /// File name, save date and firmware badge of the opened file. Returns the file's layout when
    /// its Describe for support… was clicked.
    fn file_badge(&mut self, ui: &mut egui::Ui) -> Option<String> {
        let Some(d) = &self.doc else {
            ui.label(RichText::new("no file").color(tone::weak(ui.visuals())));
            return None;
        };
        let src_tip = match &d.source {
            Source::Camera { link, read_at } => format!("Read over {link} at {}", self.stamp_words(read_at)),
            Source::Disk => "Opened from disk".to_string(),
            Source::Sample => "Built-in sample file".to_string(),
        };
        // the definition the file is read with, under where it came from
        let src_tip = match self.definition_words() { Some((_, how)) => format!("{src_tip}\n{how}"), None => src_tip };
        let filename = d.path.file_name().unwrap_or_default().to_string_lossy().to_string();
        let is_rtl = ui.layout().prefer_right_to_left();
        let show_edit_anyway = self.offers_edit_anyway(d);

        let chosen;
        let msg = if is_rtl {
            chosen = self.open_with_menu(ui);
            if show_edit_anyway
                && ui.small_button("Edit anyway…").on_hover_text("Change the settings this firmware keeps where the editor expects them; the others stay locked").clicked()
            {
                self.show_unchecked = true;
            }
            let m = self.firmware_badge(ui, &d.edited, &d.signature, d.unchecked_ok);
            ui.label(RichText::new(filename).strong()).on_hover_text(format!("{}\n{src_tip}", d.path.display()));
            m
        } else {
            ui.label(RichText::new(filename).strong()).on_hover_text(format!("{}\n{src_tip}", d.path.display()));
            let m = self.firmware_badge(ui, &d.edited, &d.signature, d.unchecked_ok);
            if show_edit_anyway
                && ui.small_button("Edit anyway…").on_hover_text("Change the settings this firmware keeps where the editor expects them; the others stay locked").clicked()
            {
                self.show_unchecked = true;
            }
            chosen = self.open_with_menu(ui);
            m
        };
        if let Some(choice) = chosen {
            self.override_definition(choice);
        }
        msg
    }

    /// Expert mode: "Open with…" beside the file name, every definition found, and the one the file's header picks.
    /// The choice, when one was made (`override_definition` carries it out).
    fn open_with_menu(&self, ui: &mut egui::Ui) -> Option<Option<Origin>> {
        let d = self.doc.as_ref().filter(|_| self.prefs.expert)?;
        let mut pick = None;
        let title = if d.override_def.is_some() { "⚙ Open with… (chosen by hand)" } else { "Open with…" };
        ui.menu_button(title, |ui| {
            ui.label(RichText::new("Read this file with another camera definition: the names shown become that definition's. Editing still needs a checked layout or Edit anyway, and a save or a write says which definition was used.").small().color(tone::weak(ui.visuals())));
            if ui.add_enabled(d.override_def.is_some(), egui::Button::new("The definition its header picks")).clicked() {
                pick = Some(None);
                ui.close_menu();
            }
            ui.separator();
            for s in &self.defs.list {
                let text = format!("{} firmware {} ({}{})", s.model, s.firmware(), s.origin.word(), if s.overridden { ", yours is used instead" } else { "" });
                let path = s.origin.path().map(shown_path).unwrap_or_default();
                if ui.selectable_label(s.origin == self.schema.origin, text).on_hover_text(path).clicked() {
                    pick = Some(Some(s.origin.clone()));
                    ui.close_menu();
                }
            }
        }).response.on_hover_text("Expert mode: read this file with another camera definition");
        pick
    }

    /// Model, save date, and whether the file's record layout matches a verified firmware.
    /// Returns the file's layout (`layout_json`) when its Describe for support… was clicked.
    pub(crate) fn firmware_badge(&self, ui: &mut egui::Ui, c: &CamSet, signature: &str, unchecked_ok: bool) -> Option<String> {
        let is_rtl = ui.layout().prefer_right_to_left();
        let unknown = self.schema.layout(signature).filter(|_| self.schema.camera.knows(c) && c.checksums_ok()).is_none();
        let mut export_clicked = false;

        let render_export = |ui: &mut egui::Ui| -> bool {
            unknown
                && ui.small_button("Describe for support…").on_hover_text("Save a description of how this file is laid out, without any settings values, so support for this firmware can be added").clicked()
        };

        if is_rtl && render_export(ui) {
            export_clicked = true;
        }
        // the video system the file was saved under, after the firmware, where the block says where it is
        let (video, video_tip) = video_badge(c);

        match self.schema.layout(signature).filter(|_| self.schema.camera.knows(c)) {
            _ if !c.checksums_ok() => {
                let which = if c.header_checksum_ok() { "trailer checksum".to_string() } else { Self::header_checksum_name(c) };
                ui.label(RichText::new("⚠ file looks damaged: view only").color(tone::bad(ui.visuals())).strong())
                    .on_hover_text(format!("{} · saved {}\nThe file's {which} does not match what its camera definition says: the file may be damaged, or the definition may not describe it. It is shown, but never edited.", c.model(), self.stamp_words(&c.timestamp())));
            }
            Some(l) => {
                let layout = if self.prefs.expert { format!(" (layout {signature})") } else { String::new() };
                // the layout's note is the mapping team's words: Expert mode only (`note_shown`)
                let info = format!("{} · saved {}{video_tip}\nThis file's firmware has been checked: the editor knows where every setting is{layout}.\n{}", c.model(), self.stamp_words(&c.timestamp()), l.note_shown(self.prefs.expert)).trim_end().to_string();
                ui.label(RichText::new(format!("✔ firmware {}{video}", l.firmware)).color(tone::ok(ui.visuals())))
                    .on_hover_text(info);
            }
            None if unchecked_ok => {
                let info = format!(
                    "{} · saved {}{video_tip}\nThe settings this firmware keeps where the editor expects them can be changed; the others stay locked. \
                     A value a newer firmware changed may be refused or changed by the camera; writing to the camera reads it first \
                     (↩ Put the camera back) and reads it back afterwards. Checked firmware: {}.",
                    c.model(), self.stamp_words(&c.timestamp()), self.schema.firmwares()
                );
                ui.label(RichText::new(format!("⚠ firmware {} not checked: editing on{video}", c.firmware())).color(tone::caution(ui.visuals())).strong())
                    .on_hover_text(info);
            }
            None if self.foreign_model(c).is_some() => {
                let model = c.model();
                ui.label(RichText::new(format!("⚠ {model} is not supported yet: view only")).color(tone::bad(ui.visuals())).strong())
                    .on_hover_text(format!("{}\nSupported so far: {}.", self.foreign_words(&model), self.defs.works_with().join(", ")));
            }
            None => {
                let info = format!(
                    "{} · saved {}{video_tip}\nThis file comes from a firmware the editor has not checked yet (layout {}); \
                     a firmware update can move or resize settings. \
                     Settings are shown, but editing and saving are off so the file cannot be damaged.",
                    c.model(), self.stamp_words(&c.timestamp()), signature
                );
                ui.label(RichText::new(format!("⚠ firmware {} not checked: view only{video}", c.firmware())).color(tone::bad(ui.visuals())).strong())
                    .on_hover_text(info);
            }
        };

        if !is_rtl && render_export(ui) {
            export_clicked = true;
        }

        if export_clicked {
            Some(Self::layout_json(c))
        } else {
            None
        }
    }

    pub(crate) fn top_bar(&mut self, ui: &mut egui::Ui) {
        ui.spacing_mut().interact_size.y = 26.0;
        ui.spacing_mut().button_padding = egui::vec2(8.0, 4.0);

        let has_doc = self.doc.is_some();
        let can_save = self.can_save_as();
        let n_changes = self.doc.as_ref().map(|d| d.changes().len()).unwrap_or(0);
        let has_edits = !self.undo.is_empty() || !self.redo.is_empty() || n_changes > 0;
        let busy = self.camera_job.is_some();

        ui.horizontal_wrapped(|ui| {
            // Mode switcher
            for (m, label) in [(Mode::Edit, "Edit"), (Mode::Compare, "Compare")] {
                let text = RichText::new(label).strong();
                if ui.add(egui::Button::new(text).selected(self.mode == m).min_size(egui::vec2(76.0, 26.0))).clicked() {
                    self.mode = m;
                }
            }
            ui.separator();

            match self.mode {
                Mode::Edit => {
                    // File group: the daily ones as buttons, the rest in the File menu
                    self.file_menu(ui, can_save, has_edits);
                    let ctx = ui.ctx().clone();
                    if ui.button("Open…").on_hover_text(format!("Open a settings file ({})", ctx.format_shortcut(&KEY_OPEN))).clicked() {
                        self.ask(ui.ctx(), DialogKind::OpenA, None);
                    }
                    if has_doc && ui.add_enabled(can_save, egui::Button::new("Save As…")).on_hover_text(format!("Save the edited file under a new name ({})", ctx.format_shortcut(&KEY_SAVE))).clicked() {
                        self.save_as(ui.ctx());
                    }

                    // Undo and Redo: always shown when a file is open, so the row does not jump
                    if has_doc {
                        ui.separator();
                        if ui.add_enabled(!self.undo.is_empty(), egui::Button::new("↺ Undo")).on_hover_text("Undo the last edit (Cmd/Ctrl+Z)").clicked() {
                            self.undo();
                        }
                        if ui.add_enabled(!self.redo.is_empty(), egui::Button::new("↻ Redo")).on_hover_text("Redo (Shift+Cmd/Ctrl+Z)").clicked() {
                            self.redo();
                        }
                    }

                    // Camera group (deduplicated)
                    ui.separator();
                    let (dot_color, state_text, state_desc) = match &self.link_state {
                        LinkState::Up { at } => {
                            (tone::ok(ui.visuals()), format!("last read {}", when_words(at)), format!("The camera answered at {}", self.stamp_words(at)))
                        }
                        LinkState::Down { why } => {
                            (tone::bad(ui.visuals()), "disconnected".to_string(), format!("Camera action failed: {why}"))
                        }
                        LinkState::Untried => {
                            (ui.visuals().text_color(), "not checked".to_string(), "No camera action yet this session".to_string())
                        }
                    };
                    let helper = self.have_helper();
                    let cam_btn_text = self.camera_button_text(true);
                    let which = self.prefs.current_camera().map(|i| &self.prefs.cameras[i])
                        .and_then(|k| camera_words(&k.name, Some(&self.defs.model_words(&k.model)))).map(|w| format!("{w}\n")).unwrap_or_default();
                    let cam_tooltip = if helper {
                        format!("{which}{cam_btn_text} · {state_text}\n{state_desc}\nClick to open Connect to the camera")
                    } else {
                        "Reading from and writing to the camera need the camera link program, which is not in the download. Click to see how to set it up; settings files from the card work without it.".to_string()
                    };
                    let dot_color = if helper { dot_color } else { ui.visuals().text_color() };
                    if ui.add(egui::Button::new(RichText::new(cam_btn_text).color(dot_color))).on_hover_text(cam_tooltip).clicked() {
                        self.show_connect = true;
                    }
                    if helper && ui.add_enabled(!busy, egui::Button::new("⬇ Read")).on_hover_text(self.read_tip("; Cmd/Ctrl+R")).clicked() {
                        self.start_camera_job(None);
                    }
                    let write_label = if n_changes > 0 { format!("⬆ Write ({n_changes})…") } else { "⬆ Write…".to_string() };
                    // off, with the reason on hover, whenever a write would be refused (the sample, a file view only, busy)
                    let blocked = self.send_blocked();
                    if helper && has_doc && ui.add_enabled(blocked.is_none(), egui::Button::new(write_label))
                        .on_hover_text("Write this file to the camera: the camera is read first, then the Write window lists what changes before anything is written. The camera restarts")
                        .on_disabled_hover_text(blocked.unwrap_or_default()).clicked() {
                        self.send_to_camera();
                    }
                    if busy {
                        ui.spinner();
                    }
                }
                Mode::Compare => {
                    let mut layout: Option<String> = None; // a badge's Describe for support… was clicked
                    self.file_menu(ui, can_save, has_edits);
                    ui.separator();
                    ui.label(RichText::new("A:").strong());
                    if ui.button("Open…").on_hover_text("File A: the one you can edit").clicked() {
                        self.ask(ui.ctx(), DialogKind::OpenA, None);
                    }
                    if let Some(d) = &self.doc {
                        ui.label(RichText::new(d.path.file_name().unwrap_or_default().to_string_lossy()).strong());
                        if let Some(l) = self.firmware_badge(ui, &d.edited, &d.signature, d.unchecked_ok) {
                            layout = Some(l);
                        }
                        if self.offers_edit_anyway(d)
                            && ui.small_button("Edit anyway…").on_hover_text("Change the settings this firmware keeps where the editor expects them; the others stay locked").clicked()
                        {
                            self.show_unchecked = true;
                        }
                    } else {
                        ui.label(RichText::new("none").color(tone::weak(ui.visuals())));
                    }

                    ui.separator();
                    ui.label(RichText::new("B:").strong().color(Src::B.tone(ui.visuals())));
                    if ui.button("Open…").on_hover_text("File B: compared against A").clicked() {
                        self.ask(ui.ctx(), DialogKind::OpenB, None);
                    }
                    if let Some((p, c)) = &self.compare {
                        ui.label(RichText::new(p.file_name().unwrap_or_default().to_string_lossy()).strong().color(Src::B.tone(ui.visuals())));
                        if let Some(l) = self.firmware_badge(ui, c, &c.layout_signature(), false) {
                            layout = Some(l);
                        }
                    } else {
                        ui.label(RichText::new("none").color(tone::weak(ui.visuals())));
                    }

                    if self.compare.is_some() {
                        ui.separator();
                        ui.label(RichText::new("Base:").strong().color(Src::Base.tone(ui.visuals())));
                        if ui.button("Open…").on_hover_text("Three-way compare: the file A and B both started from. Rows are then tagged as changed in A, changed in B, the same change, or a conflict, and B's changes can be merged into A.").clicked() {
                            self.ask(ui.ctx(), DialogKind::OpenBase, None);
                        }
                        if let Some((p, c)) = self.base.clone() {
                            ui.label(RichText::new(p.file_name().unwrap_or_default().to_string_lossy()).strong().color(Src::Base.tone(ui.visuals())));
                            if let Some(l) = self.firmware_badge(ui, &c, &c.layout_signature(), false) {
                                layout = Some(l);
                            }
                            if named(ui.small_button("✖"), "Close the base file").on_hover_text("Close the base file (back to a two-way compare)").clicked() {
                                self.close_base();
                            }
                        } else {
                            ui.label(RichText::new("none").color(tone::weak(ui.visuals())));
                        }
                    }
                    if let Some(l) = layout {
                        self.export_layout(ui.ctx(), l);
                    }
                }
            }

            // Right-aligned on Row 1: Settings button
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                if ui.button("⚙ Settings").on_hover_text(format!("Theme, text size, camera connection, backups, keyboard shortcuts and more ({})", ui.ctx().format_shortcut(&KEY_SETTINGS))).clicked() {
                    self.show_settings = !self.show_settings;
                }
            });
        });

        if self.mode == Mode::Edit && self.doc.is_none() {
            return;
        }

        ui.add_space(4.0);
        ui.horizontal(|ui| match self.mode {
            Mode::Edit => {
                self.back_to_compare_ui(ui);
                ui.label("Editing:");
                let others: Vec<usize> = (1..self.n_sections()).filter(|s| !self.schema.camera.is_dial(*s)).collect();
                let dial: Vec<usize> = std::iter::once(0).chain(self.dial_sets()).collect();
                for s in dial {
                    ui.selectable_value(&mut self.target, s, self.schema.camera.target_name(s));
                }
                if self.prefs.expert && !others.is_empty() {
                    let r = egui::ComboBox::from_id_salt("other_sets")
                        .selected_text(if others.contains(&self.target) { self.schema.camera.target_name(self.target) } else { "Other memories".into() })
                        .show_ui(ui, |ui| {
                            for s in others {
                                ui.selectable_value(&mut self.target, s, self.schema.camera.target_name(s));
                            }
                        });
                    named(r.response, "Other memories to edit");
                }
                ui.separator();
                let resp = named(ui.add(egui::TextEdit::singleline(&mut self.search).id(egui::Id::new(SEARCH_ID)).hint_text(RichText::new("🔍 Search settings, groups or values").color(tone::weak(ui.visuals()))).desired_width(220.0)), "Search settings, groups or values");
                // the pages that filter their own rows keep the search on them
                if resp.changed() && !self.search.trim().is_empty() && !matches!(self.view, View::Records | View::Unmapped | View::Memories) {
                    self.view = View::Search;
                }
                if !self.search.is_empty() && named(ui.small_button("✖"), "Clear the search").on_hover_text("Clear the search").clicked() {
                    self.search.clear();
                    if self.view == View::Search {
                        self.view = View::Main;
                    }
                }
                ui.checkbox(&mut self.only_changed, "Only edited");

                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if let Some(layout) = self.file_badge(ui) {
                        self.export_layout(ui.ctx(), layout);
                    }
                });
            }
            Mode::Compare => {
                let can_save = self.can_save_as();
                let unsaved = self.doc.as_ref().is_some_and(|d| d.unsaved() > 0);
                if self.compare.is_some() && self.doc.is_some()
                    && ui.add_enabled(!unsaved, egui::Button::new("Swap A/B")).on_hover_text("Swap A and B (save or revert edits first)").clicked()
                {
                    match self.swap_ab() {
                        Ok(()) => self.status = "A and B swapped".into(),
                        Err(why) => self.status = why,
                    }
                }
                if ui.add_enabled(can_save, egui::Button::new("Save A As…")).clicked() {
                    self.save_as(ui.ctx());
                }
                if ui.add_enabled(self.doc.is_some() && self.cols.len() >= 2, egui::Button::new("Export CSV…")).on_hover_text("The comparison as shown, as a spreadsheet (export only)").clicked() {
                    self.export_csv(ui.ctx());
                }
                ui.separator();
                named(ui.add(egui::TextEdit::singleline(&mut self.search).id(egui::Id::new(SEARCH_ID)).hint_text(RichText::new("🔍 Search settings or values").color(tone::weak(ui.visuals()))).desired_width(220.0)), "Search settings or values");
                let r = egui::ComboBox::from_id_salt("compare_tab")
                    .selected_text(self.compare_tab.clone().unwrap_or_else(|| "All tabs".into()))
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut self.compare_tab, None, "All tabs");
                        for t in self.schema.tabs.clone() {
                            ui.selectable_value(&mut self.compare_tab, Some(t.clone()), t);
                        }
                    });
                named(r.response, "Tab compared");
                if ui.checkbox(&mut self.matrix_only_diff, "Only rows that differ").changed() {
                    self.cmp_kept = None;
                    self.prefs.matrix_only_diff = self.matrix_only_diff;
                    self.prefs.save();
                }
                if self.prefs.expert {
                    if ui.checkbox(&mut self.show_raw, "Show raw values").changed() {
                        self.prefs.show_raw = self.show_raw;
                        self.prefs.save();
                    }
                    ui.checkbox(&mut self.compare_records, "Record map")
                        .on_hover_text("Every record in file order, mapped or not, so unmapped records can be compared next to their neighbours");
                }
            }
        });
        // which file each letter of the compare's column names is, said once
        if self.mode == Mode::Compare && self.letters_in_use() {
            ui.horizontal_wrapped(|ui| {
                for src in [Src::A, Src::B, Src::Base] {
                    if self.set_for(src).is_none() {
                        continue;
                    }
                    let what = if src == Src::A { " (the file you edit)" } else { "" };
                    ui.label(RichText::new(format!("{} = {}{what}", src.letter(), self.file_name_of(src))).color(src.tone(ui.visuals())));
                    ui.add_space(12.0);
                }
            });
            if let Some(note) = self.video_systems_note() {
                ui.add(egui::Label::new(RichText::new(note).small().color(tone::caution(ui.visuals()))).wrap());
            }
        }
        if self.mode == Mode::Edit && self.target != 0 {
            ui.label(RichText::new(format!(
                "{} is a memory: changes here apply when it is recalled, not to the live settings.",
                self.schema.camera.target_name(self.target)
            )).small().italics());
        }
        if let Some(model) = self.foreign_a() {
            ui.label(RichText::new(format!("⚠ {}", self.foreign_words(&model))).color(tone::bad(ui.visuals())));
        }
    }

    /// The File menu: opening (and the recent files), saving, exporting, the kept copies, the edit history, closing.
    fn file_menu(&mut self, ui: &mut egui::Ui, can_save: bool, has_edits: bool) {
        let ctx = ui.ctx().clone();
        let has_doc = self.doc.is_some();
        let n_changes = self.doc.as_ref().map(|d| d.changes().len()).unwrap_or(0);
        let mut open: Option<PathBuf> = None;
        ui.menu_button("File ⏷", |ui| {
            ui.set_min_width(220.0);
            if ui.add(egui::Button::new("Open…").shortcut_text(ctx.format_shortcut(&KEY_OPEN))).clicked() {
                self.ask(ui.ctx(), DialogKind::OpenA, None);
                ui.close_menu();
            }
            ui.add_enabled_ui(!self.prefs.recent.is_empty(), |ui| {
                ui.menu_button("Recent", |ui| {
                    for r in &self.prefs.recent {
                        let p = Path::new(r);
                        let name = p.file_name().unwrap_or_default().to_string_lossy().to_string();
                        // the folder too, so two cards' CAMSET01.DAT can be told apart
                        let folder = p.parent().and_then(|d| d.file_name()).map(|d| d.to_string_lossy().to_string()).unwrap_or_default();
                        let label = if folder.is_empty() { name } else { format!("{name}  ({folder})") };
                        if ui.button(label).on_hover_text(r).clicked() {
                            open = Some(PathBuf::from(r));
                            ui.close_menu();
                        }
                    }
                });
            });
            if ui.add_enabled(has_doc && can_save, egui::Button::new("Save As…").shortcut_text(ctx.format_shortcut(&KEY_SAVE))).clicked() {
                self.save_as(ui.ctx());
                ui.close_menu();
            }
            let csv_hover = if self.mode == Mode::Compare { "The comparison as shown, as a spreadsheet (export only)" } else { "The settings of this set as a spreadsheet (export only)" };
            if ui.add_enabled(has_doc, egui::Button::new("Export CSV…")).on_hover_text(csv_hover).clicked() {
                self.export_csv(ui.ctx());
                ui.close_menu();
            }
            ui.separator();
            if ui.button("📂 Backups…").on_hover_text("Every settings file as first opened, and the camera's settings at each read and around each write").clicked() {
                self.show_backups = true;
                self.backups = Self::list_backups();
                ui.close_menu();
            }
            let hist_label = if n_changes > 0 { format!("🕓 Edit history ({n_changes})…") } else { "🕓 Edit history…".to_string() };
            if ui.add_enabled(has_doc && has_edits, egui::Button::new(hist_label)).on_hover_text("Every edit of this session, with its before and after, each one revertable").clicked() {
                self.show_history = true;
                ui.close_menu();
            }
            ui.separator();
            if ui.add_enabled(has_doc, egui::Button::new("Close file").shortcut_text(ctx.format_shortcut(&KEY_CLOSE))).on_hover_text("Close the open files; with edits not saved yet, it asks first: Save As…, Discard edits or Cancel").clicked() {
                self.close_file();
                ui.close_menu();
            }
        });
        if let Some(p) = open { self.open(p); }
    }
}
