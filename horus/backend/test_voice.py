"""
Voice diagnostic.
Run: ..\venv\Scripts\python.exe test_voice.py
"""
from dotenv import load_dotenv
from pathlib import Path
import os, requests, wave, winsound, time, tempfile
import numpy as np
import sounddevice as sd

load_dotenv(Path(__file__).parent / ".env", override=True)
key = os.getenv("ELEVENLABS_API_KEY", "")
vid = os.getenv("ELEVENLABS_VOICE_ID", "")
print("Voice ID:", vid)

url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/stream"
headers = {"xi-api-key": key, "Content-Type": "application/json"}

def get_pcm(fmt):
    payload = {
        "text": "Hello, I am Horus. Your AI assistant.",
        "model_id": "eleven_turbo_v2_5",
        "output_format": fmt,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.content

# --- Test both sample rates ---
print("\n--- pcm_22050 ---")
pcm22 = get_pcm("pcm_22050")
s22 = np.frombuffer(pcm22, dtype='<i2')
print(f"  bytes={len(pcm22)}  samples={len(s22)}  dur={len(s22)/22050:.2f}s  mean_abs={int(np.abs(s22).mean())}  first5={s22[:5].tolist()}")

print("\n--- pcm_44100 ---")
pcm44 = get_pcm("pcm_44100")
s44 = np.frombuffer(pcm44, dtype='<i2')
print(f"  bytes={len(pcm44)}  samples={len(s44)}  dur@44100={len(s44)/44100:.2f}s  dur@22050={len(s44)/22050:.2f}s  mean_abs={int(np.abs(s44).mean())}  first5={s44[:5].tolist()}")

# If pcm_44100 actual duration (at 44100) ≈ pcm_22050 duration, it's real 44100 Hz.
# If pcm_44100 duration (at 44100) ≈ half of pcm_22050 duration, it returned 22050 Hz data.
print(f"\n  pcm_22050 duration:  {len(s22)/22050:.2f}s")
print(f"  pcm_44100 @44100Hz:  {len(s44)/44100:.2f}s  <-- same if 44100 Hz is real")
print(f"  pcm_44100 @22050Hz:  {len(s44)/22050:.2f}s  <-- same if ElevenLabs sent 22050 Hz data mislabeled")

# --- Write WAV files to temp dir ---
tmp = Path(tempfile.gettempdir())

wav22_path = str(tmp / "horus_22050.wav")
with wave.open(wav22_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050); wf.writeframes(pcm22)
print(f"\nSaved: {wav22_path}")

wav44_path = str(tmp / "horus_44100.wav")
with wave.open(wav44_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(44100); wf.writeframes(pcm44)
print(f"Saved: {wav44_path}")

# Also write the 44k data AS IF it were 22050 Hz
wav44as22_path = str(tmp / "horus_44k_as_22050.wav")
with wave.open(wav44as22_path, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050); wf.writeframes(pcm44)
print(f"Saved: {wav44as22_path}  (44k data played at 22050 Hz rate — slower)")

print("\n--- Output devices ---")
for i, d in enumerate(sd.query_devices()):
    if d['max_output_channels'] > 0:
        print(f"  [{i}] {d['name']}")

print(f"\nDefault output: {sd.query_devices(kind='output')['name']}")

print("\n=== Playing 22050 Hz WAV via winsound ===")
winsound.PlaySound(wav22_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
time.sleep(len(s22)/22050 + 1.0)
print("done\n")

time.sleep(0.5)

print("=== Playing 44100 Hz WAV via winsound ===")
winsound.PlaySound(wav44_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
time.sleep(len(s44)/44100 + 1.0)
print("done\n")

time.sleep(0.5)

print("=== Playing 22050 Hz WAV via sounddevice ===")
sd.play(s22.astype(np.float32) / 32768.0, samplerate=22050)
sd.wait()
print("done\n")
