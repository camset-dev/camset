//! The detail panel of a row: a setting's options as the camera lays them out, its numbers and texts, the choices
//! beside an option, a family's table, and what is known about the setting.

use crate::*;

/// A number put on its setting's steps counted from `lo`: the nearest step, never past `hi` (the last step at or
/// below it, when `hi - lo` is not a whole number of steps) nor below `lo`.
pub(crate) fn snap_to_step(v: i64, lo: i64, hi: i64, step: i64) -> i64 {
    let step = step.max(1);
    let top = (hi - (hi - lo).rem_euclid(step)).max(lo);
    (lo + ((v - lo) as f64 / step as f64).round() as i64 * step).clamp(lo, top)
}

/// The mark beside an edit you have not saved yet (with the edit colour, `tone::edit`).
pub(crate) const EDIT_MARK: &str = "✏";

/// The hover of an option the camera refuses (`Setting::refused`), wherever a value is chosen (`option_choice_ui`), and
/// the page's mark for it (web/mod.rs sends it with the row).
pub(crate) const REFUSED_HOVER: &str = "The camera refuses files holding this value: choosing it makes the camera reject the whole file.";

/// The hover of an option no proof on the camera established (`Setting::established`), wherever a value is chosen
/// (`option_choice_ui`), and the page's (web/mod.rs, `web_option_help`), word for word.
pub(crate) const UNPROVED_HOVER: &str = "Not checked on the camera yet: the camera may refuse a file holding this value.";

/// Expert mode's line for the values the gate holds back (`Setting::hidden_unproved`), in the detail panel and in
/// Compare's picker, pointing at the preference that lists them (`allow_unobserved`, shown in Expert mode only); the
/// page says the same.
pub(crate) fn hidden_words(n: usize) -> String {
    format!("{n} value(s) not checked on the camera yet are hidden (\"Offer values not checked on the camera yet\" in Settings > Editing & Compare lists them)")
}

/// A number box for `s`'s stored number `v` within `lo..=hi`, in steps of `step`: shown as the definition says
/// (`shown_as`, then `unit`: 7500 as "75 %"), typed in those terms and stored multiplied back (`Setting::stored_number`).
pub(crate) fn number_box<'a>(s: &'a Setting, v: &'a mut i64, lo: i64, hi: i64, step: i64) -> egui::DragValue<'a> {
    let d = egui::DragValue::new(v).range(lo..=hi).speed(0.2 * step as f64)
        .suffix(if s.unit.is_empty() { String::new() } else { format!(" {}", s.unit) });
    if s.shown_as.is_none() {
        return d;
    }
    d.custom_formatter(move |n, _| s.shown_number(n.round() as i64)).custom_parser(move |t| s.stored_number(t).map(|x| x as f64))
}

/// A number's range in words, in the terms it is shown in (`shown_as`): "0 – 100 %, in steps of 5"; the step when it
/// is more than one stored unit, or shown other than as stored ("in steps of 0.1").
pub(crate) fn range_words(s: &Setting, lo: i64, hi: i64, step: i64) -> String {
    let (a, b) = (s.shown_number(lo), s.shown_number(hi));
    if step > 1 || s.shown_as.is_some() { format!("{a} – {b} {}, in steps of {}", s.unit, s.shown_number(step)) } else { format!("{a} – {b} {}", s.unit) }
}

/// The hover of a proved setting's proof line, the window's and the page's: what a proof is. How, when and in which run
/// each was made is the mapping's evidence, kept by whoever mapped the camera, never in the definition.
pub(crate) const PROVED_HOVER: &str = "Checked on the camera: each option chosen in the camera's own menu, the settings file downloaded and compared";

/// The hover of the proof line of a setting whose list was proved partly on another setting (`Setting::list_shared`),
/// the window's and the page's: what is true of the whole list, since the definition never says which values were
/// chosen where (docs/decisions/0025).
pub(crate) const SHARED_HOVER: &str = "Proved on the camera, partly on another setting that offers the same list (another key, slot or copy of the same kind): some of these values were chosen there, not on this setting, and are named here from that proof.";

/// A proved setting's proof-line hover (`PROVED_HOVER`, or `SHARED_HOVER` for a list proved partly elsewhere).
pub(crate) fn proved_hover(s: &Setting) -> &'static str {
    if s.list_shared() { SHARED_HOVER } else { PROVED_HOVER }
}

/// The proof line of a setting the definition marks `disputed` (Expert mode), in the window and the page.
pub(crate) const DISPUTED: &str = "Disputed: left out of the proofs until a mapper decides";

impl App {
    /// The video system file A was saved under, by the name its container block gives it (`CamSet::video_system`):
    /// what decides which of a setting's `video_system_values` are offered. None when no file is open, the block does
    /// not say where the video system is, or names none for the value the file holds: every value is offered then.
    pub(crate) fn file_system(&self) -> Option<String> {
        self.doc.as_ref()?.edited.video_system()?.1
    }

    /// The video system that decides what `s` offers in set `section` of file A (`file_system`): in the live settings
    /// only. The camera's own files hold either system's values in their memory sets, so there nothing is held back,
    /// flagged or warned about on that ground.
    pub(crate) fn system_in(&self, section: usize) -> Option<String> {
        if section == 0 { self.file_system() } else { None }
    }

    /// Why `v` is not offered for `s` in set `section` of file A because of its video system, in plain words: the value
    /// is one the menus offer under another one than the file was saved under (`Setting::other_system`), in the live
    /// settings (`system_in`). None otherwise.
    pub(crate) fn other_system_words(&self, s: &Setting, v: i64, section: usize) -> Option<String> {
        let sys = self.system_in(section);
        let other = s.other_system(v, sys.as_deref())?;
        Some(format!("{} is offered only with the camera set to {other}, and this file was saved with it set to {}.", Self::describe(s, Some(v)), sys.unwrap_or_default()))
    }

    /// The values the editor offers for `s` in set `section` of file A (`Setting::offered`, with Expert mode's "Offer
    /// values…"), less those of another video system than the file's in the live settings (`system_in`).
    pub(crate) fn offered_values(&self, s: &Setting, section: usize) -> Vec<(i64, String)> {
        let sys = self.system_in(section);
        s.offered(self.allow_unobserved).into_iter().filter(|(v, _)| s.other_system(*v, sys.as_deref()).is_none()).collect()
    }

    /// The hover text of a setting's "Applies in": where the shooting modes come from (`text.modes_source`).
    pub(crate) fn modes_hover(&self) -> String {
        match self.schema.camera.text.modes_source.as_deref().filter(|s| !s.is_empty() && self.prefs.expert) {
            Some(src) => format!("From {src}: the shooting modes in which this menu item appears"),
            None => "The shooting modes in which this item appears in the camera's menu".into(),
        }
    }

    /// The hover of "Kept in the memories too", the window's and the page's: what registering a memory does.
    pub(crate) fn memories_hover(&self) -> String {
        let menu = self.schema.camera.text.memory_register_menu.as_deref().filter(|t| !t.is_empty()).map(|m| format!(" ({m})")).unwrap_or_default();
        format!("Registering a memory{menu} copies this setting into it. The Memories page shows them side by side.")
    }

    /// The values of a setting the camera's menus never offer (`not_offered`), one line per reason in the order first
    /// met, each with its hover: (the line, the menu whose list leaves them out). A
    /// value never offered reads "Not on the camera's list: A, B. <why>"; a held one, a factory value the camera writes
    /// itself and the editor keeps offering, "A: <why>". The window's detail panel, Compare's in-place choice and the page say them.
    pub(crate) fn not_offered_lines(&self, s: &Setting) -> Vec<(String, String)> {
        let mut groups: Vec<(bool, &str, &str, Vec<&str>)> = Vec::new();
        for n in &s.not_offered {
            match groups.iter_mut().find(|g| g.0 == n.held && g.1 == n.why && g.2 == n.menu) {
                Some(g) => g.3.push(&n.label),
                None => groups.push((n.held, &n.why, &n.menu, vec![&n.label])),
            }
        }
        groups.into_iter().map(|(held, why, menu, labels)| {
            let text = if held { format!("{}: {why}", labels.join(", ")) } else { format!("Not on the camera's list: {}. {why}", labels.join(", ")) };
            let hover = if menu.is_empty() { String::new() } else { format!("In {menu}") };
            (text.trim().to_string(), hover)
        }).collect()
    }

    /// The not-offered lines (`not_offered_lines`) under a setting, in the note colour.
    pub(crate) fn not_offered_ui(&self, ui: &mut egui::Ui, s: &Setting) {
        for (text, hover) in self.not_offered_lines(s) {
            let r = ui.add(egui::Label::new(RichText::new(text).small().color(tone::note(ui.visuals()))).wrap());
            if !hover.is_empty() {
                r.on_hover_text(hover);
            }
        }
    }

    /// The hover text of a setting's help, true to whose words it shows: the camera's own help when a help file found
    /// on this computer supplied it (`Schema::apply_help`; `src` names the file in Expert mode), else the project's
    /// own description from the definition.
    pub(crate) fn help_hover(&self, from_file: bool, src: &str) -> String {
        let definition = self.schema.origin.path().and_then(|p| p.file_name()).map(|n| format!(" {}", n.to_string_lossy())).unwrap_or_default();
        match (from_file, self.prefs.expert) {
            (true, true) => format!("From the camera's own help ({src})"),
            (true, false) => "From the camera's own help".into(),
            (false, true) => format!("Camset's own description, from the definition{definition} (not the camera's own help)"),
            (false, false) => "Camset's own description (not the camera's own help)".into(),
        }
    }

