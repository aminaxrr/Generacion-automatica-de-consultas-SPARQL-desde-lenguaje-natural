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

## Text2SPARQL offline (estilo NeoDash Text2Cypher)

Además del baseline por reglas, hay un modo **LLM-like** pero **local/offline**: genera SPARQL a partir de una pregunta y la valida/ejecuta sobre el grafo.

Script: `python src/text2sparql_cli.py "..."`

Modos:

- `--mode translate`: solo genera la SPARQL
- `--mode run`: genera + ejecuta (por defecto)

Backends soportados:

1) **Rules (sin modelos, 100% reproducible)**

`python src/text2sparql_cli.py "¿Cuántos proveedores hay?" --backend rules --mode run`

2) **Ollama (local)**

- Instala/arranca Ollama y descarga un modelo, por ejemplo:
	- `ollama pull llama3.1`

Ejemplo:

`python src/text2sparql_cli.py "requisitos sin trazabilidad end to end" --backend ollama --model llama3.1 --mode run`

Por defecto usa `http://localhost:11434/api/chat`. Puedes cambiarlo con:

- `TEXT2SPARQL_OLLAMA_URL`

3) **Servidor OpenAI-compatible local** (por ejemplo LM Studio, LocalAI, etc.)

Configura:

- `TEXT2SPARQL_OPENAI_BASE_URL` (ej: `http://localhost:1234`)
- `TEXT2SPARQL_OPENAI_API_KEY` (si aplica; puede estar vacío)

Ejemplo:

`python src/text2sparql_cli.py "auditoría links duplicados" --backend openai_compat --model <tu_modelo> --mode run`

### Seguridad / restricciones

- Solo se permiten consultas `SELECT` o `ASK` (se bloquean `CONSTRUCT/DESCRIBE/INSERT/DELETE/...`).
- Si es `SELECT` y no incluye `LIMIT`, se añade `LIMIT 200` (configurable con `--limit`).
- Se incluye un conjunto few-shot en `eval/text2sparql_examples.jsonl` para anclar el estilo a tu catálogo `queries_p510/`.

## Demo visual (web local)

Hay una demo visual tipo “NeoDash” (web local) **sin dependencias extra**: HTML+JS servido por Python estándar.

1) Ejecutar la demo:

`python src/demo_server.py`

2) Abrir:

`http://127.0.0.1:8000`

Notas:

- Si no existe `data/p510_sintetico.ttl`, la demo puede regenerarlo (botón “Regenerar grafo”).
- Para usar Ollama: servidor levantado (`ollama serve`) y un modelo descargado.

### (Opcional) Demo Streamlit

También hay una versión con Streamlit en `src/demo_visual.py`, pero depende de `streamlit/pandas` (puede requerir Python ≤ 3.12 según wheels disponibles).

`pip install -r requirements.txt`

`python -m streamlit run src/demo_visual.py`

## Auto-evaluación (para el capítulo de evaluación)

Script: `python src/text2sparql_eval.py`

1) Validar que las SPARQL de referencia del JSONL ejecutan (sanity check):

`python src/text2sparql_eval.py --mode reference`

2) Evaluar el generador (genera desde NL y comprueba que se ejecuta):

`python src/text2sparql_eval.py --mode generate --backend rules`

Si usas un LLM local:

`python src/text2sparql_eval.py --mode generate --backend ollama --model llama3.1`

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
