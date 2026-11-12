//! Compare's view: the matrix of columns, its picker, the change map beside it, and the record map of every record.

use crate::*;

impl App {
    /// The column picker shared by the settings matrix and the record map: one row of section
    /// toggles per open file.
    fn column_picker(&mut self, ui: &mut egui::Ui) {
        self.prune_cols();
        let mut sources = vec![Src::A];
        if self.compare.is_some() { sources.push(Src::B); }
        if self.base.is_some() { sources.push(Src::Base); }
        for src in sources {
            ui.horizontal_wrapped(|ui| {
                let file = self.file_name_of(src);
                ui.label(RichText::new(format!("{} {file}:", src.letter())).strong().color(src.tone(ui.visuals())));
                for section in self.shown_sections() {
                    let c = Col { src, section };
                    let mut on = self.cols.contains(&c);
                    let short = self.schema.camera.short_name(section);
                    if ui.toggle_value(&mut on, short).on_hover_text(self.schema.camera.target_name(section)).changed() {
                        if on { self.cols.push(c) } else { self.cols.retain(|x| *x != c) }
                        self.diff_cursor = None;
                    }
                }
            });
        }
    }

    /// Compare mode's record map: every record of the baseline column's section in file order, one
    /// column per selected file/section, mapped or not, differences from the baseline highlighted.
    pub(crate) fn records_matrix(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let actions = Vec::new();
        if self.doc.is_none() {
            ui.label("No file open.");
            return actions;
        }
        // the same column picker as the settings matrix
        self.column_picker(ui);
        ui.label(RichText::new("Records in file order of the first column (the baseline); cells that differ from it are highlighted; unmapped records in amber. Click a setting to open it.").small().color(tone::weak(ui.visuals())));
        ui.separator();
        if self.cols.is_empty() {
            ui.label("Pick at least one column.");
            return actions;
        }
        let cols = self.cols.clone();
        let base = cols[0];
        let set_of = |c: Col| -> Option<&CamSet> { self.set_for(c.src) };
        let Some(base_set) = set_of(base) else { return actions };
        let Some(base_sec) = base_set.sections.get(base.section) else { return actions };
        // where each record starts, by the framing of the file's container block
        let offsets = base_set.record_offsets(base.section);
        let in_set = base.section != 0;
        let q = self.search.to_lowercase();
        let mut jump: Option<Setting> = None;
        let diff_fill = tone::differs(ui.visuals());
        egui::Grid::new(("record_matrix", base.section)).striped(true).num_columns(4 + cols.len()).spacing([14.0, 3.0]).show(ui, |ui| {
            ui.strong("Offset");
            ui.strong("Record");
            ui.strong("Shape");
            ui.strong("Setting");
            for c in &cols {
                self.col_title(ui, *c);
            }
            ui.end_row();
            for (ri, r) in base_sec.records.iter().enumerate() {
                let off = offsets.get(ri).copied().unwrap_or_default();
                let setting = self.setting_at(in_set, r.id);
                let cell = |rec: Option<&camset_editor::camset::Record>| -> String {
                    match rec {
                        None => "—".into(),
                        Some(rec) => match &setting {
                            Some(s) if s.text.is_some() => rec.text().unwrap_or_default(),
                            Some(s) if s.scalar => if self.show_raw { format!("{} [{}]", Self::describe(s, rec.as_int()), rec.display_value()) } else { Self::describe(s, rec.as_int()) },
                            _ => rec.display_value(),
                        },
                    }
                };
                let values: Vec<(String, bool)> = cols.iter().map(|c| {
                    let rec = set_of(*c).and_then(|s| s.sections.get(c.section)).and_then(|s| s.get(r.id));
                    (cell(rec), rec.is_some_and(|x| x.value != r.value))
                }).collect();
                let differs = values.iter().any(|(_, d)| *d);
                if self.matrix_only_diff && !differs { continue; }
                let id = format!("0x{:04x}", r.id);
                if !q.is_empty() && !id.contains(&q) && !setting.as_ref().is_some_and(|s| s.name.to_lowercase().contains(&q) || s.group.to_lowercase().contains(&q)) && !values.iter().any(|(v, _)| v.to_lowercase().contains(&q)) {
                    continue;
                }
                let amber = tone::unnamed(ui.visuals());
                let mono = |t: String| if setting.is_none() { RichText::new(t).monospace().color(amber) } else { RichText::new(t).monospace() };
                ui.label(mono(format!("{off:06x}")));
                ui.label(mono(id));
                ui.label(mono(format!("{}×{}", r.elem_size, r.count)));
                match setting {
                    Some(s) => {
                        if ui.add(egui::Label::new(&s.name).sense(egui::Sense::click())).on_hover_text(format!("{} > {}\n{}", s.tab, s.group, s.note_shown(self.prefs.expert)).trim_end().to_string()).clicked() {
                            jump = Some(s.clone());
                        }
                    }
                    None => { ui.label(RichText::new("— unmapped —").color(amber)); }
                }
                for (i, (v, d)) in values.iter().enumerate() {
                    let short: String = if v.chars().count() > 28 { format!("{}…", v.chars().take(28).collect::<String>()) } else { v.clone() };
                    let fill = if i > 0 && *d { diff_fill } else { Color32::TRANSPARENT };
                    let resp = egui::Frame::new().fill(fill).inner_margin(egui::Margin::symmetric(4, 1)).corner_radius(3.0)
                        .show(ui, |ui| { ui.label(RichText::new(short).monospace()); }).response;
                    if v.chars().count() > 28 { resp.on_hover_text(v.clone()); }
                }
                ui.end_row();
            }
        });
        if let Some(s) = jump {
            self.mode = Mode::Edit;
            self.target = base.section;
            self.view = self.view_of(&s);
            self.group = Some(self.shown_group_of(&s));
            self.item = Some(s.name.clone());
            self.focus = Focus::Items;
        }
        actions
    }

    /// A compare column's name as a header, in its file's colour; files B and Base carry a lock.
    pub(crate) fn col_title(&self, ui: &mut egui::Ui, c: Col) {
        ui.horizontal(|ui| {
            ui.label(RichText::new(self.col_name(c)).strong().color(c.src.tone(ui.visuals())));
            if !c.editable() {
                ui.label(RichText::new("🔒").small().color(tone::weak(ui.visuals()))).on_hover_text("This file is never changed; values only go into A");
            }
        });
    }

