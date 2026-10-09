import os
from datetime import date, datetime
try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo('America/Argentina/Buenos_Aires')
except Exception:
    ZONA = None
import psycopg2
from psycopg2 import extras


def hoy():
    if ZONA:
        return datetime.now(ZONA).date()
    return date.today()

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'America/Argentina/Buenos_Aires'")
    except Exception:
        pass
    return conn

def fetch_all(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return [_serialize(dict(r)) for r in rows]

def fetch_one(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        r = cur.fetchone()
        return _serialize(dict(r)) if r else None

def fetch_one_raw(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        r = cur.fetchone()
        return dict(r) if r else None

def fetch_all_raw(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]

def _serialize(row):
    from datetime import date, datetime
    return {k: (v.strftime('%d/%m/%Y') if isinstance(v, (date, datetime)) else v) for k, v in row.items()}

def execute(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())

def execute_return(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()[0]

# ─── INICIALIZACIÓN ──────────────────────

def inicializar_bd():
    conn = conectar()
    try:
        execute(conn, '''CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL,
            sala TEXT DEFAULT '3 Años B',
            turno TEXT DEFAULT 'Tarde'
        )''')

        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'trial'")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_vencimiento DATE")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS mp_preapproval_id TEXT")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS baja_solicitada_en TIMESTAMP")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS motivo_baja TEXT")
        execute(conn, "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS avatar_data TEXT")

        execute(conn, '''CREATE TABLE IF NOT EXISTS app_config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS pagos (
            id_pago SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            monto INTEGER NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'mensual',
            mp_payment_id TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS soportes (
            id_soporte SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            estado TEXT DEFAULT 'abierto',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS mensajes (
            id_mensaje SERIAL PRIMARY KEY,
            id_soporte INTEGER NOT NULL REFERENCES soportes(id_soporte),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            texto TEXT NOT NULL,
            leido BOOLEAN DEFAULT FALSE,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        migrado = fetch_one(conn, "SELECT valor FROM app_config WHERE clave = 'grandfathered'")
        if not migrado:
            execute(conn, "UPDATE usuarios SET plan = 'pago', fecha_vencimiento = '2099-12-31'")
            execute(conn, "INSERT INTO app_config (clave, valor) VALUES ('grandfathered', '1')")
            conn.commit()

        execute(conn, '''CREATE TABLE IF NOT EXISTS alumnos (
            id_alumno SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS actividades (
            id_actividad SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            nombre TEXT NOT NULL,
            area TEXT NOT NULL DEFAULT 'Identidad y Convivencia',
            fecha DATE NOT NULL DEFAULT CURRENT_DATE,
            id_unidad INTEGER
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS unidades (
            id_unidad SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            titulo TEXT NOT NULL,
            contenido TEXT NOT NULL,
            ruta_archivo TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS observaciones (
            id_observacion SERIAL PRIMARY KEY,
            id_alumno INTEGER NOT NULL REFERENCES alumnos(id_alumno),
            id_actividad INTEGER REFERENCES actividades(id_actividad),
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            nota_cruda TEXT NOT NULL,
            tipo TEXT DEFAULT 'texto' CHECK(tipo IN ('texto','audio')),
            ruta_audio TEXT
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS informes_finales (
            id_informe SERIAL PRIMARY KEY,
            id_alumno INTEGER REFERENCES alumnos(id_alumno),
            fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            etapa TEXT NOT NULL,
            contenido_informe TEXT
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS reset_tokens (
            id_token SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            token TEXT NOT NULL UNIQUE,
            expira TIMESTAMP NOT NULL
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS areas_usuario (
            id_area SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            nombre TEXT NOT NULL
        )''')

        execute(conn, '''CREATE TABLE IF NOT EXISTS salas_docente (
            id_sala SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            sala TEXT NOT NULL,
            turno TEXT NOT NULL,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(id_usuario, nombre)
        )''')
        execute(conn, '''INSERT INTO salas_docente (id_usuario, nombre, sala, turno)
                         SELECT u.id_usuario, u.sala || ' · ' || u.turno, u.sala, u.turno
                         FROM usuarios u
                         WHERE NOT EXISTS (
                           SELECT 1 FROM salas_docente s WHERE s.id_usuario = u.id_usuario
                         )''')
        for tabla in ('alumnos', 'actividades', 'unidades', 'areas_usuario'):
            execute(conn, f'ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS id_sala INTEGER REFERENCES salas_docente(id_sala)')
            execute(conn, f'''UPDATE {tabla} item SET id_sala = sala.id_sala
                              FROM salas_docente sala
                              WHERE item.id_sala IS NULL AND item.id_usuario = sala.id_usuario
                                AND sala.id_sala = (
                                  SELECT MIN(s2.id_sala) FROM salas_docente s2
                                  WHERE s2.id_usuario = sala.id_usuario
                                )''')
            execute(conn, f'ALTER TABLE {tabla} ALTER COLUMN id_sala SET NOT NULL')
            execute(conn, f'CREATE INDEX IF NOT EXISTS idx_{tabla}_sala ON {tabla}(id_sala)')

        conn.commit()
        print("Base de datos PostgreSQL actualizada con éxito!")
    except Exception as e:
        conn.rollback()
        print(f"Error inicializando BD: {e}")
        raise
    finally:
        conn.close()

# ─── USUARIOS ────────────────────────────

def crear_usuario(nombre, email, contraseña, sala, turno):
    conn = conectar()
    try:
        uid = execute_return(conn,
            "INSERT INTO usuarios (nombre, email, contraseña, sala, turno, plan) VALUES (%s,%s,%s,%s,%s,'trial') RETURNING id_usuario",
            (nombre, email, contraseña, sala, turno))
        nombre_sala = f'{sala} - {turno}'
        id_sala = execute_return(conn,
            'INSERT INTO salas_docente (id_usuario, nombre, sala, turno) VALUES (%s,%s,%s,%s) RETURNING id_sala',
            (uid, nombre_sala, sala, turno))
        for area in AREAS_DEFAULT:
            execute(conn, 'INSERT INTO areas_usuario (id_usuario, id_sala, nombre) VALUES (%s,%s,%s)',
                    (uid, id_sala, area))
        conn.commit()
        return uid
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return None
    finally:
        conn.close()

def obtener_usuario_por_email(email):
    conn = conectar()
    try:
        return fetch_one(conn, 'SELECT * FROM usuarios WHERE email = %s', (email,))
    finally:
        conn.close()

def obtener_usuario_por_id(id_usuario):
    conn = conectar()
    try:
        return fetch_one(conn, 'SELECT * FROM usuarios WHERE id_usuario = %s', (id_usuario,))
    finally:
        conn.close()

def obtener_salas_docente(id_usuario):
    conn = conectar()
    try:
        return fetch_all(conn, '''SELECT id_sala, nombre, sala, turno, fecha_creacion
                                  FROM salas_docente WHERE id_usuario = %s
                                  ORDER BY fecha_creacion, id_sala''', (id_usuario,))
    finally:
        conn.close()

def obtener_sala_docente(id_sala, id_usuario):
    conn = conectar()
    try:
        return fetch_one(conn, 'SELECT * FROM salas_docente WHERE id_sala = %s AND id_usuario = %s',
                         (id_sala, id_usuario))
    finally:
        conn.close()

def crear_sala_docente(id_usuario, nombre, sala, turno):
    conn = conectar()
    try:
        id_sala = execute_return(conn,
            'INSERT INTO salas_docente (id_usuario, nombre, sala, turno) VALUES (%s,%s,%s,%s) RETURNING id_sala',
            (id_usuario, nombre, sala, turno))
        for area in AREAS_DEFAULT:
            execute(conn, 'INSERT INTO areas_usuario (id_usuario, id_sala, nombre) VALUES (%s,%s,%s)',
                    (id_usuario, id_sala, area))
        conn.commit()
        return id_sala
    finally:
        conn.close()

def actualizar_sala_docente(id_sala, id_usuario, nombre, sala, turno):
    conn = conectar()
    try:
        execute(conn, '''UPDATE salas_docente SET nombre = %s, sala = %s, turno = %s
                         WHERE id_sala = %s AND id_usuario = %s''',
                (nombre, sala, turno, id_sala, id_usuario))
        conn.commit()
    finally:
        conn.close()

def eliminar_sala_docente(id_sala, id_usuario):
    conn = conectar()
    try:
        total = fetch_one(conn, 'SELECT COUNT(*) AS cantidad FROM salas_docente WHERE id_usuario = %s',
                          (id_usuario,))['cantidad']
        contenido = fetch_one(conn, '''SELECT
                                         (SELECT COUNT(*) FROM alumnos WHERE id_sala = %s) +
                                         (SELECT COUNT(*) FROM actividades WHERE id_sala = %s) +
                                         (SELECT COUNT(*) FROM unidades WHERE id_sala = %s) AS cantidad''',
                              (id_sala, id_sala, id_sala))['cantidad']
        if total <= 1 or contenido:
            return False
        execute(conn, 'DELETE FROM areas_usuario WHERE id_sala = %s AND id_usuario = %s', (id_sala, id_usuario))
        execute(conn, 'DELETE FROM unidades WHERE id_sala = %s AND id_usuario = %s', (id_sala, id_usuario))
        execute(conn, 'DELETE FROM actividades WHERE id_sala = %s AND id_usuario = %s', (id_sala, id_usuario))
        execute(conn, 'DELETE FROM salas_docente WHERE id_sala = %s AND id_usuario = %s', (id_sala, id_usuario))
        conn.commit()
        return True
    finally:
        conn.close()

def solicitar_baja_usuario(id_usuario, motivo):
    conn = conectar()
    try:
        execute(conn, '''UPDATE usuarios
                         SET baja_solicitada_en = CURRENT_TIMESTAMP,
                             motivo_baja = %s
                         WHERE id_usuario = %s AND baja_solicitada_en IS NULL''',
                (motivo, id_usuario))
        conn.commit()
    finally:
        conn.close()

def cancelar_baja_usuario(id_usuario):
    conn = conectar()
    try:
        execute(conn, '''UPDATE usuarios
                         SET baja_solicitada_en = NULL, motivo_baja = NULL
                         WHERE id_usuario = %s''', (id_usuario,))
        conn.commit()
    finally:
        conn.close()

def eliminar_usuario_completamente(id_usuario):
    """Elimina los datos propios de una cuenta y devuelve las rutas de sus audios."""
    conn = conectar()
    try:
        audios = fetch_all_raw(conn, '''
            SELECT o.ruta_audio
            FROM observaciones o
            JOIN alumnos a ON a.id_alumno = o.id_alumno
            WHERE a.id_usuario = %s AND o.ruta_audio IS NOT NULL
        ''', (id_usuario,))
        execute(conn, '''DELETE FROM mensajes
                         WHERE id_usuario = %s OR id_soporte IN
                           (SELECT id_soporte FROM soportes WHERE id_usuario = %s)''',
                (id_usuario, id_usuario))
        execute(conn, 'DELETE FROM soportes WHERE id_usuario = %s', (id_usuario,))
        execute(conn, '''DELETE FROM informes_finales
                         WHERE id_alumno IN (SELECT id_alumno FROM alumnos WHERE id_usuario = %s)''',
                (id_usuario,))
        execute(conn, '''DELETE FROM observaciones
                         WHERE id_alumno IN (SELECT id_alumno FROM alumnos WHERE id_usuario = %s)''',
                (id_usuario,))
        execute(conn, 'DELETE FROM alumnos WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM actividades WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM unidades WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM areas_usuario WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM reset_tokens WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM pagos WHERE id_usuario = %s', (id_usuario,))
        execute(conn, 'DELETE FROM usuarios WHERE id_usuario = %s', (id_usuario,))
        conn.commit()
        return [a['ruta_audio'] for a in audios]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def obtener_bajas_vencidas(dias=7):
    conn = conectar()
    try:
        return fetch_all_raw(conn, '''
            SELECT id_usuario FROM usuarios
            WHERE baja_solicitada_en IS NOT NULL
              AND baja_solicitada_en <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')
        ''', (dias,))
    finally:
        conn.close()

def actualizar_perfil(id_usuario, nombre, sala, turno):
    conn = conectar()
    try:
        execute(conn, 'UPDATE usuarios SET nombre = %s, sala = %s, turno = %s WHERE id_usuario = %s',
                (nombre, sala, turno, id_usuario))
        conn.commit()
    finally:
        conn.close()

def actualizar_avatar(id_usuario, avatar_data):
    conn = conectar()
    try:
        execute(conn, 'UPDATE usuarios SET avatar_data = %s WHERE id_usuario = %s',
                (avatar_data, id_usuario))
        conn.commit()
    finally:
        conn.close()

def actualizar_contraseña(id_usuario, nueva_hash):
    conn = conectar()
    try:
        execute(conn, 'UPDATE usuarios SET contraseña = %s WHERE id_usuario = %s', (nueva_hash, id_usuario))
        conn.commit()
    finally:
        conn.close()

def guardar_reset_token(id_usuario, token, expira):
    conn = conectar()
    try:
        execute(conn, 'INSERT INTO reset_tokens (id_usuario, token, expira) VALUES (%s,%s,%s)',
                (id_usuario, token, expira))
        conn.commit()
    finally:
        conn.close()

# ─── SUSCRIPCIÓN ─────────────────────────

def obtener_suscripcion(id_usuario):
    conn = conectar()
    try:
        return fetch_one_raw(conn,
            'SELECT email, fecha_registro, plan, fecha_vencimiento, mp_preapproval_id FROM usuarios WHERE id_usuario = %s',
            (id_usuario,))
    finally:
        conn.close()

def extender_suscripcion(id_usuario, dias, mp_preapproval_id):
    conn = conectar()
    try:
        execute(conn,
            '''UPDATE usuarios
               SET plan = 'pago',
                   fecha_vencimiento = GREATEST(CURRENT_DATE + %s::int, COALESCE(fecha_vencimiento, CURRENT_DATE + %s::int)),
                   mp_preapproval_id = %s
               WHERE id_usuario = %s''',
            (dias, dias, mp_preapproval_id, id_usuario))
        conn.commit()
    finally:
        conn.close()

def registrar_pago(id_usuario, monto, tipo, mp_payment_id=None):
    conn = conectar()
    try:
        execute(conn,
            'INSERT INTO pagos (id_usuario, monto, tipo, mp_payment_id) VALUES (%s,%s,%s,%s)',
            (id_usuario, monto, tipo, mp_payment_id))
        conn.commit()
    finally:
        conn.close()

def obtener_todos_usuarios():
    conn = conectar()
    try:
        return fetch_all_raw(conn,
            'SELECT id_usuario, nombre, email, sala, turno, plan, fecha_registro, fecha_vencimiento FROM usuarios ORDER BY fecha_registro')
    finally:
        conn.close()

def obtener_pagos():
    conn = conectar()
    try:
        return fetch_all(conn,
            '''SELECT p.id_pago, p.monto, p.tipo, p.fecha, u.nombre, u.email
               FROM pagos p JOIN usuarios u ON p.id_usuario = u.id_usuario
               ORDER BY p.fecha DESC''')
    finally:
        conn.close()

def obtener_ingresos_mes():
    conn = conectar()
    try:
        r = fetch_one(conn,
            "SELECT COALESCE(SUM(monto),0) AS total FROM pagos WHERE date_trunc('month', fecha) = date_trunc('month', CURRENT_TIMESTAMP)")
        return r['total']
    finally:
        conn.close()

def obtener_usuario_por_token(token):
    conn = conectar()
    try:
        r = fetch_one(conn,
            'SELECT u.* FROM usuarios u JOIN reset_tokens rt ON u.id_usuario = rt.id_usuario WHERE rt.token = %s AND rt.expira > NOW()',
            (token,))
        return r
    finally:
        conn.close()

def eliminar_token(token):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM reset_tokens WHERE token = %s', (token,))
        conn.commit()
    finally:
        conn.close()

# ─── SOPORTE ─────────────────────────────

def obtener_o_crear_soporte(id_usuario):
    conn = conectar()
    try:
        r = fetch_one_raw(conn, 'SELECT id_soporte FROM soportes WHERE id_usuario = %s', (id_usuario,))
        if not r:
            id_soporte = execute_return(conn, 'INSERT INTO soportes (id_usuario) VALUES (%s) RETURNING id_soporte', (id_usuario,))
            conn.commit()
            return id_soporte
        return r['id_soporte']
    finally:
        conn.close()

def enviar_mensaje(id_soporte, id_usuario, texto):
    conn = conectar()
    try:
        execute(conn,
            'INSERT INTO mensajes (id_soporte, id_usuario, texto) VALUES (%s,%s,%s)',
            (id_soporte, id_usuario, texto))
        conn.commit()
    finally:
        conn.close()

def obtener_mensajes_soporte(id_soporte):
    conn = conectar()
    try:
        return fetch_all_raw(conn,
            '''SELECT id_mensaje, id_usuario, texto, leido, fecha
               FROM mensajes WHERE id_soporte = %s ORDER BY fecha''',
            (id_soporte,))
    finally:
        conn.close()

def marcar_mensajes_leidos(id_soporte, id_lector):
    conn = conectar()
    try:
        execute(conn,
            'UPDATE mensajes SET leido = TRUE WHERE id_soporte = %s AND id_usuario != %s AND leido = FALSE',
            (id_soporte, id_lector))
        conn.commit()
    finally:
        conn.close()

def contar_no_leidos_usuario(id_usuario):
    conn = conectar()
    try:
        r = fetch_one(conn,
            '''SELECT COUNT(*) AS c FROM mensajes m JOIN soportes s ON m.id_soporte = s.id_soporte
               WHERE s.id_usuario = %s AND m.id_usuario != %s AND m.leido = FALSE''',
            (id_usuario, id_usuario))
        return r['c']
    finally:
        conn.close()

def listar_soportes_admin(id_admin):
    conn = conectar()
    try:
        return fetch_all_raw(conn,
            '''SELECT s.id_soporte, s.id_usuario, u.nombre, u.email,
                      (SELECT COUNT(*) FROM mensajes m WHERE m.id_soporte = s.id_soporte AND m.id_usuario != %s AND m.leido = FALSE) AS no_leidos,
                      (SELECT texto FROM mensajes m WHERE m.id_soporte = s.id_soporte ORDER BY m.fecha DESC LIMIT 1) AS ultimo,
                      (SELECT fecha FROM mensajes m WHERE m.id_soporte = s.id_soporte ORDER BY m.fecha DESC LIMIT 1) AS ultima_fecha
               FROM soportes s JOIN usuarios u ON s.id_usuario = u.id_usuario
               ORDER BY (SELECT fecha FROM mensajes m WHERE m.id_soporte = s.id_soporte ORDER BY m.fecha DESC LIMIT 1) DESC NULLS LAST''',
            (id_admin,))
    finally:
        conn.close()

def reactivar_usuario(id_usuario, dias):
    conn = conectar()
    try:
        execute(conn,
            '''UPDATE usuarios SET plan = 'pago',
               fecha_vencimiento = GREATEST(CURRENT_DATE + %s::int, COALESCE(fecha_vencimiento, CURRENT_DATE + %s::int))
               WHERE id_usuario = %s''',
            (dias, dias, id_usuario))
        conn.commit()
    finally:
        conn.close()

def enviar_comunicado(id_admin, texto):
    conn = conectar()
    try:
        usuarios = fetch_all_raw(conn, 'SELECT id_usuario FROM usuarios')
        for u in usuarios:
            sop = fetch_one_raw(conn, 'SELECT id_soporte FROM soportes WHERE id_usuario = %s', (u['id_usuario'],))
            if not sop:
                sop = {'id_soporte': execute_return(conn, 'INSERT INTO soportes (id_usuario) VALUES (%s) RETURNING id_soporte', (u['id_usuario'],))}
            execute(conn,
                'INSERT INTO mensajes (id_soporte, id_usuario, texto) VALUES (%s,%s,%s)',
                (sop['id_soporte'], id_admin, texto))
        conn.commit()
        return len(usuarios)
    finally:
        conn.close()

# ─── ALUMNOS ─────────────────────────────

def registrar_alumno(id_usuario, nombre, apellido, id_sala=None):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO alumnos (id_usuario, id_sala, nombre, apellido) VALUES (%s,%s,%s,%s) RETURNING id_alumno',
            (id_usuario, id_sala, nombre, apellido))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_alumnos(id_usuario, id_sala=None):
    conn = conectar()
    try:
        return fetch_all(conn,
            'SELECT id_alumno, nombre, apellido FROM alumnos WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) ORDER BY apellido, nombre',
            (id_usuario, id_sala))
    finally:
        conn.close()

def eliminar_alumno(id_alumno, id_usuario, id_sala=None):
    conn = conectar()
    try:
        pertenece = fetch_one(conn, '''SELECT id_alumno FROM alumnos WHERE id_alumno = %s
                                       AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)''',
                              (id_alumno, id_usuario, id_sala))
        if not pertenece:
            return False
        execute(conn, 'DELETE FROM informes_finales WHERE id_alumno = %s', (id_alumno,))
        execute(conn, 'DELETE FROM observaciones WHERE id_alumno = %s', (id_alumno,))
        execute(conn, 'DELETE FROM alumnos WHERE id_alumno = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                (id_alumno, id_usuario, id_sala))
        conn.commit()
        return True
    finally:
        conn.close()

# ─── ACTIVIDADES ─────────────────────────

def crear_actividad(id_usuario, nombre, area, fecha=None, id_unidad=None, id_sala=None):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO actividades (id_usuario, id_sala, nombre, area, fecha, id_unidad) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_actividad',
            (id_usuario, id_sala, nombre, area, fecha or hoy().isoformat(), id_unidad))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_actividades_dia(id_usuario, fecha=None, id_sala=None):
    conn = conectar()
    try:
        if fecha:
            rows = fetch_all(conn,
                'SELECT a.*, u.titulo as unidad_titulo FROM actividades a LEFT JOIN unidades u ON a.id_unidad = u.id_unidad WHERE a.id_usuario = %s AND a.id_sala = COALESCE(%s, a.id_sala) AND a.fecha = %s ORDER BY a.area, a.nombre',
                (id_usuario, id_sala, fecha))
        else:
            rows = fetch_all(conn,
                'SELECT a.*, u.titulo as unidad_titulo FROM actividades a LEFT JOIN unidades u ON a.id_unidad = u.id_unidad WHERE a.id_usuario = %s AND a.id_sala = COALESCE(%s, a.id_sala) ORDER BY a.area, a.nombre',
                (id_usuario, id_sala))
        return rows
    finally:
        conn.close()

def actualizar_actividad(id_actividad, id_usuario, nombre=None, area=None, id_sala=None):
    conn = conectar()
    try:
        if nombre and area:
            execute(conn, 'UPDATE actividades SET nombre = %s, area = %s WHERE id_actividad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                    (nombre, area, id_actividad, id_usuario, id_sala))
        elif nombre:
            execute(conn, 'UPDATE actividades SET nombre = %s WHERE id_actividad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                    (nombre, id_actividad, id_usuario, id_sala))
        elif area:
            execute(conn, 'UPDATE actividades SET area = %s WHERE id_actividad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                    (area, id_actividad, id_usuario, id_sala))
        conn.commit()
    finally:
        conn.close()

def crear_actividades_multi(id_usuario, actividades, fecha=None, id_unidad=None, id_sala=None):
    conn = conectar()
    ids = []
    try:
        f = fecha or hoy().isoformat()
        for act in actividades:
            uid = execute_return(conn,
                'INSERT INTO actividades (id_usuario, id_sala, nombre, area, fecha, id_unidad) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id_actividad',
                (id_usuario, id_sala, act['nombre'], act.get('area', 'Identidad y Convivencia'), f, id_unidad))
            ids.append(uid)
        conn.commit()
        return ids
    finally:
        conn.close()

def eliminar_actividad(id_actividad, id_usuario, id_sala=None):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM actividades WHERE id_actividad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                (id_actividad, id_usuario, id_sala))
        conn.commit()
    finally:
        conn.close()

# ─── UNIDADES DIDÁCTICAS ──────────────────

def crear_unidad(id_usuario, titulo, contenido, ruta_archivo=None, id_sala=None):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO unidades (id_usuario, id_sala, titulo, contenido, ruta_archivo) VALUES (%s,%s,%s,%s,%s) RETURNING id_unidad',
            (id_usuario, id_sala, titulo, contenido, ruta_archivo))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_unidades(id_usuario, id_sala=None):
    conn = conectar()
    try:
        return fetch_all(conn,
            'SELECT * FROM unidades WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) ORDER BY fecha_creacion DESC',
            (id_usuario, id_sala))
    finally:
        conn.close()

def obtener_unidad(id_unidad, id_usuario, id_sala=None):
    conn = conectar()
    try:
        return fetch_one(conn,
            'SELECT * FROM unidades WHERE id_unidad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
            (id_unidad, id_usuario, id_sala))
    finally:
        conn.close()

def actualizar_unidad(id_unidad, id_usuario, titulo, contenido, id_sala=None):
    conn = conectar()
    try:
        execute(conn,
            'UPDATE unidades SET titulo = %s, contenido = %s WHERE id_unidad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
            (titulo, contenido, id_unidad, id_usuario, id_sala))
        conn.commit()
    finally:
        conn.close()

def eliminar_unidad(id_unidad, id_usuario, id_sala=None):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM unidades WHERE id_unidad = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)',
                (id_unidad, id_usuario, id_sala))
        conn.commit()
    finally:
        conn.close()

# ─── STATS ────────────────────────────────

def obtener_stats(id_usuario, id_sala=None):
    conn = conectar()
    try:
        r = fetch_one(conn, """
            SELECT
              (SELECT COUNT(*) FROM alumnos WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala)) AS total_alumnos,
              (SELECT COUNT(*) FROM observaciones o JOIN alumnos al ON o.id_alumno = al.id_alumno WHERE al.id_usuario = %s AND al.id_sala = COALESCE(%s, al.id_sala) AND date(o.fecha) = CURRENT_DATE) AS obs_hoy,
              (SELECT COUNT(*) FROM observaciones o JOIN alumnos al ON o.id_alumno = al.id_alumno WHERE al.id_usuario = %s AND al.id_sala = COALESCE(%s, al.id_sala)) AS total_obs,
              (SELECT COUNT(*) FROM informes_finales i JOIN alumnos al ON i.id_alumno = al.id_alumno WHERE al.id_usuario = %s AND al.id_sala = COALESCE(%s, al.id_sala)) AS informes
        """, (id_usuario, id_sala, id_usuario, id_sala, id_usuario, id_sala, id_usuario, id_sala))
        return {
            'total_alumnos': r['total_alumnos'],
            'observaciones_hoy': r['obs_hoy'],
            'total_observaciones': r['total_obs'],
            'total_informes': r['informes'],
        }
    finally:
        conn.close()

# ─── ÁREAS ────────────────────────────────

AREAS_DEFAULT = ['Identidad y Convivencia', 'Lenguaje y Literatura',
                 'Matemáticas', 'Ciencias Sociales, Ciencias Naturales y Tecnología']

def _asegurar_areas_default(conn, id_usuario, id_sala=None):
    count = fetch_one(conn, 'SELECT COUNT(*) AS c FROM areas_usuario WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (id_usuario, id_sala))['c']
    if count == 0:
        for nombre in AREAS_DEFAULT:
            execute(conn, 'INSERT INTO areas_usuario (id_usuario, id_sala, nombre) VALUES (%s,%s,%s)', (id_usuario, id_sala, nombre))
        conn.commit()
    else:
        existing = {r['nombre'] for r in fetch_all(conn, 'SELECT nombre FROM areas_usuario WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (id_usuario, id_sala))}
        activity_areas = fetch_all(conn, "SELECT DISTINCT area FROM actividades WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) AND area != '' AND area != 'Sin área'", (id_usuario, id_sala))
        added = False
        for row in activity_areas:
            if row['area'] not in existing:
                execute(conn, 'INSERT INTO areas_usuario (id_usuario, id_sala, nombre) VALUES (%s,%s,%s)', (id_usuario, id_sala, row['area']))
                added = True
        if added:
            conn.commit()

def obtener_areas_usuario(id_usuario, id_sala=None):
    conn = conectar()
    try:
        _asegurar_areas_default(conn, id_usuario, id_sala)
        rows = fetch_all(conn, 'SELECT id_area, nombre FROM areas_usuario WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) ORDER BY nombre', (id_usuario, id_sala))
        return [{'id': row['id_area'], 'nombre': row['nombre']} for row in rows]
    finally:
        conn.close()

def crear_area(id_usuario, nombre, id_sala=None):
    conn = conectar()
    try:
        execute(conn, 'INSERT INTO areas_usuario (id_usuario, id_sala, nombre) VALUES (%s,%s,%s)', (id_usuario, id_sala, nombre))
        conn.commit()
    finally:
        conn.close()

def renombrar_area(id_usuario, area_id, nuevo_nombre, id_sala=None):
    conn = conectar()
    try:
        old = fetch_one(conn, 'SELECT nombre FROM areas_usuario WHERE id_area = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (area_id, id_usuario, id_sala))
        if old:
            execute(conn, 'UPDATE areas_usuario SET nombre = %s WHERE id_area = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (nuevo_nombre, area_id, id_usuario, id_sala))
            execute(conn, 'UPDATE actividades SET area = %s WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) AND area = %s', (nuevo_nombre, id_usuario, id_sala, old['nombre']))
            conn.commit()
    finally:
        conn.close()

def eliminar_area(id_usuario, area_id, id_sala=None):
    conn = conectar()
    try:
        area = fetch_one(conn, 'SELECT nombre FROM areas_usuario WHERE id_area = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (area_id, id_usuario, id_sala))
        if area:
            execute(conn, 'DELETE FROM areas_usuario WHERE id_area = %s AND id_usuario = %s AND id_sala = COALESCE(%s, id_sala)', (area_id, id_usuario, id_sala))
            execute(conn, "UPDATE actividades SET area = 'Sin área' WHERE id_usuario = %s AND id_sala = COALESCE(%s, id_sala) AND area = %s", (id_usuario, id_sala, area['nombre']))
            conn.commit()
            return True
        return False
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def guardar_observacion(id_alumno, id_actividad, nota_cruda, tipo='texto', ruta_audio=None, id_usuario=None, id_sala=None):
    conn = conectar()
    try:
        if id_usuario is not None:
            alumno = fetch_one(conn, 'SELECT id_alumno FROM alumnos WHERE id_alumno = %s AND id_usuario = %s AND id_sala = %s',
                               (id_alumno, id_usuario, id_sala))
            if not alumno:
                raise ValueError('El alumno no pertenece a la sala activa.')
            if id_actividad is not None:
                actividad = fetch_one(conn, 'SELECT id_actividad FROM actividades WHERE id_actividad = %s AND id_usuario = %s AND id_sala = %s',
                                      (id_actividad, id_usuario, id_sala))
                if not actividad:
                    raise ValueError('El indicador no pertenece a la sala activa.')
        execute(conn,
            'INSERT INTO observaciones (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio) VALUES (%s,%s,%s,%s,%s)',
            (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio))
        conn.commit()
    finally:
        conn.close()

def eliminar_observacion(id_observacion, id_usuario=None, id_sala=None):
    conn = conectar()
    try:
        if id_usuario is None:
            ruta = fetch_one(conn, 'SELECT ruta_audio FROM observaciones WHERE id_observacion = %s', (id_observacion,))
        else:
            ruta = fetch_one(conn, '''SELECT o.ruta_audio FROM observaciones o JOIN alumnos al ON al.id_alumno = o.id_alumno
                                      WHERE o.id_observacion = %s AND al.id_usuario = %s AND al.id_sala = %s''',
                             (id_observacion, id_usuario, id_sala))
        if ruta:
            if id_usuario is None:
                execute(conn, 'DELETE FROM observaciones WHERE id_observacion = %s', (id_observacion,))
            else:
                execute(conn, '''DELETE FROM observaciones WHERE id_observacion = %s AND id_alumno IN
                                 (SELECT id_alumno FROM alumnos WHERE id_usuario = %s AND id_sala = %s)''',
                        (id_observacion, id_usuario, id_sala))
            conn.commit()
            return ruta['ruta_audio']
        return None
    finally:
        conn.close()

def eliminar_observaciones_multi(ids, id_usuario=None, id_sala=None):
    conn = conectar()
    try:
        placeholders = ','.join(['%s'] * len(ids))
        scope = ''
        params = list(ids)
        if id_usuario is not None:
            scope = ' AND id_alumno IN (SELECT id_alumno FROM alumnos WHERE id_usuario = %s AND id_sala = %s)'
            params.extend([id_usuario, id_sala])
        rows = fetch_all(conn, f'SELECT ruta_audio FROM observaciones WHERE id_observacion IN ({placeholders}){scope}', params)
        execute(conn, f'DELETE FROM observaciones WHERE id_observacion IN ({placeholders}){scope}', params)
        conn.commit()
        return [r['ruta_audio'] for r in rows if r['ruta_audio']]
    finally:
        conn.close()

def obtener_observaciones_alumno(id_alumno):
    conn = conectar()
    try:
        return fetch_all(conn,
            '''SELECT o.*, a.nombre as act_nombre, a.area
               FROM observaciones o
               LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
               WHERE o.id_alumno = %s
               ORDER BY o.fecha DESC''', (id_alumno,))
    finally:
        conn.close()

def obtener_todas_observaciones_dia(id_usuario, fecha=None, id_sala=None):
    conn = conectar()
    try:
        if fecha:
            rows = fetch_all(conn, '''SELECT o.*, al.nombre AS al_nombre, al.apellido AS al_apellido,
                                      a.nombre AS act_nombre, a.area
                               FROM observaciones o
                               JOIN alumnos al ON o.id_alumno = al.id_alumno
                               LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
                               WHERE al.id_usuario = %s AND al.id_sala = COALESCE(%s, al.id_sala)
                                 AND date(o.fecha) = %s
                               ORDER BY al.apellido, al.nombre, o.fecha''', (id_usuario, id_sala, fecha))
        else:
            rows = fetch_all(conn, '''SELECT o.*, al.nombre AS al_nombre, al.apellido AS al_apellido,
                                      a.nombre AS act_nombre, a.area
                               FROM observaciones o
                               JOIN alumnos al ON o.id_alumno = al.id_alumno
                               LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
                               WHERE al.id_usuario = %s AND al.id_sala = COALESCE(%s, al.id_sala)
                                 AND date(o.fecha) = CURRENT_DATE
                               ORDER BY al.apellido, al.nombre, o.fecha''', (id_usuario, id_sala))
        return rows
    finally:
        conn.close()
def guardar_informe(id_alumno, etapa, contenido):
    conn = conectar()
    try:
        execute(conn,
            'INSERT INTO informes_finales (id_alumno, etapa, contenido_informe) VALUES (%s,%s,%s)',
            (id_alumno, etapa, contenido))
        conn.commit()
    finally:
        conn.close()

def obtener_informe_reciente(id_alumno):
    conn = conectar()
    try:
        return fetch_one(conn,
            'SELECT * FROM informes_finales WHERE id_alumno = %s ORDER BY fecha_generacion DESC LIMIT 1',
            (id_alumno,))
    finally:
        conn.close()

def actualizar_informe(id_alumno, contenido):
    conn = conectar()
    try:
        execute(conn,
            '''UPDATE informes_finales
               SET contenido_informe = %s, fecha_generacion = CURRENT_TIMESTAMP
               WHERE id_informe = (
                   SELECT id_informe FROM informes_finales
                   WHERE id_alumno = %s ORDER BY fecha_generacion DESC LIMIT 1
               )''', (contenido, id_alumno))
        conn.commit()
    finally:
        conn.close()
