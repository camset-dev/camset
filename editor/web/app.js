"use strict";
// The web page of Camset Editor, laid out like its window: the toolbar, the Editing row, the Menu
// column, the page and the status bar. The editor does all the work: this page asks it for the
// open file's settings, sends it each change, and shows what it answers.

const $ = (id) => document.getElementById(id);

/** An element with attributes, listeners (on…), a style ({prop: value}) and children. */
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "style") for (const [p, x] of Object.entries(v)) { if (x) e.style.setProperty(p, x); }
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k);
  return e;
}

/** The editor draws ✔ ⚠ ⬇ ⬆ ↩ as plain symbols; a browser may draw them as coloured emoji unless asked not to. */
const plain = (s) => String(s).replace(/([←-⇿☀-➿⬀-⯿])(?!︎)/g, "$1︎");

/** Put a text into an element only when it changed: the status bar's live regions are then not read out again, nor
 *  the toolbar measured again, for the same words at every poll. */
function setText(node, text) {
  if (node.textContent !== text) node.textContent = text;
}

/** An element that acts as a button (a name that unfolds, a link in a table, a badge with more to say): reached with
 *  Tab, and Enter or Space does what a click does. */
function pressable(node, run) {
  node.setAttribute("role", "button");
  node.setAttribute("tabindex", "0");
  node.addEventListener("click", run);
  node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); run(e); } });
  return node;
}

/** A button greyed out while `why` says why (empty turns it back on), kept in the Tab order: a disabled button is
 *  skipped by Tab, so a keyboard user would not know it is there, and its hover text reaches neither the keyboard nor
 *  a touch screen. Pressed while greyed out, it says why (`saysWhy`) instead of acting. */
function greyOut(b, why) {
  b.disabled = false;
  b.classList.toggle("off", !!why);
  b.setAttribute("aria-disabled", String(!!why));
  b.dataset.why = why || "";
  return b;
}

/** A button pressed while greyed out (`greyOut`): its reason in the toast, and true, so its own action is not done. */
function saysWhy(b) {
  if (!b.dataset.why) return false;
  toast(b.dataset.why);
  return true;
}

/** A button that acts with `run`, or, greyed out while `why` says why, says that instead (`greyOut`). */
function offButton(attrs, label, run, why) {
  const b = el("button", { ...attrs, onclick: () => { if (!saysWhy(b)) run(); } }, label);
  return greyOut(b, why);
}

/** A pop-up (a menu, a picker) at (x, y), moved in where it would run off the screen, and no taller than the part of
 *  the screen the browser leaves visible (a phone's browser bars take some of what CSS's 100vh counts), so its own
 *  scroll reaches its last item. */
function placeAt(box, x, y) {
  box.style.maxHeight = `${Math.max(40, innerHeight - 8)}px`;
  box.style.left = `${Math.max(4, Math.min(x, innerWidth - box.offsetWidth - 4))}px`;
  box.style.top = `${Math.max(4, Math.min(y, innerHeight - box.offsetHeight - 4))}px`;
}

/** A menu's keys (More, a compare cell's menu): the arrows, Home and End step through its items; Escape closes it
 *  and gives the focus back (`close(true)`); Tab closes it too, the focus back on the control that opened it, from
 *  where the browser's Tab moves on (not from the edge of the page, as from a menu taken away under the focus). */
function menuKeys(box, close) {
  box.addEventListener("keydown", (e) => {
    const items = [...box.querySelectorAll("button:not(:disabled)")];
    const i = items.indexOf(document.activeElement);
    const to = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key];
    if (to !== undefined && items.length) {
      e.preventDefault();
      items[(to + items.length) % items.length].focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close(true);
    } else if (e.key === "Tab") close(true);
  });
}

/** How the control that has the focus got it: from the keyboard (Tab, an arrow, a key that opened something), or
 *  from a tap or a click. Typing into a field it was tapped into does not change it, so a phone's number box, typed
 *  into and sent with Go, still lets go of the focus (and of the on-screen keyboard), as it always did; a browser's
 *  `:focus-visible` cannot tell that apart, as it always matches a text field. Kept by the listeners at the end. */
const focusOrigin = { last: "pointer", keys: false };

/** Whether the focus came from the keyboard, so it is worth keeping through a change and a redraw; a tapped or
 *  clicked control lets go, so the page is drawn again with the answer at once. */
function keyboardFocus() {
  return focusOrigin.keys;
}

/** What the page keeps in this browser only (camset_…): the page works when nothing can be kept. */
const store = {
  get(k) { try { return localStorage.getItem("camset_" + k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem("camset_" + k, v); } catch { /* not kept */ } },
  remove(k) { try { localStorage.removeItem("camset_" + k); } catch { /* nothing kept */ } },
};
// the access code was kept as camset-code before the keys were named alike
try {
  const old = localStorage.getItem("camset-code");
  if (old !== null) { localStorage.removeItem("camset-code"); if (store.get("code") === null) store.set("code", old); }
} catch { /* nothing kept */ }

/** The file name of a path, whatever follows it in brackets (an explanation) left out; the full text stays as hover text. */
function fileName(t) {
  const path = String(t || "").replace(/\s+\(.*$/s, "");
  return path.split(/[\\/]/).filter(Boolean).pop() || String(t || "");
}

/** Where the desktop app shows the access code. */
const WEB_SETTINGS = "Settings > Camera support & web page > Web page for a phone or tablet";
/** Where the desktop app takes the camera's user name and password. */
const DESK_LOGIN = "Connect to the camera > Network address and camera login";
/** A message naming the access code's place in older words, put in the desktop app's. */
const wherePut = (t) => String(t).replace(/Settings(?: > |, )Web page/g, WEB_SETTINGS);

class CodeError extends Error {}
/** A request the editor refused (4xx): its reason, and the rest of its answer (a setting's current value or row). */
class Refused extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body || {};
  }
}
/** The editor did not answer: it closed or turned its web page off (`closed`, a 503), or is out of reach. */
class Offline extends Error {
  constructor(message, closed = false) {
    super(message);
    this.closed = closed;
  }
}
/** Too many wrong codes reached the editor (from anywhere): it takes none for a while. The code kept here stays. */
class TooMany extends Error {}
const UNREACHABLE = "The editor could not be reached. Is it still running, with the web page on?";

// --- the page's state: what it shows and how, none of it the editor's ---

let code = null;   // the access code typed or given by the link, for this page's life
let state = null;
// page: "main", "tab" or "edits"; a search (q) shows its results over any of them
const view = { page: "main", tab: null, target: 0, q: "", only: false, set: 0, focus: null, mode: "edit" };
let drawn = null;          // what the page was last drawn for
let loading = 0;           // the newest page request; answers to older ones are dropped
let hits = null;           // settings the search found
const openGroups = new Map();  // per tab: the groups left open
// The page's own Compare view, kept here as the window keeps its own, so neither moves the other:
// the columns ([file, set], the first the baseline; null until the state gives the window's), the
// search, the tab ("" for all), "Only rows that differ" and "Show raw values" (null: the window's
// choice), the three-way filter, the tabs and groups folded, the difference cursor (a row's index),
// the record map, the files the columns were made for, the Edit page to go back to, the last answer
// drawn and the change map's marks.
const cmp = { cols: null, q: "", tab: "", only: null, raw: null, three: "all", folded: new Set(), cursor: null,
  records: false, files: null, back: null, last: null, marks: [],
  // "Open in Edit" from a row: where Edit was opened (setting key, tab, set) while it offers "← Back to Compare",
  // and the row (setting key) that Back puts under the cursor once the comparison is drawn
  from: null, goKey: null,
  // the row (setting key) last changed with the compare's picker, kept shown until a filter changes (the window's
  // `cmp_kept`), and the picker open (its box, the cell's column and setting)
  kept: null, pick: null,
  // the column header that holds the header row's one Tab stop: its column (`cmpColId`) and its place, which a header
  // takes when its column is removed (null: the first)
  head: null };
let pollTimer = null;
let askOpen = null;        // how the question shown ends (with false when another takes its place or the login comes up)
let polls = 0;             // the newest state request; an older one answered later is dropped, so it cannot undo a newer state
/** The editor out of reach: since when, how many polls in a row failed, the file open before. */
const away = { since: 0, fails: 0, file: null, slow: false };
// the page's own state for the rest of the window (none of it is the editor's)
const xp = {
  detail: new Set(),                                          // the rows whose details are unfolded, by setting key
  reveal: null,                                               // a setting to bring into view once its tab is drawn
  expert: null,                                               // the Expert switch as the Menu column was drawn for
  rm: { unmapped: false, edited: false, open: new Set() },    // the record map's filters and unfolded records
  windows: { backups: false, history: false, settings: false, connect: false, changelog: false },   // the windows open, by their element's id
  keys: {},                                                   // what each window was last drawn for
  backups: null, history: null, historyRev: null,             // the lists Backups and Edit history show
  changelog: null, changelogFailed: false,                    // the changelog the Changes window shows, and whether asking failed
  historyAsked: 0,                                            // the newest Edit history request; older answers are dropped
  settingsTab: 0,                                             // the Settings tab shown (`SETTINGS_ABOUT` the last)
  folds: new Set(),                                           // the folding parts of the windows left open
  rowFolds: new Set(),                                        // the camera's rows folded in the "As on the camera" layout
  subFocus: null,                                             // the sub-choice opened from elsewhere, marked beside its option, by key
  camera: null, cameraKey: null,                              // the camera cards (`camera_cards`), the state's camera they follow
  sending: false,                                             // Write… is being opened: a second tap waits for it
  sendRound: 0,                                               // the login ends a Write check still running (`checkSend`)
};

let searchTimer = null;    // the search box's wait for the typing to stop

/** The Memories page's own view: the search it was opened with (the window's Memories page lists the
 *  rows its search box matches) and whether the file's other memory sets are columns too (null: as
 *  the editor's "all memory columns" preference has it). */
const memView = { q: "", all: null, only: null };
/** The "What decides …" lists left open on the Exposure page. */
const exOpen = new Set();

// --- talking to the editor: the session, requests, the login, the polls and what a request does ---

/** How the page proves it may ask. An editor with sessions exchanges the access code once (`login`) for a session
 *  (`session`, ending after `idle_hours` without a request), sent as X-Camset-Session from then on; this browser keeps
 *  the session, not the code. An editor without them is asked with the code on every request, as before. */
const session = {
  token: null,
  until: 0,
  idle: 0,
  load() {
    const t = store.get("session"), until = Number(store.get("session_until")) || 0;
    if (t && until > Date.now()) [this.token, this.until, this.idle] = [t, until, Number(store.get("session_idle")) || 12 * 3600e3];
    else this.forget();
  },
  /** The session `login` answered with: true when there is one. */
  take(j) {
    if (!j || typeof j.session !== "string" || !j.session) return false;
    this.token = j.session;
    this.idle = (Number(j.idle_hours) || 12) * 3600e3;
    store.set("session", this.token);
    store.set("session_idle", String(this.idle));
    store.remove("code");
    this.touch();
    return true;
  },
  /** A request went through: the session lasts `idle` from now (kept at most once a minute). */
  touch() {
    if (!this.token || Date.now() + this.idle - this.until < 60000) return;
    this.until = Date.now() + this.idle;
    store.set("session_until", String(this.until));
  },
  forget() {
    this.token = null;
    this.until = 0;
    for (const k of ["session", "session_until", "session_idle"]) store.remove(k);
  },
  headers() {
    return this.token ? { "X-Camset-Session": this.token } : { "X-Camset-Code": code || "" };
  },
};

/** One request to the editor: JSON in and out, or a file up (`file`) or down (a Response). A file sent up carries
 *  `body.discard` as a header, as it has no JSON body. */
async function api(name, body = {}, file = null) {
  const withSession = !!session.token;
  const headers = session.headers();
  let payload;
  if (file) {
    headers["Content-Type"] = "application/octet-stream";
    headers["X-File-Name"] = encodeURIComponent(file.name);
    if (body.discard) headers["X-Camset-Discard"] = "1";   // the person agreed: the file may replace unsaved edits
    payload = file;
  } else {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let r;
  try {
    r = await fetch("/api/" + name, { method: "POST", headers, body: payload, cache: "no-store" });
  } catch {
    throw new Offline(UNREACHABLE);
  }
  const json = (r.headers.get("Content-Type") || "").startsWith("application/json");
  const j = json ? await r.json().catch(() => ({})) : null;
  const said = (j && j.error) || `${r.status} ${r.statusText}`;
  if (r.status === 401) {
    // a session that ended (12 hours unused, signed out, the page turned off or a new code): the code again
    if (withSession || (j && j.session === "ended")) {
      session.forget();
      throw new CodeError((j && j.error) || "Your session ended: enter the access code again.");
    }
    throw new CodeError(wherePut((j && j.error) || "The access code was not accepted."));
  }
  if (r.status === 429) throw new TooMany(wherePut((j && j.error) || "Too many wrong access codes reached the editor: it takes none for a minute."));
  if (r.status === 503) throw new Offline(said, true);
  if (!r.ok) throw new Refused(said, r.status, j);
  session.touch();
  return json ? j : r;
}

let toastTimer = null;
/** A message at the foot of the page for 7 seconds (10 with Undo, which `undo` adds: one tap takes the change back). */
function toast(text, undo = false) {
  const t = $("toast");
  // its Undo, like the shortcut, only while the page is in use (not behind the login, a question or Write…)
  t.replaceChildren(plain(text), undo ? el("button", { class: "small", onclick: () => { t.hidden = true; if (pageInUse()) act("undo"); } }, plain("↺ Undo")) : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, undo ? 10000 : 7000);
}

/** The code or the session was not accepted: nothing is kept for it any more, and the login asks again. */
function lostAccess(e) {
  store.remove("code");
  session.forget();
  code = null;
  showLogin(e.message);
}

/** A failure of a request the person made: the login, the editor-closed notice, or the reason in the toast. */
function failed(e) {
  if (e instanceof CodeError) lostAccess(e);
  else {
    if (e instanceof Offline) goneAway(e, true);
    toast(e.message);
  }
}

/** The login in place of the page: every window, menu and picker over the page closed, the editor-closed notice
 *  taken down (the login says what went wrong), a Write check still running ended, the toast (and its Undo) gone,
 *  and a poll already on its way dropped when it answers, so it cannot replace the login's message with its own. */
function showLogin(msg) {
  clearTimeout(pollTimer);
  polls += 1;
  notAway();
  for (const w of Object.keys(xp.windows)) closeWindow(w);
  hideMyMenu(false);
  closeMore(false);
  cmpHideMenu();
  cmpPickClose();
  if (askOpen) askOpen(false);
  xp.sendRound += 1;
  $("toast").hidden = true;
  $("app").hidden = true;
  // the modal windows emptied too: the Camera link report, still in the state after the code is entered again, is
  // then shown as a modal window again, not just unhidden
  for (const w of ["ask", "send", "report"]) {
    $(w).hidden = true;
    $(w).replaceChildren();
    $(w).dataset.key = "";
    setDialog($(w), false);
  }
  $("login").hidden = false;
  $("login-msg").textContent = msg || "";
  $("code").focus();
}

let retryLogin = null;
async function connect() {
  clearTimeout(retryLogin);
  try {
    // the code for a session, once; an editor without sessions does not know `login` and takes the code each time
    if (code && !session.token) {
      try {
        session.take(await api("login"));
      } catch (e) {
        if (!(e instanceof Refused)) throw e;
      }
    }
    state = await api("state", { target: view.target });
  } catch (e) {
    if (e instanceof CodeError) lostAccess(e);
    else {
      // the code is kept: the editor is out of reach, or takes no code for a while (too many wrong ones, from
      // anywhere); the page tries again by itself
      showLogin(e.message);
      if (code) {
        $("code").value = code;
        retryLogin = setTimeout(connect, e instanceof TooMany ? 30000 : 10000);
      }
    }
    return;
  }
  if (!session.token && code) store.set("code", code);
  $("login").hidden = true;
  $("app").hidden = false;
  render();
  schedule();
}

function schedule() {
  clearTimeout(pollTimer);
  const wait = document.hidden ? 15000 : away.since ? 4000 : away.slow ? 10000 : state && state.job ? 1000 : 2500;
  pollTimer = setTimeout(poll, wait);
}

/** The editor closed, or a few polls in a row could not reach it (`now`: at once): a notice over the page with a
 *  Retry, and the page's controls out of use until it answers again. */
function goneAway(e, now) {
  away.fails += 1;
  if (!(now || e.closed || away.fails >= 2)) return;
  if (!away.since) {
    away.since = Date.now();
    away.file = state && state.file ? { name: state.file.name, edits: state.edits } : null;
  }
  setText($("offline-why"), e.message);
  $("offline").hidden = false;
  for (const id of ["top", "side", "central", "windows"]) $(id).inert = true;
  $("app").classList.add("away");
}

/** The editor-closed notice taken down, and the page's controls back in use. */
function notAway() {
  away.since = 0;
  away.fails = 0;
  $("offline").hidden = true;
  for (const id of ["top", "side", "central", "windows"]) $(id).inert = false;
  $("app").classList.remove("away");
}

/** The editor answers again: the notice goes, and the page says what changed if the editor restarted meanwhile. */
function backAgain(s) {
  away.fails = 0;
  if (!away.since) return;
  const was = away.file, now = s.file;
  notAway();
  if (was && (!now || now.name !== was.name)) {
    toast(now ? `The editor restarted: the open file is now ${now.name}.`
      : `The editor restarted with no file open${was.edits ? `; the ${was.edits} unsaved edit(s) shown before are gone` : ""}.`);
  }
  drawn = null;
}

/** Ask for the state again and draw it; nothing while the login is shown (a request would only be refused, and the
 *  refusal would replace the login's message). */
async function poll() {
  if ($("app").hidden) return;
  const n = ++polls;
  try {
    const s = await api("state", { target: view.target });
    if (n !== polls) return;
    state = s;
    away.slow = false;
    backAgain(s);
    $("status").classList.remove("bad");
    render();
  } catch (e) {
    if (n !== polls) return;
    if (e instanceof CodeError) { lostAccess(e); return; }
    if (e instanceof Offline) goneAway(e, false);
    away.slow = e instanceof TooMany;
    setText($("status"), e.message);
    $("status").title = e.message;
    $("status").classList.add("bad");
  }
  schedule();
}

async function refresh() {
  clearTimeout(pollTimer);
  await poll();
}

/** Ask the editor to do something, then show the outcome; a refusal goes to the toast in the editor's words.
 *  `done` draws the answer at once (before the state is asked for again), `undo` puts back what the page showed
 *  when the editor did not take it (a control the person changed). A control of the page tapped or clicked lets go of
 *  the focus, so the page is drawn again with the answer (it is not drawn under a field that has the focus); one
 *  reached with the keyboard keeps it, and the rows drawn again carry it to the same control (`swapNode`). */
async function act(name, body = {}, file = null, { done = null, undo = null } = {}) {
  const a = document.activeElement;
  if (a && $("content").contains(a) && !keyboardFocus()) a.blur();
  try {
    const j = await api(name, body, file);
    keepCamera(j);
    if (done) done(j);
    await refresh();
    return j;
  } catch (e) {
    if (e instanceof CodeError) { lostAccess(e); return null; }
    failed(e);
    if (undo) undo(e);
    await refresh();
    return null;
  }
}

/** A request that replaces the open file (Read, Open…, a recent file, a kept copy, the sample, Switch to USB and read).
 *  With unsaved edits it asks first, and tells the editor to discard them only once the person agreed (`discard`, a
 *  header for a file sent up). An editor holding edits the page did not know of (made in its window a moment
 *  ago) refuses (409), and the page asks then. `why(n)` is the question for n unsaved edits; edits the camera holds
 *  but the file does not are said to be so first, in the editor's words (`on_camera`). */
async function replaceAct(name, body, file, title, why, yes) {
  const n = state && state.file ? state.file.changes : 0;
  const camera = n && state.file.on_camera ? state.file.on_camera + " " : "";
  if (n && !(await ask(title, camera + why(n), yes))) return null;
  let discard = n > 0;
  for (;;) {
    try {
      const j = await api(name, discard ? { ...body, discard: true } : body, file);
      await refresh();
      return j;
    } catch (e) {
      if (!discard && e instanceof Refused && e.status === 409 && /unsaved edit/i.test(e.message)) {
        if (!(await ask(title, e.message, yes))) return null;
        discard = true;
        continue;
      }
      failed(e);
      await refresh();
      return null;
    }
  }
}

/** The open file's edits in a question: "N unsaved edit(s)", or "N edit(s)" after the editor's line saying they are on
 *  the camera but not saved to a file (`replaceAct`). */
const unsavedNoun = (n) => (state && state.file && state.file.on_camera ? `${n} edit(s)` : `${n} unsaved edit(s)`);

/** Opening a file the editor has on its computer replaces the open one. */
const opening = (what) => (n) => `Opening ${what} replaces the open file and its ${unsavedNoun(n)} in the editor.`;

function openRecent(i) {
  const r = (state.recent || [])[i];
  if (r) replaceAct("open_recent", { index: i }, null, "Open a recent file", opening(r.name), "Open anyway");
}

/** Reading the camera replaces the open file. */
const reading = (n) => `Reading the camera replaces the open file and its ${unsavedNoun(n)} in the editor. Download the file first to keep them.`;

/** Ask the editor for a file and hand it to the browser as a download, by the name the editor gives it (the window's
 *  Save and Export dialogs); `said(file)` is the message after it. */
async function downloadAnswer(name, body, fallback, said = (file) => `Downloaded ${file}`) {
  try {
    const r = await api(name, body);
    if (!(r instanceof Response)) throw new Error("The editor sent no file.");
    const file = (/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "") || [])[1] || fallback;
    const url = URL.createObjectURL(await r.blob());
    const a = el("a", { href: url, download: file });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast(said(file));
    refresh();
  } catch (e) {
    failed(e);
  }
}

/** The open file with its edits, downloaded; the message says when the camera may not take some of them, and, for the
 *  sample or a file made from it, that it must never be loaded into a camera (`sample_words`, the editor's). */
function downloadFile() {
  return downloadAnswer("file", {}, "CAMSET.DAT", (file) => {
    const f = state && state.file ? state.file : {};
    const said = f.issues ? `Downloaded ${file}. ${f.issues} changed value(s) the camera is not known to take: Write lists them.` : `Downloaded ${file}`;
    return f.sample_words ? `${said}${said.endsWith(".") ? "" : "."} ${f.sample_words}` : said;
  });
}

/** Describe for support…: how a file is laid out, without any settings values (file A, B or the base). */
function downloadLayout(src) {
  return downloadAnswer("layout", { src }, "camera_layout.json");
}

/** Sign out: the session ends at the editor when it has sessions, and this browser forgets the code and the token. */
async function signOut() {
  if (session.token) {
    try { await api("logout"); } catch { /* the session ends here in any case */ }
  }
  session.forget();
  store.remove("code");
  code = null;
  $("code").value = "";
  xp.camera = null;
  showLogin("Signed out. Enter the access code to use the page again.");
}

// --- the windows and questions floating over the page ---

const FOCUSABLE = "button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex='-1'])";

/** The windows open, the last on top: each a dialog (named by its title), with the focus moved into it when it opens
 *  and given back where it was when it closes; Escape closes the top one. A modal one (a question, Write, the
 *  Camera link report) dims the page and keeps the rest out of reach. */
const dialogs = [];
function setDialog(box, open, { modal = false, close = null } = {}) {
  const i = dialogs.findIndex((d) => d.box === box);
  if (open) {
    const t = box.querySelector(".title > span") || box.querySelector(".title");
    if (t) {
      t.id = box.id + "-title";
      box.setAttribute("aria-labelledby", t.id);
    }
    box.setAttribute("role", modal ? "alertdialog" : "dialog");
    box.setAttribute("aria-modal", String(modal));
    if (i >= 0) {
      dialogs[i].close = close;
      return;
    }
    dialogs.push({ box, modal, close, back: document.activeElement });
    if (!box.hasAttribute("tabindex")) box.setAttribute("tabindex", "-1");
    const first = box.querySelector(".wbody " + FOCUSABLE.split(", ").join(", .wbody ")) || box;
    first.focus({ preventScroll: true });
  } else if (i >= 0) {
    const [d] = dialogs.splice(i, 1);
    if (d.back && d.back !== document.body && document.contains(d.back) && !d.back.closest("[inert], [hidden]")) d.back.focus({ preventScroll: true });
  }
  const top = [...dialogs].reverse().find((d) => d.modal);
  $("backdrop").hidden = !top;
  $("app").inert = !!top;
  for (const d of dialogs) d.box.inert = !!top && d !== top;
}

/** What names the control that has the focus inside `scope`, to find it again once `scope` is drawn anew:
 *  - the setting it belongs to (the nearest `data-key`), and which of that setting's places in `scope` it is in (Main
 *    shows a setting as a tile and as a row; a flat list shows a sub-choice as a row and beside its owner's option);
 *  - its part of the setting (`data-ctl`: its value control, its name, a compare cell's column), else its kind and its
 *    words (its label, else its text);
 *  - and which of those it is, when several match.
 *  Never its place among all the controls: a row's controls come, go and grey out with its value ("+" at the top of
 *  the range, Revert once it is edited), so a place would name another control, and the next key press would act on
 *  it. Null when the focus is not in `scope`. */
function focusMark(scope) {
  const a = document.activeElement;
  if (!a || a === scope || !scope.contains(a)) return null;
  const holder = a.closest("[data-key]");
  const key = holder && (holder === scope || scope.contains(holder)) ? holder.dataset.key : null;
  const mark = { key, place: key ? holdersOf(scope, key).indexOf(holder) : 0, part: a.dataset.ctl || null, tag: a.tagName, words: controlWords(a), nth: 0 };
  mark.nth = controlsOf(scope, mark).indexOf(a);
  return mark;
}

/** A control's words, which tell it apart from the others of its setting: its label, else its text. */
function controlWords(c) {
  return c.getAttribute("aria-label") || c.textContent.trim();
}

/** The elements in `scope` (itself included) that show the setting `key`, in the page's order. */
function holdersOf(scope, key) {
  const sel = `[data-key="${CSS.escape(key)}"]`;
  return [...(scope.matches(sel) ? [scope] : []), ...scope.querySelectorAll(sel)];
}

/** The controls in `scope` that can take the focus and belong to the setting `mark` names, in the same place of the
 *  page (not to a row of sub-choices in its details): those of `part` (a `data-ctl`), else of `mark`'s kind and words.
 *  A place no longer there falls back to the setting's first. */
function controlsOf(scope, mark, part = mark.part) {
  const holders = mark.key ? holdersOf(scope, mark.key) : [scope];
  const holder = holders[mark.place] || holders[0];
  if (!holder) return [];
  return [...holder.querySelectorAll(FOCUSABLE)].filter((c) => (!mark.key || c.closest("[data-key]") === holder)
    && (part ? c.dataset.ctl === part : c.tagName === mark.tag && controlWords(c) === mark.words));
}

/** Put the focus back on the control `mark` names, in `scope` drawn anew. In a setting whose control is gone or greyed
 *  out (the "+" of a value now at its top), the setting's value control takes it, else its name: never another
 *  button, which a key press would then press. In a window, a control gone or greyed out (a button off while the
 *  camera is busy) leaves the focus on the window itself, so Tab goes on inside it. Else, nothing found, the focus
 *  stays where the browser left it. */
function focusAgain(scope, mark) {
  if (!mark) return;
  const c = controlsOf(scope, mark)[mark.nth] || (mark.key ? controlsOf(scope, mark, "value")[0] || controlsOf(scope, mark, "name")[0] : null);
  if (c) c.focus({ preventScroll: true });
  else if (!mark.key && scope.hasAttribute("tabindex")) scope.focus({ preventScroll: true });
}

/** Draw a window's contents again, the focus kept on the same control where it can be (`focusMark`). */
function refill(box, ...kids) {
  const mark = focusMark(box);
  box.replaceChildren(...kids);
  focusAgain(box, mark);
}

/** Fill one of the modal windows (egui's Window): a title bar, then its contents; `close` is what Escape does. */
function showWindow(box, title, close, ...kids) {
  refill(box, el("div", { class: "title" }, title), el("div", { class: "wbody" }, ...kids));
  box.hidden = false;
  setDialog(box, true, { modal: true, close });
}

/** A question in the page (not a browser dialog): resolves true for `yes`. */
function ask(title, text, yes) {
  if (askOpen) askOpen(false);
  return new Promise((resolve) => {
    const box = $("ask");
    const done = (v) => { askOpen = null; box.hidden = true; box.replaceChildren(); setDialog(box, false); resolve(v); };
    askOpen = done;
    showWindow(box, title, () => done(false), el("p", {}, text), el("div", { class: "buttons" },
      el("button", { onclick: () => done(true) }, yes),
      el("button", { onclick: () => done(false) }, "Cancel")));
  });
}

// --- the page's own look: text size, theme and row spacing, kept in this browser ---

