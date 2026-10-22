"""Read-only smoke test for TBA after it has been deployed to Render.

Usage: python scripts/check_deployment.py https://your-app.onrender.com
It does not modify server state or guarantee publisher image availability.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

def get(url, timeout=40):
    request = urllib.request.Request(url, headers={"User-Agent": "TBA-Deployment-Check/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read(2_000_000)

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_deployment.py https://your-app.onrender.com")
        return 2
    root = sys.argv[1].rstrip("/")
    parsed = urlsplit(root)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        print("Pass the public HTTPS origin URL, e.g. https://tba-news.onrender.com")
        return 2
    failed = False
    tests = [
        ("Health JSON", "/api/health"),
        ("Homepage HTML", "/"),
        ("Logo asset", "/static/assets/tba-logo.webp"),
        ("News RSS", "/api/news?category=top"),
    ]
    for name, path in tests:
        try:
            status, content_type, content = get(root + path)
            if name == "Health JSON":
                ok = status == 200 and json.loads(content).get("status") == "ok"
            elif name == "Homepage HTML":
                ok = status == 200 and "text/html" in content_type
            elif name == "Logo asset":
                ok = status == 200 and content.startswith(b"RIFF") and content[8:12] == b"WEBP"
            else:
                data = json.loads(content)
                ok = status == 200 and isinstance(data.get("items"), list) and bool(data["items"])
                if ok:
                    print(f"     {len(data['items'])} live stories returned")
            print(f"{'PASS' if ok else 'FAIL'} {name}")
            failed |= not ok
        except (ValueError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            failed = True
            print(f"FAIL {name}: {exc}")
    print("Note: Per-story photographs depend on third-party publishers; no blanket guarantee.")
    return int(failed)

if __name__ == "__main__":
    raise SystemExit(main())
