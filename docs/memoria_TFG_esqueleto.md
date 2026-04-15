# Memoria TFG — Text2SPARQL offline (P510-like)

> Este documento es un esqueleto de memoria (≈80 páginas) con **contenido-guía** y **fuentes** por capítulo.
> Puedes usarlo tal cual en Markdown o como base para Word/LaTeX.

## 0. Resumen (1 pág)
- Problema: consulta en lenguaje natural sobre un grafo RDF (trazabilidad/auditoría).
- Propuesta: sistema **offline y determinista** que hace *grounding palabra→concepto* y **compila SPARQL por operadores**, con **checker anti-invención** y **explicabilidad**.
- Validación: ejecución en RDFLib + set de ejemplos NL→SPARQL.

## 1. Introducción (6–8 págs)
### 1.1 Contexto
- En ingeniería, los grafos RDF se usan para trazabilidad, verificación, auditoría y gobierno de datos.
- Problema práctico: SPARQL es una barrera para usuarios no expertos.

### 1.2 Motivación
- Necesidad de hacer preguntas “como las diría una persona” y obtener SPARQL ejecutable.
- Requisitos de entorno: privacidad, control de esquema, reproducibilidad ⇒ **offline**.

### 1.3 Objetivos
- Objetivo general y objetivos específicos (robustez a parafraseo dentro de familias de consulta, no inventar esquema, explainability, demos).

### 1.4 Alcance y limitaciones
- “Universal” dentro de un conjunto de familias (operadores) inspiradas en consultas P510.
- No es un compilador universal para cualquier pregunta arbitraria.

**Fuentes recomendadas (Introducción)**
- W3C, *RDF 1.1 Primer* (visión general): https://www.w3.org/TR/rdf11-primer/
- W3C, *SPARQL 1.1 Overview*: https://www.w3.org/TR/sparql11-overview/
- Survey KGQA (visión general de NL→consultas sobre grafos):
  - Usbek et al., “Survey on Question Answering over Knowledge Graphs” (hay varias revisiones; elige una reciente de revista/conferencia).

## 2. Marco Teórico (10–14 págs)
### 2.1 RDF y grafos de conocimiento
- Triples (s,p,o), IRIs, literales, prefijos.
- `rdf:type`, clases y propiedades.

### 2.2 SPARQL (lo necesario)
- `SELECT`/`WHERE`, `OPTIONAL`, `FILTER`, `ORDER BY`, `LIMIT`.
- `EXISTS`/`NOT EXISTS` (auditorías de “faltan datos”).
- `GROUP BY` + `HAVING` (duplicados, distribuciones).
- `UNION` (combinar entidades/condiciones).

### 2.3 Patrones de modelado de trazabilidad con link nodes
- Enlace directo vs nodo intermedio (link node) con metadatos.

**Fuentes recomendadas (Teoría)**
- W3C SPARQL 1.1 Query Language (detalles formales): https://www.w3.org/TR/sparql11-query/
- W3C SPARQL 1.1 Update (para explicar por qué se bloquea): https://www.w3.org/TR/sparql11-update/
- RDFLib (documentación y ejemplos): https://rdflib.readthedocs.io/

## 3. Dominio y Datos (P510-like) (8–10 págs)
### 3.1 Dominio P510-like
- Explicar a alto nivel qué representa (trazabilidad requisitos→modelos→tests; manifest PLM; V&V scenarios; proveedores; auditorías de calidad).

### 3.2 Ontología/Namespaces usados
- `p510:` (dominio), `ex:` (extensiones sintéticas), `foaf:` (organizaciones), `dcterms:` (fechas).

### 3.3 Patrón de link node
- Estructura típica:
  - `?src p510:Satisfied_by|Verified_by|Validated_by|uses ?linkNode .`
  - `?linkNode a p510:Traceability_Link_Type ; p510:Link ?target ; p510:ContentType "..." .`

### 3.4 Dataset sintético
- Cómo se genera (parámetros), qué propiedades asegura, limitaciones.

**Fuentes recomendadas (Dominio)**
- FOAF vocabulary (para `foaf:Organization`): http://xmlns.com/foaf/spec/
- Dublin Core Terms (`dcterms:created`): https://www.dublincore.org/specifications/dublin-core/dcmi-terms/
- LOTAR / P510: si puedes citar la página oficial o documentación accesible públicamente. Si no es pública, cítala como “documentación interna / restringida” y apóyate en la descripción del modelo que implementas.