// The text size (90 % to 140 %, in steps of 5 %), the page's own; 1 is egui's 14 px body text, so it
// scales the page as the editor's zoom scales the window.
const BASE_PX = 14;
function getFontScale() {
  const v = parseFloat(store.get("font_scale"));
  return Number.isFinite(v) && v >= 0.85 && v <= 1.45 ? v : 1.0;
}

function setFontScale(scale) {
  const v = Math.round(Math.min(1.4, Math.max(0.9, scale)) * 20) / 20;
  store.set("font_scale", v.toFixed(2));
  document.documentElement.style.fontSize = `${BASE_PX * v}px`;
  $("font-scale-pct").textContent = `${Math.round(v * 100)}%`;
  greyOut($("b-font-dec"), v <= 0.9 ? "The text is at its smallest size (90 %)." : "");
  greyOut($("b-font-inc"), v >= 1.4 ? "The text is at its largest size (140 %)." : "");
}

/** The page's own theme, chosen in its Settings: "system" follows the browser, "light" and "dark" override it. */
function pageTheme() {
  const t = store.get("theme");
  return t === "light" || t === "dark" ? t : "system";
}
function setPageTheme(t) {
  store.set("theme", t);
  document.documentElement.classList.toggle("theme-light", t === "light");
  document.documentElement.classList.toggle("theme-dark", t === "dark");
}

/** The page's own row spacing, as the window's: 0 compact, 1 comfortable, 2 spacious. */
function pageDensity() {
  const d = store.get("density");
  return d === "0" ? 0 : d === "2" ? 2 : 1;
}
function setPageDensity(d) {
  store.set("density", String(d));
  for (const i of [0, 1, 2]) document.body.classList.toggle("density-" + i, i === d);
}

// --- the frame: the toolbar, the Editing row, the Menu column and the status bar ---

/** The set, page and tab the page shows, kept to what the state has: the live settings for a set the file does not
 *  show; a tab with no entry of its own where the Menu shows its settings (My Menu's page, or Other); a page the file
 *  or its definition does not have (another camera's file opened meanwhile) given up for Main, so it is not asked
 *  for, and refused, at every poll. */
function keepViewValid(s) {
  if (!s.targets.some(([i]) => i === view.target)) view.target = 0;
  if (view.page === "tab" && view.tab && !s.tabs.includes(view.tab)) Object.assign(view, menuPlace(view.tab));
  if ((view.page === "mymenu" && !s.my_menu) || (view.page === "memories" && !s.memories) || (view.page === "exposure" && !s.exposure)) view.page = "main";
  if (!view.tab || !s.tabs.includes(view.tab)) view.tab = s.tabs[0] || null;
  if (view.page === "tab" && !view.tab) view.page = "main";
}

/** The frame drawn from the state (after each poll and each request): the toolbar, the Editing row, a camera job,
 *  the Camera link report, the Menu column, the status bar and the open windows; then the content, if it changed. */
function render() {
  const s = state;
  const f = s.file;
  const busy = !!s.job;
  cmpRender(s, f);
  $("app").classList.toggle("nofile", !f);
  keepViewValid(s);

  // the toolbar
  const up = s.link.up === true ? "up" : s.link.up === false ? "down" : "";
  const link = `${s.link.text} · ${s.link.state}`;
  if ($("link").dataset.key !== up + link) {
    $("link").dataset.key = up + link;
    $("link").replaceChildren(el("span", { class: "dot " + up }), link);
    $("link").title = `Camera: ${link}`;
  }
  // a greyed-out button of the toolbar stays in the Tab order and says why when pressed (`greyOut`), as Write does
  greyOut($("b-read"), busy ? "The camera link is busy: wait for the camera action under way to finish, then read." : "");
  // how long a read usually takes, as this computer has timed it (the window's hover)
  $("b-read").title = s.read_tip || "Read the camera's current settings over USB or the network";
  // Write greyed out says why when tapped (a touch screen shows no hover text)
  const why = !f ? "Read the camera or open a file first: there is nothing to write yet."
    : f.source === "sample" ? "The sample is not your camera's file, so it cannot be written to a camera."
      : !f.editable ? "This file's firmware has not been checked yet, so it is view only and is not written to a camera."
        : busy ? "The camera link is busy." : "";
  greyOut($("b-send"), why);
  $("b-send").title = why || "Write this file to the camera after an acceptance check. The camera's settings are read and kept first; the camera restarts";
  setText($("b-send"), plain(s.edits ? `⬆ Write (${s.edits})…` : "⬆ Write…"));
  $("busy").hidden = !busy;
  greyOut($("b-undo"), s.can_undo ? "" : "There is no edit to undo.");
  greyOut($("b-redo"), s.can_redo ? "" : "There is nothing to redo: Redo puts back an edit that Undo took away.");
  greyOut($("b-download"), f ? "" : "Read the camera or open a file first: there is nothing to download yet.");

  // the Editing row: the sets, the search, the file and its firmware
  $("bar2").hidden = !f;
  drawTargets();
  drawFile(f);
  const memory = f && view.target !== 0 ? (s.targets.find(([i]) => i === view.target) || [])[1] : null;
  $("memnote").hidden = !memory;
  if (memory) setText($("memnote"), `${memory} is a memory set: changes here apply when that memory is recalled, not to the live settings.`);

  const job = s.job;
  $("job").hidden = !job;
  if (job) {
    $("job").replaceChildren(
      el("div", { class: "jt" }, el("span", { class: "spinner" }), job.title),
      typeof job.progress === "number"
        ? el("div", { class: "pbar" }, el("i", { style: { width: `${Math.round(Math.min(1, Math.max(0, job.progress)) * 100)}%` } }), el("span", {}, job.line))
        : el("div", { class: "weak" }, job.line));
  }
  drawReport(s.report, busy);
  drawSide();

  // the status bar, in the editor's words: "N unsaved edit(s)", or "N edit(s) on the camera, not saved to …"
  setText($("edits"), s.edits ? s.edits_text : "No edits");
  $("edits").className = s.edits ? "edit" : "";
  setText($("status"), s.status || "");
  $("status").title = s.status || "";
  drawVersion(s);
  drawMore(s, f);
  maybeDraw();
}

/** One button per set (the live settings and the dial memories), the others in a list (expert mode). */
function drawTargets() {
  const key = JSON.stringify(state.targets) + "|" + view.target;
  if ($("targets").dataset.key === key) return;
  $("targets").dataset.key = key;
  const pick = (i) => {
    if (i === view.target) return;
    view.target = i;
    drawTargets();
    refresh();
  };
  const own = state.targets.filter((t) => t[2] !== false);
  const others = state.targets.filter((t) => t[2] === false);
  const kids = own.map(([i, n]) => el("button", { class: "sel" + (i === view.target ? " on" : ""), onclick: () => pick(i) }, n));
  if (others.length) {
    const cur = others.find(([i]) => i === view.target);
    const sel = el("select", { "aria-label": "Other sets", onchange: () => pick(Number(sel.value)) },
      el("option", { value: "", disabled: true }, "Other sets"),
      ...others.map(([i, n]) => el("option", { value: String(i) }, n)));
    sel.value = cur ? String(cur[0]) : "";
    kids.push(el("span", { class: "combo narrow" }, sel));
  }
  // a phone: every set in one list
  const all = el("select", { "aria-label": "The set you edit", onchange: () => pick(Number(all.value)) },
    ...state.targets.map(([i, n]) => el("option", { value: String(i) }, n)));
  all.value = String(view.target);
  kids.push(el("span", { class: "combo narrow tsel" }, all));
  $("targets").replaceChildren(...kids);
}

/** The file's name and the firmware badge, at the right of the Editing row. */
function drawFile(f) {
  const key = f ? JSON.stringify([f.name, f.source, f.link, f.read_at, f.model, f.saved, f.firmware, f.badge, f.definition, f.edit_anyway_in_desktop]) : "";
  if ($("file").dataset.key === key) return;
  $("file").dataset.key = key;
  $("file").classList.toggle("warn", !!(f && f.badge && f.badge.kind !== "ok"));
  // the definition the file is read with, named beside it (model, firmware, built-in or yours)
  const def = f && f.definition;
  $("foot-file").textContent = f ? f.name : "";
  $("foot-file").title = f ? (def ? `${f.name}\n${def.tip}` : f.name) : "";
  if (!f) { $("file").replaceChildren(); return; }
  const where = f.source === "camera" ? `Read over ${f.link} at ${f.read_at}`
    : f.source === "sample" ? "Built-in sample file" : "Opened from a file";
  const badge = f.badge || { kind: "ok", text: f.firmware ? `✔ firmware ${f.firmware}` : "", tip: "" };
  $("file").replaceChildren(...[
    el("strong", { title: `${where}\n${f.model}${f.saved ? " · saved " + f.saved : ""}${def ? "\n" + def.tip : ""}` }, f.name),
    def ? el("span", { class: "small weak", title: def.tip }, def.text) : null,
    firmwareBadge(badge),
    // Describe for support… for a firmware not checked; Edit anyway, which the desktop app turns on, for one of this model
    f.badge && f.badge.kind !== "ok" ? describeButton("a") : null,
    f.edit_anyway_in_desktop ? editAnywayInDesktop() : null].filter(Boolean));
}

/** A file's firmware badge, its details on a tap too (a touch screen shows no hover text); `who` names the file to a
 *  screen reader where several files show one (the Compare bar: "file B"). */
function firmwareBadge(b, who = null) {
  const shown = el("span", { class: b.kind + " tip", title: b.tip, "aria-label": who ? `${plain(b.text)} (${who})` : null }, plain(b.text));
  return b.tip ? pressable(shown, () => toast(b.tip)) : shown;
}

/** Describe for support… beside a file whose firmware is not checked (file A, B or the base); `who` as the badge's. */
function describeButton(src, who = null) {
  return el("button", { class: "small", onclick: () => downloadLayout(src), "aria-label": who ? `Describe for support… (${who})` : null,
    title: "Save a description of how this file is laid out, without any settings values, so support for this firmware can be added" }, "Describe for support…");
}

/** Edit anyway… for a file of another firmware, which only the desktop app turns on. */
function editAnywayInDesktop() {
  const why = "Editing a file of a firmware not checked yet is turned on in the desktop app (Edit anyway… beside the file's name); the page then edits it too.";
  return pressable(el("span", { class: "small weak tip", title: why }, "Edit anyway: in the desktop app"), () => toast(why));
}

/** The Camera link window: what happened, the link's own words (Expert mode only, asked for when unfolded; else a
 *  note saying where they are), how often it retried, and the ways on the window offers: Change connection, Switch to
 *  USB and read, Try again, Put the camera back. What only the desktop app does (enter the camera's login) the
 *  editor says in a line of its own (`in_desktop`), with no button. */
function drawReport(rep, busy) {
  const box = $("report");
  box.hidden = !rep;
  if (!rep) { box.dataset.key = ""; setDialog(box, false); return; }
  const key = JSON.stringify(rep) + busy;
  if (box.dataset.key === key) return;  // redrawn only when it changes, so open details stay open
  box.dataset.key = key;
  const changeConnection = async () => { await act("dismiss"); openWindow("connect"); };
  showWindow(box, "Camera link", () => act("dismiss"),
    el("div", { class: "big " + (rep.ok ? "ok" : "bad") }, plain(rep.title)),
    el("div", {}, ...rep.lines.map(([t, warn]) => el("p", { class: warn ? "edit" : "" }, plain(t)))),
    rep.retries ? el("p", { class: "small weak" }, `The link retried ${rep.retries} time(s) before connecting; that is normal when the computer's own camera service grabs the camera first.`) : null,
    rep.has_probe ? probeDetails() : null,
    rep.note ? el("p", { class: "small weak" }, plain(rep.note)) : null,
    el("div", { class: "buttons" },
      el("button", { onclick: () => act("dismiss") }, "Close"),
      rep.retry ? el("button", { disabled: busy, onclick: () => act("retry") }, "Try again") : null,
      !rep.ok && !rep.in_desktop ? el("button", { onclick: changeConnection, title: "Open Connect to the camera: choose USB or network and find the camera" }, "Change connection") : null,
      rep.offer_usb ? el("button", { disabled: busy, onclick: () => replaceAct("switch_usb", {}, null, "Switch to USB and read", reading, "Read anyway"),
        title: "Set the link to USB (camera in PC Remote) and read the camera" }, "Switch to USB and read") : null,
      rep.put_back ? el("button", { disabled: busy, title: `Write the camera's settings read at ${rep.put_back}, just before the last write; the camera restarts`,
        onclick: () => act("put_back") }, plain(`↩ Put the camera back as it was at ${rep.put_back}`)) : null));
}

/** The camera link's own words, asked for when unfolded (Expert mode: they name the camera's address and serial). */
function probeDetails() {
  const pre = el("pre", {}, "…");
  const d = el("details", { class: "grp" }, el("summary", {}, "Details from the camera link"), pre);
  d.addEventListener("toggle", async () => {
    if (!d.open || d.dataset.got) return;
    d.dataset.got = "1";
    try { pre.textContent = (await api("camera_report")).probe || "(nothing)"; } catch (e) { pre.textContent = e.message; }
  });
  return d;
}

/** The Menu column: Main, the tabs with their colours and counts, then the other pages. */
function drawSide() {
  const s = state;
  const key = JSON.stringify([s.tab_info, s.my_menu, s.edits, s.memories, s.exposure, s.known, s.definition, s.help_src, s.help_refused,
    view.page, view.tab, view.q, view.only, hits]);
  if ($("side").dataset.key === key) return;
  $("side").dataset.key = key;
  const go = (page, tab) => () => {
    view.page = page;
    if (tab) view.tab = tab;
    clearSearch();
    drawSide();
    maybeDraw();
  };
  const searching = !!view.q;
  const expert = !!(s.prefs && s.prefs.expert);
  // the page shown, unless a search's results are shown over it
  const showing = (page) => !searching && view.page === page;
  // one entry, as the window's selectable label: a mark in its colour (the tabs), how many of its settings are edited
  const item = ({ label, on, onclick, color, edited, title, badgeTitle }) => el("div", { class: "mi" },
    color ? el("span", { class: "mark", style: { background: color } }) : null,
    el("button", { class: "sel" + (on ? " on" : ""), "aria-current": on ? "page" : null, title, onclick }, label,
      edited ? el("span", { class: "badge", title: badgeTitle || "settings edited in this tab" }, String(edited)) : null));
  const side = $("side"), was = side.dataset.at, left = side.scrollLeft;
  side.dataset.at = JSON.stringify([view.page, view.tab, searching]);
  const mm = s.my_menu;
  side.replaceChildren(...[
    el("h1", { class: "menu-title" }, "Menu"),
    item({ label: "Main", color: "var(--main-mark)", on: showing("main"), onclick: go("main") }),
    // My Menu, a tab of its own on the camera, under Main as in the window
    mm ? item({ label: mm.label, color: mm.color, on: showing("mymenu"), onclick: go("mymenu"), edited: mm.edited, title: mm.title,
      badgeTitle: `places and settings edited in ${mm.name}` }) : null,
    ...(s.tab_info || []).map((t) => item({ label: `${t.name}  (${view.only ? t.edited : t.count})`, color: t.color,
      on: showing("tab") && view.tab === t.name, onclick: go("tab", t.name), edited: t.edited, title: t.title || undefined })),
    el("hr"),
    searching ? item({ label: `Search results${hits === null ? "" : ` (${hits})`}`, on: true }) : null,
    s.memories ? item({ label: s.memories, on: showing("memories"), onclick: memOpen,
      title: "The memories on the mode dial beside the live settings: recall one into the live settings, or register the live settings into one" }) : null,
    s.exposure ? item({ label: s.exposure, on: showing("exposure"), onclick: go("exposure"),
      title: "Aperture, shutter speed and ISO for the live settings and each memory: who sets each in that exposure mode, and the limits on what the camera may choose" }) : null,
    item({ label: `All edits (${s.edits || 0})`, on: showing("edits"), onclick: go("edits") }),
    // the Expert pages stay shown under a search, which filters them
    expert ? item({ label: "Unmapped records", on: view.page === "unmapped", onclick: go("unmapped") }) : null,
    expert ? item({ label: "Record map", on: view.page === "records", onclick: go("records"),
      title: "Every record of the set in file order, mapped or not, so an unmapped record can be read next to its neighbours" }) : null,
    el("hr"),
    el("div", { class: "foot" }, ...(!expert ? [] : [
      el("div", { class: "small", title: "The settings the editor can name for this camera. Where they come from: ⚙ Settings > Camera support & web page" }, `${s.known} known settings`),
      // the definition and the help file in Expert mode only, as the window's side bar has them
      el("div", { class: "small weak", title: s.definition }, `definition: ${fileName(s.definition)}`),
      s.help_src ? el("div", { class: "small weak", title: s.help_src }, `help: ${fileName(s.help_src)}`) : null,
      // a help file of the definition's name that is another camera's: not used, said by its name, why in the hover
      ...(s.help_refused || []).map((r) => el("div", { class: "small warn", title: r.text }, `help: ${r.file} not used`))])),
  ].filter(Boolean));
  // the Menu as a strip (a phone): where it was, or the page now shown brought into view
  const on = side.querySelector("button.on");
  if (was === side.dataset.at || !on) side.scrollLeft = left;
  else if (side.scrollWidth > side.clientWidth) side.scrollLeft = Math.max(0, on.offsetLeft - side.offsetLeft - side.clientWidth / 3);
  stripEdges();
}

/** The Menu strip fades at an edge with more of it off that side. */
function stripEdges() {
  const side = $("side");
  const can = side.scrollWidth > side.clientWidth + 1;
  side.classList.toggle("more-left", can && side.scrollLeft > 2);
  side.classList.toggle("more-right", can && side.scrollLeft + side.clientWidth < side.scrollWidth - 2);
}

/** What the rest of the page leaves to this part, at the end of each render: the bar's Recent, Export CSV,
 *  History and camera buttons, what the Expert switch changes, and the open windows. */
function drawMore(s, f) {
  const recent = s.recent || [];
  const sel = $("b-recent");
  const rk = JSON.stringify(recent);
  if (sel.dataset.key !== rk) {
    sel.dataset.key = rk;
    sel.replaceChildren(el("option", { value: "" }, "Recent"), ...recent.map((r, i) => el("option", { value: String(i), title: r.path }, r.name)));
    sel.value = "";
  }
  $("b-recent-box").hidden = !recent.length;
  $("b-csv").hidden = !f;
  const hist = $("b-history");
  hist.hidden = !f;
  greyOut(hist, s.history || s.can_redo || s.edits ? "" : "No edits in this session yet: Edit history lists each one once it is made.");
  setText(hist, s.edits ? `🕓 History (${s.edits})` : "🕓 History");
  const cam = s.camera && s.camera.button;
  // the camera button carries the link and its state; the link's own text only stands in without it
  $("link").hidden = !!cam;
  if (cam) {
    const b = $("b-camera");
    setText(b, cam.text);
    b.title = cam.tip;
    b.classList.toggle("ok", cam.up === true);
    b.classList.toggle("bad", cam.up === false);
  }
  // Expert off leaves the Expert pages, as the window does; the Menu column gains or loses them
  const expert = !!(s.prefs && s.prefs.expert);
  if (xp.expert !== expert) {
    xp.expert = expert;
    if (!expert && (view.page === "unmapped" || view.page === "records")) {
      view.page = "main";
      clearSearch();
    }
    $("side").dataset.key = "";
    drawSide();
  }
  drawWindows();
}

function clearSearch() {
  clearTimeout(searchTimer);
  view.q = "";
  hits = null;
  $("search").value = "";
  $("b-clear").hidden = true;
}

// --- the page's content: which page is shown, fetched and drawn, and changes patched in place ---

/** What the page's content is drawn for: it is fetched and drawn again when this changes. */
function contentKey() {
  const what = view.q ? "?" + view.q : view.page === "main" ? "main:" + view.set : view.page === "tab" ? "tab:" + view.tab : "*" + view.page;
  return [state.rev, view.target, what, view.only, extraKey()].join("|");
}

/** More that a page's content depends on beyond `view`: Compare is fetched again when its columns or filters change
 *  (its folds and cursor are drawn from the last answer). */
function extraKey() {
  return view.mode === "compare" ? JSON.stringify([cmp.cols, cmp.q, cmp.tab, cmpOnly(), cmpRaw(), cmp.three]) : "";
}

/** How many Undo and Redo pressed on the keyboard the editor has not answered yet (`shortcut`). The key came to the
 *  page, so no list was open under the person's hand (an open list takes the keys): the page is drawn again with the
 *  value put back even while a list of the settings has the focus, and the focus stays on that list (`drawContent`).
 *  A count, not a yes or no: with the key held down several presses are on their way at once, and the first one
 *  answered must not keep the last one from being drawn. */
let undoKeys = 0;

/** Typing in a field of the settings, or a list of values open: they are not drawn again under the person's hand. A
 *  list focused while an Undo or Redo from the keyboard is on its way is not open, and is drawn again (`undoKeys`). */
function typing() {
  const a = document.activeElement;
  return !!a && $("content").contains(a) && ((a.tagName === "SELECT" && !undoKeys) || (a.tagName === "INPUT" && a.type !== "checkbox" && a.type !== "radio"));
}

function maybeDraw() {
  if (!state.file) {
    if (drawn !== "welcome") $("content").replaceChildren(welcome());
    drawn = "welcome";
    return;
  }
  const key = contentKey();
  if (key !== drawn && !typing()) drawContent(key);
}

/** The pages by name (`pageName`): how each is fetched from the editor and drawn from its answer, and for the pages
 *  of settings how a newer answer is patched in (false when its rows are not the same ones: the page is drawn anew). */
const pages = {
  main: { load: () => api("main", { target: view.target, set: view.set }), draw: drawMain, patch: patchMain },
  tab: { load: () => api("tab", { target: view.target, tab: view.tab }), draw: (j) => drawTab(j.groups, j), patch: (a, b) => patchGroups(a.groups, b.groups) },
  search: { load: () => api("tab", { target: view.target, q: view.q }), draw: (j) => drawSearch(j.groups), patch: (a, b) => patchGroups(a.groups, b.groups) },
  edits: { load: () => api("changes"), draw: (j) => drawChanges(j.changes) },
  memories: { load: () => api("memories", { q: memView.q, ...(memView.all === null ? {} : { all: memView.all }), ...(memView.only === null ? {} : { only_diff: memView.only }) }),
    draw: drawMemories },
  exposure: { load: () => api("exposure"), draw: drawExposure },
  mymenu: { load: () => api("mymenu_page", { target: view.target }), draw: drawMyMenu },
  unmapped: { load: () => api("unmapped", { target: view.target, q: view.q, only: view.only }), draw: drawUnmapped },
  records: { load: () => api("records", { target: view.target, q: view.q, only_unmapped: xp.rm.unmapped, only_edited: xp.rm.edited, open: [...xp.rm.open] }),
    draw: drawRecords },
  compare: { load: () => api("compare", cmpBody()), draw: drawCompareAnswer },
  compare_records: { load: () => api("compare_records", cmpBody()), draw: (j) => { cmp.last = j; return drawCompareRecords(); } },
};

/** The page shown: a search's results over any page but the Expert ones, which a search filters, as in the window. */
function pageName() {
  if (view.q && view.page !== "unmapped" && view.page !== "records") return "search";
  return pages[view.page] ? view.page : "tab";
}

let shownPage = null;   // the page drawn and the answer it was drawn from: { name, data }

/** The page's content for `key`, fetched from the editor. The same page again (after an edit, here, in another
 *  browser or in the window) has the rows that changed drawn in place when its rows are the same ones, else is drawn
 *  anew where it was scrolled to, sideways too; another page starts at its top. `whole` draws it anew in any case.
 *  A page the editor refuses says why in its place, once (not again at every poll); one that could not be asked
 *  for at all is asked for again when the editor answers. The same page drawn anew keeps the focus on the same
 *  control (`focusMark`), and so does Compare drawn for other columns or filters. */
