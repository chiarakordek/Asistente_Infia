"""Tests de comportamiento que no necesitan una base de datos real.

Las funciones de acceso a datos se reemplazan con mocks, así que estos tests
verifican la lógica de la app (permisos, privacidad, informe) y no el SQL.
"""
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('FLASK_DEBUG', '1')  # cookies sin "Secure" para el cliente de pruebas
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('GROQ_API_KEY', 'gsk_test_key')

with mock.patch('src.db.inicializar_bd'):
    import app as app_module

from src import generar_informe
from src import db

USUARIO = {
    'id_usuario': 7, 'nombre': 'Laura Gómez', 'email': 'laura@example.com',
    'contraseña': 'pbkdf2:sha256:secreto', 'sala': '4 Años', 'turno': 'Mañana',
    'plan': 'trial', 'motivo_baja': 'privado', 'baja_solicitada_en': None,
    'tutorial_completado': True,
}
SALAS = [{'id_sala': 3, 'nombre': 'Sala Roja', 'sala': '4 Años', 'turno': 'Mañana'}]


class ClienteBase(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.parches = [
            mock.patch.object(app_module, 'obtener_usuario_por_id', return_value=dict(USUARIO)),
            mock.patch.object(app_module, 'obtener_salas_docente', return_value=SALAS),
            mock.patch.object(app_module, 'obtener_bajas_vencidas', return_value=[]),
        ]
        for p in self.parches:
            p.start()
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as s:
            s['user_id'] = USUARIO['id_usuario']

    def tearDown(self):
        for p in self.parches:
            p.stop()


class ApiMeTest(ClienteBase):
    def test_no_expone_hash_ni_datos_internos(self):
        r = self.client.get('/api/me')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data['email'], USUARIO['email'])
        self.assertNotIn('contraseña', data)
        self.assertNotIn('motivo_baja', data)


class AislamientoEntreDocentesTest(ClienteBase):
    """Una docente no puede leer ni generar informes de alumnos ajenos."""

    def test_observaciones_de_alumno_ajeno(self):
        with mock.patch.object(app_module, 'obtener_alumnos', return_value=[{'id_alumno': 1}]), \
             mock.patch.object(app_module, 'obtener_observaciones_alumno') as obs:
            r = self.client.get('/api/observaciones/alumno/99')
        self.assertEqual(r.status_code, 404)
        obs.assert_not_called()

    def test_informe_de_alumno_ajeno(self):
        with mock.patch.object(app_module, 'obtener_alumnos', return_value=[{'id_alumno': 1}]), \
             mock.patch.object(app_module, 'formatear_informe_ia') as generar:
            r = self.client.post('/api/informe/99')
        self.assertEqual(r.status_code, 404)
        generar.assert_not_called()

    def test_genero_de_alumno_ajeno(self):
        with mock.patch.object(app_module, 'obtener_alumnos', return_value=[{'id_alumno': 1}]), \
             mock.patch.object(app_module, 'actualizar_genero_alumno') as actualizar:
            r = self.client.put('/api/alumnos/99/genero', json={'genero': 'F'})
        self.assertEqual(r.status_code, 404)
        actualizar.assert_not_called()

    def test_genero_invalido(self):
        r = self.client.put('/api/alumnos/1/genero', json={'genero': 'X'})
        self.assertEqual(r.status_code, 400)


