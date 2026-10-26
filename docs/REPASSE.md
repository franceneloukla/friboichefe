# REPASSE TÉCNICO — Friboi Online (clone com banco próprio)

Documento de entrega para outro dev. Tudo aqui foi verificado no código e no
deploy em produção. Última atualização: commit `06e1d89`.

---

## 1. O que é

Réplica funcional do front-end da loja **friboionline.com.br**, rodando com
banco de dados próprio (SQLite/Postgres), cadastro, login, carrinho e
**venda por cotação** (a loja não exibe preço — decisão do cliente: o preço é
do representante de cada estado).

- **No ar:** https://friboichefes-hhbc.vercel.app
- **Local:** `http://127.0.0.1:8099` (padrão do `server/run.sh`)

| Número | Valor |
|---|---|
| Produtos no catálogo | 1.567 |
| Categorias | 471 |
| Fotos de produto (locais) | 1.557 (600×600, 63 MB) |
| Assets de interface | 108 arquivos em `web/static` (5,3 MB) |
| Templates Jinja2 | 13 |
| Rotas | 15 páginas + 19 endpoints de API + sitemap/robots |
| Arquivos versionados | 1.805 |
| Commit atual | `06e1d89` (branch `main`) |

Stack: **Python 3.12+ · FastAPI · SQLAlchemy 2 · Jinja2 · SQLite (ou Postgres) ·
HTML/CSS/JS puro** (sem Tailwind, sem React, sem CDN).

---

## 2. Acesso ao código (Git)

Existem **dois repositórios públicos espelhados**, mesmo conteúdo, mesma branch:

```
origin   https://github.com/franceneloukla/friboichefe.git
github2  https://github.com/franceneloukla/friboichefes.git    ← este está ligado ao Vercel
```

Branch única: **`main`**. Não há `develop`.

### Clonar

```bash
git clone https://github.com/franceneloukla/friboichefes.git
cd friboichefes
```

### Identidade de commit (obrigatória — é a conta do dono no GitHub e no Vercel)

```bash
git config user.name  "franceneloukla"
git config user.email "franceneloukla@inbox.lv"
```

O `~/.gitconfig` global do dono já está assim. **Nunca** commitar como
`wiu <wiu@local>` ou identidade fake — já vazou rastro uma vez.

### Commitar e publicar nos dois remotos

```bash
git add -A
git commit -m "área: o que mudou (imperativo, curto)"
git push origin main
git push github2 main      # mantém o espelho em sincronia
```

> Os remotes locais do dono carregam um Personal Access Token na URL
> (`https://franceneloukla:<TOKEN>@github.com/...`). O token **não** está em
> nenhum arquivo do repositório — se você for commitar, use **suas próprias
> credenciais** (`git remote set-url origin https://github.com/franceneloukla/friboichefes.git`
> + `gh auth login` ou um token seu).

### Regras de commit do projeto (aprendidas na dor)

1. **Rastro zero**: nada de `/home/<usuario>`, `~/`, hostname ou nome de máquina
   dentro de arquivo versionado. Rode antes de todo push:
   ```bash
   git grep -I -n -F -e "/home/" -e "$(hostname)" HEAD -- . ':!docs/REPASSE.md'
   ```
   Qualquer resultado é bug — corrija antes de publicar.
2. **Nunca** versionar: `.venv/`, `_scratch/`, `data/store.db`, `data/_raw/`,
   checkpoints do scraper, `public/`, `tests/artifacts/`, `tests/screenshots/`.
   Já estão no `.gitignore` — não force com `git add -f`.
3. **`data/seed.db` e `data/catalog.json` SÃO versionados** (o deploy depende
   deles). Se mudar o catálogo/imagens, regenere o seed e commite os dois juntos.
4. Se editar `README.md` direto no GitHub, o merge local pode esvaziar o arquivo —
   confira `wc -l README.md` depois de puxar (já aconteceu uma vez).

---

## 3. Rodar localmente

```bash
cd <projeto>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 1ª vez: cria data/store.db e popula com o catálogo (seed automático, ~5 s)
cd server && ./run.sh          # http://127.0.0.1:8099
```

Atalhos na raiz: `./start.sh` (venv + seed + servidor), `make seed`, `make reset`.

**Usuário de teste** (só com `DEV_MODE=1`): `admin@loja.local` / `admin123`.

Variáveis de ambiente (todas opcionais; ver `server/.env.example`):

| Variável | Default | Para que serve |
|---|---|---|
| `DATABASE_URL` | — | Postgres (`postgres://…` é normalizado p/ `postgresql+psycopg2://`). Sem ela: SQLite |
| `DB_PATH` | `data/store.db` | caminho do SQLite |
| `SECRET_KEY` | valor de dev | assinatura do JWT — **trocar em produção** |
| `CATALOG_PATH` | `data/catalog.json` | catálogo alternativo p/ o seed |
| `SEED_DB_PATH` | `data/seed.db` | banco pré-montado copiado no cold start |
| `SEED_ON_INIT` | `1` | popula o banco se estiver vazio |
| `DEV_MODE` | `0` | `1` cria o admin de teste |
| `SITE_URL` | host da request | base absoluta do sitemap/robots |

