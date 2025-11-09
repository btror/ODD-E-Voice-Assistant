from textwrap import dedent

"""
assistant_api.py — Voice → Spotify assistant that uses the Spotify Web API
instead of UI automation. Drop this file next to your existing assistant.py
and run it with the same flags. First run will pop a browser window to auth.

Requires env vars:
  SPOTIFY_CLIENT_ID
  SPOTIFY_CLIENT_SECRET
  SPOTIFY_REDIRECT_URI  (e.g., http://localhost:8080/callback)

Optional:
  SPOTIFY_DEVICE_NAME   (preferred playback device name to auto-target)

Install deps:
  pip install spotipy python-dotenv

This keeps your existing config.json playlist map and intent parsing.
"""

import os
import argparse
import ctypes
import traceback
from typing import Optional

from dotenv import load_dotenv

# Project-local imports (reuse your existing modules)
try:
    from src.env_setup import initialize
    from src.config import load_config
    from src.intent_parser import parse_intent
    from src.audio import PTTRecorder, transcribe_audio
    from faster_whisper import WhisperModel
    import sounddevice as sd
except Exception as e:
    # Fallback if the repo uses flat layout without src/
    initialize = lambda: None
    def load_config():
        import json
        with open("config.json","r",encoding="utf-8") as f:
            return json.load(f)
    from intent_parser import parse_intent       # raises if not present
    from audio import PTTRecorder, transcribe_audio
    from faster_whisper import WhisperModel
    import sounddevice as sd

# Third-party for Spotify API
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# ---------- Boot env ----------
def boot_env():
    # load .env if present
    load_dotenv(override=False)
    # if repo provides initialize() do it
    try:
        initialize()
    except Exception:
        pass


# ---------- Spotify API control ----------
class SpotifyAPI:
    def __init__(self):
        scope = (
            "user-read-playback-state "
            "user-modify-playback-state "
            "user-read-currently-playing"
        )
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
        cache_path = os.getenv("SPOTIPY_CACHE", ".spotipyoauthcache")
        if not (client_id and client_secret):
            raise RuntimeError("Missing SPOTIFY_CLIENT_ID/SECRET env vars. Put them in .env.")
        self.oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope,
            cache_path=cache_path,
            open_browser=True,
            show_dialog=False,
        )
        self.sp = spotipy.Spotify(auth_manager=self.oauth)

    # ---- helpers ----
    def _pick_device_id(self) -> Optional[str]:
        devices = self.sp.devices().get("devices", [])
        if not devices:
            return None
        pref = os.getenv("SPOTIFY_DEVICE_NAME")
        if pref:
            for d in devices:
                if d.get("name","").lower() == pref.lower():
                    return d["id"]
        # choose active device, else first available
        for d in devices:
            if d.get("is_active"):
                return d["id"]
        return devices[0]["id"]

    def _ensure_device(self) -> Optional[str]:
        did = self._pick_device_id()
        if not did:
            return None
        # transfer playback to preferred device but do not auto-play
        try:
            self.sp.transfer_playback(device_id=did, force_play=False)
        except spotipy.SpotifyException:
            pass
        return did

    # ---- transports ----
    def play_pause(self):
        pb = self.sp.current_playback()
        if pb and pb.get("is_playing"):
            self.sp.pause_playback()
        else:
            self.sp.start_playback()

    def next(self):
        self.sp.next_track()

    def previous(self):
        self.sp.previous_track()

    def volume_step(self, delta: int):
        did = self._ensure_device()
        if not did:
            print("[spotify] No active device. Open Spotify on any device.")
            return
        pb = self.sp.current_playback()
        vol = 50
        if pb and pb.get("device"):
            vol = pb["device"].get("volume_percent", 50)
        vol = max(0, min(100, vol + delta))
        self.sp.volume(vol, device_id=did)

    # ---- content ----
    def start_playlist(self, context_uri: str):
        did = self._ensure_device()
        if not did:
            print("[spotify] No active device. Open Spotify on any device.")
            return
        # start from top of playlist
        self.sp.start_playback(device_id=did, context_uri=context_uri, offset={"position": 0}, position_ms=0)

    def search_and_play(self, query: str):
        did = self._ensure_device()
        if not did:
            print("[spotify] No active device. Open Spotify on any device.")
            return
        res = self.sp.search(q=query, limit=1, type="track")
        items = res.get("tracks", {}).get("items", [])
        if not items:
            print(f"[spotify] No track results for: {query}")
            return
        track_uri = items[0]["uri"]
        self.sp.start_playback(device_id=did, uris=[track_uri], position_ms=0)


