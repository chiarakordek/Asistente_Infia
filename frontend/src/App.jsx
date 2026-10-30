import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { ArrowUpRight, BookOpenCheck, ClipboardList, LoaderCircle, Mic2, UsersRound, Search, Plus, Trash2, X, Square, MessageCircle, Send } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

async function request(path) {
  const response = await fetch(path, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (response.status === 401) throw new Error('session');
  if (response.status === 402) { window.location.assign(`${window.location.pathname.startsWith('/react-preview') ? '/react-preview' : ''}/suscripcion`); throw new Error('subscription'); }
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('No pudimos conectar con Infia. Revisá tu conexión e intentá otra vez.');
  if (!response.ok) throw new Error('No pudimos cargar esta información. Intentá actualizar la página.');
  return response.json();
}

async function mutate(path, method, payload) {
  const response = await fetch(path, { method, credentials: 'same-origin', headers: { Accept: 'application/json', ...(payload instanceof FormData ? {} : { 'Content-Type': 'application/json' }) }, body: payload == null ? undefined : payload instanceof FormData ? payload : JSON.stringify(payload) });
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('No pudimos conectar con Infia. Revisá tu conexión e intentá otra vez.');
  const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : {};
  if (!response.ok) throw new Error(data.error || 'No pudimos completar la acción. Intentá nuevamente.');
  return data;
}

function AppFrame({ children, user }) {
  const location = useLocation();
  const [rooms, setRooms] = useState([]);
  const [roomId, setRoomId] = useState('');

  useEffect(() => {
    if (location.pathname === '/suscripcion') return;
    request('/api/salas').then(data => {
      setRooms(data);
      const active = data.find(room => room.activa);
      if (active) setRoomId(String(active.id_sala));
    }).catch(() => {});
  }, [location.pathname]);

  async function changeRoom(id) {
    setRoomId(id);
    try {
      await mutate('/api/salas/activar', 'POST', { id_sala: Number(id) });
      window.location.reload();
    } catch (error) { setRoomId(''); window.alert(error.message); }
  }

  return <div className="infia-app-shell">
    <header className="app-header">
      <Link className="brand" to="/dashboard" aria-label="Infia, inicio">
        <img src="/static/icons/iconoinfia.png" alt="" /><span>Infia</span>
      </Link>
      {location.pathname !== '/suscripcion' && <div className="header-room">
        <label htmlFor="active-room">Sala</label>
        <select id="active-room" value={roomId} onChange={event => changeRoom(event.target.value)} aria-label="Cambiar de sala">
          {rooms.map(room => <option value={room.id_sala} key={room.id_sala}>{room.nombre} · {room.turno}</option>)}
        </select>
        <Link to="/salas" aria-label="Administrar salas" title="Administrar salas"><ArrowUpRight size={17} /></Link>
      </div>}
      <nav className="main-nav" aria-label="Navegación principal">
        <Link className={location.pathname === '/dashboard' ? 'active' : ''} to="/dashboard">Inicio</Link>
        <Link className={location.pathname.startsWith('/planificacion') ? 'active' : ''} to="/planificacion">Planificación</Link>
        <Link className={location.pathname === '/perfil' ? 'active' : ''} to="/perfil">Perfil</Link>
        {user.es_admin && <Link className={location.pathname === '/admin' ? 'active' : ''} to="/admin">Admin</Link>}
        <button type="button" onClick={async () => { await fetch('/api/logout', { credentials: 'same-origin' }); window.location.href = `${window.location.pathname.startsWith('/react-preview') ? '/react-preview' : ''}/login`; }}>Salir</button>
      </nav>
    </header>
    <main className="app-main">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={location.pathname} className="route-motion" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: .18 }}>
          {children}
        </motion.div>
      </AnimatePresence>
    </main>
    <SupportBubble />
  </div>;
}

function SupportBubble(){const location=useLocation();const [open,setOpen]=useState(new URLSearchParams(location.search).get('soporte')==='1'),[data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);async function load(){setError('');try{setData(await request('/api/soporte'));}catch(err){setError(err.message);}}useEffect(()=>{if(new URLSearchParams(location.search).get('soporte')==='1')setOpen(true);},[location.search]);useEffect(()=>{if(open)load();},[open]);async function send(e){e.preventDefault();const form=e.currentTarget;const fields=new FormData(form);setBusy(true);try{await mutate('/api/soporte/mensaje','POST',{texto:fields.get('texto')});form.reset();await load();}catch(err){setError(err.message);}finally{setBusy(false);}}return <div className="support-widget"><button className="support-fab" aria-label={open?'Cerrar soporte':'Abrir ayuda y soporte'} onClick={()=>setOpen(!open)}>{open?<X size={21}/>:<span className="support-avatar-mini" aria-hidden="true">👩‍🏫</span>}<span>{open?'Cerrar':'¿Necesitás ayuda?'}</span></button>{open&&<section className="support-panel" aria-label="Chat de soporte"><header><div className="support-header-avatar" aria-hidden="true">👩‍🏫</div><div><strong>Ayuda y soporte</strong><small>Escribinos tu consulta</small></div><button aria-label="Cerrar" onClick={()=>setOpen(false)}><X size={18}/></button></header><div className="support-messages">{error&&<p className="inline-error">{error}</p>}{data?.mensajes?.length?data.mensajes.map(message=><article key={message.id} className={`support-message ${message.id_usuario===data.mi_id?'mine':''}`}><p>{message.texto}</p><small>{message.fecha}</small></article>):<p className="quiet-empty">Todavía no hay mensajes. Escribinos cuando quieras.</p>}</div><form className="support-compose" onSubmit={send}><input name="texto" aria-label="Escribí tu mensaje" required placeholder="Escribí tu mensaje…"/><button disabled={busy} aria-label="Enviar mensaje"><Send size={17}/></button></form></section>}</div>}