---

## 4. Estrutura de arquivos

```
api/index.py            entrada serverless (Vercel) — importa server.app e instala
                        o middleware que recupera o path reescrito
server/
  app.py                rotas de página (Jinja2) + API JSON (2.185 linhas)
  models.py             ORM (SQLAlchemy 2.0): users, categories, products, carts,
                        cart_items, orders, order_items, quote_requests
  db.py                 engine DB-agnóstico + init_db() (create_all, seed, cópia do
                        seed.db, migrações defensivas) + log do backend usado
  auth.py               bcrypt + JWT HS256 em cookie httpOnly
  seed.py               importa data/catalog.json → banco (idempotente)
  build_seed_db.py      gera data/seed.db (banco pré-montado p/ o cold start)
  textutil.py           fold_text / make_search_blob (normalização de busca)
  ufs.py                as 27 UFs + normalização
  run.sh                sobe uvicorn em 127.0.0.1:8099
  templates/            13 .html (base, index, catalogo, produto, cotacao, carrinho,
                        checkout, conta, login, cadastro, institucional, 404, _macros)
  static/               css/app.css (3.225 linhas) + js/app.js (852 linhas)
web/static/             assets originais (logo, ícones, hero, cards de marca, fontes)
data/
  catalog.json          catálogo extraído (1.567 produtos, 2,1 MB)
  seed.db               banco pré-montado (2,3 MB) — copiado p/ /tmp no cold start
  images/products/{id}/ 1.557 fotos
  prices.csv            planilha de preços (importável)
scraper/                extrator do catálogo (Playwright + API Oracle Commerce)
scripts/                build_vercel.py · normalize_assets.py · update_prices.py
docs/                   CONTRATO.md · DESIGN_SPEC.md · VERCEL.md · VERIFICACAO.md
tests/                  baterias E2E (e2e_api.py, pages_assets.py, visual_check.py…)
```

---

## 5. Banco de dados

SQLite por padrão (`data/store.db`), Postgres se `DATABASE_URL` existir.
`server/db.py::init_db()` roda no boot e: cria tabelas, copia `data/seed.db` se o
banco estiver vazio (0,15 s em vez de 3,5 s semeando) e aplica migrações
defensivas (`search_blob`, `quote_requests`).

| Tabela | Colunas principais | Observação |
|---|---|---|
| `products` | id, sku, name, slug, brand, category_id, **price**, sale_price, unit, ean, weight_min/avg/max, stock, max_qty, **search_blob**, description_html, video_url, image_path, attrs_json, nutrition_json, active | `price` **fica no banco** mas **nunca** é exposto na API/UI |
| `categories` | id, name, slug, parent_id, sort | 471 registros |
| `users` | id, name, email (unique), password_hash (bcrypt), cpf, phone, is_admin | |
| `carts` / `cart_items` | token (cookie), user_id; cart_id, product_id, qty | carrinho funciona deslogado, funde no login |
| `orders` / `order_items` | status, total, ship_*, payment | legado do checkout antigo; hoje grava `status="cotacao"`, `total=0` |
| **`quote_requests`** | id, nome, email, telefone, uf, cidade, mensagem, items_json, origem, status, created_at | **é aqui que as cotações caem** |

Ler as cotações recebidas:

```bash
sqlite3 data/store.db "select id,nome,email,telefone,uf,origem,created_at,items_json from quote_requests order by id desc;"
```

Regenerar o catálogo (se precisar): `make scrape` (~13 min, usa Playwright) →
`make seed` → `.venv/bin/python server/build_seed_db.py` → commitar
`data/catalog.json` + `data/seed.db`.

---

## 6. Rotas

**Páginas** (Jinja2, PT-BR): `/` · `/categoria/{slug}` · `/busca?q=` · `/promocoes`
· `/produto/{slug}` · `/login` · `/cadastro` · `/carrinho` · `/cotacao` ·
`/checkout` (303 → `/cotacao?carrinho=1`) · `/conta` · `/institucional/{slug}`
(16 páginas) · `/sitemap.xml` · `/robots.txt` · 404 próprio.

**API** (`/api`, JSON):

```
POST /api/auth/register        POST /api/auth/login      POST /api/auth/logout
GET  /api/auth/me
GET  /api/categories
GET  /api/products?q=&category=&page=&limit=&sort=&on_sale=1&in_stock=1
GET  /api/products/{slug_or_id}
GET  /api/cart                 POST /api/cart/items      PATCH/DELETE /api/cart/items/{id}
POST /api/cart/merge           DELETE /api/cart
GET  /api/cotacao/ufs          POST /api/cotacao          ← coração do fluxo atual
POST /api/checkout             (legado: grava status "cotacao", total 0)
GET  /api/orders               GET  /api/orders/{id}
GET  /api/health               ← healthcheck: {status, db, products, categories, templates}
```

`POST /api/cotacao` (201):

```json
{ "nome": "…", "email": "…", "telefone": "…", "uf": "SP", "cidade": "…",
  "mensagem": "…", "produto_id": "376490", "items": [{"product_id":"376490","qty":2}],
  "origem": "produto|carrinho|site" }
```

