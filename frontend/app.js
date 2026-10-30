"use strict";

// ── Utilidades ──────────────────────────────────────────────────────────────
const $app = document.getElementById("app");
const CLAVE_LOCAL = "wallet-onboarding-id";

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const local = {
  get() { try { return localStorage.getItem(CLAVE_LOCAL); } catch { return null; } },
  set(v) { try { localStorage.setItem(CLAVE_LOCAL, v); } catch { /* sin almacenamiento */ } },
  del() { try { localStorage.removeItem(CLAVE_LOCAL); } catch { /* sin almacenamiento */ } },
};

class ErrorApi extends Error {
  constructor(status, cuerpo) {
    super(cuerpo?.mensaje || `Error ${status}`);
    this.status = status;
    this.cuerpo = cuerpo || {};
  }
}

async function api(metodo, ruta, cuerpo) {
  const r = await fetch(ruta, {
    method: metodo,
    headers: cuerpo ? { "Content-Type": "application/json" } : {},
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErrorApi(r.status, datos);
  return datos;
}

let toastTimer;
function toast(texto) {
  const t = document.getElementById("toast");
  t.textContent = texto;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}

const fmt = {
  num: (n) => (n == null ? "—" : Number(n).toLocaleString("es-PE")),
  pen: (n) => (n == null ? "—" : `S/ ${Number(n).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`),
  min: (n) => (n == null ? "—" : `${Number(n).toLocaleString("es-PE", { maximumFractionDigits: 1 })} min`),
  pct: (n) => (n == null ? "—" : `${(n * 100).toLocaleString("es-PE", { maximumFractionDigits: 1 })} %`),
  hora: (iso) => new Date(iso).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "medium" }),
};

// ── Registro (onboarding) ──────────────────────────────────────────────────
let estado = null;   // última respuesta del backend
let cronometro;      // intervalo del tiempo transcurrido

const FORMULARIOS = {
  datos_personales: () => `
    ${campo("dni", "DNI", `<input type="text" id="dni" name="dni" inputmode="numeric" maxlength="8" autocomplete="off" placeholder="8 dígitos">`)}
    ${campo("nombres", "Nombres", `<input type="text" id="nombres" name="nombres" autocomplete="given-name">`)}
    ${campo("apellidos", "Apellidos", `<input type="text" id="apellidos" name="apellidos" autocomplete="family-name">`)}
    ${campo("fecha_nacimiento", "Fecha de nacimiento", `<input type="date" id="fecha_nacimiento" name="fecha_nacimiento">`, "Debes ser mayor de 18 años.")}`,
  celular: () => `
    ${campo("celular", "Número de celular", `
      <div class="fila">
        <input type="tel" id="celular" name="celular" inputmode="numeric" maxlength="15" placeholder="987654321" autocomplete="tel-national">
        <button type="button" class="btn btn-secundario" id="btn-otp" style="flex:none">Enviar código</button>
      </div>`)}
    ${campo("codigo_otp", "Código SMS", `<input type="text" id="codigo_otp" name="codigo_otp" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="6 dígitos">`, "Te lo enviamos por SMS. En la demo es 123456.")}`,
  identidad: () => `
    <p class="muted">Validaremos tu DNI con el registro de identidad para proteger tu cuenta.</p>
    ${campo("autoriza_validacion", null, check("autoriza_validacion", "Autorizo la validación de mi identidad con mi número de DNI."))}`,
  terminos: () => `
    ${campo("acepta_terminos", null, check("acepta_terminos", 'Acepto los <a href="#" onclick="return false">términos y condiciones</a> de la wallet.'))}
    ${campo("acepta_tratamiento_datos", null, check("acepta_tratamiento_datos", "Autorizo el tratamiento de mis datos personales según la Ley N.° 29733."))}`,
  clave: () => `
    ${campo("clave", "Clave de 6 dígitos", `<input type="password" id="clave" name="clave" inputmode="numeric" maxlength="6" autocomplete="new-password">`, "No uses números repetidos, seguidos ni tu fecha de nacimiento.")}
    ${campo("confirmacion_clave", "Repite tu clave", `<input type="password" id="confirmacion_clave" name="confirmacion_clave" inputmode="numeric" maxlength="6" autocomplete="new-password">`)}`,
};

function campo(nombre, etiqueta, control, ayuda) {
  return `<div class="campo" data-campo="${nombre}">
    ${etiqueta ? `<label for="${nombre}">${etiqueta}</label>` : ""}
    ${control}
    ${ayuda ? `<div class="ayuda">${ayuda}</div>` : ""}
    <div class="error-campo" id="error-${nombre}" hidden></div>
  </div>`;
}

