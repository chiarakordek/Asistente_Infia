// ─── TOAST ───────────────────────────────
function aplicarTamanoTexto() {
  const tamano = localStorage.getItem('infia-tamano-texto') || 'normal';
  if (tamano === 'grande') {
    document.body.classList.add('texto-grande');
  }
  document.querySelectorAll('[data-texto]').forEach(btn => {
    const activo = btn.dataset.texto === tamano;
    btn.classList.toggle('active', activo);
    btn.setAttribute('aria-pressed', String(activo));
  });
}

function cambiarTamanoTexto(tamano) {
  localStorage.setItem('infia-tamano-texto', tamano);
  document.body.classList.toggle('texto-grande', tamano === 'grande');
  document.querySelectorAll('[data-texto]').forEach(btn => {
    const activo = btn.dataset.texto === tamano;
    btn.classList.toggle('active', activo);
    btn.setAttribute('aria-pressed', String(activo));
  });
  mostrarToast(tamano === 'grande' ? 'Texto grande activado' : 'Texto normal activado');
}

document.addEventListener('DOMContentLoaded', aplicarTamanoTexto);

function mostrarToast(msg, tipo) {
  const c = document.querySelector('.toast-container') || (() => {
    const d = document.createElement('div');
    d.className = 'toast-container';
    document.body.appendChild(d);
    return d;
  })();
  const t = document.createElement('div');
  t.className = `toast align-items-center text-bg-${tipo || 'success'} border-0 show`;
  t.setAttribute('role', 'alert');
  t.setAttribute('aria-live', 'assertive');
  t.role = 'alert';
  t.innerHTML = '<div class="d-flex"><div class="toast-body small fw-medium"></div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
  t.querySelector('.toast-body').textContent = msg;
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
  if (r.status === 402) { window.location = '/suscripcion'; throw new Error('Tu suscripción venció'); }
  if (r.status === 423) { window.location = '/config'; throw new Error('Tu cuenta está suspendida'); }
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
      const formData = { email: lf.email.value, contraseña: lf.password.value };
      const r = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(formData) });
      if (!r.ok) {
        const text = await r.text();
        let msg = text;
        try { const j = JSON.parse(text); msg = j.error || text; } catch(e) {}
        throw new Error(msg);
      }
      const j = await r.json().catch(() => ({}));
      window.location = j.destino || '/dashboard';
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
    const aceptaTerminos = rf.aceptaTerminos;
    const errEl = document.getElementById('errorMsg');
    errEl.classList.add('d-none');
    // Reset validation
    rf.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    let valid = true;
    if (!nombre) { rf.nombre.classList.add('is-invalid'); valid = false; }
    if (!email || !email.includes('@')) { rf.email.classList.add('is-invalid'); valid = false; }
    if (pw.length < 8) { rf.password.classList.add('is-invalid'); valid = false; }
    if (pw !== pw2) { rf.password2.classList.add('is-invalid'); valid = false; }
    if (aceptaTerminos && !aceptaTerminos.checked) { aceptaTerminos.classList.add('is-invalid'); valid = false; }
    const invCodigo = rf.codigo;
    if (invCodigo && !invCodigo.value.trim()) { invCodigo.classList.add('is-invalid'); valid = false; }
    if (!valid) return;
    const btn = rf.querySelector('button[type=submit]');
    btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando...';
    try {
      await api('POST', '/api/register', {
         nombre, email, contraseña: pw, sala: rf.sala.value, turno: rf.turno.value,
         codigo: invCodigo ? invCodigo.value.trim() : '',
         acepta_terminos: aceptaTerminos ? aceptaTerminos.checked : false
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
let alumnoObservacionActiva = null;

async function cargarDashboard() {
  await cargarActividadesSelect();
  await Promise.all([cargarStats(), cargarAlumnos()]);
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
      const count = document.getElementById('studentCount');
      if (count) count.textContent = '0 alumnos';
      c.innerHTML = `<div class="text-center py-5 text-muted">
        <p class="mb-2 fs-4">👩‍🏫</p>
        <p class="small">Todavía no cargaste alumnos. Agregá tu grupo para empezar a registrar observaciones.</p>
        <button class="btn btn-primary btn-sm" type="button" onclick="mostrarModalAlumno()">Agregar primer alumno</button>
      </div>`;
      return;
    }
    c.innerHTML = `
      <div class="bulk-selection-bar d-none" id="bulkBar">
        <label class="bulk-select-all" for="selectAll"><input type="checkbox" id="selectAll" onchange="toggleSelectAll(this)"><span>Seleccionar todos</span></label>
        <span class="bulk-selected-count" id="bulkSelectedCount" aria-live="polite"></span>
        <button class="btn btn-sm btn-danger bulk-delete-btn d-none" id="bulkDeleteButton" onclick="eliminarSeleccionados()">Eliminar seleccionados</button>
      </div>
    ` + alumnos.map(a => `
       <div class="alumno-item" data-id="${a.id_alumno}">
         <div class="alumno-top">
           <input type="checkbox" class="form-check-input alumno-check" data-id="${a.id_alumno}" onchange="actualizarBulkBar()">
           <a href="/alumno/${a.id_alumno}" class="alumno-nombre text-decoration-none"><span class="student-avatar" aria-hidden="true">${(a.nombre || '?').charAt(0)}${(a.apellido || '?').charAt(0)}</span><span class="student-name">${a.apellido}, ${a.nombre}</span><span class="student-open" aria-hidden="true">↗</span></a>
           <button type="button" class="btn btn-sm btn-outline-success student-quick-record" data-alumno="${a.id_alumno}" aria-label="Grabar observación de ${a.apellido}, ${a.nombre}" aria-pressed="false" title="Grabar observación por voz" onclick="toggleRecord(this)">🎤</button>
           <button type="button" class="btn btn-sm btn-outline-primary student-add-observation" onclick="abrirModalObservacion(${a.id_alumno})"><span aria-hidden="true">＋</span> Registrar observación</button>
           <span class="recording-status student-recording-status" aria-live="polite"></span>
         </div>
      </div>
    `).join('');
    if (typeof filtrarAlumnos === 'function') filtrarAlumnos();
  } catch (e) {
    c.innerHTML = `<div class="alert alert-danger py-2 small">Error: ${e.message}</div>`;
  }
}

async function cargarActividadesSelect() {
  try {
    actividadesGlobales = await api('GET', '/api/actividades') || [];
  } catch (e) { actividadesGlobales = []; }
}

function abrirModalObservacion(idAlumno) {
  const item = document.querySelector(`.alumno-item[data-id="${idAlumno}"]`);
  if (!item) return;
  alumnoObservacionActiva = idAlumno;
  document.getElementById('observacionAlumnoNombre').textContent = item.querySelector('.student-name')?.textContent.trim() || 'Alumno';
  document.getElementById('btnGrabarObservacion').dataset.alumno = idAlumno;
  const select = document.getElementById('observacionIndicador');
  select.replaceChildren(new Option('Sin indicador (opcional)', ''), ...actividadesGlobales.map(act => new Option(act.nombre, act.id_actividad)));
  document.getElementById('observacionTexto').value = '';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('modalObservacion')).show();
}

