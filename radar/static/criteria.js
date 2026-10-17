/* Home list filter: opens and closes the phone sheet, keeps the rail's scroll and open groups across the htmx refresh of the list, and carries
   the active filters across the group and country links. Everything works without it: every option is a plain link, a filter is a URL. */
(function () {
  if (window.__criteriaRail) return;
  window.__criteriaRail = true;
  var root = document.documentElement, FILTERS = ["verdict", "impact", "trl", "brl", "irl", "fit", "country", "sector", "age", "src", "deadline", "member"];
  var returnTo = null;

  function isOpen() { return root.getAttribute("data-rail") === "open"; }
  function sync() {
    var open = isOpen();
    [].forEach.call(document.querySelectorAll(".hc-fbtn"), function (b) { b.setAttribute("aria-expanded", open ? "true" : "false"); });
  }
  function setOpen(open) {
    if (open) { returnTo = document.activeElement; root.setAttribute("data-rail", "open"); }
    else { root.removeAttribute("data-rail"); if (returnTo && returnTo.focus) returnTo.focus(); returnTo = null; }
    sync();
    if (open) { var c = document.querySelector(".hr-close"); if (c && c.offsetParent !== null) c.focus(); }
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-rail-toggle]");
    if (t) { e.preventDefault(); setOpen(!isOpen()); }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && isOpen()) setOpen(false); });
  window.addEventListener("resize", function () { if (window.innerWidth >= 960 && isOpen()) setOpen(false); });

  // keep the filters when the visitor switches group or country
  function carry() {
    var here = new URLSearchParams(location.search), keep = [];
    FILTERS.forEach(function (f) { here.getAll(f).forEach(function (v) { keep.push([f, v]); }); });
    [].forEach.call(document.querySelectorAll(".hc-pills a, .hc-countries a"), function (a) {
      var u = new URL(a.getAttribute("href"), location.href);
      FILTERS.forEach(function (f) { u.searchParams.delete(f); });
      keep.forEach(function (kv) { u.searchParams.append(kv[0], kv[1]); });
      a.setAttribute("href", u.pathname + u.search);
    });
  }

  // htmx replaces the whole .hc section: restore the rail's scroll position and which groups were open
  var saved = null;
  document.addEventListener("htmx:beforeSwap", function (e) {
    var rail = document.querySelector(".hc-rail");
    if (!rail || !e.detail.target || !e.detail.target.classList || !e.detail.target.classList.contains("hc")) return;
    saved = { top: rail.scrollTop, open: {} };
    [].forEach.call(rail.querySelectorAll("details[data-f]"), function (d) { saved.open[d.getAttribute("data-f")] = d.open; });
  });
  document.addEventListener("htmx:afterSettle", function () {
    if (saved) {
      var rail = document.querySelector(".hc-rail");
      if (rail) {
        [].forEach.call(rail.querySelectorAll("details[data-f]"), function (d) { var k = d.getAttribute("data-f"); if (k in saved.open && !d.querySelector(".on")) d.open = saved.open[k]; });
        rail.scrollTop = saved.top;
      }
      saved = null;
    }
    carry(); sync();
  });
  document.addEventListener("DOMContentLoaded", function () { carry(); sync(); });
  if (document.readyState !== "loading") { carry(); sync(); }
})();
