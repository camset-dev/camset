//! Connect to the camera, and Settings > Camera link: the same camera cards in both (the link and the search, the
//! setup steps, the known cameras, the network address and login, the camera link program).

use crate::*;

/// What the found-cameras table did this frame.
#[derive(Default)]
pub(crate) struct GridOutcome {
    /// The row picked with "Use this one".
    pub(crate) pick: Option<Discovered>,
    /// A name was typed: the known cameras changed.
    pub(crate) renamed: bool,
    /// A name field was left: the time to copy names into the credentials file.
    pub(crate) name_done: bool,
}

/// The "Cameras found" table: one row per camera the helper listed, with "Use this one" first, so it shows at any
/// window width without scrolling, then the person's own name for it (saved into the known cameras as typed), its
/// serial number and its MAC address (the row's, else the known camera's). The whole table fits the Connect and
/// Settings windows at their default width; a table still wider than the window scrolls sideways.
/// `expert`: Expert mode is on (an empty Serial cell's hover then names the raw id the search sent).
pub(crate) fn discovered_grid(ui: &mut egui::Ui, id: &str, found: &[Discovered], cams: &mut Vec<KnownCamera>, expert: bool) -> GridOutcome {
    let mut out = GridOutcome::default();
    egui::ScrollArea::horizontal().id_salt((id, "scroll")).auto_shrink([true, true]).show(ui, |ui| {
        egui::Grid::new(id).striped(true).num_columns(6).spacing([14.0, 4.0]).show(ui, |ui| {
            ui.strong("");
            ui.strong("Model");
            ui.strong("Link");
            ui.strong("Your name").on_hover_text("Your own name for this camera; the editor names it so wherever it names the camera");
            ui.strong("Serial").on_hover_text("The body's serial number: a USB camera sends it, a network camera tells it when the editor first connects");
            ui.strong("MAC address").on_hover_text("The camera's network card: the search sends it, or for a camera answered at its address, this computer's network table. Each camera's user name and password are kept under it");
            ui.end_row();
            for (row, d) in found.iter().enumerate() {
                let k = known_index(cams, d);
                if ui.button("Use this one").clicked() { out.pick = Some(d.clone()); }
                let model = ui.label(&d.model);
                if !d.name.trim().is_empty() { model.on_hover_text(format!("The camera's own name for itself: {}", d.name.trim())); }
                let (link, by_address) = d.link_lines();
                match by_address {
                    Some(second) => {
                        ui.vertical(|ui| {
                            ui.add(egui::Label::new(link).extend()).on_hover_text(d.link_hover());
                            ui.add(egui::Label::new(RichText::new(second).small().color(tone::weak(ui.visuals()))).extend()).on_hover_text(d.link_hover());
                        });
                    }
                    None => {
                        let r = ui.label(link);
                        if expert { r.on_hover_text(d.link_hover()); }
                    }
                }
                let mut name = k.map(|i| cams[i].name.clone()).unwrap_or_default();
                let can_name = k.is_some() || !d.serial().is_empty() || !norm_mac(&d.mac).is_empty() || d.is_network();
                let r = name_field(ui, (id, "name", row), &mut name, can_name);
                if r.changed() {
                    let i = k.unwrap_or_else(|| remember_camera(cams, &d.as_known(&local_stamp())));
                    cams[i].name = name;
                    out.renamed = true;
                }
                out.name_done |= r.lost_focus();
                let serial = if d.serial().is_empty() { k.map(|i| cams[i].serial.clone()).unwrap_or_default() } else { d.serial().to_string() };
                id_cell(ui, &serial, &serial_why(d, expert));
                let mac = Some(norm_mac(&d.mac)).filter(|m| !m.is_empty()).or_else(|| k.map(|i| norm_mac(&cams[i].mac))).unwrap_or_default();
                id_cell(ui, &mac, if d.by_address() { "This computer's network table held no MAC address for the camera's address. Learned when the editor first connects to it" } else { LEARNED_ON_CONNECT });
                ui.end_row();
            }
        });
    });
    out
}

/// What the camera cards did this frame, for the window that shows them to act on (`App::camera_cards_done`).
#[derive(Default)]
pub(crate) struct CameraCardsOutcome {
    /// A preference changed: the preferences are saved.
    pub(crate) changed: bool,
    /// "Search for cameras" was pressed.
    pub(crate) search: bool,
    /// The found camera picked with "Use this one".
    pub(crate) picked: Option<Discovered>,
    /// A name field was left: the time to copy names into the credentials file.
    pub(crate) names_done: bool,
    /// Save was pressed beside the user name and password.
    pub(crate) save_creds: bool,
    /// The known camera to forget.
    pub(crate) forget: Option<usize>,
}

