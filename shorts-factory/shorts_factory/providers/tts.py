"""Speech providers: one WAV of narration per slide.

auto     Offline first: sapi on Windows, then piper (if PIPER_VOICE is set), then espeak-ng/espeak, then silent.
         OpenAI is used only when you ask for it, because it costs money.
sapi     Windows' built-in voices (System.Speech through PowerShell). Free, offline. SHORTS_SAPI_VOICE picks a
         voice by name (e.g. "Microsoft Zira Desktop"), SHORTS_SAPI_RATE -10..10 (default 1).
piper    Piper neural TTS, free and offline. PIPER_VOICE = path to a voice .onnx; PIPER_BIN if piper is not on PATH.
espeak   espeak-ng (or espeak). Free, offline, robotic. SHORTS_ESPEAK_VOICE (default en-us+f3), SHORTS_ESPEAK_SPEED.
openai   OpenAI speech API. OPENAI_API_KEY; OPENAI_TTS_MODEL (default gpt-4o-mini-tts), OPENAI_TTS_VOICE (coral).
silent   No voice: silence as long as the narration would take. Captions still show. For tests and drafts.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
from pathlib import Path

from .. import media
from ..timing import estimate_speech_seconds

PROVIDERS = ("auto", "sapi", "piper", "espeak", "openai", "silent")
OFFLINE = ("sapi", "piper", "espeak", "silent")
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

SAPI_PS = (
    "$ErrorActionPreference='Stop';"
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "Add-Type -AssemblyName System.Speech;"
    "$t=[Console]::In.ReadToEnd();"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "if($env:SHORTS_SAPI_VOICE){$s.SelectVoice($env:SHORTS_SAPI_VOICE)};"
    "$s.Rate=[int]$env:SHORTS_SAPI_RATE_EFFECTIVE;"
    "$s.SetOutputToWaveFile($env:SHORTS_SAPI_OUT);"
    "$s.Speak($t);$s.Dispose()"
)


def available() -> dict[str, bool]:
    return {
        "sapi": platform.system() == "Windows" and bool(shutil.which("powershell") or shutil.which("pwsh")),
        "piper": bool(os.environ.get("PIPER_VOICE")) and bool(media.find("piper", "PIPER_BIN")),
        "espeak": bool(shutil.which("espeak-ng") or shutil.which("espeak")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "silent": True,
    }


def pick(name: str | None, *, offline: bool = False) -> str:
    name = (name or os.environ.get("SHORTS_TTS") or "auto").lower()
    if name not in PROVIDERS:
        raise ValueError(f"tts must be one of {', '.join(PROVIDERS)}")
    if offline and name == "openai":
        raise ValueError("offline mode cannot use OpenAI speech; choose sapi, piper, espeak or silent")
    if name != "auto":
        return name
    have = available()
    for cand in ("sapi", "piper", "espeak"):
        if have[cand]:
            return cand
    return "silent"


def cache_name(index: int, provider: str, text: str) -> str:
    voice = {"sapi": os.environ.get("SHORTS_SAPI_VOICE", ""), "piper": os.environ.get("PIPER_VOICE", ""),
             "espeak": os.environ.get("SHORTS_ESPEAK_VOICE", ""), "openai": os.environ.get("OPENAI_TTS_VOICE", "")}
    h = hashlib.sha1(f"{provider}|{voice.get(provider, '')}|{text}".encode("utf-8")).hexdigest()[:10]
    return f"voice-{index + 1:02d}-{provider}-{h}.wav"


def _sapi(text: str, out: Path):
    ps = shutil.which("powershell") or shutil.which("pwsh")
    env_before = {k: os.environ.get(k) for k in ("SHORTS_SAPI_OUT", "SHORTS_SAPI_RATE_EFFECTIVE")}
    os.environ["SHORTS_SAPI_OUT"] = str(out)
    os.environ["SHORTS_SAPI_RATE_EFFECTIVE"] = os.environ.get("SHORTS_SAPI_RATE", "1")
    try:
        media.run([ps, "-NoProfile", "-NonInteractive", "-Command", SAPI_PS], input_text=text, timeout=120)
    finally:
        for k, v in env_before.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _piper(text: str, out: Path):
    piper = media.find("piper", "PIPER_BIN")
    voice = os.environ.get("PIPER_VOICE")
    if not piper or not voice:
        raise RuntimeError("piper needs PIPER_VOICE (a voice .onnx) and piper on PATH or PIPER_BIN")
    media.run([piper, "--model", voice, "--output_file", str(out)], input_text=text, timeout=120)


def _espeak(text: str, out: Path):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise RuntimeError("espeak-ng is not installed")
    media.run([exe, "-v", os.environ.get("SHORTS_ESPEAK_VOICE", "en-us+f3"),
               "-s", os.environ.get("SHORTS_ESPEAK_SPEED", "165"), "-w", str(out), "--stdin"],
              input_text=text, timeout=120)


def _openai(text: str, out: Path):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set (needed for --tts openai)")
    audio = media.http_bytes(OPENAI_TTS_URL, {"model": os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                                              "voice": os.environ.get("OPENAI_TTS_VOICE", "coral"),
                                              "input": text, "response_format": "wav"},
                             {"authorization": f"Bearer {key}"})
    out.write_bytes(audio)


def _silent(text: str, out: Path):
    secs = estimate_speech_seconds(text)
    media.run([media.ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
               "anullsrc=r=48000:cl=stereo", "-t", f"{secs:.3f}", str(out)])


SPEAKERS = {"sapi": _sapi, "piper": _piper, "espeak": _espeak, "openai": _openai, "silent": _silent}


def speak_all(texts: list[str], out_dir: Path, provider: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, t in enumerate(texts):
        p = out_dir / cache_name(i, provider, t)
        if not p.exists() or p.stat().st_size == 0:
            tmp = p.with_suffix(".part.wav")
            SPEAKERS[provider](t, tmp)
            tmp.replace(p)
        paths.append(p)
    return paths
