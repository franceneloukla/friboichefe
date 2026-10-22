# DESIGN SPEC — Friboi Online (dossiê de reconstrução visual)

> **Origem de todos os dados:** captura real de `https://www.friboionline.com.br` feita com Playwright/Chromium
> (viewport 1440×900, locale `pt-BR`, `networkidle` + 6 s de espera para render client-side do Oracle Commerce Cloud).
> Nada aqui é estimado: todo valor em px/hex foi lido por `getComputedStyle`, `getBoundingClientRect`,
> `document.styleSheets` (CSSOM) ou por amostragem de pixel nos screenshots.
>
> **Quem usa:** T4 (front-end). Este documento vence o `CONTRATO.md` na parte visual.
> **Arquivos de apoio em `docs/CAPTURE/`:**
> `styles-home-1440.json`, `styles-categoria-detalhe.json`, `styles-pdp-detalhe.json`, `css-rules-home.json`
> (regras CSS que casam com cada elemento), `sections/*.html` (markup limpo de cada bloco da home),
> `components/*.html` (listagem e PDP), `screenshots/*.png`, `pages/*.html|txt`, `assets_map.json`.
>
> **Layout de referência:** `docs/CAPTURE/screenshots/home-1440.png` (= `_scratch/ref/ORIGINAL_HOME_1440.png`).

---

## 0. Resumo executivo (o que o clone precisa acertar de olhos fechados)

| Item | Valor real |
|---|---|
| Fundo da página | `#FFFFFF` |
| Header | **branco** (`#FFFFFF`), logo vermelho à esquerda, busca cinza `#EFEFEF` central, botão vermelho `#B5000B` 220×52 à direita |
| Nav | branca, 57 px de altura, links 15 px/500 `#102161` |
| Faixa de cupom | 53 px, **gradiente azul** `linear-gradient(90deg,#020024,#090979 55%,#07419E,#00D4FF)` |
| Hero | 1200×250 px, raio 6, bolinhas de 28 px (`#666` / ativa `#B5000B`) |
| Título de seção | 40 px, mistura **Roboto 900** + **Roboto Condensed 300**, cor `#0D0154` |
| Card de produto | 255×271 px, raio 8, borda 1 px `#EFEFEF`, badge `#0D174F`, nome 12 px/700 `#102161`, botão 35 px `#B5000B` raio 4 |
| Título de página (listagem) | 40 px/700 `#102161` |
| H1 da PDP | 44 px/900 `#0D0154` |
| Footer | `#0D174F`, 4 colunas de 320,75 px (gap 28), h3 13,3 px/800 uppercase com barra vermelha `#E30613` |
| CTA vermelho | `#B5000B` (botões) — o vermelho `#E30613` é **acento**, não CTA |
| Container | 1170 px (conteúdo 1140); hero e faixa de marcas usam 1200 px |
| Breakpoint estrutural | **≥ 1200 px = desktop**; ≤ 1199 px o site entrega outro template (compacto) |

Três armadilhas que quebram a fidelidade se ignoradas:

1. **O header NÃO é azul.** A captura de referência mostra header branco e faixa de cupom azul. Se você pintar o
   header de `#0D174F` o resultado diverge do original (ver §1.4 e §4.1).
2. **O header não é sticky de verdade.** No scroll o `.landing-wrapper` recebe a classe `no-top` e a linha
   superior (86 px) sai de cena; sobra só a nav de 57 px rolando junto com a página (ver §3.2).
3. **Dois vermelhos e dois azuis de texto coexistem.** `#B5000B` (CTA) ≠ `#E30613` (acento/ícone); `#102161`
   (texto de UI) ≠ `#0D0154` (títulos display). Trocar um pelo outro é o erro mais visível.

---

## 1. PALETA

### 1.1 Tokens extraídos do site (`:root` / `document.documentElement`)

O tema declara estas variáveis (lidas em `getComputedStyle(document.documentElement)`):

```css
:root {
  --azul-escuro:   #0d174f;   /* footer, badge de temperatura, gradiente dos benefícios */
  --azul-claro:    #2a62dd;   /* fim do gradiente dos benefícios, badge "desconto" */
  --vermelho:      #e30613;   /* acento: ícones, barra do footer, hover de redes sociais */
  --branco:        #fff;
  --primary-bg:    #0d174f;
  --accent-color:  #e30613;
  --text-color:    #fff;
  --max-width:     1280px;    /* largura máxima do .footer-container */
}
```

### 1.2 Tabela de cores (hex exato → onde)

| Token | Hex | Onde aparece (confirmado no CSSOM) |
|---|---|---|
| Azul institucional escuro | `#0D174F` | Fundo do footer (`.custom-footer`), badge "Congelado/Resfriado" (`.product-tag.temperatura`), início do gradiente dos 4 cards de benefício, `.promobar-container` (versão não usada) |
| Azul-marinho profundo | `#08086F` (média) / `#020129`→`#083798` | Faixa de cupom: gradiente `90deg` `#020024` 0% → `#090979` 55% → `#07419E` 100% → `#00D4FF` 100% (pixels conferidos: `#020129 / #080870 / #083798`) |
| Azul de texto/UI | `#102161` | Links da nav (15 px/500), nome do produto no card (12 px/700), `.label-cod`, título da listagem (`#cc-product-listing-title`), títulos dos acordeões da PDP (24 px/900), `price-label` |
| Azul display | `#0D0154` | Títulos de vitrine (40 px), H1 da PDP (44 px/900), `.price-now`, `Cód.:` da listagem (`#535276` é o valor do código) |
| Azul claro | `#2A62DD` | Fim do gradiente `linear-gradient(135deg,#0d174f 0,#2a62dd 100%)` dos cards de benefício; badge `.desconto` |
| **Vermelho CTA** | `#B5000B` | Botão "Login ou Cadastre-se" (220×52), botão "Ver Produto" (35 px), "VER PRODUTO" da listagem (232×34), "Consultar Preços" da PDP (520×48), setas do carrossel (40×40), bolinha ativa do hero, borda dos ícones de categoria |
| Vermelho acento | `#E30613` | Fundo do `.icon-wrapper` dos 4 benefícios, `border-left: 3px solid` dos h3 do footer, hover dos `.social-icon`, fundo do ícone "oferta da semana" na listagem |
| Verde estoque/oferta | `#00A239` | Badge `.oferta` (top 35 px, abaixo do badge de temperatura) |
| Verde "adicionado" | `#007700` | `.added-to-cart-message` (texto e borda 1 px) |
| Preto indisponível | `#000000` | Badge `.indisponivel` |
| Cinza borda clara | `#EFEFEF` | Borda de 1 px do `.product-card`; fundo do input de busca e do botão da lupa |
| Cinza borda 2 | `#E1E1E1` | Borda do botão de login (`#B5000B` com `border:1px solid #E1E1E1`) e do input de busca no CSS antigo |
| Cinza borda 3 | `#DDDDDD` | Borda dos painéis da sidebar de filtros |
| Cinza chip | `#F0F0F0` | Fundo dos `.info-item` ("Caixa:", "Peças:") |
| Cinza painel | `#F5F5F5` | Fundo do `.panel-heading` da sidebar (MARCA, TEMPERATURA…) |
| Cinza card listagem | `#F7F7F7` | Fundo declarado do `.cc-product-item` (na prática branco `#FFFFFF` por override) |
| Cinza texto 1 | `#333333` | Cor de texto padrão do `body` |
| Cinza texto 2 | `#495057` | Texto dos `.info-item` (8 px/500) |
| Cinza texto 3 | `#535276` | Texto "Cód.:" na listagem (`#CC-productListing`) |
| Cinza texto 4 | `#555555` | Texto digitado no input de busca |
| Cinza texto 5 | `#808080` | Ícone/texto do botão da lupa |
| Cinza bolinha inativa | `#666666` | Indicadores do hero (28×28, `border-radius:50px`) |
| Branco | `#FFFFFF` | Fundo geral, header, nav, texto sobre azul/vermelho |
| Hover escuro | `#9F0606` / `#8C000A` | Hover do `.category-item` / hover das setas do carrossel |

### 1.3 Combinações de contraste já usadas (copie, não reinvente)

- Texto branco sobre `#B5000B` → CTA principal.
- Texto branco sobre `#0D174F` → footer inteiro, badge de temperatura.
- Texto `#102161` sobre branco → nav, nome de produto, títulos de bloco.
- Texto `#0D0154` sobre branco → títulos display 40/44 px.
- Texto `#495057` sobre `#F0F0F0` → chips de metadados do card.
- Texto branco sobre gradiente azul → faixa de cupom (`<strong>` para "CADASTRE-SE E GANHE 5% DE DESCONTO").

### 1.4 Onde a cor é aplicada por `style` inline (não está em folha de estilo)

- Faixa de cupom: `style="background:linear-gradient(90deg, rgba(2,0,36,1) 0%, rgba(9,9,121,1) 55%, rgba(7,65,158,1) 100%, rgba(0,212,255,1) 100%); padding:1.0em"` no `.container` interno.
- Botão de login: `style="color: rgb(255,255,255); background-color: rgb(181, 0, 11); padding: 15px 15px 35px; border-radius: 6px; width: 220px;"`.
- Input de busca: `style="background-color:#efefef !important; height:50px; border:none; border-radius:6px"`.
- Botão da lupa: `style="background-color:#efefef !important; border:none; border-radius:6px; height:50px"` (imagem interna `width:38px`).
- Badge AMEX do footer: `style="background:#016fd0; border:1px solid #016fd0"`.

---

## 2. TIPOGRAFIA

### 2.1 Famílias reais (via `document.fonts` + `@font-face` do CSSOM)

1. **Roboto** — pesos 400, 700, 900 (+ itálicos), servida pelo Google Fonts.
   `font-family: Roboto, "Helvetica Neue", Helvetica, Arial, sans-serif` no `body`.
2. **Roboto Condensed** — pesos 300, 400, 700 (+ itálicos), Google Fonts.
   Usada nos títulos de vitrine (peso 300) e no botão "Consultar Preços" (18 px).
3. **Helvetica Neue** (@font-face local do site, `/file/thirdparty/fonts/*.woff2`) com os aliases
   `helveticaRegular`, `helveticaMedium`, `helveticaLight`, `helveticaBold`, `helveticaBlack`.
   Usada no botão de login (`font-family: helveticaBold`) e no input de busca (`font-family: Helvetica`).
4. `FontAwesome` e `Glyphicons Halflings` existem no tema mas **não são usados** na home —
   não baixe, o clone não precisa.

