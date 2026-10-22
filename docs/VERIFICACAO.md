# Verificação E2E — relatório final

**Data:** 2026-10-21 · **Estado verificado:** código congelado (front + back)
**Ambiente:** servidor local em `127.0.0.1:8199` (banco de teste em `tests/tmp/`) e bundle
serverless simulado com `VERCEL=1`, banco em `/tmp`. Nada disso toca o banco de produção local.

A verificação foi feita **por execução** (scripts em `tests/`), não por leitura de relato.
Artefatos brutos: `tests/artifacts/` (saída JSON + log de cada rodada, não versionados).

| Suite | Resultado |
|---|---|
| `tests/e2e_api.py` — API, auth, carrinho, pedido, segurança | **44/44 OK** |
| `tests/pages_assets.py` — páginas, seções e assets locais | **20/20 OK** |
| `tests/vercel_check.py` — bundle serverless | **8/8 OK** |
| `tests/visual_check.py` + `compare_images.py` — fidelidade visual | ver §4 |

---

## 1. Catálogo e banco

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| Produtos no SQLite == total do `catalog.json` | 1.567 | 1.567 | OK |
| Categorias | ≥ 8 | **471** | OK |
| Produtos com imagem em disco | ≥ 1.500 | **1.557** | OK |
| `image_path` apontando para arquivo existente | 0 quebrados | **0 quebrados / 1.557** | OK |
| `data/seed.db` (banco pré-montado) | íntegro | 1.567 produtos, 471 categorias, 0 usuários, 0 pedidos, `integrity_check=ok` | OK |

## 2. Páginas

Todas as rotas de página respondem 200, sem traceback Jinja2 e sem "Internal Server Error":

`/` · `/categoria/bovinos` · `/produto/<slug>` · `/login` · `/cadastro` · `/carrinho` ·
`/checkout` · `/promocoes` · `/busca?q=acem` · `/institucional/faq` · `/institucional/marca-friboi` ·
`/sitemap.xml` (200, `application/xml`, 2.039 URLs) · `/robots.txt` (200)

- `/conta` deslogado → **303 → /login?next=/conta**; logado → 200 com os dados do usuário.
- `/nao-existe` → **404** com a página 404 própria.
- Home tem **12/12** seções do original; PDP tem **9/9** partes exigidas pelo `docs/CONTRATO.md`.

## 3. Assets — 100 % locais

| Check | Obtido | Status |
|---|---|---|
| Assets apontando para domínio externo obrigatório | **0** | OK |
| `url()` externo no CSS (Google Fonts / CDN) | **0** | OK |
| Referências locais quebradas | **0** | OK |
| Assets locais referenciados respondendo 200 com bytes > 0 | **76/76** | OK |
| `@font-face` locais servindo 200 | **17/17** | OK |
| Imagens de produto na home | 16 únicas, 0 quebradas | OK |
| Erros de console no navegador (todas as páginas) | **0** (só o 404 esperado) | OK |

## 4. Fidelidade visual (home, 1440 px)

Comparação pixel a pixel contra o screenshot do original:

| Métrica | Original | Clone |
|---|---|---|
| Altura do documento | 3.385 px | **3.387 px** (Δ = 2 px, 0,06 %) |
| Cor dominante | `#FFFFFF` 41,56 % | `#FFFFFF` 40,36 % |
| 2ª cor dominante | `#091956` 11,47 % | `#0A1956` 11,39 % |
| 3ª cor dominante | `#9C1011` 8,27 % | `#9E1011` 8,24 % |
| Pixels idênticos | — | **73,9 %** |
| Logo | x152 y28 87×40 | x153 y28 87×40 |
| Input de busca | x315..941 | x315..946 |
| Botão de login | x959..1176 y33..82 | x958..1177 y31..82 |
| Faixa de cupom | x15..1409, 53 px | x15..1410, 53 px |
| Hero | x113 1200×250 | x113 1200×250 |
| Container | 143..1283 (1140 px) | 143..1283 (1140 px) |
| Faixa de marcas | 133..1291, 5×199 | 133..1291, 5×199 |

### Divergências medidas (cosméticas, nenhuma bloqueante)

| Item | Esperado (original) | Obtido | Gravidade |
|---|---|---|---|
| `nav.font` | 15 px / peso 500 | 13 px / peso 400 | baixa — nav um pouco mais leve |
| Card da home mostra preço | original **esconde** o preço do visitante | mostra `Por R$9.999,00 /kg` | intencional (decisão do cliente: preço visível) |
| `card.h` | 271 px | 292 px | consequência do preço visível |
| `badge.size` (selo "Congelado") | 8,4 px | 9,6 px | baixa |
| `footer_h3` | 13,3 px / 800 | 12 px / 700 | baixa |
| `footer_col.w` | 320,75 px | 298,5 px | baixa |
| `footer_copy` (copyright) | 9,8 px | 11 px | baixa |
| `benefit_titulo.weight` | 800 | 700 | baixa |
| `body` fonte primária | Roboto | Helvetica Neue primeiro | baixa (as duas existem localmente) |
| `search_input_w` | 565 px | 547 px | baixa |

