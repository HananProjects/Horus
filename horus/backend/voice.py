import tempfile
import os
import sys
import subprocess
import numpy as np
import sounddevice as sd
import whisper
import scipy.io.wavfile as wav

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

SAMPLE_RATE = 16000
DURATION = 5
WAKE_DURATION = 2
WAKE_WORD = "horus"
SILENCE_THRESHOLD = 0.01

# ElevenLabs config — set these in .env
_ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY", "")
_ELEVEN_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # Adam: free tier, deep
_ELEVEN_MODEL = "eleven_turbo_v2_5"


def _speak_elevenlabs(text: str) -> bool:
    """Returns True if speech succeeded, False to fall back to SAPI5."""
    if not _ELEVEN_KEY or not _REQUESTS_OK:
        return False
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{_ELEVEN_VOICE}"
        resp = _requests.post(
            url,
            headers={"xi-api-key": _ELEVEN_KEY, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": _ELEVEN_MODEL,
                "output_format": "mp3_44100_128",
                "voice_settings": {
                    "stability": 0.55,
                    "similarity_boost": 0.80,
                    "style": 0.20,
                    "use_speaker_boost": True,
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name
        uri = "file:///" + tmp_path.replace("\\", "/")
        ps = (
            "Add-Type -AssemblyName presentationCore; "
            "$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([System.Uri]'{uri}'); "
            "$p.Play(); "
            "Start-Sleep -Milliseconds 800; "
            "while (-not $p.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds 50 }; "
            "$dur = [int]$p.NaturalDuration.TimeSpan.TotalMilliseconds; "
            "Start-Sleep -Milliseconds ($dur + 300); "
            "$p.Close()"
        )
        subprocess.run(["powershell", "-Command", ps], check=False)
        os.unlink(tmp_path)
        return True
    except Exception as e:
        print(f"[voice] ElevenLabs error: {e} — falling back to SAPI5")
        return False


def _speak_sapi5(text: str, rate: int = 185):
    sapi_rate = max(-10, min(10, int((rate - 150) / 15)))
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Rate = {sapi_rate}; "
        "$s.Speak($env:HORUS_SPEECH)"
    )
    env = os.environ.copy()
    env["HORUS_SPEECH"] = text
    subprocess.run(["powershell", "-Command", ps], env=env, check=False)


class VoicePipeline:
    def __init__(self):
        self.whisper_model = whisper.load_model("base")

    def _record_and_transcribe(self, duration: int) -> str:
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        audio_np = audio.squeeze()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        wav.write(tmp_path, SAMPLE_RATE, (audio_np * 32767).astype(np.int16))
        result = self.whisper_model.transcribe(tmp_path, language="en")
        os.unlink(tmp_path)
        return result["text"].strip()

    def listen(self) -> str:
        return self._record_and_transcribe(DURATION)

    def listen_for_wake_word(self) -> bool:
        audio = sd.rec(
            int(WAKE_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        if np.abs(audio).mean() < SILENCE_THRESHOLD:
            return False

        audio_np = audio.squeeze()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        wav.write(tmp_path, SAMPLE_RATE, (audio_np * 32767).astype(np.int16))
        result = self.whisper_model.transcribe(tmp_path, language="en")
        os.unlink(tmp_path)
        text = result["text"].lower().strip()
        print(f"[wake] heard: {text!r}")
        WAKE_VARIANTS = ("horus", "horace", "horas", "harris", "hora", "horse")
        return any(v in text for v in WAKE_VARIANTS)

    def speak(self, text: str, rate: int = 185):
        if not _speak_elevenlabs(text):
            if sys.platform == "win32":
                _speak_sapi5(text, rate)
            else:
                subprocess.run(["say", "-v", "Daniel", "-r", str(rate), text], check=False)
