---
name: zotero-bib-lncs
description: Mantém o references.bib de um artigo LaTeX (LNCS/splncs04 ou outro estilo BibTeX) em sincronia com uma coleção do Zotero, nos dois sentidos, sem mudar chaves já citadas. Use quando o usuário pedir para atualizar a bibliografia do artigo a partir do Zotero ou levar o .bib para o Zotero.
---

# Sincronizar references.bib com o Zotero

Usa o cliente da skill `zotero-api`, em `../zotero-api/scripts/zot.py` a partir da pasta
desta skill. Credenciais e regras gerais estão no SKILL.md da `zotero-api`.

```bash
Z="python3 <pasta-desta-skill>/../zotero-api/scripts/zot.py"
```

## Zotero → references.bib

1. Ache a coleção: `$Z collections`.
2. Prévia: `$Z bibsync caminho/references.bib --collection KEY --dry-run`. Ele exporta em
   BibTeX (o `splncs04.bst` usa BibTeX; use `--format biblatex` só se o artigo usar biblatex)
   e marca como existente o que bate por chave, DOI ou título.
3. Mostre as entradas novas ao usuário e rode sem `--dry-run`. Elas entram no fim do arquivo,
   depois do comentário `Zotero (bibsync)`. Entradas existentes nunca são reescritas, para
   não quebrar `\cite{}`.
4. Revise as entradas novas contra o padrão do arquivo: acentos, `{}` em siglas no título
   (`{RAG}`), `note` para preprints e chaves no estilo do arquivo. Se trocar uma chave gerada
   pelo Zotero, grave `Citation Key: novachave` no Extra do item para a próxima exportação
   manter a mesma chave, e confira na exportação seguinte se ela foi respeitada.
5. Se o projeto tiver `.tex`, rode `grep -o '\cite{[^}]*}' *.tex` (ou compile) e avise sobre
   chaves citadas que não existem no `.bib`.

Para usar um `.bib` já exportado sem chamar a API: `bibsync refs.bib --from-file export.bib`.

## references.bib → Zotero

1. `$Z convert references.bib --tag Projeto > bib.json`. Cada item leva
   `Citation Key: <chave original>` no Extra.
2. `$Z add bib.json --collection KEY --dry-run`, revise com o usuário (itens `document`
   costumam ser páginas web ou normas: ajuste para `webpage`, `report` ou `standard`) e envie
   sem `--dry-run`.
3. O conversor entende `@tipo{chave, campo = {...}}`, acentos LaTeX comuns e `and` entre
   autores. Ele ignora `@string` e macros. Em `author = {X and others}`, o "others" se perde:
   avise que a lista de autores ficou incompleta.

## Regras

- Nunca reordene nem reformate o `.bib` existente. Só acrescente no fim.
- Confirme o caminho do `.bib` antes de gravar.
