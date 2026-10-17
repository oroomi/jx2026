/* Aava's conversation (PROJECT_RULES D61). Loaded only when the server has a model key (the script tag is not in the page otherwise), and does
   nothing unless the demo flag is on (window.AAVA_DEMO, set by _aava.html) and GET /api/aava/status says available.
   Home page: the Ask bar becomes a conversation (message list under the bar, streamed answers, follow-up chips, Clear). Company page: an
   "Ask a follow-up" input under the six questions opens the same conversation in a sheet with that company as context.
   The server speaks Server-Sent Events (status, delta, action, entities, followups, done, error); this file reads them with fetch.
   Companies are links: when the row is on the home list the page scrolls to it and marks it, else the company page opens.
   Filters: an apply_filters action goes to window.radarFilters.apply, a thin adapter over window.Filters (radar/static/filters.js, the in-place
   filter state synced to the address bar); where that is missing it sets location.search. No library; all text is set with textContent. */
(function () {
  "use strict";
  if (window.AavaChat || !window.AAVA_DEMO) return;
  var KEY = "aava_chat_v1", MAX_TURNS = 12, MAX_IN = 500;
  var $ = function (id) { return document.getElementById(id); };
  var reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var askRoot = $("ask"), aavaRoot = $("aava");
  var companyKey = "", companyName = "";
  if (aavaRoot && aavaRoot.dataset.kind === "company") {
    var m = /\/aava\/script\/(.+)$/.exec(aavaRoot.dataset.script || "");
    companyKey = m ? decodeURIComponent(m[1]) : "";
    var h1 = document.querySelector("main h1");
    companyName = h1 ? h1.textContent.trim() : "";
  }
  if (!askRoot && !companyKey) return;

  /* ---- small DOM helpers ------------------------------------------------------------------------------------------------------ */
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function linkNode(label, url) {
    var a = document.createElement("a"), co = /^\/c\/([^?#\s]+)/.exec(url);
    a.textContent = label;
    if (co) { a.href = "/c/" + co[1]; a.className = "chat-co"; try { a.dataset.key = decodeURIComponent(co[1]); } catch (e) { a.dataset.key = co[1]; } }
    else if (/^\/[^\/\\]/.test(url)) { a.href = url; }
    else if (/^https:\/\//i.test(url)) { a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.className = "chat-src"; }
    else return document.createTextNode(label);
    return a;
  }
  function inline(parent, s) {
    var re = /\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|\[([^\]\n]+)\]\(([^)\s]+)\)/g, last = 0, m;
    while ((m = re.exec(s))) {
      if (m.index > last) parent.appendChild(document.createTextNode(s.slice(last, m.index)));
      parent.appendChild(m[1] != null ? el("strong", null, m[1]) : m[2] != null ? el("em", null, m[2]) : linkNode(m[3], m[4]));
      last = re.lastIndex;
    }
    if (last < s.length) parent.appendChild(document.createTextNode(s.slice(last)));
  }
  function blocks(host, text) {
    host.textContent = "";
    String(text || "").split(/\n{2,}/).forEach(function (block) {
      var lines = block.split("\n").filter(function (l) { return l.trim(); });
      if (!lines.length) return;
      if (lines.every(function (l) { return /^\s*[-*] /.test(l); })) {
        var ul = el("ul");
        lines.forEach(function (l) { var li = el("li"); inline(li, l.replace(/^\s*[-*] /, "")); ul.appendChild(li); });
        host.appendChild(ul);
      } else {
        var p = el("p");
        lines.forEach(function (l, i) { if (i) p.appendChild(document.createElement("br")); inline(p, l); });
        host.appendChild(p);
      }
    });
  }
  function plain(text) { return String(text || "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*/g, "").replace(/^\s*[-*] /gm, "").replace(/\s+/g, " ").trim(); }
  function safeJson(s) { try { return JSON.parse(s); } catch (e) { return null; } }

  /* ---- the filters adapter ------------------------------------------------------------------------------------------------------ */
  window.radarFilters = window.radarFilters || {
    apply: function (change) {
      change = change || {};
      if (window.Filters && window.Filters.apply) {
        var c = { filters: change.filters || {}, group: change.group || "" };
        if (change.for) c.for = change.for;                    /* the Top matching tab for one investor or accelerator */
        return window.Filters.apply(c);
      }
      var q = new URLSearchParams(location.search);
      ["verdict", "impact", "trl", "brl", "irl", "fit", "country", "sector", "age", "source", "src", "deadline", "member", "group"].forEach(function (k) { q.delete(k); });
      Object.keys(change.filters || {}).forEach(function (k) { [].concat(change.filters[k]).forEach(function (v) { q.append(k, v); }); });
      if (change.group) q.set("group", change.group);
      if (change.for) q.set("for", change.for);
      location.assign("/" + (q.toString() ? "?" + q.toString() : ""));
      return Promise.resolve(false);
    }
  };
  function describe(f) {
    var parts = Object.keys(f || {}).map(function (k) { return k + " " + [].concat(f[k]).join(" or "); });
    return parts.length ? parts.join(", ") : "all filters cleared";
  }

  /* ---- what the page shows right now, sent with each question ----------------------------------------------------------------- */
  function currentView() {
    var list = $("hc-list"), st = { filters: {}, group: "" };
    try { if (window.Filters && window.Filters.read) st = window.Filters.read(); } catch (e) {}
    var rows = list ? [].slice.call(list.querySelectorAll(".hc-rows > li[data-key]")) : [];
    return { filters: st.filters || {}, group: st.group || "", count: rows.length, rows: rows.slice(0, 20).map(function (r) { return r.dataset.key; }) };
  }
  function thesisId() {
    var l = $("hc-list");
    return (l && l.dataset.thesis) || (askRoot && askRoot.dataset.thesis) || new URLSearchParams(location.search).get("thesis") || "";
  }

  /* ---- the row a company name points at ---------------------------------------------------------------------------------------- */
  function rowFor(key) {
    var list = $("hc-list");
    if (!list || !key) return null;
    return [].slice.call(list.querySelectorAll(".hc-rows > li[data-key]")).filter(function (r) { return r.dataset.key === key; })[0] || null;
  }
  function pick(row) {
    var a = row.querySelector("a.hc-row");
    row.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    row.classList.add("is-picked");
    if (a) a.focus({ preventScroll: true });
    setTimeout(function () { row.classList.remove("is-picked"); }, 2800);
  }

  /* ---- the conversation: state and storage -------------------------------------------------------------------------------------- */
  var msgs = [], busy = false, ctl = null, status = { available: false, tts: false }, panels = [];
  try { var saved = safeJson(sessionStorage.getItem(KEY)); if (saved && Array.isArray(saved.msgs)) msgs = saved.msgs.slice(-MAX_TURNS); } catch (e) {}
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify({ msgs: msgs.slice(-MAX_TURNS) })); } catch (e) {} }

  /* ---- one panel (the home bar's, or the company sheet's) ------------------------------------------------------------------- */
  function Panel(host, opts) {
    var self = this;
    this.host = host; this.opts = opts || {};
    host.classList.add("chat");
    host.setAttribute("aria-label", "Conversation with Aava");
    var head = el("div", "chat-head");
    head.appendChild(el("span", "chat-title", this.opts.title || "Conversation with Aava"));
    var clear = el("button", "chat-clear", "Clear conversation"); clear.type = "button";
    head.appendChild(clear);
    this.log = el("div", "chat-log"); this.log.setAttribute("role", "log"); this.log.setAttribute("aria-live", "polite");
    this.fu = el("div", "chat-fu");
    host.appendChild(head); host.appendChild(this.log); host.appendChild(this.fu);
    clear.addEventListener("click", function () { api.clear(); });
    host.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a.chat-co");
      if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
      var row = rowFor(a.dataset.key);
      if (row) { e.preventDefault(); pick(row); }
    });
    host.addEventListener("keydown", function (e) { if (e.key === "Escape" && busy) { e.stopPropagation(); api.stop(); } });
    panels.push(this);
    msgs.forEach(function (m) { self.add(m.role, m.content); });
    this.refresh();
  }
  Panel.prototype.refresh = function () { this.host.hidden = !msgs.length && !busy; };
  Panel.prototype.add = function (role, text) {
    var box = el("div", "chat-m " + (role === "user" ? "chat-u" : "chat-a"));
    if (role === "user") { box.appendChild(el("p", null, text)); }
    else { box.appendChild(el("span", "chat-who", "Aava")); var body = el("div", "chat-body"); blocks(body, text); box.appendChild(body); if (text) this.listen(box, text); }
    this.log.appendChild(box); this.scroll(); this.refresh();
    return box;
  };
  Panel.prototype.listen = function (box, text) {
    if (!(window.AskBar && window.AskBar.speak)) return;
    var b = el("button", "chat-listen", "Listen"); b.type = "button";
    b.addEventListener("click", function () {
      if (b.classList.contains("is-on")) { window.AskBar.stopSpeech(); b.classList.remove("is-on"); b.textContent = "Listen"; return; }
      b.classList.add("is-on"); b.textContent = "Stop";
      api.audioFor(plain(text)).then(function (url) {
        window.AskBar.speak({ say: plain(text), segments: [], audio_dir: null, blob_url: url }, { onEnd: function () { b.classList.remove("is-on"); b.textContent = "Listen"; } });
      });
    });
    box.appendChild(b);
  };
  Panel.prototype.scroll = function () { var h = this.host; if (h.scrollHeight > h.clientHeight && h.classList.contains("chat-sheet-body")) h.scrollTop = h.scrollHeight; };
  Panel.prototype.chips = function (qs) {
    var fu = this.fu, withCompany = !!this.opts.company; fu.textContent = "";
    (qs || []).forEach(function (q) {
      var b = el("button", "chat-chip", q); b.type = "button";
      b.addEventListener("click", function () { api.send(q, { withCompany: withCompany }); });
      fu.appendChild(b);
    });
  };

  /* ---- the stream --------------------------------------------------------------------------------------------------------------- */
  function readStream(resp, on) {
    var reader = resp.body.getReader(), dec = new TextDecoder("utf-8"), buf = "";
    function pump() {
      return reader.read().then(function (r) {
        if (r.done) { if (buf.trim()) flush(buf); return; }
        buf += dec.decode(r.value, { stream: true });
        var i;
        while ((i = buf.indexOf("\n\n")) >= 0) { flush(buf.slice(0, i)); buf = buf.slice(i + 2); }
        return pump();
      });
    }
    function flush(block) {
      var ev = "message", data = [];
      block.split("\n").forEach(function (l) { if (l.indexOf("event: ") === 0) ev = l.slice(7); else if (l.indexOf("data: ") === 0) data.push(l.slice(6)); });
      var d = safeJson(data.join("\n"));
      if (d && on[ev]) on[ev](d);
    }
    return pump();
  }

  var api = {
    ready: false,
    active: function () { return api.ready && status.available; },
    stop: function () { if (ctl) ctl.abort(); },
    clear: function () {
      api.stop(); msgs = []; save();
      panels.forEach(function (p) { p.log.textContent = ""; p.chips([]); p.refresh(); });
    },
    /* Speak a chat answer: ElevenLabs through the server when it is configured, else resolves null and the browser voice is used. */
    audioFor: function (text) {
      if (!status.tts || !text) return Promise.resolve(null);
      return fetch("/api/aava/tts", { method: "POST", headers: { "Content-Type": "application/json", "X-Aava-Demo": "1" }, body: JSON.stringify({ text: text }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.blob(); })
        .then(function (b) { return URL.createObjectURL(b); })
        .catch(function () { return null; });
    },
    /* Ask. Resolves with {text, plain, keys, items, fallback} when the answer is complete, or null when it was stopped or never arrived. */
    send: function (q, o) {
      o = o || {};
      q = String(q || "").replace(/\s+/g, " ").trim().slice(0, MAX_IN);
      if (!q) return Promise.resolve(null);
      if (busy) api.stop();
      var targets = panels.filter(function (p) { return p.opts.visible ? p.opts.visible() : true; });
      if (!targets.length) targets = panels;
      msgs.push({ role: "user", content: q }); msgs = msgs.slice(-MAX_TURNS); save();
      var boxes = targets.map(function (p) { p.chips([]); p.add("user", q); var b = p.add("assistant", ""); b.setAttribute("aria-busy", "true"); b.classList.add("is-thinking"); return { p: p, box: b, body: b.querySelector(".chat-body") }; });
      boxes.forEach(function (x) { x.status = el("p", "chat-status"); x.status.appendChild(dots()); x.label = el("span", null, "Aava is thinking"); x.status.appendChild(x.label); x.box.appendChild(x.status); });
      if (askRoot) askRoot.classList.add("is-thinking");
      busy = true; ctl = new AbortController();
      var raw = "", note = "", acts = [], final = null, followups = [], failed = false, frame = 0;
      function paint() { frame = 0; boxes.forEach(function (x) { if (note) { var n = el("p", "chat-note", note); } blocks(x.body, raw); if (note) x.body.insertBefore(n, x.body.firstChild); x.p.scroll(); }); }
      function queue() { if (!frame) frame = requestAnimationFrame(paint); }
      function label(t) { boxes.forEach(function (x) { if (x.label) x.label.textContent = t; }); if (o.onStatus) o.onStatus(t); }
      var body = { messages: msgs.slice(-MAX_TURNS).map(function (m) { return { role: m.role, content: m.content }; }), view: currentView(), thesis: thesisId() };
      if (companyKey && o.withCompany) body.company = companyKey;
      var handlers = {
        status: function (d) { label(d.label ? "Aava is " + d.label : d.state === "tool" ? "Aava is using " + d.tool : "Aava is thinking"); },
        delta: function (d) { raw += d.text; queue(); },
        action: function (d) {
          acts.push(d);
          Promise.resolve(window.radarFilters.apply(d)).catch(function () {});
        },
        error: function (d) { failed = true; raw = ""; note = d.message || "Aava's reasoning is not available right now."; queue(); },
        entities: function () {},
        followups: function (d) { followups = d.questions || []; },
        done: function (d) { final = d; }
      };
      var posted = fetch("/api/aava/chat", { method: "POST", signal: ctl.signal, headers: { "Content-Type": "application/json", "X-Aava-Demo": "1", Accept: "text/event-stream" }, body: JSON.stringify(body) })
        .then(function (r) {
          var type = r.headers.get("content-type") || "";
          if (type.indexOf("text/event-stream") < 0) return r.json().catch(function () { return {}; }).then(function (j) { throw new Error(j.error || "Aava is not available (" + r.status + ")"); });
          return readStream(r, handlers);
        });
      return posted.then(function () {
        if (!final) throw new Error("the answer stopped early");
        if (frame) cancelAnimationFrame(frame);
        var text = final.text || raw;
        raw = text; paint();
        boxes.forEach(function (x) {
          x.box.removeAttribute("aria-busy"); x.box.classList.remove("is-thinking"); x.status.remove();
          x.p.listen(x.box, text);
          if (acts.length) { var last = acts[acts.length - 1]; x.box.appendChild(el("p", "chat-act", "Applied to the list: " + describe(last.filters) + (last.for ? ", top matching for " + last.for : "") + (typeof last.matches === "number" ? " (" + last.matches + " shown)" : ""))); }
          if (final.sources && final.sources.length) x.box.appendChild(sourcesLine(final.sources));
          if (final.unverified && final.unverified.length) x.box.appendChild(el("p", "chat-note", "Not from the records Aava looked at, treat as unverified: " + final.unverified.join(", ") + "."));
          x.p.chips(followups);
        });
        msgs.push({ role: "assistant", content: text }); msgs = msgs.slice(-MAX_TURNS); save();
        var items = (final.keys || []).map(function (k) { return { label: nameOf(text, k), url: "/c/" + encodeURIComponent(k) }; });
        return { text: text, plain: plain(text), keys: final.keys || [], items: items, fallback: !!final.fallback || failed };
      }).catch(function (e) {
        if (frame) cancelAnimationFrame(frame);
        var aborted = e && e.name === "AbortError";
        boxes.forEach(function (x) {
          x.box.removeAttribute("aria-busy"); x.box.classList.remove("is-thinking"); x.status.remove();
          if (aborted) { if (!raw) x.box.remove(); else { blocks(x.body, raw); x.body.appendChild(el("p", "chat-note", "Stopped.")); } }
          else { x.body.textContent = ""; x.body.appendChild(el("p", "chat-note", "Aava could not reach the records just now. Try again, or search the radar.")); }
        });
        if (aborted && raw) msgs.push({ role: "assistant", content: raw }); else msgs.pop();   /* a question with no answer is not kept */
        save();
        return null;
      }).then(function (res) {
        busy = false; ctl = null;
        if (askRoot) askRoot.classList.remove("is-thinking");
        panels.forEach(function (p) { p.refresh(); });
        return res;
      });
    }
  };
  /* The records behind the answer, as links the server took from its tool results: "Sources: Viva Jets Oy: PRH register, Business Finland export". */
  function sourcesLine(list) {
    var p = el("p", "chat-sources");
    p.appendChild(el("span", "chat-sources-h", "Sources "));
    list.forEach(function (g, i) {
      var span = el("span", "chat-sources-g");
      span.appendChild(document.createTextNode(g.name + ": "));
      (g.links || []).forEach(function (l, j) {
        if (j) span.appendChild(document.createTextNode(", "));
        var a = linkNode(l.label, l.url);
        if (a.nodeType === 1) { a.classList.remove("chat-co"); a.classList.add("chat-src"); if (/^\//.test(l.url)) { a.removeAttribute("target"); } }
        span.appendChild(a);
      });
      p.appendChild(span);
      if (i < list.length - 1) p.appendChild(document.createTextNode(" · "));
    });
    return p;
  }
  function nameOf(text, key) {
    var m = new RegExp("\\[([^\\]]+)\\]\\(/c/" + key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\)").exec(text);
    return m ? m[1] : key;
  }
  function dots() { var d = el("span", "ask-dots"); d.setAttribute("aria-hidden", "true"); for (var i = 0; i < 3; i++) d.appendChild(el("i")); return d; }
  window.AavaChat = api;

  /* ---- mount ------------------------------------------------------------------------------------------------------------------- */
  function mount() {
    if (askRoot) {
      var host = el("section", "chat chat-home"); host.id = "aava-chat"; host.hidden = true;
      var card = $("ask-card");
      askRoot.insertBefore(host, card || null);
      new Panel(host, { title: "Conversation with Aava" });
      document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape" || e.defaultPrevented) return;
        if (busy && askRoot.contains(document.activeElement)) { api.stop(); }
      });
    }
    if (companyKey) mountCompany();
    api.ready = true;
    document.documentElement.classList.add("aava-chat-on");
    if (askRoot) {
      var sub = askRoot.querySelector(".ask-sub");
      if (sub) sub.textContent = "Ask about any company on this radar, or ask Aava to narrow the list. It reasons from the public records on file and every name it gives links to the record.";
    }
  }

  function mountCompany() {
    var form = $("aava-follow"), input = $("aava-follow-q");
    if (!form || !input) return;
    form.hidden = false;
    var sheet = el("section", "chat-sheet"); sheet.id = "aava-chat-sheet"; sheet.hidden = true;
    sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-modal", "false"); sheet.setAttribute("aria-label", "Ask Aava about " + (companyName || "this company"));
    var top = el("div", "chat-sheet-top");
    top.appendChild(el("span", "chat-sheet-title", "Ask Aava" + (companyName ? " about " + companyName : "")));
    var close = el("button", "chat-close", "Close"); close.type = "button"; top.appendChild(close);
    var body = el("div", "chat-sheet-body");
    var form2 = el("form", "chat-sheet-form"); form2.setAttribute("autocomplete", "off");
    var in2 = el("input"); in2.type = "text"; in2.maxLength = MAX_IN; in2.placeholder = "Ask a follow-up"; in2.setAttribute("aria-label", "Ask a follow-up");
    var go = el("button", "chat-go", "Ask"); go.type = "submit";
    form2.appendChild(in2); form2.appendChild(go);
    sheet.appendChild(top); sheet.appendChild(body); sheet.appendChild(form2);
    document.body.appendChild(sheet);
    var panel = new Panel(body, { title: companyName ? "About " + companyName : "Conversation", company: true, visible: function () { return !sheet.hidden; } });
    panel.host.hidden = false;
    var opener = null;
    function open(q) {
      opener = document.activeElement;
      var narr = $("aava-sheet"); if (narr && !narr.hidden && $("aava-close")) $("aava-close").click();
      sheet.hidden = false; document.documentElement.classList.add("chat-sheet-open");
      if (q) api.send(q, { withCompany: true }); else in2.focus();
    }
    function shut() { api.stop(); sheet.hidden = true; document.documentElement.classList.remove("chat-sheet-open"); if (opener && opener.focus) opener.focus(); }
    form.addEventListener("submit", function (e) { e.preventDefault(); var q = input.value.trim(); input.value = ""; open(q); });
    form2.addEventListener("submit", function (e) { e.preventDefault(); var q = in2.value.trim(); in2.value = ""; if (q) api.send(q, { withCompany: true }); });
    close.addEventListener("click", shut);
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || sheet.hidden || e.defaultPrevented) return;
      if (busy) api.stop(); else shut();
    });
  }

  fetch("/api/aava/status", { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : { available: false }; })
    .then(function (s) { status = s || status; if (status.available) mount(); })
    .catch(function () {});
})();
