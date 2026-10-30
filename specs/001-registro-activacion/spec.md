# SPEC-001 · Registro y activación del MVP de wallet

| Campo | Valor |
|---|---|
| Épica | MVP de wallet en Perú para pagos cotidianos |
| Estado | Aprobada para la demo · v1.0 |
| Origen | **Formalizada después de la implementación** a partir de la historia, los criterios y las decisiones del equipo. Desde esta versión, la spec es la fuente de verdad: cualquier cambio de comportamiento empieza aquí. |
| Plan | [plan.md](plan.md) · Contrato: [contracts/openapi.yaml](contracts/openapi.yaml) · Tareas: [tasks.md](tasks.md) |

## 1. Historia

> Como usuario de smartphone que realiza transferencias diarias de bajo monto,
> quiero completar el onboarding de la wallet con un flujo guiado y señales claras de siguiente paso,
> para poder empezar a pagar sin abandonar el proceso.

**Objetivo de negocio:** reducir la mediana del onboarding de 8 a 3 minutos y medir MAU (1,000–2,000) y CAC (PEN 10) en los meses 1 a 3.

**Actores:** usuario que se registra · equipo de producto y analítica · cumplimiento.

## 2. Alcance

**Incluye:** onboarding de 5 pasos, validaciones, activación de la wallet, acceso al punto de entrada de pagos, eventos analíticos y reporte de mediana, nuevos activos, gasto y CAC.

**No incluye:** los pagos en sí (otra historia), integraciones reales de OTP e identidad (simuladas), autenticación de sesión, recuperación desde otro dispositivo.

## 3. Criterios de aceptación

Cada criterio tiene un ID estable. Las pruebas citan ese ID y `tools/check_trazabilidad.py` comprueba que ningún criterio quede sin pruebas.

### CA-1 · Secuencia de pasos y paso actual visibles

El flujo de onboarding muestra la secuencia de pasos requeridos y el paso actual en todo momento.

```gherkin
Escenario: Al iniciar se ven los 5 pasos
  Dado que inicio el registro
  Entonces la respuesta incluye 5 pasos en orden: datos_personales, celular, identidad, terminos, clave
  Y exactamente un paso tiene estado ACTUAL y es "datos_personales"
  Y "siguiente_accion" empieza con "Paso 1 de 5"

Escenario: El paso actual avanza al completar un paso
  Dado que completé n pasos (n < 5)
  Entonces los pasos 1..n tienen estado COMPLETADO y el paso n+1 es ACTUAL

Escenario: Retomar
  Dado que completé el paso 1 y vuelvo a consultar mi registro
  Entonces el paso actual es "celular"
```

### CA-2 · Bloqueo con mensaje accionable

Si falta información obligatoria o hay datos inválidos, el flujo bloquea el avance y muestra un mensaje accionable para corregir.

```gherkin
Escenario: Dato inválido
  Dado que envío un paso con un dato que incumple una regla RN-n
  Entonces recibo 422 con codigo "DATOS_INVALIDOS"
  Y "errores" lista cada campo inválido con campo, codigo y mensaje en español que indica cómo corregir
  Y el paso actual no cambia

Escenario: Corregir y avanzar
  Dado que recibí un 422 en un paso
  Cuando reenvío el paso con datos válidos
  Entonces avanzo al siguiente paso
```

### CA-3 · Wallet activa y acceso a pagos

Cuando el onboarding finaliza correctamente, el estado de la wallet cambia a activo y el usuario puede acceder al punto de entrada de pagos de bajo monto.

```gherkin
Escenario: Activación
  Dado que completo los 5 pasos con datos válidos
  Entonces el registro queda COMPLETADO, la wallet ACTIVA y "puede_pagar" es true
  Y "punto_entrada_pagos" apunta a /api/wallets/{wallet_id}/pagos

Escenario: Wallet no activa
  Dado que mi wallet no está ACTIVA
  Cuando pido el punto de entrada de pagos
  Entonces recibo 403 con codigo "WALLET_NO_ACTIVA" y un mensaje para completar el registro
```

### CA-4 · Eventos de inicio, pasos y cierre

El sistema registra eventos de inicio de onboarding, finalización de cada paso y cierre del flujo para analítica del MVP.

```gherkin
Escenario: Registro exitoso
  Entonces se registran, en orden: onboarding_iniciado, paso_completado (x5), wallet_activada, onboarding_cerrado (resultado COMPLETADO)

Escenario: Intento fallido
  Cuando un paso responde 422
  Entonces se registra paso_fallido con paso y codigo_error

Escenario: Abandono
  Cuando el usuario sale del registro
  Entonces se registra onboarding_cerrado con resultado ABANDONADO y ultimo_paso
```

Cada evento tiene `id`, `tipo`, `onboarding_id`, `canal` y `ocurrido_en` (ISO 8601, UTC). Ver RS-1.

### CA-5 · Mediana de duración del onboarding

Para la cohorte MVP en Perú, el tiempo mediano de finalización de onboarding baja de 8 minutos a 3 minutos dentro del trimestre posterior al lanzamiento.

> Meta de negocio: se verifica en producción. Esta spec exige la **medición**.

