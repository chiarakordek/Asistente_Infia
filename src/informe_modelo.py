"""Informe modelo: la docente carga un informe propio y la IA copia su formato.

Todo lo de este módulo es puro (sin base de datos ni red) para poder testearlo.
"""
import io
import re
import unicodedata
import zipfile
from xml.etree import ElementTree

MAX_MODELO = 8000
MAX_ARCHIVO_BYTES = 2 * 1024 * 1024

_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class ModeloInvalido(ValueError):
    """El archivo o el texto del modelo no se pudo usar."""


def limpiar_modelo(texto):
    """Normaliza saltos de línea y espacios; recorta al máximo permitido."""
    if not texto:
        return ''
    texto = texto.replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ')
    lineas = [re.sub(r'[  ]+', ' ', linea).strip() for linea in texto.split('\n')]
    texto = re.sub(r'\n{3,}', '\n\n', '\n'.join(lineas)).strip()
    return texto[:MAX_MODELO]


def extraer_texto_docx(contenido):
    """Extrae el texto de un .docx (párrafos y tablas) sin dependencias externas."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            xml = z.read('word/document.xml')
    except (zipfile.BadZipFile, KeyError) as e:
        raise ModeloInvalido('No pudimos leer el archivo de Word. Probá copiando y pegando el texto.') from e
    raiz = ElementTree.fromstring(xml)
    parrafos = []
    for p in raiz.iter(f'{_W}p'):
        partes = []
        for nodo in p.iter():
            if nodo.tag == f'{_W}t' and nodo.text:
                partes.append(nodo.text)
            elif nodo.tag == f'{_W}tab':
                partes.append(' ')
            elif nodo.tag in (f'{_W}br', f'{_W}cr'):
                partes.append('\n')
        parrafos.append(''.join(partes))
    return limpiar_modelo('\n'.join(parrafos))


def texto_de_archivo(nombre, contenido):
    """Devuelve el texto de un archivo subido (.docx o .txt)."""
    if len(contenido) > MAX_ARCHIVO_BYTES:
        raise ModeloInvalido('El archivo es muy grande. Subí un informe de hasta 2 MB.')
    nombre = (nombre or '').lower()
    if nombre.endswith('.docx'):
        return extraer_texto_docx(contenido)
    if nombre.endswith('.txt'):
        for codificacion in ('utf-8-sig', 'latin-1'):
            try:
                return limpiar_modelo(contenido.decode(codificacion))
            except UnicodeDecodeError:
                continue
    raise ModeloInvalido('Por ahora aceptamos Word (.docx) o texto (.txt). Si es PDF, copiá y pegá el texto.')


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')


def anonimizar_modelo(texto, nombres_alumnos=(), nombre_docente=''):
    """Reemplaza nombres conocidos (alumnos de la docente y la docente) antes de enviar el modelo a la IA."""
    if not texto:
        return texto
    reemplazos = []
    for nombre in nombres_alumnos:
        for parte in (nombre or '').split():
            if len(parte) >= 3:
                reemplazos.append((parte, 'ALUMNO'))
    for parte in (nombre_docente or '').split():
        if len(parte) >= 3:
            reemplazos.append((parte, 'DOCENTE'))
    # primero los más largos, para no cortar nombres compuestos
    reemplazos.sort(key=lambda r: len(r[0]), reverse=True)
    for original, marcador in reemplazos:
        patron = re.compile(rf'(?<!\w){re.escape(original)}(?!\w)', re.IGNORECASE)
        texto = patron.sub(marcador, texto)
        sin_tilde = _sin_tildes(original)
        if sin_tilde != original:
            texto = re.compile(rf'(?<!\w){re.escape(sin_tilde)}(?!\w)', re.IGNORECASE).sub(marcador, texto)
    return re.sub(r'ALUMNO(\s+ALUMNO)+', 'ALUMNO', texto)


def observaciones_por_area(notas):
    """Agrupa las observaciones con el nombre real del área de la docente (sin forzar áreas fijas)."""
    grupos = {}
    for n in notas:
        area = (n.get('area') or '').strip() or 'Sin área asignada'
        etiqueta = f" [{n['act_nombre']}]" if n.get('act_nombre') else ''
        grupos.setdefault(area, []).append(f"- {n['nota_cruda']}{etiqueta}")
    return ''.join(f"\n{area}:\n" + '\n'.join(lineas) + '\n' for area, lineas in grupos.items())


def construir_prompt_modelo(modelo, observaciones, encabezado):
    """Pedido a la IA para redactar el informe copiando el formato del modelo de la docente."""
    return f"""Redactá el informe evaluativo de ALUMNO copiando el FORMATO del INFORME MODELO de abajo.

COPIÁ DEL MODELO:
- La estructura: encabezado, títulos y secciones, en el mismo orden y escritos igual (mayúsculas, dos puntos, etc.).
- La extensión aproximada de cada sección.
- La persona gramatical (por ejemplo "ALUMNO participa…" o "Querida familia…"), el tono y la forma de redactar.

NO COPIES DEL MODELO:
- Los hechos, logros ni frases sobre el niño o la niña del modelo: es otra persona.
- Nombres propios: si el modelo tiene nombres, ignoralos.

CONTENIDO:
- Usá SOLO las observaciones de ALUMNO que están al final. Ubicá cada una en la sección del modelo que mejor le corresponda.
- Si una sección del modelo no tiene observaciones, escribí un texto breve, cálido y en positivo, sin inventar hechos concretos.
- Si el modelo indica año y etapa, usá: {encabezado}.
- Donde el modelo tenga datos de la sala, la docente o el turno, escribí SALA, DOCENTE y TURNO.
- Nombrá al alumno siempre como ALUMNO. No incluyas datos identificatorios reales.
- Respondé solo con el informe, en texto plano, sin markdown ni comentarios.

===== INFORME MODELO =====
{modelo}
===== FIN DEL MODELO =====

OBSERVACIONES DE ALUMNO (agrupadas por área):
{observaciones}"""


def es_titulo(linea):
    """Línea de título de sección: corta, en mayúsculas y con letras (sirve para cualquier formato)."""
    t = linea.strip().rstrip(':').strip()
    if not t or len(t) > 80:
        return False
    letras = [c for c in t if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)