async function guardarObs(idAlumno, btn) {
  const input = document.getElementById('observacionTexto');
  const select = document.getElementById('observacionIndicador');
  const value = select ? select.value : '';
  const nota = input ? input.value.trim() : '';
  if (!nota) {
      mostrarToast('Escribí primero qué observaste', 'warning');
      if (input) input.focus();
    return;
  }
  btn.disabled = true;
  btn.setAttribute('aria-busy', 'true');
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Guardando…';
  try {
    await api('POST', '/api/observaciones', {
      id_alumno: idAlumno, id_actividad: value ? parseInt(value) : null,
      nota_cruda: nota,
      tipo: 'texto'
    });
    mostrarToast('Observación guardada en la ficha del alumno.');
    if (input) input.value = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalObservacion')).hide();
    await cargarStats();
    cargarObsHoy();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'danger');
  } finally {
    btn.disabled = false;
    btn.removeAttribute('aria-busy');
    btn.innerHTML = 'Guardar observación';
  }
}

// ─── GRABACIÓN DE AUDIO ─────────────────
function mejorMimeType() {
  const tipos = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4;codecs=mp4a.40.2',
    'audio/mp4',
    'audio/aac',
    'audio/ogg;codecs=opus',
  ];
  for (const t of tipos) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return '';
}

function extDesdeMime(mime) {
  if (mime.includes('mp4') || mime.includes('aac')) return 'mp4';
  if (mime.includes('ogg')) return 'ogg';
  return 'webm';
}

