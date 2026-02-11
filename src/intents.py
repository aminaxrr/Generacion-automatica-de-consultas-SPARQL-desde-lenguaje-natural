INTENTS = [
    {
        "id": "INT_01_REQ_HUERFANOS",
        "name": "Requisitos huérfanos",
        "keywords": [
            "requisito sin modelo",
            "requisito huerfano",
            "sin implementar",
            "no tienen modelo"
        ],
        "examples": [
            "¿Hay requisitos huérfanos?",
            "¿Qué requisitos no tienen modelo?",
            "¿Existen requisitos sin implementar?"
        ],
        "sparql_file": "q1_requisitos_huerfanos.sparql",
        "output": "list"
    },
    {
        "id": "INT_02_MODELOS_SIN_TEST",
        "name": "Modelos sin verificación",
        "keywords": [
            "modelo sin test",
            "modelo no verificado",
            "sin verificacion"
        ],
        "examples": [
            "¿Qué modelos no tienen test?",
            "¿Hay modelos sin verificación?"
        ],
        "sparql_file": "q2_modelos_sin_test.sparql",
        "output": "list"
    },
    {
        "id": "INT_07_PORCENTAJE_TRAZABILIDAD",
        "name": "Porcentaje de trazabilidad",
        "keywords": [
            "porcentaje",
            "cobertura",
            "nivel de trazabilidad"
        ],
        "examples": [
            "¿Qué porcentaje de requisitos está trazado?",
            "¿Cuál es la cobertura del sistema?"
        ],
        "sparql_file": "q8_porcentaje_trazabilidad.sparql",
        "output": "percentage"
    },
    {
        "id": "INT_14_BUSQUEDA_SEMANTICA",
        "name": "Búsqueda semántica",
        "keywords": [
            "buscar",
            "contienen",
            "mencionan",
            "relacionados con"
        ],
        "examples": [
            "Busca requisitos sobre seguridad",
            "Encuentra modelos que hablen de control"
        ],
        "sparql_file": "q11_busqueda_texto.sparql",
        "output": "list",
        "parameters": ["keyword"]
    }
]
