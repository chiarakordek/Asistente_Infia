import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'informes_jardin.db')

# ─── INICIALIZACIÓN DE BASE DE DATOS ─────

def inicializar_bd():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        contraseña TEXT NOT NULL,
        sala TEXT DEFAULT '3 Años B', turno TEXT DEFAULT 'Tarde'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS alumnos (
        id_alumno INTEGER PRIMARY KEY AUTOINCREMENT,
        id_usuario INTEGER NOT NULL, nombre TEXT NOT NULL, apellido TEXT NOT NULL,
        FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS actividades (
        id_actividad INTEGER PRIMARY KEY AUTOINCREMENT,
        id_usuario INTEGER NOT NULL, nombre TEXT NOT NULL,
        area TEXT NOT NULL DEFAULT 'Identidad y Convivencia',
        fecha TEXT NOT NULL DEFAULT (date('now')), id_unidad INTEGER,
        FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS unidades (
        id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
        id_usuario INTEGER NOT NULL, titulo TEXT NOT NULL,
        contenido TEXT NOT NULL, ruta_archivo TEXT,
        fecha_creacion TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS observaciones (
        id_observacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_alumno INTEGER NOT NULL, id_actividad INTEGER,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP, nota_cruda TEXT NOT NULL,
        tipo TEXT DEFAULT 'texto' CHECK(tipo IN ('texto','audio')),
        FOREIGN KEY(id_alumno) REFERENCES alumnos(id_alumno),
        FOREIGN KEY(id_actividad) REFERENCES actividades(id_actividad)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS informes_finales (
        id_informe INTEGER PRIMARY KEY AUTOINCREMENT,
        id_alumno INTEGER, fecha_generacion TEXT DEFAULT CURRENT_TIMESTAMP,
        etapa TEXT NOT NULL, contenido_informe TEXT,
        FOREIGN KEY(id_alumno) REFERENCES alumnos(id_alumno)
    )''')

    # Migraciones
    for col in [('actividades', 'id_unidad'), ('observaciones', 'ruta_audio'), ('unidades', 'ruta_archivo')]:
        try: c.execute(f'ALTER TABLE {col[0]} ADD COLUMN {col[1]} TEXT')
        except: pass

    # Migración: eliminar CHECK constraint de actividades.area
    try:
        row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='actividades'").fetchone()
        if row and 'CHECK' in row[0].upper():
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("CREATE TABLE actividades_temp (id_actividad INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER NOT NULL, nombre TEXT NOT NULL, area TEXT NOT NULL DEFAULT 'Identidad y Convivencia', fecha TEXT NOT NULL DEFAULT (date('now')), id_unidad INTEGER, FOREIGN KEY(id_usuario) REFERENCES usuarios(id_usuario))")
            c.execute("INSERT INTO actividades_temp SELECT * FROM actividades")
            c.execute("DROP TABLE actividades")
            c.execute("ALTER TABLE actividades_temp RENAME TO actividades")
            c.execute("PRAGMA foreign_keys=ON")
    except: pass

    conn.commit()
    conn.close()

inicializar_bd()

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# ─── USUARIOS ────────────────────────────────────────────────

def crear_usuario(nombre, email, contraseña, sala, turno):
    conn = conectar()
    try:
        conn.execute('INSERT INTO usuarios (nombre, email, contraseña, sala, turno) VALUES (?,?,?,?,?)',
                     (nombre, email, contraseña, sala, turno))
        conn.commit()
        return conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def obtener_usuario_por_email(email):
    conn = conectar()
    u = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(u) if u else None

def obtener_usuario_por_id(id_usuario):
    conn = conectar()
    u = conn.execute('SELECT * FROM usuarios WHERE id_usuario = ?', (id_usuario,)).fetchone()
    conn.close()
    return dict(u) if u else None

# ─── ALUMNOS ─────────────────────────────────────────────────

def registrar_alumno(id_usuario, nombre, apellido):
    conn = conectar()
    conn.execute('INSERT INTO alumnos (id_usuario, nombre, apellido) VALUES (?,?,?)',
                 (id_usuario, nombre, apellido))
    conn.commit()
    uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return uid

def obtener_alumnos(id_usuario):
    conn = conectar()
    rows = conn.execute('SELECT id_alumno, nombre, apellido FROM alumnos WHERE id_usuario = ? ORDER BY apellido, nombre',
                        (id_usuario,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def eliminar_alumno(id_alumno, id_usuario):
    conn = conectar()
    conn.execute('DELETE FROM alumnos WHERE id_alumno = ? AND id_usuario = ?', (id_alumno, id_usuario))
    conn.execute('DELETE FROM observaciones WHERE id_alumno = ?', (id_alumno,))
    conn.commit()
    conn.close()

# ─── ACTIVIDADES ─────────────────────────────────────────────

def crear_actividad(id_usuario, nombre, area, fecha=None, id_unidad=None):
    conn = conectar()
    conn.execute('INSERT INTO actividades (id_usuario, nombre, area, fecha, id_unidad) VALUES (?,?,?,?,?)',
                 (id_usuario, nombre, area, fecha or date.today().isoformat(), id_unidad))
    conn.commit()
    uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return uid

def obtener_actividades_dia(id_usuario, fecha=None):
    conn = conectar()
    if fecha:
        rows = conn.execute('''
            SELECT a.*, u.titulo as unidad_titulo
            FROM actividades a
            LEFT JOIN unidades u ON a.id_unidad = u.id_unidad
            WHERE a.id_usuario = ? AND a.fecha = ?
            ORDER BY a.area, a.nombre
        ''', (id_usuario, fecha)).fetchall()
    else:
        rows = conn.execute('''
            SELECT a.*, u.titulo as unidad_titulo
            FROM actividades a
            LEFT JOIN unidades u ON a.id_unidad = u.id_unidad
            WHERE a.id_usuario = ? AND a.fecha = date('now','localtime')
            ORDER BY a.area, a.nombre
        ''', (id_usuario,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def actualizar_actividad(id_actividad, id_usuario, nombre=None, area=None):
    conn = conectar()
    if nombre and area:
        conn.execute('UPDATE actividades SET nombre = ?, area = ? WHERE id_actividad = ? AND id_usuario = ?',
                     (nombre, area, id_actividad, id_usuario))
    elif nombre:
        conn.execute('UPDATE actividades SET nombre = ? WHERE id_actividad = ? AND id_usuario = ?',
                     (nombre, id_actividad, id_usuario))
    elif area:
        conn.execute('UPDATE actividades SET area = ? WHERE id_actividad = ? AND id_usuario = ?',
                     (area, id_actividad, id_usuario))
    conn.commit()
    conn.close()

def crear_actividades_multi(id_usuario, actividades, fecha=None):
    conn = conectar()
    ids = []
    f = fecha or date.today().isoformat()
    for act in actividades:
        cur = conn.execute(
            'INSERT INTO actividades (id_usuario, nombre, area, fecha) VALUES (?,?,?,?)',
            (id_usuario, act['nombre'], act.get('area', 'Identidad y Convivencia'), f)
        )
        ids.append(cur.lastrowid)
    conn.commit()
    conn.close()
    return ids

def eliminar_actividad(id_actividad, id_usuario):
    conn = conectar()
    conn.execute('DELETE FROM actividades WHERE id_actividad = ? AND id_usuario = ?', (id_actividad, id_usuario))
    conn.commit()
    conn.close()

def renombrar_area(id_usuario, area_vieja, area_nueva):
    conn = conectar()
    conn.execute('UPDATE actividades SET area = ? WHERE id_usuario = ? AND area = ?',
                 (area_nueva, id_usuario, area_vieja))
    conn.commit()
    conn.close()

def obtener_areas_usuario(id_usuario):
    conn = conectar()
    rows = conn.execute('''
        SELECT DISTINCT area FROM actividades
        WHERE id_usuario = ? AND area != ''
        ORDER BY area
    ''', (id_usuario,)).fetchall()
    conn.close()
    areas = [r['area'] for r in rows]
    if not areas:
        areas = [
            'Identidad y Convivencia',
            'Lenguaje y Literatura',
            'Matemáticas',
            'Ciencias Sociales, Ciencias Naturales y Tecnología',
        ]
    return areas

# ─── OBSERVACIONES ───────────────────────────────────────────

def guardar_observacion(id_alumno, id_actividad, nota_cruda, tipo='texto', ruta_audio=None):
    conn = conectar()
    conn.execute('INSERT INTO observaciones (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio) VALUES (?,?,?,?,?)',
                 (id_alumno, id_actividad, nota_cruda, tipo, ruta_audio))
    conn.commit()
    conn.close()

def eliminar_observacion(id_observacion):
    conn = conectar()
    row = conn.execute('SELECT ruta_audio FROM observaciones WHERE id_observacion = ?',
                       (id_observacion,)).fetchone()
    if row:
        conn.execute('DELETE FROM observaciones WHERE id_observacion = ?', (id_observacion,))
        conn.commit()
        conn.close()
        return row['ruta_audio']
    conn.close()
    return None

def eliminar_observaciones_multi(ids):
    conn = conectar()
    placeholders = ','.join(['?'] * len(ids))
    rows = conn.execute(f'SELECT ruta_audio FROM observaciones WHERE id_observacion IN ({placeholders})',
                        ids).fetchall()
    conn.execute(f'DELETE FROM observaciones WHERE id_observacion IN ({placeholders})', ids)
    conn.commit()
    conn.close()
    return [r['ruta_audio'] for r in rows if r['ruta_audio']]

def obtener_observaciones_alumno(id_alumno):
    conn = conectar()
    rows = conn.execute('''
        SELECT o.*, a.nombre as act_nombre, a.area
        FROM observaciones o
        LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
        WHERE o.id_alumno = ?
        ORDER BY o.fecha DESC
    ''', (id_alumno,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def obtener_todas_observaciones_dia(id_usuario, fecha=None):
    conn = conectar()
    if fecha:
        rows = conn.execute('''
            SELECT o.*, al.nombre as al_nombre, al.apellido as al_apellido,
                   a.nombre as act_nombre, a.area
            FROM observaciones o
            JOIN alumnos al ON o.id_alumno = al.id_alumno
            LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
            WHERE al.id_usuario = ? AND date(o.fecha) = ?
            ORDER BY al.apellido, al.nombre, o.fecha
        ''', (id_usuario, fecha)).fetchall()
    else:
        rows = conn.execute('''
            SELECT o.*, al.nombre as al_nombre, al.apellido as al_apellido,
                   a.nombre as act_nombre, a.area
            FROM observaciones o
            JOIN alumnos al ON o.id_alumno = al.id_alumno
            LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
            WHERE al.id_usuario = ? AND date(o.fecha) = date('now','localtime')
            ORDER BY al.apellido, al.nombre, o.fecha
        ''', (id_usuario,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── INFORMES ─────────────────────────────────────────────────

def guardar_informe(id_alumno, etapa, contenido):
    conn = conectar()
    conn.execute('INSERT INTO informes_finales (id_alumno, etapa, contenido_informe) VALUES (?,?,?)',
                 (id_alumno, etapa, contenido))
    conn.commit()
    conn.close()

def obtener_informe_reciente(id_alumno):
    conn = conectar()
    row = conn.execute('''
        SELECT * FROM informes_finales
        WHERE id_alumno = ?
        ORDER BY fecha_generacion DESC
        LIMIT 1
    ''', (id_alumno,)).fetchone()
    conn.close()
    return dict(row) if row else None

def actualizar_informe(id_alumno, contenido):
    conn = conectar()
    conn.execute('''
        UPDATE informes_finales
        SET contenido_informe = ?, fecha_generacion = datetime('now','localtime')
        WHERE id_informe = (
            SELECT id_informe FROM informes_finales
            WHERE id_alumno = ?
            ORDER BY fecha_generacion DESC
            LIMIT 1
        )
    ''', (contenido, id_alumno))
    conn.commit()
    conn.close()
