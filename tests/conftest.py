from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import JsonStore


class RelojFalso:
    """Reloj controlable para medir duraciones sin esperar."""

    def __init__(self) -> None:
        self.ahora = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **kwargs) -> None:
        self.ahora += timedelta(**kwargs)


DATOS_VALIDOS = {
    "datos_personales": {"dni": "45678912", "nombres": "Rosa María", "apellidos": "Quispe Huamán",
                         "fecha_nacimiento": "1995-04-12"},
    "celular": {"celular": "987654321", "codigo_otp": "123456"},
    "identidad": {"autoriza_validacion": True},
    "terminos": {"acepta_terminos": True, "acepta_tratamiento_datos": True},
    "clave": {"clave": "482915", "confirmacion_clave": "482915"},
}


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def client(reloj):
    app = create_app(store=JsonStore(), reloj=reloj, cargar_demo=False)
    return TestClient(app)


@pytest.fixture
def iniciar(client):
    def _iniciar(canal="redes_sociales"):
        r = client.post("/api/onboardings", json={"canal_adquisicion": canal})
        assert r.status_code == 201, r.text
        return r.json()
    return _iniciar


@pytest.fixture
def completar(client, iniciar, reloj):
    """Recorre los 5 pasos con datos válidos, un minuto por paso."""
    def _completar(canal="redes_sociales", dni="45678912", minutos_por_paso=1):
        ob = iniciar(canal)
        for paso, datos in DATOS_VALIDOS.items():
            if paso == "datos_personales":
                datos = {**datos, "dni": dni}
            reloj.avanzar(minutes=minutos_por_paso)
            r = client.post(f"/api/onboardings/{ob['id']}/pasos/{paso}", json=datos)
            assert r.status_code == 200, r.text
        return r.json()
    return _completar
