# Importar as fontes de uma pesquisa para o Zotero

Prompt para delegar a tarefa a um agente. Troque o que está entre `<>`.

---

Objetivo: enviar ao Zotero (Web API v3) as fontes da pesquisa `<PROJETO>` com os arquivos
anexados. Trabalhe em `<PASTA>`, onde estão `<ids.txt>` (DOI/arXiv, um por linha),
`<fontes.ris|.bib>` e `<baixar_fontes.sh>`. Use `scripts/zot.py` da skill zotero-api (no repositório, `skills/zotero-api/scripts/zot.py`).

1. **Credenciais:** siga o SKILL.md. Se faltarem, use `prompts/01-configurar-credenciais.md`.
   Nunca exiba a chave. O `whoami` precisa mostrar write e files.
2. **Downloads:** leia o script antes de rodar e execute `bash <baixar_fontes.sh> fontes`.
   Anote o que falhar e não contorne erros de SSL.
3. **Coleções:** `C=$(zot.py mkcol <PROJETO>)` e `S=$(zot.py mkcol <SUBTEMA> --parent $C)`.
4. **Itens:** `zot.py convert <ids.txt> <fontes.ris> --tag <PROJETO> --tag <SUBTEMA> > itens.json`.
   Depois rode `add itens.json --collection $S --dry-run` e, em seguida,
   `add itens.json --collection $S > keys.tsv`. Itens que já existem são pulados. Se algum
   item falhar por campo inválido, remova o campo e reenvie só esse item.
5. **Anexos:** monte `manifesto.tsv` com `KEY<TAB>fontes/arquivo<TAB>url_original`, associando
   cada arquivo ao item pelo título ou pela URL em `keys.tsv`. Rode `zot.py attach-many manifesto.tsv`:
   PDFs vão por upload; páginas HTML e downloads que falharam vão como link. Se der 413, o
   restante vira link.
6. **Conferência:** confira pela API que a coleção tem N itens e N anexos.
7. **Relatório:** itens criados, pulados por duplicata, falhas, anexos (arquivo e link),
   o que não foi anexado e por quê, e o link `https://www.zotero.org/<username>/collections/<KEY de S>`.
   Não apague nada da biblioteca.

---

## Exemplo de relatório

> 17 itens criados na coleção EmendasRAG > pesquisa-rag-enxuto, nenhum duplicado e nenhuma falha.
> 8 PDFs enviados como arquivo. 9 anexados como link: 7 páginas HTML e 2 downloads que falharam
> (um por certificado SSL inválido, outro por HTTP 405). A API confirma 17 itens e 17 anexos.
> Link: https://www.zotero.org/<username>/collections/<KEY>
