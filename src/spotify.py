"""Spotify integration functions."""

import os
import time
import subprocess
import keyboard
import pygetwindow as gw

# Try to import pyautogui, but make it optional
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    # Note: pyautogui is recommended for reliable playlist auto-play
    # Install with: pip install pyautogui Pillow


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


def _try_play_first_song(win, use_mouse=True):
    """Helper function to play the first song in a playlist.
    Uses the most reliable method: scroll to top, select first song, play it.
    """
    win.activate()
    time.sleep(0.4)
    
    # Step 1: Click in the playlist area to give it focus
    if use_mouse and HAS_PYAUTOGUI:
        win_left = win.left
        win_top = win.top
        win_width = win.width
        # Click in the center-right area where the song list is
        click_x = win_left + int(win_width * 0.65)
        click_y = win_top + 300
        pyautogui.click(click_x, click_y)
        time.sleep(0.3)
    
    # Step 2: Scroll to the VERY TOP of the playlist
    # Press Home multiple times to ensure we're at the top
    for _ in range(3):
        keyboard.press_and_release("home")
        time.sleep(0.15)
    
    # Step 3: Press Down then Up to ensure first song is selected
    keyboard.press_and_release("down")
    time.sleep(0.1)
    keyboard.press_and_release("up")
    time.sleep(0.2)
    
    # Step 4: Press Enter to play the first song
    # This should start the playlist from the beginning
    keyboard.press_and_release("enter")
    time.sleep(0.3)
    
    return True


def open_spotify_uri(uri: str, auto_play: bool = False) -> bool:
    """Open a Spotify URI.
    
    Args:
        uri: Spotify URI to open
        auto_play: If True, automatically start playback from the first song
    """
    try:
        if auto_play:
            # FIRST: Stop any currently playing track
            # This prevents Spotify from resuming it
            bring_spotify_to_front()
            time.sleep(0.2)
            keyboard.press_and_release("space")  # Stop/pause
            time.sleep(0.5)
        
        # Open the playlist URI
        os.startfile(uri)
        
        if auto_play:
            # Wait for Spotify to load the playlist
            time.sleep(10.0)  # Give it time to fully load
            # Bring Spotify to front
            bring_spotify_to_front()
            time.sleep(0.6)
            
            # Get Spotify window
            titles = [t for t in gw.getAllTitles() if "Spotify" in t]
            if not titles:
                return True
            
            try:
                win = gw.getWindowsWithTitle(titles[0])[0]
                if win.isMinimized:
                    win.restore()
                    time.sleep(0.3)
                
                # SIMPLE APPROACH: Navigate to first song and play it
                # This should start from the beginning of the playlist
                _try_play_first_song(win, use_mouse=HAS_PYAUTOGUI)
                
            except Exception:
                # Fallback
                try:
                    win = gw.getWindowsWithTitle(titles[0])[0]
                    win.activate()
                    time.sleep(0.3)
                    keyboard.press_and_release("home")
                    time.sleep(0.2)
                    keyboard.press_and_release("enter")
                except Exception:
                    pass
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

