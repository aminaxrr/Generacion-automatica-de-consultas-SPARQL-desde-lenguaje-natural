# Bibliografía recomendada (base)

> Esta lista es intencionalmente “segura”: fuentes estables y ampliamente citables.
> Si tu uni exige APA/IEEE, luego lo convertimos a ese formato.

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
