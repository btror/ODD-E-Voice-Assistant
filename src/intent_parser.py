"""Intent parsing and text normalization."""

import re
from typing import Optional, Tuple, List
from rapidfuzz import fuzz, process


def normalize(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()


def best_match(name: str, keys: List[str], cutoff: int = 78) -> Optional[Tuple[str, int]]:
    """Find best fuzzy match for a name in a list of keys."""
    if not keys:
        return None
    norm_keys = [normalize(k) for k in keys]
    hit = process.extractOne(normalize(name), norm_keys, scorer=fuzz.token_set_ratio)
    if hit and hit[1] >= cutoff:
        idx = norm_keys.index(hit[0])
        return keys[idx], hit[1]
    return None


def parse_intent(text: str, playlists: dict) -> Tuple[str, Optional[str]]:
    """Parse user intent from transcribed text."""
    t = normalize(text)

    # Transport commands
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

