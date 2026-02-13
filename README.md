# TFG — NL → SPARQL sobre trazabilidad (P510-like)

Este repositorio está pensado para un TFG de **generación/selección de consultas SPARQL a partir de Lenguaje Natural**, acotado a **trazabilidad** y **responsables** (proveedores/owners).

La idea es trabajar con un grafo RDF inspirado en el estándar **LOTAR P510** (no es necesario copiarlo literal):

- Las relaciones de trazabilidad se modelan como **nodos de enlace** `p510:Traceability_Link_Type`.
- Ejemplo de patrón:

	- `?req p510:Satisfied_by ?link .`
	- `?link p510:Link ?modelo ; p510:ContentType "Physical Model" .`

Esto permite formular preguntas típicas del tutor: “¿existen enlaces?”, “¿están todos trazados?”, “¿cuántos X tengo?”, “¿quién es responsable?”

## Empezar (núcleo limpio)

1) Generar un grafo sintético P510-like:

`python src/p510_generate_synthetic.py`

Salida: `data/p510_sintetico.ttl`

2) Ejecutar el set inicial de consultas SPARQL:

`python src/run_queries_p510.py`

Consultas en `queries_p510/`.

## Demo NL→SPARQL (baseline reproducible)

Incluye una demo **sin ML** (reglas + plantillas) que convierte preguntas en español a SPARQL y las ejecuta.

Ejemplos:

`python src/nl2sparql_cli.py "¿Cuántos proveedores hay?"`

`python src/nl2sparql_cli.py "requisitos sin modelo"`

`python src/nl2sparql_cli.py "modelos del proveedor 03"`

Esto te da un punto de partida para el TFG: luego puedes sustituir/expandir el parser por un clasificador, LLM, etc.

## Consultas incluidas (ejemplos)

- Requisitos sin modelo físico (falta de `Satisfied_by`)
- Modelos físicos sin test (falta de `Verified_by`)
- Porcentaje de requisitos con modelo
- Requisitos sin trazabilidad end-to-end (Req → Model → Test)
- Requisitos sobre-especificados (más de un modelo)
- Cuántos proveedores hay
- Modelos por proveedor

Además (más cercano al XSD):

- Resumen de metadatos PLM (GeneralPLMInfo)
- Info del entorno de desarrollo (RequirementsDevStructure)
- Documentos usados (`uses`)
- Escenarios de V&V con credibilidad (Requirements_Verification_Validation / Scenario)
	- Las evidencias incluyen `p510:Id` (así los resúmenes no quedan en `None`)
- Auditoría de links sin timestamps

Auditorías de calidad de dato (para hacer el TFG más sólido):

- Aprobados sin aprobador (incoherencia de aprobación)
- Links con `ContentType` incoherente con el destino
- Trazas duplicadas (mismo origen/predicado/destino repetido)
- Links sin `Description`

Y más completo para "responsables"/"owners":

- Conteo de entidades (requisitos/modelos/tests/escenarios/documentos/links)
- Modelos sin proveedor (responsable faltante)
- Requisitos sin aprobador
- Distribución de requisitos por maturity
- Requisitos por organización autora
- Proveedor con más modelos sin test
- Tests por proveedor (vía modelos)

## Siguiente paso (TFG)

Una vez el grafo y las queries estén bien definidos, la parte de NL→SPARQL se puede plantear en 2 niveles:

- **Clasificación a intent** (elige una query predefinida).
- **Relleno de plantillas** (por ejemplo filtros por tipo/proveedor/keyword).
