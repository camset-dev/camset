//! The web page's HTTP server: the listening thread, one thread per connection, the request read with its limits, the
//! gate every request passes (`Host`, `Origin`, the access code and the sessions) and the reply written. It knows
//! nothing of the editor: a request for the editor goes to the window as a `WebRequest` and waits for its `WebReply`
//! (`App::web_answer` in web/mod.rs).

use super::*;
use std::io::{Read, Write};
use std::net::{IpAddr, SocketAddr, TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

pub(crate) const DEFAULT_PORT: u16 = 8642;
pub(crate) const PAGE: &str = include_str!("../../web/index.html");
pub(crate) const SCRIPT: &str = include_str!("../../web/app.js");
const ICON: &[u8] = include_bytes!("../../assets/icon.png");
/// The largest request taken (settings files are far smaller).
const MAX_BODY: usize = 4 << 20;
const MAX_HEAD: usize = 32 << 10;
/// Connections open at once, in all and from one client address.
const MAX_CONNECTIONS: usize = 64;
const MAX_PER_ADDRESS: usize = 8;
/// How long a request's head may take to arrive, and then its body (an upload from a phone).
const HEAD_DEADLINE: Duration = Duration::from_secs(10);
const BODY_DEADLINE: Duration = Duration::from_secs(120);
/// How long a request waits for the editor window to answer it.
const REPLY_WAIT: Duration = Duration::from_secs(30);
/// Wrong access codes one client address may send within `WRONG_WINDOW` before its codes are refused until the
/// oldest falls out of the window. Sessions, and every other address, go on.
const MAX_WRONG: usize = 10;
const WRONG_WINDOW: Duration = Duration::from_secs(60);
/// Client addresses whose wrong codes are counted at once; past it, a code from an address not counted is refused.
const MAX_COUNTED: usize = 4096;
/// A session ends after this long without a request; at most this many are kept (the oldest is dropped).
const SESSION_IDLE: Duration = Duration::from_secs(12 * 3600);
const MAX_SESSIONS: usize = 64;

/// A request for the editor, and where its answer goes.
pub(crate) struct WebRequest {
    pub(crate) name: String,
    pub(crate) body: Vec<u8>,
    /// The file name an upload came with (percent-encoded by the page).
    pub(crate) file_name: String,
    /// The page asked the person, who agreed that the request may throw away unsaved edits (a file sent up says so
    /// in a header; a JSON request with `discard: true`).
    pub(crate) discard: bool,
    pub(crate) peer: String,
    pub(crate) reply: mpsc::Sender<WebReply>,
}

pub(crate) struct WebReply {
    pub(crate) status: u16,
    pub(crate) content_type: &'static str,
    pub(crate) body: Vec<u8>,
    /// Sent as a download with this file name.
    pub(crate) download: Option<String>,
    /// Kept by the browser (the fonts, which do not change within a build); everything else is fetched each time.
    pub(crate) keep: bool,
}

impl WebReply {
    pub(crate) fn json(v: Value) -> Self {
        WebReply { status: 200, content_type: "application/json", body: v.to_string().into_bytes(), download: None, keep: false }
    }
    pub(crate) fn error(status: u16, why: &str) -> Self {
        Self::refused(status, why, Value::Null)
    }
    /// A refusal with more for the page beside its reason (`more`'s fields, when it is an object).
    pub(crate) fn refused(status: u16, why: &str, more: Value) -> Self {
        let mut body = json!({ "error": why });
        if let (Some(b), Value::Object(m)) = (body.as_object_mut(), more) {
            b.extend(m);
        }
        WebReply { status, content_type: "application/json", body: body.to_string().into_bytes(), download: None, keep: false }
    }
    /// The answer while the page is being turned off or the editor quits.
    pub(crate) fn closed() -> Self {
        Self::refused(503, "The editor has closed the web page: it was turned off, or the editor quit.", json!({ "closed": true }))
    }
    pub(crate) fn fixed(content_type: &'static str, body: &[u8]) -> Self {
        WebReply { status: 200, content_type, body: body.to_vec(), download: None, keep: false }
    }
    /// One of the fonts egui draws the window with, so the page draws its text the same way.
    pub(crate) fn font(name: &str) -> Self {
        match egui_font(name) {
            [] => WebReply::error(404, "not found"),
            bytes => WebReply { keep: true, ..WebReply::fixed("font/ttf", bytes) },
        }
    }
}

/// A font egui builds in (`FontDefinitions::default()`: "Ubuntu-Light" for text, "Hack" for
/// monospace) as the program carries it; empty when this build has no such font. Their licences are
/// in THIRD_PARTY_LICENSES.html, with the crate that carries them (epaint_default_fonts).
fn egui_font(name: &str) -> &'static [u8] {
    match egui::FontDefinitions::default().font_data.get(name).map(|f| f.font.clone()) {
        Some(std::borrow::Cow::Borrowed(bytes)) => bytes,
        _ => &[],
    }
}