function AuthPage() {
  const location = useLocation();
  const path = location.pathname;
  const isRegister = path === '/registro';
  const isForgot = path === '/forgot';
  const isReset = path.startsWith('/reset/');
  const token = isReset ? path.split('/').pop() : '';
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [needsInvite, setNeedsInvite] = useState(false);

  useEffect(() => {
    fetch('/api/me', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then(response => {
      if (response.ok && response.headers.get('content-type')?.includes('application/json') && !isForgot && !isReset) {
        window.location.assign(`${window.location.pathname.startsWith('/react-preview') ? '/react-preview' : ''}/dashboard`);
      }
    }).catch(() => {});
  }, []);

  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(''); setNotice(''); setBusy(true);
    const prefix = window.location.pathname.startsWith('/react-preview') ? '/react-preview' : '';
    try {
      if (path === '/login') {
        const result = await mutate('/api/login', 'POST', { email: form.get('email'), contraseña: form.get('password') });
        window.location.assign(`${prefix}${result.destino || '/dashboard'}`); return;
      }
      if (isRegister) {
        if (form.get('password') !== form.get('password2')) throw new Error('Las contraseñas no coinciden.');
        await mutate('/api/register', 'POST', { nombre: form.get('nombre'), email: form.get('email'), contraseña: form.get('password'), sala: form.get('sala'), turno: form.get('turno'), codigo: form.get('codigo'), acepta_terminos: form.get('terms') === 'on' });
        window.location.assign(`${prefix}/dashboard`); return;
      }
      if (isForgot) {
        const result = await mutate('/api/usuario/reset-solicitar', 'POST', { email: form.get('email') });
        setNotice(result.mensaje); return;
      }
      await mutate(`/api/usuario/reset/${token}`, 'POST', { nueva: form.get('password') });
      setNotice('Contraseña actualizada. Ya podés iniciar sesión.');
    } catch (err) {
      setError(err.message);
      if (isRegister && err.message.toLowerCase().includes('invitación')) setNeedsInvite(true);
    } finally { setBusy(false); }
  }

  const title = isRegister ? 'Creá tu espacio' : isForgot ? 'Recuperá tu contraseña' : isReset ? 'Elegí una contraseña nueva' : 'Qué bueno verte';
  const showForm = !notice || (isReset && notice.startsWith('Contraseña'));
  return <main className="auth-react">
    <Link className="brand auth-brand" to="/login"><img src="/static/icons/iconoinfia.png" alt=""/>Infia</Link>
    <section className="auth-react-story"><span className="eyebrow">HECHA PARA ACOMPAÑAR TU TAREA</span><h1>Lo que pasa en la sala merece quedar registrado.</h1><p>Dictá una observación en el momento y convertí ese recorrido en un informe que podés revisar, editar y descargar.</p><div className="auth-story-card"><span className="recording-pip"/> Nota de voz transcripta<p>“Hoy Alma se animó a contar cómo resolvió el desafío con sus compañeras.”</p><small>Guardada en la ficha de la alumna ✓</small></div><div className="auth-story-steps"><span>01 · Registrá</span><span>02 · Revisá</span><span>03 · Prepará</span></div></section>
    <section className="auth-react-card"><span className="eyebrow">{isRegister?'TU AULA, MÁS FÁCIL DE ACOMPAÑAR':'TU ESPACIO DE TRABAJO'}</span><h2>{title}</h2><p>{isRegister?'Un espacio sencillo para guardar lo que ves cada día.':isForgot?'Te enviaremos un enlace para recuperar el acceso.':isReset?'Usá una clave segura que puedas recordar.':'Iniciá sesión para seguir con tus salas y observaciones.'}</p>
      {error&&<p className="inline-error" role="alert">{error}</p>}{notice&&<p className="inline-success" role="status">{notice}</p>}
      {showForm&&<form className="auth-react-form" onSubmit={submit}>
        {isRegister&&<label>Nombre completo<input name="nombre" autoComplete="name" required placeholder="Tu nombre y apellido"/></label>}
        {!isReset&&!isForgot&&<label>Email<input name="email" type="email" autoComplete="email" required placeholder="tu@email.com"/></label>}
        {isForgot&&<label>Email<input name="email" type="email" autoComplete="email" required placeholder="tu@email.com"/></label>}
        {isRegister&&needsInvite&&<label>Código de invitación<input name="codigo" required/></label>}
        {isRegister&&<><label>Contraseña<input name="password" type="password" minLength="8" autoComplete="new-password" required/><small>8 caracteres, una mayúscula y un número.</small></label><label>Confirmar contraseña<input name="password2" type="password" autoComplete="new-password" required/></label><div className="auth-two-cols"><label>Sala<select name="sala"><option>3 Años A</option><option>3 Años B</option><option>3 Años C</option><option>4 Años A</option><option>4 Años B</option><option>4 Años C</option><option>5 Años A</option><option>5 Años B</option></select></label><label>Turno<select name="turno"><option>Mañana</option><option selected>Tarde</option></select></label></div><label className="auth-check"><input name="terms" type="checkbox" required/> Acepto los <Link to="/terminos">Términos de uso</Link> y la <Link to="/privacidad">Política de privacidad</Link>.</label></>}
        {!isRegister&&!isForgot&&<label>{isReset?'Nueva contraseña':'Contraseña'}<input name="password" type="password" minLength={isReset?8:undefined} autoComplete={isReset?'new-password':'current-password'} required/></label>}
        <button className="button-primary" disabled={busy}>{busy?'Un momento…':isRegister?'Crear mi cuenta':isForgot?'Enviar enlace':isReset?'Actualizar contraseña':'Entrar a mi aula'} <ArrowUpRight size={17}/></button>
      </form>}
      {!isRegister&&!isForgot&&!isReset&&<Link className="auth-forgot-link" to="/forgot">¿Olvidaste tu contraseña?</Link>}
      {isReset&&notice&&<div className="auth-bottom-link"><Link to="/login">Ir a iniciar sesión</Link></div>}
      {!isReset&&!isForgot&&<div className="auth-bottom-link">{isRegister?<><span>¿Ya tenés cuenta?</span> <Link to="/login">Iniciar sesión</Link></>:<><span>¿Todavía no tenés cuenta?</span> <Link to="/registro">Crear mi espacio</Link></>}</div>}
      <div className="auth-legal-links"><Link to="/privacidad">Privacidad</Link><span>·</span><Link to="/terminos">Términos de uso</Link></div>
    </section>
  </main>;
}

