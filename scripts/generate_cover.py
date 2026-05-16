from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        if not bold
        else [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica-Bold.ttf",
            "/System/Library/Fonts/SFNS.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def main() -> None:
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), "#0f141a")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, width, 90), fill="#18222d")
    draw.rectangle((0, height - 110, width, height), fill="#131b24")
    draw.rectangle((78, 126, 1202, 596), outline="#3a4b5e", width=3)

    circles = [
        (330, 335, 72, "#1f6f8b"),
        (640, 272, 92, "#2f8f83"),
        (950, 335, 72, "#1f6f8b"),
    ]
    for cx, cy, r, color in circles:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color, outline="#b9d7de", width=3)
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill="#0f141a")

    draw.line((402, 335, 548, 292), fill="#7aa6b8", width=6)
    draw.line((732, 292, 878, 335), fill="#7aa6b8", width=6)

    draw.text((78, 26), "CerberusGuard", fill="#e8edf2", font=font(44, bold=True))
    draw.text((78, 100), "Three-Head Defence for Production AI Agents", fill="#c7d1da", font=font(30))
    draw.text((78, 622), "Prompt Inspection  ·  Budget Governance  ·  Sandboxed Execution", fill="#9fb0bf", font=font(28))
    draw.text((996, 28), "TechEx 2026", fill="#8fa4b6", font=font(26, bold=True))

    out = Path("cover.png")
    image.save(out, format="PNG")
    print(out)


if __name__ == "__main__":
    main()