/// The server while the web page is on: the listening thread and the requests it hands over.
/// Dropping it answers the requests still waiting (`WebReply::closed`) and closes the port.
pub(crate) struct WebServer {
    /// The address to open in a browser, e.g. http://192.168.1.20:8642
    pub(crate) url: String,
    /// The access code, as shown (ABCD-EFGH): new each time the page is turned on, never written to a file.
    pub(crate) code: String,
    /// Open to the network (on this computer's network address), or to this computer only.
    pub(crate) everyone: bool,
    stop: Arc<AtomicBool>,
    gate: Arc<Gate>,
    open: Arc<AtomicUsize>,
    pub(crate) requests: mpsc::Receiver<WebRequest>,
    thread: Option<std::thread::JoinHandle<()>>,
    /// Who sent the last request and when (local time stamp).
    pub(crate) last: Option<(String, String)>,
}

/// Why the server did not start.
#[derive(Debug)]
pub(crate) enum StartError {
    /// Open to the network asked, and this computer is on none.
    NoNetwork,
    /// The port could not be opened, and the system's own words for why.
    Port(u16, std::io::Error),
}

impl StartError {
    /// Why, in plain words, with what to do.
    pub(crate) fn words(&self) -> String {
        use std::io::ErrorKind as K;
        match self {
            StartError::NoNetwork => "this computer is on no network now: join one, or choose \"this computer only\".".into(),
            StartError::Port(port, e) => match e.kind() {
                K::AddrInUse => format!("another program is using port {port}: choose another port, or quit that program."),
                K::PermissionDenied => format!("this computer does not let the editor use port {port}: choose another port."),
                K::AddrNotAvailable => "this computer's network address changed as the page started: try again.".into(),
                _ => format!("port {port} could not be opened: try again, or choose another port."),
            },
        }
    }

    /// The system's own words, for Expert mode (`details`); none for a computer on no network.
    pub(crate) fn system_words(&self) -> Option<String> {
        match self {
            StartError::NoNetwork => None,
            StartError::Port(port, e) => Some(format!("port {port}: {e}")),
        }
    }
}

/// One open connection: counted in all and for its client address while it lasts.
struct SlotGuard(Arc<AtomicUsize>, Arc<Mutex<HashMap<IpAddr, usize>>>, IpAddr);
impl Drop for SlotGuard {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::AcqRel);
        let mut by = self.1.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(n) = by.get_mut(&self.2) {
            *n -= 1;
            if *n == 0 {
                by.remove(&self.2);
            }
        }
    }
}

impl WebServer {
    /// Listen on `port`: on this computer's address on its network (`everyone`), or for this computer only. Each
    /// connection gets its own thread; requests for the editor wake the window (`ctx`).
    pub(crate) fn start(port: u16, everyone: bool, code: &str, ctx: egui::Context) -> Result<WebServer, StartError> {
        let host = if everyone { lan_address().ok_or(StartError::NoNetwork)? } else { IpAddr::from([127, 0, 0, 1]) };
        let listener = TcpListener::bind((host, port)).map_err(|e| StartError::Port(port, e))?;
        listener.set_nonblocking(true).map_err(|e| StartError::Port(port, e))?;
        let bound = listener.local_addr().map_err(|e| StartError::Port(port, e))?;
        let url = format!("http://{}", SocketAddr::new(bound.ip(), bound.port()));
        let stop = Arc::new(AtomicBool::new(false));
        let (tx, requests) = mpsc::channel();
        let gate = Arc::new(Gate::new(code, bound.port()));
        let open = Arc::new(AtomicUsize::new(0));
        let (stop2, gate2, open2) = (stop.clone(), gate.clone(), open.clone());
        let thread = std::thread::spawn(move || {
            let by_address = Arc::new(Mutex::new(HashMap::<IpAddr, usize>::new()));
            while !stop2.load(Ordering::Relaxed) {
                match listener.accept() {
                    Ok((stream, peer)) => {
                        // a client that holds connections open without finishing them keeps its own slots only
                        let ip = peer.ip();
                        {
                            let mut by = by_address.lock().unwrap_or_else(|e| e.into_inner());
                            if open2.load(Ordering::Relaxed) >= MAX_CONNECTIONS || by.get(&ip).is_some_and(|&n| n >= MAX_PER_ADDRESS) {
                                continue;
                            }
                            *by.entry(ip).or_default() += 1;
                        }
                        open2.fetch_add(1, Ordering::AcqRel);
                        let guard = SlotGuard(open2.clone(), by_address.clone(), ip);
                        let (tx, ctx, gate) = (tx.clone(), ctx.clone(), gate2.clone());
                        std::thread::spawn(move || {
                            let _guard = guard;
                            let _ = serve(stream, peer, &gate, &tx, &ctx);
                        });
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => std::thread::sleep(Duration::from_millis(50)),
                    Err(_) => std::thread::sleep(Duration::from_millis(200)),
                }
            }
        });
        Ok(WebServer { url, code: code.to_string(), everyone, stop, gate, open, requests, thread: Some(thread), last: None })
    }

    /// Answer every request waiting for the editor: the page is closing.
    fn say_goodbye(&self) {
        for r in self.requests.try_iter() {
            let _ = r.reply.send(WebReply::closed());
        }
    }
}

impl Drop for WebServer {
    fn drop(&mut self) {
        // goodbye: what waits for the editor, and what comes in from now on, is answered that the page has closed
        self.gate.closing.store(true, Ordering::Relaxed);
        self.say_goodbye();
        self.stop.store(true, Ordering::Relaxed);
        if let Some(t) = self.thread.take() {
            let _ = t.join();
        }
        // a moment for those answers to go out before the editor quits
        let t = Instant::now();
        while self.open.load(Ordering::Relaxed) > 0 && t.elapsed() < Duration::from_millis(500) {
            self.say_goodbye();
            std::thread::sleep(Duration::from_millis(20));
        }
    }
}

/// This computer's address on the network its default route goes out on (no packet is sent:
/// connecting a UDP socket only picks the route).
fn lan_address() -> Option<std::net::IpAddr> {
    let s = std::net::UdpSocket::bind("0.0.0.0:0").ok()?;
    s.connect("192.0.2.1:9").ok()?;
    s.local_addr().ok().map(|a| a.ip()).filter(|ip| !ip.is_unspecified())
}

/// `N` bytes from the system's random source (/dev/urandom on Unix and macOS); elsewhere, or when it cannot be read,
/// from hashers the standard library keys from it.
fn random_bytes<const N: usize>() -> [u8; N] {
    let mut out = [0u8; N];
    #[cfg(unix)]
    if std::fs::File::open("/dev/urandom").and_then(|mut f| f.read_exact(&mut out)).is_ok() {
        return out;
    }
    use std::hash::{BuildHasher, Hasher};
    static DRAWN: AtomicUsize = AtomicUsize::new(0);
    for (i, chunk) in out.chunks_mut(8).enumerate() {
        // RandomState is keyed from the system's random source
        let mut h = std::collections::hash_map::RandomState::new().build_hasher();
        h.write_u128(std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0));
        h.write_usize(DRAWN.fetch_add(1, Ordering::Relaxed));
        h.write_usize(i);
        chunk.copy_from_slice(&h.finish().to_le_bytes()[..chunk.len()]);
    }
    out
}

