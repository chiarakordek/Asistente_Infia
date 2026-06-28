import os
from openai import OpenAI
from src.config import GROQ_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

def transcribir_audio(id_alumno, id_actividad, ruta_audio, id_usuario=None):
    if not os.path.exists(ruta_audio):
        return None
    try:
        with open(ruta_audio, "rb") as f:
            transcripcion = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo", file=f, language="es"
            )
        return transcripcion.text
    except Exception as e:
        print(f"Error Whisper (Groq): {e}")
        return None
