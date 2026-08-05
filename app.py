import os
import json
import functools
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, session, redirect, render_template, send_from_directory

# ─── Rutas base ───────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
    template_folder=os.path.join(ROOT, 'templates'),
    static_folder=os.path.join(ROOT, 'static'))

app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.permanent_session_lifetime = 86400 * 30  # 30 días
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if not os.environ.get('FLASK_DEBUG'):
    app.config['SESSION_COOKIE_SECURE'] = True
AUDIO_DIR = os.path.join(app.static_folder, 'audios')
os.makedirs(AUDIO_DIR, exist_ok=True)

# ─── Seguridad: rate limiting simple ────
from collections import defaultdict
from datetime import datetime, timedelta
import re
_login_intentos = defaultdict(list)
_reset_intentos = defaultdict(list)
_MAX_INTENTOS = 5
_MAX_RESETS = 3
_VENTANA_MINUTOS = 15

def revisar_rate_limit(ip):
    ahora = datetime.now()
    intentos = [t for t in _login_intentos[ip] if ahora - t < timedelta(minutes=_VENTANA_MINUTOS)]
    _login_intentos[ip] = intentos
    if len(intentos) >= _MAX_INTENTOS:
        return False
    _login_intentos[ip].append(ahora)
    return True

def revisar_rate_limit_reset(ip):
    ahora = datetime.now()
    intentos = [t for t in _reset_intentos[ip] if ahora - t < timedelta(minutes=_VENTANA_MINUTOS)]
    _reset_intentos[ip] = intentos
    if len(intentos) >= _MAX_RESETS:
        return False
    _reset_intentos[ip].append(ahora)
    return True

def validar_contraseña(pw):
    """Valida que la contraseña cumpla la política de seguridad."""
    errores = []
    if len(pw) < 8:
        errores.append('al menos 8 caracteres')
    if not re.search(r'[A-Z]', pw):
        errores.append('al menos una mayúscula')
    if not re.search(r'[0-9]', pw):
        errores.append('al menos un número')
    if re.search(r'(.)\1{2,}', pw):
        errores.append('no repetir el mismo carácter 3 veces seguidas')
    return errores

# ─── Security headers ────────────────────
@app.after_request
def seguridad_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['X-XSS-Protection'] = '1; mode=block'
    resp.headers['Referrer-Policy'] = 'same-origin'
    if not os.environ.get('FLASK_DEBUG'):
        resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    csp = "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self' https://cdn.jsdelivr.net; media-src 'self' blob:; font-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:"
    resp.headers['Content-Security-Policy'] = csp
    return resp

# ─── Imports del backend ─────────────────
from src.db import (
    crear_usuario, obtener_usuario_por_email, obtener_usuario_por_id,
    registrar_alumno, obtener_alumnos, eliminar_alumno,
    crear_actividad, crear_actividades_multi, obtener_actividades_dia,
    eliminar_actividad, actualizar_actividad,
    guardar_observacion, eliminar_observacion, eliminar_observaciones_multi,
    obtener_observaciones_alumno, obtener_todas_observaciones_dia,
    guardar_informe, obtener_informe_reciente, actualizar_informe,
    renombrar_area, obtener_areas_usuario, eliminar_area, crear_area,
    crear_unidad, obtener_unidades, obtener_unidad, actualizar_unidad, eliminar_unidad,
    obtener_stats, guardar_reset_token,
    obtener_suscripcion,
    obtener_todos_usuarios, obtener_pagos, obtener_ingresos_mes,
    obtener_o_crear_soporte, enviar_mensaje, obtener_mensajes_soporte,
    marcar_mensajes_leidos, contar_no_leidos_usuario, listar_soportes_admin,
    reactivar_usuario, enviar_comunicado,
)
from src.suscripcion import (
    estado_cuenta, dias_restantes, crear_preapproval,
    suscripcion_activa, procesar_notificacion, es_gratis,
)
from src.transcriptor import transcribir_audio
from src.generar_informe import formatear_informe_ia
from src.db import inicializar_bd

# Inicializar base de datos al arrancar
inicializar_bd()

# ─── Helpers ─────────────────────────────
AREAS_DEFAULT = [
    {'id': 0, 'nombre': 'Identidad y Convivencia'}, {'id': 0, 'nombre': 'Lenguaje y Literatura'},
    {'id': 0, 'nombre': 'Matemáticas'}, {'id': 0, 'nombre': 'Ciencias Sociales, Ciencias Naturales y Tecnología'},
]

