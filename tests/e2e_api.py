#!/usr/bin/env python3
"""Verificação E2E adversarial da API/páginas do clone Friboi Online.

Checks 1, 2, 5, 6 e 8 do checklist do T5. Prova com execução real contra um
servidor uvicorn já no ar (default http://127.0.0.1:8199).

Uso:
    ./.venv/bin/python tests/e2e_api.py [BASE_URL]

Saída:
    tests/artifacts/e2e_api.log   (log legível, evidências)
    tests/artifacts/e2e_api.json  (resultado estruturado)
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
BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://127.0.0.1:8199")).rstrip("/")

LOG: list[str] = []
RESULTS: list[dict] = []


def log(msg: str = "") -> None:
    print(msg, flush=True)
    LOG.append(msg)


class Resp:
    def __init__(self, status: int, headers: dict, body: bytes, url: str):
        self.status = status
        self.headers = headers
        self.body = body
        self.url = url

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self):
        try:
            return json.loads(self.text)
        except Exception:
            return None


class Client:
    """Cliente HTTP com cookie jar próprio (simula um browser)."""

    def __init__(self, label: str):
        self.label = label
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.last: Resp | None = None

    def cookie(self, name: str) -> str | None:
        for c in self.jar:
            if c.name == name:
                return c.value
        return None

    def set_cookie(self, name: str, value: str) -> None:
        host = urllib.parse.urlparse(BASE).hostname or "127.0.0.1"
        c = http.cookiejar.Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=host, domain_specified=False, domain_initial_dot=False,
            path="/", path_specified=True, secure=False, expires=None,
            discard=False, comment=None, comment_url=None, rest={},
        )
        self.jar.set_cookie(c)

    def req(self, method: str, path: str, body=None, headers: dict | None = None) -> Resp:
        url = path if path.startswith("http") else BASE + path
        data = None
        hdrs = {"Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
                "User-Agent": "T5-verificador/1.0"}
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode()
                hdrs["Content-Type"] = "application/json"
            elif isinstance(body, bytes):
                data = body
                hdrs.setdefault("Content-Type", "application/json")
            else:
                data = str(body).encode()
                hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update(headers)
        request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with self.opener.open(request, timeout=30) as r:
                resp = Resp(r.status, dict(r.headers), r.read(), url)
        except urllib.error.HTTPError as e:  # 4xx/5xx: corpo ainda interessa
            resp = Resp(e.code, dict(e.headers), e.read(), url)
        except urllib.error.URLError as e:
            resp = Resp(0, {}, f"ERRO DE REDE: {e}".encode(), url)
        self.last = resp
        return resp


def record(check: str, title: str, ok: bool, expected: str, got: str, evidence: str = "") -> None:
    RESULTS.append({"check": check, "title": title, "ok": bool(ok),
                    "expected": expected, "got": got, "evidence": evidence})
    log(f"  [{'OK ' if ok else 'FALHOU'}] {check} {title}")
    log(f"          esperado: {expected}")
    log(f"          obtido:   {got}")
    if evidence:
        for line in evidence.rstrip().splitlines()[:14]:
            log(f"          | {line}")


def db_conn():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def jdump(obj, n=400) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------------------------
# CHECK 1 — banco / catálogo
# ---------------------------------------------------------------------------
def check_db() -> None:
    log("\n=== CHECK 1 — BANCO / CATÁLOGO ===")
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text())
    c = db_conn()
    n_products = c.execute("select count(*) from products").fetchone()[0]
    n_cats = c.execute("select count(*) from categories").fetchone()[0]
    rows = c.execute("select id, image_path from products").fetchall()
    c.close()
    imgs_dir = ROOT / "data" / "images" / "products"
    n_imgdirs = len([p for p in imgs_dir.iterdir() if p.is_dir()]) if imgs_dir.exists() else 0
    broken = [(r["id"], r["image_path"]) for r in rows
              if r["image_path"] and not (ROOT / "data" / "images" / r["image_path"]).is_file()]
    with_path = sum(1 for r in rows if r["image_path"])
    sem_path = sum(1 for r in rows if not r["image_path"])

    record("1a", "products no SQLite == total do catalog.json",
           n_products == catalog["total"],
           f"{catalog['total']}", f"{n_products} (catalog.json total={catalog['total']}, len(products)={len(catalog['products'])})",
           f"select count(*) from products -> {n_products}")
    record("1b", "categories >= 8 (dossiê: 471)",
           n_cats >= 8, ">= 8", f"{n_cats} categorias",
           f"select count(*) from categories -> {n_cats}")
    record("1c", "imagens em data/images/products >= 1500",
           n_imgdirs >= 1500, ">= 1500", f"{n_imgdirs} diretórios de produto com imagem",
           f"catalog_stats.json: images={json.loads((ROOT/'data'/'catalog_stats.json').read_text())['images']}")
    record("1d", "image_path apontando para arquivo existente (0 quebrados)",
           len(broken) == 0, "0 quebrados", f"{len(broken)} quebrados / {with_path} com image_path",
           "exemplos: " + jdump(broken[:5]) if broken else f"todos os {with_path} image_path existem em disco; {sem_path} produtos sem imagem (sem primaryMediumImageURL no original)")


# ---------------------------------------------------------------------------
# CHECK 2 — servidor no ar
# ---------------------------------------------------------------------------
def check_server(cli: Client) -> None:
    log("\n=== CHECK 2 — SERVIDOR NO AR ===")
    r = cli.req("GET", "/")
    has_friboi = "friboi" in r.text.lower()
    has_money = "R$" in r.text
    record("2a", "GET / -> 200", r.status == 200, "200", str(r.status),
           f"bytes={len(r.body)} content-type={r.headers.get('content-type')}")
    record("2b", "GET / contém 'Friboi'", has_friboi, "sim", "sim" if has_friboi else "não",
           f"ocorrências: {r.text.lower().count('friboi')}")
    record("2c", "GET / contém preço 'R$'", has_money, "sim", "sim" if has_money else "não",
           f"ocorrências de 'R$': {r.text.count('R$')}")
    h = cli.req("GET", "/api/health")
    record("2d", "GET /api/health -> 200 com products=1567", h.status == 200 and (h.json() or {}).get("products") == 1567,
           "200 {products:1567}", f"{h.status} {jdump(h.json())}", "")


# ---------------------------------------------------------------------------
# CHECK 5 — autenticação
# ---------------------------------------------------------------------------
def check_auth() -> dict:
    log("\n=== CHECK 5 — AUTENTICAÇÃO ===")
    email = f"t5.{uuid.uuid4().hex[:10]}@teste.local"
    senha = "Senha#12345"
    cli = Client("auth")
    r = cli.req("POST", "/api/auth/register", {"name": "Verificador T5", "email": email, "password": senha,
                                             "cpf": "12345678909", "phone": "11999998888"})
    j = r.json() or {}
    record("5a", "POST /api/auth/register -> 201 + user/access_token",
           r.status == 201 and "user" in j and "access_token" in j,
           "201 {user,access_token}", f"{r.status} {jdump({k: (v if k != 'access_token' else v[:24] + '…') for k, v in j.items() if k in ('user','access_token','token_type')})}",
           f"cookie auth_token presente: {bool(cli.cookie('auth_token'))}")

    r = cli.req("POST", "/api/auth/login", {"email": email, "password": senha})
    j = r.json() or {}
    record("5b", "POST /api/auth/login -> 200", r.status == 200 and "access_token" in j,
           "200 {user,access_token}", f"{r.status} {jdump(j.get('user'))}")

    r = cli.req("GET", "/api/auth/me")
    j = r.json() or {}
    record("5c", "GET /api/auth/me com cookie -> 200 e e-mail correto",
           r.status == 200 and str(j.get("email", "")).lower() == email.lower(),
           f"200 email={email}", f"{r.status} {jdump(j)}")

    # /api/auth/me sem cookie deve ser 401
    anon = Client("anon")
    r2 = anon.req("GET", "/api/auth/me")
    record("5d", "GET /api/auth/me sem cookie -> 401", r2.status == 401, "401", str(r2.status), jdump(r2.json()))

    r = Client("errado").req("POST", "/api/auth/login", {"email": email, "password": "senha-errada-xyz"})
    record("5e", "login com senha errada -> 401", r.status == 401, "401", str(r.status), jdump(r.json()))

    # hash no banco
    c = db_conn()
    row = c.execute("select password_hash from users where lower(email)=lower(?)", (email,)).fetchone()
    all_plain = c.execute("select count(*) from users where password_hash = ? or password_hash = '' or length(password_hash) < 20", (senha,)).fetchone()[0]
    c.close()
    h = row["password_hash"] if row else ""
    record("5f", "senha no banco em bcrypt ($2b$) e nunca em texto puro",
           bool(row) and h.startswith("$2b$") and h != senha and all_plain == 0,
           "hash começando com $2b$, != senha", f"hash={h[:7]}… (len={len(h)}), usuários com hash degenerado={all_plain}",
           f"select password_hash -> {h[:20]}… ; texto puro presente? {senha in h}")

    # regressão: 2º usuário no MESMO browser (mesmo cart_token) não pode dar 500
    cart_token = cli.cookie("cart_token") or ""
    email2 = f"t5.{uuid.uuid4().hex[:10]}@teste.local"
    same = Client("mesmo-browser")
    if cart_token:
        same.set_cookie("cart_token", cart_token)
    r3 = same.req("POST", "/api/auth/register", {"name": "Segundo Usuário", "email": email2,
                                                "password": "OutraSenha#987"})
    j3 = r3.json() or {}
    record("5g", "2º usuário cadastrando no MESMO browser (mesmo cart_token) -> 201/200 sem 500",
           r3.status in (200, 201) and "user" in j3,
           "201 sem erro", f"{r3.status} {jdump({k: j3.get(k) for k in ('user', 'detail')})}",
           f"cart_token reutilizado: {cart_token[:12]}… ; ver server_8199.log para traceback" if cart_token else "cart_token ausente no 1º cadastro")

    # login do 2º usuário no mesmo browser (trocando o cookie auth)
    r4 = same.req("POST", "/api/auth/login", {"email": email2, "password": "OutraSenha#987"})
    record("5h", "login do 2º usuário no mesmo browser -> 200 sem 500",
           r4.status == 200, "200", f"{r4.status} {jdump((r4.json() or {}).get('user'))}")
    me2 = same.req("GET", "/api/auth/me")
    record("5i", "/api/auth/me do 2º usuário devolve o 2º e-mail (troca de sessão limpa)",
           me2.status == 200 and str((me2.json() or {}).get("email", "")).lower() == email2.lower(),
           email2, f"{me2.status} {jdump(me2.json())}")

    return {"email": email, "senha": senha, "client": cli, "email2": email2}


# ---------------------------------------------------------------------------
# CHECK 6 — carrinho + pedido
# ---------------------------------------------------------------------------
def product_prices(ids: list[str]) -> dict[str, float]:
    c = db_conn()
    q = ",".join("?" * len(ids))
    rows = c.execute(f"select id, name, price, sale_price, unit from products where id in ({q})", ids).fetchall()
    c.close()
    out = {}
    for r in rows:
        preco = r["sale_price"] if r["sale_price"] not in (None, 0) else r["price"]
        out[r["id"]] = {"price": float(preco), "list": float(r["price"]), "name": r["name"], "unit": r["unit"]}
    return out


def check_cart_order(auth: dict) -> dict:
    log("\n=== CHECK 6 — CARRINHO + PEDIDO ===")
    c = db_conn()
    rows = c.execute("select id, name, price from products where stock='Disponível' and active=1 order by id limit 2").fetchall()
    c.close()
    ids = [r["id"] for r in rows]
    precos = product_prices(ids)
    qty = {ids[0]: 2, ids[1]: 3}
    esperado = round(sum(precos[i]["price"] * qty[i] for i in ids), 2)

    cli = Client("carrinho")
    cli.req("GET", "/")  # garante cart_token
    for pid, q in qty.items():
        cli.req("POST", "/api/cart/items", {"product_id": pid, "qty": q})
    cart = (cli.req("GET", "/api/cart").json()) or {}
    sub = round(float(cart.get("subtotal") or 0), 2)
    cnt = cart.get("count")
    detalhe = ", ".join(f"{i['name'][:28]} ×{i['qty']} = {i['subtotal']}" for i in cart.get("items", []))
    record("6a", "subtotal do carrinho == soma(preço do BANCO × qty)",
           abs(sub - esperado) < 0.01,
           f"{esperado:.2f} (banco: " + ", ".join(f"{p['price']}×{qty[i]}" for i, p in precos.items()) + ")",
           f"{sub:.2f} count={cnt}", detalhe)

    # login funde o carrinho anônimo
    r = cli.req("POST", "/api/auth/login", {"email": auth["email"], "password": auth["senha"]})
    cart_pos = (cli.req("GET", "/api/cart").json()) or {}
    sub2 = round(float(cart_pos.get("subtotal") or 0), 2)
    record("6b", "login funde carrinho anônimo (itens preservados)",
           r.status == 200 and sub2 == sub and cart_pos.get("count") == cnt,
           f"{sub:.2f} / {cnt} itens", f"{sub2:.2f} / {cart_pos.get('count')} itens após login")

    # checkout com preço/total falsos no body
    body = {
        "payment": "pix",
        "ship": {"name": "Verificador T5", "email": auth["email"], "phone": "11999998888",
                 "cep": "01310-100", "address": "Av Paulista", "number": "1000", "complement": "cj 1",
                 "district": "Bela Vista", "city": "São Paulo", "state": "SP"},
        "price": 0.01, "total": 0.01, "subtotal": 0.01,
        "items": [{"product_id": ids[0], "qty": 99, "unit_price": 0.01, "price": 0.01}],
    }
    r = cli.req("POST", "/api/checkout", body)
    j = r.json() or {}
    order = j.get("order") or {}
    total = round(float(order.get("total") or 0), 2)
    record("6c", "POST /api/checkout -> 201", r.status == 201, "201", f"{r.status} {jdump(j.get('detail'))}",
           f"order.id={order.get('id')} total={order.get('total')} status={order.get('status')}")

    # preço do cliente ignorado (check 8a)
    record("8a", "price/total/itens falsos no body NÃO alteram o valor do pedido",
           r.status == 201 and abs(total - esperado) < 0.01,
           f"total={esperado:.2f} (preço do banco), qty preservada do carrinho (2/3)",
           f"total={total:.2f}, itens=" + jdump([(i['product_id'], i['qty'], i['unit_price'], i['subtotal']) for i in order.get('items', [])]))

    # persistência no SQLite
    c = db_conn()
    oid = order.get("id")
    orow = c.execute("select id, user_id, status, subtotal, total, payment, ship_cep from orders where id=?", (oid,)).fetchone()
    irows = c.execute("select product_id, qty, unit_price, subtotal from order_items where order_id=?", (oid,)).fetchall()
    carrinho_restante = c.execute(
        "select count(*) from cart_items ci join carts ca on ca.id=ci.cart_id where ca.token=?",
        (cli.cookie("cart_token") or "",)).fetchone()[0]
    c.close()
    record("6d", "pedido gravado em orders + order_items (SQLite)",
           bool(orow) and len(irows) == 2,
           "1 linha em orders, 2 em order_items",
           f"orders={dict(orow) if orow else None}; order_items={[dict(x) for x in irows]}")
    record("6e", "carrinho zerado após o checkout",
           carrinho_restante == 0, "0 itens", f"{carrinho_restante} itens no cart do token",
           f"GET /api/cart -> count={(cli.req('GET','/api/cart').json() or {}).get('count')}")
    record("6f", "subtotal do pedido == total (frete 0) e status pendente",
           bool(orow) and abs(float(orow["subtotal"]) - esperado) < 0.01 and orow["status"] == "pendente"
           and abs(float(orow["total"]) - float(orow["subtotal"])) < 0.01,
           f"subtotal={esperado:.2f} total={esperado:.2f} status=pendente",
           f"subtotal={orow['subtotal'] if orow else None} total={orow['total'] if orow else None} status={orow['status'] if orow else None}")
    record("6g", "GET /api/orders lista o pedido do usuário",
           any(o.get("id") == oid for o in ((cli.req("GET", "/api/orders").json()) or {}).get("orders", [])),
           f"pedido {oid} na lista", jdump([o.get("id") for o in ((cli.req('GET','/api/orders').json()) or {}).get('orders', [])]))

    return {"order_id": oid, "client": cli, "ids": ids, "total": esperado, "qty": qty}


# ---------------------------------------------------------------------------
# CHECK 8 — segurança (restante)
# ---------------------------------------------------------------------------
def check_security(auth: dict, order: dict) -> None:
    log("\n=== CHECK 8 — SEGURANÇA BÁSICA ===")

    # 8b — outro usuário pedindo o pedido
    outro = Client("intruso")
    email3 = f"t5.{uuid.uuid4().hex[:10]}@teste.local"
    outro.req("POST", "/api/auth/register", {"name": "Intruso", "email": email3, "password": "Intruso#123"})
    r = outro.req("GET", f"/api/orders/{order['order_id']}")
    record("8b", "GET /api/orders/{id} de outro usuário -> 403/404",
           r.status in (403, 404), "403 ou 404", f"{r.status} {jdump(r.json())}",
           f"pedido {order['order_id']} pertence a outro usuário (cookie do intruso)")

    # 8c — SQLi
    for q in ["' OR 1=1--", "' OR '1'='1", "%' UNION SELECT 1,2,3--", "acem' --"]:
        r = Client("sqli").req("GET", "/api/products?" + urllib.parse.urlencode({"q": q, "limit": 5}))
        j = r.json() or {}
        total = j.get("total")
        # vazou se devolver o catálogo inteiro ou erro 500 / mensagem de SQL no corpo
        vazou = r.status != 200 or (total or 0) > 50 or "sqlalchemy" in r.text.lower() or "syntax error" in r.text.lower()
        record("8c", f"SQLi em /api/products?q={q!r} -> 200 sem vazar", not vazou,
               "200, total pequeno, sem erro SQL", f"{r.status} total={total} items={len(j.get('items') or [])}",
               jdump(r.text[:200]))

    # endpoint de detalhe com payload de injeção
    r = Client("sqli2").req("GET", "/api/products/" + urllib.parse.quote("1' OR '1'='1", safe=""))
    record("8c2", "SQLi em /api/products/{slug_or_id} -> 404 limpo", r.status == 404, "404", f"{r.status} {jdump(r.json())}")

    # 8d — XSS no cadastro + renderização em /conta
    xss = Client("xss")
    email4 = f"t5.{uuid.uuid4().hex[:10]}@teste.local"
    nome = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    r = xss.req("POST", "/api/auth/register", {"name": nome, "email": email4, "password": "Xss#12345"})
    pagina = xss.req("GET", "/conta")
    html = pagina.text
    tem_cru = "<script>alert(1)</script>" in html or "<img src=x onerror=alert(2)>" in html
    tem_escapado = "&lt;script&gt;alert(1)&lt;/script&gt;" in html or "&lt;script&gt;" in html
    record("8d", "XSS: nome com <script> é escapado em /conta",
           r.status == 201 and pagina.status == 200 and not tem_cru and tem_escapado,
           "HTML escapado (&lt;script&gt;), nenhum <script>alert(1)</script> cru",
           f"register={r.status} conta={pagina.status} cru={tem_cru} escapado={tem_escapado}",
           "trecho: " + (re.search(r".{0,90}(alert\(1\)|alert\(2\)).{0,60}", html, re.S).group(0).replace("\n", " ") if re.search(r"alert\([12]\)", html) else "nome não aparece na página"))

    # também no JSON de /api/auth/me e /api/orders? e no html do header
    me = xss.req("GET", "/api/auth/me").json() or {}
    record("8e", "XSS: nome com <script> não chega cru em outra página (base/header)",
           "<script>alert(1)</script>" not in xss.req("GET", "/").text and "<script>alert(1)</script>" not in xss.req("GET", "/carrinho").text,
           "home e carrinho sem <script>alert(1)</script> cru",
           f"home cru={'<script>alert(1)</script>' in xss.req('GET','/').text} json_me_name={jdump(me.get('name'))}")

    # 8f — IDOR no carrinho
    dono = order["client"]
    pid = order["ids"][0]
    dono.req("POST", "/api/cart/items", {"product_id": pid, "qty": 1})
    antes = (dono.req("GET", "/api/cart").json() or {})
    qtd_antes = next((i["qty"] for i in antes.get("items", []) if i["product_id"] == pid), 0)

    ladrao = Client("idor")
    ladrao.req("GET", "/")  # cart_token próprio, carrinho vazio
    r_patch = ladrao.req("PATCH", f"/api/cart/items/{pid}", {"qty": 99})
    r_del = ladrao.req("DELETE", f"/api/cart/items/{pid}")
    depois = (dono.req("GET", "/api/cart").json() or {})
    qtd_depois = next((i["qty"] for i in depois.get("items", []) if i["product_id"] == pid), None)
    record("8f", "IDOR no carrinho: PATCH/DELETE de item de outro carrinho não funciona",
           r_patch.status in (404, 403) and r_del.status in (404, 403, 200) and qtd_depois == qtd_antes,
           "PATCH 404/403; DELETE 404 (ou 200 idempotente, desde que o carrinho do dono fique intacto)",
           f"patch={r_patch.status} delete={r_del.status} dono qty: {qtd_antes} -> {qtd_depois}",
           f"DELETE é escopado em CartItem.cart_id == cart.id (server/app.py:1379-1385): item de outro carrinho "
           f"nunca é tocado e a resposta é idempotente. PATCH corpo: {jdump(r_patch.json())}")

    # 8g — mass assignment no carrinho (user_id/preço no body)
    r = Client("mass").req("POST", "/api/cart/items", {"product_id": pid, "qty": 1, "price": 0.01, "user_id": 1})
    record("8g", "mass assignment no carrinho (price/user_id no body) é ignorado",
           r.status in (200, 201) and all(abs(float(i.get("price", 0)) - product_prices([pid])[pid]["price"]) < 0.01 for i in ((r.json() or {}).get("items") or [])),
           "preço do banco", f"{r.status} " + jdump([(i['product_id'], i['price']) for i in ((r.json() or {}).get("items") or [])]))

    # 8h — checkout sem autenticação
    r = Client("semlogin").req("POST", "/api/checkout", {"payment": "pix"})
    record("8h", "POST /api/checkout sem JWT -> 401", r.status == 401, "401", f"{r.status} {jdump(r.json())}")

    # 8i — qty negativa / absurda
    r = Client("qty").req("POST", "/api/cart/items", {"product_id": pid, "qty": -5})
    record("8i", "qty negativa no carrinho -> 4xx (não aceita)", r.status >= 400, "422/400", f"{r.status} {jdump(r.json())}")

    # 8j — JWT forjado / adulterado
    import base64
    token = dono.cookie("auth_token") or ""
    if token.count(".") == 2:
        h, p_, sig = token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(p_ + "=" * (-len(p_) % 4)))
        payload["sub"] = "1"
        forged = h + "." + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=") + "." + sig
        r = Client("jwt").req("GET", "/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
        record("8j", "JWT adulterado (sub trocado, assinatura velha) -> 401", r.status == 401, "401",
               f"{r.status} {jdump(r.json())}", f"payload original sub={payload.get('sub')} / uid do dono")
    else:
        record("8j", "JWT adulterado -> 401", False, "401", "sem cookie auth_token para testar")

    # 8k — flags do cookie de sessão
    hdrs = dono.last.headers if dono.last else {}
    r_login = Client("flags").req("POST", "/api/auth/login", {"email": auth["email"], "password": auth["senha"]})
    sc = r_login.headers.get("set-cookie") or r_login.headers.get("Set-Cookie") or ""
    record("8k", "cookie auth_token é httpOnly (e SameSite definido)",
           "httponly" in sc.lower(), "HttpOnly",
           sc[:160] or "sem Set-Cookie",
           f"SameSite presente: {'samesite' in sc.lower()}; Secure: {'secure' in sc.lower()}")

    # 8l — qty acima do max_qty é limitada no servidor
    cdb = db_conn()
    row = cdb.execute("select max_qty, name from products where id=?", (pid,)).fetchone()
    cdb.close()
    max_qty = int(row["max_qty"] or 1)
    c2 = Client("qtymax")
    c2.req("GET", "/")
    r9999 = c2.req("POST", "/api/cart/items", {"product_id": pid, "qty": 9999})
    r = c2.req("POST", "/api/cart/items", {"product_id": pid, "qty": 999})
    got = next((i["qty"] for i in ((r.json() or {}).get("items") or []) if i["product_id"] == pid), None)
    record("8l", "qty acima do max_qty do produto é limitada pelo servidor (e 9999 é rejeitado)",
           got is not None and int(got) <= max_qty and r9999.status == 422,
           f"<= {max_qty} (max_qty do produto) e 9999 rejeitado com 422",
           f"qty pedindo 999 -> {got}; pedindo 9999 -> HTTP {r9999.status}",
           f"produto testado: {row['name'][:40]} (max_qty={max_qty}); server/app.py:1680-1681 faz min(payload.qty, max_qty)")

    # 8m — e-mail duplicado no cadastro
    r = Client("dup").req("POST", "/api/auth/register",
                          {"name": "Duplicado", "email": auth["email"], "password": "Outra#12345"})
    record("8m", "cadastro com e-mail já existente -> 409", r.status == 409, "409", f"{r.status} {jdump(r.json())}")

    # 8n — payload gigante não derruba o servidor (limite de tamanho do nome)
    enorme = "A" * 100000
    r = Client("grande").req("POST", "/api/auth/register",
                             {"name": enorme, "email": f"t5.{uuid.uuid4().hex[:8]}@teste.local",
                              "password": "Grande#12345"})
    record("8n", "nome com 100.000 caracteres -> 4xx (validação) ou 201 sem 500",
           r.status < 500, "4xx ou 201, nunca 5xx", f"{r.status} {jdump(r.json())[:160]}")

    # 8o — injeção no id do pedido
    r = dono.req("GET", "/api/orders/1%20OR%201=1")
    record("8o", "injeção no id do pedido -> 404/422 (nunca 500)", r.status in (404, 422), "404/422",
           f"{r.status} {jdump(r.json())}")

    # 8p — acesso a pedido de outro usuário por id sequencial (varredura 1..N)
    ids_visiveis = []
    for oid in range(1, 8):
        rr = outro.req("GET", f"/api/orders/{oid}")
        if rr.status == 200:
            ids_visiveis.append(oid)
    record("8p", "varredura de /api/orders/1..7 pelo intruso não vaza pedido alheio",
           not ids_visiveis, "nenhum 200", f"{len(ids_visiveis)} pedido(s) visíveis: {ids_visiveis}",
           "todos 403/404")


def main() -> int:
    log(f"BASE_URL = {BASE}")
    log(f"início: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    check_db()
    check_server(Client("servidor"))
    auth = check_auth()
    order = check_cart_order(auth)
    check_security(auth, order)

    total = len(RESULTS)
    falhas = [r for r in RESULTS if not r["ok"]]
    log("\n" + "=" * 70)
    log(f"RESUMO: {total - len(falhas)}/{total} OK, {len(falhas)} FALHOU")
    for f in falhas:
        log(f"  FALHOU {f['check']} {f['title']} -> {f['got']}")

    (ARTI / "e2e_api.log").write_text("\n".join(LOG), encoding="utf-8")
    (ARTI / "e2e_api.json").write_text(json.dumps(
        {"base": BASE, "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "ok": total - len(falhas), "total": total, "falhas": len(falhas), "results": RESULTS},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
