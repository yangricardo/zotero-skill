---
name: zotero-api
description: Cliente da Zotero Web API v3 (scripts/zot.py, só stdlib) para buscar, criar coleções e itens, anexar arquivos ou links, ajustar tags e exportar BibTeX/RIS/CSL-JSON. Use para qualquer leitura ou escrita na biblioteca Zotero online; as skills zotero-importar-fontes e zotero-bib-lncs se apoiam nela.
---

# Zotero API

Cliente: `scripts/zot.py`, dentro da pasta desta skill (Python 3.9+, sem dependências).
Rode `python3 scripts/zot.py -h` e `python3 scripts/zot.py <comando> -h` para ver as opções.
As skills `zotero-importar-fontes` e `zotero-bib-lncs` chamam este mesmo arquivo como
`../zotero-api/scripts/zot.py`.

## Credenciais (sempre primeiro)

1. O script lê `ZOTERO_API_KEY` e `ZOTERO_LIBRARY` do ambiente. Se faltarem, lê de
   `~/.config/zotero/env` (ou do caminho em `ZOTERO_ENV_FILE`), sem sobrescrever o ambiente.
2. Se não houver credenciais, peça ao usuário que siga `prompts/01-configurar-credenciais.md`
   (na raiz do repositório). **Nunca peça, imprima, registre ou repita a chave.** Ela não pode
   aparecer no chat, em logs, na memória nem em commits.
3. `python3 scripts/zot.py whoami` precisa mostrar `library`, `write` e `files` como `true`.
   - HTTP 403 "Invalid key": quase sempre um caractere sobrando ao copiar. O `whoami`
     avisa quando a chave não tem 24 caracteres alfanuméricos. Confira o comprimento
     sem exibir a chave.
   - O userID é numérico e aparece em https://www.zotero.org/settings/keys
     ("Your user ID for use in API calls is …"). Não é o nome de usuário.

## Comandos

| comando | uso |
|---|---|
| `whoami` | userID, username e permissões da chave |
| `collections` | árvore de coleções com contagem |
| `mkcol NOME [--parent K]` | cria coleção ou devolve a existente (idempotente) |
| `search "q" [--collection K] [--tag T]` | busca em itens de topo |
| `get KEY` | JSON editável de um item |
| `convert ids.txt fontes.ris refs.bib [--tag T]` | DOI/arXiv/RIS/BibTeX → JSON de itens, sem tocar na biblioteca |
| `add itens.json --collection K [--dry-run]` | cria itens em lotes de 50 e pula títulos existentes |
| `attach KEY --file X.pdf [--fallback-url URL]` / `--url URL` | anexa arquivo (upload) ou link |
| `attach-many manifesto.tsv [--all-files]` | anexos em lote (`KEY<TAB>arquivo<TAB>url`) |
| `tag KEY --add T --remove T --collection K` | ajusta tags/coleção (PATCH com versão) |
| `export --collection K --format biblatex --out x.bib` | exporta (bibtex, biblatex, ris, csljson…) |
| `bibsync refs.bib --collection K [--dry-run]` | acrescenta ao .bib só as entradas novas |

`ZOTERO_BASE=http://localhost:23119/api` usa a API local do Zotero desktop, que só faz leitura
sem chave.

## O que a Web API permite

- Leitura paginada (máx. 100 por página, header `Link`), busca por `q`, `tag` e `itemType`.
- Escrita em lotes de 50, com `Zotero-Write-Token` ou `If-Unmodified-Since-Version`. A resposta
  é HTTP 200 mesmo com falhas parciais: sempre confira `failed`.
- Upload de arquivo em 3 passos (autorização, envio, registro). Cota grátis de 300 MB (413).
- **Não existe:** importar RIS/BibTeX direto ou resolver DOI. O `convert` faz isso localmente,
  usando doi.org e export.arxiv.org.

## Regras

- Não apague nada da biblioteca do usuário. Os comandos só criam e editam. A única remoção
  automática é a do anexo vazio no caso de 413.
- Sempre rode `add --dry-run` antes de gravar e mostre ao usuário o que será criado.
- Downloads que falham (SSL inválido, 403/405): **não** contorne com `curl -k`. Anexe o link
  e relate o problema.
- Se a rede bloquear `api.zotero.org`, `doi.org` ou `export.arxiv.org` (por exemplo, `CONNECT
  tunnel failed`), diga qual host falhou e sugira rodar onde a rede é liberada.
