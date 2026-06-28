import os
from datetime import date
import psycopg2
from psycopg2 import extras

DATABASE_URL = os.environ.get('DATABASE_URL')

def conectar():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    conn.autocommit = False
    return conn

def fetch_all(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]

def fetch_one(conn, sql, params=None):
    with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        r = cur.fetchone()
        return dict(r) if r else None

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
            'INSERT INTO usuarios (nombre, email, contraseña, sala, turno) VALUES (%s,%s,%s,%s,%s) RETURNING id_usuario',
            (nombre, email, contraseña, sala, turno))
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

# ─── ALUMNOS ─────────────────────────────

def registrar_alumno(id_usuario, nombre, apellido):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO alumnos (id_usuario, nombre, apellido) VALUES (%s,%s,%s) RETURNING id_alumno',
            (id_usuario, nombre, apellido))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_alumnos(id_usuario):
    conn = conectar()
    try:
        return fetch_all(conn,
            'SELECT id_alumno, nombre, apellido FROM alumnos WHERE id_usuario = %s ORDER BY apellido, nombre',
            (id_usuario,))
    finally:
        conn.close()

def eliminar_alumno(id_alumno, id_usuario):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM alumnos WHERE id_alumno = %s AND id_usuario = %s', (id_alumno, id_usuario))
        execute(conn, 'DELETE FROM observaciones WHERE id_alumno = %s', (id_alumno,))
        conn.commit()
    finally:
        conn.close()

# ─── ACTIVIDADES ─────────────────────────

def crear_actividad(id_usuario, nombre, area, fecha=None, id_unidad=None):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO actividades (id_usuario, nombre, area, fecha, id_unidad) VALUES (%s,%s,%s,%s,%s) RETURNING id_actividad',
            (id_usuario, nombre, area, fecha or date.today().isoformat(), id_unidad))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_actividades_dia(id_usuario, fecha=None):
    conn = conectar()
    try:
        if fecha:
            rows = fetch_all(conn,
                'SELECT a.*, u.titulo as unidad_titulo FROM actividades a LEFT JOIN unidades u ON a.id_unidad = u.id_unidad WHERE a.id_usuario = %s AND a.fecha = %s ORDER BY a.area, a.nombre',
                (id_usuario, fecha))
        else:
            rows = fetch_all(conn,
                "SELECT a.*, u.titulo as unidad_titulo FROM actividades a LEFT JOIN unidades u ON a.id_unidad = u.id_unidad WHERE a.id_usuario = %s AND a.fecha = CURRENT_DATE ORDER BY a.area, a.nombre",
                (id_usuario,))
        return rows
    finally:
        conn.close()

def actualizar_actividad(id_actividad, id_usuario, nombre=None, area=None):
    conn = conectar()
    try:
        if nombre and area:
            execute(conn, 'UPDATE actividades SET nombre = %s, area = %s WHERE id_actividad = %s AND id_usuario = %s',
                    (nombre, area, id_actividad, id_usuario))
        elif nombre:
            execute(conn, 'UPDATE actividades SET nombre = %s WHERE id_actividad = %s AND id_usuario = %s',
                    (nombre, id_actividad, id_usuario))
        elif area:
            execute(conn, 'UPDATE actividades SET area = %s WHERE id_actividad = %s AND id_usuario = %s',
                    (area, id_actividad, id_usuario))
        conn.commit()
    finally:
        conn.close()

def crear_actividades_multi(id_usuario, actividades, fecha=None):
    conn = conectar()
    ids = []
    try:
        f = fecha or date.today().isoformat()
        for act in actividades:
            uid = execute_return(conn,
                'INSERT INTO actividades (id_usuario, nombre, area, fecha) VALUES (%s,%s,%s,%s) RETURNING id_actividad',
                (id_usuario, act['nombre'], act.get('area', 'Identidad y Convivencia'), f))
            ids.append(uid)
        conn.commit()
        return ids
    finally:
        conn.close()

def eliminar_actividad(id_actividad, id_usuario):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM actividades WHERE id_actividad = %s AND id_usuario = %s', (id_actividad, id_usuario))
        conn.commit()
    finally:
        conn.close()

# ─── UNIDADES DIDÁCTICAS ──────────────────

def crear_unidad(id_usuario, titulo, contenido, ruta_archivo=None):
    conn = conectar()
    try:
        uid = execute_return(conn,
            'INSERT INTO unidades (id_usuario, titulo, contenido, ruta_archivo) VALUES (%s,%s,%s,%s) RETURNING id_unidad',
            (id_usuario, titulo, contenido, ruta_archivo))
        conn.commit()
        return uid
    finally:
        conn.close()

def obtener_unidades(id_usuario):
    conn = conectar()
    try:
        return fetch_all(conn,
            'SELECT * FROM unidades WHERE id_usuario = %s ORDER BY fecha_creacion DESC',
            (id_usuario,))
    finally:
        conn.close()

def obtener_unidad(id_unidad, id_usuario):
    conn = conectar()
    try:
        return fetch_one(conn,
            'SELECT * FROM unidades WHERE id_unidad = %s AND id_usuario = %s',
            (id_unidad, id_usuario))
    finally:
        conn.close()