    /// The narrow cell between two compare columns: an arrow into each column of file A that can take
    /// the other column's value in this row. A column of file A keeps its slot when it gets no arrow,
    /// so the arrows stay in line down the table.
    fn gap_cell(&self, ui: &mut egui::Ui, linked: &[Setting], left: Col, right: Col) -> Vec<Action> {
        let mut out = Vec::new();
        let (into_l, into_r) = self.arrows_between(left, right, &linked[0]);
        let editable = self.editable();
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = 0.0;
            for (slot, on, glyph, from, to) in [(left.editable(), into_l, "◀", right, left), (right.editable(), into_r, "▶", left, right)] {
                if !(editable && slot) {
                    continue;
                }
                if !on {
                    ui.allocate_exact_size(Self::ARROW, egui::Sense::hover());
                } else if Self::arrow_button(ui, glyph, &Self::arrow_words(&self.col_name(from), &self.col_name(to))).clicked() {
                    out.extend(self.copy_row(linked, from, to));
                }
            }
        });
        out
    }

    /// Size of a copy arrow between two compare columns.
    const ARROW: egui::Vec2 = egui::Vec2::new(14.0, 16.0);

    /// A small arrow that copies a value, in a weak colour until the pointer is on it.
    fn arrow_button(ui: &mut egui::Ui, glyph: &str, hover: &str) -> egui::Response {
        let (rect, resp) = ui.allocate_exact_size(Self::ARROW, egui::Sense::click());
        let resp = as_button(resp, hover);
        let v = ui.visuals();
        let color = if resp.hovered() { v.strong_text_color() } else { tone::weak(v) };
        if resp.hovered() {
            ui.painter().rect_filled(rect, 3.0, v.widgets.hovered.weak_bg_fill);
        }
        ui.painter().text(rect.center(), egui::Align2::CENTER_CENTER, glyph, egui::FontId::proportional(11.0), color);
        resp.on_hover_text(hover).on_hover_cursor(egui::CursorIcon::PointingHand)
    }

    /// The change minimap beside the compare matrix: one tick per row shown, differences and edits
    /// coloured, the rows on screen framed, the difference cursor marked. Click to jump.
    pub(crate) fn minimap(&mut self, ui: &mut egui::Ui) {
        let n = self.mm_rows.len();
        let (resp, painter) = ui.allocate_painter(egui::vec2(ui.available_width(), ui.available_height()), egui::Sense::click_and_drag());
        let resp = as_button(resp, "Map of the differences: click to go to a row (F3 and Shift+F3 step through them)");
        let rect = resp.rect;
        let v = ui.visuals().clone();
        painter.rect_filled(rect, 2.0, tone::track(&v));
        if n == 0 {
            return;
        }
        let row_h = (rect.height() / n as f32).max(1.0);
        let y = |i: usize| rect.top() + rect.height() * i as f32 / n as f32;
        for (i, m) in self.mm_rows.iter().enumerate() {
            let color = match m {
                RowMark::Same => continue,
                RowMark::Differs => tone::differs_mark(&v),
                RowMark::Edited => tone::edit(&v),
                RowMark::Conflict => tone::bad(&v),
            };
            painter.rect_filled(egui::Rect::from_min_size(egui::pos2(rect.left(), y(i)), egui::vec2(rect.width(), row_h)), 0.0, color);
        }
        if let Some((a, b)) = self.mm_visible {
            let r = egui::Rect::from_min_max(egui::pos2(rect.left(), y(a)), egui::pos2(rect.right(), y(b + 1).min(rect.bottom())));
            let t = v.strong_text_color();
            painter.rect_filled(r, 0.0, Color32::from_rgba_unmultiplied(t.r(), t.g(), t.b(), 28));
            painter.rect_stroke(r, 0.0, egui::Stroke::new(1.0_f32, Color32::from_rgba_unmultiplied(t.r(), t.g(), t.b(), 140)), egui::StrokeKind::Inside);
        }
        if let Some(c) = self.diff_cursor.filter(|c| *c < n) {
            painter.rect_filled(egui::Rect::from_min_size(egui::pos2(rect.left() - 2.0, y(c)), egui::vec2(rect.width() + 4.0, row_h.max(2.0))), 0.0, v.strong_text_color());
        }
        if resp.clicked() || resp.dragged() {
            if let Some(p) = resp.interact_pointer_pos() {
                let i = (((p.y - rect.top()) / rect.height()) * n as f32).floor().clamp(0.0, (n - 1) as f32) as usize;
                self.scroll_to_row = Some(i);
                self.diff_cursor = Some(i);
            }
        }
        resp.on_hover_text("Change map: every row of the comparison, differences in pale amber, your edits orange, changes that clash red. Click to jump.");
    }

    /// "← Back to Compare" at the head of Edit's row, while Edit still shows the setting Compare opened; once the
    /// person goes elsewhere on their own (another setting, group, page or set) it is gone for good.
    pub(crate) fn back_to_compare_ui(&mut self, ui: &mut egui::Ui) {
        let Some(f) = &self.from_compare else { return };
        if self.mode != Mode::Edit || self.view != f.view || self.group != f.group || self.item != f.item || self.target != f.target {
            self.from_compare = None;
            return;
        }
        if ui.button("← Back to Compare").on_hover_text("Return to Compare, on the row this setting was opened from").clicked() {
            self.back_to_compare();
        }
        ui.separator();
    }

    pub(crate) fn matrix_view(&mut self, ui: &mut egui::Ui) -> Vec<Action> {
        let mut actions = Vec::new();
        // Compare is shown: an "Open in Edit" from before is over, whether ← Back to Compare or the Compare button came here
        self.from_compare = None;
        if self.doc.is_none() {
            ui.label("No file open.");
            self.mm_rows.clear();
            return actions;
        }
        self.column_picker(ui);
        ui.label(RichText::new("The other columns are compared with the first: values that differ from it are shaded, your edits are orange with a pencil. The small arrows between columns put a value into the column they point at (only the open file, A, takes values); a click on a value of A changes it; right-click a value or a column heading for more.").small().color(tone::weak(ui.visuals())));
        // one click to recall a memory into the live settings of file A, or to register the live settings into a memory
        if self.editable() && !self.dial_sets().is_empty() {
            ui.horizontal_wrapped(|ui| {
                ui.label(RichText::new("Whole sets:").strong());
                let every = self.whole_set_note(!self.search.trim().is_empty() || self.compare_tab.is_some());
                for section in self.dial_sets() {
                    let m = Col::a(section);
                    let live = Col::a(0);
                    // the whole set, whatever the search and the tab filter show
                    let (label, hover, said) = self.recall_words(section, &every, "");
                    if ui.button(label).on_hover_text(hover).clicked() {
                        for (_, _, linked) in self.memory_rows() {
                            actions.extend(self.copy_row(&linked, m, live));
                        }
                        self.status = said;
                    }
                    let (label, hover, said) = self.register_words(section, &every, "");
                    if ui.button(label).on_hover_text(hover).clicked() {
                        for (_, _, linked) in self.memory_rows() {
                            actions.extend(self.copy_row(&linked, live, m));
                        }
                        self.status = said;
                    }
                }
            });
        }
        ui.separator();
        if self.cols.len() < 2 {
            ui.label("Pick at least two columns.");
            self.mm_rows.clear();
            return actions;
        }
        let cols = self.cols.clone();
        let rows = self.matrix_rows_shared(&self.search, self.compare_tab.as_deref());
        let editable = self.editable();
        let three = self.three_cols();
        // each row's values and standing, worked out once a frame for the counts, the filters, the change map and the cells
        let info: Vec<RowInfo> = rows.iter().map(|r| self.row_info(&cols, three, &r.2[0])).collect();
        // per-column difference counts for the headers
        let counts: Vec<usize> = (0..cols.len()).map(|i| info.iter().filter(|x| x.stored[i] && x.vals[i] != x.vals[0]).count()).collect();
        // a row changed with Compare's picker stays shown until a filter changes (`cmp_kept`)
        let kept = |k: usize| self.cmp_kept.as_ref().is_some_and(|(t, n)| rows[k].0 == *t && rows[k].2[0].key == *n);
        let picked: Vec<usize> = (0..rows.len())
            .filter(|&k| !self.matrix_only_diff || info[k].differs || kept(k))
            .filter(|&k| info[k].class.is_none_or(|c| self.three_filter.keeps(c)) || kept(k))
            .collect();
        let shown: Vec<&Row> = picked.iter().map(|&k| &rows[k]).collect();
        let shown_info: Vec<&RowInfo> = picked.iter().map(|&k| &info[k]).collect();
        // back from Edit (← Back to Compare): the row the setting was opened from, under the cursor and in view
        if let Some((tab, key)) = self.compare_row_to.take() {
            if let Some(i) = shown.iter().position(|r| r.0 == tab && r.2[0].key == key) {
                self.diff_cursor = Some(i);
                self.scroll_to_row = Some(i);
            }
        }
        // three-way summary, filter and merge buttons
        if let Some(tc) = three {
            let (tb, ta, tbb) = tc;
            let classes: Vec<Three> = rows.iter().map(|r| self.three_way(tc, &r.2[0])).collect();
            let count = |k: Three| classes.iter().filter(|c| **c == k).count();
            ui.horizontal_wrapped(|ui| {
                ui.label(RichText::new("Three-way:").strong().color(Src::Base.tone(ui.visuals())));
                ui.label(format!("{} changed in A, {} in B, {} the same change, {} conflicts", count(Three::AOnly), count(Three::BOnly), count(Three::Both), count(Three::Conflict)))
                    .on_hover_text(format!("{} against {} and {}", self.col_name(tb), self.col_name(ta), self.col_name(tbb)));
                let r = egui::ComboBox::from_id_salt("three_filter").selected_text(self.three_filter.label()).show_ui(ui, |ui| {
                    for f in [ThreeFilter::All, ThreeFilter::AOnly, ThreeFilter::BOnly, ThreeFilter::Both, ThreeFilter::Conflicts] {
                        if ui.selectable_value(&mut self.three_filter, f, f.label()).changed() { self.diff_cursor = None; self.cmp_kept = None; }
                    }
                });
                named(r.response, "Rows shown in the three-way compare");
                if editable {
                    let mergeable = count(Three::BOnly);
                    if ui.add_enabled(mergeable > 0, egui::Button::new(format!("Merge B into A ({mergeable})"))).on_hover_text("Take every change B made where A kept the base value. Conflicts are left alone.").clicked() {
                        for (r, c) in rows.iter().zip(&classes) {
                            if *c == Three::BOnly { actions.extend(self.copy_row(&r.2, tbb, ta)); }
                        }
                        self.pin_families(None, ta.section, &mut actions);
                        self.status = format!("{mergeable} of B's changes merged into A; save the file to keep them");
                    }
                    let conflicts = count(Three::Conflict);
                    if ui.add_enabled(conflicts > 0, egui::Button::new("Conflicts: take B")).on_hover_text("Where A and B changed a setting differently, use B's value").clicked() {
                        for (r, c) in rows.iter().zip(&classes) {
                            if *c == Three::Conflict { actions.extend(self.copy_row(&r.2, tbb, ta)); }
                        }
                        self.pin_families(None, ta.section, &mut actions);
                        self.status = format!("{conflicts} conflicts resolved with B's values; save the file to keep them");
                    }
                    if ui.add_enabled(conflicts > 0, egui::Button::new("Conflicts: take Base")).on_hover_text("Where A and B changed a setting differently, go back to the base value").clicked() {
                        for (r, c) in rows.iter().zip(&classes) {
                            if *c == Three::Conflict { actions.extend(self.copy_row(&r.2, tb, ta)); }
                        }
                        self.pin_families(None, ta.section, &mut actions);
                        self.status = format!("{conflicts} conflicts reset to the base values; save the file to keep them");
                    }
                }
            });
        }
        // difference cursor: Next / Previous over the rows shown that differ from the baseline
        let diff_rows: Vec<usize> = shown_info.iter().enumerate().filter(|(_, x)| x.differs).map(|(i, _)| i).collect();
        if self.diff_step != 0 && !diff_rows.is_empty() {
            let pos = match (self.diff_cursor, self.diff_step) {
                (Some(c), 1) => diff_rows.iter().position(|i| *i > c).unwrap_or(0),
                (Some(c), _) => diff_rows.iter().rposition(|i| *i < c).unwrap_or(diff_rows.len() - 1),
                (None, 1) => 0,
                (None, _) => diff_rows.len() - 1,
            };
            self.diff_cursor = Some(diff_rows[pos]);
            self.scroll_to_row = self.diff_cursor;
        }
        self.diff_step = 0;
        if self.diff_cursor.is_some_and(|c| c >= shown.len()) { self.diff_cursor = None; }
        ui.horizontal(|ui| {
            ui.label(format!("{} of {} settings shown", shown.len(), rows.len()));
            if ui.button("Collapse all").on_hover_text("Fold every tab; click a tab or group heading to open it").clicked() {
                for (t, _, _) in rows.iter() { self.matrix_closed.insert((t.clone(), String::new())); }
            }
            if ui.button("Expand all").clicked() { self.matrix_closed.clear(); }
            ui.separator();
            let at = self.diff_cursor.and_then(|c| diff_rows.iter().position(|i| *i == c));
            if ui.add_enabled(!diff_rows.is_empty(), egui::Button::new("⏶ Previous")).on_hover_text("Previous difference (Shift+F3 or Alt+Up)").clicked() { self.diff_step = -1; }
            if ui.add_enabled(!diff_rows.is_empty(), egui::Button::new("⏷ Next")).on_hover_text("Next difference (F3 or Alt+Down)").clicked() { self.diff_step = 1; }
            ui.label(match at {
                Some(k) => format!("difference {} of {}", k + 1, diff_rows.len()),
                None => format!("{} differences", diff_rows.len()),
            });
        });
        if self.diff_step != 0 { ui.ctx().request_repaint(); }
        let cursor_color = ui.visuals().strong_text_color();
        if let Some((t, g, _)) = self.scroll_to_row.and_then(|i| shown.get(i).copied()) {
            self.matrix_closed.remove(&(t.clone(), String::new()));
            self.matrix_closed.remove(&(t.clone(), g.clone()));
        }
        let scroll_to = self.scroll_to_row.take();
        let cursor = self.diff_cursor;
        // each tab's and group's settings shown, and how many of them differ, for the headings
        let mut tally: std::collections::HashMap<(String, String), (usize, usize)> = Default::default();
        for ((t, g, _), x) in shown.iter().zip(&shown_info) {
            let d = usize::from(x.differs);
            for k in [(t.clone(), String::new()), (t.clone(), g.clone())] {
                let e = tally.entry(k).or_default();
                e.0 += 1;
                e.1 += d;
            }
        }
        // the change map's marks: every row shown, folded or not
        let marks: Vec<RowMark> = shown_info.iter().map(|x| x.mark).collect();
        let mut visible: Option<(usize, usize)> = None;
        let clip = ui.clip_rect();
        // the setting, the 3-way tag, then the columns with a narrow gap between each two for the copy arrows
        let ncols = 2 * cols.len() + usize::from(three.is_some());
        // fixed column widths, so the columns stay put while rows off screen are skipped: the setting names' widest,
        // and one width for every value column (a longer value is cut short, in full on hover)
        let body = egui::TextStyle::Body.resolve(ui.style());
        let name_w = ui.fonts(|f| shown.iter().map(|r| f.layout_no_wrap(self.setting_title(&r.2[0]), body.clone(), Color32::WHITE).size().x)
            .fold(130.0_f32, f32::max)).min(460.0) + 2.0;
        let cell_w = 190.0;
        // a row's height as last drawn, for the rows off screen, which only keep their place
        let row_h = self.matrix_row_h.get();
        let mut drawn_h = 0.0_f32;
        // a setting to open in Edit (its name clicked, or Open in Edit on a value of file A), in that section
        let mut open_edit: Option<(Setting, usize)> = None;

        egui::Grid::new("matrix").striped(true).num_columns(ncols).spacing([8.0, 4.0]).min_col_width(0.0).show(ui, |ui| {
            ui.horizontal(|ui| { ui.set_width(name_w); ui.strong("Setting"); });
            if three.is_some() { ui.strong("Changes").on_hover_text("Against the base file. A: changed in A only; B: changed in B only; A=B: the same change in both; !: changed differently in each"); }
            for (i, c) in cols.iter().enumerate() {
                if i > 0 { ui.label(""); }
                let head = if i == 0 { "the others are compared with it".to_string() } else { format!("{} differ", counts[i]) };
                let r = ui.vertical(|ui| { ui.set_width(cell_w + 8.0); self.col_title(ui, *c); ui.label(RichText::new(head).small().color(tone::weak(ui.visuals()))); }).response;
                r.context_menu(|ui| {
                    if i > 0 && ui.button("Compare the others with this column").clicked() {
                        self.cols.swap(0, i); self.diff_cursor = None; ui.close_menu();
                    }
                    if ui.button("Remove column").clicked() {
                        self.cols.retain(|x| x != c); self.diff_cursor = None; ui.close_menu();
                    }
                    for t in cols.iter().filter(|t| t.editable() && *t != c) {
                        if editable && ui.button(format!("Copy all shown rows to {}", self.col_name(*t))).clicked() {
                            for (_, _, linked) in &shown { actions.extend(self.copy_row(linked, *c, *t)); }
                            self.pin_families((c.src == Src::A).then_some(c.section), t.section, &mut actions);
                            ui.close_menu();
                        }
                    }
                });
            }
            ui.end_row();
            // tab and group headings fold what is under them (a click opens or closes one)
            let mut last_group = (String::new(), String::new());
            for (ri, ((tab, group, linked), x)) in shown.iter().zip(&shown_info).enumerate() {
                let tab_key = (tab.clone(), String::new());
                if *tab != last_group.0 {
                    let closed = self.matrix_closed.contains(&tab_key);
                    let (n, d) = tally.get(&tab_key).copied().unwrap_or_default();
                    let head = RichText::new(format!("{} {tab}", if closed { "⏵" } else { "⏷" })).strong().size(15.0).color(tab_ink(ui.visuals(), &self.schema.camera, tab));
                    if ui.add(egui::Label::new(head).sense(egui::Sense::click())).on_hover_text("Click to fold or open the tab").clicked() {
                        if closed { self.matrix_closed.remove(&tab_key); } else { self.matrix_closed.insert(tab_key.clone()); }
                    }
                    ui.label(RichText::new(format!("{n} settings · {d} differ")).small().color(tone::weak(ui.visuals())));
                    for _ in 0..ncols - 2 { ui.label(""); }
                    ui.end_row();
                    last_group = (tab.clone(), String::new());
                }
                let tab_closed = self.matrix_closed.contains(&tab_key);
                let group_key = (tab.clone(), group.clone());
                if !tab_closed && *group != last_group.1 {
                    let closed = self.matrix_closed.contains(&group_key);
                    let (n, d) = tally.get(&group_key).copied().unwrap_or_default();
                    let head = RichText::new(format!("   {} {group}", if closed { "⏵" } else { "⏷" })).strong().color(tab_ink(ui.visuals(), &self.schema.camera, tab));
                    if ui.add(egui::Label::new(head).sense(egui::Sense::click())).on_hover_text("Click to fold or open the group").clicked() {
                        if closed { self.matrix_closed.remove(&group_key); } else { self.matrix_closed.insert(group_key.clone()); }
                    }
                    ui.label(RichText::new(format!("{n} · {d} differ")).small().color(tone::weak(ui.visuals())));
                    for _ in 0..ncols - 2 { ui.label(""); }
                    ui.end_row();
                    last_group.1 = group.clone();
                }
                let s = &linked[0];
                // a folded row is not drawn; its mark stays, so the change map and the difference cursor still count it
                if tab_closed || self.matrix_closed.contains(&group_key) {
                    continue;
                }
                // a row off screen only keeps its place (its height as last drawn), unless it is to be scrolled to
                let top = ui.cursor().top();
                let on_screen = top <= clip.bottom() + row_h && top + row_h >= clip.top() - row_h;
                if !on_screen && scroll_to != Some(ri) {
                    ui.allocate_space(egui::vec2(name_w, row_h));
                    ui.end_row();
                    continue;
                }
                let on_cursor = cursor == Some(ri);
                let title = self.setting_title(s);
                let name = if on_cursor { RichText::new(title).strong().color(cursor_color) } else { RichText::new(title) };
                // the name is a link, underlined under the pointer: a click opens the setting in Edit, in the first
                // column of file A that keeps it (else the live settings)
                let a_sec = cols.iter().find(|c| c.editable() && (c.section == 0 || s.in_sets)).map_or(0, |c| c.section);
                let name_r = ui.horizontal(|ui| {
                    ui.set_width(name_w);
                    let r = ui.add(egui::Label::new(name).truncate().selectable(false).sense(egui::Sense::click()));
                    if r.hovered() {
                        ui.painter().hline(r.rect.x_range(), r.rect.bottom(), egui::Stroke::new(1.0_f32, ui.visuals().text_color()));
                    }
                    as_button(r, &format!("Open {} in Edit", s.name))
                        .on_hover_text(format!("{}\nClick to open it in Edit ({})", self.where_kept(s), self.schema.camera.target_name(a_sec)))
                        .on_hover_cursor(egui::CursorIcon::PointingHand)
                }).inner;
                if name_r.clicked() {
                    open_edit = Some((s.clone(), a_sec));
                }
                drawn_h = drawn_h.max(name_r.rect.height());
                if scroll_to == Some(ri) {
                    name_r.scroll_to_me(Some(egui::Align::Center));
                }
                if name_r.rect.intersects(clip) {
                    visible = Some(match visible { None => (ri, ri), Some((a, _)) => (a, ri) });
                }
                if let Some(c) = x.class {
                    let (tag, hover) = c.tag();
                    ui.label(RichText::new(tag).strong().color(c.tone(ui.visuals()))).on_hover_text(hover);
                }
                for (i, c) in cols.iter().enumerate() {
                    if i > 0 { actions.extend(self.gap_cell(ui, linked, cols[i - 1], *c)); }
                    let (v, stored, edited) = (x.vals[i], x.stored[i], x.edited[i]);
                    let shown_text = if s.text.is_some() { self.col_text(*c, s).unwrap_or_default() } else { Self::describe(s, v) };
                    let mut text = if stored { RichText::new(shown_text) } else { RichText::new("—").weak() };
                    if self.show_raw { if let Some(v) = v { text = RichText::new(format!("{}  [{v}]", Self::describe(s, Some(v)))); } }
                    let differs_here = i > 0 && stored && v != x.vals[0];
                    // one line per cell: long values are cut short, the full text is on hover
                    let r = Self::value_cell_w(ui, text, differs_here, edited, Some(cell_w)).interact(egui::Sense::click());
                    drawn_h = drawn_h.max(r.rect.height());
                    if !stored { continue; }
                    // a number with no name yet says why on hover
                    let r = match self.unnamed_why(s, v) { Some(why) => r.on_hover_text(why), None => r };
                    // an edit says what it was on hover, as Edit's row does
                    let r = if edited { r.on_hover_text(format!("was {}", self.col_was(*c, s))) } else { r };
                    // a value of file A that is view only outside Expert mode says why it takes none (`locked_why`), and
                    // one the camera keeps in more than one record what changing it changes (`copy_note`)
                    let r = match self.locked_why(s, c.section).filter(|_| c.editable()) { Some((why, _)) => r.on_hover_text(why), None => r };
                    let r = match self.copy_note(s, c.section).filter(|_| c.editable()) { Some((note, _)) => r.on_hover_text(note), None => r };
                    // a value of file A that can change opens Compare's picker on a click (or the menu's "Change…",
                    // the frame after its menu closes)
                    let changeable = editable && self.cell_editable(*c, linked);
                    let pick_id = Self::picker_id(s, c.section);
                    let r = if changeable { r.on_hover_text("Click to change this value").on_hover_cursor(egui::CursorIcon::PointingHand) } else { r };
                    let pending = changeable && ui.data_mut(|d| d.remove_temp::<bool>(pick_id.with("pending"))).is_some();
                    if changeable && (r.clicked() || pending) {
                        Self::open_compare_picker(ui, pick_id, r.clicked());
                    }
                    if changeable && self.compare_picker(ui, pick_id, &r, c.section, linked, &mut actions) {
                        self.cmp_kept = Some((tab.clone(), s.key.clone()));
                    }
                    // a value copies only into the other columns of file A that the compare shows; a column of file A
                    // also opens the setting in Edit, in that column's set
                    let targets = self.copy_targets(*c, s);
                    let can_copy = editable && !targets.is_empty();
                    let open_here = c.editable();
                    if !can_copy && editable && !edited && !open_here { continue; }
                    let r = if can_copy { r.on_hover_text_at_pointer("Right-click to put this value into another column of file A") } else { r };
                    r.context_menu(|ui| {
                        if can_copy {
                            ui.label(RichText::new(format!("Copy {} from {}", s.name, self.col_name(*c))).color(tone::weak(ui.visuals())).small());
                            for t in &targets {
                                // the arrow points from this cell's column toward the column the value goes into
                                let arrow = if cols.iter().position(|x| x == t).is_some_and(|p| p < i) { "◀" } else { "▶" };
                                let name = self.col_name(*t);
                                if ui.button(format!("{arrow} {name}")).on_hover_text(format!("Put this value into {name}")).clicked() {
                                    actions.extend(self.copy_row(linked, *c, *t)); ui.close_menu();
                                }
                            }
                            if targets.len() > 1 {
                                let names = targets.iter().map(|t| self.col_name(*t)).collect::<Vec<_>>().join(", ");
                                if ui.button(format!("All of A ({} columns)", targets.len())).on_hover_text(format!("Put this value into {names}")).clicked() {
                                    for t in &targets { actions.extend(self.copy_row(linked, *c, *t)); }
                                    ui.close_menu();
                                }
                            }
                            ui.separator();
                        }
                        if changeable && ui.button("Change…").on_hover_text("Choose another value here, as in Edit").clicked() {
                            ui.data_mut(|d| d.insert_temp(pick_id.with("pending"), true));
                            ui.ctx().request_repaint();
                            ui.close_menu();
                        }
                        if open_here && ui.button(format!("Open in Edit: {}", self.col_name(*c))).on_hover_text("Open this setting in Edit, in this column's set").clicked() {
                            open_edit = Some((s.clone(), c.section));
                            ui.close_menu();
                        }
                        if edited && ui.button("Revert").clicked() {
                            for l in linked.iter() { actions.push(Action::Revert(c.section, l.slot())); }
                            ui.close_menu();
                        }
                        // where the plain Revert does not serve: back where the camera keeps it (`put_back_choice`)
                        if editable && c.editable() {
                            if let Some((words, fix)) = self.put_back_choice(linked, c.section) {
                                if ui.button(words).clicked() { actions.extend(fix); ui.close_menu(); }
                            }
                        }
                        if !editable { ui.label("This firmware has not been checked yet; editing is off."); }
                    });
                }
                if on_cursor {
                    let row = egui::Rect::from_min_max(egui::pos2(name_r.rect.left() - 4.0, name_r.rect.top() - 2.0), egui::pos2(ui.max_rect().right(), name_r.rect.bottom() + 2.0));
                    ui.painter().rect_stroke(row, 3.0, egui::Stroke::new(1.5_f32, cursor_color), egui::StrokeKind::Outside);
                }
                ui.end_row();
            }
        });
        if drawn_h > 0.0 { self.matrix_row_h.set(drawn_h); }
        self.mm_rows = marks;
        self.mm_visible = visible;
        if let Some((s, section)) = open_edit {
            self.open_in_edit_from_compare(&s, section);
        }
        actions
    }

    /// The popup of Compare's picker for setting `s`'s row in the set `section` of file A: one per cell, the same
    /// from frame to frame wherever the row is drawn.
    fn picker_id(s: &Setting, section: usize) -> egui::Id {
        egui::Id::new(("cmp_pick", s.key.as_str(), section))
    }

    /// Open Compare's picker `id` (`toggle`: a click on its cell opens or closes it), the number or text typed in it
    /// before forgotten.
    fn open_compare_picker(ui: &mut egui::Ui, id: egui::Id, toggle: bool) {
        ui.data_mut(|d| {
            d.remove::<(Option<i64>, i64)>(id.with("num"));
            d.remove::<(String, String)>(id.with("text"));
        });
        ui.memory_mut(|m| if toggle { m.toggle_popup(id) } else { m.open_popup(id) });
    }

    /// Compare's picker for a value of file A, under its cell (`cell` clicked, or its menu's "Change…"): the choice the
    /// detail panel offers for the setting, in the column's set `section`, applied through the same actions (every
    /// record of the row together, `set_linked`), so the edit marks, undo, Revert and the write check follow as from
    /// Edit. Named values as the detail panel lists them (`option_choice_ui`: those no proof established only when
    /// asked for, the refused ones marked, the option tree's main option and its choice), a number within its range
    /// and steps, or a text by its rule; then what it was, with Revert, and why the camera may not take it. A final
    /// choice closes it; a main option with choices of its own keeps it open on them. True when it changed something.
    pub(crate) fn compare_picker(&self, ui: &mut egui::Ui, id: egui::Id, cell: &egui::Response, section: usize, linked: &[Setting], actions: &mut Vec<Action>) -> bool {
        let (Some(doc), Some(s)) = (&self.doc, linked.first()) else { return false };
        let n = actions.len();
        let (cur, orig) = (doc.value(section, s.slot()), doc.original_value(section, s.slot()));
        let mut close = false;
        egui::popup_below_widget(ui, id, cell, egui::PopupCloseBehavior::CloseOnClickOutside, |ui| {
            ui.set_min_width(240.0);
            ui.set_max_width(420.0);
            ui.label(RichText::new(&s.name).strong());
            ui.label(RichText::new(self.schema.camera.target_name(section)).small().color(tone::weak(ui.visuals())));
            self.unnamed_line(ui, s, cur);
            let changed;
            if let Some(rule) = &s.text {
                let text_of = |c: &CamSet| c.sections.get(section).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default();
                let (now, was) = (text_of(&doc.edited), text_of(&doc.original));
                changed = now != was;
                // what is typed belongs to the text it was typed over: an undo or an edit elsewhere starts it afresh
                let key = id.with("text");
                let mut buf = ui.data(|d| d.get_temp::<(String, String)>(key)).filter(|(over, _)| *over == now).map_or_else(|| now.clone(), |(_, b)| b);
                let mut apply = false;
                ui.horizontal(|ui| {
                    let resp = named(ui.add(egui::TextEdit::singleline(&mut buf).desired_width(180.0).char_limit(rule.max_len)), &s.name);
                    if rule.uppercase {
                        buf = buf.to_uppercase();
                    }
                    let ok = rule.check(&buf).is_ok() && buf != now;
                    apply = ui.add_enabled(ok, egui::Button::new("Apply")).clicked() || (ok && resp.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)));
                });
                if let Err(e) = rule.check(&buf) {
                    ui.label(RichText::new(e).small().color(tone::bad(ui.visuals())));
                }
                if apply {
                    actions.push(Action::SetText(section, s.id, buf.clone()));
                    close = true;
                }
                ui.data_mut(|d| d.insert_temp(key, (now, buf)));
                if changed {
                    ui.horizontal(|ui| {
                        ui.label(RichText::new(format!("was {was}")).small().color(tone::weak(ui.visuals())));
                        if ui.small_button("Revert").clicked() {
                            actions.push(Action::Revert(section, (s.id, None)));
                            close = true;
                        }
                    });
                }
                return;
            }
            changed = cur != orig;
            if let (Some((lo, hi)), Some(now)) = (s.range, cur) {
                // a number within its range, in its steps: applied with OK or Enter, as the Main page's tiles do
                let step = s.step.unwrap_or(1).max(1);
                let key = id.with("num");
                let mut v = ui.data(|d| d.get_temp::<(Option<i64>, i64)>(key)).filter(|(over, _)| *over == cur).map_or(now, |(_, v)| v);
                let mut apply = false;
                ui.horizontal(|ui| {
                    if named(ui.add_enabled(v - step >= lo, egui::Button::new(" − ")), &format!("{}: one step down", s.name)).clicked() {
                        v -= step;
                    }
                    let resp = named(ui.add(number_box(s, &mut v, lo, hi, step)), &s.name);
                    if named(ui.add_enabled(v + step <= hi, egui::Button::new(" + ")), &format!("{}: one step up", s.name)).clicked() {
                        v += step;
                    }
                    apply = ui.button("OK").clicked() || (resp.lost_focus() && ui.input(|i| i.key_pressed(egui::Key::Enter)));
                });
                ui.label(RichText::new(range_words(s, lo, hi, step)).small().color(tone::weak(ui.visuals())));
                let snapped = snap_to_step(v, lo, hi, step);
                if apply {
                    if snapped != now {
                        actions.extend(Self::set_linked(section, linked, snapped));
                    }
                    close = true;
                }
                ui.data_mut(|d| d.insert_temp(key, (cur, v)));
            } else if s.values.len() >= 2 {
                let hidden = s.hidden_unproved(self.allow_unobserved);
                if hidden > 0 && self.prefs.expert {
                    ui.label(RichText::new(super::detail::hidden_words(hidden)).small().color(tone::weak(ui.visuals())));
                }
                // the values its menus never offer are not in the list, Expert mode or not: why, as Edit says it
                self.not_offered_ui(ui, s);
                egui::ScrollArea::vertical().id_salt(id.with("list")).max_height(360.0).show(ui, |ui| {
                    if let Some((v, last)) = self.option_choice_ui(ui, section, s, (cur, orig), true, false) {
                        if Some(v) != cur {
                            actions.extend(Self::set_linked(section, linked, v));
                        }
                        close = last;
                    }
                });
            }
            if changed {
                ui.separator();
                ui.horizontal(|ui| {
                    ui.label(RichText::new(format!("was {}", Self::describe(s, orig))).small().color(tone::weak(ui.visuals())));
                    if ui.small_button("Revert").clicked() {
                        actions.extend(linked.iter().map(|l| Action::Revert(section, l.slot())));
                        close = true;
                    }
                });
                if let Some(reason) = cur.and_then(|v| s.acceptance(v)) {
                    ui.label(RichText::new(format!("⚠ {reason}")).small().color(tone::caution(ui.visuals())));
                }
            }
            if linked.len() > 1 && self.prefs.expert {
                ui.label(RichText::new("The camera keeps this setting in more than one place; changing it here changes them all together.").small().color(tone::weak(ui.visuals())));
            }
        });
        if close {
            ui.memory_mut(|m| m.close_popup());
        }
        actions.len() > n
    }
}