class SesionDeCuentaEliminadaTest(ClienteBase):
    def test_sesion_de_usuario_inexistente_se_cierra(self):
        with mock.patch.object(app_module, 'obtener_usuario_por_id', return_value=None):
            r = self.client.get('/api/alumnos', headers={'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 401)
        with self.client.session_transaction() as s:
            self.assertNotIn('user_id', s)


class ConsultasPorPedidoTest(ClienteBase):
    def test_usuario_y_salas_se_consultan_una_vez(self):
        with mock.patch.object(app_module, 'obtener_areas_usuario', return_value=[]):
            r = self.client.get('/dashboard')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(app_module.obtener_usuario_por_id.call_count, 1)
        self.assertEqual(app_module.obtener_salas_docente.call_count, 1)


class RateLimitTest(unittest.TestCase):
    def test_respaldo_en_memoria_si_la_base_falla(self):
        app_module._intentos_memoria.clear()
        with mock.patch.object(app_module, 'registrar_intento_acceso', side_effect=RuntimeError('sin base')):
            resultados = [app_module.revisar_rate_limit('1.2.3.4') for _ in range(6)]
        self.assertEqual(resultados, [True] * 5 + [False])

    def test_usa_la_base_cuando_esta_disponible(self):
        with mock.patch.object(app_module, 'registrar_intento_acceso', return_value=False) as reg:
            self.assertFalse(app_module.revisar_rate_limit('5.6.7.8'))
        reg.assert_called_once_with('login:5.6.7.8', app_module._MAX_INTENTOS, app_module._VENTANA_MINUTOS)


class WebhookTest(unittest.TestCase):
    def test_rechaza_secreto_incorrecto(self):
        client = app_module.app.test_client()
        with mock.patch.dict(os.environ, {'MP_WEBHOOK_SECRET': 'abc'}), \
             mock.patch.object(app_module, 'procesar_notificacion') as proc:
            r = client.post('/webhook/mercadopago?secret=otro&data.id=1')
        self.assertEqual(r.status_code, 403)
        proc.assert_not_called()


class AnonimizacionTest(unittest.TestCase):
    def test_reemplaza_alumno_sin_importar_mayusculas_ni_tildes(self):
        texto = 'Martín jugó. martin compartió. MARTIN López pintó. Lopez rió.'
        res = generar_informe.anonimizar(texto, 'Martín', 'López')
        self.assertNotRegex(res.lower(), r'mart[ií]n|l[oó]pez')
        self.assertIn('ALUMNO jugó', res)

    def test_reemplaza_companeros_y_docente(self):
        texto = 'Martín jugó con Sofía Pérez y con sofia. La seño Laura Gómez lo ayudó.'
        res = generar_informe.anonimizar(texto, 'Martín', 'López',
                                         otros_nombres=['Sofía Pérez'], docente='Laura Gómez')
        for nombre in ('Sofía', 'sofia', 'Pérez', 'Laura', 'Gómez'):
            self.assertNotIn(nombre, res)
        self.assertIn('un compañero', res)
        self.assertIn('la docente', res)

    def test_no_toca_palabras_cortas_ni_partes_de_otras_palabras(self):
        res = generar_informe.anonimizar('Ana de la sala come banana.', 'Ana', 'De la Fuente')
        self.assertIn('banana', res)
        self.assertIn(' de la sala', res)
        self.assertTrue(res.startswith('ALUMNO'))


class EtapaYGeneroTest(unittest.TestCase):
    def test_etapa_segun_fecha(self):
        self.assertEqual(generar_informe.etapa_actual(date(2026, 5, 10)), (2026, 'PRIMERA'))
        self.assertEqual(generar_informe.etapa_actual(date(2026, 11, 13)), (2026, 'SEGUNDA'))

    def test_instruccion_de_genero(self):
        self.assertIn('femenino', generar_informe.instruccion_genero('F'))
        self.assertIn('masculino', generar_informe.instruccion_genero('M'))
        self.assertIn('evitá', generar_informe.instruccion_genero(None))


class FormatearInformeTest(unittest.TestCase):
    def test_no_envia_nombres_y_completa_encabezado(self):
        alumno = {'nombre': 'Martina', 'apellido': 'Ruiz', 'genero': 'F', 'id_usuario': 7,
                  'sala': '4 Años', 'turno': 'Mañana', 'docente': 'Laura Gómez'}
        notas = [{'area': 'Matemáticas', 'act_nombre': 'Conteo', 'nota_cruda': 'Martina cuenta hasta 10 con Tomás', 'fecha': None}]
        respuesta = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='INFORME 2026 - SEGUNDA ETAPA\nSala: SALA - Docente: DOCENTE - Turno: TURNO\n\nALUMNA cuenta.'))])
        with mock.patch.object(generar_informe, 'obtener_datos_alumno',
                               return_value=(alumno, notas, [{'nombre': 'Tomás', 'apellido': 'Paz'}])), \
             mock.patch.object(generar_informe, 'etapa_actual', return_value=(2026, 'SEGUNDA')), \
             mock.patch.object(generar_informe.client.chat.completions, 'create', return_value=respuesta) as create:
            texto = generar_informe.formatear_informe_ia(1)
        prompt = create.call_args.kwargs['messages'][1]['content']
        for dato in ('Martina', 'Ruiz', 'Tomás', 'Laura', 'Gómez'):
            self.assertNotIn(dato, prompt)
        self.assertIn('INFORME 2026 - SEGUNDA ETAPA', prompt)
        self.assertIn('femenino', prompt)
        self.assertIn('Sala: 4 Años - Docente: Laura Gómez - Turno: Mañana', texto)
        self.assertIn('Martina Ruiz cuenta.', texto)


class PoolDeConexionesTest(unittest.TestCase):
    def test_close_devuelve_la_conexion_y_hace_rollback(self):
        raw = mock.MagicMock()
        raw.closed = 0
        raw.get_transaction_status.return_value = db.extensions.TRANSACTION_STATUS_INTRANS
        pool = mock.MagicMock()
        with mock.patch.object(db, '_obtener_pool', return_value=pool):
            conn = db._ConexionPool(raw)
            conn.close()
            conn.close()  # cerrar dos veces no devuelve la conexión dos veces
        raw.rollback.assert_called_once()
        pool.putconn.assert_called_once_with(raw, close=False)

    def test_conexion_rota_se_descarta(self):
        raw = mock.MagicMock()
        raw.closed = 1
        pool = mock.MagicMock()
        with mock.patch.object(db, '_obtener_pool', return_value=pool):
            db._ConexionPool(raw).close()
        pool.putconn.assert_called_once_with(raw, close=True)


if __name__ == '__main__':
    unittest.main()
