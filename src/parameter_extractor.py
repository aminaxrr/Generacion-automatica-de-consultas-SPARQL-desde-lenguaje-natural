def extraer_parametros(pregunta, intent):
    params = {}

    if intent.get("parameters"):
        if "keyword" in intent["parameters"]:
            tokens = pregunta.split()
            params["keyword"] = tokens[-1]  # baseline simple

    return params
