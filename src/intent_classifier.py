import re
from intents import INTENTS

def normalizar(texto):
    texto = texto.lower()
    texto = re.sub(r"[¿?¡!.,]", "", texto)
    return texto

def puntuar_intencion(pregunta, intent):
    score = 0
    for kw in intent.get("keywords", []):
        if kw in pregunta:
            score += 2
    for ex in intent.get("examples", []):
        if any(p in pregunta for p in ex.lower().split()):
            score += 1
    return score

def detectar_intencion(pregunta):
    pregunta = normalizar(pregunta)

    mejor_intencion = None
    mejor_score = 0

    for intent in INTENTS:
        score = puntuar_intencion(pregunta, intent)
        if score > mejor_score:
            mejor_score = score
            mejor_intencion = intent

    if mejor_score == 0:
        return None

    return mejor_intencion
