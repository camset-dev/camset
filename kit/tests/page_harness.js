"use strict";
// The web page's script (editor/web/app.js) run under node, without a browser, for kit/tests/test_page_script.py:
//   node page_harness.js <app.js> <test.js>
// The script is evaluated whole, as the browser loads it, in a context with the few things it touches: a small DOM
// (elements with children, attributes, classes, dataset, listeners and a selector matcher for the selectors the page
// uses), localStorage, location, history, timers and a fetch that answers nothing. The page starts as with no access
// code: it shows its login and asks the editor nothing. The test script then runs in the same context, so it sees the
// page's functions and its state (`state`, `view`, `cmp`, `openGroups`, `xp`) by name, can stub a function the page
// declares (`drawSide = () => {}`) and prints its findings as JSON. No npm package: node's own vm and fs only.

const fs = require("fs");
const vm = require("vm");

class Text {
  constructor(s) { this.data = String(s); this.parentNode = null; this.nodeType = 3; }
  get textContent() { return this.data; }
}

/** A selector of the kinds the page uses: compounds (tag, #id, .class, [attr], [attr="v"], :not(…), :disabled) joined by
 *  spaces or ">"; any other pseudo-class (:scope, :focus-visible) matches every element. */
function parse(sel) {
  return sel.split(",").map((one) => {
    const steps = [];
    let comb = " ";
    for (const tok of one.trim().match(/>|[^\s>]+(?:\[[^\]]*\])*/g) || []) {
      if (tok === ">") { comb = ">"; continue; }
      const c = { comb, tag: null, id: null, cls: [], attrs: [], not: [] };
      const re = /^[a-zA-Z][\w-]*|#[\w-]+|\.[\w-]+|\[([\w-]+)(?:="([^"]*)"|='([^']*)')?\]|:not\(([^)]*)\)|:[\w-]+/g;
      let m;
      while ((m = re.exec(tok))) {
        const t = m[0];
        if (t[0] === "#") c.id = t.slice(1);
        else if (t[0] === ".") c.cls.push(t.slice(1));
        else if (t[0] === "[") c.attrs.push([m[1], m[2] ?? m[3]]);
        else if (t.startsWith(":not(")) c.not.push(m[4]);
        else if (t === ":disabled") c.attrs.push(["disabled", undefined]);
        else if (t[0] === ":") { /* :scope, :focus-visible and the like: not told apart here */ }
        else c.tag = t.toUpperCase();
      }
      steps.push(c);
      comb = " ";
    }
    return steps;
  });
}

function matchOne(e, c) {
  if (!(e instanceof Element)) return false;
  if (c.tag && e.tagName !== c.tag) return false;
  if (c.id && e.id !== c.id) return false;
  for (const k of c.cls) if (!e.classList.contains(k)) return false;
  for (const [a, v] of c.attrs) if (!e.hasAttribute(a) || (v !== undefined && e.getAttribute(a) !== v)) return false;
  for (const n of c.not) if (e.matches(n)) return false;
  return true;
}

function matchSteps(e, steps, i = steps.length - 1) {
  if (!matchOne(e, steps[i])) return false;
  if (i === 0) return true;
  if (steps[i].comb === ">") return !!e.parentElement && matchSteps(e.parentElement, steps, i - 1);
  for (let p = e.parentElement; p; p = p.parentElement) if (matchSteps(p, steps, i - 1)) return true;
  return false;
}

class ClassList {
  constructor(e) { this.e = e; }
  get set() { return new Set((this.e.getAttribute("class") || "").split(/\s+/).filter(Boolean)); }
  write(s) { this.e.setAttribute("class", [...s].join(" ")); }
  contains(k) { return this.set.has(k); }
  add(...ks) { const s = this.set; ks.forEach((k) => s.add(k)); this.write(s); }
  remove(...ks) { const s = this.set; ks.forEach((k) => s.delete(k)); this.write(s); }
  toggle(k, on) { const s = this.set; const want = on === undefined ? !s.has(k) : !!on; if (want) s.add(k); else s.delete(k); this.write(s); return want; }
}