## 4. Estado del Arte / Enfoques (8–10 págs)
### 4.1 Enfoques de NL→consulta
- Recuperación por catálogo (retrieval/matching).
- Compilación por operadores (reglas/IR).
- LLM (solo como comparación: pros/contras y riesgos de inventar esquema).

### 4.2 Preguntas sobre grafos (KGQA)
- Diferencia entre text-to-SQL y text-to-SPARQL.

**Fuentes recomendadas (Estado del arte)**
- Trabajos clásicos de *semantic parsing* (orientativos, para justificar el enfoque):
  - Zettlemoyer & Collins (2005/2007) — parsing semántico con supervisión.
  - Berant et al. (2013) — QA sobre KB con preguntas.
- Para text-to-SQL como referencia metodológica:
  - Yu et al., Spider dataset (2018) — benchmark de text-to-SQL.
- Surveys KGQA recientes (elige 1–2 de 2020+).

## 5. Requisitos y Alcance (6–8 págs)
- Funcionales: traducir, ejecutar, explicar, UI.
- No funcionales: determinismo, reproducibilidad, seguridad (bloquear UPDATE), extensibilidad.
- Criterios de éxito: pass-rate en ejemplos, ejecución sin errores, coherencia con familias.

**Fuentes recomendadas (Requisitos)**
- W3C SPARQL Update (para justificar la lista de keywords bloqueadas).

## 6. Diseño de la Solución (10–12 págs)
### 6.1 Arquitectura
- Pipeline: normalización → sinónimos → `SchemaIndex` → grounding → routing → compilación → checker → ejecución → explicación.

### 6.2 Decisiones de diseño (argumentación)
- Offline/determinista: por privacidad/reproducibilidad.
- Checker anti-invención: por robustez y credibilidad técnica.
- Operadores: “universal dentro del dominio”.

### 6.3 Explainability
- Qué se muestra y por qué es útil.

**Fuentes recomendadas (Diseño)**
- Documentación RDFLib (ejecución SPARQL).
- Streamlit docs (si incluyes UI): https://docs.streamlit.io/

## 7. Implementación (12–16 págs)
### 7.1 Estructura del proyecto
- `src/text2sparql.py`: motor
- `src/text2sparql_cli.py`: CLI
- `src/demo_server.py`: demo web
- `src/demo_visual.py`: demo Streamlit
- `eval/text2sparql_examples.jsonl`: evaluación

### 7.2 Normalización y sinónimos
- Describir el bloque `### SYNONYMS` y su papel.

### 7.3 Indexado del esquema
- Cómo se extraen clases/predicados reales del grafo.

### 7.4 Grounding
- Dataclasses (`GroundingHit`, `GroundingResult`).
- Ejemplos de hits.

### 7.5 Operadores (familias)
- Not-exists trazabilidad
- Group-by distribuciones
- Auditorías (timestamps, description, mismatch, duplicates)
- Manifest (PLM/dev/baseline)
- V&V scenarios

### 7.6 Checker y validación
- Bloqueo de SPARQL Update.
- Verificación de términos contra el grafo.
- Validación por ejecución.

**Fuentes recomendadas (Implementación)**
- RDFLib Graph.query: https://rdflib.readthedocs.io/
- PyParsing (si comentas el error de parseo y su solución, opcional): https://pyparsing-docs.readthedocs.io/

## 8. Evaluación y Resultados (8–12 págs)
- Metodología: set de ejemplos, ejecución, métricas.
- Resultados: tablas y análisis.
- Casos de estudio con explicación.

**Fuentes recomendadas (Evaluación)**
- Buenas prácticas de evaluación en semantic parsing / QA sobre KB (elige survey/paper que discuta métricas, split, etc.).

## 9. Discusión (4–6 págs)
- Limitaciones: alcance, ambigüedad, dependencia del esquema, dataset sintético.
- Amenazas a la validez.

## 10. Conclusiones y Trabajo Futuro (3–5 págs)
- Conclusiones enlazadas a objetivos.
- Trabajo futuro: tests de parafraseo por operador, ampliar dominio, IR más formal.

---

## Apéndice sugerido: Tabla Operador → Patrón
- Operador
- Señales NL (tokens/hits)
- Patrón SPARQL (NOT EXISTS / GROUP BY / UNION / OPTIONAL)
- Esquema usado (clases/predicados)

## Apéndice sugerido: Guía de reproducción
- `pip install -r requirements.txt`
- `python src/p510_generate_synthetic.py`
- `python src/text2sparql_eval.py --mode generate --engine dynamic`
- `streamlit run src/demo_visual.py`
