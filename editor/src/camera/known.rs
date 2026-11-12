//! The cameras this editor has met (the known cameras, kept in the preferences), the login kept for each in the
//! credentials file, and the cameras this computer trusts. The window's cards for them are in `connect`.

use crate::*;

/// A camera the probe's `discover` command listed.
#[derive(Clone, Default, serde::Deserialize)]
pub(crate) struct Discovered {
    #[serde(default)] pub(crate) model: String,
    #[serde(default)] pub(crate) name: String,
    #[serde(default)] pub(crate) connection: String,
    #[serde(default)] pub(crate) ip: String,
    #[serde(default)] pub(crate) mac: String,
    #[serde(default)] pub(crate) ssh: bool,
    /// The SDK's id for the camera when it is text (a USB camera's body serial number), whatever its type; empty for
    /// an id that is not text (the network id is a binary record).
    #[serde(default)] pub(crate) id: String,
    /// The SDK's id type (0 USB, 2 network in Sony's headers), as information: the serial number does not depend on
    /// it.
    #[serde(default)] pub(crate) id_type: u32,
    /// The SDK's raw id, whatever its type, as lower-case hex (at most 64 bytes): the evidence when `id` is empty.
    /// Empty from an older helper.
    #[serde(default)] pub(crate) id_hex: String,
    /// How the helper found it: "search" (the SDK's search listed it) or "address" (the search did not, but a camera
    /// answered when asked at the address given); empty from an older helper.
    #[serde(default)] pub(crate) found: String,
}

impl Discovered {
    /// The SDK named the connection USB.
    fn is_usb(&self) -> bool { self.connection.to_ascii_uppercase().contains("USB") }
    /// A network camera: it has an address and its connection is not USB (the SDK may fill the address of a USB
    /// camera object).
    pub(crate) fn is_network(&self) -> bool { !self.ip.is_empty() && !self.is_usb() }
    /// A camera the search did not list that answered at the address given: its MAC address is the one this
    /// computer's network table holds for the address, and its serial number is learned on connecting.
    pub(crate) fn by_address(&self) -> bool { self.found == "address" }
    pub(crate) fn link_text(&self) -> String {
        if self.is_network() { format!("Network {}", self.ip) } else { "USB".to_string() }
    }
    /// The Link cell of the found-cameras table, as its two lines: "Network 192.168.1.50 (authenticated)", and for a
    /// row found by its address a second line, "answered at its address", so the cell stays narrow.
    pub(crate) fn link_lines(&self) -> (String, Option<&'static str>) {
        let mut s = self.link_text();
        if self.ssh { s += " (authenticated)"; }
        (s, self.by_address().then_some("answered at its address"))
    }
    /// The Link cell's hover text.
    pub(crate) fn link_hover(&self) -> String {
        if self.by_address() {
            "The search did not list this camera; it answered when asked at the address you entered. Its MAC address is \
             the one this computer's network table holds for that address. Its serial number is learned when the editor \
             first connects to it.".into()
        } else {
            format!("SDK connection type: {}", self.connection)
        }
    }
    /// The serial number the row carries: a USB camera's id, whatever the id type the SDK gives (a row the SDK names
    /// USB counts as USB whatever its address). A network camera does not send its serial (the SDK's network id is a
    /// binary record); the helper prints it once connected.
    pub(crate) fn serial(&self) -> &str {
        if self.is_network() { "" } else { self.id.trim() }
    }
    /// The row as a known camera, met at `when`.
    pub(crate) fn as_known(&self, when: &str) -> KnownCamera {
        KnownCamera {
            name: String::new(),
            model: self.model.clone(),
            serial: self.serial().to_string(),
            mac: norm_mac(&self.mac),
            ip: if self.is_network() { self.ip.clone() } else { String::new() },
            link: if self.is_network() { "network" } else { "usb" }.into(),
            last_seen: when.to_string(),
        }
    }
}

/// A camera this editor has met: the person's own name for it and what tells it apart. Kept in the preferences.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub(crate) struct KnownCamera {
    /// The person's own name for it ("Studio a1 II"); may be empty.
    #[serde(default)] pub(crate) name: String,
    #[serde(default)] pub(crate) model: String,
    /// The body's serial number: from a USB search, or from the helper's `serial:` line once connected.
    #[serde(default)] pub(crate) serial: String,
    /// The MAC address, upper case with colons: from a network search, or from the helper's `mac:` line.
    #[serde(default)] pub(crate) mac: String,
    /// The last network address (empty for a camera met only over USB).
    #[serde(default)] pub(crate) ip: String,
    /// The last link: "usb" or "network".
    #[serde(default)] pub(crate) link: String,
    /// When it was last picked or connected to: a local YYYYMMDD_HHMMSS stamp.
    #[serde(default)] pub(crate) last_seen: String,
}

impl KnownCamera {
    /// This is the camera with that serial, MAC address and network address: by serial when both have one, else by
    /// MAC when both have one, else by address when one of the two has neither (a network camera the helper found
    /// only by its address).
    pub(crate) fn matches(&self, serial: &str, mac: &str, ip: &str) -> bool {
        if !serial.trim().is_empty() && !self.serial.trim().is_empty() { return same_serial(serial, &self.serial); }
        let (a, b) = (norm_mac(mac), norm_mac(&self.mac));
        if !a.is_empty() && !b.is_empty() { return a == b; }
        let bare = |s: &str, m: &str| s.trim().is_empty() && norm_mac(m).is_empty();
        (bare(serial, mac) || bare(&self.serial, &self.mac)) && !ip.trim().is_empty() && ip.trim() == self.ip.trim()
    }

    /// What the person calls it: their name, else the model.
    pub(crate) fn label(&self) -> &str {
        if self.name.trim().is_empty() { self.model.trim() } else { self.name.trim() }
    }

    /// The last link and address in words: "Network 192.168.1.50", "USB".
    pub(crate) fn link_text(&self) -> String {
        match (self.link.as_str(), self.ip.trim()) {
            ("network", "") => "Network".into(),
            ("network", ip) => format!("Network {ip}"),
            ("usb", _) => "USB".into(),
            _ => String::new(),
        }
    }
}

/// A MAC address as the helper prints it: upper-case hex pairs joined by ':' ('-' read as ':'); empty when the
/// text is not one, or is all zero (a camera object made without a MAC).
pub(crate) fn norm_mac(m: &str) -> String {
    let s: String = m.trim().chars().map(|c| if c == '-' { ':' } else { c.to_ascii_uppercase() }).collect();
    let ok = s.len() == 17 && s.chars().enumerate().all(|(i, c)| if i % 3 == 2 { c == ':' } else { c.is_ascii_hexdigit() });
    if ok && s != "00:00:00:00:00:00" { s } else { String::new() }
}

/// Two serial numbers name the same body: equal but for case and leading zeros, or the one the end of the other
/// (a USB id that pads the body's serial number).
fn same_serial(a: &str, b: &str) -> bool {
    let n = |s: &str| s.trim().trim_start_matches('0').to_ascii_uppercase();
    let (a, b) = (n(a), n(b));
    let (short, long) = if a.len() <= b.len() { (a, b) } else { (b, a) };
    !short.is_empty() && (short == long || (short.len() >= 6 && long.ends_with(&short)))
}

/// Add what was just learned about a camera to the known cameras: into the entry it matches, with every other entry
/// it matches folded in (the same body met over USB and over the network), or as a new entry. Its name is kept unless
/// `seen` brings one. Returns the entry's index.
pub(crate) fn remember_camera(cams: &mut Vec<KnownCamera>, seen: &KnownCamera) -> usize {
    let hits: Vec<usize> = (0..cams.len()).filter(|&i| cams[i].matches(&seen.serial, &seen.mac, &seen.ip)).collect();
    let Some(&first) = hits.first() else {
        cams.push(KnownCamera { mac: norm_mac(&seen.mac), ..seen.clone() });
        return cams.len() - 1;
    };
    for &j in hits[1..].iter().rev() {
        let other = cams.remove(j);
        let k = &mut cams[first];
        for (mine, theirs) in [(&mut k.name, other.name), (&mut k.model, other.model), (&mut k.serial, other.serial),
                               (&mut k.mac, other.mac), (&mut k.ip, other.ip), (&mut k.link, other.link)] {
            if mine.trim().is_empty() { *mine = theirs; }
        }
        if other.last_seen > k.last_seen { k.last_seen = other.last_seen; }
    }
    let k = &mut cams[first];
    let mac = norm_mac(&seen.mac);
    for (mine, new) in [(&mut k.name, &seen.name), (&mut k.model, &seen.model), (&mut k.serial, &seen.serial),
                        (&mut k.mac, &mac), (&mut k.ip, &seen.ip), (&mut k.link, &seen.link), (&mut k.last_seen, &seen.last_seen)] {
        if !new.trim().is_empty() { *mine = new.trim().to_string(); }
    }
    first
}