/// A new access code: eight letters and digits that cannot be mistaken for each other, as ABCD-EFGH.
pub(crate) fn new_code() -> String {
    const LETTERS: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    let mut x = random_bytes::<8>().iter().fold(0u64, |a, &b| a << 8 | u64::from(b));
    let mut out = String::new();
    for i in 0..8 {
        if i == 4 {
            out.push('-');
        }
        out.push(LETTERS[(x & 31) as usize] as char);
        x >>= 5;
    }
    out
}

/// A session token: 128 bits as hex.
fn new_token() -> String {
    random_bytes::<16>().iter().map(|b| format!("{b:02x}")).collect()
}

/// This computer's own names, as a browser on the network may reach it ("studio", "studio.local"), lower case.
fn host_names() -> Vec<String> {
    #[cfg(unix)]
    let name = {
        let mut buf = [0u8; 256];
        // SAFETY: gethostname writes at most buf.len() bytes into buf
        let ok = unsafe { libc::gethostname(buf.as_mut_ptr().cast(), buf.len()) } == 0;
        if ok { String::from_utf8_lossy(&buf[..buf.iter().position(|&b| b == 0).unwrap_or(buf.len())]).to_string() } else { String::new() }
    };
    #[cfg(not(unix))]
    let name = std::env::var("COMPUTERNAME").unwrap_or_default();
    let name = name.trim().trim_end_matches('.').to_ascii_lowercase();
    if name.is_empty() {
        return Vec::new();
    }
    let short = name.strip_suffix(".local").unwrap_or(&name).to_string();
    let mut names = vec![name.clone(), format!("{short}.local"), short];
    names.dedup();
    names
}

/// What the server thread checks before a request reaches the editor: where it was sent (`Host`), which page sent
/// it (`Origin`), and who sent it: a session, or the access code, whose wrong guesses are counted per client address.
struct Gate {
    /// The access code as compared (`normal_code`).
    code: String,
    port: u16,
    names: Vec<String>,
    sessions: Mutex<HashMap<String, Instant>>,
    wrong: Mutex<HashMap<IpAddr, Vec<Instant>>>,
    /// `SESSION_IDLE` and `WRONG_WINDOW` (shorter in the tests).
    session_idle: Duration,
    wrong_window: Duration,
    /// The page is being turned off, or the editor quits.
    closing: AtomicBool,
}

impl Gate {
    fn new(code: &str, port: u16) -> Gate {
        Gate { code: normal_code(code), port, names: host_names(), sessions: Mutex::default(), wrong: Mutex::default(),
               session_idle: SESSION_IDLE, wrong_window: WRONG_WINDOW, closing: AtomicBool::new(false) }
    }