async function drawContent(key, whole = false) {
  const n = ++loading;
  const name = pageName(), page = pages[name];
  try {
    const data = await page.load();
    if (n !== loading) return;
    const of = (k) => (k || "").split("|").slice(1).join("|");
    const same = !!shownPage && shownPage.name === name && of(drawn) === of(key);
    // Compare keeps the focus also when it is drawn for other columns or filters: a column moved or removed from its
    // header's menu, a column picked, the three-way list; the keyboard stays on the control that changed them
    const held = same || (!!shownPage && shownPage.name === name && name === "compare");
    if (!(same && !whole && page.patch && page.patch(shownPage.data, data))) {
      const keep = same ? keepScroll() : null;
      const mark = held ? focusMark($("content")) : null;
      $("content").replaceChildren(...page.draw(data));
      if (keep) keep();
      else {
        $("central").scrollTop = 0;
        const top = $("central").getBoundingClientRect().top + window.scrollY;
        if (window.scrollY > top) window.scrollTo(window.scrollX, top);
      }
      focusAgain($("content"), mark);
      if (name === "compare") cmpHeadGone(mark);
      // drawn from its top, the control that kept the focus is brought into view
      const a = document.activeElement;
      if (mark && !keep && a && $("content").contains(a)) a.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    shownPage = { name, data };
    drawn = key;
    // "← Back to Compare" is gone for good once the person goes elsewhere on their own
    if (cmp.from && !cmpFromHere()) cmp.from = null;
    drawSide();
  } catch (e) {
    if (n !== loading) return;
    if (e instanceof Refused) {
      $("content").replaceChildren(el("p", { class: "bad" }, e.message));
      shownPage = null;
      drawn = key;
    } else if (e instanceof CodeError) lostAccess(e);
    // out of reach: counted as a failed poll is (the notice comes after two in a row, not at one Wi-Fi blip)
    else if (e instanceof Offline) goneAway(e, false);
    else toast(e.message);
  }
}

/** The page drawn anew now, where it was scrolled to, for a change of its own view rather than of the file. */
function redraw() {
  drawContent(contentKey(), true);
}

/** Draw `fresh` in place of `node`; a focus in `node` moves to the same control in `fresh` (`focusMark`), so a
 *  keyboard user's place survives the redraw. */
function swapNode(node, fresh) {
  const mark = focusMark(node);
  node.replaceWith(fresh);
  focusAgain(fresh, mark);
}

/** Main again with the same tiles and rows: the ones that changed drawn in place. Its rows are the grid's own (a row's
 *  details hold grids of sub-choices too, which are not Main's rows). */
function patchMain(a, b) {
  const plan = (j) => JSON.stringify([j.set, j.sets, j.tiles.map((t) => [t.caption, t.edit ? t.edit.key : null]), j.rows.map((r) => [r.key, r.caption])]);
  if (plan(a) !== plan(b)) return false;
  const grid = [...$("content").children].find((c) => c.classList.contains("grid"));
  const tiles = $("content").querySelectorAll(".tiles > .tile"), rows = grid ? [...grid.children] : [];
  if (tiles.length !== b.tiles.length || rows.length !== b.rows.length) return false;
  const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  b.tiles.forEach((t, i) => { if (!same(t, a.tiles[i])) swapNode(tiles[i], drawTile(t)); });
  b.rows.forEach((r, i) => { if (!same(r, a.rows[i])) swapNode(rows[i], drawRow(r)); });
  return true;
}

/** A tab or a search again with the same groups and rows (as Only edited shows them): each group's head and the rows
 *  and cells that changed drawn in place; a group still folded draws its rows as they are now when it opens. */
function patchGroups(a, b) {
  const [da, db] = [onlyEdited(a), onlyEdited(b)];
  const plan = (gs) => JSON.stringify(gs.map((g) => [g.name, g.family ? [g.profiles, g.params, g.cells] : 0, g.rows.map((r) => r.key), g.layout || 0]));
  if (plan(da) !== plan(db)) return false;
  const boxes = $("content").querySelectorAll("details.grp[data-group]");
  if (boxes.length !== db.length) return false;
  const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  db.forEach((g, i) => {
    const d = boxes[i], was = da[i];
    d._group = g;
    if (same(was, g)) return;
    d.querySelector(":scope > summary").replaceChildren(...groupHead(g));
    const before = new Map(was.rows.map((r) => [r.key, r]));
    for (const r of g.rows) {
      if (same(before.get(r.key), r)) continue;
      for (const node of d.querySelectorAll(`[data-key="${CSS.escape(r.key)}"]`)) {
        if (node.tagName === "TD") swapNode(node, familyCell(r));
        else redrawRow(node, r);
      }
    }
  });
  return true;
}

/** Where the page is scrolled (down, and sideways in each wide table), to put back after it is drawn again. */
function keepScroll() {
  const boxes = () => document.querySelectorAll("#content .scrollx, #content .cmp-scroll");
  const left = [...boxes()].map((b) => b.scrollLeft), top = $("central").scrollTop, y = window.scrollY;
  return () => {
    boxes().forEach((b, i) => { if (left[i]) b.scrollLeft = left[i]; });
    $("central").scrollTop = top;
    if (window.scrollY !== y) window.scrollTo(window.scrollX, y);
  };
}

/** The set a row shows and changes: the one it was drawn for (the My Menu page's rows are the live settings'), else
 *  the set the page edits. */
const rowTarget = (r) => r.target ?? view.target;

/** The rows an answer carries: `rows`, or the one `row`. */
const replyRows = (j) => (!j ? [] : Array.isArray(j.rows) ? j.rows.filter(Boolean) : j.row ? [j.row] : []);

/** Change a setting from its row, its Main tile or its Picture Profile cell. The rows the editor answers with are
 *  drawn in place at once, and the rest of the page follows when it is fetched again; a change the editor did not
 *  take puts the setting's real value back: the one the refusal carries, else the one shown before. */
function setSetting(r, body) {
  // from the compare's picker: the cell's column goes with it, and the compare, not a page of rows, shows the answer
  if (r.col) return cmpPickSet(r, body);
  return act("set", { target: rowTarget(r), key: r.key, ...body }, null, {
    done: (j) => {
      const rows = replyRows(j);
      patchRows(rows, r.key);
      noteRows(rows, r.key);
      // the editor names every row the change touched (`rows`, those it greys out or brings back included) and the
      // new `rev`, so a tab or a search is left as it is now drawn: it is not fetched again for this change (each
      // group's head is drawn again for its count of edits)
      if (typeof j.rev === "string" && Array.isArray(j.rows) && drawn && shownPage && (shownPage.name === "tab" || shownPage.name === "search") && !view.only) {
        drawn = [j.rev, ...drawn.split("|").slice(1)].join("|");
        for (const d of $("content").querySelectorAll("details.grp[data-group]")) if (d._group) d.querySelector(":scope > summary").replaceChildren(...groupHead(d._group));
      }
    },
    undo: (e) => {
      const b = (e && e.body) || {};
      const rows = replyRows(b);
      if (rows.length) patchRows(rows, r.key);
      else if ("value" in b) patchRows([{ ...r, value: b.value }], r.key);
      else patchRows([r], r.key);
    },
  });
}

/** Draw these rows again wherever the page shows them: a setting's row, its Picture Profile or Creative Look cell,
 *  its Main tile. The first is also drawn for `asKey`, the setting changed, which the editor may answer for under
 *  the key of another of its records. */
function patchRows(rows, asKey) {
  rows.forEach((r, i) => {
    const keys = new Set([r.key]);
    if (i === 0 && asKey) keys.add(asKey);
    for (const k of keys) {
      for (const node of document.querySelectorAll(`#content [data-key="${CSS.escape(k)}"]`)) {
        const was = node._row || {}, row = { ...r, key: k };
        if (node.classList.contains("tile")) swapNode(node, drawTile({ ...node._tile, edit: row, text: row.label, changed: row.changed }));
        else if (node.tagName === "TD") swapNode(node, familyCell({ ...row, cell_title: was.cell_title }));
        // a Main row is named by its tile
        else redrawRow(node, was.caption ? { ...row, name: was.name, caption: was.caption, editable: was.editable && row.editable } : row);
      }
    }
  });
}

/** The answer the page was drawn from, brought up to date with the rows of a change, so the next answer is compared
 *  with what is shown (a Main row keeps its tile's name, a table cell its title). */
function noteRows(rows, asKey) {
  if (!shownPage || !shownPage.data || !rows.length) return;
  const by = new Map(rows.map((r) => [r.key, r]));
  if (asKey && !by.has(asKey)) by.set(asKey, { ...rows[0], key: asKey });
  const fix = (r) => {
    const n = r && by.get(r.key);
    if (!n) return r;
    return { ...n, ...(r.caption ? { name: r.name, caption: r.caption, editable: r.editable && n.editable } : {}), ...(r.cell_title ? { cell_title: r.cell_title } : {}) };
  };
  const d = shownPage.data;
  if (Array.isArray(d.rows)) d.rows = d.rows.map(fix);
  if (Array.isArray(d.tiles)) d.tiles = d.tiles.map((t) => (t.edit && by.has(t.edit.key) ? { ...t, edit: fix(t.edit), text: by.get(t.edit.key).label, changed: by.get(t.edit.key).changed } : t));
  if (Array.isArray(d.groups)) for (const g of d.groups) g.rows = g.rows.map(fix);
}

// --- the welcome page, before a file is open ---

/** A text with a place to break the line after each "/", so a path on the card (PRIVATE/SONY/…) wraps at its folders. */
const slashBreaks = (t) => t.split("/").flatMap((part, i) => (i ? ["/", el("wbr"), part] : [part]));

/** What the window shows before a file is open: the ways in (Read names the camera it reads, or opens Connect to the
 *  camera while no link is chosen; a file; the sample), then the recent files. */
function welcome() {
  const s = state;
  const recent = s.recent || [];
  const card = (title, sub, onclick) => el("button", { class: "card", onclick }, el("span", { class: "ct" }, plain(title)), el("span", { class: "weak" }, sub));
  return el("div", { class: "welcome" },
    el("h1", {}, "Camset Editor"),
    el("p", { class: "lead" }, "See and change your Sony camera's settings in plain words, compare setups, and write them back to the camera."),
    el("div", { class: "cards" },
      card("⬇ Read from camera", s.read_sub || "Over USB or the network.",
        () => { if (s.camera && !s.camera.link) openWindow("connect"); else $("b-read").click(); }),
      card("📂 Open a settings file", slashBreaks(s.open_sub || "A settings file the camera saved."), () => $("f-open").click()),
      s.sample ? card("✨ Explore a sample", "Look around with a sample camera, no setup needed.",
        () => replaceAct("sample", {}, null, "Explore a sample", opening("the sample"), "Open the sample")) : null),
    s.works_with && s.works_with.length ? el("p", { class: "weak" }, `Works with: ${s.works_with.join(", ")}`) : null,
    el("p", { class: "small weak" }, s.not_sony),
    // which editor this is: the status bar's version (a tap opens Settings > About), alone
    recent.length ? el("div", { class: "strong", style: { "margin-top": "24px" } }, "Recent files") : null,
    ...recent.map((r, i) => el("div", { style: { margin: "4px 0" } },
      el("a", { href: "#", title: r.path || r.name, style: { color: "var(--link)" }, onclick: (e) => { e.preventDefault(); openRecent(i); } }, r.name))));
}

// --- Main: its tiles and rows ---

/** The Main page: its pages (Stills, Movie, …), the tiles, then every setting they show as rows. */
function drawMain(j) {
  view.set = j.set;
  const head = el("div", { class: "head" }, el("h1", {}, "Main"),
    ...j.sets.map((n, i) => el("button", { class: "sel" + (i === j.set ? " on" : ""), onclick: () => { view.set = i; maybeDraw(); } }, n)));
  if (!j.tiles.length) return [head, el("p", {}, "The editor has no Main page tiles for this camera. The settings are in the tabs on the left.")];
  return [head,
    el("div", { class: "tiles" }, ...j.tiles.map(drawTile)),
    el("hr", { style: { "margin-top": "10px" } }),
    el("div", { class: "strong sub" }, "All Main settings"),
    el("div", { class: "grid" }, ...j.rows.map(drawRow))];
}

/** The tile last clicked, and its rows, as the window marks them. */
function focusTile(caption) {
  view.focus = caption;
  for (const t of document.querySelectorAll(".tile")) t.classList.toggle("focus", t.dataset.caption === caption);
  for (const r of document.querySelectorAll(".row[data-caption]")) r.classList.toggle("focus", r.dataset.caption === caption);
}

/** The values of a number setting, for a list on its tile (none when there are too many). */
function rangeOptions(e) {
  const step = Math.max(1, e.step || 1);
  if ((e.hi - e.lo) / step > 400) return null;
  const out = [];
  for (let v = e.lo; v <= e.hi; v += step) out.push([v, e.unit ? `${shownNumber(e, v)} ${e.unit}` : shownNumber(e, v)]);
  return out;
}

function drawTile(t) {
  const e = t.edit;
  // a value not checked on the camera is marked, as the window draws it in italics, but not the value held now, which
  // the window draws as the current value (its hover says why)
  const options = !e ? null : e.kind === "choice" ? e.options.map(([v, label, seen]) => [v, seen === false && v !== e.value ? `${label} (not checked)` : label]) : rangeOptions(e);
  const tile = el("div", { class: "tile" + (t.changed ? " changed" : "") + (options ? " can" : "") + (view.focus === t.caption ? " focus" : ""),
    "data-caption": t.caption, "data-key": options ? e.key : null, title: t.why ? `${t.text}\n\n${t.why}` : t.text, onclick: () => focusTile(t.caption) },
  el("div", { class: "cap" }, t.caption, t.changed ? el("span", { class: "edited" }, "  · edited") : null),
  el("div", { class: "val" }, t.text));
  if (options) {
    // the whole tile opens the list, as a click on it opens the window's
    const sel = el("select", { "aria-label": t.caption, "data-ctl": "value", onfocus: () => focusTile(t.caption),
      onchange: () => setSetting(e, { value: Number(sel.value) }) },
    ...options.map(([v, label]) => el("option", { value: String(v) }, label)));
    sel.value = String(e.value);
    tile.append(sel);
  }
  tile._tile = t;
  return tile;
}

// --- a tab: its groups, a setting's row and what its details say, the family tables ---

/** The settings with edits only, when Only edited is ticked. */
function onlyEdited(groups) {
  if (!view.only) return groups;
  return groups.map((g) => ({ ...g, rows: g.rows.filter((r) => r.changed || (g.beside && r.subs && r.subs.edited)) })).filter((g) => g.rows.length);
}

/** A tab: its name (and the layout switch when the definition says where its settings sit on the camera), then its
 *  groups as the window's collapsing headers in the tab's colour. */
function drawTab(groups, j = {}) {
  const t = (state.tab_info || []).find((x) => x.name === view.tab);
  const head = el("div", { class: "head" }, cmpBackButton(), el("h1", { style: { color: t && t.color } }, view.tab), j.places ? layoutSwitch(j.flat) : null);
  groups = onlyEdited(groups);
  if (!groups.length) return [head, el("p", {}, "No settings match.")];
  return [head, ...drawGroups(groups, view.tab, view.only)];
}

function drawSearch(groups) {
  hits = groups.reduce((n, g) => n + g.rows.length, 0);
  const head = el("div", { class: "head" }, el("h1", {}, `Search: "${view.q}"`));
  if (!hits) return [head, el("p", {}, "Nothing matches. The search looks at setting names, groups and value labels.")];
  groups = onlyEdited(groups);
  if (!groups.length) return [head, el("p", {}, `No edited settings match: none of the ${hits} setting(s) that match is edited.`)];
  return [head, el("p", { class: "small weak" }, `${hits} setting(s)${view.only ? ", the edited ones shown" : ""}`),
    ...drawGroups(groups, "?", true)];
}

/** The window's switch above the rows: as on the camera (the camera's order, a submenu's rows under it) or one flat
 *  list. The editor keeps the choice, for its window too. */
function layoutSwitch(flat) {
  const pick = (on) => () => { if (flat !== on) act("prefs", { name: "flat_list", value: on }); };
  return el("span", { class: "layout-switch" },
    selButton(!flat, "As on the camera", pick(false), "The rows in the camera's order, each submenu's rows indented under it, as the camera's menu lists them"),
    selButton(flat, "Flat list", pick(true), "Every setting of the group in one list"));
}

/** A tab's groups as the window's collapsing headers, open as they were left (all of them for a search); Picture
 *  Profiles and Creative Looks as one table per family. A group's rows are made when it is first opened: a tab can
 *  hold a thousand settings. */
function drawGroups(groups, where, allOpen) {
  if (!openGroups.has(where)) openGroups.set(where, new Set(groups.length ? [groups[0].name] : []));
  const open = openGroups.get(where);
  return groups.map((g) => {
    if (g.family) return drawFamily(g, open, allOpen);
    const body = el("div", { class: "grid" });
    const d = el("details", { class: "grp", open: allOpen || open.has(g.name), "data-group": g.name },
      el("summary", { style: { "--c": g.color } }, ...groupHead(g)), body);
    d._group = g;
    const fill = () => { if (!body.childElementCount) { body.append(...groupRows(d._group, where)); foldRows(body); } };
    if (d.open) fill();
    d.addEventListener("toggle", () => {
      if (d.open) { open.add(g.name); fill(); } else open.delete(g.name);
    });
    return d;
  });
}

/** A group's rows as drawn: as on the camera when the editor lays them out so (`layout`: the camera's rows that are
 *  headings, each setting's depth, the rows only another shooting mode's menu has under that mode's name ("In Movie
 *  mode"), the settings its definition does not place under "More settings in this group"), else the flat list. With
 *  Only edited, a heading stays only with a row still under it. */
function groupRows(g, where) {
  if (!g.layout) return g.rows.map(drawRow);
  const byKey = new Map(g.rows.map((r) => [r.key, r]));
  const lines = g.layout.filter((l) => !("key" in l) || byKey.has(l.key));
  const holds = (i) => {
    const l = lines[i];
    for (const m of lines.slice(i + 1)) {
      if ("more" in l) { if ("key" in m) return true; continue; }
      if ("mode" in l) { if ("key" in m) return true; if ("more" in m || "mode" in m) return false; continue; }
      if ("more" in m || "mode" in m || m.depth <= l.depth) return false;
      if ("key" in m) return true;
    }
    return false;
  };
  const out = [];
  lines.forEach((l, i) => {
    if ("key" in l) out.push(drawRow({ ...byKey.get(l.key), depth: l.depth }));
    else if (!holds(i)) return;
    else if ("head" in l) out.push(rowHead(l, g, where));
    else if ("mode" in l) out.push(el("div", { class: "row rowmore rowmode", "data-depth": 0, title: `The rows below are in the camera's menu in ${l.name} mode only` }, el("div", { class: "name" }, l.mode)));
    else out.push(el("div", { class: "row rowmore", "data-depth": 0, title: "The settings whose row in the camera's menu is not known yet" }, el("div", { class: "name" }, l.more)));
  });
  return out;
}

/** A row of the camera's menu that holds no setting of its own here: a heading that folds the rows under it, kept
 *  folded while the page is open, as the window keeps its own. */
function rowHead(l, g, where) {
  const key = JSON.stringify([where, g.name, l.path]);
  const name = el("div", { class: "name", title: "A row of the camera's menu: click to fold or show the settings under it" }, l.head);
  const head = el("div", { class: "row rowhead", "data-depth": l.depth, style: { "--depth": String(l.depth) } }, name);
  const show = () => {
    const folded = xp.rowFolds.has(key);
    head.classList.toggle("folded", folded);
    name.setAttribute("aria-expanded", String(!folded));
  };
  pressable(name, () => {
    if (xp.rowFolds.has(key)) xp.rowFolds.delete(key); else xp.rowFolds.add(key);
    show();
    foldRows(head.parentElement);
  });
  show();
  return head;
}

/** Hide the rows a folded heading of the camera's layout holds, down to the next line as shallow. */
function foldRows(body) {
  if (!body) return;
  let under = null;
  for (const n of body.children) {
    const d = Number(n.dataset.depth || 0);
    if (under !== null && (d <= under || n.classList.contains("rowmore"))) under = null;
    n.hidden = under !== null;
    if (under === null && n.classList.contains("rowhead") && n.classList.contains("folded")) under = d;
  }
}

/** A setting's row drawn again in place: how deep the camera's layout put it and whether a folded heading hides it
 *  stay as they were. */
function redrawRow(node, r) {
  const was = node._row || {};
  const fresh = drawRow(was.depth !== undefined ? { ...r, depth: was.depth } : r);
  fresh.hidden = node.hidden;
  swapNode(node, fresh);
}

/** A group's head: its name and count, and how many of its settings are edited. */
function groupHead(g) {
  const edited = g.rows.filter((r) => r.changed).length + (g.beside ? g.rows.reduce((n, r) => n + ownSubs(r).filter((x) => x.changed).length, 0) : 0);
  // the page an option opens (`page`), marked as the window's group column marks it
  return [el("span", { style: { "white-space": "pre-wrap" }, title: g.page ? "A page of settings an option opens on the camera (Right on it)" : undefined }, `${g.page ? "› " : ""}${g.name}  (${groupCount(g)})`),
    edited ? el("span", { class: "badge", title: "settings edited in this group" }, String(edited)) : null].filter(Boolean);
}

/** How many settings a group shows, as the window counts them: its rows, and as on the camera the sub-choices beside
 *  their owners' options (`beside`), which are no rows (with Only edited, the edited ones). */
function groupCount(g) {
  if (!g.beside) return g.rows.length;
  return g.rows.reduce((n, r) => n + 1 + ownSubs(r).filter((x) => !view.only || x.changed).length, 0);
}

/** A row's sub-choices this group counts: a family's (a look's parameters) are counted once, in the family's table. */
function ownSubs(r) {
  return ((r.subs && r.subs.rows) || []).filter((x) => !x.family);
}

/** A stored number as shown (`shown_as`, as the window's `Setting::shown_number`): divided by `divide`, with
 *  `decimals` decimals (7500 by 100 is "75", 3 by 10 with one decimal "0.3"), more when those would round it (9250
 *  by 100 is "92.5"); the number itself without one. */
function shownNumber(r, v) {
  const a = r && r.shown_as;
  if (!a || !(a.divide > 0)) return String(v);
  let d = Math.min(a.decimals || 0, 9);
  while (d < 9 && (v * 10 ** d) % a.divide !== 0) d += 1;
  return (v / a.divide).toFixed(d);
}

/** The number stored for a shown one ("75", "0,3"): multiplied back by `shown_as`'s divide and rounded; null when it
 *  is no number. */
function storedNumber(r, text) {
  const x = Number(String(text).trim().replace(",", "."));
  if (String(text).trim() === "" || !Number.isFinite(x)) return null;
  const a = r && r.shown_as;
  return Math.round(x * (a && a.divide > 0 ? a.divide : 1));
}

/** A number's range in the terms it is shown in, as the window's: "%, 0 to 100 in steps of 5". */
function rangeWords(r) {
  const steps = r.step > 1 || r.shown_as ? " in steps of " + shownNumber(r, r.step) : "";
  return `${r.unit ? r.unit + ", " : ""}${shownNumber(r, r.lo)} to ${shownNumber(r, r.hi)}${steps}`;
}

/** A typed number put on the setting's steps and into its range, as the window's number box does (`snap_to_step`):
 *  the nearest step from the bottom of the range, at most the last step under its top. */
function snapToStep(v, lo, hi, step) {
  step = Math.max(1, step || 1);
  const top = Math.max(lo, hi - (hi - lo) % step);
  return Math.min(top, Math.max(lo, lo + Math.round((v - lo) / step) * step));
}

/** A number box for a range row, shown and typed in the terms `shown_as` gives. What is typed is put on the
 *  setting's steps and into its range before it is sent, as the window does (else the editor would refuse it); a
 *  box left empty, or holding no number, shows the value again. */
function numberInput(r, label, set) {
  const s = (v) => shownNumber(r, v);
  const input = el("input", { type: "number", min: s(r.lo), max: s(r.hi), step: s(r.step), value: s(r.value), disabled: !r.editable, "aria-label": label, "data-ctl": "value" });
  input.addEventListener("change", () => {
    const typed = storedNumber(r, input.value);
    const v = typed === null ? r.value : snapToStep(typed, r.lo, r.hi, r.step);
    input.value = s(v);
    if (v !== r.value) set(v);
  });
  return input;
}

/** An option of a row's list in words, and its hover: "(not checked)" after a value not checked on the camera yet
 *  (`unseen`, the window's italics; the callers leave the value held now unmarked, as the window draws it as the
 *  current value), "(refused by the camera)" after one the camera refuses (`refused`, with the window's hover); its
 *  help on hover, which says why for either. A value the menus never offer (seen null: listed only while the file
 *  holds it) has no mark, its help saying why, as the window draws it. */
function optionWords(r, v, label, unseen, help) {
  const refused = !!r.refused && r.refused.includes(v);
  // an option that opens a whole page of rows on the camera (`pages`: Picture Profile's PP1), marked "›" as in the window
  const page = (r.pages || []).find((p) => p.option === label);
  const named = label + (page ? "  ›" : "");
  const text = refused ? `${named} (refused by the camera)` : unseen ? `${named} (not checked)` : named;
  const title = [help, refused ? r.refused_why : null, page ? `Opens a page of ${page.count} settings on the camera (Right on it).` : null].filter(Boolean).join("\n\n") || undefined;
  return [text, title];
}

/** A row's list of values as options of a list box, in words (`optionWords`). */
function optionList(r, options) {
  return options.map(([v, label, seen, help]) => {
    const [text, title] = optionWords(r, v, label, seen === false && v !== r.value, help);
    return el("option", { value: String(v), title }, text);
  });
}

/** The main option of a row's option tree that holds its value, or -1 (then the row shows its flat list). */
function treeAt(r) {
  return (r.tree || []).findIndex((n) => n.value === r.value || (n.options || []).some(([v]) => v === r.value));
}

/** What choosing a main option of the tree stores, as the window's detail panel: the value held now when it is one
 *  of the option's, else its one value, else its first choice. */
function treePick(node, value) {
  if (node.options) return node.options.some(([v]) => v === value) ? value : node.options[0][0];
  return node.value;
}

/** A setting's options as the camera lays them out (`tree`, from the definition's option_tree): a list of its main
 *  options, and under it, when the value belongs to an option with a choice of its own, the list of that choice. The
 *  stored value is still one of the flat list's; each option's help and "not checked" come with it. */
function treeControls(r, set) {
  const at = treeAt(r);
  const flat = new Map(r.options.map((o) => [o[0], o]));
  const main = el("select", { disabled: !r.editable, "aria-label": r.name, "data-ctl": "value", onchange: () => {
    const v = treePick(r.tree[Number(main.value)], r.value);
    if (v !== r.value) set({ value: v });
  } }, ...r.tree.map((n, i) => {
    if (n.options) return el("option", { value: String(i), title: `Has a choice of its own: ${n.options.map(([, l]) => l).join(", ")}` }, n.label);
    const [, , seen, help] = flat.get(n.value) || [];
    const [text, title] = optionWords(r, n.value, n.label, seen === false && n.value !== r.value, help);
    return el("option", { value: String(i), title }, text);
  }));
  main.value = String(at);
  const out = [el("span", { class: "combo" + (r.editable ? "" : " off") }, main)];
  const node = r.tree[at];
  if (node.options) {
    const sub = el("select", { disabled: !r.editable, "aria-label": `${r.name}: ${node.label}`, onchange: () => set({ value: Number(sub.value) }) },
      ...optionList(r, node.options));
    sub.value = String(r.value);
    out.push(el("span", { class: "combo sub" + (r.editable ? "" : " off") }, sub));
  }
  return out;
}

/** One setting: its name (the record id beside it when Settings asks; a click unfolds the window's detail panel), its
 *  control, what it was, the proof line, the raw value, its notes, and why it is greyed out on the camera. */
function drawRow(r) {
  const set = (body) => setSetting(r, body);
  const ctl = el("div", { class: "ctl" });
  const more = [];
  if (r.kind === "choice" && treeAt(r) >= 0) {
    ctl.append(...treeControls(r, set));
  } else if (r.kind === "choice") {
    const sel = el("select", { disabled: !r.editable, "aria-label": r.name, "data-ctl": "value", onchange: () => set({ value: Number(sel.value) }) }, ...optionList(r, r.options));
    sel.value = String(r.value);
    ctl.append(el("span", { class: "combo" + (r.editable ? "" : " off") }, sel));
  } else if (r.kind === "range") {
    const input = numberInput(r, r.name, (v) => set({ value: v }));
    const nudge = (d) => () => set({ value: r.value + d * r.step });
    ctl.append(el("div", { class: "drag" },
      el("button", { class: "small", disabled: !r.editable || r.value - r.step < r.lo, onclick: nudge(-1), "aria-label": `${r.name}: one step down` }, "−"),
      input,
      el("button", { class: "small", disabled: !r.editable || r.value + r.step > r.hi, onclick: nudge(1), "aria-label": `${r.name}: one step up` }, "+")));
    more.push(el("span", { class: "weak" }, rangeWords(r)));
  } else if (r.kind === "text") {
    const input = el("input", { type: "text", maxlength: r.max_len, value: r.label, disabled: !r.editable, spellcheck: "false", autocomplete: "off", "aria-label": r.name, "data-ctl": "value" });
    const apply = () => set({ text: input.value });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") apply(); });
    ctl.append(el("div", { class: "textset" }, input, el("button", { class: "small", disabled: !r.editable, onclick: apply }, "Apply")));
  } else {
    ctl.append(el("span", { class: "shown" }, r.label));
  }
  // a number with no name yet says why on hover (the row's details say it too)
  if (r.unnamed) ctl.title = r.unnamed;
  if (r.changed) {
    // a copy in step with its setting takes the setting back along, as its note says (the editor's Revert)
    more.push(el("span", { class: "weak" }, "was " + (r.original || "(empty)")),
      el("button", { class: "small", onclick: () => act("revert", { target: rowTarget(r), key: r.key }) }, "Revert"));
  }
  // where the plain Revert changes nothing: a value a Save As kept put back to what the camera wrote, or a copy put back
  // in step with its setting (`put_back`, in the editor's words, with what it does on hover)
  if (r.put_back) more.push(el("button", { class: "small", "data-put-back": "", title: r.put_back_why || undefined, onclick: () => act("restore", { target: rowTarget(r), key: r.key }) }, r.put_back));
  const expert = !!(state.prefs && state.prefs.expert);
  // a setting whose proofs disagree says so in place of the proof line (the editor sends it in Expert mode only)
  if (r.disputed && expert) more.push(el("span", { class: "proof no", title: "The proofs of this setting disagree: what the editor shows is not counted as proved" }, r.disputed));
  else if (r.proof && expert) more.push(el("span", { class: "proof " + (r.proof_kind || "no"), title: r.proof_why || undefined }, r.proof));
  if (expert && r.raw !== undefined && r.raw !== null) more.push(el("span", { class: "weak mono" }, `raw value: ${r.raw}`));
  const under = [];
  if (r.warn) under.push(el("div", { class: "warn" }, plain("⚠ " + r.warn)));
  // view only outside Expert mode (a copy the camera keeps of another setting, or a setting no menu writes): why, in
  // the window's words, the definition's own reason on hover
  if (r.locked) under.push(el("div", { class: "note", "data-locked": "", title: r.locked_why || undefined }, plain(r.locked)));
  // a value the camera keeps in more than one record: what changing it changes, or that the file is out of step there,
  // in the window's words (`copy_note`), before anything is changed
  if (r.copy_note) under.push(el("div", { class: "note", "data-copy-note": "", title: r.copy_note_why || undefined }, plain(r.copy_note)));
  if (r.inactive) {
    under.push(el("div", { class: "weak" }, r.inactive.text, " ",
      r.inactive.unlock ? el("button", { class: "small", onclick: () => act("activate", { target: rowTarget(r), key: r.key }) }, r.inactive.unlock) : null));
  }
  // the record id beside the name, as Settings asks (the Main page's rows keep their tile's caption)
  const name = el("div", { class: "name", "data-ctl": "name" }, r.name, expert && r.record_id && !r.caption ? `\u00a0\u00a0${r.record_id}` : null);
  const row = el("div", { class: "row" + (r.changed ? " changed" : "") + (r.inactive ? " inactive" : "") + (r.caption && r.caption === view.focus ? " focus" : ""),
    "data-caption": r.caption, "data-key": r.key, "data-depth": r.depth, style: r.depth ? { "--depth": String(r.depth) } : undefined },
  name, ctl, el("div", { class: "more" }, ...more),
  under.length ? el("div", { class: "under" }, ...under) : null);
  const lines = rowDetail(r);
  if (lines.length) {
    const box = el("div", { class: "detail" }, ...lines);
    const show = (on) => { row.classList.toggle("open", on); box.hidden = !on; name.setAttribute("aria-expanded", String(on)); };
    name.classList.add("dt");
    name.title = "Click for more about this setting";
    pressable(name, () => {
      const on = !xp.detail.has(r.key);
      if (on) xp.detail.add(r.key); else xp.detail.delete(r.key);
      show(on);
    });
    show(xp.detail.has(r.key));
    row.append(box);
  }
  // where it sits on the camera, as the window's hover says
  if (r.place) name.title = [r.place, name.title || null].filter(Boolean).join("\n");
  if (r.mymenu_on) name.addEventListener("contextmenu", (e) => { e.preventDefault(); showMyMenu(r, e.clientX, e.clientY); });
  row._row = r;
  return row;
}

/** The links to the pages a row's options open on the camera (`pages`), as the window's option list has them: the
 *  chosen option's ("Open the PP1 page"), then the others, each opening its page's group where it is shown. */
function pageLinks(r) {
  const link = (p, words) => el("a", { href: "#", "data-page": p.option, title: `The ${p.count} settings the camera lists on the page ${p.option} opens`,
    onclick: (e) => { e.preventDefault(); openSetting({ key: p.key, tab: p.open_tab, open_tab: p.open_tab, open_group: p.open_group }); } }, words);
  const now = r.pages.find((p) => p.option === r.label);
  const others = r.pages.filter((p) => p !== now);
  return el("div", { class: "small pages" }, now ? link(now, now.words) : null,
    others.length ? el("span", { class: "weak" }, now ? "  · Other pages: " : "Pages: ") : null,
    ...others.flatMap((p, i) => [i ? " · " : "", link(p, p.option)]));
}

/** The detail panel's lines the row does not show already. */
function rowDetail(r) {
  const h = state.row_hovers || {};
  const expert = !!(state.prefs && state.prefs.expert);
  const out = [];
  // the photographer's line first: whose words the help is, as the window's hover says, the camera's own (a help file
  // on that computer) or Camset's
  if (r.help) out.push(el("div", { class: "help", title: r.help_from_file ? h.help : h.help_own }, r.help));
  // a setting this camera's menu does not have, said in plain words where the proof badge does not say it
  if (r.not_on_camera && !(expert && state.prefs.show_proof)) out.push(el("div", { class: "small weak" }, "Not on this camera's menu"));
  // as under the window's option list: the options with a choice of their own (named in Expert mode), and the choice
  // of the one chosen now, changed as on its own row
  if (r.subs) {
    const box = el("div", { class: "subs" },
      expert ? el("div", { class: "weak" }, `These options have a choice of their own on the camera: ${r.subs.options.join(", ")}`) : null);
    // every choice of the option chosen now, in the definition's order, and any other edited or opened from elsewhere
    const flat = !!(state.prefs && state.prefs.flat_list);
    for (const s of (r.subs.rows || []).filter((x) => x.option === r.subs.now || x.changed || x.key === xp.subFocus)) {
      const title = s.option !== r.subs.now ? `The camera shows this choice beside ${s.option} when ${s.option} is chosen; it is shown here as it is edited or was opened.`
        : flat ? "The choice the camera shows beside this option. It is also a row of its own in this group." : "The choice the camera shows beside this option (Right opens it on the camera).";
      const one = el("div", { class: "grid" + (s.key === xp.subFocus ? " focus" : "") }, drawRow(s));
      box.append(el("div", { class: "strong", title }, `For ${s.option}:`), one);
    }
    out.push(box);
  }
  // the pages its options open (Picture Profile's PP1…): the chosen option's link first, the others after it
  if (r.pages) out.push(pageLinks(r));
  // a sub-choice listed by a search: as on the camera it is beside its row's option, which this opens
  if (r.beside) {
    out.push(el("div", { class: "small" }, el("a", { href: "#", title: `As on the camera it is beside ${r.beside.option} of ${r.beside.name}`,
      onclick: (e) => { e.preventDefault(); openSetting({ ...r.beside, key: r.key }); } }, `Open beside ${r.beside.name} > ${r.beside.option}`)));
  }
  // the mapping team's note, and the records and what is written with them: Expert mode only
  if (expert && r.note) out.push(el("div", { class: "note" }, r.note));
  if (r.unnamed) out.push(el("div", { class: "note" }, r.unnamed));
  const meta = [];
  if (r.modes) meta.push(el("span", { class: "modes", title: h.modes }, `Applies in: ${r.modes}`));
  if (r.stored === "sets") meta.push(el("span", { class: "weak", title: "Registering a memory (Camera Set. Memory) copies this setting into it. The Memories page shows them side by side." }, "Kept in the memories too"));
  if (r.stored === "live" && expert) meta.push(el("span", { class: "weak", title: h.live }, "Live settings only"));
  if (r.record && expert) meta.push(el("span", { class: "weak", title: h.record }, r.record));
  if (meta.length) out.push(el("div", { class: "meta" }, ...meta));
  // the values its menus never offer, and a factory value the camera writes itself, in the window's words (not_offered_lines)
  for (const n of r.not_offered || []) out.push(el("div", { class: "note", title: n.title || undefined }, n.text));
  if (r.display_rule) out.push(el("div", { class: "weak" }, `Shown differently on the camera: ${r.display_rule}`));
  // the values the gate holds back, in the window's words (hidden_words), as its detail panel says them
  if (r.hidden_words && expert) out.push(el("div", { class: "weak" }, r.hidden_words));
  if (r.kind === "fixed") out.push(el("div", { class: "weak" }, "Only one value is known for this setting, so it cannot be changed here."));
  if (r.compare_text !== undefined) out.push(el("div", {}, el("span", { class: "weak" }, "Compare file: "), el("span", { class: "cmpval" }, r.compare_text)));
  if (r.records && expert) {
    out.push(el("div", { class: "meta" }, el("span", { class: "weak" }, r.records),
      el("button", { class: "small", title: h.record_map, onclick: () => showInMap(r.record_hex) }, "Show in record map")));
  }
  if (r.mymenu_on) out.push(el("div", { class: "meta" }, ...myMenuItems(r)));
  return out;
}

/** A family (Picture Profiles, Creative Looks) as the window's table: a row per parameter, a column per profile, its
 *  cells made when the group is first opened. */
function drawFamily(g, open, allOpen) {
  const body = el("div", { class: "fam" });
  const d = el("details", { class: "grp", open: allOpen || open.has(g.name) || g.rows.some((r) => r.key === xp.reveal), "data-group": g.name },
    el("summary", { style: { "--c": g.color } }, ...groupHead(g)), body);
  d._group = g;
  const fill = () => {
    if (body.childElementCount) return;
    // the group as it is now (patchGroups keeps it up to date while folded); Only edited keeps the changed cells, as
    // the window's table keeps only the edited settings
    const now = d._group;
    const byKey = new Map(now.rows.map((r) => [r.key, r]));
    const lines = now.params.map((p, i) => [p, now.cells[i].map((k) => (k && byKey.get(k)) || null)]).filter(([, cells]) => cells.some(Boolean));
    body.append(el("div", { class: "small weak" }, now.note),
      el("div", { class: "scrollx" }, el("table", { class: "egrid" },
        el("thead", {}, el("tr", {}, el("th", {}, "Parameter"), ...now.profiles.map((p) => el("th", {}, p)))),
        el("tbody", {}, ...lines.map(([name, cells]) => el("tr", {}, el("td", {}, name), ...cells.map(familyCell)))))));
  };
  if (d.open) fill();
  d.addEventListener("toggle", () => {
    if (d.open) { open.add(g.name); fill(); } else open.delete(g.name);
  });
  return d;
}

/** One cell of a family's table: the setting's control, named by its place (`cell_title`). */
function familyCell(r) {
  if (!r) return el("td", {});
  const set = (value) => setSetting(r, { value });
  let ctl;
  if (r.kind === "choice") {
    // the values in words as a row's list has them, the ones the camera refuses marked (choosing one makes the camera
    // reject the whole file)
    const sel = el("select", { disabled: !r.editable, "aria-label": r.cell_title, "data-ctl": "value", onchange: () => set(Number(sel.value)) },
      ...optionList(r, r.options));
    sel.value = String(r.value);
    ctl = el("span", { class: "combo" + (r.editable ? "" : " off") }, sel);
  } else if (r.kind === "range") {
    ctl = el("div", { class: "drag" }, numberInput(r, r.cell_title, set));
  } else {
    ctl = el("span", {}, r.label);
  }
  // its place, and why a number has no name yet, on hover (the window's table cell)
  const title = [r.cell_title, r.unnamed].filter(Boolean).join("\n\n") || undefined;
  const td = el("td", { class: r.changed ? "fam-changed" : undefined, title, "data-key": r.key }, ctl);
  td._row = r;
  return td;
}

/** Where the Menu shows the settings of a tab, as the window has it (`shown_view`): the tab's own entry, or for a tab
 *  with none the editor's route (`routes`): the My Menu page, or Other. */
function menuPlace(tab) {
  const r = (state.routes || {})[tab];
  return r ? { page: r.page, tab: r.tab || null } : { page: "tab", tab };
}

/** Open a setting in its tab (or where the Menu shows it: `open_tab`, the entry for what the camera's menus do not
 *  hold as on the camera, else where the Menu shows its tab: `menuPlace`), with its group and details unfolded, and
 *  bring it into view. Its group is the one that shows it in the layout in use, as the editor names it
 *  (`open_group`: as on the camera, the camera group whose page holds its row), else its own. Answers the row (or the
 *  sub-choice's box) brought into view, if any. */
async function openSetting(s) {
  const place = menuPlace(s.open_tab || s.tab);
  view.page = place.page;
  if (place.tab) view.tab = place.tab;
  clearSearch();
  const where = place.page === "tab" ? place.tab : place.page;
  if (!openGroups.has(where)) openGroups.set(where, new Set());
  openGroups.get(where).add(s.open_group || s.group);
  xp.detail.add(s.key);
  xp.reveal = s.key;
  xp.subFocus = s.key;
  drawSide();
  await drawContent(contentKey());
  // its own row of the group, not its copy in another row's details (a choice shown under its option)
  const key = CSS.escape(s.key);
  let at = document.querySelector(`details.grp > .grid > [data-key="${key}"]`);
  if (!at) {
    // as on the camera a sub-choice is no row: its owner's row opens, its details showing it beside the option, marked
    const owner = [...document.querySelectorAll("details.grp > .grid > .row")].find((n) => n._row && n._row.subs && (n._row.subs.rows || []).some((x) => x.key === s.key));
    if (owner) {
      xp.detail.add(owner._row.key);
      if (owner.hidden) unfoldTo(owner);
      redrawRow(owner, owner._row);
      const fresh = document.querySelector(`details.grp > .grid > [data-key="${CSS.escape(owner._row.key)}"]`);
      at = (fresh && fresh.querySelector(`.subs [data-key="${key}"]`)) || fresh;
    }
  }
  at = at || document.querySelector(`[data-key="${key}"]`);
  if (at && at.hidden) unfoldTo(at);
  if (at) at.scrollIntoView({ block: "center" });
  xp.reveal = null;
  return at;
}

/** Show a row a folded heading of the camera's layout hides: the headings above it unfold, the nearest first. */
function unfoldTo(node) {
  let depth = Number(node.dataset.depth || 0);
  for (let n = node.previousElementSibling; n && depth > 0; n = n.previousElementSibling) {
    const d = Number(n.dataset.depth || 0);
    if (d >= depth) continue;
    if (n.classList.contains("rowhead") && n.classList.contains("folded")) n.querySelector(".name").click();
    depth = d;
  }
}

/** "Show in record map": the record map, searched for the record, as the window's button does. */
function showInMap(hex) {
  view.page = "records";
  view.q = hex;
  hits = null;
  $("search").value = hex;
  $("b-clear").hidden = false;
  drawSide();
  drawContent(contentKey());
}

/** A value whose label is its own number ("30 [30]") shown once, as one without a label is. */
const sameNumber = (t) => String(t ?? "").replace(/^([+-]?\d+(?:\.\d+)?)\s*\[\1\]$/, "$1");

/** Every edit: where, which setting, what it was and is, as the window's All edits. */
function drawChanges(list) {
  const head = el("div", { class: "head" }, el("h1", {}, "All edits"));
  if (!list.length) return [head, el("p", {}, "No edits yet.")];
  return [head, el("div", { class: "scrollx" }, el("table", { class: "egrid" },
    el("thead", {}, el("tr", {}, el("th", {}, "Where"), el("th", {}, "Setting"), el("th", {}, "Was"), el("th", {}, "Now"), el("th", {}, ""))),
    el("tbody", {}, ...list.map((c) => el("tr", {},
      el("td", {}, c.where), el("td", {}, c.name), el("td", {}, sameNumber(c.was)), el("td", { class: "now" }, sameNumber(c.now)),
      el("td", {}, el("button", { class: "small", onclick: () => act("revert_record", { section: c.section, id: c.id }) }, "Revert")))))))];
}

// --- Memories ---

/** The Memories item: the page opens with the rows the search box matches, as the window's does
 *  (typing in the box again shows the search's results, as there). */
function memOpen() {
  clearTimeout(searchTimer);
  memView.q = $("search").value.trim();
  view.q = "";
  hits = null;
  view.page = "memories";
  drawn = null;
  drawSide();
  redraw();
}

/** "Only the rows shown" beside Recall, Register and Whole sets: off unless ticked, so a whole set copies the whole set. */
const wholeSets = { onlyShown: false };

/** The box saying whether Recall and Register copy only the rows a search or a tab leaves (`n` of them, when known). */
function onlyShownBox(n) {
  const box = el("input", { type: "checkbox", checked: wholeSets.onlyShown, onchange: () => { wholeSets.onlyShown = box.checked; redraw(); } });
  return el("label", { class: "check", title: "Off: the whole set is copied. On: only the settings the search or the tab leaves" }, box,
    n === undefined ? " Only the rows shown" : ` Only the ${n} row(s) shown`);
}

/** A dial memory's Recall and Register buttons (the Whole sets of Compare and of the Memories page), in the window's
 *  words and with its hover texts. */
function wholeSetButtons(b, filter, disabled = false) {
  return [el("button", { disabled, title: b.recall_tip, onclick: () => copySet("recall", b.section, b.recall, filter) }, plain(b.recall)),
    el("button", { disabled, title: b.register_tip, onclick: () => copySet("register", b.section, b.register, filter) }, plain(b.register))];
}

/** Recall a memory into the live settings, or register them into it; then say what was copied, with Undo. */
async function copySet(what, memory, label, filter) {
  const only = wholeSets.onlyShown && !!filter;
  // `shown` narrows the copy to the search and tab given
  const j = await act(what, { memory, ...(only ? { ...filter, shown: true } : {}) });
  if (!j) return;
  const n = typeof j.n === "number" ? `${j.n} value(s) copied` : "copied";
  // and the settings a file here holds in another shape, which the copy left alone (the editor's `message`)
  toast(`${label}: ${n}${only ? ", only the rows shown" : ", the whole set"}.${j.message ? " " + j.message : ""}`, true);
}

/** The Memories page, as the window's: recall a memory into the live settings or register them into
 *  it, then every setting the memories keep, by tab and group, the live value beside each memory's,
 *  a pale fill where a memory differs (an arrow each way), orange with a pencil where it is an edit. */
function drawMemories(j) {
  const kids = [el("div", { class: "head" }, el("h1", {}, j.title)), el("p", { class: "small weak" }, j.intro)];
  const actions = el("div", { class: "mem-actions" }, el("strong", {}, "Whole sets:"));
  const filter = memView.q ? { q: memView.q } : null;
  j.buttons.forEach((b, i) => {
    if (i) actions.append(el("span", { class: "vsep" }));
    actions.append(...wholeSetButtons(b, filter, !j.editable));
  });
  if (filter) actions.append(onlyShownBox(j.groups.reduce((n, g) => n + g.rows.length, 0)));
  if (j.others.length) {
    const box = el("input", { type: "checkbox", checked: j.all, onchange: () => { memView.all = box.checked; redraw(); } });
    actions.append(el("span", { class: "vsep" }), el("label", { class: "check",
      title: `Also show ${j.others.map(([, n]) => n).join(", ")} as columns. Recall and register stay with the mode dial's memories.` }, box, " Other memory sets"));
  }
  kids.push(actions);
  if (typeof j.only_diff === "boolean") {
    // as the window's: only the rows where a memory differs from the live settings
    const only = el("input", { type: "checkbox", checked: j.only_diff, onchange: () => { memView.only = only.checked; redraw(); } });
    kids.push(el("div", { class: "mem-actions" }, el("label", { class: "check", title: "Show only the settings where a memory holds another value than the live settings" }, only, " Only rows that differ from Live")));
  }
  if (memView.q) {
    kids.push(el("p", { class: "small weak" }, `The settings that match "${memView.q}". `,
      el("button", { class: "small", onclick: () => $("b-clear").click() }, "Show all")));
  }
  if (!j.groups.length) return [...kids, el("p", {}, j.only_diff ? "No memory holds another value than the live settings here." : "No settings match.")];
  const names = new Map(j.cols);
  const body = el("tbody");
  for (const g of j.groups) {
    body.append(el("tr", {}, el("td", { colspan: 2 + j.cols.length, class: "strong", style: { color: g.color } }, el("span", {}, `${g.tab} > ${g.group}`))));
    for (const r of g.rows) {
      body.append(el("tr", {},
        el("td", {}, r.name),
        el("td", {}, memValue(r.live, false)),
        ...r.cells.map((c) => el("td", {}, el("span", { class: "mem-cell" },
          memValue(c, c.differs),
          // an arrow only into a set that takes a value of it (`takes`: not where it is view only outside Expert mode)
          j.editable && c.differs && (!c.takes || c.takes[0] || c.takes[1]) ? el("span", { class: "mem-arrows" },
            !c.takes || c.takes[0] ? el("button", { class: "small", title: withNote(c.into_live || "Put this value into the live settings", r.live.copies), "aria-label": c.into_live || "Put this value into the live settings",
              onclick: () => act("memory_copy", { key: r.key, from: c.section, to: 0 }) }, plain("⬅")) : null,
            !c.takes || c.takes[1] ? el("button", { class: "small", title: withNote(c.from_live || `Put the live value into ${names.get(c.section)}`, c.copies), "aria-label": c.from_live || `Put the live value into ${names.get(c.section)}`,
              onclick: () => act("memory_copy", { key: r.key, from: 0, to: c.section }) }, plain("➡")) : null) : null)))));
    }
  }
  kids.push(el("div", { class: "scrollx mem-scroll" }, el("table", { class: "egrid mem" },
    el("thead", {}, el("tr", {}, el("th", {}, "Setting"), el("th", {}, "Live"), ...j.cols.map(([, n]) => el("th", {}, n)))),
    body)));
  return kids;
}

/** An arrow's words, with what the copy changes where the camera keeps the value in more than one record (the
 *  editor's `copy_note` for the set it goes into), as the window's arrow says on hover. */
function withNote(words, note) {
  return note ? `${words}\n\n${note}` : words;
}

/** One value on the Memories page, as the window draws it: a pale fill where it differs from the live settings,
 *  orange with a pencil and an orange outline where it is an edit. */
function memValue(c, differs) {
  // a number with no name yet says why on hover
  return el("span", { class: "mem-v" + (differs ? " diff" : "") + (c.edited ? " edited" : ""), title: c.why || null }, c.edited ? plain("✏ " + c.text) : c.text);
}

// --- Exposure ---

const EX_SVG_NS = "http://www.w3.org/2000/svg";
/** An SVG element with attributes and children. */
function exSvg(tag, attrs = {}, ...kids) {
  const e = document.createElementNS(EX_SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) e.setAttribute(k, String(v));
  for (const k of kids) if (k !== null && k !== undefined) e.append(k);
  return e;
}

/** One side on its stop scale, as the window draws it (210 × 30, 7 at each end): a tick per whole
 *  stop, the band the limits leave the camera, a bar at a one-sided limit, and the value (a filled
 *  dot: you set it; a ring: the camera does). */
function exStrip(cell, scale) {
  const [w, pad, y] = [210, 7, 15];
  const span = scale.hi - scale.lo || 1;   // a scale of a single stop draws everything at its left end, not nowhere
  const x = (s) => pad + Math.min(1, Math.max(0, (s - scale.lo) / span)) * (w - 2 * pad);
  const out = exSvg("svg", { class: "ex-strip", viewBox: "0 0 210 30", role: "img", "aria-label": cell.hover }, exSvg("title", {}, cell.hover));
  if (cell.band) {
    const [a, b] = cell.band.map(x);
    out.append(exSvg("rect", { class: "ex-band", x: a, y: y - 7, width: Math.max(b, a + 2) - a, height: 14, rx: 3 }));
  }
  out.append(exSvg("line", { class: "ex-axis", x1: pad, y1: y, x2: w - pad, y2: y }));
  for (const t of scale.ticks) out.append(exSvg("line", { class: "ex-axis", x1: x(t), y1: y - 3, x2: x(t), y2: y + 3 }));
  if (cell.bound) out.append(exSvg("line", { class: "ex-bound", x1: x(cell.bound[0]), y1: y - 9, x2: x(cell.bound[0]), y2: y + 9 }));
  if (cell.at !== null && cell.at !== undefined) out.append(exSvg("circle", { class: "ex-at ex-" + cell.who, cx: x(cell.at), cy: y, r: 5 }));
  return out;
}

/** "Show in menu": the setting's tab with its group open and its row in view and marked, as the window's button
 *  selects it there (found by its key, as `openSetting` finds it). A setting only the memory sets keep is in the menu
 *  while a memory is edited. */
async function exShowInMenu(s) {
  const target = view.target;
  if (!s.live && view.target === 0) {
    const m = state.targets.find(([i, , own]) => i !== 0 && own !== false);
    if (m) view.target = m[0];
  }
  const at = await openSetting(s);
  if (view.target !== target) {
    const name = (state.targets.find(([i]) => i === view.target) || [])[1];
    toast(`${s.name} is kept in the memory sets only: now editing ${name}. Live settings are one tap away on the Editing row.`);
    refresh();
  }
  const row = at && at.closest(".row");
  if (row) row.classList.add("focus");
}

/** The Exposure page, as the window's: per column (the live settings and each dial memory) the
 *  exposure mode, the three sides on aligned stop scales, compensation and the EV they expose for;
 *  then what decides each side. On a phone the columns stack, each cell named. */
function drawExposure(j) {
  const n = j.columns.length;
  const grid = el("div", { class: "ex-grid", style: { "grid-template-columns": `max-content repeat(${n}, minmax(15rem, 17.9rem))` } });
  const at = (row, col) => ({ "grid-row": String(row), "grid-column": String(col) });
  const rowNames = ["", "Exposure mode", ...j.sides.map(([, name]) => name), "Exposure comp.", "Exposes for"];
  const range = (side) => { const sc = j.scales[side]; return sc ? `${sc.lo_label} to ${sc.hi_label}` : ""; };
  // egui's striped grid: every other row shaded, the header row not
  for (let r = 2; r <= rowNames.length; r += 2) grid.append(el("div", { class: "ex-stripe", style: { "grid-row": String(r) } }));
  rowNames.forEach((name, i) => {
    const side = j.sides[i - 2];
    if (name) grid.append(el("div", { class: "ex-head", style: at(i + 1, 1) }, el("div", { class: "strong" }, name),
      side && range(side[0]) ? el("div", { class: "small weak" }, range(side[0])) : null));
  });
  // a cell's own name, shown only where the columns stack (a phone)
  const lab = (name, sub) => el("div", { class: "ex-lab" }, el("span", { class: "strong" }, name), sub ? el("span", { class: "small weak" }, "  " + sub) : null);
  const chip = (who) => el("div", { class: "ex-chip ex-" + who }, el("span", { class: "ex-dot" }),
    who === "you" ? "you set it" : who === "camera" ? "the camera sets it" : "not known");
  j.columns.forEach((c, i) => {
    const col = i + 2;
    grid.append(el("div", { class: "ex-colname strong", style: at(1, col) }, c.name));
    grid.append(el("div", { class: "ex-cell", style: at(2, col) }, lab("Exposure mode"),
      el("div", { class: "strong" }, c.mode ?? "—"),
      c.control ? el("div", { class: "small" }, c.control) : null,
      c.mode_note ? el("div", { class: "small weak" }, c.mode_note) : null));
    j.sides.forEach(([side, name], k) => {
      const cell = c.cells[side];
      const scale = j.scales[side];
      grid.append(el("div", { class: "ex-cell", style: at(3 + k, col) }, lab(name, range(side)),
        el("div", { class: "strong" }, cell.text),
        chip(cell.who),
        scale ? exStrip(cell, scale) : null,
        ...cell.notes.map((t) => el("div", { class: "small weak" }, t))));
    });
    grid.append(el("div", { class: "ex-cell", style: at(3 + j.sides.length, col) }, lab("Exposure comp."),
      el("div", { class: "strong" }, c.comp.text),
      el("div", { class: "small weak" }, c.comp.note)));
    grid.append(el("div", { class: "ex-cell", style: at(4 + j.sides.length, col) }, lab("Exposes for"),
      c.exposes ? el("div", { title: c.exposes_hover }, c.exposes) : el("div", { class: "small weak" }, "the camera meters the scene")));
  });
  const decides = j.decides.map((d) => {
    const det = el("details", { class: "grp ex", open: exOpen.has(d.side) },
      el("summary", {}, `What decides ${d.name}`),
      el("div", { class: "ex-decides" },
        el("div", { class: "small" }, d.effect),
        ...d.settings.map((s) => el("div", { class: "ex-set" },
          el("span", {}, s.name),
          el("span", { class: "small weak" }, `${s.tab} > ${s.group}`),
          // the proof only while Settings shows the proof lines (null otherwise)
          typeof s.proved === "boolean" ? el("span", { class: "small " + (s.proved ? "ex-proved" : "weak") }, s.proved ? "proved on the camera" : "not proved on the camera yet") : null,
          el("button", { class: "small", onclick: () => exShowInMenu(s) }, "Show in menu")))));
    det.addEventListener("toggle", () => { if (det.open) exOpen.add(d.side); else exOpen.delete(d.side); });
    return det;
  });
  return [el("div", { class: "head" }, el("h1", {}, j.title)),
    el("p", { class: "small weak" }, j.intro),
    el("div", { class: "scrollx ex-wrap" }, grid),
    el("div", { class: "ex-whats" }, ...decides)];
}

// --- My Menu ---

/** A My Menu request, its answer's words (`message`: what moved where) said in the toast. */
async function actAndSay(name, body) {
  const j = await act(name, body);
  if (j && j.message) toast(j.message);
  return j;
}

/** My Menu for a row, as the window's right-click menu: where it is and Remove, or Add, or why it cannot be; My Menu
 *  by the camera's name for it (`my_menu`). */
function myMenuItems(r, done = () => {}) {
  const editable = !!(state.file && state.file.editable);
  const name = (state.my_menu && state.my_menu.name) || "My Menu";
  const go = (add) => () => {
    done();
    actAndSay("mymenu", { key: r.key, add });
  };
  if (!r.menu_code) return [el("span", { title: r.mymenu_why }, el("button", { class: "small", disabled: true }, `Add to ${name}`))];
  if (r.mymenu) {
    return [el("span", { class: "weak" }, `In ${name}: page ${r.mymenu.page}, item ${r.mymenu.item}`),
      el("button", { class: "small", disabled: !editable, onclick: go(false) }, `Remove from ${name}`)];
  }
  return [el("button", { class: "small", disabled: !editable, onclick: go(true) }, `Add to ${name}`)];
}

/** The My Menu page, as the window's: each page's places in order, an item by the camera's name for it, as a link
 *  that opens the setting it opens (with that setting's value), Remove and Move up / Move down; then the settings of
 *  My Menu's own tab by group, as rows. Always the live settings, which a note says while a memory is edited. */
function drawMyMenu(j) {
  const out = [el("div", { class: "head" }, el("h1", {}, j.name))];
  if (j.memory) out.push(el("p", {}, j.memory));
  if (!j.pages) out.push(el("p", {}, j.missing));
  else {
    out.push(el("p", { class: "small weak" }, j.lead));
    j.pages.forEach((pg, p) => out.push(el("div", { class: "strong mm-page" }, `${pg.name}  (${pg.held})`),
      el("div", { class: "scrollx" }, el("table", { class: "egrid mm" }, el("tbody", {}, ...pg.places.map((x, i) => myMenuPlace(j, p, i, x)))))));
  }
  if (j.groups.length) out.push(...drawGroups(j.groups, "mymenu", false));
  return out;
}

/** One place of a My Menu page: its number, its item (edited in the edit colour, what it held on hover), the value
 *  of the setting it opens, and its buttons; an empty place says so. */
function myMenuPlace(j, p, i, x) {
  const was = x.edited ? `\nWas: ${x.was}` : "";
  const mark = x.edited ? "✏ " : "";
  const tr = el("tr", { class: x.edited ? "mm-edited" : null }, el("td", { class: "weak" }, String(i + 1)));
  const pick = (e) => showMyMenuPicker(j, p, i, x, e.currentTarget);
  if (x.empty) {
    tr.append(el("td", { class: "mm-item weak", colspan: "2", title: `An empty place${was}` }, el("i", {}, mark + x.name)),
      el("td", { class: "mm-do" }, x.pick ? el("button", { class: "small", disabled: !j.editable,
        title: `Add an item to this page of ${j.name}: it goes after the page's items, as on the camera`, onclick: pick }, "Add here…") : null));
    return tr;
  }
  const name = x.opens
    ? el("a", { href: "#", title: `Click to open ${x.opens.name} in its menu (${x.opens.where})${was}`, onclick: (e) => { e.preventDefault(); openSetting(x.opens); } }, mark + x.name)
    : el("span", { title: `No setting the editor knows belongs to this item, so it has no value to show${was}` }, mark + x.name);
  const more = x.more.length ? el("span", { class: "small weak", title: `The item holds these settings too:\n${x.more.join("\n")}` }, `  and ${x.more.length} more`) : null;
  const go = (what) => () => actAndSay("mymenu_slot", { page: p, item: i, code: x.code, do: what });
  tr.append(el("td", { class: "mm-item" }, name, more),
    el("td", { class: x.opens && !x.opens.held ? "weak" : null }, x.opens ? x.opens.value : ""),
    el("td", { class: "mm-do" },
      el("button", { class: "small", disabled: !j.editable, title: `Put another item in place of ${x.name}: any item ${j.name} can hold, not only the settings shown in the menus`, onclick: pick }, "Change…"),
      el("button", { class: "small", disabled: !j.editable, title: `Take ${x.name} out of ${j.name}`, onclick: go("remove") }, "Remove"),
      el("button", { class: "small", disabled: !j.editable || !x.up, title: "Move up", "aria-label": "Move up", onclick: go("up") }, plain("⬆")),
      el("button", { class: "small", disabled: !j.editable || !x.down, title: "Move down", "aria-label": "Move down", onclick: go("down") }, plain("⬇"))));
  return tr;
}

/** The item picker of place `i` of page `p` (`x`), as the window's: every item a place can hold (`j.items`), narrowed
 *  by the words typed into its filter box, each with the tab of the setting that carries it, the items already in
 *  My Menu greyed out with where they are, and what the camera keeps out; a click puts the item there
 *  (`mymenu_slot` "set"). In the My Menu pop-up, under the button that opened it. */
function showMyMenuPicker(j, p, i, x, button) {
  const list = el("div", { class: "mm-pick-list", role: "listbox", "aria-label": `Items for ${j.name} ${p + 1}, place ${i + 1}` });
  const choose = (code) => () => {
    hideMyMenu(true);
    actAndSay("mymenu_slot", { page: p, item: i, code: x.code, do: "set", to: code });
  };
  const fill = (q) => {
    q = q.trim().toLowerCase();
    const shown = j.items.filter((it) => !q || it.name.toLowerCase().includes(q) || (it.tab || "").toLowerCase().includes(q));
    list.replaceChildren(...shown.map((it) => el("button", { class: "small mm-pick", role: "option", disabled: !!it.in, onclick: choose(it.code),
      title: it.in ? `Already in ${j.name} ${it.in.page}, item ${it.in.item}` : null },
      it.name, it.in ? el("span", { class: "weak" }, `   (in ${j.name} ${it.in.page}, item ${it.in.item})`) : it.tab ? el("span", { class: "weak" }, `   (${it.tab})`) : null)));
    if (!shown.length) list.append(el("span", { class: "weak" }, "No item matches."));
  };
  const filter = el("input", { type: "search", placeholder: "Type to filter the items", "aria-label": "Filter the items", oninput: (e) => fill(e.target.value) });
  fill("");
  const at = button.getBoundingClientRect();
  showMyMenuPopup(`Items for ${j.name} ${p + 1}, place ${i + 1}`,
    [el("div", { class: "strong" }, x.empty ? `Add to ${j.name} ${p + 1}` : `In place of ${x.name}`), filter, j.excluded ? el("div", { class: "small weak" }, j.excluded) : null, list],
    at.left, at.bottom + 2, button);
  filter.focus();
}

/** A row's My Menu items in the pop-up, as the window's right-click menu (or the keyboard's context-menu key) has
 *  them, the focus on the first that can be used. */
function showMyMenu(r, x, y) {
  const from = document.activeElement;
  const name = (state.my_menu && state.my_menu.name) || "My Menu";
  showMyMenuPopup(`${name}: ${r.name}`, myMenuItems(r, () => hideMyMenu(true)), x, y, from);
  const first = $("mymenu").querySelector("button:not(:disabled)");
  if (first) first.focus({ preventScroll: true });
}

/** The control the My Menu pop-up was opened from, to give the focus back to, and where it was opened (to place it
 *  again when the window's size changes). */
let myMenuFrom = null;
let myMenuAt = null;

/** The My Menu pop-up (a row's items, or a place's item picker) at (x, y), named for a screen reader by `label`; it
 *  stays until a choice, a tap elsewhere or Escape. */
function showMyMenuPopup(label, kids, x, y, from) {
  const pop = $("mymenu");
  pop.setAttribute("aria-label", label);
  pop.replaceChildren(...kids.filter(Boolean));
  pop.hidden = false;
  placeAt(pop, x, y);
  myMenuFrom = from || null;
  myMenuAt = { x, y };
}

/** The My Menu pop-up closed; `focusBack`: the focus goes back where it was opened from (Escape, a choice). */
function hideMyMenu(focusBack) {
  const pop = $("mymenu");
  if (pop.hidden) return;
  pop.hidden = true;
  if (focusBack && myMenuFrom && document.contains(myMenuFrom)) myMenuFrom.focus({ preventScroll: true });
  myMenuFrom = null;
}

// --- the Expert pages: Unmapped records and the Record map; a search filters them, as in the window ---

function drawUnmapped(j) {
  const desk = deskOnly("allow_raw_edits");
  const allow = el("input", { type: "checkbox", disabled: desk, title: desk ? "Set in the desktop app" : undefined });
  allow.checked = !!j.allow_raw_edits;
  allow.addEventListener("change", () => act("prefs", { name: "allow_raw_edits", value: allow.checked }));
  const value = (r) => {
    if (!j.editable || r.int === null) return el("span", { class: "mono" + (r.changed ? " edit" : "") }, r.value);
    const input = el("input", { type: "number", step: 1, value: String(r.int), "aria-label": r.hex, class: r.changed ? "edit" : undefined });
    input.addEventListener("change", () => {
      const typed = input.value.trim(), v = Number(typed);
      // a box emptied, or holding no whole number, shows the value again: nothing is written (Number("") is 0)
      if (typed === "" || !Number.isInteger(v)) { input.value = String(r.int); return; }
      if (v === r.int) return;
      // the box may keep the keyboard, so the page is not drawn again under it: the value it compares with is brought
      // up to date at once, and the page drawn anew once the editor has taken it (the edit mark), the focus kept
      act("raw_set", { target: view.target, id: r.id, value: v }, null, { done: () => { r.int = v; }, undo: redraw }).then((done) => {
        // drawn anew only while the box still has the keyboard and holds what was sent (else `act`'s own poll has drawn
        // the page, or digits typed meanwhile would be wiped)
        if (done && document.activeElement === input && input.value === String(v)) redraw();
      });
    });
    return el("div", { class: "drag" }, input);
  };
  return [
    el("div", { class: "head" }, el("h1", {}, "Unmapped records")),
    el("div", { class: "head" }, el("label", { class: "check" }, allow, "Allow raw edits", desk ? el("span", { class: "small weak" }, " (set in the desktop app)") : null),
      el("span", { class: "um-warn" }, "Raw values have unknown meaning. The camera may reject or misread them; test edited files one change at a time.")),
    el("hr"),
    el("div", { class: "scrollx" }, el("table", { class: "egrid" },
      el("thead", {}, el("tr", {}, el("th", {}, "Record"), el("th", {}, "Shape"), el("th", {}, "Value"))),
      el("tbody", {}, ...j.rows.map((r) => el("tr", {}, el("td", { class: "mono" }, r.hex), el("td", {}, r.shape), el("td", {}, value(r))))))),
  ];
}

function drawRecords(j) {
  const filter = (key, label, title) => {
    const b = el("input", { type: "checkbox" });
    b.checked = xp.rm[key];
    b.addEventListener("change", () => { xp.rm[key] = b.checked; redraw(); });
    return el("label", { class: "check", title }, b, label);
  };
  const head = el("div", { class: "head" }, el("h1", {}, j.title), el("span", { class: "vsep" }),
    filter("unmapped", "Only unmapped"), filter("edited", "Only edited", "Records whose value differs from the file as it was opened"),
    el("span", { class: "small weak" }, "Search matches record ids (0x1234), setting names and values. Click a setting to open it; click the shape of a multi-byte record for its bytes."));
  if (!j.rows.length) return [head, el("hr"), el("p", {}, "No records match.")];
  const row = (r) => {
    const open = r.big && xp.rm.open.has(r.id);
    const toggle = () => { if (open) xp.rm.open.delete(r.id); else xp.rm.open.add(r.id); redraw(); };
    return el("tr", { class: r.edited ? "rm-edited" : !r.setting ? "rm-unmapped" : undefined },
      el("td", {}, r.offset), el("td", {}, r.hex),
      r.big ? pressable(el("td", { class: "rm-shape big", "aria-expanded": String(open), title: "Click to show the bytes" }, `${r.shape} ${open ? "▾" : "▸"}`), toggle)
        : el("td", {}, r.shape),
      r.setting
        ? pressable(el("td", { class: "rm-setting", title: `${r.setting.tab} > ${r.setting.group}\n${r.setting.note}` }, r.setting.title), () => openSetting(r.setting))
        : el("td", { class: "rm-setting rm-unmapped" }, "— unmapped —"),
      open && r.bytes ? el("td", {}, el("pre", { class: "rm-dump" }, r.bytes.dump)) : el("td", {}, r.value),
      el("td", { title: r.raw_full }, r.raw));
  };
  return [head, el("hr"), el("div", { class: "scrollx" }, el("table", { class: "egrid rm" },
    el("thead", {}, el("tr", {}, ...["Offset", "Record", "Shape", "Setting", "Value", "Raw"].map((h) => el("th", {}, h)))),
    el("tbody", {}, ...j.rows.map(row))))];
}

// --- Compare ---

// The Compare mode, as the window's: file A beside file B and a base file, any of their sets as
// columns (the first is the baseline), the rows that differ highlighted, arrows and menus that put a
// value into file A, the three-way tags and merge, a difference cursor and the change map. The
// columns, filters, folds and cursor are the page's own; every copy is an edit of the open file.

let cmpWatcher = null;      // what watches which rows are on screen, for the change map's frame
const cmpSeen = new Set();  // the rows on screen, by index

/** "Only rows that differ" and "Show raw values": the page's choice, else the window's. */
function cmpOnly() {
  return cmp.only ?? !!(state && state.compare && state.compare.only_diff_default);
}
function cmpRaw() {
  return cmp.raw ?? !!(state && state.compare && state.compare.show_raw);
}

/** What the compare asks the editor for: the page's columns, search, tab and filters. */
function cmpBody() {
  return { cols: cmp.cols || [], q: cmp.q, tab: cmp.tab || null, only_diff: cmpOnly(), raw: cmpRaw(), three: cmp.three, keep: cmp.kept };
}

/** The compare drawn from the editor's answer: the cursor kept on a row still shown; back from Edit ("← Back to
 *  Compare"), the row the setting was opened from opened, under the cursor and in view; the picker open kept on its
 *  cell, showing the setting as it is now (after a change, a Revert or an undo). */
function drawCompareAnswer(j) {
  cmp.last = j;
  if (cmp.cursor !== null && cmp.cursor >= j.rows.length) cmp.cursor = null;
  if (cmp.goKey !== null) {
    const i = j.rows.findIndex((r) => r.key === cmp.goKey);
    cmp.goKey = null;
    if (i >= 0) {
      const r = j.rows[i];
      for (const k of foldKeys(r)) cmp.folded.delete(k);
      cmp.cursor = i;
      requestAnimationFrame(() => cmpJump(i));
    }
  }
  if (cmp.pick) cmpPickRefresh();
  return drawCompare();
}

/** The Compare mode's part of the frame (called first in render): the mode switch, which bar shows,
 *  the page's columns kept in step with the open files, and the Compare bar. */
function cmpRender(s, f) {
  const on = view.mode === "compare";
  $("app").classList.toggle("compare", on);
  $("bar-compare").hidden = !on;
  $("b-edit").classList.toggle("on", !on);
  $("b-edit").setAttribute("aria-pressed", String(!on));
  $("b-compare").classList.toggle("on", on);
  $("b-compare").setAttribute("aria-pressed", String(on));
  cmpSync(s);
  if (on) view.page = cmp.records ? "compare_records" : "compare";
  else if (view.page === "compare" || view.page === "compare_records") view.page = "main";
  if (!on) return;
  drawCompareBar(s, f);
  if (!f) cmpMap(null);
  cmpPlaceMap();
}

/** The page's columns follow the files as the window's do: file B opened (from this page, the window
 *  or another page) starts "A against B" in the set the page edits, the base first when one is open
 *  (`open_compare`); a base opened becomes the baseline (`open_base`); a file closed, or a set no
 *  longer shown, takes its columns with it (`prune_cols`). */
function cmpSync(s) {
  const c = s.compare || { b: null, base: null, cols: [] };
  const files = { a: s.file ? s.file.name : null, b: c.b ? c.b.name : null, base: c.base ? c.base.name : null };
  const was = cmp.files, t = view.target;
  if (cmp.cols === null || !was) {
    cmp.cols = (c.cols || []).map((x) => x.slice());
  } else if (files.b && files.b !== was.b) {
    cmp.cols = files.base ? [["base", t], ["a", t], ["b", t]] : [["a", t], ["b", t]];
    cmp.only = null;
    cmp.cursor = null;
  } else if (files.base && files.base !== was.base) {
    const sec = cmp.cols.length ? cmp.cols[0][1] : t;
    cmp.cols = [["base", sec], ...cmp.cols.filter(([src]) => src !== "base")];
    if (!cmp.cols.some(([src]) => src === "a")) cmp.cols.push(["a", sec]);
    if (files.b && !cmp.cols.some(([src]) => src === "b")) cmp.cols.push(["b", sec]);
    cmp.only = null;
    cmp.records = false;
    cmp.cursor = null;
  }
  if (was && was.base && !files.base) cmp.three = "all";
  cmp.files = files;
  const sets = new Set(s.targets.map(([i]) => i));
  cmp.cols = cmp.cols.filter(([src, sec]) => (src === "a" || !!files[src]) && sets.has(sec));
}

/** Edit or Compare, as the two buttons at the window's top left; Edit comes back to the page it left. */
function cmpSetMode(mode) {
  if (!state || view.mode === mode) return;
  cmpHideMenu();
  cmpPickClose();
  if (mode === "compare") {
    cmp.back = { page: view.page, q: view.q };
    clearSearch();
    view.mode = "compare";
  } else {
    view.mode = "edit";
    const b = cmp.back || { page: "main", q: "" };
    view.page = b.page;
    if (b.q) {
      view.q = b.q;
      $("search").value = b.q;
      $("b-clear").hidden = false;
    }
    cmp.back = null;
  }
  render();
}

/** The Compare bar: A, B and the base with their names and firmware badges (Open… on each), Swap A/B,
 *  Download A, Export CSV, the search, the tab and the switches, the line saying once which file
 *  each letter of the columns' names is, and the window's line when the files were saved under different video
 *  systems (`video_note`). */
function drawCompareBar(s, f) {
  const c = s.compare || { b: null, base: null, tabs: [] };
  const bar = $("bar-compare");
  const key = JSON.stringify([f && [f.name, f.model, f.saved, f.badge, f.edit_anyway_in_desktop], c.b, c.base, c.tabs, c.video_note]);
  if (bar.dataset.key !== key) {
    bar.dataset.key = key;
    const none = () => el("span", { class: "weak" }, "none");
    // a badge and its Describe for support… name their file to a screen reader, as A, B and the base each have one
    const who = { a: "file A", b: "file B", base: "the base file" };
    const badge = (b, src) => (!b ? [] : [firmwareBadge(b, who[src]), b.kind === "ok" ? null : describeButton(src, who[src])]);
    const file = (x, src) => (x ? [el("strong", { class: "cmp-src-" + src, title: `${x.model} · saved ${x.saved}` }, x.name), ...badge(x.badge, src)] : [none()]);
    $("cmp-a").replaceChildren(...(f
      ? [el("strong", { class: "cmp-src-a", title: `${f.model}${f.saved ? " · saved " + f.saved : ""}` }, f.name), ...badge(f.badge, "a"),
        f.edit_anyway_in_desktop ? editAnywayInDesktop() : null]
      : [none()]).filter(Boolean));
    $("cmp-b").replaceChildren(...file(c.b, "b").filter(Boolean));
    $("cmp-base").replaceChildren(...file(c.base, "base").filter(Boolean));
    for (const e of bar.querySelectorAll(".cmp-base")) e.hidden = !c.b;
    $("b-close-base").hidden = !c.base;
    const tabs = c.tabs || [];
    if (cmp.tab && !tabs.includes(cmp.tab)) cmp.tab = "";
    $("cmp-tab").replaceChildren(el("option", { value: "" }, "All tabs"), ...tabs.map((t) => el("option", { value: t }, t)));
    $("cmp-tab").value = cmp.tab;
    const letters = !(c.b || c.base) ? [] : [
      f ? el("span", { class: "cmp-src-a" }, `A = ${f.name} (the file you edit)`) : null,
      c.b ? el("span", { class: "cmp-src-b" }, `B = ${c.b.name}`) : null,
      c.base ? el("span", { class: "cmp-src-base" }, `Base = ${c.base.name}`) : null,
      c.video_note ? el("span", { class: "small warn" }, c.video_note) : null].filter(Boolean);
    $("cmp-letters").replaceChildren(...letters);
    $("cmp-letters").hidden = !letters.length;
  }
  $("b-swap").hidden = !(c.b && f);
  // greyed out, each stays in the Tab order and says why when pressed (`greyOut`)
  greyOut($("b-swap"), s.edits ? "Swap A/B opens both files again, so A's edits would be lost: download file A or revert its edits first." : "");
  greyOut($("b-download-a"), f ? "" : "Open file A first: there is nothing to download yet.");
  greyOut($("b-csv-cmp"), !f ? "Open file A first: there is nothing to export yet."
    : (cmp.cols || []).length < 2 ? "Pick at least two columns first: the export is the comparison as shown." : "");
  $("cmp-only").checked = cmpOnly();
  $("cmp-raw").checked = cmpRaw();
  // the record map for mapping work: Expert mode only, as the Menu's
  const expert = !!(s.prefs && s.prefs.expert);
  if (!expert && cmp.records) { cmp.records = false; if (view.page === "compare_records") view.page = "compare"; }
  $("cmp-records").checked = cmp.records;
  const recBox = $("cmp-records").closest("label");
  if (recBox) recBox.hidden = !expert;
  // the stored numbers likewise, as the window shows that switch in Expert mode only
  const rawBox = $("cmp-raw").closest("label");
  if (rawBox) rawBox.hidden = !expert;
}

/** The column picker (the window's `column_picker`): a row per open file, a toggle per set, named with its file's
 *  letter to a screen reader ("B Live"), as each file's row has the same sets. */
function cmpPicker(j) {
  const c = state.compare || {};
  const f = state.file;
  const files = [["a", "A", f && f.name], ["b", "B", c.b && c.b.name], ["base", "Base", c.base && c.base.name]].filter(([src, , name]) => src === "a" || name);
  return el("div", {}, ...files.map(([src, letter, name]) => el("div", { class: "cmp-pick" },
    el("strong", { class: "cmp-src-" + src }, `${letter} ${name || ""}:`),
    ...j.sections.map(([sec, short, long]) => {
      const on = (cmp.cols || []).some((x) => x[0] === src && x[1] === sec);
      return el("button", { class: "sel" + (on ? " on" : ""), title: long, "aria-label": `${letter} ${short}`, "aria-pressed": String(on), "data-col": `${src}:${sec}`, onclick: () => {
        cmp.cols = on ? cmp.cols.filter((x) => !(x[0] === src && x[1] === sec)) : [...cmp.cols, [src, sec]];
        cmp.cursor = null;
        maybeDraw();
      } }, short);
    }))));
}

/** The rows the difference cursor steps over: the rows shown that differ from the baseline. */
function cmpDiffRows() {
  const out = [];
  ((cmp.last && cmp.last.rows) || []).forEach((r, i) => { if (r.differs) out.push(i); });
  return out;
}

/** The keys a row's tab and group are folded under in `cmp.folded`. */
function foldKeys(r) {
  return ["t\u0000" + r.tab, "g\u0000" + r.tab + "\u0000" + r.group];
}

/** The lock beside the name of a column of file B or the base, which never take a value. */
function cmpLock(c) {
  return c.editable ? null : el("span", { class: "small weak", title: "This file is never changed; values only go into A" }, " 🔒");
}

/** Where the difference cursor is, in words: "difference 3 of 12", or how many there are. */
function cmpAtText() {
  const rows = cmpDiffRows();
  const at = cmp.cursor === null ? -1 : rows.indexOf(cmp.cursor);
  return at >= 0 ? `difference ${at + 1} of ${rows.length}` : `${rows.length} differences`;
}

/** The compare page (the window's `matrix_view`). */
function drawCompare() {
  const j = cmp.last;
  const out = [cmpPicker(j),
    el("p", { class: "small weak" }, "The first column is the baseline; cells that differ from it are highlighted. The small arrows between columns put a value into the column they point at (only the open file, A, takes values); a click on a value of A changes it; a click on a column header opens its menu (← and → move between the headers); right-click a cell for more (on a phone, touch and hold it).")];
  // one click to recall a memory into the live settings of file A, or to register the live settings into a memory
  if (j.editable && j.dial.length) {
    const filter = cmp.q || cmp.tab ? { q: cmp.q, tab: cmp.tab || null } : null;
    // in the window's words
    out.push(el("div", { class: "cmp-tools" }, el("strong", {}, "Whole sets:"), ...j.whole_sets.flatMap((b) => wholeSetButtons(b, filter)),
      filter ? onlyShownBox() : null));
  }
  out.push(el("hr"));
  if (j.cols.length < 2) {
    cmpMap(null);
    out.push(el("p", {}, "Pick at least two columns."));
    return out;
  }
  if (j.three) out.push(cmpThree(j));
  const diffs = cmpDiffRows().length;
  // with no difference, Previous and Next stay in the Tab order and say so when pressed (`offButton`)
  const none = diffs ? "" : "No row shown differs from the baseline: there is no difference to step to.";
  out.push(el("div", { class: "cmp-tools" },
    el("span", {}, `${j.shown} of ${j.total} settings shown`),
    el("button", { title: "Fold every tab; click a tab or group heading to open it", onclick: () => { for (const r of j.rows) cmp.folded.add(foldKeys(r)[0]); redrawCompare(); } }, "Collapse all"),
    el("button", { onclick: () => { cmp.folded.clear(); redrawCompare(); } }, "Expand all"),
    el("span", { class: "vsep" }),
    offButton({ title: "Previous difference (Shift+F3 or Alt+Up)", "aria-label": "Previous difference", "aria-keyshortcuts": "Shift+F3 Alt+ArrowUp", "data-ctl": "cmp-prev" },
      "⏶ Previous", () => cmpStep(-1), none),
    offButton({ title: "Next difference (F3 or Alt+Down)", "aria-label": "Next difference", "aria-keyshortcuts": "F3 Alt+ArrowDown", "data-ctl": "cmp-next" },
      "⏷ Next", () => cmpStep(1), none),
    el("span", { id: "cmp-at" }, cmpAtText())));
  const { table, marks } = cmpTable(j);
  out.push(el("div", { class: "cmp-scroll" }, table));
  cmpMap(marks);
  cmpWatch(table);
  return out;
}

/** The three-way line: the counts, the filter, and the merge buttons (the window's, over the same rows). */
function cmpThree(j) {
  const t = j.three;
  const merge = (kind) => act("merge", { base: t.cols[0], a: t.cols[1], b: t.cols[2], kind, q: cmp.q, tab: cmp.tab || null });
  // drawn at once, though the list keeps the focus (`maybeDraw` waits while a list of the page has it, for a row's list
  // open under the hand); the focus stays on it (`drawContent`)
  const sel = el("select", { "aria-label": "Rows of the three-way compare", onchange: () => { cmp.three = sel.value; cmp.cursor = null; cmp.kept = null; drawContent(contentKey()); } },
    ...t.filters.map(([w, label]) => el("option", { value: w }, label)));
  sel.value = cmp.three;
  // a merge with nothing to take stays in the Tab order and says so when pressed (`offButton`); each is named by its
  // part (`data-ctl`), as its words hold a count, so the compare drawn anew after it keeps the keyboard on it
  const noConflict = t.conflict ? "" : "No setting was changed differently in A and B: there is no conflict to settle.";
  return el("div", { class: "cmp-tools" },
    el("strong", { class: "cmp-src-base" }, "Three-way:"),
    el("span", { title: t.against }, `${t.a} changed in A, ${t.b} in B, ${t.both} the same change, ${t.conflict} conflicts`),
    el("span", { class: "combo narrow" }, sel),
    ...(j.editable ? [
      offButton({ title: "Take every change B made where A kept the base value. Conflicts are left alone.", "data-ctl": "cmp-merge-b" }, `Merge B into A (${t.b})`, () => merge("b_into_a"),
        t.b ? "" : "B made no change where A kept the base value: there is nothing to merge."),
      offButton({ title: "Where A and B changed a setting differently, use B's value", "data-ctl": "cmp-conflicts-b" }, "Conflicts: take B", () => merge("conflicts_b"), noConflict),
      offButton({ title: "Where A and B changed a setting differently, go back to the base value", "data-ctl": "cmp-conflicts-base" }, "Conflicts: take Base",
        () => merge("conflicts_base"), noConflict)] : []));
}

/** The header row's key (`data-key`), which no setting has. */
const CMP_HEAD = "(columns)";

/** What names a compare column whatever its place: its file and its set. */
const cmpColId = (c) => `${c.src}:${c.section}`;

/** The place of the column header holding the header row's Tab stop (`cmp.head`): its column's, else, its column
 *  removed, the header now in its place, else the first. */
function cmpHeadAt(cols) {
  const h = cmp.head;
  if (!h || !cols.length) return 0;
  const i = cols.findIndex((c) => cmpColId(c) === h.col);
  return i >= 0 ? i : Math.max(0, Math.min(h.i, cols.length - 1));
}

/** The matrix: a header with each column's name, its lock (B and Base) and how many rows differ (`cmpHead`); then
 *  per tab and group a heading that folds, with its counts, and a row per setting shown. Also each
 *  row's mark for the change map, folded rows included. */
function cmpTable(j) {
  const cols = j.cols;
  const span = String((j.three ? 2 : 1) + 2 * cols.length - 1);
  const at = cmpHeadAt(cols);
  if (cmp.head) cmp.head = { col: cmpColId(cols[at]), i: at };
  // the header row's key and its Tab stop's `data-ctl` let the focus be found again on the same column's header once
  // the compare is drawn anew (`focusMark`), whatever its words (its count of differences) became
  const head = el("tr", { "data-key": CMP_HEAD },
    el("th", { class: "cmp-name" }, "Setting"),
    j.three ? el("th", { title: "A: changed in A only; B: changed in B only; A=B: the same change; !: conflict" }, "3-way") : null,
    ...cols.flatMap((c, i) => [
      i > 0 ? el("th", { class: "cmp-gap" }) : null,
      el("th", { class: "cmp-col", "data-c": String(i) }, cmpHead(j, c, i, i === at))]));
  const tally = new Map();
  const add = (k, d) => { const t = tally.get(k) || [0, 0]; t[0] += 1; t[1] += d; tally.set(k, t); };
  for (const r of j.rows) {
    for (const k of foldKeys(r)) add(k, r.differs ? 1 : 0);
  }
  const heading = (cls, key, text, counts, color, what) => el("tr", { class: cls }, el("td", { colspan: span },
    el("span", { class: "cmp-fold", role: "button", tabindex: "0", "aria-expanded": String(!cmp.folded.has(key)), "data-fold": key, title: `Click to fold or open the ${what}`, style: { "--c": color } },
      `${cmp.folded.has(key) ? "⏵" : "⏷"} ${text}`),
    el("span", { class: "small weak" }, `   ${counts}`)));
  const body = [], marks = [];
  let lastTab = null, lastGroup = "";
  j.rows.forEach((r, i) => {
    const [tk, gk] = foldKeys(r);
    if (r.tab !== lastTab) {
      const [n, d] = tally.get(tk);
      body.push(heading("cmp-tabhead", tk, r.tab, `${n} settings · ${d} differ`, r.color, "tab"));
      lastTab = r.tab;
      lastGroup = "";
    }
    const tabClosed = cmp.folded.has(tk);
    if (!tabClosed && r.group !== lastGroup) {
      const [n, d] = tally.get(gk);
      body.push(heading("cmp-grouphead", gk, r.group, `${n} · ${d} differ`, r.color, "group"));
      lastGroup = r.group;
    }
    if (tabClosed || cmp.folded.has(gk)) {
      // a folded row is not drawn but keeps its mark, so the change map and the cursor still count it
      marks.push(r.mark === "conflict" ? "differs" : r.mark);
      return;
    }
    marks.push(r.mark);
    body.push(cmpRow(j, r, i));
  });
  const table = el("table", { class: "egrid cmp" }, el("thead", {}, head), el("tbody", {}, ...body));
  const fold = (e) => {
    const k = e.target.closest("[data-fold]");
    if (!k) return false;
    const key = k.dataset.fold, focused = document.activeElement === k;
    if (cmp.folded.has(key)) cmp.folded.delete(key); else cmp.folded.add(key);
    redrawCompare();
    if (focused) {
      const again = [...document.querySelectorAll("#content [data-fold]")].find((x) => x.dataset.fold === key);
      if (again) again.focus();
    }
    return true;
  };
  table.addEventListener("click", fold);
  table.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && fold(e)) e.preventDefault(); });
  cmpMenus(table, (target) => {
    const th = target.closest("th[data-c]");
    if (th) return cmpHeadMenu(j, Number(th.dataset.c));
    const td = target.closest("td[data-c]"), tr = target.closest("tr[data-i]");
    return td && tr ? cmpCellMenu(j, j.rows[Number(tr.dataset.i)], Number(td.dataset.c)) : [];
  });
  return { table, marks };
}

