"""Replace desktop scenery while retaining the original demo's exact timeline."""

import argparse
import io
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


BASELINE = "4308a53449a0adecf87c4c47f54b4a37ce5e2989"
OFFSET = (40, 40)
SAMPLES = (0, 80, 170, 245, 350, 450, 560)
GUIDES = ((54, 56, 540, 233), (740, 56, 1180, 233))


def original_animation(path: Path | None) -> Image.Image:
    if path:
        return Image.open(path)
    repository = Path(__file__).resolve().parents[2]
    data = subprocess.check_output(
        ["git", "show", f"{BASELINE}:docs/assets/vibe-hud-demo.gif"], cwd=repository
    )
    return Image.open(io.BytesIO(data))


def hud_mask(frame: Image.Image) -> Image.Image:
    """Trace black HUD rows; fill message bubbles without capturing the desktop."""
    pixels = np.asarray(frame)
    dark = pixels[16:650, 300:900].max(axis=2) < 14
    occupied = dark.any(axis=1)
    left = dark.argmax(axis=1)
    right = dark.shape[1] - dark[:, ::-1].argmax(axis=1)
    # Separators can cover a full row; interpolate that row from its neighbors.
    valid = np.flatnonzero(occupied)
    gaps = np.flatnonzero(np.diff(valid) > 3)
    if len(gaps):
        valid = valid[:gaps[0] + 1]
    rows = np.arange(dark.shape[0])
    left = np.interp(rows, valid, left[valid])
    right = np.interp(rows, valid, right[valid])
    occupied = (rows >= valid[0]) & (rows <= valid[-1])
    columns = np.arange(dark.shape[1])[None, :]
    body = occupied[:, None] & (columns >= left[:, None]) & (columns < right[:, None])
    mask = Image.new("L", frame.size)
    mask.paste(Image.fromarray((body * 255).astype(np.uint8)), (300, 16))
    return mask


