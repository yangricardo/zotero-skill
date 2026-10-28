import argparse, io, json, os, pathlib, tempfile, unittest, urllib.error
from unittest import mock

from helpers import FakeAPI, capture, load_zot

zot = load_zot()


def ns(**kw):
    return argparse.Namespace(**kw)


class TestEnvEChave(unittest.TestCase):
    def test_load_env_file_nao_sobrescreve(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write("export ZOTERO_TESTE_A='um'\nZOTERO_TESTE_B=dois\n# comentario\n")
        try:
            os.environ["ZOTERO_TESTE_B"] = "ja"
            zot.load_env_file(fh.name)
            self.assertEqual(os.environ["ZOTERO_TESTE_A"], "um")
            self.assertEqual(os.environ["ZOTERO_TESTE_B"], "ja")
        finally:
            os.unlink(fh.name)
            os.environ.pop("ZOTERO_TESTE_A", None)
            os.environ.pop("ZOTERO_TESTE_B", None)

    def test_check_key_format(self):
        self.assertIsNone(zot.check_key_format("P9NiFoyLeZu2bZNvvuQPDWsd"))
        self.assertIn("25", zot.check_key_format("P9NiFoyLeZu2bZNvvuQPDWsdX"))
        self.assertIsNotNone(zot.check_key_format("'P9NiFoyLeZu2bZNvvuQPDWs'"))

    def test_whoami_usa_keys_current_e_avisa_formato(self):
        api = FakeAPI(zot).on("GET", r"^/keys/current$", {"userID": 1, "username": "u", "access": {}})
        with mock.patch.object(zot, "http", api), mock.patch.object(zot, "KEY", "curta"):
            out, err, _ = capture(zot.cmd_whoami, ns())
        self.assertEqual(api.paths(), ["/keys/current"])
        self.assertIn("aviso", err)
        self.assertEqual(json.loads(out)["username"], "u")

    def test_erro_http_nao_vaza_chave(self):
        segredo = "S" * 24
        err = urllib.error.HTTPError(f"https://api.zotero.org/x?key={segredo}", 403, "x", {},
                                     io.BytesIO(b"Invalid key"))
        with mock.patch.object(zot, "KEY", segredo), \
             mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(zot.ZoteroError) as cm:
                zot.http("GET", f"https://api.zotero.org/x?key={segredo}", absolute=True)
        self.assertEqual(cm.exception.code, 403)
        self.assertNotIn(segredo, str(cm.exception))


class TestEscrita(unittest.TestCase):
    def test_post_batches_lotes_de_50(self):
        def resp(body, _):
            return {"successful": {str(i): {"key": f"K{o['n']}"} for i, o in enumerate(body)},
                    "failed": {}}
        api = FakeAPI(zot).on("POST", r"/items$", resp)
        with mock.patch.object(zot, "http", api):
            keys = zot.post_batches("/users/123/items", [{"n": n} for n in range(120)])
        self.assertEqual(len(api.calls), 3)
        self.assertEqual(keys[0], "K0")
        self.assertEqual(keys[119], "K119")
        tokens = {c["headers"]["Zotero-Write-Token"] for c in api.calls}
        self.assertEqual(len(tokens), 3)

    def test_post_batches_relata_falha(self):
        api = FakeAPI(zot).on("POST", r"/items$", {"successful": {"0": {"key": "OK1"}},
                                                    "failed": {"1": {"code": 400, "message": "campo"}}})
        with mock.patch.object(zot, "http", api):
            out, err, _ = capture(lambda: print(zot.post_batches("/u/items", [{"title": "a"}, {"title": "b"}])))
        self.assertIn("falhou #1 (b): 400 campo", err)
        self.assertIn("OK1", out)

    def test_add_pula_duplicata_e_aplica_colecao(self):
        itens = [{"itemType": "document", "title": "Já Existe!"}, {"itemType": "document", "title": "Novo"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(itens, fh)

        def busca(_, params):
            return [{"key": "OLD1", "data": {"title": "já existe"}}] if params["q"].startswith("Já") else []
        api = (FakeAPI(zot).on("GET", r"/items/top$", busca)
               .on("POST", r"/items$", lambda body, _: {"successful": {"0": {"key": "NEW1"}}}))
        try:
            with mock.patch.object(zot, "http", api):
                out, err, _ = capture(zot.cmd_add, ns(json=fh.name, collection="COL",
                                                      allow_duplicates=False, dry_run=False))
        finally:
            os.unlink(fh.name)
        self.assertIn("ja existe (OLD1)", err)
        self.assertEqual(out.strip(), "NEW1\tNovo")
        enviado = api.calls[-1]["body"]
        self.assertEqual([i["title"] for i in enviado], ["Novo"])
        self.assertEqual(enviado[0]["collections"], ["COL"])

    def test_mkcol_idempotente(self):
        cols = [{"data": {"key": "C1", "name": "EmendasRAG", "parentCollection": False}}]
        api = FakeAPI(zot).on("GET", r"/collections$", cols)
        with mock.patch.object(zot, "http", api):
            out, _, _ = capture(zot.cmd_mkcol, ns(name="EmendasRAG", parent=None))
        self.assertEqual(out.strip(), "C1")
        self.assertEqual(api.paths("POST"), [])


class TestAnexos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.tmp.name, "02_artigo.pdf")
        with open(self.pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 teste")

    def tearDown(self):
        self.tmp.cleanup()

    def att_args(self, **kw):
        base = dict(parent="P1", title=None, content_type=None, file=None, url=None, fallback_url=None)
        base.update(kw)
        return ns(**base)

    def test_link(self):
        api = FakeAPI(zot).on("POST", r"/items$", {"successful": {"0": {"key": "L1"}}})
        with mock.patch.object(zot, "http", api):
            out, _, _ = capture(zot.cmd_attach, self.att_args(url="https://ex.org/p"))
        att = api.calls[0]["body"][0]
        self.assertEqual((att["linkMode"], att["parentItem"], att["url"]), ("linked_url", "P1", "https://ex.org/p"))
        self.assertEqual(out.strip(), "L1")

    def test_upload_completo(self):
        api = (FakeAPI(zot).on("POST", r"/items$", {"successful": {"0": {"key": "F1"}}})
               .on("POST", r"/items/F1/file$", lambda body, _: (
                   {"url": "https://s3/up", "prefix": "<", "suffix": ">", "contentType": "x/y",
                    "uploadKey": "UK"} if "md5=" in body else b""))
               .on("POST", r"^https://s3/up$", b""))
        with mock.patch.object(zot, "http", api):
            out, _, _ = capture(zot.cmd_attach, self.att_args(file=self.pdf))
        self.assertEqual(out.strip(), "F1")
        att = api.calls[0]["body"][0]
        self.assertEqual((att["contentType"], att["filename"]), ("application/pdf", "02_artigo.pdf"))
        self.assertEqual(api.calls[2]["body"], b"<%PDF-1.4 teste>")
        self.assertEqual(api.calls[3]["body"], "upload=UK")

    def test_413_remove_anexo_vazio_e_usa_fallback(self):
        criados = iter(["F1", "L1"])
        api = (FakeAPI(zot)
               .on("POST", r"/items$", lambda *_: {"successful": {"0": {"key": next(criados)}}})
               .on("POST", r"/items/F1/file$", zot.ZoteroError("quota", 413))
               .on("GET", r"/items/F1$", {"data": {}, "version": 7})
               .on("DELETE", r"/items/F1$", b""))
        with mock.patch.object(zot, "http", api):
            out, err, _ = capture(zot.cmd_attach, self.att_args(file=self.pdf, fallback_url="https://ex.org/a.pdf"))
        self.assertIn("413", err)
        self.assertEqual(out.strip(), "L1")
        delete = next(c for c in api.calls if c["method"] == "DELETE")
        self.assertEqual(delete["headers"]["If-Unmodified-Since-Version"], "7")
        self.assertEqual(api.calls[-1]["body"][0]["url"], "https://ex.org/a.pdf")

    def test_attach_many(self):
        html = os.path.join(self.tmp.name, "01_pagina.html")
        open(html, "w").close()
        manifest = os.path.join(self.tmp.name, "m.tsv")
        with open(manifest, "w") as fh:
            fh.write(f"# key\tarquivo\turl\nA1\t{self.pdf}\thttps://ex.org/a.pdf\n"
                     f"A2\t{html}\thttps://ex.org/pagina\nA3\t\thttps://ex.org/so-link\n"
                     f"A4\t{self.tmp.name}/faltou.pdf\t\n")
        feitos = []

        def fake_attach(a):
            feitos.append((a.parent, "arquivo" if a.file else "link"))
        with mock.patch.object(zot, "cmd_attach", fake_attach):
            out, err, code = capture(zot.cmd_attach_many, ns(manifest=manifest, links_only=False, all_files=False))
        self.assertEqual(feitos, [("A1", "arquivo"), ("A2", "link"), ("A3", "link")])
        self.assertIn("falhou\tA4", err)
        self.assertEqual((out.strip(), code), ("3 anexo(s), 1 falha(s)", 1))

    def test_attach_many_413_vira_links(self):
        pdf2 = os.path.join(self.tmp.name, "03.pdf")
        open(pdf2, "wb").close()
        manifest = os.path.join(self.tmp.name, "m.tsv")
        with open(manifest, "w") as fh:
            fh.write(f"A1\t{self.pdf}\thttps://ex.org/1\nA2\t{pdf2}\thttps://ex.org/2\n")
        feitos = []

        def fake_attach(a):
            if a.file:
                raise zot.ZoteroError("quota", 413)
            feitos.append((a.parent, a.url))
        with mock.patch.object(zot, "cmd_attach", fake_attach):
            out, _, code = capture(zot.cmd_attach_many, ns(manifest=manifest, links_only=False, all_files=False))
        self.assertEqual(feitos, [("A1", "https://ex.org/1"), ("A2", "https://ex.org/2")])
        self.assertEqual(code, 0)


class TestBibsync(unittest.TestCase):
    def test_acrescenta_so_novas(self):
        with tempfile.TemporaryDirectory() as d:
            alvo, novo = os.path.join(d, "refs.bib"), os.path.join(d, "novo.bib")
            pathlib.Path(alvo).write_text("@article{a1, title={Velho}, doi={10.1/A}}\n")
            pathlib.Path(novo).write_text("@article{a1, title={Velho}}\n@article{x, title={Outro}, doi={10.1/a}}\n"
                                  "@misc{n1, title={Velho!}}\n@misc{n2, title={Realmente novo}}\n")
            out, err, _ = capture(zot.cmd_bibsync, ns(target=alvo, from_file=novo, collection=None,
                                                      tag=None, format="bibtex", dry_run=False))
            final = pathlib.Path(alvo).read_text()
        self.assertIn("1 nova(s), 3 ja existente(s)", out)
        self.assertIn("(chave)", err); self.assertIn("(DOI)", err); self.assertIn("(titulo)", err)
        self.assertIn("@misc{n2, title={Realmente novo}}", final)
        self.assertEqual(final.count("@"), 2)


if __name__ == "__main__":
    unittest.main()