    /// Label of a record's value using any setting the schema has for that record.
    pub(crate) fn describe_record(schema: &Schema, id: u16, v: Option<i64>) -> String {
        match schema.settings.iter().find(|s| s.id == id && s.index.is_none()) {
            Some(s) => Self::describe(s, v),
            None => v.map(|v| v.to_string()).unwrap_or_else(|| "—".into()),
        }
    }

    /// A value in words: its label; for a setting with a range, the number and its unit; for a setting with named
    /// values, a number none of them names, marked "(no name yet)" (`unnamed_why` says why); for a setting with
    /// neither (a plain number the definition has no names for), the number.
    pub(crate) fn describe(s: &Setting, v: Option<i64>) -> String {
        match v {
            None => "—".into(),
            Some(v) if s.range.is_some() && s.label_for(v).is_none() => s.shown_value(v),
            Some(v) => match s.label_for(v) {
                Some(l) => l.to_string(),
                None if s.values.is_empty() && s.unit.is_empty() => v.to_string(),
                None if s.values.is_empty() => s.shown_value(v),
                None => format!("{v} (no name yet)"),
            },
        }
    }

    /// Why a value shows as "{v} (no name yet)" (`describe`), in plain words, for its hover and the detail panel: the
    /// setting has named values and this one is not among them. None for any other value. The record number in
    /// Expert mode only.
    pub(crate) fn unnamed_why(&self, s: &Setting, v: Option<i64>) -> Option<String> {
        let v = v?;
        if s.text.is_some() || s.range.is_some() || s.values.is_empty() || s.label_for(v).is_some() {
            return None;
        }
        if !self.prefs.expert {
            return Some(format!("The camera holds {v} here, a value Camset has no name for yet."));
        }
        let mut why = format!("The camera stores {v} here. This camera's definition has no name for that value: no choice on the camera wrote it when the setting was mapped (the camera's list may not offer it), so the editor shows the number.");
        why += &format!(" Record 0x{:04x}.", s.id);
        Some(why)
    }

    /// The detail panel's line for a value with no name yet (`unnamed_why`), in the note colour; nothing otherwise.
    pub(crate) fn unnamed_line(&self, ui: &mut egui::Ui, s: &Setting, v: Option<i64>) {
        if let Some(why) = self.unnamed_why(s, v) {
            ui.add(egui::Label::new(RichText::new(why).small().color(tone::note(ui.visuals()))).wrap());
            ui.add_space(4.0);
        }
    }

    /// A one-line editor for a setting (dropdown, number box or plain value).
    pub(crate) fn compact_editor(&self, ui: &mut egui::Ui, s: &Setting, editable: bool, actions: &mut Vec<Action>) {
        self.compact_editor_in(ui, self.target, s, editable, actions);
    }

    /// A one-line editor for a setting in the set `target` (`compact_editor`), as the My Menu page edits the live
    /// settings whatever set is being edited.
    pub(crate) fn compact_editor_in(&self, ui: &mut egui::Ui, target: usize, s: &Setting, editable: bool, actions: &mut Vec<Action>) {
        let Some(doc) = &self.doc else { ui.label(""); return };
        let cur = doc.value(target, s.slot());
        // a setting no menu writes is view only outside Expert mode (`locked_why`): why, on hover; and one the camera
        // keeps in more than one record says what changing it changes (`copy_note`), on hover too
        let locked = self.locked_why(s, target);
        let note = self.copy_note(s, target);
        let can_edit = editable && s.scalar && cur.is_some() && self.shape_ok_in(s, target) && locked.is_none();
        let mut chosen = cur;
        let r = ui.add_enabled_ui(can_edit, |ui| {
            if let (Some((lo, hi)), Some(mut v)) = (s.range, cur) {
                let step = s.step.unwrap_or(1).max(1);
                named(ui.add(number_box(s, &mut v, lo, hi, step)), &s.name);
                chosen = Some(snap_to_step(v, lo, hi, step));
            } else if s.values.len() >= 2 {
                let r = egui::ComboBox::from_id_salt(("main", s.key.as_str(), target)).width(220.0)
                    .selected_text(Self::describe(s, cur))
                    .show_ui(ui, |ui| {
                        for (v, label) in self.offered_values(s, target) {
                            ui.selectable_value(&mut chosen, Some(v), label);
                        }
                    });
                let r = named(r.response, &s.name);
                if let Some(why) = self.unnamed_why(s, cur) { r.on_hover_text(why); }
            } else {
                let r = ui.label(Self::describe(s, cur));
                if let Some(why) = self.unnamed_why(s, cur) { r.on_hover_text(why); }
            }
        });
        let resp = match &locked {
            Some((why, _)) => r.response.on_disabled_hover_text(why),
            None => r.response,
        };
        if let Some((note, _)) = &note {
            resp.on_hover_text(note);
        }
        if chosen != cur {
            if let Some(v) = chosen {
                actions.push(Action::Set(target, s.slot(), v));
            }
        }
    }

    /// Picture Profile parameters as a table: one row per parameter, one column per profile.
    /// The family (`camera.families`) a table's settings belong to.
    pub(crate) fn family_of(&self, pp: &[Setting]) -> Option<&camset_editor::schema::Family> {
        let group = &pp.first()?.group;
        self.schema.camera.families.iter().find(|f| !f.prefix.is_empty() && group.starts_with(&f.prefix))
    }

    /// A family table's column title from a group's name, as its family says (`column_label`).
    pub(crate) fn family_column(&self, pp: &[Setting], group: &str) -> String {
        self.family_of(pp).map_or_else(|| group.to_string(), |f| f.column_title(group))
    }

    /// The family's line under its table ("Each column is one profile. "), or nothing.
    pub(crate) fn family_note(&self, pp: &[Setting]) -> String {
        self.family_of(pp).map(|f| f.note.trim()).filter(|n| !n.is_empty()).map(|n| format!("{n} ")).unwrap_or_default()
    }

    pub(crate) fn pp_table(&self, ui: &mut egui::Ui, title: &str, pp: &[Setting], editable: bool, actions: &mut Vec<Action>) {
        let Some(doc) = &self.doc else { return };
        let mut params: Vec<String> = Vec::new();
        for s in pp {
            if !params.contains(&s.name) {
                params.push(s.name.clone());
            }
        }
        let n_profiles = pp.iter().filter_map(|s| s.index).max().map(|m| m as usize + 1).unwrap_or(0);
        // column titles from the group names, as the family says ("Picture Profile PP3" -> "PP3" with group_suffix)
        let col_title = |i: usize| -> String {
            pp.iter().find(|s| s.index == Some(i as u16)).map(|s| self.family_column(pp, &s.group)).unwrap_or_default()
        };
        egui::CollapsingHeader::new(RichText::new(title).strong().color(tab_ink(ui.visuals(), &self.schema.camera, pp.first().map_or("", |s| s.tab.as_str()))))
            .id_salt((title, self.target))
            .default_open(true)
            // Collapse all / Expand all (`head_fold`, `fold_all`), for this one drawing
            .open(self.head_fold.map(|collapse| !collapse))
            .show(ui, |ui| {
                ui.label(RichText::new(format!("{}Values the camera never produces are not offered.", self.family_note(pp))).small().color(tone::weak(ui.visuals())));
                egui::ScrollArea::horizontal().id_salt((title, "scroll")).show(ui, |ui| {
                    egui::Grid::new((title, "grid", self.target)).striped(true).spacing([10.0, 4.0]).show(ui, |ui| {
                        ui.strong("Parameter");
                        for i in 0..n_profiles {
                            ui.strong(col_title(i));
                        }
                        ui.end_row();
                        for name in &params {
                            ui.label(name);
                            for i in 0..n_profiles {
                                // the linked copies of this parameter for profile i
                                let linked: Vec<&Setting> = pp.iter().filter(|s| &s.name == name && s.index == Some(i as u16)).collect();
                                let Some(s) = linked.first() else { ui.label(""); continue };
                                let cur = doc.value(self.target, s.slot());
                                let changed = cur != doc.original_value(self.target, s.slot());
                                // a profile no menu writes is view only outside Expert mode (`locked_why`); a value the
                                // camera keeps in more than one record says what changing it changes (`copy_note`)
                                let locked = linked.iter().find_map(|l| self.locked_why(l, self.target));
                                let note = linked.iter().find_map(|l| self.copy_note(l, self.target));
                                let can_edit = editable && s.scalar && cur.is_some() && linked.iter().all(|l| self.shape_ok(l)) && locked.is_none();
                                let mut chosen = cur;
                                let spoken = format!("{} {name}", col_title(i));
                                let cell = ui.add_enabled_ui(can_edit, |ui| {
                                    if let (Some((lo, hi)), Some(mut v)) = (s.range, cur) {
                                        let step = s.step.unwrap_or(1).max(1);
                                        named(ui.add(egui::DragValue::new(&mut v).range(lo..=hi).speed(0.2 * step as f64)), &spoken);
                                        chosen = Some(snap_to_step(v, lo, hi, step));
                                    } else {
                                        let r = egui::ComboBox::from_id_salt((s.key.as_str(), self.target)).width(110.0)
                                            .selected_text(Self::describe(s, cur))
                                            .show_ui(ui, |ui| {
                                                for (v, label) in self.offered_values(s, self.target) {
                                                    ui.selectable_value(&mut chosen, Some(v), label);
                                                }
                                            });
                                        named(r.response, &spoken);
                                    }
                                });
                                let r = cell.response.rect;
                                let radius = egui::CornerRadius::same(2);
                                if changed {
                                    ui.painter().rect_stroke(r, radius, egui::Stroke::new(1.5_f32, tone::edit(ui.visuals())), egui::StrokeKind::Outside);
                                }
                                let hover = if self.prefs.expert { format!("{} {name}: record 0x{:04x}[{i}]", col_title(i), s.id) } else { format!("{} {name}", col_title(i)) };
                                let hover = match self.unnamed_why(s, cur) { Some(w) => format!("{hover}\n\n{w}"), None => hover };
                                let hover = match &locked { Some((w, _)) => format!("{hover}\n\n{w}"), None => hover };
                                let hover = match &note { Some((w, _)) => format!("{hover}\n\n{w}"), None => hover };
                                cell.response.on_hover_text(hover.clone()).on_disabled_hover_text(hover);
                                // its other records follow it, by the value of the same name (`apply`)
                                if chosen != cur {
                                    if let Some(v) = chosen {
                                        actions.push(Action::Set(self.target, s.slot(), v));
                                    }
                                }
                            }
                            ui.end_row();
                        }
                    });
                });
            });
    }

