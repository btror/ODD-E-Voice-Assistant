"""Spotify integration functions."""

import os
import time
import subprocess
import keyboard
import pygetwindow as gw


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
    """Bring Spotify window to front."""
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
    """Send media transport command via keyboard."""
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
    """Open a Spotify URI."""
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

