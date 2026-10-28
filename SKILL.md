---
name: zotero-api
description: Envia referências e arquivos para uma biblioteca Zotero pela Web API v3 com scripts/zot.py, que usa só a stdlib. Converte DOI, arXiv, RIS e BibTeX em itens, cria coleções, evita duplicatas, anexa PDFs (upload) ou links e sincroniza um .bib. Use quando o usuário pedir para "mandar para o Zotero", organizar fontes de uma pesquisa em coleções, anexar artigos baixados ou atualizar o .bib a partir do Zotero.
---

# Zotero API

Cliente: `scripts/zot.py` (Python 3.9+, sem dependências). Rode `python3 scripts/zot.py -h`
e `python3 scripts/zot.py <comando> -h` para ver as opções.

## Credenciais (sempre primeiro)

1. O script lê `ZOTERO_API_KEY` e `ZOTERO_LIBRARY` do ambiente. Se faltarem, lê de
   `~/.config/zotero/env` (ou do caminho em `ZOTERO_ENV_FILE`), sem sobrescrever o ambiente.
2. Se não houver credenciais, peça ao usuário que siga `prompts/01-configurar-credenciais.md`.
   **Nunca peça, imprima, registre ou repita a chave.** Ela não pode aparecer no chat,
   em logs nem em commits.
3. `python3 scripts/zot.py whoami` precisa mostrar `library`, `write` e `files` como `true`.
   - HTTP 403 "Invalid key": quase sempre um caractere sobrando ao copiar. O `whoami`
     avisa quando a chave não tem 24 caracteres alfanuméricos. Confira o comprimento
     sem exibir a chave.
   - O userID é numérico e aparece em https://www.zotero.org/settings/keys
     ("Your user ID for use in API calls is …"). Não é o nome de usuário.

## Fluxo padrão (fontes de uma pesquisa)

```bash
Z="python3 scripts/zot.py"
C=$($Z mkcol Projeto)                         # idempotente
S=$($Z mkcol subtema --parent "$C")
$Z convert ids.txt fontes.ris refs.bib --tag Projeto > itens.json   # DOI/arXiv: 1 por linha
$Z add itens.json --collection "$S" --dry-run  # mostra o que será criado
$Z add itens.json --collection "$S" > keys.tsv # KEY<TAB>título; duplicatas são puladas
# manifesto TSV: KEY<TAB>arquivo_local<TAB>url_original
$Z attach-many manifesto.tsv                   # PDF: upload; HTML ou sem arquivo: link
```

- Duplicatas: `add` compara títulos normalizados e pula os que já existem. Não use
  `--allow-duplicates` sem pedido explícito.
- Campos inválidos: o `add` informa `falhou #i (título): 400 …`. Remova o campo e reenvie só esse item.
- Cota de arquivos (HTTP 413): `attach-many` passa a anexar só links dali em diante. Para um
  item avulso, use `attach KEY --file X.pdf --fallback-url URL`. O anexo vazio que a chamada
  tinha acabado de criar é removido.
- Páginas HTML: prefira anexar o link original, porque o HTML salvo raramente fica legível
  no Zotero. Use `--all-files` em `attach-many` só se o usuário quiser o arquivo.
- Downloads que falham (SSL inválido, 403/405): **não** contorne com `curl -k`. Anexe o link
  e relate o problema.
- Link da coleção: `https://www.zotero.org/<username>/collections/<KEY>` (o username vem do `whoami`).

## Outros comandos

| comando | uso |
|---|---|
| `collections` | árvore de coleções com contagem |
| `search "q" [--collection K] [--tag T]` | busca em itens de topo |
| `get KEY` | JSON editável de um item |
| `tag KEY --add T --remove T --collection K` | ajusta tags/coleção (PATCH com versão) |
| `export --collection K --format biblatex --out x.bib` | exporta |
| `bibsync refs.bib --collection K [--dry-run]` | acrescenta ao .bib só as entradas novas (por chave, DOI e título) |

`ZOTERO_BASE=http://localhost:23119/api` usa a API local do Zotero desktop, que só faz leitura
sem chave.

## Regras

- Não apague nada da biblioteca do usuário. Os comandos só criam e editam. A única remoção
  automática é a do anexo vazio no caso de 413.
- Antes de rodar um script de download recebido, leia o script inteiro. Salve os arquivos
  baixados numa pasta nova.
- No fim, relate: itens criados, pulados por duplicata, falhas, anexos (arquivo e link),
  o que não foi anexado e o link da coleção. Use `prompts/02-importar-fontes.md` como modelo.