/** One setting's row: its name (the record on hover), its three-way tag, and per column its value,
 *  filled where it differs from the baseline or was edited, with the copy arrows between columns. */
function cmpRow(j, r, i) {
  const tag = r.three && j.three ? j.three.tags[r.three] : null;
  // the name is a link, as the window's: it opens the setting in Edit, in the first column of file A that keeps it
  const into = j.cols.find((c) => c.editable && (c.section === 0 || r.in_sets));
  const section = into ? into.section : 0;
  // where it is kept, in the editor's words (the record in Expert mode only)
  const link = el("span", { class: "cmp-link", title: `${r.where}\nClick to open it in Edit` }, r.name);
  // the setting's key and each cell's column (`data-ctl`) let the keyboard's place be found again once the compare is
  // drawn anew with the cell's new value (its words, which name the value, change)
  const tr = el("tr", { "data-i": String(i), "data-key": r.key, class: cmp.cursor === i ? "cmp-cursor" : null },
    el("td", { class: "cmp-name" }, pressable(link, () => cmpOpenInEdit(r, section))),
    j.three ? el("td", {}, tag ? el("span", { class: "cmp-tag " + r.three, title: tag[1] }, tag[0]) : null) : null);
  r.cells.forEach((c, ci) => {
    if (ci > 0) tr.append(cmpGap(j, r, ci));
    // the full text of a value cut short, and why a number has no name yet (`why`), on hover
    // an edit says what it was; a value of file A that can change says a click changes it (`editable`)
    const title = [c.text_full, c.why, c.was !== undefined ? `was ${c.was || "(empty)"}` : null, c.editable ? "Click to change this value; right-click for more" : null].filter(Boolean).join("\n\n") || null;
    const td = el("td", { class: "cmp-v" + (c.edited ? " edited" : c.differs ? " diff" : "") + (c.editable ? " take" : ""), "data-c": String(ci), "data-ctl": "c" + ci },
      el("span", { class: c.stored ? null : "weak", title }, c.text));
    if (c.editable) {
      pressable(td, () => cmpPick(j, r, ci, td));
      td.setAttribute("aria-label", `${r.name}, ${j.cols[ci].name}: ${c.text}. Change`);
    }
    tr.append(td);
  });
  return tr;
}

