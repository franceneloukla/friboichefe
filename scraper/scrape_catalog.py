#!/usr/bin/env python3
"""Scraper do catálogo Friboi Online (Oracle Commerce Cloud).

O site fica atrás de Akamai: curl/requests levam TIMEOUT. Tudo aqui roda dentro
de uma página real do Chromium via Playwright (fetch na própria página, que
compartilha TLS/cookies/fingerprint do browser).

Saídas (todas relativas à raiz do projeto):
  data/catalog.json                 catálogo no formato de docs/CONTRATO.md
  data/images/products/{id}/main.jpg 1 imagem por produto (width=400)
  data/images_missing.json          produtos sem imagem
  data/catalog_stats.json           {products, categories, images, bytes, elapsed_s, scraped_at}
  data/_checkpoint.json             checkpoint da paginação (permite retomar)
  data/_checkpoint_images.json      progresso das imagens
  data/_image_index.json            mapa id -> source da imagem
  data/_raw/products-XXXXX.json     cache bruto de cada página (resume sem refetch)
  data/scrape.log                   log da execução

Uso:
  python scraper/scrape_catalog.py                 # catálogo + imagens + stats
  python scraper/scrape_catalog.py --phase catalog # só catálogo
  python scraper/scrape_catalog.py --phase images  # só imagens
  python scraper/scrape_catalog.py --phase finalize
  python scraper/scrape_catalog.py --only-missing --workers 2   # 2ª passada
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DIR = DATA / "_raw"
IMAGES_DIR = DATA / "images" / "products"
CHECKPOINT = DATA / "_checkpoint.json"
IMG_CHECKPOINT = DATA / "_checkpoint_images.json"
IMG_INDEX = DATA / "_image_index.json"
CATALOG = DATA / "catalog.json"
STATS = DATA / "catalog_stats.json"
MISSING = DATA / "images_missing.json"
LOG_FILE = DATA / "scrape.log"

DEFAULT_BASE = "https://www.friboionline.com.br"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NAV_JS = (
    "() => Array.from(document.querySelectorAll('a[href^=\"/category/\"]'))"
    ".map(a => [a.getAttribute('href'), (a.textContent || '').replace(/\\s+/g, ' ').trim()])"
    ".filter(([h, t]) => h && t)"
)
FETCH_TEXT_JS = """async (u) => {
  const x = await fetch(u, {headers: {'Accept': 'application/json'}});
  const t = await x.text();
  return {status: x.status, text: t};
}"""
FETCH_IMAGE_JS = """async (u) => {
  const x = await fetch(u, {headers: {'Accept': 'image/*,*/*;q=0.8'}});
  const ct = x.headers.get('content-type') || '';
  if (!x.ok) return {status: x.status, ct, data: null};
  const blob = await x.blob();
  const data = await new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = () => rej(new Error('FileReader falhou'));
    fr.readAsDataURL(blob);
  });
  return {status: x.status, ct, data};
}"""
FETCH_COLLECTIONS_JS = """async (ids) => {
  return await Promise.all(ids.map(async (id) => {
    try {
      const x = await fetch('/ccstore/v1/collections/' + encodeURIComponent(id));
      if (!x.ok) return {id, status: x.status};
      const j = await x.json();
      return {
        id,
        status: 200,
        name: j.displayName || j.name || null,
        paths: j.categoryIdPaths || null,
        childCount: (j.childCategories || []).length,
      };
    } catch (e) {
      return {id, status: -1, error: String(e)};
    }
  }));
}"""


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #
class ScrapeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    DATA.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def write_json(path: Path, obj, *, indent: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent)
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def to_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def slugify_id(cat_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", cat_id.lower()).strip("-")


def prettify_id(cat_id: str) -> str:
    known = {
        "BOVINOS": "Bovinos",
        "BOVINOS_IMPORTADOS": "Bovinos Importados",
        "AVES": "Aves",
        "SUINOS": "Suínos",
        "PESCADOS": "Pescados",
        "BATATAS_E_VEGETAIS": "Batatas e Vegetais",
        "CORDEIROS": "Cordeirinhos",
        "CHARQUES": "Charques",
        "OUTROS": "Outros",
        "MARCAS": "Marcas",
        "PROMOCOES": "Promoções",
    }
    if cat_id in known:
        return known[cat_id]
    parts = [p for p in cat_id.split("_") if p]
    for root in sorted(known, key=len, reverse=True):
        if cat_id.startswith(root + "_") and parts:
            parts = parts[1:]
            break
    words = [p.lower() for p in parts]
    if not words:
        return prettify_id(cat_id.replace("_", "")) if "_" in cat_id else cat_id
    small = {"de", "da", "do", "das", "dos", "e", "com", "sem", "a", "o", "para"}
    out = []
    for i, w in enumerate(words):
        if i > 0 and w in small:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


# --------------------------------------------------------------------------- #
# browser
# --------------------------------------------------------------------------- #
class Browser:
    def __init__(self, base_url: str, headless: bool = True, width: int = 400):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.width = width
        self._pw = None
        self.browser = None
        self.context = None

    async def __aenter__(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=UA,
            locale="pt-BR",
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9"},
        )
        return self

    async def __aexit__(self, *exc):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def new_page(self):
        page = await self.context.new_page()
        page.set_default_timeout(60000)
        page.set_default_navigation_timeout(120000)
        return page

    async def open_home(self, page, attempts: int = 4, wait_nav: bool = True):
        last = None
        for i in range(attempts):
            try:
                await page.goto(self.base_url + "/", wait_until="domcontentloaded", timeout=120000)
                # o menu de categorias é montado por JS depois do load
                if wait_nav:
                    try:
                        await page.wait_for_function(
                            "() => document.querySelectorAll('a[href^=\"/category/\"]').length > 50",
                            timeout=60000,
                        )
                    except Exception:
                        pass
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                delay = min(2 ** i * 3, 30) + random.uniform(0, 1.5)
                log(f"  home falhou ({type(exc).__name__}: {exc}); retry em {delay:.1f}s")
                await asyncio.sleep(delay)
        raise ScrapeError(f"não consegui abrir {self.base_url}/ : {last}")


async def page_fetch_text(page, path: str, attempts: int = 5) -> str:
    last = "?"
    for i in range(attempts):
        try:
            res = await asyncio.wait_for(page.evaluate(FETCH_TEXT_JS, path), timeout=120)
            if res and res.get("status") == 200 and res.get("text"):
                return res["text"]
            last = f"HTTP {res.get('status') if res else '?'}"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        if i == attempts - 1:
            break
        delay = min(2 ** i * 2, 45) + random.uniform(0, 1.5)
        log(f"  retry {i + 1}/{attempts - 1} em {delay:.1f}s <- {path.split('?')[0]} ({last})")
        await asyncio.sleep(delay)
    raise ScrapeError(f"falha ao buscar {path}: {last}")


# --------------------------------------------------------------------------- #
# fase 1 — catálogo
# --------------------------------------------------------------------------- #
async def collect_nav(page) -> tuple[dict, list]:
    """Nomes das categorias visíveis no menu (inclui categorias virtuais)."""
    try:
        anchors = await page.evaluate(NAV_JS)
    except Exception as exc:  # noqa: BLE001
        log(f"  aviso: não consegui ler o menu ({exc}); seguindo sem ele")
        return {}, []
    nav = {}
    order = []
    for href, text in anchors:
        cat_id = href.rsplit("/", 1)[-1].strip()
        if not cat_id:
            continue
        if cat_id not in nav:
            order.append(cat_id)
        nav.setdefault(cat_id, text)
    log(f"menu: {len(nav)} categorias com nome")
    return nav, order


def parse_path(path: str) -> list[str]:
    return [p for p in (path or "").split(">") if p]


async def fetch_categories(page, ids: list[str], chunk: int = 20) -> dict:
    meta: dict[str, dict] = {}
    for start in range(0, len(ids), chunk):
        part = ids[start:start + chunk]
        try:
            res = await asyncio.wait_for(page.evaluate(FETCH_COLLECTIONS_JS, part), timeout=120)
        except Exception as exc:  # noqa: BLE001
            log(f"  aviso: lote de coleções falhou ({type(exc).__name__}: {exc}); tentando 1 a 1")
            res = []
            for cid in part:
                try:
                    one = await asyncio.wait_for(page.evaluate(FETCH_COLLECTIONS_JS, [cid]), timeout=60)
                    res.extend(one or [])
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(0.15)
        for row in res or []:
            if row.get("status") == 200:
                meta[row["id"]] = {
                    "name": row.get("name"),
                    "paths": row.get("paths") or [],
                }
            else:
                meta.setdefault(row["id"], {"name": None, "paths": []})
        await asyncio.sleep(0.12)
    log(f"coleções: {sum(1 for v in meta.values() if v.get('name'))}/{len(ids)} com nome oficial")
    return meta


SENTINEL_SEGMENTS = {"rootCategory", "nonNavigableCategory"}


def normalize_path(path: str) -> list[str]:
    """Remove segmentos-sentinela do OCC e duplicatas consecutivas."""
    segs = [seg for seg in parse_path(path) if seg not in SENTINEL_SEGMENTS]
    out: list[str] = []
    for seg in segs:
        if not out or out[-1] != seg:
            out.append(seg)
    return out


def dedupe_slugs(rows: list[dict], key: str, fallback) -> None:
    """Garante slug único (o contrato exige UNIQUE): duplicado vira <slug>-<id>."""
    seen: set[str] = set()
    for row in rows:
        slug = (row.get(key) or "").strip() or fallback(row)
        if slug in seen:
            base = f"{slug}-{fallback(row)}"
            slug = base
            n = 2
            while slug in seen:
                slug = f"{base}-{n}"
                n += 1
        seen.add(slug)
        row[key] = slug


def build_category_tree(products: list[dict], meta: dict, nav: dict, nav_order: list) -> list[dict]:
    """Monta a lista de categorias do contrato a partir dos paths reais dos produtos."""
    all_paths: dict[str, str] = {}   # id -> path normalizado ("A>B>C")
    for prod in products:
        for raw in prod["_paths"]:
            segs = normalize_path(raw)
            if segs:
                all_paths.setdefault(segs[-1], ">".join(segs))

    for cid, info in meta.items():
        paths = [normalize_path(p) for p in (info.get("paths") or [])]
        paths = [p for p in paths if p]
        if not paths:
            continue
        chosen = next((p for p in paths if p[-1] == cid), paths[0])
        all_paths.setdefault(cid, ">".join(chosen))

    ids = set(all_paths) | set(nav) | set(nav_order)
    ids = {cid for cid in ids if cid and cid not in SENTINEL_SEGMENTS}

    # completa ancestrais que apareçam nos paths
    for path in list(all_paths.values()):
        for seg in parse_path(path):
            if seg not in SENTINEL_SEGMENTS:
                ids.add(seg)

    # pai por prefixo para ids que não têm path oficial
    def guess_parent(cat_id: str):
        best = None
        for other in ids:
            if other == cat_id or other in SENTINEL_SEGMENTS:
                continue
            if cat_id.startswith(other + "_") and (best is None or len(other) > len(best)):
                best = other
        return best

    categories = []
    for cat_id in ids:
        path = all_paths.get(cat_id)
        if path:
            segs = parse_path(path)
            parent = segs[-2] if len(segs) >= 2 else None
            raw_path = ">".join(segs)
        else:
            parent = guess_parent(cat_id)
            raw_path = f"{parent}>{cat_id}" if parent else cat_id
        name = (meta.get(cat_id) or {}).get("name") or nav.get(cat_id) or prettify_id(cat_id)
        categories.append(
            {
                "id": cat_id,
                "name": name,
                "slug": slugify_id(cat_id),
                "parent": parent,
                "path": raw_path,
            }
        )
    categories.sort(key=lambda c: (c["path"], c["id"]))
    return categories


def parse_nutrition(item: dict) -> list[str]:
    out = []
    for i in range(1, 22):
        raw = clean_text(item.get(f"x_iItem_{i}"))
        if not raw:
            continue
        parts = [p.strip() for p in raw.split("/") if p.strip()]
        if len(parts) < 4:
            continue
        name = parts[2]
        value = parts[3]
        vd = parts[4] if len(parts) > 4 else ""
        if not name:
            continue
        out.append(f"{name}: {value}" + (f" ({vd})" if vd else ""))
    return out


def image_source(item: dict) -> str | None:
    for key in ("primaryMediumImageURL", "primaryLargeImageURL", "primaryFullImageURL"):
        url = item.get(key)
        if not url:
            continue
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        src = (query.get("source") or [None])[0]
        if src:
            return src
    return None


def image_url(src: str, width: int, height: int = 0) -> str:
    height = height or width
    return (
        f"/ccstore/v1/images/?source={urllib.parse.quote(src, safe='/')}"
        f"&height={height}&width={width}"
    )


def build_product(item: dict, cat_names: dict, width: int, height: int = 0) -> dict:
    prod_id = clean_text(item.get("x_nCdProduto")) or str(item.get("id"))
    name = clean_text(item.get("x_cNmProduto"))
    if not name:
        display = clean_text(item.get("displayName")) or prod_id
        name = re.sub(r"\s*\(\s*" + re.escape(prod_id) + r"\s*\)\s*$", "", display).strip()
    paths = [clean_text(p) for p in (item.get("parentCategoryIdPath") or "").split(">") if p]
    paths = [p for p in paths if p]
    leaf = paths[-1] if paths else None
    cat_path = [p for p in paths if p != "rootCategory"]
    list_prices = item.get("listPrices") or {}
    sale_prices = item.get("salePrices") or {}
    price = to_float(list_prices.get("padrao"))
    if price is None:
        price = to_float(item.get("listPrice"))
    # fiel à API: itens sem preço ficam com price=null (reportado no stats)
    sale_price = to_float(sale_prices.get("padrao"))
    stock = "Indisponível"
    for key, value in item.items():
        if key.startswith("stock_") and value == "Disponível":
            stock = "Disponível"
            break
    attrs = {}
    for key in ("x_MARCA", "x_LINHA", "x_TEMPERATURA", "x_recomendadoPara"):
        val = clean_text(item.get(key))
        if val:
            attrs[key] = val
    src = image_source(item)
    prod = {
        "id": prod_id,
        "sku": prod_id,
        "name": name,
        "slug": clean_text(item.get("seoUrlSlugDerived")),
        "route": clean_text(item.get("route")),
        "brand": clean_text(item.get("brand")),
        "category_id": leaf,
        "category_name": cat_names.get(leaf),
        "category_path": cat_path,
        "price": price,
        "sale_price": sale_price,
        "unit": clean_text(item.get("x_cSgUnidadeMedida")),
        "ean": clean_text(item.get("x_cCdEAN")),
        "weight_min": to_float(item.get("x_nPesoMinimoVolume")),
        "weight_avg": to_float(item.get("x_nPesoMedioVolume")),
        "weight_max": to_float(item.get("x_nPesoMaximoVolume")),
        "stock": stock,
        "max_qty": to_int(item.get("x_iQtdeMaximaPeca")) or 1,
        "description_html": clean_text(item.get("longDescription")),
        "video_url": clean_text(item.get("x_videoUrl")),
        "nutrition": parse_nutrition(item),
        "attrs": attrs,
        "images": [],
    }
    prod["_paths"] = [item.get("parentCategoryIdPath")] if item.get("parentCategoryIdPath") else []
    prod["_image_src"] = src
    prod["_image_url"] = image_url(src, width, height) if src else None
    return prod


async def phase_catalog(args) -> tuple[list[dict], list[dict]]:
    DATA.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ckpt = read_json(CHECKPOINT, {}) or {}
    if args.force:
        ckpt = {}
    started = ckpt.get("started_at") or now_iso()

    async with Browser(args.base_url, args.headless, args.width) as br:
        page = await br.new_page()
        await br.open_home(page)
        nav, nav_order = await collect_nav(page)

        total_results = ckpt.get("total_results")
        limit = args.limit
        pages_done = set(ckpt.get("pages_done") or [])
        offset = ckpt.get("next_offset") or 0
        if pages_done and not args.force:
            log(f"retomando do checkpoint: {len(pages_done)} páginas feitas, próximo offset={offset}")

        while True:
            if total_results is not None and offset >= total_results:
                break
            raw_file = RAW_DIR / f"products-{offset:05d}.json"
            payload = None
            if raw_file.exists() and not args.force and offset in pages_done:
                payload = read_json(raw_file)
                if payload:
                    log(f"página offset={offset}: reaproveitando cache ({len(payload.get('items') or [])} itens)")
            if payload is None:
                text = await page_fetch_text(page, f"/ccstore/v1/products?limit={limit}&offset={offset}")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ScrapeError(f"JSON inválido no offset {offset}: {exc}") from exc
                total_results = payload.get("totalResults", total_results)
                write_json(raw_file, payload)
            if total_results is None:
                total_results = payload.get("totalResults")
            items = payload.get("items") or []
            log(
                f"página offset={offset}: {len(items)} itens | acumulado "
                f"{offset + len(items)}/{total_results}"
            )
            pages_done.add(offset)
            offset += limit
            write_json(
                CHECKPOINT,
                {
                    "started_at": started,
                    "updated_at": now_iso(),
                    "total_results": total_results,
                    "limit": limit,
                    "next_offset": offset,
                    "pages_done": sorted(pages_done),
                },
                indent=1,
            )
            if not items:
                break
            if args.max_pages and len(pages_done) >= args.max_pages:
                log("--max-pages atingido, parando paginação")
                break
            if total_results is not None and offset >= total_results:
                break

        # junta tudo (cache + memória) na ordem dos offsets
        raw_items: list[dict] = []
        seen = set()
        for off in sorted(pages_done):
            payload = read_json(RAW_DIR / f"products-{off:05d}.json", {}) or {}
            for item in payload.get("items") or []:
                pid = str(item.get("id"))
                if pid in seen:
                    continue
                seen.add(pid)
                raw_items.append(item)
        log(f"catálogo: {len(raw_items)} produtos brutos")

        # nomes oficiais das categorias
        ids: set[str] = set()
        for item in raw_items:
            for seg in (item.get("parentCategoryIdPath") or "").split(">"):
                seg = seg.strip()
                if seg and seg != "rootCategory":
                    ids.add(seg)
        ids.update(nav)
        meta = await fetch_categories(page, sorted(ids))

        products = [build_product(item, {}, args.width, args.height) for item in raw_items]
        dedupe_slugs(products, key="slug", fallback=lambda prod: str(prod["id"]))
        categories = build_category_tree(products, meta, nav, nav_order)
        dedupe_slugs(categories, key="slug", fallback=lambda cat: cat["id"].lower())
        cat_by_id = {c["id"]: c for c in categories}
        for prod in products:
            cid = prod["category_id"]
            cat = cat_by_id.get(cid)
            if cat:
                prod["category_name"] = cat["name"]
                prod["category_path"] = parse_path(cat["path"])
            else:
                prod["category_name"] = None
                prod["category_path"] = []

        scraped_at = now_iso()
        public_products = [
            {k: v for k, v in prod.items() if not k.startswith("_")} for prod in products
        ]
        catalog = {
            "scraped_at": scraped_at,
            "total": len(public_products),
            "categories": categories,
            "products": public_products,
        }
        write_json(CATALOG, catalog)
        write_json(
            IMG_INDEX,
            {
                prod["id"]: {
                    "url": prod["_image_url"],
                    "source": prod["_image_src"],
                }
                for prod in products
                if prod.get("_image_url")
            },
            indent=1,
        )
        log(
            f"catalog.json escrito: {len(products)} produtos, {len(categories)} categorias, "
            f"{len(raw_items) - len(products)} duplicados descartados"
        )
        log(
            f"com imagem: {sum(1 for p in products if p.get('_image_url'))} | "
            f"sem imagem: {sum(1 for p in products if not p.get('_image_url'))}"
        )
    return products, categories


# --------------------------------------------------------------------------- #
# fase 2 — imagens
# --------------------------------------------------------------------------- #
def count_done_images(products: list[dict]) -> tuple[int, int]:
    done = missing = 0
    for prod in products:
        path = IMAGES_DIR / str(prod["id"]) / "main.jpg"
        if path.exists() and path.stat().st_size > 500:
            done += 1
        else:
            missing += 1
    return done, missing


async def download_one(page, url: str, dest: Path, attempts: int = 4) -> tuple[bool, str, int]:
    last = "?"
    for i in range(attempts):
        try:
            res = await asyncio.wait_for(page.evaluate(FETCH_IMAGE_JS, url), timeout=90)
            if not res:
                last = "resposta vazia"
            elif res.get("status") != 200:
                last = f"HTTP {res.get('status')}"
            else:
                data = res.get("data") or ""
                ct = (res.get("ct") or "").lower()
                if "," not in data:
                    last = f"conteúdo inválido ({ct})"
                elif "image" not in ct:
                    last = f"content-type {ct or '?'}"
                else:
                    raw = base64.b64decode(data.split(",", 1)[1], validate=False)
                    if len(raw) < 500:
                        last = f"arquivo muito pequeno ({len(raw)}B)"
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        tmp = dest.with_name(dest.name + ".part")
                        tmp.write_bytes(raw)
                        tmp.replace(dest)
                        return True, "", len(raw)
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        if i < attempts - 1:
            await asyncio.sleep(min(2 ** i, 8) + random.uniform(0, 0.8))
    return False, last, 0


async def phase_images(args, products: list[dict]) -> dict:
    index = read_json(IMG_INDEX, {}) or {}
    todo: list[dict] = []
    for prod in products:
        pid = str(prod["id"])
        dest = IMAGES_DIR / pid / "main.jpg"
        if not args.force and dest.exists() and dest.stat().st_size > 500:
            continue
        entry = index.get(pid) or {}
        url = entry.get("url") or prod.get("_image_url")
        if not url:
            continue
        todo.append({"id": pid, "url": url})

    done_before, _ = count_done_images(products)
    log(f"imagens: {len(todo)} a baixar ({done_before} já no disco), workers={args.workers}")
    if not todo:
        return {
            "downloaded": 0,
            "failed": 0,
            "failed_items": [],
            "missing_origin": [],
            "aborted": False,
            "workers": args.workers,
            "failed_ids": set(),
        }

    queue: asyncio.Queue = asyncio.Queue()
    for job in todo:
        queue.put_nowait(job)

    state = {
        "consec_fail": 0,
        "delay": 0.0,
        "downloaded": 0,
        "failed": 0,
        "failed_items": [],
        "done": 0,
        "started": time.time(),
        "abort": False,
    }
    lock = asyncio.Lock()

    async def worker(wid: int, page):
        while not state["abort"]:
            try:
                job = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if state["delay"]:
                await asyncio.sleep(state["delay"])
            dest = IMAGES_DIR / job["id"] / "main.jpg"
            ok, err, size = await download_one(page, job["url"], dest)
            async with lock:
                state["done"] += 1
                if ok:
                    state["downloaded"] += 1
                    state["consec_fail"] = 0
                    if state["delay"]:
                        state["delay"] = max(0.0, state["delay"] - 0.2)
                else:
                    state["failed"] += 1
                    state["consec_fail"] += 1
                    state["failed_items"].append({"id": job["id"], "reason": err})
                    if state["consec_fail"] >= 6:
                        state["delay"] = min(state["delay"] + 1.5, 10.0)
                        log(f"  AVISO: {state['consec_fail']} falhas seguidas -> delay {state['delay']:.1f}s")
                    if state["consec_fail"] >= 20:
                        state["abort"] = True
                        log("  ABORTANDO: 20 falhas consecutivas. Rode de novo com --workers 2 --only-missing")
                n = state["done"]
                if n % 50 == 0 or n == len(todo):
                    elapsed = time.time() - state["started"]
                    rate = n / elapsed if elapsed else 0
                    eta = (len(todo) - n) / rate if rate else 0
                    log(
                        f"  {n}/{len(todo)} ({state['downloaded']} ok, {state['failed']} falhas) "
                        f"{rate:.1f} img/s ETA {eta/60:.1f}min"
                    )
                    write_json(
                        IMG_CHECKPOINT,
                        {
                            "updated_at": now_iso(),
                            "total": len(todo),
                            "done": n,
                            "downloaded": state["downloaded"],
                            "failed": state["failed"],
                            "workers": args.workers,
                        },
                        indent=1,
                    )

    async with Browser(args.base_url, args.headless, args.width) as br:
        page = await br.new_page()
        await br.open_home(page, wait_nav=False)
        pages = [page]
        for _ in range(max(0, args.workers - 1)):
            extra = await br.new_page()
            await br.open_home(extra, wait_nav=False)
            pages.append(extra)
        log(f"  {len(pages)} abas prontas")
        await asyncio.gather(*(worker(i, pages[i % len(pages)]) for i in range(len(pages))))

    if state["abort"]:
        log(f"imagens interrompidas: {state['downloaded']} baixadas, {state['failed']} falhas")
    else:
        log(f"imagens: {state['downloaded']} baixadas, {state['failed']} falhas")
    write_json(
        IMG_CHECKPOINT,
        {
            "updated_at": now_iso(),
            "total": len(todo),
            "done": state["done"],
            "downloaded": state["downloaded"],
            "failed": state["failed"],
            "workers": args.workers,
            "aborted": state["abort"],
        },
        indent=1,
    )

    # produtos sem imagem de origem (não é falha de download)
    missing_origin = [prod["id"] for prod in products if not (index.get(str(prod["id"])) or prod.get("_image_url"))]
    failed_ids = {row["id"] for row in state["failed_items"]}
    return {
        "downloaded": state["downloaded"],
        "failed": state["failed"],
        "failed_items": state["failed_items"],
        "missing_origin": missing_origin,
        "aborted": state["abort"],
        "workers": args.workers,
        "failed_ids": failed_ids,
    }


# --------------------------------------------------------------------------- #
# fase 2b — resize (padroniza imagens já baixadas)
# --------------------------------------------------------------------------- #
def phase_resize(args) -> dict:
    from PIL import Image

    target_w, target_h = args.width, args.height or args.width
    resized = skipped = failed = 0
    for path in sorted(IMAGES_DIR.rglob("main.jpg")):
        try:
            with Image.open(path) as im:
                width, height = im.size
                if width <= target_w and height <= target_h:
                    skipped += 1
                    continue
                rgb = im.convert("RGB")
                rgb.thumbnail((target_w, target_h), Image.LANCZOS)
                rgb.save(path, "JPEG", quality=80, optimize=True)
                resized += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log(f"  resize falhou em {path}: {type(exc).__name__}: {exc}")
    log(f"resize: {resized} redimensionadas p/ {target_w}x{target_h}, {skipped} já ok, {failed} falhas")
    return {"resized": resized, "skipped": skipped, "failed": failed}


# --------------------------------------------------------------------------- #
# fase 3 — finalize (amarra images[] com o disco e escreve stats)
# --------------------------------------------------------------------------- #
def phase_finalize(products: list[dict], categories: list[dict], img_result: dict | None, elapsed: float | None, args=None) -> dict:
    catalog = read_json(CATALOG) or {"scraped_at": now_iso(), "total": 0, "categories": [], "products": []}
    products = catalog.get("products") or products
    categories = catalog.get("categories") or categories

    img_index = read_json(IMG_INDEX, {}) or {}
    missing_rows = []
    with_images = 0
    for prod in products:
        pid = str(prod["id"])
        path = IMAGES_DIR / pid / "main.jpg"
        if path.exists() and path.stat().st_size > 500:
            prod["images"] = [{"file": f"products/{pid}/main.jpg"}]
            with_images += 1
        else:
            prod["images"] = []
            missing_rows.append(
                {
                    "id": pid,
                    "name": prod.get("name"),
                    "reason": "sem primaryMediumImageURL" if pid not in img_index else "download falhou",
                }
            )
        prod.pop("_image_url", None)
        prod.pop("_image_src", None)
        prod.pop("_paths", None)

    catalog["products"] = products
    catalog["total"] = len(products)
    catalog["categories"] = categories
    write_json(CATALOG, catalog)

    total_bytes = 0
    images = 0
    for path in IMAGES_DIR.rglob("*"):
        if path.is_file():
            total_bytes += path.stat().st_size
            images += 1

    ckpt = read_json(CHECKPOINT, {}) or {}
    started_at = ckpt.get("started_at")
    if ckpt.get("elapsed_s") is not None:
        # já congelado numa execução anterior: re-finalizar não infla o tempo
        elapsed = ckpt["elapsed_s"]
    elif started_at:
        # tempo da captura: do primeiro --phase catalog até o fim do download das imagens
        end_at = (read_json(IMG_CHECKPOINT, {}) or {}).get("updated_at") or now_iso()
        try:
            elapsed = (datetime.fromisoformat(end_at) - datetime.fromisoformat(started_at)).total_seconds()
        except ValueError:
            elapsed = None
        if elapsed is not None:
            ckpt["elapsed_s"] = round(elapsed, 1)
            write_json(CHECKPOINT, ckpt, indent=1)

    prices = [prod.get("price") for prod in products]
    price_null = [prod["id"] for prod in products if prod.get("price") is None]
    stats = {
        "products": len(products),
        "categories": len(categories),
        "images": images,
        "bytes": total_bytes,
        "elapsed_s": round(elapsed, 1) if elapsed else None,
        "scraped_at": catalog.get("scraped_at") or now_iso(),
        "products_with_image": with_images,
        "products_without_image": len(products) - with_images,
        "images_mb": round(total_bytes / (1024 * 1024), 2),
        "image_dimensions_max": f"{getattr(args, 'width', 600)}x{getattr(args, 'height', 600)}",
        "sale_price_not_null": sum(1 for prod in products if prod.get("sale_price") is not None),
        "price_9999": sum(1 for value in prices if value == 9999.0),
        "price_null": len(price_null),
        "price_null_ids": price_null,
        "price_distinct_values": sorted({value for value in prices if value is not None}),
        "failed_downloads": len(img_result.get("failed_items") or []) if img_result else 0,
        "aborted": bool(img_result and img_result.get("aborted")),
    }
    write_json(STATS, stats, indent=1)

    reasons = {}
    for row in missing_rows:
        reasons.setdefault(row["reason"], 0)
        reasons[row["reason"]] += 1
    write_json(MISSING, {"scraped_at": stats["scraped_at"], "count": len(missing_rows), "products": missing_rows}, indent=1)
    log(f"finalize: {stats}")
    return stats


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Scraper do catálogo Friboi Online (Playwright)")
    ap.add_argument("--phase", choices=["all", "catalog", "images", "resize", "finalize"], default="all")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--width", type=int, default=600)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--force", action="store_true", help="ignora cache/checkpoint e baixa tudo de novo")
    ap.add_argument("--only-missing", action="store_true", help="imagens: só as que faltam no disco")
    ap.add_argument("--max-pages", type=int, default=0, help="DEBUG: limita quantas páginas puxar")
    ap.add_argument("--max-images", type=int, default=0, help="DEBUG: limita quantas imagens baixar")
    ap.add_argument("--headed", action="store_true")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    args.headless = not args.headed
    if args.workers < 1:
        args.workers = 1
    DATA.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    products: list[dict] = []
    categories: list[dict] = []
    img_result = None

    try:
        if args.phase in ("all", "catalog"):
            log(f"=== fase catálogo (limit={args.limit}) ===")
            products, categories = asyncio.run(phase_catalog(args))
        if args.phase in ("all", "images"):
            if not products:
                catalog = read_json(CATALOG, {}) or {}
                products = catalog.get("products") or []
                categories = catalog.get("categories") or []
            if not products:
                raise ScrapeError("catalog.json vazio ou inexistente: rode --phase catalog antes")
            log(f"=== fase imagens (workers={args.workers}) ===")
            if args.max_images:
                products = products[: args.max_images]
            img_result = asyncio.run(phase_images(args, products))
        if args.phase in ("all", "resize"):
            log(f"=== fase resize ({args.width}x{args.height}) ===")
            phase_resize(args)
        if args.phase in ("all", "images", "finalize"):
            log("=== fase finalize ===")
            phase_finalize(products, categories, img_result, time.time() - t0, args)
    except ScrapeError as exc:
        log(f"ERRO: {exc}")
        log("progresso preservado no checkpoint; rode o mesmo comando para retomar.")
        return 2
    except KeyboardInterrupt:
        log("interrompido pelo usuário; progresso preservado.")
        return 130

    log(f"OK em {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