Arquivos locais baixados em `web/static/fonts/` (32 arquivos, 1,16 MB):
`roboto-{400,700,900}[-italic]-{latin,latin-ext}.woff2`,
`roboto-condensed-{300,400,700}[-italic]-{latin,latin-ext}.woff2`,
`helvetica-neue-{regular,light,medium,bold,condensed-bold}.woff2`, `helvetica-neue-caps-*.woff2`.
O `@font-face` do Google está em `web/static/css/google-fonts-roboto.css` (copie para o CSS do clone,
apontando as `url()` para `/assets/fonts/...`).

### 2.2 Escala tipográfica medida (1440 px)

| Elemento | Família | Tamanho | Peso | Line-height | Cor | Extras |
|---|---|---|---|---|---|---|
| `body` | Roboto | 14 px | 400 | 21 px | `#333333` | — |
| Título de vitrine — parte 1 (`span.titleText1`) | Roboto | 40 px | 900 | 21 px herdado (caixa do texto: 47 px) | `#0D0154` | `text-transform: capitalize` |
| Título de vitrine — parte 2 (`span.titleText2`) | Roboto Condensed | 40 px | 300 | 21 px herdado (caixa: 47 px) | `#0D0154` | `capitalize`; bloco `.cc-recommendations-title` com `margin-bottom:32px` |
| Título da listagem (`#cc-product-listing-title`) | Helvetica Neue/Roboto | 40 px | 700 | 1.1 | `#102161` | `margin:0 0 10px; margin-left:10%` |
| H2 da tela de login (`h2.friboi.instrucoes`) | Roboto | 40 px | 900 | 48 px | `#102161` | — |
| H1 da PDP (`.nome-produto`) | Roboto | 44 px | 900 | 52,8 px (1.2) | `#0D0154` | `capitalize`; largura da coluna 505 px |
| H2 dos acordeões da PDP | Roboto | 24 px | 900 | — | `#102161` | — |
| Nav (link) | Roboto | 15 px | 500 | 20 px | `#102161` | `padding: 15px 13px 15px 5px` |
| Nome do produto no card da home | Roboto | 12 px | 700 | 15,6 px | `#102161` | `capitalize`, 2 linhas com elipse |
| Nome do produto na listagem | Roboto | 16 px | 700 | 24 px | `#102161` | `.cc-text-overflow` (1 linha + ellipsis) |
| Código no card da home (`.label-cod`) | Roboto | 10 px | 700 | 21 px | `#102161` | `uppercase`, `letter-spacing:.5px` |
| Código na listagem (`.codigo` + valor) | Roboto | 12 px | 400 | 1.45em | `#535276` | prefixo "Cód.: " |
| Chips do card (`.info-item`) | Roboto | 8 px | 500 | 1 | `#495057` | fundo `#F0F0F0`, `padding:4px 8px`, raio 4 |
| Preço (`.price-now`) — hoje oculto nos cards | Roboto | 13 px | 700 | 21 px | `#0D0154` | `display:none` no card da home (cliente deslogado vê "Consultar Preços") |
| Preço rótulo (`.price-label`) | Roboto | 10,5 px | 700 | 21 px | `#102161` | texto "Por" |
| Botão "Ver Produto" (home) | Roboto | 14 px | 400 | 21 px | `#FFFFFF` | botão 35 px, raio 4 |
| Botão "VER PRODUTO" (listagem) | Roboto | 14 px | 400 | 20 px | `#FFFFFF` | botão 232×34, raio 6 |
| Botão "Consultar Preços" (PDP) | Roboto Condensed | 18 px | 400 | 20 px | `#FFFFFF` | botão 520×48, raio 0 |
| Botão "Login ou Cadastre-se" | helveticaBold | 14 px | 400 (span 600) | 20 px | `#FFFFFF` | 220×52, raio 6 |
| Input de busca | Helvetica | 14 px | 400 | 20 px | `#555555` | 565×50, raio 6 |
| Título da faixa de cupom | Roboto | 14 px | 400 (`<strong>` = 700) | 21 px | `#FFFFFF` | `letter-spacing` normal |
| Ícone de categoria (rótulo) | Roboto | 13 px | 600 | 21 px | `#B5000B` | `white-space:nowrap` |
| Nome de marca (`.brand-name`) | Roboto | 9 px | 700 | 21 px | `#333` (`--text-muted`) | `uppercase`, `letter-spacing:.15em`, `opacity:0` (só aparece no hover) |
| Card de benefício — título | Roboto | 14 px | 800 | 16,8 px | `#FFFFFF` | `capitalize` |
| Card de benefício — texto | Roboto | 10,5 px | 400 | 13,65 px (1.3) | `#FFFFFF` | `opacity:.9` |
| Footer — h3 de coluna | Roboto | 13,3 px (0.95rem) | 800 | 19,95 px | `#FFFFFF` | `uppercase`, `letter-spacing:.5px`, `border-left:3px solid #E30613`, `padding-left:12px` |
| Footer — `.section-title` (MEIOS DE PAGAMENTO / REDES SOCIAIS) | Roboto | 10 px | 800 | 21 px | `#FFFFFF` | `uppercase`, `letter-spacing:1px`, `opacity:.9` |
| Footer — link (`.footer-link`) | Roboto | 11,9 px (0.85rem) | 400 | 21 px | `#FFFFFF` | `opacity:.75`, `padding:.4rem 0` |
| Footer — copyright | Roboto | 9,8 px (0.7rem) | 400 | 21 px | `#FFFFFF` | `opacity:.5`, borda superior `rgba(255,255,255,.08)` |
| Badge do card (`.product-tag`) | Roboto | 8,4 px (`.6rem`) | 700 | 21 px | `#FFFFFF` | `capitalize`, `padding:0 8px` |
| Faixa "Adicionado ao Carrinho" | Roboto | 11,2 px | 700 | 15,68 px | `#007700` | borda 1 px `#007700`, raio 4 |

### 2.3 Regras de uso

- **Só duas famílias visíveis**: Roboto (quase tudo) e Roboto Condensed (título de vitrine + botão da PDP).
  "Helvetica Neue" é legado do tema OCC: aparece no botão de login e no input; pode ser substituída por Roboto
  com perda imperceptível, mas os `.woff2` já estão baixados se quiser fidelidade total.
- `strong` na faixa de cupom é 700; o resto do texto é 400. Não use 600/800 fora do footer.
- Escala display: **40 px** (títulos de seção e de listagem), **44 px** (H1 da PDP), **24 px** (subtítulos da PDP).
  Nunca use 32/36 px: não existem no original.
- `letter-spacing` só existe em três lugares: `.label-cod` (.5 px), `.brand-name` (.15em) e `.section-title` (1 px).

---

## 3. LAYOUT E MÉTRICAS

### 3.1 Containers (três larguras diferentes convivem na home — não unifique)

| Container | Largura | Onde | Observação |
|---|---|---|---|
| Página (`#page.container`) | 100% (1425 px de viewport com scrollbar) | wrapper de tudo | Bootstrap 3 com `*{box-sizing:border-box}` |
| Conteúdo padrão (`.container`) | **1170 px** (1140 px de conteúdo + 15 px de padding lateral) | header interno, banner final, PDP, benefícios, cards de marca | `.container { width:1170px; padding: 0 15px }` em ≥1200 px |
| Hero e faixa de marcas | **1200 px** | `.cc_heroWidget` (`max-width:1228px; padding:0 14px`), `.section-container` (`max-width:1200px`) | o hero é 30 px mais largo que o conteúdo padrão |

Coordenadas medidas em 1440 px (viewport útil 1425 px):

```
hero/carrossel      x=113  w=1200   → margem 113 de cada lado
faixa de marcas     x=113  w=1200
conteúdo padrão     x=143  w=1140   (benefícios, banner final, PDP)
shelf/vitrine       x=128  w=1170   → trilha de cards começa em x=178 (50 px de recuo p/ seta)
listagem: sidebar   x=0..356 ; coluna de produtos x=356 w=1069 (conteúdo 1039)
```

### 3.2 Header (86 px + 57 px = 143 px)

| Elemento | Medida | Observação |
|---|---|---|
| `header.landing-wrapper` | 1395×**143** px, `background:#fff` | `position:static`; `width:100vw` no CSS do widget |
| Linha da marca (`.container` interno) | 1140×**86** px | logo, busca, botão |
| Logo (`img.logo`) | **129×82** px, `object-fit:contain` | `margin-left:-36px; margin-top:-14px` (desloca o logo para a esquerda do bloco) |
| Busca (`input.search-query`) | **565×50** px, raio 6 | começa em x=315 (50 px depois do logo) |
| Botão da lupa | **67×50** px, raio 6, ícone 38 px | fundo `#EFEFEF` |
| Botão de login (`a.btn.login`) | **220×52** px, raio 6 | `margin-top:-2px`; alinhado à direita em x=958 |
| Nav (`nav.navbar.container.menu`) | 1140×**57** px, raio 4 | `padding:5px 15px 0 4px`; começa em y=86 |
| Nav lista (`ul.navbar-nav.color`) | 961×50 px | `li.nav-item` com 50 px de altura |

**Comportamento no scroll (importante):** o header **não é fixo**. Ao rolar, o JS adiciona a classe
`no-top` em `.landing-wrapper` e a linha da marca (86 px) sai do fluxo: a altura cai para **57 px**
(só a nav). Com `scrollY=300`, `header.top = -300` — ou seja, header e nav rolam junto com a página.
Regra para o clone: header estático no topo, 143 px de altura, colapsando para 57 px após ~200 px de scroll
(ou simplesmente estático — a diferença visual é mínima e não afeta a captura de 1440).

### 3.3 Ritmo vertical da home (y medido em 1440 px, documento de 3385 px)

| y | h | Bloco |
|---|---|---|
| 0 | 143 | header (86 marca + 57 nav) |
| 143 | 53 | faixa de cupom (`.container` com gradiente, `padding:14px`) |
| 206 | 250 | hero (4 slides, indicadores em y=472) |
| 506 | 153 | faixa de 9 categorias (`nav.nav-container`, raio 24, `padding:12px`) |
| 659 | 393 | vitrine "Negócios Como O Seu Compraram" |
| 1052 | 393 | vitrine "Sugestão Para O Seu Negócio" |
| 1445 | 504 | 6 cards de marca (3 linhas de 2, 560×224) |
| 1949 | 252 | par de banners extra (`C_5_pescado` + `C_6_batatas`) |
| 2201 | 433 | faixa de marcas (5 logos 200×340) |
| 2634 | 190 | 4 cards de benefício (160 px + padding do container) |
| 2824 | 211 | banner institucional final (1140×176) |
| 3035 | 350 | footer (`.custom-footer` 322 px) |

### 3.4 Faixa de cupom (53 px)

`.container` com `padding:1.0em` (14 px) e gradiente; dentro, `.row.text-center` de 25 px de altura com
ícone 25×25 + `<span>` (564 px) + link "Cadastre-se". Texto branco centralizado a partir de x=379.

