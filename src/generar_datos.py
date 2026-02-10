import random
import os
from rdflib import Graph, URIRef, Literal, RDF, Namespace

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------
CANTIDAD_REQUISITOS = 50
CANTIDAD_MODELOS = 30
CANTIDAD_TESTS = 20

# Probabilidades de errores de trazabilidad
PROB_REQUISITO_HUERFANO = 0.15   # Requisitos sin modelo
PROB_MODELO_SIN_TEST = 0.20      # Modelos sin test

# --------------------------------------------------
# NAMESPACES
# --------------------------------------------------
P510 = Namespace("http://www.lotar.org/schemas/mbse/p510#")
EX = Namespace("http://mi-empresa.org/proyecto-avion#")

# --------------------------------------------------
# GENERACIÓN DEL GRAFO RDF
# --------------------------------------------------
def generar_grafo():
    print("🏭 Generando grafo RDF basado en P510...")

    g = Graph()
    g.bind("p510", P510)
    g.bind("ex", EX)

    requisitos = []
    modelos = []
    tests = []

    # --------------------------------------------------
    # 1. REQUISITOS
    # --------------------------------------------------
    print(f"   - Creando {CANTIDAD_REQUISITOS} requisitos")
    for i in range(1, CANTIDAD_REQUISITOS + 1):
        req = EX[f"Req_{i:03d}"]

        g.add((req, RDF.type, P510.Requirement))
        g.add((req, P510.id, Literal(f"REQ-{i:03d}")))
        g.add((req, P510.description, Literal(f"El sistema debe cumplir la función {i}")))
        g.add((req, P510.contentType, Literal("Requirement")))

        requisitos.append(req)

    # --------------------------------------------------
    # 2. MODELOS DE DISEÑO
    # --------------------------------------------------
    print(f"   - Creando {CANTIDAD_MODELOS} modelos de diseño")
    for i in range(1, CANTIDAD_MODELOS + 1):
        model = EX[f"Model_{i:03d}"]

        g.add((model, RDF.type, P510.DesignModel))
        g.add((model, P510.name, Literal(f"Modelo físico {i}")))
        g.add((model, P510.contentType, Literal("Physical Model")))

        modelos.append(model)

    # --------------------------------------------------
    # 3. TESTS DE VERIFICACIÓN
    # --------------------------------------------------
    print(f"   - Creando {CANTIDAD_TESTS} tests de verificación")
    for i in range(1, CANTIDAD_TESTS + 1):
        test = EX[f"Test_{i:03d}"]

        g.add((test, RDF.type, P510.VerificationTest))
        g.add((test, P510.status, Literal("Passed")))
        g.add((test, P510.contentType, Literal("Test Case")))

        tests.append(test)

    # --------------------------------------------------
    # 4. TRAZABILIDAD
    # --------------------------------------------------
    print("🔗 Creando enlaces de trazabilidad")

    # Requisito → Modelo (Satisfied_by)
    for req in requisitos:
        if random.random() > PROB_REQUISITO_HUERFANO:
            modelo = random.choice(modelos)
            g.add((req, P510.Satisfied_by, modelo))

    # Modelo → Test (Verified_by)
    for modelo in modelos:
        if random.random() > PROB_MODELO_SIN_TEST:
            test = random.choice(tests)
            g.add((modelo, P510.Verified_by, test))

    # --------------------------------------------------
    # 5. EXPORTACIÓN
    # --------------------------------------------------
    os.makedirs("data", exist_ok=True)
    ruta = os.path.join("data", "grafo_sintetico.ttl")

    g.serialize(destination=ruta, format="turtle")

    print("✅ Grafo generado correctamente")
    print(f"   → Archivo: {ruta}")
    print(f"   → Tripletas: {len(g)}")


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    generar_grafo()
