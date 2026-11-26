import io
import unittest
import zipfile
from pathlib import Path

from src.informe_modelo import (
    MAX_MODELO,
    ModeloInvalido,
    anonimizar_modelo,
    construir_prompt_modelo,
    es_titulo,
    extraer_texto_docx,
    limpiar_modelo,
    observaciones_por_area,
    texto_de_archivo,
)

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def docx_con(parrafos):
    """Arma un .docx mínimo en memoria con los párrafos dados."""
    cuerpo = ''.join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in parrafos)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body>{cuerpo}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('word/document.xml', xml)
    return buf.getvalue()


class LecturaModeloTest(unittest.TestCase):
    def test_limpia_espacios_y_saltos(self):
        self.assertEqual(limpiar_modelo('  TÍTULO \r\n\r\n\r\n\r\nTexto   con  espacios\t'), 'TÍTULO\n\nTexto con espacios')
        self.assertEqual(len(limpiar_modelo('x' * (MAX_MODELO + 500))), MAX_MODELO)
        self.assertEqual(limpiar_modelo(None), '')

    def test_lee_word(self):
        texto = extraer_texto_docx(docx_con(['INFORME FINAL', 'PRÁCTICAS DEL LENGUAJE', 'ALUMNO disfruta de los cuentos.']))
        self.assertEqual(texto, 'INFORME FINAL\nPRÁCTICAS DEL LENGUAJE\nALUMNO disfruta de los cuentos.')

    def test_word_roto(self):
        with self.assertRaises(ModeloInvalido):
            extraer_texto_docx(b'no es un zip')

    def test_archivos(self):
        self.assertEqual(texto_de_archivo('modelo.TXT', 'Matemática'.encode('latin-1')), 'Matemática')
        self.assertIn('ALUMNO', texto_de_archivo('Informe.docx', docx_con(['ALUMNO juega'])))
        with self.assertRaises(ModeloInvalido):
            texto_de_archivo('informe.pdf', b'%PDF-1.4')
        with self.assertRaises(ModeloInvalido):
            texto_de_archivo('grande.txt', b'x' * (3 * 1024 * 1024))


class AnonimizarTest(unittest.TestCase):
    def test_reemplaza_alumnos_y_docente(self):
        texto = 'Lucía Pérez comparte con Mateo. Docente: Sofía Gómez. LUCIA juega.'
        res = anonimizar_modelo(texto, ['Lucía Pérez', 'Mateo García'], 'Sofía Gómez')
        for nombre in ('Lucía', 'Pérez', 'Mateo', 'Sofía', 'Gómez', 'LUCIA'):
            self.assertNotIn(nombre, res)
        self.assertIn('ALUMNO comparte con ALUMNO', res)
        self.assertIn('DOCENTE DOCENTE', res)

    def test_no_corta_palabras_ni_nombres_cortos(self):
        res = anonimizar_modelo('Ana juega en la Mateoteca con Li.', ['Ana', 'Mateo', 'Li'])
        self.assertIn('Mateoteca', res)
        self.assertIn('Li.', res)
        self.assertTrue(res.startswith('ALUMNO juega'))


class PromptModeloTest(unittest.TestCase):
    def test_agrupa_por_las_areas_de_la_docente(self):
        notas = [
            {'area': 'Prácticas del Lenguaje', 'act_nombre': 'Ronda', 'nota_cruda': 'Cuenta un cuento.'},
            {'area': 'Educación Artística', 'act_nombre': None, 'nota_cruda': 'Pinta con témperas.'},
            {'area': None, 'act_nombre': None, 'nota_cruda': 'Ayuda a ordenar.'},
        ]
        obs = observaciones_por_area(notas)
        self.assertIn('Prácticas del Lenguaje:\n- Cuenta un cuento. [Ronda]', obs)
        self.assertIn('Educación Artística:\n- Pinta con témperas.', obs)
        self.assertIn('Sin área asignada:\n- Ayuda a ordenar.', obs)

    def test_prompt_incluye_modelo_observaciones_y_periodo(self):
        prompt = construir_prompt_modelo('MI MODELO', '- obs', 'INFORME 2026 - SEGUNDA ETAPA')
        self.assertIn('MI MODELO', prompt)
        self.assertIn('- obs', prompt)
        self.assertIn('INFORME 2026 - SEGUNDA ETAPA', prompt)
        self.assertIn('NO COPIES DEL MODELO', prompt)

    def test_titulos_de_cualquier_formato(self):
        for t in ('PRÁCTICAS DEL LENGUAJE', 'EDUCACIÓN ARTÍSTICA:', 'IDENTIDAD Y CONVIVENCIA'):
            self.assertTrue(es_titulo(t), t)
        for t in ('Lucía Pérez', 'ALUMNO disfruta de los cuentos', '', '12/11', 'A' * 90):
            self.assertFalse(es_titulo(t), t)


class LimpiezaMarkdownTest(unittest.TestCase):
    def test_saca_asteriscos_y_titulos_markdown(self):
        from src.informe_utils import quitar_linea_faltas
        texto = '**\n**INFORMES EVALUATIVOS**\n## IDENTIDAD Y CONVIVENCIA\nLucía **participa** con `alegría`.\nFALTAS: 3\n*'
        limpio = quitar_linea_faltas(texto)
        self.assertNotIn('*', limpio)
        self.assertNotIn('#', limpio)
        self.assertNotIn('`', limpio)
        self.assertNotIn('FALTAS', limpio)
        self.assertIn('INFORMES EVALUATIVOS\nIDENTIDAD Y CONVIVENCIA\nLucía participa con alegría.', limpio)

    def test_respeta_texto_sin_markdown(self):
        from src.informe_utils import limpiar_markdown
        texto = 'IDENTIDAD Y CONVIVENCIA\nComparte con sus pares - y espera su turno.'
        self.assertEqual(limpiar_markdown(texto), texto)


class IntegracionTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding='utf-8')

    def test_rutas_boton_y_columna(self):
        app = self.read('app.py')
        self.assertIn("@app.route('/api/informe-modelo', methods=['PUT'])", app)
        self.assertIn("@app.route('/api/informe-modelo/archivo', methods=['POST'])", app)
        self.assertIn('informe_modelo TEXT', self.read('src/db.py'))
        alumno = self.read('templates/alumno.html')
        # botón chico arriba de "Generar informe" y ventana emergente, sin páginas nuevas
        self.assertIn('Agregar formato de informe', alumno)
        self.assertIn('id="modalFormato"', alumno)
        self.assertLess(alumno.index('id="formatoBar"'), alumno.index('id="btnGenerar"'))
        self.assertNotIn('/informe-modelo"', self.read('templates/perfil.html'))

    def test_el_generador_usa_el_modelo_anonimizado(self):
        gen = self.read('src/generar_informe.py')
        self.assertIn('anonimizar_modelo(modelo, nombres, docente)', gen)
        self.assertIn('construir_prompt_modelo(', gen)


if __name__ == '__main__':
    unittest.main()
