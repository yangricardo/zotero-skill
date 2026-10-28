#!/usr/bin/env python3
"""zot.py - cliente minimo da Zotero Web API v3 (stdlib apenas).

Ambiente:
  ZOTERO_API_KEY   chave criada em https://www.zotero.org/settings/keys
  ZOTERO_LIBRARY   "users/<userID>" ou "groups/<groupID>"
  ZOTERO_BASE      opcional; padrao https://api.zotero.org
                   (http://localhost:23119/api para a API local do Zotero desktop)
  ZOTERO_ENV_FILE  opcional; padrao ~/.config/zotero/env (KEY=valor, uma por linha),
                   lido so para variaveis ainda nao definidas no ambiente
"""
import argparse, hashlib, json, os, re, secrets, sys, time, unicodedata
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET



def load_env_file(path=None):
    """Carrega KEY=valor de ZOTERO_ENV_FILE sem sobrescrever o ambiente."""
    path = os.path.expanduser(path or os.environ.get("ZOTERO_ENV_FILE", "~/.config/zotero/env"))
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        linhas = fh.read().splitlines()
    for line in linhas:
        m = re.match(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=(.*)$", line)
        if m:
            os.environ.setdefault(m.group(1), m.group(2).strip().strip("'\""))


load_env_file()
BASE = os.environ.get("ZOTERO_BASE", "https://api.zotero.org").rstrip("/")
KEY = os.environ.get("ZOTERO_API_KEY", "")
LIB = os.environ.get("ZOTERO_LIBRARY", "").strip("/")
UA = "zot.py/1.0 (skill zotero-api)"


class ZoteroError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def die(msg):
    raise ZoteroError(msg)


def check_key_format(key):
    """Chaves da Zotero Web API tem 24 caracteres alfanumericos."""
    if not re.fullmatch(r"[A-Za-z0-9]{24}", key or ""):
        return (f"a chave tem {len(key or '')} caractere(s); esperado 24 alfanumericos "
                "(caractere sobrando ao copiar, aspas ou espaco?)")


# ---------------------------------------------------------------- HTTP
def http(method, path, body=None, headers=None, params=None, raw=False, absolute=False):
    url = path if absolute else BASE + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    h = {"Zotero-API-Version": "3", "User-Agent": UA}
    if KEY and not absolute:
        h["Zotero-API-Key"] = KEY
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    elif isinstance(body, str):
        body = body.encode()
    h.update(headers or {})
    for attempt in range(6):
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data, hdr, code = r.read(), r.headers, r.status
        except urllib.error.HTTPError as e:
            data, hdr, code = e.read(), e.headers, e.code
            if code in (429, 503):
                wait = int(hdr.get("Retry-After") or 2 ** attempt)
                print(f"aviso: HTTP {code}, aguardando {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
        if hdr.get("Backoff"):
            time.sleep(int(hdr["Backoff"]))
        if code >= 400:
            shown = url.replace(KEY, "<KEY>") if KEY else url
            raise ZoteroError(f"{method} {shown} -> HTTP {code}: {data[:500].decode(errors='replace')}", code)
        if raw:
            return data, hdr, code
        return (json.loads(data) if data.strip() else None), hdr, code
    die(f"{method} {url}: tentativas esgotadas")


def lib(path=""):
    if not LIB:
        die("defina ZOTERO_LIBRARY (ex.: users/1234567)")
    return f"/{LIB}{path}"


def get_all(path, params=None, raw=False):
    """GET paginado seguindo o header Link rel=next (limite 100 por pagina)."""
    params = dict(params or {})
    params.setdefault("limit", 100)
    out, chunks = [], []
    data, hdr, _ = http("GET", path, params=params, raw=raw)
    while True:
        if raw:
            chunks.append(data.decode())
        else:
            out.extend(data)
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', hdr.get("Link", ""))
        if not nxt:
            break
        data, hdr, _ = http("GET", nxt.group(1), raw=raw, absolute=True,
                            headers={"Zotero-API-Key": KEY} if KEY else None)
    return "\n".join(chunks) if raw else out


def post_batches(path, objs):
    """POST em lotes de 50 com Zotero-Write-Token. Retorna {indice_global: key}."""
    keys, failed = {}, {}
    for i in range(0, len(objs), 50):
        lote = objs[i:i + 50]
        res, _, _ = http("POST", path, lote, {"Zotero-Write-Token": secrets.token_hex(16)})
        for k, v in (res.get("successful") or res.get("success") or {}).items():
            keys[i + int(k)] = v["key"] if isinstance(v, dict) else v
        for k, v in (res.get("unchanged") or {}).items():
            keys[i + int(k)] = v
        for k, v in (res.get("failed") or {}).items():
            failed[i + int(k)] = v
    for idx, f in failed.items():
        print(f"falhou #{idx} ({objs[idx].get('title') or objs[idx].get('name')}): "
              f"{f.get('code')} {f.get('message')}", file=sys.stderr)
    return keys


# ---------------------------------------------------------------- conversoes
# Campos aceitos por tipo (subconjunto do schema; confira com /items/new?itemType=X).
FIELDS = {
    "journalArticle": {"publicationTitle", "volume", "issue", "pages", "DOI", "ISSN"},
    "conferencePaper": {"proceedingsTitle", "conferenceName", "publisher", "place", "pages", "DOI", "ISBN"},
    "preprint": {"repository", "archiveID", "DOI", "place"},
    "report": {"institution", "reportNumber", "reportType", "place", "pages", "seriesTitle"},
    "thesis": {"university", "thesisType", "place", "numPages"},
    "book": {"publisher", "place", "ISBN", "edition", "numPages", "series"},
    "bookSection": {"bookTitle", "publisher", "place", "pages", "ISBN"},
    "webpage": {"websiteTitle", "websiteType"},
    "document": {"publisher"},
    "dataset": {"repository", "DOI", "place"},
}
COMMON = {"title", "abstractNote", "date", "url", "accessDate", "language", "extra", "shortTitle"}


INSTITUCIONAL = re.compile(
    r"\b(C[aâ]mara|Senado|Congresso|Consultoria|Controladoria|Tribunal|Minist[eé]rio|Secretaria|"
    r"Governo|Portal|Universidade|Instituto|Departamento|Ag[eê]ncia|Associa[cç][aã]o|Funda[cç][aã]o|"
    r"Comiss[aã]o|Banco|Conselho|University|Institute|Department|Agency|Office|Committee)\b", re.I)


def creator(nome, tipo="author"):
    nome = nome.strip()
    if "," in nome and not INSTITUCIONAL.search(nome):
        last, first = [p.strip() for p in nome.split(",", 1)]
        if first and len(last.split()) <= 3 and len(first.split()) <= 3:
            return {"creatorType": tipo, "lastName": last, "firstName": first}
    return {"creatorType": tipo, "name": nome}  # autor institucional


def item(itemType, fields, creators=(), tags=(), collections=()):
    allowed = COMMON | FIELDS.get(itemType, set())
    it = {"itemType": itemType, "creators": list(creators),
          "tags": [{"tag": t} for t in dict.fromkeys(tags) if t],
          "collections": list(collections), "relations": {}}
    extra = []
    for k, v in fields.items():
        if not v:
            continue
        if k in allowed:
            it[k] = v
        elif k == "DOI":
            extra.append(f"DOI: {v}")  # Zotero le DOI do Extra em tipos sem o campo
        elif k == "citationKey":
            extra.append(f"Citation Key: {v}")
    if extra:
        it["extra"] = "\n".join(filter(None, [it.get("extra")] + extra))
    return it


RIS_TYPES = {"JOUR": "journalArticle", "CONF": "conferencePaper", "CPAPER": "conferencePaper",
             "RPRT": "report", "THES": "thesis", "BOOK": "book", "CHAP": "bookSection",
             "ELEC": "webpage", "WEB": "webpage", "DATA": "dataset", "GEN": "document"}


def from_ris(text, tags=(), collections=()):
    items, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"TY": val, "AU": [], "KW": []}
        elif tag == "ER" and cur is not None:
            t = RIS_TYPES.get(cur["TY"], "document")
            f = {"title": cur.get("TI") or cur.get("T1"), "date": cur.get("PY") or cur.get("DA"),
                 "url": cur.get("UR"), "abstractNote": cur.get("AB"), "DOI": cur.get("DO"),
                 "publicationTitle": cur.get("JO") or cur.get("T2"),
                 "proceedingsTitle": cur.get("T2"), "websiteTitle": cur.get("T2"),
                 "volume": cur.get("VL"), "issue": cur.get("IS"),
                 "pages": "-".join(filter(None, [cur.get("SP"), cur.get("EP")])),
                 "publisher": cur.get("PB"), "institution": cur.get("PB"),
                 "university": cur.get("PB"), "place": cur.get("CY"), "language": cur.get("LA"),
                 "extra": cur.get("N1")}
            items.append(item(t, f, [creator(a) for a in cur["AU"]],
                              list(cur["KW"]) + list(tags), collections))
            cur = None
        elif cur is not None:
            if tag in ("AU", "A1", "A2"):
                cur["AU"].append(val)
            elif tag == "KW":
                cur["KW"].append(val)
            else:
                cur.setdefault(tag, val)
    return items


BIB_TYPES = {"article": "journalArticle", "inproceedings": "conferencePaper", "conference": "conferencePaper",
             "techreport": "report", "report": "report", "phdthesis": "thesis", "mastersthesis": "thesis",
             "thesis": "thesis", "book": "book", "incollection": "bookSection", "inbook": "bookSection",
             "online": "webpage", "misc": "document", "dataset": "dataset", "unpublished": "document"}


def parse_bib(text):
    """Parser BibTeX simples (chaves balanceadas). Retorna [(tipo, chave, {campo: valor})]."""
    out, i = [], 0
    while True:
        m = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,").search(text, i)
        if not m:
            return out
        typ, key, i, fields = m.group(1).lower(), m.group(2), m.end(), {}
        while True:
            fm = re.compile(r"\s*(\w+)\s*=\s*").match(text, i)
            if not fm:
                break
            name, j = fm.group(1).lower(), fm.end()
            if text[j] == "{":
                depth, k = 0, j
                while True:
                    depth += {"{": 1, "}": -1}.get(text[k], 0)
                    if depth == 0:
                        break
                    k += 1
                val, i = text[j + 1:k], k + 1
            elif text[j] == '"':
                k = text.index('"', j + 1); val, i = text[j + 1:k], k + 1
            else:
                vm = re.compile(r"[^,}\s]+").match(text, j); val, i = vm.group(0), vm.end()
            fields[name] = re.sub(r"\s+", " ", val).strip()
            cm = re.compile(r"\s*,").match(text, i)
            if cm:
                i = cm.end()
        out.append((typ, key, fields))


ACENTOS = {"`": "\u0300", "'": "\u0301", "^": "\u0302", '"': "\u0308", "~": "\u0303", "c": "\u0327"}


def unlatex(s):
    s = re.sub(r"\{?\\([`'^\"~]|c\s*)\s*\{?(\w)\}?\}?",
               lambda m: unicodedata.normalize("NFC", m.group(2) + ACENTOS[m.group(1).strip()]), s or "")
    s = s.replace("\\&", "&").replace("\\#", "#").replace("\\%", "%").replace("\\$", "$").replace("--", "-")
    return re.sub(r"[{}]", "", s).strip()


def from_bib(text, tags=(), collections=()):
    items = []
    for typ, key, f in parse_bib(text):
        t = BIB_TYPES.get(typ, "document")
        cont = unlatex(f.get("journal") or f.get("booktitle"))
        hp = unlatex(f.get("howpublished"))
        arx = re.search(r"arXiv:?\s*(\d{4}\.\d{4,5})", hp + " " + f.get("eprint", ""))
        if arx:
            t = "preprint"
        fields = {"title": unlatex(f.get("title")), "date": f.get("date") or f.get("year"),
                  "url": f.get("url"), "DOI": f.get("doi"), "publicationTitle": cont,
                  "proceedingsTitle": cont, "bookTitle": cont, "volume": f.get("volume"),
                  "issue": f.get("number"), "pages": unlatex(f.get("pages")),
                  "publisher": unlatex(f.get("publisher")),
                  "institution": unlatex(f.get("institution") or f.get("organization")),
                  "university": unlatex(f.get("school")), "place": unlatex(f.get("address")),
                  "ISBN": f.get("isbn"), "ISSN": f.get("issn"),
                  "repository": "arXiv" if arx else None,
                  "archiveID": f"arXiv:{arx.group(1)}" if arx else None,
                  "extra": unlatex(f.get("note")), "citationKey": key}
        cr = [creator(unlatex(a)) for a in re.split(r"\s+and\s+", f.get("author", "")) if a.strip()]
        cr = [c for c in cr if (c.get("name") or c.get("lastName")) not in ("others",)]
        items.append(item(t, fields, cr, tags, collections))
    return items


CSL_TYPES = {"article-journal": "journalArticle", "paper-conference": "conferencePaper",
             "report": "report", "thesis": "thesis", "book": "book", "chapter": "bookSection",
             "webpage": "webpage", "article": "preprint", "posted-content": "preprint",
             "dataset": "dataset"}


def from_csl(c, tags=(), collections=()):
    t = CSL_TYPES.get(c.get("type"), "document")
    d = (c.get("issued") or {}).get("date-parts", [[None]])[0]
    date = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(d) if p) if d and d[0] else ""
    title = c.get("title")
    title = title[0] if isinstance(title, list) else title
    cont = c.get("container-title")
    cont = cont[0] if isinstance(cont, list) and cont else cont
    f = {"title": title, "date": date, "DOI": c.get("DOI"), "url": c.get("URL"),
         "abstractNote": re.sub(r"<[^>]+>", "", c.get("abstract") or "").strip(),
         "publicationTitle": cont, "proceedingsTitle": cont, "bookTitle": cont,
         "conferenceName": c.get("event") if isinstance(c.get("event"), str) else None,
         "volume": c.get("volume"), "issue": c.get("issue"), "pages": c.get("page"),
         "publisher": c.get("publisher"), "institution": c.get("publisher"),
         "ISSN": (c.get("ISSN") or [None])[0], "ISBN": (c.get("ISBN") or [None])[0],
         "language": c.get("language")}
    cr = [{"creatorType": "author", "lastName": a["family"], "firstName": a.get("given", "")}
          if "family" in a else {"creatorType": "author", "name": a.get("literal", "")}
          for a in c.get("author", [])]
    return item(t, f, cr, tags, collections)


