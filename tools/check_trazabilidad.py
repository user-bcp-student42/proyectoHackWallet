"""Verifica que cada criterio CA-n de la spec tenga pruebas automatizadas.

Un archivo de pruebas cubre los criterios que cita en su docstring de módulo
(por ejemplo: «CA-5 y CA-6: ...»). Falla si:
  - un criterio de la spec no tiene ningún archivo de pruebas, o
  - un archivo de pruebas cita un criterio que no existe en la spec.

Uso: python tools/check_trazabilidad.py [--json]
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_ids import RAIZ, criterios, leer_spec  # noqa: E402

TESTS = RAIZ / "tests"


def cobertura(tests_dir: Path = TESTS) -> dict[str, list[dict]]:
    por_ca: dict[str, list[dict]] = {}
    for archivo in sorted(tests_dir.glob("test_*.py")):
        modulo = ast.parse(archivo.read_text(encoding="utf-8"))
        doc = ast.get_docstring(modulo) or ""
        pruebas = [n.name for n in modulo.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
        for ca in sorted(set(re.findall(r"\bCA-\d+\b", doc))):
            por_ca.setdefault(ca, []).append({"archivo": f"tests/{archivo.name}", "pruebas": len(pruebas)})
    return por_ca


def verificar(texto_spec: str, tests_dir: Path = TESTS) -> tuple[bool, list[dict], list[str]]:
    esperados = criterios(texto_spec)
    cubiertos = cobertura(tests_dir)
    filas = [{"criterio": ca, "archivos": cubiertos.get(ca, [])} for ca in esperados]
    errores = [f"{ca} no tiene pruebas" for ca in esperados if ca not in cubiertos]
    errores += [f"{ca} se cita en {', '.join(a['archivo'] for a in arch)} pero no existe en la spec"
                for ca, arch in cubiertos.items() if ca not in esperados]
    return not errores, filas, errores


def main() -> int:
    ok, filas, errores = verificar(leer_spec())
    if "--json" in sys.argv:
        print(json.dumps({"ok": ok, "criterios": filas, "errores": errores}, ensure_ascii=False, indent=2))
    else:
        print("Trazabilidad spec → pruebas")
        for f in filas:
            detalle = ", ".join(f"{a['archivo']} ({a['pruebas']} funciones de prueba)" for a in f["archivos"]) or "SIN PRUEBAS"
            print(f"  {'✓' if f['archivos'] else '✗'} {f['criterio']}: {detalle}")
        for e in errores:
            print(f"  ERROR: {e}")
        print("OK" if ok else "FALLÓ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
