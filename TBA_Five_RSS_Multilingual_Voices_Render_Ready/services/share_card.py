"""Server-side branded news card rendering (1200x630 PNG) for social share previews."""
from __future__ import annotations

import io
import os
from typing import Any
from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _get_font(size: int, bold: bool = False) -> Any:
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                idx = 1 if bold and p.endswith(".ttc") else 0
                return ImageFont.truetype(p, size, index=idx)
            except Exception:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int, max_lines: int = 3) -> list[str]:
    words = text.split()
    lines: list[str] = []
    curr: list[str] = []
    for w in words:
        trial = " ".join(curr + [w])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) > max_width and curr:
            lines.append(" ".join(curr))
            curr = [w]
        else:
            curr.append(w)
    if curr:
        lines.append(" ".join(curr))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and (draw.textbbox((0, 0), last + "…", font=font)[2] - draw.textbbox((0, 0), last + "…", font=font)[0]) > max_width:
            last = last[:-1].strip()
        lines[-1] = last + "…"
    return lines


DEFAULT_LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "assets", "tba-logo.png")


def render_share_card_png(
    title: str,
    summary: str,
    source: str = "TBA",
    topic: str = "NEWS",
    date_str: str = "",
    image_bytes: bytes | None = None,
    url: str = "https://tba.news",
    logo_path: str = DEFAULT_LOGO_PATH
) -> bytes:
    """Render a high-resolution 1200x630 PNG branded news card for social previews."""
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), "#0e1a2b")
    draw = ImageDraw.Draw(img)

    # Gradient background: deep navy gradient from #0e1a2b to #16283f
    for y in range(H):
        ratio = y / H
        r = int(14 * (1 - ratio) + 22 * ratio)
        g = int(26 * (1 - ratio) + 40 * ratio)
        b = int(43 * (1 - ratio) + 65 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # Outer border
    draw.rounded_rectangle([(16, 16), (W - 16, H - 16)], radius=20, outline=(70, 100, 145, 120), width=2)

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((160, 48), Image.Resampling.LANCZOS)
            lw, lh = logo.size
            draw.rounded_rectangle([(48, 38), (48 + lw + 24, 38 + lh + 12)], radius=10, fill=(255, 255, 255, 240))
            img.alpha_composite(logo, (60, 44))
        except Exception:
            font_logo = _get_font(34, bold=True)
            draw.text((50, 40), "TBA", fill="#ffffff", font=font_logo)
    else:
        font_logo = _get_font(34, bold=True)
        draw.text((50, 40), "TBA", fill="#ffffff", font=font_logo)

    # Category Pill
    topic_text = (topic or "NEWS").upper()
    font_topic = _get_font(16, bold=True)
    tbbox = draw.textbbox((0, 0), topic_text, font=font_topic)
    tw = tbbox[2] - tbbox[0]
    draw.rounded_rectangle([(W - 50 - tw - 24, 40), (W - 50, 76)], radius=8, fill=(37, 99, 235, 220), outline=(96, 165, 250, 255), width=1)
    draw.text((W - 50 - tw - 12, 48), topic_text, fill="#ffffff", font=font_topic)

    # Article image
    has_img = False
    art_img = None
    if image_bytes:
        try:
            art_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            has_img = True
        except Exception:
            pass

    left_w = 690 if has_img else 1080

    # Headline
    font_title = _get_font(34, bold=True)
    title_lines = _wrap_text(draw, title or "News story", font_title, left_w - 40, max_lines=3)
    y_text = 120
    for line in title_lines:
        draw.text((50, y_text), line, fill="#ffffff", font=font_title)
        y_text += 44

    # Summary box
    box_top = max(y_text + 15, 260)
    box_h = 175
    draw.rounded_rectangle([(50, box_top), (50 + left_w, box_top + box_h)], radius=12, fill=(20, 35, 55, 220), outline=(60, 90, 130, 150), width=1)
    # Accent bar
    draw.rounded_rectangle([(50, box_top), (56, box_top + box_h)], radius=3, fill=(59, 130, 246, 255))

    # Label inside summary box
    draw.ellipse([(72, box_top + 16), (82, box_top + 26)], fill=(59, 130, 246, 255))
    font_sub = _get_font(14, bold=True)
    draw.text((92, box_top + 14), "STORY SUMMARY · KEY TAKEAWAY", fill="#93c5fd", font=font_sub)

    # Summary text
    font_sum = _get_font(20, bold=False)
    sum_lines = _wrap_text(draw, summary or "Read the verified news report on TBA.", font_sum, left_w - 50, max_lines=3)
    sy = box_top + 48
    for sline in sum_lines:
        draw.text((72, sy), sline, fill="#e2e8f0", font=font_sum)
        sy += 28

    # Image placement on the right
    if has_img and art_img:
        try:
            iw, ih = art_img.size
            tw, th = 390, 320
            scale = max(tw / iw, th / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            resized = art_img.resize((nw, nh), Image.Resampling.LANCZOS)
            x_crop = (nw - tw) // 2
            y_crop = (nh - th) // 2
            cropped = resized.crop((x_crop, y_crop, x_crop + tw, y_crop + th))

            mask = Image.new("L", (tw, th), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (tw, th)], radius=14, fill=255)

            img.paste(cropped, (W - 50 - tw, 120), mask)
            draw.rounded_rectangle([(W - 50 - tw, 120), (W - 50, 120 + th)], radius=14, outline=(70, 110, 160, 180), width=1)
        except Exception:
            pass

    # Footer
    draw.line([(50, 530), (W - 50, 530)], fill=(40, 65, 95, 200), width=1)

    font_footer = _get_font(18, bold=True)
    source_str = f"{source or 'TBA'} · {date_str or 'Today'}"
    draw.text((50, 546), source_str, fill="#94a3b8", font=font_footer)

    font_link = _get_font(16, bold=False)
    link_str = f"Read full story & audio on TBA · {url}"
    draw.text((50, 580), link_str, fill="#60a5fa", font=font_link)

    # Convert to RGB before saving as PNG to avoid transparency issues on some platforms
    final_img = Image.new("RGB", (W, H), "#0e1a2b")
    final_img.paste(img, (0, 0), img)

    buf = io.BytesIO()
    final_img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