def from_doi(doi, **kw):
    data, _, _ = http("GET", f"https://doi.org/{urllib.parse.quote(doi)}", raw=True, absolute=True,
                      headers={"Accept": "application/vnd.citationstyles.csl+json"})
    return from_csl(json.loads(data), **kw)


def from_arxiv(aid, tags=(), collections=()):
    aid = re.sub(r"^arxiv:", "", aid, flags=re.I)
    data, _, _ = http("GET", "https://export.arxiv.org/api/query", params={"id_list": aid},
                      raw=True, absolute=True)
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    e = ET.fromstring(data).find("a:entry", ns)
    if e is None or e.find("a:title", ns) is None:
        die(f"arXiv {aid} nao encontrado")
    txt = lambda p: re.sub(r"\s+", " ", (e.findtext(p, "", ns) or "")).strip()
    cr = []
    for a in e.findall("a:author", ns):
        n = txt_el(a.find("a:name", ns))
        parts = n.rsplit(" ", 1)
        cr.append({"creatorType": "author", "lastName": parts[-1], "firstName": parts[0] if len(parts) > 1 else ""})
    f = {"title": txt("a:title"), "abstractNote": txt("a:summary"), "date": txt("a:published")[:10],
         "url": f"https://arxiv.org/abs/{aid}", "repository": "arXiv", "archiveID": f"arXiv:{aid}",
         "DOI": txt("x:doi") or f"10.48550/arXiv.{re.sub(r'v[0-9]+$', '', aid)}"}
    return item("preprint", f, cr, tags, collections)


