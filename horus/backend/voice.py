import os
import tempfile  # still used by listen/_record_and_transcribe
import threading
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
import whisper
import scipy.io.wavfile as wav
import pyttsx3
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SAMPLE_RATE = 16000
DURATION = 5
WAKE_DURATION = 2
WAKE_WORD = "horus"
SILENCE_THRESHOLD = 0.01

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=pcm_22050"


def list_input_devices() -> list[dict]:
    try:
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"]}
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]
    except Exception:
        return []


class VoicePipeline:
    def __init__(self):
        self.whisper_model = whisper.load_model("base")
        self.device_index = None
        self._stop_event = threading.Event()

    def interrupt(self):
        self._stop_event.set()
        sd.stop()

    def stop_speaking(self):
        self._stop_event.set()
        sd.stop()

    def speak(self, text: str, rate: int = 185):
        self._stop_event.clear()
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        print(f"[voice] api_key={'set' if api_key else 'MISSING'}  voice_id={'set' if voice_id else 'MISSING'}")
        if api_key and voice_id:
            self._speak_elevenlabs(text, api_key, voice_id)
        else:
            print("[voice] falling back to pyttsx3 — missing ElevenLabs credentials")
            self._speak_pyttsx3(text, rate)

    def _speak_elevenlabs(self, text: str, api_key: str, voice_id: str):
        url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "use_speaker_boost": True,
            },
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=15)
            resp.raise_for_status()

            pcm_data = b""
            for chunk in resp.iter_content(chunk_size=4096):
                if self._stop_event.is_set():
                    return
                if chunk:
                    pcm_data += chunk

            if self._stop_event.is_set() or not pcm_data:
                return

            # Decode raw PCM → float32 and play directly
            audio = np.frombuffer(pcm_data, dtype="<i2").astype(np.float32) / 32768.0
            duration = len(audio) / 22050
            sd.play(audio, samplerate=22050)

            # Poll until done or stopped
            deadline = time.time() + duration + 0.5
            while time.time() < deadline:
                if self._stop_event.is_set():
                    sd.stop()
                    return
                time.sleep(0.05)
            sd.wait()

        except Exception as e:
            print(f"[ElevenLabs] error: {e}")
            if not self._stop_event.is_set():
                self._speak_pyttsx3(text, 185)

    def _speak_pyttsx3(self, text: str, rate: int = 185):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[pyttsx3] error: {e}")

    def _record_and_transcribe(self, duration: int) -> str:
        audio = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.device_index,
        )
        sd.wait()
        audio_np = audio.squeeze()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        wav.write(tmp_path, SAMPLE_RATE, (audio_np * 32767).astype(np.int16))
        result = self.whisper_model.transcribe(tmp_path, language="en")
        os.unlink(tmp_path)
        return result["text"].strip()

    def listen(self, timeout: int = DURATION) -> str:
        self._stop_event.clear()
        return self._record_and_transcribe(timeout)

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