/// The known camera a row of the found-cameras table is, if any. A row answered at its address that matches none is
/// the camera last met at that address: its MAC address is this computer's record of the address, which can be the
/// camera's other network card than the one the search names (the SDK names the wired or the wireless one by model).
pub(crate) fn known_index(cams: &[KnownCamera], d: &Discovered) -> Option<usize> {
    let ip = if d.is_network() { d.ip.as_str() } else { "" };
    cams.iter().position(|k| k.matches(d.serial(), &d.mac, ip)).or_else(|| {
        if !d.by_address() { return None; }
        (0..cams.len()).filter(|&i| cams[i].matches("", "", ip)).max_by(|&a, &b| cams[a].last_seen.cmp(&cams[b].last_seen))
    })
}

/// A picked row as a known camera. A row answered at its address that is a known camera keeps that camera's MAC
/// address (see known_index): the login saved under it stays that camera's.
fn found_as_known(cams: &[KnownCamera], d: &Discovered, when: &str) -> KnownCamera {
    let mut seen = d.as_known(when);
    if let Some(i) = known_index(cams, d).filter(|_| d.by_address()) {
        let mac = norm_mac(&cams[i].mac);
        if !mac.is_empty() { seen.mac = mac; }
    }
    seen
}

/// The camera the helper connected to, from its `serial:`, `mac:` and `model:` lines (each printed only when known).
fn helper_identity(text: &str) -> KnownCamera {
    let field = |key: &str| text.lines().find_map(|l| l.trim().strip_prefix(key)).map(|v| v.trim().to_string()).unwrap_or_default();
    KnownCamera { serial: field("serial:"), mac: norm_mac(&field("mac:")), model: field("model:"), ..Default::default() }
}

/// How a report names the camera: "Studio a1 II (ILCE-1M2)" with the person's name for it, else the model.
pub(crate) fn camera_words(name: &str, model: Option<&str>) -> Option<String> {
    match (name.trim(), model.map(str::trim).filter(|m| !m.is_empty())) {
        ("", m) => m.map(str::to_string),
        (n, Some(m)) if n != m => Some(format!("{n} ({m})")),
        (n, _) => Some(n.to_string()),
    }
}

/// Why a serial number or MAC address is not known yet, in general.
pub(crate) const LEARNED_ON_CONNECT: &str = "Learned when the editor first connects to this camera";

/// The hover text of a found-cameras row's empty Serial cell. A USB row: the search carried no serial number, and
/// where to see what it sent (in Expert mode, under Details from the camera link, with the raw id it sent).
pub(crate) fn serial_why(d: &Discovered, expert: bool) -> String {
    if d.is_network() { return "A network camera tells its serial number when the editor first connects to it".into(); }
    let said = "The helper's search did not carry a serial number for this camera; the editor learns it when it first \
                connects to it.";
    if !expert { return format!("{said} Expert mode (⚙ Settings) shows what the search sent."); }
    let raw = if d.id_hex.is_empty() { "no raw id".to_string() } else { format!("the raw id {} (type {})", d.id_hex, d.id_type) };
    format!("{said} What the search sent is under Details from the camera link; for this camera, {raw}.")
}

/// Whether the setup steps open on their own: while the editor knows no camera and no search has found one.
pub(crate) fn steps_open(known: usize, found: usize) -> bool {
    known == 0 && found == 0
}

// ---------- the credentials file, ~/.config/camset/network.json ----------
// A default pair and one pair per camera under its MAC address; its shape is in kit/probe/camset_probe.cpp's header.
// The helpers read it; the editor writes it, mode 600, and never shows a password.

/// The credentials file's text as a JSON object (empty text: an empty one); an error when it is not one, so a
/// save never overwrites a file it could not read.
fn credentials_doc(existing: &str) -> Result<serde_json::Map<String, serde_json::Value>, String> {
    if existing.trim().is_empty() { return Ok(serde_json::Map::new()); }
    match serde_json::from_str::<serde_json::Value>(existing) {
        Ok(serde_json::Value::Object(m)) => Ok(m),
        _ => Err("the credentials file is not a JSON object; fix it or remove it, then save again".into()),
    }
}

/// The credentials file's text: the default pair first, then the cameras, then anything else it held.
fn credentials_text(doc: &serde_json::Map<String, serde_json::Value>) -> String {
    const FIRST: [&str; 3] = ["user", "password", "cameras"];
    let keys = FIRST.iter().map(|k| k.to_string()).filter(|k| doc.contains_key(k)).chain(doc.keys().filter(|k| !FIRST.contains(&k.as_str())).cloned());
    let body: Vec<String> = keys.map(|k| format!("  {}: {}", serde_json::Value::from(k.as_str()), serde_json::to_string_pretty(&doc[&k]).unwrap_or_default().replace('\n', "\n  "))).collect();
    if body.is_empty() { "{}\n".into() } else { format!("{{\n{}\n}}\n", body.join(",\n")) }
}

/// The credentials file with a pair saved: under the camera's MAC address when it has one (with the person's name
/// for it), and as the default pair when there is no MAC or the file has no default pair yet. Every other entry
/// is kept.
fn credentials_with(existing: &str, mac: &str, name: &str, user: &str, password: &str) -> Result<String, String> {
    let mut doc = credentials_doc(existing)?;
    let mac = norm_mac(mac);
    let has_default = doc.get("user").and_then(|u| u.as_str()).is_some_and(|u| !u.trim().is_empty());
    if !mac.is_empty() {
        let cams = doc.entry("cameras").or_insert_with(|| serde_json::json!({}));
        if !cams.is_object() { *cams = serde_json::json!({}); }
        if let Some(m) = cams.as_object_mut() {
            m.retain(|k, _| norm_mac(k) != mac);   // one entry per camera, whatever case it was written in
            m.insert(mac.clone(), serde_json::json!({ "name": name.trim(), "user": user, "password": password }));
        }
    }
    if mac.is_empty() || !has_default {
        doc.insert("user".into(), user.into());
        doc.insert("password".into(), password.into());
    }
    Ok(credentials_text(&doc))
}

/// The credentials file without the entry for this MAC address; None when it holds none (or cannot be read).
fn credentials_without(existing: &str, mac: &str) -> Option<String> {
    let mut doc = credentials_doc(existing).ok()?;
    let mac = norm_mac(mac);
    let m = doc.get_mut("cameras")?.as_object_mut()?;
    let before = m.len();
    m.retain(|k, _| mac.is_empty() || norm_mac(k) != mac);
    (m.len() != before).then(|| credentials_text(&doc))
}

/// The credentials file with each camera entry's "name" set to the person's name for that camera; None when nothing
/// changes.
fn credentials_renamed(existing: &str, cams: &[KnownCamera]) -> Option<String> {
    let mut doc = credentials_doc(existing).ok()?;
    let m = doc.get_mut("cameras")?.as_object_mut()?;
    let mut changed = false;
    for (key, entry) in m.iter_mut() {
        let Some(k) = cams.iter().find(|k| !norm_mac(key).is_empty() && norm_mac(&k.mac) == norm_mac(key)) else { continue };
        let Some(e) = entry.as_object_mut() else { continue };
        if e.get("name").and_then(|n| n.as_str()).unwrap_or("") != k.name.trim() {
            e.insert("name".into(), k.name.trim().into());
            changed = true;
        }
    }
    changed.then(|| credentials_text(&doc))
}

/// Which pairs the credentials file holds for the camera with this MAC address: (its own, a default).
pub(crate) fn credentials_state(existing: &str, mac: &str) -> (bool, bool) {
    let Ok(doc) = credentials_doc(existing) else { return (false, false) };
    let filled = |v: Option<&serde_json::Value>| v.and_then(|u| u.as_str()).is_some_and(|u| !u.trim().is_empty());
    let mac = norm_mac(mac);
    let own = !mac.is_empty() && doc.get("cameras").and_then(|c| c.as_object())
        .is_some_and(|m| m.iter().any(|(k, e)| norm_mac(k) == mac && filled(e.get("user"))));
    (own, filled(doc.get("user")))
}

