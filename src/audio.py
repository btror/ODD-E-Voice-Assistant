"""Audio recording and speech-to-text transcription."""

import queue
import numpy as np
import sounddevice as sd
import keyboard
from faster_whisper import WhisperModel


COMMAND_HINT = (
    "Voice assistant commands about Spotify. Common phrases include: "
    "play, pause, resume, next, previous, open spotify, "
    "play my <playlist> playlist, play <song> by <artist>, volume up, volume down."
)


class PTTRecorder:
    """Push-to-talk audio recorder."""
    
    def __init__(self, device=None, samplerate=48000, verbose=False):
        self.device = device
        self.samplerate = samplerate
        self.q = queue.Queue()
        self.recording = False
        self.stream = None
        self.verbose = verbose

    def _callback(self, indata, frames, time_info, status):
        """Audio input callback."""
        if self.recording:
            self.q.put(indata.copy())

    def start(self):
        """Start the audio input stream."""
        self.stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.samplerate,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        """Stop the audio input stream."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def record_blocking(self, hotkey):
        """Record audio while hotkey is held, yielding audio chunks."""
        print(f"[assistant] Hold '{hotkey}' to speak...")
        while True:
            keyboard.wait(hotkey, suppress=False, trigger_on_release=False)
            self.recording = True
            print("[assistant] Listening...")
            chunks = []
            while keyboard.is_pressed(hotkey):
                try:
                    chunks.append(self.q.get(timeout=0.1))
                except queue.Empty:
                    pass
            self.recording = False
            if chunks:
                audio = np.concatenate(chunks, axis=0).flatten()
                if self.verbose:
                    print(f"[debug] captured {len(audio)} samples")
                yield audio
            print("[assistant] Processing...")


def _downsample_to_16k(x: np.ndarray, sr_in: int) -> np.ndarray:
    """Downsample audio from 48k to 16k."""
    if sr_in == 48000:
        return x[::3]  # simple 48k -> 16k decimation
    return x


def transcribe_audio(model: WhisperModel, audio: np.ndarray, sr: int = 48000, use_vad: bool = True) -> str:
    """Transcribe audio using Whisper model."""
    audio_f32 = audio.astype(np.float32, copy=False)
    audio_16k = _downsample_to_16k(audio_f32, sr)
    
    # Some ONNXRuntime builds can segfault with VAD; guard + fallback
    try:
        segments, _ = model.transcribe(
            audio_16k,
            language="en",
            vad_filter=use_vad,
            vad_parameters=dict(min_silence_duration_ms=200),
            beam_size=5,
            temperature=[0.0, 0.2, 0.4],
            initial_prompt=COMMAND_HINT,
            condition_on_previous_text=False,
        )
    except Exception as e:
        print("[assistant] VAD path failed, retrying without VAD →", e)
        segments, _ = model.transcribe(
            audio_16k,
            language="en",
            vad_filter=False,
            beam_size=5,
            temperature=[0.0, 0.2, 0.4],
            initial_prompt=COMMAND_HINT,
            condition_on_previous_text=False,
        )
    return "".join(s.text for s in segments).strip()

