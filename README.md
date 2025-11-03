ODD-E Spotify Voice Asisstant

TODO: clean this up

setup requirements:

pip install -r requirements.txt

running:

.\venv\Scripts\Activate.ps1

python -u .\assistant.py --hotkey f9 --mic 25 --model small --compute float16 --no-vad --verbose
python -u .\assistant.py --hotkey f9 --mic 25 --model small --compute float16 --verbose

stop processes:

Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
