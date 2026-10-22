"""Offline TBA branding regression checks (no network or Flask required)."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static" / "assets"


class BrandingTests(unittest.TestCase):
    def test_brand_assets_are_present(self):
        for asset in (
            "tba-logo.webp", "tba-logo.png", "favicon-16.png", "favicon-32.png",
            "apple-touch-icon.png", "tba-app-icon.png", "tba-social.jpg",
        ):
            with self.subTest(asset=asset):
                self.assertTrue((ASSETS / asset).stat().st_size > 200)

    def test_navigation_displays_official_logo(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="brand-logo"', html)
        self.assertIn('class="topbar-brand"', html)
        self.assertIn("/static/assets/tba-logo.webp", html)
        self.assertIn("/static/assets/favicon-32.png", html)

    def test_share_card_reuses_official_logo(self):
        source = (ROOT / "static" / "share.js").read_text(encoding="utf-8")
        self.assertIn("/static/assets/tba-logo.webp", source)
        self.assertIn("await loadBrandLogo()", source)
        self.assertIn("ctx.fillText('TBA'", source)  # Offline fallback


if __name__ == "__main__":
    unittest.main()
