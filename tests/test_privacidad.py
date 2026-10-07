import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PrivacidadTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding='utf-8')

    def test_documentos_legales_publicos(self):
        privacidad = self.read('templates/privacidad.html')
        terminos = self.read('templates/terminos.html')
        self.assertIn('Chiara Agustina Kordek', privacidad)
        self.assertIn('infia.soporte@gmail.com', privacidad)
        self.assertIn('Groq', privacidad)
        self.assertIn('Mercado Pago', privacidad)
        self.assertIn('7 días', privacidad)
        self.assertIn('Términos de Uso', terminos)

    def test_registro_requiere_consentimiento(self):
        registro = self.read('templates/registro.html')
        app = self.read('app.py')
        js = self.read('static/js/app.js')
        self.assertIn('aceptaTerminos', registro)
        self.assertIn("data.get('acepta_terminos')", app)
        self.assertIn('acepta_terminos', js)

    def test_audio_no_se_conserva_despues_de_procesar(self):
        app = self.read('app.py')
        self.assertIn('finally:', app)
        self.assertIn('os.remove(path)', app)
        self.assertIn('ruta_audio=None', app)

    def test_baja_y_cron_configurados(self):
        db = self.read('src/db.py')
        render = self.read('render.yaml')
        script = self.read('scripts/procesar_bajas.py')
        self.assertIn('baja_solicitada_en', db)
        self.assertIn('asistente-informes-limpieza', render)
        self.assertIn('obtener_bajas_vencidas', script)


if __name__ == '__main__':
    unittest.main()
