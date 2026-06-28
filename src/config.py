import os

# En producción (Render) asigná estas variables en Environment Variables.
# En desarrollo local podés editarlas acá o usar un archivo .env

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "...")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_...")
