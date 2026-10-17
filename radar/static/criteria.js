/* Home list filter sheet: opens and closes the phone bottom sheet (its open state lives on <html data-rail>, so a swap of the list does not close it).
   The filter state itself is radar/static/filters.js. Everything works without scripts: every option is a plain link, a filter is a URL. */
(function () {
  if (window.__criteriaRail) return;
  window.__criteriaRail = true;
  var root = document.documentElement;
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

  // the list section is replaced by htmx after every change (radar/static/filters.js keeps the rail's scroll and open groups); the Filter button's state is re-read
  document.addEventListener("htmx:afterSettle", sync);
  document.addEventListener("DOMContentLoaded", sync);
  if (document.readyState !== "loading") sync();
})();