def areas_para(user_id):
    areas = obtener_areas_usuario(user_id)
    return areas or AREAS_DEFAULT

def hash_pass(pw):
    return generate_password_hash(pw)

def login_required(f):
    @functools.wraps(f)
    def wrap(*a, **kw):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify(error='No autorizado'), 401
            return redirect('/login')
        return f(*a, **kw)
    return wrap

# ─── Inicialización perezosa de BD ──────
_bd_inicializada = False

@app.before_request
def asegurar_bd():
    global _bd_inicializada
    if not _bd_inicializada:
        try:
            inicializar_bd()
            _bd_inicializada = True
        except Exception:
            pass  # Reintenta en el próximo request

@app.before_request
def verificar_suscripcion():
    if not suscripcion_activa():
        return
    if 'user_id' not in session:
        return
    if request.path in ('/suscripcion', '/api/logout') or request.path.startswith('/api/suscripcion'):
        return
    if request.path.startswith('/soporte') or request.path.startswith('/api/soporte'):
        return
    if request.path.startswith('/admin') or request.path.startswith('/api/admin'):
        return
    try:
        s = obtener_suscripcion(session['user_id'])
    except Exception:
        return
    if not s:
        return
    if es_gratis(s.get('email')):
        return
    if estado_cuenta(s) == 'vencida':
        if request.is_json or request.path.startswith('/api/'):
            return jsonify(error='Tu suscripción venció. Renová para seguir usando Infia.'), 402
        return redirect('/suscripcion')

@app.before_request
def redirigir_admin_a_panel():
    if not os.environ.get('ADMIN_EMAIL'):
        return
    if 'user_id' not in session:
        return
    if request.path.startswith('/static'):
        return
    if es_admin():
        if request.path.startswith('/admin') or request.path.startswith('/api/'):
            return
        return redirect('/admin')

# ─── PÁGINAS ─────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        if es_admin():
            return redirect('/admin')
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/registro')
def registro_page():
    return render_template('registro.html', requiere_codigo=bool(os.environ.get('CODIGO_INVITACION')))

@app.route('/dashboard')
@login_required
def dashboard_page():
    user = obtener_usuario_por_id(session['user_id'])
    return render_template('dashboard.html', user=user, areas=areas_para(session['user_id']))

@app.route('/actividades')
@login_required
def actividades_page():
    user = obtener_usuario_por_id(session['user_id'])
    unidades = obtener_unidades(session['user_id'])
    return render_template('actividades.html', user=user, areas=areas_para(session['user_id']), unidades=unidades)

@app.route('/unidades')
@login_required
def unidades_page():
    user = obtener_usuario_por_id(session['user_id'])
    return render_template('unidades.html', user=user)

@app.route('/areas')
@login_required
def areas_page():
    user = obtener_usuario_por_id(session['user_id'])
    return render_template('areas.html', user=user)

@app.route('/alumno/<int:id_alumno>')
@login_required
def alumno_page(id_alumno):
    from src.db import obtener_alumnos
    alumnos = obtener_alumnos(session['user_id'])
    alumno = next((a for a in alumnos if a['id_alumno'] == id_alumno), None)
    if not alumno:
        return redirect('/dashboard')
    user = obtener_usuario_por_id(session['user_id'])
    return render_template('alumno.html', alumno=alumno, user=user)

# ─── SUSCRIPCIÓN ─────────────────────────

def _fmt_fecha(v):
    if hasattr(v, 'strftime'):
        return v.strftime('%d/%m/%Y')
    return ''

@app.route('/suscripcion')
@login_required
def suscripcion_page():
    user = obtener_usuario_por_id(session['user_id'])
    s = obtener_suscripcion(session['user_id'])
    estado = estado_cuenta(s)
    gratis = es_gratis(user.get('email'))
    return render_template('suscripcion.html', user=user, estado=estado,
                           gratis=gratis,
                           dias=dias_restantes(s),
                           vencimiento=_fmt_fecha(s.get('fecha_vencimiento')) if s else '')

@app.route('/api/suscripcion/crear', methods=['POST'])
@login_required
def api_suscripcion_crear():
    data = request.json or {}
    tipo = data.get('tipo') or 'mensual'
    if tipo not in ('mensual', 'anual'):
        return jsonify(error='Tipo de plan inválido'), 400
    user = obtener_usuario_por_id(session['user_id'])
    if es_gratis(user.get('email')):
        return jsonify(error='Tu cuenta está exenta de pago'), 403
    try:
        mp_id, init_point = crear_preapproval(user, tipo)
    except Exception as e:
        return jsonify(error='Error al crear el pago: ' + str(e)), 500
    if not init_point:
        return jsonify(error='No se pudo iniciar el pago'), 500
    return jsonify(ok=True, init_point=init_point)

