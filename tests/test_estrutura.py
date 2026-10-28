"""Confere a estrutura do plugin: frontmatter das skills, caminhos citados e manifestos."""
import json
import re
import unittest

from helpers import ROOT

SKILLS = ["zotero-api", "zotero-importar-fontes", "zotero-bib-lncs"]


def frontmatter(texto):
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    if not m:
        return {}
    return dict(linha.split(": ", 1) for linha in m.group(1).splitlines() if ": " in linha)


class TestEstrutura(unittest.TestCase):
    def test_cada_skill_tem_frontmatter_valido(self):
        for nome in SKILLS:
            with self.subTest(skill=nome):
                fm = frontmatter((ROOT / "skills" / nome / "SKILL.md").read_text("utf-8"))
                self.assertEqual(fm.get("name"), nome)
                self.assertTrue(10 < len(fm.get("description", "")) <= 1024)

    def test_skills_de_fluxo_apontam_para_o_cliente(self):
        cliente = ROOT / "skills" / "zotero-api" / "scripts" / "zot.py"
        self.assertTrue(cliente.is_file())
        for nome in SKILLS[1:]:
            with self.subTest(skill=nome):
                texto = (ROOT / "skills" / nome / "SKILL.md").read_text("utf-8")
                self.assertIn("../zotero-api/scripts/zot.py", texto)
                self.assertTrue((ROOT / "skills" / nome / "../zotero-api/scripts/zot.py").resolve().is_file())

    def test_comandos_citados_existem_no_cliente(self):
        ajuda = (ROOT / "skills" / "zotero-api" / "scripts" / "zot.py").read_text("utf-8")
        for nome in SKILLS:
            texto = (ROOT / "skills" / nome / "SKILL.md").read_text("utf-8")
            for cmd in set(re.findall(r"\$Z ([a-z-]+)", texto)):
                with self.subTest(skill=nome, comando=cmd):
                    self.assertIn(f'"{cmd}"', ajuda)

    def test_manifestos_do_plugin(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        mkt = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
        self.assertEqual(plugin["name"], mkt["plugins"][0]["name"])
        self.assertEqual(plugin["license"], "MIT")
        self.assertTrue((ROOT / "LICENSE").is_file())


if __name__ == "__main__":
    unittest.main()
