//! The welcome page, and the Main page: the camera's own Main page tiles for the set edited.

use crate::*;

/// A Main tile whose live value the file does not hold (the shutter speed and aperture set on the dials), and why.
pub(crate) const ON_CAMERA: &str = "on the camera";

const ON_CAMERA_HOVER: &str = "The live settings in the file do not hold this value: it is set on the camera. The memories keep the value they were registered with.";

impl App {
    /// Whether a tile showing setting `s` alone changes it in place in set `target`, the window's tile and the page's
    /// alike (with editing on): a number with its range or two named values or more, held by the file in the shape it
    /// was mapped in, and not view only outside Expert mode (`locked_why`).
    pub(crate) fn tile_changes_in_place(&self, s: &Setting, target: usize) -> bool {
        s.scalar && self.doc.as_ref().is_some_and(|d| d.value(target, s.slot()).is_some()) && self.shape_ok_in(s, target)
            && !self.locked(s, target) && (s.range.is_some() || s.values.len() >= 2)
    }

    /// The camera's Main page: a grid of tiles with the key settings (stills or movie), and the
    /// same settings below as rows to edit and compare. Values follow the set being edited.
    /// One large clickable card of the welcome screen; true when clicked.
    fn welcome_card(ui: &mut egui::Ui, title: &str, sub: &str) -> bool {
        let id = ui.id().with(("welcome_card", title));
        let hovered = ui.ctx().data(|d| d.get_temp::<bool>(id)).unwrap_or(false);
        // a little darker under the pointer, and its quiet line still readable on it
        let fill = if hovered { tone::boxed(ui.visuals()) } else { tone::raised(ui.visuals()) };
        let resp = egui::Frame::new().fill(fill).corner_radius(6).inner_margin(egui::Margin::same(16)).show(ui, |ui| {
            ui.set_min_size(egui::vec2(260.0, 120.0));
            ui.set_max_width(260.0);
            ui.vertical(|ui| {
                ui.add(egui::Label::new(RichText::new(title).size(20.0).strong()).selectable(false));
                ui.add_space(8.0);
                ui.add(egui::Label::new(RichText::new(sub).color(tone::weak(ui.visuals()))).selectable(false).wrap());
            });
        }).response.interact(egui::Sense::click());
        // named by its words, without the symbol in front
        let resp = as_button(resp, title.trim_start_matches(|c: char| !c.is_alphanumeric()));
        ui.ctx().data_mut(|d| d.insert_temp(id, resp.hovered()));
        if resp.hovered() { ui.ctx().set_cursor_icon(egui::CursorIcon::PointingHand); }
        resp.clicked()
    }

