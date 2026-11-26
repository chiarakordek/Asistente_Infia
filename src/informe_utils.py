import re
from datetime import date, datetime

try:
    from zoneinfo import ZoneInfo
    _ZONA = ZoneInfo('America/Argentina/Buenos_Aires')
except Exception:
    _ZONA = None

# Encabezado del informe con cualquier año y etapa (también reconoce informes viejos con "2025").
RE_ENCABEZADO = re.compile(r"INFORME\s+\d{4}\s*-\s*[A-ZÁÉÍÓÚÑ ]*ETAPA", re.IGNORECASE)


def quitar_linea_faltas(contenido):
    """Retira el campo de faltas de informes nuevos y ya guardados."""
    if not contenido:
        return contenido
    return re.sub(
        r"^\s*(?:FALTAS|INASISTENCIAS|AUSENCIAS)\s*:[^\r\n]*(?:\r?\n|$)",
        "",
        contenido,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()


def _hoy():
    return datetime.now(_ZONA).date() if _ZONA else date.today()


def periodo_informe(fecha=None):
    """Año lectivo y etapa del informe según la fecha (calendario escolar argentino).

    - Marzo a julio: PRIMERA ETAPA (informes de mitad de año).
    - Agosto a diciembre: SEGUNDA ETAPA (cierre del año).
    - Enero y febrero: todavía es la SEGUNDA ETAPA del año lectivo anterior.
    """
    fecha = fecha or _hoy()
    if fecha.month <= 2:
        return fecha.year - 1, 'SEGUNDA ETAPA'
    if fecha.month <= 7:
        return fecha.year, 'PRIMERA ETAPA'
    return fecha.year, 'SEGUNDA ETAPA'


def encabezado_informe(fecha=None):
    anio, etapa = periodo_informe(fecha)
    return f"INFORME {anio} - {etapa}"


def fijar_encabezado(contenido, fecha=None):
    """Asegura que el encabezado tenga el año y la etapa correctos aunque el modelo copie otro."""
    if not contenido:
        return contenido
    return RE_ENCABEZADO.sub(encabezado_informe(fecha), contenido, count=1)
