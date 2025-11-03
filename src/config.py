"""Configuration management for the voice assistant."""

import os
import json


CONFIG_PATH = "config.json"
DEFAULT_CONFIG = {
    "playlists": {},
    "whisper_model": "small",
    "push_to_talk_key": "right ctrl"
}


def load_config():
    """Load configuration from JSON file, creating default if missing."""
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG.copy()
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # Allow environment variables to override top-level fields if JSON leaves them empty
    config["whisper_model"] = config.get("whisper_model") or os.getenv("WHISPER_MODEL", "small")
    config["push_to_talk_key"] = config.get("push_to_talk_key") or os.getenv("PTT_KEY", "right ctrl")
    
    return config

