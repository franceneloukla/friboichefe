#!/usr/bin/env python3
"""Monta o diretório public/ do Vercel com os assets estáticos.

- public/assets      -> web/static           (logo, ícones, banners, fontes)
- public/static      -> server/static        (css/app.css, js/app.js)
- public/img/products-> data/images/products (fotos dos produtos)
- public/favicon.ico e robots.txt

Roda: python3 scripts/build_vercel.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"

PAIRS = [
    (ROOT / "web" / "static", PUBLIC / "assets"),
    (ROOT / "server" / "static", PUBLIC / "static"),
    (ROOT / "data" / "images", PUBLIC / "img"),
]

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "*.tmp")


def copytree(src: Path, dst: Path) -> int:
    if not src.is_dir():
        print(f"  [skip] {src.relative_to(ROOT)} nao existe")
        return 0
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)
    n = sum(1 for _ in dst.rglob("*") if _.is_file())
    mb = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file()) / 1_048_576
    print(f"  [ok]   {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}  ({n} arquivos, {mb:.1f} MB)")
    return n


def main() -> int:
    PUBLIC.mkdir(exist_ok=True)
    total = 0
    for src, dst in PAIRS:
        total += copytree(src, dst)

    # favicon.ico: envolve o PNG do tema num container ICO (o formato aceita
    # payload PNG desde o Vista, então não precisa de Pillow no build)
    fav_png = None
    for candidate in (
        ROOT / "web" / "static" / "img" / "ui" / "logos" / "favicon-v3.png",
        ROOT / "web" / "static" / "img" / "ui" / "logos" / "favicon.png",
    ):
        if candidate.is_file():
            fav_png = candidate
            break
    if fav_png is not None:
        data = fav_png.read_bytes()
        side = 32
        if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 24:
            side = min(int.from_bytes(data[16:20], "big"), 256)
        header = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        entry = (
            bytes([side if side < 256 else 0, side if side < 256 else 0])
            + b"\x00\x00"
            + (1).to_bytes(2, "little")
            + (32).to_bytes(2, "little")
            + len(data).to_bytes(4, "little")
            + (22).to_bytes(4, "little")
        )
        (PUBLIC / "favicon.ico").write_bytes(header + entry + data)
        shutil.copy2(fav_png, PUBLIC / "favicon.png")

    (PUBLIC / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    if total == 0:
        print("\n[!] Nenhum asset copiado: rode o scraper e a captura de design primeiro.")
    print(f"\nTotal: {total} arquivos em public/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
