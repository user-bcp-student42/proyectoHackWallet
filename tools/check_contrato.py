"""Verifica que el contrato OpenAPI de la spec y la API real coincidan.

Falla si:
  - una operación del contrato no existe en la app, o la app expone una que no está en el contrato;
  - una operación del contrato no declara `x-spec` o cita un ID que no existe en spec.md;
  - un criterio CA-n de la spec no está cubierto por ninguna operación.

Uso: python tools/check_contrato.py [--json]
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_ids import CONTRATO, RAIZ, criterios, ids_definidos, leer_spec  # noqa: E402

METODOS = {"get", "post", "put", "patch", "delete"}


def _normalizar(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", ruta)


def operaciones_contrato(contrato: dict) -> dict[tuple[str, str], dict]:
    return {(m.upper(), _normalizar(ruta)): op
            for ruta, item in contrato.get("paths", {}).items()
            for m, op in item.items() if m in METODOS}


def operaciones_app() -> set[tuple[str, str]]:
    sys.path.insert(0, str(RAIZ))
    os.environ.setdefault("DEMO_ENDPOINTS", "true")
    from app.main import create_app
    from app.store import JsonStore

    app = create_app(store=JsonStore(), cargar_demo=False)
    return {(m, _normalizar(r.path)) for r in app.routes
            if r.path.startswith("/api") for m in (getattr(r, "methods", None) or []) if m != "HEAD"}


def verificar(contrato: dict, texto_spec: str, reales: set[tuple[str, str]]) -> tuple[bool, list[str]]:
    ops = operaciones_contrato(contrato)
    validos = ids_definidos(texto_spec)
    errores = [f"{m} {r} está en el contrato pero no en la app" for m, r in sorted(set(ops) - reales)]
    errores += [f"{m} {r} está en la app pero no en el contrato" for m, r in sorted(reales - set(ops))]
    citados: set[str] = set()
    for (m, r), op in sorted(ops.items()):
        refs = op.get("x-spec") or []
        if not refs:
            errores.append(f"{m} {r} no declara x-spec")
        for ref in refs:
            if ref not in validos:
                errores.append(f"{m} {r} cita {ref}, que no existe en la spec")
        citados.update(refs)
    errores += [f"{ca} no está cubierto por ninguna operación del contrato"
                for ca in criterios(texto_spec) if ca not in citados]
    return not errores, errores


def main() -> int:
    contrato = yaml.safe_load(CONTRATO.read_text(encoding="utf-8"))
    reales = operaciones_app()
    ok, errores = verificar(contrato, leer_spec(), reales)
    total = len(operaciones_contrato(contrato))
    if "--json" in sys.argv:
        print(json.dumps({"ok": ok, "operaciones": total, "errores": errores}, ensure_ascii=False, indent=2))
    else:
        print(f"Contrato ({total} operaciones) frente a la API real")
        for e in errores:
            print(f"  ERROR: {e}")
        print("OK" if ok else "FALLÓ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