    /// The selected setting: where it is, its options (listed like the camera's picker),
    /// and the original / compare values. `linked` holds every record that stores this
    /// setting; the first one drives the display and the others follow it.
    pub(crate) fn detail_panel(&self, ui: &mut egui::Ui, tab: &str, group: &str, linked: &[Setting], editable: bool, actions: &mut Vec<Action>) {
        let s = &linked[0];
        ui.label(RichText::new(format!("{tab} > {group}")).small().color(tab_ink(ui.visuals(), &self.schema.camera, tab)));
        // the setting's full name, where a camera menu titles its row as the camera draws it ("SteadyShot")
        ui.heading(self.full_name(s));
        if !s.help.is_empty() {
            ui.label(RichText::new(&s.help)).on_hover_text(self.help_hover(s.help_from_file, &self.schema.help_src));
        }
        // the note is the mapping team's words: Expert mode only
        if self.prefs.expert && !s.note.is_empty() {
            ui.label(RichText::new(&s.note).small().color(tone::weak(ui.visuals())));
        }
        ui.horizontal_wrapped(|ui| {
            if !s.modes.is_empty() {
                ui.label(RichText::new(format!("Applies in: {}", s.modes)).small().color(tone::note(ui.visuals()))).on_hover_text(self.modes_hover());
            }
            // where the camera greys it whatever the file holds (`grey_in`)
            if let Some(words) = self.grey_in_words(s) {
                ui.label(RichText::new(words).small().color(tone::note(ui.visuals())));
            }
            if s.in_sets {
                ui.label(RichText::new("Kept in the memories too").small().color(tone::weak(ui.visuals()))).on_hover_text(self.memories_hover());
            } else if self.prefs.expert && s.area == "global" {
                ui.label(RichText::new("Live settings only").small().color(tone::weak(ui.visuals()))).on_hover_text("The memories don't keep it");
            }
            if self.prefs.expert {
                ui.label(RichText::new(format!("record 0x{:04x}", s.id)).small().color(tone::weak(ui.visuals())));
            }
            if self.prefs.expert && s.disputed {
                ui.label(RichText::new(DISPUTED).small().color(tone::caution(ui.visuals())))
                    .on_hover_text("The proofs of this setting disagree: what the editor shows is not counted as proved");
            } else if self.prefs.expert && self.prefs.show_proof {
                match (&s.proved, s.unproved_in(self.target)) {
                    (_, Some(u)) => {
                        ui.label(RichText::new(s.proof_badge_in(self.target).0).small().color(tone::note(ui.visuals()))).on_hover_text(&u.why);
                    }
                    (Some(_), None) => {
                        ui.label(RichText::new(s.proof_badge().0).small().color(tone::ok(ui.visuals())))
                            .on_hover_text(proved_hover(s));
                    }
                    (None, None) => match &s.unproved_reason {
                        Some(u) => {
                            ui.label(RichText::new(s.proof_badge().0).small().color(tone::note(ui.visuals()))).on_hover_text(&u.why);
                        }
                        None => {
                            ui.label(RichText::new(s.proof_badge().0).small().color(tone::weak(ui.visuals())))
                                .on_hover_text("The meaning comes from the mapping work but has not been checked by choosing each option in the camera's own menu");
                        }
                    },
                }
            } else if s.not_on_camera() {
                // with the proof line off, the one plain fact it carries
                ui.label(RichText::new("Not on this camera's menu").small().color(tone::weak(ui.visuals())));
            }
        });
        // the values its menus never offer, and a factory value the camera writes itself, one line per reason
        self.not_offered_ui(ui, s);
        if !s.display_rule.is_empty() {
            ui.label(RichText::new(format!("Shown differently on the camera: {}", s.display_rule)).small().color(tone::weak(ui.visuals())));
        }
        let Some(doc) = &self.doc else {
            ui.label("Open a settings file to see and edit this value.");
            return;
        };
        let cur = doc.value(self.target, s.slot());
        let orig = doc.original_value(self.target, s.slot());
        let changed = cur != orig;
        ui.add_space(8.0);

        // greyed out on the camera? (the value is kept and used once the blocker changes)
        if let Some(r) = s.inactive_when.as_ref().filter(|r| r.inactive(doc.value(self.target, (r.record, None)))) {
            egui::Frame::new().fill(tone::boxed(ui.visuals())).inner_margin(8.0).corner_radius(4.0).show(ui, |ui| {
                ui.label(format!(
                    "Greyed out on the camera while {} = {}. The value is kept and takes effect when {} changes.",
                    r.name, Self::describe_record(&self.schema, r.record, doc.value(self.target, (r.record, None))), r.name
                ));
                if editable && ui.button(format!("Activate (set {} to {})", r.name, r.unlock_label)).clicked() {
                    actions.push(Action::Set(self.target, (r.record, None), r.unlock));
                }
            });
            ui.add_space(8.0);
        }
        // greyed out on the camera in some modes only, or with a device on the HDMI socket (`inactive_if`): when, and Activate
        for line in self.grey_lines(s, self.target, self.menu_shown().as_deref()).into_iter().filter(|l| l.activate.is_some() || l.muted.is_some()) {
            egui::Frame::new().fill(tone::boxed(ui.visuals())).inner_margin(8.0).corner_radius(4.0).show(ui, |ui| {
                ui.label(&line.text);
                if let Some((record, unlock, name, label)) = &line.activate {
                    if editable && ui.button(format!("Activate (set {name} to {label})")).clicked() {
                        actions.push(Action::Set(self.target, (*record, None), *unlock));
                    }
                }
                // its modes none of this menu's: no Activate, and why
                if let Some(why) = &line.muted {
                    ui.label(RichText::new(why).small().color(tone::weak(ui.visuals())));
                }
                if let Some(cable) = &line.cable {
                    ui.label(RichText::new(cable).small().color(tone::weak(ui.visuals())));
                }
            });
            ui.add_space(8.0);
        }
        let foreign = self.foreign_model(&doc.edited);
        if let Some(model) = &foreign {
            ui.label(RichText::new(self.foreign_words(model)).color(tone::bad(ui.visuals())));
        } else if !editable {
            ui.add(egui::Label::new(RichText::new(self.view_only_why(false)).color(tone::bad(ui.visuals()))).wrap());
        }
        // a setting no menu of the camera writes: view only outside Expert mode, and why (`locked_why`)
        let locked = linked.iter().find_map(|l| self.locked_why(l, self.target));
        if let Some((why, hover)) = &locked {
            ui.add(egui::Label::new(RichText::new(why).small().color(tone::note(ui.visuals()))).wrap()).on_hover_text(hover);
            ui.add_space(4.0);
        }
        // a value the camera keeps in more than one record: what changing it changes, or that the file is out of step
        // there (`copy_note`), before anything is changed
        if let Some((note, hover)) = linked.iter().find_map(|l| self.copy_note(l, self.target)) {
            ui.add(egui::Label::new(RichText::new(note).small().color(tone::note(ui.visuals()))).wrap()).on_hover_text(hover);
            ui.add_space(4.0);
        }
        self.unnamed_line(ui, s, cur);

        if let Some(rule) = &s.text {
            let rec = doc.edited.sections.get(self.target).and_then(|sec| sec.get(s.id));
            let cur_text = rec.and_then(|r| r.text()).unwrap_or_default();
            let editable_text = editable && rec.is_some() && linked.iter().all(|l| self.shape_ok(l)) && locked.is_none();
            // what is typed belongs to this file as opened and to the text it held: another file, an undo, a revert
            // or an edit from the page starts the field afresh, so it never applies text typed over something else
            let id = egui::Id::new(("text", s.key.as_str(), self.target, doc.opened, cur_text.as_str()));
            let mut buf = ui.data_mut(|d| d.get_temp::<String>(id)).unwrap_or_else(|| cur_text.clone());
            ui.add_enabled_ui(editable_text, |ui| {
                let resp = named(ui.add(egui::TextEdit::singleline(&mut buf).desired_width(160.0).char_limit(rule.max_len)), &s.name);
                if rule.uppercase {
                    buf = buf.to_uppercase();
                }
                match rule.check(&buf) {
                    Ok(()) if buf != cur_text => {
                        if resp.lost_focus() || ui.input(|i| i.key_pressed(egui::Key::Enter)) {
                            actions.push(Action::SetText(self.target, s.id, buf.clone()));
                        } else {
                            ui.label(RichText::new("press Enter to apply").small().color(tone::weak(ui.visuals())));
                        }
                    }
                    Ok(()) => {}
                    Err(e) => {
                        ui.label(RichText::new(e).small().color(tone::bad(ui.visuals())));
                    }
                }
            });
            ui.data_mut(|d| d.insert_temp(id, buf));
            let orig_text = doc.original.sections.get(self.target).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default();
            ui.add_space(8.0);
            egui::Grid::new("text_info").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
                ui.label(RichText::new("Original").color(tone::weak(ui.visuals())));
                ui.label(&orig_text);
                ui.end_row();
                if let Some(c) = self.compare.as_ref().and_then(|(_, c)| c.sections.get(self.target)?.get(s.id)?.text()) {
                    ui.label(RichText::new("Compare file").color(tone::weak(ui.visuals())));
                    ui.label(RichText::new(c).color(Src::B.tone(ui.visuals())));
                    ui.end_row();
                }
            });
            if cur_text != orig_text && ui.button(format!("Revert to {orig_text}")).clicked() {
                actions.push(Action::Revert(self.target, (s.id, None)));
                ui.data_mut(|d| d.remove::<String>(id));
            }
        } else {
            let mut chosen = cur;
            let can_edit = editable && s.scalar && cur.is_some() && linked.iter().all(|l| self.shape_ok(l)) && locked.is_none();
            if let (Some((lo, hi)), Some(mut v)) = (s.range, cur) {
                // numeric setting with a known range: only values the camera can produce
                let step = s.step.unwrap_or(1).max(1);
                ui.add_enabled_ui(can_edit, |ui| {
                    ui.horizontal(|ui| {
                        if named(ui.add_enabled(v - step >= lo, egui::Button::new(" − ")), &format!("{}: one step down", s.name)).clicked() {
                            v -= step;
                        }
                        named(ui.add(number_box(s, &mut v, lo, hi, step)), &s.name);
                        if named(ui.add_enabled(v + step <= hi, egui::Button::new(" + ")), &format!("{}: one step up", s.name)).clicked() {
                            v += step;
                        }
                    });
                });
                ui.label(RichText::new(range_words(s, lo, hi, step)).small().color(tone::weak(ui.visuals())));
                chosen = Some(snap_to_step(v, lo, hi, step));
            } else if s.values.len() >= 2 {
                let hidden = s.hidden_unproved(self.allow_unobserved);
                if hidden > 0 && self.prefs.expert {
                    ui.label(RichText::new(hidden_words(hidden)).small().color(tone::weak(ui.visuals())));
                }
                if let Some((v, _)) = self.option_choice_ui(ui, self.target, s, (cur, orig), can_edit, foreign.is_some()) {
                    chosen = Some(v);
                }
                self.sub_choice_ui(ui, s, cur, editable, actions);
            } else {
                ui.label(RichText::new(Self::describe(s, cur)).strong());
                ui.label(RichText::new("Can't be changed here: only one value is known.").small().color(tone::weak(ui.visuals())));
            }
            // its other records follow it (`apply`)
            if chosen != cur {
                if let Some(v) = chosen {
                    actions.push(Action::Set(self.target, s.slot(), v));
                }
            }
            ui.add_space(8.0);
            egui::Grid::new("value_info").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
                if changed {
                    ui.label(RichText::new("Original").color(tone::weak(ui.visuals())));
                    ui.label(Self::describe(s, orig));
                    ui.end_row();
                }
            });
            // a fraction tile's part goes back with its other part (`revert_actions`)
            if changed && ui.button(format!("Revert to {}", Self::describe(s, orig))).clicked() {
                actions.extend(self.revert_actions(std::slice::from_ref(s), self.target));
            }
            // where the plain Revert does not serve: a value a Save As kept put back to what the camera wrote, a copy put
            // back in step with its setting (`put_back_choice`), its hover saying which (`put_back_hover`)
            if let Some((words, fix)) = self.put_back_choice(linked, self.target) {
                let hover = Self::put_back_hover(&words);
                if ui.button(words).on_hover_text(hover).clicked() {
                    actions.extend(fix);
                }
            }
        }

        ui.add_space(12.0);
        if self.prefs.expert {
            let ids: Vec<String> = linked.iter().map(|l| format!("0x{:04x}", l.id)).collect();
            ui.label(RichText::new(format!(
                "{} {} ({}){}",
                if linked.len() > 1 { "Records" } else { "Record" },
                ids.join(", "),
                s.area,
                if linked.len() > 1 { " · changing this updates all linked records together" } else { "" },
            )).small().color(tone::weak(ui.visuals())));
            if ui.small_button("Show in record map").on_hover_text("The record and its neighbours in file order").clicked() {
                actions.push(Action::ShowInMap(s.id));
            }
        }
        if let Some(v) = cur {
            if let Some(reason) = s.acceptance(v) {
                if changed {
                    ui.label(RichText::new(format!("⚠ {reason}")).small().color(tone::caution(ui.visuals())));
                }
            }
            // a value of another video system than the file's, edited or not: the Write window lists it too
            if let Some(why) = self.other_system_words(s, v, self.target) {
                ui.add(egui::Label::new(RichText::new(format!("⚠ {why}")).small().color(tone::caution(ui.visuals()))).wrap());
            }
        }
        if self.show_raw {
            ui.label(RichText::new(format!("raw value: {}", cur.map(|v| v.to_string()).unwrap_or_default())).small().monospace().color(tone::weak(ui.visuals())));
        }
    }

    /// A setting's named values as the detail panel lists them, like the camera's picker: each option with how it was
    /// proved (a value no proof on the camera established in italics, one the camera refuses in the caution colour,
    /// each saying so on hover with the option's help), the value held now marked (in the edit colour when it is an
    /// edit) and "↑ original" beside the one it was; as the camera nests them when the definition's option tree fits
    /// (the main options, and under the one the value belongs to, its choices). Values no proof established are listed
    /// only when the person asks for them (`allow_unobserved`), or when held now. The option clicked, if any, with whether
    /// it is final: false for a main option with choices of its own, whose choices it then shows. The detail panel
    /// and Compare's picker (`compare_picker`) both draw it, for set `section`, so a value is chosen the same way in each.
    pub(crate) fn option_choice_ui(&self, ui: &mut egui::Ui, section: usize, s: &Setting, (cur, orig): (Option<i64>, Option<i64>), can_edit: bool, weak: bool) -> Option<(i64, bool)> {
        let changed = cur != orig;
        let mut pick: Option<(i64, bool)> = None;
        // the options that open a choice of their own on the camera (`menu_rows::sub_choices`), marked "›"
        let beside = self.beside(s);
        let opens = |label: &str| -> Vec<&str> { beside.iter().filter(|(_, o)| o == label).map(|(x, _)| x.name.as_str()).collect() };
        // the options that open a whole page of rows (`menu_rows::pages`), marked "›" too, with a link to the page when
        // chosen or under the pointer (in Edit: Compare's picker only picks)
        let pages = if self.mode == Mode::Edit { self.option_pages(s) } else { Vec::new() };
        // one option: its label (and code), how it was seen, its help on hover, "original" beside it; true on a click
        let option_line = |ui: &mut egui::Ui, v: i64, label: &str| -> bool {
            // a value the menus never offer is listed only while the file holds it, and says why
            let never = s.never_offered(v);
            let seen = s.established(v) && never.is_none();
            let refused = s.refused.contains(&v);
            let subs = opens(label);
            let page = menu_rows::page_for(&pages, label);
            let shown = if subs.is_empty() && page.is_none() { label.to_string() } else { format!("{label}  ›") };
            let mut text = RichText::new(if self.show_raw { format!("{shown}  [{v}]") } else { shown });
            if Some(v) == cur {
                text = text.strong().color(if changed { tone::edit(ui.visuals()) } else { ui.visuals().selection.stroke.color });
            } else if refused {
                text = text.color(tone::caution(ui.visuals()));
            } else if !seen {
                text = text.color(tone::weak(ui.visuals())).italics();
            }
            if weak { text = text.weak(); }
            // the option's help, and whose words it is, value by value (`option_help_from_file`)
            let whose = |h: &str| format!("{h}\n\n{}", self.help_hover(s.option_help_from_file.contains(&v), &self.schema.help_src));
            let unseen = match never {
                Some(n) => format!("The camera's menus never offer this value: {}", n.why),
                None => UNPROVED_HOVER.to_string(),
            };
            let hover = match (s.option_help(v), seen) {
                (Some(h), true) => whose(h),
                (Some(h), false) => format!("{}\n\n{unseen}", whose(h)),
                (None, true) => String::new(),
                (None, false) => unseen,
            };
            let hover = if !refused { hover } else if hover.is_empty() { REFUSED_HOVER.to_string() } else { format!("{hover}\n\n{REFUSED_HOVER}") };
            // an option not chosen says what choosing it opens beside it, as Right does on the camera
            let hover = match (subs.is_empty() || Some(v) == cur, hover.is_empty()) {
                (true, _) => hover,
                (false, true) => format!("Has a choice of its own: {}", subs.join(", ")),
                (false, false) => format!("{hover}\n\nHas a choice of its own: {}", subs.join(", ")),
            };
            let hover = match page.filter(|_| Some(v) != cur) {
                Some(p) => format!("{}Opens a page of {} settings on the camera (Right on it).", if hover.is_empty() { String::new() } else { format!("{hover}\n\n") }, p.count),
                None => hover,
            };
            let resp = ui.add_enabled(can_edit, egui::SelectableLabel::new(Some(v) == cur, text)).on_hover_text(hover);
            if changed && Some(v) == orig {
                ui.label(RichText::new("   ↑ original").small().color(tone::note(ui.visuals())));
            }
            // the link to the page the option opens: under it while it is chosen or under the pointer
            if let Some(p) = page {
                let id = ui.id().with(("page_link", &s.key, v));
                let was = ui.ctx().data(|d| d.get_temp::<bool>(id)).unwrap_or(false);
                let mut near = resp.hovered();
                if Some(v) == cur || was {
                    let words = Self::page_link_words(&p.option, self.camera_layout());
                    let link = ui.indent(("page_link", v), |ui| ui.link(RichText::new(words).small())).inner
                        .on_hover_text(format!("The {} settings the camera lists on the page {} opens", p.count, p.option));
                    near |= link.hovered() || ui.rect_contains_pointer(resp.rect.union(link.rect).expand(4.0));
                    if link.clicked() {
                        *self.open_page.borrow_mut() = Some(p.key.clone());
                    }
                }
                ui.ctx().data_mut(|d| d.insert_temp(id, near));
            }
            resp.clicked()
        };
        let sys = self.system_in(section);
        let shown = |v: i64| Some(v) == cur || (s.offerable(v) && (s.established(v) || self.allow_unobserved) && s.other_system(v, sys.as_deref()).is_none());
        if let Some(tree) = s.option_tree() {
            // as the camera lays them out: the main options, and under the one the value belongs to, its choices
            let offered: Vec<i64> = s.values.iter().map(|(v, _)| *v).filter(|&v| shown(v)).collect();
            for node in tree {
                if let Some(v) = node.value {
                    if shown(v) && option_line(ui, v, s.label_for(v).unwrap_or(&node.label)) {
                        pick = Some((v, true));
                    }
                    continue;
                }
                let subs: Vec<&(i64, String)> = node.options.iter().filter(|(v, _)| shown(*v)).collect();
                if subs.is_empty() {
                    continue;
                }
                let here = cur.is_some_and(|c| node.holds(c));
                let mut text = RichText::new(&node.label);
                if here {
                    text = text.strong().color(if changed { tone::edit(ui.visuals()) } else { ui.visuals().selection.stroke.color });
                }
                if weak { text = text.weak(); }
                let hover = if here { String::new() } else {
                    format!("Has a choice of its own: {}", subs.iter().map(|(_, l)| l.as_str()).collect::<Vec<_>>().join(", "))
                };
                let resp = ui.add_enabled(can_edit, egui::SelectableLabel::new(here, text)).on_hover_text(hover);
                if let Some(o) = orig.filter(|&o| changed && !here && node.holds(o)) {
                    let was = node.options.iter().find(|(v, _)| *v == o).map_or(String::new(), |(_, l)| format!(": {l}"));
                    ui.label(RichText::new(format!("   ↑ original{was}")).small().color(tone::note(ui.visuals())));
                }
                if resp.clicked() {
                    pick = node.pick(cur, &offered).map(|v| (v, false));
                }
                if here {
                    ui.indent(("option_tree", &node.label), |ui| {
                        for (v, label) in &subs {
                            if option_line(ui, *v, label) {
                                pick = Some((*v, true));
                            }
                        }
                    });
                }
            }
        } else {
            for (v, label) in &s.values {
                if shown(*v) && option_line(ui, *v, label) {
                    pick = Some((*v, true));
                }
            }
        }
        pick
    }

    /// The words of the link to the page an option opens: "Open the PP1 page" as on the camera; in the flat list, where
    /// the page is no group, its settings in their table.
    pub(crate) fn page_link_words(option: &str, camera: bool) -> String {
        if camera { format!("Open the {option} page") } else { format!("Open the {option} settings") }
    }

    /// The settings shown beside `s`'s options in the detail panel (`menu_rows::sub_choices`), with their option, from
    /// its camera group in the set being edited, and of a row a camera menu laid out (`shown_in`) as that menu lays
    /// them out (`beside_in`); none unless `s` is its row's own setting.
    pub(crate) fn beside(&self, s: &Setting) -> Vec<(Setting, String)> {
        self.beside_in(self.target, s.shown_in.as_deref(), s)
    }

    /// The settings of `s`'s camera group in the set being edited, as the camera menu that laid `s` out lists them
    /// (`settings_in_menu`), or as before menus: where the detail panel finds the records of a choice shown beside an
    /// option.
    fn camera_group_of(&self, s: &Setting) -> Vec<Setting> {
        let tab = self.layout_tab(s).to_string();
        let among: Vec<Setting> = match s.shown_in.as_deref().filter(|m| self.menu_named(m).is_some()) {
            Some(m) => self.settings_in_menu(self.target, m, Some(&tab)),
            None => self.settings_in(self.target, Some(&tab)).cloned().collect(),
        };
        among.into_iter().filter(|o| menu_rows::camera_group(o) == menu_rows::camera_group(s)).collect()
    }

    /// Under a setting's options in the detail panel: which of its options have a choice of their own on the camera,
    /// and every choice of the option chosen now (Drive Mode on Continuous Shooting: the continuous shooting speed;
    /// a look's parameters), in the order the definition lists them, each changed with the same control and rules as
    /// on a row, with its own Revert. As on the camera these are no rows of the middle panel (`menu_rows::lay_out`),
    /// so a sub-choice opened from elsewhere (`sub_focus`) is shown too, marked, whatever its option, and scrolled
    /// to. From the definition's `under_option` places; nothing when it has none for this setting, nor for an option
    /// whose choices the option tree shows already.
    fn sub_choice_ui(&self, ui: &mut egui::Ui, s: &Setting, cur: Option<i64>, editable: bool, actions: &mut Vec<Action>) {
        let subs = self.beside(s);
        if subs.is_empty() {
            return;
        }
        let Some(doc) = &self.doc else { return };
        let group = self.camera_group_of(s);
        let mut options: Vec<&str> = subs.iter().map(|(_, o)| o.as_str()).collect();
        options.dedup();
        ui.add_space(6.0);
        if self.prefs.expert {
            ui.label(RichText::new(format!("These options have a choice of their own on the camera: {}", options.join(", "))).small().color(tone::weak(ui.visuals())));
        }
        let now = cur.and_then(|v| s.label_for(v));
        let row_too = !self.camera_layout();
        // the chosen option's, and any other edited or opened from elsewhere, so an edit is never out of sight
        for (sub, option) in subs.iter().filter(|(x, o)| Some(o.as_str()) == now || self.changed(x) || self.sub_focus.as_ref() == Some(&x.key)) {
            // every record of that setting, as its own row has them
            let linked: Vec<Setting> = group.iter().filter(|o| o.links_with(sub)).cloned().collect();
            let (sv, so) = (doc.value(self.target, sub.slot()), doc.original_value(self.target, sub.slot()));
            let focused = self.sub_focus.as_ref() == Some(&sub.key);
            let mut frame = egui::Frame::new().fill(tone::boxed(ui.visuals())).inner_margin(8.0).corner_radius(4.0);
            if focused {
                frame = frame.stroke(egui::Stroke::new(1.5_f32, ui.visuals().selection.stroke.color));
            }
            let r = frame.show(ui, |ui| {
                let mut title = RichText::new(format!("For {option}: {}", sub.name)).strong();
                if sv != so {
                    title = title.color(tone::edit(ui.visuals()));
                }
                let hover = match (Some(option.as_str()) == now, row_too) {
                    (false, _) => format!("The camera shows this choice beside {option} when {option} is chosen; it is shown here as it is edited or was opened."),
                    (true, true) => "The choice the camera shows beside this option. It is also a row of its own in this group.".to_string(),
                    (true, false) => "The choice the camera shows beside this option (Right opens it on the camera).".to_string(),
                };
                ui.label(title).on_hover_text(hover);
                // its records move together, as on its own row (`apply`)
                ui.horizontal(|ui| self.compact_editor(ui, sub, editable && linked.iter().all(|l| self.shape_ok(l)), actions));
                if sv != so {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new(format!("was {}", Self::describe(sub, so))).small().color(tone::weak(ui.visuals())));
                        if ui.small_button("Revert").clicked() {
                            actions.extend(self.revert_actions(std::slice::from_ref(sub), self.target));
                        }
                    });
                }
            });
            if focused && self.sub_scroll.take() {
                r.response.scroll_to_me(Some(egui::Align::Center));
            }
            ui.add_space(4.0);
        }
    }
}