class DesktopRestyler:
    def __init__(self, template: Image.Image, animation: Image.Image):
        if template.size != (1280, 880) or animation.size != (1200, 800):
            raise ValueError("Expected a 1280×880 desktop and the original 1200×800 GIF")
        self.template = template.convert("RGB")
        animation.seek(0)
        self.reference = np.asarray(animation.convert("RGB")).astype(np.float32)
        animation.seek(170)
        self.guide_reference = np.asarray(animation.convert("RGB")).astype(np.float32)
        self.body_clip = Image.new("L", animation.size)
        ImageDraw.Draw(self.body_clip).rounded_rectangle((146, 234, 1054, 662), radius=12, fill=255)
        self.screen_clip = Image.new("L", animation.size)
        ImageDraw.Draw(self.screen_clip).rounded_rectangle((16, 16, 1183, 743), radius=24, fill=255)
        self.device_clip = Image.new("L", (1208 * 4, 768 * 4))
        ImageDraw.Draw(self.device_clip).rounded_rectangle((0, 0, 1208 * 4 - 1, 768 * 4 - 1), radius=40 * 4, fill=255)
        self.device_clip = self.device_clip.resize((1208, 768), Image.Resampling.LANCZOS)

    def render(self, frame: Image.Image) -> Image.Image:
        canvas = self.template.copy()
        pixels = np.asarray(frame).astype(np.float32)
        mask = hud_mask(frame)

        # Keep the original terminal log, typing, progress, and pointer pixel-for-pixel.
        client = (147, 271, 1053, 661)
        canvas.paste(frame.crop(client), (client[0] + OFFSET[0], client[1] + OFFSET[1]), self.body_clip.crop(client))

        # The same menu items and agent icons, in www's white-on-purple treatment.
        menu = (16, 16, 1184, 50)
        luminance = pixels[16:50, 16:1184].mean(axis=2)
        alpha = np.clip((200 - luminance) / 160, 0, 1) * 255
        protected = np.asarray(mask.filter(ImageFilter.MaxFilter(5)).crop(menu)) > 0
        alpha[protected] = 0
        alpha *= np.asarray(self.screen_clip.crop(menu)) / 255
        canvas.paste(Image.new("RGB", (1168, 34), "white"), (56, 56), Image.fromarray(alpha.astype(np.uint8)))

        # Preserve both original guide cards and their fades. Remove the old blue
        # background contribution from partially transparent card pixels.
        for box in GUIDES:
            x0, y0, x1, y1 = box
            original_background = self.reference[y0:y1, x0:x1]
            full_card = self.guide_reference[y0:y1, x0:x1]
            current = pixels[y0:y1, x0:x1]
            difference = full_card - original_background
            # Fill the card's interior so light glyphs never become matte holes.
            blue = (full_card[:, :, 2] > 130) & (full_card[:, :, 2] - full_card[:, :, 1] > 70) & (full_card[:, :, 2] - full_card[:, :, 0] > 50)
            present = blue.any(axis=1)
            first = blue.argmax(axis=1)
            last = blue.shape[1] - blue[:, ::-1].argmax(axis=1)
            columns = np.arange(blue.shape[1])[None, :]
            changed = present[:, None] & (columns >= first[:, None]) & (columns < last[:, None])
            expanded = np.asarray(Image.fromarray((changed * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
            changed |= expanded & (np.abs(difference).max(axis=2) > 8)
            # Median projection is stable across text, borders, and flat fill.
            strong = np.abs(difference).max(axis=2) > 80
            denominator = np.square(difference).sum(axis=2)
            projected = ((current - original_background) * difference).sum(axis=2) / np.maximum(denominator, 1)
            opacity = float(np.clip(np.median(projected[strong]), 0, 1))
            if opacity < 0.005:
                continue
            destination_box = (x0 + 40, y0 + 40, x1 + 40, y1 + 40)
            new_background = np.asarray(canvas.crop(destination_box)).astype(np.float32)
            corrected = current + (1 - opacity) * (new_background - original_background)
            corrected = Image.fromarray(np.clip(corrected, 0, 255).astype(np.uint8))
            canvas.paste(corrected, destination_box[:2], Image.fromarray((changed * 255).astype(np.uint8)))

        # Carry the original HUD geometry, rings, text, highlights, and transitions.
        shadow = mask.filter(ImageFilter.GaussianBlur(9)).point(lambda value: round(value * 0.3))
        canvas.paste(Image.new("RGB", frame.size, "black"), OFFSET, shadow)
        canvas.paste(frame, OFFSET, mask)

        # Keep the colored highlight outside the collapsed rings, and the pointer
        # while it travels between the terminal and HUD on exposed wallpaper.
        highlights = np.zeros((800, 1200), dtype=np.uint8)
        ring = pixels[16:62, 458:524]
        highlights[16:62, 458:524] = ((ring[:, :, 0] < 150) & (ring[:, :, 1] < 200)) * 255
        difference = np.abs(pixels - self.reference).max(axis=2)
        cursor = (pixels.min(axis=2) > 190) & (np.ptp(pixels, axis=2) < 30) & (difference > 24)
        cursor[:50] = False
        cursor[234:663, 146:1055] = False
        cursor[744:] = False
        for x0, y0, x1, y1 in GUIDES:
            cursor[y0:y1, x0:x1] = False
        highlights[cursor] = 255
        canvas.paste(frame, OFFSET, Image.fromarray(highlights))

        # Keep only the screen and bezel. No surrounding canvas or caption strip.
        device = canvas.crop((36, 36, 1244, 804)).convert("RGBA")
        device.putalpha(self.device_clip)
        return device


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", nargs="?", type=Path, default=Path(__file__).parent / "desktop.png", help="Full-page www desktop screenshot")
    parser.add_argument("--original", type=Path, help="Default: original GIF from the baseline Git commit")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent.parent / "assets/vibe-hud-demo.gif")
    parser.add_argument("--preview", type=Path, help="Export representative PNGs without replacing the GIF")
    args = parser.parse_args()
    animation = original_animation(args.original)
    restyler = DesktopRestyler(Image.open(args.template), animation)
    previews = []
    for index in SAMPLES:
        animation.seek(index)
        rendered = restyler.render(animation.convert("RGB"))
        previews.append(rendered)
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            rendered.save(args.preview / f"frame-{index:03}.png")
    if args.preview:
        print(json.dumps({"preview": str(args.preview), "frames": list(SAMPLES)}))
        return

    samples = Image.new("RGB", (320 * len(previews), 204))
    for index, preview in enumerate(previews):
        samples.paste(preview.convert("RGB").resize((320, 204)), (320 * index, 0))
    palette = samples.quantize(colors=255)
    # Palette slot 255 is reserved for the rounded transparent outer corners.
    colors = palette.getpalette()
    colors[255 * 3:256 * 3] = [0, 0, 0]
    palette.putpalette(colors)
    opaque_black = int(np.asarray(colors[:255 * 3]).reshape(-1, 3).sum(axis=1).argmin())
    frames, durations = [], []
    for index in range(animation.n_frames):
        animation.seek(index)
        frame = restyler.render(animation.convert("RGB"))
        indexed = frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        # A duplicate black swatch must never make the HUD itself transparent.
        indices = np.asarray(indexed).copy()
        indices[indices == 255] = opaque_black
        indexed = Image.fromarray(indices)
        indexed.putpalette(colors)
        indexed.paste(255, mask=frame.getchannel("A").point(lambda value: 255 if value < 128 else 0))
        frames.append(indexed)
        durations.append(animation.info.get("duration", 50))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp.gif")
    frames[0].save(temporary, format="GIF", save_all=True, append_images=frames[1:],
                   duration=durations, loop=animation.info.get("loop", 0), optimize=True, disposal=1, transparency=255)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "frames": len(frames),
                      "durationMs": sum(durations), "bytes": args.output.stat().st_size}))


if __name__ == "__main__":
    main()
