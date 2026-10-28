"""Carrega scripts/zot.py isolado do ambiente real e simula a API."""
import importlib.util, io, os, pathlib, re, sys
from contextlib import redirect_stderr, redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def load_zot():
    for k in ("ZOTERO_API_KEY", "ZOTERO_LIBRARY", "ZOTERO_BASE"):
        os.environ.pop(k, None)
    os.environ["ZOTERO_ENV_FILE"] = str(FIXTURES / "nao-existe.env")
    spec = importlib.util.spec_from_file_location("zot", ROOT / "scripts" / "zot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.KEY = "A" * 24
    mod.LIB = "users/123"
    return mod


class FakeAPI:
    """Substitui zot.http: responde por (metodo, regex do caminho) e grava as chamadas."""

    def __init__(self, zot):
        self.zot, self.calls, self.routes = zot, [], []

    def on(self, method, pattern, response):
        self.routes.append((method, re.compile(pattern), response))
        return self

    def __call__(self, method, path, body=None, headers=None, params=None, raw=False, absolute=False):
        self.calls.append({"method": method, "path": path, "body": body,
                           "headers": headers or {}, "params": params})
        for m, rx, resp in self.routes:
            if m == method and rx.search(path):
                out = resp(body, params) if callable(resp) else resp
                if isinstance(out, Exception):
                    raise out
                return out, {}, 200
        raise AssertionError(f"rota nao simulada: {method} {path}")

    def paths(self, method=None):
        return [c["path"] for c in self.calls if method in (None, c["method"])]


def capture(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            fn(*args)
        except SystemExit as e:
            code = e.code
    return out.getvalue(), err.getvalue(), code
