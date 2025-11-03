import os
os.environ.setdefault("ORT_DISABLE_CUDA", "1")  # keep onnx out of CUDA path
os.environ.setdefault(
    "HUGGINGFACE_HUB_CACHE",
    os.path.expandvars(r"%USERPROFILE%\hfcache")
)
os.environ.setdefault("CT2_LOG_LEVEL", "INFO")

def _try_add_dll_dir(path: str):
    try:
        if os.path.isdir(path):
            os.add_dll_directory(path)
    except Exception:
        pass

# CUDA 13 + cuDNN 9
_try_add_dll_dir(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin")
_try_add_dll_dir(r"C:\Program Files\NVIDIA\CUDNN\v9.14\bin\13.0")
# Probe CUDA 12.x + cuDNN 12.9 in case a wheel reaches for cublas64_12.dll
_try_add_dll_dir(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin")
_try_add_dll_dir(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin")
_try_add_dll_dir(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin")
_try_add_dll_dir(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin")
_try_add_dll_dir(r"C:\Program Files\NVIDIA\CUDNN\v9.14\bin\12.9")

import re, time, json, queue, ctypes, subprocess, sys, traceback, argparse
from typing import Optional, Tuple, List

import numpy as np
import sounddevice as sd
import keyboard
import pygetwindow as gw
from rapidfuzz import fuzz, process
from faster_whisper import WhisperModel

# --------------------------- Excepthook ---------------------------
def _install_excepthook():
    def _hook(exc_type, exc, tb):
        try:
            with open("error.log", "a", encoding="utf-8") as f:
                f.write("\n--- Uncaught exception ---\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
            print("\n[assistant] Uncaught exception:")
            traceback.print_exception(exc_type, exc, tb)
        except Exception:
            try:
                sys.__stderr__.write(f"\n[assistant] fatal: {exc_type.__name__}: {exc}\n")
            except Exception:
                pass
    sys.excepthook = _hook
_install_excepthook()

# --------------------------- Config ---------------------------
CONFIG_PATH = "config.json"
DEFAULT_CONFIG = {
    "playlists": {},
    "whisper_model": "small",
    "push_to_talk_key": "right ctrl"
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CFG = load_config()

# Allow .env to override top-level fields if JSON leaves them empty
CFG["whisper_model"] = CFG.get("whisper_model") or os.getenv("WHISPER_MODEL", "small")
CFG["push_to_talk_key"] = CFG.get("push_to_talk_key") or os.getenv("PTT_KEY", "right ctrl")

# --------------------------- Spotify helpers ---------------------------
def ensure_spotify_running() -> bool:
    """Open Spotify if it's not already running."""
    for title in gw.getAllTitles():
        if "Spotify" in title:
            return True
    candidates = [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                subprocess.Popen([p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
                return True
            except Exception:
                pass
    try:
        os.startfile("spotify:")
        time.sleep(2)
        return True
    except Exception:
        return False

def bring_spotify_to_front() -> bool:
    titles = [t for t in gw.getAllTitles() if "Spotify" in t]
    if not titles:
        return False
    try:
        win = gw.getWindowsWithTitle(titles[0])[0]
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(0.15)
        return True
    except Exception:
        return False

def media_transport(cmd: str) -> bool:
    keymap = {
        "play": "play/pause media",
        "pause": "play/pause media",
        "resume": "play/pause media",
        "next": "next track",
        "previous": "previous track",
        "prev": "previous track",
        "mute": "volume mute",
        "volup": "volume up",
        "voldown": "volume down",
    }
    k = keymap.get(cmd)
    if k:
        keyboard.send(k)
        return True
    return False

def open_spotify_uri(uri: str) -> bool:
    try:
        os.startfile(uri)
        return True
    except Exception:
        return False

def search_and_play(query: str) -> bool:
    """Global search and play top hit via UI (no Spotify API needed)."""
    if not bring_spotify_to_front():
        ensure_spotify_running()
        time.sleep(0.6)
        bring_spotify_to_front()
    # Global search shortcut (recent Spotify builds)
    keyboard.press_and_release("ctrl+k")
    time.sleep(0.10)
    keyboard.write(query, delay=0.01)
    time.sleep(0.15)
    keyboard.press_and_release("enter")   # go to results
    time.sleep(0.85)
    keyboard.press_and_release("enter")   # play top hit
    return True

# --------------------------- Intent parsing (fuzzy) ---------------------------
def normalize(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower()).strip()

def best_match(name: str, keys: List[str], cutoff: int = 78) -> Optional[Tuple[str, int]]:
    if not keys:
        return None
    norm_keys = [normalize(k) for k in keys]
    hit = process.extractOne(normalize(name), norm_keys, scorer=fuzz.token_set_ratio)
    if hit and hit[1] >= cutoff:
        idx = norm_keys.index(hit[0])
        return keys[idx], hit[1]
    return None

def parse_intent(text: str, playlists: dict) -> Tuple[str, Optional[str]]:
    t = normalize(text)

    # Transport
    if t in {"play", "pause", "resume", "next", "previous", "prev", "mute"}:
        return ("transport", "previous" if t == "prev" else t)
    if t in {"volume up", "turn it up", "louder", "vol up"}:
        return ("transport", "volup")
    if t in {"volume down", "turn it down", "quieter", "vol down"}:
        return ("transport", "voldown")

    # "play my|the <name> playlist"
    m = re.match(r"^play( my| the)? (.+) playlist$", t)
    if m:
        raw = m.group(2).strip()
        hit = best_match(raw, list(playlists.keys()))
        if hit:
            return ("playlist", playlists[hit[0]])
        return ("say", f"I don't know the '{raw}' playlist. Add it to config.json.")

    # "play my|the <name>" → playlist if known, else treat as song/artist
    m = re.match(r"^play( my| the)? (.+)$", t)
    if m:
        raw = m.group(2).strip()
        hit = best_match(raw, list(playlists.keys()))
        if hit:
            return ("playlist", playlists[hit[0]])
        return ("song", raw)

    if t in {"open spotify", "launch spotify", "open spoti", "open the spotify"}:
        return ("open", None)

    return ("say", "Unrecognized command.")

# --------------------------- PTT Recorder (48k capture) ---------------------------
class PTTRecorder:
    def __init__(self, device=None, samplerate=48000, verbose=False):
        self.device = device
        self.samplerate = samplerate
        self.q = queue.Queue()
        self.recording = False
        self.stream = None
        self.verbose = verbose

    def _callback(self, indata, frames, time_info, status):
        if self.recording:
            self.q.put(indata.copy())

    def start(self):
        self.stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.samplerate,
            dtype="float32",
            callback=self._callback,
        )
        self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def record_blocking(self, hotkey):
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

# --------------------------- Whisper STT ---------------------------
COMMAND_HINT = (
    "Voice assistant commands about Spotify. Common phrases include: "
    "play, pause, resume, next, previous, open spotify, "
    "play my <playlist> playlist, play <song> by <artist>, volume up, volume down."
)

def _downsample_to_16k(x: np.ndarray, sr_in: int) -> np.ndarray:
    if sr_in == 48000:
        return x[::3]  # simple 48k -> 16k decimation
    return x

def transcribe_audio(model, audio, sr=48000, use_vad=True):
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

# --------------------------- Main ---------------------------
def build_argparser():
    p = argparse.ArgumentParser(description="Voice → Spotify assistant")
    p.add_argument("--hotkey", default=CFG.get("push_to_talk_key", "right ctrl"))
    p.add_argument("--mic", type=int, default=None, help="sounddevice input index (e.g., 25)")
    p.add_argument("--model", default=CFG.get("whisper_model", "small"))
    p.add_argument("--compute", default="float16", choices=["int8", "float16", "float32"])
    p.add_argument("--cpu", action="store_true", help="force CPU inference")
    p.add_argument("--no-vad", action="store_true", help="disable VAD pre-segmentation")
    p.add_argument("--verbose", action="store_true")
    return p

def main():
    print("[boot] assistant.py starting…")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    args = build_argparser().parse_args()

    ensure_spotify_running()
    bring_spotify_to_front()

    print("[assistant] Loading Whisper…")
    device = "cpu" if args.cpu else "cuda"
    compute_type = args.compute if device == "cuda" else ("int8" if args.compute == "float16" else args.compute)

    # Init model (GPU then CPU fallback if needed)
    try:
        model = WhisperModel(
            args.model,
            device=device,
            compute_type=compute_type,
            device_index=0,
            download_root=os.environ["HUGGINGFACE_HUB_CACHE"],
        )
    except Exception as e:
        print("[assistant] GPU init failed (or forced CPU):", e, "→ falling back to CPU")
        model = WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            download_root=os.environ["HUGGINGFACE_HUB_CACHE"],
        )

    # Audio / mic selection
    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = None
    print(f"[audio] default input device: {default_in}")

    if args.verbose:
        # dump hostapis + devices
        print(sd.query_hostapis())

    if args.mic is not None:
        sd.default.device = (args.mic, None)
        # Prefer WASAPI to dodge MME weirdness
        try:
            sd.default.hostapi = 2  # Windows WASAPI
        except Exception:
            pass

    rec = PTTRecorder(device=sd.default.device[0], samplerate=48000, verbose=args.verbose)
    rec.start()

    hotkey = args.hotkey
    print(f"[assistant] Hold '{hotkey}' to speak...")
    use_vad = not args.no_vad

    try:
        for audio in rec.record_blocking(hotkey):
            try:
                text = transcribe_audio(model, audio, sr=48000, use_vad=use_vad)
                if not text:
                    print("[assistant] Heard nothing useful.")
                    continue
                print(f"[you] {text}")
                typ, arg = parse_intent(text, CFG.get("playlists", {}))
                if args.verbose:
                    print(f"[debug] intent={typ} arg={arg!r}")

                if typ == "transport":
                    media_transport(arg)
                elif typ == "playlist":
                    ensure_spotify_running(); bring_spotify_to_front()
                    if arg: open_spotify_uri(arg)
                    else:   print("[assistant] Missing playlist URI.")
                elif typ == "song":
                    ensure_spotify_running(); search_and_play(arg)
                elif typ == "open":
                    ensure_spotify_running(); bring_spotify_to_front()
                elif typ == "say":
                    print(f"[assistant] {arg}")
            except KeyboardInterrupt:
                raise
            except Exception:
                print("[assistant] Handler blew up:")
                traceback.print_exc()
    except KeyboardInterrupt:
        print("\n[assistant] Ctrl+C — shutting down.")
    finally:
        rec.stop()

if __name__ == "__main__":
    main()