/** The narrow cell between two columns (the window's `gap_cell`): an arrow into each column of file A
 *  that can take the other column's value in this row; a column of A keeps the arrow's place when it
 *  gets none, so the arrows stay in line down the table. */
function cmpGap(j, r, ci) {
  const left = j.cols[ci - 1], right = j.cols[ci];
  const [intoL, intoR] = r.arrows[ci - 1];
  const td = el("td", { class: "cmp-gap" });
  for (const [slot, on, glyph, from, to] of [[left.editable, intoL, "◀︎", right, left], [right.editable, intoR, "▶︎", left, right]]) {
    if (!(j.editable && slot)) continue;
    const what = `Put the value from ${from.name} into ${to.name}`;
    td.append(on
      ? el("button", { class: "cmp-arrow", title: what, "aria-label": what, onclick: () => act("copy", { from: [from.src, from.section], to: [to.src, to.section], key: r.key }) }, glyph)
      : el("span", { class: "cmp-arrow" }));
  }
  return td;
}

/** A cell's menu: copy its value into each other shown column of file A (an arrow toward that
 *  column), or into all of them at once; Revert an edited value; nothing for a value not stored. */
function cmpCellMenu(j, r, ci) {
  const c = j.cols[ci], cell = r && r.cells[ci];
  if (!cell || !cell.stored) return [];
  // a value cut short in its cell, in full (a touch screen shows no hover text)
  const whole = cell.text_full && cell.text_full !== cell.text ? [cell.text_full, "-"] : [];
  // a set where the setting is view only outside Expert mode (`locked`, the editor's) takes no copy, as the window's menu offers none
  const targets = j.cols.filter((t) => t.editable && !(t.src === c.src && t.section === c.section) && (t.section === 0 || r.in_sets) && !(r.locked || []).includes(t.section));
  const canCopy = j.editable && targets.length > 0;
  // a column of file A also opens the setting in Edit, in that column's set
  const open = c.editable ? [[`Open in Edit: ${c.name}`, "Open this setting in Edit, in this column's set", () => cmpOpenInEdit(r, c.section)]] : [];
  // a value of file A that can change: the picker, as a click on the cell opens it
  if (cell.editable) {
    const td = document.querySelector(`#content tr[data-i="${j.rows.indexOf(r)}"] td[data-c="${ci}"]`);
    open.unshift(["Change…", "Choose another value here, as in Edit", () => cmpPick(j, r, ci, td)]);
  }
  if (!canCopy && j.editable && !cell.edited && !cell.put_back) return [...whole, ...open];
  const from = [c.src, c.section];
  const items = [...whole];
  if (canCopy) {
    items.push(`Copy ${r.name} from ${c.name}`);
    for (const t of targets) {
      const at = j.cols.findIndex((x) => x.src === t.src && x.section === t.section);
      items.push([`${at < ci ? "◀︎" : "▶︎"} ${t.name}`, `Put this value into ${t.name}`, () => act("copy", { from, to: [t.src, t.section], key: r.key })]);
    }
    if (targets.length > 1) {
      items.push([`All of A (${targets.length} columns)`, `Put this value into ${targets.map((t) => t.name).join(", ")}`,
        () => act("copy", { from, to: targets.map((t) => [t.src, t.section]), key: r.key })]);
    }
    items.push("-");
  }
  items.push(...open);
  if (cell.edited) items.push(["Revert", null, () => act("revert", { target: c.section, key: r.key })]);
  if (cell.put_back) items.push([cell.put_back, null, () => act("restore", { target: c.section, key: r.key })]);
  if (!j.editable) items.push("This firmware has not been checked yet; editing is off.");
  return items;
}

