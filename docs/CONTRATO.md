# CONTRATO TÉCNICO — Friboi Online (clone de front-end com banco próprio)

Todo mundo (backend, frontend, scraper, verificador) segue ESTE contrato. Ele é a
fonte de verdade para caminhos, schema, endpoints e templates. Não invente fora dele.

## Estrutura do projeto

```
friboi-online/
├── data/                     # gerado pelo scraper (T1) — catálogo + imagens
│   ├── catalog.json          # produtos e categorias (schema abaixo)
│   ├── catalog_stats.json
│   ├── store.db              # SQLite do app (criado pelo seed, T3)
│   └── images/products/{id}/main.jpg
├── scraper/                  # T1
├── server/                   # T3 (código) + T4 (templates/static)
│   ├── app.py                # FastAPI: páginas Jinja2 + API JSON
│   ├── db.py                 # engine/session SQLAlchemy 2.0
│   ├── models.py             # ORM
│   ├── auth.py               # bcrypt + JWT (python-jose)
│   ├── seed.py               # importa data/catalog.json -> SQLite
│   ├── run.sh                # sobe uvicorn 127.0.0.1:8099
│   ├── templates/            # T4 — Jinja2 (.html)
│   └── static/css/app.css    # T4 — CSS da loja
├── web/static/               # T2 — assets originais baixados
│   ├── img/ui/               # logo, ícones, banners, cards de marca, pagamentos
│   ├── fonts/
│   └── css/                  # css original do site (referência)
├── docs/
│   ├── CONTRATO.md           # este arquivo
│   ├── DESIGN_SPEC.md        # T2
│   ├── CAPTURE/              # T2 screenshots + DOM + assets_map.json
│   └── VERIFICACAO.md        # T5
└── tests/                    # T5
```

## Mounts do FastAPI (T3 implementa)

| Rota HTTP | Diretório |
|---|---|
| `/static` | `server/static` |
| `/assets` | `web/static` |
| `/img/products` | `data/images/products` |

## Banco: SQLite em `data/store.db` (SQLAlchemy 2.0)

```
users(id PK, name, email UNIQUE NOT NULL, password_hash, cpf, phone, is_admin BOOL DEFAULT 0, created_at)

categories(id TEXT PK, name, slug UNIQUE, parent_id TEXT NULL, sort INT DEFAULT 0)

products(id TEXT PK, sku, name NOT NULL, slug UNIQUE NOT NULL, brand, category_id TEXT NULL,
         price NUMERIC(10,2) NOT NULL, sale_price NUMERIC(10,2) NULL, unit TEXT DEFAULT 'KG',
         ean, weight_min NUMERIC, weight_avg NUMERIC, weight_max NUMERIC,
         stock TEXT DEFAULT 'Indisponível', max_qty INT DEFAULT 1,
         description_html TEXT, video_url TEXT, image_path TEXT,
         attrs_json TEXT, nutrition_json TEXT, active BOOL DEFAULT 1, created_at)

carts(id PK, token TEXT UNIQUE NOT NULL, user_id INT NULL, created_at, updated_at)
cart_items(id PK, cart_id FK, product_id TEXT FK, qty INT NOT NULL, UNIQUE(cart_id, product_id))

orders(id PK, user_id INT NOT NULL, status TEXT DEFAULT 'pendente', subtotal NUMERIC, shipping NUMERIC DEFAULT 0,
       total NUMERIC, payment TEXT, ship_name, ship_email, ship_phone, ship_cep, ship_address,
       ship_number, ship_complement, ship_district, ship_city, ship_state, created_at)
order_items(id PK, order_id FK, product_id TEXT, name TEXT, unit_price NUMERIC, qty INT, subtotal NUMERIC)
```

`image_path` guarda o caminho relativo dentro de `data/images`, ex: `products/376490/main.jpg`
(servido como `/img/products/376490/main.jpg`).

## API JSON (T3) — todas as respostas em JSON, erros `{"detail": "..."}`

Auth:
- `POST /api/auth/register` body `{name,email,password,cpf?,phone?}` → 201 `{user:{id,name,email},access_token}`
- `POST /api/auth/login` body `{email,password}` → 200 `{user,access_token}` | 401 `{"detail":"E-mail ou senha inválidos"}`
- `POST /api/auth/logout` → 200 (limpa cookie)
- `GET  /api/auth/me` → `{id,name,email,cpf,phone}` | 401

Catálogo:
- `GET /api/categories` → `[{id,name,slug,parent_id,count}]`
- `GET /api/products?q=&category=&page=1&limit=12&sort=relevance|price_asc|price_desc|name&on_sale=1&in_stock=1`
  → `{total,page,limit,pages,items:[Product]}` onde
  `Product = {id,sku,name,slug,brand,category_id,price,sale_price,unit,weight_min,weight_avg,weight_max,stock,max_qty,image_url,attrs}`
