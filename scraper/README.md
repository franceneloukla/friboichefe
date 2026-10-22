# Scraper — Catálogo Friboi Online

Extrai **100% do catálogo** de `https://www.friboionline.com.br` (Oracle Commerce Cloud)
e baixa **1 imagem por produto** (600×600), gravando tudo em `data/` no formato de
`docs/CONTRATO.md`.

O site está atrás de Akamai: `curl` e `python-requests` levam **timeout**. Por isso tudo é
feito dentro de uma página real do Chromium via **Playwright** (`fetch` na própria página),
que compartilha TLS/cookies/fingerprint do browser.

## Requisitos

- Python 3.11+ com **Playwright** e o Chromium do Playwright instalado (cache padrão).
- **Pillow** apenas para a fase `resize` (opcional, mas recomendada).
- Neste projeto o Playwright está no **python3 do sistema** (o `.venv` não tem playwright).
  Se preferir isolar: `python3 -m venv .venv && .venv/bin/pip install playwright pillow`.

## Como rodar

Sempre a partir da raiz do projeto:

```bash
cd <raiz do projeto>

# tudo: catálogo + imagens + resize + stats
python3 scraper/scrape_catalog.py

# só o catálogo (7 páginas de 250 = 1567 produtos)
python3 scraper/scrape_catalog.py --phase catalog

# só as imagens (usa data/catalog.json + data/_image_index.json)
python3 scraper/scrape_catalog.py --phase images --workers 5

# segunda passada só nas imagens que faltaram (recomendado se o site bloquear)
python3 scraper/scrape_catalog.py --phase images --workers 2 --only-missing

# padronizar imagens já baixadas em 600x600 (Pillow)
python3 scraper/scrape_catalog.py --phase resize

# recalcular images[]/stats a partir do que está no disco
python3 scraper/scrape_catalog.py --phase finalize
```

Rodando em background (recomendado, são ~1600 requisições de imagem):

```bash
nohup python3 scraper/scrape_catalog.py --phase all --workers 5 > data/run_all.log 2>&1 &
tail -f data/run_all.log
```

### Flags

| flag | efeito |
|---|---|
| `--phase all\|catalog\|images\|resize\|finalize` | fase a executar (default `all`) |
| `--workers N` | abas paralelas na fase de imagens (default 5; use 2 se o site bloquear) |
| `--limit N` | itens por página da API (default 250) |
| `--width N` / `--height N` | dimensão da imagem (default 600×600; ver nota abaixo) |
| `--force` | ignora cache/checkpoint e refaz tudo |
| `--only-missing` | imagens: só produtos sem `main.jpg` no disco |
| `--max-pages N` / `--max-images N` | DEBUG: limita o trabalho |
| `--headed` | abre o Chromium visível (debug) |
| `--base-url` | outro host (default `https://www.friboionline.com.br`) |

## Saídas

```
data/catalog.json                    catálogo no formato de docs/CONTRATO.md
data/images/products/{id}/main.jpg   1 imagem por produto (600x600, JPEG)
data/images_missing.json             produtos sem imagem (com motivo)
data/catalog_stats.json              contagens, bytes, MB, tempo e distribuição de preço
data/scrape.log                      log completo da execução
data/_checkpoint.json                checkpoint da paginação
data/_checkpoint_images.json         progresso do download
data/_image_index.json               id -> URL da imagem (usado para retomar)
data/_raw/products-XXXXX.json        cache bruto de cada página (~28 MB, ver data/.gitignore)
```

## Como retomar (checkpoint)

Cada página baixada é gravada em `data/_raw/` e o offset é salvo em `data/_checkpoint.json`
**antes** de avançar. Se o processo morrer (timeout, Ctrl-C, queda de rede), basta repetir o
mesmo comando: as páginas já baixadas saem do cache e a paginação continua de onde parou.

As imagens usam o próprio disco como checkpoint: `main.jpg` existente com mais de 500 bytes é
pulado, então repetir `--phase images` só baixa o que falta. O progresso agregado fica em
`data/_checkpoint_images.json`.