function check(nombre, texto) {
  return `<label class="check" for="${nombre}"><input type="checkbox" id="${nombre}" name="${nombre}"><span>${texto}</span></label>`;
}

function leerFormulario(form) {
  const datos = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    datos[el.name] = el.type === "checkbox" ? el.checked : el.value;
  }
  return datos;
}

function mostrarErrores(form, errores) {
  form.querySelectorAll(".campo").forEach((c) => c.classList.remove("con-error"));
  form.querySelectorAll(".error-campo").forEach((e) => { e.hidden = true; e.textContent = ""; });
  let primero = null;
  for (const err of errores) {
    const c = form.querySelector(`[data-campo="${err.campo}"]`);
    const box = form.querySelector(`#error-${err.campo}`);
    if (!c || !box) continue;
    c.classList.add("con-error");
    box.hidden = false;
    box.textContent = err.mensaje;
    primero = primero || c.querySelector("input, select");
  }
  primero?.focus();
}

function progreso(ob) {
  const pct = Math.round((ob.pasos_completados / ob.total_pasos) * 100);
  const actual = ob.paso_actual;
  return `<section class="progreso" aria-label="Progreso del registro">
    <div class="progreso-cabecera">
      <strong>${actual ? `Paso ${actual.orden} de ${ob.total_pasos}` : `${ob.pasos_completados} de ${ob.total_pasos} pasos`}</strong>
      <span class="cronometro" id="cronometro"></span>
    </div>
    <div class="barra" role="progressbar" aria-valuemin="0" aria-valuemax="${ob.total_pasos}" aria-valuenow="${ob.pasos_completados}"
      aria-label="${ob.pasos_completados} de ${ob.total_pasos} pasos completados"><span style="width:${pct}%"></span></div>
    <ol class="pasos">
      ${ob.pasos.map((p) => `<li data-orden="${p.orden}" data-estado="${p.estado}" ${p.estado === "ACTUAL" ? 'aria-current="step"' : ""}>
        <span>${esc(p.titulo)}</span></li>`).join("")}
    </ol>
  </section>`;
}