@app.route('/api/suscripcion/estado', methods=['GET'])
@login_required
def api_suscripcion_estado():
    s = obtener_suscripcion(session['user_id'])
    estado = estado_cuenta(s)
    if es_gratis(s.get('email')):
        estado = 'pago'
    return jsonify(estado=estado, dias=dias_restantes(s),
                   vencimiento=_fmt_fecha(s.get('fecha_vencimiento')) if s else '')

@app.route('/webhook/mercadopago', methods=['POST', 'GET'])
def webhook_mercadopago():
    secret = os.environ.get('MP_WEBHOOK_SECRET', '')
    if request.args.get('secret') != secret:
        return jsonify(error='no autorizado'), 403
    tipo = request.args.get('type') or 'preapproval'
    mp_id = request.args.get('data.id')
    if not mp_id:
        try:
            j = request.json or {}
            mp_id = j.get('data', {}).get('id')
            tipo = j.get('type') or tipo
        except Exception:
            mp_id = None
    if not mp_id:
        return jsonify(ok=True)
    try:
        procesar_notificacion(mp_id, tipo)
    except Exception:
        pass
    return jsonify(ok=True)

# ─── ADMIN ────────────────────────────────

def es_admin():
    if 'user_id' not in session:
        return False
    admin_email = os.environ.get('ADMIN_EMAIL', '')
    if not admin_email:
        return False
    user = obtener_usuario_por_id(session['user_id'])
    return bool(user and (user.get('email') or '').lower() == admin_email.lower())

def _fmt_monto(n):
    try:
        return f'${int(n):,}'.replace(',', '.')
    except Exception:
        return f'${n}'

@app.route('/admin')
@login_required
def admin_page():
    if not es_admin():
        return redirect('/dashboard')
    usuarios = obtener_todos_usuarios()
    pagos = obtener_pagos()
    ingresos_mes = obtener_ingresos_mes()
    filas = []
    for u in usuarios:
        estado = estado_cuenta(u)
        if es_gratis(u.get('email')):
            estado = 'gratis'
        filas.append({
            'id': u['id_usuario'],
            'nombre': u['nombre'],
            'email': u['email'],
            'sala': u['sala'],
            'estado': estado,
            'registro': _fmt_fecha(u.get('fecha_registro')),
            'vencimiento': _fmt_fecha(u.get('fecha_vencimiento')),
        })
    activos = sum(1 for f in filas if f['estado'] in ('pago', 'gratis'))
    trials = sum(1 for f in filas if f['estado'] == 'trial')
    vencidas = sum(1 for f in filas if f['estado'] == 'vencida')
    return render_template('admin.html', filas=filas, pagos=pagos,
                           ingresos_mes=_fmt_monto(ingresos_mes),
                           activos=activos, trials=trials, vencidas=vencidas,
                           admin_id=session['user_id'])

# ─── PÁGINAS Y API: SOPORTE ──────────────

def _formatear_mensajes(mensajes):
    res = []
    for m in mensajes:
        f = m['fecha']
        try:
            fecha_txt = f.strftime('%d/%m %H:%M') if hasattr(f, 'strftime') else str(f)
        except Exception:
            fecha_txt = ''
        res.append({'id': m['id_mensaje'], 'id_usuario': m['id_usuario'],
                    'texto': m['texto'], 'fecha': fecha_txt})
    return res

@app.route('/soporte')
@login_required
def soporte_page():
    return render_template('soporte.html', user=obtener_usuario_por_id(session['user_id']))

@app.route('/api/soporte', methods=['GET'])
@login_required
def api_soporte():
    id_soporte = obtener_o_crear_soporte(session['user_id'])
    marcar_mensajes_leidos(id_soporte, session['user_id'])
    return jsonify(id_soporte=id_soporte,
                   mi_id=session['user_id'],
                   mensajes=_formatear_mensajes(obtener_mensajes_soporte(id_soporte)))

@app.route('/api/soporte/mensaje', methods=['POST'])
@login_required
def api_soporte_mensaje():
    texto = (request.json or {}).get('texto', '').strip()
    if not texto:
        return jsonify(error='Escribí un mensaje'), 400
    id_soporte = obtener_o_crear_soporte(session['user_id'])
    enviar_mensaje(id_soporte, session['user_id'], texto)
    return jsonify(ok=True)

