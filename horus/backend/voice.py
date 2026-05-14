import tempfile
import os
import subprocess
import numpy as np
import sounddevice as sd
import whisper

SAMPLE_RATE = 16000
DURATION = 5  # seconds to record per voice turn


class VoicePipeline:
    def __init__(self):
        self.whisper_model = whisper.load_model("base")

    def listen(self) -> str:
        audio = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        audio_np = audio.squeeze()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        import scipy.io.wavfile as wav
        wav.write(tmp_path, SAMPLE_RATE, (audio_np * 32767).astype(np.int16))

        result = self.whisper_model.transcribe(tmp_path)
        os.unlink(tmp_path)
        return result["text"].strip()

    def speak(self, text: str):
        # macOS built-in `say` — works reliably in threads, no extra deps
        subprocess.run(["say", "-v", "Daniel", "-r", "185", text], check=False)
