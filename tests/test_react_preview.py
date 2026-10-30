import unittest
from unittest.mock import patch

import src.db

# Loading app.py normally initializes PostgreSQL. Keep these route tests isolated
# from the user's database and exercise only the HTTP/session boundary.
with patch.object(src.db, 'inicializar_bd', lambda: None):
    import app as app_module


class ReactPreviewTest(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY='test-only-secret')
        self.client = app_module.app.test_client()
        self.init_patch = patch.object(app_module, 'inicializar_bd', lambda: None)
        self.expiry_patch = patch.object(app_module, 'obtener_bajas_vencidas', lambda: [])
        self.init_patch.start()
        self.expiry_patch.start()
        app_module._bd_inicializada = True

    def tearDown(self):
        self.init_patch.stop()
        self.expiry_patch.stop()

    def test_preview_routes_serve_react_shell(self):
        for path in ('/react-preview/login', '/react-preview/dashboard', '/react-preview/planificacion'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'id="root"', response.data)
                self.assertIn(b'/static/react-app/assets/', response.data)
                response.close()

    def test_public_auth_pages_serve_react_shell(self):
        for path in ('/login', '/registro', '/forgot'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'id="root"', response.data)
                response.close()

    def test_teacher_pages_serve_react_after_authentication(self):
        user = {'id_usuario': 7, 'nombre': 'Docente', 'email': 'docente@example.com', 'plan': 'trial'}
        with patch.object(app_module, 'obtener_usuario_por_id', return_value=user), \
             patch.object(app_module, 'es_admin', return_value=False):
            with self.client.session_transaction() as session:
                session['user_id'] = 7
            for path in ('/dashboard', '/planificacion?seccion=areas', '/perfil', '/config',
                         '/cuenta', '/suscripcion', '/salas', '/alumno/15'):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b'id="root"', response.data)
                    response.close()

    def test_admin_route_keeps_admin_guard_and_serves_react(self):
        user = {'id_usuario': 7, 'nombre': 'Admin', 'email': 'admin@example.com', 'plan': 'pago'}
        with patch.object(app_module, 'es_admin', return_value=True), \
             patch.object(app_module, 'obtener_usuario_por_id', return_value=user):
            with self.client.session_transaction() as session:
                session['user_id'] = 7
            response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="root"', response.data)
        response.close()

    def test_unauthenticated_api_returns_json_401(self):
        response = self.client.get('/api/me')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error'], 'No autorizado')

    def test_me_never_exposes_password_hash(self):
        user = {
            'id_usuario': 7, 'nombre': 'Docente', 'email': 'docente@example.com',
            'contraseña': 'sensitive-hash', 'plan': 'trial', 'tipo_plan': 'mensual',
        }
        with patch.object(app_module, 'obtener_usuario_por_id', return_value=user), \
             patch.object(app_module, 'es_admin', return_value=False):
            with self.client.session_transaction() as session:
                session['user_id'] = 7
            response = self.client.get('/api/me')
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['nombre'], 'Docente')
        self.assertNotIn('contraseña', payload)


if __name__ == '__main__':
    unittest.main()