@app.route('/api/soporte/no-leidos', methods=['GET'])
@login_required
def api_soporte_no_leidos():
    return jsonify(count=contar_no_leidos_usuario(session['user_id']))

@app.route('/api/admin/soporte', methods=['GET'])
@login_required
def api_admin_soporte_lista():
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    hilos = listar_soportes_admin(session['user_id'])
    for h in hilos:
        f = h.get('ultima_fecha')
        try:
            h['ultima_fecha'] = f.strftime('%d/%m %H:%M') if hasattr(f, 'strftime') else (str(f) if f else '')
        except Exception:
            h['ultima_fecha'] = ''
    return jsonify(hilos=hilos)

@app.route('/api/admin/soporte/<int:id_soporte>', methods=['GET'])
@login_required
def api_admin_soporte_detalle(id_soporte):
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    marcar_mensajes_leidos(id_soporte, session['user_id'])
    return jsonify(id_soporte=id_soporte,
                   mi_id=session['user_id'],
                   mensajes=_formatear_mensajes(obtener_mensajes_soporte(id_soporte)))

@app.route('/api/admin/soporte/<int:id_soporte>/mensaje', methods=['POST'])
@login_required
def api_admin_soporte_enviar(id_soporte):
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    texto = (request.json or {}).get('texto', '').strip()
    if not texto:
        return jsonify(error='Escribí un mensaje'), 400
    enviar_mensaje(id_soporte, session['user_id'], texto)
    return jsonify(ok=True)

@app.route('/api/admin/comunicado', methods=['POST'])
@login_required
def api_admin_comunicado():
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    texto = (request.json or {}).get('texto', '').strip()
    if not texto:
        return jsonify(error='Escribí el comunicado'), 400
    total = enviar_comunicado(session['user_id'], texto)
    return jsonify(ok=True, total=total)

@app.route('/api/admin/usuario/<int:id_usuario>/reactivar', methods=['POST'])
@login_required
def api_admin_reactivar(id_usuario):
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    dias = int((request.json or {}).get('dias', 30))
    if dias <= 0 or dias > 3650:
        dias = 30
    reactivar_usuario(id_usuario, dias)
    return jsonify(ok=True)

@app.route('/api/admin/usuario/<int:id_usuario>/reset', methods=['POST'])
@login_required
def api_admin_reset(id_usuario):
    if not es_admin():
        return jsonify(error='sin permiso'), 403
    import secrets
    token = secrets.token_urlsafe(32)
    expira = datetime.now() + timedelta(hours=24)
    guardar_reset_token(id_usuario, token, expira)
    base = os.environ.get('BASE_URL', 'https://infia.onrender.com').rstrip('/')
    return jsonify(ok=True, reset_link=f'{base}/reset/{token}')

# ─── API: AUTH ───────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        ip = request.remote_addr or 'unknown'
        if not revisar_rate_limit(ip):
            return jsonify(error='Demasiados intentos. Esperá 15 minutos.'), 429
        data = request.json
        email = (data.get('email') or '').strip()
        contraseña = data.get('contraseña') or ''
        if not email or not contraseña:
            return jsonify(error='Completá todos los campos'), 400
        user = obtener_usuario_por_email(email)
        if not user or not check_password_hash(user['contraseña'], contraseña):
            return jsonify(error='Email o contraseña incorrectos'), 401
        session.permanent = True
        session['user_id'] = user['id_usuario']
        _login_intentos[ip] = []
        admin_email = os.environ.get('ADMIN_EMAIL', '')
        es_admin_login = bool(admin_email and (user['email'] or '').lower() == admin_email.lower())
        return jsonify(ok=True, nombre=user['nombre'],
                       destino='/admin' if es_admin_login else '/dashboard')
    except Exception as e:
        return jsonify(error='Error interno: ' + str(e)), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    ip = request.remote_addr or 'unknown'
    if not revisar_rate_limit(ip):
        return jsonify(error='Demasiados intentos. Esperá 15 minutos.'), 429
    data = request.json
    nombre = (data.get('nombre') or '').strip()
    email = (data.get('email') or '').strip()
    contraseña = data.get('contraseña') or ''
    codigo_esperado = os.environ.get('CODIGO_INVITACION', '')
    if codigo_esperado:
        codigo = (data.get('codigo') or '').strip()
        if not codigo or codigo != codigo_esperado:
            return jsonify(error='El código de invitación es inválido'), 403
    if not nombre:
        return jsonify(error='El nombre es obligatorio'), 400
    if not email or '@' not in email or '.' not in email:
        return jsonify(error='Email inválido'), 400
    errores_pw = validar_contraseña(contraseña)
    if errores_pw:
        return jsonify(error='La contraseña debe tener ' + ', '.join(errores_pw)), 400
    uid = crear_usuario(nombre, email,
                        hash_pass(contraseña),
                        data.get('sala', '3 Años B'),
                        data.get('turno', 'Tarde'))
    if uid is None:
        return jsonify(error='El email ya está registrado'), 400
    session['user_id'] = uid
    return jsonify(ok=True, nombre=nombre)

