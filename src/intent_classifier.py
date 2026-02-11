import joblib

MODELO = "models/intent_model.joblib"

class IntentClassifier:
    def __init__(self):
        self.model = joblib.load(MODELO)

    def predecir(self, texto):
        return self.model.predict([texto])[0]

if __name__ == "__main__":
    clf = IntentClassifier()

    while True:
        pregunta = input("Pregunta: ")
        if pregunta.lower() == "salir":
            break

        intent = clf.predecir(pregunta)
        print(f"👉 Intención detectada: {intent}")