/// What a row of a view of one menu shows of the greys the file does not decide alone (`App::grey`): whether it is
/// dimmed, and the words beside it ("grey in S&Q"). Never hidden, never view only.
pub(crate) struct Grey {
    pub(crate) dim: bool,
    pub(crate) note: Option<String>,
}

/// A line of the detail panel about a grey (`App::grey_lines`): its words; the Activate it offers (the record, the value
/// that lifts the grey, the record's name and that value's label); why it offers none where its modes are none of the
/// view's (`muted`: Activate would change nothing there); and, for a rule that needs a device on the HDMI socket, the
/// words that say the cable is the owner's.
pub(crate) struct GreyLine {
    pub(crate) text: String,
    pub(crate) activate: Option<(u16, i64, String, String)>,
    pub(crate) muted: Option<String>,
    pub(crate) cable: Option<String>,
}

/// "S&Q", "S&Q and Time-lapse", "Stills, Movie and S&Q".
fn modes_words(list: &[String]) -> String {
    match list {
        [] => String::new(),
        [one] => one.clone(),
        [rest @ .., last] => format!("{} and {last}", rest.join(", ")),
    }
}

impl App {
    /// The shooting modes the definition names (`camera.live_mode`, `memory_sets.modes`).
    fn known_modes(&self) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        let names = self.schema.camera.live_mode.iter().flat_map(|l| l.modes.values().cloned())
            .chain(self.schema.camera.memory_sets.iter().flat_map(|m| m.modes.keys().cloned()));
        for n in names {
            if !out.contains(&n) {
                out.push(n);
            }
        }
        out
    }

    /// The shooting modes a view of menu `menu` for set `target` stands for: the set's own mode (`set_mode`: the live
    /// settings' by `camera.live_mode`, a memory's by `memory_sets.modes`) where it is one of the menu's, else every mode
    /// of the menu; with no menu, the set's mode where known, else every mode the definition names.
    pub(crate) fn view_modes(&self, target: usize, menu: Option<&str>) -> Vec<String> {
        let mode = self.set_mode(target);
        match menu.and_then(|m| self.menu_named(m)) {
            Some(m) => match mode.filter(|f| m.modes.contains(f)) {
                Some(f) => vec![f],
                None => m.modes.clone(),
            },
            None => mode.map_or_else(|| self.known_modes(), |f| vec![f]),
        }
    }

    /// `list` where the definition names every mode in it; None for a mode it does not name, so that grey is drawn
    /// as usual and said nowhere.
    fn named_modes(&self, list: &[String]) -> Option<Vec<String>> {
        let known = self.known_modes();
        list.iter().all(|m| known.contains(m)).then(|| list.to_vec())
    }

    /// The modes `s` is grey in whatever the file holds (`grey_in`), where it names any and the definition names them all.
    fn grey_in_modes(&self, s: &Setting) -> Option<Vec<String>> {
        self.named_modes(&s.grey_in).filter(|l| !l.is_empty())
    }

    /// The detail's words for `grey_in` ("The camera greys this out in S&Q and Time-lapse."), for every user.
    pub(crate) fn grey_in_words(&self, s: &Setting) -> Option<String> {
        self.grey_in_modes(s).map(|l| format!("The camera greys this out in {}.", modes_words(&l)))
    }

    /// `s`'s `inactive_if` where its rule holds in set `target` by the file (and the definition names its modes), with
    /// the record's value there.
    fn inactive_if_holds<'a>(&self, s: &'a Setting, target: usize) -> Option<(&'a camset_editor::schema::InactiveIf, Option<i64>)> {
        let r = s.inactive_if.as_ref()?;
        self.named_modes(&r.family)?;
        let v = self.doc.as_ref()?.value(target, (r.rule.record, None));
        r.rule.inactive(v).then_some((r, v))
    }

    /// What a row of `s` shows in a view of menu `menu` for set `target` (`view_modes`) of the greys the camera keeps:
    /// `inactive_when` dimmed where its rule holds, as always; `grey_in` dimmed where it covers every mode the view stands
    /// for, "grey in S&Q" beside it where it covers some; `inactive_if` where its rule holds: with `family` dimmed where it
    /// covers every mode, the reason and "in S&Q" where it covers some, as usual where none; with `hdmi_device` never
    /// dimmed, "greyed with an HDMI device connected" (and its modes where they cover some). Never hidden, never view only.
    pub(crate) fn grey(&self, s: &Setting, target: usize, menu: Option<&str>) -> Grey {
        let view = self.view_modes(target, menu);
        let covered = |list: &[String]| -> Vec<String> { view.iter().filter(|m| list.contains(m)).cloned().collect() };
        let mut dim = self.doc.as_ref().is_some_and(|d| s.inactive_when.as_ref().is_some_and(|r| r.inactive(d.value(target, (r.record, None)))));
        let mut notes: Vec<String> = Vec::new();
        if let Some(list) = self.grey_in_modes(s) {
            let c = covered(&list);
            if !c.is_empty() && c.len() == view.len() {
                dim = true;
            } else if !c.is_empty() {
                notes.push(format!("grey in {}", modes_words(&c)));
            }
        }
        if let Some((r, v)) = self.inactive_if_holds(s, target) {
            let c = covered(&r.family);
            let all = r.family.is_empty() || (!c.is_empty() && c.len() == view.len());
            let some = !all && !c.is_empty();
            if r.hdmi_device {
                if all || some {
                    let modes = if some { format!(", in {}", modes_words(&c)) } else { String::new() };
                    notes.push(format!("greyed with an HDMI device connected{modes}"));
                }
            } else if all {
                dim = true;
            } else if some {
                notes.push(format!("greyed while {} = {}, in {}", r.rule.name, Self::describe_record(&self.schema, r.rule.record, v), modes_words(&c)));
            }
        }
        Grey { dim, note: (!notes.is_empty()).then(|| notes.join("; ")) }
    }

    /// The detail panel's lines about `s`'s greys in set `target` as menu `menu` shows it, for every user: `grey_in`'s
    /// modes (no Activate), and where `inactive_if`'s rule holds, when the camera greys it, with Activate where its modes
    /// meet the view's (`view_modes`; else why there is none: it would change nothing here), and for a device on the
    /// HDMI socket that the cable is the owner's.
    pub(crate) fn grey_lines(&self, s: &Setting, target: usize, menu: Option<&str>) -> Vec<GreyLine> {
        let mut out: Vec<GreyLine> = self.grey_in_words(s).into_iter().map(|text| GreyLine { text, activate: None, muted: None, cable: None }).collect();
        if let Some((r, v)) = self.inactive_if_holds(s, target) {
            let what = format!("{} = {}", r.rule.name, Self::describe_record(&self.schema, r.rule.record, v));
            let device = if r.hdmi_device { " and a device is connected to the HDMI socket" } else { "" };
            let only = if r.family.is_empty() { String::new() } else { format!(", in {} only", modes_words(&r.family)) };
            let view = self.view_modes(target, menu);
            let here = r.family.is_empty() || r.family.iter().any(|m| view.contains(m));
            out.push(GreyLine {
                text: format!("Greyed out on the camera while {what}{device}{only}."),
                activate: here.then(|| (r.rule.record, r.rule.unlock, r.rule.name.clone(), r.rule.unlock_label.clone())),
                muted: (!here).then(|| format!("Nothing to activate in this menu: the camera greys it in {} only.", modes_words(&r.family))),
                cable: r.hdmi_device.then(|| "Unplugging the HDMI device is yours to do: Activate changes the setting only.".to_string()),
            });
        }
        out
    }

    /// The switch Activate sets for `s` in set `target` as menu `menu` shows it, the window's and the page's alike:
    /// `inactive_when`'s where its rule holds, else `inactive_if`'s where its rule holds and its modes meet the view's
    /// (`grey_lines`): the record, its value, the record's name and that value's label. None where nothing here is greyed
    /// that a setting lifts.
    pub(crate) fn activate_rule(&self, s: &Setting, target: usize, menu: Option<&str>) -> Option<(u16, i64, String, String)> {
        let d = self.doc.as_ref()?;
        if let Some(r) = s.inactive_when.as_ref().filter(|r| r.inactive(d.value(target, (r.record, None)))) {
            return Some((r.record, r.unlock, r.name.clone(), r.unlock_label.clone()));
        }
        self.grey_lines(s, target, menu).into_iter().find_map(|l| l.activate)
    }
}