As bordas de seção (21 marcas de y) coincidem dentro de 1–3 px em praticamente toda a página.

## 5. Autenticação

| Check | Obtido | Status |
|---|---|---|
| Registro | 201 com `user` + `access_token` | OK |
| Login | 200 | OK |
| `/api/auth/me` com cookie | 200 com o e-mail correto | OK |
| `/api/auth/me` sem cookie | **401** | OK |
| Login com senha errada | **401** | OK |
| Hash de senha no banco | `$2b$12$…` (60 chars), 0 hashes degenerados, 0 senhas em texto puro | OK |
| 2º usuário no mesmo navegador (mesmo `cart_token`) | 201/200, **sem 500** (regressão do bug de UNIQUE coberta) | OK |
| Troca de sessão no mesmo browser | `/api/auth/me` devolve o 2º usuário | OK |
| Cookie `auth_token` | httpOnly + SameSite | OK |
| E-mail duplicado | **409** "Este e-mail já está cadastrado" | OK |

## 6. Carrinho e pedido

| Check | Obtido | Status |
|---|---|---|
| Subtotal = Σ (preço do banco × qty) | R$ 49.995,00 (5 itens) | OK |
| Carrinho anônimo fundido ao logar | 5 itens preservados | OK |
| `POST /api/checkout` | **201** | OK |
| Pedido gravado em `orders` + `order_items` | pedido 1, 2 itens, total R$ 49.995,00 | OK |
| Carrinho zerado após o checkout | 0 itens | OK |
| `GET /api/orders` lista o pedido do dono | sim | OK |

## 7. Segurança

| Ataque testado | Resultado | Status |
|---|---|---|
| Preço/total falsos no corpo do checkout | ignorados — total recalculado do banco (R$ 49.995,00) | OK |
| Pedido de outro usuário (`/api/orders/{id}`) | **403** "Você não tem acesso a este pedido" | OK |
| Varredura de `/api/orders/1..7` por intruso | 0 pedidos visíveis | OK |
| SQLi em `q` (`' OR 1=1--`, `UNION SELECT`, `acem' --`) | 200, `total=0`, sem vazamento | OK |
| SQLi no `slug_or_id` | 404 limpo | OK |
| XSS no nome do usuário (`<script>`) | escapado em `/conta` e no header | OK |
| IDOR no carrinho (PATCH/DELETE de item alheio) | 404 / não altera o dono | OK |
| Mass assignment (`price`, `user_id` no body) | ignorado | OK |
| Checkout sem JWT | **401** | OK |
| `qty` negativa / acima do `max_qty` | 422 / limitada ao estoque | OK |
| JWT adulterado | **401** | OK |
| Nome com 100.000 caracteres | 422 (limite de validação) | OK |
| ID de pedido não numérico | 422 (nunca 500) | OK |

## 8. Bundle serverless (o que vai para o Vercel)

| Check | Obtido | Status |
|---|---|---|
| Cold start com `data/seed.db` | **3,19 s** até responder (banco: ~0,15 s vs ~3,5 s semeando) | OK |
| `/api/health` no serverless | 200, `products=1567`, `categories=471` | OK |
| Banco criado no diretório temporário | `/tmp/friboi-store.db` (não usa nem altera o `data/store.db` do projeto) | OK |
| Página `/` renderizando no serverless | 200, 59.504 bytes, com "Friboi" e "R$" | OK |
| Assets servidos por `public/` (CDN antes do rewrite) | 1.669 arquivos no `outputDirectory` | OK |

---

## 9. Veredito

**O clone está pronto para rodar e para ir ao Vercel.** Catálogo, imagens, login, cadastro,
carrinho e pedido funcionam de ponta a ponta com o nosso banco; nenhum asset depende da internet;
nenhum bug bloqueante foi encontrado nos 72 checks executados.

Limites conhecidos (não são bugs):

1. **Persistência no Vercel sem Postgres.** Sem `DATABASE_URL`, o SQLite vive em `/tmp` e é
   recriado a cada cold start — cadastro/pedido não sobrevive. Para loja real, configure
   `DATABASE_URL` (Neon). Ver `docs/VERCEL.md`.
2. **Preços.** Os 1.567 itens vêm com o preço de tabela do site original (R$ 9.999,00), porque
   a API pública não expõe o preço de venda. Use `data/prices.csv` +
   `scripts/update_prices.py` para aplicar os seus preços.
3. **Facetas da listagem.** O original filtra por MARCA/TEMPERATURA/TIPO DE PRODUTO; o clone
   filtra por disponibilidade, ordenação e categorias (os atributos existem no banco em
   `attrs_json`, a UI ainda não os expõe).
4. **Pagamento.** O checkout registra o pedido e o método escolhido (PIX/boleto/cartão), sem
   integração com gateway.
5. **Megamenu.** A navegação usa dropdown simples com até 12 filhos por categoria.