```gherkin
Escenario: Cálculo
  Dado onboardings completados con duraciones de 5, 10 y 15 minutos
  Entonces la mediana reportada es 10 minutos y "cumple_objetivo_mediana" es false
```

**Definición (DEC-1):** duración = `ocurrido_en(wallet_activada) − ocurrido_en(onboarding_iniciado)`. Solo cuentan los onboardings completados.

### CA-6 · Nuevos usuarios activos, gasto y CAC por mes

La salida analítica incluye conteos mensuales de nuevos usuarios activos y la atribución de gasto de adquisición necesaria para verificar MAU entre 1,000 y 2,000 y CAC de PEN 10 por usuario nuevo en los primeros 3 meses.

```gherkin
Escenario: CAC por mes y canal
  Dado 2 wallets activadas en un mes y un gasto de S/ 20 en ese mes
  Entonces el reporte muestra 2 nuevos usuarios activos, gasto S/ 20 y CAC S/ 10
  Y el desglose por canal

Escenario: Sin gasto
  Dado un mes con activaciones y sin gasto registrado
  Entonces el CAC es null y "cumple_cac" es null (no se informa 0)
```

## 4. Reglas de negocio

| ID | Regla | Código de error |
|---|---|---|
| RN-1 | El DNI es obligatorio y tiene exactamente 8 dígitos. | `CAMPO_OBLIGATORIO`, `DNI_INVALIDO` |
| RN-2 | Nombres y apellidos son obligatorios: solo letras, espacios, apóstrofo o guion, de 2 a 60 caracteres. | `CAMPO_OBLIGATORIO`, `NOMBRE_INVALIDO` |
| RN-3 | La fecha de nacimiento usa el formato AAAA-MM-DD; la persona tiene entre 18 y 120 años. | `FECHA_INVALIDA`, `MENOR_DE_EDAD` |
| RN-4 | El celular tiene 9 dígitos y empieza por 9. Se aceptan el prefijo +51, espacios y guiones. | `CELULAR_INVALIDO` |
| RN-5 | El código OTP tiene 6 dígitos y debe coincidir (simulado: `123456`). | `OTP_FORMATO_INVALIDO`, `OTP_INCORRECTO` |
| RN-6 | La validación de identidad requiere autorización explícita. Si el DNI no se valida (simulado: `99999999`), la wallet queda RECHAZADA y el registro se cierra. | `AUTORIZACION_REQUERIDA`, `IDENTIDAD_NO_VALIDADA` |
| RN-7 | Se deben aceptar los términos y el tratamiento de datos personales (Ley N.° 29733). | `TERMINOS_REQUERIDOS`, `TRATAMIENTO_DATOS_REQUERIDO` |
| RN-8 | La clave tiene 6 dígitos; no puede ser repetida, secuencial ni la fecha de nacimiento (DDMMAA o AAMMDD). La confirmación debe coincidir. | `CLAVE_FORMATO_INVALIDO`, `CLAVE_INSEGURA`, `CLAVES_NO_COINCIDEN` |
| RN-9 | Un DNI no puede tener dos wallets activas. | `DNI_YA_REGISTRADO` |
| RN-10 | Los pasos se completan en orden. | `PASO_FUERA_DE_ORDEN` (409) |
| RN-11 | Un registro cerrado no acepta pasos nuevos. | `ONBOARDING_CERRADO` (409) |
| RN-12 | El canal de adquisición es uno de: `organico`, `redes_sociales`, `referidos`, `campana_comercios`. | `CANAL_INVALIDO` |

## 5. Requisitos de seguridad y privacidad

| ID | Requisito | Estado |
|---|---|---|
| RS-1 | Los eventos analíticos no contienen datos personales (DNI, nombres, celular, clave). | Cubierto |
| RS-2 | La clave se guarda con un hash con sal (PBKDF2-SHA256) y nunca en texto plano. | Cubierto |
| RS-3 | Toda regla RN-n se valida en el servidor; la validación del cliente no la reemplaza. | Cubierto |
| RS-4 | DNI y celular se devuelven enmascarados (solo los 3 últimos dígitos). | Cubierto |
| RS-5 | Las respuestas de error no exponen detalles internos (trazas, rutas, consultas). | Cubierto |
| RS-6 | El acceso a un registro debe estar ligado a una sesión autenticada del dispositivo. | **Pendiente**, fuera del MVP |
| RS-7 | Límite de intentos para OTP y clave, con bloqueo temporal. | **Pendiente**, fuera del MVP |

## 6. Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-1 | La interfaz se usa en celular (ancho de 390 px) sin desplazamiento horizontal. |
| RNF-2 | Todos los mensajes al usuario están en español y dicen qué hacer. |
| RNF-3 | El almacenamiento escribe de forma atómica: un fallo a mitad de escritura no deja el archivo corrupto. |
| RNF-4 | Las pruebas automatizadas se ejecutan sin servicios externos. |

## 7. Supuestos y preguntas

Ver [docs/supuestos-y-decisiones.md](../../docs/supuestos-y-decisiones.md): SUP-1 a SUP-8 y PREG-1 a PREG-5.