/// A family's table beside an option of a camera row, and an option that opens a page of its own.
#[cfg(test)]
mod family_tests {
    use super::*;
    use crate::test_support::sample_app;

    /// A family's settings placed beside an option of a camera row (a Creative Look's parameters, on the Creative Look
    /// row of Color/Tone) stay in the family's table in both layouts, counted once there, and the row still offers the
    /// chosen look's parameters beside it, in the window and on the page.
    #[test]
    fn a_family_table_keeps_the_settings_beside_an_option() {
        let (mut app, dir, user) = sample_app("family_beside", None);
        assert!(app.camera_layout());
        let fam = app.schema.camera.families.iter().find(|f| f.title == "Creative Looks").expect("the Creative Looks family").clone();
        let params: Vec<Setting> = app.settings_in(0, None).filter(|s| s.group.starts_with(&fam.prefix) && s.under_option.is_some()).cloned().collect();
        assert!(params.len() >= 100, "{} look parameters placed beside a look", params.len());
        let tab = params[0].tab.clone();
        for flat in [false, true] {
            app.prefs.flat_list = flat;
            let groups = app.tab_groups(&tab);
            let table = groups.iter().find(|(n, is_fam, _)| *is_fam && *n == fam.title).unwrap_or_else(|| panic!("no Creative Looks table (flat list {flat})"));
            let keys: std::collections::HashSet<&str> = table.2[0].iter().map(|s| s.key.as_str()).collect();
            assert!(params.iter().all(|p| keys.contains(p.key.as_str())), "flat list {flat}: a look parameter left the table");
            // each setting once across the tab's groups, but as on the camera one on the page an option opens (a
            // profile's parameter), in its table and its page's group; the Menu counts each setting once
            let mut seen: std::collections::HashMap<&str, Vec<(&str, bool)>> = Default::default();
            for (name, is_fam, rows) in &groups {
                for s in rows.iter().flatten() {
                    seen.entry(s.key.as_str()).or_default().push((name.as_str(), *is_fam));
                }
            }
            for (key, at) in &seen {
                let s = app.schema.settings.iter().find(|s| s.key == *key).unwrap();
                if at.len() > 1 {
                    assert!(!flat && s.on_page() && at.len() == 2 && at.iter().any(|(_, f)| *f) && at.contains(&(s.group.as_str(), false)), "flat list {flat}: {} listed in {at:?}", s.name);
                }
            }
            assert_eq!(app.visible_count(Some(&tab)), app.visible_settings(Some(&tab)).len(), "the Menu counts each setting once");
            assert!(params.iter().all(|p| app.shown_group_of(p) == fam.title));
        }
        app.prefs.flat_list = false;
        // the Creative Look row in Color/Tone offers the parameters of the look chosen
        let own = menu_rows::owner(app.settings_in(0, Some(&tab)), &params[0]).cloned().expect("the Creative Look row's own setting");
        let now = app.doc.as_ref().unwrap().value(0, own.slot()).and_then(|v| own.label_for(v)).expect("a named look in the sample").to_string();
        let beside: Vec<String> = app.beside(&own).into_iter().filter(|(_, o)| *o == now).map(|(s, _)| s.key.clone()).collect();
        assert!(!beside.is_empty(), "no parameters beside {now}");
        assert!(beside.iter().all(|k| params.iter().any(|p| &p.key == k)));
        let color = app.tab_groups(&tab).into_iter().find(|(n, _, _)| *n == menu_rows::camera_group(&params[0])).expect("the row's camera group").2;
        assert!(color.iter().any(|r| r[0].key == own.key) && !color.iter().flatten().any(|s| params.iter().any(|p| p.key == s.key)), "the parameters are not rows of the camera group too");
        // the page: the same table, and the row's sub-choices marked as counted in the family
        let row = app.web_row(0, std::slice::from_ref(&own));
        let subs = row["subs"]["rows"].as_array().expect("the page's sub-choices");
        assert!(subs.iter().any(|r| r["option"] == now.as_str()));
        assert!(subs.iter().filter(|r| params.iter().any(|p| p.key == r["key"].as_str().unwrap())).all(|r| r["family"] == true));
        let _ = (std::fs::remove_dir_all(dir), std::fs::remove_dir_all(user));
    }

