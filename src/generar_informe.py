import os
import re
import unicodedata
from openai import OpenAI
from src.config import GROQ_API_KEY
from src.informe_utils import quitar_linea_faltas
from src.db import conectar, fetch_all, fetch_one, hoy

AREAS_INFORME = [
    'IDENTIDAD Y CONVIVENCIA',
    'LENGUAJE Y LITERATURA',
    'MATEMÁTICAS',
    'CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA',
]

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MODELO_INFORMES = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')

# Mes hasta el cual corre la primera etapa (receso invernal en Argentina).
ULTIMO_MES_PRIMERA_ETAPA = 7


def obtener_datos_alumno(id_alumno):
    conn = conectar()
    try:
        # Sala y turno salen de la sala del alumno (una docente puede tener varias).
        alumno = fetch_one(conn, '''
            SELECT al.nombre, al.apellido, al.genero, al.id_usuario,
                   COALESCE(s.sala, u.sala) AS sala, COALESCE(s.turno, u.turno) AS turno,
                   u.nombre AS docente
            FROM alumnos al
            JOIN usuarios u ON al.id_usuario = u.id_usuario
            LEFT JOIN salas_docente s ON s.id_sala = al.id_sala
            WHERE al.id_alumno = %s
        ''', (id_alumno,))
        if not alumno:
            return None, [], []
        notas = fetch_all(conn, '''
            SELECT a.area, a.nombre as act_nombre, o.nota_cruda, o.fecha
            FROM observaciones o
            LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
            WHERE o.id_alumno = %s
            ORDER BY o.fecha
        ''', (id_alumno,))
        companeros = fetch_all(conn, '''
            SELECT nombre, apellido FROM alumnos
            WHERE id_usuario = %s AND id_alumno <> %s
        ''', (alumno['id_usuario'], id_alumno))
        return alumno, notas, companeros
    finally:
        conn.close()


def etapa_actual(fecha=None):
    """Devuelve (año, 'PRIMERA'|'SEGUNDA') según la fecha de generación."""
    fecha = fecha or hoy()
    etapa = 'PRIMERA' if fecha.month <= ULTIMO_MES_PRIMERA_ETAPA else 'SEGUNDA'
    return fecha.year, etapa


_VARIANTES = {
    'a': 'aáàäâ', 'e': 'eéèëê', 'i': 'iíìïî', 'o': 'oóòöô', 'u': 'uúùüû',
}


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')


def _patron_palabra(palabra):
    """Regex que encuentra la palabra completa sin importar mayúsculas ni tildes."""
    partes = []
    for c in _sin_tildes(palabra).lower():
        if c in _VARIANTES:
            partes.append('[' + _VARIANTES[c] + ']')
        else:
            partes.append(re.escape(c))
    return r'(?<!\w)' + ''.join(partes) + r'(?!\w)'


def _palabras_de(*textos):
    palabras = set()
    for t in textos:
        for p in re.split(r'[\s\-]+', t or ''):
            p = p.strip(".,;:'\"()")
            # Palabras muy cortas ("de", "la") darían reemplazos indebidos.
            if len(p) >= 3:
                palabras.add(p)
    return palabras


def anonimizar(texto, nombre, apellido, otros_nombres=(), docente=None):
    """Quita del texto los datos que identifican a chicos y docente antes de
    enviarlo al proveedor de IA. El alumno pasa a ser ALUMNO; compañeros y
    docente, referencias genéricas."""
    reemplazos = [(p, 'ALUMNO') for p in _palabras_de(nombre, apellido)]
    usadas = {_sin_tildes(p).lower() for p, _ in reemplazos}
    for otro in otros_nombres:
        for p in _palabras_de(otro):
            clave = _sin_tildes(p).lower()
            if clave not in usadas:
                reemplazos.append((p, 'un compañero'))
                usadas.add(clave)
    for p in _palabras_de(docente):
        if _sin_tildes(p).lower() not in usadas:
            reemplazos.append((p, 'la docente'))
    # Primero las palabras más largas, para no cortar nombres compuestos.
    reemplazos.sort(key=lambda r: len(r[0]), reverse=True)
    for palabra, marcador in reemplazos:
        texto = re.sub(_patron_palabra(palabra), marcador, texto, flags=re.IGNORECASE)
    # Nombre y apellido seguidos quedan como un solo marcador.
    texto = re.sub(r'ALUMNO(?:\s+ALUMNO)+', 'ALUMNO', texto)
    texto = re.sub(r'un compañero(?:\s+un compañero)+', 'un compañero', texto)
    return texto


