import unittest
from datetime import date

from src.informe_utils import RE_ENCABEZADO, encabezado_informe, fijar_encabezado, periodo_informe


class PeriodoInformeTest(unittest.TestCase):
    def test_primera_etapa_de_marzo_a_julio(self):
        for mes in (3, 5, 7):
            self.assertEqual(periodo_informe(date(2026, mes, 15)), (2026, 'PRIMERA ETAPA'))

    def test_segunda_etapa_de_agosto_a_diciembre(self):
        for mes in (8, 11, 12):
            self.assertEqual(periodo_informe(date(2026, mes, 15)), (2026, 'SEGUNDA ETAPA'))

    def test_enero_y_febrero_cierran_el_anio_anterior(self):
        self.assertEqual(periodo_informe(date(2027, 1, 10)), (2026, 'SEGUNDA ETAPA'))
        self.assertEqual(periodo_informe(date(2027, 2, 28)), (2026, 'SEGUNDA ETAPA'))

    def test_encabezado(self):
        self.assertEqual(encabezado_informe(date(2026, 11, 25)), 'INFORME 2026 - SEGUNDA ETAPA')
        self.assertEqual(encabezado_informe(date(2027, 6, 1)), 'INFORME 2027 - PRIMERA ETAPA')

    def test_corrige_el_encabezado_que_copie_el_modelo(self):
        texto = 'INFORMES EVALUATIVOS\nINFORME 2025 - PRIMERA ETAPA\nSala: 4 Años A'
        corregido = fijar_encabezado(texto, date(2026, 11, 25))
        self.assertIn('INFORME 2026 - SEGUNDA ETAPA', corregido)
        self.assertNotIn('2025', corregido)
        self.assertTrue(corregido.endswith('Sala: 4 Años A'))

    def test_reconoce_encabezados_viejos_y_nuevos(self):
        for linea in ('INFORME 2025 - PRIMERA ETAPA', 'INFORME 2026 - SEGUNDA ETAPA', 'Informe 2027 - Primera etapa'):
            self.assertTrue(RE_ENCABEZADO.search(linea), linea)
        self.assertIsNone(RE_ENCABEZADO.search('IDENTIDAD Y CONVIVENCIA'))

    def test_sin_contenido(self):
        self.assertEqual(fijar_encabezado(''), '')
        self.assertIsNone(fijar_encabezado(None))


if __name__ == '__main__':
    unittest.main()