    /// The owner's case (2026-11-07): Right on PP1 of Picture Profile opens a whole page of rows. As on the camera the
    /// page is its own group after Color/Tone, laid out with its headings (Black Gamma > Range, Level), the stills and
    /// movie copies side by side; the option is marked and links to it, its settings are no boxes beside it, and a
    /// jump to one of them lands on the page. The flat list keeps the table. Skipped while no setting is on a page.
    #[test]
    fn an_option_opens_its_page() {
        let (mut app, dir, user) = sample_app("page", Some(crate::test_support::strip_menus));
        let Some(own) = app.settings_in(0, None).find(|s| !app.option_pages(s).is_empty()).cloned() else {
            assert!(!app.schema.settings.iter().any(Setting::on_page), "settings on a page and no option opening it");
            let _ = (std::fs::remove_dir_all(dir), std::fs::remove_dir_all(user));
            return;
        };
        let pages = app.option_pages(&own);
        let p = pages[0].clone();
        assert!(p.count > 10 && own.values.iter().any(|(_, l)| *l == p.option), "{p:?}");
        assert!(app.beside(&own).iter().all(|(x, _)| !x.on_page()), "no boxes for the page's settings");
        let on = app.schema.settings.iter().find(|s| s.key == p.key).cloned().unwrap();
        let tab = app.layout_tab(&on).to_string();
        let groups = app.tab_groups(&tab);
        let names: Vec<&str> = groups.iter().map(|(n, _, _)| n.as_str()).collect();
        let at = names.iter().position(|n| *n == p.group).unwrap_or_else(|| panic!("no group {} in {names:?}", p.group));
        assert!(!groups[at].1 && names.iter().position(|n| *n == menu_rows::camera_group(&own)).is_some_and(|o| o < at), "after its owner's group: {names:?}");
        let rows = &groups[at].2;
        let lines = app.group_lines(rows);
        assert!(lines.iter().any(|l| matches!(l, Line::Heading { depth: 0, .. })) && !lines.iter().any(|l| matches!(l, Line::Heading { label, .. } if *label == p.option || *label == own.row[0])), "the page's own headings: {lines:?}");
        // a parameter's copies side by side, at one depth
        let drawn: Vec<(String, usize)> = lines.iter().filter_map(|l| match l { Line::Row { index, depth } => Some((rows[*index][0].name.clone(), *depth)), _ => None }).collect();
        assert!(drawn.windows(2).any(|w| w[1].0 == format!("{} (stills)", w[0].0) && w[0].1 == w[1].1) || drawn.windows(2).any(|w| w[0].0 == format!("{} (stills)", w[1].0) && w[0].1 == w[1].1), "{drawn:?}");
        // the option's link opens the page, the frame after
        let ctx = egui::Context::default();
        let mut frame = eframe::Frame::_new_kittest();
        (app.view, app.group, app.item, app.item_key) = (View::Tab(own.tab.clone()), Some(menu_rows::camera_group(&own).to_string()), Some(own.name.clone()), Some(own.key.clone()));
        *app.open_page.borrow_mut() = Some(p.key.clone());
        let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(&mut app, ctx, &mut frame));
        assert_eq!((&app.view, app.group.as_deref()), (&View::Tab(tab.clone()), Some(p.group.as_str())));
        assert!(app.item.as_ref().is_some_and(|i| rows.iter().any(|r| &r[0].name == i)), "the page's first row chosen");
        // a jump to one of its settings lands on the page, not on its owner
        app.open_in_menu(&on);
        assert_eq!(app.group.as_deref(), Some(p.group.as_str()));
        assert_eq!(App::page_link_words(&p.option, true), format!("Open the {} page", p.option));
        // the flat list: the family's table, no page group
        app.set_flat_list(true);
        assert!(app.tab_groups(&tab).iter().all(|(n, _, _)| *n != p.group) && app.shown_group_of(&on) != p.group);
        app.set_flat_list(false);
        let _ = (std::fs::remove_dir_all(dir), std::fs::remove_dir_all(user));
    }
}

