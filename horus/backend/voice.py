import tempfile
import os
import subprocess
import numpy as np
import sounddevice as sd
import whisper
import scipy.io.wavfile as wav

SAMPLE_RATE = 16000
DURATION = 5
WAKE_DURATION = 2
WAKE_WORD = "horus"
SILENCE_THRESHOLD = 0.01


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
        """Record a short clip; return True if wake word detected."""
        audio = sd.rec(
            int(WAKE_DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        # Skip transcription if silent
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
        # Whisper often mishears "Horus" — cast a wide net
        WAKE_VARIANTS = ("horus", "horace", "horas", "harris", "hora", "horse")
        return any(v in text for v in WAKE_VARIANTS)

    def speak(self, text: str, rate: int = 185):
        subprocess.run(["say", "-v", "Daniel", "-r", str(rate), text], check=False)