    /// The request was sent to this server: to a loopback name or address (any port: an SSH tunnel may forward
    /// another), or with this server's port to an address (v4 or v6) or this computer's name. A site that has its own
    /// name point at this computer (DNS rebinding) sends its own name, which is none of these.
    fn host_ok(&self, host: &str) -> bool {
        let host = host.trim().to_ascii_lowercase();
        let (name, port) = match host.rsplit_once(':') {
            Some((n, p)) if !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()) && (n.starts_with('[') || !n.contains(':')) => (n, p.parse::<u16>().ok()),
            _ => (host.as_str(), None),
        };
        let bare = name.trim_start_matches('[').trim_end_matches(']');
        let ip = bare.parse::<IpAddr>().ok();
        if bare == "localhost" || ip.is_some_and(|ip| ip.is_loopback()) {
            return true;
        }
        port == Some(self.port) && (ip.is_some() || self.names.iter().any(|n| n == bare))
    }

    /// The client address wrong codes are counted under: its IPv6 network (the first 64 bits), so one client cannot
    /// spread its guesses over the addresses of its own network.
    fn counted_as(ip: IpAddr) -> IpAddr {
        match ip {
            IpAddr::V6(v6) if v6.to_ipv4_mapped().is_none() => {
                let s = v6.segments();
                IpAddr::from([s[0], s[1], s[2], s[3], 0, 0, 0, 0])
            }
            IpAddr::V6(v6) => IpAddr::V4(v6.to_ipv4_mapped().unwrap_or(std::net::Ipv4Addr::UNSPECIFIED)),
            v4 => v4,
        }
    }

    /// The access code given, checked: wrong ones count for the client address for `WRONG_WINDOW`; while it has sent
    /// `MAX_WRONG`, its codes are not compared at all (429). Every other address, and every session, goes on.
    fn check_code(&self, given: &str, ip: IpAddr) -> Result<(), WebReply> {
        if given.trim().is_empty() {
            return Err(WebReply::error(401, "Enter the access code shown in the editor: Settings > Camera support & web page > Web page for a phone or tablet."));
        }
        let who = Self::counted_as(ip);
        let mut wrong = self.wrong.lock().unwrap_or_else(|e| e.into_inner());
        wrong.retain(|_, times| {
            times.retain(|t| t.elapsed() < self.wrong_window);
            !times.is_empty()
        });
        let counted = wrong.contains_key(&who);
        if wrong.get(&who).is_some_and(|t| t.len() >= MAX_WRONG) || (!counted && wrong.len() >= MAX_COUNTED) {
            return Err(WebReply::error(429, "Too many wrong access codes from this device: it can try again in a minute."));
        }
        if code_ok(given, &self.code) {
            return Ok(());
        }
        wrong.entry(who).or_default().push(Instant::now());
        Err(WebReply::error(401, "That is not the access code. It is shown in the editor: Settings > Camera support & web page > Web page for a phone or tablet."))
    }

    /// Exchange the access code for a session.
    fn login(&self, code: &str, ip: IpAddr) -> WebReply {
        if let Err(r) = self.check_code(code, ip) {
            return r;
        }
        let token = new_token();
        let mut s = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        s.retain(|_, used| used.elapsed() < self.session_idle);
        while s.len() >= MAX_SESSIONS {
            let Some(oldest) = s.iter().min_by_key(|(_, used)| **used).map(|(t, _)| t.clone()) else { break };
            s.remove(&oldest);
        }
        s.insert(token.clone(), Instant::now());
        WebReply::json(json!({ "session": token, "idle_hours": self.session_idle.as_secs() / 3600 }))
    }

    /// End the session the request carries.
    fn logout(&self, token: &str) -> WebReply {
        self.sessions.lock().unwrap_or_else(|e| e.into_inner()).remove(token.trim());
        WebReply::json(json!({ "ok": true }))
    }

    /// Whether a request for the editor may go on: a session that has not ended (its time starts again), else the
    /// access code itself.
    fn admit(&self, req: &Request, ip: IpAddr) -> Result<(), WebReply> {
        let token = req.header("x-camset-session").trim();
        if !token.is_empty() {
            let mut s = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
            return match s.get_mut(token) {
                Some(used) if used.elapsed() < self.session_idle => {
                    *used = Instant::now();
                    Ok(())
                }
                _ => {
                    s.remove(token);
                    Err(WebReply::refused(401, "This page's session has ended: enter the access code again.", json!({ "session": "ended" })))
                }
            };
        }
        self.check_code(req.header("x-camset-code"), ip)
    }
}

/// A code as typed: case, spaces and dashes do not matter.
fn normal_code(c: &str) -> String {
    c.chars().filter(|c| c.is_ascii_alphanumeric()).map(|c| c.to_ascii_uppercase()).collect()
}

fn code_ok(given: &str, code: &str) -> bool {
    let given = normal_code(given);
    // compare every byte, so the time taken does not tell how much of a guess was right
    !code.is_empty() && given.len() == code.len() && given.bytes().zip(code.bytes()).fold(0u8, |acc, (a, b)| acc | (a ^ b)) == 0
}

