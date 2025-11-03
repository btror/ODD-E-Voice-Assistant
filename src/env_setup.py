"""Environment setup and initialization for the voice assistant."""

import os
import sys
import traceback


def setup_environment():
    """Configure environment variables for CUDA and HuggingFace."""
    os.environ.setdefault("ORT_DISABLE_CUDA", "1")  # keep onnx out of CUDA path
    os.environ.setdefault(
        "HUGGINGFACE_HUB_CACHE",
        os.path.expandvars(r"%USERPROFILE%\hfcache")
    )
    os.environ.setdefault("CT2_LOG_LEVEL", "INFO")


def setup_dll_directories():
    """Add CUDA and cuDNN DLL directories to the path."""
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


def install_exception_hook():
    """Install custom exception hook for error logging."""
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


def initialize():
    """Run all setup functions."""
    setup_environment()
    setup_dll_directories()
    install_exception_hook()