Aceita `items` **ou** `itens`. Valida: nome ≥ 3, e-mail, telefone ≥ 10 dígitos,
UF entre as 27 (aceita sigla ou nome por extenso) → 422 com `{detail, errors:{campo:msg}}`.

### Regra de negócio atual: sem preços

- `Product` **não** devolve `price`/`sale_price`/`effective_price`.
- `GET /api/cart` devolve `{token,count,items:[{product_id,name,slug,unit,qty,image_url}]}` — sem valores.
- Cards têm o botão **Ver Produto** que abre o modal `#modal-cotacao`
  (classe `js-ver-produto` + `data-slug`); o `href` para `/produto/{slug}` é o
  fallback sem JS.
- Nenhuma página pode imprimir `R$`. Se voltar a ter preço, é contrariar o
  `docs/CONTRATO.md` (ADENDO v2).

---

## 7. Deploy (Vercel)

Está tudo em `docs/VERCEL.md`. Resumo do que **não pode ser mexido sem cuidado**:

- **`.python-version` não existe de propósito** — o Vercel usa o CPython da imagem
  (hoje 3.14). Por isso o `requirements.txt` está nas versões que têm wheel cp314
  **e** cp312. Se voltar `pydantic 2.10`/`psycopg2` no requirements, o build
  quebra (foi o bug do maturin/PyO3).
- **`vercel.json`**: `includeFiles` tem que ser **string** (o schema do Vercel
  rejeita array). O rewrite é `/((?!assets/|static/|img/|favicon).*)` →
  `/api/index/$1`, e o `api/index.py` remove esse prefixo antes do roteamento —
  sem isso toda URL devolve `{"detail":"Not Found"}`.
- **Build**: `scripts/build_vercel.py` copia `web/static` → `public/assets`,
  `server/static` → `public/static`, `data/images` → `public/img` (1.669 arquivos).
  Estático é servido pelo CDN **antes** da função.
- **Banco no Vercel**: sem `DATABASE_URL` usa SQLite em `/tmp` → **cotações,
  cadastros e pedidos não sobrevivem ao cold start**. Para produção de verdade,
  crie um Postgres (Neon free), set `DATABASE_URL` e adicione
  `psycopg2-binary==2.9.10` ao `requirements.txt` (tem wheel cp314).
- Variável opcional `SITE_URL` deixa o sitemap com o domínio correto.

---

## 8. Verificação / testes

```bash
cd server && ./run.sh &                       # sobe o site
.venv/bin/python tests/e2e_api.py             # API, auth, carrinho, segurança
.venv/bin/python tests/pages_assets.py        # páginas + assets locais
.venv/bin/python tests/visual_check.py        # fidelidade visual
```

⚠️ `tests/e2e_api.py` ainda tem checks do contrato **v1** (subtotal/total/status
"pendente") que falham por design depois do modo cotação — foi sinalizado e é a
primeira coisa a atualizar se vocês voltarem a rodar a bateria.

Relatórios já produzidos: `docs/VERIFICACAO.md` (72 checks executados no v1),
`docs/DESIGN_SPEC.md` (1.284 linhas medidas no site original: paleta, tipografia,
layout, markup de referência), `docs/CONTRATO.md` (fonte de verdade do schema/rotas).

Diagnóstico em produção sem acesso a log: chamar qualquer URL com
`?vg_diag=diag-9f2c` (ou header `x-vg-diag: diag-9f2c`) devolve o traceback em JSON.

---

## 9. Pendências e limites conhecidos

| # | Item | Impacto |
|---|---|---|
| 1 | **Persistência no Vercel** sem `DATABASE_URL` | cotações/cadastros somem no cold start — é o item mais importante |
| 2 | Tela de admin para listar as cotações | hoje só via `sqlite3`/painel do Neon |
| 3 | Facetas da listagem (MARCA, TEMPERATURA, TIPO) | o original tem; os dados estão em `products.attrs_json`, falta UI |
| 4 | Pagamento/gateway | não existe; o fluxo termina na cotação |
| 5 | `tests/e2e_api.py` desatualizado (v1) | checks 6a/6c/6f falham por design |
| 6 | `/favicon.ico` responde 404 | o `<link rel="icon">` aponta p/ `/assets/img/ui/logos/favicon.png` (200) — cosmético |
| 7 | Preço no banco | 1.566 itens em R$ 9.999,00 (valor de tabela do site original) — invisível na UI; use `scripts/update_prices.py` se voltar a exibir |

---

## 10. Checklist de onboarding (1ª hora)

```bash
git clone https://github.com/franceneloukla/friboichefes.git && cd friboichefes
git config user.name "franceneloukla" && git config user.email "franceneloukla@inbox.lv"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd server && ./run.sh                      # abre em 127.0.0.1:8099
curl -s localhost:8099/api/health          # products=1567
# ler, nesta ordem: docs/CONTRATO.md → docs/VERCEL.md → docs/DESIGN_SPEC.md (só o §1 e §6.5)
```

Se algo divergir do que está aqui, o código é a verdade — este documento
acompanha o commit `06e1d89`.