#[cfg(test)]
pub(crate) mod screen_reader_tests {
    use super::*;
    use eframe::App as _;
    use egui::accesskit::Role;

    /// What a screen reader is told about the window once it has settled (two frames): each named control's role and
    /// name.
    fn spoken(app: &mut App) -> Vec<(Role, String)> {
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut frame = eframe::Frame::_new_kittest();
        let _ = ctx.run(egui::RawInput::default(), |ctx| app.update(ctx, &mut frame));
        let out = ctx.run(egui::RawInput::default(), |ctx| app.update(ctx, &mut frame));
        let tree = out.platform_output.accesskit_update.expect("the window tells screen readers what it shows");
        tree.nodes.iter().filter_map(|(_, n)| n.label().map(|l| (n.role(), l.to_string()))).collect()
    }

    fn has(said: &[(Role, String)], role: Role, name: &str) -> bool {
        said.iter().any(|(r, l)| *r == role && l == name)
    }

    /// The window's controls are named for screen readers where egui names none: the welcome cards, the search box,
    /// the Main page's tiles, Settings' symbol buttons.
    #[test]
    fn controls_are_named_for_screen_readers() {
        let mut app = App::new(vec![], Prefs::default());
        let said = spoken(&mut app);
        assert!(has(&said, Role::Button, "Explore a sample") && has(&said, Role::Button, "Open a settings file"), "{said:?}");
        app.open_sample_now();
        app.view = View::Main;
        let said = spoken(&mut app);
        assert!(has(&said, Role::TextInput, "Search settings, groups or values"), "{said:?}");
        let tile = app.schema.camera.main_tiles.as_ref().and_then(|t| t.0.first()).and_then(|s| s.tiles.first()).map(|t| t.caption.clone()).unwrap();
        assert!(said.iter().any(|(r, l)| *r == Role::Button && l.starts_with(&format!("{tile}: "))), "a Main tile: {said:?}");
        // Settings: the text size's − and + by what they do
        app.show_settings = true;
        let said = spoken(&mut app);
        assert!(has(&said, Role::Button, "Smaller text") && has(&said, Role::Button, "Larger text"), "{said:?}");
        assert!(said.iter().all(|(_, l)| !l.trim().is_empty()));
    }

