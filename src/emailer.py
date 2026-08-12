import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def enviar_email(destinatario, asunto, html):
    host = os.environ.get('SMTP_HOST', 'smtp.gmail.com').strip()
    port = int(os.environ.get('SMTP_PORT', '465'))
    usuario = os.environ.get('SMTP_USER', '').strip()
    password = os.environ.get('SMTP_PASS', '').strip()
    nombre = os.environ.get('EMAIL_NOMBRE', 'Infia').strip()
    if not usuario or not password:
        raise RuntimeError('SMTP_USER / SMTP_PASS no configurados')
    msg = MIMEMultipart('alternative')
    msg['Subject'] = asunto
    msg['From'] = f'{nombre} <{usuario}>'
    msg['To'] = destinatario
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    contexto = ssl.create_default_context()
    if port == 587:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=contexto)
            server.ehlo()
            server.login(usuario, password)
            server.sendmail(usuario, [destinatario], msg.as_string())
    else:
        with smtplib.SMTP_SSL(host, port, context=contexto, timeout=20) as server:
            server.login(usuario, password)
            server.sendmail(usuario, [destinatario], msg.as_string())
