# Guion de la demo (unos 5 minutos)

Antes de empezar: abre la app, despliega "Datos de prueba" y pulsa **Reiniciar datos de la demo**.

## 1. Contexto (30 s)

"Elegimos la historia de **registro y activación**. El problema: el onboarding tarda 8 minutos y mucha gente abandona. La meta es bajarlo a 3 minutos y medir MAU y CAC."

## 2. Flujo feliz con errores (2 min), en vista de celular

1. Pantalla de bienvenida: elegir el canal "Me lo recomendó alguien" y pulsar **Empezar**.
   *Señalar:* "Paso 1 de 5", los 5 pasos visibles y el cronómetro (**CA-1**).
2. Escribir el DNI `1234` y pulsar Continuar.
   *Señalar:* no avanza y cada campo dice cómo corregirse (**CA-2**).
3. Completar los datos válidos. Celular `987654321`, **Enviar código**, OTP `123456`.
4. **Recargar la página**: el registro sigue en el paso 3 ("retomamos tu registro").
5. Autorizar la identidad y aceptar los términos.
6. Clave `123456`: rechazada por insegura. Usar `482915`.
7. Mostrar "¡Tu wallet está activa!" con la wallet en estado **ACTIVA**, pulsar **Ir a pagar** y ver el punto de entrada (**CA-3**).

## 3. Caso de rechazo (30 s)

Registrar otra wallet con el DNI `99999999`: la validación de identidad falla, la wallet queda **RECHAZADA** y el mensaje dice qué hacer.

## 4. Analítica (1 min)

Pestaña **Analítica**:
- "Últimos eventos reales": los eventos del registro que acabamos de hacer (**CA-4**).
- Reporte mensual con 3 meses ficticios: la mediana baja de 5.6 a 2.8 min (**CA-5**); nuevos activos y CAC por mes contra las metas (**CA-6**).
- Embudo y errores frecuentes: el mayor abandono ocurre en la verificación del celular, lo que sugiere la siguiente mejora.

## 5. Pruebas y cierre (1 min)

- Terminal: `python -m pytest -v` → **52 pruebas**, organizadas por criterio.
- `python tools/check_trazabilidad.py` y `python tools/check_contrato.py`: la spec manda, y CI falla si el código se aparta de ella.
- `docs/supuestos-y-decisiones.md`: qué simulamos (OTP, identidad, pagos), las decisiones (por ejemplo, la definición de duración) y lo pendiente (KYC con cumplimiento, límite de intentos, autenticación).
