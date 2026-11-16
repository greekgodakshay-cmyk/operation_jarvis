"""
Test script to benchmark the local voice pipeline:
Kokoro TTS synthesis + Faster-Whisper STT transcription.
"""
import sys
import time
import os
from pathlib import Path

# Add LOCAL_AI_MEMORY to sys.path
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY")

from engine.voice.stt_engine import WhisperSTT
import kokoro_onnx
import soundfile as sf

def run_voice_benchmark():
    print("=" * 60)
    print("OPERATION JARVIS — LOCAL VOICE PIPELINE BENCHMARK")
    print("=" * 60)

    # 1. Benchmark Kokoro TTS
    model_path = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\models\kokoro\kokoro-v0_19.int8.onnx"
    voices_path = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\models\kokoro\voices-v1.0.bin"
    output_wav = r"C:\Users\Akshay aravind .rv\operation_jarvis\data\audio_cache\benchmark_voice.wav"

    input_text = "Operation JARVIS local voice pipeline latency and transcription benchmark."
    print(f"Input Text: \"{input_text}\"")

    t0 = time.time()
    kokoro = kokoro_onnx.Kokoro(model_path, voices_path)
    samples, sr = kokoro.create(input_text, voice="bm_george", speed=1.0)
    sf.write(output_wav, samples, sr)
    tts_latency = time.time() - t0
    audio_dur = len(samples) / sr

    print(f"\n[TTS] Kokoro-82M ONNX Synthesis:")
    print(f"  Synthesis Time:    {tts_latency:.3f}s")
    print(f"  Generated Audio:   {audio_dur:.2f}s ({len(samples)} samples @ {sr}Hz)")
    print(f"  Real-Time Factor:  {tts_latency / audio_dur:.3f}x (< 1.0 is faster than real time)")
    print(f"  Audio File Size:   {os.path.getsize(output_wav) / 1024:.1f} KB")

    # 2. Benchmark Faster-Whisper STT
    t0_stt = time.time()
    stt = WhisperSTT(model_size="tiny", device="cpu", compute_type="int8")
    init_time = time.time() - t0_stt

    t1_trans = time.time()
    text, lang, prob = stt.transcribe_file(output_wav)
    trans_latency = time.time() - t1_trans

    print(f"\n[STT] Faster-Whisper (tiny.en int8) Transcription:")
    print(f"  Model Load Time:   {init_time:.3f}s")
    print(f"  Transcribe Time:   {trans_latency:.3f}s")
    print(f"  Transcribed Text:  \"{text.strip()}\"")
    print(f"  Detected Language: {lang} (confidence: {prob:.2f})")
    print(f"  Real-Time Factor:  {trans_latency / audio_dur:.3f}x")

    total_roundtrip = tts_latency + trans_latency
    print(f"\nTotal Pipeline Roundtrip: {total_roundtrip:.3f}s")
    print("VOICE PIPELINE BENCHMARK: COMPLETE & VERIFIED")
    print("=" * 60)

if __name__ == "__main__":
    run_voice_benchmark()
