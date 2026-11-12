//! Small pieces of the window used everywhere: names for screen readers, a drawn area as a button, and the
//! camera tables' cells.

use crate::*;

/// A serial number or MAC address cell: the value, or a weak "not yet known" that says `why` on hover.
pub(crate) fn id_cell(ui: &mut egui::Ui, value: &str, why: &str) {
    if value.trim().is_empty() {
        ui.label(RichText::new("not yet known").small().color(tone::weak(ui.visuals()))).on_hover_text(why);
    } else {
        ui.label(RichText::new(value).monospace().small());
    }
}

/// How wide the name field of the camera tables is (`name_field`): room for about 22 characters, so the found-cameras
/// table, its longest Link cell included, fits the Connect and Settings windows at their default width
/// (`found_table_fits_its_windows`).
const NAME_FIELD_W: f32 = 160.0;

/// The person's own name for a camera, as a text field of `NAME_FIELD_W` points that takes up to 60 characters (a
/// longer name scrolls inside it). It keeps its width whatever else the row holds: in a table, a crowded row widens
/// the table (which then scrolls sideways) instead of shrinking the box.
pub(crate) fn name_field(ui: &mut egui::Ui, salt: impl std::hash::Hash, name: &mut String, enabled: bool) -> egui::Response {
    let field = egui::TextEdit::singleline(name).hint_text(RichText::new("e.g. Studio camera").color(tone::weak(ui.visuals()))).char_limit(60).desired_width(NAME_FIELD_W).id_salt(salt);
    named(ui.add_sized([NAME_FIELD_W, ui.spacing().interact_size.y], |ui: &mut egui::Ui| ui.add_enabled(enabled, field)), "Your name for this camera")
}

/// Name a control for screen readers (egui's accesskit) where egui gives it no name of its own: a text field, a
/// number field, a button that shows only a symbol. Its role and value stay as egui set them.
pub(crate) fn named(resp: egui::Response, name: &str) -> egui::Response {
    resp.ctx.accesskit_node_builder(resp.id, |node| node.set_label(name));
    resp
}

/// A drawn area that acts as a button (a welcome card, a Main page tile, a copy arrow, the minimap): a button named
/// `name` to screen readers.
pub(crate) fn as_button(resp: egui::Response, name: &str) -> egui::Response {
    resp.widget_info(|| egui::WidgetInfo::labeled(egui::WidgetType::Button, resp.enabled(), name));
    resp
}
