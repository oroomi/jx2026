/* Aava: reads the records on this page aloud and moves the page in step. Vanilla JS, voice output only, no microphone.
   Speech starts only after a tap. Without an English voice the same script plays as captions with the same timing. */
(function () {
  "use strict";
  var root = document.getElementById("aava");
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  var segs = [], idx = 0, run = 0, timer = null, guard = null, paused = false, current = null, lastIntent = "brief";

  function pickVoice() {
    var vs = synth ? synth.getVoices() : [];
    var en = vs.filter(function (v) { return /^en([-_]|$)/i.test(v.lang); });
    return en.filter(function (v) { return /^en[-_](GB|US)/i.test(v.lang); })[0] || en[0] || null;
  }

  function setMode() {
    $("aava-mode").textContent = pickVoice() ? "Voice and captions" : "Captions only (no English voice on this device)";
  }
  if (synth && synth.addEventListener) synth.addEventListener("voiceschanged", setMode);

  function clearHighlight() {
    if (current) current.classList.remove("aava-hl");
    current = null;
  }

  function animate(el, from, to, ms, apply) {
    if (reduced) { apply(to); return; }
    var t0 = performance.now();
    (function step(t) {
      var p = Math.min(1, (t - t0) / ms);
      apply(from + (to - from) * p);
      if (p < 1) requestAnimationFrame(step);
    })(t0);
  }

  function resetVisuals() {
    $("aava-meter").hidden = true;
    $("aava-line").hidden = true;
    $("aava-line").querySelectorAll(".aava-dot").forEach(function (d) { d.remove(); });
    $("aava-line-fill").style.width = "0";
    $("aava-meter-fill").style.width = "0";
  }

  function act(s, target) {
    resetVisuals();
    if (s.action === "count_up" || s.action === "fill_level") {
      var max = s.max || s.value || 1;
      $("aava-meter").hidden = false;
      $("aava-meter-max").textContent = " of " + max;
      animate(null, 0, s.value, 300, function (v) {
        $("aava-meter-num").textContent = String(Math.round(v));
        $("aava-meter-fill").style.width = (v / max * 100) + "%";
      });
    } else if (s.action === "draw_timeline" && s.points) {
      var line = $("aava-line");
      line.hidden = false;
      s.points.forEach(function (p) {
        var d = document.createElement("span");
        d.className = "aava-dot";
        d.style.left = p.left + "%";
        d.title = p.label + ", " + p.date;
        line.appendChild(d);
      });
      animate(null, 0, 100, 400, function (v) { $("aava-line-fill").style.width = v + "%"; });
    }
  }

  function show(s) {
    $("aava-caption").textContent = s.text;
    var src = $("aava-source");
    src.textContent = "";
    if (s.source_url) {
      var a = document.createElement("a");
      a.href = s.source_url; a.target = "_blank"; a.rel = "noopener"; a.textContent = "Source for this sentence";
      src.appendChild(a);
    }
    clearHighlight();
    var target = s.target ? document.getElementById(s.target) : null;
    if (target) {
      target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
      if (s.action !== "scroll" && s.action !== "none") { target.classList.add("aava-hl"); current = target; }
    }
    act(s, target);
  }

  function finish() {
    $("aava-sheet").classList.remove("playing");
    $("aava-pause").disabled = true;
    $("aava-pause").textContent = "Pause";
    $("aava-stop").disabled = true;
    clearHighlight();
    $("aava-caption").textContent = "Done. Tap a question to hear it again.";
  }

  function next(token) {
    if (token !== run || paused) return;
    clearTimeout(timer); clearTimeout(guard);
    idx += 1;
    if (idx >= segs.length) { finish(); return; }
    play(token);
  }

  function play(token) {
    var s = segs[idx];
    show(s);
    var words = s.text.length;
    var ms = Math.max(2200, words * 60);
    var voice = pickVoice();
    if (synth && voice) {
      var u = new SpeechSynthesisUtterance(s.text);
      u.voice = voice; u.lang = voice.lang; u.rate = 0.95;
      u.onend = function () { next(token); };
      u.onerror = function () { next(token); };
      synth.speak(u);
      guard = setTimeout(function () { next(token); }, ms * 2 + 4000); /* some browsers never fire onend */
    } else {
      timer = setTimeout(function () { next(token); }, ms);
    }
  }

  function halt() {
    run += 1; paused = false;
    clearTimeout(timer); clearTimeout(guard);
    if (synth) synth.cancel();
  }

  function start(intent) {
    halt();
    lastIntent = intent;
    $("aava-caption").textContent = "Loading the records.";
    var url = root.dataset.script + (root.dataset.kind === "company" ? "?intent=" + encodeURIComponent(intent) : "") ;
    var thesis = new URLSearchParams(location.search).get("thesis");
    if (thesis) url += (url.indexOf("?") < 0 ? "?" : "&") + "thesis=" + encodeURIComponent(thesis);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        segs = data.segments || []; idx = 0;
        if (!segs.length) { $("aava-caption").textContent = "No public record to read."; return; }
        $("aava-pause").disabled = false; $("aava-stop").disabled = false;
        $("aava-sheet").classList.add("playing");
        setMode();
        var token = run;
        play(token);
      })
      .catch(function () { $("aava-caption").textContent = "Aava could not load the records. Try again."; });
  }

  function stop() {
    halt(); resetVisuals(); clearHighlight();
    $("aava-sheet").classList.remove("playing");
    $("aava-pause").disabled = true; $("aava-pause").textContent = "Pause"; $("aava-stop").disabled = true;
    $("aava-caption").textContent = "Stopped. Tap a question to start again.";
    $("aava-source").textContent = "";
  }

  function pause() {
    if (!paused) {
      paused = true; run += 1;
      clearTimeout(timer); clearTimeout(guard);
      if (synth) synth.cancel();
      $("aava-pause").textContent = "Resume";
    } else {
      paused = false; run += 1;
      $("aava-pause").textContent = "Pause";
      play(run);
    }
  }

  $("aava-open").addEventListener("click", function () { $("aava-sheet").hidden = false; setMode(); $("aava-open").setAttribute("aria-expanded", "true"); });
  $("aava-close").addEventListener("click", function () { stop(); $("aava-sheet").hidden = true; $("aava-open").setAttribute("aria-expanded", "false"); $("aava-open").focus(); });
  $("aava-stop").addEventListener("click", stop);
  $("aava-pause").addEventListener("click", pause);
  root.querySelectorAll("[data-intent]").forEach(function (b) { b.addEventListener("click", function () { start(b.dataset.intent); }); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("aava-sheet").hidden) $("aava-close").click(); });
  window.addEventListener("pagehide", halt);
  window.addEventListener("beforeunload", halt);
  document.body.addEventListener("htmx:beforeRequest", stop); /* the feed pills swap the rows Aava is reading */
  window.Aava = { stop: stop, voices: function () { return synth ? synth.getVoices().length : 0; } };
})();