class Element {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.childNodes = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = {};
    this.style = { setProperty(p, v) { this[p] = v; }, removeProperty(p) { delete this[p]; } };
    this.classList = new ClassList(this);
    this.dataset = new Proxy({}, {
      get: (_, k) => (typeof k === "string" ? this.getAttribute("data-" + k.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase())) ?? undefined : undefined),
      set: (_, k, v) => { this.setAttribute("data-" + String(k).replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()), v); return true; },
    });
    this.checked = false;
    this.value = "";
    this.offsetWidth = 0;
    this.offsetHeight = 0;
    this.clientWidth = 0;
    this.scrollTop = 0;
    this.spaceDown = false;   // a Space keydown not prevented, which the Space keyup then turns into a click
  }
  get id() { return this.getAttribute("id") || ""; }
  set id(v) { this.setAttribute("id", v); }
  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }
  get title() { return this.getAttribute("title") || ""; }
  set title(v) { this.setAttribute("title", v); }
  get open() { return this.hasAttribute("open"); }
  get hidden() { return this.hasAttribute("hidden"); }
  set hidden(v) { this.toggleAttribute("hidden", !!v); }
  get disabled() { return this.hasAttribute("disabled"); }
  set disabled(v) { this.toggleAttribute("disabled", !!v); }
  set open(v) { if (v) this.setAttribute("open", ""); else this.removeAttribute("open"); }
  setAttribute(k, v) { this.attributes.set(k, String(v)); }
  getAttribute(k) { return this.attributes.has(k) ? this.attributes.get(k) : null; }
  hasAttribute(k) { return this.attributes.has(k); }
  removeAttribute(k) { this.attributes.delete(k); }
  toggleAttribute(k, on) { const want = on === undefined ? !this.hasAttribute(k) : !!on; if (want) this.setAttribute(k, ""); else this.removeAttribute(k); return want; }
  get children() { return this.childNodes.filter((n) => n instanceof Element); }
  get childElementCount() { return this.children.length; }
  get firstChild() { return this.childNodes[0] || null; }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { const c = this.children; return c[c.length - 1] || null; }
  get parentElement() { return this.parentNode instanceof Element ? this.parentNode : null; }
  sibling(d) {
    if (!this.parentNode) return null;
    const c = this.parentNode.children;
    return c[c.indexOf(this) + d] || null;
  }
  get previousElementSibling() { return this.sibling(-1); }
  get nextElementSibling() { return this.sibling(1); }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(""); }
  set textContent(v) { this.replaceChildren(String(v ?? "")); }
  get innerText() { return this.textContent; }
  set innerHTML(v) { this.replaceChildren(); }
  adopt(k) {
    const n = k instanceof Element || k instanceof Text ? k : new Text(k);
    if (n.parentNode) n.parentNode.childNodes.splice(n.parentNode.childNodes.indexOf(n), 1);
    n.parentNode = this;
    return n;
  }
  append(...ks) { for (const k of ks) this.childNodes.push(this.adopt(k)); }
  appendChild(k) { this.append(k); return k; }
  prepend(...ks) { this.childNodes.unshift(...ks.map((k) => this.adopt(k))); }
  insertBefore(k, ref) {
    const n = this.adopt(k);
    const i = ref ? this.childNodes.indexOf(ref) : -1;
    if (i < 0) this.childNodes.push(n); else this.childNodes.splice(i, 0, n);
    return k;
  }
  removeChild(k) { this.childNodes.splice(this.childNodes.indexOf(k), 1); k.parentNode = null; return k; }
  replaceChildren(...ks) { for (const n of this.childNodes) n.parentNode = null; this.childNodes = []; this.append(...ks); }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  replaceWith(n) {
    const p = this.parentNode;
    if (!p) return;
    const i = p.childNodes.indexOf(this);
    this.parentNode = null;
    p.childNodes.splice(i, 1);
    p.childNodes.splice(i, 0, p.adopt(n));
  }
  before(n) { if (this.parentNode) this.parentNode.insertBefore(n, this); }
  after(n) { if (this.parentNode) this.parentNode.insertBefore(n, this.nextElementSibling); }
  contains(n) { for (let x = n; x; x = x.parentNode) if (x === this) return true; return false; }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  removeEventListener(t, f) { this.listeners[t] = (this.listeners[t] || []).filter((x) => x !== f); }
  // one event for every listener, so a listener's preventDefault is seen after them all: a button not prevented then
  // does what a browser's does, Enter on keydown turned into a click, and Space on keyup, only after a Space keydown on
  // the same button that was not prevented (`spaceDown`)
  dispatchEvent(ev) {
    ev.target ||= this;
    const e = { currentTarget: this, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, stopPropagation() {}, ...ev };
    for (const f of this.listeners[ev.type] || []) f.call(this, e);
    if (this.tagName === "BUTTON" && ev.key === " " && (ev.type === "keydown" || ev.type === "keyup")) {
      const armed = this.spaceDown;
      this.spaceDown = ev.type === "keydown" && !e.defaultPrevented;
      if (ev.type === "keyup" && armed && !this.disabled && !e.defaultPrevented) this.click();
    } else if (this.tagName === "BUTTON" && !this.disabled && !e.defaultPrevented && ev.type === "keydown" && ev.key === "Enter") this.click();
    return true;
  }
  click() { this.dispatchEvent({ type: "click" }); }
  // as a browser's: focus fires focus on the element, then focusin (the page tells from it how the focus was reached),
  // and blur gives it to the body
  focus() {
    doc.activeElement = this;
    this.dispatchEvent({ type: "focus" });
    for (const f of doc.listeners.focusin || []) f({ type: "focusin", target: this });
  }
  blur() { if (doc.activeElement === this) doc.activeElement = body; }
  select() {}
  scrollIntoView() { this.scrolledTo = true; }
  getBoundingClientRect() { return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 }; }
  // no box for an element hidden itself or under a hidden one, one box for any other (as the window's Tab trap asks)
  getClientRects() { for (let x = this; x instanceof Element; x = x.parentNode) if (x.hidden) return []; return [this.getBoundingClientRect()]; }
  matches(sel) { return parse(sel).some((steps) => matchSteps(this, steps)); }
  closest(sel) { for (let x = this; x instanceof Element; x = x.parentNode) if (x.matches(sel)) return x; return null; }
  *all() { for (const c of this.children) { yield c; yield* c.all(); } }
  querySelectorAll(sel) { const ss = parse(sel); return [...this.all()].filter((e) => ss.some((steps) => matchSteps(e, steps))); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  showModal() { this.open = true; }
  close() { this.open = false; }
}

