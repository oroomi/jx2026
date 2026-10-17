/* Weigh the reasons (PROJECT_RULES D90). Reorders a startup's counterparts on /match by the visitor's weights.
   Rule: the sum of the weights over the reasons that hold (no record counts 0), ties in the server's order; all weights zero keeps the
   server's order. With the thesis file's weights this is the server's order exactly. No total is ever printed: each row gets a bar whose
   segments are its reasons, as wide as their weights, and a line naming the reasons that hold. The weights live in the URL (?w=...).
   Without this script the panel stays hidden and the list keeps the server's order. */
(function () {
  "use strict";
  var panel = document.getElementById("mw"), dataEl = document.getElementById("mw-data");
  if (!panel || !dataEl) return;
  var D;
  try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var list = panel.nextElementSibling;
  while (list && !(list.classList && list.classList.contains("mt-results"))) list = list.nextElementSibling;
  if (!list || !D.rows || !D.rows.length) return;

  var KEYS = D.keys, LABELS = D.labels, SHOWN = D.shown, rows = D.rows, byId = {}, els = {};
  rows.forEach(function (r, i) { r.i = i; byId[r.id] = r; });

  function orgId(a) {
    try { return new URL(a.getAttribute("href"), location.href).searchParams.get("org"); } catch (e) { return null; }
  }
  var lis = Array.prototype.slice.call(list.children);
  var same = lis.length === SHOWN && lis.every(function (li, i) {
    var a = li.querySelector("a.mt-res-n"), id = a && orgId(a);
    if (!id || !byId[id] || byId[id].i !== i) return false;
    els[id] = li;
    return true;
  });
  if (!same) return;          // the list is not the one the data describes: leave the page as the server drew it

  var inputs = {};
  Array.prototype.forEach.call(panel.querySelectorAll("input.mw-r"), function (inp) { inputs[inp.getAttribute("data-k")] = inp; });
  if (KEYS.some(function (k) { return !inputs[k]; })) return;
  var still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var results = document.getElementById("results"), status = document.getElementById("mw-status"), stateEl = document.getElementById("mw-state");

  function current() { var w = {}; KEYS.forEach(function (k) { w[k] = Math.max(0, parseInt(inputs[k].value, 10) || 0); }); return w; }
  function total(w) { return KEYS.reduce(function (s, k) { return s + w[k]; }, 0); }
  function weightOf(r, w) { return r.met.reduce(function (s, k) { return s + (w[k] || 0); }, 0); }
  function rank(w) {
    if (!total(w)) return rows.slice();
    return rows.slice().sort(function (a, b) { return weightOf(b, w) - weightOf(a, w) || a.i - b.i; });
  }
  function equal(a, b) { return KEYS.every(function (k) { return a[k] === b[k]; }); }
  function presetOf(w) { return equal(w, D.presets.thesis) ? "thesis" : equal(w, D.presets.brief) ? "brief" : "custom"; }
  function byKeyOrder(ks) { return ks.slice().sort(function (a, b) { return KEYS.indexOf(a) - KEYS.indexOf(b); }); }
  function names(ks) { return byKeyOrder(ks).map(function (k) { return LABELS[k].toLowerCase(); }).join(", "); }

  // ---- the bar and the "holds" line on one row --------------------------------------------------------------------------------
  var STATE = { met: "holds", no: "does not hold", none: "no record" };
  function drawBar(li, r, w) {
    var bar = li.querySelector(".mw-bar"), cap = li.querySelector(".mw-holds");
    if (!bar) {
      bar = document.createElement("div"); bar.className = "mw-bar"; bar.setAttribute("role", "img");
      cap = document.createElement("p"); cap.className = "mw-holds";
      var head = li.querySelector(".mt-res-h");
      var at = head ? head.nextSibling : li.firstChild;
      li.insertBefore(cap, at); li.insertBefore(bar, cap);
    }
    bar.textContent = "";
    ["met", "no", "none"].forEach(function (s) {
      byKeyOrder(r[s]).forEach(function (k) {
        var seg = document.createElement("span");
        seg.className = "mw-seg"; seg.setAttribute("data-s", s); seg.setAttribute("data-k", k);
        seg.title = LABELS[k] + ": " + STATE[s];
        seg.style.flexGrow = String(w[k]);
        if (!w[k]) seg.hidden = true;
        bar.appendChild(seg);
      });
    });
    var parts = ["Holds: " + (r.met.length ? names(r.met) : "none of these reasons")];
    if (r.no.length) parts.push("does not hold: " + names(r.no));
    if (r.none.length) parts.push("no record: " + names(r.none));
    bar.setAttribute("aria-label", parts.join("; ") + ".");
    cap.textContent = parts[0] + ".";
  }

  // ---- the counterparts below the cut, fetched once, only when a new order could need them -------------------------------------
  var extras = null;
  function fallbackRow(r) {
    var li = document.createElement("li"), p = document.createElement("p"), a = document.createElement("a"), m = document.createElement("span");
    li.className = "mt-res"; p.className = "mt-res-h"; a.className = "mt-res-n"; m.className = "mt-meta";
    a.href = "/match?org=" + encodeURIComponent(r.id); a.textContent = r.name; m.textContent = r.kind;
    p.appendChild(a); p.appendChild(document.createTextNode(" ")); p.appendChild(m); li.appendChild(p);
    return li;
  }
  function loadExtras() {
    if (extras) return extras;
    if (rows.length <= SHOWN) { extras = Promise.resolve(); return extras; }
    var q = "company=" + encodeURIComponent(D.company) + "&skip=" + SHOWN;
    var th = new URLSearchParams(location.search).get("thesis");
    if (th) q += "&thesis=" + encodeURIComponent(th);
    extras = fetch("/match/weights/rows?" + q, { credentials: "same-origin" })
      .then(function (res) { return res.ok ? res.json() : { rows: [] }; })
      .catch(function () { return { rows: [] }; })
      .then(function (j) {
        (j.rows || []).forEach(function (x) {
          if (!byId[x.id] || els[x.id]) return;
          var t = document.createElement("template");
          t.innerHTML = String(x.html || "").trim();
          var li = t.content.firstElementChild;
          if (li && li.tagName === "LI") els[x.id] = li;
        });
        rows.forEach(function (r) { if (!els[r.id]) els[r.id] = fallbackRow(r); });
      });
    return extras;
  }

  // ---- apply --------------------------------------------------------------------------------------------------------------------
  var shownOrder = rows.slice(0, SHOWN).map(function (r) { return r.id; });
  var fullOrder = rows.map(function (r) { return r.id; });
  var basePos = null, timer = null;

  function syncPanel(w) {
    var t = total(w), preset = presetOf(w);
    KEYS.forEach(function (k) {
      var o = document.getElementById("mw-o-" + k);
      if (o) o.textContent = (t ? Math.round(100 * w[k] / t) : 0) + "%";
    });
    Array.prototype.forEach.call(panel.querySelectorAll("button[data-preset]:not([data-reset])"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-preset") === preset ? "true" : "false");
    });
    if (stateEl) stateEl.textContent = D.states[preset];
    try {
      var p = new URLSearchParams(location.search);
      if (preset === "thesis") p.delete("w"); else p.set("w", KEYS.map(function (k) { return k + "-" + w[k]; }).join(","));
      var s = p.toString().replace(/%2C/gi, ",");
      history.replaceState(history.state, "", location.pathname + (s ? "?" + s : "") + location.hash);
    } catch (e) { /* a URL that cannot be written keeps the old one */ }
  }

  function clearMoves() {
    Array.prototype.forEach.call(list.querySelectorAll(".mw-move"), function (b) { b.parentNode.removeChild(b); });
  }

  function render(w, announce) {
    var ord = rank(w), top = ord.slice(0, SHOWN);
    if (top.some(function (r) { return !els[r.id]; })) {
      loadExtras().then(function () { render(current(), announce); });
      return;
    }
    if (announce && !basePos) {
      basePos = {};
      fullOrder.forEach(function (id, i) { basePos[id] = i; });
    }
    if (results) results.setAttribute("aria-live", "off");          // the panel's status line speaks; the moved rows do not
    top.forEach(function (r) { list.appendChild(els[r.id]); });
    Array.prototype.slice.call(list.children).forEach(function (li) {
      if (top.every(function (r) { return els[r.id] !== li; })) list.removeChild(li);
    });
    top.forEach(function (r) { drawBar(els[r.id], r, w); });
    clearMoves();
    var moved = 0;
    if (announce) {
      top.forEach(function (r, i) {
        var d = basePos[r.id] - i;
        if (!d) return;
        moved += 1;
        var b = document.createElement("span");
        b.className = "mw-move"; b.textContent = (d > 0 ? "up " : "down ") + Math.abs(d);
        var head = els[r.id].querySelector(".mt-res-h");
        if (head) head.appendChild(b);
      });
      clearTimeout(timer);
      timer = setTimeout(function () {
        basePos = null;
        if (still) { clearMoves(); return; }
        Array.prototype.forEach.call(list.querySelectorAll(".mw-move"), function (b) { b.classList.add("mw-fade"); });
        setTimeout(clearMoves, 300);
      }, 4000);
      var first = top[0] ? top[0].name : "";
      var was = shownOrder.join("|") !== top.map(function (r) { return r.id; }).join("|");
      if (status) status.textContent = was ? "New order: " + first + " first; " + moved + " of the top " + SHOWN + " moved." : "Same order.";
    }
    shownOrder = top.map(function (r) { return r.id; });
    fullOrder = ord.map(function (r) { return r.id; });
    if (results) setTimeout(function () { results.setAttribute("aria-live", "polite"); }, 600);
    syncPanel(w);
  }

  function setValues(v) { KEYS.forEach(function (k) { inputs[k].value = String(v[k] || 0); }); }

  KEYS.forEach(function (k) {
    inputs[k].addEventListener("input", function () { render(current(), true); });
  });
  Array.prototype.forEach.call(panel.querySelectorAll("button[data-preset]"), function (b) {
    b.addEventListener("click", function () {
      setValues(D.presets[b.getAttribute("data-preset")] || D.presets.thesis);
      render(current(), true);
    });
  });
  ["pointerdown", "focusin", "keydown", "toggle"].forEach(function (ev) {
    panel.addEventListener(ev, function once() { loadExtras(); panel.removeEventListener(ev, once); });
  });

  panel.hidden = false;
  if (window.matchMedia && matchMedia("(min-width: 900px)").matches) panel.open = true;
  var start = current();
  if (presetOf(start) === "thesis") {
    rows.slice(0, SHOWN).forEach(function (r) { drawBar(els[r.id], r, start); });   // the server's order, now with its bars
    syncPanel(start);
  } else {
    render(start, false);                                                           // a shared link: its order, without the movement
  }
  panel.setAttribute("data-ready", "1");
})();
