// ─── TOAST ───────────────────────────────
function mostrarToast(msg, tipo) {
  const c = document.querySelector('.toast-container') || (() => {
    const d = document.createElement('div');
    d.className = 'toast-container';
    document.body.appendChild(d);
    return d;
  })();
  const t = document.createElement('div');
  t.className = `toast align-items-center text-bg-${tipo || 'success'} border-0 show`;
  t.role = 'alert';
  t.innerHTML = `<div class="d-flex"><div class="toast-body small fw-medium">${msg}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  c.appendChild(t);
  const bs = new bootstrap.Toast(t, { delay: 2500 });
  bs.show();
  t.addEventListener('hidden.bs.toast', () => t.remove());
}

// ─── API ─────────────────────────────────
async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body && !(body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    opts.body = body;
  }
  const r = await fetch(url, opts);
  if (r.status === 401) { window.location = '/login'; return; }
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.error || 'Error de red');
  }
  return r.json();
}

// ─── AUTH ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const lf = document.getElementById('loginForm');
  if (lf) lf.addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('errorMsg');
    errEl.classList.add('d-none');
    if (!lf.email.value || !lf.password.value) {
      errEl.textContent = 'Completá todos los campos';
      errEl.classList.remove('d-none');
      return;
    }
    const btn = lf.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Entrando...';
    try {
      await api('POST', '/api/login', { email: lf.email.value, contraseña: lf.password.value });
      window.location = '/dashboard';
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('d-none');
      btn.disabled = false; btn.innerHTML = 'Entrar';
    }
  });

  const rf = document.getElementById('registerForm');
  if (rf) rf.addEventListener('submit', async (e) => {
    e.preventDefault();
    // Client-side validation
    const nombre = rf.nombre.value.trim();
    const email = rf.email.value.trim();
    const pw = rf.password.value;
    const pw2 = rf.password2.value;
    const errEl = document.getElementById('errorMsg');
    errEl.classList.add('d-none');
    // Reset validation
    rf.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    let valid = true;
    if (!nombre) { rf.nombre.classList.add('is-invalid'); valid = false; }
    if (!email || !email.includes('@')) { rf.email.classList.add('is-invalid'); valid = false; }
    if (pw.length < 4) { rf.password.classList.add('is-invalid'); valid = false; }
    if (pw !== pw2) { rf.password2.classList.add('is-invalid'); valid = false; }
    if (!valid) return;
    const btn = rf.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando...';
    try {
      await api('POST', '/api/register', {
        nombre, email, contraseña: pw, sala: rf.sala.value, turno: rf.turno.value
      });
      window.location = '/dashboard';
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('d-none');
      btn.disabled = false; btn.innerHTML = 'Crear cuenta';
    }
  });
});

async function logout() {
  await api('GET', '/api/logout');
  window.location = '/login';
}

// ─── DASHBOARD ───────────────────────────
let actividadesGlobales = [];
let recordingState = { mediaRecorder: null, chunks: [], alumnoId: null, actividadId: null, button: null };
let seleccionMode = false;

async function cargarDashboard() {
  await cargarStats();
  await cargarActividadesSelect();
  await cargarAlumnos();
  cargarObsHoy();
}

async function cargarStats() {
  try {
    const s = await api('GET', '/api/stats');
    const el = id => document.getElementById(id);
    el('statAlumnos').textContent = s.total_alumnos;
    el('statObsHoy').textContent = s.observaciones_hoy;
    el('statTotalObs').textContent = s.total_observaciones;
    el('statInformes').textContent = s.total_informes;
  } catch (e) {}
}

async function cargarAlumnos() {
  const c = document.getElementById('alumnosContainer');
  try {
    const alumnos = await api('GET', '/api/alumnos');
    if (!alumnos.length) {
      c.innerHTML = `<div class="text-center py-5 text-muted">
        <p class="mb-2 fs-4">👩‍🏫</p>
        <p class="small">Todavía no cargaste alumnos.</p>
        <button class="btn btn-sm btn-primary" onclick="mostrarModalAlumno()">Agregar primer alumno</button>
      </div>`;
      return;
    }
    c.innerHTML = alumnos.map(a => `
      <div class="alumno-item" data-id="${a.id_alumno}">
        <div class="alumno-header">
          <a href="/alumno/${a.id_alumno}" class="alumno-nombre text-decoration-none">${a.apellido}, ${a.nombre}</a>
          <div class="d-flex gap-1 flex-shrink-0">
            <button class="btn btn-sm btn-outline-success btn-record" data-alumno="${a.id_alumno}" onclick="toggleRecord(this)" title="Grabar audio">🎤</button>
            <button class="btn btn-sm btn-outline-info" onclick="verObs(${a.id_alumno})" title="Ver observaciones">📄</button>
            <button class="btn btn-sm btn-outline-danger" onclick="eliminarAlumno(${a.id_alumno})" title="Eliminar">✕</button>
          </div>
        </div>
        <div class="alumno-actions">
          <div class="dropdown actividad-dropdown" data-alumno="${a.id_alumno}">
            <button class="btn btn-sm btn-outline-secondary dropdown-toggle text-truncate" type="button" data-bs-toggle="dropdown">
              <span class="actividad-label">Seleccionar actividad</span>
            </button>
            <ul class="dropdown-menu dropdown-menu-actividades" style="max-height:40vh;overflow-y:auto">
              <li><a class="dropdown-item" href="#" data-value="">— Sin actividad —</a></li>
              ${actividadesGlobales.map(act => `<li><a class="dropdown-item actividad-opcion" href="#" data-value="${act.id_actividad}" data-area="${act.area}">${act.nombre}</a></li>`).join('')}
            </ul>
          </div>
          <input type="text" class="form-control form-control-sm obs-texto" placeholder="Observación..." data-alumno="${a.id_alumno}">
          <button class="btn btn-sm btn-primary fw-bold" onclick="guardarObs(${a.id_alumno}, this)" title="Guardar texto">💾</button>
        </div>
      </div>
    `).join('');
    // Attach dropdown item click handlers
    document.querySelectorAll('.actividad-dropdown .dropdown-item').forEach(el => {
      el.addEventListener('click', e => {
        e.preventDefault();
        const dd = el.closest('.actividad-dropdown');
        const btn = dd.querySelector('.dropdown-toggle');
        const label = dd.querySelector('.actividad-label');
        const value = el.dataset.value;
        const text = value ? el.textContent : 'Seleccionar actividad';
        dd.dataset.selected = value;
        label.textContent = text;
        btn.classList.toggle('btn-outline-primary', !!value);
        btn.classList.toggle('btn-outline-secondary', !value);
      });
    });
  } catch (e) {
    c.innerHTML = `<div class="alert alert-danger py-2 small">Error: ${e.message}</div>`;
  }
}

async function cargarActividadesSelect() {
  try {
    actividadesGlobales = await api('GET', '/api/actividades') || [];
  } catch (e) { actividadesGlobales = []; }
}

async function guardarObs(idAlumno, btn) {
  const dd = document.querySelector(`.actividad-dropdown[data-alumno="${idAlumno}"]`);
  const value = dd ? dd.dataset.selected : '';
  const input = document.querySelector(`.obs-texto[data-alumno="${idAlumno}"]`);
  const texto = input ? input.value.trim() : '';
  if (!texto && !value) {
    mostrarToast('Escribí una observación o seleccioná una actividad', 'warning');
    return;
  }
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
  try {
    await api('POST', '/api/observaciones', {
      id_alumno: idAlumno,
      id_actividad: value ? parseInt(value) : null,
      nota_cruda: texto || '(sin texto)',
      tipo: 'texto'
    });
    if (input) input.value = '';
    mostrarToast('Observación guardada');
    cargarObsHoy();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '💾';
  }
}

// ─── GRABACIÓN DE AUDIO ─────────────────
async function toggleRecord(btn) {
  // Si ya está grabando para este botón, detener
  if (recordingState.mediaRecorder && recordingState.mediaRecorder.state === 'recording') {
    detenerGrabacion();
    return;
  }
  const idAlumno = parseInt(btn.dataset.alumno);
  const dd = document.querySelector(`.actividad-dropdown[data-alumno="${idAlumno}"]`);
  const idActividad = dd && dd.dataset.selected ? parseInt(dd.dataset.selected) : null;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
    const mr = new MediaRecorder(stream, { mimeType });
    const chunks = [];

    recordingState = { mediaRecorder: mr, chunks, alumnoId: idAlumno, actividadId: idActividad, button: btn };

    mr.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    mr.onstop = async () => {
      btn.classList.remove('recording');
      btn.innerHTML = '🎤';
      const blob = new Blob(chunks, { type: mr.mimeType });
      stream.getTracks().forEach(t => t.stop());
      if (blob.size > 0) {
        await subirAudio(blob, idAlumno, idActividad);
      }
    };

    mr.start();
    btn.classList.add('recording');
    btn.innerHTML = '⏹';
    mostrarToast('Grabando... tocá de nuevo para detener', 'info');
  } catch (e) {
    mostrarToast('Error al acceder al micrófono: ' + e.message, 'danger');
  }
}

function detenerGrabacion() {
  if (recordingState.mediaRecorder && recordingState.mediaRecorder.state === 'recording') {
    recordingState.mediaRecorder.stop();
  }
}

async function subirAudio(blob, idAlumno, idActividad) {
  const fd = new FormData();
  fd.append('audio', blob, `grabacion_${Date.now()}.webm`);
  fd.append('id_alumno', idAlumno);
  if (idActividad) fd.append('id_actividad', idActividad);
  try {
    const r = await api('POST', '/api/audio/subir', fd);
    if (r.texto && r.texto.startsWith('[Error:')) {
      mostrarToast('⚠️ ' + r.texto.replace(/^\[Error:\s*/, '').replace(/\]$/, ''), 'danger');
    } else {
      mostrarToast('Audio transcrito: ' + (r.texto || '').substring(0, 80));
    }
    cargarObsHoy();
  } catch (e) {
    mostrarToast('Error al procesar audio: ' + e.message, 'danger');
  }
}

function verObs(id) {
  window.location = `/alumno/${id}`;
}

async function eliminarObs(idObs, btn) {
  if (!confirm('¿Eliminar esta observación?')) return;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:0.7rem;height:0.7rem"></span>';
  try {
    await api('DELETE', `/api/observaciones/${idObs}`);
    const item = btn.closest('.obs-item');
    if (item) item.remove();
    mostrarToast('Observación eliminada');
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
    btn.disabled = false;
    btn.innerHTML = '✕';
  }
}

function toggleSeleccionObs() {
  seleccionMode = !seleccionMode;
  const btn = document.getElementById('btnSelectMode');
  const btnEliminar = document.getElementById('btnEliminarSel');
  const btnTodo = document.getElementById('btnEliminarTodo');
  if (seleccionMode) {
    btn.textContent = 'Cancelar';
    btn.className = 'btn btn-sm btn-secondary fw-bold';
    btnEliminar.classList.remove('d-none');
    btnTodo.classList.remove('d-none');
    mostrarCheckboxes();
  } else {
    btn.textContent = 'Eliminar';
    btn.className = 'btn btn-sm btn-outline-danger';
    btnEliminar.classList.add('d-none');
    btnTodo.classList.add('d-none');
    ocultarCheckboxes();
  }
}

function mostrarCheckboxes() {
  document.querySelectorAll('.obs-checkbox').forEach(cb => cb.style.display = '');
  actualizarContadorSel();
}

function ocultarCheckboxes() {
  document.querySelectorAll('.obs-checkbox').forEach(cb => { cb.style.display = 'none'; cb.checked = false; });
}

function actualizarContadorSel() {
  const checked = document.querySelectorAll('.obs-checkbox:checked').length;
  const btn = document.getElementById('btnEliminarSel');
  if (btn) btn.textContent = `Eliminar seleccionadas (${checked})`;
}

async function eliminarSeleccionadas() {
  const checked = document.querySelectorAll('.obs-checkbox:checked');
  const ids = Array.from(checked).map(cb => parseInt(cb.dataset.obsId));
  if (!ids.length) { mostrarToast('Seleccioná al menos una observación', 'warning'); return; }
  if (!confirm(`¿Eliminar ${ids.length} observaciones?`)) return;
  try {
    await api('POST', '/api/observaciones/batch-delete', { ids });
    ids.forEach(id => {
      const item = document.querySelector(`.obs-item[data-obs-id="${id}"]`);
      if (item) item.remove();
    });
    mostrarToast(`${ids.length} observaciones eliminadas`);
    toggleSeleccionObs();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

async function eliminarTodas() {
  const items = document.querySelectorAll('.obs-item');
  const ids = Array.from(items).map(el => parseInt(el.dataset.obsId));
  if (!ids.length) return;
  if (!confirm(`¿Eliminar TODAS las ${ids.length} observaciones?`)) return;
  try {
    await api('POST', '/api/observaciones/batch-delete', { ids });
    items.forEach(el => el.remove());
    mostrarToast(`${ids.length} observaciones eliminadas`);
    toggleSeleccionObs();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

// ─── PÁGINA DEL ALUMNO ──────────────────
async function cargarObsAlumno(idAlumno) {
  const c = document.getElementById('obsContainer');
  const ic = document.getElementById('informeContainer');
  try {
    const data = await api('GET', `/api/alumno/${idAlumno}/detalle`);
    const obs = data.observaciones || [];

    // Mostrar informe si existe
    if (data.informe && data.informe.contenido_informe) {
      mostrarInforme(ic, data.informe.contenido_informe, idAlumno);
    } else {
      const btnPDF = document.getElementById('btnPDF');
      if (btnPDF) btnPDF.style.display = 'none';
      if (obs.length > 0) {
        ic.innerHTML = `<div class="text-center py-4">
          <p class="mb-2 fs-4">📄</p>
          <p class="small text-muted">Hay ${obs.length} observaciones. Presioná "Generar" para crear el informe.</p>
        </div>`;
      } else {
        ic.innerHTML = `<div class="text-center py-4 text-muted">
          <p class="mb-1 fs-4">📄</p>
          <p class="small">No hay actividades registradas para generar informe.</p>
        </div>`;
      }
    }

    // Mostrar observaciones
    if (!obs.length) {
      c.innerHTML = '<div class="text-center py-5 text-muted"><p class="mb-2 fs-4">📋</p><p class="small">Este alumno no tiene actividades registradas aún.</p></div>';
      return;
    }
    const grupos = {};
    obs.forEach(o => {
      const fecha = o.fecha?.split(' ')[0] || 'Sin fecha';
      if (!grupos[fecha]) grupos[fecha] = [];
      grupos[fecha].push(o);
    });
    c.innerHTML = Object.entries(grupos).map(([fecha, lista]) => `
      <h6 class="text-muted fw-bold mt-3 mb-2 small text-uppercase">${fecha}</h6>
      ${lista.map(o => `
        <div class="obs-item ${o.tipo}" data-obs-id="${o.id_observacion}">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div class="flex-grow-1">
              ${o.act_nombre ? `<small class="fw-medium text-primary">${o.act_nombre}</small>` : ''}
              <p class="mb-1 mt-1">${o.nota_cruda}</p>
            </div>
            <input type="checkbox" class="obs-checkbox mt-1 flex-shrink-0" data-obs-id="${o.id_observacion}" style="display:none">
          </div>
          ${o.ruta_audio ? `
            <div class="mt-2">
              <audio controls preload="none" class="w-100" style="max-width:300px;height:36px">
                <source src="${o.ruta_audio}" type="audio/webm">
              </audio>
            </div>
          ` : ''}
        </div>
      `).join('')}
    `).join('');
    // Restore selection mode if active
    if (seleccionMode) mostrarCheckboxes();
    // Listen for checkbox changes to update counter
    c.addEventListener('change', e => {
      if (e.target.classList.contains('obs-checkbox')) actualizarContadorSel();
    });
  } catch (e) {
    c.innerHTML = `<div class="alert alert-danger py-2 small">${e.message}</div>`;
  }
}

// ─── INFORME (view / edit) ──────────────
function mostrarInforme(container, contenido, idAlumno) {
  if (!contenido) {
    container.innerHTML = `<div class="text-center py-4 text-muted">
      <p class="small">No hay informe generado aún.</p>
    </div>`;
    return;
  }

  const html = contenido
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/INFORMES EVALUATIVOS/g, '<div class="titulo">INFORMES EVALUATIVOS</div>')
    .replace(/INFORME 2025 - PRIMERA ETAPA/g, '<div class="subtitulo">INFORME 2025 - PRIMERA ETAPA</div>')
    .replace(/(IDENTIDAD Y CONVIVENCIA|LENGUAJE Y LITERATURA|MATEMÁTICAS|CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA):?/g, '<div class="area">$1</div>')
    .replace(/FALTAS:.*/g, m => `<div class="faltas">${m}</div>`);

  const btnPDF = document.getElementById('btnPDF');
  if (btnPDF) btnPDF.style.display = '';

  container.innerHTML = `
    <div class="informe-card" id="informeView">${html}</div>
    <div class="d-flex gap-2 mt-2 justify-content-end">
      <button class="btn btn-sm btn-outline-secondary" onclick="editarInforme(${idAlumno})" id="btnEditarInforme">✏️ Editar</button>
    </div>
  `;
}

async function editarInforme(idAlumno) {
  // Obtener el contenido actual desde el servidor para tener el texto limpio
  try {
    const data = await api('GET', `/api/alumno/${idAlumno}/detalle`);
    let contenido = (data.informe && data.informe.contenido_informe) || '';

    const container = document.getElementById('informeContainer');
    container.innerHTML = `
      <textarea class="informe-edit" id="informeTextarea">${contenido.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</textarea>
      <div class="d-flex gap-2 mt-2 justify-content-end">
        <button class="btn btn-sm btn-success fw-bold" onclick="guardarInformeEdit(${idAlumno})">💾 Guardar</button>
        <button class="btn btn-sm btn-outline-secondary" onclick="recargarInforme(${idAlumno})">Cancelar</button>
      </div>
    `;
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

async function guardarInformeEdit(idAlumno) {
  const textarea = document.getElementById('informeTextarea');
  const contenido = textarea.value.trim();
  if (!contenido) {
    mostrarToast('El informe no puede estar vacío', 'warning');
    return;
  }
  try {
    await api('PUT', `/api/informe/${idAlumno}`, { contenido });
    mostrarToast('Informe actualizado');
    recargarInforme(idAlumno);
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

async function recargarInforme(idAlumno) {
  const ic = document.getElementById('informeContainer');
  ic.innerHTML = '<div class="text-center py-4"><span class="spinner-border spinner-border-sm"></span></div>';
  try {
    const data = await api('GET', `/api/alumno/${idAlumno}/detalle`);
    if (data.informe && data.informe.contenido_informe) {
      mostrarInforme(ic, data.informe.contenido_informe, idAlumno);
    } else {
      ic.innerHTML = `<div class="text-center py-4 text-muted">
        <p class="small">No hay informe generado aún.</p>
      </div>`;
    }
  } catch (e) {
    ic.innerHTML = `<div class="alert alert-danger py-2 small">${e.message}</div>`;
  }
}

async function generarInforme(idAlumno, auto = false) {
  const btn = document.getElementById('btnGenerar');
  const ic = document.getElementById('informeContainer');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generando...'; }
  if (!auto) {
    ic.innerHTML = '<div class="text-center py-4"><span class="spinner-border spinner-border-sm"></span> <span class="small text-muted">Generando informe con IA...</span></div>';
  }
  try {
    const r = await api('POST', `/api/informe/${idAlumno}`, {});
    mostrarInforme(ic, r.contenido, idAlumno);
    if (!auto) mostrarToast('Informe generado');
  } catch (e) {
    ic.innerHTML = `<div class="alert alert-danger py-2 small">Error: ${e.message}</div>`;
    if (!auto) mostrarToast('Error al generar informe: ' + e.message, 'danger');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = 'Generar / Regenerar'; }
  }
}

// ─── OBSERVACIONES DE HOY ───────────────
async function cargarObsHoy() {
  const c = document.getElementById('obsHoyContainer');
  if (!c) return;
  try {
    const obs = await api('GET', '/api/observaciones/hoy');
    if (!obs.length) {
      c.innerHTML = '<p class="text-muted small">No hay observaciones registradas hoy.</p>';
      return;
    }
    c.innerHTML = obs.map(o => `
      <div class="obs-item ${o.tipo}">
        <div class="d-flex justify-content-between">
          <strong class="small">${o.al_apellido}, ${o.al_nombre}</strong>
          <span class="badge ${o.tipo === 'audio' ? 'bg-success' : 'bg-primary'}">${o.tipo === 'audio' ? '🎤' : '📝'}</span>
        </div>
        ${o.act_nombre ? `<small class="text-primary">${o.act_nombre}</small>` : ''}
        ${o.tipo === 'audio' && o.ruta_audio ? `
          <div class="mt-1">
            <audio controls preload="none" class="w-100" style="max-width:300px;height:32px">
              <source src="${o.ruta_audio}" type="audio/webm">
            </audio>
          </div>
        ` : ''}
        <p class="mb-0 mt-1 small ${o.tipo === 'audio' ? 'fst-italic text-muted' : ''}">${o.nota_cruda}</p>
      </div>
    `).join('');
  } catch (e) {
    c.innerHTML = `<div class="alert alert-danger py-2 small">${e.message}</div>`;
  }
}

// ─── CRUD ALUMNOS ───────────────────────
let modalAlumno, modalVarios;

document.addEventListener('DOMContentLoaded', () => {
  modalAlumno = document.getElementById('modalAlumno') ? new bootstrap.Modal('#modalAlumno') : null;
  modalVarios = document.getElementById('modalVarios') ? new bootstrap.Modal('#modalVarios') : null;
});

function mostrarModalAlumno() {
  document.getElementById('formAlumno').reset();
  modalAlumno.show();
}

async function guardarAlumno() {
  const nombre = document.getElementById('alNombre').value.trim();
  const apellido = document.getElementById('alApellido').value.trim();
  if (!nombre || !apellido) return mostrarToast('Completá nombre y apellido', 'warning');
  try {
    await api('POST', '/api/alumnos', { nombre, apellido });
    modalAlumno.hide();
    mostrarToast('Alumno agregado');
    cargarAlumnos();
  } catch (e) { mostrarToast(e.message, 'danger'); }
}

function cargarVarios() {
  document.getElementById('listaAlumnos').value = '';
  modalVarios.show();
}

async function guardarVarios() {
  const lines = document.getElementById('listaAlumnos').value.trim().split('\n').filter(Boolean);
  if (!lines.length) return mostrarToast('Pegá al menos un alumno', 'warning');
  let ok = 0;
  for (const l of lines) {
    const partes = l.trim().split(/\s+/);
    if (partes.length < 2) continue;
    const apellido = partes.pop();
    const nombre = partes.join(' ');
    try {
      await api('POST', '/api/alumnos', { nombre, apellido });
      ok++;
    } catch (e) {}
  }
  modalVarios.hide();
  mostrarToast(`${ok} alumnos cargados`);
  cargarAlumnos();
}

async function eliminarAlumno(id) {
  if (!confirm('¿Eliminar este alumno y sus observaciones?')) return;
  try {
    await api('DELETE', `/api/alumnos/${id}`);
    mostrarToast('Alumno eliminado');
    cargarAlumnos();
    cargarObsHoy();
  } catch (e) { mostrarToast(e.message, 'danger'); }
}

// ─── ACTIVIDADES ────────────────────────
async function cargarActividades() {
  const c = document.getElementById('actividadesContainer');
  try {
    let acts = await api('GET', '/api/actividades');
    const filtro = document.getElementById('filtroArea')?.value;
    if (filtro) acts = acts.filter(a => a.area === filtro);

    if (!acts.length) {
      c.innerHTML = `<div class="text-center py-5 text-muted">
        <p class="mb-2 fs-4">📋</p>
        <p class="small">${filtro ? 'No hay actividades para esta área hoy.' : 'No hay actividades para hoy.'}</p>
        <button class="btn btn-sm btn-primary" onclick="document.getElementById('bulkActividades').focus()">Crear actividades</button>
      </div>`;
      return;
    }
    const areas = {};
    acts.forEach(a => {
      if (!areas[a.area]) areas[a.area] = [];
      areas[a.area].push(a);
    });
    c.innerHTML = Object.entries(areas).map(([area, lista]) => `
      <div class="area-header">
        <h6>${area}</h6>
        <button class="btn btn-sm btn-link text-muted p-0 text-decoration-none" onclick="editarArea('${area.replace(/'/g, "\\'")}')" title="Renombrar área">✏️</button>
      </div>
      ${lista.map(a => `
        <div class="actividad-card" data-id="${a.id_actividad}">
          <div class="flex-grow-1 me-2" style="min-width:0">
            <div class="fw-medium d-flex align-items-center gap-2">
              <span class="act-nombre-texto">${a.nombre}</span>
            </div>
          </div>
          <div class="d-flex gap-1 flex-shrink-0">
            <button class="btn btn-sm btn-outline-secondary" onclick="editarActividad(${a.id_actividad}, this)" title="Editar">✏️</button>
            <button class="btn btn-sm btn-outline-danger" onclick="eliminarActividad(${a.id_actividad})">✕</button>
          </div>
        </div>
      `).join('')}
    `).join('');
  } catch (e) {
    c.innerHTML = `<div class="alert alert-danger py-2 small">${e.message}</div>`;
  }
}

async function guardarActividadesMulti() {
  const textarea = document.getElementById('bulkActividades');
  const areaDefault = document.getElementById('bulkArea').value;
  const lines = textarea.value.trim().split('\n').filter(Boolean);
  if (!lines.length) return mostrarToast('Pegá al menos una actividad', 'warning');

  const actividades = lines.map(line => {
    line = line.trim();
    const pipeIdx = line.lastIndexOf('|');
    if (pipeIdx > 0) {
      const nombre = line.substring(0, pipeIdx).trim();
      const area = line.substring(pipeIdx + 1).trim();
      if (nombre && area) return { nombre, area };
    }
    return { nombre: line, area: areaDefault };
  });

  try {
    const r = await api('POST', '/api/actividades/multi', { actividades });
    textarea.value = '';
    mostrarToast(`${r.count} actividades cargadas`);
    cargarActividades();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

function editarActividad(id, btn) {
  const card = btn.closest('.actividad-card');
  const textoEl = card.querySelector('.act-nombre-texto');
  const nombreActual = textoEl.textContent;

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'form-control form-control-sm';
  input.value = nombreActual;
  textoEl.replaceWith(input);
  input.focus();
  input.select();

  btn.textContent = '💾';
  btn.className = 'btn btn-sm btn-outline-success';
  btn.onclick = null;

  const guardarEdit = async () => {
    const nuevoNombre = input.value.trim();
    if (!nuevoNombre) return mostrarToast('El nombre no puede estar vacío', 'warning');
    try {
      await api('PUT', `/api/actividades/${id}`, { nombre: nuevoNombre });
      mostrarToast('Actividad actualizada');
      cargarActividades();
    } catch (e) {
      mostrarToast('Error: ' + e.message, 'danger');
    }
  };

  btn.addEventListener('click', guardarEdit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') guardarEdit();
    if (e.key === 'Escape') cargarActividades();
  });
}

async function editarArea(areaVieja) {
  const areaNueva = prompt('Nuevo nombre para el área "' + areaVieja + '":', areaVieja);
  if (!areaNueva || areaNueva.trim() === areaVieja) return;
  try {
    await api('POST', '/api/areas/rename', { area_vieja: areaVieja, area_nueva: areaNueva.trim() });
    mostrarToast('Área renombrada');
    await cargarAreas();
    cargarActividades();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  }
}

async function cargarAreas() {
  try {
    const areas = await api('GET', '/api/areas');
    const filtro = document.getElementById('filtroArea');
    if (filtro) {
      const actual = filtro.value;
      filtro.innerHTML = '<option value="">Todas las áreas</option>' +
        areas.map(a => `<option ${a === actual ? 'selected' : ''}>${a}</option>`).join('');
    }
    const bulk = document.getElementById('bulkArea');
    if (bulk) {
      const actual = bulk.value;
      bulk.innerHTML = areas.map(a => `<option ${a === actual ? 'selected' : ''}>${a}</option>`).join('');
    }
  } catch (e) {}
}

async function eliminarActividad(id) {
  if (!confirm('¿Eliminar esta actividad?')) return;
  try {
    await api('DELETE', `/api/actividades/${id}`);
    mostrarToast('Actividad eliminada');
    cargarActividades();
  } catch (e) { mostrarToast(e.message, 'danger'); }
}

// ─── SERVICE WORKER & INSTALL (PWA) ──────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

let installPrompt = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  installPrompt = e;
  const banner = document.getElementById('installBanner');
  if (banner) banner.classList.add('show');
});

document.addEventListener('click', e => {
  const target = e.target.closest('#btnInstalar');
  if (!target || !installPrompt) return;
  installPrompt.prompt();
  installPrompt.userChoice.then(() => {
    installPrompt = null;
    document.getElementById('installBanner')?.classList.remove('show');
  });
});

window.addEventListener('appinstalled', () => {
  installPrompt = null;
  document.getElementById('installBanner')?.classList.remove('show');
});