// ---------- the cameras this computer trusts, ~/.config/camset/known_cameras.json ----------
// The fingerprint each network camera showed the first time a helper connected to it, under its MAC addresses
// ("by_mac") and its address ("by_address"); the helpers write it and refuse a camera that shows another (cause
// camera_changed). Its shape: kit/common/camera_net.h.

/// The file without the camera known by this MAC address and address: their entries, and every other entry that
/// holds the same fingerprint (the same camera under its other MAC address or an old address), so the next connection
/// trusts it again. None when nothing changes or the file cannot be read.
fn trusted_without(existing: &str, mac: &str, ip: &str) -> Option<String> {
    let serde_json::Value::Object(mut doc) = serde_json::from_str::<serde_json::Value>(existing).ok()? else { return None };
    let (mac, ip) = (norm_mac(mac), ip.trim());
    let named = |group: &str, k: &str| if group == "by_mac" { !mac.is_empty() && norm_mac(k) == mac } else { !ip.is_empty() && k == ip };
    let mut prints = Vec::new();
    for group in ["by_mac", "by_address"] {
        if let Some(m) = doc.get(group).and_then(|g| g.as_object()) {
            prints.extend(m.iter().filter(|(k, _)| named(group, k)).filter_map(|(_, v)| v.as_str().map(str::to_string)));
        }
    }
    let mut changed = false;
    for group in ["by_mac", "by_address"] {
        if let Some(m) = doc.get_mut(group).and_then(|g| g.as_object_mut()) {
            let before = m.len();
            m.retain(|k, v| !named(group, k) && !v.as_str().is_some_and(|f| prints.iter().any(|p| p == f)));
            changed |= m.len() != before;
        }
    }
    changed.then(|| serde_json::to_string_pretty(&doc).unwrap_or_default() + "\n")
}

impl App {
    pub(crate) fn credentials_path() -> PathBuf {
        // tests never read or rewrite the person's own credentials file
        if cfg!(test) {
            return Prefs::path().with_file_name("network.json");
        }
        let home = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")).unwrap_or_default();
        PathBuf::from(home).join(".config").join("camset").join("network.json")
    }

    /// The cameras this computer trusts (`trusted_without`), beside the credentials file.
    fn trusted_path() -> PathBuf {
        Self::credentials_path().with_file_name("known_cameras.json")
    }

    /// The credentials file's text: empty when there is none yet, an error when it cannot be read.
    pub(crate) fn read_credentials() -> std::io::Result<String> {
        match std::fs::read_to_string(Self::credentials_path()) {
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(String::new()),
            read => read,
        }
    }

    /// One of the editor's own files (`path`) could not be read or (`writing`) written: why in plain words, with its
    /// folder; the system's own words and the file in Expert mode.
    pub(crate) fn own_file_problem(&self, path: &Path, e: &std::io::Error, writing: bool) -> String {
        let folder = path.parent().map(shown_path).unwrap_or_default();
        format!("{}{}", own_file_words(e, writing, &folder), details(self.prefs.expert, format_args!("{}: {e}", shown_path(path))))
    }

    /// Save the user name and password typed: under the chosen camera's MAC address when the editor knows it, and as
    /// the default pair when it does not or the file has none yet. The password is written to that file only.
    pub(crate) fn save_credentials(&mut self) {
        let mac = norm_mac(&self.prefs.camera_mac);
        let known = self.prefs.cameras.iter().find(|k| !mac.is_empty() && norm_mac(&k.mac) == mac);
        let (name, label) = (known.map(|k| k.name.trim().to_string()).unwrap_or_default(), known.map(|k| k.label().to_string()).filter(|l| !l.is_empty()));
        let path = Self::credentials_path();
        let saved = Self::read_credentials().map_err(|e| self.own_file_problem(&path, &e, false))
            .and_then(|old| credentials_with(&old, &mac, &name, self.net_user.trim(), &self.net_pass))
            .and_then(|text| write_private(&path, &text).map_err(|e| self.own_file_problem(&path, &e, true)));
        self.status = match saved {
            Ok(()) if mac.is_empty() => "Camera login saved, for every camera without its own".into(),
            Ok(()) => format!("Camera login saved for {}", label.unwrap_or_else(|| format!("the camera {mac}"))),
            Err(why) => format!("The camera login was not saved: {why}"),
        };
        self.net_pass.clear();
    }

    /// Which pair the chosen camera gets, under the user name and password fields.
    /// The file itself is named on hover only (`credentials_path`).
    pub(crate) fn credentials_note(&self) -> String {
        let (own, default) = credentials_state(&Self::read_credentials().unwrap_or_default(), &self.prefs.camera_mac);
        let chosen = !norm_mac(&self.prefs.camera_mac).is_empty();
        match (own, default, chosen) {
            (true, _, _) => "This camera's own login is saved, on this computer only.".into(),
            (false, true, true) => "This camera has no login of its own yet: the one saved for every camera is used; Save keeps one for this camera.".into(),
            (false, true, false) => "Saved on this computer only, for every camera without its own.".into(),
            (false, false, _) => "Not saved yet. It is kept on this computer only, never in a settings file.".into(),
        }
    }

    /// The person's name for the camera found, for the "found" line: the chosen camera when it is among those
    /// found, else the only one found; empty when it has no name.
    pub(crate) fn found_name(&self) -> String {
        let found: Vec<usize> = self.discovered.iter().filter_map(|d| known_index(&self.prefs.cameras, d)).collect();
        let only = (self.discovered.len() == 1).then(|| found.first().copied()).flatten();
        self.named(self.prefs.current_camera().filter(|c| found.contains(c)).or(only))
    }

    /// A row picked with "Use this one": the link, the address and the chosen camera, which the known cameras keep.
    pub(crate) fn use_found_camera(&mut self, d: &Discovered) {
        if d.is_network() { self.prefs.link = "network".into(); self.prefs.camera_ip = d.ip.clone(); }
        else { self.prefs.link = "usb".into(); }
        let seen = found_as_known(&self.prefs.cameras, d, &local_stamp());
        let i = remember_camera(&mut self.prefs.cameras, &seen);
        self.prefs.camera_mac = norm_mac(&self.prefs.cameras[i].mac);
        self.status = format!("Camera link set to {} ({})", d.link_text(), self.prefs.cameras[i].label());
        self.prefs.save();
    }

    /// After a camera action: what the helper said about the camera it connected to goes into the known cameras, and
    /// a network camera's MAC address becomes the chosen one. The known camera's index, when the helper named one.
    pub(crate) fn learn_camera(&mut self, text: &str) -> Option<usize> {
        let mut seen = helper_identity(text);
        if seen.serial.is_empty() && seen.mac.is_empty() { return None; }
        let (model, link) = probe_camera(text);
        let addr = link.as_deref().and_then(|l| l.strip_prefix("LAN ")).and_then(|r| r.split_whitespace().next()).map(str::to_string);
        if seen.model.is_empty() { seen.model = model.unwrap_or_default(); }
        seen.link = if addr.is_some() { "network" } else { "usb" }.into();
        seen.ip = addr.unwrap_or_default();
        seen.last_seen = local_stamp();
        let i = remember_camera(&mut self.prefs.cameras, &seen);
        if seen.link == "network" && !seen.mac.is_empty() { self.prefs.camera_mac = seen.mac.clone(); }
        self.prefs.save();
        Some(i)
    }

    /// Forget a known camera: off the list, its entry in the credentials file, and the fingerprint this computer trusts
    /// for it, so the next connection trusts it again (after a reset of its network settings).
    pub(crate) fn forget_camera(&mut self, i: usize) {
        if i >= self.prefs.cameras.len() { return; }
        let k = self.prefs.cameras.remove(i);
        let mac = norm_mac(&k.mac);
        // what went wrong, each a sentence of its own after the first
        let mut left: Vec<String> = Vec::new();
        let mut with_login = "";
        let trusted = Self::trusted_path();
        if let Some(e) = std::fs::read_to_string(&trusted).ok().and_then(|t| trusted_without(&t, &mac, &k.ip)).and_then(|text| write_private(&trusted, &text).err()) {
            left.push(format!("This computer still trusts it: {}", self.own_file_problem(&trusted, &e, true)));
        }
        if !mac.is_empty() {
            if norm_mac(&self.prefs.camera_mac) == mac { self.prefs.camera_mac.clear(); }
            if let Some(text) = Self::read_credentials().ok().and_then(|t| credentials_without(&t, &mac)) {
                let path = Self::credentials_path();
                match write_private(&path, &text) {
                    Ok(()) => with_login = ", with its user name and password",
                    Err(e) => left.insert(0, format!("Its user name and password were not removed: {}", self.own_file_problem(&path, &e, true))),
                }
            }
        }
        self.prefs.save();
        let name = if k.label().is_empty() { "the camera" } else { k.label() };
        self.status = std::iter::once(format!("Forgot {name}{with_login}.")).chain(left).collect::<Vec<_>>().join(" ");
    }

