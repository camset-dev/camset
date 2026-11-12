//! The status line under the window, the log of its last messages, and the toast a warning shows as.

use crate::*;

/// How many status messages the log keeps.
pub(crate) const STATUS_LOG: usize = 20;

/// How long a toast stays.
const TOAST_SECS: u64 = 12;

/// A status message that matters enough to show as a toast as well: a warning, a failure, a refusal.
fn is_warning(msg: &str) -> bool {
    let m = msg.to_lowercase();
    ["warning", "failed", "not saved", "could not", "nothing written", "nothing read", "refusing", "not found", "cannot", "⚠", "✖"]
        .iter().any(|w| m.contains(w))
}

impl App {
    /// A time stamp in words (`when_words`), with the stamp itself after it in Expert mode.
    pub(crate) fn stamp_words(&self, stamp: &str) -> String {
        stamp_in_words(stamp, self.prefs.expert)
    }

    /// How the camera definition names the header checksum, for messages.
    pub(crate) fn header_checksum_name(c: &CamSet) -> String {
        format!("header checksum ({})", c.format().header_checksum.kind.name())
    }

    /// Keep a new status message in the log (the last `STATUS_LOG`), and show it as a toast when it matters.
    pub(crate) fn log_status(&mut self) {
        if self.status == self.status_seen { return; }
        self.status_seen = self.status.clone();
        if self.status.trim().is_empty() { return; }
        self.status_log.push((when_words(&local_stamp()), self.status.clone()));
        if self.status_log.len() > STATUS_LOG { self.status_log.remove(0); }
        if is_warning(&self.status) { self.toast = Some((self.status.clone(), std::time::Instant::now())); }
    }

    /// The status line: the last message on up to two lines (all of it on hover); a click opens the last messages.
    pub(crate) fn status_line(&mut self, ui: &mut egui::Ui, width: f32) {
        let mut job = egui::text::LayoutJob::single_section(self.status.clone(), egui::TextFormat::simple(
            egui::TextStyle::Body.resolve(ui.style()), ui.visuals().text_color()));
        job.wrap = egui::text::TextWrapping { max_width: width.max(80.0), max_rows: 2, break_anywhere: false, overflow_character: Some('…') };
        let galley = ui.fonts(|f| f.layout_job(job));
        let cut = galley.elided;
        let r = ui.add(egui::Label::new(galley).sense(egui::Sense::click()));
        let r = if cut { r.on_hover_text(format!("{}\n\nClick for the last messages.", self.status)) } else { r.on_hover_text("Click for the last messages.") };
        if r.clicked() { self.show_log = !self.show_log; }
    }

    /// The last status messages, newest first.
    pub(crate) fn log_window(&mut self, ctx: &egui::Context) {
        if !self.show_log { return; }
        let mut open = true;
        let mut clear = false;
        egui::Window::new("Messages").open(&mut open).resizable(true).default_width(620.0).show(ctx, |ui| {
            if self.status_log.is_empty() { ui.label("No messages yet."); }
            egui::ScrollArea::vertical().max_height(360.0).show(ui, |ui| {
                egui::Grid::new("status_log").striped(true).num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
                    for (at, msg) in self.status_log.iter().rev() {
                        ui.label(RichText::new(at).color(tone::weak(ui.visuals())).monospace());
                        let t = RichText::new(msg);
                        ui.add(egui::Label::new(if is_warning(msg) { t.color(tone::caution(ui.visuals())) } else { t }).wrap());
                        ui.end_row();
                    }
                });
            });
            if !self.status_log.is_empty() && ui.small_button("Clear").clicked() { clear = true; }
        });
        if clear { self.status_log.clear(); }
        if !open { self.show_log = false; }
    }

    /// A message that matters, in a corner over the window for a while (`TOAST_SECS`), with the way to the log.
    pub(crate) fn toast_ui(&mut self, ctx: &egui::Context) {
        let Some((msg, at)) = self.toast.clone() else { return };
        let left = std::time::Duration::from_secs(TOAST_SECS).saturating_sub(at.elapsed());
        if left.is_zero() { self.toast = None; return; }
        ctx.request_repaint_after(left);
        let (mut close, mut log) = (false, false);
        egui::Area::new(egui::Id::new("toast")).anchor(egui::Align2::RIGHT_BOTTOM, egui::vec2(-16.0, -44.0)).order(egui::Order::Foreground).show(ctx, |ui| {
            egui::Frame::popup(ui.style()).show(ui, |ui| {
                ui.set_max_width(440.0);
                ui.add(egui::Label::new(RichText::new(&msg).color(tone::caution(ui.visuals()))).wrap());
                ui.horizontal(|ui| {
                    if ui.small_button("Messages…").clicked() { log = true; }
                    if ui.small_button("Close").clicked() { close = true; }
                });
            });
        });
        if log { self.show_log = true; }
        if close || log { self.toast = None; }
    }
}

#[cfg(test)]
pub(crate) mod status_log_tests {
    use super::*;

    /// The log keeps the last messages once each; a warning also becomes a toast, a plain message does not.
    #[test]
    fn last_messages_kept_and_warnings_toasted() {
        let mut app = App::new(vec![], Prefs::default());
        for i in 0..30 {
            app.status = format!("Message {i}");
            app.log_status();
            app.log_status();
        }
        assert_eq!(app.status_log.len(), STATUS_LOG);
        assert_eq!(app.status_log.last().map(|m| m.1.as_str()), Some("Message 29"));
        assert_eq!(app.status_log.first().map(|m| m.1.as_str()), Some("Message 10"));
        assert!(app.toast.is_none());
        app.status = "Saved CAMSET02.DAT with 1 change(s) (warning: 11 settings files in that folder; the camera lists only 10)".into();
        app.log_status();
        assert!(app.toast.as_ref().is_some_and(|t| t.0.contains("only 10")));
        assert!(!is_warning("Opened CAMSET01.DAT"));
        assert!(is_warning("Save failed: the card is full"));
    }
}
