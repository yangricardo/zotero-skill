# Configurar credenciais do Zotero

Texto para enviar ao usuário quando `ZOTERO_API_KEY` ou `ZOTERO_LIBRARY` estiverem faltando.

---

Não encontrei credenciais do Zotero. Para configurar (leva uns 2 minutos):

1. Crie uma chave em https://www.zotero.org/settings/keys/new e marque **Allow library access**,
   **Allow write access** e, se quiser anexar arquivos, **Allow file access**. Copie a chave
   logo depois de criar: ela tem 24 caracteres e só aparece uma vez.
2. Na mesma página aparece o seu userID ("Your user ID for use in API calls is NNNNNNN").
   É um número, não o seu nome de usuário.
3. No Terminal (troque os valores; a chave não passa pelo chat):

   ```bash
   mkdir -p ~/.config/zotero && \
   printf 'ZOTERO_API_KEY=%s\nZOTERO_LIBRARY=users/%s\n' 'SUA_CHAVE' 'SEU_USERID' \
     > ~/.config/zotero/env && chmod 600 ~/.config/zotero/env
   ```

4. Me avise quando terminar. **Não cole a chave aqui.**

---

## Depois que o usuário avisar

```bash
python3 skills/zotero-api/scripts/zot.py whoami   # library, write e files precisam estar true
```

Se der 403 "Invalid key", confira o formato sem exibir a chave:

```bash
python3 -c "import os,re;k=os.environ.get('ZOTERO_API_KEY','');print(len(k), bool(re.fullmatch(r'[A-Za-z0-9]{24}',k)))"
```

Um comprimento de 25 costuma ser um caractere a mais na hora de copiar. Peça ao usuário para
copiar a chave de novo. Se ele preferir que você corrija, só corte o caractere depois de
confirmar com `curl -s -o /dev/null -w '%{http_code}' -H "Zotero-API-Key: …" https://api.zotero.org/keys/current`
que a versão cortada recebe 200. Nunca imprima a chave.
