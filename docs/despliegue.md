# Despliegue

La app es **un solo servicio**: FastAPI sirve la API (`/api/...`) y el frontend (`/`). Se empaqueta con el `Dockerfile` de la raíz.

> Antes de publicar en internet, confirmen con el instructor que está permitido. Usen solo datos ficticios.

## Opción 1 · Local (recomendada para la presentación)

No depende del wifi ni de servicios externos.

```bash
uvicorn app.main:create_app --factory
```

O con Docker:

```bash
docker build -t wallet-onboarding-mvp .
docker run --rm -p 8000:8000 wallet-onboarding-mvp
```

## Opción 2 · Render (enlace público)

El repo trae un blueprint, `render.yaml`.

1. Crear una cuenta en https://render.com con GitHub.
2. **New → Blueprint** y elegir este repositorio. Render detecta `render.yaml`.
3. Pulsar **Apply**. Al terminar da una URL `https://wallet-onboarding-mvp-xxxx.onrender.com`.

Notas del plan gratuito (revisen las condiciones vigentes):
- El servicio se "duerme" sin tráfico y tarda unos segundos en despertar. Ábranlo un par de minutos antes de presentar.
- El disco es efímero: los registros (`data/db.json`) se borran al reiniciar. Los datos ficticios se regeneran solos.

## Opción 3 · Otros servicios con Docker

Cualquier servicio que despliegue un `Dockerfile` funciona igual (Railway, Fly.io, Google Cloud Run, Azure Container Apps). La app escucha en el puerto indicado por la variable `PORT` (8000 por defecto) y expone el health check en `/api/salud`.

## Respaldo · GitHub Codespaces

Si una laptop falla: en GitHub, **Code → Codespaces → Create codespace**, y luego:

```bash
pip install -r requirements.txt
uvicorn app.main:create_app --factory
```

Codespaces ofrece abrir el puerto 8000 en el navegador.

## CI

`.github/workflows/ci.yml` ejecuta las pruebas y construye la imagen Docker en cada push y pull request.
