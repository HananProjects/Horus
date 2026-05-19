import tempfile
import os
import sys
import time
import threading
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
WAKE_DURATION = 2
WAKE_WORD = "horus"
SILENCE_THRESHOLD = 0.012   # amplitude RMS to consider as speech
SPEECH_THRESHOLD = 0.025    # louder threshold to trigger speech start
CHUNK = 1024                # samples per read block (~64ms at 16kHz)
PRE_ROLL_CHUNKS = 8         # keep ~0.5s before speech detected
SILENCE_CHUNKS = 22         # ~1.4s of quiet before stopping
MAX_RECORD_SECONDS = 30

_stop_event = threading.Event()


def interrupt():
    """Stop the current speech immediately."""
    _stop_event.set()


def _run_interruptible(args, env=None):
    """Run a subprocess and kill it if interrupt() is called."""
    _stop_event.clear()
    proc = subprocess.Popen(args, env=env)
    while proc.poll() is None:
        if _stop_event.is_set():
            proc.kill()
            return
        time.sleep(0.05)


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
        _run_interruptible(["powershell", "-Command", ps])
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
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
    _run_interruptible(["powershell", "-Command", ps], env=env)


def list_input_devices() -> list[dict]:
    """Return MME input devices only (avoids DirectSound/WASAPI duplicates)."""
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["hostapi"] == 0:
            devices.append({"index": i, "name": d["name"]})
    return devices


class VoicePipeline:
    def __init__(self):
        self.whisper_model = whisper.load_model("base")
        self.device_index = None  # None = system default

    def _transcribe(self, audio_np: np.ndarray) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        wav.write(tmp_path, SAMPLE_RATE, (audio_np * 32767).astype(np.int16))
        result = self.whisper_model.transcribe(tmp_path, language="en")
        os.unlink(tmp_path)
        return result["text"].strip()

    def listen(self, max_seconds: int = MAX_RECORD_SECONDS) -> str:
        """VAD-based recording: waits for speech, stops on silence."""
        print("[voice] ready — waiting for speech...")
        pre_roll: list[np.ndarray] = []
        chunks: list[np.ndarray] = []
        speech_started = False
        silence_count = 0
        max_chunks = (max_seconds * SAMPLE_RATE) // CHUNK

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK,
            device=self.device_index,
        )
        stream.start()
        try:
            for _ in range(max_chunks):
                data, _ = stream.read(CHUNK)
                amplitude = float(np.abs(data).mean())

                if not speech_started:
                    pre_roll.append(data.copy())
                    if len(pre_roll) > PRE_ROLL_CHUNKS:
                        pre_roll.pop(0)
                    if amplitude > SPEECH_THRESHOLD:
                        speech_started = True
                        chunks.extend(pre_roll)
                        pre_roll = []
                        print("[voice] speech detected")
                else:
                    chunks.append(data.copy())
                    if amplitude < SILENCE_THRESHOLD:
                        silence_count += 1
                        if silence_count >= SILENCE_CHUNKS:
                            print("[voice] silence — stopping")
                            break
                    else:
                        silence_count = 0
        finally:
            stream.stop()
            stream.close()

        if not chunks:
            print("[voice] no speech detected")
            return ""

        audio_np = np.concatenate(chunks).squeeze()
        return self._transcribe(audio_np)

    def listen_for_wake_word(self) -> bool:
        audio = sd.rec(
            int(WAKE_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.device_index,
        )
        sd.wait()
        if np.abs(audio).mean() < SILENCE_THRESHOLD:
            return False

        audio_np = audio.squeeze()
        text = self._transcribe(audio_np).lower()
        print(f"[wake] heard: {text!r}")
        WAKE_VARIANTS = ("horus", "horace", "horas", "harris", "hora", "horse")
        return any(v in text for v in WAKE_VARIANTS)

    def speak(self, text: str, rate: int = 185):
        if not _speak_elevenlabs(text):
            if sys.platform == "win32":
                _speak_sapi5(text, rate)
            else:
                subprocess.run(["say", "-v", "Daniel", "-r", str(rate), text], check=False)