def instruccion_genero(genero):
    if genero == 'F':
        return ('Es una nena: escribí todo en femenino ("la alumna", "atenta", "cuidadosa", '
                '"la guía"), pero usá igual la palabra exacta ALUMNO como marcador de su nombre.')
    if genero == 'M':
        return 'Es un nene: escribí en masculino ("el alumno", "atento", "cuidadoso").'
    return ('No sabemos si es nena o nene: evitá adjetivos y pronombres con género cuando puedas '
            '(por ejemplo "demuestra interés" en lugar de "está interesado") y usá ALUMNO como sujeto.')


def formatear_informe_ia(id_alumno):
    if not GROQ_API_KEY or '...' in GROQ_API_KEY:
        raise RuntimeError('Falta configurar GROQ_API_KEY en las variables de entorno del servidor.')

    alumno, notas, companeros = obtener_datos_alumno(id_alumno)
    if not alumno:
        return None

    nombre, apellido, sala, turno, docente = alumno['nombre'], alumno['apellido'], alumno['sala'], alumno['turno'], alumno['docente']
    nombre_completo = ' '.join(parte for parte in (nombre, apellido) if parte).strip()
    anio, etapa = etapa_actual()

    obs_por_area = {a: [] for a in AREAS_INFORME}
    areas_map = {
        'Identidad y Convivencia': 'IDENTIDAD Y CONVIVENCIA',
        'Lenguaje y Literatura': 'LENGUAJE Y LITERATURA',
        'Matemáticas': 'MATEMÁTICAS',
        'Ciencias Sociales, Ciencias Naturales y Tecnología': 'CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA',
    }
    for n in notas:
        area_db = n['area'] or ''
        area_informe = areas_map.get(area_db, 'IDENTIDAD Y CONVIVENCIA')
        act_label = f"[{n['act_nombre'] or 'Sin actividad'}]" if n['act_nombre'] else ''
        obs_por_area[area_informe].append(
            f"- {n['nota_cruda']} {act_label}"
        )

    texto_observaciones = ""
    for area in AREAS_INFORME:
        lista = obs_por_area[area]
        if lista:
            texto_observaciones += f"\n{area}:\n" + "\n".join(lista) + "\n"

    # Evita reenviar al proveedor los nombres del alumno, de sus compañeros y de la docente.
    texto_observaciones_ia = anonimizar(
        texto_observaciones, nombre, apellido,
        otros_nombres=[f"{c['nombre']} {c['apellido']}" for c in companeros],
        docente=docente,
    )

    system_prompt = "Sos un docente de nivel inicial argentino. Generá informes evaluativos formales pero cálidos, siempre en positivo."
    user_prompt = f"""Generá un informe evaluativo para ALUMNO siguiendo EXACTAMENTE este formato.
No incluyas nombres, apellidos, nombres de docentes, salas ni otros datos identificatorios reales.

INFORMES EVALUATIVOS
INFORME {anio} - {etapa} ETAPA
Sala: SALA - Docente: DOCENTE - Turno: TURNO

ALUMNO

IDENTIDAD Y CONVIVENCIA:
[Párrafo de 4-6 líneas]

LENGUAJE Y LITERATURA:
[Párrafo de 4-6 líneas]

MATEMÁTICAS:
[Párrafo de 4-6 líneas]

CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA:
[Párrafo de 4-6 líneas]

REGLAS (obligatorio):
- {instruccion_genero(alumno.get('genero'))}
- Cada párrafo 4-6 líneas
- Lenguaje formal pero cálido, SIEMPRE EN POSITIVO
- Usá frases como "se está iniciando en...", "paulatinamente logra...", "disfruta de...", "logró...", "está en proceso de...", "presenta avances en...", "necesita del estímulo de la docente para...", "se observan progresos en..."
- Nombrá al alumno como "ALUMNO" dentro de los párrafos
- Basate en las observaciones de abajo
- Si un área no tiene observaciones, escribí un párrafo genérico positivo
- NO incluyas nada más que el informe
- **NUNCA menciones nombres de actividades, tareas, ejercicios o unidades**. No uses frases como "en la actividad", "realizó la actividad", "participó en la tarea", "en el ejercicio", etc. El informe debe hablar de LOGROS y PROCESOS del alumno, no de actividades puntuales.
- **NUNca uses el formato "Actividad: X" ni listes actividades.** Sintetizá las observaciones en un texto fluido como el ejemplo de abajo.
- No incluyas faltas, inasistencias ni asistencia.

EJEMPLO DE ESTILO (modelo real de informes 2025):
--- INICIO EJEMPLO ---
IDENTIDAD Y CONVIVENCIA

Felipe se adaptó de manera positiva al jardín. En su interacción social, ha logrado establecer conexión con compañeros que comparten sus mismas características e intereses. En ocasiones imita conductas, que, si bien es un comportamiento común a esta edad ya que es una forma de aprendizaje y desarrollo social, la docente lo fue guiando en la diferenciación de conductas favorables para determinados momentos.

Participó en la construcción de los acuerdos de convivencia, a veces es necesario recordárselo. Se está iniciando en el juego reglado, el respeto de las reglas del mismo y del tiempo de espera.

Disfruta del juego libre en el patio. Pone en práctica hábitos de higiene y orden, siendo más cuidadoso con sus pertenencias y organizado al momento de preparar la merienda como de trabajar.

En arte, se observan progresos en el control de sus trazos, colorea sin realizar descargas excesivas, lo que indica una mayor precisión y conciencia espacial. Dedica más tiempo a sus producciones, demostrando un mayor interés y concentración.

LENGUAJE Y LITERATURA

Presenta un desarrollo comunicativo en proceso, mejorando la pronunciación de algunas palabras. En las actividades grupales necesita del estímulo de la docente para participar, debido a que se dispersa con facilidad lo que a veces interfiere en su interacción o trabajo colaborativo.

Demuestra avances significativos en el reconocimiento y la denominación de su entorno. Reconoce y nombra los colores y objetos que se le presentan, lo que indica una buena capacidad de asociación y memoria visual. Está incorporando nuevas palabras a su vocabulario.

En los momentos de lectura de cuentos, su tiempo de escucha es parcial. Los juegos lingüísticos, cuentos cortos e instrucciones simples son actividades que fueron favoreciendo su escucha. Para fomentar su participación oral, necesita del estímulo de la docente.

MATEMÁTICAS

En actividades de motricidad fina, demuestra creatividad en la manipulación, manifestando una creciente intencionalidad en el proceso de modelar. Va evidenciando desarrollo en la motricidad fina y coordinación ojo-mano necesarios para futuros aprendizajes.

En cuanto a la serie numérica, logra el recitado oral hasta el número 5, realizando una correspondencia término a término hasta ese punto. Al avanzar omite números, lo que indica que está afianzando los primeros conceptos de conteo pero aún está en proceso de consolidar la secuencia numérica completa.

Respecto a las nociones espaciales, está en proceso de incorporar conceptos como "adentro" y "afuera". Logra diferenciar tamaños en grande-pequeño y mucho-poco utilizando la percepción.

CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA

Se encuentra en vías de comprender el paso del tiempo, organizando acciones a partir de referencias como "antes", "ahora", "después". Se está iniciando en el reconocimiento y valoración de los símbolos patrios.

Participó y disfrutó junto con su familia en la confección de la bandera, trabajando en conjunto.

A partir de la observación diaria, logra reconocer y dar cuenta de algunos fenómenos naturales del ambiente como la lluvia, el viento, el sol, entre otros; estableciendo relaciones entre estos fenómenos y las acciones cotidianas. Demostró interés por identificar y nombrar animales del mar, participando de actividades que le permitieron conocer otros tipos de animales también.
--- FIN EJEMPLO ---

IMPORTANTE: El ejemplo es solo para el ESTILO. NO copies el contenido. Usá las observaciones reales del alumno de abajo para escribir párrafos originales.

OBSERVACIONES DEL ALUMNO:
{texto_observaciones_ia}"""

    response = client.chat.completions.create(
        model=MODELO_INFORMES,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_completion_tokens=4096,
    )
    texto = response.choices[0].message.content
    if not texto:
        return None
    # Los datos identificatorios se incorporan localmente, no se envían al proveedor.
    texto = re.sub(r'\bALUMN[OA]\b', lambda _: nombre_completo, texto)
    texto = re.sub(r'\bSALA\b', lambda _: sala or '', texto)
    texto = re.sub(r'\bDOCENTE\b', lambda _: docente or '', texto)
    texto = re.sub(r'\bTURNO\b', lambda _: turno or '', texto)
    return quitar_linea_faltas(texto)

if __name__ == '__main__':
    print(formatear_informe_ia(1))