def actualizar_unidad(id_unidad, id_usuario, titulo, contenido):
    conn = conectar()
    try:
        execute(conn,
            'UPDATE unidades SET titulo = %s, contenido = %s WHERE id_unidad = %s AND id_usuario = %s',
            (titulo, contenido, id_unidad, id_usuario))
        conn.commit()
    finally:
        conn.close()

def eliminar_unidad(id_unidad, id_usuario):
    conn = conectar()
    try:
        execute(conn, 'DELETE FROM unidades WHERE id_unidad = %s AND id_usuario = %s',
                (id_unidad, id_usuario))
        conn.commit()
    finally:
        conn.close()

# ─── STATS ────────────────────────────────

def obtener_stats(id_usuario):
    conn = conectar()
    try:
        total_alumnos = fetch_one(conn,
            'SELECT COUNT(*) as count FROM alumnos WHERE id_usuario = %s', (id_usuario,))['count']
        obs_hoy = fetch_one(conn,
            "SELECT COUNT(*) as count FROM observaciones o JOIN alumnos al ON o.id_alumno = al.id_alumno WHERE al.id_usuario = %s AND date(o.fecha) = CURRENT_DATE",
            (id_usuario,))['count']
        total_obs = fetch_one(conn,
            'SELECT COUNT(*) as count FROM observaciones o JOIN alumnos al ON o.id_alumno = al.id_alumno WHERE al.id_usuario = %s',
            (id_usuario,))['count']
        informes = fetch_one(conn,
            'SELECT COUNT(*) as count FROM informes_finales i JOIN alumnos al ON i.id_alumno = al.id_alumno WHERE al.id_usuario = %s',
            (id_usuario,))['count']
        return {
            'total_alumnos': total_alumnos,
            'observaciones_hoy': obs_hoy,
            'total_observaciones': total_obs,
            'total_informes': informes,
        }
    finally:
        conn.close()

def renombrar_area(id_usuario, area_vieja, area_nueva):
    conn = conectar()
    try:
        execute(conn, 'UPDATE actividades SET area = %s WHERE id_usuario = %s AND area = %s',
                (area_nueva, id_usuario, area_vieja))
        conn.commit()
    finally:
        conn.close()

def obtener_areas_usuario(id_usuario):
    conn = conectar()
    try:
        rows = fetch_all(conn,
            "SELECT DISTINCT area FROM actividades WHERE id_usuario = %s AND area != '' ORDER BY area",
            (id_usuario,))
        areas = [r['area'] for r in rows]
        if not areas:
            areas = ['Identidad y Convivencia', 'Lenguaje y Literatura', 'Matemáticas',
                     'Ciencias Sociales, Ciencias Naturales y Tecnología']
        return areas
    finally:
        conn.close()

# ─── OBSERVACIONES ───────────────────────

def guardar_observacion(id_alumno, id_actividad, nota_cruda, tipo='texto', ruta_audio=None):
    conn = conectar()
    try:
        execute(conn,
            'INSERT INTO observaciones (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio) VALUES (%s,%s,%s,%s,%s)',
            (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio))
        conn.commit()
    finally:
        conn.close()

def eliminar_observacion(id_observacion):
    conn = conectar()
    try:
        ruta = fetch_one(conn, 'SELECT ruta_audio FROM observaciones WHERE id_observacion = %s', (id_observacion,))
        if ruta:
            execute(conn, 'DELETE FROM observaciones WHERE id_observacion = %s', (id_observacion,))
            conn.commit()
            return ruta['ruta_audio']
        return None
    finally:
        conn.close()

def eliminar_observaciones_multi(ids):
    conn = conectar()
    try:
        placeholders = ','.join(['%s'] * len(ids))
        rows = fetch_all(conn, f'SELECT ruta_audio FROM observaciones WHERE id_observacion IN ({placeholders})', ids)
        execute(conn, f'DELETE FROM observaciones WHERE id_observacion IN ({placeholders})', ids)
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

def obtener_todas_observaciones_dia(id_usuario, fecha=None):
    conn = conectar()
    try:
        if fecha:
            rows = fetch_all(conn,
                '''SELECT o.*, al.nombre as al_nombre, al.apellido as al_apellido,
                          a.nombre as act_nombre, a.area
                   FROM observaciones o
                   JOIN alumnos al ON o.id_alumno = al.id_alumno
                   LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
                   WHERE al.id_usuario = %s AND date(o.fecha) = %s
                   ORDER BY al.apellido, al.nombre, o.fecha''', (id_usuario, fecha))
        else:
            rows = fetch_all(conn,
                '''SELECT o.*, al.nombre as al_nombre, al.apellido as al_apellido,
                          a.nombre as act_nombre, a.area
                   FROM observaciones o
                   JOIN alumnos al ON o.id_alumno = al.id_alumno
                   LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
                   WHERE al.id_usuario = %s AND date(o.fecha) = CURRENT_DATE
                   ORDER BY al.apellido, al.nombre, o.fecha''', (id_usuario,))
        return rows
    finally:
        conn.close()

# ─── INFORMES ─────────────────────────────

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