def txt_el(el):
    return re.sub(r"\s+", " ", el.text or "").strip() if el is not None else ""


def from_id(ident, **kw):
    ident = ident.strip()
    if re.match(r"^(arxiv:)?\d{4}\.\d{4,5}(v\d+)?$", ident, re.I):
        return from_arxiv(ident, **kw)
    m = re.search(r"(10\.\d{4,9}/\S+)", ident)
    if m:
        return from_doi(m.group(1), **kw)
    die(f"identificador nao reconhecido (use DOI ou arXiv): {ident}")


# ---------------------------------------------------------------- comandos
def find_collection(name, parent=None):
    for c in get_all(lib("/collections")):
        d = c["data"]
        if d["name"] == name and (d.get("parentCollection") or None) == (parent or None):
            return d["key"]


def cmd_whoami(a):
    problema = check_key_format(KEY)
    if problema:
        print(f"aviso: {problema}", file=sys.stderr)
    d, _, _ = http("GET", "/keys/current")
    print(json.dumps({"userID": d.get("userID"), "username": d.get("username"),
                      "access": d.get("access")}, indent=2, ensure_ascii=False))


def cmd_collections(a):
    cols = get_all(lib("/collections"))
    by_parent = {}
    for c in cols:
        by_parent.setdefault(c["data"].get("parentCollection") or None, []).append(c)

    def show(p, depth):
        for c in sorted(by_parent.get(p, []), key=lambda c: c["data"]["name"]):
            print(f"{'  ' * depth}{c['key']}  {c['data']['name']}  ({c['meta'].get('numItems', 0)} itens)")
            show(c["key"], depth + 1)
    show(None, 0)


