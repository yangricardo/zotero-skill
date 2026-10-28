# Sincronizar o .bib de um artigo com uma coleção do Zotero

---

Atualize `<refs.bib>` com as referências novas da coleção `<NOME>` do Zotero, sem mexer nas
entradas que já existem.

1. Ache a coleção: `python3 skills/zotero-api/scripts/zot.py collections` e anote a KEY.
2. Prévia: `python3 skills/zotero-api/scripts/zot.py bibsync <refs.bib> --collection <KEY> --dry-run`.
   Ele lista o que é novo e o que já existe, comparando por chave, DOI e título.
3. Mostre a lista ao usuário e, se ele concordar, rode sem `--dry-run`. As entradas novas
   entram no fim do arquivo, depois de um comentário `% ---- Zotero (bibsync)`.
4. Se o projeto compila LaTeX, compile e relate as citações indefinidas.

Para usar um .bib que já foi exportado, sem chamar a API: `--from-file export.bib`.
