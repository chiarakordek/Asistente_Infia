import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo('America/Argentina/Buenos_Aires')
except Exception:
    ZONA = None

PRECIO_MENSUAL = 10000
PRECIO_ANUAL = 96000
DIAS_TRIAL = 30


def hoy():
    if ZONA:
        return datetime.now(ZONA).date()
    return date.today()


def suscripcion_activa():
    return os.environ.get('SUSCRIPCION_ACTIVA', '0').lower() in ('1', 'true', 'si', 'yes')


def estado_cuenta(s):
    plan = s.get('plan') or 'trial'
    hoy_d = hoy()
    if plan == 'pago':
        venc = s.get('fecha_vencimiento')
        if venc is None:
            return 'vencida'
        venc_date = venc.date() if isinstance(venc, datetime) else venc
        return 'pago' if venc_date >= hoy_d else 'vencida'
    reg = s.get('fecha_registro')
    if reg is None:
        return 'trial'
    reg_date = reg.date() if isinstance(reg, datetime) else reg
    fin_trial = reg_date + timedelta(days=DIAS_TRIAL)
    return 'trial' if hoy_d <= fin_trial else 'vencida'


def dias_restantes(s):
    if estado_cuenta(s) != 'trial':
        return 0
    reg = s.get('fecha_registro')
    if reg is None:
        return DIAS_TRIAL
    reg_date = reg.date() if isinstance(reg, datetime) else reg
    return max(0, (reg_date + timedelta(days=DIAS_TRIAL) - hoy()).days)


def _mp_token():
    token = os.environ.get('MP_ACCESS_TOKEN', '').strip()
    if not token:
        raise RuntimeError('MercadoPago no está configurado todavía')
    return token


def crear_preapproval(user, tipo):
    import requests
    token = _mp_token()
    base = os.environ.get('BASE_URL', 'https://infia.com.ar').rstrip('/')
    secret = os.environ.get('MP_WEBHOOK_SECRET', '')
    if tipo == 'anual':
        monto, freq, razon = PRECIO_ANUAL, 12, 'Infia - Plan Anual'
    else:
        monto, freq, razon = PRECIO_MENSUAL, 1, 'Infia - Plan Mensual'
    body = {
        'reason': razon,
        'auto_recurring': {
            'frequency': freq,
            'frequency_type': 'months',
            'transaction_amount': monto,
            'currency_id': 'ARS',
        },
        'payer_email': user.get('email'),
        'external_reference': f"infia-u{user['id_usuario']}-{tipo}",
        'back_url': base + '/suscripcion',
        'notification_url': base + '/webhook/mercadopago?secret=' + quote(secret),
    }
    r = requests.post('https://api.mercadopago.com/preapproval',
                      json=body, headers={'Authorization': 'Bearer ' + token}, timeout=20)
    r.raise_for_status()
    j = r.json()
    return j.get('id'), j.get('init_point')


def obtener_preapproval(mp_id):
    import requests
    token = _mp_token()
    r = requests.get(f'https://api.mercadopago.com/preapproval/{mp_id}',
                     headers={'Authorization': 'Bearer ' + token}, timeout=20)
    r.raise_for_status()
    return r.json()


def obtener_pago(mp_id):
    import requests
    token = _mp_token()
    r = requests.get(f'https://api.mercadopago.com/v1/payments/{mp_id}',
                     headers={'Authorization': 'Bearer ' + token}, timeout=20)
    r.raise_for_status()
    return r.json()


def _parse_referencia(ext):
    m = re.match(r'^infia-u(\d+)-(mensual|anual)$', ext or '')
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def procesar_notificacion(mp_id, tipo):
    from src.db import extender_suscripcion, registrar_pago
    if tipo == 'payment':
        j = obtener_pago(mp_id)
        if j.get('status') != 'approved':
            return None
        parsed = _parse_referencia(j.get('external_reference'))
        if not parsed:
            return None
        user_id, tipo_plan = parsed
        dias = 360 if tipo_plan == 'anual' else 30
        extender_suscripcion(user_id, dias, mp_id)
        registrar_pago(user_id, int(j.get('transaction_amount') or 0), tipo_plan, mp_id)
        return user_id
    j = obtener_preapproval(mp_id)
    if j.get('status') != 'authorized':
        return None
    parsed = _parse_referencia(j.get('external_reference'))
    if not parsed:
        return None
    user_id, tipo_plan = parsed
    dias = 360 if tipo_plan == 'anual' else 30
    extender_suscripcion(user_id, dias, mp_id)
    return user_id
