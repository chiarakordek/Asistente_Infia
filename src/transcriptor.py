import os
from openai import OpenAI
from src.config import GROQ_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

MIN_ARCHIVO_BYTES = 100

def transcribir_audio(id_alumno, id_actividad, ruta_audio, id_usuario=None):
    if not os.path.exists(ruta_audio):
        print(f"transcriptor: archivo no existe {ruta_audio}")
        return "Audio grabado (archivo no encontrado)"
    tamano = os.path.getsize(ruta_audio)
    if tamano < MIN_ARCHIVO_BYTES:
        print(f"transcriptor: archivo muy chico ({tamano}b), no se envía a Groq")
        return "Audio grabado (muy corto, no se pudo transcribir)"
    try:
        with open(ruta_audio, "rb") as f:
            transcripcion = client.audio.transcriptions.create(
                model="whisper-large-v3", file=f, language="es"
            )
        texto = transcripcion.text.strip()
        if texto:
            print(f"transcriptor: OK ({tamano}b) → '{texto[:80]}'")
            return texto
        print("transcriptor: transcripción vacía")
        return "Audio grabado (sin transcripción)"
    except Exception as e:
        print(f"transcriptor: Error Groq Whisper: {e}")
        error_msg = str(e)
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return "[Error: GROQ_API_KEY inválida o no configurada. Verificá las variables de entorno en Render.]"
        if "429" in error_msg:
            return "[Error: Límite de requests excedido. Esperá unos segundos.]"
        if "413" in error_msg:
            return "[Error: Archivo de audio demasiado grande (>25MB).]"
        if "model_not_found" in error_msg or "404" in error_msg:
            return "[Error: Modelo de transcripción no encontrado en Groq.]"
        return f"[Error al transcribir: {str(e)[:120]}]"