/** The compare's picker for a value of file A (a click on its cell, or its menu's "Change…"), as the window's: the
 *  setting as the page's rows draw it in that column's set (`compare_cell`), with the same control (its values, those no
 *  checked on the camera only when asked for, the refused ones marked, the option tree's main option and choice, a
 *  number or a text), what it was and Revert, under the cell. A change goes through the same "set" (with the cell's
 *  column), so linked records, edit marks, undo and the write check follow as from Edit. File B's cells have none. */
async function cmpPick(j, r, ci, td) {
  const c = j.cols[ci], cell = r.cells[ci];
  cmpHideMenu();
  if (!c || !c.editable || !cell || !cell.editable) return;
  const was = cmp.pick;
  cmpPickClose();
  if (was && was.key === r.key && was.col[1] === c.section) return;          // a second click closes it
  const rect = td ? td.getBoundingClientRect() : { left: 8, bottom: 80 };
  const box = el("div", { class: "cmp-picker", role: "dialog", "aria-label": `${r.name}, ${c.name}` });
  document.body.append(box);
  // under the cell, moved in where it would run off the screen once its contents are drawn (`cmpPickRefresh`); opened
  // from the keyboard (Enter on the cell, or the cell menu's Change… chosen with the keys), it takes the focus, which
  // goes back to the cell when it closes
  cmp.pick = { box, key: r.key, col: [c.src, c.section], name: c.name, x: rect.left, y: rect.bottom + 2, keys: keyboardFocus(), from: td, focused: false };
  placeAt(box, cmp.pick.x, cmp.pick.y);
  // its row stays shown while it is changed or reverted here, even once it no longer differs
  cmp.kept = r.key;
  await cmpPickRefresh();
}

/** The picker drawn again from the setting as it is now; closed when the editor no longer offers it. */
async function cmpPickRefresh() {
  const p = cmp.pick;
  if (!p) return;
  let j;
  try {
    j = await api("compare_cell", { target: p.col[1], key: p.key });
  } catch (e) {
    if (e instanceof CodeError) { lostAccess(e); return; }
    cmpPickClose();
    failed(e);
    return;
  }
  if (cmp.pick !== p || !j || !j.row) return;
  const mark = focusMark(p.box);
  const row = drawRow({ ...j.row, col: p.col });
  // why a value is not in the choice, as the window's in-place choice says it: the values held back (hidden_words, in
  // Expert mode) and those the menus never offer (not_offered_lines)
  const held = state.prefs && state.prefs.expert && j.row.hidden_words ? [el("div", { class: "small weak" }, j.row.hidden_words)] : [];
  const why = [...held, ...(j.row.not_offered || []).map((n) => el("div", { class: "small note", title: n.title || undefined }, n.text))];
  p.box.replaceChildren(el("div", { class: "small weak" }, p.name), row, ...why);
  placeAt(p.box, p.x, p.y);
  if (mark) focusAgain(p.box, mark);
  else if (p.keys && !p.focused) {
    const first = p.box.querySelector('[data-ctl="value"]') || p.box.querySelector(FOCUSABLE);
    if (first) first.focus({ preventScroll: true });
  }
  p.focused = true;
}

/** The compare's picker closed; the focus, if it was in it, back on the cell it was opened from (when still shown). */
function cmpPickClose() {
  const p = cmp.pick;
  cmp.pick = null;
  if (!p) return;
  const inside = p.box.contains(document.activeElement);
  p.box.remove();
  if (inside && p.from && document.contains(p.from)) p.from.focus({ preventScroll: true });
}

/** A change from the picker: "set" with the cell's column (its row stays shown where it was: `kept`), and a choice
 *  from a plain list closes the picker as the window's final choice does (an option with a choice of its own, a
 *  number and a text keep it open, drawn again with the compare). */
function cmpPickSet(r, body) {
  const final = r.kind === "choice" && !r.tree;
  return act("set", { target: rowTarget(r), key: r.key, col: r.col, ...body }, null, {
    done: () => { if (final) cmpPickClose(); },
    undo: () => cmpPickRefresh(),
  });
}

/** A column header's menu: Make baseline, Remove column, and copy every row shown into a column of A. */
function cmpHeadMenu(j, i) {
  const c = j.cols[i];
  const same = (x) => x[0] === c.src && x[1] === c.section;
  const items = [];
  if (i > 0) {
    items.push(["Make baseline", null, () => {
      const k = cmp.cols.findIndex(same);
      if (k > 0) [cmp.cols[0], cmp.cols[k]] = [cmp.cols[k], cmp.cols[0]];
      cmp.cursor = null;
      maybeDraw();
    }]);
  }
  items.push(["Remove column", null, () => { cmp.cols = cmp.cols.filter((x) => !same(x)); cmp.cursor = null; maybeDraw(); }]);
  if (j.editable) {
    for (const t of j.cols.filter((col) => col.editable && !(col.src === c.src && col.section === c.section))) {
      items.push([`Copy all shown rows to ${t.name}`, null, () => act("copy_rows", { from: [c.src, c.section], to: [t.src, t.section], keys: j.rows.map((r) => r.key) })]);
    }
  }
  return items;
}

let cmpMenuBox = null;    // a cell's or a column header's menu, while it is open
let cmpMenuAt = 0;        // when it opened (a second right-click or hold right after does not open another)
let cmpMenuFrom = null;   // the control it was opened from, to give the focus back to

/** The menu closed; `focusBack`: the focus goes back where it was opened from (Escape, or an item chosen with the
 *  keyboard). A column header it was opened from says its menu is closed (`aria-expanded`). */
function cmpHideMenu(focusBack = false) {
  if (cmpMenuBox) cmpMenuBox.remove();
  cmpMenuBox = null;
  const from = cmpMenuFrom;
  cmpMenuFrom = null;
  if (from && from.getAttribute && from.getAttribute("aria-expanded") === "true") from.setAttribute("aria-expanded", "false");
  if (focusBack && from && document.contains(from)) from.focus({ preventScroll: true });
}

/** A menu at (x, y), as the window's right-click menu: [label, hover, action] items, plain lines
 *  (strings) and separators ("-"). Opened with a mouse or the keyboard, the focus moves to its first item; `from` is
 *  what it was opened from (a column header opened by a click, else what had the focus), which an item chosen with the
 *  keyboard gives the focus back to, so the compare drawn anew keeps it there (`drawContent`). */
function cmpShowMenu(x, y, items, touch, from = document.activeElement) {
  cmpHideMenu();
  while (items.length && items[items.length - 1] === "-") items.pop();
  if (!items.length) return;
  const box = el("div", { class: "cmp-menu", role: "menu" }, ...items.map((it) => (it === "-" ? el("hr")
    : typeof it === "string" ? el("div", { class: "small weak cmp-menu-label" }, it)
      : el("button", { role: "menuitem", title: it[1], onclick: () => { cmpHideMenu(keyboardFocus()); it[2](); }, onkeydown: heldKey }, plain(it[0])))));
  menuKeys(box, cmpHideMenu);
  document.body.append(box);
  placeAt(box, x, y);
  // the finger lifted after a touch and hold does not choose the item under it
  if (touch) {
    box.style.pointerEvents = "none";
    setTimeout(() => { box.style.pointerEvents = ""; }, 450);
  } else {
    const first = box.querySelector("button");
    if (first) first.focus({ preventScroll: true });
  }
  cmpMenuBox = box;
  cmpMenuAt = Date.now();
  cmpMenuFrom = from;
  if (from && from.getAttribute && from.getAttribute("aria-haspopup") === "menu") from.setAttribute("aria-expanded", "true");
}

/** The keyboard on a column header drawn no more (the columns cut down to one, so no header row): it goes to the
 *  column picker's toggle of that column, from where it is put back, else to the picker's first toggle. */
function cmpHeadGone(mark) {
  if (!mark || mark.key !== CMP_HEAD || $("content").contains(document.activeElement)) return;
  const toggles = [...$("content").querySelectorAll(".cmp-pick button")];
  const to = (cmp.head && toggles.find((b) => b.dataset.col === cmp.head.col)) || toggles[0];
  if (to) to.focus({ preventScroll: true });
}

/** A column's header: its name, its lock (B and Base) and how many rows differ, as a button that opens the column's
 *  menu (Make baseline, Remove column, Copy all shown rows), as a right-click or a touch and hold on it does too; its
 *  name to a screen reader says all three in words. The header row is one Tab stop (a roving tabindex: 0 on the
 *  header `cmp.head` names, -1 on the others), and the arrows move along it (`cmpHeadKey`). */
function cmpHead(j, c, i, on) {
  const count = i === 0 ? "baseline" : `${j.counts[i]} differ`;
  const b = el("button", { class: "cmp-head", tabindex: on ? "0" : "-1", "data-ctl": on ? "head" : null, "data-col": cmpColId(c),
    "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": `${c.name}${c.editable ? "" : ", never changed"}: ${count}` },
  el("span", { class: "cmp-src-" + c.src }, c.name), cmpLock(c), el("span", { class: "small weak cmp-count" }, count));
  b.addEventListener("click", () => cmpHeadOpen(j, i, b));
  b.addEventListener("keydown", (e) => cmpHeadKey(e, b));
  // a header that takes the focus any other way (a right-click, a screen reader's cursor) takes the stop with it, so
  // the compare drawn anew finds it again
  b.addEventListener("focus", () => cmpHeadStop(b));
  return b;
}

/** A column header's keys: ← and → move to the header beside it (stopping at either end), Home and End to the first
 *  and the last; the header moved to takes the row's Tab stop. Enter and Space are the button's own: they click it,
 *  as on every button of the page (Space on its release), which opens its menu. */
function cmpHeadKey(e, b) {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const all = [...b.closest("tr").querySelectorAll("button.cmp-head")];
  const i = all.indexOf(b);
  const to = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: all.length - 1 }[e.key];
  if (to === undefined) return;
  e.preventDefault();
  const next = all[Math.max(0, Math.min(all.length - 1, to))];
  cmpHeadStop(next);
  next.focus();
}

/** The header row's Tab stop on header `b`, and kept for its column (`cmp.head`) through the compare drawn anew. */
function cmpHeadStop(b) {
  for (const x of b.closest("tr").querySelectorAll("button.cmp-head")) {
    x.setAttribute("tabindex", x === b ? "0" : "-1");
    if (x === b) x.dataset.ctl = "head";
    else x.removeAttribute("data-ctl");
  }
  cmp.head = { col: b.dataset.col, i: Number(b.closest("th").dataset.c) };
}

/** A column header's menu under it (a click, Enter or Space on it); a second click on the header closes it. */
function cmpHeadOpen(j, i, b) {
  // the finger lifted after a touch and hold, or a click right after the one that opened it, opens no other
  if (cmpMenuBox && Date.now() - cmpMenuAt < 700) return;
  if (cmpMenuBox && cmpMenuFrom === b) {
    cmpHideMenu(true);
    return;
  }
  cmpHeadStop(b);
  const r = b.getBoundingClientRect();
  cmpShowMenu(r.left, r.bottom + 2, cmpHeadMenu(j, i), false, b);
}

/** Enter or Space held down where a menu was opened (a column header) repeats onto the menu's first item, which takes
 *  the focus: a repeat chooses nothing. */
function heldKey(e) {
  if (e.repeat && (e.key === "Enter" || e.key === " ")) e.preventDefault();
}

/** Right-click, or touch and hold, in the matrix opens the menu `menuFor(target)` gives, if any. */
function cmpMenus(table, menuFor) {
  const recent = () => cmpMenuBox && Date.now() - cmpMenuAt < 700;
  table.addEventListener("contextmenu", (e) => {
    const items = menuFor(e.target);
    if (!items.length) return;
    e.preventDefault();
    if (!recent()) cmpShowMenu(e.clientX, e.clientY, items, false);
  });
  let hold = null;
  const cancel = () => { if (hold) clearTimeout(hold.timer); hold = null; };
  table.addEventListener("pointerdown", (e) => {
    cancel();
    if (e.pointerType !== "touch") return;
    const { clientX: x, clientY: y, target } = e;
    hold = { x, y, timer: setTimeout(() => {
      hold = null;
      const items = menuFor(target);
      if (items.length && !recent()) cmpShowMenu(x, y + 8, items, true);
    }, 500) };
  });
  table.addEventListener("pointermove", (e) => { if (hold && Math.hypot(e.clientX - hold.x, e.clientY - hold.y) > 10) cancel(); });
  table.addEventListener("pointerup", cancel);
  table.addEventListener("pointercancel", cancel);
}

/** The next (1) or previous (-1) difference from the cursor, round at either end (the window's F3). */
function cmpStep(d) {
  if (view.mode !== "compare" || cmp.records || !cmp.last) return;
  const rows = cmpDiffRows();
  if (!rows.length) return;
  const c = cmp.cursor;
  let pos;
  if (c === null) pos = d > 0 ? 0 : rows.length - 1;
  else if (d > 0) {
    pos = rows.findIndex((i) => i > c);
    if (pos < 0) pos = 0;
  } else {
    pos = rows.length - 1;
    while (pos >= 0 && rows[pos] >= c) pos -= 1;
    if (pos < 0) pos = rows.length - 1;
  }
  cmpJump(rows[pos]);
}

/** The cursor on row i: its tab and group opened, the row outlined and brought to the middle. */
function cmpJump(i) {
  const r = cmp.last && cmp.last.rows && cmp.last.rows[i];
  if (!r || cmp.records) return;
  const [tk, gk] = foldKeys(r);
  cmp.cursor = i;
  if (cmp.folded.has(tk) || cmp.folded.has(gk)) {
    cmp.folded.delete(tk);
    cmp.folded.delete(gk);
    redrawCompare();
  } else {
    for (const x of document.querySelectorAll("#content tr.cmp-cursor")) x.classList.remove("cmp-cursor");
    const tr = document.querySelector(`#content tr[data-i="${i}"]`);
    if (tr) tr.classList.add("cmp-cursor");
    const at = $("cmp-at");
    if (at) setText(at, cmpAtText());
    cmpMapCursor();
  }
  const tr = document.querySelector(`#content tr[data-i="${i}"]`);
  if (tr) tr.scrollIntoView({ block: "center", inline: "nearest" });
}

/** The compare drawn again from its last answer (a fold, the cursor), where it was scrolled to, the focus kept on the
 *  same control (`focusMark`: a column header, a cell, Next). */
function redrawCompare() {
  if (view.mode !== "compare" || cmp.records || !cmp.last) return;
  const keep = keepScroll();
  const mark = focusMark($("content"));
  $("content").replaceChildren(...drawCompare());
  keep();
  focusAgain($("content"), mark);
}

/** The change map at the right (the window's minimap): a mark per row, folded ones too, differences
 *  orange, edits brighter, conflicts red, the rows on screen framed and the cursor marked; null hides it. */
function cmpMap(marks) {
  const m = $("cmp-map");
  cmp.marks = marks || [];
  m.hidden = !marks;
  if (!marks) {
    if (cmpWatcher) cmpWatcher.disconnect();
    cmpSeen.clear();
    return;
  }
  const n = marks.length;
  const kids = [];
  marks.forEach((k, i) => {
    if (k !== "same") kids.push(el("i", { class: k, style: { top: `${(i / n) * 100}%`, height: `max(1px, ${100 / n}%)` } }));
  });
  m.replaceChildren(...kids, el("span", { hidden: true }));
  cmpMapCursor();
  cmpPlaceMap();
}

function cmpMapCursor() {
  const m = $("cmp-map"), n = cmp.marks.length;
  let b = m.querySelector("b");
  if (cmp.cursor === null || cmp.cursor >= n) {
    if (b) b.remove();
    return;
  }
  if (!b) {
    b = el("b");
    m.append(b);
  }
  b.style.top = `${(cmp.cursor / n) * 100}%`;
  b.style.height = `max(2px, ${100 / n}%)`;
}

/** The change map runs from the top of the page to the status bar, as the window's right-hand panel. */
let cmpPlacing = false;
function cmpPlaceMap() {
  if (cmpPlacing) return;
  cmpPlacing = true;
  requestAnimationFrame(() => {
    cmpPlacing = false;
    const m = $("cmp-map");
    if (m.hidden || $("bar-compare").hidden) return;
    const c = $("central"), box = c.getBoundingClientRect();
    const top = Math.max(0, box.top) + 4;
    const bottom = Math.min(innerHeight, $("statusbar").getBoundingClientRect().top) - 4;
    m.style.top = `${top}px`;
    m.style.height = `${Math.max(40, bottom - top)}px`;
    // beside the page's own scroll bar, not over it
    m.style.right = `${Math.max(0, innerWidth - box.right) + Math.max(0, c.offsetWidth - c.clientWidth) + 5}px`;
  });
}

/** The rows on screen, for the change map's frame. */
function cmpWatch(table) {
  if (cmpWatcher) cmpWatcher.disconnect();
  cmpSeen.clear();
  if (!("IntersectionObserver" in window)) return;
  cmpWatcher = new IntersectionObserver((entries) => {
    for (const e of entries) {
      const i = Number(e.target.dataset.i);
      if (e.isIntersecting) cmpSeen.add(i); else cmpSeen.delete(i);
    }
    const f = $("cmp-map").querySelector("span"), n = cmp.marks.length;
    if (!f) return;
    if (!cmpSeen.size || !n) {
      f.hidden = true;
      return;
    }
    let a = Infinity, b = -1;
    for (const i of cmpSeen) { a = Math.min(a, i); b = Math.max(b, i); }
    f.hidden = false;
    f.style.top = `${(a / n) * 100}%`;
    f.style.height = `${((b + 1 - a) / n) * 100}%`;
  });
  for (const tr of table.querySelectorAll("tr[data-i]")) cmpWatcher.observe(tr);
}

/** The compare's record map (the window's `records_matrix`): every record in the file order of the
 *  baseline column, unmapped ones in amber; a setting's name opens it in Edit mode. */
function drawCompareRecords() {
  const j = cmp.last;
  cmpMap(null);
  const out = [cmpPicker(j),
    el("p", { class: "small weak" }, "Records in file order of the first column (the baseline); cells that differ from it are highlighted; unmapped records in amber. Click a setting to open it."),
    el("hr")];
  if (!j.cols.length) return [...out, el("p", {}, "Pick at least one column.")];
  const base = j.cols[0];
  const head = el("tr", {}, el("th", {}, "Offset"), el("th", {}, "Record"), el("th", {}, "Shape"), el("th", {}, "Setting"),
    ...j.cols.map((c) => el("th", { class: "cmp-col" }, el("span", { class: "cmp-src-" + c.src }, c.name), cmpLock(c))));
  const rows = j.rows.map((r) => {
    const s = r.setting;
    const mono = (t) => el("td", { class: "cmp-mono" + (s ? "" : " cmp-amber") }, t);
    return el("tr", {}, mono(r.offset), mono(r.id), mono(r.shape),
      s ? el("td", {}, pressable(el("span", { class: "cmp-link", title: `${s.tab} > ${s.group}\n${s.note}` }, s.name), () => cmpOpenSetting(s, base.section)))
        : el("td", { class: "cmp-amber" }, "— unmapped —"),
      ...r.cells.map((c, i) => {
        const chars = [...c.text];
        const long = chars.length > 28;
        return el("td", { class: "cmp-v" + (i > 0 && c.differs ? " diff" : "") },
          el("span", { class: "cmp-mono", title: long ? c.text : null }, long ? chars.slice(0, 28).join("") + "…" : c.text));
      }));
  });
  return [...out, el("div", { class: "cmp-scroll" }, el("table", { class: "egrid cmp" }, el("thead", {}, head), el("tbody", {}, ...rows)))];
}

/** A setting of the record map opened in Edit mode, in the baseline column's set, as the window opens it: where the
 *  Menu shows it, its group and details unfolded and its row in view, found by its key (`openSetting`). */
async function cmpOpenSetting(s, section) {
  const was = view.target;
  if (state.targets.some(([i]) => i === section)) view.target = section;
  cmp.back = { page: "tab", q: "" };
  cmpSetMode("edit");
  const at = await openSetting(s);
  // another set: the Menu column's counts follow once the page is drawn (asked before, the state's answer would race
  // the page's own request and could have it dropped)
  if (view.target !== was) refresh();
  return at;
}

/** A row's "Open in Edit" (its name, or a value's menu in a column of file A), as the window's: Edit on that setting in
 *  `section` (the live settings when that set does not keep it), its tab shown with its group and details unfolded and
 *  the row in view (`openSetting`), and "← Back to Compare" at the head of the tab while it stays there. Only edited
 *  is turned off when it would hide the setting. */
async function cmpOpenInEdit(r, section) {
  cmpHideMenu();
  const keeps = section === 0 || r.in_sets;
  const target = keeps && state.targets.some(([i]) => i === section) ? section : 0;
  const ci = ((cmp.last && cmp.last.cols) || []).findIndex((c) => c.editable && c.section === target);
  const edited = ci >= 0 && !!r.cells[ci] && r.cells[ci].edited;
  if (view.only && !edited) {
    view.only = false;
    $("only").checked = false;
  }
  view.target = target;
  cmp.from = { key: r.key, tab: r.open_tab || r.tab, target };
  cmp.back = { page: "tab", q: "" };
  cmpSetMode("edit");
  await openSetting({ tab: r.tab, group: r.group, open_group: r.open_group, open_tab: r.open_tab, key: r.key });
}

/** Whether Edit still shows what "Open in Edit" opened: that setting's tab, in that set. */
function cmpFromHere() {
  return !!cmp.from && view.mode === "edit" && pageName() === "tab" && view.tab === cmp.from.tab && view.target === cmp.from.target;
}

/** "← Back to Compare" at the head of the tab "Open in Edit" opened, while it is shown (`cmpFromHere`). */
function cmpBackButton() {
  return cmpFromHere() ? el("button", { title: "Return to Compare, on the row this setting was opened from", onclick: cmpBackToCompare }, plain("← Back to Compare")) : null;
}

/** "← Back to Compare": Compare again, the row the setting was opened from under the cursor and in view. */
function cmpBackToCompare() {
  const f = cmp.from;
  cmp.from = null;
  if (!f) return;
  cmp.goKey = f.key;
  cmpSetMode("compare");
}

/** F3 / Shift+F3 (and Alt+↓ / Alt+↑) step through the differences unless a field has the keyboard;
 *  Escape closes a cell's menu. True when the key was taken. */
function cmpKey(e) {
  if (e.key === "Escape" && cmpMenuBox) {
    e.preventDefault();
    cmpHideMenu(true);
    return true;
  }
  if (e.key === "Escape" && cmp.pick) {
    e.preventDefault();
    cmpPickClose();
    return true;
  }
  if (view.mode !== "compare" || cmp.records || !state || !state.file) return false;
  const a = document.activeElement;
  if (a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.tagName === "SELECT" || a.isContentEditable)) return false;
  const next = (e.key === "F3" && !e.shiftKey) || (e.altKey && !e.ctrlKey && !e.metaKey && e.key === "ArrowDown");
  const prev = (e.key === "F3" && e.shiftKey) || (e.altKey && !e.ctrlKey && !e.metaKey && e.key === "ArrowUp");
  if (!next && !prev) return false;
  e.preventDefault();
  cmpStep(next ? 1 : -1);
  return true;
}

