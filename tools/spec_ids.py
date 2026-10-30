"""Lectura de los IDs definidos en la spec (CA-n, RN-n, RS-n, RNF-n)."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SPEC_DIR = RAIZ / "specs" / "001-registro-activacion"
SPEC = SPEC_DIR / "spec.md"
CONTRATO = SPEC_DIR / "contracts" / "openapi.yaml"

ID_RE = re.compile(r"\b(CA|RN|RS|RNF)-\d+\b")


def ids_definidos(texto: str) -> set[str]:
    """IDs definidos en la spec: encabezados `### CA-n` y primeras columnas de tabla `| RN-n |`."""
    ids = set(re.findall(r"^###\s+(CA-\d+)\b", texto, re.MULTILINE))
    ids |= set(re.findall(r"^\|\s*((?:RN|RS|RNF)-\d+)\s*\|", texto, re.MULTILINE))
    return ids


def criterios(texto: str) -> list[str]:
    return sorted({i for i in ids_definidos(texto) if i.startswith("CA-")}, key=lambda x: int(x[3:]))


def leer_spec(ruta: Path = SPEC) -> str:
    return ruta.read_text(encoding="utf-8")