    /// What the window shows before any file is open: the three ways in, the supported models, recent files.
    pub(crate) fn welcome_view(&mut self, ui: &mut egui::Ui) {
        ui.add_space(40.0);
        egui::Frame::new().inner_margin(egui::Margin::symmetric(40, 0)).show(ui, |ui| {
            ui.heading(RichText::new("Camset Editor").size(30.0).strong());
            ui.add_space(6.0);
            ui.label(RichText::new("See and change your Sony camera's settings in plain words, compare setups, and write them back to the camera.").size(15.0));
            ui.add_space(24.0);
            let (mut read, mut open, mut sample) = (false, false, false);
            let helper = self.have_helper();
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 16.0;
                ui.spacing_mut().item_spacing.y = 16.0;
                // the camera the read goes to, when the editor knows it: "Studio a1 II over the network"
                let read_sub = if helper { self.read_sub() } else { "Reading the camera needs an extra program you set up once. Click to see how.".to_string() };
                let open_sub = self.open_hint();
                // without the camera link program, files come first: that is what works
                if helper { read = Self::welcome_card(ui, "⬇ Read from camera", &read_sub); }
                open = Self::welcome_card(ui, "📂 Open a settings file", &open_sub);
                if !helper { read = Self::welcome_card(ui, "⬇ Read from camera", &read_sub); }
                // offered when a definition names a sample that is there (`camera.sample`)
                if !self.defs.samples().is_empty() {
                    sample = Self::welcome_card(ui, "✨ Explore a sample", "Look around with a sample camera, no setup needed.");
                }
            });
            if read {
                if !helper || self.prefs.link.is_empty() { self.show_connect = true; } else { self.start_camera_job(None); }
            }
            if open {
                self.ask(ui.ctx(), DialogKind::OpenA, None);
            }
            if sample { self.open_sample(); }
            ui.add_space(20.0);
            let models = self.defs.works_with();
            if !models.is_empty() {
                ui.label(RichText::new(format!("Works with: {}", models.join(", "))).color(tone::weak(ui.visuals())));
                ui.label(RichText::new(NOT_SONY).small().color(tone::weak(ui.visuals())));
            }
            // which editor this is, in full (the status bar gives it short; About has the rest)
            ui.label(RichText::new(format!("Version {}", version_words())).small().color(tone::weak(ui.visuals())));
            if self.defs.shipped_dir.is_none() {
                let looked: Vec<String> = self.defs.looked_in.iter().map(|d| shown_path(d)).collect();
                ui.label(RichText::new("The camera definitions that come with the editor were not found, so no settings file can be read yet. Reinstall the editor, or add a definition in ⚙ Settings > Camera support & web page.").color(tone::bad(ui.visuals())))
                    .on_hover_text(format!("Looked in:\n{}", looked.join("\n")));
            }
            if !self.prefs.recent.is_empty() {
                ui.add_space(24.0);
                ui.label(RichText::new("Recent files").strong());
                ui.add_space(4.0);
                let mut pick: Option<String> = None;
                for r in &self.prefs.recent {
                    let name = Path::new(r).file_name().unwrap_or_default().to_string_lossy().to_string();
                    if ui.link(name).on_hover_text(r).clicked() { pick = Some(r.clone()); }
                }
                if let Some(r) = pick { self.open(PathBuf::from(r)); }
            }
        });
    }

    pub(crate) fn main_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        ui.horizontal(|ui| {
            ui.heading(self.schema.camera.text.main_title());
            ui.add_space(12.0);
            let names: Vec<String> = self.schema.camera.main_tiles.as_ref().map(|t| t.0.iter().map(|s| s.name.clone()).collect()).unwrap_or_default();
            for (i, n) in names.iter().enumerate() {
                ui.selectable_value(&mut self.main_set, i, n);
            }
        });
        ui.add_space(6.0);
        let tiles: Vec<Tile> = match &self.schema.camera.main_tiles {
            Some(t) => t.0.get(self.main_set).or_else(|| t.0.first()).map(|s| s.tiles.clone()).unwrap_or_default(),
            None => Vec::new(),
        };
        if tiles.is_empty() {
            ui.label("This camera's definition has no Main page tiles. The settings are in the tabs on the left.");
            return actions;
        }
        let Some(doc) = &self.doc else {
            ui.label("Open a settings file to see its values.");
            return actions;
        };
        let target = self.target;
        let foreign = self.foreign_model(&doc.edited).is_some();
        // tiles
        let mut pick = None;
        let editable_doc = self.editable();
        egui::Grid::new(("main_tiles", self.main_set)).spacing([6.0, 6.0]).show(ui, |ui| {
            for (n, tile) in tiles.iter().enumerate() {
                let caption = tile.caption.as_str();
                let text = self.tile_text(doc, target, tile);
                let on_camera = text == Self::live_text(tile);
                let settings = self.tile_settings(tile);
                let changed = settings.iter().any(|s| self.changed(s));
                // a tile with one plain setting (a list of values or a number) can be edited in place
                let single = match settings.as_slice() {
                    [s] if editable_doc && self.tile_changes_in_place(s, target) => Some(s.clone()),
                    _ => None,
                };
                let selected = self.main_focus.as_deref() == Some(caption);
                let spoken = format!("{caption}: {text}{}", if changed { ", edited" } else { "" });
                let v = ui.visuals().clone();
                let fill = if selected { tone::chosen(&v) } else { tone::raised(&v) };
                let ink = if selected { tone::chosen_text(&v) } else { v.text_color() };
                let weak = if selected { tone::chosen_text(&v) } else { tone::weak(&v) };
                // another camera's values are greyed out, as everywhere
                let greyed = if selected { tone::chosen_text(&v) } else { v.weak_text_color() };
                let resp = egui::Frame::new().fill(fill).corner_radius(4.0).inner_margin(egui::Margin::symmetric(10, 6)).show(ui, |ui| {
                    ui.set_min_size(egui::vec2(150.0, 54.0));
                    ui.set_max_width(150.0);
                    ui.vertical(|ui| {
                        let cap = if changed {
                            let mut job = egui::text::LayoutJob::default();
                            let small = egui::TextStyle::Small.resolve(ui.style());
                            job.append(caption, 0.0, egui::TextFormat::simple(small.clone(), weak));
                            job.append(&format!("  {EDIT_MARK} edited"), 0.0, egui::TextFormat::simple(small, tone::edit(&v)));
                            egui::Label::new(job)
                        } else {
                            egui::Label::new(RichText::new(caption).small().color(weak))
                        };
                        ui.add(cap.truncate());
                        let mut t = RichText::new(text).size(18.0).strong().color(if foreign { greyed } else { ink });
                        if changed && !selected { t = t.color(tone::edit(&v)); }
                        ui.add(egui::Label::new(t).truncate());
                    });
                }).response.interact(egui::Sense::click());
                let resp = as_button(resp, &spoken);
                let resp = if on_camera { resp.on_hover_text(ON_CAMERA_HOVER) } else { resp };
                // a number with no name yet says why on hover, and a value the camera keeps in more than one record what
                // changing it changes (`copy_note`)
                let why: Vec<String> = settings.iter().filter_map(|s| self.unnamed_why(s, doc.value(target, s.slot())))
                    .chain(settings.iter().filter_map(|s| self.copy_note(s, target).map(|(w, _)| w))).collect();
                let resp = if why.is_empty() { resp } else { resp.on_hover_text(why.join("\n\n")) };
                if resp.clicked() { pick = Some(caption.to_string()); }
                if let Some(s) = single {
                    // edit hint in the top-right corner, painted over the tile so its size stays the same
                    // a small down-pointing triangle (drawn, since the small font has no "▾" glyph)
                    let c = resp.rect.right_top() + egui::vec2(-10.0, 9.0);
                    ui.painter().add(egui::Shape::convex_polygon(
                        vec![c + egui::vec2(-4.0, -2.0), c + egui::vec2(4.0, -2.0), c + egui::vec2(0.0, 3.0)],
                        tone::weak(ui.visuals()), egui::Stroke::NONE));
                    let resp = resp.on_hover_cursor(egui::CursorIcon::PointingHand);
                    let id = ui.make_persistent_id(("tile_pop", caption));
                    let cur = doc.value(target, s.slot());
                    if resp.clicked() {
                        ui.memory_mut(|m| m.toggle_popup(id));
                        if let Some(v) = cur { ui.data_mut(|d| d.insert_temp(id.with("num"), v)); }
                    }
                    let mut set_to: Option<i64> = None;
                    // a number box needs clicks inside the popup, so only close it on clicks outside
                    let close = if s.range.is_some() { egui::PopupCloseBehavior::CloseOnClickOutside } else { egui::PopupCloseBehavior::CloseOnClick };
                    egui::popup_below_widget(ui, id, &resp, close, |ui| {
                        ui.set_min_width(220.0);
                        ui.label(RichText::new(caption).small().color(tone::weak(ui.visuals())));
                        // a value the camera keeps in more than one record: what a choice here changes, before it is made
                        if let Some((note, hover)) = self.copy_note(&s, target) {
                            ui.set_max_width(320.0);
                            ui.add(egui::Label::new(RichText::new(note).small().color(tone::note(ui.visuals()))).wrap()).on_hover_text(hover);
                        }
                        if let Some((lo, hi)) = s.range {
                            let step = s.step.unwrap_or(1).max(1);
                            let mut v = ui.data(|d| d.get_temp::<i64>(id.with("num"))).or(cur).unwrap_or(lo);
                            ui.horizontal(|ui| {
                                named(ui.add(number_box(&s, &mut v, lo, hi, step)), caption);
                                let snapped = snap_to_step(v, lo, hi, step);
                                if ui.button("OK").clicked() {
                                    if Some(snapped) != cur { set_to = Some(snapped); }
                                    ui.memory_mut(|m| m.close_popup());
                                }
                            });
                            ui.data_mut(|d| d.insert_temp(id.with("num"), v));
                        } else {
                            for (v, label) in self.offered_values(&s, target) {
                                if ui.selectable_label(cur == Some(v), label).clicked() && cur != Some(v) {
                                    set_to = Some(v);
                                }
                            }
                        }
                    });
                    if let Some(v) = set_to { actions.push(Action::Set(target, s.slot(), v)); }
                }
                if (n + 1) % 4 == 0 { ui.end_row(); }
            }
        });
        if pick.is_some() { self.main_focus = pick; }
        ui.add_space(10.0);
        ui.separator();
        ui.label(RichText::new("All Main settings").strong());
        ui.add_space(4.0);
        let editable = self.editable();
        egui::Grid::new(("main_rows", self.main_set, target)).striped(true).num_columns(3).spacing([18.0, 4.0]).show(ui, |ui| {
            for tile in tiles.iter() {
                let caption = tile.caption.as_str();
                for s in self.tile_settings(tile) {
                    // several settings under one tile: show each one's own name, without repeating the tile's
                    let label = if self.tile_settings(tile).len() > 1 {
                        let n = s.name.trim_start_matches(&format!("{caption}: ")).replace(&format!(" ({caption})"), "");
                        if n.to_lowercase().starts_with(&caption.to_lowercase()) { n } else { format!("{caption} – {n}") }
                    } else {
                        caption.to_string()
                    };
                    let edited = self.changed(&s);
                    let mut name = RichText::new(if edited { format!("{EDIT_MARK} {label}") } else { label });
                    if edited { name = name.color(tone::edit(ui.visuals())); }
                    if self.main_focus.as_deref() == Some(caption) { name = name.strong().underline(); }
                    ui.label(name).on_hover_text(self.where_kept(&s));
                    self.compact_editor(ui, &s, editable, &mut actions);
                    if self.changed(&s) && ui.small_button("Revert").clicked() {
                        actions.push(Action::Revert(target, s.slot()));
                    } else {
                        ui.label("");
                    }
                    ui.end_row();
                }
            }
        });
        actions
    }

    /// A setting's hover in the lists: its full name and whether the memories keep it; the record number in
    /// Expert mode only.
    pub(crate) fn where_kept(&self, s: &Setting) -> String {
        let kept = if s.in_sets { "Live settings and memories" } else { "Live settings only; memories don't keep it" };
        if self.prefs.expert { format!("{}\n{kept} · record 0x{:04x}", s.name, s.id) } else { format!("{}\n{kept}", s.name) }
    }

    /// Settings a tile shows (the memory-only ones only when a memory set is being edited).
    fn tile_settings(&self, tile: &Tile) -> Vec<Setting> {
        let keys = tile.keys_for(self.target);
        keys.iter().filter_map(|k| self.schema.settings.iter().find(|s| s.key == *k).cloned()).collect()
    }

    /// What a tile shows where the live settings hold no value for it: the definition's words (`live_text`), else
    /// "on the camera".
    pub(crate) fn live_text(tile: &Tile) -> &str {
        if tile.live_text.is_empty() { ON_CAMERA } else { &tile.live_text }
    }

    pub(crate) fn tile_text(&self, doc: &Doc, target: usize, tile: &Tile) -> String {
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
        let ss = self.tile_settings(tile);
        if ss.is_empty() {
            return Self::live_text(tile).into();
        }
        ss.iter().map(|s| self.row_value(s)).collect::<Vec<_>>().join(" · ")
    }
}
