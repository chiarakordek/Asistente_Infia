import re


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