impl App {
    /// What the camera link program is and how to get it, with a link to Sony's SDK page and a button to choose
    /// the program once built (the camera cards, when it is not found).
    fn helper_howto_ui(&mut self, ui: &mut egui::Ui) {
        ui.label("Reading from and writing to the camera go through the camera link program. It is not in the editor's download: you build it yourself from Sony's Camera Remote SDK, which Sony gives out free under its own agreement.");
        ui.add_space(2.0);
        ui.label("Put the SDK's zip into kit/sdk/ in the Camset folder and run python3 kit/setup.py: it builds the program, and the editor finds it there. Or choose the program below once it is built.");
        ui.add_space(2.0);
        ui.label(RichText::new("Without it, everything else works: copy settings files from the camera's card, edit them, and copy them back.").color(tone::weak(ui.visuals())));
        ui.horizontal(|ui| {
            ui.hyperlink_to("Sony's Camera Remote SDK page", "https://support.d-imaging.sony.co.jp/app/sdk/l/index.php");
            if ui.button("Choose the program…").clicked() {
                self.ask(ui.ctx(), DialogKind::ProbePath, None);
            }
        });
    }

    /// The helper's own words about the last search: in Expert mode only, else a note that they are there. In Expert
    /// mode a failed search's words are its whole output, shown under Details from the camera link
    /// (`discover_text_ui`), and not twice.
    fn discover_detail_ui(&self, ui: &mut egui::Ui) {
        if self.discover_detail.is_empty() { return; }
        if self.prefs.expert {
            if self.discover_detail != self.discover_text {
                ui.add(egui::Label::new(RichText::new(&self.discover_detail).monospace().small().color(tone::weak(ui.visuals()))).wrap());
            }
        } else {
            ui.label(RichText::new(EXPERT_LINK_NOTE).small().color(tone::weak(ui.visuals())));
        }
    }

    /// The helper's whole output from the last search, every row it sent included (the raw `id_hex` the serial
    /// number is read from): in Expert mode only, folded under the found table.
    fn discover_text_ui(&self, ui: &mut egui::Ui) {
        if !self.prefs.expert || self.discover_text.is_empty() { return; }
        egui::CollapsingHeader::new("Details from the camera link").id_salt("discover_text").show(ui, |ui| {
            egui::ScrollArea::vertical().id_salt("discover_text_scroll").max_height(240.0).show(ui, |ui| {
                ui.add(egui::Label::new(RichText::new(&self.discover_text).monospace().small().color(tone::weak(ui.visuals()))).wrap());
            });
        });
    }

    /// The setup steps follow `steps_open` when its value changes (a camera found or known folds them, none left opens
    /// them); otherwise they stay as they are.
    pub(crate) fn follow_steps_rule(&mut self) {
        let rule = steps_open(self.prefs.cameras.len(), self.discovered.len());
        if rule != self.steps_rule {
            self.steps_rule = rule;
            self.steps_shown = rule;
        }
    }

    /// The setup steps for the chosen link, from the camera definition (generic ones when it has none), each with a
    /// box to tick.
    fn setup_steps_ui(&mut self, ui: &mut egui::Ui) {
        let (steps, note) = self.setup_steps();
        if self.connect_checks.len() < steps.len() { self.connect_checks.resize(steps.len(), false); }
        for (i, step) in steps.iter().enumerate() {
            ui.checkbox(&mut self.connect_checks[i], step.as_str());
        }
        if let Some(n) = note.filter(|n| !n.is_empty()) {
            ui.label(RichText::new(n).small().color(tone::weak(ui.visuals())));
        }
    }

    /// The setup steps for the chosen link and the note under them: the camera definition's, else generic ones
    /// (the window's camera cards and the web page's).
    pub(crate) fn setup_steps(&self) -> (Vec<String>, Option<String>) {
        let net = self.prefs.link == "network";
        let txt = &self.schema.camera.text;
        let steps: Vec<String> = match (net, &txt.connect_network_steps, &txt.connect_usb_steps) {
            (true, n, _) if !n.is_empty() => n.clone(),
            (false, _, u) if !u.is_empty() => u.clone(),
            (true, _, _) => ["If a USB cable joins the camera to a computer, unplug it first.",
                "Connect the camera to the same network as this computer (wired LAN or Wi-Fi).",
                "Turn on the camera's network remote control.",
                "If the camera asks for access authentication, set a user name and password on it and enter the same pair once in the desktop app's Connect to the camera.",
                "Leave the camera on the shooting screen."].map(String::from).to_vec(),
            (false, _, _) => ["Put the camera in PC Remote mode.", "Put a memory card in the camera.",
                "Connect the cable and quit any other program that may hold the camera.",
                "Leave the camera on the shooting screen."].map(String::from).to_vec(),
        };
        let note = if net { txt.connect_network_note.clone() } else { None };
        (steps, note)
    }

