document.addEventListener('DOMContentLoaded', cargarAreas);

    async function cargarAreas() {
      try {
        const areas = await api('GET', '/api/areas');
        const c = document.getElementById('areasContainer');
        const areaSelect = document.getElementById('actArea');
        const areaSeleccionada = areaSelect.value;
        areaSelect.replaceChildren(new Option('Seleccionar área', '', true, true), ...areas.map(a => new Option(a.nombre, a.nombre)));
        if (areas.some(a => a.nombre === areaSeleccionada)) areaSelect.value = areaSeleccionada;
        if (!areas.length) {
          c.innerHTML = '<div class="text-center py-4 text-muted small">No hay áreas</div>';
          return;
        }
        c.innerHTML = `
          <div class="d-flex align-items-center gap-2 mb-2 ${areas.length ? '' : 'd-none'}" id="bulkBarArea">
            <input type="checkbox" id="selectAllArea" onchange="toggleSelectAllArea(this)">
            <span class="text-muted small">Seleccionar todo</span>
            <button class="btn btn-sm btn-danger ms-auto" onclick="eliminarAreasSeleccionadas()">Eliminar seleccionadas</button>
          </div>
        ` + areas.map(a => `
          <div class="actividad-card">
            <div class="d-flex align-items-center gap-2">
              <input type="checkbox" class="area-check" data-id="${a.id}" onchange="actualizarBulkBarArea()">
              <span>${a.nombre}</span>
            </div>
            <div class="d-flex gap-1">
              <button class="btn btn-sm btn-outline-secondary" onclick="editarArea(${a.id},'${a.nombre.replace(/'/g,"\\'")}')">Editar</button>
            </div>
          </div>
        `).join('');
        if (areas.length) actualizarBulkBarArea();
      } catch (e) {}
    }

    async function agregarArea() {
      const inp = document.getElementById('nuevaArea');
      const nombre = inp.value.trim();
      if (!nombre) return mostrarToast('Escribí un nombre', 'warning');
      try {
        await api('POST', '/api/areas', { nombre });
        inp.value = '';
        mostrarToast('Área agregada');
        cargarAreas();
      } catch (e) { mostrarToast('Error: ' + e.message, 'danger'); }
    }

    async function editarArea(id, nombreActual) {
      const nuevo = prompt('Nombre del área:', nombreActual);
      if (!nuevo || nuevo === nombreActual) return;
      try {
        await api('PUT', '/api/areas/' + id, { nombre: nuevo });
        mostrarToast('Área actualizada');
        cargarAreas();
      } catch (e) { mostrarToast('Error: ' + e.message, 'danger'); }
    }

    async function eliminarArea(id) {
      if (!confirm('¿Eliminar esta área? Los indicadores quedarán como "Sin área".')) return;
      try {
        await api('DELETE', '/api/areas/' + id);
        mostrarToast('Área eliminada');
        cargarAreas();
      } catch (e) { mostrarToast('Error: ' + e.message, 'danger'); }
    }

    function toggleSelectAllArea(el) {
      document.querySelectorAll('.area-check').forEach(cb => cb.checked = el.checked);
      actualizarBulkBarArea();
    }

    function actualizarBulkBarArea() {
      const checked = document.querySelectorAll('.area-check:checked');
      document.getElementById('bulkBarArea').classList.toggle('d-none', checked.length === 0);
    }

    async function eliminarAreasSeleccionadas() {
      const ids = [...document.querySelectorAll('.area-check:checked')].map(cb => parseInt(cb.dataset.id));
      if (!ids.length) return;
      if (!confirm('¿Eliminar ' + ids.length + ' área(s)? Los indicadores quedarán como "Sin área".')) return;
      try {
        await api('POST', '/api/areas/delete-multi', { ids });
        mostrarToast(ids.length + ' área(s) eliminada(s)');
        cargarAreas();
      } catch (e) { mostrarToast('Error: ' + e.message, 'danger'); }
    }