/** Files dropped on the page, as on the window: with no file open the first opens, any other is
 *  compared as file B. */
async function cmpDrop(files) {
  for (const f of files) {
    if (!state.file) await act("open", {}, f);
    else if (await act("open_b", {}, f)) cmpSetMode("compare");
  }
}

let cmpSearchTimer = null;

// the change map: a click, or a drag, jumps to that row
let cmpMapRow = null;
function cmpMapAt(e) {
  const m = $("cmp-map"), n = cmp.marks.length;
  if (!n) return;
  const r = m.getBoundingClientRect();
  if (cmpMapRow === null) requestAnimationFrame(() => { const i = cmpMapRow; cmpMapRow = null; cmpJump(i); });
  cmpMapRow = Math.max(0, Math.min(n - 1, Math.floor(((e.clientY - r.top) / r.height) * n)));
}

// --- Write… ---

/** Write…: the editor reads the camera first (`send_check` with `read`), as the window's Write does. The window says
 *  so while the state shows the editor busy with the camera, then lists what the write changes against the camera
 *  now and offers Write to camera for the file it checked (`rev`). A read that fails ends it, the camera report
 *  saying why in plain words; nothing is written until Write to camera is pressed. A second tap while the first is
 *  still being answered (before the window shows) does nothing: it would only start a second read, refused as busy. */
async function openSend() {
  if (xp.sending) return;
  xp.sending = true;
  try {
    await checkSend();
  } finally {
    xp.sending = false;
  }
}

/** The Write window closed. */
function closeSend() {
  const box = $("send");
  box.hidden = true;
  box.replaceChildren();
  setDialog(box, false);
}

/** The check behind Write…; it ends, asking nothing more, once its window is closed or the login takes the page's
 *  place (`xp.sendRound`): behind the login a request would carry no code, which the editor counts as a wrong one. */
async function checkSend() {
  const box = $("send");
  const round = xp.sendRound;
  let closed = false;
  const gone = () => closed || round !== xp.sendRound || $("app").hidden;
  let j;
  try { j = await api("send_check", { read: true }); } catch (e) { failed(e); await refresh(); return; }
  if (gone()) return;
  if (j.reading) {
    const close = () => {
      closed = true;
      closeSend();
      // the read goes on (a camera action is never cut short), but nobody waits for it any more
      api("send_cancel").catch(() => {});
    };
    box.classList.remove("alarm");
    showWindow(box, "Write to camera", close,
      el("div", { class: "set-row" }, el("span", { class: "spinner" }), el("strong", {}, "Reading the camera, to list what this write changes…")),
      el("p", { class: "small weak" }, `${state && state.read_time ? `Usually about ${state.read_time}. ` : ""}Nothing is written until you press Write to camera.`),
      el("div", { class: "buttons" },
        el("button", { disabled: true, title: "The camera is read first, so the window can list what the write changes" }, "Write to camera"),
        el("button", { onclick: close }, "Cancel")));
    // the editor is busy with the camera while it reads: the state names the job (asked every second meanwhile)
    const until = Date.now() + 180000;
    await refresh();
    while (!gone() && state && state.job && Date.now() < until) {
      await new Promise((r) => setTimeout(r, 1000));
      await refresh();
    }
    if (gone()) return;
    try { j = await api("send_check"); } catch (e) {
      if (gone()) return;
      closeSend();
      await refresh();
      // a read that failed: the Camera link report says why, so the toast does not say it twice
      if (!(e instanceof Refused && state && state.report)) failed(e);
      return;
    }
    if (gone()) return;
    if (j.reading) {
      closeSend();
      toast("The camera is still being read. Press Write again in a moment.");
      return;
    }
  }
  drawSend(j);
}

/** The values the Write window lists (`issues`), under what each is (`kind`, its line on hover and under it), in the
 *  editor's order, as the window lists them. */
function issueGroups(issues) {
  const out = [];
  for (const i of issues) {
    const last = out[out.length - 1];
    if (last && last.kind === i.kind) last.rows.push(i);
    else out.push({ kind: i.kind, line: i.kind_line, rows: [i] });
  }
  return out.flatMap((g) => [
    el("p", { class: "strong issue-kind", title: g.line || undefined }, g.kind),
    g.line ? el("p", { class: "small weak" }, g.line) : null,
    el("div", { class: "scrollx" }, el("table", { class: "egrid" }, el("tbody", {}, ...g.rows.map((i) =>
      el("tr", {}, el("td", {}, i.name), el("td", {}, el("strong", {}, i.value)), el("td", { class: "small" }, i.reason)))))),
  ]).filter(Boolean);
}

/** The Write window's check: what the write changes, how long to leave the camera on, a write that would turn the
 *  link off (Write anyway, once a box says it is understood), and the values the camera is not known to take, under
 *  what each is; the all-clear only when the editor sends no value (every changed one checked on the camera). With
 *  values listed, the button says it writes them anyway. */
function drawSend(j) {
  const box = $("send");
  const close = closeSend;
  // a file that would turn off the link the editor uses: sending it may leave the camera out of reach
  const risky = j.warnings.length > 0;
  const words = j.words || {};
  // what only the camera's copy shows (`camera_only`) is no flagged value, though it keeps the all-clear away
  const flagged = j.issues.filter((i) => !i.camera_only).length;
  const theirs = j.issues.length - flagged;
  // the file the check was made for (`rev`): the editor writes nothing if the file changed meanwhile
  const label = flagged ? `Write anyway, with ${flagged} flagged` : risky || theirs ? "Write anyway" : "Write to camera";
  const go = el("button", { disabled: risky, onclick: async () => { close(); await act("send", j.rev ? { rev: j.rev } : {}); } }, label);
  const sure = risky ? el("input", { type: "checkbox", onchange: (e) => { go.disabled = !e.target.checked; } }) : null;
  const again = async () => {
    await act("revert_flagged");
    try { drawSend(await api("send_check")); } catch (e) { failed(e); }
  };
  box.classList.toggle("alarm", risky);
  showWindow(box, "Write to camera", close,
    el("div", {}, ...j.summary.map(([t, warn]) => el("p", { class: warn ? "edit" : "" }, plain(t)))),
    el("p", { class: "small weak" }, "The whole file is written and the camera restarts; memories, custom keys and everything else in the file are replaced by what the file holds."),
    // how long to leave the camera on: its restart, then the check (the window's words)
    j.leave_on ? el("p", {}, plain(j.leave_on)) : null,
    ...j.warnings.map((w) => el("p", { class: "edit" }, plain(w))),
    risky ? el("label", { class: "check", style: { "white-space": "normal" } }, sure, " I understand the camera may drop off the network, and that someone has to reach it to turn the link back on.") : null,
    j.issues.length
      ? el("div", { class: "issues" },
          flagged ? el("p", { class: "warn" }, words.issues || `${flagged} value(s) the camera is not known to take as written.`) : null,
          flagged && words.todo ? el("p", { class: "small" }, words.todo) : null,
          theirs && words.camera_only ? el("p", { class: "warn", "data-camera-only": "" }, words.camera_only) : null,
          ...issueGroups(j.issues),
          j.issues.some((i) => i.edited !== false && !i.camera_only) ? el("div", { class: "buttons" }, el("button", { onclick: again }, "Revert all flagged")) : null)
      : el("p", { class: "ok" }, plain(words.all_clear || "✔ Every changed value was checked on the camera and is one it takes.")),
    el("div", { class: "buttons" }, go, el("button", { onclick: close }, "Cancel")));
}

// --- the windows: Settings (About is its last tab), Connect to the camera, Backups, Edit history and Changes, stacked
// from the top by when they were opened, the newest first (`toFront`) ---

// Settings' About tab, the last: its place in the editor's `SettingsTab::ALL`, whose labels come as `settings_tabs`
// (a test of the editor's holds the two together)
const SETTINGS_ABOUT = 5;

// the windows a question, Write and the Camera link report float in: they keep their place at the top of the stack
const FIXED_WINDOWS = ["ask", "send", "report"];

/** Put a window at the front of the stack, under the questions (`FIXED_WINDOWS`), and on top of `dialogs`, so that
 *  Escape closes it first. #windows does not scroll and each window is as tall as the screen at most, so the windows
 *  stack by when they were opened or asked for, the newest first: one opened later never lands out of sight below
 *  another. Moved in the page itself, not only in its look, so Tab and a screen reader meet the windows as they are
 *  seen; the focus stays where it was, and where it goes back to when the window closes is unchanged. */
function toFront(box) {
  const stack = $("windows");
  const first = [...stack.children].find((n) => n.tagName === "SECTION" && !FIXED_WINDOWS.includes(n.id));
  if (first && first !== box) {
    const had = document.activeElement;
    stack.insertBefore(box, first);
    if (had && box.contains(had) && document.activeElement !== had) had.focus({ preventScroll: true });
  }
  const i = dialogs.findIndex((d) => d.box === box);
  if (i >= 0 && !dialogs[i].modal) {
    const [d] = dialogs.splice(i, 1);
    const modal = dialogs.findIndex((x) => x.modal);
    dialogs.splice(modal < 0 ? dialogs.length : modal, 0, d);
  }
}

/** Open one of the windows (`xp.windows`), with what it shows asked for afresh, at the front of the stack (`toFront`):
 *  a window open already comes to the front too. */
function openWindow(name) {
  xp.windows[name] = true;
  xp.keys[name] = null;
  toFront($(name));
  if (name === "connect" || (name === "settings" && xp.settingsTab === 1)) loadCameraCards();
  if (name === "backups") loadBackups();
  if (name === "history") xp.historyRev = null;
  if (name === "changelog") loadChangelog();
  drawWindows();
}

/** Open Settings on one of its tabs (an index into `settings_tabs`), or turn the open Settings to it: drawn here, as
 *  its tab buttons draw it, since `drawWindows` leaves a window alone while one of its text fields has the focus. */
function openSettings(tab) {
  xp.settingsTab = tab;
  openWindow("settings");
  drawSettings();
}

function closeWindow(name) {
  xp.windows[name] = false;
  xp.keys[name] = null;
  $(name).hidden = true;
  $(name).replaceChildren();
  setDialog($(name), false);
}

function toggleWindow(name) {
  if (xp.windows[name]) closeWindow(name); else openWindow(name);
}

/** Fill one of the windows (Settings, Connect to the camera, Backups, Edit history): a title bar with its ✖, then its
 *  contents; what was scrolled stays scrolled. They float over the page as the window's do, not modal. */
function fillWindow(name, title, ...kids) {
  const box = $(name);
  const top = box.scrollTop;
  refill(box,
    el("div", { class: "title wtitle" }, el("span", {}, plain(title)),
      el("button", { class: "small sel", title: "Close", "aria-label": "Close", onclick: () => closeWindow(name) }, plain("✖"))),
    el("div", { class: "wbody" }, ...kids));
  box.hidden = false;
  box.scrollTop = top;
  setDialog(box, true, { close: () => closeWindow(name) });
}

/** True when the window was last drawn for `key` (nothing to do); else it is drawn now, for this key. */
function drawnFor(name, key) {
  if (xp.keys[name] === key) return true;
  xp.keys[name] = key;
  return false;
}

/** The open windows, drawn again when what they show changed, but not under the cursor of one of their fields. */
function drawWindows() {
  if (!state) return;
  const ck = JSON.stringify(state.camera || null);
  if (ck !== xp.cameraKey) {
    xp.cameraKey = ck;
    if (xp.windows.connect || (xp.windows.settings && xp.settingsTab === 1)) loadCameraCards();
  }
  const draw = { backups: drawBackups, history: drawHistory, settings: drawSettings, connect: drawConnect, changelog: drawChangelog };
  for (const name of Object.keys(xp.windows)) {
    const box = $(name);
    if (!xp.windows[name]) {
      if (!box.hidden) closeWindow(name);
      continue;
    }
    const a = document.activeElement;
    if (a && box.contains(a) && a.tagName === "INPUT" && a.type !== "checkbox" && a.type !== "radio") continue;
    draw[name]();
  }
}

/** A frame of the window's Settings and camera cards, with its title. */
function setCard(title, ...kids) {
  return el("div", { class: "set-card" }, el("div", { class: "ct" }, title), ...kids);
}

/** A card that folds, as the window's setup steps; whether it is open is kept while the page is open. */
function folding(id, title, ...kids) {
  const d = el("details", { class: "grp", open: xp.folds.has(id) }, el("summary", {}, title), ...kids);
  d.addEventListener("toggle", () => { if (d.open) xp.folds.add(id); else xp.folds.delete(id); });
  return d;
}

/** egui's selectable label. */
function selButton(on, label, onclick, title) {
  return el("button", { class: "sel" + (on ? " on" : ""), onclick, title }, label);
}

/** Whether one of the editor's switches is the desktop app's only (`prefs.desktop`, or not in `prefs.page_sets`). */
function deskOnly(name) {
  const p = (state && state.prefs) || {};
  return (Array.isArray(p.desktop) && p.desktop.includes(name)) || (Array.isArray(p.page_sets) && !p.page_sets.includes(name));
}

/** A checkbox for one of the editor's own switches: the change goes to the editor, which keeps it; one the desktop
 *  app keeps to itself is shown as it stands. */
function prefBox(name, label, opts = {}) {
  if (deskOnly(name)) return deskBox(state.prefs[name], label);
  const box = el("input", { type: "checkbox", disabled: opts.disabled });
  box.checked = !!state.prefs[name];
  box.addEventListener("change", () => act("prefs", { name, value: box.checked }));
  return el("div", { class: "set-row" }, el("label", { class: "check wrap", title: opts.title }, box, label));
}

/** A switch of the window's own, shown as it stands: it is set in the desktop app. */
function deskBox(on, label) {
  const box = el("input", { type: "checkbox", disabled: true });
  box.checked = !!on;
  return el("div", { class: "set-row" }, el("label", { class: "check wrap", title: "Set in the desktop app" }, box, label,
    el("span", { class: "small weak" }, "(set in the desktop app)")));
}

/** A control the page cannot offer (a dialog on the editor's computer), greyed out with where it is. */
function deskButton(label, where) {
  return el("span", { title: where }, el("button", { disabled: true }, label));
}

/** Settings, as the window's: its six tabs, each with its subtitle and cards, About the last (`SETTINGS_ABOUT`). */
function drawSettings() {
  const s = state;
  const tabs = s.settings_tabs || [];
  const key = JSON.stringify([xp.settingsTab, s.prefs, camData(), !!s.job, s.recent, s.schemas, s.dirs, s.web_url, pageTheme(), pageDensity(), getFontScale(), session.token,
    s.version, s.version_short, s.build, s.works_with, s.not_sony, s.about]);
  if (drawnFor("settings", key)) return;
  const tab = Math.max(0, Math.min(xp.settingsTab, tabs.length - 1));
  const draw = [settingsAppearance, () => cameraCards("settings"), settingsEditing, settingsFiles, settingsDefinitions, settingsAbout][tab] || (() => []);
  fillWindow("settings", "Settings",
    el("div", { class: "set-tabs" }, ...tabs.map(([label], i) => selButton(i === tab, plain(label), () => { xp.settingsTab = i; if (i === 1) loadCameraCards(); drawSettings(); }))),
    el("hr"),
    el("div", { class: "small weak set-row" }, tabs[tab] ? tabs[tab][1] : ""),
    el("div", {}, ...draw()),
    el("hr"),
    // where the settings are kept; the version, the not-affiliated line and Changes are the About tab's alone, as in
    // the window
    el("div", { class: "set-foot small weak" },
      el("span", { title: `Preferences file: ${s.prefs.prefs_path}` }, plain("⚙ Preferences"))));
}

function settingsAppearance() {
  const p = state.prefs;
  const [theme, density, scale] = [pageTheme(), pageDensity(), getFontScale()];
  const again = () => drawSettings();
  const spacing = ["Compact", "Comfortable", "Spacious"];
  return [
    setCard("Theme and text size",
      el("div", { class: "set-row" }, "Theme:",
        ...[["system", "Follow the system"], ["dark", "Dark"], ["light", "Light"]].map(([t, label]) =>
          selButton(theme === t, label, () => { setPageTheme(t); again(); }, t === "system" ? "As this browser or phone is set" : undefined))),
      el("div", { class: "set-row" }, "Text size:",
        ...[[0.9, "90%"], [1.0, "100%"], [1.15, "115%"], [1.3, "130%"]].map(([v, label]) =>
          selButton(Math.abs(scale - v) < 0.02, label, () => { setFontScale(v); again(); })),
        el("button", { title: "Smaller text (Cmd/Ctrl −)", "aria-label": "Smaller text", onclick: () => { setFontScale(getFontScale() - 0.1); again(); } }, "−"),
        el("button", { title: "Larger text (Cmd/Ctrl +)", "aria-label": "Larger text", onclick: () => { setFontScale(getFontScale() + 0.1); again(); } }, "+")),
      el("div", { class: "small weak" }, "Shortcut: Cmd/Ctrl + and −, or Cmd/Ctrl 0 for 100%."),
      el("div", { class: "set-row" }, "Row spacing:", ...spacing.map((label, i) => selButton(density === i, label, () => { setPageDensity(i); again(); }))),
      el("div", { class: "small weak" }, `These three are this page's own, kept in this browser (its text goes from 90% to 140%). The editor's window: `
        + `${{ system: "Follow the system", light: "Light", dark: "Dark" }[p.theme] || (p.light ? "Light" : "Dark")}, ${Math.round(p.zoom * 100)}% text, ${spacing[p.density] || spacing[1]} rows, set in the desktop app.`)),
  ];
}

function settingsEditing() {
  const p = state.prefs;
  return [
    setCard("Compare and Memories",
      prefBox("matrix_only_diff", "Compare starts with only the rows that differ"),
      prefBox("all_memory_cols", "Compare starts with a second shooting mode's memories too")),
    setCard("Expert mode",
      prefBox("expert", "Expert mode: also show the settings without a name yet, the duplicate copies the camera keeps, and every memory",
        { title: "For mapping work and support: record numbers and the record map, the settings the editor cannot name yet, the copies the camera keeps twice, every memory in the file, and the numbers the camera stores" }),
      el("div", { class: "set-indent" },
        prefBox("allow_unobserved", "Offer values not checked on the camera yet (the camera may refuse a file holding one)", { disabled: !p.expert }),
        prefBox("allow_raw_edits", "Allow changing the stored number of the settings without a name yet", { disabled: !p.expert })),
      // what each row shows for mapping work, under Expert mode as in the window, shown only while it is on
      p.expert ? el("div", { class: "set-indent" },
        prefBox("show_record_ids", "Show each setting's record number beside its name"),
        prefBox("show_proof", "Show whether each setting was proved on the camera (e.g. Proved on the camera (3/3))"),
        prefBox("show_raw", "Show the number the camera stores beside each value's name")) : null),
    el("div", { class: "small weak" }, "Compare's two are the editor's own switches: they change its window too. Expert mode and its options open what can harm the camera, so they are set in the desktop app."),
  ];
}

function settingsFiles() {
  const s = state;
  const d = s.dirs || {};
  const recent = s.recent || [];
  return [
    setCard("Copies kept",
      el("div", { class: "small weak" }, `Kept copies: files as first opened in ${d.originals}, the camera's settings in ${d.camera}`),
      prefBox("backup_on_save", "Keep a copy of a file before Save As replaces it"),
      el("div", { class: "set-row" },
        el("button", { onclick: () => openWindow("backups") }, "📂 View backups…"),
        deskButton("Open backups folder", "The folder is on the editor's computer: opened from the desktop app"))),
    setCard("Start-up and recent files",
      deskBox(s.prefs.reopen_last, "Reopen the last files, mode and page at start"),
      el("div", { class: "strong" }, "Recent files:"),
      recent.length ? null : el("div", { class: "weak" }, "none yet"),
      ...recent.map((r, i) => el("div", { class: "set-row" },
        el("button", { class: "small", onclick: () => { closeWindow("settings"); openRecent(i); } }, "Open"), el("span", { class: "mono" }, r.path))),
      recent.length ? el("div", { class: "set-row" }, el("button", { class: "small", onclick: () => act("clear_recent") }, "Clear list")) : null),
  ];
}

