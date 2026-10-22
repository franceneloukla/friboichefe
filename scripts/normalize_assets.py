#!/usr/bin/env python3
"""Normaliza assets: garante que o CONTEÚDO do arquivo bate com a extensão.

Problema real encontrado na integração: o site original serve AVIF (e às vezes
WebP/JPEG) em URLs terminadas em .jpg/.png. Salvo cru no disco, o navegador
recebe `image/jpeg` com bytes AVIF e simplesmente não desenha a imagem — foi o
que fez a faixa de marcas da home renderizar como blocos de cor com texto de
alt.

Este script varre web/static e data/images, detecta o formato real por magic
bytes e reescreve o arquivo no formato da extensão (usando PIL). Idempotente:
roda quantas vezes quiser.

Uso:
    python3 scripts/normalize_assets.py            # corrige
    python3 scripts/normalize_assets.py --check    # só relata
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "web" / "static", ROOT / "data" / "images"]

# extensão -> (formato PIL de saída, magic esperado)
RULES = {
    "jpeg": {"target": "JPEG", "save": {"quality": 88, "optimize": True, "progressive": True}},
    "png": {"target": "PNG", "save": {"optimize": True}},
    "webp": {"target": "WEBP", "save": {"quality": 88, "method": 4}},
}


def sniff(path: Path) -> str | None:
    """Formato real pelos magic bytes (None = não é imagem binária conhecida)."""
    with path.open("rb") as fh:
        head = fh.read(16)
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"
    if head[:4] == b"GIF8":
        return "gif"
    return None


def expected(path: Path) -> str | None:
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    return ext if ext in RULES else None


def convert(path: Path, want: str) -> bool:
    """Reescreve o arquivo no formato `want`. Retorna True se mexeu."""
    rule = RULES[want]
    try:
        with Image.open(path) as im:
            im.load()
            if rule["target"] == "JPEG":
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
            out = im.copy()
    except Exception as exc:  # noqa: BLE001 - queremos seguir com os outros arquivos
        print(f"  [erro] {path.relative_to(ROOT)}: {exc}")
        return False

    tmp = path.with_suffix(path.suffix + ".tmp")
    out.save(tmp, format=rule["target"], **rule["save"])
    tmp.replace(path)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="não altera nada, só relata")
    args = ap.parse_args()

    total = fixed = 0
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix == ".tmp":
                continue
            want = expected(path)
            if not want:
                continue
            total += 1
            got = sniff(path)
            if got is None or got == want:
                continue
            rel = path.relative_to(ROOT)
            if args.check:
                print(f"  [x] {rel}: conteúdo={got} extensão={want}")
                fixed += 1
                continue
            if convert(path, want):
                print(f"  [ok] {rel}: {got} -> {want}")
                fixed += 1

    verb = "desalinhados" if args.check else "corrigidos"
    print(f"\n{total} imagens verificadas, {fixed} {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