    /// The person's names for the cameras, copied into their entries in the credentials file (when a name field is
    /// left, so the file is not written on every key).
    pub(crate) fn copy_names_to_credentials(&mut self) {
        if let Some(text) = Self::read_credentials().ok().and_then(|t| credentials_renamed(&t, &self.prefs.cameras)) {
            let path = Self::credentials_path();
            if let Err(e) = write_private(&path, &text) {
                self.status = format!("Your names for the cameras were not copied into the file that keeps their logins: {}", self.own_file_problem(&path, &e, true));
            }
        }
    }

    /// The person's name for a known camera; empty when it has none.
    pub(crate) fn named(&self, i: Option<usize>) -> String {
        i.and_then(|i| self.prefs.cameras.get(i)).map(|k| k.name.trim().to_string()).unwrap_or_default()
    }
}

#[cfg(test)]
pub(crate) mod camera_link_tests {
    use super::*;

    /// A failed camera action's lines with the editor's own words for what to check (no definition's).
    fn cause_lines(text: &str, network: bool) -> Vec<(String, bool)> {
        cause_lines_with(text, network, None)
    }

    /// A failed action's report lines, the action's own lines given, with the editor's own words for what to check.
    fn failure_lines(text: &str, network: bool, own: Vec<(String, bool)>) -> Vec<(String, bool)> {
        failure_lines_with(text, network, own, None)
    }

    /// The setup steps open on their own only while the editor knows no camera and no search has found one.
    #[test]
    fn steps_open_only_before_any_camera() {
        assert!(steps_open(0, 0));
        assert!(!steps_open(0, 1));
        assert!(!steps_open(1, 0));
        assert!(!steps_open(2, 3));
    }

    /// The setup steps are open while no camera is known, fold once one is, stay as the person left them, and open
    /// again after a search that finds nothing.
    #[test]
    fn steps_fold_and_reopen() {
        let mut app = App::new(vec![], Prefs::default());
        assert!(app.steps_shown);
        app.follow_steps_rule();
        assert!(app.steps_shown);
        app.prefs.cameras.push(KnownCamera { model: "ILCE-1M2".into(), mac: "00:11:22:33:44:55".into(), ..Default::default() });
        app.follow_steps_rule();
        assert!(!app.steps_shown);
        app.steps_shown = true;
        app.follow_steps_rule();
        assert!(app.steps_shown, "opened by hand, they stay open");
        app.steps_shown = false;
        app.camera_job = Some(CameraJob::finished(JobKind::Discover, Ok((PathBuf::new(), "found 0 cameras\n".to_string())), None));
        app.poll_camera_job();
        assert!(app.discovered.is_empty());
        assert!(app.steps_shown, "a search that finds nothing opens them");
        assert!(!App::new(vec![], Prefs { cameras: app.prefs.cameras.clone(), ..Prefs::default() }).steps_shown, "folded at start once a camera is known");
    }
    #[test]
    fn stamps() {
        assert_eq!(stamp_minutes("20261025_084800").unwrap() - stamp_minutes("20261025_084600").unwrap(), 2);
        assert_eq!(stamp_minutes("20261026_000000").unwrap() - stamp_minutes("20261025_235900").unwrap(), 1);
        assert_eq!(stamp_minutes("20270301_000000").unwrap() - stamp_minutes("20270228_000000").unwrap(), 1440);
        assert!(stamp_minutes("garbage").is_none());
        let now = local_stamp();
        assert_eq!(now.len(), 15);
        assert!(stamp_minutes(&now).is_some());
    }
    #[test]
    fn probe_lines() {
        // the helper's own spelling, "found:"
        let lan = "found: ILCE-0000 via IP at 192.168.1.50 (SSH)\nfingerprint: abc\nCamera: network 192.168.1.50 (authenticated)\nsaved /x/y.DAT\n";
        assert_eq!(probe_camera(lan), (Some("ILCE-0000".into()), Some("LAN 192.168.1.50 (authenticated)".into())));
        // an older helper's "Found:" still parses
        let old = "Found: ILCE-0000 via IP at 192.168.1.50 (SSH)\nCamera: network 192.168.1.50 (authenticated)\n";
        assert_eq!(probe_camera(old), (Some("ILCE-0000".into()), Some("LAN 192.168.1.50 (authenticated)".into())));
        // several cameras listed: the one at the address connected to
        let two = "found: ILCE-1111 via USB\nfound: ILCE-0000 via IP at 192.168.1.50 (SSH)\nCamera: network 192.168.1.50 (authenticated)\n";
        assert_eq!(probe_camera(two).0, Some("ILCE-0000".into()));
        let usb = "Camera: ILCE-0000\nsaved /x/y.DAT\n";
        assert_eq!(probe_camera(usb), (Some("ILCE-0000".into()), Some("USB".into())));
        assert_eq!(probe_camera("No camera found."), (None, None));
    }

    /// Every cause the helper prints becomes one warning in plain words; without one, what to check.
    #[test]
    fn causes_in_plain_words() {
        let cases = [
            ("credentials_missing", "asks for a user name and password"),
            ("credentials_rejected", "refused the user name or password"),
            ("camera_not_trusted", "identity did not check out"),
            ("camera_changed", "not the one this computer trusted before"),
            ("credentials_file_open", "could be read by other users"),
            ("usb_cable_in", "also on a USB cable"),
            ("no_answer", "did not answer at that address"),
            ("held_by_other_program", "Another program on this computer is holding the camera"),
            ("no_usb_camera", "No camera was found on USB"),
            ("usb_no_permission", "does not let programs open it yet"),
        ];
        for (token, words) in cases {
            let text = format!("found: ILCE-0000 via IP at 192.168.1.50 (SSH)\ncause: {token}\nnetwork connection failed (raw)\n");
            assert_eq!(probe_cause(&text), Some(token));
            for network in [true, false] {
                let lines = cause_lines(&text, network);
                assert_eq!(lines.len(), 1, "{token}");
                assert!(lines[0].0.contains(words) && lines[0].1, "{token}: {}", lines[0].0);
                assert!(["SDK", "SSH", "CrError", "fingerprint"].iter().all(|w| !lines[0].0.contains(w)), "{token}: no jargon");
            }
            // the cause comes before the action's own lines, and the generic checks are left out
            let all = failure_lines(&text, true, vec![("own".into(), true)]);
            assert_eq!(all.len(), 2);
            assert!(all[0].0.contains(words) && all[1].0 == "own");
        }
        // no cause line, or one this editor does not know: the generic checks for the link, after the own lines
        for text in ["SDK error: CrError_Connect_TimeOut\n", "cause: something_new\n", ""] {
            assert_eq!(probe_cause(text), None);
            let net = cause_lines(text, true);
            let usb = cause_lines(text, false);
            assert_eq!((net.len(), usb.len()), (1, 1));
            assert!(!net[0].1 && !usb[0].1);
            assert!(net[0].0.contains("same network") && usb[0].0.contains("remote control over USB"));
            let all = failure_lines(text, false, vec![("own".into(), true)]);
            assert_eq!(all.len(), 2);
            assert!(all[0].0 == "own" && all[1].0 == usb[0].0);
        }
        // a camera that is not the one trusted: the way on is to forget it, where the window offers Forget
        let changed = cause_lines("cause: camera_changed\ntrusted_before: 00:11:22:33:44:55\n", true);
        assert!(changed[0].0.contains("Known cameras, Forget") && changed[0].0.contains("were not sent"));
    }

