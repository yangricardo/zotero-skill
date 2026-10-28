---
name: zotero-importar-fontes
description: Envia as fontes de uma pesquisa (lista de DOIs/arXiv, .ris, .bib e PDFs/HTML baixados) para uma coleção do Zotero, com tags, sem duplicatas e com os arquivos anexados. Use quando o usuário pedir para "mandar para o Zotero" o resultado de uma pesquisa ou anexar artigos baixados.
---

# Importar fontes para o Zotero

Usa o cliente da skill `zotero-api`, em `../zotero-api/scripts/zot.py` a partir da pasta
desta skill. Credenciais e regras gerais estão no SKILL.md da `zotero-api`: leia-o antes,
se ainda não o carregou.

```bash
Z="python3 <pasta-desta-skill>/../zotero-api/scripts/zot.py"
```

## Fluxo

1. **Acesso:** `$Z whoami` precisa mostrar `write` e, para anexar arquivos, `files`.
2. **Downloads** (se houver script): leia o script inteiro antes de rodar e salve numa pasta
   nova, por exemplo `bash baixar_fontes.sh fontes`. Anote o que falhar.
3. **Coleções:** pergunte o nome só se não estiver claro pelo contexto.
   ```bash
   C=$($Z mkcol Projeto)                      # idempotente
   S=$($Z mkcol subtema --parent "$C")
   ```
4. **Itens:**
   ```bash
   $Z convert ids.txt fontes.ris refs.bib --tag Projeto --tag subtema > itens.json
   $Z add itens.json --collection "$S" --dry-run   # mostre a tabela ao usuário
   $Z add itens.json --collection "$S" > keys.tsv  # KEY<TAB>título
   ```
   - Corrija tipos óbvios no JSON antes de enviar (norma → `statute`, página → `webpage`,
     relatório técnico → `report`). Autores institucionais ficam em `name`.
   - `falhou #i (título): 400 …`: remova o campo inválido e reenvie só esse item.
   - Não use `--allow-duplicates` sem pedido explícito.
5. **Anexos:** monte `manifesto.tsv` com `KEY<TAB>fontes/arquivo<TAB>url_original`, casando
   cada arquivo com o item pelo título ou pela URL (veja `examples/manifesto.tsv` na raiz do
   repositório). Depois rode `$Z attach-many manifesto.tsv`.
   - PDF vai por upload. HTML e arquivo ausente vão como link, porque HTML salvo raramente
     fica legível no Zotero. Use `--all-files` só se o usuário quiser o arquivo.
   - Em 413 (cota), o restante vira link sozinho.
6. **Conferência:** confira pela API que a coleção tem N itens e os anexos esperados.
7. **Relatório:** itens criados, pulados por duplicata, falhas, anexos (arquivo e link), o que
   não foi anexado e por quê, e o link `https://www.zotero.org/<username>/collections/<KEY>`
   (username vem do `whoami`). O modelo está em `prompts/02-importar-fontes.md`.
