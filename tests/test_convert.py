import unittest
from unittest import mock

from helpers import FIXTURES, load_zot

zot = load_zot()


class TestCreator(unittest.TestCase):
    def test_pessoa_com_virgula(self):
        self.assertEqual(zot.creator("Finardi, Paulo"),
                         {"creatorType": "author", "lastName": "Finardi", "firstName": "Paulo"})

    def test_instituicao_com_virgula_fica_inteira(self):
        c = zot.creator("Câmara dos Deputados, Consultoria de Orçamento")
        self.assertEqual(c["name"], "Câmara dos Deputados, Consultoria de Orçamento")

    def test_sem_virgula_e_nome_unico(self):
        self.assertEqual(zot.creator("Transparência Brasil"),
                         {"creatorType": "author", "name": "Transparência Brasil"})


class TestItem(unittest.TestCase):
    def test_filtra_campos_por_tipo(self):
        it = zot.item("webpage", {"title": "T", "volume": "3", "websiteTitle": "W"})
        self.assertEqual(it["websiteTitle"], "W")
        self.assertNotIn("volume", it)

    def test_doi_vai_para_extra_quando_tipo_nao_tem_campo(self):
        it = zot.item("report", {"title": "T", "DOI": "10.1/x", "extra": "nota"})
        self.assertEqual(it["extra"], "nota\nDOI: 10.1/x")

    def test_tags_sem_duplicatas_e_vazias(self):
        it = zot.item("document", {"title": "T"}, tags=["a", "b", "a", ""])
        self.assertEqual(it["tags"], [{"tag": "a"}, {"tag": "b"}])


class TestRIS(unittest.TestCase):
    def setUp(self):
        text = (FIXTURES / "exemplo.ris").read_text(encoding="utf-8-sig")
        self.items = zot.from_ris(text, tags=["extra-tag"], collections=["COL1"])

    def test_conta_itens(self):
        self.assertEqual(len(self.items), 12)

    def test_tipos(self):
        tipos = {i["itemType"] for i in self.items}
        self.assertTrue({"report", "document", "webpage", "dataset", "thesis"} <= tipos)

    def test_campos_e_tags(self):
        pix = next(i for i in self.items if i["title"] == "Emendas Pix 2024")
        self.assertEqual(pix["date"], "2024")
        self.assertEqual(pix["collections"], ["COL1"])
        tags = [t["tag"] for t in pix["tags"]]
        self.assertEqual(tags, ["EmendasRAG", "pesquisa-rag-enxuto", "extra-tag"])

    def test_varios_autores(self):
        sug = next(i for i in self.items if i["title"].startswith("Sugestões"))
        self.assertEqual(len(sug["creators"]), 3)

    def test_todos_tem_url(self):
        self.assertTrue(all(i.get("url") for i in self.items))


BIB = r"""
@article{silva2024,
  author = {Silva, Jo{\~a}o and Souza, Maria and others},
  title = {{Emendas} e {RAG}},
  journal = {Revista X},
  year = 2024,
  pages = {10--20},
  doi = {10.1234/abc}
}
@misc{finardi2024,
  author = "Finardi, Paulo",
  title = "The Chronicles of RAG",
  howpublished = {arXiv:2401.07883},
}
@techreport{tb, title={Relat\'orio}, institution={Transpar\^encia Brasil}, doi={10.9/z}}
"""


class TestBib(unittest.TestCase):
    def test_parse(self):
        e = zot.parse_bib(BIB)
        self.assertEqual([k for _, k, _ in e], ["silva2024", "finardi2024", "tb"])
        self.assertEqual(e[0][2]["year"], "2024")

    def test_unlatex(self):
        self.assertEqual(zot.unlatex(r"Jo{\~a}o \& {RAG} 10--20"), "João & RAG 10-20")
        self.assertEqual(zot.unlatex(r"Relat\'orio"), "Relatório")

    def test_from_bib(self):
        a, b, c = zot.from_bib(BIB, tags=["t"])
        self.assertEqual(a["itemType"], "journalArticle")
        self.assertEqual(a["DOI"], "10.1234/abc")
        self.assertEqual(a["pages"], "10-20")
        self.assertEqual(a["creators"][0]["firstName"], "João")
        self.assertEqual(len(a["creators"]), 2)  # "others" descartado
        self.assertIn("Citation Key: silva2024", a["extra"])
        self.assertEqual(b["itemType"], "preprint")
        self.assertEqual(b["archiveID"], "arXiv:2401.07883")
        self.assertEqual(c["institution"], "Transparência Brasil")
        self.assertIn("DOI: 10.9/z", c["extra"])


class TestCSLeIds(unittest.TestCase):
    def test_from_csl(self):
        it = zot.from_csl({"type": "paper-conference", "title": ["Arquitetura RAG"],
                           "issued": {"date-parts": [[2026, 5, 3]]}, "DOI": "10.5753/x",
                           "container-title": "Anais do SEMISH",
                           "author": [{"family": "Lima", "given": "Ana"}, {"literal": "Grupo X"}],
                           "abstract": "<p>Resumo</p>"})
        self.assertEqual(it["itemType"], "conferencePaper")
        self.assertEqual(it["date"], "2026-05-03")
        self.assertEqual(it["proceedingsTitle"], "Anais do SEMISH")
        self.assertEqual(it["abstractNote"], "Resumo")
        self.assertEqual(it["creators"][1], {"creatorType": "author", "name": "Grupo X"})

    def test_from_id_despacha(self):
        with mock.patch.object(zot, "from_arxiv", return_value="ARX") as fa, \
             mock.patch.object(zot, "from_doi", return_value="DOI") as fd:
            self.assertEqual(zot.from_id("arXiv:2506.10380"), "ARX")
            self.assertEqual(zot.from_id("2506.10380v1"), "ARX")
            self.assertEqual(zot.from_id("https://doi.org/10.5753/semish.2026.23972"), "DOI")
            fd.assert_called_with("10.5753/semish.2026.23972")
            fa.assert_called_with("2506.10380v1")

    def test_from_id_invalido(self):
        with self.assertRaises(zot.ZoteroError):
            zot.from_id("isso nao e id")

    def test_from_arxiv_parseia_atom(self):
        atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>TableRAG:  A Framework</title><summary>Abs</summary>
          <published>2025-06-12T00:00:00Z</published>
          <author><name>Xiaohan Yu</name></author></entry></feed>"""
        with mock.patch.object(zot, "http", return_value=(atom, {}, 200)):
            it = zot.from_arxiv("arXiv:2506.10380v1", tags=["t"])
        self.assertEqual(it["title"], "TableRAG: A Framework")
        self.assertEqual(it["date"], "2025-06-12")
        self.assertEqual(it["DOI"], "10.48550/arXiv.2506.10380")
        self.assertEqual(it["creators"][0]["lastName"], "Yu")


if __name__ == "__main__":
    unittest.main()