    /// The causes the helper's header comment lists (kit/probe/camset_probe.cpp, after "`cause: <token>`"), each
    /// `//   token   what it means` with its continuation lines further in.
    fn listed_causes(header: &str) -> Vec<String> {
        let mut out = Vec::new();
        let mut inside = false;
        for line in header.lines() {
            if !line.starts_with("//") {
                if inside { break; }
                continue;
            }
            if line.contains("`cause: <token>`") {
                inside = true;
                continue;
            }
            let Some(rest) = line.strip_prefix("//   ").filter(|_| inside) else { continue };
            let token: String = rest.chars().take_while(|c| c.is_ascii_lowercase() || *c == '_').collect();
            if !token.is_empty() && rest[token.len()..].starts_with(' ') {
                out.push(token);
            }
        }
        out
    }

    /// Every cause the helper's header lists has its sentence here, so a new one never reaches the person as the
    /// generic checks alone.
    #[test]
    fn every_listed_cause_has_its_sentence() {
        let probe = Path::new(env!("CARGO_MANIFEST_DIR")).join("../kit/probe/camset_probe.cpp");
        let text = std::fs::read_to_string(&probe).expect("the helper's source beside the editor");
        let listed = listed_causes(&text);
        assert!(listed.len() >= 10 && listed.iter().any(|t| t == "credentials_missing") && listed.iter().any(|t| t == "usb_no_permission"), "the list was read: {listed:?}");
        for token in &listed {
            let said = cause_sentence(token).unwrap_or_else(|| panic!("no sentence for the helper's cause {token}"));
            assert!(["SDK", "CrError", "CAMSET_IP", "fingerprint", "IPv4"].iter().all(|w| !said.contains(w)), "{token}: no jargon");
        }
        // the causes the helper prints once connected, and the address it checks first
        for (token, words) in [
            ("bad_address", "not a valid address"),
            ("connect_failed", "Expert mode"),
            ("download_refused", "shooting screen"),
            ("upload_refused", "nothing was written"),
            ("not_a_settings_file", "nothing was sent"),
        ] {
            assert!(cause_sentence(token).is_some_and(|s| s.contains(words)), "{token}");
        }
        // the parse itself, on a made-up header: continuation lines and the prose after the list are not tokens
        let made_up = "// intro\n// When a connection fails, one line `cause: <token>` goes out.\n//   one_token    what it means\n//                its next line\n// and, once connected:\n//   two_token    more\n\n//   not_this     after the comment\n";
        assert_eq!(listed_causes(made_up), ["one_token", "two_token"]);
    }