function settingsDefinitions() {
  const s = state;
  const p = s.prefs;
  return [
    setCard("Camera definitions",
      el("div", { class: "small weak" }, "A camera definition tells the editor what every record of one camera model and firmware means. The built-in ones come with the editor; your own, added in the desktop app, are used in place of a built-in one of the same model and firmware."),
      el("div", { class: "set-row" },
        deskButton("Add definition…", "A file on the editor's computer: added in the desktop app"),
        el("button", { onclick: () => act("reload_schemas") }, "Reload")),
      el("div", { class: "mono" }, `Yours: ${p.definitions_dir || ""}`),
      el("div", { class: "scrollx" }, el("table", { class: "egrid" },
        el("thead", {}, el("tr", {}, ...["Model", "Firmware", "Settings", "File"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...(s.schemas || []).map((d) => el("tr", { class: d.active ? "ok" : "" },
          el("td", {}, d.model), el("td", {}, d.firmwares), el("td", {}, String(d.settings)),
          el("td", { title: d.active ? "in use for the opened file" : undefined }, d.src)))))),
      // the camera's own help text in use, by its file name, as the window's; and a help file of a definition's name
      // that is another camera's (or not a help file): not used, and why
      s.help_src ? el("div", { class: "small weak" }, `The camera's own help text: ${s.help_src}`) : null,
      ...(s.schemas || []).flatMap((d) => d.help_refused || []).map((t) => el("div", { class: "small warn" }, t))),
    setCard("Web page for a phone or tablet",
      el("div", { class: "small weak" }, "Use this editor from a browser on another computer, a tablet or a phone: read the camera, change settings and send them. For a camera far away on a network, run the editor on a computer on that network and open the page from wherever you are. The page works on the file open here, so edits show in both."),
      deskBox(true, `Web page on, port ${p.web_port}, ${p.web_local_only ? "this computer only" : "from the network"}`),
      el("div", { class: "set-row" }, "Open", el("strong", { class: "mono" }, s.web_url || location.origin), "and enter the access code shown in the desktop app."),
      el("div", { class: "small weak" }, "The port, who may connect, the access code and turning the page off are set in the desktop app: changed from here, they would cut this page off."),
      el("div", { class: "small http-warn" }, "Anyone who can reach this computer and has the code can change the camera's settings and send them. The page is plain HTTP, so the code and the settings cross the network unencrypted: on a network you do not trust, or across the internet, use a VPN or an SSH tunnel, and do not open the port on a router."),
      el("div", { class: "set-row" },
        el("button", { onclick: signOut, title: "This browser forgets the access code and its session; the page asks for the code again" }, "Sign out"),
        el("span", { class: "small weak" }, session.token
          ? `This browser keeps a session, not the code; it ends after ${Math.round(session.idle / 3600e3)} hours unused. New code in the desktop app signs every browser out.`
          : "This browser keeps the access code until you sign out here or New code is pressed in the desktop app.")),
      deskBox(p.web_at_start, "Turn the web page on when the editor starts")),
  ];
}

/** The camera cards, the same in Connect to the camera and Settings > Camera link: the link and the search, the
 *  setup steps (their fold and ticks are the editor's, shared with its window), the known cameras, the address
 *  and where the login is entered (network only) and the helper. `where` keeps the two windows' radio buttons apart. */
function cameraCards(where) {
  const s = state;
  const c = camData();
  if (!c) return [el("p", { class: "weak" }, "Asking the editor for the camera details…")];
  const busy = !!s.job;
  const net = c.link === "network";
  const link = (value, label) => {
    const r = el("input", { type: "radio", name: `${where}-link` });
    r.checked = (value === "network") === net;
    // as the window's radio buttons: a click sets the link, also the one shown when none was chosen yet
    r.addEventListener("click", () => { if (c.link !== value) act("camera_link", { link: value }); });
    return el("label", { class: "check" }, r, label);
  };
  const found = c.found || [];
  const cards = [setCard("Connection",
    el("div", { class: "set-row" }, "Connection method:", link("usb", "USB cable"), link("network", "Network (wired LAN or Wi-Fi)")),
    el("div", { class: "set-row" },
      el("button", { disabled: busy, onclick: () => act("camera_search"),
        title: c.search_tip || "Looks for every camera this computer can reach: USB ones in PC Remote mode and network ones with remote control on" }, "🔍 Search for cameras"),
      busy ? el("span", { class: "spinner" }) : null),
    c.msg ? el("div", { class: "small weak" }, plain(c.msg)) : null,
    c.detail ? el("pre", { class: "small weak" }, c.detail) : null,
    c.detail_note ? el("div", { class: "small weak" }, plain(c.detail_note)) : null,
    found.length ? foundTable(c, found) : null,
    found.length ? el("div", { class: "ok" }, c.found_line) : null,
    c.text ? folding(`${where}-text`, "Details from the camera link", el("pre", { class: "small weak" }, c.text)) : null)];

  const steps = el("details", { class: "set-card grp", open: c.steps_open },
    el("summary", {}, "Set the camera up like this"),
    ...c.steps.map((t, i) => {
      const b = el("input", { type: "checkbox" });
      b.checked = !!c.checks[i];
      b.addEventListener("change", () => act("camera_check", { index: i, value: b.checked }));
      return el("div", { class: "set-row" }, el("label", { class: "check wrap" }, b, t));
    }),
    c.steps_note ? el("div", { class: "small weak" }, c.steps_note) : null);
  steps.addEventListener("toggle", () => { if (steps.open !== c.steps_open) act("camera_steps", { open: steps.open }); });
  cards.push(steps);

  cards.push(setCard("Known cameras", ...(!c.known.length
    ? [el("div", { class: "small weak" }, "None yet. The editor remembers a camera when you pick it after a search, or when it connects to it.")]
    : [el("div", { class: "small weak" }, "Give each camera a name of your own. Each camera's user name and password are kept separately, under its MAC address."),
      el("div", { class: "scrollx" }, el("table", { class: "egrid conn-table" },
        el("thead", {}, el("tr", {}, ...["Your name", "Model", "Serial", "MAC address", "Last link", "Last seen", ""].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...c.known.map((k) => el("tr", {},
          el("td", {}, nameField(k.name, false, (name) => act("camera_name", { known: k.index, name }))),
          el("td", {}, k.model), el("td", {}, idCell(k.serial, c.learned)), el("td", {}, idCell(k.mac, c.learned)),
          el("td", {}, k.link), el("td", {}, k.last_seen),
          el("td", {}, el("button", { class: "small", title: "Take this camera off the list. Its user name and password, and the trust in it, stay on the editor's computer until Forget in the desktop app",
            onclick: () => act("camera_forget", { index: k.index }) }, "Forget")))))))])));

  if (net) {
    // the page picks among the addresses the editor has met a camera at; a new one is typed in the desktop app, or
    // found with Search, so the page cannot send the camera's login to an address of its choosing
    const met = [...new Set([c.ip, ...(c.addresses || []), ...(c.known || []).map((k) => k.ip)].map((x) => String(x || "").trim()).filter(Boolean))];
    let ip;
    if (met.length > 1) {
      ip = el("select", { "aria-label": "Camera IP address", onchange: () => act("camera_link", { link: "network", ip: ip.value }) }, ...met.map((a) => el("option", { value: a }, a)));
      ip.value = String(c.ip || "").trim();
      ip = el("span", { class: "combo narrow" }, ip);
    } else ip = el("strong", { class: "mono" }, String(c.ip || "").trim() || "none yet");
    // the user name and password are typed in the desktop app only: the page is plain HTTP and never sends them
    cards.push(setCard("Network address and camera login",
      el("div", { class: "set-row" }, "Camera IP address:", ip, c.address_hint ? el("span", { class: "small weak" }, `(${c.address_hint})`) : null),
      el("div", { class: "small weak" }, "A new address is typed in the desktop app, or found with 🔍 Search for cameras."),
      el("div", { class: "set-row" }, "Camera login:", el("span", {}, [loginKept(c), `The camera's user name and password are entered in the desktop app (${DESK_LOGIN}); they never cross the network from this page.`].filter(Boolean).join(" ")))));
  }

  cards.push(setCard("Camera link program",
    el("div", { class: "small weak" }, "Reading and writing go through the camera link program (camset_probe)."),
    el("div", { class: "set-row" }, "Program:", deskButton("Choose…", "A program on the editor's computer: chosen in the desktop app")),
    el("div", { class: "mono" }, c.helper)));
  return cards;
}

/** Whether the editor's computer keeps a login for the chosen camera, in the page's words: `login_saved`, and from the
 *  editor's note whether that is the default pair (the note's own words are not shown). */
function loginKept(c) {
  if (String(c.credentials_note || "").toLowerCase().includes("default pair")) return "This camera uses the default login; none of its own is saved yet.";
  if (c.login_saved === true) return "A login is saved for this camera.";
  if (c.login_saved === false) return "No login is saved for this camera yet.";
  return "";
}

/** The camera cards' details: the last `camera_cards` answer, with the state's link, busy and button (which the
 *  state carries every few seconds); null until it has come. */
function camData() {
  return xp.camera ? { ...xp.camera, ...((state && state.camera) || {}) } : null;
}

/** An answer carrying the camera cards (`camera`, as every camera request's does): kept for the windows. */
function keepCamera(j) {
  if (j && j.camera && typeof j.camera === "object" && Array.isArray(j.camera.steps)) {
    xp.camera = j.camera;
    xp.keys.connect = xp.keys.settings = null;
  }
}

/** Ask the editor for the camera cards (the state carries only the link, busy and the button). */
async function loadCameraCards() {
  try { keepCamera(await api("camera_cards")); } catch (e) { failed(e); }
  drawWindows();
}

/** A serial number or MAC address cell: the value, or a weak "not yet known" that says why on hover. */
function idCell(value, why) {
  return value ? el("span", { class: "mono" }, value) : el("span", { class: "small weak", title: why }, "not yet known");
}

/** The person's own name for a camera, saved when the field is left. */
function nameField(value, disabled, save) {
  const f = el("input", { type: "text", class: "conn-name", maxlength: 60, placeholder: "e.g. Studio camera", value, disabled,
    autocomplete: "off", spellcheck: "false", "aria-label": "Your name for this camera" });
  f.addEventListener("change", () => save(f.value));
  return f;
}

/** The "Cameras found" table of the last search, as the window's: "Use this one" first, so it shows on any screen
 *  without scrolling (and stays in place while a narrow screen scrolls the table sideways). */
function foundTable(c, found) {
  const head = [[""], ["Model"], ["Link"], ["Your name", "Your own name for this camera; the editor names it so wherever it names the camera"],
    ["Serial", "The body's serial number: a USB camera sends it, a network camera tells it when the editor first connects"],
    ["MAC address", "The camera's network card: the search sends it, or for a camera answered at its address, this computer's network table. Each camera's user name and password are kept under it"]];
  return el("div", { class: "scrollx" }, el("table", { class: "egrid conn-table conn-found" },
    el("thead", {}, el("tr", {}, ...head.map(([h, t]) => el("th", { title: t }, h)))),
    el("tbody", {}, ...found.map((d) => el("tr", {},
      el("td", {}, el("button", { onclick: () => act("camera_use", { index: d.index }) }, "Use this one")),
      el("td", { title: d.own_name ? `The camera's own name for itself: ${d.own_name}` : undefined }, d.model),
      el("td", { title: d.link_hover }, d.link, d.link_note ? el("div", { class: "small weak" }, d.link_note) : null),
      el("td", {}, nameField(d.name, !d.can_name, (name) => act("camera_name", { found: d.index, name }))),
      el("td", {}, idCell(d.serial, d.serial_why)),
      el("td", {}, idCell(d.mac, d.mac_why)))))));
}

/** Connect to the camera: the camera cards and a button that connects and reads. */
function drawConnect() {
  const s = state;
  if (drawnFor("connect", JSON.stringify([camData(), !!s.job, s.prefs.expert]))) return;
  fillWindow("connect", "Connect to the camera", ...cameraCards("connect"),
    el("hr"),
    el("div", { class: "set-row" },
      el("button", { disabled: !!s.job, onclick: () => { closeWindow("connect"); $("b-read").click(); } }, "Connect and read from camera"),
      el("span", { class: "small weak" }, "A Camera link window then reports what happened.")));
}

/** Ask the editor for the copies it keeps, for Backups. */
async function loadBackups() {
  try {
    xp.backups = await api("backups");
  } catch (e) {
    failed(e);
  }
  drawWindows();
}

/** Backups: every copy the editor keeps, newest first, each one opened by request. */
function drawBackups() {
  const b = xp.backups;
  if (drawnFor("backups", JSON.stringify([b, state.file ? state.file.changes : 0]))) return;
  const d = (b && b.dirs) || state.dirs || {};
  const list = b ? b.list : [];
  const open = (x) => () => replaceAct("open_backup", { index: x.index, name: x.name }, null, "Open a kept copy", opening(x.name), "Open anyway");
  fillWindow("backups", "Backups",
    el("p", { class: "small" }, "The editor never writes into a file it opened. It keeps every settings file as first opened (and any file a Save As replaces), and the camera's settings at every read, just before every write and after it. To go back, open a copy and write it to the camera or Save As."),
    el("p", { class: "small weak", style: { "white-space": "pre-wrap" } }, `Originals: ${d.originals}\nCamera: ${d.camera}`),
    el("button", { class: "small", onclick: loadBackups }, "Refresh"),
    b && !list.length ? el("p", {}, "Nothing kept yet.") : null,
    list.length ? el("div", { class: "scrollx" }, el("table", { class: "egrid" }, el("tbody", {}, ...list.map((x) => el("tr", {},
      el("td", {}, x.when), el("td", {}, x.kind), el("td", { class: "small" }, x.name),
      el("td", {}, el("button", { class: "small", onclick: open(x), title: "Open this copy; edits go to a new file with Save As, so the copy stays as it is" }, "Open"))))))) : null);
}

/** Ask the editor for the session's edits, for Edit history. Two edits in a row ask twice: the answer to the older
 *  request, should it come last, is dropped, so it cannot show the list as it was before the newer edit. */
async function loadHistory() {
  const n = ++xp.historyAsked;
  let h = null;
  try {
    h = state.file ? await api("history") : null;
  } catch (e) {
    if (n === xp.historyAsked) failed(e);
  }
  if (n !== xp.historyAsked) return;
  xp.history = h;
  drawWindows();
}

/** Edit history: every edit of the session with its before and after, each record revertable. */
function drawHistory() {
  const s = state;
  if (xp.historyRev !== s.rev) {
    xp.historyRev = s.rev;
    loadHistory();
  }
  const h = xp.history;
  if (drawnFor("history", JSON.stringify([h, !!s.file, s.history]))) return;
  let body = [];
  if (!s.file) body = [el("p", {}, "No file open.")];
  else if (!s.history) body = [el("p", {}, "No edits yet in this session.")];
  else if (h) {
    body = [el("p", { class: "small weak" }, "Oldest first. Revert puts one setting back to what it was before that edit; Undo and Redo in the top bar step through the whole list."),
      el("div", { class: "scrollx" }, el("table", { class: "egrid" },
        el("thead", {}, el("tr", {}, ...["#", "Setting", "Before", "After", ""].map((x) => el("th", {}, x)))),
        el("tbody", {}, ...h.steps.map((x) => el("tr", {},
          el("td", {}, String(x.step + 1)), el("td", {}, x.name), el("td", {}, x.before), el("td", { class: "hist-after" }, x.after),
          el("td", {}, x.revert === false ? null : el("button", { class: "small", title: "Put this setting back to its value before this edit",
            onclick: () => act("revert_history", { step: x.step, section: x.section, id: x.id }) }, "Revert")))))))];
  }
  fillWindow("history", "Edit history", ...body);
}

/** The status bar's version, at its right end, as the window's: the editor's name and short version (the version alone
 *  on a phone), the whole version on hover; a click or a tap opens Settings on its About tab. */
function drawVersion(s) {
  const b = $("foot-version");
  const short = s.version_short || s.version || "";
  if (b.dataset.key === `${short}|${s.version}`) return;
  b.dataset.key = `${short}|${s.version}`;
  b.replaceChildren(el("span", { class: "vname" }, "Camset Editor "), short);
  b.title = `Camset Editor ${s.version || short}\nClick for Settings > About`;
  b.setAttribute("aria-label", `Camset Editor ${short}`);
}

/** Settings > About, as the window's: which editor this is (its version, and the commit of a build made from the
 *  repository), the system the editor runs on, the cameras it works with, whether the camera link program is there,
 *  the licence, the project's pages, and the ways to what changed, to the licences (a page on the editor's computer,
 *  which the desktop app opens) and to a copy of the details for a message about a problem. All of it is the editor's
 *  (`state.about`, `web_about`), so the page and the window say the same. */
function settingsAbout() {
  const s = state;
  const a = s.about || {};
  return [
    setCard("Camset Editor",
      el("p", {}, `Version ${s.version_short || s.version || ""}`),
      s.build ? el("p", { title: "The commit it was built from, in the project's repository" }, `Build ${s.build}`) : null,
      a.system ? el("p", { title: "The computer the editor runs on, and the processor the program was built for" }, a.system) : null,
      s.works_with && s.works_with.length ? el("p", { class: "weak", title: "The cameras and firmware the editor has a definition for: built in, or added in Settings > Camera support & web page" }, `Works with: ${s.works_with.join(", ")}`) : null,
      a.helper ? el("p", { class: "weak", title: "The program that reads and writes a camera over USB or the network; without it the editor opens files only" }, a.helper) : null,
      el("div", { class: "buttons" },
        a.details ? el("button", { title: `Copies these lines, to paste into a message about a problem:\n${a.details}`,
          onclick: async () => toast(await copyText(a.details) ? "About's details copied, to paste into a message about a problem"
            : "This browser did not let the page copy: select the lines above and copy them") }, "Copy details") : null,
        el("button", { title: "What changed, release by release", onclick: () => openWindow("changelog") }, "Changes"))),
    // in a new tab, and the project's pages are not told which page sent the reader there
    setCard("The project's pages",
      el("div", { class: "buttons about-links" }, ...(a.links || []).map((l) =>
        el("a", { href: l.url, target: "_blank", rel: "noopener noreferrer", title: `${l.title}\n${l.url}` }, l.text)))),
    setCard("Licence",
      a.licence ? el("p", { class: "weak" }, a.licence) : null,
      el("p", { class: "weak" }, s.not_sony),
      el("div", { class: "buttons" },
        deskButton("Third-party licences", "In the desktop app: Settings > About opens the licences page on the editor's computer"))),
  ];
}

/** Put a text on the clipboard of the device the page is on: with the Clipboard API where the browser offers it (on a
 *  secure page only: localhost or https), else with the older copy command, which also works on the page's plain
 *  http address on the network. False when neither did; the text box it copies from is always taken away again, and
 *  the focus goes back where it was. */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (e) { /* no Clipboard API on an http address: the copy command below */ }
  const back = document.activeElement;
  const t = el("textarea", { readonly: true, "aria-hidden": "true", tabindex: "-1", style: { position: "fixed", top: "0", left: "0", opacity: "0" } });
  t.value = text;
  try {
    document.body.append(t);
    t.select();
    t.setSelectionRange(0, text.length);   // iOS selects nothing with select() alone
    return document.execCommand("copy") === true;
  } catch (e) {
    return false;
  } finally {
    t.remove();
    if (back && back.focus) back.focus();
  }
}

/** Ask the editor for the changelog built into it, for Changes, each time the window opens: a request that failed
 *  leaves nothing kept, so opening Changes again asks again. */
async function loadChangelog() {
  xp.changelog = null;
  xp.changelogFailed = false;
  try {
    xp.changelog = (await api("changelog")).blocks || [];
  } catch (e) {
    xp.changelogFailed = true;
    failed(e);
  }
  drawWindows();
}

/** Changes, as the window's: the changelog built into this editor, release by release (kind 2 a release, 3 a part,
 *  1 a point, 0 a paragraph; `changelog_blocks`). */
function drawChangelog() {
  const b = xp.changelog;
  if (drawnFor("changelog", JSON.stringify([b, xp.changelogFailed, state.version]))) return;
  const block = ([kind, text]) => kind === 2 ? el("h1", { style: { "margin-top": "10px" } }, text)
    : kind === 3 ? el("div", { class: "strong", style: { "margin-top": "6px" } }, text)
    : kind === 1 ? el("div", { class: "set-row", style: { "align-items": "flex-start" } }, el("span", {}, "•"), el("span", {}, text))
    : el("p", {}, text);
  fillWindow("changelog", "Changes",
    el("p", { class: "weak" }, `Camset Editor ${state.version || ""}`),
    b ? el("div", {}, ...b.map(block))
      : xp.changelogFailed ? el("p", { class: "warn" }, "The editor could not be asked for what changed. Close Changes and open it again to try again.")
      : el("p", { class: "weak" }, "Asking the editor…"));
}

// --- the toolbar: what does not fit folds into More ---

// the top bar keeps one row: the buttons that do not fit fold into More, the lowest data-fold first (the text size,
// Recent, Export CSV, Backups, History, Download, Settings, Redo, Open, the camera, then Edit/Compare), so on a phone
// Undo, Read, Write and More stay; the row wraps only when even those do not fit
const bar1 = $("bar1");
function fitBar() {
  const items = [...bar1.querySelectorAll("[data-fold]")];
  const before = items.filter((x) => x.classList.contains("folded")).map((x) => x.id).join();
  bar1.classList.remove("fold", "wrap");
  for (const x of items) x.classList.remove("folded");
  const over = () => bar1.scrollWidth > bar1.clientWidth + 1;
  loneSeparators();
  if (over()) {
    bar1.classList.add("fold");
    const can = items.filter((x) => !x.hidden && getComputedStyle(x).display !== "none").sort((a, b) => a.dataset.fold - b.dataset.fold);
    for (const x of can) {
      x.classList.add("folded");
      loneSeparators();
      if (!over()) break;
    }
    if (!can.length) bar1.classList.remove("fold");
    if (over()) bar1.classList.add("wrap");
  }
  const after = items.filter((x) => x.classList.contains("folded")).map((x) => x.id).join();
  if (!$("moremenu").hidden && after !== before) openMore(false);
}

/** The bar fitted once the page has settled: a resize, or a button shown, hidden or relabelled. */
let fitQueued = false;
function queueFit() {
  if (fitQueued) return;
  fitQueued = true;
  requestAnimationFrame(() => { fitQueued = false; fitBar(); });
}

/** A separator with nothing shown on one side of it is not drawn. */
function loneSeparators() {
  for (const row of [bar1, bar1.querySelector(".right")]) {
    let last = null;
    for (const x of row.children) {
      if (x.classList.contains("vsep")) {
        x.classList.remove("lone");
        if (!last || last.classList.contains("vsep")) x.classList.add("lone");
        else last = x;
      } else if (!x.hidden && !x.classList.contains("folded") && getComputedStyle(x).display !== "none") last = x;
    }
    if (last && last.classList.contains("vsep")) last.classList.add("lone");
  }
}

/** What More offers: each button folded out of the bar, in the bar's order, as it stands (greyed out where the button
 *  is: one greyed out with a reason, `greyOut`, stays reachable and says it when chosen); Recent as its files, the
 *  text size as its two steps, Edit/Compare as the mode not shown. */
function moreItems() {
  const out = [];
  const off = (b) => b.classList.contains("off");
  for (const x of bar1.querySelectorAll(".folded")) {
    if (x.hidden) continue;
    if (x.id === "mode") {
      const to = view.mode === "compare" ? $("b-edit") : $("b-compare");
      out.push([to.textContent, to.title, () => to.click()]);
    } else if (x.id === "b-recent-box") {
      (state.recent || []).forEach((r, i) => out.push([`Recent: ${r.name}`, "Open a file opened before", () => openRecent(i)]));
    } else if (x.id === "font-scale") {
      out.push(["A− Smaller text", $("b-font-dec").title, () => $("b-font-dec").click(), $("b-font-dec").disabled, off($("b-font-dec"))],
        ["A+ Larger text", $("b-font-inc").title, () => $("b-font-inc").click(), $("b-font-inc").disabled, off($("b-font-inc"))]);
    } else if (x.tagName === "BUTTON") {
      out.push([x.textContent.trim(), x.title, () => x.click(), x.disabled, off(x)]);
    }
  }
  return out;
}

/** More's menu under its button, open until a choice, a tap elsewhere or Escape; the page's polls leave it open. */
function openMore(focus = true) {
  const box = $("moremenu"), btn = $("b-more");
  const items = moreItems();
  if (!items.length) { closeMore(false); return; }
  const at = box.contains(document.activeElement) ? [...box.children].indexOf(document.activeElement) : -1;
  box.replaceChildren(...items.map(([label, title, run, disabled, off]) =>
    el("button", { role: "menuitem", title, disabled, class: off ? "off" : null, "aria-disabled": off ? "true" : null, onclick: () => { closeMore(true); run(); } }, plain(label))));
  box.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  const r = btn.getBoundingClientRect();
  placeAt(box, r.left, r.bottom + 2);
  const enabled = [...box.querySelectorAll("button:not(:disabled)")];
  if (at >= 0 && box.children[at]) box.children[at].focus();
  else if (focus && enabled.length) enabled[0].focus();
}

/** The pop-ups open placed again inside the window once its size changes (a phone turned): More, My Menu and the
 *  compare's picker. (A compare cell's menu closes instead.) */
function placePopups() {
  if (!$("moremenu").hidden) openMore(false);
  if (!$("mymenu").hidden && myMenuAt) placeAt($("mymenu"), myMenuAt.x, myMenuAt.y);
  if (cmp.pick) placeAt(cmp.pick.box, cmp.pick.x, cmp.pick.y);
}

/** More's menu closed; `focusBack`: the focus goes back to its button. */
function closeMore(focusBack) {
  const box = $("moremenu");
  if (box.hidden) return;
  box.hidden = true;
  box.replaceChildren();
  $("b-more").setAttribute("aria-expanded", "false");
  if (focusBack) $("b-more").focus();
}

// --- the keyboard ---

/** Whether the page is in use: shown (not the login), the editor in reach, and no question, Write window or Camera
 *  link report over it. */
function pageInUse() {
  return !!state && !$("app").hidden && !$("app").inert && !away.since;
}

/** The shortcuts, unless a text field has the keyboard: the text size (Cmd/Ctrl +, − and 0), and Undo and Redo
 *  (Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z, Cmd/Ctrl+Y) only while the page is in use, so a key on the login sends no request
 *  (one without the code counts as a wrong code) and none undoes an edit behind the window that is about it. Until
 *  the editor has answered an Undo or Redo, whatever the answer, the page is drawn again under a list of the settings
 *  that has the keyboard, so the list shows the value put back (`undoKeys`). True when the key was taken. */
function shortcut(e) {
  const a = document.activeElement;
  if (a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.isContentEditable)) return false;
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return false;
  const k = e.key.toLowerCase();
  if (k === "=" || k === "+") setFontScale(getFontScale() + 0.1);
  else if (k === "-" || k === "_") setFontScale(getFontScale() - 0.1);
  else if (k === "0") setFontScale(1.0);
  else if ((k === "z" || (k === "y" && !e.shiftKey)) && pageInUse()) {
    // `act` is async: a failure inside it ends its promise too, so the count always comes down again
    undoKeys += 1;
    act(k === "z" && !e.shiftKey ? "undo" : "redo").finally(() => { undoKeys -= 1; });
  } else return false;
  e.preventDefault();
  return true;
}

/** Tab stays within the window on top while the focus is in it (in a modal one, always). */
function keepTabInWindow(e) {
  const top = dialogs[dialogs.length - 1];
  if (!top || !(top.modal || top.box.contains(document.activeElement))) return;
  const all = [...top.box.querySelectorAll(FOCUSABLE)].filter((x) => x.getClientRects().length);
  if (!all.length) return;
  const i = all.indexOf(document.activeElement);
  if (e.shiftKey && i <= 0) { e.preventDefault(); all[all.length - 1].focus(); }
  else if (!e.shiftKey && (i === all.length - 1 || i < 0)) { e.preventDefault(); all[0].focus(); }
}

// --- the controls of the frame, wired once ---

/** A file input: the file chosen handed to `use`, and the input emptied, so the same file can be chosen again. */
function onFile(id, use) {
  $(id).addEventListener("change", () => {
    const f = $(id).files[0];
    $(id).value = "";
    if (f) use(f);
  });
}

$("login-form").addEventListener("submit", (e) => {
  e.preventDefault();
  code = $("code").value.trim();
  if (code) {
    session.forget();
    connect();
  }
});

// the toolbar
$("b-edit").addEventListener("click", () => cmpSetMode("edit"));
$("b-compare").addEventListener("click", () => cmpSetMode("compare"));
for (const [b, f] of [["b-open", "f-open"], ["b-open-a", "f-open-a"], ["b-open-b", "f-open-b"], ["b-open-base", "f-open-base"]]) {
  $(b).addEventListener("click", () => $(f).click());
}
onFile("f-open", (f) => replaceAct("open", {}, f, "Open a settings file", opening(f.name), "Open anyway"));
$("b-download").addEventListener("click", () => { if (!saysWhy($("b-download"))) downloadFile(); });
$("b-recent").addEventListener("change", () => {
  const sel = $("b-recent");
  const i = sel.value === "" ? -1 : Number(sel.value);
  sel.value = "";
  if (i >= 0) openRecent(i);
});
$("b-csv").addEventListener("click", () => downloadAnswer("csv", { target: view.target, q: view.q, only: view.only }, "settings.csv"));
$("b-backups").addEventListener("click", () => toggleWindow("backups"));
// a button greyed out says why when pressed (`greyOut`), Write's among them
$("b-undo").addEventListener("click", () => { if (!saysWhy($("b-undo"))) act("undo"); });
$("b-redo").addEventListener("click", () => { if (!saysWhy($("b-redo"))) act("redo"); });
$("b-history").addEventListener("click", () => { if (!saysWhy($("b-history"))) toggleWindow("history"); });
$("b-camera").addEventListener("click", () => openWindow("connect"));
$("b-read").addEventListener("click", () => { if (!saysWhy($("b-read"))) replaceAct("read", {}, null, "Read from camera", reading, "Read anyway"); });
$("b-send").addEventListener("click", () => { if (!saysWhy($("b-send"))) openSend(); });
$("b-more").addEventListener("click", () => { if ($("moremenu").hidden) openMore(true); else closeMore(true); });
menuKeys($("moremenu"), closeMore);
$("b-settings").addEventListener("click", () => toggleWindow("settings"));
$("b-font-dec").addEventListener("click", () => { if (!saysWhy($("b-font-dec"))) setFontScale(getFontScale() - 0.1); });
$("b-font-inc").addEventListener("click", () => { if (!saysWhy($("b-font-inc"))) setFontScale(getFontScale() + 0.1); });
new ResizeObserver(queueFit).observe($("top"));
new MutationObserver(queueFit).observe(bar1, { subtree: true, attributes: true, attributeFilter: ["hidden"], childList: true, characterData: true });

// the Editing row
$("search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  $("b-clear").hidden = !$("search").value;
  searchTimer = setTimeout(() => {
    view.q = $("search").value.trim();
    hits = null;
    drawSide();
    maybeDraw();
  }, 300);
});
// clearing the search box shows every row again; on the Memories page it also drops the words the page was opened
// with, so the page is drawn anew
$("b-clear").addEventListener("click", () => {
  if (view.page === "memories" && memView.q) {
    memView.q = "";
    drawn = null;
  }
  clearSearch();
  drawSide();
  maybeDraw();
});
$("only").addEventListener("change", () => {
  view.only = $("only").checked;
  drawSide();
  maybeDraw();
});

// the Compare bar
onFile("f-open-a", (f) => replaceAct("open", {}, f, "Open a settings file", opening(`${f.name} as file A`), "Open anyway"));
onFile("f-open-b", (f) => act("open_b", {}, f));
onFile("f-open-base", (f) => act("open_base", {}, f));
$("b-close-base").addEventListener("click", () => act("close_base"));
$("b-swap").addEventListener("click", () => { if (!saysWhy($("b-swap"))) act("swap_ab"); });
$("b-download-a").addEventListener("click", () => { if (!saysWhy($("b-download-a"))) downloadFile(); });
$("b-csv-cmp").addEventListener("click", () => saysWhy($("b-csv-cmp")) || downloadAnswer("csv",
  { target: view.target, compare: true, cols: cmp.cols, only_diff: cmpOnly(), raw: cmpRaw(), q: cmp.q, tab: cmp.tab || null }, "compare.csv"));
$("cmp-q").addEventListener("input", () => {
  clearTimeout(cmpSearchTimer);
  cmpSearchTimer = setTimeout(() => { cmp.q = $("cmp-q").value.trim(); maybeDraw(); }, 300);
});
$("cmp-tab").addEventListener("change", () => { cmp.tab = $("cmp-tab").value; maybeDraw(); });
$("cmp-only").addEventListener("change", () => { cmp.only = $("cmp-only").checked; cmp.kept = null; maybeDraw(); });
$("cmp-raw").addEventListener("change", () => { cmp.raw = $("cmp-raw").checked; maybeDraw(); });
$("cmp-records").addEventListener("change", () => { cmp.records = $("cmp-records").checked; render(); });
$("cmp-map").addEventListener("pointerdown", (e) => { e.preventDefault(); $("cmp-map").setPointerCapture(e.pointerId); cmpMapAt(e); });
$("cmp-map").addEventListener("pointermove", (e) => { if ($("cmp-map").hasPointerCapture(e.pointerId)) cmpMapAt(e); });

// the editor-closed notice, the Menu strip (a phone) and the status bar, which a phone cuts to one line: a tap shows
// all of it, the open file's name first
$("b-retry").addEventListener("click", () => {
  $("offline-why").textContent = "Trying again…";
  refresh();
});
$("side").addEventListener("scroll", stripEdges, { passive: true });
$("statusbar").addEventListener("click", () => {
  if (matchMedia("(max-width: 699px)").matches) $("statusbar").classList.toggle("open");
});
// the status bar's version opens Settings on its About tab, and leaves the status bar as it was
$("foot-version").addEventListener("click", (e) => {
  e.stopPropagation();
  openSettings(SETTINGS_ABOUT);
});

// how the focus is reached (`focusOrigin`): the last key or tap before it moved. A tap or a click elsewhere also ends
// keyboard use (Safari focuses no clicked button, so the focus would stay on a list reached with the keys), and a key
// that moves within a control (an arrow on a list clicked open) starts it; Enter and the text keys do not, so a phone's
// Go still lets go of a number box tapped into
const NAVIGATION_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"]);
document.addEventListener("keydown", (e) => {
  focusOrigin.last = "key";
  if (NAVIGATION_KEYS.has(e.key)) focusOrigin.keys = true;
}, true);
document.addEventListener("pointerdown", () => {
  focusOrigin.last = "pointer";
  focusOrigin.keys = false;
}, true);
document.addEventListener("focusin", () => { focusOrigin.keys = focusOrigin.last === "key"; }, true);

// the keyboard: Compare's keys first; Escape closes the My Menu pop-up, else the window on top; Tab stays in the
// window on top; then the shortcuts
document.addEventListener("keydown", (e) => {
  if (cmpKey(e) || e.defaultPrevented) return;
  if (e.key === "Escape") {
    const top = dialogs[dialogs.length - 1];
    if (!$("mymenu").hidden) hideMyMenu(true);
    else if (top && top.close) {
      e.preventDefault();
      top.close();
    }
  } else if (e.key === "Tab") keepTabInWindow(e);
  else shortcut(e);
});

// a tap or a click elsewhere closes the menus and the picker floating over the page
document.addEventListener("pointerdown", (e) => {
  const t = e.target;
  // (not a press on the column header the menu was opened from, which closes it itself)
  if (cmpMenuBox && !cmpMenuBox.contains(t) && !(cmpMenuFrom && cmpMenuFrom.classList && cmpMenuFrom.classList.contains("cmp-head") && cmpMenuFrom.contains(t))) cmpHideMenu();
  // the compare's picker too, unless the click is on its own cell (which closes it itself) or in a menu opened from it
  if (cmp.pick && !cmp.pick.box.contains(t) && !t.closest("td.cmp-v.take") && !(cmpMenuBox && cmpMenuBox.contains(t))) cmpPickClose();
  if (!$("mymenu").contains(t)) hideMyMenu(false);
  if (!$("moremenu").contains(t) && !$("b-more").contains(t)) closeMore(false);
}, true);
// a compare cell's menu closes when the page scrolls under it (not when the menu itself scrolls) or the window is
// resized; the change map, the toolbar and the Menu strip follow the window's size
document.addEventListener("scroll", (e) => {
  if (!(cmpMenuBox && cmpMenuBox.contains(e.target))) cmpHideMenu();
  cmpPlaceMap();
}, true);
window.addEventListener("resize", () => {
  cmpHideMenu();
  cmpPlaceMap();
  queueFit();
  stripEdges();
  placePopups();
});

// a file dropped on the page: opened with no file open, else compared as file B (the window's drop)
document.addEventListener("dragover", (e) => { if (e.dataTransfer && [...e.dataTransfer.types].includes("Files")) e.preventDefault(); });
document.addEventListener("drop", (e) => {
  if (!e.dataTransfer || !e.dataTransfer.files.length) return;
  e.preventDefault();
  if (!$("app").hidden && state) cmpDrop([...e.dataTransfer.files]);
});

document.addEventListener("visibilitychange", () => { if (!document.hidden && !$("app").hidden) refresh(); });

// --- start ---

setPageTheme(pageTheme());
setPageDensity(pageDensity());
setFontScale(getFontScale());
$("login-where").textContent = WEB_SETTINGS;
// a link with the code after # fills it in; the code is then taken out of the address
const fromLink = /[#&]code=([A-Za-z0-9-]+)/.exec(location.hash);
if (fromLink) history.replaceState(null, "", location.pathname + location.search);
session.load();
code = fromLink ? fromLink[1] : session.token ? null : store.get("code");
if (fromLink) session.forget();
if (code || session.token) connect(); else showLogin("");
