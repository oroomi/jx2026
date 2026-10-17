"""Aava voice: pre-rendered narration audio for "Ask Aava", so the demo plays MP3 files with no network call and no key at runtime.

    python3 -m radar.aava_voice render --keys 2962040-6,3166759-6 --feed          # one MP3 per segment, ElevenLabs text-to-speech
    python3 -m radar.aava_voice render --keys 2962040-6 --dry-run --out /tmp/aava  # manifest only, estimated durations, no API call

Segments are the ones the page itself embeds (radar.routes.aava.company_json and feed_json, built by radar.aava), so the text spoken is
the text on screen. Output, committed to the repo so the demo works offline from the ZIP:

    radar/static/aava/audio/<company key | feed>/<n>_<sha8>.mp3      sha8 = first 8 hex of the text fingerprint (radar.aava.text_sha)
    radar/static/aava/audio/<company key | feed>/manifest.json       {segments: [{n, target, text_sha, file, duration_s, ...}]}

The player (radar/static/aava.js) plays a question from these files only when every segment of that question has a manifest entry
whose text_sha equals the segment's own sha; otherwise it speaks with the browser voice exactly as before.

Environment (read with os.environ at run time, never from a file this module opens):
    ELEVENLABS_API_KEY   required unless --dry-run; never printed, never written.
    ELEVENLABS_VOICE_ID  optional; default DEFAULT_VOICE_ID below.
    ELEVENLABS_OUTPUT_FORMAT  optional; default mp3_44100_64 (speech at about 8 KB per second).
    RADAR_DATA_DIR, RADAR_DB, RADAR_THESIS as for the app: the database read is the one the app serves.

A text whose file already exists is not rendered again (cache by text hash, so a re-run after an edit renders only what changed);
--force renders everything again, for a new voice. ElevenLabs bills per character: a dry run prints the characters still to render.
Exit codes: 0 done, 1 a target failed, 2 bad arguments, 3 BLOCKED (no API key)."""
from __future__ import annotations

import argparse
import http.client
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from radar import aava, thesis as thesis_mod

ROOT = Path(__file__).resolve().parent.parent
AUDIO_ROOT = ROOT / "radar" / "static" / "aava" / "audio"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel", one of ElevenLabs' premade voices: calm, clear, neutral English
MODEL_ID = "eleven_multilingual_v2"
DEFAULT_FORMAT = "mp3_44100_64"
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format={fmt}"
WORDS_PER_SECOND = 2.6
EXIT_BLOCKED = 3
RETRY_STATUS = (429, 500, 502, 503, 504)
_sleep = time.sleep  # a test replaces this


class VoiceError(Exception):
    """A target that cannot be rendered; the message is safe to print (it never holds the key)."""


# ---- names -------------------------------------------------------------------------------------------------------------------
def dir_name(key: str) -> str:
    """Directory of a company's audio. aava.js computes the same name from the key in the page's data-script attribute."""
    d = re.sub(r"[^A-Za-z0-9._-]", "_", key)
    return "_" + d if re.fullmatch(r"\.*", d) else d


def estimate_seconds(text: str) -> float:
    return round(len(text.split()) / WORDS_PER_SECOND, 2)


