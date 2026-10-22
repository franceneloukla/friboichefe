# Deploy no Vercel

O projeto já está no GitHub (`franceneloukla/friboichefe`) e o repositório tem
tudo o que o Vercel precisa: `vercel.json`, `api/index.py`, `requirements.txt`
e o build que monta os assets estáticos em `public/`.

## 1. Como o deploy funciona aqui

```
public/            → servido como estático pelo CDN do Vercel
   assets/         ← web/static      (logo, ícones, banners, fontes)
   static/         ← server/static   (app.css, app.js)
   img/products/   ← data/images/products (1.557 fotos)
                      gerado por scripts/build_vercel.py no buildCommand

api/index.py       → função Python (FastAPI ASGI) que responde todo o resto
```

- `vercel.json` → `buildCommand: python3 scripts/build_vercel.py`,
  `outputDirectory: public`, e `rewrites: /(.*) → /api/index`.
- O Vercel serve **primeiro** os arquivos estáticos de `public/` e só cai na
  função quando o caminho não é um arquivo — por isso `/assets/...`,
  `/static/...` e `/img/products/...` nunca passam pela função.
- A função recebe `server/**` + `data/catalog.json` (`includeFiles`), então o
  bundle fica pequeno (~2,3 MB) e as fotos são servidas pelo CDN.

## 2. Banco de dados: os três cenários

| Cenário | `DATABASE_URL` | Comportamento | Serve para |
|---|---|---|---|
| Produção | Postgres (Neon/Supabase/Vercel Postgres) | persistente, log `postgres:<host>/<db>` | loja real |
| Preview | ausente | SQLite em `/tmp/friboi-store.db`; o seed roda a cada cold start | testar layout |
| Local | ausente | SQLite em `data/store.db` | desenvolvimento |

Com Postgres, o primeiro acesso cria as tabelas e popula **1.567 produtos** a
partir de `data/catalog.json` (leva alguns segundos, só na primeira vez).

### Criar o Postgres no Neon (grátis)

1. <https://neon.tech> → *New Project* → copie a connection string
   (`postgresql://user:senha@ep-xxx.neon.tech/neondb?sslmode=require`).
2. No Vercel: **Project → Settings → Environment Variables** → `DATABASE_URL`
   com essa string, nos ambientes *Production* e *Preview*.
3. Redeploy. Confirme em `/api/health`: o campo `db` deve mostrar
   `postgres:<host>/<banco>`.

## 3. Deploy pelo CLI

```bash
# na raiz do projeto
vercel login            # ou: vercel --token SEU_TOKEN
vercel link             # cria/liga o projeto "friboichefe"
vercel env add DATABASE_URL production     # cole a string do Neon
vercel env add SECRET_KEY production       # valor aleatório longo
vercel --prod
```

## 4. Deploy pelo painel (sem CLI)

1. <https://vercel.com/new> → **Import Git Repository** → `franceneloukla/friboichefe`.
2. Framework Preset: **Other**. Build Command e Output Directory já vêm do
   `vercel.json` — não mexa.
3. Environment Variables: `DATABASE_URL` (e `SECRET_KEY`, recomendado).
4. **Deploy**.

## 5. Variáveis de ambiente

| Variável | Obrigatória | Default | Para que serve |
|---|---|---|---|
| `DATABASE_URL` | em produção | — | Postgres; sem ela o Vercel usa SQLite em `/tmp` |
| `.python-version` (arquivo) | sim | `3.12` | fixa o CPython do build; sem isso o Vercel usa 3.14 e as wheels de `pydantic-core`/`psycopg2` não existem |
| `SECRET_KEY` | recomendada | valor de dev | assinatura do JWT — troque em produção |
| `SEED_ON_INIT` | não | `1` | popula o banco automaticamente se estiver vazio |
| `DEV_MODE` | não | `0` | `1` cria o admin de teste `admin@loja.local` |
| `CATALOG_PATH` | não | `data/catalog.json` | caminho alternativo do catálogo |
| `DB_PATH` | não | `data/store.db` | caminho do SQLite local |

## 6. Conferir depois do deploy

```bash
curl -s https://SEU-PROJETO.vercel.app/api/health
# {"status":"ok","db":"postgres:...","products":1567,"ok":true,"categories":471,"templates":true}
```

Se `products` vier 0, o seed não rodou: confira se `data/catalog.json` subiu
(`includeFiles`) e se `SEED_ON_INIT` não está `0`.

## 7. Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| 404 em `/assets/...` | `public/` vazio no deploy | veja o log do build: `scripts/build_vercel.py` tem que imprimir "1.672 arquivos" |
| 500 em toda página | template fora do bundle | confirme `includeFiles: "{server/**,data/catalog.json,data/seed.db}"` |
| `Internal Server Error` na primeira visita | timeout do seed com Postgres lento | aumente `maxDuration` em `vercel.json` (60 → 120) ou rode o seed uma vez |
| Cadastro "some" depois de um tempo | sem `DATABASE_URL` (SQLite efêmero) | conecte o Neon |
| `pg_config executable not found` | `psycopg2` tentando compilar por falta de wheel | mantenha `.python-version` = `3.12`. O driver Postgres fica em `requirements-postgres.txt` e **não** entra no build por padrão |
| Login não persiste | cookies de terceiros bloqueados | use o domínio próprio, não um preview |

## 8. Estático vs. função — se o rewrite conflitar

O `vercel.json` atual usa `rewrites: /(.*) → /api/index`, e o Vercel aplica
`rewrites` **depois** do filesystem. Se em algum plano/momento os estáticos
passarem a ser capturados pela função, troque o bloco por exclusão explícita:

```json
"rewrites": [
  { "source": "/((?!assets/|static/|img/|favicon).*)", "destination": "/api/index" }
]
```

## 9. Python 3.12 é obrigatório

O Vercel escolhe o CPython pelo arquivo `.python-version` na raiz. **Não remova esse
arquivo**: sem ele o build usa o 3.14 (default) e quebra em dois pontos, porque não
existem wheels cp314 para as versões fixadas:

- `pydantic-core==2.27.2` teria que compilar (precisa de Rust);
- `psycopg2-binary` teria que compilar (precisa de `pg_config`) → `BUILD_UTILS_SPAWN_1`.

Com `3.12`, os 34 pacotes da árvore resolvem 100 % como wheel (verificado com
`pip download --only-binary=:all: --python-version 3.12 --platform manylinux2014_x86_64`).

### Quero usar Postgres no Vercel

O driver fica separado para não quebrar o build de quem não usa banco externo:

```bash
# 1) acrescente a linha do requirements-postgres.txt ao requirements.txt
echo "psycopg2-binary==2.9.10" >> requirements.txt
# 2) crie a env var DATABASE_URL (Neon) no projeto do Vercel
# 3) redeploy
```

Confirme em `/api/health`: `"db":"postgres:<host>/<banco>"`.