async function toggleRecord(btn) {
  if (recordingState.mediaRecorder && recordingState.mediaRecorder.state === 'recording') {
    detenerGrabacion();
    return;
  }
  const idAlumno = parseInt(btn.dataset.alumno);
  const modalEl = document.getElementById('modalObservacion');
  const select = modalEl?.classList.contains('show') ? document.getElementById('observacionIndicador') : null;
  const idActividad = select && select.value ? parseInt(select.value) : null;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 }
    });
    const mimeType = mejorMimeType();
    const mr = new MediaRecorder(stream, mimeType ? { mimeType } : {});
    const chunks = [];
    const startTime = Date.now();

    recordingState = { mediaRecorder: mr, chunks, alumnoId: idAlumno, actividadId: idActividad, button: btn, startTime };

    mr.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
    mr.onstop = async () => {
      if (recordingState.timer) clearInterval(recordingState.timer);
      btn.classList.remove('recording');
      btn.setAttribute('aria-pressed', 'false');
      btn.removeAttribute('aria-label');
      const status = btn.closest('.observation-actions')?.querySelector('.recording-status') || btn.closest('.alumno-top')?.querySelector('.recording-status');
      if (status) status.textContent = '';
      btn.innerHTML = btn.classList.contains('student-quick-record') ? '🎤' : '🎤 Grabar audio';
      if (btn.classList.contains('student-quick-record')) btn.setAttribute('aria-label', `Grabar observación por voz de ${btn.closest('.alumno-item')?.querySelector('.student-name')?.textContent.trim() || 'este alumno'}`);
      stream.getTracks().forEach(t => t.stop());
      const duracion = (Date.now() - startTime) / 1000;
      if (duracion < 1) {
        mostrarToast('Grabación muy corta. Mantené presionado al menos 1 segundo.', 'warning');
        return;
      }
      const blob = new Blob(chunks, { type: mr.mimeType });
      if (blob.size < 500) {
        mostrarToast('Audio muy pequeño. Probá de nuevo hablando más cerca del micrófono.', 'warning');
        return;
      }
      if (blob.size > 0) {
        await subirAudio(blob, idAlumno, idActividad);
      }
    };

    mr.start();
    btn.classList.add('recording');
    btn.setAttribute('aria-pressed', 'true');
    const status = btn.closest('.observation-actions')?.querySelector('.recording-status') || btn.closest('.alumno-top')?.querySelector('.recording-status');
    const updateRecordingStatus = () => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const clock = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
      if (status) status.textContent = `Grabando ${clock} · tocá para detener`;
      btn.setAttribute('aria-label', `Detener grabación, ${clock}`);
    };
    updateRecordingStatus();
    recordingState.timer = setInterval(updateRecordingStatus, 1000);
    btn.innerHTML = '⏹';
    mostrarToast('Grabando... toca el botón rojo para detener', 'info');
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
  const ext = extDesdeMime(blob.type);
  const fd = new FormData();
  fd.append('audio', blob, `grabacion_${Date.now()}.${ext}`);
  fd.append('id_alumno', idAlumno);
  if (idActividad) fd.append('id_actividad', idActividad);
  try {
    const r = await api('POST', '/api/audio/subir', fd);
    if (r.texto && r.texto.startsWith('[Error:')) {
      mostrarToast('⚠️ ' + r.texto.replace(/^\[Error:\s*/, '').replace(/\]$/, ''), 'danger');
    } else {
      mostrarToast('Voz transcripta y guardada.');
      const modalEl = document.getElementById('modalObservacion');
      if (modalEl?.classList.contains('show')) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
      await cargarStats();
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
    btn.className = 'btn btn-sm btn-secondary';
    btnEliminar.classList.remove('d-none');
    btnTodo.classList.remove('d-none');
    mostrarCheckboxes();
  } else {
     btn.textContent = 'Gestionar eliminaciones';
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

function actualizarRecorridoAlumno(tieneObservaciones, tieneInforme) {
  const pasos = document.querySelectorAll('.student-journey .journey-step');
  if (pasos.length !== 3) return;
  pasos[0].classList.toggle('journey-step-done', tieneObservaciones);
  pasos[0].classList.toggle('journey-step-current', !tieneObservaciones);
  pasos[1].classList.toggle('journey-step-done', tieneInforme);
  pasos[1].classList.toggle('journey-step-current', tieneObservaciones && !tieneInforme);
  pasos[2].classList.toggle('journey-step-current', tieneInforme);
  pasos.forEach(paso => {
    if (paso.classList.contains('journey-step-current')) paso.setAttribute('aria-current', 'step');
    else paso.removeAttribute('aria-current');
  });
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
    const tieneInforme = Boolean(data.informe && data.informe.contenido_informe);
    const generateBtn = document.getElementById('btnGenerar');
    const reportHint = document.getElementById('reportHint');
    if (generateBtn) generateBtn.disabled = obs.length === 0;
    if (reportHint) reportHint.textContent = obs.length
      ? `Este borrador tomará ${obs.length} ${obs.length === 1 ? 'observación' : 'observaciones'} como punto de partida. Después podés editarlo.`
      : 'Primero registrá una observación por voz o texto; luego vas a poder crear el informe.';
    actualizarRecorridoAlumno(obs.length > 0, tieneInforme);

    // Mostrar informe si existe
    if (tieneInforme) {
      mostrarInforme(ic, data.informe.contenido_informe, idAlumno, data.nombre, data.apellido);
    } else {
      if (obs.length > 0) {
        ic.innerHTML = `<div class="report-empty">
          <span class="report-empty-icon" aria-hidden="true">✦</span>
          <strong>Ya tenés material para armar el informe</strong>
          <span>${obs.length} ${obs.length === 1 ? 'observación lista' : 'observaciones listas'}. Generá un borrador para revisarlo y editarlo.</span>
        </div>`;
      } else {
        ic.innerHTML = `<div class="report-empty">
          <span class="report-empty-icon" aria-hidden="true">✦</span>
          <strong>El informe empieza con una observación</strong>
          <span>Dictá una nota con el micrófono o escribila. Infia la guarda en esta ficha.</span>
          <a href="/dashboard?registrar=${idAlumno}" class="btn btn-outline-primary mt-2">Registrar primera observación</a>
        </div>`;
      }
    }

    // Mostrar observaciones
    if (!obs.length) {
      c.innerHTML = '<div class="text-center py-5 text-muted"><p class="mb-2 fs-4">📋</p><p class="small">Todavía no hay observaciones. Las notas de voz o escritas aparecerán acá.</p></div>';
      return;
    }
    const grupos = {};
    obs.forEach(o => {
      const fecha = o.fecha || 'Sin fecha';
      if (!grupos[fecha]) grupos[fecha] = [];
      grupos[fecha].push(o);
    });
    c.innerHTML = Object.entries(grupos).map(([fecha, lista]) => `
      <h6 class="text-muted mt-3 mb-2 small text-uppercase">${fecha}</h6>
      ${lista.map(o => `
        <div class="obs-item ${o.tipo}" data-obs-id="${o.id_observacion}">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div class="flex-grow-1">
              ${o.act_nombre ? `<small class="text-primary">${o.act_nombre}</small>` : ''}
              <p class="mb-1 mt-1">${o.nota_cruda}</p>
            </div>
            <input type="checkbox" class="obs-checkbox mt-1 flex-shrink-0" data-obs-id="${o.id_observacion}" style="display:none">
          </div>
          ${o.ruta_audio ? `
            <div class="mt-2">
              <audio controls preload="none" class="w-100" style="max-width:300px;height:36px">
                <source src="${o.ruta_audio}">
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
function mostrarInforme(container, contenido, idAlumno, nombre, apellido) {
  if (!contenido) {
    container.innerHTML = `<div class="text-center py-4 text-muted">
      <p class="small">No hay informe generado aún.</p>
    </div>`;
    return;
  }

  contenido = completarNombreInforme(limpiarFaltasInforme(contenido), nombre, apellido);
  const html = contenido
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/INFORMES EVALUATIVOS/g, '<div class="titulo">INFORMES EVALUATIVOS</div>')
    .replace(/INFORME 2025 - PRIMERA ETAPA/g, '<div class="subtitulo">INFORME 2025 - PRIMERA ETAPA</div>')
    .replace(/(IDENTIDAD Y CONVIVENCIA|LENGUAJE Y LITERATURA|MATEMÁTICAS|CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA):?/g, '<div class="area">$1</div>')
    .replace(/\n{3,}/g, '\n\n');

  container.innerHTML = `
    <div class="informe-card velora-reveal" id="informeView">${html}</div>
    <div class="report-actions mt-3 velora-reveal">
      <button class="btn btn-outline-primary" type="button" onclick="editarInforme(${idAlumno})" id="btnEditarInforme">Editar informe</button>
      <a class="btn btn-primary" href="/api/informe/${idAlumno}/pdf" id="btnDescargarInforme">Descargar PDF</a>
    </div>
  `;
  const generateBtn = document.getElementById('btnGenerar');
  if (generateBtn) generateBtn.textContent = 'Regenerar informe';
}

function limpiarFaltasInforme(contenido) {
  return (contenido || '')
    .replace(/^\s*(?:FALTAS|INASISTENCIAS|AUSENCIAS)\s*:[^\r\n]*(?:\r?\n|$)/gim, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function completarNombreInforme(contenido, nombre, apellido) {
  const nombreCompleto = [nombre, apellido].filter(Boolean).join(' ').trim();
  if (!contenido || !nombre || !apellido || !nombreCompleto) return contenido;
  const escaparRegex = texto => texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const nombreSolo = new RegExp(`(^|[^\\p{L}\\p{N}_])${escaparRegex(nombre)}(?![\\p{L}\\p{N}_]|\\s+${escaparRegex(apellido)}(?![\\p{L}\\p{N}_]))`, 'gu');
  return contenido.replace(nombreSolo, (_, prefijo) => `${prefijo}${nombreCompleto}`);
}

async function editarInforme(idAlumno) {
  // Obtener el contenido actual desde el servidor para tener el texto limpio
  try {
    const data = await api('GET', `/api/alumno/${idAlumno}/detalle`);
    let contenido = completarNombreInforme(
      limpiarFaltasInforme((data.informe && data.informe.contenido_informe) || ''),
      data.nombre,
      data.apellido
    );

    const container = document.getElementById('informeContainer');
    container.innerHTML = `
      <textarea class="informe-edit" id="informeTextarea">${contenido.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</textarea>
      <div class="report-actions mt-3">
        <button class="btn btn-primary" type="button" onclick="guardarInformeEdit(${idAlumno})">Guardar cambios</button>
        <button class="btn btn-outline-secondary" type="button" onclick="recargarInforme(${idAlumno})">Cancelar</button>
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
      mostrarInforme(ic, data.informe.contenido_informe, idAlumno, data.nombre, data.apellido);
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
  const informePrevio = Boolean(ic.querySelector('#informeView'));
  let resultado = 'error';
  if (btn) {
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.classList.add('velora-btn-loading');
    btn.innerHTML = '<span class="velora-button-loader" aria-hidden="true"></span><span>Preparando informe</span>';
  }
  if (!auto) {
    const estado = `<div class="${informePrevio ? 'velora-report-refresh' : 'velora-report-loading'}" role="status"><span class="velora-report-orbit" aria-hidden="true"><i></i></span><div class="velora-report-copy"><span class="velora-report-kicker">TU BORRADOR</span><strong>${informePrevio ? 'Actualizando el informe' : 'Preparando tu informe'}</strong><small>Ordenamos las observaciones para crear un punto de partida que puedas revisar.</small></div><span class="velora-loading-dots" aria-hidden="true"><i></i><i></i><i></i></span></div>`;
    if (informePrevio) ic.insertAdjacentHTML('afterbegin', estado);
    else ic.innerHTML = estado;
  }
  try {
    const r = await api('POST', `/api/informe/${idAlumno}`, {});
    mostrarInforme(ic, r.contenido, idAlumno);
    actualizarRecorridoAlumno(true, true);
    resultado = 'ok';
    if (!auto) mostrarToast('Informe generado. Revisalo antes de descargarlo.');
  } catch (e) {
    ic.querySelector('.velora-report-loading, .velora-report-refresh')?.remove();
    if (!informePrevio) {
      const error = document.createElement('div');
      error.className = 'velora-report-error';
      const title = document.createElement('strong');
      title.textContent = 'No pudimos generar el informe';
      const detail = document.createElement('small');
      detail.textContent = e.message || 'Probá nuevamente en unos instantes.';
      error.append(title, detail);
      ic.replaceChildren(error);
    }
    if (!auto) mostrarToast('Error al generar informe: ' + e.message, 'danger');
  } finally {
    if (btn) {
      const tieneInforme = Boolean(document.getElementById('informeView'));
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      btn.classList.remove('velora-btn-loading');
      btn.classList.toggle('velora-btn-success', resultado === 'ok' && !auto);
      btn.innerHTML = resultado === 'ok' && !auto
        ? '<span aria-hidden="true">✓</span><span>Informe listo</span>'
        : `<span aria-hidden="true">✦</span><span>${tieneInforme ? 'Regenerar informe' : 'Generar informe'}</span>`;
      if (resultado === 'ok' && !auto) setTimeout(() => {
        if (!btn.isConnected || btn.disabled) return;
        btn.classList.remove('velora-btn-success');
        btn.innerHTML = `<span aria-hidden="true">✦</span><span>${document.getElementById('informeView') ? 'Regenerar informe' : 'Generar informe'}</span>`;
      }, 1500);
    }
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
          <span class="small">${o.al_apellido}, ${o.al_nombre}</span>
          <span class="badge ${o.tipo === 'audio' ? 'bg-success' : 'bg-primary'}">${o.tipo === 'audio' ? '🎤' : '📝'}</span>
        </div>
        ${o.act_nombre ? `<small class="text-primary">${o.act_nombre}</small>` : ''}
        ${o.tipo === 'audio' && o.ruta_audio ? `
          <div class="mt-1">
            <audio controls preload="none" class="w-100" style="max-width:300px;height:32px">
              <source src="${o.ruta_audio}">
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

function toggleSelectAll(el) {
  document.querySelectorAll('#alumnosContainer .alumno-item:not([hidden]) .alumno-check').forEach(cb => cb.checked = el.checked);
  actualizarBulkBar();
}

function actualizarBulkBar() {
  const checkboxes = [...document.querySelectorAll('#alumnosContainer .alumno-item:not([hidden]) .alumno-check')];
  const checked = document.querySelectorAll('#alumnosContainer .alumno-check:checked');
  const selectAll = document.getElementById('selectAll');
  const bar = document.getElementById('bulkBar');
  const deleteButton = document.getElementById('bulkDeleteButton');
  const count = document.getElementById('bulkSelectedCount');
  if (bar) bar.classList.toggle('d-none', checked.length === 0);
  if (selectAll) {
    selectAll.checked = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
    selectAll.indeterminate = checkboxes.some(cb => cb.checked) && !selectAll.checked;
    selectAll.disabled = checkboxes.length === 0;
  }
  if (deleteButton) deleteButton.classList.toggle('d-none', checked.length === 0);
  if (count) count.textContent = checked.length ? `${checked.length} seleccionado${checked.length === 1 ? '' : 's'}` : '';
}

async function eliminarSeleccionados() {
  const ids = [...document.querySelectorAll('.alumno-check:checked')].map(cb => parseInt(cb.dataset.id));
  if (!ids.length) return;
  if (!confirm(`¿Eliminar ${ids.length} alumno(s) y sus observaciones?`)) return;
  try {
    await api('POST', '/api/alumnos/delete-multi', { ids });
    mostrarToast(ids.length + ' alumno(s) eliminado(s)');
    cargarAlumnos();
    cargarObsHoy();
    cargarStats();
  } catch (e) { mostrarToast(e.message, 'danger'); }
}

function desmarcarTodas() {
  document.querySelectorAll('.alumno-check').forEach(cb => cb.checked = false);
  const selectAll = document.getElementById('selectAll');
  if (selectAll) selectAll.checked = false;
  actualizarBulkBar();
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
        <p class="small">${filtro ? 'No hay indicadores para esta área hoy.' : 'No hay indicadores para hoy.'}</p>
        <button class="btn btn-sm btn-primary" onclick="document.getElementById('bulkActividades').focus()">Crear indicadores</button>
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
              ${a.unidad_titulo ? `<span class="badge bg-light text-muted fw-normal" style="font-size:0.65rem">${a.unidad_titulo}</span>` : ''}
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
  const unidadSelect = document.getElementById('bulkUnidad');
  const idUnidad = unidadSelect ? parseInt(unidadSelect.value) || null : null;
  const lines = textarea.value.trim().split('\n').filter(Boolean);
  if (!lines.length) return mostrarToast('Pegá al menos un indicador', 'warning');

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
    const r = await api('POST', '/api/actividades/multi', { actividades, id_unidad: idUnidad });
    textarea.value = '';
    mostrarToast(`${r.count} indicadores cargados`);
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
      mostrarToast('Indicador actualizado');
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
  if (!confirm('¿Eliminar este indicador?')) return;
  try {
    await api('DELETE', `/api/actividades/${id}`);
    mostrarToast('Indicador eliminado');
    cargarActividades();
  } catch (e) { mostrarToast(e.message, 'danger'); }
}

// ─── BOTÓN DE SOPORTE FLOTANTE ───────────
(function () {
  const path = window.location.pathname;
  if (!document.querySelector('.navbar') && !document.body.classList.contains('support-enabled')) return;
  if (path.startsWith('/admin')) return;

  const btn = document.createElement('button');
  btn.className = 'soporte-btn';
  btn.type = 'button';
  btn.title = 'Abrir ayuda y soporte';
  btn.setAttribute('aria-label', 'Abrir ayuda y soporte');
  btn.setAttribute('aria-expanded', 'false');
  btn.setAttribute('aria-controls', 'soportePanel');
  btn.innerHTML = '<span class="soporte-avatar-mini" aria-hidden="true">👩‍🏫</span><span class="soporte-label">¿Necesitás ayuda?</span><span class="soporte-badge d-none"></span>';
  document.body.appendChild(btn);

  const panel = document.createElement('section');
  panel.className = 'soporte-panel';
  panel.id = 'soportePanel';
  panel.setAttribute('aria-label', 'Chat de soporte');
  panel.setAttribute('aria-hidden', 'true');
  panel.innerHTML = '<header class="soporte-panel-header"><span class="soporte-avatar-mini" aria-hidden="true">👩‍🏫</span><div><strong>Ayuda y soporte</strong><small>Escribinos tu consulta</small></div><button type="button" class="soporte-close" aria-label="Cerrar chat">×</button></header><div class="soporte-panel-messages" id="soporteWidgetMsgs" aria-live="polite"><div class="chat-vacio">Cargando conversación…</div></div><form class="soporte-panel-form" id="soporteWidgetForm"><textarea id="soporteWidgetText" rows="1" maxlength="1000" placeholder="Escribí tu consulta…" aria-label="Escribí tu consulta"></textarea><button type="submit" aria-label="Enviar mensaje">➤</button></form>';
  document.body.appendChild(panel);
  let open = false;
  let miId = null;
  let ultimoMensaje = 0;
  let conversacionCargada = false;

  function cerrarPanel() {
    open = false;
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false');
  }
  function renderConversacion(mensajes) {
    const cont = panel.querySelector('#soporteWidgetMsgs');
    cont.replaceChildren();
    if (!mensajes.length) {
      const empty = document.createElement('div');
      empty.className = 'chat-vacio';
      empty.textContent = '¡Hola! Dejanos tu consulta y te ayudamos.';
      cont.appendChild(empty);
    }
    mensajes.forEach(m => {
      const bubble = document.createElement('div');
      bubble.className = `chat-burbuja ${m.id_usuario === miId ? 'propia' : 'ajena'}`;
      const text = document.createElement('div');
      text.className = 'chat-texto';
      text.textContent = m.texto;
      const time = document.createElement('div');
      time.className = 'chat-hora';
      time.textContent = m.fecha;
      bubble.append(text, time);
      cont.appendChild(bubble);
    });
    cont.scrollTop = cont.scrollHeight;
    ultimoMensaje = mensajes.length ? mensajes[mensajes.length - 1].id : 0;
  }
  async function cargarConversacion() {
    try {
      const data = await api('GET', '/api/soporte');
      miId = data.mi_id;
      const mensajes = data.mensajes || [];
      const idUltimo = mensajes.length ? mensajes[mensajes.length - 1].id : 0;
      if (!conversacionCargada || idUltimo !== ultimoMensaje) renderConversacion(mensajes);
      conversacionCargada = true;
      actualizarBadge();
    } catch (e) {
      panel.querySelector('#soporteWidgetMsgs').innerHTML = '<div class="chat-vacio">No se pudo cargar el chat. Probá de nuevo.</div>';
    }
  }
  btn.addEventListener('click', async () => {
    open = !open;
    panel.classList.toggle('open', open);
    panel.setAttribute('aria-hidden', String(!open));
    btn.setAttribute('aria-expanded', String(open));
    if (open) {
      if (!conversacionCargada) await cargarConversacion();
      panel.querySelector('#soporteWidgetText').focus();
    }
  });
  panel.querySelector('.soporte-close').addEventListener('click', cerrarPanel);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && open) cerrarPanel(); });
  panel.querySelector('#soporteWidgetForm').addEventListener('submit', async e => {
    e.preventDefault();
    const input = panel.querySelector('#soporteWidgetText');
    const text = input.value.trim();
    if (!text) return;
    const send = panel.querySelector('button[type="submit"]');
    send.disabled = true;
    try {
      await api('POST', '/api/soporte/mensaje', { texto: text });
      input.value = '';
      input.style.height = 'auto';
      await cargarConversacion();
    } catch (e) { mostrarToast(e.message, 'danger'); }
    finally { send.disabled = false; input.focus(); }
  });
  panel.querySelector('#soporteWidgetText').addEventListener('input', e => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
  });
  panel.querySelector('#soporteWidgetText').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      panel.querySelector('#soporteWidgetForm').requestSubmit();
    }
  });

  async function actualizarBadge() {
    try {
      const r = await fetch('/api/soporte/no-leidos', { headers: { 'Accept': 'application/json' } });
      if (!r.ok) return;
      const data = await r.json();
      const badge = btn.querySelector('.soporte-badge');
      if (data.count > 0) {
        badge.textContent = data.count > 99 ? '99+' : data.count;
        badge.classList.remove('d-none');
      } else {
        badge.classList.add('d-none');
      }
    } catch (e) {}
  }
  if (new URLSearchParams(window.location.search).get('soporte') === '1') {
    btn.click();
    history.replaceState(null, '', window.location.pathname);
  }
  actualizarBadge();
  setInterval(() => {
    actualizarBadge();
    if (open) cargarConversacion();
  }, 15000);
})();

// Las ayudas contextuales usan una única burbuja compacta en toda la app.
function iniciarBurbujasDeAyuda() {
  const triggers = [...document.querySelectorAll('.help-trigger')];
  if (!triggers.length) return;

  function cerrarAyudas() {
    document.querySelectorAll('.workflow-help-popover:not([hidden])').forEach(popover => {
      popover.hidden = true;
      popover.closest('.workflow-help')?.querySelector('.help-trigger')?.setAttribute('aria-expanded', 'false');
    });
  }

  triggers.forEach((trigger, index) => {
    let wrap = trigger.closest('.workflow-help');
    let popover = wrap?.querySelector('.workflow-help-popover');
    const modal = trigger.dataset.bsTarget ? document.querySelector(trigger.dataset.bsTarget) : null;
    if (!wrap) {
      wrap = document.createElement('span');
      wrap.className = 'workflow-help';
      trigger.parentNode.insertBefore(wrap, trigger);
      wrap.appendChild(trigger);
    }
    if (!popover) {
      popover = document.createElement('div');
      popover.className = 'workflow-help-popover';
      popover.hidden = true;
      const title = trigger.dataset.helpTitle || modal?.querySelector('.modal-title')?.textContent.trim() || trigger.getAttribute('aria-label') || 'Ayuda';
      const content = trigger.dataset.helpContent || modal?.querySelector('.modal-body')?.innerHTML || '';
      const heading = document.createElement('div');
      heading.className = 'workflow-help-popover-title';
      const headingText = document.createElement('span');
      headingText.textContent = title;
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'workflow-help-close';
      close.setAttribute('aria-label', 'Cerrar ayuda');
      close.textContent = '×';
      heading.append(headingText, close);
      const body = document.createElement('div');
      body.className = 'workflow-help-content';
      body.innerHTML = content;
      popover.append(heading, body);
      wrap.appendChild(popover);
    }

    const popoverId = popover.id || `helpBubble${index + 1}`;
    popover.id = popoverId;
    popover.setAttribute('role', 'dialog');
    trigger.classList.add('workflow-help-trigger');
    trigger.removeAttribute('data-bs-toggle');
    trigger.removeAttribute('data-bs-target');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', popoverId);
    trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const abrir = popover.hidden;
      cerrarAyudas();
      popover.hidden = !abrir;
      trigger.setAttribute('aria-expanded', String(abrir));
    });
    popover.querySelector('.workflow-help-close')?.addEventListener('click', event => {
      event.stopPropagation();
      popover.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    });
  });

  document.addEventListener('click', event => {
    if (!event.target.closest('.workflow-help')) cerrarAyudas();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') cerrarAyudas();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciarBurbujasDeAyuda, { once: true });
} else {
  iniciarBurbujasDeAyuda();
}

// Ripple breve al tocar, adaptado del patrón Ripple Button de Velora UI.
document.addEventListener('pointerdown', event => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const button = event.target.closest('.btn-primary, .btn-outline-primary, .welcome-action');
  if (!button || button.disabled) return;
  const bounds = button.getBoundingClientRect();
  const size = Math.max(bounds.width, bounds.height) * 1.5;
  button.querySelectorAll(':scope > .velora-ripple').forEach(ripple => ripple.remove());
  let label = button.querySelector(':scope > .velora-ripple-label');
  if (!label) {
    label = document.createElement('span');
    label.className = 'velora-ripple-label';
    while (button.firstChild) label.appendChild(button.firstChild);
    button.appendChild(label);
  }
  const ripple = document.createElement('span');
  ripple.className = 'velora-ripple';
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${event.clientX - bounds.left - size / 2}px`;
  ripple.style.top = `${event.clientY - bounds.top - size / 2}px`;
  button.classList.add('velora-ripple-host');
  button.appendChild(ripple);
  ripple.addEventListener('animationend', () => ripple.remove(), { once: true });
});

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


async function cambiarSala(idSala) {
  try {
    await api('POST', '/api/salas/activar', { id_sala: Number(idSala) });
    window.location.reload();
  } catch (e) { mostrarToast(e.message || 'No pudimos cambiar de sala.', 'danger'); }
}
