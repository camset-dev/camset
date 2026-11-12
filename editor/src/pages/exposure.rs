//! The exposure page: the three sides of the exposure triangle (aperture, shutter, ISO) for the
//! live settings and each dial memory, on aligned stop scales, with who sets each side in that
//! column's exposure mode and the limits on what the camera may choose. What is stored where and
//! who sets what in each mode comes from the camera definition (camera.exposure); the editor itself
//! only knows the physics (camset_editor::stops). The web page draws the same page from the same
//! helpers (`web_exposure` in web/mod.rs), so the words and the numbers have one source.

use crate::*;
use camset_editor::schema::{Control, Exposure, ExposureLimit, ExposureSide};
use camset_editor::stops::{self, Side};

/// A stop scale's size at most; it narrows with its column.
const STRIP: egui::Vec2 = egui::vec2(210.0, 30.0);
/// A column's width at most, and at least (narrower windows scroll sideways).
const CELL_W: f32 = 250.0;
const CELL_MIN: f32 = 150.0;
/// The row names' column (the names wrap in it).
const NAME_W: f32 = 120.0;
const GAP: f32 = 18.0;

/// What you set: the strongest text colour of the theme in use.
fn you(v: &egui::Visuals) -> Color32 {
    v.strong_text_color()
}

/// What the page says under its heading.
pub(crate) const INTRO: &str = "Aperture, shutter speed and ISO on aligned scales: each tick is one stop, which halves or doubles the light. A filled dot is a value you set, a ring one the camera sets (a memory keeps the one stored when it was registered), and the shaded band is where the camera may take it.";
/// The three sides as the page names them, in its order.
pub(crate) const SIDES: [(Side, &str); 3] = [(Side::Aperture, "Aperture"), (Side::Shutter, "Shutter speed"), (Side::Iso, "ISO")];
/// What each side does to the picture, for the "What decides …" lists.
pub(crate) const EFFECTS: [(Side, &str, &str); 3] = [
    (Side::Aperture, "the aperture", "A smaller F-number lets in more light and blurs what is in front of and behind the focus more; a larger one keeps more of the scene sharp."),
    (Side::Shutter, "the shutter speed", "A faster speed freezes movement; a slower one lets in more light but blurs movement and camera shake."),
    (Side::Iso, "ISO", "A higher ISO brightens the picture after the light is captured, and adds noise."),
];
/// The hover text of "Exposes for".
pub(crate) const EV_HOVER: &str = "The scene brightness these three together expose correctly for (EV100): about 15 for direct sun, 12 for overcast, 8 for a bright room.";

/// Who sets one side of the triangle in one column.
#[derive(Clone, Copy, PartialEq)]
pub(crate) enum Who {
    You,
    Camera,
    Unknown,
}

impl Who {
    /// The web page's name for it.
    pub(crate) fn word(self) -> &'static str {
        match self { Who::You => "you", Who::Camera => "camera", Who::Unknown => "unknown" }
    }

    /// The chip beside a value: the scale's marker shape and a word as well as colour (a filled
    /// dot: you set it; a ring: the camera does). Drawn, not a glyph: the font has no filled dot.
    fn chip(self, ui: &mut egui::Ui) {
        let (rect, _) = ui.allocate_exact_size(egui::vec2(10.0, 10.0), egui::Sense::hover());
        let (c, r) = (rect.center(), 4.0);
        let weak = ui.visuals().weak_text_color();
        let (you, camera) = (you(ui.visuals()), tone::camera(ui.visuals()));
        match self {
            Who::You => { ui.painter().circle_filled(c, r, you); ui.label(RichText::new("you set it").color(you).small()); }
            Who::Camera => { ui.painter().circle_stroke(c, r, egui::Stroke::new(1.5_f32, camera)); ui.label(RichText::new("the camera sets it").color(camera).small()); }
            Who::Unknown => { ui.painter().circle_stroke(c, r, egui::Stroke::new(1.0_f32, weak)); ui.label(RichText::new("not known").color(tone::weak(ui.visuals())).small()); }
        }
    }
}