# ---------- CLI / Whisper plumbing (same UX as your current script) ----------
CFG = None

def build_argparser():
    import json
    p = argparse.ArgumentParser(description="Voice → Spotify (Web API edition)")
    p.add_argument("--hotkey", default=(CFG.get("push_to_talk_key") if CFG else "f9"))
    p.add_argument("--mic", type=int, default=None, help="sounddevice input index (e.g., 25)")
    p.add_argument("--model", default=(CFG.get("whisper_model") if CFG else "small"))
    p.add_argument("--compute", default="float16", choices=["int8", "float16", "float32"])
    p.add_argument("--cpu", action="store_true", help="force CPU inference")
    p.add_argument("--no-vad", action="store_true", help="disable VAD pre-segmentation")
    p.add_argument("--verbose", action="store_true")
    return p


def load_whisper_model(args):
    device = "cpu" if args.cpu else "cuda"
    compute_type = args.compute if device == "cuda" else ("int8" if args.compute == "float16" else args.compute)
    try:
        model = WhisperModel(
            args.model,
            device=device,
            compute_type=compute_type,
            device_index=0,
            download_root=os.environ.get("HUGGINGFACE_HUB_CACHE"),
        )
        return model
    except Exception as e:
        print("[assistant-api] GPU init failed (or forced CPU):", e, "→ falling back to CPU")
        return WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            download_root=os.environ.get("HUGGINGFACE_HUB_CACHE"),
        )


def setup_audio_device(args):
    try:
        default_in = sd.default.device[0]
    except Exception:
        default_in = None
    print(f"[audio] default input device: {default_in}")
    if args.verbose:
        print(sd.query_hostapis())
    if args.mic is not None:
        sd.default.device = (args.mic, None)
        try:
            sd.default.hostapi = 2  # Windows WASAPI
        except Exception:
            pass
    return sd.default.device[0]


def handle_intent_api(sp: SpotifyAPI, typ: str, arg: str):
    if typ == "transport":
        if arg in {"play", "pause", "resume"}:
            sp.play_pause()
        elif arg == "next":
            sp.next()
        elif arg in {"previous", "prev"}:
            sp.previous()
        elif arg == "volup":
            sp.volume_step(+10)
        elif arg == "voldown":
            sp.volume_step(-10)
        elif arg == "mute":
            sp.volume_step(-100)
    elif typ == "playlist":
        if not arg:
            print("[assistant-api] Missing playlist URI.")
        else:
            sp.start_playlist(arg)
    elif typ == "song":
        sp.search_and_play(arg)
    elif typ == "open":
        # Not needed with Web API; we just target a device if available.
        did = sp._ensure_device()
        if did:
            print("[assistant-api] Target device ready.")
        else:
            print("[assistant-api] Open Spotify on any device to create an active session.")
    elif typ == "say":
        print(f"[assistant-api] {arg}")


def main():
    boot_env()
    global CFG
    CFG = load_config()

    # DPI awareness (Windows nicety)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    args = build_argparser().parse_args()

    # Spotify API client
    try:
        sp = SpotifyAPI()
    except Exception as e:
        print("[assistant-api] Spotify auth failed:", e)
        print("Make sure SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI are set.")
        return

    print("[assistant-api] Loading Whisper…")
    model = load_whisper_model(args)

    # audio
    device = setup_audio_device(args)
    rec = PTTRecorder(device=device, samplerate=48000, verbose=args.verbose)
    rec.start()

    hotkey = args.hotkey
    print(f"[assistant-api] Hold '{hotkey}' to speak...")
    use_vad = not args.no_vad

    try:
        for audio in rec.record_blocking(hotkey):
            try:
                text = transcribe_audio(model, audio, sr=48000, use_vad=use_vad)
                if not text:
                    print("[assistant-api] Heard nothing useful.")
                    continue
                print(f"[you] {text}")

                typ, arg = parse_intent(text, CFG.get("playlists", {}))
                if args.verbose:
                    print(f"[debug] intent={typ} arg={arg!r}")
                handle_intent_api(sp, typ, arg)

            except KeyboardInterrupt:
                raise
            except Exception:
                print("[assistant-api] Handler blew up:")
                traceback.print_exc()
    except KeyboardInterrupt:
        print("\n[assistant-api] Ctrl+C — shutting down.")
    finally:
        rec.stop()


if __name__ == "__main__":
    main()
