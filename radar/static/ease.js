/* Ease of use: "See why" boxes are open on desktop and closed on phones. Without JS they stay open. */
(function () {
  if (!window.matchMedia || window.matchMedia("(min-width: 900px)").matches) return;
  document.querySelectorAll("details.why-box").forEach(function (d) { d.open = false; });
})();