    /// The status bar names the editor and its short version at its right end, on the welcome page and with a file open;
    /// a click on it, or on the version at the foot of Settings, opens About, which gives the version (and the build,
    /// when there is one), the cameras it works with, and the ways to the changes, the licences and a copy of the version.
    #[test]
    fn the_status_bar_version_opens_about() {
        use egui::accesskit::{Action as Ak, ActionRequest};
        let label = format!("Camset Editor {}", version_short());
        let mut app = App::new(vec![], Prefs::default());
        let said = spoken(&mut app);
        assert!(has(&said, Role::Button, &label), "on the welcome page: {said:?}");
        // the window run frame by frame; a label's words are its value, a control's its name
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut frame = eframe::Frame::_new_kittest();
        let mut run = |app: &mut App, events: Vec<egui::Event>| {
            let out = ctx.run(egui::RawInput { events, ..Default::default() }, |ctx| app.update(ctx, &mut frame));
            out.platform_output.accesskit_update.map(|t| t.nodes.iter().filter_map(|(id, n)| n.label().or(n.value()).map(|l| (*id, n.role(), l.to_string()))).collect::<Vec<_>>()).unwrap_or_default()
        };
        let _ = run(&mut app, vec![]);
        let said = run(&mut app, vec![]);
        assert!(said.iter().any(|(_, _, l)| *l == format!("Version {}", version_words())), "the welcome page's line: {said:?}");
        app.open_sample_now();
        let _ = run(&mut app, vec![]);
        let said = run(&mut app, vec![]);
        let hit: Vec<_> = said.iter().filter(|(_, r, l)| *l == label && *r == Role::Button).collect();
        assert_eq!(hit.len(), 1, "with a file open, one version in the status bar: {said:?}");
        assert!(!app.show_about);
        let _ = run(&mut app, vec![egui::Event::AccessKitActionRequest(ActionRequest { action: Ak::Click, target: hit[0].0, data: None })]);
        assert!(app.show_about, "a click on the version opens About");
        let _ = run(&mut app, vec![]);
        let said = run(&mut app, vec![]);
        let shows = |name: &str| said.iter().any(|(_, _, l)| l == name);
        assert!(shows("About Camset Editor") && shows(&format!("Version {}", version_short())) && shows(NOT_SONY), "{said:?}");
        assert_eq!(build_hash().is_some_and(|h| shows(&format!("Build {h}"))), build_hash().is_some(), "{said:?}");
        let models = app.defs.works_with();
        assert!(models.is_empty() || shows(&format!("Works with: {}", models.join(", "))), "{said:?}");
        for b in ["Changes", "Copy version"] {
            assert!(said.iter().any(|(_, r, l)| l == b && *r == Role::Button), "{b}: {said:?}");
        }
        assert!(said.iter().any(|(_, r, l)| l.starts_with("Third-party licences") && *r == Role::Button), "{said:?}");
        // About's Changes opens the changelog
        let changes: Vec<_> = said.iter().filter(|(_, r, l)| l == "Changes" && *r == Role::Button).collect();
        let _ = run(&mut app, vec![egui::Event::AccessKitActionRequest(ActionRequest { action: Ak::Click, target: changes[0].0, data: None })]);
        assert!(app.show_changes && app.show_about);
        // the version at the foot of Settings (the whole of it) opens About too
        let bar = hit[0].0;
        (app.show_about, app.show_changes, app.show_settings) = (false, false, true);
        let _ = run(&mut app, vec![]);
        let said = run(&mut app, vec![]);
        let foot: Vec<_> = said.iter().filter(|(id, r, l)| *l == format!("Camset Editor {}", version_words()) && *r == Role::Button && *id != bar).collect();
        assert_eq!(foot.len(), 1, "the foot of Settings: {said:?}");
        let _ = run(&mut app, vec![egui::Event::AccessKitActionRequest(ActionRequest { action: Ak::Click, target: foot[0].0, data: None })]);
        assert!(app.show_about, "the version at the foot of Settings opens About");
    }

