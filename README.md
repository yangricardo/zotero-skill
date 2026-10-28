# zotero-skill

Skill para agentes (Claude Code e similares) que leva as fontes de uma pesquisa para o
Zotero pela Web API v3. Inclui um cliente Python que usa só a stdlib, prompts reutilizáveis
e testes offline.

```
SKILL.md              instruções da skill (frontmatter + fluxo + regras)
scripts/zot.py        cliente da Zotero Web API v3 (stdlib apenas)
prompts/              prompts prontos: credenciais, importação de fontes, sync do .bib
examples/             lista de ids, script de download e manifesto de anexos
tests/                testes unittest sem rede (HTTP simulado)
```

## Instalar como skill

```bash
git clone git@github.com:yangricardo/zotero-skill.git ~/.claude/skills/zotero-api
```

## Credenciais

Crie uma chave em https://www.zotero.org/settings/keys/new com acesso à biblioteca, escrita
e arquivos. Depois:

```bash
mkdir -p ~/.config/zotero
printf 'ZOTERO_API_KEY=%s\nZOTERO_LIBRARY=users/%s\n' 'SUA_CHAVE' 'SEU_USERID' > ~/.config/zotero/env
chmod 600 ~/.config/zotero/env
python3 scripts/zot.py whoami
```

O `zot.py` lê esse arquivo sozinho quando as variáveis não estão no ambiente.

## Uso rápido

```bash
Z="python3 scripts/zot.py"
S=$($Z mkcol subtema --parent "$($Z mkcol Projeto)")
$Z convert examples/identificadores.txt --tag Projeto > itens.json
$Z add itens.json --collection "$S" > keys.tsv
$Z attach-many manifesto.tsv
$Z bibsync refs.bib --collection "$S" --dry-run
```

Comandos: `whoami`, `collections`, `mkcol`, `search`, `get`, `export`, `convert`, `add`,
`attach`, `attach-many`, `tag`, `bibsync`. Veja `python3 scripts/zot.py <cmd> -h`.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Os testes não usam rede nem credenciais. O HTTP é simulado em `tests/helpers.py`.

## Origem

Extraída da importação das 17 fontes da pesquisa EmendasRAG (RAG sobre emendas parlamentares),
em 28/10/2026. Lições incorporadas:

- O `whoami` usa `/keys/current` e avisa quando a chave não tem 24 caracteres.
- Os erros mascaram a chave.
- O `attach --fallback-url` e o `attach-many` tratam o erro de cota (413).
- O arquivo `~/.config/zotero/env` é carregado automaticamente.
