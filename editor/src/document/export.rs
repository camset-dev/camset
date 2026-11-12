//! What the editor exports: the CSV of a set or of Compare's columns, and the layout of a file for support.

use crate::*;

/// A spreadsheet cell of the CSV export: quoted, its quotes doubled. A text a spreadsheet would take for a formula
/// (starting with =, +, -, @, a tab or a carriage return, as a copyright or artist text from a shared file may) gets
/// a ' in front, so it stays text; a plain number ("-0.3") is left as it is.
fn csv_cell(t: &str) -> String {
    // a sign, digits, and at most one point with digits on both sides
    let number = |s: &str| {
        let s = s.strip_prefix(['+', '-']).unwrap_or(s);
        let (int, frac) = s.split_once('.').unwrap_or((s, "0"));
        !int.is_empty() && !frac.is_empty() && int.chars().chain(frac.chars()).all(|c| c.is_ascii_digit())
    };
    let formula = t.starts_with(['=', '+', '-', '@', '\t', '\r']) && !number(t);
    let t = if formula { format!("'{t}") } else { t.to_string() };
    format!("\"{}\"", t.replace('"', "\"\""))
}

impl App {
    /// Write the settings as a spreadsheet-friendly CSV (export only: the camera file is never
    /// built from a CSV, so a stray edit in a spreadsheet cannot corrupt a settings file).
    /// Edit mode: the set being edited, one row per setting (with file B's value when loaded).
    /// Compare mode: the rows and columns currently shown.
    pub(crate) fn export_csv(&mut self, ctx: &egui::Context) {
        let Some(doc) = &self.doc else { return };
        let stem = doc.path.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| "CAMSET".into());
        let suggested = if self.mode == Mode::Compare { format!("{stem}_compare.csv") } else { format!("{stem}_{}.csv", self.schema.camera.target_name(self.target).replace(' ', "_").to_lowercase()) };
        self.ask(ctx, DialogKind::ExportCsv, Some(suggested));
    }

    /// Write the CSV export as `p`, the name the Export CSV dialog gave: Compare mode's columns as shown, or Edit
    /// mode's set with the search and Only edited.
    pub(crate) fn export_csv_to(&mut self, p: PathBuf) {
        if self.doc.is_none() { return; }
        let compare = (self.mode == Mode::Compare && self.cols.len() >= 2).then_some((self.cols.as_slice(), self.matrix_only_diff, self.show_raw));
        let tab = if compare.is_some() { self.compare_tab.as_deref() } else { None };
        let (text, n) = self.csv_text(compare, self.target, &self.search, tab, self.only_changed);
        match std::fs::write(&p, text) {
            Ok(_) => self.status = format!("Exported {n} rows to {}", p.display()),
            Err(e) => self.status = format!("Not exported: {}{}", io_words(&e, true), details(self.prefs.expert, format_args!("{}: {e}", p.display()))),
        }
    }

    /// The CSV export and its number of rows. `compare`: the columns (the first is the baseline), only the rows that
    /// differ, raw values beside the labels; else the settings of set `target`. `q` is a search as the search box
    /// takes it, `tab` the compare's tab filter, `only_changed` Edit mode's Only edited.
    pub(crate) fn csv_text(&self, compare: Option<(&[Col], bool, bool)>, target: usize, q: &str, tab: Option<&str>, only_changed: bool) -> (String, usize) {
        let Some(doc) = &self.doc else { return (String::new(), 0) };
        let quote = csv_cell;
        let mut lines: Vec<String> = Vec::new();
        let mut n = 0;
        if let Some((cols, only_diff, raw)) = compare.filter(|(cols, _, _)| cols.len() >= 2) {
            let base = cols[0];
            let mut head = vec!["Tab".to_string(), "Group".into(), "Setting".into(), "Record".into()];
            head.extend(cols.iter().map(|c| quote(&self.col_name_with_file(*c))));
            lines.push(head.join(","));
            for (tab, group, linked) in self.matrix_rows_for(q, tab) {
                let s = &linked[0];
                let b = self.col_value(base, s);
                let differs = cols[1..].iter().any(|c| (c.section == 0 || s.in_sets) && self.col_value(*c, s) != b);
                if only_diff && !differs {
                    continue;
                }
                let mut row = vec![quote(&tab), quote(&group), quote(&s.name), format!("0x{:04x}", s.id)];
                for c in cols {
                    let stored = c.section == 0 || s.in_sets;
                    let v = self.col_value(*c, s);
                    let text = if !stored { String::new() } else if s.text.is_some() { self.col_text(*c, s).unwrap_or_default() } else { Self::describe(s, v) };
                    row.push(quote(&if raw && stored { format!("{text} [{}]", v.map(|v| v.to_string()).unwrap_or_default()) } else { text }));
                }
                lines.push(row.join(","));
                n += 1;
            }
        } else {
            let mut head = vec!["Tab".to_string(), "Group".into(), "Setting".into(), "Record".into(), "Value".into(), "Raw".into(), "Original".into()];
            head.push("Note".into());
            lines.push(head.join(","));
            let tab_idx = |t: &str| self.schema.tabs.iter().position(|x| x == t).unwrap_or(99);
            let q = q.to_lowercase();
            let mut list: Vec<&Setting> = self.settings_in(target, None)
                .filter(|s| q.is_empty() || Self::matches_query(s, &q))
                .filter(|s| !only_changed || doc.value(target, s.slot()) != doc.original_value(target, s.slot()))
                .collect();
            list.sort_by_key(|s| (tab_idx(&s.tab), s.order));
            let mut seen: Vec<(String, String)> = Vec::new();
            for s in list {
                if seen.contains(&(s.tab.clone(), s.name.clone())) {
                    continue; // linked copies of one setting: one row
                }
                seen.push((s.tab.clone(), s.name.clone()));
                let cur = doc.value(target, s.slot());
                let orig = doc.original_value(target, s.slot());
                let value = match s.text {
                    Some(_) => doc.edited.sections.get(target).and_then(|sec| sec.get(s.id)).and_then(|r| r.text()).unwrap_or_default(),
                    None => Self::describe(s, cur),
                };
                let mut row = vec![quote(&s.tab), quote(&s.group), quote(&s.name), format!("0x{:04x}", s.id), quote(&value),
                                   cur.map(|v| v.to_string()).unwrap_or_default(), quote(&if cur != orig { Self::describe(s, orig) } else { String::new() })];
                row.push(quote(&s.note));
                lines.push(row.join(","));
                n += 1;
            }
        }
        // a byte-order mark so Excel opens the file as UTF-8
        (format!("\u{feff}{}\n", lines.join("\n")), n)
    }

    /// Ask where to save a file's record layout (`layout_json`); `on_dialog` writes it.
    pub(crate) fn export_layout(&mut self, ctx: &egui::Context, layout: String) {
        self.ask(ctx, DialogKind::ExportLayout(layout), Some("camera_layout.json".into()));
    }

    /// A file's record layout (ids and shapes, no values) as JSON, so support for its firmware
    /// can be added.
    pub(crate) fn layout_json(c: &CamSet) -> String {
        let sections: Vec<serde_json::Value> = c.sections.iter().map(|s| serde_json::json!({
            "records": s.records.iter().map(|r| serde_json::json!([r.id, r.elem_size, r.count])).collect::<Vec<_>>()
        })).collect();
        let doc = serde_json::json!({
            "model": c.model(),
            "timestamp": c.timestamp(),
            "firmware": c.firmware(),
            "firmware_bytes": c.firmware_bytes().iter().map(|b| format!("{b:02x}")).collect::<String>(),
            "video_system": c.video_system().map(|(v, name)| serde_json::json!({ "byte": format!("{v:02x}"), "name": name })),
            "header_checksum_ok": c.header_checksum_ok(),
            "trailer_checksum_ok": c.trailer_checksum_ok(),
            "signature": c.layout_signature(),
            "sections": sections,
        });
        serde_json::to_string_pretty(&doc).unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// E-29: a CSV cell a spreadsheet would take for a formula stays text; numbers and plain words are as they were.
    #[test]
    fn csv_cells_never_formulas() {
        assert_eq!(csv_cell("=HYPERLINK(\"http://x\",\"y\")"), "\"'=HYPERLINK(\"\"http://x\"\",\"\"y\"\")\"");
        for t in ["+1+cmd", "-2+3", "@SUM(A1)", "\tx", "\rx", "+0.3 EV", "-", "-1.", "+.5"] {
            assert!(csv_cell(t).starts_with("\"'"), "{t}");
        }
        for t in ["-0.3", "+1.0", "42", "-7", "ISO 50", "Off", "", "a=b"] {
            assert_eq!(csv_cell(t), format!("\"{t}\""), "{t}");
        }
    }
}
