"""Elimina cuentas cuya solicitud de baja cumplió el período de espera."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.db import eliminar_usuario_completamente, obtener_bajas_vencidas

AUDIO_DIR = os.path.join(ROOT, 'static', 'audios')


def main():
    eliminadas = 0
    for baja in obtener_bajas_vencidas():
        for ruta in eliminar_usuario_completamente(baja['id_usuario']):
            if ruta:
                audio_path = os.path.join(AUDIO_DIR, os.path.basename(ruta))
                if os.path.exists(audio_path):
                    os.remove(audio_path)
        eliminadas += 1
    print(f'Cuentas eliminadas: {eliminadas}')


if __name__ == '__main__':
    main()