@app.route('/api/logout')
def api_logout():
    session.clear()
    return jsonify(ok=True)

@app.route('/api/me')
@login_required
def api_me():
    return jsonify(obtener_usuario_por_id(session['user_id']))

# ─── API: ALUMNOS ────────────────────────

@app.route('/api/alumnos', methods=['GET'])
@login_required
def api_listar_alumnos():
    return jsonify(obtener_alumnos(session['user_id']))

@app.route('/api/alumnos', methods=['POST'])
@login_required
def api_crear_alumno():
    data = request.json
    uid = registrar_alumno(session['user_id'], data['nombre'], data['apellido'])
    return jsonify(id_alumno=uid), 201

@app.route('/api/alumnos/multi', methods=['POST'])
@login_required
def api_crear_alumnos_multi():
    data = request.json
    alumnos = data.get('alumnos', [])
    if not alumnos:
        return jsonify(error='Sin alumnos'), 400
    ids = []
    for a in alumnos:
        nombre = a.get('nombre', '').strip()
        apellido = a.get('apellido', '').strip()
        if nombre and apellido:
            uid = registrar_alumno(session['user_id'], nombre, apellido)
            ids.append(uid)
    return jsonify(creados=len(ids)), 201

@app.route('/api/alumnos/<int:id_alumno>', methods=['DELETE'])
@login_required
def api_eliminar_alumno(id_alumno):
    try:
        eliminar_alumno(id_alumno, session['user_id'])
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(ok=True)

@app.route('/api/alumnos/delete-multi', methods=['POST'])
@login_required
def api_eliminar_alumnos_multi():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify(error='Sin IDs'), 400
    try:
        for aid in ids:
            eliminar_alumno(aid, session['user_id'])
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(eliminados=len(ids))

# ─── API: ACTIVIDADES ────────────────────

@app.route('/api/actividades', methods=['GET'])
@login_required
def api_listar_actividades():
    fecha = request.args.get('fecha')
    return jsonify(obtener_actividades_dia(session['user_id'], fecha))

@app.route('/api/actividades', methods=['POST'])
@login_required
def api_crear_actividad():
    data = request.json
    uid = crear_actividad(session['user_id'], data['nombre'], data['area'], data.get('fecha'))
    return jsonify(id_actividad=uid), 201

@app.route('/api/actividades/<int:id_actividad>', methods=['PUT'])
@login_required
def api_actualizar_actividad(id_actividad):
    data = request.json
    actualizar_actividad(id_actividad, session['user_id'], data.get('nombre'), data.get('area'))
    return jsonify(ok=True)

@app.route('/api/actividades/<int:id_actividad>', methods=['DELETE'])
@login_required
def api_eliminar_actividad(id_actividad):
    eliminar_actividad(id_actividad, session['user_id'])
    return jsonify(ok=True)

@app.route('/api/actividades/delete-multi', methods=['POST'])
@login_required
def api_eliminar_actividades_multi():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify(error='Sin IDs'), 400
    try:
        for aid in ids:
            eliminar_actividad(aid, session['user_id'])
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(eliminados=len(ids))

@app.route('/api/actividades/multi', methods=['POST'])
@login_required
def api_crear_actividades_multi():
    data = request.json
    actividades = data.get('actividades', [])
    if not actividades:
        return jsonify(error='No hay actividades'), 400
    ids = crear_actividades_multi(session['user_id'], actividades, data.get('fecha'), data.get('id_unidad'))
    return jsonify(ids=ids, count=len(ids)), 201

# ─── API: OBSERVACIONES ──────────────────

