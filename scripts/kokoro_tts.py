"""
Kokoro ONNX Voice Synthesis Engine for Operation JARVIS.
Invoked by the Python 3.11 .venv_voice runtime to render spoken responses.
"""
import sys
import os
from pathlib import Path

def synthesize(text: str, output_path: str, voice: str = "bm_george", speed: float = 1.0) -> bool:
    import kokoro_onnx
    import soundfile as sf

    model_path = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\models\kokoro\kokoro-v0_19.int8.onnx"
    voices_path = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\models\kokoro\voices-v1.0.bin"

    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        print(f"Error: Kokoro models missing at {model_path}", file=sys.stderr)
        return False

    try:
        kokoro = kokoro_onnx.Kokoro(model_path, voices_path)
        samples, sr = kokoro.create(text, voice=voice, speed=speed)
        
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out), samples, sr)
        return True
    except Exception as e:
        print(f"Synthesis error: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: kokoro_tts.py <text> <output_wav_path> [voice] [speed]")
        sys.exit(1)

    text_arg = sys.argv[1]
    out_arg = sys.argv[2]
    voice_arg = sys.argv[3] if len(sys.argv) > 3 else "bm_george"
    speed_arg = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    ok = synthesize(text_arg, out_arg, voice=voice_arg, speed=speed_arg)
    if ok:
        print(f"OK:{out_arg}")
        sys.exit(0)
    else:
        sys.exit(1)
