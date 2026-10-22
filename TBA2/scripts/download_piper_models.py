"""Download the two official Piper Hindi female voice files to ./models/.
Run only on your own machine; requires internet once. No paid API key.
Dataset attribution / noncommercial license: see docs/OFFLINE_VOICES.md.
"""
from pathlib import Path
import urllib.request
import argparse

BASE = Path(__file__).resolve().parents[1]
DEST = BASE / 'models'
DEST.mkdir(parents=True, exist_ok=True)
argp = argparse.ArgumentParser(description="Download an offline Piper Hindi voice")
argp.add_argument("--voice", choices=("priyamvada", "rohan"), default="priyamvada")
name = argp.parse_args().voice
VOICE = f"hi_IN-{name}-medium"
PREFIX = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/{name}/medium/"
for suffix in ('.onnx', '.onnx.json'):
    name = VOICE + suffix
    target = DEST / name
    if target.is_file() and target.stat().st_size > (1000000 if suffix == '.onnx' else 100):
        print('Already downloaded:', name)
        continue
    print('Downloading', name, '(may take a while)...')
    request = urllib.request.Request(PREFIX + name, headers={'User-Agent':'TBAVoiceSetup/1.0'})
    partial = target.with_name(name + '.part')
    try:
        with urllib.request.urlopen(request, timeout=60) as resp, partial.open('wb') as fh:
            while True:
                block = resp.read(1024 * 1024)
                if not block: break
                fh.write(block)
        if partial.stat().st_size < (1000000 if suffix == '.onnx' else 100):
            raise RuntimeError('Downloaded file was unexpectedly small')
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    print('Saved:', target)
print(f'Piper Hindi voice {name} is ready.')
