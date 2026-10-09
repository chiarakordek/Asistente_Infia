document.addEventListener('DOMContentLoaded', () => {
  cargarUnidades();
  document.getElementById('formUnidad').addEventListener('submit', event => { event.preventDefault(); guardarUnidad(); });
});
    let editandoUnidadId = null;

    async function cargarUnidades() {
      const c = document.getElementById('unidadesContainer');
      try {
        const unidades = await api('GET', '/api/unidades');
        const unidadSelect = document.getElementById('actUnidad');
        const unidadSeleccionada = unidadSelect.value;
        unidadSelect.replaceChildren(new Option('Sin unidad', ''), ...unidades.map(u => new Option(u.titulo, u.id_unidad)));
        if (unidades.some(u => String(u.id_unidad) === unidadSeleccionada)) unidadSelect.value = unidadSeleccionada;
        if (!unidades.length) {
          c.innerHTML = '<div class="text-center py-5 text-muted"><p class="mb-1" style="font-size:2rem">📚</p><p class="small">No hay unidades didácticas todavía.</p></div>';
          return;
        }
        c.innerHTML = `
          <div class="d-flex align-items-center gap-2 mb-2 ${unidades.length ? '' : 'd-none'}" id="bulkBarUni">
            <input type="checkbox" id="selectAllUni" onchange="toggleSelectAllUni(this)">
            <span class="text-muted small">Seleccionar todo</span>
            <button class="btn btn-sm btn-danger ms-auto" onclick="eliminarUnidadesSeleccionadas()">Eliminar seleccionadas</button>
          </div>
        ` + unidades.map(u => `
          <div class="card mb-2 p-3">
            <div class="d-flex justify-content-between align-items-start">
              <div class="d-flex align-items-center gap-2">
                <input type="checkbox" class="uni-check" data-id="${u.id_unidad}" onchange="actualizarBulkBarUni()">
                <div>
                  <h6 class="mb-1">${u.titulo}</h6>
                  <p class="small text-muted mb-0">${(u.contenido||'').substring(0,150)}${(u.contenido||'').length>150?'...':''}</p>
                  <small class="text-muted">${u.fecha_creacion||''}</small>
                </div>
              </div>
              <div class="d-flex gap-1 flex-shrink-0">
                <button class="btn btn-sm btn-outline-secondary" onclick="editarUnidad(${u.id_unidad})">Editar</button>
              </div>
            </div>
          </div>
        `).join('');
        if (unidades.length) actualizarBulkBarUni();
      } catch (e) {
        c.innerHTML = '<div class="alert alert-danger py-2 small">'+e.message+'</div>';
      }
    }

    function mostrarModalUnidad() {
      editandoUnidadId = null;
      document.getElementById('modalUnidadTitle').textContent = 'Nueva unidad';
      document.getElementById('formUnidad').reset();
      new bootstrap.Modal('#modalUnidad').show();
    }

    async function guardarUnidad() {
      const titulo = document.getElementById('uTitulo').value.trim();
      const contenido = document.getElementById('uContenido').value.trim();
      if (!titulo) return mostrarToast('El título es obligatorio','warning');
      try {
        if (editandoUnidadId) {
          await api('PUT', '/api/unidades/'+editandoUnidadId, { titulo, contenido });
          mostrarToast('Unidad actualizada');
        } else {
          await api('POST', '/api/unidades', { titulo, contenido });
          mostrarToast('Unidad creada');
        }
        bootstrap.Modal.getInstance(document.getElementById('modalUnidad')).hide();
        cargarUnidades();
      } catch (e) { mostrarToast(e.message,'danger'); }
    }

    async function editarUnidad(id) {
      try {
        const unidades = await api('GET', '/api/unidades');
        const unidadSelect = document.getElementById('actUnidad');
        const unidadSeleccionada = unidadSelect.value;
        unidadSelect.replaceChildren(new Option('Sin unidad', ''), ...unidades.map(u => new Option(u.titulo, u.id_unidad)));
        if (unidades.some(u => String(u.id_unidad) === unidadSeleccionada)) unidadSelect.value = unidadSeleccionada;
        const u = unidades.find(x => x.id_unidad === id);
        if (!u) return;
        editandoUnidadId = id;
        document.getElementById('modalUnidadTitle').textContent = 'Editar unidad';
        document.getElementById('uTitulo').value = u.titulo;
        document.getElementById('uContenido').value = u.contenido||'';
        new bootstrap.Modal('#modalUnidad').show();
      } catch (e) { mostrarToast(e.message,'danger'); }
    }

    async function eliminarUnidad(id) {
      if (!confirm('¿Eliminar esta unidad?')) return;
      try {
        await api('DELETE', '/api/unidades/'+id);
        mostrarToast('Unidad eliminada');
        cargarUnidades();
      } catch (e) { mostrarToast(e.message,'danger'); }
    }

    function toggleSelectAllUni(el) {
      document.querySelectorAll('.uni-check').forEach(cb => cb.checked = el.checked);
      actualizarBulkBarUni();
    }

    function actualizarBulkBarUni() {
      const checked = document.querySelectorAll('.uni-check:checked');
      document.getElementById('bulkBarUni').classList.toggle('d-none', checked.length === 0);
    }

    async function eliminarUnidadesSeleccionadas() {
      const ids = [...document.querySelectorAll('.uni-check:checked')].map(cb => parseInt(cb.dataset.id));
      if (!ids.length) return;
      if (!confirm('¿Eliminar ' + ids.length + ' unidad(es)?')) return;
      try {
        await api('POST', '/api/unidades/delete-multi', { ids });
        mostrarToast(ids.length + ' unidad(es) eliminada(s)');
        cargarUnidades();
      } catch (e) { mostrarToast(e.message, 'danger'); }
    }