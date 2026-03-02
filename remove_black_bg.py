"""
Remove black background from a logo image and save as transparent WebP.

Usage:
    python remove_black_bg.py input_image.png
    python remove_black_bg.py input_image.png output_image.webp
    python remove_black_bg.py input_image.png -t 30        # custom threshold (default: 30)
    python remove_black_bg.py input_image.png -q 90        # custom quality (default: 95)
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def remove_black_background(
    input_path: str,
    output_path: str | None = None,
    threshold: int = 30,
    quality: int = 95,
    feather: bool = True,
) -> str:
    """
    Remove black background from logo, making it transparent.

    Args:
        input_path: Path to the input image.
        output_path: Path for the output WebP. Defaults to input name + .webp.
        threshold: Brightness threshold (0-255). Pixels with R,G,B all below
                   this value are treated as background. Default 30.
        quality: WebP quality (1-100). Default 95.
        feather: If True, semi-transparent pixels get smooth alpha based on
                 brightness, giving cleaner edges.

    Returns:
        The output file path.
    """
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img, dtype=np.float32)

    r, g, b, _ = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]

    # Max channel value per pixel — represents "brightness"
    brightness = np.maximum(np.maximum(r, g), np.maximum(b, 1e-6))  # avoid div by zero

    # Mask: pixels where ALL channels are below threshold → background
    is_black = brightness <= threshold

    if feather:
        # Smooth alpha: scale from 0 (pure black) to 255 (bright white)
        # This handles anti-aliased edges gracefully
        alpha = np.clip(brightness * (255.0 / 255.0), 0, 255)
        # For clearly non-black pixels, ensure full opacity
        alpha = np.where(brightness > threshold, 255.0, alpha)
        # For pure black, ensure full transparency
        alpha = np.where(is_black, 0.0, alpha)
    else:
        # Hard cutoff — binary transparency
        alpha = np.where(is_black, 0.0, 255.0)

    data[:, :, 3] = alpha
    result = Image.fromarray(data.astype(np.uint8), "RGBA")

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".webp"))

    result.save(output_path, "WEBP", quality=quality, lossless=(quality == 100))
    print(f"✅ Saved: {output_path} ({Path(output_path).stat().st_size / 1024:.1f} KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Remove black background from a logo and export as transparent WebP."
    )
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", nargs="?", default=None, help="Output WebP path (optional)")
    parser.add_argument("-t", "--threshold", type=int, default=30,
                        help="Black threshold 0-255 (default: 30)")
    parser.add_argument("-q", "--quality", type=int, default=95,
                        help="WebP quality 1-100 (default: 95)")
    parser.add_argument("--no-feather", action="store_true",
                        help="Disable smooth alpha edges (hard cutoff)")
    args = parser.parse_args()

    remove_black_background(
        input_path=args.input,
        output_path=args.output,
        threshold=args.threshold,
        quality=args.quality,
        feather=not args.no_feather,
    )


if __name__ == "__main__":
    main()
