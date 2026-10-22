#!/usr/bin/env python3
"""Check 7 — fidelidade visual: screenshots + medição de estilos computados.

Roda com o python3 do sistema (Playwright global; o .venv do projeto não tem
playwright). O servidor precisa estar no ar (tests/run_e2e.sh sobe na 8199).

Uso:
    python3 tests/visual_check.py [BASE_URL]

Saída:
    tests/screenshots/*.png     screenshots full-page de cada página (1440/1024)
    tests/artifacts/visual.json medições, comparação com o DESIGN_SPEC e erros de console
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
ARTI = ROOT / "tests" / "artifacts"
SHOTS.mkdir(parents=True, exist_ok=True)
ARTI.mkdir(parents=True, exist_ok=True)
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8199").rstrip("/")

PROD = "alcatra-com-maminha-fracionada-3-partes-friboi-bovino-resfriado"

MEASURE_JS = r"""
async () => {
  const one = (s, ctx) => (ctx || document).querySelector(s);
  const num = v => { const n = parseFloat(v); return Number.isFinite(n) ? Math.round(n*100)/100 : null; };
  const box = (s) => { const e = one(s); if (!e) return null; const r = e.getBoundingClientRect();
    return {w: Math.round(r.width*100)/100, h: Math.round(r.height*100)/100,
            x: Math.round(r.left*100)/100, y: Math.round((r.top+scrollY)*100)/100}; };
  const cs = (s, props, pseudo) => { const e = one(s); if (!e) return null; const st = getComputedStyle(e, pseudo||null);
    const o = {}; for (const p of props) o[p] = st[p]; return o; };
  const boxes = (s) => [...document.querySelectorAll(s)].map(e => { const r = e.getBoundingClientRect();
    return {w: Math.round(r.width*100)/100, h: Math.round(r.height*100)/100,
            x: Math.round(r.left*100)/100, y: Math.round((r.top+scrollY)*100)/100}; });
  const txt = s => { const e = one(s); return e ? (e.textContent||'').replace(/\s+/g,' ').trim() : null; };

  // fontes: força o load e só então verifica
  const faces = [...document.fonts].map(f => ({family: f.family, weight: f.weight, style: f.style, status: f.status}));
  let roboto = false, robotoCond = false;
  try { await document.fonts.load('400 16px Roboto'); } catch(e) {}
  try { await document.fonts.load('300 16px "Roboto Condensed"'); } catch(e) {}
  try { await document.fonts.ready; } catch(e) {}
  roboto = document.fonts.check('400 16px Roboto');
  robotoCond = document.fonts.check('300 16px "Roboto Condensed"');

  const sections = [...document.querySelectorAll('main section, main > div, .site-footer')].map(e => ({
    cls: (typeof e.className === 'string' ? e.className : e.tagName),
    h: Math.round(e.getBoundingClientRect().height*100)/100,
    y: Math.round((e.getBoundingClientRect().top + scrollY)*100)/100,
  })).filter(s => s.h > 8);

  const navTop = [...document.querySelectorAll('.main-nav > .nav-inner > ul > li > a')]
    .map(a => (a.textContent||'').trim()).filter(Boolean);

  return {
    url: location.href, title: document.title,
    viewport: {w: innerWidth, h: innerHeight},
    doc: {scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollHeight: document.documentElement.scrollHeight,
          horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1},

    header: box('.site-header'),
    header_style: cs('.site-header', ['backgroundColor']),
    header_inner: box('.header-inner'),
    logo: box('.site-header .logo-img'),
    search: box('.site-header form.search'),
    search_style: cs('.site-header form.search', ['backgroundColor','borderRadius']),
    search_input: box('.site-header form.search input'),
    search_input_style: cs('.site-header form.search input', ['fontSize','color','backgroundColor','borderRadius','fontFamily']),
    search_btn: box('.site-header form.search button'),
    login_btn: box('.site-header .btn-login'),
    login_btn_style: cs('.site-header .btn-login', ['backgroundColor','color','fontSize','fontWeight','borderRadius']),
    cart_link: box('.site-header .cart-link'),

    nav: box('.main-nav'),
    nav_style: cs('.main-nav', ['backgroundColor','fontSize']),
    nav_top_links: navTop,
    nav_link_style: cs('.main-nav > .nav-inner > ul > li > a', ['fontSize','fontWeight','color']),

    coupon: box('.coupon-bar'),
    coupon_bg: (() => { const e = one('.coupon-bar'); return e ? getComputedStyle(e).backgroundImage : null; })(),
    coupon_text: txt('.coupon-bar'),
    coupon_inner_style: cs('.coupon-bar .coupon-inner', ['fontSize','color']),
    coupon_link: txt('.coupon-bar a'),

    hero: box('.hero'),
    hero_viewport: box('.hero-viewport'),
    hero_viewport_style: cs('.hero-viewport', ['borderRadius','aspectRatio','backgroundColor']),
    hero_img: box('.hero-slide.is-active img'),
    hero_img_src: (() => { const e = one('.hero-slide.is-active img'); return e ? e.getAttribute('src') : null; })(),
    hero_dots: boxes('.hero-dots button'),
    dot_active_bg: (() => { const e = one('.hero-dots button.is-active'); return e ? getComputedStyle(e).backgroundColor : null; })(),
    dot_idle_bg: (() => { const e = one('.hero-dots button:not(.is-active)'); return e ? getComputedStyle(e).backgroundColor : null; })(),
    hero_arrows: box('.hero-nav.prev'),

    cats: boxes('.categories-grid .category-item'),
    cat_item_style: cs('.category-item', ['borderColor','borderWidth','borderRadius','backgroundColor']),
    cat_icon_box: box('.category-item .icon-box'),
    cat_icon: box('.category-item .cat-img'),
    cat_name_style: cs('.category-item .category-name', ['fontSize','fontWeight','color','fontFamily']),
    cat_names: [...document.querySelectorAll('.category-item .category-name')].map(e => (e.textContent||'').trim()),

    vitrine: box('.vitrine'),
    vitrine_title: box('.vitrine-title'),
    vitrine_title_style: cs('.vitrine-title', ['fontSize','fontWeight','color','fontFamily']),
    vitrine_title_text: txt('.vitrine-title'),
    vitrine_t1_style: cs('.vitrine-title .t1', ['fontFamily','fontWeight','fontSize']),
    vitrine_t2_style: cs('.vitrine-title .t2', ['fontFamily','fontWeight','fontSize']),
    carousel_arrow: box('.carousel-arrow'),
    carousel_arrow_style: cs('.carousel-arrow', ['backgroundColor','borderRadius','width','height']),

    product_card: box('.product-card'),
    product_card_style: cs('.product-card', ['borderColor','borderWidth','borderRadius','boxShadow','backgroundColor']),
    product_tag: box('.product-tag.temperatura'),
    product_tag_style: cs('.product-tag.temperatura', ['backgroundColor','color','fontSize','fontWeight','borderRadius','padding']),
    product_code_style: cs('.label-cod', ['fontSize','fontWeight','color']),
    product_name_style: cs('.product-name', ['fontSize','fontWeight','color','lineHeight']),
    info_item_style: cs('.info-item', ['fontSize','fontWeight','color','backgroundColor']),
    price_now_style: cs('.price-now', ['fontSize','fontWeight','color','fontFamily']),
    card_pricing: (() => { const e = one('.product-card .product-pricing'); if (!e) return null;
      return {h: Math.round(e.getBoundingClientRect().height*100)/100,
              txt: (e.textContent||'').replace(/\s+/g,' ').trim().slice(0,40)}; })(),
    card_details_h: (() => { const e = one('.product-card .product-details'); return e ? Math.round(e.getBoundingClientRect().height*100)/100 : null; })(),
    ver_btn: box('.ver-produto-btn'),
    ver_btn_style: cs('.ver-produto-btn', ['backgroundColor','color','height','fontSize','borderRadius','fontWeight']),

    brand_cards: boxes('.brand-card'),
    brand_cards_title: txt('.brand-cards h2, .brand-cards .section-title-lg'),
    brand_imgs: [...document.querySelectorAll('.brand-card img')].map(i => ({src: i.getAttribute('src'),
      nw: i.naturalWidth, nh: i.naturalHeight})),
    brand_items: boxes('.brand-item'),
    brand_item_titles: [...document.querySelectorAll('.brand-item')].map(e => (e.textContent||'').replace(/\s+/g,' ').trim().slice(0,40)),
    brand_item_imgs: [...document.querySelectorAll('.brand-item img')].map(i => ({src: i.getAttribute('src'),
      nw: i.naturalWidth, nh: i.naturalHeight})),

    benefit_cards: boxes('.benefit-card'),
    benefit_style: cs('.benefit-card', ['backgroundImage','borderRadius']),
    benefit_icon: box('.benefit-card .icon-wrapper'),
    benefit_icon_style: cs('.benefit-card .icon-wrapper', ['backgroundColor','width','height','borderRadius']),
    benefit_titles: [...document.querySelectorAll('.benefit-card h3, .beneficio-titulo')].map(e => (e.textContent||'').trim()),
    benefit_title_style: cs('.benefit-card h3, .beneficio-titulo', ['fontSize','fontWeight','color']),

    institutional: box('.institutional-banner'),
    institutional_img: box('.institutional-banner img'),
    institutional_style: cs('.institutional-banner', ['borderRadius']),

    footer: box('.site-footer'),
    footer_bg: (() => { const e = one('.site-footer'); return e ? getComputedStyle(e).backgroundColor : null; })(),
    footer_cols: boxes('.footer-column'),
    footer_h3_style: cs('.footer-column h3', ['fontSize','fontWeight','color','textTransform','letterSpacing']),
    footer_h3_bar: cs('.footer-column h3', ['width','backgroundColor'], '::before'),
    footer_h3s: [...document.querySelectorAll('.footer-column h3')].map(h => (h.textContent||'').trim()),
    footer_links: [...document.querySelectorAll('.footer-link')].map(a => (a.textContent||'').trim()).slice(0, 30),
    footer_payments: [...document.querySelectorAll('.payment-row .payment-item')].map(e => {
      const i = e.querySelector('img');
      return {title: e.getAttribute('title'), src: i ? i.getAttribute('src') : null,
              nw: i ? i.naturalWidth : null, nh: i ? i.naturalHeight : null};
    }),
    footer_safety: [...document.querySelectorAll('.safety-row .safety-badge')].map(e => (e.textContent||'').replace(/\s+/g,' ').trim().slice(0,40)),
    footer_socials: [...document.querySelectorAll('.site-footer .social-icon, .site-footer [class*=social] a')]
      .map(a => ({href: a.getAttribute('href'), label: (a.getAttribute('aria-label')||'')})).slice(0, 6),
    footer_copyright: txt('.site-footer [class*=copy], .site-footer small, .site-footer p'),
    footer_copyright_style: cs('.copyright-bar p, .site-footer [class*=copy] p', ['fontSize','color']),

    body_font: (() => { const s = getComputedStyle(document.body); return {family: s.fontFamily, size: s.fontSize, color: s.color}; })(),
    fonts: {roboto_loaded_ok: roboto, roboto_cond_loaded_ok: robotoCond, faces},
    counts: {
      categories: document.querySelectorAll('.categories-grid .category-item').length,
      product_cards: document.querySelectorAll('.product-card').length,
      brand_cards: document.querySelectorAll('.brand-card').length,
      brand_items: document.querySelectorAll('.brand-item').length,
      benefits: document.querySelectorAll('.benefit-card').length,
      heroes: document.querySelectorAll('.hero-slide').length,
      dots: document.querySelectorAll('.hero-dots button').length,
      vitrines: document.querySelectorAll('.vitrine').length,
      footer_cols: document.querySelectorAll('.footer-column').length,
    },
    broken_images: [...document.images].filter(i => !i.complete || i.naturalWidth === 0)
      .map(i => i.getAttribute('src')).slice(0, 20),
    sections,
  };
}
"""

PAGES = [
    ("home", "/", True),
    ("home-1024", "/", False, 1024),
    ("categoria-bovinos", "/categoria/bovinos", False),
    ("produto", f"/produto/{PROD}", False),
    ("login", "/login", False),
    ("cadastro", "/cadastro", False),
    ("carrinho", "/carrinho", False),
    ("checkout", "/checkout", False),
    ("promocoes", "/promocoes", False),
    ("busca-acem", "/busca?q=acem", False),
    ("404", "/nao-existe-t5", False),
]

# (valor esperado, tolerância, fonte no DESIGN_SPEC, caminho em `med`, tipo)
SPEC: dict[str, tuple] = {
    "header.height":  (143, 8, "§6.5 header branco de 143 px", "header.h", "num"),
    "header.bg":      ("#FFFFFF", None, "§0/§1.4 header branco", "header_style.backgroundColor", "hex"),
    "logo.w":         (129, 4, "§6.5 logo 129×82", "logo.w", "num"),
    "logo.h":         (82, 4, "§6.5 logo 129×82", "logo.h", "num"),
    "search.w":       (565, 20, "§6.5/CAPTURE input de busca 565×50", "search_input.w", "num"),
    "search.h":       (50, 6, "§6.5 busca cinza 565×50", "search.h", "num"),
    "search.bg":      ("#EFEFEF", None, "§1.4 input de busca #EFEFEF", "search_style.backgroundColor", "hex"),
    "login_btn.w":    (220, 8, "§6.5 botão #B5000B 220×52", "login_btn.w", "num"),
    "login_btn.h":    (52, 6, "§6.5 botão #B5000B 220×52", "login_btn.h", "num"),
    "login_btn.bg":   ("#B5000B", None, "§1.2 vermelho CTA", "login_btn_style.backgroundColor", "hex"),
    "nav.h":          (57, 6, "§0 nav 57 px", "nav.h", "num"),
    "nav.font":       (15, 1, "§1.2 links da nav 15 px/500", "nav_link_style.fontSize", "num"),
    "nav.weight":     ("500", None, "§1.2 links da nav 15 px/500", "nav_link_style.fontWeight", "str"),
    "coupon.h":       (53, 8, "§6.5 faixa de cupom 53 px", "coupon.h", "num"),
    "hero.w":         (1200, 30, "§6.5 hero 1200×250", "hero_viewport.w", "num"),
    "hero.h":         (250, 20, "§6.5 hero 1200×250", "hero_viewport.h", "num"),
    "hero.radius":    (6, 2, "§6.5 hero raio 6", "hero_viewport_style.borderRadius", "num"),
    "dot.w":          (28, 3, "§6.5 bolinhas de 28 px", "hero_dots.0.w", "num"),
    "dot.active_bg":  ("#B5000B", None, "§6.5 bolinha ativa vermelha", "dot_active_bg", "hex"),
    "dot.idle_bg":    ("#666666", None, "§1.2 bolinha inativa #666", "dot_idle_bg", "hex"),
    "cat.count":      (9, 0, "§6.5 faixa de 9 categorias", "counts.categories", "num"),
    "cat_tile.w":     (100, 8, "§6.5 quadrados 100×113", "cats.0.w", "num"),
    "cat_tile.h":     (113, 8, "§6.5 quadrados 100×113", "cats.0.h", "num"),
    "cat_border":     ("#B5000B", None, "§6.5 borda #B5000B", "cat_item_style.borderColor", "hex"),
    "cat_radius":     (8, 2, "§6.5 raio 8", "cat_item_style.borderRadius", "num"),
    "cat_icon.w":     (52, 4, "§6.5 ícones 52×52", "cat_icon.w", "num"),
    "cat_name.size":  (13, 1, "§6.5 rótulo 13 px", "cat_name_style.fontSize", "num"),
    "cat_name.weight": ("600", None, "§6.5 rótulo 600", "cat_name_style.fontWeight", "str"),
    "title.size":     (40, 4, "§6.5 título de vitrine 40 px", "vitrine_title_style.fontSize", "num"),
    "title.color":    ("#0D0154", None, "§1.2 azul display #0D0154", "vitrine_title_style.color", "hex"),
    "arrow.size":     (40, 3, "§6.5 setas circulares de 40 px", "carousel_arrow.w", "num"),
    "arrow.bg":       ("#B5000B", None, "§1.2 setas #B5000B", "carousel_arrow_style.backgroundColor", "hex"),
    "card.w":         (255, 6, "§6.5 card 255×271", "product_card.w", "num"),
    "card.h":         (271, 6, "§6.5/CAPTURE card 255×271", "product_card.h", "num"),
    "card.no_price":  (None, None, "CAPTURE: o card do original NÃO exibe preço (só badge/CÓD/nome/chips/botão)", "card_pricing", "absent"),
    "badge.size":     (8.4, 1, "CAPTURE .product-tag 8,4 px", "product_tag_style.fontSize", "num"),
    "card.border":    ("#EFEFEF", None, "§1.2 borda #EFEFEF", "product_card_style.borderColor", "hex"),
    "badge.bg":       ("#0D174F", None, "§6.5 badge #0D174F", "product_tag_style.backgroundColor", "hex"),
    "name.size":      (12, 1, "§6.5 nome 12 px/700", "product_name_style.fontSize", "num"),
    "name.weight":    ("700", None, "§6.5 nome 12 px/700", "product_name_style.fontWeight", "str"),
    "name.color":     ("#102161", None, "§1.2 #102161", "product_name_style.color", "hex"),
    "ver_btn.h":      (35, 4, "§6.5 botão vermelho 35 px", "ver_btn.h", "num"),
    "ver_btn.bg":     ("#B5000B", None, "§1.2 CTA #B5000B", "ver_btn_style.backgroundColor", "hex"),
    "brand_card.w":   (560, 14, "§6.5 cards de marca 560×224", "brand_cards.0.w", "num"),
    "brand_card.h":   (224, 12, "§6.5 cards de marca 560×224", "brand_cards.0.h", "num"),
    "brand_card.count": (6, 0, "§6.5 6 cards de marca", "counts.brand_cards", "num"),
    "brand_item.w":   (200, 10, "§6.5 faixa de 5 marcas 200×340", "brand_items.0.w", "num"),
    "brand_item.h":   (340, 16, "§6.5 faixa de 5 marcas 200×340", "brand_items.0.h", "num"),
    "brand_item.count": (5, 0, "§6.5 faixa de 5 marcas", "counts.brand_items", "num"),
    "benefit.count":  (4, 0, "§6.5 4 cards de benefício", "counts.benefits", "num"),
    "benefit_card.w": (270, 10, "CAPTURE .card-beneficio 270×160", "benefit_cards.0.w", "num"),
    "benefit_card.h": (160, 10, "CAPTURE .card-beneficio 270×160", "benefit_cards.0.h", "num"),
    "benefit_titulo.size": (14, 1, "CAPTURE .beneficio-titulo 14 px", "benefit_title_style.fontSize", "num"),
    "benefit_titulo.weight": ("800", None, "CAPTURE .beneficio-titulo 800", "benefit_title_style.fontWeight", "str"),
    "card_code.size": (10, 1, "CAPTURE .product-code-tag 10 px", "product_code_style.fontSize", "num"),
    "footer_copy.size": (9.8, 1, "CAPTURE .copyright-bar 9,8 px", "footer_copyright_style.fontSize", "num"),
    "benefit.radius": (16, 2, "§6.5 raio 16", "benefit_style.borderRadius", "num"),
    "benefit_icon.w": (32, 3, "§6.5 ícone 32×32", "benefit_icon.w", "num"),
    "benefit_icon.bg": ("#E30613", None, "§6.5 quadrado #E30613", "benefit_icon_style.backgroundColor", "hex"),
    "inst.w":         (1140, 20, "§6.5 banner 1140×176", "institutional.w", "num"),
    "inst.h":         (176, 14, "§6.5 banner 1140×176", "institutional.h", "num"),
    "inst.radius":    (8, 2, "§6.5 raio 8", "institutional_style.borderRadius", "num"),
    "footer.bg":      ("#0D174F", None, "§6.5 footer #0D174F", "footer_bg", "hex"),
    "footer.cols":    (4, 0, "§6.5 footer 4 colunas", "counts.footer_cols", "num"),
    "footer_col.w":   (321, 10, "§6.5/CAPTURE colunas de 320,75 px", "footer_cols.0.w", "num"),
    "footer_h3.size": (13.3, 1.2, "§6.5 h3 13,3 px", "footer_h3_style.fontSize", "num"),
    "footer_h3.weight": ("800", None, "§6.5 h3 800", "footer_h3_style.fontWeight", "str"),
    "footer_h3.bar":  ("#E30613", None, "§6.5 barra vermelha #E30613", "footer_h3_bar.backgroundColor", "hex"),
    "nav.order":      (["Bovinos", "Bovinos Importados", "Aves", "Suínos", "Pescados", "Batatas e Vegetais",
                        "Cordeiros", "Charques", "Outros", "Promoções", "Marcas"], None, "CONTRATO §Identidade visual", "nav_top_links", "list"),
    "coupon.text":    ("PCFRIBOI5", None, "CONTRATO faixa de cupom", "coupon_text", "contains"),
    "search.ph":      ("Busque aqui seu produto", None, "CONTRATO busca", "search_placeholder", "contains"),
    "login.label":    ("Login ou Cadastre-se", None, "CONTRATO botão", "login_label", "contains"),
    "fonts.roboto":   (True, None, "§6.5 Roboto carregada localmente", "fonts.roboto_loaded_ok", "bool"),
    "fonts.roboto_cond": (True, None, "§6.5 Roboto Condensed carregada localmente", "fonts.roboto_cond_loaded_ok", "bool"),
    "body.font_first": ("Roboto", None, "§2.1 e CAPTURE: body = Roboto primeiro", "body_font.family", "first_family"),
    "footer.payments": (5, 0, "§6.5 5 meios de pagamento", "footer_payments", "len"),
    "footer.safety":   (2, 0, "§6.5 2 selos de segurança", "footer_safety", "len"),
    "footer.socials":  (3, 0, "§6.5 3 redes sociais", "footer_socials", "len"),
}

ORDER_SPEC = ["hero", "categories-strip", "vitrine", "vitrine", "brand-cards", "brand-strip",
              "benefits", "institutional", "site-footer"]


def hexify(css):
    if not isinstance(css, str):
        return css
    m = re.match(r"rgba?\(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", css)
    if not m:
        return css
    r, g, b = (int(round(float(x))) for x in m.groups())
    return f"#{r:02X}{g:02X}{b:02X}"


def grab(root, path):
    cur = root
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def to_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s.endswith("px"):
            s = s[:-2]
        try:
            return float(s)
        except ValueError:
            return None
    return None


def main() -> int:
    med, console, req4xx, pages = {}, {}, {}, {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for item in PAGES:
            name, path, is_home = item[0], item[1], item[2]
            width = item[3] if len(item) > 3 else 1440
            ctx = browser.new_context(viewport={"width": width, "height": 900},
                                      locale="pt-BR", device_scale_factor=1)
            page = ctx.new_page()
            erros, ruins = [], []
            page.on("console", lambda m, e=erros: e.append(f"{m.type}: {m.text}"[:300]) if m.type == "error" else None)
            page.on("pageerror", lambda err, e=erros: e.append(f"pageerror: {err}"[:300]))
            page.on("requestfailed", lambda r, e=ruins: e.append(f"REQUESTFAILED {r.url} :: {r.failure}"))
            page.on("response", lambda r, e=ruins: e.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
            page.goto(BASE + path, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            # placeholder do input de busca (não exposto pela medição genérica)
            ph = page.evaluate("() => { const i=document.querySelector('.site-header form.search input'); "
                               "return i ? (i.placeholder||'') : null; }")
            label = page.evaluate("() => { const a=document.querySelector('.site-header .btn-login'); "
                                  "return a ? a.textContent.replace(/\\s+/g,' ').trim() : null; }")
            page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
            if is_home:
                med = page.evaluate(MEASURE_JS)
                med.setdefault("texts", {})
                med["texts"]["search_placeholder"] = ph
                med["texts"]["login_label"] = label
                page.screenshot(path=str(SHOTS / "home-1440-viewport.png"), full_page=False)
            console[name] = erros
            req4xx[name] = ruins
            pages[name] = {"path": path, "url": page.url, "title": page.title(),
                           "screenshot": f"tests/screenshots/{name}-{width}.png"}
            ctx.close()
        browser.close()

    # ---- comparar com o DESIGN_SPEC ----
    comparacao, divergencias = {}, []
    for key, (esperado, tol, fonte, path, tipo) in SPEC.items():
        bruto = grab(med, path)
        if key == "search.ph":
            bruto = grab(med, "texts.search_placeholder")
        if key == "login.label":
            bruto = grab(med, "texts.login_label")
        if tipo == "num":
            obtido = to_num(bruto)
            status = "SEM_DADO" if obtido is None else ("OK" if abs(obtido - float(esperado)) <= (tol or 0) else "DIVERGE")
        elif tipo == "hex":
            obtido = hexify(bruto)
            status = "SEM_DADO" if obtido is None else ("OK" if str(obtido).upper() == str(esperado).upper() else "DIVERGE")
        elif tipo == "str":
            obtido = str(bruto) if bruto is not None else None
            status = "SEM_DADO" if obtido is None else ("OK" if obtido == str(esperado) else "DIVERGE")
        elif tipo == "bool":
            obtido = bool(bruto)
            status = "OK" if obtido == bool(esperado) else "DIVERGE"
        elif tipo == "absent":
            obtido = bruto
            status = "OK" if not bruto else "DIVERGE"
        elif tipo == "len":
            obtido = len(bruto) if isinstance(bruto, list) else None
            status = "SEM_DADO" if obtido is None else ("OK" if int(obtido) == int(esperado) else "DIVERGE")
        elif tipo == "first_family":
            fam = str(bruto or "").split(",")[0].strip().strip("'\"")
            obtido = fam or None
            status = "SEM_DADO" if not fam else ("OK" if fam.lower() == str(esperado).lower() else "DIVERGE")
        elif tipo == "list":
            obtido = bruto or []
            status = "OK" if [str(x) for x in obtido] == [str(x) for x in esperado] else ("SEM_DADO" if not obtido else "DIVERGE")
        else:  # contains
            obtido = bruto
            status = "SEM_DADO" if not obtido else ("OK" if str(esperado).lower() in str(obtido).lower() else "DIVERGE")
        comparacao[key] = {"esperado": esperado, "obtido": obtido, "tol": tol, "status": status,
                           "fonte": fonte, "caminho": path}
        if status != "OK":
            divergencias.append({"item": key, "esperado": esperado, "obtido": obtido,
                                 "status": status, "fonte": fonte})

    ordem_obtida = [s["cls"].split()[0] for s in med.get("sections", [])]
    ordem_ok = ordem_obtida == ORDER_SPEC
    comparacao["section.order"] = {"esperado": ORDER_SPEC, "obtido": ordem_obtida, "tol": None,
                                   "status": "OK" if ordem_ok else "DIVERGE",
                                   "fonte": "§6.5 ordem das seções", "caminho": "sections"}
    if not ordem_ok:
        divergencias.append({"item": "section.order", "esperado": ORDER_SPEC, "obtido": ordem_obtida,
                             "status": "DIVERGE", "fonte": "§6.5 ordem das seções"})

    # ---- geometria vertical/estrutural contra a CAPTURA real (docs/CAPTURE/styles-home-1440.json) ----
    # valores lidos por getBoundingClientRect na captura do site original em 1440px
    REF_GEOM = [
        ("ref.dots_y",     472, "hero_dots.0.y",        "bolinhas do hero a y=472 na captura"),
        ("ref.cattile_y",  535, "cat_icon_box.y",       ".icon-box das categorias a y=535 na captura"),
        ("ref.card_y",     741, "product_card.y",       "primeiro .product-card a y=741 na captura"),
        ("ref.card_h",     271, "product_card.h",       ".product-card 255×271 na captura"),
        ("ref.arrow_y",    866, "carousel_arrow.y",     "seta do carrossel a y=866 na captura"),
        ("ref.shelf_title_y", None, "vitrine_title.y",  "título da vitrine (referência visual)"),
        ("ref.search_input_w", 565, "search_input.w",   "input de busca 565 px"),
        ("ref.search_btn_w",   67, "search_btn.w",      "botão da lupa 67 px"),
    ]
    for key, ref, path, fonte in REF_GEOM:
        if ref is None:
            continue
        obtido = to_num(grab(med, path))
        tol = 6 if key.endswith("_w") or key == "ref.card_h" else 15
        status = "SEM_DADO" if obtido is None else ("OK" if abs(obtido - ref) <= tol else "DIVERGE")
        comparacao[key] = {"esperado": ref, "obtido": obtido, "tol": tol, "status": status,
                           "fonte": fonte, "caminho": path}
        if status != "OK":
            divergencias.append({"item": key, "esperado": ref, "obtido": obtido,
                                 "status": status, "fonte": fonte})

    # ---- referência textual da captura: nav tem 11 itens, 9 categorias, 4 benefícios ----
    if med.get("doc", {}).get("horizontal_overflow"):
        divergencias.append({"item": "layout.horizontal_overflow", "esperado": False,
                             "obtido": med["doc"], "status": "DIVERGE", "fonte": "layout"})
    if med.get("broken_images"):
        divergencias.append({"item": "images.broken", "esperado": [], "obtido": med["broken_images"],
                             "status": "DIVERGE", "fonte": "assets"})

    res = {"base": BASE, "quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "paginas": pages,
           "medicoes": med, "comparacao": comparacao, "divergencias": divergencias,
           "console_errors": console, "requisicoes_4xx": req4xx}
    (ARTI / "visual.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = sum(1 for v in comparacao.values() if v["status"] == "OK")
    div = sum(1 for v in comparacao.values() if v["status"] == "DIVERGE")
    sem = sum(1 for v in comparacao.values() if v["status"] == "SEM_DADO")
    print(f"\n== comparação DESIGN_SPEC: {ok}/{len(comparacao)} OK, {div} divergem, {sem} sem dado")
    for k, v in comparacao.items():
        esp = str(v["esperado"])[:70]
        obt = str(v["obtido"])[:70]
        print(f"  [{v['status']:8s}] {k:20s} spec={esp:70s} obtido={obt}")
    print("\n== seções (ordem/altura):", [(s['cls'].split()[0], s['h']) for s in med.get('sections', [])])
    print("== doc:", med.get("doc"))
    print("== fontes carregadas:", med.get("fonts", {}).get("roboto_loaded_ok"),
          med.get("fonts", {}).get("roboto_cond_loaded_ok"), "| body:", med.get("body_font", {}).get("family"))
    print("== erros de console:", {k: v for k, v in console.items() if v} or "nenhum")
    print("== requests >=400:", {k: v for k, v in req4xx.items() if v} or "nenhum")
    print("== screenshots em tests/screenshots/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
