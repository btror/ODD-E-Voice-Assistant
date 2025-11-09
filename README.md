# WIP - just messing around

# ODD-E Spotify Voice Assistant

A hands-free voice-controlled Spotify assistant that runs entirely on your local machine. Control Spotify with natural voice commands without needing the Spotify API or any cloud services.

## How It Works

ODD-E uses **OpenAI's Whisper AI** (via `faster-whisper`) to convert your voice commands into text in real-time. The AI model runs locally on your machine, leveraging GPU acceleration when available for fast, private speech recognition.

**AI-Powered Pipeline:**
1. **Voice Capture** → Records audio when you hold the push-to-talk hotkey
2. **AI Transcription** → Whisper AI converts speech to text (runs locally, no cloud)
3. **Intent Recognition** → Fuzzy matching parses your natural language commands
4. **Spotify Control** → Executes commands via UI automation

The entire process is **100% local** - your voice never leaves your machine. Whisper AI handles everything from understanding your speech to extracting the intent, making it feel like a natural conversation with your music player.

## Features

- 🎤 **Voice Control** - Push-to-talk activation (default: F9)
- 🤖 **Local AI** - Whisper model runs entirely on your machine
- 🚀 **GPU Accelerated** - Uses CUDA when available, falls back to CPU
- 🎵 **Spotify Integration** - No API keys needed, works via UI automation
- 🎯 **Fuzzy Matching** - Finds playlists even with typos/variations
- 🔊 **Media Controls** - Play, pause, skip, volume control
- 📋 **Custom Playlists** - Configure your own playlists in `config.json`

## Requirements

- Python 3.9+
- Windows 10/11
- Spotify Desktop App installed
- NVIDIA GPU with CUDA (optional, for faster transcription)
  - **Note:** If you want GPU acceleration, you'll need to install:
    - NVIDIA GPU drivers
    - **CUDA Toolkit** - Version **12.6 or 13.0** (required)
      - CUDA 12.6 is the minimum required version
      - CUDA 13.0 is also supported
      - Download from: [NVIDIA CUDA Downloads](https://developer.nvidia.com/cuda-downloads)
    - **cuDNN** - Version 9.14 (optional but recommended for optimal performance)
      - Download from: [NVIDIA cuDNN Downloads](https://developer.nvidia.com/cudnn)
  - **No GPU?** The assistant works perfectly on CPU - just add `--cpu` flag or let it auto-detect

## Installation

1. **Clone or download this repository**

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

## Configuration

Create or edit `config.json` in the project root:

```json
{
  "playlists": {
    "general": "spotify:playlist:YOUR_PLAYLIST_ID_HERE",
    "workout": "spotify:playlist:ANOTHER_PLAYLIST_ID"
  },
  "whisper_model": "small",
  "push_to_talk_key": "f9"
}
```

- **playlists**: Map friendly names to Spotify playlist URIs
- **whisper_model**: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`). Smaller = faster, larger = more accurate
- **push_to_talk_key**: Hotkey to hold while speaking (e.g., `"f9"`, `"right ctrl"`)

## Usage

### Basic Usage

```powershell
python -u .\assistant.py --hotkey f9 --mic 25 --model small --compute float16 # uses UI navigation tools

python -u .\assistant_api.py --hotkey f9 --mic 25 --model small --compute float16 # uses spotify api
```

### Command-Line Options

- `--hotkey` - Push-to-talk key (default: from config)
- `--mic` - Audio input device index (optional, uses default if not specified)
- `--model` - Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- `--compute` - Compute type: `int8`, `float16` (GPU), or `float32`
- `--cpu` - Force CPU inference (disable GPU)
- `--no-vad` - Disable voice activity detection
- `--verbose` - Show debug output

### Example Commands

Once running, hold your hotkey and say:
- **"play"** / **"pause"** / **"next"** / **"previous"**
- **"volume up"** / **"volume down"**
- **"play my workout playlist"** (uses fuzzy matching)
- **"play Bohemian Rhapsody"** (searches and plays)
- **"open spotify"**

## Stopping the Assistant

Press `Ctrl+C` in the terminal, or run:

```powershell
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
```

## How the AI Works

### Whisper AI Model

The project uses **OpenAI's Whisper** - a state-of-the-art speech recognition model trained on multilingual audio data. It excels at understanding:
- Natural speech patterns
- Various accents and speaking styles
- Background noise tolerance
- Contextual understanding

### Why Local AI?

- **Privacy** - Your voice never leaves your machine
- **Speed** - No network latency, instant transcription
- **Reliability** - Works offline, no API rate limits
- **Cost** - No cloud API fees

### Performance Notes

- **GPU Recommended**: Transcription is 5-10x faster with CUDA
  - Requires **CUDA 12.6 and 13.0** (separate installation, not included in pip packages)
  - Automatically falls back to CPU if CUDA unavailable or wrong version
  - Use `--cpu` flag to force CPU mode
- **Model Size Trade-off**: 
  - `tiny`/`base` - Fastest, less accurate
  - `small` - Balanced (recommended)
  - `medium`/`large` - Most accurate, slower

## Project Structure

```
odd-e-ai/
├── assistant.py          # Main entry point
├── config.json           # Configuration file
├── requirements.txt      # Python dependencies
├── src/                  # Package directory
│   ├── __init__.py
│   ├── env_setup.py      # Environment & CUDA setup
│   ├── config.py         # Configuration management
│   ├── audio.py          # Audio capture & Whisper transcription
│   ├── intent_parser.py  # Command parsing & fuzzy matching
│   └── spotify.py        # Spotify UI automation
└── README.md
```

## Troubleshooting

**"Import could not be resolved" errors:**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

**Audio device issues:**
- Run with `--verbose` to see available devices
- Use `--mic <index>` to specify device explicitly

**CUDA/GPU errors:**
- Use `--cpu` flag to force CPU mode (no installation needed)
- If you want GPU acceleration:
  - Install NVIDIA GPU drivers (latest compatible version)
  - Install **CUDA Toolkit 12.6 and 13.0** (required - minimum 12.6) from [NVIDIA's website](https://developer.nvidia.com/cuda-downloads)
    - CUDA 12.6 is the minimum required version for faster-whisper
    - CUDA 13.0 is also supported
  - Install **cuDNN 9.14** for optimal performance (optional but recommended)
  - The code automatically detects and uses CUDA if available
- **Verify CUDA installation:**
  ```powershell
  nvcc --version  # Should show CUDA 12.6 and 13.0
  ```
- The assistant works fine on CPU - GPU is optional for speed

**Spotify not responding:**
- Ensure Spotify desktop app is installed
- Check that Spotify can be launched via `spotify:` URI

## License

This project is for personal use. Whisper AI is licensed under MIT License (OpenAI).
