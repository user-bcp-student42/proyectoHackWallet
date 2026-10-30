"""Almacenamiento simple en un archivo JSON (o solo en memoria).

No es una base de datos real: sirve para la demo del MVP. Todas las
operaciones pasan por un lock y cada escritura reemplaza el archivo de
forma atómica (archivo temporal + os.replace) para no dejarlo corrupto.

Si un bloque `write()` lanza una excepción, el archivo no se guarda, pero la
copia en memoria no se revierte: los servicios validan antes de modificar.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

MEMORY = ":memory:"


def empty_db() -> dict[str, Any]:
    return {
        "onboardings": {},
        "wallets": {},
        "eventos": [],
        "gasto_adquisicion": [],
    }


class JsonStore:
    def __init__(self, path: str = MEMORY) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()
        # Datos ficticios para la analítica: viven solo en memoria (se regeneran
        # al iniciar) para no reescribir varios MB en cada operación.
        self.demo: dict[str, list] = {"eventos": [], "gasto_adquisicion": []}

    @property
    def in_memory(self) -> bool:
        return self.path == MEMORY

    def _load(self) -> dict[str, Any]:
        if self.in_memory or not Path(self.path).exists():
            return empty_db()
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        base = empty_db()
        base.update(data)
        return base

    def _flush(self) -> None:
        if self.in_memory:
            return
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".db-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        os.replace(tmp, target)

    @contextmanager
    def write(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            yield self._data
            self._flush()

    @contextmanager
    def read(self) -> Iterator[dict[str, Any]]:
        with self._lock:
            yield self._data

    def reset(self) -> None:
        with self.write() as db:
            db.clear()
            db.update(empty_db())