### 3.5 Hero (carrossel)

- `.cc_heroWidget` 1228 px de largura (com `padding:0 14px`), `margin-top:10px`.
- `.carousel-inner` **1200×250**, `border-radius:6px`, `aspect-ratio:4.8`.
- 4 slides (`div.item`), imagens 1200×250 com `object-fit:contain`.
- Indicadores: `.carousel-indicators` com `bottom:-60px`, `li` **28×28**, `border-radius:50px`,
  `background:#666`, `margin:5px`; `.active` → **`#B5000B`**.
- CSS responsivo do widget: `@media (min-width:1025px) and (max-width:1257px){ min-height:calc(8.75vw) }`,
  `@media (min-width:1258px){ min-height:250px }`.

### 3.6 Faixa de categorias (9 ícones)

- `nav.nav-container`: 1152×153, `padding:12px`, `border-radius:24px`.
- `.category-list`: 1128×129, `padding:8px 4px`, **`gap:16px`**, `display:flex` sem quebra.
- `.category-item`: **100×113** px, `padding:8px`, `border-radius:8px`, `border:1px solid #B5000B`;
  os itens de rótulo longo crescem: "Batatas e Vegetais" = 126 px, "Bovinos Importados" = 133 px.
- `.icon-box`: **62×62**, `padding:5px`, `border-radius:12px`; a imagem dentro é **52×52**.
- `.category-name`: 13 px/600 `#B5000B`, `margin-bottom` implícito pelo `icon-box` (`margin-bottom:12px`).
- Hover: fundo `#9F0606`, texto branco, ícone `translateY(-4px)`.

### 3.7 Vitrines (carrossel horizontal)

- Bloco: título (`.cc-recommendations-title`, `margin-bottom:32px`) + carrossel (393 px de altura total).
- `.carousel-container.cc-recs-custom-carousel`: 1170×291, `gap:10px` (seta + trilha).
- `.carousel-wrapper` / `.product-carousel`: **1080 px** visíveis, `gap:15px`, `padding-bottom:20px`,
  `overflow-x:hidden`, `scroll-snap-type:x mandatory`.
- `.product-card`: **255×271** px, raio 8, `border:1px solid #EFEFEF`, `flex:0 0 255px`.
  Passo entre cards = 270 px (255 + 15) → **4 cards visíveis** por vez.
- Setas `.carousel-arrow`: **40×40**, círculo (`border-radius:50%`), fundo `#B5000B`,
  `box-shadow:0 2px 6px rgba(0,0,0,.2)`, ícone SVG 20×20 com `fill:#fff`; hover `#8C000A`.
  Em telas menores viram `position:absolute; top:-50px; width:35px; height:35px`.
- Composição interna do card (medidas absolutas):
  imagem 120×120 (`margin:10px auto`), `product-details` com `padding:10px`,
  código (21 px de altura), nome (16 px), chips (`gap:8px`), botão de 35 px no rodapé do card.

### 3.8 Cards de marca ("COMPRE AGORA")

- Grid de 2 colunas; cada card é **uma única imagem** (`img.img-responsive.border-6`) de **560×224**
  com raio 6 e `max-width:560px`; o texto ("Costela", "Picanha", … e o botão "COMPRE AGORA") está
  **queimado na imagem** — não há botão em HTML.
- Estrutura: 3 linhas de 2 cards (Costela/Picanha, Contra Filé/Coxão mole, Pescados/Batatas),
  `padding` de 15 px em cada célula (`.pd-15`) e `padding-top:2em` entre linhas; bloco total 504 px.

### 3.9 Faixa de marcas (5 logos)

- `.section-container` 1200 px; `.brands-grid` `display:flex; justify-content:space-around; padding:20px 0`.
- `.brand-item`: **220×393** px, `padding:10px`; `.brand-logo-container` 200×340;
  `img` **200×340** com `border-radius:8px` e `object-fit:contain`.
- `.brand-name` existe mas fica com `opacity:0` (aparece só no hover).
- Abaixo de 768 px o `.brands-grid` vira `display:none` e entra um carrossel (`.mobile-slider`).

### 3.10 4 cards de benefício

- `.container-beneficios` (1140 px) → `.beneficios-grid`:
  `display:grid; grid-template-columns:repeat(4,1fr); gap:20px` → **4 × 270 px**.
- `.card-beneficio`: **160 px** de altura mínima, `border-radius:16px`, `padding:16px`,
  `background:linear-gradient(135deg,#0d174f 0,#2a62dd 100%)`, `box-shadow:0 4px 15px rgba(0,0,0,.1)`,
  hover `translateY(-5px)`.
- `.icon-wrapper`: **32×32**, `border-radius:8px`, fundo **`#E30613`**, SVG branco 18×18 (`stroke-width:2.5`).
- Abaixo de 992 px: vira carrossel `flex:0 0 70%` com `scroll-snap-type:x mandatory`
  (`@media (min-width:992px)` é o que liga o grid de 4).

### 3.11 Banner institucional final

- `.container.centralizar` (1140) com `padding-bottom:2em`; `.carousel-inner` com 1 slide.
- Imagem desktop `institucional_friboi_1200x185.jpg` renderizada em **1140×176**, `border-radius:8px`.
- Existe variante mobile (`hidden-lg hidden-md`) de 384×168.

### 3.12 Footer

- `footer.custom-footer`: **`background:#0D174F`**, `color:#fff`, `padding:2.5rem 1rem 1rem 1rem`
  (medido: 35 px 14 px 14 px), `margin-top:2rem`, altura 322 px.
- `.footer-container`: `max-width:1280px; margin:0 auto`.
- `.footer-grid`: `display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:2rem` →
  **4 × 320,75 px com gap 28 px**.
- `.footer-column h3`: `border-left:3px solid #E30613`, `padding-left:12px`,
  `display:flex; justify-content:space-between` (o chevron só aparece no mobile).
- `.payment-item`: **44×28**, fundo branco, `padding:2px`, `border-radius:3px` (ícones são SVG inline).
- `.safety-badges-container`: `gap:8px`; `.safety-badge` fundo `rgba(255,255,255,.05)`,
  borda `1px solid rgba(255,255,255,.1)`, raio 6.
- `.social-icon`: **34×34**, `border-radius:8px`, fundo `rgba(255,255,255,.08)`, hover `#E30613`.
- `.copyright-bar`: `border-top:1px solid rgba(255,255,255,.08)`, `margin-top:2rem`, `padding-top:1rem`,
  texto centralizado 9,8 px com `opacity:.5`.
- No mobile (`<1024 px`) o grid vira 1 coluna e cada `.footer-column` vira acordeão
  (`onclick="toggleAccordion(this)"`, `h3` com chevron).

### 3.13 Página de listagem (`/category/{ID}`)

| Elemento | Medida |
|---|---|
| Banner da categoria (`#Bex_BannerMarcas`) | imagem **1270×117**, raio 6 |
| Breadcrumb (`#CC-breadcrumb-details`) | 1170 px de largura, faixa de 62 px, texto 12 px "INÍCIO > BOVINOS" |
| Sidebar (`#CC-guidedNavigation-column`) | **321 px** (a região tem 356 px); `hidden-xs` |
| Sidebar — bloco de filtro | `.panel-heading` fundo **`#F5F5F5`**, 353×48, `padding:10px 15px`, borda `#DDD`, raio 3 no topo |
| Sidebar — título do filtro (`h4`) | 13 px/700, `padding-bottom:5px` |
| Sidebar — item de filtro (`ul li a`) | 13 px/400, `padding:3px 15px`, cor de link do tema `#195D8D` |
| Título "REFINAR POR" | 13 px/700, `text-transform:uppercase` |
| Coluna de produtos (`#CC-productListing`) | **1039 px** |
| Grade | 3 colunas; cada `.cc-product-item` = **260×315**, `padding:0 15px`, `border:1px solid #EFEFEF`, fundo branco |
| Título da coleção (`#cc-product-listing-title`) | 40 px/700 `#102161`, `margin-left:10%` |
| Card — nome | 16 px/700 `#102161` (1 linha com ellipsis) |
| Card — código | 12 px/400, prefixo "Cód.: " em `#535276` |
| Card — metadados | `Caixa: 8kg a 12kg, 8 peças por caixa` (13–14 px, `#0D0154`) |
| Card — botão "VER PRODUTO" | **232×34**, fundo `#B5000B`, raio 6, borda 1 px `#B5000B` |
| Paginação | topo (em `#CC-product-listing-controls`, 159 px de altura) e base com `« < 1 2 3 4 5 > »` |
| Resultados por página | **12** (texto real: `Resultados: 1 - 12 (de 589)`) |
| Banner de categoria | fica acima do breadcrumb, largura total 1270 px |

### 3.14 Página de produto (PDP)

