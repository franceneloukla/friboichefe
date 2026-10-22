#!/usr/bin/env python3
"""Comparação pixel a pixel entre a nossa home e a captura do original.

Uso (python3 do sistema — precisa de Pillow):
    python3 tests/compare_images.py

Lê  : tests/screenshots/home-1440.png  (clone, 1440px, full page)
      _scratch/ref/ORIGINAL_HOME_1440.png (original, 1440px, full page)
Grava: tests/artifacts/image_compare.json
       tests/screenshots/comparacao-lado-a-lado.png
       tests/screenshots/comparacao-diff.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
ARTI = ROOT / "tests" / "artifacts"
NOSSA = SHOTS / "home-1440.png"
REF = ROOT / "_scratch" / "ref" / "ORIGINAL_HOME_1440.png"


def dominant_colors(img: Image.Image, top: int = 12) -> list[dict]:
    small = img.convert("RGB").resize((240, int(240 * img.height / img.width)))
    q = small.quantize(colors=top, method=Image.MEDIANCUT).convert("RGB")
    cores = q.getcolors(maxcolors=top * 4) or []
    total = sum(c for c, _ in cores) or 1
    cores.sort(reverse=True)
    return [{"hex": "#%02X%02X%02X" % rgb, "pct": round(100 * c / total, 2)} for c, rgb in cores]


def band_diff(a: Image.Image, b: Image.Image, step: int = 50) -> list[dict]:
    """Diferença média por faixa horizontal (mesma largura, altura comum)."""
    a = a.convert("RGB")
    b = b.convert("RGB")
    h = min(a.height, b.height)
    out = []
    for y in range(0, h, step):
        ya, yb = a.crop((0, y, a.width, min(y + step, h))), b.crop((0, y, a.width, min(y + step, h)))
        diff = ImageChops.difference(ya, yb)
        px = list(diff.getdata())
        n = len(px) or 1
        mean = [sum(p[i] for p in px) / n for i in range(3)]
        out.append({"y": y, "y2": min(y + step, h),
                    "mean_abs_diff": round(sum(mean) / 3, 2),
                    "rgb_diff": [round(x, 1) for x in mean]})
    return out


def section_bands(img: Image.Image, step: int = 2, threshold: float = 6.0) -> list[int]:
    """Fronteiras horizontais: linhas em que a média da linha muda de forma abrupta."""
    small = img.convert("L").resize((160, img.height))
    px = small.load()
    rows = []
    for y in range(small.height):
        rows.append(sum(px[x, y] for x in range(small.width)) / small.width)
    bordas = []
    for y in range(1, len(rows)):
        if abs(rows[y] - rows[y - 1]) > threshold:
            if not bordas or y - bordas[-1] > 6:
                bordas.append(y)
    return bordas


def main() -> int:
    if not NOSSA.is_file() or not REF.is_file():
        print(f"faltando imagem: {NOSSA} ou {REF}")
        return 1
    a = Image.open(NOSSA)
    b = Image.open(REF)
    pa, pb = a.convert("RGB"), b.convert("RGB")

    res = {
        "nossa": str(NOSSA.relative_to(ROOT)),
        "original": str(REF.relative_to(ROOT)),
        "dim_original": {"w": b.width, "h": b.height},
        "dim_clone": {"w": a.width, "h": a.height},
        "delta_altura_px": a.height - b.height,
        "delta_altura_pct": round(100 * (a.height - b.height) / b.height, 2),
        "dominante_original": dominant_colors(b),
        "dominante_clone": dominant_colors(a),
        "faixas": band_diff(a, b, 50),
        "bordas_original": section_bands(b),
        "bordas_clone": section_bands(a),
    }

    # diferença global na área comum
    h = min(a.height, b.height)
    diff = ImageChops.difference(pa.crop((0, 0, a.width, h)), pb.crop((0, 0, b.width, h)))
    px = list(diff.getdata())
    res["diff_global_media"] = round(sum(sum(p) for p in px) / (3 * len(px)), 2)
    res["diff_global_pct_pixels_iguais"] = round(
        100 * sum(1 for p in px if max(p) <= 8) / len(px), 2)
    res["faixas"].sort(key=lambda f: -f["mean_abs_diff"])
    res["faixas_top10"] = res["faixas"][:10]

    # lado a lado (720px de largura cada)
    esc = 720
    ra = a.convert("RGB").resize((esc, int(esc * a.height / a.width)))
    rb = b.convert("RGB").resize((esc, int(esc * b.height / b.width)))
    hl = max(ra.height, rb.height)
    lado = Image.new("RGB", (esc * 2 + 24, hl + 34), "white")
    lado.paste(rb, (0, 34))
    lado.paste(ra, (esc + 24, 34))
    d = ImageDraw.Draw(lado)
    d.text((8, 10), "ORIGINAL (friboionline.com.br)", fill="black")
    d.text((esc + 32, 10), "CLONE (127.0.0.1)", fill="black")
    lado.save(SHOTS / "comparacao-lado-a-lado.png")

    # mapa de calor da diferença (área comum, 720px)
    hm = diff.resize((esc, int(esc * h / diff.width)))
    hm = hm.point(lambda v: min(255, v * 3)).convert("L")
    hm.save(SHOTS / "comparacao-diff.png")

    (ARTI / "image_compare.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"original: {b.width}x{b.height}  clone: {a.width}x{a.height}  "
          f"delta altura: {res['delta_altura_px']}px ({res['delta_altura_pct']}%)")
    print(f"diff global médio (0-255): {res['diff_global_media']}  "
          f"pixels praticamente iguais: {res['diff_global_pct_pixels_iguais']}%")
    print("\ncores dominantes original:", [f"{c['hex']} {c['pct']}%" for c in res["dominante_original"]])
    print("cores dominantes clone   :", [f"{c['hex']} {c['pct']}%" for c in res["dominante_clone"]])
    print("\nfaixas mais divergentes (y, diff médio):")
    for f in res["faixas_top10"]:
        print(f"  y={f['y']:5d}-{f['y2']:5d}  diff={f['mean_abs_diff']:6.2f}  rgb={f['rgb_diff']}")
    print("\nfronteiras de seção original:", res["bordas_original"][:20])
    print("fronteiras de seção clone   :", res["bordas_clone"][:20])
    print("\ngerados: tests/screenshots/comparacao-lado-a-lado.png, comparacao-diff.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
