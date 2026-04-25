# Bibliografía recomendada (base)

> Esta lista es intencionalmente “segura”: fuentes estables y ampliamente citables.
> En tu caso, la memoria va en **IEEE**: citas numéricas en el texto tipo **[1]** y sección de referencias numerada.

## Guía rápida IEEE (para esta memoria)
- En el texto: “... como define el W3C en [1]” o “... según [2], [3]”.
- En la bibliografía: lista numerada en el orden de aparición.
- Prioriza referencias con autor/organización + título + año. Si solo hay URL, usa organización + título del documento y fecha de acceso.

## Estándares y especificaciones (W3C)
- W3C. *RDF 1.1 Primer*. https://www.w3.org/TR/rdf11-primer/
- W3C. *RDF 1.1 Concepts and Abstract Syntax*. https://www.w3.org/TR/rdf11-concepts/
- W3C. *SPARQL 1.1 Overview*. https://www.w3.org/TR/sparql11-overview/
- W3C. *SPARQL 1.1 Query Language*. https://www.w3.org/TR/sparql11-query/
- W3C. *SPARQL 1.1 Update*. https://www.w3.org/TR/sparql11-update/

## Vocabularios
- FOAF Vocabulary Specification. http://xmlns.com/foaf/spec/
- Dublin Core Terms (DCMI). https://www.dublincore.org/specifications/dublin-core/dcmi-terms/

## Librerías / herramientas
- RDFLib Documentation (Python). https://rdflib.readthedocs.io/
- Streamlit Documentation. https://docs.streamlit.io/

## Licencias, estándares y cumplimiento (para “marco legal”)
> Úsalo para justificar licencias de software y buenas prácticas de uso.

- Open Source Initiative (OSI). *The Open Source Definition*. https://opensource.org/osd/
- SPDX. *SPDX License List*. https://spdx.org/licenses/

## Privacidad / protección de datos (si aplica)
> Si tu solución no procesa datos personales reales, cita igualmente el marco y explica por qué **no aplica** o cómo reduces riesgos.

- EU. *Regulation (EU) 2016/679 (GDPR / RGPD)*. (Texto consolidado accesible en EUR-Lex): https://eur-lex.europa.eu/

## Gestión de proyectos (para “planificación y presupuesto”)
- Project Management Institute (PMI). *PMBOK Guide* (edición vigente) — referencia estándar para planificación y gestión.
- ISO 21500 / ISO 21502 (gestión de proyectos) — si tu universidad prefiere ISO.

## Question Answering / Semantic Parsing (para “estado del arte”)
> Elige 4–8 referencias en total (no hace falta meter 40).

- Zettlemoyer, L., & Collins, M. (2005/2007). Trabajos clásicos de semantic parsing (CCG) para mapear NL a representaciones lógicas.
- Berant, J., Chou, A., Frostig, R., & Liang, P. (2013). Semantic parsing on Freebase con preguntas (línea “KB QA”).
- Survey(s) KGQA recientes (2020+). Busca “question answering over knowledge graphs survey” y selecciona uno de revista o conferencia.

## Text-to-SQL (referencia metodológica)
- Yu, T. et al. (2018). Spider: benchmark text-to-SQL. (Útil para explicar evaluación por queries/familias y generalización.)

## LOTAR / P510
- LOTAR (sitio oficial / material público). Si la especificación P510 es restringida, puedes citar:
  - Página general de LOTAR y describir que tu modelo es “inspirado en P510” y definido por el TTL y las queries de referencia.

---

## Cómo usar esta bibliografía por capítulo
- Teoría: W3C RDF + W3C SPARQL.
- Dominio: FOAF, DCTERMS, y documentación LOTAR (si es accesible).
- Implementación: RDFLib (y Streamlit si incluyes UI).
- Estado del arte: 1 survey KGQA + 1–2 semantic parsing + 1 text-to-SQL (opcional) para justificar la metodología.