pub(crate) fn percent_decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        let hex = |c: u8| (c as char).to_digit(16);
        match (b[i], b.get(i + 1).copied().and_then(hex), b.get(i + 2).copied().and_then(hex)) {
            (b'%', Some(h), Some(l)) => {
                out.push((h * 16 + l) as u8);
                i += 3;
            }
            (c, _, _) => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

struct Request {
    method: String,
    path: String,
    headers: Vec<(String, String)>,
    body: Vec<u8>,
}

impl Request {
    fn header(&self, name: &str) -> &str {
        self.headers.iter().find(|(k, _)| k == name).map_or("", |(_, v)| v.as_str())
    }
}

fn serve(mut stream: TcpStream, peer: SocketAddr, gate: &Gate, tx: &mpsc::Sender<WebRequest>, ctx: &egui::Context) -> std::io::Result<()> {
    // an accepted socket can inherit the listener's non-blocking mode
    stream.set_nonblocking(false)?;
    stream.set_write_timeout(Some(Duration::from_secs(30)))?;
    let reply = match read_request(&mut stream) {
        Ok(req) => route(req, peer, gate, tx, ctx),
        Err(why) => WebReply::error(400, &why),
    };
    write_reply(&mut stream, &reply)
}

/// Wait for the next bytes until `until` at most: a request that trickles in does not hold its connection for long.
fn read_by(s: &mut TcpStream, buf: &mut [u8], until: Instant) -> Result<usize, String> {
    let left = until.saturating_duration_since(Instant::now());
    if left.is_zero() {
        return Err("the request took too long to arrive".into());
    }
    s.set_read_timeout(Some(left)).map_err(|e| e.to_string())?;
    s.read(buf).map_err(|e| e.to_string())
}

fn read_request(s: &mut TcpStream) -> Result<Request, String> {
    let mut buf = Vec::new();
    let mut chunk = [0u8; 16 << 10];
    let head_by = Instant::now() + HEAD_DEADLINE;
    let head_end = loop {
        if let Some(i) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
            break i;
        }
        if buf.len() > MAX_HEAD {
            return Err("request head too long".into());
        }
        let n = read_by(s, &mut chunk, head_by)?;
        if n == 0 {
            return Err("connection closed".into());
        }
        buf.extend_from_slice(&chunk[..n]);
    };
    let head = String::from_utf8_lossy(&buf[..head_end]).into_owned();
    let mut lines = head.split("\r\n");
    let mut first = lines.next().unwrap_or("").split(' ');
    let method = first.next().unwrap_or("").to_string();
    let path = first.next().unwrap_or("/").split('?').next().unwrap_or("/").to_string();
    let headers: Vec<(String, String)> = lines.filter_map(|l| l.split_once(':')).map(|(k, v)| (k.trim().to_ascii_lowercase(), v.trim().to_string())).collect();
    let mut req = Request { method, path, headers, body: Vec::new() };
    if !req.header("transfer-encoding").is_empty() {
        return Err("send the body with a Content-Length".into());
    }
    let len: usize = req.header("content-length").parse().unwrap_or(0);
    if len > MAX_BODY {
        return Err("request too large".into());
    }
    if req.header("expect").eq_ignore_ascii_case("100-continue") {
        s.write_all(b"HTTP/1.1 100 Continue\r\n\r\n").map_err(|e| e.to_string())?;
    }
    let mut body = buf[head_end + 4..].to_vec();
    let body_by = Instant::now() + BODY_DEADLINE;
    while body.len() < len {
        let n = read_by(s, &mut chunk, body_by)?;
        if n == 0 {
            return Err("request cut short".into());
        }
        body.extend_from_slice(&chunk[..n]);
    }
    body.truncate(len);
    req.body = body;
    Ok(req)
}

/// The page and its files are served here; API requests go to the editor once the gate lets them through. Every
/// request must be sent to this server (`Gate::host_ok`); a request for the editor that a page sent must come from
/// this server's own page (`Origin`, when present). No CORS header is ever sent, so no other site may read an answer.
fn route(req: Request, peer: SocketAddr, gate: &Gate, tx: &mpsc::Sender<WebRequest>, ctx: &egui::Context) -> WebReply {
    let host = req.header("host");
    if !gate.host_ok(host) {
        return WebReply::error(403, "Open the page at the address the editor shows.");
    }
    let origin = req.header("origin");
    let same_origin = origin.is_empty() || origin.eq_ignore_ascii_case(&format!("http://{}", host.trim()));
    match (req.method.as_str(), req.path.as_str()) {
        ("GET", "/") | ("GET", "/index.html") => WebReply::fixed("text/html; charset=utf-8", PAGE.as_bytes()),
        ("GET", "/app.js") => WebReply::fixed("text/javascript; charset=utf-8", SCRIPT.as_bytes()),
        ("GET", "/icon.png") => WebReply::fixed("image/png", ICON),
        ("GET", "/font-ubuntu.ttf") => WebReply::font("Ubuntu-Light"),
        ("GET", "/font-hack.ttf") => WebReply::font("Hack"),
        ("POST", p) if p.starts_with("/api/") && !same_origin => WebReply::error(403, "Only the editor's own page may send it requests."),
        ("POST", "/api/login") => gate.login(req.header("x-camset-code"), peer.ip()),
        ("POST", "/api/logout") => gate.logout(req.header("x-camset-session")),
        ("POST", p) if p.starts_with("/api/") => {
            if let Err(refused) = gate.admit(&req, peer.ip()) {
                return refused;
            }
            if gate.closing.load(Ordering::Relaxed) {
                return WebReply::closed();
            }
            let (reply, answer) = mpsc::channel();
            let discard = req.header("x-camset-discard") == "1";
            let r = WebRequest { name: p["/api/".len()..].to_string(), file_name: req.header("x-file-name").to_string(), discard, body: req.body, peer: peer.ip().to_string(), reply };
            if tx.send(r).is_err() {
                return WebReply::closed();
            }
            ctx.request_repaint();
            answer.recv_timeout(REPLY_WAIT).unwrap_or_else(|_| {
                if gate.closing.load(Ordering::Relaxed) { WebReply::closed() } else { WebReply::error(503, "The editor did not answer. Is its window still open?") }
            })
        }
        ("GET", _) => WebReply::error(404, "not found"),
        _ => WebReply::error(405, "not allowed"),
    }
}

