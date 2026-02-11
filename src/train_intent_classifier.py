import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
import joblib
import os

# --- CARGA DE DATOS ---
df = pd.read_csv("data/intents.csv")

X = df["texto"]
y = df["intencion"]

# --- SPLIT ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- PIPELINE ML ---
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1,2),
        stop_words="spanish"
    )),
    ("clf", LogisticRegression(
        max_iter=1000,
        multi_class="auto"
    ))
])

# --- ENTRENAMIENTO ---
pipeline.fit(X_train, y_train)

# --- EVALUACIÓN ---
y_pred = pipeline.predict(X_test)
print("\n📊 RESULTADOS DEL CLASIFICADOR:\n")
print(classification_report(y_test, y_pred))

# --- GUARDAR MODELO ---
os.makedirs("models", exist_ok=True)
joblib.dump(pipeline, "models/intent_model.joblib")

print("\n✅ Modelo guardado en models/intent_model.joblib")
