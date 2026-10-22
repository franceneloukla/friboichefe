#!/usr/bin/env python3
"""Checks 3 (páginas) e 4 (assets locais) da verificação E2E do Friboi Online.

Uso:
    ./.venv/bin/python tests/pages_assets.py [BASE_URL]

Evidências em tests/artifacts/pages_assets.log e pages_assets.json.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTI = ROOT / "tests" / "artifacts"
ARTI.mkdir(parents=True, exist_ok=True)
DB = Path(os.environ["DB_PATH"]) if os.environ.get("DB_PATH") else ROOT / "data" / "store.db"
_DB_REAL = ROOT / "data" / "store.db"
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8199").rstrip("/")

LOG: list[str] = []
RESULTS: list[dict] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    LOG.append(msg)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Não segue redirect: devolve o 3xx e o Location (necessário para o check do /conta)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class Client:
    def __init__(self, follow: bool = True):
        self.jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow:
            handlers.append(_NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def get(self, path: str, follow=True):
        url = path if path.startswith("http") else BASE + path
        req = urllib.request.Request(url, headers={"User-Agent": "T5-verificador/1.0",
                                                  "Accept": "*/*"})
        try:
            with self.opener.open(req, timeout=40) as r:
                return r.status, dict(r.headers), r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read(), url
        except urllib.error.URLError as e:
            return 0, {}, f"ERRO DE REDE: {e}".encode(), url


def record(check: str, title: str, ok: bool, expected: str, got: str, evidence: str = "") -> None:
    RESULTS.append({"check": check, "title": title, "ok": bool(ok),
                    "expected": expected, "got": got, "evidence": evidence})
    log(f"  [{'OK ' if ok else 'FALHOU'}] {check} {title}")
    log(f"          esperado: {expected}")
    log(f"          obtido:   {got}")
    if evidence:
        for line in evidence.rstrip().splitlines()[:10]:
            log(f"          | {line}")


def parse_html(text: str) -> str:
    return text


# ---------------------------------------------------------------------------
# CHECK 3 — páginas
# ---------------------------------------------------------------------------
ERROS = [
    "Traceback (most recent call last)",
    "Internal Server Error",
    "jinja2.exceptions",
    "TemplateNotFound",
    "UndefinedError",
    "TemplateSyntaxError",
    "werkzeug",
]


def check_pages(cli: Client) -> dict:
    log("\n=== CHECK 3 — PÁGINAS ===")
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    prod = c.execute("select slug from products where image_path is not null order by id limit 1").fetchone()["slug"]
    cat = c.execute("select slug from categories where id='BOVINOS'").fetchone()
    cat_slug = cat["slug"] if cat else "bovinos"
    c.close()

    paginas = [
        ("3a", "/", 200),
        ("3b", f"/categoria/{cat_slug}", 200),
        ("3c", f"/produto/{prod}", 200),
        ("3d", "/login", 200),
        ("3e", "/cadastro", 200),
        ("3f", "/carrinho", 200),
        ("3g", "/checkout", (200, 303, 302, 307)),
        ("3h", "/promocoes", 200),
        ("3i", "/busca?q=acem", 200),
        ("3j", "/conta", (302, 303, 307)),        # deslogado deve redirecionar
        ("3k", "/nao-existe-" + uuid.uuid4().hex[:6], 404),
    ]
    status_map = {}
    for check, path, esperado in paginas:
        # /conta precisa de um cliente que NÃO siga o redirect, senão a evidência
        # do 3xx se perde (o handler devolve 303 para /login?next=/conta).
        cli_pg = Client(follow=False) if path.startswith("/conta") else cli
        st, hdrs, body, final = cli_pg.get(path)
        status_map[path] = st
        html = body.decode("utf-8", "replace")
        achados = [e for e in ERROS if e in html]
        esperado_ok = st in esperado if isinstance(esperado, tuple) else st == esperado
        redir = hdrs.get("location") or hdrs.get("Location") or ""
        ok = esperado_ok and not achados
        record(check, f"GET {path} -> {esperado if not isinstance(esperado, tuple) else '/'.join(map(str, esperado))}",
               ok,
               f"{esperado}", f"{st}" + (f" -> {redir}" if redir else "") + (f" ERRO:{achados}" if achados else ""),
               f"bytes={len(body)}" + (f", redirect Location={redir}" if redir else "") +
               (f", markers={achados}" if achados else ", sem traceback/500"))

    # conteúdo mínimo esperado nas páginas principais
    st, _, body, _ = cli.get("/")
    html = body.decode("utf-8", "replace")
    secoes = {
        "header/logo": "friboi" in html.lower(),
        "busca 'Busque aqui seu produto'": bool(re.search(r"Busque aqui seu produto", html, re.I)),
        "botão Login ou Cadastre-se": bool(re.search(r"Login ou Cadastre-se", html, re.I)),
        "nav Bovinos": "Bovinos" in html,
        "faixa de cupom PCFRIBOI5": "PCFRIBOI5" in html,
        "hero/carrossel": bool(re.search(r"(hero|carousel|carrossel|banner)", html, re.I)),
        "grid de categorias": bool(re.search(r"categor", html, re.I)),
        "vitrine": bool(re.search(r"(vitrine|Neg[oó]cios Como|Sugest[ãa]o)", html, re.I)),
        "cards de marca COMPRE AGORA": bool(re.search(r"COMPRE AGORA", html, re.I)),
        "4 benefícios": bool(re.search(r"(Benef|benef[ií]cio)", html, re.I)),
        "footer copyright": bool(re.search(r"(©|&copy;)", html)),
        "preço R$": "R$" in html,
    }
    faltando = [k for k, v in secoes.items() if not v]
    record("3l", "home tem as 12 seções/elementos do original", not faltando,
           "todos presentes (espelho do checklist §6.5)",
           f"{len(secoes) - len(faltando)}/{len(secoes)} presentes" + (f"; faltando: {faltando}" if faltando else ""),
           "checklist: " + ", ".join(f"{k}={'ok' if v else 'FALTA'}" for k, v in secoes.items()))

    # PDP: partes obrigatórias do CONTRATO
    st, _, body, _ = cli.get(f"/produto/{prod}")
    h = body.decode("utf-8", "replace")
    partes = {
        "breadcrumb": bool(re.search(r"(breadcrumb|Breadcrumb|›|&gt;)", h)),
        "preço": "R$" in h,
        "unidade KG": bool(re.search(r"\bKG\b", h)),
        "estoque": bool(re.search(r"(Dispon[ií]vel|Indispon[ií]vel|estoque)", h, re.I)),
        "quantidade": bool(re.search(r"(quantidade|qty)", h, re.I)),
        "adicionar ao carrinho": bool(re.search(r"(carrinho)", h, re.I)),
        "descrição": bool(re.search(r"(Descri|descri)", h, re.I)),
        "nutri": bool(re.search(r"(nutri|Nutri)", h, re.I)),
        "relacionados": bool(re.search(r"(relacionad|Relacionad|Tamb[eé]m)", h)),
    }
    faltando = [k for k, v in partes.items() if not v]
    record("3m", "PDP tem as 9 partes exigidas pelo CONTRATO", not faltando,
           "todas", f"{len(partes)-len(faltando)}/{len(partes)}" + (f"; faltando: {faltando}" if faltando else ""),
           ", ".join(f"{k}={'ok' if v else 'FALTA'}" for k, v in partes.items()))

    # /conta logado deve ser 200
    reg = Client()
    email = f"t5.paginas.{uuid.uuid4().hex[:8]}@teste.local"
    reg.opener.open(urllib.request.Request(
        BASE + "/api/auth/register",
        data=json.dumps({"name": "Páginas T5", "email": email, "password": "Paginas#123"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST"), timeout=30).read()
    st, _, body, _ = reg.get("/conta")
    record("3n", "GET /conta LOGADO -> 200 com dados do usuário",
           st == 200 and email in body.decode("utf-8", "replace"),
           "200 com e-mail na página", f"{st} ({'e-mail presente' if email in body.decode('utf-8','replace') else 'e-mail AUSENTE'})")

    return {"prod_slug": prod, "cat_slug": cat_slug, "email": email}


# ---------------------------------------------------------------------------
# CHECK 4 — assets 100% locais
# ---------------------------------------------------------------------------
ATTR_RE = re.compile(r"""(?:src|href|data-src|poster)\s*=\s*["']([^"']+)["']""", re.I)
SRCSET_RE = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.I)
CSSURL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
SOCIAL = ("instagram.com", "facebook.com", "youtube.com", "wa.me", "whatsapp.com",
          "linkedin.com", "twitter.com", "x.com", "tiktok.com")


def is_asset(path: str) -> bool:
    if path.startswith(("/assets/", "/static/", "/img/products/", "/favicon")):
        return True
    return bool(re.search(r"\.(png|jpe?g|webp|gif|svg|ico|css|js|woff2?|ttf|eot|avif)(\?|$)", path, re.I))


def check_assets(cli: Client, ctx: dict) -> None:
    log("\n=== CHECK 4 — ASSETS 100% LOCAIS ===")
    alvos = ["/", f"/produto/{ctx['prod_slug']}", f"/categoria/{ctx['cat_slug']}", "/carrinho", "/login"]
    externos: dict[str, list[str]] = {}
    locais: set[str] = set()
    data_uris = 0
    bad_uris: list[str] = []

    for page in alvos:
        st, _, body, _ = cli.get(page)
        html = body.decode("utf-8", "replace")
        refs = ATTR_RE.findall(html)
        for srcset in SRCSET_RE.findall(html):
            for part in srcset.split(","):
                refs.append(part.strip().split(" ")[0])
        for ref in refs:
            ref = ref.strip()
            if not ref or ref.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            if ref.startswith("data:"):
                data_uris += 1
                continue
            if ref.startswith(("http://", "https://", "//")):
                host = urllib.parse.urlparse(ref if not ref.startswith("//") else "https:" + ref).netloc.lower()
                externos.setdefault(host, []).append(page)
                continue
            if ref.startswith("/"):
                if is_asset(ref):
                    locais.add(ref.split("#")[0])
            else:
                bad_uris.append((page, ref))

    # CSS: url() absolutos/relativos e imports
    css_ext: list[tuple[str, str]] = []
    css_locais: set[str] = set()
    for css in sorted(locais):
        if not css.endswith(".css"):
            continue
        st, _, body, _ = cli.get(css)
        if st != 200:
            continue
        txt = body.decode("utf-8", "replace")
        for u in CSSURL_RE.findall(txt) + re.findall(r"@import\s+['\"]([^'\"]+)", txt):
            if u.startswith("data:"):
                continue
            if u.startswith(("http://", "https://", "//")):
                css_ext.append((css, u))
            elif u.startswith("/"):
                css_locais.add(u.split("?")[0].split("#")[0])

    hosts_obrigatorios = {h: p for h, p in externos.items() if not any(s in h for s in SOCIAL)}
    record("4a", "nenhum asset (img/css/js/fonte) aponta para domínio externo", not hosts_obrigatorios,
           "0 hosts externos", f"{len(hosts_obrigatorios)} host(s) externo(s) obrigatório(s)" +
           (f": {sorted(hosts_obrigatorios)}" if hosts_obrigatorios else ""),
           f"externos encontrados (todos): {json.dumps({k: len(v) for k, v in externos.items()}, ensure_ascii=False)}; "
           f"data: URIs={data_uris}; refs relativas inválidas={len(bad_uris)}")
    record("4b", "CSS não importa fonte/asset externo (sem fonts.googleapis/gstatic)",
           not css_ext, "0 url() externo em CSS",
           f"{len(css_ext)} url() externo(s)" + (f": {css_ext[:5]}" if css_ext else ""))
    record("4c", "refs relativas inválidas (sem '/') = 0", not bad_uris, "0", f"{len(bad_uris)}",
           json.dumps(bad_uris[:8], ensure_ascii=False) if bad_uris else "todas as refs de asset são absolutas (/assets, /static, /img/products)")

    # amostra: hosts sociais (permitidos no footer)
    if externos:
        log(f"          (informativo) hosts externos no HTML: { {k: len(v) for k, v in externos.items()} }")

    # baixar todos os assets locais
    todos = sorted(locais | css_locais)
    log(f"\n  baixando {len(todos)} assets locais únicos …")
    faltando, vazios, ok_count, bytes_total = [], [], 0, 0
    for path in todos:
        st, hdrs, body, _ = cli.get(path)
        if st != 200:
            faltando.append((path, st))
            continue
        if len(body) == 0:
            vazios.append(path)
            continue
        ok_count += 1
        bytes_total += len(body)
    record("4d", "todo asset local referenciado responde 200 e bytes > 0",
           not faltando and not vazios,
           f"{len(todos)}/{len(todos)} OK",
           f"{ok_count}/{len(todos)} OK, {len(faltando)} com erro HTTP, {len(vazios)} vazios",
           (f"404/erro: {faltando[:10]}" if faltando else "") +
           f"\nbytes totais baixados: {bytes_total/1024:.1f} KiB; exemplos: " + ", ".join(todos[:6]))

    # checagem específica das imagens de produto da home
    st, _, body, _ = cli.get("/")
    imgs = re.findall(r'src=["\'](/img/products/[^"\']+)["\']', body.decode("utf-8", "replace"))
    quebradas = []
    for p in sorted(set(imgs)):
        s, _, b, _ = cli.get(p)
        if s != 200 or len(b) < 100:
            quebradas.append((p, s, len(b)))
    record("4e", "imagens de produto da home servem 200 com conteúdo real",
           not quebradas, f"{len(set(imgs))} imagens, 0 quebradas",
           f"{len(set(imgs))} únicas, {len(quebradas)} quebradas",
           json.dumps(quebradas[:5]) if quebradas else f"ex.: {sorted(set(imgs))[:3]}")

    # fontes locais declaradas no CSS existem de fato
    st, _, body, _ = cli.get("/static/css/app.css")
    fontes = sorted(set(re.findall(r"url\(['\"]?(/assets/fonts/[^'\")]+)", body.decode("utf-8", "replace"))))
    f404 = []
    for f in fontes:
        s, _, b, _ = cli.get(f)
        if s != 200 or len(b) < 1000:
            f404.append((f, s, len(b)))
    record("4f", f"@font-face locais em /assets/fonts servem 200 ({len(fontes)} declaradas)",
           bool(fontes) and not f404, "todas 200 com bytes > 1000",
           f"{len(fontes) - len(f404)}/{len(fontes)} OK",
           json.dumps(f404[:5]) if f404 else ", ".join(fontes[:6]))


def main() -> int:
    log(f"BASE_URL = {BASE}")
    log(f"início: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    cli = Client()
    ctx = check_pages(cli)
    check_assets(cli, ctx)

    total = len(RESULTS)
    falhas = [r for r in RESULTS if not r["ok"]]
    log("\n" + "=" * 70)
    log(f"RESUMO: {total - len(falhas)}/{total} OK, {len(falhas)} FALHOU")
    for f in falhas:
        log(f"  FALHOU {f['check']} {f['title']} -> {f['got']}")
    (ARTI / "pages_assets.log").write_text("\n".join(LOG), encoding="utf-8")
    (ARTI / "pages_assets.json").write_text(json.dumps(
        {"base": BASE, "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "ok": total - len(falhas), "total": total, "falhas": len(falhas),
         "ctx": ctx, "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