/** The document: the page's elements by id are made on first ask and kept, so a test can look at what was drawn. */
const byId = new Map();
const pageTags = new Map();
const root = new Element("html");
const body = new Element("body");
root.append(body);
const doc = {
  documentElement: root,
  body,
  activeElement: null,
  hidden: false,
  listeners: {},
  // of the tag index.html gives it (a button is a BUTTON, a list a SELECT), a DIV for an id the page does not have
  getElementById(id) {
    if (!byId.has(id)) { const e = new Element(pageTags.get(id) || "div"); e.id = id; body.append(e); byId.set(id, e); }
    return byId.get(id);
  },
  createElement: (t) => new Element(t),
  createElementNS: (_, t) => new Element(t),
  createTextNode: (s) => new Text(s),
  createDocumentFragment: () => new Element("#fragment"),
  querySelectorAll: (sel) => root.querySelectorAll(sel),
  querySelector: (sel) => root.querySelector(sel),
  contains: (n) => root.contains(n),
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); },
  removeEventListener() {},
};

const kept = new Map();
const fetches = [];
const sandbox = {
  console,
  document: doc,
  localStorage: {
    getItem: (k) => (kept.has(k) ? kept.get(k) : null),
    setItem: (k, v) => kept.set(k, String(v)),
    removeItem: (k) => kept.delete(k),
  },
  location: { hash: "", pathname: "/", search: "", origin: "http://localhost", href: "http://localhost/", reload() {} },
  history: { replaceState() {} },
  navigator: { userAgent: "node", clipboard: { writeText: async () => {} } },
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
  getComputedStyle: () => ({ display: "block", getPropertyValue: () => "" }),
  requestAnimationFrame: (f) => setTimeout(f, 0),
  ResizeObserver: class { observe() {} disconnect() {} },
  MutationObserver: class { observe() {} disconnect() {} },
  IntersectionObserver: class { observe() {} disconnect() {} },
  CSS: { escape: (s) => String(s).replace(/["\\]/g, "\\$&") },
  innerWidth: 1280,
  innerHeight: 800,
  setTimeout, clearTimeout, setInterval, clearInterval,
  URL, URLSearchParams, Blob: class {}, FormData: class { append() {} }, TextEncoder, TextDecoder,
  // the editor answers nothing: a test that needs an answer puts its own fetch in place
  fetch: (url, init) => { fetches.push([String(url), init]); return new Promise(() => {}); },
  __fetches: fetches,
  __Element: Element,
  addEventListener() {},
  removeEventListener() {},
};
sandbox.window = sandbox;
sandbox.self = sandbox;
vm.createContext(sandbox);

const [app, test] = process.argv.slice(2);
// the tag of each element of index.html (beside the script), by id
const pageFile = require("path").join(require("path").dirname(app), "index.html");
for (const m of (fs.existsSync(pageFile) ? fs.readFileSync(pageFile, "utf8") : "").matchAll(/<([a-zA-Z][\w-]*)\b[^>]*?\sid="([^"]+)"/g)) pageTags.set(m[2], m[1]);
vm.runInContext(fs.readFileSync(app, "utf8"), sandbox, { filename: app });
const done = vm.runInContext(fs.readFileSync(test, "utf8"), sandbox, { filename: test });
// a test that awaits returns its promise; the process ends when it settles, whatever timers the page left
Promise.resolve(done).then(() => process.exit(0), (e) => { console.error(e && e.stack || e); process.exit(1); });