- `GET /api/products/{slug_or_id}` → `ProductFull` = Product + `{ean,description_html,video_url,nutrition,images:[url]}`

Carrinho (via cookie `cart_token`, criado se ausente; funciona para visitante e logado):
- `GET /api/cart` → `{token,items:[{product_id,name,slug,unit,price,qty,subtotal,image_url}],count,subtotal}`
- `POST /api/cart/items` `{product_id, qty=1}` → carrinho
- `PATCH /api/cart/items/{product_id}` `{qty}` (qty<=0 remove) → carrinho
- `DELETE /api/cart/items/{product_id}` → carrinho
- `POST /api/cart/merge` — ao logar, funde carrinho anônimo no do usuário
- `DELETE /api/cart` — limpa

Pedidos (exige JWT):
- `POST /api/checkout` `{payment:"pix"|"boleto"|"cartao", ship:{name,email,phone,cep,address,number,complement,district,city,state}}`
  → 201 `{order:{id,total,status,items:[...]}}` e limpa o carrinho
- `GET /api/orders` → pedidos do usuário logado
- `GET /api/orders/{id}` → pedido do usuário (403 se de outro)

## Páginas (Jinja2, PT-BR, server-side)

| Rota | Template | Conteúdo |
|---|---|---|
| `/` | `index.html` | hero, categorias, 2 vitrines, cards de marca, marcas, benefícios, banner final |
| `/categoria/{slug}` | `catalogo.html` | grid + filtros (ordenação, promoções, estoque) + paginação |
| `/busca?q=` | `catalogo.html` | idem |
| `/promocoes` | `catalogo.html` | só `on_sale=1` |
| `/produto/{slug}` | `produto.html` | galeria, preço, estoque, qtd, add ao carrinho, descrição, nutrição, relacionados |
| `/login` | `login.html` | email+senha, link cadastro |
| `/cadastro` | `cadastro.html` | nome, email, senha, confirmação, CPF, telefone |
| `/carrinho` | `carrinho.html` | itens, qtd, subtotal, botão checkout |
| `/checkout` | `checkout.html` | endereço + pagamento + resumo |
| `/conta` | `conta.html` | dados + histórico de pedidos |
| `/404` | `404.html` | página não encontrada |

Todas as páginas herdam `base.html` (header + nav + footer idênticos ao original).

## Identidade visual (obrigatório bater com o original)

- Azul institucional do header/nav, vermelho do CTA `Login ou Cadastre-se` e dos botões `Ver Produto`.
- Fundo branco, cards com borda cinza clara e sombra suave.
- Logo Friboi Online no header e no footer.
- Header: logo à esquerda · busca central (`Busque aqui seu produto...` + lupa) · botão vermelho à direita.
- Nav: Bovinos · Bovinos Importados · Aves · Suínos · Pescados · Batatas e Vegetais · Cordeiros · Charques · Outros · Promoções · Marcas.
- Faixa de cupom: `CADASTRE-SE E GANHE 5% DE DESCONTO na primeira compra com o cupom PCFRIBOI5. Cadastre-se`
- Cards de produto: badge `Congelado`, `CÓD. {sku}`, nome, `Caixa: {min}kg a {max}kg`, `Peças: ...`, botão vermelho `Ver Produto`.
- Rodapé: colunas Acesso Rápido / Nossas Marcas / A Friboi / Meios de Pagamento + Redes Sociais e a linha `© 2026 JBS Friboi. Todos os direitos reservados.`

Valores exatos de cor, fonte e espaçamento: ver `docs/DESIGN_SPEC.md` (T2). Em caso de
divergência entre este contrato e o DESIGN_SPEC, o DESIGN_SPEC vence na parte visual.

## Porta e execução

```bash
cd server && ./run.sh        # uvicorn em 127.0.0.1:8099
```
`run.sh` exporta `SECRET_KEY` (default de dev), monta o `PYTHONPATH` para o `.venv` da raiz
(`../.venv/bin/python`) e sobe com `--host 127.0.0.1 --port 8099`.

## Regras

1. Nada de caminho absoluto de máquina, home de usuário, hostname ou nome de máquina dentro de arquivo versionado. Caminhos relativos ao root.
2. Nenhum asset pode vir da internet em runtime — tudo local em `web/static` e `data/images`.
3. Sem CDN externo obrigatório (Google Fonts, jquery): fontes e libs locais.
4. Tabela de preços vem 100% do nosso SQLite, nunca do site original.