def cmd_mkcol(a):
    key = find_collection(a.name, a.parent)
    if not key:
        key = post_batches(lib("/collections"), [{"name": a.name, "parentCollection": a.parent or False}])[0]
    print(key)


def cmd_search(a):
    p = {"q": a.q, "qmode": a.qmode, "limit": a.limit}
    if a.tag:
        p["tag"] = a.tag
    path = lib(f"/collections/{a.collection}/items/top") if a.collection else lib("/items/top")
    data, hdr, _ = http("GET", path, params=p)
    print(f"# {hdr.get('Total-Results', len(data))} resultado(s)", file=sys.stderr)
    for it in data:
        d = it["data"]
        who = "; ".join(c.get("lastName") or c.get("name", "") for c in d.get("creators", [])[:3])
        print(f"{d['key']}  {d['itemType']:<16} {d.get('date', '')[:4]:<4}  {who[:40]:<40}  {d.get('title', '')}")


def cmd_get(a):
    data, _, _ = http("GET", lib(f"/items/{a.key}"))
    print(json.dumps(data["data"], indent=2, ensure_ascii=False))


def cmd_export(a):
    path = lib(f"/collections/{a.collection}/items/top") if a.collection else lib("/items/top")
    p = {"format": a.format, "itemType": "-attachment || note"}
    if a.tag:
        p["tag"] = a.tag
    out = get_all(path, p, raw=True)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print(f"gravado {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(out)


def cmd_convert(a):
    kw = {"tags": a.tag or [], "collections": [a.collection] if a.collection else []}
    items = []
    for src in a.src:
        if src.lower().endswith(".ris"):
            items += from_ris(open(src, encoding="utf-8-sig").read(), **kw)
        elif src.lower().endswith(".bib"):
            items += from_bib(open(src, encoding="utf-8").read(), **kw)
        elif src.lower().endswith(".txt"):
            items += [from_id(l, **kw) for l in open(src, encoding="utf-8")
                      if l.strip() and not l.startswith("#")]
        else:
            items.append(from_id(src, **kw))
    json.dump(items, sys.stdout, indent=2, ensure_ascii=False)
    print()


def norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


def cmd_add(a):
    items = json.load(open(a.json, encoding="utf-8") if a.json != "-" else sys.stdin)
    if a.collection:
        for it in items:
            it.setdefault("collections", [])
            if a.collection not in it["collections"]:
                it["collections"].append(a.collection)
    if not a.allow_duplicates:
        novos = []
        for it in items:
            hits, _, _ = http("GET", lib("/items/top"), params={"q": it.get("title", "")[:120], "limit": 10})
            dup = [h for h in hits if norm(h["data"].get("title")) == norm(it.get("title"))]
            if dup:
                print(f"ja existe ({dup[0]['key']}): {it.get('title')}", file=sys.stderr)
            else:
                novos.append(it)
        items = novos
    if a.dry_run:
        json.dump(items, sys.stdout, indent=2, ensure_ascii=False)
        return
    keys = post_batches(lib("/items"), items) if items else {}
    for i, k in sorted(keys.items()):
        print(f"{k}\t{items[i].get('title')}")


def cmd_attach(a):
    if a.file and a.fallback_url:
        try:
            return attach_file(a)
        except ZoteroError as e:
            if e.code != 413:
                raise
            print("aviso: cota de arquivos esgotada (413), anexando link", file=sys.stderr)
            a.url = a.fallback_url
    if a.file and not a.url:
        return attach_file(a)
    att = {"itemType": "attachment", "linkMode": "linked_url", "title": a.title or a.url,
           "url": a.url, "parentItem": a.parent, "tags": [], "relations": {},
           "contentType": "", "charset": ""}
    print(post_batches(lib("/items"), [att])[0])


def attach_file(a):
    path = a.file
    fname = os.path.basename(path)
    blob = open(path, "rb").read()
    ctype = a.content_type or ("application/pdf" if fname.lower().endswith(".pdf") else
                               "text/html" if fname.lower().endswith((".html", ".htm")) else
                               "application/octet-stream")
    att = {"itemType": "attachment", "linkMode": "imported_file", "title": a.title or fname,
           "parentItem": a.parent, "contentType": ctype, "charset": "", "filename": fname,
           "tags": [], "relations": {}}
    key = post_batches(lib("/items"), [att])[0]
    form = urllib.parse.urlencode({"md5": hashlib.md5(blob).hexdigest(), "filename": fname,
                                   "filesize": len(blob),
                                   "mtime": int(os.path.getmtime(path) * 1000)})
    hdr = {"Content-Type": "application/x-www-form-urlencoded", "If-None-Match": "*"}
    try:
        auth, _, _ = http("POST", lib(f"/items/{key}/file"), form, hdr)
    except ZoteroError as e:
        if e.code == 413:  # remove o anexo vazio criado acima por esta mesma chamada
            d, _, _ = http("GET", lib(f"/items/{key}"))
            http("DELETE", lib(f"/items/{key}"), headers={"If-Unmodified-Since-Version": str(d["version"])},
                 raw=True)
        raise
    if not auth.get("exists"):
        payload = auth["prefix"].encode() + blob + auth["suffix"].encode()
        http("POST", auth["url"], payload, {"Content-Type": auth["contentType"]}, raw=True, absolute=True)
        http("POST", lib(f"/items/{key}/file"), f"upload={auth['uploadKey']}", hdr, raw=True)
    print(key)


def read_manifest(path):
    """TSV: KEY<TAB>arquivo<TAB>url (arquivo ou url podem ficar vazios; # comenta)."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        linhas = fh.read().splitlines()
    for n, line in enumerate(linhas, 1):
        if not line.strip() or line.startswith("#"):
            continue
        cols = (line.split("\t") + ["", ""])[:3]
        key, f, url = (c.strip() for c in cols)
        if not key or not (f or url):
            die(f"{path}:{n}: linha precisa de KEY e de arquivo ou url")
        rows.append((key, f, url))
    return rows


def cmd_attach_many(a):
    """Anexa em lote; PDFs viram upload e o resto link. Apos um 413, so links."""
    sem_cota = a.links_only
    ok, falhas = 0, 0
    for key, f, url in read_manifest(a.manifest):
        usar_arquivo = f and os.path.isfile(f) and not sem_cota and (a.all_files or f.lower().endswith(".pdf") or not url)
        args = argparse.Namespace(parent=key, title=None, content_type=None,
                                  file=f if usar_arquivo else None,
                                  url=None if usar_arquivo else url, fallback_url=None)
        try:
            if not args.file and not args.url:
                raise ZoteroError(f"arquivo nao encontrado e sem url: {f}")
            try:
                cmd_attach(args)
            except ZoteroError as e:
                if e.code != 413 or not url:
                    raise
                sem_cota = True
                print("aviso: cota de arquivos esgotada (413); restante vira link", file=sys.stderr)
                cmd_attach(argparse.Namespace(**{**vars(args), "file": None, "url": url}))
            print(f"ok\t{key}\t{'arquivo' if args.file and not sem_cota else 'link'}\t{f or url}",
                  file=sys.stderr)
            ok += 1
        except ZoteroError as e:
            print(f"falhou\t{key}\t{f or url}\t{e}", file=sys.stderr)
            falhas += 1
    print(f"{ok} anexo(s), {falhas} falha(s)")
    if falhas:
        sys.exit(1)


def cmd_tag(a):
    data, hdr, _ = http("GET", lib(f"/items/{a.key}"))
    d = data["data"]
    tags = [t for t in d.get("tags", []) if t["tag"] not in (a.remove or [])]
    tags += [{"tag": t} for t in (a.add or []) if t not in {x["tag"] for x in tags}]
    patch = {"tags": tags}
    if a.collection:
        patch["collections"] = sorted(set(d.get("collections", [])) | {a.collection})
    http("PATCH", lib(f"/items/{a.key}"), patch, {"If-Unmodified-Since-Version": str(d["version"])}, raw=True)
    print(f"{a.key} atualizado")


def raw_entries(text):
    """{chave: texto_bruto_da_entrada} preservando a formatacao original."""
    out = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        depth, k = 0, text.index("{", m.start())
        while k < len(text):
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            if depth == 0:
                break
            k += 1
        out[m.group(2)] = text[m.start():k + 1]
    return out


def cmd_bibsync(a):
    """Exporta (bibtex) e acrescenta ao .bib alvo so as entradas novas (chave, DOI e titulo)."""
    if a.from_file:
        novo = open(a.from_file, encoding="utf-8").read()
    else:
        path = lib(f"/collections/{a.collection}/items/top") if a.collection else lib("/items/top")
        p = {"format": a.format, "itemType": "-attachment || note"}
        if a.tag:
            p["tag"] = a.tag
        novo = get_all(path, p, raw=True)
    alvo = open(a.target, encoding="utf-8").read() if os.path.exists(a.target) else ""
    existentes = parse_bib(alvo)
    chaves = {k for _, k, _ in existentes}
    dois = {f.get("doi", "").lower() for _, _, f in existentes if f.get("doi")}
    titulos = {norm(unlatex(f.get("title"))) for _, _, f in existentes}
    brutos = raw_entries(novo)
    add, pul = [], []
    for typ, key, f in parse_bib(novo):
        motivo = ("chave" if key in chaves else
                  "DOI" if f.get("doi", "").lower() in dois and f.get("doi") else
                  "titulo" if norm(unlatex(f.get("title"))) in titulos else None)
        (pul if motivo else add).append((key, motivo, unlatex(f.get("title"))))
    for key, motivo, t in pul:
        print(f"ja no alvo ({motivo}): {key}  {t[:70]}", file=sys.stderr)
    for key, _, t in add:
        print(f"novo: {key}  {t[:70]}", file=sys.stderr)
    if add and not a.dry_run:
        bloco = "\n\n% ---------------------------------------------------------------- Zotero (bibsync)\n"
        bloco += "\n\n".join(brutos[k].strip() for k, _, _ in add) + "\n"
        with open(a.target, "a", encoding="utf-8") as fh:
            fh.write(bloco)
    print(f"{len(add)} nova(s), {len(pul)} ja existente(s)" + (" (dry-run)" if a.dry_run else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("whoami", help="confere a chave e as permissoes").set_defaults(fn=cmd_whoami)
    sp.add_parser("collections", help="arvore de colecoes").set_defaults(fn=cmd_collections)
    p = sp.add_parser("mkcol", help="cria colecao (idempotente), imprime a key")
    p.add_argument("name"); p.add_argument("--parent"); p.set_defaults(fn=cmd_mkcol)
    p = sp.add_parser("search", help="busca rapida em itens de topo")
    p.add_argument("q"); p.add_argument("--collection"); p.add_argument("--tag")
    p.add_argument("--qmode", default="titleCreatorYear", choices=["titleCreatorYear", "everything"])
    p.add_argument("--limit", type=int, default=25); p.set_defaults(fn=cmd_search)
    p = sp.add_parser("get", help="JSON editavel de um item"); p.add_argument("key"); p.set_defaults(fn=cmd_get)
    p = sp.add_parser("export", help="exporta itens (bibtex, biblatex, csljson, ris...)")
    p.add_argument("--collection"); p.add_argument("--tag"); p.add_argument("--out")
    p.add_argument("--format", default="biblatex"); p.set_defaults(fn=cmd_export)
    p = sp.add_parser("convert", help="RIS / BibTeX / lista .txt / DOI / arXiv -> JSON de itens Zotero")
    p.add_argument("src", nargs="+"); p.add_argument("--tag", action="append")
    p.add_argument("--collection"); p.set_defaults(fn=cmd_convert)
    p = sp.add_parser("add", help="cria itens a partir de JSON (lotes de 50)")
    p.add_argument("json", help="arquivo ou - para stdin"); p.add_argument("--collection")
    p.add_argument("--allow-duplicates", action="store_true"); p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_add)
    p = sp.add_parser("attach", help="anexa arquivo (upload) ou link a um item")
    p.add_argument("parent"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file"); g.add_argument("--url"); p.add_argument("--title")
    p.add_argument("--fallback-url", help="com --file: se a cota estourar (413), anexa este link")
    p.add_argument("--content-type"); p.set_defaults(fn=cmd_attach)
    p = sp.add_parser("attach-many", help="anexa em lote a partir de TSV KEY/arquivo/url")
    p.add_argument("manifest"); p.add_argument("--links-only", action="store_true",
                                               help="nunca faz upload, so links")
    p.add_argument("--all-files", action="store_true", help="faz upload tambem de nao-PDF")
    p.set_defaults(fn=cmd_attach_many)
    p = sp.add_parser("tag", help="adiciona/remove tags e colecao de um item")
    p.add_argument("key"); p.add_argument("--add", action="append"); p.add_argument("--remove", action="append")
    p.add_argument("--collection"); p.set_defaults(fn=cmd_tag)
    p = sp.add_parser("bibsync", help="acrescenta ao .bib alvo as entradas novas de uma colecao")
    p.add_argument("target"); p.add_argument("--collection"); p.add_argument("--tag")
    p.add_argument("--format", default="bibtex", choices=["bibtex", "biblatex"])
    p.add_argument("--from-file", help="usa um .bib ja exportado em vez da API")
    p.add_argument("--dry-run", action="store_true"); p.set_defaults(fn=cmd_bibsync)
    a = ap.parse_args()
    if a.cmd != "convert" and not getattr(a, "from_file", None) and not KEY and "localhost" not in BASE:
        die("defina ZOTERO_API_KEY")
    a.fn(a)


def run():
    try:
        main()
    except ZoteroError as e:
        print(f"erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
