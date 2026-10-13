import os
from dotenv import load_dotenv

# Carga las variables locales antes de inicializar clientes externos.
load_dotenv()

# En producción (Render) asigná estas variables en Environment Variables.
# En desarrollo local guardalas en .env (ver .env.example).

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "...")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_...")
