/* Aava: reads the records on this page aloud and moves the page in step. Vanilla JS, voice output only, no microphone.
   Speech starts only after a tap. Without an English voice the same script plays as captions with the same timing.
   Narration: when /static/aava/audio/<key>/manifest.json (pre-rendered by radar/aava_voice.py) holds a clip for the sha of EVERY segment of the
   question, the clips play in order from same-origin MP3 files; otherwise (no manifest, one sha that differs, a file that will not load) the
   browser's SpeechSynthesis reads the same text exactly as before. No third party is contacted either way.
   Conversation: the sheet lists the questions in order. A tap on a question plays its answer; Next (button, space bar, right arrow) plays the
   answer after the last one played and highlights its question. */
(function () {
  "use strict";
  var root = document.getElementById("aava");
  if (!root) return;
  var self = document.currentScript;
  var $ = function (id) { return document.getElementById(id); };
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  var segs = [], idx = 0, run = 0, timer = null, guard = null, paused = false, current = null;
  var order = [], byq = {}, cur = -1; /* order: question numbers in page order; byq: number -> its segments; cur: index of the question last asked */
  var clips = null, clipBase = "", entries = null, audio = null, mode = null; /* mode: "clips" while a recording plays, "speech" otherwise */
  /* The scripts for every question are embedded in the page: a tap plays them at once, so speech starts inside the tap
     (mobile browsers refuse speech that starts after a network wait). */
  var groups = {};
  try { groups = JSON.parse(($("aava-data") || {}).textContent || "{}") || {}; } catch (e) { groups = {}; }
  /* Every segment knows its question (q). The old intent groups share some answers (why holds questions 2 and 3, meet and talk question 4):
     a segment is kept once per question. */
  Object.keys(groups).forEach(function (g) {
    (groups[g] || []).forEach(function (s) {
      if (!s || typeof s.q !== "number") return;
      var list = byq[s.q] = byq[s.q] || [];
      if (!list.some(function (x) { return x.sha === s.sha; })) list.push(s);
    });
  });
  root.querySelectorAll(".aava-q").forEach(function (b) { order.push(Number(b.dataset.q)); });

  function pickVoice() {
    var vs = synth ? synth.getVoices() : [];
    var en = vs.filter(function (v) { return /^en([-_]|$)/i.test(v.lang); });
    return en.filter(function (v) { return /^en[-_](GB|US)/i.test(v.lang); })[0] || en[0] || null;
  }

  function canSpeak() {
    /* voices load late on some browsers: an empty list still speaks with the browser's English default */
    return !!synth && (pickVoice() !== null || synth.getVoices().length === 0);
  }

  function setMode() {
    var m = mode || (clips ? "clips" : "speech");
    $("aava-mode").textContent = m === "clips" ? "Recorded voice and captions"
      : canSpeak() ? "Voice and captions" : "Captions only (no English voice on this device)";
  }
  if (synth && synth.addEventListener) synth.addEventListener("voiceschanged", setMode);

  /* Pre-rendered narration. The directory name is the key with anything outside A-Z a-z 0-9 . _ - replaced by "_" (radar/aava_voice.dir_name). */
  function dirFor(key) {
    var d = String(key).replace(/[^A-Za-z0-9._-]/gu, "_");
    return /^\.*$/.test(d) ? "_" + d : d;
  }

  function loadClips() {
    var key = root.dataset.kind === "company" ? (root.dataset.script || "").replace(/^\/aava\/script\//, "") : "feed";
    var ver = /[?&]v=([^&]+)/.exec((self && self.src) || "");
    var base = "/static/aava/audio/" + dirFor(key) + "/";
    fetch(base + "manifest.json" + (ver ? "?v=" + ver[1] : ""), { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (m) {
        var map = {};
        ((m && m.segments) || []).forEach(function (e) {
          if (e && typeof e.text_sha === "string" && e.rendered !== false && /^[A-Za-z0-9._-]+\.mp3$/.test(e.file || "")) map[e.text_sha] = e;
        });
        if (Object.keys(map).length) { clips = map; clipBase = base; setMode(); }
      })
      .catch(function () { clips = null; }); /* no recording for this page: the browser voice reads it */
  }

  /* One clip per segment, matched by the segment's own sha. Any segment without a clip means no recording for this question at all. */
  function clipsFor(list) {
    if (!clips) return null;
    var out = [];
    for (var i = 0; i < list.length; i++) {
      var e = list[i].sha ? clips[list[i].sha] : null;
      if (!e) return null;
      out.push(e);
    }
    return out;
  }

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
    clearHighlight(); /* the answer stays on screen as a caption */
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
    if (mode === "clips" && entries && entries[idx]) playClip(s, entries[idx], token);
    else playSpeech(s, token);
  }

  function playClip(s, e, token) {
    if (!audio) { /* one element for the whole briefing: a browser that let the tap start it lets it play the next clips too */
      audio = document.createElement("audio");
      audio.id = "aava-audio"; audio.preload = "auto";
      root.appendChild(audio);
    }
    audio.onended = function () { next(token); };
    audio.onerror = function () { fallBack(s, token); };
    audio.src = clipBase + e.file;
    var p = audio.play();
    if (p && p.catch) p.catch(function (err) { if (!err || err.name !== "AbortError") fallBack(s, token); });
  }

  /* A clip that will not load or play: this segment and the rest of the briefing go to the browser voice. */
  function fallBack(s, token) {
    if (token !== run) return;
    mode = "speech"; setMode();
    if (audio) { audio.onended = null; audio.onerror = null; audio.pause(); }
    playSpeech(s, token);
  }

  function playSpeech(s, token) {
    var words = s.text.length;
    var ms = Math.max(2200, words * 60);
    var voice = pickVoice();
    if (canSpeak()) {
      var u = new SpeechSynthesisUtterance(s.text);
      if (voice) { u.voice = voice; u.lang = voice.lang; } else { u.lang = "en-GB"; }
      u.rate = 0.95;
      var t0 = Date.now();
      /* a device that cannot really speak ends or fails at once: then the caption stays up for its reading time instead */
      var after = function () { timer = setTimeout(function () { next(token); }, Math.max(0, ms - (Date.now() - t0))); };
      u.onend = function () { if (Date.now() - t0 < ms * 0.25) after(); else next(token); };
      u.onerror = after;
      synth.speak(u);
      guard = setTimeout(function () { next(token); }, ms * 2 + 4000); /* some browsers never fire onend */
    } else {
      timer = setTimeout(function () { next(token); }, ms);
    }
  }

  function halt() {
    run += 1; paused = false;
    clearTimeout(timer); clearTimeout(guard);
    if (synth && (synth.speaking || synth.pending)) synth.cancel(); /* a cancel right before speak can swallow it in Chrome */
    if (audio) { audio.onended = null; audio.onerror = null; audio.pause(); }
  }

  function begin(list) {
    segs = list || []; idx = 0;
    if (!segs.length) { $("aava-caption").textContent = "No public record to read."; return; }
    entries = clipsFor(segs);
    mode = entries ? "clips" : "speech";
    $("aava-pause").disabled = false; $("aava-stop").disabled = false;
    $("aava-pause").textContent = "Pause"; /* a new answer starts running, even when Next was pressed while the last one was paused */
    $("aava-sheet").classList.add("playing");
    setMode();
    play(run);
  }

  /* The question buttons: the current one is marked, the ones already asked are quieter, and the list scrolls to keep the current one in view. */
  function mark() {
    var btns = root.querySelectorAll(".aava-q");
    btns.forEach(function (b, i) {
      b.classList.toggle("is-now", i === cur);
      b.classList.toggle("is-done", cur >= 0 && i < cur);
      if (i === cur) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    var list = $("aava-qs"), b = btns[cur];
    if (b && list) {
      if (b.offsetTop < list.scrollTop) list.scrollTop = b.offsetTop;
      else if (b.offsetTop + b.offsetHeight > list.scrollTop + list.clientHeight) list.scrollTop = b.offsetTop + b.offsetHeight - list.clientHeight;
    }
    $("aava-next").disabled = cur >= order.length - 1;
  }

  /* One question. Called inside the tap (or key press), so the browser lets speech start. */
  function ask(q) {
    var i = order.indexOf(Number(q));
    if (i < 0) return;
    halt();
    cur = i; mark();
    if (byq[q] && byq[q].length) { begin(byq[q]); return; } /* same tick as the tap: speech is allowed to start */
    $("aava-caption").textContent = "Loading the records.";
    var btn = root.querySelectorAll(".aava-q")[i];
    var url = root.dataset.script + (root.dataset.kind === "company" ? "?intent=" + encodeURIComponent(btn.dataset.intent) : "");
    var thesis = new URLSearchParams(location.search).get("thesis");
    if (thesis) url += (url.indexOf("?") < 0 ? "?" : "&") + "thesis=" + encodeURIComponent(thesis);
    var token = run;
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        if (token !== run) return;
        var list = (data.segments || []).filter(function (s) { return typeof s.q !== "number" || s.q === Number(q); });
        byq[q] = list; begin(list);
      })
      .catch(function () { $("aava-caption").textContent = "Aava could not load the records. Try again."; });
  }

  /* Next: the question after the one last asked (the first one when none has been asked yet). */
  function nextQuestion() {
    if (cur >= order.length - 1) return; /* the last question: Next is disabled, a tap on any question plays it again */
    ask(order[cur + 1]);
  }

  function stop() {
    halt(); resetVisuals(); clearHighlight();
    $("aava-sheet").classList.remove("playing");
    $("aava-pause").disabled = true; $("aava-pause").textContent = "Pause"; $("aava-stop").disabled = true;
    $("aava-caption").textContent = "Stopped. Tap a question, or press Next.";
    $("aava-source").textContent = "";
  }

  function pause() {
    if (mode === "clips" && audio) { /* a recording pauses and resumes where it is; the run stays the same so its ended event still advances */
      paused = !paused;
      $("aava-pause").textContent = paused ? "Resume" : "Pause";
      if (paused) audio.pause();
      else if (audio.ended) next(run); /* the clip finished while paused: go on to the next one, do not replay it */
      else { var p = audio.play(); if (p && p.catch) p.catch(function (err) { if (!err || err.name !== "AbortError") fallBack(segs[idx], run); }); }
      return;
    }
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

  function sheetOpen() { return !$("aava-sheet").hidden; }

  $("aava-open").addEventListener("click", function () {
    $("aava-sheet").hidden = false; setMode(); mark();
    $("aava-open").setAttribute("aria-expanded", "true");
    $("aava-next").focus({ preventScroll: true });
  });
  $("aava-close").addEventListener("click", function () {
    stop(); cur = -1; mark(); $("aava-sheet").hidden = true; $("aava-open").setAttribute("aria-expanded", "false"); $("aava-open").focus();
    $("aava-caption").textContent = "Tap a question, or press Next (space bar or right arrow). Aava speaks only after you tap.";
  });
  $("aava-stop").addEventListener("click", stop);
  $("aava-pause").addEventListener("click", pause);
  $("aava-next").addEventListener("click", nextQuestion);
  root.querySelectorAll(".aava-q").forEach(function (b) { b.addEventListener("click", function () { ask(b.dataset.q); }); });

  /* Keys while the sheet is open: Escape closes, space bar and right arrow play the next answer. Typing fields and the Pause, Stop and Close
     buttons keep the space bar for themselves. */
  function keyIsNext(e) {
    if (!sheetOpen() || e.altKey || e.ctrlKey || e.metaKey) return false;
    if (e.key !== " " && e.key !== "ArrowRight") return false;
    var t = e.target;
    if (t && t.closest && t.closest("input, textarea, select, [contenteditable=''], [contenteditable='true']")) return false;
    if (e.key === " " && t && t.closest && t.closest("#aava-pause, #aava-stop, #aava-close, a")) return false;
    return true;
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sheetOpen()) { $("aava-close").click(); return; }
    if (!keyIsNext(e)) return;
    e.preventDefault();
    if (!e.repeat) nextQuestion();
  });
  document.addEventListener("keyup", function (e) { if (keyIsNext(e) && e.key === " ") e.preventDefault(); }); /* a button would click on the key's release */
  window.addEventListener("pagehide", halt);
  window.addEventListener("beforeunload", halt);
  document.body.addEventListener("htmx:beforeRequest", stop); /* the feed pills swap the rows Aava is reading */
  window.Aava = { stop: stop, voices: function () { return synth ? synth.getVoices().length : 0; }, audioDir: dirFor };
  loadClips();
})();
