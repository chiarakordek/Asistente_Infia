import os
from openai import OpenAI
from src.config import GROQ_API_KEY
import psycopg2
from psycopg2 import extras

DATABASE_URL = os.environ.get('DATABASE_URL')

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

def fetch_all(sql, params=None):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def fetch_one(sql, params=None):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            r = cur.fetchone()
            return dict(r) if r else None
    finally:
        conn.close()

def obtener_datos_alumno(id_alumno):
    alumno = fetch_one('''
        SELECT al.nombre, al.apellido, u.sala, u.turno, u.nombre as docente
        FROM alumnos al
        JOIN usuarios u ON al.id_usuario = u.id_usuario
        WHERE al.id_alumno = %s
    ''', (id_alumno,))
    if not alumno:
        return None, []
    notas = fetch_all('''
        SELECT a.area, a.nombre as act_nombre, o.nota_cruda, o.fecha
        FROM observaciones o
        LEFT JOIN actividades a ON o.id_actividad = a.id_actividad
        WHERE o.id_alumno = %s
        ORDER BY o.fecha
    ''', (id_alumno,))
    return alumno, notas

def formatear_informe_ia(id_alumno):
    alumno, notas = obtener_datos_alumno(id_alumno)
    if not alumno:
        return None

    nombre, apellido, sala, turno, docente = alumno['nombre'], alumno['apellido'], alumno['sala'], alumno['turno'], alumno['docente']
    nombre_completo = f"{apellido}, {nombre}"

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

    system_prompt = "Sos un docente de nivel inicial argentino. Generá informes evaluativos formales pero cálidos, siempre en positivo."
    user_prompt = f"""Generá un informe evaluativo para {nombre_completo} siguiendo EXACTAMENTE este formato:

INFORMES EVALUATIVOS
INFORME 2025 - PRIMERA ETAPA
Sala: {sala} - Docente: {docente} - Turno: {turno}

{nombre.upper()} {apellido.upper()}

IDENTIDAD Y CONVIVENCIA:
[Párrafo de 4-6 líneas]

LENGUAJE Y LITERATURA:
[Párrafo de 4-6 líneas]

MATEMÁTICAS:
[Párrafo de 4-6 líneas]

CIENCIAS SOCIALES, CIENCIAS NATURALES Y TECNOLOGIA:
[Párrafo de 4-6 líneas]

FALTAS: 0

REGLAS (obligatorio):
- Cada párrafo 4-6 líneas
- Lenguaje formal pero cálido, SIEMPRE EN POSITIVO
- Usá frases como "se está iniciando en...", "paulatinamente logra...", "disfruta de...", "logró...", "está en proceso de...", "presenta avances en...", "necesita del estímulo de la docente para...", "se observan progresos en..."
- Nombrá al alumno como "{nombre}" dentro de los párrafos
- Basate en las observaciones de abajo
- Si un área no tiene observaciones, escribí un párrafo genérico positivo
- NO incluyas nada más que el informe
- **NUNCA menciones nombres de actividades, tareas, ejercicios o unidades**. No uses frases como "en la actividad", "realizó la actividad", "participó en la tarea", "en el ejercicio", etc. El informe debe hablar de LOGROS y PROCESOS del alumno, no de actividades puntuales.
- **NUNca uses el formato "Actividad: X" ni listes actividades.** Sintetizá las observaciones en un texto fluido como el ejemplo de abajo.

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
{texto_observaciones}"""

    for intento in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4096,
            )
            texto = response.choices[0].message.content
            if texto:
                return texto
            return None
        except Exception as e:
            print(f"Error Groq (intento {intento+1}): {e}")
            if intento < 2:
                import time
                time.sleep(3)
            else:
                return None
    return None

if __name__ == '__main__':
    print(formatear_informe_ia(1))