/// The greys the camera measured that the definition could not say before (`grey_in`, `inactive_if`), stubbed as the
/// next data pass gives them (`test_support::grey_stub`).
#[cfg(test)]
mod grey_tests {
    use super::*;
    use crate::test_support::{done, grey_stub, sample_app};

    /// The live-mode record (`camera.live_mode`).
    const LIVE_MODE: u16 = 0x13bf;

    fn by(app: &App, key: &str) -> Setting {
        app.schema.settings.iter().find(|s| s.key == key).cloned().unwrap()
    }

    fn put(app: &mut App, section: usize, id: u16, v: i64) {
        app.doc.as_mut().unwrap().edited.sections[section].get_mut(id).unwrap().put(None, v).unwrap();
        app.schema_gen += 1;
    }

    /// A view of one menu stands for the edited set's mode (`set_mode`) where it is one of the menu's, else for every
    /// mode of the menu: the S&Q menu for S&Q and Time-lapse, for S&Q alone with the live settings saved in S&Q or an S&Q
    /// memory edited, for Time-lapse alone with a Time-lapse memory.
    #[test]
    fn a_view_stands_for_its_sets_mode_or_all_of_its_menus() {
        let (mut app, dir, user) = sample_app("grey_view", Some(grey_stub));
        put(&mut app, 0, LIVE_MODE, 0);
        assert_eq!(app.view_modes(0, Some("Still")), vec!["Stills".to_string()]);
        assert_eq!(app.view_modes(0, Some("S&Q")), vec!["S&Q".to_string(), "Time-lapse".into()]);
        assert_eq!(app.view_modes(7, Some("S&Q")), vec!["S&Q".to_string()], "an S&Q memory edited");
        assert_eq!(app.view_modes(10, Some("S&Q")), vec!["Time-lapse".to_string()], "a Time-lapse memory edited");
        put(&mut app, 0, LIVE_MODE, 2);
        assert_eq!(app.view_modes(0, Some("S&Q")), vec!["S&Q".to_string()], "the live settings saved in S&Q");
        done(&dir, &user);
    }

    /// `grey_in`: dimmed where it covers every mode the view stands for, as usual with "grey in S&Q" where it covers
    /// some, as usual where none; the detail says it for every user, with no Activate, and the row stays editable. A mode
    /// the definition does not name: as usual, said nowhere.
    #[test]
    fn grey_in_dims_where_it_covers_the_view_and_says_where_it_covers_some() {
        let (mut app, dir, user) = sample_app("grey_in", Some(grey_stub));
        put(&mut app, 0, LIVE_MODE, 0);
        let (audio, tc) = (by(&app, "global:0x02e9"), by(&app, "global:0x02f4"));
        let g = app.grey(&audio, 0, Some("Movie"));
        assert!(!g.dim && g.note.is_none(), "the Movie menu: as usual");
        assert!(app.grey(&audio, 0, Some("S&Q")).dim, "grey in both of the S&Q menu's modes: dimmed");
        let g = app.grey(&tc, 0, Some("S&Q"));
        assert!(!g.dim && g.note.as_deref() == Some("grey in S&Q"), "grey in one of them: a note");
        put(&mut app, 0, LIVE_MODE, 2);
        assert!(app.grey(&tc, 0, Some("S&Q")).dim, "the view standing for S&Q alone");
        assert!(app.grey(&audio, 10, Some("S&Q")).dim, "a Time-lapse memory edited");
        let lines = app.grey_lines(&audio, 0, Some("S&Q"));
        assert_eq!(lines.iter().map(|l| l.text.as_str()).collect::<Vec<_>>(), ["The camera greys this out in S&Q and Time-lapse."]);
        assert!(lines[0].activate.is_none());
        assert!(app.locked_why(&audio, 0).is_none() && app.cell_editable(Col::a(0), std::slice::from_ref(&audio)), "never view only");
        let slow = by(&app, "global:0x0332");
        let g = app.grey(&slow, 0, Some("S&Q"));
        assert!(!g.dim && g.note.is_none() && app.grey_lines(&slow, 0, Some("S&Q")).is_empty(), "an unknown mode: as usual");
        done(&dir, &user);
    }