Para refazer do zero: `python3 scraper/scrape_catalog.py --force --phase all`
(ou apague `data/_checkpoint.json` e `data/_raw/`).

## Resiliência

- Paginação: 5 tentativas por página com backoff exponencial (2s → 45s) + jitter.
- Home/Akamai: até 4 tentativas abrindo o Chromium.
- Imagens: 4 tentativas por imagem (1s, 2s, 4s + jitter).
- Bloqueio progressivo: após 6 falhas consecutivas o script aumenta o delay entre requisições;
  após 20 falhas consecutivas ele aborta e orienta rodar `--phase images --workers 2 --only-missing`
  (o progresso fica no disco, nada é perdido).
- Produto sem `primaryMediumImageURL` é pulado e listado em `data/images_missing.json`.

## Detalhes da API usada

| dado | endpoint |
|---|---|
| catálogo | `GET /ccstore/v1/products?limit=250&offset=N` (`totalResults=1567`) |
| categorias | `GET /ccstore/v1/collections/{ID}` (`displayName` + `categoryIdPaths`) |
| imagem | `GET /ccstore/v1/images/?source=<source do item>&height=600&width=600` |

Todas as chamadas são feitas com `page.evaluate("async () => fetch(...)")`; as imagens voltam
como `data:` URL (FileReader → base64) e são gravadas em disco.

## Imagens: por que `height` + `width`

`/ccstore/v1/images/?source=...&width=600` (só `width`) é **ignorado** pelo OCC: ele devolve o
asset original (1000×1000, ~90 KB). A API só redimensiona quando recebe `width` **e** `height`
juntos — com `&height=600&width=600` vem 600×600 (~16 KB). O scraper já monta a URL com os dois.

A fase `--phase resize` existe para normalizar imagens que tenham sido baixadas grandes: ela
reduz o que estiver acima da dimensão alvo (preservando proporção, via `thumbnail` do Pillow),
pula o que já está no tamanho e não faz upscale. É idempotente.

## Formato do catálogo (resumo)

`data/catalog.json` = `{scraped_at, total, categories[], products[]}`.
Campos por produto: `id, sku, name, slug, route, brand, category_id, category_name,
category_path, price, sale_price, unit, ean, weight_min, weight_avg, weight_max, stock,
max_qty, description_html, video_url, nutrition, attrs{x_MARCA, x_LINHA, x_TEMPERATURA,
x_recomendadoPara}, images[{file}]`.

- `price` = `listPrices.padrao`; `sale_price` = `salePrices.padrao`. **Fiel à API:** 1566 itens
  vêm com o valor de tabela `9999.0` (o próprio site exibe `R$ 9.999,00` na vitrine) e 1 item
  (`389279`) vem sem preço (`price: null`) — reportado em `catalog_stats.json`
  (`price_9999`, `price_null`, `price_null_ids`). Nenhum preço é inventado.
- `unit` = `x_cSgUnidadeMedida` (`KG`/`CX`).
- `stock` = `Disponível` se qualquer campo `stock_*` do item for `Disponível`.
- `nutrition` = itens `x_iItem_1..21` normalizados (`"PROTEINAS: 18 g (36 %)"`).
- `slug` é único (o contrato pede UNIQUE): quando dois SKUs compartilham o mesmo
  `seoUrlSlugDerived`, o duplicado vira `<slug>-<id>`. O `route` original é preservado.
- `category_id`/`category_path` vêm de `parentCategoryIdPath` (categoria primária do produto no
  OCC), com os segmentos-sentinela `rootCategory`/`nonNavigableCategory` removidos.
- `images[].file` é relativo a `data/images` (`products/{id}/main.jpg`).

## Stats

`data/catalog_stats.json` inclui `products`, `categories`, `images`, `bytes`, `elapsed_s`,
`scraped_at` (contrato) e extras úteis: `products_with_image`, `products_without_image`,
`images_mb`, `image_dimensions_max`, `sale_price_not_null`, `price_9999`, `price_null`,
`price_null_ids`, `price_distinct_values`, `failed_downloads`, `aborted`.