function Dashboard({ user, onUser }) {
  const location = useLocation();
  const [students, setStudents] = useState(null);
  const [stats, setStats] = useState(null);
  const [activities, setActivities] = useState([]);
  const [today, setToday] = useState([]);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState([]);
  const [dialog, setDialog] = useState(null);
  const [working, setWorking] = useState(false);
  const [recording, setRecording] = useState(null);
  const [tourOpen, setTourOpen] = useState(new URLSearchParams(location.search).get('tutorial') === '1' || !user.tutorial_completado);
  const recorder = useRef(null);
  const chunks = useRef([]);

  async function refresh() {
    const [list, summary, acts, observations] = await Promise.all([request('/api/alumnos'), request('/api/stats'), request('/api/actividades'), request('/api/observaciones/hoy')]);
    setStudents(list); setStats(summary); setActivities(acts); setToday(observations);
  }
  useEffect(() => { refresh().catch(err => err.message === 'session' ? window.location.assign('/login') : setError(err.message)); }, []);

  async function submitObservation(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setWorking(true); setError('');
    try {
      await mutate('/api/observaciones', 'POST', { id_alumno: Number(form.get('id_alumno')), id_actividad: form.get('id_actividad') || null, nota_cruda: form.get('nota_cruda') });
      setDialog(null); await refresh();
    } catch (err) { setError(err.message); } finally { setWorking(false); }
  }

  async function submitStudents(event) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const raw = String(form.get('names') || '');
    const alumnos = raw.split(/\n|,/).map(line => line.trim()).filter(Boolean).map(line => { const parts = line.split(/\s+/); return { nombre: parts.shift(), apellido: parts.join(' ') }; }).filter(item => item.apellido);
    if (!alumnos.length) { setError('Escribí nombre y apellido de cada alumno.'); return; }
    setWorking(true); setError('');
    try { if (alumnos.length === 1) await mutate('/api/alumnos', 'POST', alumnos[0]); else await mutate('/api/alumnos/multi', 'POST', { alumnos }); setDialog(null); await refresh(); }
    catch (err) { setError(err.message); } finally { setWorking(false); }
  }

  async function toggleRecording(student) {
    if (recording) {
      recorder.current?.stop(); setRecording(null); return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { setError('Este dispositivo no permite grabar desde el navegador. Podés registrar la observación por escrito.'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream); recorder.current = media; chunks.current = [];
      media.ondataavailable = event => { if (event.data.size) chunks.current.push(event.data); };
      media.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        const blob = new Blob(chunks.current, { type: media.mimeType || 'audio/webm' });
        const body = new FormData(); body.append('audio', blob, 'observacion.webm'); body.append('id_alumno', student.id_alumno);
        setWorking(true);
        try { await mutate('/api/audio/subir', 'POST', body); await refresh(); }
        catch (err) { setError(err.message); } finally { setWorking(false); }
      };
      media.start(); setRecording(student.id_alumno);
    } catch { setError('No pudimos acceder al micrófono. Revisá el permiso del navegador.'); }
  }

  async function deleteSelected() {
    if (!selected.length || !window.confirm(`¿Eliminar ${selected.length} alumno${selected.length === 1 ? '' : 's'} y sus registros? Esta acción no se puede deshacer.`)) return;
    setWorking(true); setError('');
    try { await mutate('/api/alumnos/delete-multi', 'POST', { ids: selected }); setSelected([]); await refresh(); }
    catch (err) { setError(err.message); } finally { setWorking(false); }
  }

  const visibleStudents = (students || []).filter(student => `${student.nombre} ${student.apellido}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const allVisibleSelected = visibleStudents.length > 0 && visibleStudents.every(student => selected.includes(student.id_alumno));
  function toggleOne(id) { setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]); }

  async function finishTour() { try { await mutate('/api/tutorial/completar','POST',{}); onUser({...user,tutorial_completado:true}); } catch {} setTourOpen(false); }

  return <div className="dashboard-view">
    <section className="welcome-panel">
      <div className="welcome-avatar">{user.nombre?.[0]?.toUpperCase() || 'I'}</div>
      <div><span className="eyebrow">TU AULA, EN UN SOLO LUGAR</span><h1>Hola, {user.nombre}</h1><p>Cada observación ayuda a contar mejor el recorrido de tus alumnos.</p></div>
      <a className="button-primary" href="#students">Cargar observación <ArrowUpRight size={17} /></a>
    </section>
    <section className="stats-grid" aria-label="Resumen del aula">
      {[['Alumnos', stats?.total_alumnos], ['Observaciones hoy', stats?.observaciones_hoy], ['Observaciones', stats?.total_observaciones], ['Informes', stats?.total_informes]].map(([label, value]) => <article className="stat-card" key={label}><span>{label}</span><strong>{value ?? '—'}</strong></article>)}
    </section>
    <section className="students-panel" id="students">
      <div className="section-heading"><div><span className="eyebrow">REGISTRO DIARIO</span><h2>Mis alumnos</h2><p>Dictá con el micrófono para registrar en el momento o tocá + para escribir.</p></div><div className="heading-actions"><button className="button-soft" type="button" onClick={() => setDialog({ type: 'student' })}>Agregar varios</button><button className="button-primary" type="button" onClick={() => setDialog({ type: 'student' })}><Plus size={16}/> Agregar alumno</button></div></div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <div className="student-tools"><label className="search-box"><Search size={19}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Buscar un alumno por nombre"/><span>{students?.length ?? 0} alumnos</span></label>
        {selected.length > 0 && <div className="selection-toolbar"><label><input type="checkbox" checked={allVisibleSelected} onChange={() => setSelected(allVisibleSelected ? selected.filter(id => !visibleStudents.some(s => s.id_alumno === id)) : [...new Set([...selected, ...visibleStudents.map(s => s.id_alumno)])])}/> Seleccionar todos</label><button className="button-danger" disabled={working} onClick={deleteSelected}><Trash2 size={16}/> Eliminar seleccionados ({selected.length})</button></div>}
      </div>
      {students === null ? <div className="loading-state"><LoaderCircle className="spin" size={22} /> Cargando tus alumnos…</div> : students.length === 0 ? <div className="empty-state"><UsersRound size={30} /><strong>Tu sala empieza acá</strong><p>Agregá a tus alumnos para comenzar a registrar observaciones.</p><button className="button-primary" onClick={() => setDialog({ type: 'student' })}><Plus size={17}/> Agregar alumnos</button></div> : visibleStudents.length === 0 ? <div className="empty-state">No encontramos alumnos con ese nombre.</div> : <ul className="student-list">{visibleStudents.map(student => <li key={student.id_alumno} className={`student-row ${selected.includes(student.id_alumno) ? 'selected' : ''}`}><input aria-label={`Seleccionar ${student.nombre} ${student.apellido}`} type="checkbox" checked={selected.includes(student.id_alumno)} onChange={() => toggleOne(student.id_alumno)}/><span className="student-avatar">{student.nombre?.[0]}{student.apellido?.[0]}</span><Link className="student-link" to={`/alumno/${student.id_alumno}`}>{student.apellido}, {student.nombre}<ArrowUpRight size={17} /></Link><button className={`icon-button voice-button ${recording === student.id_alumno ? 'recording' : ''}`} disabled={working || (recording && recording !== student.id_alumno)} type="button" onClick={() => toggleRecording(student)} aria-label={recording === student.id_alumno ? 'Detener grabación' : `Grabar observación de ${student.nombre} ${student.apellido}`} title={recording === student.id_alumno ? 'Detener grabación' : 'Grabar observación por voz'}>{recording === student.id_alumno ? <Square size={18}/> : <Mic2 size={19}/>}</button><button className="button-soft" type="button" onClick={() => setDialog({ type: 'observation', student })}>＋ Registrar observación</button></li>)}</ul>}
    </section>
    <section className="students-panel daily-panel"><div className="section-heading"><div><span className="eyebrow">HOY</span><h2>Lo que quedó registrado</h2></div><span className="daily-count">{today.length} {today.length === 1 ? 'observación' : 'observaciones'}</span></div>{today.length ? <ul className="daily-list">{today.map((item, index) => <li key={item.id_observacion || index}><span className="daily-dot"/><div><strong>{item.al_apellido}, {item.al_nombre}</strong><p>{item.nota_cruda}</p><small>{item.act_nombre || 'Observación libre'}</small></div></li>)}</ul> : <p className="quiet-empty">Las observaciones que registres hoy van a aparecer acá.</p>}</section>
    <div className="secondary-links"><Link to="/planificacion"><BookOpenCheck size={17} /> Organizar indicadores y unidades</Link></div>
    <Dialog open={!!dialog} close={() => setDialog(null)} title={dialog?.type === 'student' ? 'Agregar alumnos' : `Registrar observación · ${dialog?.student?.nombre || ''} ${dialog?.student?.apellido || ''}`}>
      {dialog?.type === 'student' ? <form className="modal-form" onSubmit={submitStudents}><p>Escribí nombre y apellido. Para cargar varios, poné un alumno por línea.</p><textarea autoFocus name="names" rows="5" placeholder={'Alma García\nTomás Pérez'} required/><button className="button-primary" disabled={working}>{working ? 'Guardando…' : 'Guardar alumnos'}</button></form> : <form className="modal-form" onSubmit={submitObservation}><label>¿Qué observaste?<textarea autoFocus name="nota_cruda" rows="5" required placeholder="Contá brevemente lo que pasó…"/></label><label>Indicador (opcional)<select name="id_actividad"><option value="">Sin indicador</option>{activities.map(activity => <option key={activity.id_actividad} value={activity.id_actividad}>{activity.area} · {activity.nombre}</option>)}</select></label><input type="hidden" name="id_alumno" value={dialog?.student?.id_alumno || ''}/><button className="button-primary" disabled={working}>{working ? 'Guardando…' : 'Guardar observación'}</button></form>}
    </Dialog>
    <WelcomeTour open={tourOpen} close={finishTour}/>
  </div>;
}

function WelcomeTour({open,close}){const [step,setStep]=useState(0);const steps=[['Bienvenida a Infia','Este es tu espacio para registrar lo que observás y preparar informes con tu mirada.'],['Cargá una observación','Usá el micrófono al lado del nombre para dictar en el momento, o escribí una nota.'],['Revisá la ficha','Abrí un alumno para consultar lo registrado, generar un borrador, editarlo y descargarlo.'],['Organizá tu planificación','Áreas, indicadores y unidades son herramientas opcionales. Podés configurarlas cuando las necesites.']];if(!open)return null;return <div className="dialog-backdrop tour-backdrop"><section className="dialog-card tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title"><span className="eyebrow">RECORRIDO BREVE · {step+1} DE {steps.length}</span><div className="tour-progress" aria-label={`Paso ${step+1} de ${steps.length}`}><span style={{width:`${((step+1)/steps.length)*100}%`}}/></div><h2 id="tour-title">{steps[step][0]}</h2><p>{steps[step][1]}</p><div className="tour-footer"><button className="tour-skip" onClick={close}>Saltar</button><button className="button-primary" onClick={()=>step===steps.length-1?close():setStep(step+1)}>{step===steps.length-1?'Empezar a usar Infia':'Siguiente →'}</button></div></section></div>}

function Dialog({ open, close, title, children }) {
  useEffect(() => { if (!open) return; const onKey = event => event.key === 'Escape' && close(); window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey); }, [open, close]);
  if (!open) return null;
  return <div className="dialog-backdrop" onMouseDown={event => event.target === event.currentTarget && close()}><section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><header><h2 id="dialog-title">{title}</h2><button className="dialog-close" type="button" onClick={close} aria-label="Cerrar"><X size={20}/></button></header>{children}</section></div>;
}

function StudentDetail() {
  const { studentId } = useParams();
  const [data, setData] = useState(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [editing, setEditing] = useState(false); const [draft, setDraft] = useState('');
  const [selectedObs, setSelectedObs] = useState([]);
  async function load() { const result = await request(`/api/alumno/${studentId}/detalle`); setData(result); setDraft(result.informe?.contenido_informe || ''); }
  useEffect(() => { load().catch(err => setError(err.message)); }, [studentId]);
  async function generate() { setBusy(true); setError(''); try { await mutate(`/api/informe/${studentId}`, 'POST'); await load(); setEditing(false); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  async function save() { setBusy(true); setError(''); try { await mutate(`/api/informe/${studentId}`, 'PUT', { contenido: draft }); await load(); setEditing(false); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  async function removeObservation(id) { if (!window.confirm('¿Eliminar esta observación?')) return; try { await mutate(`/api/observaciones/${id}`, 'DELETE'); await load(); } catch (err) { setError(err.message); } }
  async function removeSelectedObs() { if (!selectedObs.length || !window.confirm(`¿Eliminar ${selectedObs.length} observaciones?`)) return; setBusy(true); setError(''); try { await mutate('/api/observaciones/batch-delete','POST',{ids:selectedObs}); setSelectedObs([]); await load(); } catch (err) { setError(err.message); } finally { setBusy(false); } }
  if (!data) return <div className="loading-state"><LoaderCircle className="spin"/> {error || 'Cargando ficha…'}</div>;
  return <div className="detail-view"><Link className="back-link" to="/dashboard">← Volver a mis alumnos</Link><section className="welcome-panel"><span className="student-avatar large">{data.nombre?.[0]}{data.apellido?.[0]}</span><div><span className="eyebrow">FICHA DEL ALUMNO</span><h1>{data.nombre} {data.apellido}</h1><p>{data.observaciones?.length || 0} observaciones registradas</p></div><button className="button-primary" disabled={busy} onClick={generate}><BookOpenCheck size={17}/>{busy ? 'Preparando…' : data.informe ? 'Regenerar informe' : 'Generar informe'}</button></section>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <section className="students-panel"><div className="section-heading"><div><span className="eyebrow">RECORRIDO</span><h2>Observaciones</h2></div>{data.observaciones?.length>0&&<div className="heading-actions">{selectedObs.length>0&&<button className="button-danger" disabled={busy} onClick={removeSelectedObs}><Trash2 size={16}/> Eliminar seleccionadas ({selectedObs.length})</button>}<label className="select-all-observations"><input type="checkbox" checked={data.observaciones.every(obs=>selectedObs.includes(obs.id_observacion))} onChange={event=>setSelectedObs(event.target.checked?data.observaciones.map(obs=>obs.id_observacion):[])}/> Seleccionar todas</label></div>}</div>{data.observaciones?.length ? <ul className="observation-list">{data.observaciones.map(obs => <li key={obs.id_observacion}><input className="observation-check" type="checkbox" aria-label="Seleccionar observación" checked={selectedObs.includes(obs.id_observacion)} onChange={event=>setSelectedObs(current=>event.target.checked?[...current,obs.id_observacion]:current.filter(id=>id!==obs.id_observacion))}/><div><strong>{obs.act_nombre || 'Observación libre'}</strong><small>{new Date(obs.fecha).toLocaleString('es-AR')}</small><p>{obs.nota_cruda}</p></div><button className="icon-button danger-icon" onClick={() => removeObservation(obs.id_observacion)} aria-label="Eliminar observación"><Trash2 size={17}/></button></li>)}</ul> : <div className="empty-state"><ClipboardList size={28}/><strong>Todavía no hay observaciones</strong><p>Cuando registres una nota para este alumno, aparecerá acá.</p></div>}</section>
    <section className="students-panel report-panel"><div className="section-heading"><div><span className="eyebrow">BORRADOR CON IA</span><h2>Informe</h2><p>Revisá y ajustá el texto antes de descargarlo.</p></div>{data.informe && !editing && <div className="heading-actions"><button className="button-soft" onClick={() => setEditing(true)}>Editar informe</button><a className="button-primary" href={`/api/informe/${studentId}/pdf`}><ArrowUpRight size={16}/> Descargar PDF</a></div>}</div>{data.informe ? editing ? <><textarea className="report-editor" value={draft} onChange={event => setDraft(event.target.value)} aria-label="Editar informe"/><div className="heading-actions report-actions"><button className="button-soft" onClick={() => { setEditing(false); setDraft(data.informe.contenido_informe); }}>Cancelar</button><button className="button-primary" disabled={busy} onClick={save}>{busy ? 'Guardando…' : 'Guardar cambios'}</button></div></> : <article className="report-content">{data.informe.contenido_informe}</article> : <p className="quiet-empty">El informe aparecerá acá cuando lo generes.</p>}</section>
  </div>;
}

function Planning() {
  const location = useLocation();
  const requestedTab = new URLSearchParams(location.search).get('seccion');
  const [tab, setTab] = useState(['indicadores','unidades','areas'].includes(requestedTab) ? requestedTab : 'indicadores'); const [areas, setAreas] = useState([]); const [activities, setActivities] = useState([]); const [units, setUnits] = useState([]); const [error, setError] = useState(''); const [dialog, setDialog] = useState(null); const [busy, setBusy] = useState(false);
  async function load() { const [a, i, u] = await Promise.all([request('/api/areas'), request('/api/actividades'), request('/api/unidades')]); setAreas(a); setActivities(i); setUnits(u); }
  useEffect(() => { load().catch(err => setError(err.message)); }, []);
  async function save(event) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const edit = dialog?.item; let path, payload, method;
    if (tab === 'areas') { path = edit ? `/api/areas/${edit.id}` : '/api/areas'; method = edit ? 'PUT' : 'POST'; payload = { nombre: form.get('nombre') }; }
    else if (tab === 'unidades') { path = edit ? `/api/unidades/${edit.id_unidad}` : '/api/unidades'; method = edit ? 'PUT' : 'POST'; payload = { titulo: form.get('titulo'), contenido: form.get('contenido') }; }
    else if (dialog?.bulk) { path = '/api/actividades/multi'; method = 'POST'; const defaultArea=form.get('area'); const actividades=String(form.get('nombres')||'').split('\n').map(line=>line.trim()).filter(Boolean).map(line=>{const parts=line.split('|');return {nombre:parts[0].trim(),area:(parts[1]||defaultArea).trim()};});payload={actividades,id_unidad:form.get('id_unidad')||null}; }
    else { path = edit ? `/api/actividades/${edit.id_actividad}` : '/api/actividades'; method = edit ? 'PUT' : 'POST'; payload = { nombre: form.get('nombre'), area: form.get('area'), ...(edit ? {} : { fecha: new Date().toISOString().slice(0,10), id_unidad: form.get('id_unidad') || null }) }; }
    setBusy(true); setError(''); try { await mutate(path, method, payload); setDialog(null); await load(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function remove(item) { if (!window.confirm('¿Eliminar este elemento?')) return; const path = tab === 'areas' ? `/api/areas/${item.id}` : tab === 'unidades' ? `/api/unidades/${item.id_unidad}` : `/api/actividades/${item.id_actividad}`; try { await mutate(path, 'DELETE'); await load(); } catch (err) { setError(err.message); } }
  const tabs = [['indicadores','Indicadores','Qué vas a observar'],['unidades','Unidades','Cómo organizás propuestas'],['areas','Áreas','Tus campos de observación']];
  return <div className="planning-view"><section className="welcome-panel"><div><span className="eyebrow">TU ORGANIZACIÓN PEDAGÓGICA</span><h1>Planificación</h1><p>Organizá lo que observás y las propuestas que acompañan tu sala.</p></div></section><div className="planning-tabs" role="tablist">{tabs.map(([key,title,subtitle])=><button key={key} role="tab" aria-selected={tab===key} className={tab===key?'active':''} onClick={()=>setTab(key)}><strong>{title}</strong><span>{subtitle}</span></button>)}</div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <section className="students-panel planning-panel"><header className="section-heading"><div><span className="eyebrow">{tab === 'areas' ? 'PERSONALIZÁ TU SALA' : tab === 'unidades' ? 'TUS PROPUESTAS' : 'REGISTRO DE OBSERVACIÓN'}</span><h2>{tab === 'areas' ? 'Áreas' : tab === 'unidades' ? 'Unidades didácticas' : 'Indicadores'}</h2><p>{tab === 'areas' ? 'Creá solo las áreas que realmente usás.' : tab === 'unidades' ? 'Guardá proyectos o secuencias para consultarlos al registrar observaciones.' : 'Asociá observaciones con algo concreto que quieras seguir.'}</p></div><div className="planning-add-actions">{tab==='indicadores'&&<button className="button-soft" onClick={()=>setDialog({type:'create',bulk:true})}>Agregar varios</button>}<button className="button-primary" onClick={()=>setDialog({type:'create'})}><Plus size={16}/> Agregar {tab === 'areas' ? 'área' : tab === 'unidades' ? 'unidad' : 'indicador'}</button></div></header>
      <div className="planning-list">{tab === 'areas' ? areas.map(item=><PlanningRow key={item.id} title={item.nombre} meta="Área" onEdit={()=>setDialog({type:'edit',item})} onDelete={()=>remove(item)}/>) : tab === 'unidades' ? units.map(item=><PlanningRow key={item.id_unidad} title={item.titulo} meta={item.contenido || 'Sin descripción'} onEdit={()=>setDialog({type:'edit',item})} onDelete={()=>remove(item)}/>) : activities.map(item=><PlanningRow key={item.id_actividad} title={item.nombre} meta={`${item.area || 'Sin área'}${item.unidad_titulo ? ` · ${item.unidad_titulo}` : ''}`} onEdit={()=>setDialog({type:'edit',item})} onDelete={()=>remove(item)}/>)}</div>
      {((tab==='areas'&&!areas.length)||(tab==='unidades'&&!units.length)||(tab==='indicadores'&&!activities.length)) && <div className="empty-state"><BookOpenCheck size={28}/><strong>{tab==='areas'?'Todavía no agregaste áreas':tab==='unidades'?'Todavía no hay unidades':'Todavía no hay indicadores'}</strong><p>Agregá tu primer elemento cuando quieras; podés cambiarlo más adelante.</p><button className="button-soft" onClick={()=>setDialog({type:'create'})}>Crear ahora</button></div>}
    </section>
    <Dialog open={!!dialog} close={()=>setDialog(null)} title={`${dialog?.type==='edit'?'Editar':'Agregar'} ${tab==='areas'?'área':tab==='unidades'?'unidad didáctica':dialog?.bulk?'varios indicadores':'indicador'}`}>
      <form className="modal-form" onSubmit={save}>{tab==='areas'?<label>Nombre del área<input autoFocus name="nombre" defaultValue={dialog?.item?.nombre||''} required maxLength="80" placeholder="Por ejemplo: Matemática"/></label>:tab==='unidades'?<><label>Nombre<input autoFocus name="titulo" defaultValue={dialog?.item?.titulo||''} required placeholder="Por ejemplo: El barrio"/></label><label>Descripción<textarea name="contenido" rows="4" defaultValue={dialog?.item?.contenido||''} placeholder="Propósito, contenidos o notas para vos"/></label></>:dialog?.bulk?<><label>Indicadores<textarea autoFocus name="nombres" rows="6" required placeholder={'Reconoce formas geométricas\nExplica cómo resolvió una actividad | Matemática'}/><small>Uno por línea. Podés agregar “| Nombre del área” al final para indicar un área distinta.</small></label><label>Área predeterminada<select name="area" required defaultValue={areas[0]?.nombre||''}><option value="" disabled>Elegí un área</option>{areas.map(area=><option key={area.id} value={area.nombre}>{area.nombre}</option>)}</select></label><label>Unidad didáctica (opcional)<select name="id_unidad" defaultValue=""><option value="">Sin unidad</option>{units.map(unit=><option key={unit.id_unidad} value={unit.id_unidad}>{unit.titulo}</option>)}</select></label></>:<><label>Indicador<textarea autoFocus name="nombre" rows="3" defaultValue={dialog?.item?.nombre||''} required placeholder="¿Qué querés observar?"/></label><label>Área<select name="area" required defaultValue={dialog?.item?.area||areas[0]?.nombre||''}><option value="" disabled>Elegí un área</option>{areas.map(area=><option key={area.id} value={area.nombre}>{area.nombre}</option>)}</select>{!areas.length&&<small>Primero creá un área en la pestaña Áreas.</small>}</label>{!dialog?.item&&<label>Unidad didáctica (opcional)<select name="id_unidad" defaultValue=""><option value="">Sin unidad</option>{units.map(unit=><option key={unit.id_unidad} value={unit.id_unidad}>{unit.titulo}</option>)}</select></label>}</>}
        <button className="button-primary" disabled={busy||tab==='indicadores'&&!areas.length}>{busy?'Guardando…':'Guardar'}</button></form>
    </Dialog>
  </div>;
}

function PlanningRow({title,meta,onEdit,onDelete}) { return <article className="planning-row"><div><strong>{title}</strong><small>{meta}</small></div><div className="planning-row-actions"><button className="button-soft" onClick={onEdit}>Editar</button><button className="icon-button danger-icon" aria-label={`Eliminar ${title}`} onClick={onDelete}><Trash2 size={16}/></button></div></article>; }

function Profile({ user, onUser }) {
  const [rooms,setRooms]=useState([]); const [name,setName]=useState(user.nombre||''); const [message,setMessage]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [size,setSize]=useState(localStorage.getItem('infia-tamano-texto')||'normal'); const [dialog,setDialog]=useState(null);
  async function loadRooms(){setRooms(await request('/api/salas'));}
  useEffect(()=>{loadRooms().catch(err=>setError(err.message));},[]);
  async function saveName(e){e.preventDefault();setBusy(true);setError('');setMessage('');try{await mutate('/api/usuario/perfil','PUT',{nombre:name});onUser({...user,nombre:name});setMessage('Nombre actualizado.');}catch(err){setError(err.message);}finally{setBusy(false);}}
  async function changePhoto(file){if(!file)return;if(file.size>15*1024*1024){setError('Elegí una imagen menor a 15 MB.');return;}setBusy(true);setError('');try{const image=await createImageBitmap(file);const canvas=document.createElement('canvas');let scale=Math.min(1,480/Math.max(image.width,image.height));canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);let blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/webp',.8));if(!blob||blob.type!=='image/webp')blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.8));if(blob.size>180*1024)throw new Error('La foto quedó muy pesada. Probá con otra imagen.');const avatar_data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('No pudimos leer la imagen.'));reader.readAsDataURL(blob);});await mutate('/api/usuario/avatar','PUT',{avatar_data});onUser({...user,avatar_data});setMessage('Foto actualizada.');}catch(err){setError(err.message);}finally{setBusy(false);}}
  async function saveRoom(e){e.preventDefault();const form=new FormData(e.currentTarget);setBusy(true);setError('');try{if(dialog?.room)await mutate(`/api/salas/${dialog.room.id_sala}`,'PUT',{nombre:form.get('nombre'),sala:form.get('sala'),turno:form.get('turno')});else await mutate('/api/salas','POST',{nombre:form.get('nombre'),sala:form.get('sala'),turno:form.get('turno')});setDialog(null);await loadRooms();}catch(err){setError(err.message);}finally{setBusy(false);}}
  async function removeRoom(room){if(!window.confirm(`¿Eliminar la sala “${room.nombre}”? Solo se puede borrar si está vacía.`))return;try{await mutate(`/api/salas/${room.id_sala}`,'DELETE');await loadRooms();}catch(err){setError(err.message);}}
  function setTextSize(value){setSize(value);localStorage.setItem('infia-tamano-texto',value);document.documentElement.dataset.textSize=value;document.documentElement.classList.toggle('texto-grande',value==='grande');}
  async function removePhoto(){setBusy(true);try{await mutate('/api/usuario/avatar','PUT',{avatar_data:null});onUser({...user,avatar_data:null});setMessage('Foto quitada.');}catch(err){setError(err.message);}finally{setBusy(false);}}
  return <div className="profile-view"><section className="welcome-panel profile-hero"><div className="profile-avatar-wrap"><div className="profile-avatar">{user.avatar_data?<img src={user.avatar_data} alt="Foto de perfil"/>:user.nombre?.[0]?.toUpperCase()}</div><label className="button-soft photo-select">Cambiar foto<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>changePhoto(e.target.files?.[0])}/></label>{user.avatar_data&&<button className="remove-photo-button" disabled={busy} onClick={removePhoto}>Quitar foto</button>}</div><div><span className="eyebrow">TU PERFIL</span><h1>{user.nombre}</h1><p>{user.email}</p><small>Personalizá tu cuenta y administrá tus salas.</small></div></section>
    {error&&<p className="inline-error" role="alert">{error}</p>}{message&&<p className="inline-success" role="status">{message}</p>}
    <section className="students-panel"><div className="section-heading"><div><span className="eyebrow">DATOS PERSONALES</span><h2>Tu información</h2></div></div><form className="profile-form" onSubmit={saveName}><label>Nombre completo<input value={name} onChange={e=>setName(e.target.value)} required maxLength="100"/></label><label>Correo electrónico<input value={user.email} disabled/><small>El correo de acceso no se puede cambiar desde la app.</small></label><button className="button-primary" disabled={busy}>{busy?'Guardando…':'Guardar cambios'}</button></form></section>
    <section className="students-panel"><div className="section-heading"><div><span className="eyebrow">AULAS INDEPENDIENTES</span><h2>Mis salas</h2><p>Alumnos, observaciones e informes se mantienen separados en cada sala.</p></div><button className="button-primary" onClick={()=>setDialog({})}><Plus size={16}/> Agregar sala</button></div><div className="planning-list">{rooms.map(room=><article className="planning-row" key={room.id_sala}><div><strong>{room.nombre}{room.activa&&<span className="active-tag">Sala activa</span>}</strong><small>{room.sala} · Turno {room.turno}</small></div><div className="planning-row-actions">{!room.activa&&<button className="button-soft" onClick={async()=>{try{await mutate('/api/salas/activar','POST',{id_sala:room.id_sala});window.location.reload();}catch(err){setError(err.message);}}}>Usar esta sala</button>}<button className="button-soft" onClick={()=>setDialog({room})}>Editar</button><button className="icon-button danger-icon" onClick={()=>removeRoom(room)} aria-label="Eliminar sala"><Trash2 size={16}/></button></div></article>)}</div></section>
    <section className="students-panel"><div className="section-heading"><div><span className="eyebrow">LECTURA</span><h2>Tamaño del texto</h2><p>Elegí el tamaño que te resulte más cómodo.</p></div></div><div className="text-size-options"><button className={size==='normal'?'active':''} onClick={()=>setTextSize('normal')}><span>Aa</span>Estándar</button><button className={size==='grande'?'active':''} onClick={()=>setTextSize('grande')}><span>Aa</span>Grande</button></div></section>
    <section className="students-panel"><div className="section-heading"><div><span className="eyebrow">CUENTA Y SEGURIDAD</span><h2>Configuración</h2></div></div><div className="settings-links"><Link to="/dashboard?tutorial=1">Repetir el recorrido de bienvenida <ArrowUpRight size={17}/></Link><Link to="/suscripcion">Plan y pagos <ArrowUpRight size={17}/></Link><Link to="/config">Contraseña <ArrowUpRight size={17}/></Link><Link to="/cuenta">Privacidad y cuenta <ArrowUpRight size={17}/></Link>{user.es_admin&&<Link to="/admin">Administración <ArrowUpRight size={17}/></Link>}</div></section>
    <Dialog open={!!dialog} close={()=>setDialog(null)} title={dialog?.room?'Editar sala':'Agregar una sala'}><form className="modal-form" onSubmit={saveRoom}><label>Nombre para identificarla<input autoFocus name="nombre" required defaultValue={dialog?.room?.nombre||''} placeholder="Por ejemplo: Sala de 4 · Mañana"/></label><label>Grado / sección<input name="sala" required defaultValue={dialog?.room?.sala||''} placeholder="4 Años A"/></label><label>Turno<select name="turno" defaultValue={dialog?.room?.turno||'Mañana'}><option>Mañana</option><option>Tarde</option></select></label><button className="button-primary" disabled={busy}>{busy?'Guardando…':'Guardar sala'}</button></form></Dialog>
  </div>;
}

function PasswordSettings(){const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);async function save(e){e.preventDefault();const form=e.currentTarget;const fields=new FormData(form);setBusy(true);setError('');setMessage('');try{await mutate('/api/usuario/contraseña','PUT',{actual:fields.get('actual'),nueva:fields.get('nueva')});form.reset();setMessage('Contraseña actualizada.');}catch(err){setError(err.message);}finally{setBusy(false);}}return <div className="settings-view"><Link className="back-link" to="/perfil">← Volver al perfil</Link><section className="students-panel"><span className="eyebrow">SEGURIDAD</span><h1 className="settings-title">Cambiar contraseña</h1><p className="settings-copy">Elegí una clave segura para proteger tu cuenta.</p>{error&&<p className="inline-error" role="alert">{error}</p>}{message&&<p className="inline-success" role="status">{message}</p>}<form className="profile-form" onSubmit={save}><label>Contraseña actual<input name="actual" type="password" autoComplete="current-password" required/></label><label>Nueva contraseña<input name="nueva" type="password" autoComplete="new-password" minLength="8" required/><small>Debe tener 8 caracteres, una mayúscula y un número.</small></label><button className="button-primary" disabled={busy}>{busy?'Actualizando…':'Actualizar contraseña'}</button></form></section></div>}

function AccountSettings({user}){const [error,setError]=useState(''),[pending,setPending]=useState(!!user.baja_solicitada_en),[busy,setBusy]=useState(false),[expanded,setExpanded]=useState(!!user.baja_solicitada_en);async function remove(e){e.preventDefault();const form=new FormData(e.currentTarget);setBusy(true);setError('');try{await mutate('/api/usuario/baja','POST',{motivo:form.get('motivo')});setPending(true);setExpanded(true);}catch(err){setError(err.message);}finally{setBusy(false);}}async function cancel(){if(!window.confirm('¿Querés cancelar la solicitud y conservar tu cuenta?'))return;setBusy(true);try{await mutate('/api/usuario/baja/cancelar','POST',{});setPending(false);}catch(err){setError(err.message);}finally{setBusy(false);}}return <div className="settings-view"><Link className="back-link" to="/perfil">← Volver al perfil</Link><section className="students-panel"><span className="eyebrow">PRIVACIDAD</span><h1 className="settings-title">Privacidad y cuenta</h1><p className="settings-copy">Consultá cómo se administran tus datos y controlá tu cuenta.</p><div className="settings-links legal-links"><Link to="/privacidad">Política de privacidad <ArrowUpRight size={17}/></Link><Link to="/terminos">Términos de uso <ArrowUpRight size={17}/></Link></div></section><section className="account-delete-card"><div><span className="eyebrow">OPCIÓN PERMANENTE</span><h2>Eliminar cuenta</h2><p>La cuenta se suspende al solicitarlo. Tenés 7 días para recuperarla; después se eliminan los datos asociados.</p></div><button className="button-danger" onClick={()=>setExpanded(!expanded)}>{pending?'Ver estado':'Eliminar cuenta'}</button>{expanded&&<div className="account-delete-panel">{pending?<><p>La eliminación está programada. Podés cancelar la solicitud mientras siga pendiente.</p><button className="button-soft" disabled={busy} onClick={cancel}>Conservar mi cuenta</button></>:<form className="modal-form" onSubmit={remove}><label>Si querés, contanos el motivo <small>(opcional)</small><textarea name="motivo" rows="3" maxLength="1000" placeholder="Tu comentario nos ayuda a mejorar Infia"/></label><label className="consent-row"><input type="checkbox" required/> Entiendo que mi cuenta se suspenderá ahora y que se eliminará en 7 días si no la recupero.</label>{error&&<p className="inline-error" role="alert">{error}</p>}<button className="button-danger" disabled={busy}>{busy?'Procesando…':'Confirmar eliminación'}</button></form>}</div>}</section></div>}

function Subscription({user}) {
  const [status,setStatus]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{request('/api/suscripcion/estado').then(setStatus).catch(err=>setError(err.message));},[]);
  const type=status?.tipo_plan||user.tipo_plan;
  const planTitle=status?.gratis?'Acceso gratuito':type==='anual'?'Plan anual':type==='mensual'?'Plan mensual':status?.plan==='trial'?'Período de prueba':'Sin plan activo';
  const amount=status?.monto_plan||user.monto_plan;
  const price=amount?new Intl.NumberFormat('es-AR',{style:'currency',currency:'ARS',maximumFractionDigits:0}).format(amount):null;
  const money=value=>new Intl.NumberFormat('es-AR',{style:'currency',currency:'ARS',maximumFractionDigits:0}).format(value||0);
  async function subscribe(plan){setBusy(true);setError('');try{const result=await mutate('/api/suscripcion/crear','POST',{tipo:plan});window.location.assign(result.init_point);}catch(err){setError(err.message);setBusy(false);}}
  return <div className="settings-view"><Link className="back-link" to="/perfil">← Volver al perfil</Link><section className="welcome-panel"><div><span className="eyebrow">TU SUSCRIPCIÓN</span><h1>Plan y pagos</h1><p>Revisá qué plan tenés y la información de tu próximo pago.</p></div></section>
    {error&&<p className="inline-error" role="alert">{error}</p>}
    <section className="students-panel plan-summary"><div><span className="eyebrow">PLAN CONTRATADO</span><h2>{planTitle}</h2><p>{status?.gratis?'Tu cuenta está exenta de pago.':status?.plan==='trial'?`${status.dias} días restantes en el período de prueba.`:user.plan==='pago'?'Acceso completo a las herramientas pedagógicas de Infia.':'Acceso a las herramientas pedagógicas de Infia.'}</p></div><div className="plan-facts"><div><small>Estado</small><strong>{status?.estado||'Consultando…'}</strong></div><div><small>Precio del plan</small><strong>{status?.gratis?'Sin cargo':price||'Sin cargo'}</strong></div><div><small>Vencimiento</small><strong>{status?.vencimiento||'Sin fecha registrada'}</strong></div><div><small>Renovación</small><strong>{type==='anual'?'Anual':type==='mensual'?'Mensual':'No configurada'}</strong></div></div></section>
    {!user.es_admin&&<section className="students-panel"><h2 className="settings-title">Elegir o renovar un plan</h2><p className="settings-copy">La confirmación del pago se realiza en Mercado Pago.</p><div className="plan-options"><article><strong>Mensual</strong><div className="plan-price">{money(status?.precio_mensual)}<small> / mes</small></div><p>Un pago cada mes para mantener tu acceso.</p><button className="button-soft" disabled={busy} onClick={()=>subscribe('mensual')}>Continuar con mensual</button></article><article className="annual-plan"><strong>Anual</strong><div className="plan-price">{money(status?.precio_anual)}<small> / año</small></div><p>Un pago anual, con un costo mensual equivalente menor.</p><button className="button-primary" disabled={busy} onClick={()=>subscribe('anual')}>Continuar con anual</button></article></div></section>}
  </div>;
}


function AdminPanel(){const [data,setData]=useState(null),[tab,setTab]=useState('resumen'),[threads,setThreads]=useState([]),[chat,setChat]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);async function load(){const result=await request('/api/admin/panel');setData(result);}useEffect(()=>{load().catch(err=>setError(err.message));},[]);async function openThread(id){setTab('soporte');try{setChat(await request(`/api/admin/soporte/${id}`));}catch(err){setError(err.message);}}useEffect(()=>{if(tab==='soporte')request('/api/admin/soporte').then(result=>setThreads(result.hilos||[])).catch(err=>setError(err.message));},[tab]);async function action(id,type){if(type==='reactivar'&&!window.confirm('¿Reactivar esta cuenta por 30 días?'))return;setBusy(true);setError('');try{const result=await mutate(`/api/admin/usuario/${id}/${type}`,'POST',type==='reactivar'?{dias:30}:{});if(type==='reset'&&result.mensaje)window.alert(result.mensaje);await load();}catch(err){setError(err.message);}finally{setBusy(false);}}async function sendMessage(e){e.preventDefault();const form=e.currentTarget;const value=new FormData(form).get('texto');setBusy(true);try{await mutate(`/api/admin/soporte/${chat.id_soporte}/mensaje`,'POST',{texto:value});form.reset();setChat(await request(`/api/admin/soporte/${chat.id_soporte}`));}catch(err){setError(err.message);}finally{setBusy(false);}}async function broadcast(e){e.preventDefault();const form=e.currentTarget;setBusy(true);try{const result=await mutate('/api/admin/comunicado','POST',{texto:new FormData(form).get('texto')});window.alert(`Comunicado enviado a ${result.total} cuentas.`);form.reset();}catch(err){setError(err.message);}finally{setBusy(false);}}if(!data)return <div className="loading-state"><LoaderCircle className="spin"/>{error||'Cargando panel…'}</div>;const tabs=['resumen','usuarios','movimientos','soporte','comunicados'];return <div className="admin-view"><section className="welcome-panel"><div><span className="eyebrow">ADMINISTRACIÓN</span><h1>Panel de Infia</h1><p>Usuarios, pagos y conversaciones de soporte.</p></div></section><nav className="planning-tabs admin-tabs">{tabs.map(name=><button key={name} className={tab===name?'active':''} onClick={()=>setTab(name)}><strong>{name[0].toUpperCase()+name.slice(1)}</strong></button>)}</nav>{error&&<p className="inline-error">{error}</p>}{tab==='resumen'&&<><div className="stats-grid">{[['Pagando',data.resumen.activos],['En prueba',data.resumen.trials],['Vencidas',data.resumen.vencidas],['Ingresos del mes',data.resumen.ingresos_mes]].map(([label,value])=><article className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div><section className="students-panel"><h2>Próximos vencimientos</h2>{data.proximos_vencer.length?data.proximos_vencer.map((v,i)=><PlanningRow key={i} title={v.nombre} meta={`${v.vence} · ${v.dias_txt}`} onEdit={()=>{}} onDelete={()=>{}}/>):<p className="quiet-empty">Ninguna cuenta vence en los próximos 7 días.</p>}</section></>}{tab==='usuarios'&&<section className="students-panel"><div className="section-heading"><div><h2>Usuarios</h2><p>Reactivá una cuenta o enviá un enlace para cambiar contraseña.</p></div></div><div className="admin-table-wrap"><table><thead><tr><th>Nombre</th><th>Email</th><th>Sala</th><th>Estado</th><th>Vence</th><th>Acciones</th></tr></thead><tbody>{data.usuarios.map(user=><tr key={user.id}><td>{user.nombre}</td><td>{user.email}</td><td>{user.sala}</td><td><span className={`status-tag ${user.estado}`}>{user.estado}</span></td><td>{user.vencimiento||'—'}</td><td><div className="admin-actions"><button className="button-soft" disabled={busy} onClick={()=>action(user.id,'reactivar')}>Reactivar</button><button className="button-soft" disabled={busy} onClick={()=>action(user.id,'reset')}>Reset</button></div></td></tr>)}</tbody></table></div></section>}{tab==='movimientos'&&<section className="students-panel"><h2>Movimientos</h2>{data.pagos.length?<div className="admin-table-wrap"><table><thead><tr><th>Fecha</th><th>Docente</th><th>Plan</th><th>Monto</th></tr></thead><tbody>{data.pagos.map(p=><tr key={p.id_pago}><td>{p.fecha}</td><td>{p.nombre}<small>{p.email}</small></td><td>{p.tipo==='anual'?'Anual':'Mensual'}</td><td>{new Intl.NumberFormat('es-AR',{style:'currency',currency:'ARS',maximumFractionDigits:0}).format(p.monto)}</td></tr>)}</tbody></table></div>:<p className="quiet-empty">Todavía no hay movimientos.</p>}</section>}{tab==='soporte'&&<section className="students-panel"><h2>Soporte</h2><div className="admin-support-layout"><div className="admin-thread-list">{threads.map(thread=><button key={thread.id_soporte} onClick={()=>openThread(thread.id_soporte)}><strong>{thread.nombre||thread.email||`Consulta ${thread.id_soporte}`}</strong><small>{thread.ultima_fecha||'Sin mensajes nuevos'}</small></button>)}</div>{chat?<div className="admin-chat"><div className="admin-chat-messages">{chat.mensajes.map(message=><article className={`support-message ${message.id_usuario===chat.mi_id?'mine':''}`} key={message.id}><p>{message.texto}</p><small>{message.fecha}</small></article>)}</div><form className="support-compose" onSubmit={sendMessage}><input name="texto" required placeholder="Responder…"/><button aria-label="Enviar respuesta"><Send size={17}/></button></form></div>:<p className="quiet-empty">Elegí una conversación para responder.</p>}</div></section>}{tab==='comunicados'&&<section className="students-panel"><h2>Enviar comunicado</h2><p className="settings-copy">El mensaje llegará a las cuentas de las docentes.</p><form className="modal-form" onSubmit={broadcast}><textarea name="texto" rows="5" required maxLength="2000" placeholder="Escribí el comunicado…"/><button className="button-primary" disabled={busy}>{busy?'Enviando…':'Enviar a todas las cuentas'}</button></form></section>}</div>}

export default function App() {
  const location=useLocation();
  const publicPaths=['/login','/registro','/forgot'];
  const [user, setUser] = useState(null);
  const [state, setState] = useState('loading');

  useEffect(() => {
    const size = localStorage.getItem('infia-tamano-texto') || 'normal';
    document.documentElement.dataset.textSize = size;
    document.documentElement.classList.toggle('texto-grande', size === 'grande');
  }, []);

  useEffect(() => {
    if(publicPaths.includes(location.pathname)||location.pathname.startsWith('/reset/'))return;
    request('/api/me').then(profile => { setUser(profile); setState('ready'); })
      .catch(err => { if (err.message === 'session') { window.location.assign(`${window.location.pathname.startsWith('/react-preview') ? '/react-preview' : ''}/login`); return; } setState('error'); });
  }, [location.pathname]);

  if(publicPaths.includes(location.pathname)||location.pathname.startsWith('/reset/'))return <AuthPage/>;

  if (state === 'loading') return <div className="boot-screen"><LoaderCircle className="spin" size={26} /><span>Abriendo Infia…</span></div>;
  if (state === 'error') return <div className="boot-screen">No pudimos abrir tu cuenta. <a href="/login">Volver al acceso</a></div>;
  return <AppFrame user={user}>
    <Routes>
      <Route path="/dashboard" element={<Dashboard user={user} onUser={setUser} />} />
      <Route path="/planificacion" element={<Planning />} />
      <Route path="/perfil" element={<Profile user={user} onUser={setUser} />} />
      <Route path="/config" element={<PasswordSettings />} />
      <Route path="/cuenta" element={<AccountSettings user={user} />} />
      <Route path="/suscripcion" element={<Subscription user={user} />} />
      <Route path="/salas" element={<Profile user={user} onUser={setUser} />} />
      <Route path="/admin" element={user.es_admin?<AdminPanel/>:<Navigate to="/dashboard" replace/>} />
      <Route path="/alumno/:studentId" element={<StudentDetail />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  </AppFrame>;
}
