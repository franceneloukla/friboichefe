# Friboi Online — réplica funcional com banco de dados próprio

Clone de front-end da loja **friboionline.com.br** reconstruído do zero: mesma
identidade visual, mesmos assets, mesmas imagens de produto, mesmo catálogo e
mesmos textos — rodando em cima de **um banco de dados nosso**, com cadastro,
login, carrinho e pedido de verdade.

> O catálogo, os preços e as imagens foram extraídos do site original (é a
> "referência"). A partir daqui quem manda é o nosso banco: basta trocar
> `data/catalog.json` ou os preços em `data/prices.csv`.

---

## Rodar em 3 comandos

```bash
cd server && ./run.sh
# abre em http://127.0.0.1:8099
```

`run.sh` cria o banco (`data/store.db`), popula com o catálogo (se estiver vazio)
e sobe o servidor. Na raiz existe também:

```bash
./start.sh          # atalho: checa o venv, roda o seed e sobe o servidor
make scrape         # re-extrai o catálogo do site original (~13 min)
make seed           # repopula o banco a partir de data/catalog.json
make reset          # apaga o banco e repopula
```

**Usuário de desenvolvimento** (só com `DEV_MODE=1`):
`admin@loja.local` / `admin123`

## O que já está funcionando

| Área | Estado |
|---|---|
| Catálogo | **1.567 produtos** e **471 categorias** no SQLite |
| Imagens | **1.557** fotos locais em `data/images/products/{id}/main.jpg` (600×600) |
| Assets de UI | **110 arquivos** (logos, ícones, banners, cards de marca, fontes Roboto/Roboto Condensed) em `web/static` |
| Páginas | home, categoria, busca, promoções, produto (PDP), login, cadastro, carrinho, checkout, conta, 404 |
| API | `POST /api/auth/register`, `login`, `logout`, `GET /api/auth/me`, catálogo, carrinho, checkout, pedidos |
| Auth | bcrypt + JWT HS256 em cookie httpOnly (`auth_token`) |
| Carrinho | cookie `cart_token` (funciona deslogado, funde ao logar) |
| Pedidos | checkout calcula tudo no servidor, grava `orders`/`order_items` |
| Banco | SQLite local por padrão; Postgres (Neon/Supabase) via `DATABASE_URL` |
| Deploy | pronto para Vercel (`vercel.json` + `api/index.py`) — ver `docs/VERCEL.md` |

## Estrutura

```
├── api/index.py            # entrypoint serverless do Vercel (expõe o app ASGI)
├── server/                 # FastAPI
│   ├── app.py              # rotas de página (Jinja2) + API JSON
│   ├── db.py               # engine DB-agnóstico (SQLite/Postgres) + init_db
│   ├── models.py           # ORM (users, products, categories, carts, orders…)
│   ├── auth.py             # bcrypt + JWT
│   ├── seed.py             # importa data/catalog.json para o banco
│   ├── run.sh              # sobe o servidor na 8099
│   ├── templates/          # Jinja2 (base, index, catalogo, produto, …)
│   └── static/             # app.css + app.js (CSS/JS puro, sem CDN)
├── web/static/             # assets originais baixados (servidos em /assets)
├── data/
│   ├── catalog.json        # catálogo extraído (1.567 produtos)
│   ├── images/products/    # fotos dos produtos (servidas em /img/products)
│   ├── prices.csv          # planilha de preços para editar e reimportar
│   └── store.db            # banco SQLite (gerado)
├── scraper/scrape_catalog.py # extrator do catálogo (Playwright)
├── scripts/                # build do Vercel, normalização de assets, preços
├── docs/                   # CONTRATO, DESIGN_SPEC, VERCEL, VERIFICACAO
└── vercel.json
```

## Trocar os preços

O site original não publica o preço de venda na API — todos os itens vêm com o
valor de tabela **R$ 9.999,00**. Isso é fiel ao original, não um bug.

Para colocar os seus preços:

```bash
.venv/bin/python scripts/update_prices.py --export   # gera data/prices.csv
# edite price / sale_price no CSV (aceita "1.234,56" ou "1234.56")
.venv/bin/python scripts/update_prices.py            # aplica no banco
```

Preencher `sale_price` faz o produto aparecer na página **Promoções** e ganhar
o selo de oferta.

## Trocar o catálogo

`data/catalog.json` segue o contrato documentado em `docs/CONTRATO.md`. Depois de
editar (ou re-extrair com `make scrape`), rode `make seed` — o seed é idempotente
(upsert por id) e recalcula o caminho das imagens.

## Deploy no Vercel

Passo a passo completo em **[docs/VERCEL.md](docs/VERCEL.md)**. Resumo:

```bash
vercel link
vercel env add DATABASE_URL production   # Postgres (Neon) — recomenda-se
vercel --prod
```

Sem `DATABASE_URL` o site **sobe**, mas usa SQLite em `/tmp`: funciona para
navegar/conferir o layout e **não persiste** cadastro/pedido entre cold starts.
Para loja de verdade, conecte um Postgres.

## Fidelidade ao original

- Dossiê visual medido no site original: `docs/DESIGN_SPEC.md` (paleta, tipografia
  por elemento, layout, markup recortado, copy exata).
- Capturas e markup de referência: `docs/CAPTURE/`.
- Verificação E2E independente: `docs/VERIFICACAO.md`.

## Segurança

- Senhas em bcrypt, nunca em texto puro.
- JWT HS256 assinado com `SECRET_KEY` — **defina um valor próprio em produção**.
- Checkout nunca aceita preço/total do cliente: recalcula do banco.
- Pedido de outro usuário responde 403; rotas de página não vazam dados de conta.