/// The reason phrase of a status line, for every status the server and the answers send.
fn reason(status: u16) -> &'static str {
    match status {
        200 => "OK",
        400 => "Bad Request",
        401 => "Unauthorized",
        403 => "Forbidden",
        404 => "Not Found",
        405 => "Method Not Allowed",
        409 => "Conflict",
        429 => "Too Many Requests",
        500 => "Internal Server Error",
        503 => "Service Unavailable",
        _ => "",
    }
}

fn write_reply(s: &mut TcpStream, r: &WebReply) -> std::io::Result<()> {
    let reason = reason(r.status);
    let cache = if r.keep { "public, max-age=31536000" } else { "no-store" };
    let mut head = format!(
        "HTTP/1.1 {} {reason}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\nCache-Control: {cache}\r\n\
         X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nX-Frame-Options: DENY\r\n\
         Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'\r\n",
        r.status, r.content_type, r.body.len()
    );
    if let Some(name) = &r.download {
        head += &format!("Content-Disposition: attachment; filename=\"{name}\"\r\n");
    }
    head += "\r\n";
    s.write_all(head.as_bytes())?;
    s.write_all(&r.body)?;
    s.flush()?;
    s.shutdown(std::net::Shutdown::Write)
}

/// Only letters, digits, dots, dashes and underscores, for a file name.
pub(crate) fn safe_name(name: &str) -> String {
    name.chars().map(|c| if c.is_ascii_alphanumeric() || "._-".contains(c) { c } else { '_' }).take(64).collect()
}

/// A file's name without its folders, for a reply: the page is told no path on the editor's computer. A text that
/// is not a path ("built-in") stays as it is.
pub(crate) fn file_name_of(p: &str) -> String {
    Path::new(p).file_name().map_or_else(|| p.to_string(), |n| n.to_string_lossy().to_string())
}

/// `text` without network addresses: an IPv4 address reads "(its address)" and a MAC address "(its MAC address)".
/// The desktop's status line may name the camera's; the page's never does.
pub(crate) fn without_addresses(text: &str) -> String {
    let b = text.as_bytes();
    let mut out = String::with_capacity(text.len());
    let (mut i, mut kept) = (0, 0);
    // a run of the characters an address is written with, not inside a longer word or number
    let edge = |j: usize| j >= b.len() || !(b[j].is_ascii_alphanumeric() || b[j] == b'.' || b[j] == b':' || b[j] == b'-');
    while i < b.len() {
        if (i == 0 || edge(i - 1)) && b[i].is_ascii_hexdigit() {
            let mut j = i;
            while j < b.len() && (b[j].is_ascii_hexdigit() || b[j] == b'.' || b[j] == b':' || b[j] == b'-') { j += 1; }
            // a sentence may end right after it
            let mut end = j;
            while end > i && matches!(b[end - 1], b'.' | b':' | b'-') { end -= 1; }
            let word = &text[i..end];
            // with or without a port after it
            let host = match word.split_once(':') { Some((h, port)) if !port.is_empty() && port.bytes().all(|c| c.is_ascii_digit()) => h, _ => word };
            let ipv4 = host.split('.').count() == 4 && host.split('.').all(|p| !p.is_empty() && p.len() <= 3 && p.bytes().all(|c| c.is_ascii_digit()));
            let mac = [':', '-'].iter().any(|&sep| word.split(sep).count() == 6 && word.split(sep).all(|p| p.len() == 2 && p.bytes().all(|c| c.is_ascii_hexdigit())));
            if (ipv4 || mac) && edge(j) {
                out.push_str(&text[kept..i]);
                out.push_str(if ipv4 { "(its address)" } else { "(its MAC address)" });
                kept = end;
            }
            i = j.max(i + 1);
            continue;
        }
        i += 1;
    }
    out.push_str(&text[kept..]);
    out
}

