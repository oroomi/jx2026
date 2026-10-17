/* Home list filters, browser side. The state is the URL query (verdict, impact, trl, brl, irl, fit, country, sector, age, source, deadline,
   member, group, for, thesis); the server parses it (radar/home_filter.py) and every control is already a link that carries the next state.
   This module mirrors the same parameters in one place so other scripts (the Ask bar) can change the state without a page load, and keeps the
   page honest around each swap: only #hc-list is replaced, the address bar is rewritten with history.replaceState (never a new history
   entry), the count is read out by a live region that is never swapped away, focus is not lost, the rail keeps its scroll and open groups.
   Without scripts every control is a plain link to the filtered URL, so nothing here is needed to use the list. */
(function () {
  "use strict";
  if (window.Filters) return;
  var PARTIAL = "/home/list";
  var ALIAS = { src: "source" };
  var $ = function (id) { return document.getElementById(id); };

  function params() {
    var l = $("hc-list"), raw = l && l.getAttribute("data-params");
    return raw ? raw.split(",") : [];
  }

  /* ---- the state, mirrored ---------------------------------------------------------------------------------------------------- */
  function read(search) {
    var q = new URLSearchParams(search == null ? location.search : search), f = {};
    params().forEach(function (p) {
      var vals = q.getAll(p);
      Object.keys(ALIAS).forEach(function (old) { if (ALIAS[old] === p) vals = vals.concat(q.getAll(old)); });
      vals = vals.filter(function (v, i) { return v && vals.indexOf(v) === i; });
      if (vals.length) f[p] = vals;
    });
    return { filters: f, group: q.get("group") || "", for: q.get("for") || "", thesis: q.get("thesis") || "" };
  }

  function url(state, path) {
    var pairs = [];
    ["group", "for", "thesis"].forEach(function (k) { if (state[k] && !(k === "group" && state[k] === "all")) pairs.push([k, state[k]]); });
    params().forEach(function (p) { ((state.filters || {})[p] || []).forEach(function (v) { pairs.push([p, v]); }); });
    var qs = pairs.map(function (kv) { return encodeURIComponent(kv[0]) + "=" + encodeURIComponent(kv[1]); }).join("&");
    return (path || "/") + (qs ? "?" + qs : "");
  }

  function available() { return !!($("hc-list") && window.htmx); }

  /* A change is {filters, group, for, thesis}; a key that is present replaces that part of the state, the rest stays. Resolves when the
     list has been swapped. Off the home page (or without htmx) it navigates, which is the only case that leaves the page. */
  function apply(change) {
    var next = read();
    if (change.filters) {
      var f = {};
      Object.keys(change.filters).forEach(function (p) {
        if (p === "group") return;
        var v = change.filters[p];
        f[p] = Array.isArray(v) ? v : [v];
      });
      next.filters = f;
      if (!("group" in change)) next.group = change.filters.group ? [].concat(change.filters.group)[0] : "";
    }
    ["group", "for", "thesis"].forEach(function (k) { if (k in change) next[k] = change[k] || ""; });
    var page = url(next, "/");
    if (!available()) { location.assign(page); return Promise.resolve(false); }
    return htmx.ajax("GET", url(next, PARTIAL), { target: "#hc-list", swap: "outerHTML" }).then(function () {
      if (location.pathname + location.search !== page) history.replaceState(history.state, "", page);   /* the server's HX-Replace-Url already did it */
      return true;
    });
  }

  window.Filters = { read: read, url: url, apply: apply, available: available, params: params };

  /* ---- around each swap -------------------------------------------------------------------------------------------------------- */
  var saved = null;
  function isList(t) { return t && t.id === "hc-list"; }
  function busy(on) { var h = $("hc"); if (h) { if (on) h.setAttribute("aria-busy", "true"); else h.removeAttribute("aria-busy"); } }

  document.addEventListener("htmx:beforeRequest", function (e) { if (isList(e.detail.target)) busy(true); });
  document.addEventListener("htmx:beforeSwap", function (e) {
    if (!isList(e.detail.target)) return;
    var rail = document.querySelector(".hc-rail"), a = document.activeElement;
    saved = { top: rail ? rail.scrollTop : 0, open: {}, focus: a && a.id && e.detail.target.contains(a) ? a.id : (a && e.detail.target.contains(a) ? "lost" : null) };
    if (rail) [].forEach.call(rail.querySelectorAll("details[data-f]"), function (d) { saved.open[d.getAttribute("data-f")] = d.open; });
  });
  document.addEventListener("htmx:afterSettle", function (e) {
    if (!isList(e.detail.target)) return;
    busy(false);
    var list = $("hc-list");
    if (!list) return;
    if (saved) {
      var rail = document.querySelector(".hc-rail");
      if (rail) {
        [].forEach.call(rail.querySelectorAll("details[data-f]"), function (d) { var k = d.getAttribute("data-f"); if (k in saved.open && !d.querySelector("[aria-checked='true']")) d.open = saved.open[k]; });
        rail.scrollTop = saved.top;
      }
      /* the control that was used is gone (a removed chip, a cleared filter): put focus on the count, which a screen reader reads next */
      var a = document.activeElement;
      if (saved.focus && (!a || a === document.body)) {
        var again = saved.focus !== "lost" && $(saved.focus);
        (again || $("hc-count")).focus({ preventScroll: true });
      }
      saved = null;
    }
    var thesis = list.getAttribute("data-thesis") || "", examples = [];
    try { examples = JSON.parse(list.getAttribute("data-examples") || "[]") || []; } catch (x) { examples = []; }
    /* the full records under the list belong to the sector the page was loaded with: when another sector is in view they are hidden, with a link
       to open them (a visitor's own choice, not a filter) */
    var more = $("all-records"), stale = $("hc-stale");
    if (more && stale) {
      var other = !!more.getAttribute("data-thesis") && more.getAttribute("data-thesis") !== thesis;
      more.hidden = other; stale.hidden = !other;
      var link = stale.querySelector("a");
      if (link && other) link.setAttribute("href", "/?thesis=" + encodeURIComponent(thesis) + "#all-records");
    }
    document.dispatchEvent(new CustomEvent("filters:swapped", { detail: { thesis: thesis, examples: examples } }));
  });
  function failed() {
    busy(false);
    var c = $("hc-count");
    if (c) c.textContent = "The list could not be updated. The view shown is the one before; reload the page to try again.";
  }
  document.addEventListener("htmx:responseError", failed);
  document.addEventListener("htmx:sendError", failed);

  /* Space toggles a checkbox or radio option as well as Enter (they are links, so only Enter works by itself) */
  document.addEventListener("keydown", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[role=checkbox], a[role=radio]");
    if (a && (e.key === " " || e.key === "Spacebar") && !e.altKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); a.click(); }
  });
})();