@app.route('/api/observaciones', methods=['POST'])
@login_required
def api_guardar_observacion():
    data = request.json
    guardar_observacion(data['id_alumno'], data.get('id_actividad'),
                        data['nota_cruda'], data.get('tipo', 'texto'))
    return jsonify(ok=True), 201

@app.route('/api/observaciones/<int:id_observacion>', methods=['DELETE'])
@login_required
def api_eliminar_observacion(id_observacion):
    ruta = eliminar_observacion(id_observacion)
    if ruta:
        audio_path = os.path.join(app.static_folder, 'audios', os.path.basename(ruta))
        if os.path.exists(audio_path):
            os.remove(audio_path)
    return jsonify(ok=True)

@app.route('/api/observaciones/batch-delete', methods=['POST'])
@login_required
def api_eliminar_observaciones_multi():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify(error='No hay IDs'), 400
    for ruta in eliminar_observaciones_multi(ids):
        audio_path = os.path.join(app.static_folder, 'audios', os.path.basename(ruta))
        if os.path.exists(audio_path):
            os.remove(audio_path)
    return jsonify(ok=True, count=len(ids))

@app.route('/api/observaciones/alumno/<int:id_alumno>')
@login_required
def api_obs_alumno(id_alumno):
    return jsonify(obtener_observaciones_alumno(id_alumno))

@app.route('/api/observaciones/hoy')
@login_required
def api_obs_hoy():
    return jsonify(obtener_todas_observaciones_dia(session['user_id'], request.args.get('fecha')))

@app.route('/api/alumno/<int:id_alumno>/detalle')
@login_required
def api_alumno_detalle(id_alumno):
    from src.db import obtener_alumnos
    alumnos = obtener_alumnos(session['user_id'])
    alumno = next((a for a in alumnos if a['id_alumno'] == id_alumno), None)
    if not alumno:
        return jsonify(error='Alumno no encontrado'), 404
    obs = obtener_observaciones_alumno(id_alumno)
    informe = obtener_informe_reciente(id_alumno)
    alumno['observaciones'] = obs
    alumno['informe'] = informe
    return jsonify(alumno)

# ─── API: AUDIO ──────────────────────────

@app.route('/api/audio/subir', methods=['POST'])
@login_required
def api_subir_audio():
    if 'audio' not in request.files:
        return jsonify(error='No se envió archivo de audio'), 400
    f = request.files['audio']
    ext = os.path.splitext(f.filename)[1] or '.webm'
    audio_filename = f'audio_{session["user_id"]}_{os.urandom(4).hex()}{ext}'
    path = os.path.join(AUDIO_DIR, audio_filename)
    f.save(path)
    ruta_audio = f'/static/audios/{audio_filename}'
    texto = transcribir_audio(int(request.form['id_alumno']),
                              request.form.get('id_actividad'),
                              path, session['user_id'])
    if not texto:
        texto = 'Audio grabado (transcripción no disponible)'
        import time; time.sleep(0.1)
    guardar_observacion(int(request.form['id_alumno']),
                        request.form.get('id_actividad', type=int),
                        texto, 'audio', ruta_audio=ruta_audio)
    return jsonify(ok=True, texto=texto, ruta_audio=ruta_audio), 201

# ─── API: AREAS ───────────────────────────

@app.route('/api/areas', methods=['GET'])
@login_required
def api_areas():
    return jsonify(areas_para(session['user_id']))

@app.route('/api/areas', methods=['POST'])
@login_required
def api_crear_area():
    data = request.json
    nombre = (data.get('nombre') or '').strip()
    if not nombre:
        return jsonify(error='Falta nombre'), 400
    crear_area(session['user_id'], nombre)
    return jsonify(ok=True), 201

@app.route('/api/areas/<int:id_area>', methods=['PUT'])
@login_required
def api_renombrar_area(id_area):
    data = request.json
    nuevo = (data.get('nombre') or '').strip()
    if not nuevo:
        return jsonify(error='Falta nombre'), 400
    renombrar_area(session['user_id'], id_area, nuevo)
    return jsonify(ok=True)

@app.route('/api/areas/<int:id_area>', methods=['DELETE'])
@login_required
def api_eliminar_area(id_area):
    try:
        eliminar_area(session['user_id'], id_area)
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(ok=True)

@app.route('/api/areas/delete-multi', methods=['POST'])
@login_required
def api_eliminar_areas_multi():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify(error='Sin IDs'), 400
    try:
        for aid in ids:
            eliminar_area(session['user_id'], aid)
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(eliminados=len(ids))