| Elemento | Medida |
|---|---|
| Faixa de cupom da PDP | 53 px, igual à home, link "Cadastrar Agora" |
| Breadcrumb | `INÍCIO / BOVINOS / DIANTEIRO / ACÉM` (12 px), 30 px de altura |
| `.container.con-prod` | **1140×832**, duas colunas (texto ~505 px / galeria ~560 px) |
| H1 (`.nome-produto`) | 44 px/900 `#0D0154`, largura 505 px |
| Linha "Caixa: 24 kg a 32 kg, 1 a 10 peças por caixa" | 14 px, `#0D0154` |
| Botão "Consultar Preços" | **520×48**, `#B5000B`, `border-radius:0`, Roboto Condensed 18 px |
| Galeria | imagem principal 560×560 e `.thumbnail` **113×108** (`padding:4px`, borda `#B5000B` na ativa) |
| Descrição | texto centralizado 14 px/21 px com o logo Friboi (marca d'água) ao centro |
| Acordeões (`.accordion.box`) | 3 blocos de 1140×105; cabeçalho `.card-header.borda-acima` 1140×73, título 24 px/900 `#102161`, seta circular 40×40 à direita |
| Títulos dos acordeões | "Informação Nutricional", "Entenda peso e preço final", "Embalagem e armazenamento" |

### 3.15 Breakpoints observados

| Faixa | Comportamento |
|---|---|
| **≥ 1200 px** | layout desktop completo (header de 143 px, 9 categorias, vitrines de 4 cards de 255 px, grid de benefícios 4×, footer 4 colunas, listagem 3 colunas + sidebar) |
| 1199 – 1151 px | o site **troca de template** (variante compacta): sem `.product-card` de 255 px, sem `.category-item`, sem `a.btn.login`, nav vira "Voltar/Home/Ofertas" |
| 1150 – 1024 px | variante compacta: hero 981×204, header 85 px, benefícios 4 colunas de 237 px |
| ≤ 1024 px | footer em 1 coluna (acordeão); `.footer-grid` troca para `1fr` |
| ≤ 992 px | `.beneficios-grid` volta a ser carrossel (`flex:0 0 70%`) |
| ≤ 978 px | `#cc-product-listing-title` centralizado (`margin-left:-10%`), indicadores do hero deslocados |
| ≤ 768 px | `.brands-grid` → `display:none` (entra `.mobile-slider`), `.promobar-container` 55 px, hero grid 2×1 |
| ≤ 480 px | cards `.cc-product-item` viram 2 por linha, título da listagem 25 px, hero com banners 800×350 |

**Medições em 1024 px (para conferência da versão compacta):**
header 85 px · hero **981×204** · 4 benefícios de **237 px** · faixa de marcas 1009 px de largura ·
listagem `/category/BOVINOS` mantém **3 colunas de 260×315** e sidebar de **219 px**.
Screenshot: `docs/CAPTURE/screenshots/home-1024.png` e `categoria-bovinos-1024.png`.

### 3.16 Grid resumido para o CSS do clone

```css
.container { width: 1170px; padding: 0 15px; margin: 0 auto; }          /* conteúdo 1140 */
.hero       { width: 1200px; margin: 0 auto; }                          /* 30px mais largo */
.brands     { max-width: 1200px; margin: 0 auto; }

.shelf-track { display:flex; gap:15px; }
.shelf-card  { flex:0 0 255px; width:255px; border:1px solid #efefef; border-radius:8px; }

.benefits-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:20px; width:1140px; margin:0 auto; }
.footer-grid   { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:28px; max-width:1280px; margin:0 auto; }
.listing-sheet { width:1039px; }   /* 3 colunas de 260 com 15px de padding */
.brand-row     { display:flex; justify-content:space-around; }
```

---

## 4. COMPONENTES — MARKUP DE REFERÊNCIA (recortado do DOM real)

> Todos os trechos abaixo saíram do DOM renderizado (`docs/CAPTURE/sections/*.html` e
> `docs/CAPTURE/components/*.html`) com comentários do Knockout removidos, URLs de asset trocadas por
> caminhos locais **somente nesta documentação**. No markup original os `src` apontam para
> `/ccstore/v1/images/?source=...` ou `/file/general/...` — no clone use os caminhos de `web/static/`
> (mapa completo em `docs/CAPTURE/assets_map.json` e §6).

### 4.1 Header (logo + busca + botão + nav)

Estrutura real (simplificada, mantendo classes e atributos que importam para o CSS):

```html
<header class="landing-wrapper">
  <div class="container">
    <div class="row bg_barra" id="navbar">
      <!-- coluna 1: logo -->
      <div class="col-md-1 barraMenu">
        <a id="logoFriboi" class="navbar-brand active" href="/">
          <div id="cc_img__resize_wrapper">
            <img class="logo" width="129" height="82" fetchpriority="high" alt="logo"
                 src="/assets/img/ui/logos/logo-friboi-online.png">
          </div>
        </a>
      </div>

      <!-- coluna 2: busca -->
      <div class="col-md-9 buscar">
        <form role="form">
          <div id="element-search2" class="col-xs-12 pull-right input-group search">
            <input autocomplete="off" class="form-control search-query hidden-xs hidden-sm" type="text"
                   placeholder="Busque aqui seu produto..." aria-label="Search"
                   style="background-color:#efefef !important;height:50px;border:none;border-radius:6px">
            <div id="u7020" class="ax_default icon">
              <button class="btnu7020" type="submit">
                <img id="u7020_img" class="img" src="/assets/img/ui/icones/icone-lupa-u7020.png"
                     width="14" height="14" alt="Buscar produto">
              </button>
            </div>
            <button class="btn btn-outline buscar" type="submit" aria-label="Pesquisar produtos"
                    style="background-color:#efefef !important;border:none;border-radius:6px;height:50px">
              <img src="/assets/img/ui/icones/icone-busca.png" class="icone-buscar" style="width:38px">
            </button>
          </div>
        </form>
      </div>

      <!-- coluna 3: login -->
      <div class="col-md-1 login hidden-xs">
        <a class="btn login" id="loginButtonRef" href="/login"
           style="color: rgb(255,255,255); background-color: rgb(181, 0, 11);
                  padding: 15px 15px 35px; border-radius: 6px; width: 220px;">
          <span>
            <img class="imgCarrinho" src="/assets/img/ui/icones/icone-utilizador.png"
                 loading="lazy" alt="Minha Conta" aria-hidden="true">
            Login ou Cadastre-se
          </span>
        </a>
      </div>
    </div>
  </div>

  <!-- nav desktop -->
  <nav class="navbar navbar-expand-lg navbar-light container menu">
    <div class="collapse navbar-collapse" id="navbarTogglerDemo01">
      <ul class="navbar-nav mr-auto color">
        <li class="nav-item">
          <a class="01 nav-link" data-toggle="dropdown" href="/category/BOVINOS">Bovinos</a>
        </li>
        <!-- … 10 itens iguais (ver §4.2) … -->
      </ul>
    </div>
  </nav>
</header>
```

Regras que sustentam esse markup:

```css
header.landing-wrapper { background:#fff; }              /* branco, não azul */
#navbar { align-items:center; margin:0; padding:0; }
img.logo { width:129px; height:82px; object-fit:contain; margin-left:-36px; margin-top:-14px; }
a.btn.login { background-color:#b5000b; color:#fff; border-radius:6px; width:220px;
              padding:15px 15px 35px; font-family:helveticaBold; border:1px solid #e1e1e1;
              display:inline-block; }
a.btn.login span { font-weight:600; }
input.search-query { width:565px; height:50px; background:#efefef; border:0; border-radius:6px;
                     font-family:Helvetica; font-size:14px; color:#555; padding:6px 12px; }
button.btn.buscar   { width:67px; height:50px; background:#efefef; border:0; border-radius:6px;
                      padding:6px 12px 6px 22px; }
```

### 4.2 Nav de categorias (11 itens, larguras medidas)

```html
<ul class="navbar-nav mr-auto color">
  <li class="nav-item"><a class="01 nav-link" href="/category/BOVINOS">Bovinos</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/BOVINOS_IMPORTADOS">Bovinos Importados</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/AVES">Aves</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/SUINOS">Suínos</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/PESCADOS">Pescados</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/BATATAS_E_VEGETAIS">Batatas e Vegetais</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/CORDEIROS">Cordeiros</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/CHARQUE">Charques</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/Outros_Produtos">Outros</a></li>
  <li class="nav-item"><a class="menuPromo"  href="/category/Promocao_Oferta">Promoções</a></li>
  <li class="nav-item"><a class="01 nav-link" href="/category/MARCAS">Marcas</a></li>
</ul>
```

Larguras reais dos `li` em 1440 px (soma 961 px): 72 · 153 · 51 · 64 · 84 · 144 · 84 · 82 · 63 · 96 · 68.
Cada `li` tem **50 px** de altura; o link tem `padding:15px 13px 15px 5px`, 15 px/500, `#102161`.
O item "Promoções" usa a classe `.menuPromo` (14 px/600, `padding:10px 18px`, cor `#000`).
Cada `li` pode abrir um mega-menu (`.dropdown-menu.level1Menu`, `.Level2`, `.Level3`) — no clone basta
o link direto; o mega-menu é opcional e não aparece no screenshot de referência.

### 4.3 Faixa de cupom

```html
<div class="container" style="background:linear-gradient(90deg, rgba(2,0,36,1) 0%,
     rgba(9,9,121,1) 55%, rgba(7,65,158,1) 100%, rgba(0,212,255,1) 100%); padding:1.0em">
  <div class="row text-center">
    <img src="/assets/img/ui/icones/icone-desconto.png" width="25" height="25"
         style="max-width:25px" alt="Desconto">
    <span style="color:#FFFFFF;font-family:'Roboto','Helvetica Neue',Helvetica,Arial,sans-serif">
      <strong>CADASTRE-SE E GANHE 5% DE DESCONTO</strong> na primeira compra com o cupom PCFRIBOI5.
    </span>
    <a href="/login" style="text-decoration:underline;color:#FFFFFF;">Cadastre-se</a>
  </div>
</div>
```

Altura final **53 px** (`padding:1em` + linha de 25 px). Sem `border-radius`. Texto centralizado.

### 4.4 Hero carousel

```html
<div class="cc_heroWidget" style="margin-top:10px; padding-left:14px; padding-right:14px;">
  <div class="carousel slide" id="this-carousel-id">
    <ol class="carousel-indicators">
      <li class="active" id="indicator_id_0"></li>
      <li id="indicator_id_1"></li>
      <li id="indicator_id_2"></li>
      <li id="indicator_id_3"></li>
    </ol>
    <div class="carousel-inner" style="border-radius:6px;">
      <div class="item active" id="img_id_0">
        <a href="/categoria/promocoes">
          <img style="width:100%;height:auto;aspect-ratio:1200/250;object-fit:contain"
               width="1200" height="250" class="img-responsive center-block"
               src="/assets/img/ui/hero/hero-1-institucional.jpg" alt="">
        </a>
      </div>
      <div class="item" id="img_id_1"> … Bnn_Comodato_Desktop_1920x400_V4.jpg … </div>
      <div class="item" id="img_id_2"> … B_PIX.png … </div>
      <div class="item" id="img_id_3"> … B_supergelados_16.09.jpg … </div>
    </div>
  </div>
</div>
```

```css
.carousel-inner { width:1200px; height:250px; border-radius:6px; aspect-ratio:4.8; }
.carousel-indicators { bottom:-60px; }
.carousel-indicators li { display:inline-block; width:28px; height:28px; margin:5px;
                          background-color:#666; border:0; border-radius:50px; }
.carousel-indicators .active { width:28px; height:28px; margin:5px;
                               background-color:#b5000b; border-radius:50px; }
```

### 4.5 Grid de categorias com ícones

```html
<div class="wrapper">
  <nav class="nav-container">
    <div class="category-list">
      <a href="/categoria/bovinos" class="category-item">
        <div class="hover-bg"></div>
        <div class="icon-box">
          <img src="/assets/img/ui/categorias/cat-bovinos.png" alt="Bovinos" width="52" height="52">
        </div>
        <span class="category-name">Bovinos</span>
        <div class="indicator"></div>
      </a>
      <!-- Aves, Suínos, Pescados, Batatas e Vegetais, Cordeiros, Charque, Bovinos Importados, Promoções -->
    </div>
  </nav>
</div>
```

```css
.nav-container { padding:12px; border-radius:24px; }
.category-list { display:flex; gap:16px; padding:8px 4px; overflow-x:auto; scrollbar-width:none; }
.category-item { display:flex; flex-direction:column; align-items:center; justify-content:center;
                 min-width:100px; padding:8px; border-radius:8px; border:1px solid #b5000b;
                 position:relative; overflow:hidden; text-decoration:none; }
.category-item:hover { background-color:#9f0606; }
.icon-box { margin-bottom:12px; padding:5px; border-radius:12px; }
.icon-box img { width:52px; height:52px; object-fit:contain; }
.category-name { font-size:13px; font-weight:600; color:#b5000b; white-space:nowrap; }
.category-item:hover .category-name { color:#fff; }
```

### 4.6 Card de produto (home) — a estrutura exata

```html
<div class="product-card">
  <div class="product-tag temperatura">congelado</div>
  <div class="product-image-container">
    <a id="cc-product-detail-374492" title="batata palito 9mm pacote (2kg) - do chef"
       href="/product/batata-palito-9mm-pacote-2kg-do-chef-vegetal-congelado/374492">
      <div id="cc_img__resize_wrapper">
        <img src="/img/products/374492/main.jpg" alt="BATATA PALITO 9MM PACOTE (2KG) - DO CHEF (374492)">
      </div>
    </a>
  </div>
  <div class="product-details">
    <div class="product-code-tag"><span class="label-cod">CÓD. 374492</span></div>
    <h3 class="product-name">batata palito 9mm pacote (2kg) - do chef</h3>
    <div class="product-info-grid">
      <div class="info-item">Caixa: 10kg</div>
      <div class="info-item">Peças: 5</div>
    </div>
    <div class="product-pricing" style="display:none;">   <!-- preço: oculto p/ deslogado -->
      <div class="price-now-wrapper">
        <span class="price-label">Por</span>
        <span class="price-now">R$9.999,00</span><span>/kg</span>
      </div>
    </div>
    <div class="product-pricing">
      <button class="ver-produto-btn" aria-label="Ver Produto">
        <p>Ver Produto</p>
      </button>
    </div>
  </div>
  <div class="added-to-cart-message" id="message-cart-374492">Adicionado ao Carrinho</div>
</div>
```

Medidas e regras:

```css
.product-card { background:#fff; border-radius:8px; width:255px; min-width:255px; flex-shrink:0;
                position:relative; display:flex; flex-direction:column; overflow:hidden;
                border:1px solid #efefef; scroll-snap-align:start; }
.product-tag { position:absolute; top:10px; right:10px; padding:0 8px; font-size:.6rem;
               font-weight:700; color:#fff; text-transform:capitalize; z-index:10; }
.product-tag.temperatura { background-color:#0d174f; }
.product-tag.oferta      { background-color:#00a239; top:35px; }
.product-tag.indisponivel{ background-color:#000000; top:35px; }
.product-tag.desconto    { background-color:#2a62dd; top:10px; }
.product-image-container { width:120px; height:120px; max-width:120px; max-height:120px;
                           margin:10px auto; display:flex; align-items:center; justify-content:center; }
.product-image-container img { width:100%; height:100%; object-fit:contain; }
.product-details { padding:10px; display:flex; flex-direction:column; flex-grow:1; }
.product-code-tag { display:flex; gap:4px; font-size:10px; font-weight:500;
                    letter-spacing:.5px; text-transform:uppercase; color:#102161; }
.label-cod { font-size:10px; font-weight:700; color:#102161; letter-spacing:.5px; }
.product-name { font-size:12px; font-weight:700; color:#102161; line-height:1.3;
                text-transform:capitalize; overflow:hidden; text-overflow:ellipsis; }
.product-info-grid { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:5px; }
.info-item { display:flex; align-items:center; gap:4px; font-size:8px; color:#495057; font-weight:500;
             background-color:#f0f0f0; padding:4px 8px; border-radius:4px; line-height:1; }
.ver-produto-btn { background-color:#b5000b; color:#fff; border:none; border-radius:4px;
                   padding:8px 16px; height:35px; width:100%; cursor:pointer; }
.ver-produto-btn p { margin:0; font-size:14px; }
.added-to-cart-message { display:none; font-size:11.2px; font-weight:700; color:#007700;
                         border:1px solid #007700; border-radius:4px; padding:10px; }
```

> **Atenção ao conteúdo do card:** `CÓD. {sku}` em maiúsculas com ponto; nome em `capitalize`
> (o CSS transforma "BATATA PALITO…" em "Batata Palito…"); `Caixa: {min}kg a {max}kg` e `Peças: {n}`
> em chips separados; quando min = max o original mostra **`Caixa: 10kg`** (sem "a").

### 4.7 Vitrine com setas (carrossel horizontal)

```html
<div id="cc-recs">
  <div class="row">
    <div class="cc-recommendations-title" aria-live="polite">
      <span class="titleText1">negócios</span>
      <span class="titleText2">como o seu compraram</span>
    </div>
  </div>
  <div class="cc-recommendations-carousel-slide" data-interval="false">
    <div class="carousel-container cc-recs-custom-carousel">
      <button type="button" class="carousel-arrow prev-arrow" aria-label="Anterior">
        <svg class="arrow-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M13.5 3 6.5 10l7 7z"></path></svg>
      </button>
      <div class="carousel-wrapper-container">
        <div class="carousel-wrapper">
          <div class="product-carousel">
            <!-- 8 × .product-card (§4.6) -->
          </div>
        </div>
      </div>
      <button type="button" class="carousel-arrow next-arrow" aria-label="Próximo">
        <svg class="arrow-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M6.5 3l7 7-7 7z"></path></svg>
      </button>
    </div>
  </div>
</div>
```

```css
.cc-recommendations-title { margin-bottom:32px; }
.titleText1 { font-family:'Roboto'; font-size:40px; font-weight:900; text-transform:capitalize; color:#0d0154; }
.titleText2 { font-family:'Roboto Condensed'; font-size:40px; font-weight:300;
              text-transform:capitalize; color:#0d0154; }
.carousel-container { display:flex; align-items:center; gap:10px; }
.carousel-wrapper { overflow-x:hidden; width:1080px; }
.product-carousel { display:flex; gap:15px; padding-bottom:20px; }
.carousel-arrow { background:#b5000b; border:none; border-radius:50%; width:40px; height:40px;
                  display:flex; align-items:center; justify-content:center; cursor:pointer; flex-shrink:0;
                  box-shadow:0 2px 6px rgba(0,0,0,.2); }
.carousel-arrow:hover { background-color:#8c000a; }
.arrow-icon { width:20px; height:20px; fill:#fff; }
```

> Detalhe de fidelidade: o título é **duas palavras em estilos diferentes** na mesma linha —
> "Negócios" (Roboto 900) + "Como O Seu Compraram" (Roboto Condensed 300). `capitalize` faz o resto.

### 4.8 Cards de marca ("COMPRE AGORA")

```html
<div class="container pt-20">
  <div class="pd-15 banner-categorias">
    <div class="pd-15 categoria-1">
      <a href="/categoria/bovinos-costelas">
        <img src="/assets/img/ui/cards-marca/card-costela.jpg" class="img-responsive border-6"
             alt="Costela" width="560" height="224" style="max-width:560px">
      </a>
    </div>
    <div class="pd-15 categoria-2">
      <a href="/categoria/bovinos-picanha">
        <img src="/assets/img/ui/cards-marca/card-picanha.png" class="img-responsive border-6"
             alt="Picanha" width="560" height="224" style="max-width:560px">
      </a>
    </div>
  </div>
  <div class="pt-20 pd-15 banner-categorias"> … card-contrafile.png + card-coxao-mole.png … </div>
</div>
```

Só mais um par (Pescados/Batatas) vem em outro widget (`.banner-divulgacao`), com as imagens
`card-pescados.png` e `card-batatas.png`. Regra: `.border-6 { border-radius:6px }`, `.pt-20 { padding-top:2em }`,
`.pd-15 { padding-left:15px; padding-right:15px }`.

### 4.9 Faixa de marcas

```html
<section class="section-container">
  <div class="brands-grid">
    <div class="brand-item">
      <div class="brand-logo-container">
        <a href="/categoria/marcas-friboi">
          <img src="/assets/img/ui/marcas/marca-friboi.jpg" width="200" height="340" alt="Friboi">
        </a>
      </div>
      <span class="brand-name">Friboi</span>
    </div>
    <!-- Do Chef, Maturatta, Black Friboi, 1953 -->
  </div>
</section>
```

```css
.section-container { width:100%; max-width:1200px; margin:0 auto; }
.brands-grid { display:flex; justify-content:space-around; align-items:center; padding:20px 0; }
.brand-item { display:flex; flex-direction:column; align-items:center; padding:10px; width:220px; }
.brand-logo-container { width:100%; display:flex; align-items:center; justify-content:center; }
.brand-item img { max-width:100%; max-height:100%; object-fit:contain; border-radius:8px; }
.brand-name { margin-top:12px; font-size:9px; font-weight:700; text-transform:uppercase;
              letter-spacing:.15em; opacity:0; }
.brand-item:hover .brand-name { opacity:1; }
```

### 4.10 Os 4 cards de benefício (CSS + SVG inline — não são imagens)

```html
<div class="container-beneficios">
  <div class="beneficios-grid">
    <div class="card-beneficio">
      <div class="icon-wrapper">
        <svg viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path><line x1="7" y1="7" x2="7.01" y2="7"></line></svg>
      </div>
      <h3 class="beneficio-titulo">descontos exclusivos</h3>
      <p class="beneficio-texto">Toda semana produtos com descontos exclusivos no site.</p>
    </div>
    <div class="card-beneficio">
      <div class="icon-wrapper">
        <svg viewBox="0 0 24 24"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
      </div>
      <h3 class="beneficio-titulo">frete grátis</h3>
      <p class="beneficio-texto">Receba gratuitamente em seu estabelecimento comercial.</p>
    </div>
    <div class="card-beneficio">
      <div class="icon-wrapper">
        <svg viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"></rect><line x1="2" y1="10" x2="22" y2="10"></line></svg>
      </div>
      <h3 class="beneficio-titulo">pague no cartão</h3>
      <p class="beneficio-texto">Melhore o seu fluxo de caixa realizando compras no cartão.</p>
    </div>
    <div class="card-beneficio">
      <div class="icon-wrapper">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
      </div>
      <h3 class="beneficio-titulo">compre quando quiser</h3>
      <p class="beneficio-texto">Pedidos disponíveis 24hs por dia, todos os dias da semana.</p>
    </div>
  </div>
</div>
```

```css
.beneficios-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:20px; }
.card-beneficio { min-height:160px; border-radius:16px; padding:16px; color:#fff;
                  display:flex; flex-direction:column; border:none;
                  background:linear-gradient(135deg,#0d174f 0,#2a62dd 100%);
                  box-shadow:0 4px 15px rgba(0,0,0,.1); transition:transform .3s ease; }
.card-beneficio:hover { transform:translateY(-5px); }
.icon-wrapper { background-color:#e30613; width:32px; height:32px; border-radius:8px;
                display:flex; align-items:center; justify-content:center; margin-bottom:8px; }
.icon-wrapper svg { width:18px; height:18px; fill:none; stroke:#fff; stroke-width:2.5;
                    stroke-linecap:round; stroke-linejoin:round; }
.beneficio-titulo { font-weight:800; font-size:1rem; margin:0 0 4px 0; text-transform:capitalize;
                    line-height:1.2; color:#fff; }
.beneficio-texto { font-size:.75rem; opacity:.9; line-height:1.3; margin:0; color:#fff; }
```

> Os SVGs prontos estão em `web/static/img/ui/svg/beneficio-1.svg` … `beneficio-4.svg`.

### 4.11 Banner institucional final

```html
<div class="container centralizar" style="padding-bottom:2.0em;">
  <div class="row pt-20 pd-15">
    <div id="carousel-institucional" class="carousel slide">
      <ol class="carousel-indicators"></ol>
      <div class="carousel-inner" role="listbox">
        <div class="item active">
          <a href="/categoria/marcas-friboi">
            <img src="/assets/img/ui/banners/banner-institucional.jpg"
                 class="border-8 hidden-sm hidden-xs" alt="Marca Friboi" style="max-width:1140px;">
            <img src="/assets/img/ui/banners/banner-institucional-mobile.jpg"
                 class="border-8 hidden-lg hidden-md" alt="Marca Friboi" width="384" height="168">
          </a>
        </div>
      </div>
    </div>
  </div>
</div>
```

### 4.12 Footer completo

```html
<footer class="custom-footer">
  <div class="footer-container">
    <div class="footer-grid">

      <div class="footer-column" onclick="toggleAccordion(this)">
        <h3>Acesso Rápido
          <svg class="chevron lg-hidden" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2"><path d="m6 9 6 6 6-6"></path></svg>
        </h3>
        <nav class="footer-content">
          <a href="/login" class="footer-link">Login ou Cadastre-se</a>
          <a href="/unidades" class="footer-link">Unidades de Atendimento</a>
          <a href="https://boleto.jbs.com.br/" target="_blank" class="footer-link">Segunda via Boleto</a>
          <a href="https://docs.google.com/forms/d/e/…/viewform" target="_blank" class="footer-link">Exclusão/Cancelamento de Conta</a>
          <a href="/Entregas" class="footer-link">Entregas</a>
        </nav>
      </div>

      <div class="footer-column" onclick="toggleAccordion(this)">
        <h3>Nossas Marcas <svg class="chevron lg-hidden" …></svg></h3>
        <nav class="footer-content">
          <a href="/categoria/marcas-friboi" class="footer-link">Friboi</a>
          <a href="/categoria/marcas-maturatta" class="footer-link">Maturatta</a>
          <a href="/categoria/marcas-do-chef" class="footer-link">Do Chef</a>
          <a href="/categoria/marcas-black-friboi" class="footer-link">Black Friboi</a>
          <a href="/categoria/marcas-1953" class="footer-link">1953</a>
        </nav>
      </div>

      <div class="footer-column" onclick="toggleAccordion(this)">
        <h3>A FRIBOI <svg class="chevron lg-hidden" …></svg></h3>
        <nav class="footer-content">
          <a href="/quemsomos" class="footer-link">Nossa História</a>
          <a href="/politicaprivacidade" class="footer-link">Política de Privacidade</a>
          <a href="/politica-de-cookies" class="footer-link">Política de Cookies</a>
          <a href="/sitemap" class="footer-link">Mapa do Site</a>
          <a href="/faq" class="footer-link">FAQ</a>
        </nav>
      </div>

      <div class="flex flex-col gap-8">
        <div>
          <span class="section-title">Meios de Pagamento</span>
          <div class="flex flex-wrap gap-2 mb-4">
            <div class="payment-item" title="Boleto"> …svg boleto… </div>
            <div class="payment-item" title="PIX"><span class="pix-label">PIX</span></div>
            <div class="payment-item" title="Visa"> …svg visa… </div>
            <div class="payment-item" title="Mastercard"> …svg mastercard… </div>
            <div class="payment-item" style="background:#016fd0;border:1px solid #016fd0"
                 title="American Express"><span class="amex-text">AMEX</span></div>
          </div>
          <div class="safety-badges-container">
            <div class="safety-badge"> …svg escudo verde… <span class="badge-title">GOOGLE</span><span class="badge-subtitle">Safe Browsing</span></div>
            <div class="safety-badge"> …svg cadeado dourado… <span class="badge-title">SITE 100%</span><span class="badge-subtitle">SEGURO</span></div>
          </div>
        </div>
        <div>
          <span class="section-title">Redes Sociais</span>
          <div class="flex gap-2">
            <a href="https://www.instagram.com/friboibrasil/" class="social-icon" aria-label="Instagram"> …svg… </a>
            <a href="https://www.facebook.com/Friboi" class="social-icon" aria-label="Facebook"> …svg… </a>
            <a href="https://www.youtube.com/user/AlimentosFriboi" class="social-icon" aria-label="YouTube"> …svg… </a>
          </div>
        </div>
      </div>

    </div>
    <div class="copyright-bar">
      <p>© 2026 JBS Friboi. Todos os direitos reservados. CNPJ 02.916.265/0027-07</p>
    </div>
  </div>
</footer>
```

```css
.custom-footer { background-color:#0d174f; color:#fff; padding:2.5rem 1rem 1rem 1rem; margin-top:2rem; }
.footer-container { max-width:1280px; margin:0 auto; }
.footer-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:2rem; }
.footer-column h3 { font-size:.95rem; font-weight:800; margin-bottom:1.2rem; padding-left:12px;
                    text-transform:uppercase; letter-spacing:.5px; display:flex;
                    justify-content:space-between; border-left:3px solid #e30613; }
.footer-link { color:#fff; text-decoration:none; padding:.4rem 0; display:block;
               font-size:.85rem; opacity:.75; }
.footer-link:hover { opacity:1; padding-left:6px; border-left:2px solid #e30613; }
.section-title { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:1px;
                 opacity:.9; display:block; margin-bottom:.8rem; }
.payment-item { background:#fff; padding:2px; border-radius:3px; width:44px; height:28px;
                display:flex; align-items:center; justify-content:center; overflow:hidden; }
.safety-badge { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1);
                border-radius:6px; padding:6px 10px; display:inline-flex; gap:6px; }
.social-icon { background:rgba(255,255,255,.08); width:34px; height:34px; border-radius:8px;
               display:flex; align-items:center; justify-content:center; }
.social-icon:hover { background:#e30613; transform:translateY(-2px); }
.copyright-bar { border-top:1px solid rgba(255,255,255,.08); margin-top:2rem; padding-top:1rem;
                 text-align:center; font-size:.7rem; opacity:.5; }
```

> **O footer não tem logo Friboi** no original. Não invente um.

### 4.13 Listagem — markup real (arquivos completos em `components/`)

- Sidebar de filtros: `docs/CAPTURE/components/categoria-guided.html` (25 KB, classes
  `.storefront-sidenav`, `.panel-heading`, `h4`, `ul li a`, "REFINAR POR").
- Controles/paginação do topo: `categoria-controls.html`.
- Card da listagem: `categoria-firstitem.html`.
- Paginação inferior: `categoria-paginated.html`.
- Banner de categoria e breadcrumb: `categoria-banner.html`, `categoria-breadcrumb.html`.

Card da listagem (resumo fiel):

```html
<div class="cc-product-item col-xs-6 col-sm-3" style="border:1px solid #efefef;background:#fff">
  <span class="product-tag temperatura">Congelado</span>
  <div class="col-md-2 col-xs-3 cc-item-detail">
    <img class="img-responsive" src="/img/products/350337/main.jpg" title="PICANHA (ABAIXO DE 1,35KG) - BLACK FRIBOI (350337)">
  </div>
  <div class="texto-div">
    <div class="cc-item-code">
      <span class="codigo" style="font-size:12px;font-weight:400;background:#fff;color:#535276">Cód.: </span>
      <span style="font-size:12px">350337</span>
    </div>
    <div class="cc-item-title">
      <a href="/produto/picanha-abaixo-de-1-35kg-black-friboi-bovino-congelado">
        <p class="cc-text-overflow" style="text-align:left">Picanha (abaixo De 1,35kg) - Black Friboi</p>
      </a>
    </div>
    <span class="p3 text-color-neutral-1" style="color:#0d0154">
      Caixa: 8kg a 12kg, 8 peças por caixa
    </span>
  </div>
  <div class="col-md-3 col-xs-4 pull-right">
    <a class="btn btn-default comprar" href="/produto/…">VER PRODUTO</a>
  </div>
</div>
```

Diferenças em relação ao card da home (não unifique os dois!):
`Cód.:` (com dois-pontos e espaço) em vez de `CÓD.`; metadados em **uma linha** separada por vírgula;
botão "VER PRODUTO" em maiúsculas, 232×34, raio 6; card 260×315 com borda `#EFEFEF`; paginação de 12 em 12.

### 4.14 PDP — markup real (arquivos completos em `components/`)

- `.container.con-prod`: `pdp-conprod.html` (22 KB)
- Acordeões: `pdp-accordion.html` (14 KB)
- Breadcrumb: `pdp-breadcrumb.html`
- Faixa de cupom da PDP: `pdp-cupom.html`

```html
<div class="container con-prod">
  <div class="col-md-6">                             <!-- coluna de texto (505 px) -->
    <h1 class="text-color-neutral-1 nome-produto">Acém Completo - Friboi - Congelado</h1>
    <p>Caixa: 24 kg a 32 kg, 1 a 10 peças por caixa</p>
    <button class="btn-lg btn-primary btn-radius-0">Consultar Preços</button>
  </div>
  <div class="col-md-6">                             <!-- galeria -->
    <img class="img-responsive" src="/img/products/507/main.jpg">
    <div class="thumbnails"><div class="thumbnail"><img src="…"></div>…</div>
  </div>
</div>
<div class="accordion box">
  <div class="container">
    <div class="card-header borda-acima" id="headingOne">
      <h2>Informação Nutricional</h2>
      <button class="btn"><svg …seta circular…></svg></button>
    </div>
    <div class="card-body"> …tabela nutricional… </div>
  </div>
</div>
```

---

## 5. COPY REAL (texto exato de cada seção)

### 5.1 Header

- Placeholder da busca: `Busque aqui seu produto...`
- Botão de login: `Login ou Cadastre-se` (quando logado o site troca por menu de conta; no clone: `Minha conta` + `Sair`)
- Nav: `Bovinos` · `Bovinos Importados` · `Aves` · `Suínos` · `Pescados` · `Batatas e Vegetais` · `Cordeiros` · `Charques` · `Outros` · `Promoções` · `Marcas`

### 5.2 Faixa de cupom

> **CADASTRE-SE E GANHE 5% DE DESCONTO** na primeira compra com o cupom PCFRIBOI5. [Cadastre-se]

(`PCFRIBOI5` em maiúsculas, sem destaque de cor no desktop; o link "Cadastre-se" é sublinhado e branco.)

### 5.3 Hero (4 banners, texto queimado na imagem)

1. `Pague rápido e fácil com PIX` / `Mais opções. Mais facilidade.` / `O Friboi Online aceita cartão de crédito, boleto (com opção de parcelamento*) e agora PIX` / `Aproveite e faça suas compras!` / `*Para clientes aptos a comprar nessa modalidade.`
2. Banner de comodato (`Bnn_Comodato_Desktop_1920x400_V4.jpg`) — sem link.
3. Banner PIX (`B_PIX.png`).
4. Banner de supergelados (`B_supergelados_16.09.jpg`).

### 5.4 Categorias (9 rótulos)

`Bovinos` · `Aves` · `Suínos` · `Pescados` · `Batatas e Vegetais` · `Cordeiros` · `Charque` · `Bovinos Importados` · `Promoções`

### 5.5 Títulos das vitrines

- Vitrine 1: `Negócios Como O Seu Compraram` (`titleText1` = "negócios", `titleText2` = "como o seu compraram")
- Vitrine 2: `Sugestão Para O Seu Negócio`

### 5.6 Card de produto (rótulos fixos)

- Badge de temperatura: `Congelado` / `Resfriado`
- Código: `CÓD. {sku}` (home) e `Cód.: {sku}` (listagem)
- Metadados: `Caixa: {min}kg a {max}kg` e `Peças: {n}` (home, dois chips);
  `Caixa: {min}kg a {max}kg, {n} peças por caixa` (listagem, uma linha)
- Botão: `Ver Produto` (home) / `VER PRODUTO` (listagem)
- Feedback de carrinho: `Adicionado ao Carrinho`

Produtos reais da vitrine 1 (ordem da captura):

| CÓD. | Nome | Caixa | Peças |
|---|---|---|---|
| 374492 | Batata Palito 9mm Pacote (2kg) - Do Chef | 10kg | 5 |
| 370933 | Costela Do Traseiro (Minga) Com Osso - Do Chef | 14kg a 31kg | 2 a 5 |
| 389793 | Batata Palito 9mm Pacote (1,05kg) - Do Chef | 11kg a 12kg | 10 |
| 85 | Acém Completo - Friboi | 8kg a 35kg | 1 a 3 |
| 355390 | Peito - Friboi | 20kg a 30kg | 2 a 12 |
| 111 | Cupim B - Friboi | 18kg a 32kg | 3 a 15 |
| 507 | Acém Completo - Friboi | 16kg a 32kg | 1 a 10 |
| 387549 | Contra Filé Pedaços - Do Chef | 18kg a 30kg | 10 a 20 |

Vitrine 2: 358698 (Acém Completo - Friboi, 12kg a 32kg, 1 a 12), 4950 (Acém Completo Fracionado - Friboi,
20kg a 30kg, 15 a 20), 354857 (Lagarto - 1953, 22kg a 31kg, 6 a 16), 1024 (Alcatra Completa (Acima De 6,8kg)
- Do Chef, 14kg a 31kg, 1 a 3), 8791 (Filé De Merluzão Sem Pele Interfolhado - Do Chef, 10kg, 1),
25 (Coxão Duro - Friboi, 18kg a 28kg, 2 a 8), 1440 (Acém Fracionado - Friboi, 20kg a 30kg, 15 a 20),
383188 (Acém Com Pescoço - Do Chef, 13kg a 33kg, 1 a 3).

### 5.7 Cards de marca (texto queimado nas imagens)

- `BOVINOS / Costela` — "Textura suculenta e um sabor profundo. Ricos em colágeno e gorduras, são ideais para receitas gastronômicas memoráveis, seja em cortes inteiros ou na churrasco de domingo." + botão `COMPRE AGORA`
- `BOVINOS / Picanha` — "Sabor e maciez premium para churrascarias e restaurantes, atendendo paladares mais exigentes." + `COMPRE AGORA`
- `BOVINOS / Contra Filé` — "Versátil, nobre e suculento. Garanta sabor e rendimento para o seu cardápio." + `COMPRE AGORA`
- `BOVINOS / Coxão mole` — "Carne magra e macia, ideal para assados, guisados e pratos em larga escala no seu restaurante." + `COMPRE AGORA`
- `PESCADOS / Pescados` — "Versatilidade de peixes e frutos do mar para compor pratos e receitas com excelência." + `COMPRE AGORA`
- `VEGETAIS / Batatas` — "Acompanhamento essencial no food service. Batatas selecionadas e líderes em qualidade." + `COMPRE AGORA`

### 5.8 Faixa de marcas

`FRIBOI` · `DO CHEF` · `MATURATTA` · `BLACK FRIBOI` · `1953` (rótulos em uppercase, 9 px, só no hover)

### 5.9 4 cards de benefício

| Título (como está no HTML, lowercase) | Texto |
|---|---|
| `descontos exclusivos` | Toda semana produtos com descontos exclusivos no site. |
| `frete grátis` | Receba gratuitamente em seu estabelecimento comercial. |
| `pague no cartão` | Melhore o seu fluxo de caixa realizando compras no cartão. |
| `compre quando quiser` | Pedidos disponíveis 24hs por dia, todos os dias da semana. |

O CSS aplica `text-transform: capitalize` → na tela aparece "Descontos Exclusivos", "Frete Grátis", etc.

### 5.10 Banner institucional final (texto na imagem)

> **Friboi. Primeiro lugar na cabeça e no prato dos brasileiros.**
> Mais terceiro ano consecutivo, Friboi é a marca mais lembrada na categoria de carnes do Top of Mind de Folha.

### 5.11 Footer

- `ACESSO RÁPIDO`: Login ou Cadastre-se · Unidades de Atendimento · Segunda via Boleto · Exclusão/Cancelamento de Conta · Entregas
- `NOSSAS MARCAS`: Friboi · Maturatta · Do Chef · Black Friboi · 1953
- `A FRIBOI`: Nossa História · Política de Privacidade · Política de Cookies · Mapa do Site · FAQ
- `MEIOS DE PAGAMENTO`: Boleto · PIX · Visa · Mastercard · AMEX + selos `GOOGLE / Safe Browsing` e `SITE 100% / SEGURO`
- `REDES SOCIAIS`: Instagram · Facebook · YouTube
- Copyright: `© 2026 JBS Friboi. Todos os direitos reservados. CNPJ 02.916.265/0027-07`

### 5.12 Listagem

- Breadcrumb: `INÍCIO > BOVINOS` (na PDP: `INÍCIO / BOVINOS / DIANTEIRO / ACÉM`)
- Título: nome da coleção (`Bovinos`, `Promoções`, …)
- Contador: `Resultados: 1 - 12 (de 589)`
- Filtros (título `REFINAR POR`): `MARCA` (FRIBOI, 1953 FRIBOI, DO CHEF, BLACK FRIBOI, MATURATTA, TERCEIROS, BORDON, ANGLO),
  `TEMPERATURA` (CONGELADO, RESFRIADO), `TIPO DE PRODUTO (ORIGEM)` (BOVINO, INDUSTRIALIZADO, OVINO),
  `SUBGRUPO DA FAMÍLIA` (CONTRA FILE, FILE DE COSTELA, FILE MIGNON, CORAÇÃO DA ALCATRA, PICANHA, FRALDA, PEITO,
  COXÃO MOLE, COSTELA JANELA, LAGARTO) + link `+ Ver mais`
- Paginação: `«` `‹` `1 2 3 4 5` `›` `»`

### 5.13 Login e Cadastro (rotas reais)

- `/login` — duas colunas: `Já tenho um cadastro` (esquerda) e `Cadastrar empresa` (direita).
  - Esquerda: `Informe os dados de acesso da sua empresa.` · `E-mail/Telefone` · `Senha` · `Esqueci senha ou e-mail` ·
    `Entrar` · `Lembrar e-mail nos próximos acessos`
  - Direita: `Crie uma conta com o CNPJ da sua empresa e aproveite uma variedade de produtos da melhor qualidade,
    com entregas rápidas e rastreáveis, diferentes opções de pagamento, descontos e vantagens exclusivas.` ·
    `Acesso apenas para empresas do segmento de Food Service e Varejistas do ramo alimentício` · `Pedido mínimo de 40kg` ·
    botão `Ir para o cadastro`
- **Não existe rota `/cadastro`.** O cadastro é um wizard em modal sobre `/login`:
  1. Termos: `Li e aceito os termos de utilização da plataforma de vendas da Friboi.` +
     erro `É necessário aceitar os termos de uso para dar continuidade no processo.` + botões `RETORNAR` / `CONTINUAR`
  2. Dados da empresa: aviso `Atenção: Serão permitidos somente cadastros de CNPJs do ramo alimentício.
     Todos os cadastros de CNPJs não pertencentes à este grupo, serão rejeitados/bloqueados sem aviso prévio.` +
     campos `CNPJ:` e `Inscrição Estadual:` + botões `CANCELAR` / `PROSSEGUIR`
  Screenshots: `docs/CAPTURE/screenshots/cadastro-etapa1-termos.png` e `cadastro-etapa2-cnpj.png`.
  Para o clone: use a rota própria `/cadastro` do contrato e replique o **visual** (duas colunas + formulário),
  não o fluxo modal.
- Carrinho real: `/cart` (não `/carrinho`); checkout: `/checkout` (`Pagamento`, 28 px/800 `#0D0154`).
  O `/carrinho` do site retorna 404 — o clone usa `/carrinho` por contrato.

### 5.14 PDP (produto 507 — Acém Completo - Friboi - Congelado)

- `Cód.: 507` · `Caixa: 24 kg a 32 kg, 1 a 10 peças por caixa` · botão `Consultar Preços`
- Descrição (texto real):
  > Corte localizado no dianteiro, possui sabor característico, rico em colágeno, muito utilizado em preparos de longa
  > cocção do dia a dia como: cozidos, ensopados, refogados, tiras e carne moída.
  > Corte vai com miolo do acém, pescoço e costelinha do dianteiro (sem osso).
  > Tipologias: Restaurantes comerciais, Lanchonetes · Tipo de Corte: Acém - Dianteiro · Apresentação / Embalagem:
  > IWP - Folha Plástica · Conservação / Armazenamento: Congelado
  > Origem: Bovino | Quantidade Mínima da Caixa: 1 | Quantidade Máxima da Caixa: 10
  > Tempo de vida do produto: 360 dias
- Acordeões: `Informação Nutricional` · `Entenda peso e preço final` · `Embalagem e armazenamento`

---

## 6. MAPA DE ASSETS E PATCHES

### 6.1 Estrutura local (tudo servido por `/assets` → `web/static`)

```
web/static/
├── img/ui/
│   ├── logos/        9 arquivos   (logo header, favicon, logos de marca)
│   ├── categorias/   9 arquivos   (1 ícone por categoria → .category-item)
│   ├── hero/         8 arquivos   (4 banners em resolução original + 4 recortes 1200×250)
│   ├── cards-marca/  6 arquivos   (C_1…C_6: Costela, Picanha, Contra Filé, Coxão mole, Pescados, Batatas)
│   ├── marcas/      10 arquivos   (5 logos 200×340 + 5 banners de marca "desktop")
│   ├── beneficios/   4 arquivos   (banners 585×150 legados — a home usa SVG/CSS)
│   ├── banners/      5 arquivos   (banner institucional 1140×176, variante mobile, espetinhos, topo, menu)
│   ├── icones/       6 arquivos   (lupa, lupa-u7020, utilizador, user, user-active, desconto)
│   └── svg/         15 arquivos   (4 ícones de benefício, 2 setas de carrossel, 3 SVGs de pagamento,
│                                   2 selos de segurança, 3 redes sociais, seta do acordeão do footer)
├── fonts/           32 arquivos   (Roboto 400/700/900 + Roboto Condensed 300/400/700, latin e latin-ext,
│                                    com itálicos; Helvetica Neue regular/light/medium/bold/condensed)
├── css/              6 arquivos   (style.css, base.css, common.css, storefront-ie.css,
│                                    inline-widgets.css, google-fonts-roboto.css)
```

**Totais:** 110 arquivos, **5,5 MB** em `web/static/` (72 em `img/ui`, 32 em `fonts`, 6 em `css`).
`docs/CAPTURE/assets_map.json` tem **78 entradas** `{url_original: caminho_local}` — verificado: 100% dos
caminhos apontados existem em disco.

### 6.2 Principais correspondências URL → arquivo local

| URL original (resumo) | Arquivo local |
|---|---|
| `/ccstore/v1/images/?source=/file/general/logo-friboionline-completo-v2.png&height=82&width=129` | `img/ui/logos/logo-friboi-online.png` |
| `/file/general/Favicon-friboionline.png` | `img/ui/logos/favicon.png` |
| `/ccstore/v1/images/?source=/file/general/icone-bovinos.png&height=52&width=52` | `img/ui/categorias/cat-bovinos.png` |
| `…/icone-aves-2.png` · `icone-suinos.png` · `icone-pescados-2.png` · `icone-batatas.png` · `icone-cordeiro.png` · `icone-charque-2.png` · `icone-bovinosimportado.png` · `icone-promo.png` | `img/ui/categorias/cat-{aves,suinos,pescados,batatas-e-vegetais,cordeiros,charque,bovinos-importados,promocoes}.png` |
| `/file/general/B_Institucional_17.10.jpg` | `img/ui/hero/hero-1-institucional.jpg` (+ variante `-1200x250.jpg`) |
| `/file/general/Bnn_Comodato_Desktop_1920x400_V4.jpg` | `img/ui/hero/hero-2-comodato.jpg` |
| `/file/general/B_PIX.png` | `img/ui/hero/hero-3-pix.png` |
| `/file/general/B_supergelados_16.09.jpg` | `img/ui/hero/hero-4-supergelados.jpg` |
| `/file/general/C_1_Costela.jpg` … `C_6_batatas.png` | `img/ui/cards-marca/card-{costela,picanha,contrafile,coxao-mole,pescados,batatas}.{jpg,png}` |
| `/file/general/marca_friboi.jpg` … `marca_1953.jpg` | `img/ui/marcas/marca-{friboi,do-chef,maturatta,black-friboi,1953}.jpg` |
| `/file/general/institucional_friboi_1200x185.jpg` | `img/ui/banners/banner-institucional.jpg` |
| `/ccstore/v1/images/?source=/file/general/icon-desconto.png&height=25&width=25` | `img/ui/icones/icone-desconto.png` |
| `/file/general/icone-buscar.png` | `img/ui/icones/icone-busca.png` |
| `/file/v5831035920288673452/css/base.css?occsite=siteUS` | `css/base.css` |
| `/css/style.css?bust=26.10` | `css/style.css` |
| `https://fonts.gstatic.com/…/*.woff2` (24 arquivos Latin/Latin-ext) | `fonts/roboto-*.woff2`, `fonts/roboto-condensed-*.woff2` |
| `/file/thirdparty/fonts/helveticaneue-*.woff2` (9 URLs) | `fonts/helvetica-neue-*.woff2` |

### 6.3 Achados e correções — LEIA ANTES DE RECAPTURAR

1. **Formato real ≠ extensão (28 arquivos).** O CDN do site serve **AVIF** (e alguns WebP/JPEG) em URLs
   terminadas em `.jpg`/`.png` (parâmetro `outputFormat=AVIF`). Baixados crus, esses arquivos **não renderizam**
   como `<img>` quando o nome/Content-Type não bate — na home isso deixava a faixa de marcas como bloco de cor.
   O Lead normalizou os arquivos com `scripts/normalize_assets.py`. **Depois de qualquer nova captura, rode:
   `python3 scripts/normalize_assets.py`.** Verificado ao final: 100% dos `.jpg` em `web/static/img/ui` são JPEG
   e 100% dos `.png` são PNG.
2. **SVGs “falsos” removidos.** A colheita de ícones inline gerou 3 arquivos que eram fragmentos HTML
   (`<span class="pix-label">`, `<span class="amex-text">`, `<span class="navbar-toggler-icon"></span>`),
   não SVG. Foram **apagados** de `img/ui/svg/`:
   `menu-mobile-hamburger.svg`, `pagamento-pix-texto.svg`, `pagamento-american-express-texto.svg`.
   PIX e AMEX devem ser recriados com CSS/texto (ver §4.12) — não há SVG para eles no original.
   Os 15 SVGs restantes são válidos (começam com `<svg`).
3. **Assets que NÃO existem no original** (404 no próprio site, não invente): `/file/general/icon-login.png`,
   `/file/general/usuario-do-perfil-active.png`, `/file/thirdparty/fonts/HelveticaNeueCondensedBlack.woff2`
   (o alias `helveticaBlack` cai no fallback do navegador).
4. **Elo e Google Pay não existem** no rodapé do original. Os meios de pagamento reais são Boleto, PIX, Visa,
   Mastercard e AMEX, mais os selos "Google Safe Browsing" e "Site 100% Seguro". Se o contrato pedir Elo/Google Pay,
   desenhe-os como SVGs novos e registre a diferença.
5. **O footer não tem logo Friboi.** O logo aparece só no header (129×82) e queimado nos banners de marca.
6. **Hero tem duas versões de cada banner**: a original (1920×400 etc.) e o recorte servido ao browser
   (`?height=250&width=1200`). Use a variante `-1200x250` se quiser exatamente o enquadramento da captura;
   use a original se preferir nitidez em telas 2×.
7. **Imagens de produto não estão em `web/static`** — vêm do scraper em `data/images/products/{id}/main.jpg`
   e são servidas por `/img/products/...`. As URLs do original são
   `/ccstore/v1/images/?source=/file/v<versão>/products/{sku}_00_<slug>.<ext>&height=120&width=120&outputFormat=AVIF`.
8. As posições/quantidades acima valem para a captura de **2026-10-21**. O site troca banners semanalmente
   (há `barra_top_blackweek_friboi.jpg`, `Banner-Divulgacao_Espetinhos_Do_Chef.jpg` no pacote), então o conteúdo
   do hero muda; o layout não.

### 6.4 CSS de referência (consulta, não usar cru)

| Arquivo | Bytes | Para que serve |
|---|---|---|
| `css/style.css` | 135.518 | tema OCC completo (Bootstrap 3 + tema) |
| `css/base.css` | 168.409 | customizações da marca (`.row.bg_barra`, `img.logo`, `a.btn.login`, `button.btn.buscar`) |
| `css/common.css` | 195 | widget base OCC |
| `css/storefront-ie.css` | 265 | fallback IE |
| `css/inline-widgets.css` | 116.173 | **o mais útil**: todos os `<style>` inline dos widgets da home, com as regras exatas de `.product-card`, `.ver-produto-btn`, `.beneficios-grid`, `.custom-footer`, `.brands-grid`, `.carousel-arrow`, `.titleText1/2` |
| `css/google-fonts-roboto.css` | — | `@font-face` do Roboto/Roboto Condensed (troque as `url()` por `/assets/fonts/...`) |

O clone **não deve importar** esses arquivos: use-os como fonte de verdade para copiar regras pontuais
para `server/static/css/app.css` (T4).

### 6.5 Checklist de fidelidade (para o T5 validar)

- [ ] Header branco de 143 px: logo 129×82 à esquerda, busca `#EFEFEF` de 565×50 central, botão `#B5000B` 220×52 à direita.
- [ ] Faixa de cupom de 53 px com gradiente azul e o texto `PCFRIBOI5` sublinhado em "Cadastre-se".
- [ ] Hero 1200×250, raio 6, 4 bolinhas de 28 px (ativa vermelha).
- [ ] Faixa de 9 categorias com quadrados de 100×113, borda `#B5000B`, raio 8, ícones 52×52, rótulo 13 px/600.
- [ ] Duas vitrines com título bicolor 40 px e 4 cards de 255 px visíveis + setas circulares vermelhas de 40 px.
- [ ] Card com badge `Congelado` (`#0D174F`), `CÓD.`, nome 12 px/700 `#102161`, chips `Caixa:`/`Peças:`, botão vermelho 35 px.
- [ ] 6 cards de marca 560×224 em 3 linhas de 2 (imagens com "COMPRE AGORA" queimado).
- [ ] Faixa de 5 marcas 200×340 (Friboi, Do Chef, Maturatta, Black Friboi, 1953).
- [ ] 4 cards de benefício com gradiente `#0D174F`→`#2A62DD`, raio 16, ícone em quadrado vermelho `#E30613` 32×32.
- [ ] Banner institucional 1140×176 raio 8.
- [ ] Footer `#0D174F` com 4 colunas de 320,75 px, h3 com barra vermelha `#E30613`, 5 meios de pagamento,
      2 selos, 3 redes sociais e copyright `© 2026 JBS Friboi…`.
- [ ] Tipografia: Roboto + Roboto Condensed carregadas localmente de `/assets/fonts/` (nenhum request a fonts.googleapis.com).
- [ ] Nenhum `src`/`href` de asset apontando para `https://www.friboionline.com.br` (exceto links de navegação).