/// One side in one column, ready to draw.
pub(crate) struct Cell {
    pub(crate) who: Who,
    /// The value as the camera names it, or why there is none.
    pub(crate) text: String,
    /// The value in stops, when it has one.
    pub(crate) at: Option<f64>,
    /// Where the camera may take it: the limits in force, intersected (stops).
    pub(crate) band: Option<(f64, f64)>,
    /// A one-sided limit (ISO AUTO Min. SS): its stops and how it reads ("slowest").
    pub(crate) bound: Option<(f64, String)>,
    /// The limits in force, in words.
    pub(crate) notes: Vec<String>,
}

impl App {
    pub(super) fn ex_setting(&self, key: &str) -> Option<&Setting> {
        if key.is_empty() { None } else { self.schema.settings.iter().find(|s| s.key == key) }
    }

    /// A setting's value in a section of file A, with its label.
    pub(super) fn ex_value(&self, section: usize, key: &str) -> Option<(i64, String)> {
        let s = self.ex_setting(key)?;
        let v = self.col_value(Col::a(section), s)?;
        Some((v, Self::describe(s, Some(v))))
    }

    /// " (not proved yet)" when any of the records has not been proved on the camera, and the proof lines are shown.
    fn ex_unproved(&self, keys: &[&str]) -> &'static str {
        if self.shows_proof() && keys.iter().any(|k| self.ex_setting(k).is_some_and(|s| s.proved.is_none())) { " (not proved on the camera yet)" } else { "" }
    }

    /// The scale a side is drawn on: the lowest and highest stops among a record's value labels,
    /// with those labels.
    pub(crate) fn ex_scale(&self, side: Side, key: &str) -> Option<((f64, String), (f64, String))> {
        let s = self.ex_setting(key)?;
        let st: Vec<(f64, String)> = s.values.iter().filter_map(|(_, l)| stops::stops(side, l).map(|x| (x, l.clone()))).collect();
        let lo = st.iter().min_by(|a, b| a.0.total_cmp(&b.0))?.clone();
        let hi = st.iter().max_by(|a, b| a.0.total_cmp(&b.0))?.clone();
        (lo.0 < hi.0).then_some((lo, hi))
    }

    pub(crate) fn ex_mode(&self, ex: &Exposure, section: usize) -> Option<String> {
        self.ex_value(section, if section == 0 { &ex.mode_key } else { &ex.memory_mode_key }).map(|(_, l)| l)
    }

    pub(crate) fn ex_side(ex: &Exposure, side: Side) -> &ExposureSide {
        match side { Side::Aperture => &ex.aperture, Side::Shutter => &ex.shutter, Side::Iso => &ex.iso }
    }

    fn ex_applies(l: &ExposureLimit, who: Who, iso_who: Who) -> bool {
        match l.applies.as_str() {
            "camera" => who == Who::Camera,
            "camera_iso_auto" => who == Who::Camera && iso_who == Who::Camera,
            _ => true,
        }
    }

    pub(super) fn ex_cell(&self, ex: &Exposure, section: usize, side: Side, mode: Option<&str>, iso_who: Who) -> Cell {
        let def = Self::ex_side(ex, side);
        let key = if section == 0 || def.memory_key.is_empty() && def.memory_numerator_key.is_empty() { &def.key } else { &def.memory_key };
        let mut value = self.ex_value(section, key);
        let mut at = value.as_ref().and_then(|(_, l)| stops::stops(side, l));
        if section != 0 && value.is_none() && !def.memory_numerator_key.is_empty() {
            if let (Some((n, _)), Some((d, _))) = (self.ex_value(section, &def.memory_numerator_key), self.ex_value(section, &def.memory_denominator_key)) {
                at = stops::fraction_stops(n, d);
                value = Some((n, if d > 1 { format!("{n}/{d}") } else { format!("{n}\"") }));
            }
        }
        let who = match side {
            // the mode's own word when the definition gives one (`control.<mode>.iso`), else the camera while ISO holds
            // its AUTO value
            Side::Iso => match (mode.and_then(|m| ex.control.get(m)).map(|c| c.iso.as_str()).filter(|w| !w.is_empty()), def.auto_value, &value) {
                (Some("you"), _, _) => Who::You,
                (Some("camera"), _, _) => Who::Camera,
                (_, Some(a), Some((v, _))) if *v == a => Who::Camera,
                (_, _, Some(_)) => Who::You,
                _ => Who::Unknown,
            },
            _ => match mode.and_then(|m| ex.control.get(m)).map(|c| if side == Side::Aperture { c.aperture.as_str() } else { c.shutter.as_str() }) {
                Some("you") => Who::You,
                Some("camera") => Who::Camera,
                _ => Who::Unknown,
            },
        };
        let text = match &value {
            Some((_, l)) => l.clone(),
            // the definition's words for why the live settings hold none (`live_note`)
            None if key.is_empty() => if def.live_note.is_empty() { "not in the file".into() } else { def.live_note.clone() },
            None => "—".into(),
        };
        let (mut band, mut bound, mut notes) = (None::<(f64, f64)>, None, Vec::new());
        for l in def.limits.iter().filter(|l| Self::ex_applies(l, who, iso_who)) {
            if !l.min_key.is_empty() {
                let (Some((_, a)), Some((_, b))) = (self.ex_value(section, &l.min_key), self.ex_value(section, &l.max_key)) else { continue };
                notes.push(format!("{}: {a} to {b}{}", l.name, self.ex_unproved(&[&l.min_key, &l.max_key])));
                if let (Some(x), Some(y)) = (stops::stops(side, &a), stops::stops(side, &b)) {
                    let (x, y) = (x.min(y), x.max(y));
                    band = Some(band.map_or((x, y), |(p, q)| (p.max(x), q.min(y))));
                }
            } else if let Some((_, lab)) = self.ex_value(section, &l.key) {
                notes.push(format!("{}: {lab}{}", l.name, self.ex_unproved(&[&l.key])));
                if let Some(x) = stops::stops(side, &lab) {
                    bound = Some((x, l.bound.clone()));
                }
            }
        }
        Cell { who, text, at, band: band.filter(|(p, q)| p <= q), bound, notes }
    }

    /// The page's heading.
    pub(crate) fn ex_title(ex: &Exposure) -> &str {
        if ex.title.is_empty() { "Exposure" } else { &ex.title }
    }

    /// The page's columns: the definition's, else the live settings and each dial memory.
    pub(crate) fn ex_sections(&self) -> Vec<usize> {
        let n = self.n_sections();
        match self.schema.camera.exposure.as_ref().map(|e| &e.sections).filter(|s| !s.is_empty()) {
            // the definition's columns (`exposure.sections`), those the file holds
            Some(s) => s.iter().copied().filter(|&x| x < n).collect(),
            None => std::iter::once(0).chain(self.dial_sets()).collect(),
        }
    }

    /// Each column's three sides, in the order of `SIDES`. ISO is worked out first: a limit on
    /// the shutter can hold only while the camera sets ISO.
    pub(crate) fn ex_cells(&self, ex: &Exposure, sections: &[usize], modes: &[Option<String>]) -> Vec<Vec<Cell>> {
        sections.iter().zip(modes).map(|(&sec, mode)| {
            let iso = self.ex_cell(ex, sec, Side::Iso, mode.as_deref(), Who::Unknown);
            let iso_who = iso.who;
            vec![self.ex_cell(ex, sec, Side::Aperture, mode.as_deref(), iso_who), self.ex_cell(ex, sec, Side::Shutter, mode.as_deref(), iso_who), iso]
        }).collect()
    }

    /// Who sets the aperture and the shutter speed in an exposure mode, in a sentence.
    pub(crate) fn ex_control(c: &Control) -> String {
        let mine: Vec<&str> = [("aperture", &c.aperture), ("shutter speed", &c.shutter)].iter().filter(|(_, w)| w.as_str() == "you").map(|(n, _)| *n).collect();
        let theirs: Vec<&str> = [("aperture", &c.aperture), ("shutter speed", &c.shutter)].iter().filter(|(_, w)| w.as_str() == "camera").map(|(n, _)| *n).collect();
        let mut t = String::new();
        if !mine.is_empty() { t += &format!("You set the {}. ", mine.join(" and ")); }
        if !theirs.is_empty() { t += &format!("The camera sets the {}.", theirs.join(" and ")); }
        t.trim().to_string()
    }

    /// The hover text of a side's scale: the value in stops, the limits in force, and the bar.
    pub(crate) fn ex_hover(name: &str, c: &Cell) -> String {
        let mut hover = format!("{name}: {}", c.text);
        if let Some(s) = c.at { hover += &format!(" ({s:+.1} stops)"); }
        for n in &c.notes { hover += &format!("\n{n}"); }
        if let Some((_, how)) = &c.bound { if !how.is_empty() { hover += &format!("\nthe bar: the {how} the camera goes"); } }
        hover
    }

    /// Exposure compensation in a column, with its step.
    pub(crate) fn ex_comp(&self, ex: &Exposure, section: usize) -> String {
        let comp = self.ex_value(section, &ex.comp_key).map(|(_, l)| l).unwrap_or_else(|| "—".into());
        let step = self.ex_value(section, &ex.step_key).map(|(_, l)| format!(", steps of {l}")).unwrap_or_default();
        format!("{comp}{step}")
    }

    /// What exposure compensation does in a column: it depends on whether the camera sets a side.
    pub(crate) fn ex_comp_note(row: &[Cell]) -> &'static str {
        if row.iter().any(|c| c.who == Who::Camera) { "Shifts what the camera chooses." } else { "No effect on the picture while you set all three; it shifts the exposure meter's zero." }
    }

    /// The scene brightness a column exposes for (EV100), when you set all three sides.
    pub(crate) fn ex_exposes(row: &[Cell]) -> Option<f64> {
        match (row[0].at, row[1].at, row[2].at) {
            (Some(av), Some(tv), Some(sv)) if row.iter().all(|c| c.who == Who::You) => Some(stops::ev100(av, tv, sv)),
            _ => None,
        }
    }

    /// The settings that decide one side: where it is stored, its limits and (the aperture and the
    /// shutter) the exposure mode, each once, in that order.
    pub(crate) fn ex_decides(&self, ex: &Exposure, side: Side) -> Vec<Setting> {
        let def = Self::ex_side(ex, side);
        let mut keys: Vec<&str> = vec![&def.key, &def.memory_key, &def.memory_numerator_key, &def.memory_denominator_key];
        for l in &def.limits { keys.extend([l.min_key.as_str(), l.max_key.as_str(), l.key.as_str()]); }
        if side != Side::Iso { keys.push(&ex.mode_key); keys.push(&ex.memory_mode_key); }
        let mut seen = std::collections::BTreeSet::new();
        keys.into_iter().filter(|k| !k.is_empty() && seen.insert(k.to_string())).filter_map(|k| self.ex_setting(k).cloned()).collect()
    }

    /// One side on its stop scale: a tick per stop, the band the limits leave the camera, a bar
    /// at a one-sided limit, and the value (filled dot: you set it; ring: the camera does).
    fn ex_strip(ui: &mut egui::Ui, width: f32, scale: (f64, f64), cell: &Cell, hover: String) {
        let (rect, resp) = ui.allocate_exact_size(egui::vec2(width.min(STRIP.x), STRIP.y), egui::Sense::hover());
        let p = ui.painter_at(rect);
        let (lo, hi) = scale;
        let pad = 7.0;
        let x = |s: f64| rect.left() + pad + (((s - lo) / (hi - lo)).clamp(0.0, 1.0) as f32) * (rect.width() - 2.0 * pad);
        let y = rect.center().y;
        let weak = ui.visuals().weak_text_color();
        let (you, camera) = (you(ui.visuals()), tone::camera(ui.visuals()));
        if let Some((a, b)) = cell.band {
            let r = egui::Rect::from_min_max(egui::pos2(x(a), y - 7.0), egui::pos2(x(b).max(x(a) + 2.0), y + 7.0));
            p.rect_filled(r, 3.0, tone::mix(ui.visuals().panel_fill, camera, 0.3));
        }
        p.line_segment([egui::pos2(rect.left() + pad, y), egui::pos2(rect.right() - pad, y)], egui::Stroke::new(1.0_f32, weak));
        for s in (lo.ceil() as i64)..=(hi.floor() as i64) {
            p.line_segment([egui::pos2(x(s as f64), y - 3.0), egui::pos2(x(s as f64), y + 3.0)], egui::Stroke::new(1.0_f32, weak));
        }
        if let Some((b, _)) = &cell.bound {
            p.line_segment([egui::pos2(x(*b), y - 9.0), egui::pos2(x(*b), y + 9.0)], egui::Stroke::new(2.0_f32, camera));
        }
        if let Some(s) = cell.at {
            match cell.who {
                Who::You => { p.circle_filled(egui::pos2(x(s), y), 5.0, you); }
                Who::Camera => { p.circle_stroke(egui::pos2(x(s), y), 5.0, egui::Stroke::new(2.0_f32, camera)); }
                Who::Unknown => { p.circle_stroke(egui::pos2(x(s), y), 5.0, egui::Stroke::new(1.5_f32, weak)); }
            }
        }
        resp.on_hover_text(hover);
    }

    pub(crate) fn exposure_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let Some(ex) = self.schema.camera.exposure.clone() else {
            ui.label("This camera's definition has no exposure page.");
            return Vec::new();
        };
        if self.doc.is_none() {
            ui.label("Open a settings file to see its exposure settings.");
            return Vec::new();
        }
        let sections = self.ex_sections();
        ui.heading(Self::ex_title(&ex));
        ui.label(RichText::new(INTRO).small().color(tone::weak(ui.visuals())));
        ui.add_space(6.0);
        let modes: Vec<Option<String>> = sections.iter().map(|&s| self.ex_mode(&ex, s)).collect();
        let cells = self.ex_cells(&ex, &sections, &modes);
        let mut goto: Option<Setting> = None;
        // the columns share the width shown, so every memory fits beside the live settings, its words wrapped in it
        let n = sections.len().max(1) as f32;
        let room = ui.available_width() - NAME_W - GAP * n - ui.spacing().scroll.bar_width - 2.0 * ui.spacing().scroll.bar_outer_margin;
        let cell_w = (room / n).clamp(CELL_MIN, CELL_W);
        let row_name = |ui: &mut egui::Ui, text: &str| { ui.set_width(NAME_W); ui.add(egui::Label::new(RichText::new(text).strong()).wrap()); };
        egui::ScrollArea::both().auto_shrink([false, false]).show(ui, |ui| {
            egui::Grid::new("exposure").striped(true).num_columns(1 + sections.len()).spacing([GAP, 8.0]).show(ui, |ui| {
                ui.vertical(|ui| ui.set_width(NAME_W));
                for &s in &sections { ui.vertical(|ui| { ui.set_width(cell_w); ui.strong(self.schema.camera.target_name(s)); }); }
                ui.end_row();

                ui.vertical(|ui| row_name(ui, "Exposure mode"));
                for (i, &sec) in sections.iter().enumerate() {
                    ui.vertical(|ui| {
                        ui.set_width(cell_w);
                        ui.label(RichText::new(modes[i].clone().unwrap_or_else(|| "—".into())).strong());
                        if let Some(c) = modes[i].as_ref().and_then(|m| ex.control.get(m)) {
                            ui.label(RichText::new(Self::ex_control(c)).small());
                        }
                        if sec == 0 && !ex.mode_note.is_empty() {
                            ui.label(RichText::new(&ex.mode_note).small().color(tone::weak(ui.visuals())));
                        }
                    });
                }
                ui.end_row();

                for (k, (side, side_name)) in SIDES.iter().enumerate() {
                    let def = Self::ex_side(&ex, *side);
                    let scale = self.ex_scale(*side, &def.scale_key);
                    ui.vertical(|ui| {
                        row_name(ui, side_name);
                        if let Some(((_, a), (_, b))) = &scale {
                            ui.label(RichText::new(format!("{a} to {b}")).small().color(tone::weak(ui.visuals())));
                        }
                    });
                    for row in &cells {
                        let c = &row[k];
                        ui.vertical(|ui| {
                            ui.set_width(cell_w);
                            ui.label(RichText::new(&c.text).strong());
                            ui.horizontal(|ui| c.who.chip(ui));
                            if let Some(((lo, _), (hi, _))) = scale {
                                Self::ex_strip(ui, cell_w, (lo, hi), c, Self::ex_hover(side_name, c));
                            }
                            for n in &c.notes { ui.label(RichText::new(n).small().color(tone::weak(ui.visuals()))); }
                        });
                    }
                    ui.end_row();
                }

                ui.vertical(|ui| row_name(ui, "Exposure comp."));
                for (i, &sec) in sections.iter().enumerate() {
                    ui.vertical(|ui| {
                        ui.set_width(cell_w);
                        ui.label(RichText::new(self.ex_comp(&ex, sec)).strong());
                        ui.label(RichText::new(Self::ex_comp_note(&cells[i])).small().color(tone::weak(ui.visuals())));
                    });
                }
                ui.end_row();

                ui.vertical(|ui| row_name(ui, "Exposes for"));
                for row in &cells {
                    ui.vertical(|ui| {
                        ui.set_width(cell_w);
                        match Self::ex_exposes(row) {
                            Some(ev) => { ui.label(format!("EV {ev:.1} at ISO 100")).on_hover_text(EV_HOVER); }
                            None => { ui.label(RichText::new("the camera meters the scene").small().color(tone::weak(ui.visuals()))); }
                        }
                    });
                }
                ui.end_row();
            });

            ui.add_space(10.0);
            for (side, name, effect) in EFFECTS {
                egui::CollapsingHeader::new(format!("What decides {name}")).id_salt(("ex", name)).show(ui, |ui| {
                    ui.label(RichText::new(effect).small());
                    for s in self.ex_decides(&ex, side) {
                        ui.horizontal(|ui| {
                            ui.label(&s.name);
                            ui.label(RichText::new(format!("{} > {}", s.tab, s.group)).small().color(tone::weak(ui.visuals())));
                            if self.shows_proof() {
                                ui.label(if s.proved.is_some() { RichText::new("proved on the camera").small().color(tone::ok(ui.visuals())) } else { RichText::new("not proved on the camera yet").small().color(tone::weak(ui.visuals())) });
                            }
                            if ui.small_button("Show in menu").clicked() { goto = Some(s.clone()); }
                        });
                    }
                });
            }
        });
        if let Some(s) = goto {
            self.view = self.view_of(&s);          // the page that shows it in the layout in use
            self.group = Some(self.shown_group_of(&s));          // the group that shows it in the layout in use
            self.item = Some(s.name.clone());
        }
        Vec::new()
    }
}