function iniciarCronometro(ob) {
  clearInterval(cronometro);
  const el = document.getElementById("cronometro");
  if (!el) return;
  const inicio = new Date(ob.iniciado_en).getTime();
  const fin = ob.cerrado_en ? new Date(ob.cerrado_en).getTime() : null;
  const pintar = () => {
    const s = Math.max(0, Math.floor(((fin ?? Date.now()) - inicio) / 1000));
    el.textContent = `${fin ? "Tiempo total" : "Llevas"} ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  pintar();
  if (!fin) cronometro = setInterval(pintar, 1000);
}

function vistaBienvenida(error) {
  $app.innerHTML = `
    <div class="card">
      <h1>Abre tu wallet en 3 minutos</h1>
      <p class="muted">Paga con QR y envía dinero a cualquier celular. Solo necesitas tu DNI y tu celular.</p>
      ${error ? `<div class="alerta alerta-error">${esc(error)}</div>` : ""}
      <form id="form-inicio" novalidate>
        <div class="campo">
          <label for="canal">¿Cómo te enteraste de la wallet?</label>
          <select id="canal" name="canal">
            <option value="organico">Lo encontré por mi cuenta</option>
            <option value="redes_sociales">Redes sociales</option>
            <option value="referidos">Me lo recomendó alguien</option>
            <option value="campana_comercios">En una bodega o comercio</option>
          </select>
          <div class="ayuda">Nos ayuda a medir de dónde llegan los nuevos usuarios.</div>
        </div>
        <ol class="muted" style="padding-left:20px;font-size:14px">
          <li>Datos personales</li><li>Verifica tu celular</li><li>Validación de identidad</li>
          <li>Términos y condiciones</li><li>Clave de pagos</li>
        </ol>
        <button class="btn btn-primario" type="submit">Empezar</button>
      </form>
    </div>`;
  document.getElementById("form-inicio").addEventListener("submit", async (e) => {
    e.preventDefault();
    const boton = e.target.querySelector("button");
    boton.disabled = true;
    try {
      const ob = await api("POST", "/api/onboardings", { canal_adquisicion: e.target.canal.value });
      local.set(ob.id);
      pintarRegistro(ob);
    } catch (err) {
      vistaBienvenida(err.message);
    }
  });
}

function pintarRegistro(ob) {
  estado = ob;
  if (ob.estado === "COMPLETADO") return vistaActivada(ob);
  if (ob.estado === "RECHAZADO") return vistaRechazada(ob);
  if (ob.estado === "ABANDONADO") { local.del(); return vistaBienvenida(); }

  const paso = ob.paso_actual;
  $app.innerHTML = `
    ${progreso(ob)}
    <div class="card">
      <h1>${esc(paso.titulo)}</h1>
      <p class="muted">${esc(paso.descripcion)}</p>
      <div class="alerta alerta-error" id="alerta" hidden></div>
      <form id="form-paso" novalidate>
        ${FORMULARIOS[paso.clave]()}
        <div class="acciones">
          <button class="btn btn-primario" type="submit">${paso.orden === ob.total_pasos ? "Activar mi wallet" : "Continuar"}</button>
          <button class="btn btn-ghost" type="button" id="btn-salir">Salir del registro</button>
        </div>
      </form>
    </div>`;
  iniciarCronometro(ob);

  const form = document.getElementById("form-paso");
  form.querySelector("input")?.focus();
  form.addEventListener("submit", (e) => { e.preventDefault(); enviarPaso(form, paso.clave); });
  document.getElementById("btn-salir").addEventListener("click", salir);
  document.getElementById("btn-otp")?.addEventListener("click", () => {
    toast("Te enviamos un código por SMS (simulado). En la demo usa 123456.");
    document.getElementById("codigo_otp").focus();
  });
}

async function enviarPaso(form, clave) {
  const boton = form.querySelector('button[type="submit"]');
  const alerta = document.getElementById("alerta");
  boton.disabled = true;
  alerta.hidden = true;
  try {
    const ob = await api("POST", `/api/onboardings/${estado.id}/pasos/${clave}`, leerFormulario(form));
    pintarRegistro(ob);
  } catch (err) {
    boton.disabled = false;
    if (err.status === 422) {
      mostrarErrores(form, err.cuerpo.errores || []);
      alerta.textContent = err.cuerpo.mensaje;
      alerta.hidden = false;
    } else if (err.status === 409) {
      toast(err.message);
      cargarRegistro();
    } else {
      alerta.textContent = "No pudimos conectar. Revisa tu conexión e inténtalo otra vez.";
      alerta.hidden = false;
    }
  }
}

async function salir() {
  if (!confirm("¿Seguro que quieres salir? Tendrás que empezar de nuevo.")) return;
  try { await api("POST", `/api/onboardings/${estado.id}/abandonar`); } catch { /* ya cerrado */ }
  local.del();
  clearInterval(cronometro);
  vistaBienvenida();
}

function vistaActivada(ob) {
  $app.innerHTML = `
    ${progreso(ob)}
    <div class="card center">
      <div class="icono-grande" aria-hidden="true">✅</div>
      <h1>¡Tu wallet está activa!</h1>
      <p>Hola ${esc(ob.resumen_datos.nombres)}, ya puedes hacer pagos de bajo monto.</p>
      <p><span class="chip chip-ok">Wallet ${esc(ob.wallet.estado)}</span></p>
      <p class="muted" style="font-size:14px">DNI ${esc(ob.resumen_datos.dni)} · Celular ${esc(ob.resumen_datos.celular)}</p>
      <div class="acciones">
        <a class="btn btn-primario" href="#/pagos">Ir a pagar</a>
        <button class="btn btn-ghost" type="button" id="btn-nuevo">Registrar otra wallet (demo)</button>
      </div>
    </div>`;
  iniciarCronometro(ob);
  document.getElementById("btn-nuevo").addEventListener("click", () => { local.del(); vistaBienvenida(); });
}

function vistaRechazada(ob) {
  $app.innerHTML = `
    ${progreso(ob)}
    <div class="card center">
      <div class="icono-grande" aria-hidden="true">🪪</div>
      <h1>No pudimos validar tu identidad</h1>
      <p>${esc(ob.siguiente_accion)}</p>
      <p><span class="chip chip-error">Wallet ${esc(ob.wallet.estado)}</span></p>
      <div class="acciones">
        <button class="btn btn-secundario" type="button" id="btn-nuevo">Empezar de nuevo</button>
      </div>
    </div>`;
  iniciarCronometro(ob);
  document.getElementById("btn-nuevo").addEventListener("click", () => { local.del(); vistaBienvenida(); });
}

async function cargarRegistro() {
  const id = local.get();
  if (!id) return vistaBienvenida();
  try {
    const ob = await api("GET", `/api/onboardings/${id}`);
    if (ob.estado === "EN_CURSO" && ob.pasos_completados > 0) toast("Retomamos tu registro donde lo dejaste.");
    pintarRegistro(ob);
  } catch {
    local.del();
    vistaBienvenida();
  }
}

// ── Pagos (punto de entrada) ───────────────────────────────────────────────
async function vistaPagos() {
  const id = local.get();
  let ob = null;
  try { ob = id ? await api("GET", `/api/onboardings/${id}`) : null; } catch { ob = null; }
  if (!ob) {
    $app.innerHTML = bloqueado("Primero crea tu wallet para empezar a pagar.");
    return;
  }
  try {
    const pagos = await api("GET", `/api/wallets/${ob.wallet.id}/pagos`);
    $app.innerHTML = `
      <div class="card">
        <p><span class="chip chip-ok">Wallet ${esc(pagos.estado_wallet)}</span></p>
        <h1>¿Qué quieres hacer, ${esc(pagos.titular)}?</h1>
        <div class="acciones">
          ${pagos.opciones.map((o) => `<button class="btn btn-secundario" type="button" data-op="${esc(o.clave)}">${esc(o.titulo)}</button>`).join("")}
        </div>
        <p class="muted" style="font-size:13px;margin-top:16px">${esc(pagos.nota)}</p>
      </div>`;
    $app.querySelectorAll("[data-op]").forEach((b) => b.addEventListener("click",
      () => toast("Los pagos de bajo monto son otra historia del MVP (fuera del alcance de esta demo).")));
  } catch (err) {
    $app.innerHTML = bloqueado(err.message);
  }
}

function bloqueado(mensaje) {
  return `<div class="card center">
    <div class="icono-grande" aria-hidden="true">🔒</div>
    <h1>Pagos no disponibles</h1>
    <p>${esc(mensaje)}</p>
    <p><span class="chip chip-warn">Wallet no activa</span></p>
    <a class="btn btn-primario" href="#/registro">Completar mi registro</a>
  </div>`;
}

// ── Analítica (CA-4, CA-5, CA-6) ───────────────────────────────────────────
let incluirDemo = true;

const marca = (ok) => (ok == null ? '<span class="chip chip-neutro">Sin datos</span>'
  : ok ? '<span class="chip chip-ok">Cumple</span>' : '<span class="chip chip-warn">No cumple</span>');

async function vistaAnalitica() {
  $app.innerHTML = `<p class="muted">Cargando analítica…</p>`;
  const q = `incluir_demo=${incluirDemo}`;
  const [res, mensual, eventos] = await Promise.all([
    api("GET", `/api/analitica/onboarding?${q}`),
    api("GET", `/api/analitica/mensual?${q}`),
    api("GET", "/api/analitica/eventos?limite=30"),
  ]);
  const meses = mensual.meses;
  // Las tarjetas muestran el último mes cerrado; el mes en curso está incompleto.
  const mesActual = new Date().toISOString().slice(0, 7);
  const cerrados = meses.filter((m) => m.mes < mesActual);
  const ultimo = cerrados[cerrados.length - 1] || meses[meses.length - 1];
  const maxEmbudo = Math.max(res.iniciados, 1);

  $app.innerHTML = `
    <div class="barra-herramientas">
      <div>
        <h1>Analítica del onboarding</h1>
        <p class="muted" style="margin:0">Duración = de <code>onboarding_iniciado</code> a <code>wallet_activada</code>.</p>
      </div>
      <label><input type="checkbox" id="chk-demo" ${incluirDemo ? "checked" : ""}> Incluir datos ficticios de 3 meses</label>
    </div>

    <div class="kpis">
      <div class="kpi">
        <div class="etiqueta">Mediana de onboarding (total)</div>
        <div class="valor">${fmt.min(res.mediana_minutos)}</div>
        <div class="meta">Meta ≤ ${res.objetivo_minutos} min · base ${res.linea_base_minutos} min ${marca(res.cumple_objetivo_mediana)}</div>
      </div>
      <div class="kpi">
        <div class="etiqueta">Tasa de finalización</div>
        <div class="valor">${fmt.pct(res.tasa_finalizacion)}</div>
        <div class="meta muted">${fmt.num(res.completados)} de ${fmt.num(res.iniciados)} iniciados</div>
      </div>
      <div class="kpi">
        <div class="etiqueta">Nuevos usuarios activos · ${ultimo ? esc(ultimo.mes) : "—"}</div>
        <div class="valor">${fmt.num(ultimo?.nuevos_usuarios_activos)}</div>
        <div class="meta">Meta ${fmt.num(mensual.metas.nuevos_usuarios_activos_mes.min)}–${fmt.num(mensual.metas.nuevos_usuarios_activos_mes.max)} ${ultimo ? marca(ultimo.cumple_rango_mau) : ""}</div>
      </div>
      <div class="kpi">
        <div class="etiqueta">CAC · ${ultimo ? esc(ultimo.mes) : "—"}</div>
        <div class="valor">${fmt.pen(ultimo?.cac_pen)}</div>
        <div class="meta">Meta ≤ ${fmt.pen(mensual.metas.cac_pen.objetivo)} ${ultimo ? marca(ultimo.cumple_cac) : ""}</div>
      </div>
    </div>

    <div class="card">
      <h2>Reporte mensual (CA-6)</h2>
      <div class="tabla-scroll"><table>
        <thead><tr><th>Mes</th><th>Iniciados</th><th>Nuevos activos</th><th>Mediana</th><th>Gasto adquisición</th><th>CAC</th><th>Rango MAU</th><th>CAC ≤ 10</th><th>Mediana ≤ 3</th></tr></thead>
        <tbody>${meses.length ? meses.map((m) => `<tr>
          <td>${esc(m.mes)}</td><td>${fmt.num(m.onboardings_iniciados)}</td><td>${fmt.num(m.nuevos_usuarios_activos)}</td>
          <td>${fmt.min(m.mediana_minutos)}</td><td>${fmt.pen(m.gasto_adquisicion_pen)}</td><td>${fmt.pen(m.cac_pen)}</td>
          <td>${marca(m.cumple_rango_mau)}</td><td>${marca(m.cumple_cac)}</td><td>${marca(m.cumple_mediana)}</td></tr>`).join("")
          : `<tr><td colspan="9" class="muted">Sin datos todavía.</td></tr>`}</tbody>
      </table></div>
    </div>

    <div class="grid-2" style="margin-top:16px">
      <div class="card">
        <h2>Embudo por paso</h2>
        <div class="embudo">
          <div class="embudo-fila"><span>Iniciaron</span><div class="embudo-barra"><span style="width:100%"></span></div><strong>${fmt.num(res.iniciados)}</strong></div>
          ${res.embudo.map((e) => `<div class="embudo-fila"><span>${e.orden}. ${esc(e.paso.replaceAll("_", " "))}</span>
            <div class="embudo-barra"><span style="width:${(e.completaron / maxEmbudo) * 100}%"></span></div><strong>${fmt.num(e.completaron)}</strong></div>`).join("")}
        </div>
        <h2 style="margin-top:20px">Errores más frecuentes</h2>
        <ul class="eventos">${res.errores_frecuentes.map((e) => `<li><code>${esc(e.error)}</code><strong>${fmt.num(e.veces)}</strong></li>`).join("") || '<li class="muted">Sin errores registrados.</li>'}</ul>
      </div>
      <div class="card">
        <h2>Últimos eventos reales (CA-4)</h2>
        <ul class="eventos">${eventos.map((e) => `<li>
          <span><code>${esc(e.tipo)}</code>${e.paso ? ` · ${esc(e.paso)}` : ""}${e.codigo_error ? ` · <span class="chip chip-error">${esc(e.codigo_error)}</span>` : ""}${e.resultado ? ` · ${esc(e.resultado)}` : ""}</span>
          <span class="muted">${fmt.hora(e.ocurrido_en)}</span></li>`).join("") || '<li class="muted">Haz un registro en la pestaña Registro para ver eventos aquí.</li>'}</ul>
      </div>
    </div>`;
  document.getElementById("chk-demo").addEventListener("change", (e) => { incluirDemo = e.target.checked; vistaAnalitica(); });
}

// ── Enrutador ──────────────────────────────────────────────────────────────
const RUTAS = { registro: cargarRegistro, pagos: vistaPagos, analitica: vistaAnalitica };

function enrutar() {
  clearInterval(cronometro);
  const ruta = (location.hash.replace(/^#\//, "") || "registro").split("?")[0];
  const vista = RUTAS[ruta] || cargarRegistro;
  $app.classList.toggle("ancho", ruta === "analitica");
  document.querySelectorAll("[data-ruta]").forEach((a) => {
    if (a.dataset.ruta === ruta) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  Promise.resolve(vista()).catch(() => {
    $app.innerHTML = `<div class="alerta alerta-error">No pudimos cargar esta sección. Revisa que el servidor esté encendido.</div>`;
  });
}

document.getElementById("btn-reiniciar-demo").addEventListener("click", async () => {
  if (!confirm("Esto borra todos los registros de la demo. ¿Continuar?")) return;
  await api("POST", "/api/demo/reiniciar");
  local.del();
  toast("Datos de la demo reiniciados.");
  enrutar();
});

window.addEventListener("hashchange", enrutar);
enrutar();