    /// Forget removes what this computer trusts for a camera: its MAC address's and its address's entries, and every
    /// entry holding the same fingerprint (its other network card, an old address); the other cameras stay.
    #[test]
    fn trusted_cameras_forgotten() {
        let v = |t: &str| serde_json::from_str::<serde_json::Value>(t).unwrap();
        let kept = r#"{"by_mac": {"00:11:22:33:44:55": "SHA256:one", "0A:1B:2C:3D:4E:5F": "SHA256:one", "AA:BB:CC:DD:EE:FF": "SHA256:two"},
                       "by_address": {"192.168.1.50": "SHA256:one", "192.168.1.60": "SHA256:one", "192.168.1.77": "SHA256:two"}}"#;
        let left = v(&trusted_without(kept, "00-11-22-33-44-55", "").unwrap());
        assert_eq!(left, serde_json::json!({ "by_mac": { "AA:BB:CC:DD:EE:FF": "SHA256:two" }, "by_address": { "192.168.1.77": "SHA256:two" } }));
        // known by its address only
        let left = v(&trusted_without(kept, "", "192.168.1.77").unwrap());
        assert_eq!(left["by_mac"].as_object().unwrap().len(), 2);
        assert!(left["by_address"].get("192.168.1.77").is_none() && left["by_address"].get("192.168.1.50").is_some());
        // nothing kept for it, or a file that is not the shape: nothing written
        assert_eq!(trusted_without(kept, "02:00:00:00:00:01", "192.168.1.99"), None);
        assert_eq!(trusted_without("{not json", "00:11:22:33:44:55", ""), None);
        assert_eq!(trusted_without("", "00:11:22:33:44:55", ""), None);
    }

    /// The model the helper takes for a camera it reaches by its address: the chosen camera's, else the one last met at
    /// the address; none for an address the editor has not met.
    #[test]
    fn model_for_a_camera_reached_by_address() {
        let cam = |model: &str, mac: &str, ip: &str, seen: &str| KnownCamera { model: model.into(), mac: mac.into(), ip: ip.into(), link: "network".into(), last_seen: seen.into(), ..Default::default() };
        let mut p = Prefs { link: "network".into(), camera_ip: "192.168.1.50".into(), ..Prefs::default() };
        p.cameras = vec![cam("ILME-FX3", "00:11:22:33:44:55", "192.168.1.50", "20260101_100000"), cam("ILCE-1M2", "0A:1B:2C:3D:4E:5F", "192.168.1.50", "20260102_100000")];
        assert_eq!(p.camera_model(), "ILCE-1M2", "the one last met at the address");
        p.camera_mac = "00:11:22:33:44:55".into();
        assert_eq!(p.camera_model(), "ILME-FX3", "the chosen camera");
        p.camera_ip = "192.168.1.99".into();
        p.camera_mac.clear();
        assert_eq!(p.camera_model(), "");
    }

    fn found(json: &str) -> Discovered { serde_json::from_str(json).unwrap() }

    /// A USB row carries the serial number, a network row only its MAC address (the network id is a binary record).
    #[test]
    fn found_rows_serial() {
        let usb = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","mac":"","id":"1234567","id_type":0}"#);
        assert_eq!(usb.serial(), "1234567");
        let blob = found(r#"{"ip":"192.168.1.50","mac":"","id":"00ff00ff","id_type":2}"#);
        assert_eq!(blob.serial(), "");
        let k = usb.as_known("20261105_120000");
        assert_eq!((k.serial.as_str(), k.link.as_str(), k.mac.as_str()), ("1234567", "usb", ""));
        let net = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"0a:1b:2c:3d:4e:5f","id_type":2}"#).as_known("x");
        assert_eq!((net.mac.as_str(), net.link.as_str(), net.ip.as_str()), ("0A:1B:2C:3D:4E:5F", "network", "192.168.1.50"));
    }

    /// A row the helper found by asking at the address says so in its Link cell; a search row and a row from an older
    /// helper (no "found") do not.
    #[test]
    fn found_rows_by_address() {
        let direct = found(r#"{"model":"ILCE-0000","connection":"IP","ip":"192.168.1.50","mac":"00:11:22:33:44:55","ssh":true,"id":"","id_type":2,"found":"address"}"#);
        assert!(direct.by_address());
        assert_eq!(direct.link_lines(), ("Network 192.168.1.50 (authenticated)".to_string(), Some("answered at its address")));
        assert!(direct.link_hover().starts_with("The search did not list this camera; it answered when asked at the address you entered."));
        assert_eq!((direct.serial(), norm_mac(&direct.mac).as_str()), ("", "00:11:22:33:44:55"));
        let bare = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"","ssh":true,"id_type":2,"found":"address"}"#);
        assert!(bare.by_address() && norm_mac(&bare.mac).is_empty());
        let searched = found(r#"{"model":"ILCE-0000","connection":"IP","ip":"192.168.1.50","mac":"00:11:22:33:44:55","ssh":true,"id_type":2,"found":"search"}"#);
        assert!(!searched.by_address());
        assert_eq!(searched.link_lines(), ("Network 192.168.1.50 (authenticated)".to_string(), None));
        assert_eq!(searched.link_hover(), "SDK connection type: IP");
        let older = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"","id_type":2}"#);
        assert!(!older.by_address());
        assert_eq!(older.link_lines(), ("Network 192.168.1.50".to_string(), None));
        let usb = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","id":"1234567","id_type":0,"found":"search"}"#);
        assert_eq!((usb.link_lines(), usb.serial()), (("USB".to_string(), None), "1234567"));
    }

    /// The found-cameras table as the window lays it out, with its text sizes and its widest spacing (Spacious), in a
    /// card of the Connect and Settings windows (`settings_card`: 12 points of margin and a 1-point border a side):
    /// at their default width of 860 points the whole table fits, its widest Link cell included; at their minimum of
    /// 660 "Use this one" still shows without scrolling.
    #[test]
    fn found_table_fits_its_windows() {
        use eframe::App as _;
        use egui::accesskit::Role;
        let mut app = App::new(vec![], Prefs { density: 2, ..Prefs::default() });
        let ctx = egui::Context::default();
        ctx.enable_accesskit();
        let mut frame = eframe::Frame::_new_kittest();
        let screen = egui::RawInput { screen_rect: Some(egui::Rect::from_min_size(egui::Pos2::ZERO, egui::vec2(1600.0, 1000.0))), ..Default::default() };
        // the window sets its style
        let _ = ctx.run(screen.clone(), |ctx| app.update(ctx, &mut frame));
        // the widest rows: a network camera answered at an address of 15 characters (each digit as wide as any), with
        // its MAC address, and a USB camera with a serial number of 8 digits and no MAC address yet
        let rows = [
            found(r#"{"model":"ILCE-0000","connection":"IP","ip":"000.000.000.000","mac":"00:11:22:33:44:55","ssh":true,"id_type":2,"found":"address"}"#),
            found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","id":"00000000","id_type":0,"found":"search"}"#),
        ];
        for (window, whole) in [(860.0, true), (660.0, false)] {
            let inside = window - 2.0 * (12.0 + 1.0);
            let (mut left, mut cams, mut out) = (0.0, Vec::new(), None);
            // the grid sizes its columns on the first frames
            for _ in 0..3 {
                out = Some(ctx.run(screen.clone(), |ctx| {
                    egui::CentralPanel::default().show(ctx, |ui| {
                        ui.allocate_ui(egui::vec2(inside, 600.0), |ui| {
                            ui.set_width(inside);
                            left = ui.max_rect().left();
                            discovered_grid(ui, "found", &rows, &mut cams, false);
                        });
                    });
                }));
            }
            let tree = out.unwrap().platform_output.accesskit_update.expect("the window tells screen readers what it shows");
            let right = |pick: &dyn Fn(&egui::accesskit::Node) -> bool| tree.nodes.iter().filter(|(_, n)| pick(n))
                .filter_map(|(_, n)| n.bounds()).map(|b| b.x1 as f32).fold(f32::MIN, f32::max);
            let button = right(&|n| n.role() == Role::Button && n.label() == Some("Use this one"));
            assert!(button > left && button <= left + inside, "Use this one ends at {} in a card {inside} wide (window {window})", button - left);
            let table = right(&|n| matches!(n.role(), Role::Label | Role::Button | Role::TextInput));
            if whole {
                assert!(table <= left + inside, "the table is {} wide in a card {inside} wide (window {window})", table - left);
            }
        }
    }

    /// A row the SDK names USB is a USB camera even when the address field is filled: it carries its serial number,
    /// and picking it sets the USB link with no address. The raw id comes along as hex.
    #[test]
    fn usb_row_with_an_address() {
        let usb = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"192.168.1.50","mac":"","id":"1234567","id_hex":"31323334353637","id_type":0,"found":"search"}"#);
        assert!(usb.is_usb() && !usb.is_network());
        assert_eq!((usb.serial(), usb.link_text().as_str(), usb.id_hex.as_str()), ("1234567", "USB", "31323334353637"));
        let k = usb.as_known("20261105_120000");
        assert_eq!((k.serial.as_str(), k.link.as_str(), k.ip.as_str()), ("1234567", "usb", ""));
        // the SDK's own spelling may vary in case; a network row stays a network row
        assert!(!found(r#"{"connection":"usb","ip":"192.168.1.50","id":"1234567","id_type":0}"#).is_network());
        let net = found(r#"{"connection":"IP","ip":"192.168.1.50","id":"","id_hex":"00ff00ff","id_type":2}"#);
        assert!(net.is_network() && net.serial().is_empty() && net.id_hex == "00ff00ff");
        // an older helper sends no id_hex
        assert_eq!(found(r#"{"connection":"USB","ip":"","id":"1234567","id_type":0}"#).id_hex, "");
    }

    /// The serial number does not depend on the SDK's id type: a USB row's text id is its serial whatever the type,
    /// and a network row carries none.
    #[test]
    fn serial_whatever_the_id_type() {
        let usb = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","mac":"","id":"1234567","id_hex":"31323334353637","id_type":1}"#);
        assert_eq!(usb.serial(), "1234567");
        assert_eq!(usb.as_known("20261105_120000").serial, "1234567");
        let net = found(r#"{"model":"ILCE-0000","connection":"IP","ip":"192.168.1.50","mac":"00:11:22:33:44:55","id":"","id_hex":"00ff00ff","id_type":2}"#);
        assert_eq!(net.serial(), "");
        let no_id = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","id":"","id_hex":"0001ff","id_type":0}"#);
        assert_eq!(no_id.serial(), "");
    }

    /// An empty Serial cell's hover: a USB row says the search carried no serial number and where to see what it
    /// sent; the raw id only in Expert mode.
    #[test]
    fn empty_serial_hover() {
        let usb = found(r#"{"model":"ILCE-0000","connection":"USB","ip":"","id":"","id_hex":"0001ff","id_type":0}"#);
        let plain = serial_why(&usb, false);
        assert!(plain.starts_with("The helper's search did not carry a serial number for this camera;") && plain.contains("Expert mode"));
        assert!(!plain.contains("0001ff"), "no raw output outside Expert mode");
        let expert = serial_why(&usb, true);
        assert!(expert.contains("Details from the camera link") && expert.contains("the raw id 0001ff (type 0)"));
        let older = found(r#"{"connection":"USB","ip":"","id":"","id_type":0}"#);
        assert!(serial_why(&older, true).contains("no raw id"));
        let net = found(r#"{"connection":"IP","ip":"192.168.1.50","id_hex":"00ff00ff","id_type":2}"#);
        assert_eq!(serial_why(&net, true), "A network camera tells its serial number when the editor first connects to it");
    }

    /// The whole search output is kept for Expert mode whatever the search found; the short words shown when nothing
    /// was found stay as they were.
    #[test]
    fn search_output_kept() {
        let mut app = App::new(vec![], Prefs::default());
        let run = |app: &mut App, res: Result<(PathBuf, String), String>| {
            app.camera_job = Some(CameraJob::finished(JobKind::Discover, res, None));
            app.poll_camera_job();
        };
        let text = "{\"model\":\"ILCE-0000\",\"connection\":\"USB\",\"ip\":\"\",\"mac\":\"\",\"id\":\"\",\"id_hex\":\"0001ff\",\"id_type\":0}\nfound 1 camera(s)\n";
        run(&mut app, Ok((PathBuf::new(), text.to_string())));
        assert_eq!(app.discovered.len(), 1);
        assert_eq!((app.discovered[0].serial(), app.discovered[0].id_hex.as_str()), ("", "0001ff"));
        assert_eq!(app.discover_text, text.trim());
        assert!(app.discover_detail.is_empty(), "a search that found a camera has no short words");
        let none = "direct check of 192.168.1.50: CrError_Connect_TimeOut (check)\nfound 0 camera(s)\n";
        run(&mut app, Ok((PathBuf::new(), none.to_string())));
        assert_eq!(app.discover_detail, "direct check of 192.168.1.50: CrError_Connect_TimeOut (check)");
        assert_eq!(app.discover_text, none.trim());
        run(&mut app, Err("could not run /x/camset_probe: not found\n".into()));
        assert_eq!((app.discover_detail.as_str(), app.discover_text.as_str()), ("could not run /x/camset_probe: not found", "could not run /x/camset_probe: not found"));
    }

    #[test]
    fn mac_normalised() {
        assert_eq!(norm_mac("0a:1b:2c:3d:4e:5f"), "0A:1B:2C:3D:4E:5F");
        assert_eq!(norm_mac(" 0a-1b-2c-3d-4e-5f "), "0A:1B:2C:3D:4E:5F");
        for not in ["", "00:00:00:00:00:00", "0A:1B:2C:3D:4E", "0A:1B:2C:3D:4E:5G", "0A1B2C3D4E5F00000"] { assert_eq!(norm_mac(not), "", "{not}"); }
    }

    #[test]
    fn serials_compared() {
        assert!(same_serial("1234567", "1234567"));
        assert!(same_serial("abc1234", " ABC1234"));
        assert!(same_serial("0001234567", "1234567"), "leading zeros");
        assert!(same_serial("XY1234567", "1234567"), "a USB id that pads the serial");
        assert!(!same_serial("1234567", "1234568"));
        assert!(!same_serial("12345", "912345"), "too short to pad");
        assert!(!same_serial("", ""));
    }

    /// A found row is a known camera by serial when both have one, else by MAC address, else (a network camera found
    /// only by its address) by address.
    #[test]
    fn found_rows_match_known_cameras() {
        let cams = vec![
            KnownCamera { name: "Studio a1 II".into(), model: "ILCE-0000".into(), serial: "1234567".into(), mac: "00:11:22:33:44:55".into(), ip: "192.168.1.50".into(), link: "network".into(), last_seen: "20261105_120000".into() },
            KnownCamera { name: "Spare".into(), model: "ILCE-0000".into(), serial: "7654321".into(), ..Default::default() },
        ];
        let usb = found(r#"{"model":"ILCE-0000","ip":"","mac":"","id":"7654321","id_type":0}"#);
        assert_eq!(known_index(&cams, &usb), Some(1), "by serial");
        let net = found(r#"{"model":"ILCE-0000","ip":"192.168.1.77","mac":"00:11:22:33:44:55","id_type":2}"#);
        assert_eq!(known_index(&cams, &net), Some(0), "by MAC, at another address");
        let lower = found(r#"{"ip":"192.168.1.77","mac":"00-1a-2b-3c-4d-5e","id_type":2}"#);
        let mut lettered = cams.clone();
        lettered[0].mac = "00:1A:2B:3C:4D:5E".into();
        assert_eq!(known_index(&lettered, &lower), Some(0), "MAC case and separator do not matter");
        let bare = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"","id_type":2}"#);
        assert_eq!(known_index(&cams, &bare), Some(0), "found only by its address");
        let other = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"0A:1B:2C:3D:4E:5F","id_type":2}"#);
        assert_eq!(known_index(&cams, &other), None, "another MAC at the same address");
        // answered at its address: its MAC is this computer's record of the address, which can be the camera's other
        // network card, so it is the camera last met there
        let direct = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"0A:1B:2C:3D:4E:5F","id_type":2,"found":"address"}"#);
        assert_eq!(known_index(&cams, &direct), Some(0), "answered at its address, another network card");
        let direct_bare = found(r#"{"ip":"192.168.1.50","mac":"","id_type":2,"found":"address"}"#);
        assert_eq!(known_index(&cams, &direct_bare), Some(0), "answered at its address, no MAC");
        let direct_same = found(r#"{"ip":"192.168.1.77","mac":"00:11:22:33:44:55","id_type":2,"found":"address"}"#);
        assert_eq!(known_index(&cams, &direct_same), Some(0), "answered at another address, the same MAC");
        let elsewhere = found(r#"{"ip":"192.168.1.99","mac":"0A:1B:2C:3D:4E:5F","id_type":2,"found":"address"}"#);
        assert_eq!(known_index(&cams, &elsewhere), None, "nobody known at that address");
        // picked, it keeps the known camera's MAC address, under which its login is saved
        let seen = found_as_known(&cams, &direct, "20261105_130000");
        assert_eq!(seen.mac, "00:11:22:33:44:55");
        let mut after = cams.clone();
        assert_eq!(remember_camera(&mut after, &seen), 0);
        assert_eq!((after.len(), after[0].mac.as_str(), after[0].last_seen.as_str()), (2, "00:11:22:33:44:55", "20261105_130000"));
        assert_eq!(found_as_known(&cams, &elsewhere, "x").mac, "0A:1B:2C:3D:4E:5F", "a camera new at that address keeps the table's MAC");
        assert_eq!(found_as_known(&cams, &other, "x").mac, "0A:1B:2C:3D:4E:5F", "a search row keeps its own");
        let stranger = found(r#"{"model":"ILCE-0000","ip":"","mac":"","id":"1111111","id_type":0}"#);
        assert_eq!(known_index(&cams, &stranger), None);
        let nothing = found(r#"{"model":"ILCE-0000","ip":"","mac":"","id":"","id_type":0}"#);
        assert_eq!(known_index(&cams, &nothing), None);
    }

    /// The same body met over USB (serial) and over the network (MAC) becomes one known camera once the helper names
    /// both; the person's name survives.
    #[test]
    fn known_cameras_fold() {
        let mut cams = Vec::new();
        let usb = found(r#"{"model":"ILCE-0000","ip":"","mac":"","id":"1234567","id_type":0}"#);
        let net = found(r#"{"model":"ILCE-0000","ip":"192.168.1.50","mac":"00:11:22:33:44:55","id_type":2}"#);
        assert_eq!(remember_camera(&mut cams, &usb.as_known("20261105_100000")), 0);
        assert_eq!(remember_camera(&mut cams, &net.as_known("20261105_110000")), 1);
        cams[1].name = "Studio a1 II".into();
        assert_eq!(remember_camera(&mut cams, &usb.as_known("20261105_103000")), 0, "the same USB camera again");
        assert_eq!(cams.len(), 2);
        let mut seen = helper_identity("Camera: network 192.168.1.50 (authenticated)\nserial: 1234567\nmac: 00:11:22:33:44:55\nmodel: ILCE-0000\n");
        seen.ip = "192.168.1.50".into();
        seen.link = "network".into();
        seen.last_seen = "20261105_120000".into();
        assert_eq!(remember_camera(&mut cams, &seen), 0);
        assert_eq!(cams.len(), 1, "folded into one");
        let k = &cams[0];
        assert_eq!((k.name.as_str(), k.serial.as_str(), k.mac.as_str(), k.ip.as_str(), k.link.as_str(), k.last_seen.as_str()),
                   ("Studio a1 II", "1234567", "00:11:22:33:44:55", "192.168.1.50", "network", "20261105_120000"));
        // a camera found only by its address, then named by the helper on connecting
        let mut cams = vec![found(r#"{"model":"ILCE-0000","ip":"192.168.1.60","mac":"","id_type":2}"#).as_known("20261105_100000")];
        cams[0].name = "Studio".into();
        let mut seen = helper_identity("serial: 2345678\nmac: 0A:1B:2C:3D:4E:5F\n");
        seen.ip = "192.168.1.60".into();
        assert_eq!(remember_camera(&mut cams, &seen), 0);
        assert_eq!((cams.len(), cams[0].name.as_str(), cams[0].mac.as_str()), (1, "Studio", "0A:1B:2C:3D:4E:5F"));
    }

    /// The helper's lines after a connect, and the model it names there before the one it listed.
    #[test]
    fn helper_names_the_camera() {
        let text = "found: ILCE-1111 via USB\nCamera: ILCE-1111\nserial: 1234567\nmac: 00:11:22:33:44:55\nmodel: ILCE-0000\nsaved /x/y.DAT\n";
        let k = helper_identity(text);
        assert_eq!((k.serial.as_str(), k.mac.as_str(), k.model.as_str()), ("1234567", "00:11:22:33:44:55", "ILCE-0000"));
        assert_eq!(probe_camera(text).0, Some("ILCE-0000".into()));
        let lower = helper_identity("mac: 00:aa:bb:cc:dd:ee\n");
        assert_eq!((lower.serial.as_str(), lower.mac.as_str()), ("", "00:AA:BB:CC:DD:EE"));
        let none = helper_identity("Camera: ILCE-0000\nsaved /x/y.DAT\n");
        assert!(none.serial.is_empty() && none.mac.is_empty() && none.model.is_empty());
        assert_eq!(camera_words("Studio a1 II", Some("ILCE-0000")).as_deref(), Some("Studio a1 II (ILCE-0000)"));
        assert_eq!(camera_words(" ", Some("ILCE-0000")).as_deref(), Some("ILCE-0000"));
        assert_eq!(camera_words("Studio a1 II", None).as_deref(), Some("Studio a1 II"));
        assert_eq!(camera_words("", None), None);
    }

    /// The camera the next action goes to: over the network the chosen MAC, else the address; over USB the last met.
    #[test]
    fn current_camera() {
        let mut p = Prefs { link: "network".into(), camera_ip: "192.168.1.50".into(), ..Default::default() };
        assert_eq!(p.current_camera(), None);
        p.cameras = vec![
            KnownCamera { name: "A".into(), mac: "00:11:22:33:44:55".into(), ip: "192.168.1.50".into(), link: "network".into(), last_seen: "20261105_100000".into(), ..Default::default() },
            KnownCamera { name: "B".into(), mac: "0A:1B:2C:3D:4E:5F".into(), ip: "192.168.1.50".into(), link: "network".into(), last_seen: "20261105_110000".into(), ..Default::default() },
            KnownCamera { name: "C".into(), serial: "1234567".into(), link: "usb".into(), last_seen: "20261105_090000".into(), ..Default::default() },
        ];
        assert_eq!(p.current_camera(), Some(1), "the last met at the address");
        p.camera_mac = "00:11:22:33:44:55".into();
        assert_eq!(p.current_camera(), Some(0), "the chosen MAC");
        p.address_typed();
        assert_eq!(p.camera_mac, "0A:1B:2C:3D:4E:5F", "typing an address chooses the camera last met there");
        p.camera_ip = "192.168.1.99".into();
        p.address_typed();
        assert_eq!(p.camera_mac, "");
        p.link = "usb".into();
        assert_eq!(p.current_camera(), Some(2));
    }

    /// Save keeps each camera's pair under its MAC address and one default pair; Forget removes only that camera's.
    #[test]
    fn credentials_file() {
        let v = |t: &str| serde_json::from_str::<serde_json::Value>(t).unwrap();
        // the first save, for a camera with a MAC: its own entry, and the default pair since there is none yet
        let one = credentials_with("", "00:1a:2b:3c:4d:5e", "Studio a1 II", "user", "pw1").unwrap();
        assert_eq!(v(&one), serde_json::json!({ "user": "user", "password": "pw1",
            "cameras": { "00:1A:2B:3C:4D:5E": { "name": "Studio a1 II", "user": "user", "password": "pw1" } } }));
        assert!(one.starts_with("{\n  \"user\""), "the default pair first:\n{one}");
        // a second camera: its own entry; the default pair stays
        let two = credentials_with(&one, "0a:1b:2c:3d:4e:5f", "", "ann", "pw2").unwrap();
        let d = v(&two);
        assert_eq!((d["user"].as_str(), d["password"].as_str()), (Some("user"), Some("pw1")));
        assert_eq!(d["cameras"]["0A:1B:2C:3D:4E:5F"]["user"], "ann");
        assert_eq!(d["cameras"]["00:1A:2B:3C:4D:5E"]["password"], "pw1");
        // the first camera again, its key written by hand in lower case: replaced, not doubled
        let three = credentials_with(&two.replace("00:1A:2B:3C:4D:5E", "00:1a:2b:3c:4d:5e"), "00-1A-2B-3C-4D-5E", "Studio a1 II", "user", "pw3").unwrap();
        let d = v(&three);
        assert_eq!(d["cameras"].as_object().unwrap().len(), 2);
        assert_eq!(d["cameras"]["00:1A:2B:3C:4D:5E"]["password"], "pw3");
        assert_eq!(d["password"], "pw1", "the default pair is not touched");
        // no MAC known: the default pair is what is saved
        let four = credentials_with(&three, "", "", "guest", "pw4").unwrap();
        let d = v(&four);
        assert_eq!((d["user"].as_str(), d["cameras"].as_object().unwrap().len()), (Some("guest"), 2));
        // the old shape reads as a default pair; a file that is not JSON is never overwritten
        assert_eq!(credentials_state(r#"{"user": "user", "password": "pw"}"#, "00:11:22:33:44:55"), (false, true));
        assert!(credentials_with("{not json", "", "", "u", "p").is_err());
        assert!(credentials_with("[1, 2]", "", "", "u", "p").is_err());
        // what the chosen camera gets
        assert_eq!(credentials_state(&four, "0a:1b:2c:3d:4e:5f"), (true, true));
        assert_eq!(credentials_state(&four, "00:00:00:00:00:01"), (false, true));
        assert_eq!(credentials_state("", ""), (false, false));
        // names follow the known cameras
        let cams = vec![KnownCamera { name: "Field a1 II".into(), mac: "0A:1B:2C:3D:4E:5F".into(), ..Default::default() }];
        let renamed = credentials_renamed(&four, &cams).unwrap();
        assert_eq!(v(&renamed)["cameras"]["0A:1B:2C:3D:4E:5F"]["name"], "Field a1 II");
        assert_eq!(credentials_renamed(&renamed, &cams), None, "nothing to change");
        // Forget: that camera's entry only
        let fewer = credentials_without(&renamed, "0a:1b:2c:3d:4e:5f").unwrap();
        let d = v(&fewer);
        assert!(d["cameras"].get("0A:1B:2C:3D:4E:5F").is_none() && d["cameras"].get("00:1A:2B:3C:4D:5E").is_some());
        assert_eq!(d["user"], "guest");
        assert_eq!(credentials_without(&fewer, "0A:1B:2C:3D:4E:5F"), None);
        assert_eq!(credentials_without(r#"{"user": "u"}"#, "00:11:22:33:44:55"), None);
    }

    /// The credentials file is written whole and readable by its owner only.
    #[test]
    fn credentials_written_privately() {
        let dir = std::env::temp_dir().join(format!("camset_creds_test_{}", std::process::id()));
        let p = dir.join("network.json");
        write_private(&p, "{\"user\": \"u\"}\n").unwrap();
        write_private(&p, "{\"user\": \"v\"}\n").unwrap();
        assert_eq!(std::fs::read_to_string(&p).unwrap(), "{\"user\": \"v\"}\n");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&p).unwrap().permissions().mode() & 0o777, 0o600);
        }
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 1, "no temporary file left");
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&dir).unwrap().permissions().mode() & 0o777, 0o700, "the folder is this user's only");
            std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o755)).unwrap();
            private_dir(&dir).unwrap();
            assert_eq!(std::fs::metadata(&dir).unwrap().permissions().mode() & 0o777, 0o700, "and is made so again");
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The preferences are written whole and private, like the credentials file.
    #[test]
    fn prefs_written_privately() {
        // other tests save the same file meanwhile: what is checked is that it is always whole and private
        Prefs { camera_ip: "192.168.1.50".into(), ..Prefs::default() }.save();
        assert!(serde_json::from_str::<Prefs>(&std::fs::read_to_string(Prefs::path()).unwrap()).is_ok());
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(Prefs::path()).unwrap().permissions().mode() & 0o777, 0o600);
        }
    }

    /// probe.log is started again once it reaches its size, the one before kept as probe.log.1.
    #[test]
    fn probe_log_rotates() {
        let dir = std::env::temp_dir().join(format!("camset_log_test_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let log = dir.join("probe.log");
        std::fs::write(&log, "a".repeat(10)).unwrap();
        rotate_log(&log, 100);
        assert!(log.is_file(), "under the size: kept");
        rotate_log(&log, 10);
        assert!(!log.exists() && dir.join("probe.log.1").is_file());
        std::fs::write(&log, "b".repeat(10)).unwrap();
        rotate_log(&log, 10);
        assert_eq!(std::fs::read_to_string(dir.join("probe.log.1")).unwrap(), "b".repeat(10), "one older file only");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The helper is looked for beside the program and, for a program built in a checkout, in the kit's build folder;
    /// never in the folder the editor was started from or the folders above the program.
    #[test]
    fn helper_looked_for_in_known_places() {
        let name = format!("camset_probe{}", std::env::consts::EXE_SUFFIX);
        let kit = |root: &str| PathBuf::from(root).join("kit").join("probe").join("build").join(&name);
        let c = probe_candidates(Path::new("/src/camset/editor/target/release/camset_editor"));
        assert_eq!(c[0], PathBuf::from("/src/camset/editor/target/release").join(&name));
        assert_eq!(c[1], kit("/src/camset"));
        assert_eq!(probe_candidates(Path::new("/src/camset/editor/target/aarch64-apple-darwin/release/camset_editor"))[1], kit("/src/camset"));
        assert_eq!(probe_candidates(Path::new("/src/camset/editor/target/dist/Camset Editor.app/Contents/MacOS/camset_editor"))[1], kit("/src/camset"));
        // installed: beside the program only
        let app = probe_candidates(Path::new("/Applications/Camset Editor.app/Contents/MacOS/camset_editor"));
        assert_eq!(app, vec![PathBuf::from("/Applications/Camset Editor.app/Contents/MacOS").join(&name)]);
        assert_eq!(probe_candidates(Path::new("/home/user/.local/bin/camset_editor")).len(), 1);
        // a "target" folder not inside editor/ is not a checkout
        assert_eq!(probe_candidates(Path::new("/tmp/target/release/camset_editor")).len(), 1);
    }
}