    /// The camera cards, the same in Settings > Camera and in Connect to the camera: the link and the search, the
    /// setup steps (folded once a camera is known, open again after a search that finds nothing), the known cameras,
    /// the network address and login (network only) and the camera link helper. The window that shows them acts on
    /// what they did with `camera_cards_done`.
    pub(crate) fn camera_cards(&mut self, ui: &mut egui::Ui) -> CameraCardsOutcome {
        let mut out = CameraCardsOutcome::default();
        let busy = self.camera_job.is_some();
        if !self.have_helper() {
            Self::settings_card(ui, "First: the camera link program", |ui| self.helper_howto_ui(ui));
        }
        Self::settings_card(ui, "Connection", |ui| {
            ui.horizontal(|ui| {
                ui.label("Connection method:");
                let mut net = self.prefs.link == "network";
                let was = net;
                if ui.radio_value(&mut net, false, "USB cable").clicked() { out.changed = true; }
                if ui.radio_value(&mut net, true, "Network (wired LAN or Wi-Fi)").clicked() { out.changed = true; }
                if net != was { self.connect_checks.clear(); }
                self.prefs.link = if net { "network".into() } else { "usb".into() };
            });
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                if ui.add_enabled(!busy && self.have_helper(), egui::Button::new("🔍 Search for cameras")).on_disabled_hover_text("Needs the camera link program: see the first card").on_hover_text(search_tip()).clicked() {
                    out.search = true;
                }
                if busy { ui.spinner(); }
            });
            if !self.discover_msg.is_empty() {
                ui.add(egui::Label::new(RichText::new(&self.discover_msg).small().color(tone::weak(ui.visuals()))).wrap());
            }
            self.discover_detail_ui(ui);
            if !self.discovered.is_empty() {
                ui.add_space(4.0);
                let g = discovered_grid(ui, "discovered", &self.discovered, &mut self.prefs.cameras, self.prefs.expert);
                out.changed |= g.renamed;
                out.names_done |= g.name_done;
                out.picked = g.pick;
                let name = self.found_name();
                let said = if name.is_empty() { "Camera found: the setup is complete.".to_string() } else { format!("{name} found: the setup is complete.") };
                ui.label(RichText::new(said).color(tone::ok(ui.visuals())));
            }
            self.discover_text_ui(ui);
        });

        self.follow_steps_rule();
        let mut shown = self.steps_shown;
        Self::settings_card_folding(ui, "Set the camera up like this", &mut shown, |ui| self.setup_steps_ui(ui));
        self.steps_shown = shown;

        Self::settings_card(ui, "Known cameras", |ui| {
            if self.prefs.cameras.is_empty() {
                ui.label(RichText::new("None yet. The editor remembers a camera when you pick it after a search, or when it connects to it.").small().color(tone::weak(ui.visuals())));
                return;
            }
            ui.label(RichText::new("Give each camera a name of your own. Each camera's user name and password are kept separately, under its MAC address.").small().color(tone::weak(ui.visuals())));
            ui.add_space(4.0);
            egui::ScrollArea::horizontal().id_salt("known_cameras_scroll").auto_shrink([true, true]).show(ui, |ui| {
                egui::Grid::new("known_cameras").striped(true).num_columns(7).spacing([12.0, 4.0]).show(ui, |ui| {
                    for h in ["Your name", "Model", "Serial", "MAC address", "Last link", "Last seen", ""] { ui.strong(h); }
                    ui.end_row();
                    for (i, k) in self.prefs.cameras.iter_mut().enumerate() {
                        let r = name_field(ui, ("known_name", i), &mut k.name, true);
                        out.changed |= r.changed();
                        out.names_done |= r.lost_focus();
                        ui.label(&k.model);
                        id_cell(ui, &k.serial, LEARNED_ON_CONNECT);
                        id_cell(ui, &k.mac, LEARNED_ON_CONNECT);
                        ui.label(k.link_text());
                        ui.label(when_words(&k.last_seen));
                        if ui.small_button("Forget").on_hover_text("Remove this camera from the list, and its user name and password and the trust in it from this computer").clicked() {
                            out.forget = Some(i);
                        }
                        ui.end_row();
                    }
                });
            });
        });

        if self.prefs.link == "network" {
            Self::settings_card(ui, "Network address and camera login", |ui| {
                ui.horizontal(|ui| {
                    ui.label("Camera IP address:");
                    if named(ui.add(egui::TextEdit::singleline(&mut self.prefs.camera_ip).hint_text(RichText::new("192.168.1.50").color(tone::weak(ui.visuals()))).desired_width(160.0)), "Camera IP address").changed() {
                        self.prefs.address_typed();
                        out.changed = true;
                    }
                    if let Some(h) = self.schema.camera.text.address_hint.as_deref().filter(|h| !h.is_empty()) {
                        ui.label(RichText::new(format!("({h})")).small().color(tone::weak(ui.visuals())));
                    }
                });
                ui.add_space(4.0);
                ui.horizontal(|ui| {
                    ui.label("Camera login:").on_hover_text("The user name and password set on the camera (Access Authen. Settings)");
                    named(ui.add(egui::TextEdit::singleline(&mut self.net_user).hint_text(RichText::new("user").color(tone::weak(ui.visuals()))).desired_width(110.0)), "Camera user name");
                    named(ui.add(egui::TextEdit::singleline(&mut self.net_pass).password(true).hint_text(RichText::new("password").color(tone::weak(ui.visuals()))).desired_width(130.0)), "Camera password");
                    if ui.add_enabled(!self.net_user.trim().is_empty() && !self.net_pass.is_empty(), egui::Button::new("Save")).clicked() {
                        out.save_creds = true;
                    }
                });
                ui.add(egui::Label::new(RichText::new(self.credentials_note()).small().color(tone::weak(ui.visuals()))).wrap())
                    .on_hover_text(format!("Kept in {}", shown_path(&Self::credentials_path())));
            });
        }

        if self.prefs.expert || self.prefs.probe_path.is_some() {
            Self::settings_card(ui, "Camera link program", |ui| {
                ui.label(RichText::new("Reading and writing go through the camera link program (camset_probe).").small().color(tone::weak(ui.visuals())));
                ui.horizontal(|ui| {
                    ui.label("Program:");
                    if ui.button("Choose…").clicked() {
                        self.ask(ui.ctx(), DialogKind::ProbePath, None);
                    }
                    if self.prefs.probe_path.is_some() && ui.button("Find it by itself").on_hover_text("Forget the program chosen and look for it next to the editor and in the kit").clicked() {
                        self.prefs.probe_path = None;
                        self.helper_seen.set(None);
                        out.changed = true;
                    }
                });
                let found = self.probe_path();
                let helper_str = self.prefs.probe_path.clone().unwrap_or_else(|| found.as_ref().map(|p| format!("(found) {}", p.display())).unwrap_or_else(|| "(not found)".into()));
                ui.add(egui::Label::new(RichText::new(helper_str).monospace().small()).wrap());
            });
        }
        out
    }

    /// Act on what the camera cards did this frame, in either window that shows them.
    pub(crate) fn camera_cards_done(&mut self, out: CameraCardsOutcome) {
        if out.save_creds { self.save_credentials(); }
        if let Some(d) = out.picked { self.use_found_camera(&d); }
        if let Some(i) = out.forget { self.forget_camera(i); }
        if out.changed { self.prefs.save(); }
        if out.names_done { self.copy_names_to_credentials(); }
        if out.search { self.start_job(JobKind::Discover, None); }
    }

    /// Connect to the camera: the camera cards, the same as in Settings > Camera, and a button that connects and
    /// reads.
    pub(crate) fn connect_window(&mut self, ctx: &egui::Context) {
        if !self.show_connect { return; }
        let mut open = true;
        let mut read = false;
        let mut cards = CameraCardsOutcome::default();
        let busy = self.camera_job.is_some();
        egui::Window::new("Connect to the camera").open(&mut open).resizable(true).default_width(860.0).min_width(660.0).show(ctx, |ui| {
            egui::ScrollArea::vertical().max_height(520.0).auto_shrink([false, true]).show(ui, |ui| {
                cards = self.camera_cards(ui);
            });
            ui.separator();
            ui.horizontal(|ui| {
                let helper = self.have_helper();
                if ui.add_enabled(!busy && helper, egui::Button::new("Connect and read from camera"))
                    .on_disabled_hover_text("Needs the camera link program: see the first card").clicked() { read = true; }
                ui.label(RichText::new("A Camera link window then reports what happened.").small().color(tone::weak(ui.visuals())));
            });
        });
        self.camera_cards_done(cards);
        if read { self.show_connect = false; self.start_camera_job(None); }
        if !open { self.show_connect = false; }
    }
}
