"""Main entry point for the voice assistant."""

# Initialize environment first (must be before other imports)
from src.env_setup import initialize
initialize()

import os
import ctypes
import argparse
import traceback
import sounddevice as sd
from faster_whisper import WhisperModel

from src.config import load_config
from src.spotify import (
    ensure_spotify_running,
    bring_spotify_to_front,
    media_transport,
    open_spotify_uri,
    search_and_play,
)
from src.intent_parser import parse_intent
from src.audio import PTTRecorder, transcribe_audio


# Load configuration
CFG = load_config()


def build_argparser():
    """Build command-line argument parser."""
    p = argparse.ArgumentParser(description="Voice → Spotify assistant")
    p.add_argument("--hotkey", default=CFG.get("push_to_talk_key", "right ctrl"))
    p.add_argument("--mic", type=int, default=None, help="sounddevice input index (e.g., 25)")
    p.add_argument("--model", default=CFG.get("whisper_model", "small"))
    p.add_argument("--compute", default="float16", choices=["int8", "float16", "float32"])
    p.add_argument("--cpu", action="store_true", help="force CPU inference")
    p.add_argument("--no-vad", action="store_true", help="disable VAD pre-segmentation")
    p.add_argument("--verbose", action="store_true")
    return p


def load_whisper_model(args):
    """Load Whisper model with GPU/CPU fallback."""
    device = "cpu" if args.cpu else "cuda"
    compute_type = args.compute if device == "cuda" else ("int8" if args.compute == "float16" else args.compute)

    # Try GPU first, fallback to CPU if needed
    try:
        model = WhisperModel(
            args.model,
            device=device,
            compute_type=compute_type,
            device_index=0,
            download_root=os.environ["HUGGINGFACE_HUB_CACHE"],
        )
        return model
    except Exception as e:
        print("[assistant] GPU init failed (or forced CPU):", e, "→ falling back to CPU")
        return WhisperModel(
            args.model,
            device="cpu",
            compute_type="int8",
            download_root=os.environ["HUGGINGFACE_HUB_CACHE"],
        )


def setup_audio_device(args):
    """Configure audio input device."""
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

    return sd.default.device[0]


def handle_intent(typ: str, arg: str, args):
    """Handle parsed intent and execute corresponding action."""
    if typ == "transport":
        media_transport(arg)
    elif typ == "playlist":
        ensure_spotify_running()
        bring_spotify_to_front()
        if arg:
            open_spotify_uri(arg)
        else:
            print("[assistant] Missing playlist URI.")
    elif typ == "song":
        ensure_spotify_running()
        search_and_play(arg)
    elif typ == "open":
        ensure_spotify_running()
        bring_spotify_to_front()
    elif typ == "say":
        print(f"[assistant] {arg}")


def main():
    """Main entry point."""
    print("[boot] assistant.py starting…")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    args = build_argparser().parse_args()

    ensure_spotify_running()
    bring_spotify_to_front()

    print("[assistant] Loading Whisper…")
    model = load_whisper_model(args)

    # Audio / mic selection
    device = setup_audio_device(args)
    rec = PTTRecorder(device=device, samplerate=48000, verbose=args.verbose)
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

                handle_intent(typ, arg, args)
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