# ---- MP3 duration ------------------------------------------------------------------------------------------------------------
_BITRATES = {  # kbps for bitrate index 1..14, by (mpeg version group, layer)
    (1, 1): (32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448),
    (1, 2): (32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384),
    (1, 3): (32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
    (2, 1): (32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256),
    (2, 2): (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
    (2, 3): (8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
}
_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}  # by the 2 version bits


def _frame(b: bytes, i: int):
    """(length in bytes, samples, sample rate) of the MPEG audio frame whose header starts at b[i], or None."""
    if i + 4 > len(b) or b[i] != 0xFF or (b[i + 1] & 0xE0) != 0xE0:
        return None
    ver, layer = (b[i + 1] >> 3) & 3, 4 - ((b[i + 1] >> 1) & 3)
    bi, ri, pad = b[i + 2] >> 4, (b[i + 2] >> 2) & 3, (b[i + 2] >> 1) & 1
    if ver == 1 or layer == 4 or bi in (0, 15) or ri == 3:
        return None
    group, sr = (1 if ver == 3 else 2), _RATES[ver][ri]
    rate = _BITRATES[(group, layer)][bi - 1] * 1000
    if layer == 1:
        return (12 * rate // sr + pad) * 4, 384, sr
    samples = 1152 if (layer == 2 or group == 1) else 576
    return samples // 8 * rate // sr + pad, samples, sr


def mp3_duration(data: bytes) -> float | None:
    """Length in seconds of MP3 bytes, or None when no audio frames are found. mutagen when installed, else a frame walk (no dependency)."""
    try:
        from mutagen.mp3 import MP3
        length = float(MP3(io.BytesIO(data)).info.length)
        if length > 0:
            return round(length, 3)
    except Exception:
        pass  # not installed, or mutagen could not read it: walk the frames ourselves
    i = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        i = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F)) + (10 if data[5] & 0x10 else 0)
    seconds, frames, first = 0.0, 0, True
    while i + 4 <= len(data):
        f = _frame(data, i)
        # a header counts only when the next frame follows it (or the data ends): junk bytes that look like a sync are skipped
        if f is None or (i + f[0] != len(data) and i + f[0] + 4 <= len(data) and _frame(data, i + f[0]) is None):
            i += 1
            continue
        length, samples, sr = f
        tagged = first and any(t in data[i:i + 64] for t in (b"Xing", b"Info", b"VBRI"))  # a VBR header frame holds no audio
        first = False
        if not tagged:
            seconds += samples / sr
            frames += 1
        i += length
    return round(seconds, 3) if frames else None


# ---- ElevenLabs --------------------------------------------------------------------------------------------------------------
class ElevenLabs:
    """text -> MP3 bytes through the text-to-speech HTTP API. The key lives only in this object and in the request header."""

    def __init__(self, api_key: str, voice_id: str = DEFAULT_VOICE_ID, model_id: str = MODEL_ID, output_format: str = DEFAULT_FORMAT):
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", voice_id):
            raise VoiceError("ELEVENLABS_VOICE_ID is not a voice id (letters and digits, 8 to 64 characters)")
        self._key, self.voice_id, self.model_id, self.output_format = api_key, voice_id, model_id, output_format

    def __repr__(self) -> str:
        return f"ElevenLabs(voice_id={self.voice_id!r}, model_id={self.model_id!r})"

    def __call__(self, text: str) -> bytes:
        url = API_URL.format(voice=self.voice_id, fmt=urllib.parse.quote(self.output_format))
        body = json.dumps({"text": text, "model_id": self.model_id, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode()
        headers = {"xi-api-key": self._key, "Content-Type": "application/json", "Accept": "audio/mpeg",
                   "User-Agent": "OceanOpportunityRadar/0.1 (JunctionX Turku 2026; +https://jx.hankintaviikko.fi)"}
        last = "no attempt"
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout=120) as r:
                    data = r.read()
                if mp3_duration(data) is None:
                    raise VoiceError("ElevenLabs answered with something that is not MP3 audio")
                return data
            except urllib.error.HTTPError as e:
                detail = self._detail(e)
                last = f"HTTP {e.code}{': ' + detail if detail else ''}"
                if e.code not in RETRY_STATUS:
                    raise VoiceError(f"ElevenLabs refused the request ({last})") from None
                wait = float(e.headers.get("Retry-After") or 0) if e.headers else 0
                _sleep(min(max(wait, 2 ** (attempt + 1)), 30))
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
                last = f"network error: {getattr(e, 'reason', e)}"
                _sleep(2 ** (attempt + 1))
        raise VoiceError(f"ElevenLabs did not answer after 4 attempts (last: {last})")

    def _detail(self, e: urllib.error.HTTPError) -> str:
        try:
            d = json.loads(e.read().decode("utf-8", "replace")).get("detail")
        except Exception:
            return ""
        msg = d.get("message") or d.get("status") or "" if isinstance(d, dict) else str(d or "")
        return str(msg).replace(self._key, "***")[:300]


# ---- collecting the page's own segments --------------------------------------------------------------------------------------
def collect_company(key: str, th: dict) -> dict:
    """{intent: [segment]} exactly as the company page embeds it."""
    from radar.routes import aava as page
    groups = json.loads(str(page.company_json(key, th)))
    if not groups:
        raise VoiceError(f"no company {key} in the {th['id']} database (is it built? is RADAR_DATA_DIR set?)")
    return groups


def collect_feed(thesis_id: str | None) -> tuple[dict, dict]:
    """(thesis, {"brief": [segment]}) exactly as the home page embeds it: the same view the feed route builds, strong rows in the page's order."""
    from starlette.requests import Request
    from radar.routes import aava as page, feed as feed_page
    query = urllib.parse.urlencode({"thesis": thesis_id}) if thesis_id else ""
    view = feed_page._view(Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": query.encode()}), None)
    if view["no_db"]:
        raise VoiceError(f"no database for the {view['thesis']['id']} thesis yet (is it built? is RADAR_DATA_DIR set?)")
    return view["thesis"], json.loads(str(page.feed_json(view["main_rows"])))


def plan(groups: dict, intents: tuple[str, ...] = aava.INTENTS) -> list[dict]:
    """The distinct spoken texts of the chosen intents in script order: {text, sha, target, intents}. A text shared by two questions is one clip."""
    out: dict[str, dict] = {}
    for intent in intents:
        for s in groups.get(intent) or []:
            e = out.setdefault(aava.text_sha(s["text"]), {"text": s["text"], "sha": aava.text_sha(s["text"]), "target": s["target"], "intents": []})
            e["intents"].append(intent)
    return list(out.values())


# ---- rendering ---------------------------------------------------------------------------------------------------------------
def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def render_target(name: str, groups: dict, thesis_id: str, *, out_root: Path = AUDIO_ROOT, synth=None, dry_run: bool = False,
                  force: bool = False, intents: tuple[str, ...] = aava.INTENTS, meta: dict | None = None) -> dict:
    """Render the clips of one target (a company key or "feed") and write its manifest. synth(text) -> MP3 bytes is called only for texts with no
    file yet (or all with force). dry_run calls nothing and writes only the manifest. Returns {manifest, clips, todo, cached, characters, characters_total,
    path}: todo and characters count the clips a real run sends (or just sent), so a dry run shows what it would cost.
    A failing synth raises before the manifest is touched; the clips already written stay cached, so the next run resumes."""
    d = out_root / (name if name == "feed" else dir_name(name))
    d.mkdir(parents=True, exist_ok=True)
    rows, todo, todo_chars, cached = [], 0, 0, 0
    for n, e in enumerate(plan(groups, intents)):
        have = next((p for p in sorted(d.glob(f"*_{e['sha'][:8]}.mp3")) if p.stat().st_size > 0), None)
        path = have or d / f"{n}_{e['sha'][:8]}.mp3"
        if force or not have:
            todo, todo_chars = todo + 1, todo_chars + len(e["text"])
            if not dry_run:
                if synth is None:
                    raise VoiceError("no synthesiser given")
                _write(path, synth(e["text"]))
        else:
            cached += 1
        seconds = mp3_duration(path.read_bytes()) if path.is_file() else None
        rows.append({"n": n, "target": e["target"], "text_sha": e["sha"], "file": path.name, "chars": len(e["text"]),
                     "duration_s": seconds if seconds else estimate_seconds(e["text"]),
                     "duration_source": "measured" if seconds else "estimated", "rendered": path.is_file(), "thesis": thesis_id, "intents": e["intents"]})
    manifest_path = d / "manifest.json"
    try:
        previous = json.loads(manifest_path.read_text(encoding="utf-8")).get("segments", [])
    except (OSError, ValueError, AttributeError):
        previous = []
    mine = {r["text_sha"] for r in rows}
    # another thesis's clips for the same key stay listed; this thesis's earlier entries are replaced by the ones just built
    kept = [p for p in previous if p.get("thesis") not in (None, thesis_id) and p.get("text_sha") not in mine and (d / str(p.get("file"))).is_file()]
    manifest = {"version": 1, "key": name, **(meta or {}), "segments": rows + kept}
    _write(manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"manifest": manifest, "clips": len(rows), "todo": todo, "cached": cached, "characters": todo_chars,
            "characters_total": sum(r["chars"] for r in rows), "path": manifest_path}


# ---- command line ------------------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m radar.aava_voice", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    env_help = (f"environment:\n  ELEVENLABS_API_KEY        required unless --dry-run (exit {EXIT_BLOCKED}, BLOCKED, when unset); never printed\n"
                f"  ELEVENLABS_VOICE_ID       default {DEFAULT_VOICE_ID} (premade voice \"Rachel\")\n"
                f"  ELEVENLABS_OUTPUT_FORMAT  default {DEFAULT_FORMAT}\n  model: {MODEL_ID}")
    r = sub.add_parser("render", help="render the narration clips and write each manifest", epilog=env_help, formatter_class=argparse.RawDescriptionHelpFormatter)
    r.add_argument("--keys", default="", help="comma-separated company keys, for example 2962040-6,3166759-6")
    r.add_argument("--feed", action="store_true", help="also render the home page's feed reader")
    r.add_argument("--thesis", metavar="ID", help="thesis id (default: the app's default thesis)")
    r.add_argument("--intents", default=",".join(aava.INTENTS), help="questions to render (default all: %(default)s)")
    r.add_argument("--dry-run", action="store_true", help="no API call and no key needed: write the manifests with estimated durations")
    r.add_argument("--force", action="store_true", help="render every clip again even if its file exists (a new voice)")
    r.add_argument("--out", type=Path, default=AUDIO_ROOT, help="audio root (default: radar/static/aava/audio)")
    args = ap.parse_args(argv)

    keys = list(dict.fromkeys(k.strip() for k in args.keys.split(",") if k.strip()))
    if not keys and not args.feed:
        ap.error("give --keys, --feed or both")
    intents = tuple(i.strip() for i in args.intents.split(",") if i.strip())
    if not intents or any(i not in aava.INTENTS for i in intents):
        ap.error(f"--intents must be some of: {', '.join(aava.INTENTS)}")
    if args.thesis and args.thesis not in thesis_mod.available():
        ap.error(f"unknown thesis {args.thesis!r}; available: {', '.join(thesis_mod.available())}")

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not args.dry_run and not api_key:
        print("BLOCKED: ELEVENLABS_API_KEY is not set in the environment, so nothing was rendered. Put it in the service's EnvironmentFile "
              "(or export it), or run with --dry-run to see the plan and the character count without a key.", file=sys.stderr)
        return EXIT_BLOCKED
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    fmt = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "").strip() or DEFAULT_FORMAT
    try:
        synth = None if args.dry_run else ElevenLabs(api_key, voice, MODEL_ID, fmt)
    except VoiceError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 2
    meta = {"model": MODEL_ID, "voice_id": voice, "output_format": fmt}

    code, total, th_default = 0, 0, thesis_mod.load(thesis_mod.resolve(args.thesis))
    jobs = [(k, lambda k=k: (th_default, collect_company(k, th_default))) for k in keys]
    if args.feed:
        jobs.append(("feed", lambda: collect_feed(args.thesis)))
    for name, collect in jobs:
        try:
            th, groups = collect()
            res = render_target(name, groups, th["id"], out_root=args.out, synth=synth, dry_run=args.dry_run, force=args.force, intents=intents, meta=meta)
        except VoiceError as e:
            print(f"FAILED {name}: {e}", file=sys.stderr)
            code = 1
            continue
        total += res["characters"]
        print(f"{name}: {res['clips']} clips, {res['characters_total']} characters; {'to render' if args.dry_run else 'rendered'} {res['todo']} clips "
              f"({res['characters']} characters), {res['cached']} cached -> {res['path']}")
    print(("DRY RUN: no API call was made; manifests list clips that are not rendered yet. " if args.dry_run else "") + f"Characters {'still to render' if args.dry_run else 'sent to ElevenLabs'}: {total}")
    return code


if __name__ == "__main__":
    sys.exit(main())