@app.route('/api/areas/rename', methods=['POST'])
@login_required
def api_rename_area():
    data = request.json
    area_vieja = (data.get('area_vieja') or '').strip()
    area_nueva = (data.get('area_nueva') or '').strip()
    if not area_vieja or not area_nueva:
        return jsonify(error='Faltan datos'), 400
    if area_vieja == area_nueva:
        return jsonify(error='El nombre nuevo debe ser diferente'), 400
    renombrar_area(session['user_id'], area_vieja, area_nueva)
    return jsonify(ok=True)

# ─── API: CAMBIO / RESET DE CONTRASEÑA ────

@app.route('/api/usuario/reset-solicitar', methods=['POST'])
def api_solicitar_reset():
    ip = request.remote_addr or 'unknown'
    if not revisar_rate_limit_reset(ip):
        return jsonify(error='Demasiadas solicitudes. Esperá 15 minutos.'), 429
    data = request.json
    email = (data.get('email') or '').strip()
    if not email:
        return jsonify(error='Ingresá tu email'), 400
    user = obtener_usuario_por_email(email)
    if not user:
        # No revelar si el email existe o no
        return jsonify(ok=True, mensaje='Si el email existe, recibirás instrucciones')
    import secrets
    from datetime import datetime, timedelta
    token = secrets.token_urlsafe(32)
    expira = datetime.now() + timedelta(hours=1)
    guardar_reset_token(user['id_usuario'], token, expira)
    # Como no tenemos email, devolvemos el link directo
    reset_link = f"/reset/{token}"
    return jsonify(ok=True, reset_link=reset_link, mensaje='Link generado. Hacé clic en el enlace para resetear tu contraseña.')

@app.route('/api/usuario/reset/<token>', methods=['POST'])
def api_ejecutar_reset(token):
    from src.db import obtener_usuario_por_token, eliminar_token
    data = request.json
    nueva = (data.get('nueva') or '')
    errores_pw = validar_contraseña(nueva)
    if errores_pw:
        return jsonify(error='La contraseña debe tener ' + ', '.join(errores_pw)), 400
    user = obtener_usuario_por_token(token)
    if not user:
        return jsonify(error='Token inválido o expirado'), 400
    from src.db import actualizar_contraseña
    actualizar_contraseña(user['id_usuario'], hash_pass(nueva))
    eliminar_token(token)
    return jsonify(ok=True)



@app.route('/api/usuario/contraseña', methods=['PUT'])
@login_required
def api_cambiar_contraseña():
    data = request.json
    actual = (data.get('actual') or '')
    nueva = (data.get('nueva') or '')
    if not actual or not nueva:
        return jsonify(error='Completá ambos campos'), 400
    errores_pw = validar_contraseña(nueva)
    if errores_pw:
        return jsonify(error='La nueva contraseña debe tener ' + ', '.join(errores_pw)), 400
    user = obtener_usuario_por_id(session['user_id'])
    if not check_password_hash(user['contraseña'], actual):
        return jsonify(error='La contraseña actual no es correcta'), 401
    if nueva == actual:
        return jsonify(error='La nueva contraseña debe ser diferente a la actual'), 400
    from src.db import actualizar_contraseña
    actualizar_contraseña(session['user_id'], hash_pass(nueva))
    return jsonify(ok=True)

# ─── PÁGINA: CONFIGURACIÓN ─────────────────

@app.route('/config')
@login_required
def config_page():
    return render_template('config.html')

@app.route('/perfil')
@login_required
def perfil_page():
    user = obtener_usuario_por_id(session['user_id'])
    return render_template('perfil.html', user=user, es_admin=es_admin())

@app.route('/api/usuario/perfil', methods=['PUT'])
@login_required
def api_actualizar_perfil():
    data = request.json
    user = obtener_usuario_por_id(session['user_id'])
    nombre = (data.get('nombre') or user['nombre']).strip()
    sala = data.get('sala') or user['sala']
    turno = data.get('turno') or user['turno']
    if not nombre:
        return jsonify(error='El nombre no puede estar vacío'), 400
    from src.db import actualizar_perfil
    actualizar_perfil(session['user_id'], nombre, sala, turno)
    return jsonify(ok=True)

# ─── PÁGINA: RESET ─────────────────────────

@app.route('/reset/<token>')
def reset_page(token):
    from src.db import obtener_usuario_por_token
    user = obtener_usuario_por_token(token)
    if not user:
        return '<div style="padding:2rem;text-align:center"><h3>🔗 Token inválido o expirado</h3><p>Pedí un nuevo reset en <a href="/login">iniciar sesión</a>.</p></div>'
    return render_template('reset.html', token=token)

