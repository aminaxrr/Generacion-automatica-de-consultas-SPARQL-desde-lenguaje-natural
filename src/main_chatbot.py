from intent_classifier import detectar_intencion
from parameter_extractor import extraer_parametros
import auditor

def iniciar_chat():
    grafo = auditor.cargar_grafo()
    print("🤖 Chatbot MBSE P510 listo")

    while True:
        pregunta = input("\n👉 ")
        if pregunta.lower() == "salir":
            break

        intent = detectar_intencion(pregunta)

        if not intent:
            print("🤔 No he entendido la intención.")
            continue

        params = extraer_parametros(pregunta, intent)

        auditor.ejecutar_consulta(
            grafo,
            intent["sparql_file"],
            intent["name"],
            params
        )