/// A reply's body as JSON (Null when it is not JSON), for the tests of the server and of the answers.
#[cfg(test)]
pub(crate) fn body(r: &WebReply) -> Value {
    serde_json::from_slice(&r.body).unwrap_or(Value::Null)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn codes() {
        let c = new_code();
        assert_eq!(c.len(), 9);
        assert_eq!(&c[4..5], "-");
        assert!(c.chars().all(|ch| ch == '-' || "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".contains(ch)));
        assert_ne!(new_code(), c);
        let n = normal_code(&c);
        assert!(code_ok(&c, &n));
        assert!(code_ok(&c.to_lowercase().replace('-', " "), &n));
        assert!(!code_ok("", &n));
        assert!(!code_ok(&c[..8], &n));
        assert!(!code_ok("anything", ""));
    }

    #[test]
    fn names_and_escapes() {
        assert_eq!(percent_decode("CAM%20SET%2B1.DAT"), "CAM SET+1.DAT");
        assert_eq!(percent_decode("50%"), "50%");
        assert_eq!(safe_name("../../etc/pass wd.DAT"), ".._.._etc_pass_wd.DAT");
    }

    fn get(path: &str) -> WebReply {
        let req = Request { method: "GET".into(), path: path.into(), headers: vec![("host".into(), "127.0.0.1:8642".into())], body: Vec::new() };
        let (tx, _rx) = mpsc::channel();
        route(req, "127.0.0.1:1".parse().unwrap(), &Gate::new("CODE-WORD", 8642), &tx, &egui::Context::default())
    }

    /// A request for the editor as a browser sends it, through the gate only (nothing answers for the editor: a
    /// request let through gets the "did not answer" 503 at once, its channel being closed).
    fn post(gate: &Gate, from: &str, path: &str, headers: &[(&str, &str)]) -> WebReply {
        let mut h: Vec<(String, String)> = vec![("host".into(), "192.168.1.20:8642".into())];
        for (k, v) in headers {
            h.retain(|(name, _)| name != k);
            h.push((k.to_string(), v.to_string()));
        }
        let req = Request { method: "POST".into(), path: path.into(), headers: h, body: b"{}".to_vec() };
        let (tx, rx) = mpsc::channel();
        drop(rx);
        route(req, format!("{from}:50000").parse().unwrap(), gate, &tx, &egui::Context::default())
    }

    /// Only requests sent to this server are answered: to its address with its port, to this computer's name, or to
    /// a loopback name with any port (an SSH tunnel); a site's own name (DNS rebinding) is refused, and so is a
    /// request for the editor from another site's page.
    #[test]
    fn host_and_origin() {
        let mut gate = Gate::new("ABCD-EFGH", 8642);
        gate.names = vec!["studio".into(), "studio.local".into()];
        for ok in ["192.168.1.20:8642", "studio.local:8642", "STUDIO:8642", "[fe80::1]:8642", "localhost:9000", "127.0.0.1:1234", "[::1]:8642", "localhost"] {
            assert!(gate.host_ok(ok), "{ok}");
        }
        for bad in ["", "evil.example:8642", "studio.local:8000", "192.168.1.20:80", "192.168.1.20", "studio.local", "localhost.evil.example:8642"] {
            assert!(!gate.host_ok(bad), "{bad}");
        }
        assert_eq!(post(&gate, "192.168.1.77", "/api/state", &[("host", "evil.example:8642"), ("x-camset-code", "ABCD-EFGH")]).status, 403);
        let cross = post(&gate, "192.168.1.77", "/api/login", &[("origin", "http://evil.example"), ("x-camset-code", "ABCD-EFGH")]);
        assert_eq!(cross.status, 403);
        let own = post(&gate, "192.168.1.77", "/api/login", &[("origin", "http://192.168.1.20:8642"), ("x-camset-code", "ABCD-EFGH")]);
        assert_eq!(own.status, 200);
        assert!(gate.wrong.lock().unwrap().is_empty(), "refused before any code is looked at");
    }

    /// The code is exchanged once for a session, which every later request carries; a session ends at logout, or after
    /// 12 hours unused. Wrong codes count per client address, decay after a minute, and never stop another device or
    /// a session; a request with no code at all is not counted.
    #[test]
    fn sessions_and_wrong_codes() {
        let mut gate = Gate::new("ABCD-EFGH", 8642);
        let login = post(&gate, "192.168.1.77", "/api/login", &[("x-camset-code", "abcd efgh")]);
        assert_eq!(login.status, 200);
        let token = body(&login)["session"].as_str().unwrap().to_string();
        assert_eq!((token.len(), body(&login)["idle_hours"].as_u64()), (32, Some(12)));
        let with_session = |from: &str| post(&gate, from, "/api/state", &[("x-camset-session", token.as_str())]).status;
        assert_eq!(with_session("192.168.1.77"), 503, "let through (nothing answers for the editor here)");
        // ten wrong codes from one device: that device's codes are refused; another device's, and the session, go on
        for _ in 0..MAX_WRONG {
            assert_eq!(post(&gate, "192.168.1.99", "/api/state", &[("x-camset-code", "WRONG-ONE")]).status, 401);
        }
        assert_eq!(post(&gate, "192.168.1.99", "/api/login", &[("x-camset-code", "ABCD-EFGH")]).status, 429);
        assert_eq!(post(&gate, "192.168.1.77", "/api/login", &[("x-camset-code", "ABCD-EFGH")]).status, 200);
        assert_eq!(with_session("192.168.1.99"), 503, "a session is never refused for wrong codes");
        // no code at all: refused, not counted
        assert_eq!(post(&gate, "192.168.1.60", "/api/state", &[]).status, 401);
        assert!(!gate.wrong.lock().unwrap().contains_key(&"192.168.1.60".parse::<IpAddr>().unwrap()));
        // the minute passes: the device may try again
        gate.wrong_window = Duration::ZERO;
        assert_eq!(post(&gate, "192.168.1.99", "/api/login", &[("x-camset-code", "ABCD-EFGH")]).status, 200);
        // one IPv6 network counts as one device
        assert_eq!(Gate::counted_as("2001:db8:1:2:aaaa::1".parse().unwrap()), Gate::counted_as("2001:db8:1:2:bbbb::9".parse().unwrap()));
        // logout ends the session; so does 12 hours unused
        assert_eq!(post(&gate, "192.168.1.77", "/api/logout", &[("x-camset-session", token.as_str())]).status, 200);
        let ended = post(&gate, "192.168.1.77", "/api/state", &[("x-camset-session", token.as_str())]);
        assert_eq!((ended.status, body(&ended)["session"].as_str()), (401, Some("ended")));
        let again = body(&post(&gate, "192.168.1.77", "/api/login", &[("x-camset-code", "ABCD-EFGH")]))["session"].as_str().unwrap().to_string();
        gate.session_idle = Duration::ZERO;
        assert_eq!(post(&gate, "192.168.1.77", "/api/state", &[("x-camset-session", again.as_str())]).status, 401);
        // the code itself is still taken on each request, for a page from before sessions
        assert_eq!(post(&gate, "192.168.1.77", "/api/state", &[("x-camset-code", "ABCD-EFGH")]).status, 503);
    }

    /// Every status the server and the answers send has its reason phrase on the status line: the statuses are the
    /// ones web/mod.rs and this file name in `WebReply::error`, `refused` and the replies they build.
    #[test]
    fn every_status_has_its_reason() {
        let sources = [include_str!("mod.rs"), include_str!("server.rs")].concat();
        let mut sent: Vec<u16> = vec![200];
        for (i, _) in sources.match_indices("error(").chain(sources.match_indices("refused(")).chain(sources.match_indices("status: ")) {
            let at = sources[i..].find(['(', ':']).map_or(i, |k| i + k + 1);
            let digits: String = sources[at..].trim_start().chars().take_while(char::is_ascii_digit).collect();
            if let Ok(n) = digits.parse::<u16>() { if (100..600).contains(&n) { sent.push(n); } }
        }
        sent.sort_unstable();
        sent.dedup();
        assert!(sent.contains(&500) && sent.contains(&409), "{sent:?}");
        for n in sent {
            assert!(!reason(n).is_empty(), "status {n} has no reason phrase");
        }
    }

    /// A port another program holds: why the page did not start in plain words, the system's own kept for Expert mode.
    #[test]
    fn a_port_in_use_in_plain_words() {
        let first = WebServer::start(0, false, "ABCD-EFGH", egui::Context::default()).unwrap();
        let port: u16 = first.url.rsplit(':').next().unwrap().parse().unwrap();
        let e = WebServer::start(port, false, "ABCD-EFGH", egui::Context::default()).err().expect("the port is taken");
        let said = e.words();
        assert!(said.starts_with(&format!("another program is using port {port}")) && !said.contains("os error"), "{said}");
        assert!(e.system_words().is_some_and(|w| w.starts_with(&format!("port {port}: "))));
        assert!(StartError::NoNetwork.system_words().is_none() && StartError::NoNetwork.words().contains("this computer only"));
    }

    /// Turning the page off (or quitting) answers a request still waiting for the editor: the page has closed.
    #[test]
    fn goodbye_when_the_page_closes() {
        let w = WebServer::start(0, false, "ABCD-EFGH", egui::Context::default()).unwrap();
        let addr = w.url.trim_start_matches("http://").to_string();
        let client = std::thread::spawn(move || {
            let mut s = TcpStream::connect(&addr).unwrap();
            let req = format!("POST /api/state HTTP/1.1\r\nHost: {addr}\r\nX-Camset-Code: ABCD-EFGH\r\nContent-Length: 2\r\n\r\n{{}}");
            s.write_all(req.as_bytes()).unwrap();
            let mut out = String::new();
            s.read_to_string(&mut out).unwrap();
            out
        });
        let t = Instant::now();
        while w.open.load(Ordering::Relaxed) == 0 && t.elapsed() < Duration::from_secs(5) {
            std::thread::sleep(Duration::from_millis(10));
        }
        std::thread::sleep(Duration::from_millis(100));
        drop(w);
        let out = client.join().unwrap();
        assert!(out.starts_with("HTTP/1.1 503") && out.contains("\"closed\":true"), "{out}");
    }

    /// The window's fonts are served from the program for the page, and kept by the browser.
    #[test]
    fn fonts_from_the_program() {
        for (path, name) in [("/font-ubuntu.ttf", "Ubuntu-Light"), ("/font-hack.ttf", "Hack")] {
            let font = egui_font(name);
            assert!(font.len() > 10_000, "{name} is not in the program");
            assert_eq!(&font[..4], &[0, 1, 0, 0], "{name} is not a TrueType font");
            let r = get(path);
            assert_eq!((r.status, r.content_type, r.keep, r.body.len()), (200, "font/ttf", true, font.len()));
        }
        assert!(!get("/").keep);
        assert!(!get("/app.js").keep);
        assert_eq!(get("/font-other.ttf").status, 404);
    }
}
