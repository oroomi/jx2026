/* Ask Aava: the home hero bar. Vanilla JS, no library, no network call except GET /api/ask on this site (deterministic answers, radar/ask.py).
   Text mode: the form asks, an answer card appears under the bar, words fade in. The placeholder cycles through the thesis' example questions.
   Voice mode (only when the Aava demo flag is on, the same gate as aava.js): the microphone button opens a translucent overlay with an orb that
   follows the microphone (Web Audio AnalyserNode), a live transcript (Web Speech API, en-US), then speaks the answer (a pre-rendered MP3 when the
   Aava manifest holds one for the answer's text sha, else the browser voice) while the orb follows the audio and the answer is written word by word.
   Reduced motion: no pulsing, ripples or word-by-word; the state shows as a steady ring and a text label. Escape and Close leave voice mode. */
(function () {
  "use strict";
  var root = document.getElementById("ask");
  if (!root) return;
  var $ = function (id) { return document.getElementById(id); };
  var form = $("ask-form"), input = $("ask-q"), micBtn = $("ask-mic"), card = $("ask-card");
  var thesisNow = function () { return root.dataset.thesis || ""; };   /* the sector can change in place (radar/static/filters.js) */
  var mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  var reduced = function () { return !!mq.matches; };
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var demo = window.AAVA_DEMO === true;
  if (!demo) { try { demo = localStorage.getItem("aava_demo") === "1"; } catch (e) {} }
  var examples = [];
  try { examples = JSON.parse(root.dataset.examples || "[]") || []; } catch (e) { examples = []; }
  var SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YQAAAAA=";

  /* ---- small helpers ------------------------------------------------------------------------------------------------------------ */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  /* The answer as one span per word, so it can be written word by word. Screen readers read the whole text either way. */
  function words(host, text) {
    host.textContent = "";
    var spans = [];
    String(text || "").split(/\s+/).filter(Boolean).forEach(function (w, i) {
      if (i) host.appendChild(document.createTextNode(" "));
      var s = el("span", "w", w);
      host.appendChild(s);
      spans.push(s);
    });
    return spans;
  }
  function reveal(spans, upTo) {
    for (var i = 0; i < spans.length; i++) if (i < upTo) spans[i].classList.add("is-in");
  }
  function link(href, text, cls, blank) {
    var a = el("a", cls, text);
    a.href = href;
    if (blank) { a.target = "_blank"; a.rel = "noopener"; }
    return a;
  }
  /* The answer's own link. A filter answer ("12 of 58 match: ...") changes the home list in place: the filters become the page's state and only the
     list section is swapped (radar/static/filters.js), nothing is loaded. Off the home page, or without scripts, it stays a plain link. */
  function goLink(a, after) {
    var n = link(a.url, a.label || "Open", "ask-go");
    if (a.intent === "filter" && a.filters && window.Filters && window.Filters.available()) {
      n.addEventListener("click", function (e) {
        e.preventDefault();
        window.Filters.apply({ filters: a.filters }).then(function () {
          var list = document.getElementById("hc-list"), top = list && list.querySelector(".hc-rows, .hc-empty");
          if (top && top.scrollIntoView) top.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" });
        });
        if (after) after();
      });
    }
    return n;
  }

  /* ---- placeholder cycling ------------------------------------------------------------------------------------------------------ */
  (function cyclePlaceholder() {
    if (examples.length < 2) return;
    var i = 0;
    setInterval(function () {
      if (reduced() || document.activeElement === input || input.value || document.hidden) return;
      i = (i + 1) % examples.length;
      root.classList.add("is-swapping");
      setTimeout(function () { input.placeholder = examples[i]; root.classList.remove("is-swapping"); }, 260);
    }, 4200);
  })();

  /* ---- speech output: a recorded clip when the Aava manifest has it, else the browser voice -------------------------------------- */
  var Speech = (function () {
    var audio = null, ctx = null, an = null, buf = null;
    var token = 0, raf = 0, level = 0, kick = 0, progress = 0, active = false, hooks = null, startedAt = 0, estMs = 0, byTime = false;
    var manifests = {};   /* dir -> Promise<{sha: entry}|null> */

    function ensureAudio() {
      if (audio) return;
      audio = document.createElement("audio");
      audio.preload = "auto";
      audio.setAttribute("playsinline", "");
      audio.style.display = "none";
      document.body.appendChild(audio);
    }
    function ensureCtx() {
      if (ctx) return ctx;
      var C = window.AudioContext || window.webkitAudioContext;
      if (!C) return null;
      try { ctx = new C(); } catch (e) { ctx = null; }
      return ctx;
    }
    function tap() {   /* route the playing clip through an analyser (once: an element can be a source only once) */
      if (an || !ensureCtx()) return;
      try {
        var src = ctx.createMediaElementSource(audio);
        an = ctx.createAnalyser(); an.fftSize = 256; an.smoothingTimeConstant = 0.6;
        src.connect(an); an.connect(ctx.destination);
        buf = new Uint8Array(an.fftSize);
      } catch (e) { an = null; }
    }
    /* Called inside a tap: mobile browsers only let audio and speech start from there. */
    function unlock(withSynth) {
      ensureAudio();
      var c = ensureCtx();
      if (c && c.state === "suspended" && c.resume) c.resume();
      try { audio.onended = null; audio.src = SILENT; var p = audio.play(); if (p && p.catch) p.catch(function () {}); } catch (e) {}
      try { if (synth && withSynth) { var u = new SpeechSynthesisUtterance(" "); u.volume = 0; synth.speak(u); } } catch (e) {}
    }
    function pickVoice() {
      var vs = synth ? synth.getVoices() : [];
      var en = vs.filter(function (v) { return /^en([-_]|$)/i.test(v.lang); });
      var female = /female|samantha|karen|serena|moira|fiona|kate|victoria|allison|ava\b|susan|zira|hazel|jenny|aria|libby|sonia|google uk english female/i;
      var rank = function (v) { return (/^en[-_]GB/i.test(v.lang) ? 0 : /^en[-_]US/i.test(v.lang) ? 1 : 2) + (female.test(v.name) ? 0 : 3); };
      return en.slice().sort(function (a, b) { return rank(a) - rank(b); })[0] || null;
    }
    function manifest(dir) {
      if (!dir) return Promise.resolve(null);
      if (!manifests[dir]) {
        manifests[dir] = fetch("/static/aava/audio/" + encodeURIComponent(dir) + "/manifest.json", { headers: { Accept: "application/json" } })
          .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then(function (m) {
            var map = {};
            ((m && m.segments) || []).forEach(function (e) {
              if (e && typeof e.text_sha === "string" && e.rendered !== false && /^[A-Za-z0-9._-]+\.mp3$/.test(e.file || "")) map[e.text_sha] = e;
            });
            return Object.keys(map).length ? { base: "/static/aava/audio/" + encodeURIComponent(dir) + "/", map: map } : null;
          })
          .catch(function () { return null; });
      }
      return manifests[dir];
    }
    function clipsFor(a, m) {   /* every segment needs a clip whose sha matches, else no recording at all */
      if (!m || !(a.segments || []).length) return null;
      var out = [];
      for (var i = 0; i < a.segments.length; i++) {
        var e = m.map[a.segments[i].sha];
        if (!e) return null;
        out.push(e);
      }
      return out;
    }
    function rms() {
      if (!an || !buf) return 0;
      an.getByteTimeDomainData(buf);
      var s = 0;
      for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; s += v * v; }
      return Math.min(1, Math.sqrt(s / buf.length) * 4.2);
    }
    function tick() {
      if (!active) return;
      raf = requestAnimationFrame(tick);
      var now = performance.now();
      if (an && audio && !audio.paused) level = rms();
      else {
        if (byTime) kick = Math.max(kick, 0.55 + 0.45 * Math.sin(now / 170));   /* no voice to follow: a steady reading pulse */
        else kick *= 0.9;
        level = 0.16 + 0.7 * kick * (0.65 + 0.35 * Math.sin(now / 53) * Math.sin(now / 131));
      }
      if (byTime) progress = Math.min(1, (now - startedAt) / estMs);
      if (hooks && hooks.onProgress) hooks.onProgress(progress);
      if (byTime && progress >= 1) finish(token);
    }
    function begin(my, h) {
      hooks = h || {}; active = true; progress = 0; level = 0; kick = 0; byTime = false;
      cancelAnimationFrame(raf); raf = requestAnimationFrame(tick);
    }
    function finish(my) {
      if (my !== token || !active) return;
      active = false; cancelAnimationFrame(raf); level = 0; progress = 1;
      var h = hooks; hooks = null;
      if (h && h.onProgress) h.onProgress(1);
      if (h && h.onEnd) h.onEnd();
    }
    function playClips(clips, m, a, my) {
      ensureAudio(); tap();
      if (ctx && ctx.state === "suspended" && ctx.resume) ctx.resume();
      var total = 0, known = true;
      clips.forEach(function (e) { if (typeof e.duration_s === "number") total += e.duration_s; else known = false; });
      var done = 0, i = 0;
      function nextClip() {
        if (my !== token) return;
        if (i >= clips.length) { finish(my); return; }
        var e = clips[i];
        audio.onended = function () {
          if (audio.src.indexOf(e.file) < 0) return;   /* the silent unlock clip ending late */
          done += typeof e.duration_s === "number" ? e.duration_s : (audio.duration || 0); i += 1; nextClip();
        };
        audio.onerror = function () { if (my === token) { audio.onended = null; audio.onerror = null; playSynth(a, my, true); } };
        audio.src = m.base + e.file;
        var p = audio.play();
        if (p && p.catch) p.catch(function (err) { if (my === token && (!err || err.name !== "AbortError")) playSynth(a, my, true); });
      }
      /* progress follows the audio: seconds played of the seconds in the manifest, else clips played of clips */
      var follow = function () {
        if (my !== token || !active) return;
        var cur = audio && !isNaN(audio.currentTime) ? audio.currentTime : 0;
        progress = known && total ? Math.min(1, (done + cur) / total) : Math.min(1, (i + (audio.duration ? cur / audio.duration : 0)) / clips.length);
        requestAnimationFrame(follow);
      };
      nextClip(); follow();
    }
    function playSynth(a, my, fromClip) {
      if (my !== token) return;
      var text = a.say || "";
      if (fromClip && audio) { audio.pause(); }
      if (!active) begin(my, hooks);
      var boundary = false, started = false;
      estMs = Math.max(2400, text.length * 62);
      if (!synth) { startedAt = performance.now(); byTime = true; return; }
      var u = new SpeechSynthesisUtterance(text), v = pickVoice();
      if (v) { u.voice = v; u.lang = v.lang; } else u.lang = "en-GB";
      u.rate = 0.96; u.pitch = 1.02;
      u.onstart = function () { started = true; startedAt = performance.now(); };
      u.onboundary = function (e) {
        if (my !== token) return;
        boundary = true; byTime = false; kick = 1;
        progress = Math.min(1, ((e.charIndex || 0) + (e.charLength || 4)) / Math.max(1, text.length));
      };
      u.onend = function () { finish(my); };
      u.onerror = function () { if (my === token) { startedAt = performance.now(); byTime = true; } };
      try { synth.speak(u); } catch (e) { startedAt = performance.now(); byTime = true; }
      setTimeout(function () {   /* a device that never starts speaking: the answer is still written, at reading pace */
        if (my === token && !started && !boundary) { startedAt = performance.now(); byTime = true; }
      }, 1600);
      setTimeout(function () { if (my === token && active) finish(my); }, estMs * 2 + 4000);   /* some browsers never fire onend */
      startedAt = performance.now();
    }
    return {
      unlock: unlock,
      prefetch: function (dir) { manifest(dir); },
      level: function () { return level; },
      playing: function () { return active; },
      play: function (a, h) {
        stop();
        var my = ++token;
        begin(my, h);
        if (a.blob_url) { playClips([{ file: a.blob_url }], { base: "" }, a, my); return; }   /* one spoken file from the server (aava_chat.js); a failed file falls back to the browser voice */
        manifest(a.audio_dir).then(function (m) {
          if (my !== token) return;
          var clips = clipsFor(a, m);
          if (clips) playClips(clips, m, a, my); else playSynth(a, my, false);
        });
      },
      stop: function () { stop(); }
    };
    function stop() {
      token += 1; active = false; cancelAnimationFrame(raf); level = 0; kick = 0; hooks = null; byTime = false;
      try { if (synth && (synth.speaking || synth.pending)) synth.cancel(); } catch (e) {}
      if (audio) { audio.onended = null; audio.onerror = null; try { audio.pause(); } catch (e) {} }
    }
  })();

  /* ---- the answer ---------------------------------------------------------------------------------------------------------------- */
  var seq = 0;
  /* With a model key on the server and the demo flag on, aava_chat.js (loaded after this file) takes over typed and spoken questions. */
  function chat() { return window.AavaChat && window.AavaChat.active() ? window.AavaChat : null; }
  function fetchAnswer(q) {
    var url = "/api/ask?q=" + encodeURIComponent(q) + (thesisNow() ? "&thesis=" + encodeURIComponent(thesisNow()) : "");
    return fetch(url, { headers: { Accept: "application/json" } }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  function sourceLinks(a) {
    var segs = (a.segments || []).filter(function (s) { return s.source_url; });
    var out = [];
    if (segs.length === 1) out.push(link(segs[0].source_url, "Source for this sentence", "ask-src", true));
    else segs.forEach(function (s, i) { out.push(link(s.source_url, "Source " + (i + 1), "ask-src", true)); });
    return out;
  }

  var listening = null;   /* the Listen button that is playing, to reset when another answer comes */
  function renderCard(a, q) {
    card.hidden = false;
    card.classList.remove("is-loading");
    card.textContent = "";
    var head = el("p", "ask-card-q");
    head.appendChild(el("span", "ask-card-who", "Aava"));
    head.appendChild(el("span", "ask-card-echo", "“" + q + "”"));
    card.appendChild(head);
    var say = el("p", "ask-card-say");
    card.appendChild(say);
    var spans = words(say, a.say);
    if (a.items && a.items.length) {
      var ul = el("ul", "ask-items");
      a.items.forEach(function (it) { var li = el("li"); li.appendChild(link(it.url, it.label)); ul.appendChild(li); });
      card.appendChild(ul);
    }
    var row = el("p", "ask-links");
    if (a.url && !(a.intent === "filter" && a.count === 0)) row.appendChild(goLink(a));   /* no link to an empty list */
    sourceLinks(a).forEach(function (n) { row.appendChild(n); });
    var listen = null;
    if (demo && (synth || (a.segments || []).length)) {
      listen = el("button", "ask-listen");
      listen.type = "button";
      listen.appendChild(el("i"));
      listen.appendChild(el("span", null, "Listen"));
      row.appendChild(listen);
      Speech.prefetch(a.audio_dir);
    }
    card.appendChild(row);
    /* the sentence fades in word by word, quickly; at once under reduced motion */
    if (reduced() || spans.length < 2) reveal(spans, spans.length);
    else {
      var i = 0, per = Math.min(38, 1300 / spans.length);
      var t = setInterval(function () { i += 1; reveal(spans, i); if (i >= spans.length) clearInterval(t); }, per);
    }
    if (listen) listen.addEventListener("click", function () {
      var on = listen.classList.contains("is-on");
      if (listening && listening !== listen) { listening.classList.remove("is-on"); listening.lastChild.textContent = "Listen"; }
      if (on) { Speech.stop(); listen.classList.remove("is-on"); listen.lastChild.textContent = "Listen"; listening = null; return; }
      Speech.unlock(false);
      listen.classList.add("is-on"); listen.lastChild.textContent = "Stop"; listening = listen;
      Speech.play(a, { onEnd: function () { listen.classList.remove("is-on"); listen.lastChild.textContent = "Listen"; if (listening === listen) listening = null; } });
    });
  }

  function showLoading(q) {
    card.hidden = false;
    card.classList.add("is-loading");
    card.textContent = "";
    var head = el("p", "ask-card-q");
    head.appendChild(el("span", "ask-card-who", "Aava"));
    head.appendChild(el("span", "ask-card-echo", "“" + q + "”"));
    card.appendChild(head);
    var p = el("p", "ask-card-say");
    var dots = el("span", "ask-dots"); dots.setAttribute("aria-hidden", "true");
    for (var i = 0; i < 3; i++) dots.appendChild(el("i"));
    p.appendChild(dots); p.appendChild(el("span", "ask-sr", "Looking at the records"));
    card.appendChild(p);
  }

  function showError(q) {
    card.hidden = false;
    card.classList.remove("is-loading");
    card.textContent = "";
    card.appendChild(el("p", "ask-card-say", "Aava could not reach the records just now."));
    var row = el("p", "ask-links");
    row.appendChild(link("/search?q=" + encodeURIComponent(q), "Open the search results", "ask-go"));
    card.appendChild(row);
  }

  /* Text mode: ask, show the card. Returns the answer (or null). */
  function ask(q) {
    q = (q || "").trim();
    if (!q) { input.focus(); return Promise.resolve(null); }
    var c = chat();
    if (c) { seq += 1; Speech.stop(); card.hidden = true; input.value = ""; return c.send(q); }   /* the conversation panel answers (aava_chat.js) */
    var my = ++seq;
    Speech.stop();
    showLoading(q);
    return fetchAnswer(q).then(function (a) { if (my !== seq) return null; renderCard(a, q); return a; })
      .catch(function () { if (my === seq) showError(q); return null; });
  }

  form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
  root.querySelectorAll(".ask-chip").forEach(function (b) {
    b.addEventListener("click", function () { input.value = b.dataset.q; ask(b.dataset.q); });
  });

  /* The sector changed in place (radar/static/filters.js): ask about that sector from now on, with its example questions. */
  document.addEventListener("filters:swapped", function (e) {
    var d = e.detail || {};
    if (d.thesis && d.thesis !== (root.dataset.thesis || "")) {
      root.dataset.thesis = d.thesis;
      card.hidden = true;
      if (d.examples && d.examples.length) {
        examples = d.examples;
        root.dataset.examples = JSON.stringify(examples);
        input.placeholder = examples[0];
        var ul = root.querySelector(".ask-try");
        if (ul) {
          ul.textContent = "";
          examples.slice(0, 5).forEach(function (q) {
            var li = el("li"), b = el("button", "ask-chip", q);
            b.type = "button"; b.dataset.q = q;
            b.addEventListener("click", function () { input.value = q; ask(q); });
            li.appendChild(b); ul.appendChild(li);
          });
        }
      }
    }
  });

  /* Ctrl or Cmd + K focuses the bar (the Linear and Raycast habit). */
  var mac = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent || "");
  var key = root.querySelector(".ask-key");
  if (key && window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches) {
    key.hidden = false;
    if (mac) $("ask-kbd").textContent = "⌘";
  }
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === "k" || e.key === "K") && !isOpen) {
      e.preventDefault(); input.focus(); input.select();
    }
  });

  /* A question in the address (/?ask=Tell+me+about+Viva+Jets) runs on load: shareable, and what the screenshots use. */
  try {
    var pre = new URLSearchParams(location.search).get("ask");
    if (pre) { input.value = pre; ask(pre); }
  } catch (e) {}

  /* ================================================================================================================================ */
  /* Voice mode: only with the Aava demo flag on.                                                                                      */
  /* ================================================================================================================================ */
  window.AskBar = { ask: ask, speak: function (a, h) { Speech.unlock(true); Speech.play(a, h); }, stopSpeech: function () { Speech.stop(); } };
  var ov = $("ask-voice");
  if (!demo || !ov) { if (ov) ov.remove(); return; }
  micBtn.hidden = false;
  document.body.appendChild(ov);   /* out of the page flow: a fixed layer cannot be clipped by the hero */

  var cv = $("ask-orb"), cx2 = cv.getContext("2d");
  var elState = $("ask-voice-state"), elLine = $("ask-voice-line"), elSay = $("ask-voice-say"), elLinks = $("ask-voice-links");
  var typeForm = $("ask-voice-type"), typeIn = $("ask-voice-input");
  var voiceKick = 0;
  /* One capture at a time on phones: speech recognition and an analyser on the same microphone can break each other there, so only a
     pointer-and-keyboard device (a laptop) opens the analyser as well. */
  var touchFirst = !!(window.matchMedia && matchMedia("(pointer: coarse)").matches);
  var state = "idle", isOpen = false, lastFocus = null, rec = null, micStream = null, micCtx = null, micAn = null, micBuf = null, sayWords = [];
  var LABEL = { idle: "Tap the orb to speak", listening: "Listening", thinking: "Looking at the records", speaking: "Aava is speaking",
                done: "Tap the orb to ask another question", error: "" };

  function setState(s, text) {
    state = s;
    ov.dataset.state = s;
    elState.textContent = text != null ? text : LABEL[s];
    if (reduced()) ov.style.setProperty("--lvl", s === "listening" || s === "speaking" ? "0.5" : "0.1");
  }

  /* -- microphone level through an AnalyserNode (when permission is granted); otherwise the orb breathes -- */
  function startMic() {
    if (micStream || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
    micStream = "pending";
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      if (!isOpen) { stream.getTracks().forEach(function (t) { t.stop(); }); micStream = null; return; }
      var C = window.AudioContext || window.webkitAudioContext;
      if (!C) { stream.getTracks().forEach(function (t) { t.stop(); }); micStream = null; return; }
      micCtx = new C();
      var src = micCtx.createMediaStreamSource(stream);
      micAn = micCtx.createAnalyser(); micAn.fftSize = 256; micAn.smoothingTimeConstant = 0.8;
      src.connect(micAn);
      micBuf = new Uint8Array(micAn.fftSize);
      micStream = stream;
    }).catch(function () { micStream = "denied"; });
  }
  function stopMic() {
    if (micStream && micStream.getTracks) micStream.getTracks().forEach(function (t) { t.stop(); });
    if (micCtx) { try { micCtx.close(); } catch (e) {} }
    micStream = null; micCtx = null; micAn = null; micBuf = null;
  }
  function micLevel() {
    if (typeof window.__askFakeLevel === "function") return window.__askFakeLevel(performance.now() / 1000);   /* a test or a screenshot with no microphone */
    if (!micAn) {   /* no analyser (touch devices, permission refused): the orb follows the recogniser's own activity, a pulse on each result */
      voiceKick *= 0.93;
      return state === "listening" ? 0.1 + 0.65 * voiceKick : 0;
    }
    micAn.getByteTimeDomainData(micBuf);
    var s = 0;
    for (var i = 0; i < micBuf.length; i++) { var v = (micBuf[i] - 128) / 128; s += v * v; }
    return Math.min(1, Math.sqrt(s / micBuf.length) * 5);
  }

  /* -- the orb: canvas, drawn from the skin's tokens (accent, text, bg) -- */
  var Orb = (function () {
    var raf = 0, t0 = 0, lvl = 0, col = null, ripples = [], lastPeak = 0, size = 0, dpr = 1;
    function rgb(str) {
      var c = document.createElement("canvas").getContext("2d");
      c.fillStyle = "#000"; c.fillStyle = String(str || "").trim() || "#000";
      var v = c.fillStyle;
      if (v.charAt(0) === "#") return [parseInt(v.slice(1, 3), 16), parseInt(v.slice(3, 5), 16), parseInt(v.slice(5, 7), 16)];
      var m = v.match(/[\d.]+/g) || [0, 0, 0];
      return [+m[0], +m[1], +m[2]];
    }
    function mix(a, b, k) { return [0, 1, 2].map(function (i) { return Math.round(a[i] * (1 - k) + b[i] * k); }); }
    function rgba(c, a) { return "rgba(" + c[0] + "," + c[1] + "," + c[2] + "," + Math.max(0, Math.min(1, a)) + ")"; }
    function colors() {
      var cs = getComputedStyle(document.documentElement);
      var acc = rgb(cs.getPropertyValue("--accent")), txt = rgb(cs.getPropertyValue("--text")), bg = rgb(cs.getPropertyValue("--bg"));
      var dark = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) < 128;
      /* dark page: a light core toward the text colour; light page: a light core toward the paper, a deeper rim toward the ink */
      col = { acc: acc, hi: dark ? mix(acc, txt, 0.5) : mix(acc, bg, 0.62), lo: dark ? mix(acc, bg, 0.5) : mix(acc, txt, 0.28),
              spec: dark ? txt : [255, 255, 255], dark: dark };
    }
    function resize() {
      var r = cv.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      size = Math.max(120, Math.round(r.width || 280));
      cv.width = Math.round(size * dpr); cv.height = Math.round(size * dpr);
    }
    function frame(now) {
      raf = requestAnimationFrame(frame);
      var t = (now - t0) / 1000, motion = reduced() ? 0 : 1;
      var want = state === "listening" ? micLevel() : state === "speaking" ? Speech.level() : 0;
      lvl += (want - lvl) * (want > lvl ? 0.35 : 0.1);
      var breathe = motion ? Math.sin(t * 1.7) * 0.5 + 0.5 : 0;
      var base = state === "thinking" ? 0.2 : state === "listening" ? 0.12 : state === "speaking" ? 0.1 : 0.06;
      var e = motion ? Math.min(1, base + lvl * 0.95 + breathe * (state === "thinking" ? 0.03 : 0.07))
                     : (state === "listening" || state === "speaking" ? 0.5 : 0.25);
      if (motion) ov.style.setProperty("--lvl", Math.min(1, lvl + (state === "thinking" ? 0.15 : 0.05)).toFixed(3));
      draw(now, t, e, motion);
    }
    function draw(now, t, e, motion) {
      var W = cv.width, c = W / 2, R = W / 2;
      cx2.clearRect(0, 0, W, W);
      var core = R * 0.54 * (1 + (motion ? 0.18 * e : 0));
      var g = cx2.createRadialGradient(c, c, core * 0.55, c, c, R);
      g.addColorStop(0, rgba(col.acc, 0.3 + 0.32 * e)); g.addColorStop(0.55, rgba(col.acc, 0.09 + 0.1 * e)); g.addColorStop(1, rgba(col.acc, 0));
      cx2.fillStyle = g; cx2.fillRect(0, 0, W, W);
      /* ripples leave the orb on peaks of the voice */
      if (motion && (state === "listening" || state === "speaking") && lvl > 0.4 && now - lastPeak > 380) { ripples.push(now); lastPeak = now; }
      ripples = ripples.filter(function (r) { return now - r < 1600; });
      ripples.forEach(function (r) {
        var k = (now - r) / 1600;
        cx2.beginPath(); cx2.arc(c, c, core * 1.05 + (R * 0.97 - core * 1.05) * k, 0, 6.2832);
        cx2.strokeStyle = rgba(col.hi, 0.5 * (1 - k)); cx2.lineWidth = 2 * dpr; cx2.stroke();
      });
      /* body: a lit sphere, three slow blobs inside it, a highlight */
      cx2.save();
      cx2.beginPath(); cx2.arc(c, c, core, 0, 6.2832); cx2.clip();
      var body = cx2.createRadialGradient(c - core * 0.3, c - core * 0.35, core * 0.1, c, c, core);
      body.addColorStop(0, rgba(col.hi, 0.95)); body.addColorStop(0.5, rgba(col.acc, 0.95)); body.addColorStop(1, rgba(col.lo, 0.98));
      cx2.fillStyle = body; cx2.fillRect(0, 0, W, W);
      cx2.globalCompositeOperation = col.dark ? "lighter" : "source-over";
      var spin = motion ? t * (state === "thinking" ? 1.9 : 0.55) : 0.7, tints = [col.hi, col.acc, col.lo];
      for (var i = 0; i < 3; i++) {
        var ang = spin + i * 2.094, off = core * (0.16 + 0.3 * e);
        var bx = c + Math.cos(ang) * off, by = c + Math.sin(ang * 1.1 + i) * off * 0.9, br = core * (0.95 - i * 0.06);
        var bg2 = cx2.createRadialGradient(bx, by, 0, bx, by, br);
        bg2.addColorStop(0, rgba(tints[i], (col.dark ? 0.26 : 0.45) + 0.14 * e)); bg2.addColorStop(1, rgba(tints[i], 0));
        cx2.fillStyle = bg2; cx2.fillRect(0, 0, W, W);
      }
      cx2.globalCompositeOperation = "source-over";
      var hl = cx2.createRadialGradient(c - core * 0.32, c - core * 0.4, 0, c - core * 0.32, c - core * 0.4, core * 0.62);
      hl.addColorStop(0, rgba(col.spec, 0.34)); hl.addColorStop(1, rgba(col.spec, 0));
      cx2.fillStyle = hl; cx2.fillRect(0, 0, W, W);
      cx2.restore();
      cx2.beginPath(); cx2.arc(c, c, core, 0, 6.2832); cx2.strokeStyle = rgba(col.spec, 0.22); cx2.lineWidth = 1.5 * dpr; cx2.stroke();
      /* thinking: an arc travels round the orb (a steady dashed ring under reduced motion) */
      if (state === "thinking") {
        cx2.beginPath();
        if (motion) cx2.arc(c, c, core * 1.16, t * 3.2, t * 3.2 + 1.5); else cx2.arc(c, c, core * 1.16, 0, 6.2832);
        if (!motion) cx2.setLineDash([6 * dpr, 8 * dpr]);
        cx2.strokeStyle = rgba(col.hi, 0.85); cx2.lineWidth = 2.5 * dpr; cx2.lineCap = "round"; cx2.stroke(); cx2.setLineDash([]);
      }
    }
    return {
      start: function () { colors(); resize(); t0 = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(frame); },
      stop: function () { cancelAnimationFrame(raf); ripples = []; lvl = 0; },
      resize: resize
    };
  })();
  window.addEventListener("resize", function () { if (isOpen) Orb.resize(); });

  /* -- listening: the transcript line is live (interim in grey, final in text colour) -- */
  function showType(msg) {
    typeForm.hidden = false;
    if (msg != null) elState.textContent = msg;
    typeIn.focus();
  }
  function clearAnswer() {
    elLine.textContent = ""; elLine.classList.remove("is-final");
    elSay.textContent = ""; elLinks.textContent = ""; elLinks.hidden = false; sayWords = [];
    typeForm.hidden = true;
  }
  function stopRec() {
    if (rec) { rec.onend = null; rec.onerror = null; rec.onresult = null; try { rec.abort(); } catch (e) {} rec = null; }
  }

  function listen() {
    Speech.stop(); stopRec(); clearAnswer(); seq += 1;
    if (!SR) {
      setState("idle", "Speech recognition is not supported in this browser.");
      if (!touchFirst) startMic();
      showType();
      return;
    }
    setState("listening");
    var finalText = "", gotFinal = false;
    rec = new SR();
    rec.lang = "en-US"; rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
    rec.onresult = function (e) {
      voiceKick = 1;
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        var r = e.results[i];
        if (r.isFinal) { finalText += r[0].transcript; gotFinal = true; } else interim += r[0].transcript;
      }
      var shown = (finalText + interim).trim();
      elLine.textContent = shown; elLine.classList.toggle("is-final", gotFinal && !interim);
      if (gotFinal && !interim) heard(finalText);
    };
    rec.onerror = function (e) {
      var why = e && e.error;
      if (why === "aborted") return;
      stopRec();
      var msg = why === "not-allowed" || why === "service-not-allowed" ? "The microphone is blocked in this browser. Type your question instead."
        : why === "audio-capture" ? "No microphone was found. Type your question instead."
        : why === "network" ? "Speech recognition needs a connection in this browser. Type your question instead."
        : why === "no-speech" ? "I did not hear anything. Tap the orb to try again, or type your question."
        : "Speech recognition stopped. Tap the orb to try again, or type your question.";
      setState("error", msg);
      showType(msg);
    };
    rec.onend = function () {
      if (state !== "listening") return;
      if (finalText.trim()) heard(finalText);
      else { setState("idle", "I did not catch that. Tap the orb to try again, or type your question."); showType(elState.textContent); }
    };
    try { rec.start(); if (!touchFirst) startMic(); } catch (err) { setState("error", "Speech recognition could not start. Type your question instead."); showType(); }
  }

  /* -- a question has been heard or typed: ask, then speak the answer -- */
  function heard(text) {
    text = (text || "").trim();
    if (!text) return;
    stopRec(); stopMic();
    elLine.textContent = text; elLine.classList.add("is-final");
    typeForm.hidden = true;
    setState("thinking");
    var my = ++seq, c = chat();
    if (c) {   /* the same conversation as the typed one; the final answer is spoken, with ElevenLabs when the server has it, else the browser voice */
      c.send(text, { onStatus: function (t) { if (my === seq && isOpen && state === "thinking") elState.textContent = t; } }).then(function (res) {
        if (!(my === seq && isOpen)) return null;
        if (!res) { setState("error", "Aava could not reach the records. Tap the orb to try again."); showType(); return null; }
        return c.audioFor(res.plain).then(function (url) {
          if (my === seq && isOpen) speakAnswer({ intent: "chat", say: res.plain, items: res.items, url: null, segments: [], audio_dir: null, blob_url: url }, text);
        });
      });
      return;
    }
    fetchAnswer(text).then(function (a) { if (my === seq && isOpen) speakAnswer(a, text); })
      .catch(function () { if (my === seq && isOpen) { setState("error", "Aava could not reach the records. Tap the orb to try again."); showType(); } });
  }

  function speakAnswer(a, q) {
    sayWords = words(elSay, a.say);
    elLinks.textContent = ""; elLinks.hidden = true;
    (a.items || []).forEach(function (it) { elLinks.appendChild(link(it.url, it.label)); });
    if (a.url && !(a.intent === "filter" && a.count === 0)) elLinks.appendChild(goLink(a, closeVoice));
    sourceLinks(a).forEach(function (n) { elLinks.appendChild(n); });
    var spoken = reduced();   /* reduced motion: the whole answer at once, then the voice */
    if (spoken) { reveal(sayWords, sayWords.length); elLinks.hidden = false; }
    setState("speaking");
    Speech.play(a, {
      onProgress: function (f) { if (!spoken) reveal(sayWords, Math.ceil(f * sayWords.length)); },
      onEnd: function () { reveal(sayWords, sayWords.length); elLinks.hidden = false; if (isOpen && state === "speaking") setState("done"); }
    });
  }

  /* -- open and close -- */
  function openVoice() {
    if (isOpen) return;
    Speech.unlock(true);                  /* inside the tap: audio and speech may start later */
    isOpen = true; lastFocus = document.activeElement;
    ov.hidden = false; ov.classList.add("is-open");
    document.documentElement.classList.add("ask-voice-open");
    micBtn.setAttribute("aria-expanded", "true");
    Orb.start();
    $("ask-voice-close").focus({ preventScroll: true });
    listen();
  }
  function closeVoice() {
    if (!isOpen) return;
    isOpen = false; seq += 1;
    stopRec(); stopMic(); Speech.stop(); Orb.stop();
    ov.hidden = true; ov.classList.remove("is-open");
    document.documentElement.classList.remove("ask-voice-open");
    micBtn.setAttribute("aria-expanded", "false");
    setState("idle"); clearAnswer();
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  micBtn.addEventListener("click", openVoice);
  $("ask-voice-close").addEventListener("click", closeVoice);
  $("ask-orb-btn").addEventListener("click", function () {
    Speech.unlock(true);
    if (state === "listening") { stopRec(); setState("idle"); }
    else if (state === "thinking") return;
    else listen();
  });
  $("ask-voice-again").addEventListener("click", function () { Speech.unlock(true); listen(); });
  $("ask-voice-typebtn").addEventListener("click", function () { Speech.stop(); stopRec(); setState("idle", "Type your question."); showType(); });
  typeForm.addEventListener("submit", function (e) { e.preventDefault(); var v = typeIn.value; typeIn.value = ""; Speech.unlock(true); heard(v); });

  document.addEventListener("keydown", function (e) {
    if (!isOpen) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeVoice(); return; }
    if (e.key === "Tab") {   /* keep focus inside the dialog */
      var f = [].slice.call(ov.querySelectorAll("button, input, a[href]")).filter(function (n) { return !n.hidden && n.getClientRects().length && !n.closest("[hidden]"); });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      else if (!ov.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    }
  }, true);
  window.addEventListener("pagehide", function () { closeVoice(); Speech.stop(); });

  /* a handle for tests and screenshots */
  window.AskBar = { ask: ask, speak: window.AskBar.speak, stopSpeech: window.AskBar.stopSpeech, heard: heard, openVoice: openVoice, closeVoice: closeVoice, state: function () { return state; }, setTranscript: function (t, final) {
    elLine.textContent = t; elLine.classList.toggle("is-final", !!final); } };
})();