    /// Compare's setting names are links, "Open … in Edit": Edit then shows that setting in file A's set (the live
    /// settings for one the memories do not keep; a family's member in its family's table) with "← Back to Compare",
    /// which returns to Compare with that row under the difference cursor. Once the person goes elsewhere it is gone.
    #[test]
    fn compare_opens_a_setting_in_edit_and_comes_back() {
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        app.mode = Mode::Compare;
        app.cols = vec![Col::a(0), Col::a(1)];
        app.matrix_only_diff = false;
        let rows = app.matrix_rows();
        let at = rows.iter().position(|r| r.2[0].in_sets && app.schema.camera.families.iter().all(|f| f.prefix.is_empty() || !r.1.starts_with(&f.prefix))).unwrap();
        let s = rows[at].2[0].clone();
        let said = spoken(&mut app);
        assert!(has(&said, Role::Button, &format!("Open {} in Edit", rows[0].2[0].name)), "{said:?}");
        // Open in Edit (the name, or a value of A · Memory 1): that setting, in that set
        app.only_changed = true;
        app.open_in_edit_from_compare(&s, 1);
        assert!(app.mode == Mode::Edit && app.target == 1 && app.view == View::Tab(s.tab.clone()) && !app.only_changed);
        assert_eq!((app.group.as_deref(), app.item.as_deref()), (Some(s.group.as_str()), Some(s.name.as_str())));
        let said = spoken(&mut app);
        assert!(has(&said, Role::Button, "← Back to Compare"), "{said:?}");
        assert!(app.from_compare.is_some() && app.item.as_deref() == Some(s.name.as_str()), "Edit kept the setting it was given");
        // back: Compare, with the row under the cursor
        app.back_to_compare();
        let _ = spoken(&mut app);
        assert!(app.mode == Mode::Compare && app.from_compare.is_none() && app.compare_row_to.is_none());
        assert_eq!(app.diff_cursor, Some(at));
        // gone once the person goes elsewhere on their own, and not back when they return
        app.open_in_edit_from_compare(&s, 0);
        let other = rows.iter().find(|r| r.0 == s.tab && r.1 == s.group && r.2[0].name != s.name).map(|r| r.2[0].name.clone());
        if let Some(other) = other {
            app.item = Some(other);
            let _ = spoken(&mut app);
            assert!(app.from_compare.is_none());
            app.item = Some(s.name.clone());
            let said = spoken(&mut app);
            assert!(!has(&said, Role::Button, "← Back to Compare"));
        }
        // a setting the memories do not keep opens in the live settings
        let live = rows.iter().find(|r| !r.2[0].in_sets).map(|r| r.2[0].clone()).unwrap();
        app.open_in_edit_from_compare(&live, 1);
        assert_eq!(app.target, 0);
        // a family's member opens its family's table, by the family's title; as on the camera one on the page an
        // option opens (a profile's parameter) opens that page
        if let Some((f, m)) = app.schema.camera.families.iter().filter(|f| !f.prefix.is_empty())
            .find_map(|f| rows.iter().find(|r| r.1.starts_with(&f.prefix)).map(|r| (f.title.clone(), r.2[0].clone()))) {
            let f = if app.camera_layout() && m.on_page() { m.group.clone() } else { f };
            app.open_in_edit_from_compare(&m, 0);
            assert_eq!(app.group.as_deref(), Some(f.as_str()));
            let _ = spoken(&mut app);
            assert!(app.from_compare.is_some() && app.group.as_deref() == Some(f.as_str()), "Edit shows the family's table");
        }
    }

