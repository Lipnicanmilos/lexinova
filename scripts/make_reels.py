"""Vyrobí video na Instagram (Reels aj Story) zo scripts/brand/reels.html.

Stránka má window.render(t), ktorý nakreslí presne čas t, takže snímky nezávisia
od rýchlosti počítača. Playwright ich nafotí a ffmpeg ich zloží do MP4 s H.264,
ktoré Instagram berie. Ffmpeg z Playwrightu vie len VP8/WebM, preto treba iný:
`pip install --target <priečinok> imageio-ffmpeg` a ten priečinok dať do --pylib,
alebo cestu k ffmpeg.exe do --ffmpeg.

    venv\\Scripts\\python.exe scripts\\make_reels.py --pylib <priečinok>

Výstup ide do scripts/brand/instagram/ (v gite nie je): lexinova-reels.mp4 a
obálka lexinova-reels-cover.png. Video má tichú zvukovú stopu, hudbu treba pridať
priamo v Instagrame.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "brand" / "reels.html"
OUT = ROOT / "brand" / "instagram"


def find_ffmpeg(args):
    if args.ffmpeg:
        return args.ffmpeg
    if args.pylib:
        sys.path.insert(0, args.pylib)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        found = shutil.which("ffmpeg")
        if found:
            return found
    sys.exit("Chýba ffmpeg s H.264, pozri návod hore v skripte.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg")
    parser.add_argument("--pylib")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--cover", type=float, default=14.6, help="čas snímky na obálku")
    args = parser.parse_args()
    ffmpeg = find_ffmpeg(args)
    OUT.mkdir(parents=True, exist_ok=True)
    video = OUT / "lexinova-reels.mp4"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        page.goto(PAGE.as_uri() + "?render")
        page.evaluate("document.fonts.ready")
        page.wait_for_load_state("networkidle")
        duration = page.evaluate("window.DURATION")
        frames = round(duration * args.fps)

        enc = subprocess.Popen([
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "image2pipe", "-framerate", str(args.fps), "-i", "-",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-map", "0:v", "-map", "1:a", "-shortest",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-crf", "18", "-preset", "slow", "-r", str(args.fps),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(video),
        ], stdin=subprocess.PIPE)
        for i in range(frames):
            page.evaluate(f"window.render({i / args.fps})")
            enc.stdin.write(page.screenshot(type="png"))
            if i % args.fps == 0:
                print(f"\r{i // args.fps} / {round(duration)} s", end="", flush=True)
        enc.stdin.close()
        if enc.wait():
            sys.exit("ffmpeg zlyhal")

        page.evaluate(f"window.render({args.cover})")
        page.screenshot(path=str(OUT / "lexinova-reels-cover.png"))
        browser.close()
    print(f"\nHotovo: {video}")


if __name__ == "__main__":
    main()