    /// `inactive_if` with `family`: where the record's rule holds by the file, dimmed where its modes cover every mode
    /// the view stands for, as usual with the reason and "in S&Q" where they cover some, as usual where none; the detail
    /// says it with Activate; nothing where the rule does not hold.
    #[test]
    fn a_rule_of_some_modes_dims_only_where_they_cover_the_view() {
        let (mut app, dir, user) = sample_app("grey_family", Some(grey_stub));
        put(&mut app, 0, LIVE_MODE, 0);
        let zoom = by(&app, "global:0x02ff");
        put(&mut app, 0, 584, 4);
        let g = app.grey(&zoom, 0, Some("S&Q"));
        assert!(!g.dim && g.note.is_none() && app.grey_lines(&zoom, 0, Some("S&Q")).is_empty(), "60fps: the rule does not hold");
        put(&mut app, 0, 584, 2);
        let g = app.grey(&zoom, 0, Some("S&Q"));
        assert!(!g.dim && g.note.as_deref() == Some("greyed while S&Q Frame Rate = 120fps, in S&Q"), "{:?}", g.note);
        let g = app.grey(&zoom, 0, Some("Still"));
        assert!(!g.dim && g.note.is_none(), "the Still menu: as usual");
        put(&mut app, 7, 584, 2);
        assert!(app.grey(&zoom, 7, Some("S&Q")).dim, "an S&Q memory edited: dimmed");
        let lines = app.grey_lines(&zoom, 0, Some("S&Q"));
        assert_eq!(lines.iter().map(|l| l.text.as_str()).collect::<Vec<_>>(), ["Greyed out on the camera while S&Q Frame Rate = 120fps, in S&Q only."]);
        assert_eq!(lines[0].activate.as_ref().map(|a| (a.0, a.1)), Some((584, 4)));
        assert!(app.cell_editable(Col::a(0), std::slice::from_ref(&zoom)), "still editable");
        done(&dir, &user);
    }

    /// `inactive_if` with `hdmi_device`: never dimmed, in any view; where the rule holds the row says it is greyed with an
    /// HDMI device connected, and the detail says when, with Activate and that the cable is the owner's.
    #[test]
    fn an_hdmi_device_rule_never_dims_and_says_so() {
        let (mut app, dir, user) = sample_app("grey_hdmi", Some(grey_stub));
        let touch = by(&app, "global:0x0476");
        put(&mut app, 0, 1180, 0);
        for m in ["Still", "Movie", "S&Q"] {
            let g = app.grey(&touch, 0, Some(m));
            assert!(!g.dim && g.note.as_deref() == Some("greyed with an HDMI device connected"), "{m}");
        }
        let lines = app.grey_lines(&touch, 0, Some("Still"));
        assert_eq!(lines.iter().map(|l| l.text.as_str()).collect::<Vec<_>>(), ["Greyed out on the camera while HDMI Info. Display = On and a device is connected to the HDMI socket."]);
        assert!(lines[0].activate.as_ref().is_some_and(|a| a.0 == 1180 && a.1 == 1) && lines[0].cable.is_some());
        put(&mut app, 0, 1180, 1);
        assert!(app.grey(&touch, 0, Some("Still")).note.is_none() && app.grey_lines(&touch, 0, Some("Still")).is_empty(), "HDMI Info. Display Off");
        done(&dir, &user);
    }

    /// The reviewer's finding: a setting with both rules where only `inactive_if`'s holds: the window's Activate, the
    /// page's button and the page's request all set `inactive_if`'s record, never `inactive_when`'s; where
    /// `inactive_when`'s holds, its own; with neither holding the request is refused in plain words. Where the rule's
    /// modes are none of the view's (the Still menu, for a rule of S&Q only), the line stays and no Activate is offered:
    /// the window says why, the page's row too, and the page's request is refused.
    #[test]
    fn activate_sets_the_rule_that_holds_and_none_where_it_changes_nothing() {
        use crate::web::tests::answer;
        let (mut app, dir, user) = sample_app("grey_activate", Some(grey_stub));
        for s in app.schema.settings.iter_mut().filter(|s| s.key == "global:0x02ff") {
            s.inactive_when = serde_json::from_value(serde_json::json!({ "record": 1180, "name": "HDMI Info. Display", "values": [0], "unlock": 1, "unlock_label": "Off" })).unwrap();
        }
        app.schema_gen += 1;
        put(&mut app, 0, LIVE_MODE, 0);
        put(&mut app, 0, 1180, 1);
        put(&mut app, 0, 584, 2);
        let zoom = by(&app, "global:0x02ff");
        let value = |app: &App, id: u16| app.doc.as_ref().unwrap().value(0, (id, None));
        let row = |app: &mut App, menu: &str| -> serde_json::Value {
            let j: serde_json::Value = serde_json::from_slice(&answer(app, "tab", serde_json::json!({ "target": 0, "tab": "Shooting", "menu": menu })).body).unwrap();
            j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().iter()).find(|r| r["key"] == "global:0x02ff").cloned().unwrap()
        };
        let press = |app: &mut App, menu: &str| answer(app, "activate", serde_json::json!({ "target": 0, "key": "global:0x02ff", "menu": menu }));
        // only inactive_if's rule holds (S&Q Frame Rate 120fps, HDMI Info. Display Off)
        assert_eq!(app.activate_rule(&zoom, 0, Some("S&Q")).map(|a| (a.0, a.1)), Some((584, 4)), "the window's switch");
        assert_eq!(row(&mut app, "S&Q")["inactive"]["unlock"], "Activate (set S&Q Frame Rate to 60fps)", "the page's button");
        assert_eq!(press(&mut app, "S&Q").status, 200);
        assert_eq!((value(&app, 584), value(&app, 1180)), (Some(4), Some(1)), "S&Q Frame Rate set, HDMI Info. Display left");
        let refused = press(&mut app, "S&Q");
        assert!(refused.status == 409 && String::from_utf8_lossy(&refused.body).contains("Nothing to activate here"), "neither holds now: refused");
        // inactive_when's holds: its own switch
        put(&mut app, 0, 1180, 0);
        assert_eq!(app.activate_rule(&zoom, 0, Some("S&Q")).map(|a| (a.0, a.1)), Some((1180, 1)));
        put(&mut app, 0, 1180, 1);
        // the Still menu, the rule of S&Q only holding: the line stays, no Activate, and why
        put(&mut app, 0, 584, 2);
        let lines = app.grey_lines(&zoom, 0, Some("Still"));
        assert!(lines.iter().any(|l| l.text.ends_with("in S&Q only.") && l.activate.is_none() && l.muted.as_deref().is_some_and(|m| m.starts_with("Nothing to activate in this menu"))));
        assert!(app.activate_rule(&zoom, 0, Some("Still")).is_none());
        let r = row(&mut app, "Still");
        assert!(r["inactive"]["unlock"].is_null() && r["inactive"]["muted"].as_str().is_some(), "{}", r["inactive"]);
        assert_eq!(press(&mut app, "Still").status, 409);
        assert_eq!(value(&app, 584), Some(2), "nothing changed");
        done(&dir, &user);
    }

    /// The page says what the window says: a row's dim and note, the detail's words and Activate (which the page's
    /// activate takes for `inactive_if`); the window's third column and its search list draw the note.
    #[test]
    fn the_page_the_menu_and_the_search_list_say_the_same() {
        use crate::web::tests::answer;
        let (mut app, dir, user) = sample_app("grey_page", Some(grey_stub));
        put(&mut app, 0, LIVE_MODE, 0);
        put(&mut app, 0, 584, 2);
        put(&mut app, 0, 1180, 0);
        let j: serde_json::Value = serde_json::from_slice(&answer(&mut app, "tab", serde_json::json!({ "target": 0, "tab": "Shooting", "menu": "S&Q" })).body).unwrap();
        let row = |k: &str| j["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().iter()).find(|r| r["key"] == k).cloned().unwrap_or_else(|| panic!("{k}"));
        let (tc, audio, zoom) = (row("global:0x02f4"), row("global:0x02e9"), row("global:0x02ff"));
        assert_eq!((tc["dim"].as_bool(), tc["grey_note"].as_str()), (Some(false), Some("grey in S&Q")));
        assert_eq!(audio["dim"], true);
        assert_eq!(audio["grey_in"], "The camera greys this out in S&Q and Time-lapse.");
        assert_eq!(zoom["inactive"]["text"], "Greyed out on the camera while S&Q Frame Rate = 120fps, in S&Q only.");
        assert!(zoom["inactive"]["unlock"].as_str().is_some() && zoom["editable"] == true);
        let k: serde_json::Value = serde_json::from_slice(&answer(&mut app, "tab", serde_json::json!({ "target": 0, "tab": "Setup", "menu": "Still" })).body).unwrap();
        let touch = k["groups"].as_array().unwrap().iter().flat_map(|g| g["rows"].as_array().unwrap().iter()).find(|r| r["key"] == "global:0x0476").cloned().unwrap();
        assert_eq!((touch["dim"].as_bool(), touch["grey_note"].as_str()), (Some(false), Some("greyed with an HDMI device connected")));
        assert!(touch["inactive"]["cable"].as_str().is_some_and(|c| c.contains("HDMI")));
        assert_eq!(answer(&mut app, "activate", serde_json::json!({ "target": 0, "key": "global:0x02ff", "menu": "S&Q" })).status, 200);
        assert_eq!(app.doc.as_ref().unwrap().value(0, (584, None)), Some(4), "the page's Activate set S&Q Frame Rate to 60fps");
        // the window: the third column and the search list draw the note
        app.set_menu("S&Q");
        app.select(Some(View::Tab("Shooting".into())), Some("TC/UB".into()), None);
        let texts = |app: &mut App| {
            let ctx = egui::Context::default();
            let mut frame = eframe::Frame::_new_kittest();
            let _ = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
            let out = ctx.run(egui::RawInput::default(), |ctx| eframe::App::update(app, ctx, &mut frame));
            crate::test_support::texts(&out.shapes)
        };
        assert!(texts(&mut app).iter().any(|t| t == "grey in S&Q"), "the third column");
        (app.view, app.search) = (View::Search, "Time Code Run".into());
        assert!(texts(&mut app).iter().any(|t| t == "grey in S&Q"), "the search list");
        done(&dir, &user);
    }
}