    /// Compare changes a value of file A in place: its picker (a click on the cell, or "Change…") lists the values the
    /// detail panel offers, and the one chosen goes through the same actions as Edit's: every linked record of the row
    /// set, marked as an edit, undone and redone, and put back with the picker's Revert. The row stays shown, and
    /// where it was, once it no longer differs. File B (and the base) never take a value.
    #[test]
    fn compare_changes_a_value_of_file_a_in_place() {
        use egui::accesskit::{Action as Ak, ActionRequest};
        let mut app = App::new(vec![], Prefs::default());
        app.open_sample_now();
        let b = app.doc.as_ref().unwrap().edited.clone();
        app.compare = Some((PathBuf::from("B.DAT"), b));
        app.mode = Mode::Compare;
        app.cols = vec![Col::a(0), Col::b(0)];
        app.matrix_only_diff = false;
        let rows = app.matrix_rows();
        // a row of named values with no option tree, among the first on screen, kept in several records when one is
        let fits = |r: &&(String, String, Vec<Setting>)| {
            let s = &r.2[0];
            app.cell_editable(Col::a(0), &r.2) && s.range.is_none() && s.text.is_none() && s.option_tree().is_none() && s.offered(false).len() >= 2
        };
        let row = rows.iter().take(150).filter(fits).find(|r| r.2.len() > 1).or_else(|| rows.iter().find(fits)).cloned().expect("a row of named values");
        let (tab, linked) = (row.0.clone(), row.2.clone());
        let s = linked[0].clone();
        assert!(!app.cell_editable(Col::b(0), &linked), "file B is read-only");
        assert!(!app.cell_editable(Col::base(0), &linked), "the base is read-only");
        let was = app.doc.as_ref().unwrap().value(0, s.slot());
        let (other, label) = s.offered(false).into_iter().find(|(v, _)| Some(*v) != was).unwrap();
        // the window run frame by frame, the picker open, a screen reader's click on an option
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut frame = eframe::Frame::_new_kittest();
        let mut run = |app: &mut App, events: Vec<egui::Event>| {
            let out = ctx.run(egui::RawInput { events, ..Default::default() }, |ctx| app.update(ctx, &mut frame));
            out.platform_output.accesskit_update.map(|t| t.nodes.iter().filter_map(|(id, n)| n.label().map(|l| (*id, n.role(), l.to_string()))).collect::<Vec<_>>()).unwrap_or_default()
        };
        let click = |said: &[(egui::accesskit::NodeId, Role, String)], name: &str| {
            let hit: Vec<_> = said.iter().filter(|(_, r, l)| l == name && *r != Role::Label).collect();
            assert_eq!(hit.len(), 1, "{name}: {said:?}");
            vec![egui::Event::AccessKitActionRequest(ActionRequest { action: Ak::Click, target: hit[0].0, data: None })]
        };
        let id = App::picker_id(&s, 0);
        let _ = run(&mut app, vec![]);
        ctx.memory_mut(|m| m.open_popup(id));
        let said = run(&mut app, vec![]);
        assert!(said.iter().any(|(_, _, l)| *l == label), "the picker offers {label} for {}: {said:?}", s.name);
        let _ = run(&mut app, click(&said, &label));
        let _ = run(&mut app, vec![]);
        let doc = app.doc.as_ref().unwrap();
        assert_eq!(doc.value(0, s.slot()), Some(other), "{}", app.status);
        for a in App::set_linked(0, &linked, other) {
            if let Action::Set(si, slot, v) = a { assert_eq!(doc.value(si, slot), Some(v), "every linked record set together"); }
        }
        assert!(app.row_info(&app.cols.clone(), None, &s).edited[0], "marked as an edit");
        assert_eq!(app.col_value(Col::b(0), &s), was, "file B unchanged");
        assert!(!ctx.memory(|m| m.is_popup_open(id)), "a final choice closes the picker");
        assert_eq!(app.cmp_kept, Some((tab.clone(), s.key.clone())));
        // undone and redone as any edit
        app.undo();
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), was);
        app.redo();
        assert_eq!(app.doc.as_ref().unwrap().value(0, s.slot()), Some(other));
        // only the rows that differ: this one, then still this one once Revert in the picker puts it back
        app.matrix_only_diff = true;
        let _ = run(&mut app, vec![]);
        assert_eq!(app.mm_rows.len(), 1);
        ctx.memory_mut(|m| m.open_popup(id));
        let said = run(&mut app, vec![]);
        let _ = run(&mut app, click(&said, "Revert"));
        let _ = run(&mut app, vec![]);
        assert!(linked.iter().all(|l| { let d = app.doc.as_ref().unwrap(); d.value(0, l.slot()) == d.original_value(0, l.slot()) }), "reverted");
        assert_eq!(app.mm_rows.len(), 1, "the row changed in Compare stays where it was");
        app.cmp_kept = None;
        let _ = run(&mut app, vec![]);
        assert!(app.mm_rows.is_empty(), "it was kept for that");
        // a column of file B never draws the picker: its cell does not take values
        app.cols = vec![Col::b(0), Col::a(1)];
        app.matrix_only_diff = false;
        let _ = run(&mut app, vec![]);
        ctx.memory_mut(|m| m.open_popup(id));
        let said = run(&mut app, vec![]);
        assert!(!said.iter().any(|(_, _, l)| *l == label), "{said:?}");
    }
}
