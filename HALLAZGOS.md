# Hallazgos de exploracion

Fecha: 2026-10-30

## Alcance y metodo

Se utilizo `openspec-explore` en modo de solo lectura y se contrastaron el plan, la especificacion, las tareas, la arquitectura, el codigo y las pruebas relacionadas con el onboarding.

El CLI encontro la raiz OpenSpec del proyecto, pero no reporto cambios activos ni specs OpenSpec registradas. La documentacion funcional del onboarding esta en `specs/001-registro-activacion/`.

## Skills de OpenSpec

De los skills OpenSpec disponibles, `openspec-explore` permite investigar sin modificar codigo ni archivos por defecto. Puede capturar artefactos OpenSpec solo dentro del alcance confirmado.

Los demas skills tienen efectos de escritura o implementacion:

| Skill | Efecto |
|---|---|
| `openspec-propose` | Crea artefactos de planificacion para un cambio. |
| `openspec-apply-change` | Implementa tareas y modifica codigo. |
| `openspec-update-change` | Modifica los artefactos de planificacion existentes. |
| `openspec-sync-specs` | Copia cambios a las especificaciones principales. |
| `openspec-archive-change` | Archiva un cambio completado. |

Para esta revision se uso solo `openspec-explore`; no se ejecuto ningun skill que implemente o escriba artefactos OpenSpec.

## F-1: identidad rechazada aparece como paso completado

**Prioridad: media**

Al rechazar la validacion de identidad, el servicio registra `paso_fallido` y cierra el onboarding como `RECHAZADO`. Sin embargo, la funcion que procesa el paso continua despues de ese cierre: agrega `identidad` a `pasos_completados` y emite tambien `paso_completado`. Al construir la respuesta, el backend prioriza la lista de pasos completados antes de marcar identidad como `FALLIDO`.

**Impacto:** la pantalla de rechazo muestra el paso de identidad como completado en el progreso. Ademas, la secuencia de eventos representa la misma validacion como fallida y completada, lo que vuelve ambiguos los datos de analitica.

**Evidencia:**

- [app/onboarding.py](app/onboarding.py): `_aplicar_paso` registra el rechazo, cierra el flujo y luego ejecuta la logica comun que marca el paso como completado. `_vista` clasifica primero cualquier paso presente en `pasos_completados`.
- [frontend/app.js](frontend/app.js): `progreso` representa los estados que recibe del backend; `vistaRechazada` presenta ese progreso en la pantalla de rechazo.
- [frontend/styles.css](frontend/styles.css): existe un estilo para el estado `FALLIDO`, pero este caso no llega a usarlo.
- [tests/test_ca2_validaciones.py](tests/test_ca2_validaciones.py): la prueba de identidad rechazada verifica el estado del flujo, la wallet y el mensaje, pero no el estado del paso ni sus eventos.
- [tests/test_ca4_eventos.py](tests/test_ca4_eventos.py): prueba los eventos del flujo exitoso y errores de validacion, pero no la secuencia de eventos para identidad rechazada.
- [docs/supuestos-y-decisiones.md](docs/supuestos-y-decisiones.md): DEC-7 define el cierre del flujo cuando la identidad no se valida; DEC-4 define el registro de intentos fallidos.

**Verificacion recomendada para una futura correccion:** comprobar que la respuesta marque identidad como `FALLIDO`, que el flujo siga `RECHAZADO` y que los eventos incluyan el fallo y el cierre, sin `paso_completado` para identidad.

## Riesgos ya documentados

Estos puntos constan como limitaciones del MVP y no son hallazgos nuevos de esta exploracion:

- No hay autenticacion de sesion; conocer el id permite consultar un onboarding.
- No hay limite de intentos para OTP ni clave.
- OTP e identidad son simulados.
- El almacenamiento JSON y el punto de entrada de pagos son adecuados para la demo, no una implementacion de produccion.

El detalle esta en [docs/supuestos-y-decisiones.md](docs/supuestos-y-decisiones.md) y en los requisitos RS-6 y RS-7 de [specs/001-registro-activacion/spec.md](specs/001-registro-activacion/spec.md).

## Limites de esta revision

No se modifico codigo y no se ejecutaron pruebas automatizadas. Las observaciones se basan en lectura del codigo y de las pruebas existentes.