@app.route('/forgot')
def forgot_page():
    return render_template('forgot.html')

# ─── API: UNIDADES ────────────────────────

@app.route('/api/unidades', methods=['GET'])
@login_required
def api_listar_unidades():
    return jsonify(obtener_unidades(session['user_id']))

@app.route('/api/unidades', methods=['POST'])
@login_required
def api_crear_unidad():
    data = request.json
    uid = crear_unidad(session['user_id'], data['titulo'], data.get('contenido', ''))
    return jsonify(id_unidad=uid), 201

@app.route('/api/unidades/<int:id_unidad>', methods=['PUT'])
@login_required
def api_actualizar_unidad(id_unidad):
    data = request.json
    actualizar_unidad(id_unidad, session['user_id'], data['titulo'], data.get('contenido', ''))
    return jsonify(ok=True)

@app.route('/api/unidades/<int:id_unidad>', methods=['DELETE'])
@login_required
def api_eliminar_unidad(id_unidad):
    eliminar_unidad(id_unidad, session['user_id'])
    return jsonify(ok=True)

@app.route('/api/unidades/delete-multi', methods=['POST'])
@login_required
def api_eliminar_unidades_multi():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify(error='Sin IDs'), 400
    try:
        for uid in ids:
            eliminar_unidad(uid, session['user_id'])
    except Exception as e:
        return jsonify(error=str(e)), 500
    return jsonify(eliminados=len(ids))

# ─── API: STATS ───────────────────────────

@app.route('/api/stats')
@login_required
def api_stats():
    return jsonify(obtener_stats(session['user_id']))

# ─── API: EXPORT ──────────────────────────

@app.route('/api/export/observaciones.csv')
@login_required
def api_export_csv():
    import csv, io
    alumnos = obtener_alumnos(session['user_id'])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Apellido', 'Nombre', 'Fecha', 'Actividad', 'Area', 'Observacion', 'Tipo'])
    for a in alumnos:
        obs = obtener_observaciones_alumno(a['id_alumno'])
        for o in obs:
            writer.writerow([
                a['apellido'], a['nombre'],
                (o.get('fecha') or '').split(' ')[0],
                o.get('act_nombre') or '',
                o.get('area') or '',
                o.get('nota_cruda') or '',
                o.get('tipo') or 'texto',
            ])
    return output.getvalue().encode('utf-8-sig'), 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="observaciones.csv"',
    }

# ─── API: INFORME ────────────────────────

@app.route('/api/informe/<int:id_alumno>', methods=['POST'])
@login_required
def api_generar_informe(id_alumno):
    contenido = formatear_informe_ia(id_alumno)
    if contenido:
        guardar_informe(id_alumno, 'Cuatrimestral', contenido)
        return jsonify(ok=True, contenido=contenido)
    return jsonify(error='Error al generar informe'), 500

@app.route('/api/informe/<int:id_alumno>/pdf')
@login_required
def api_informe_pdf(id_alumno):
    from src.pdf import informe_to_pdf
    alumnos = obtener_alumnos(session['user_id'])
    alumno = next((a for a in alumnos if a['id_alumno'] == id_alumno), None)
    if not alumno:
        return jsonify(error='Alumno no encontrado'), 404
    informe = obtener_informe_reciente(id_alumno)
    if not informe or not informe.get('contenido_informe'):
        return jsonify(error='No hay informe generado'), 404
    pdf_bytes = informe_to_pdf(informe['contenido_informe'],
                               f"{alumno['apellido']}, {alumno['nombre']}")
    return pdf_bytes, 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename="informe_{alumno["apellido"]}_{alumno["nombre"]}.pdf"',
    }

@app.route('/api/informe/<int:id_alumno>', methods=['PUT'])
@login_required
def api_actualizar_informe(id_alumno):
    data = request.json
    contenido = (data.get('contenido') or '').strip()
    if not contenido:
        return jsonify(error='El contenido no puede estar vacío'), 400
    actualizar_informe(id_alumno, contenido)
    return jsonify(ok=True, contenido=contenido)

# ─── PWA & STATIC ────────────────────────

@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.json')

@app.route('/sw.js')
def sw():
    return send_from_directory(app.static_folder, 'sw.js', mimetype='application/javascript')

@app.route('/offline')
def offline():
    return render_template('offline.html')



@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true'))
