# Generación automática de consultas en SPARQL desde lenguaje natural

> Borrador inicial de memoria técnica (objetivo: **70–90 páginas**) para un sistema **offline y determinista** de traducción *texto → SPARQL* sobre un grafo RDF.
>
> **Idioma y estilo:** la memoria está redactada en español. Cuando sea necesario referirse a elementos del código (nombres de módulos, funciones, clases, flags o ficheros), se mantendrán sus identificadores en inglés tal y como aparecen en el repositorio.
>
> **Citas:** el documento utiliza el estilo **IEEE** (citas numéricas tipo [1], [2], ... y lista de referencias al final).
>
> **TODO (rellenar):**
> - Autor/a, tutor/a, grado/máster, universidad, curso
> - Contexto real (si existe) y restricciones (si las hay)

## Reparto orientativo de páginas (70–90)
- Introducción: 6–10
- Estado del arte: 10–14
- Análisis: 12–18
- Diseño: 10–14
- Implementación y pruebas: 16–22
- Presupuesto y planificación: 6–10
- Entorno socio-económico y marco legal: 6–10
- Conclusiones y trabajos futuros: 3–6
- Bibliografía: 2–4

---

## 1. Introducción (6–10 págs)
### 1.1 Motivación
En numerosos entornos técnicos, la información se organiza como un **grafo**: requisitos, modelos, evidencias de prueba, proveedores y relaciones de trazabilidad entre artefactos. El modelo RDF es especialmente adecuado para representar este tipo de relaciones porque permite describir entidades heterogéneas y vínculos con metadatos (fechas, tipos, descripciones) de forma flexible.

Sin embargo, el principal mecanismo estándar para consultar grafos RDF, **SPARQL**, supone una barrera de entrada. Aunque es una herramienta potente, requiere conocer la sintaxis, los predicados del dominio y patrones de consulta no triviales (por ejemplo, `NOT EXISTS`, `GROUP BY/HAVING`, combinaciones con `OPTIONAL` y filtros). En la práctica, esto crea una dependencia de perfiles expertos y dificulta la adopción de la consulta “self-service” por parte de usuarios que sí conocen el **dominio**, pero no la consulta formal.

Además, en contextos de trazabilidad y auditoría (p. ej. calidad de datos, verificación/validación, integridad de enlaces), las consultas suelen formar parte de procesos repetibles. Por ello aparecen requisitos adicionales: (i) **reproducibilidad** (la misma pregunta debe generar siempre el mismo resultado), (ii) **control del esquema** (no inventar términos que no existan en el grafo), y (iii) **privacidad** o control de ejecución (evitar enviar datos a servicios externos). Estos requisitos motivan un enfoque **offline** y **determinista**.

### 1.2 Objetivos
El objetivo general de este Trabajo de Fin de Grado es diseñar e implementar un sistema que permita formular preguntas en lenguaje natural sobre un grafo RDF y obtener como salida una consulta **SPARQL ejecutable**, junto con el resultado y una explicación del proceso de traducción.

De forma más concreta, los objetivos específicos son:

- **O1 — Traducción texto→SPARQL (lectura):** generar consultas SPARQL de tipo `SELECT` para un conjunto acotado de familias de consultas del dominio.
- **O2 — Enfoque offline y determinista:** el sistema funciona sin dependencia de servicios remotos y produce salidas reproducibles.
- **O3 — Grounding al esquema:** cada decisión (predicado, clase, operador) se ancla a términos existentes en el grafo.
- **O4 — Checker anti-invención y seguridad:** bloquear SPARQL Update y rechazar consultas que contengan términos fuera del esquema observado.
- **O5 — Explicabilidad:** proporcionar una traza que muestre cómo palabras/frases se asocian a entidades, predicados y operadores.
- **O6 — Validación y pruebas:** ejecutar las consultas generadas sobre un grafo local y evaluar cobertura/robustez con un conjunto de ejemplos y paráfrasis.
- **O7 — Interfaz de demostración:** disponer de una interfaz (CLI y demo visual) que permita usar el sistema y revisar SPARQL, resultados y explicación.

### 1.3 Alcance y limitaciones
El alcance del trabajo se centra en un dominio **P510-like** (inspirado en trazabilidad de ingeniería), representado mediante un grafo RDF y un conjunto de consultas de referencia. El sistema no pretende resolver “cualquier pregunta arbitraria”, sino ser **universal dentro de un conjunto de familias de consulta** frecuentes en auditoría e integridad de datos (por ejemplo: “elementos sin relación”, “conteos por categoría”, “duplicados”, “inconsistencias de metadatos”).

Las limitaciones principales son:

- **Ambigüedad del lenguaje natural:** expresiones equivalentes pueden mapear a consultas distintas si no se restringe el dominio o no existen señales suficientes.
- **Dependencia del esquema:** el sistema solo puede usar predicados/clases presentes en el grafo; si el grafo no contiene cierta información, no puede inventarla.
- **Cobertura acotada:** la robustez se persigue dentro de las familias soportadas; fuera de ellas, el sistema debe fallar de forma controlada.

### 1.4 Estructura del documento
El resto del documento se organiza del siguiente modo. En el **Capítulo 2** se revisa el estado del arte de los enfoques de traducción de lenguaje natural a consultas sobre grafos (KGQA y *semantic parsing*), así como alternativas basadas en catálogos, reglas y modelos generativos. El **Capítulo 3** define el problema en detalle, incluyendo requisitos, casos de uso y el modelo de datos P510-like utilizado.

El **Capítulo 4** presenta el diseño de la solución y justifica las decisiones tecnológicas. El **Capítulo 5** describe la implementación y la estrategia de pruebas y evaluación. Finalmente, los **Capítulos 6 y 7** recogen planificación/presupuesto y el marco socio-económico/legal, y el **Capítulo 8** expone conclusiones y líneas de trabajo futuro, con la bibliografía en el **Capítulo 9**.

### 1.5 Declaración de uso de herramientas de IA (resumen)
Este trabajo se ha desarrollado con apoyo de herramientas de IA como asistente de redacción y programación. En particular, se han utilizado para:

- Proponer estructuras de capítulos, listas de verificación y reformulaciones.
- Sugerir fragmentos de código y refactorizaciones en el repositorio.

En todos los casos, el contenido se ha **revisado**, **adaptado** y **validado** manualmente. La evaluación experimental y la redacción final se basan en el comportamiento verificable del sistema implementado. Se detalla una declaración ampliada en el Capítulo 7.

**Fuentes mínimas recomendadas**
- Estándar RDF: W3C RDF 1.1 Primer [1]
- Estándar SPARQL: W3C SPARQL 1.1 Overview [2]

---

## 2. Estado del arte (10–14 págs)
### 2.1 NL→consulta sobre grafos (KGQA / semantic parsing)
La traducción de lenguaje natural a una consulta formal se sitúa en el área de *Question Answering* y, más concretamente, en **semantic parsing**: transformar una pregunta en una representación lógica o ejecutable. Cuando el conocimiento subyacente es un grafo (RDF/Knowledge Graph), el problema suele denominarse **Question Answering over Knowledge Graphs (KGQA)**.

En SPARQL, el “espacio de programas” es especialmente rico: la semántica se expresa con patrones de triples, restricciones con filtros, opcionalidad (`OPTIONAL`) y ausencia de evidencia (`FILTER NOT EXISTS`) tal y como define el estándar [3]. A diferencia de text-to-SQL, donde el esquema suele presentarse como tablas y columnas con nombres relativamente homogéneos, en RDF el esquema se materializa como **IRIs y prefijos** (vocabularios) y admite modelos más flexibles (por ejemplo, clases opcionales, propiedades multi-valor y grafos con incompletitud). Esto aumenta la dificultad de (i) decidir qué predicados usar y (ii) garantizar que la consulta generada respeta el esquema real del grafo.

Por ello, una parte relevante de los enfoques de KGQA dependen de un fuerte acoplamiento al **esquema**, al menos mediante uno de estos mecanismos: (a) diccionarios o lexicones palabra→predicado/clase, (b) alineamiento de menciones a entidades del grafo, (c) reglas o gramáticas que restringen la generación, y/o (d) entrenamiento con supervisión (total o débil) para aprender el mapeo NL→consulta.

En este TFG, además, existe un requisito adicional de ingeniería: la generación debe ser **determinista** y ejecutable **offline**, lo que condiciona las técnicas seleccionables.

#### 2.1.1 Enfoques “clásicos” de semantic parsing
En la literatura se encuentran líneas de trabajo que aprenden a mapear lenguaje natural a representaciones formales mediante estructuras lingüísticas (por ejemplo, gramáticas CCG) y aprendizaje supervisado. Un ejemplo temprano y ampliamente citado es el trabajo de Zettlemoyer y Collins, que aprende un mapeo a formas lógicas usando CCG probabilísticas [4]. Este tipo de enfoques aporta una idea clave: imponer una **estructura intermedia** que limite el espacio de programas posibles y que permita explicar cómo se compone la consulta a partir de fragmentos del texto.

Posteriormente, la comunidad explora configuraciones donde el grafo es una base de conocimiento a gran escala y la supervisión disponible es débil (pares pregunta–respuesta) en lugar de consultas explícitas. Berant et al. proponen un enfoque en Freebase donde se induce el programa a partir de la señal de respuesta [5]. En términos prácticos, estos trabajos motivan dos conclusiones: (i) el anclaje al esquema y la desambiguación sobre el grafo son el cuello de botella, y (ii) la evaluación requiere protocolos cuidadosos para evitar sobreajustes a un único esquema o a programas repetidos.

### 2.2 Enfoques principales
En la literatura y en la práctica industrial se observan tres familias de enfoques relevantes:

1) **Recuperación basada en catálogo/plantillas.** Se define un conjunto de consultas SPARQL (plantillas) y se selecciona la más cercana a la intención del usuario. Suele ser robusto y fácil de validar, pero limita la expresividad al catálogo predefinido.

2) **Compilación determinista por reglas u operadores.** En lugar de elegir una plantilla concreta, el sistema identifica un **operador** (por ejemplo, “faltan datos”, “conteo por categoría”, “duplicados”) y lo compila a un patrón SPARQL, rellenando variables y predicados a partir del esquema. Este enfoque puede generalizar dentro del dominio y mantiene control estricto del resultado.

3) **Modelos neuronales y LLM.** Los modelos generativos pueden producir consultas complejas a partir de ejemplos, pero plantean riesgos: (i) no determinismo, (ii) posibilidad de **inventar** predicados/clases no existentes, y (iii) dependencia de un servicio o de un modelo pesado. En dominios con auditoría y control, estos riesgos pueden ser inaceptables si no se añade un fuerte control posterior.

En el contexto concreto de este TFG (auditoría de integridad de datos y trazabilidad), estos riesgos se conectan con requisitos prácticos: las consultas deben ser **repetibles** y deben respetar un **esquema observado**. Por ello, incluso aunque se discutan LLM como alternativa, la implementación prioriza un pipeline determinista con validación previa a la ejecución (checker) y con ejecución local de SPARQL conforme al estándar [3]. Esta elección facilita la trazabilidad del experimento y reduce incertidumbre metodológica, alineándose con la preocupación por reproducibilidad en evaluación de KGQA [7].

La Tabla 1 resume, de forma cualitativa, los trade-offs relevantes para este trabajo.

| Enfoque | Ventajas | Inconvenientes | Adecuación a este TFG |
|---|---|---|---|
| Catálogo/plantillas | Validación simple, alta precisión por consulta | Cobertura limitada, mantenimiento manual | Útil como baseline, no como solución principal |
| Operadores/reglas | Determinismo, control del esquema, extensible por familias | Requiere ingeniería del dominio y señales NL | **Enfoque elegido** |
| Neuronal/LLM | Expresividad, menos reglas explícitas | No determinismo, invención de esquema, coste/privacidad | Útil para comparación y discusión |

#### 2.2.1 Text-to-SQL como referencia metodológica
Aunque text-to-SQL no es equivalente a text-to-SPARQL, comparte una motivación importante: traducir preguntas en NL a un lenguaje formal de consulta. En particular, el benchmark Spider introduce explícitamente el reto de **generalización a esquemas no vistos** y ha servido como referencia para discutir cobertura, complejidad y evaluación en tareas de *semantic parsing* [6]. En este TFG se toma Spider como inspiración metodológica (familias de consulta, conjuntos de ejemplos y evaluación reproducible), aunque el dominio y el lenguaje formal final sean distintos.

#### 2.2.2 Evaluación y reproducibilidad en KGQA
La comparación entre sistemas KGQA es difícil porque cambian los datasets, las particiones, el preprocesado y, en ocasiones, la propia definición de métricas. Perevalov et al. analizan este problema y proponen un recurso comunitario de leaderboard, destacando riesgos de “crisis de replicación” cuando la evaluación no es trazable o no es comparable entre trabajos [7]. Esta observación conecta directamente con los requisitos de este TFG: si el objetivo es soportar auditorías y consultas repetibles, la **reproducibilidad** y la **explicación** dejan de ser opcionales.

### 2.3 Posicionamiento del TFG
Este TFG adopta un enfoque de **compilación por operadores** con *grounding* al esquema y un **checker anti-invención**. La intención es maximizar la reproducibilidad y la seguridad del resultado: toda consulta generada debe ser ejecutable en un grafo local y no debe introducir términos fuera del conjunto observado en los datos. Además, se incorpora **explicabilidad** para que el usuario pueda entender por qué se eligió un operador y cómo se interpretaron palabras y frases.

Este posicionamiento no busca competir en generalidad con enfoques generativos, sino ofrecer una solución sólida para un dominio acotado y con necesidades de auditoría.

En concreto, el sistema diseñado en este trabajo se sitúa más cerca de los enfoques (1) y (2) descritos (catálogo/plantillas y compilación determinista por operadores), pero incorpora elementos inspirados por el estado del arte: (i) un *grounding* explícito al esquema (para evitar términos inventados) y (ii) una estrategia de evaluación que incluye consistencia frente a paráfrasis y ejecución real de la consulta.

**Referencias clave**: estándar SPARQL [3], trabajos clásicos de semantic parsing [4], KBQA débilmente supervisado [5], benchmark metodológico [6] y discusión de reproducibilidad en KGQA [7].

---

## 3. Análisis (12–18 págs)
> En este capítulo describes el **qué**: problema, requisitos y casos de uso.

### 3.1 Descripción del problema (qué se quiere resolver)
El problema a resolver consiste en permitir que un usuario formule preguntas en lenguaje natural sobre un conjunto de datos representado como un grafo RDF y reciba respuestas sin necesidad de conocer SPARQL. El usuario objetivo es un perfil técnico que comprende el dominio (requisitos, verificaciones, evidencias, proveedores, etc.) pero no necesariamente domina la sintaxis o los detalles del esquema RDF.

El sistema debe recibir como **entrada** una pregunta en texto (español o inglés, dependiendo de la configuración) y producir como **salida**: (i) una consulta SPARQL de lectura (`SELECT`) alineada con el esquema del grafo, (ii) el resultado de ejecutarla localmente, y (iii) una explicación comprensible del proceso de traducción.

Las restricciones clave del problema son:

- **Offline:** la ejecución no depende de servicios externos.
- **Determinismo:** las decisiones de compilación son reproducibles.
- **Seguridad:** no se permite SPARQL Update u operaciones de escritura.
- **Control del esquema:** no se inventan clases ni predicados; el sistema se basa en lo que existe en el grafo.

### 3.2 Contexto de datos y modelo del dominio (P510-like)
Para hacer el problema abordable y reproducible, se trabaja con un grafo RDF **sintético** inspirado en un dominio P510-like. A alto nivel, el grafo representa:

- **Artefactos de ingeniería** (por ejemplo, requisitos, modelos, tests, escenarios de V&V).
- **Organizaciones/proveedores** asociados a artefactos.
- **Relaciones de trazabilidad** entre artefactos.
- **Metadatos** asociados a relaciones (contenido, descripción, marcas temporales, etc.).

El grafo utiliza prefijos habituales en RDF y en vocabularios generales:

- `p510:` para el dominio específico (clases y predicados del modelo de trazabilidad).
- `ex:` para extensiones y entidades sintéticas auxiliares.
- `foaf:` para representar organizaciones [8].
- `dcterms:` para metadatos temporales [9].

Un elemento relevante del modelado es el uso de **nodos intermedios de enlace** (*link nodes*). En lugar de expresar una relación como un triple directo `A → B`, se introduce un nodo `L` que permite añadir metadatos a la relación (por ejemplo, tipo de enlace, contentType, timestamp o description). Esto habilita auditorías como “enlaces sin timestamp” o “enlaces con contentType incoherente”.

En términos de patrón, la idea es separar “relación” y “metadatos de la relación”:

- Entidad origen (p. ej. un requisito) se conecta a un nodo de enlace mediante un predicado del dominio (p. ej. `Satisfied_by`, `Verified_by`, `Validated_by`).
- El nodo de enlace apunta a la entidad destino mediante un predicado genérico (p. ej. `Link`).
- El nodo de enlace contiene metadatos: `ContentType`, `Description`, timestamps, etc.

Este modelado es típico en escenarios donde la trazabilidad no es solo un vínculo binario, sino un artefacto con propiedades auditables.

**Figura 3.X — Patrón de *link node* para trazabilidad (especificación).**

Para documentar el modelado de trazabilidad, la figura debe representar (como mínimo) los siguientes elementos:

- **Nodo origen** (ej.: `p510:Requirement`) con variable `?req`.
- **Nodo intermedio** `?link` tipado como `p510:Traceability_Link_Type`.
- **Nodo destino** (ej.: un modelo) con variable `?model`.
- **Aristas (predicados):**
	- `?req p510:Satisfied_by ?link` (ejemplo de relación de trazabilidad).
	- `?link p510:Link ?model` (puntero al destino).
	- Metadatos en el link node, por ejemplo:
		- `?link p510:ContentType "Physical Model"`
		- `?link p510:Description ?desc`
		- `?link dcterms:created ?ts` (o el predicado de timestamp que use el grafo).

**Pie de figura sugerido:** “La relación de trazabilidad se reifica como un nodo intermedio que permite adjuntar metadatos auditables (tipo, descripción, timestamp), habilitando consultas de calidad de datos como ausencia de timestamp o incoherencias de contentType”.

#### 3.2.1 Dataset sintético y reproducibilidad
El dataset se genera de forma sintética para poder (i) compartirlo sin restricciones, (ii) controlar el tamaño y la densidad de trazas, y (iii) repetir experimentos bajo condiciones equivalentes. En la práctica, el repositorio incorpora un generador que permite parametrizar el número de requisitos, modelos, tests y proveedores, y produce un fichero TTL reproducible.

Este enfoque permite diseñar un banco de pruebas para auditorías típicas del dominio sin depender de datos reales (que podrían estar sujetos a confidencialidad). La contrapartida es que la complejidad semántica del mundo real no está completamente representada; por ello, en la discusión de limitaciones (Cap. 1 y Cap. 8) se explicita el alcance.

### 3.3 Requisitos
#### 3.3.1 Requisitos funcionales
A partir del problema descrito, se definen los siguientes requisitos funcionales:

- **RF1 — Generación de consulta:** dado un texto, el sistema genera una consulta SPARQL de lectura (`SELECT`) correspondiente a la intención detectada.
- **RF2 — Ejecución local:** la consulta se ejecuta sobre un grafo local (RDFLib) y se devuelven filas/columnas de resultados.
- **RF3 — Grounding al esquema:** predicados, clases y entidades usados en la consulta deben existir en el grafo (o ser literales válidos), evitando inventar vocabulario.
- **RF4 — Explicación:** el sistema devuelve una traza del proceso (normalización, hits de grounding, operador elegido, plantilla/patrón SPARQL aplicado).
- **RF5 — Interfaz de uso:** al menos una CLI y una demo visual que permitan introducir preguntas y revisar SPARQL/resultados/explicación.

#### 3.3.2 Requisitos no funcionales
Los requisitos no funcionales fijan las propiedades de calidad de la solución:

- **RNF1 — Determinismo:** para una misma entrada, el sistema produce la misma consulta y el mismo resultado (a igualdad de dataset).
- **RNF2 — Reproducibilidad:** se incluyen scripts y datos para reproducir la generación del grafo y la evaluación.
- **RNF3 — Seguridad:** se bloquean explícitamente operaciones de escritura (SPARQL Update) y se limita el espacio de consultas.
- **RNF4 — Extensibilidad:** el sistema debe permitir incorporar nuevas familias de consultas mediante nuevos operadores sin reescribir todo el pipeline.

### 3.4 Casos de uso
Los casos de uso concretan las familias de preguntas que el sistema debe soportar. En este trabajo se priorizan aquellas que son frecuentes en auditoría, gobierno del dato y trazabilidad.

| Caso de uso | Descripción | Patrón SPARQL típico |
|---|---|---|
| UC1 — Faltan metadatos | Detectar enlaces/entidades sin atributos esperados (timestamp, description, etc.) | `FILTER NOT EXISTS { ... }` |
| UC2 — Conteos / distribuciones | Resúmenes por categorías (por proveedor, por estado, por maturity) | `GROUP BY` + `COUNT` |
| UC3 — Integridad/coherencia | Duplicados, inconsistencias en contentType, enlaces repetidos | `GROUP BY` + `HAVING`, filtros |
| UC4 — Trazabilidad end-to-end | Elementos sin traza completa o modelos sin pruebas | `NOT EXISTS` / patrones encadenados |

A continuación se incluyen ejemplos de preguntas (en español) que ilustran cada caso de uso. El sistema implementado trabaja principalmente con preguntas en inglés, pero estos ejemplos sirven para documentar la intención y facilitar la discusión de cobertura.

- **UC1 — Faltan metadatos / faltan relaciones**
	- “¿Qué requisitos no están satisfechos por ningún modelo físico?” → ausencia de traza `Satisfied_by` con `ContentType = "Physical Model"`.
	- “¿Qué modelos físicos no tienen tests asociados?” → ausencia de `Verified_by` con `ContentType = "Test Case"`.
	- “¿Qué enlaces no tienen timestamp?” → auditoría de metadatos (ausencia de atributo).

- **UC2 — Conteos y distribuciones**
	- “¿Cuántos proveedores hay en total?” → `COUNT(DISTINCT ...)` sobre organizaciones.
	- “¿Cuántos modelos hay por proveedor?” → agrupación por proveedor y conteo.
	- “¿Distribución de requisitos por estado de madurez (maturity)?” → `GROUP BY` + `COUNT`.

- **UC3 — Integridad/coherencia**
	- “¿Hay enlaces duplicados (misma fuente, relación y destino)?” → `GROUP BY` + `HAVING(COUNT>1)`.
	- “¿Hay enlaces con contentType incoherente con el destino?” → regla de coherencia del tipo de contenido.
	- “¿Existen links sin description?” → auditoría de atributo ausente.

- **UC4 — Trazabilidad end-to-end**
	- “¿Qué requisitos no tienen trazabilidad completa hasta test?” → ausencia de una cadena requisito→modelo→test.
	- “¿Qué modelos físicos no aparecen en ninguna cadena de verificación/validación?” → auditoría de cobertura de V&V.

Estos ejemplos se conectan con consultas SPARQL de referencia (directorio `queries_p510/`) y con familias/operadores del motor dinámico (Cap. 5).

Para hacer los casos de uso verificables, cada familia se asocia a un conjunto de consultas de referencia (en `queries_p510/`) y/o a ejemplos NL→SPARQL en el catálogo de evaluación. De este modo, el caso de uso no queda descrito solo “en texto”, sino que tiene una comprobación ejecutable.

### 3.5 Criterios de aceptación y métricas
Para considerar el sistema válido, se establecen los siguientes criterios de aceptación:

- **Ejecución correcta:** la SPARQL generada se ejecuta sin errores sobre el grafo.
- **Alineación al esquema:** no aparecen prefijos o predicados inexistentes.
- **Cobertura de ejemplos:** porcentaje de ejemplos del conjunto de evaluación que el sistema resuelve dentro del conjunto de operadores soportados.
- **Robustez a parafraseo:** dentro de una misma familia (misma intención), distintas paráfrasis deben converger al mismo operador y a resultados consistentes (por ejemplo, misma cardinalidad o misma salida esperada).

En la evaluación se reportan métricas simples y reproducibles: tasa de éxito por ejemplo, distribución de operadores elegidos y consistencia por grupos de paráfrasis.

Para interpretar los resultados de forma honesta (y evitar conclusiones infladas), es importante distinguir entre:

- **Corrección ejecutable:** la consulta se ejecuta sin error en el motor SPARQL (en este caso, RDFLib [10]).
- **Corrección semántica aproximada:** el resultado coincide con lo esperado para el caso de uso (por ejemplo, “requisitos sin modelo físico” devuelve exactamente los requisitos que no tienen ese enlace). Esta corrección requiere un oráculo (consulta de referencia o validación manual) y no se deduce solo del hecho de “ejecutar”.
- **Estabilidad:** la misma intención expresada con paráfrasis conduce a un routing consistente y, por tanto, a resultados comparables.

Esta distinción es relevante porque, como discute la literatura de evaluación en KGQA, comparar sistemas sin un protocolo claro puede llevar a resultados poco reproducibles o difíciles de verificar [7].

---

## 4. Diseño (10–14 págs)
> En este capítulo defines el **cómo** a nivel de arquitectura y decisiones tecnológicas.

### 4.1 Solución propuesta
La solución propuesta se basa en un motor de traducción determinista que identifica (a) la **intención** del usuario dentro de un conjunto de familias soportadas y (b) los elementos del dominio relevantes (entidades, predicados, filtros). A partir de esa información compila una SPARQL siguiendo un patrón asociado a un **operador**.

Un principio central del diseño es el **grounding**: las palabras y frases detectadas no se interpretan “en abstracto”, sino que se asocian a términos del esquema (predicados/clases) extraídos del grafo. Esta decisión permite controlar el comportamiento del sistema y evita resultados engañosos.

La explicación se modela como una traza que incluye: normalización aplicada, coincidencias de grounding (palabra/frase → concepto del esquema), operador elegido y justificación, y el patrón SPARQL utilizado.

### 4.2 Arquitectura del sistema
La arquitectura sigue un pipeline lineal con pasos claramente separables:

1) **Normalización y sinónimos:** homogeniza texto (por ejemplo, mayúsculas/minúsculas, tildes, variantes léxicas) para robustez.
2) **Indexado del esquema:** extrae del grafo el conjunto de clases/predicados relevantes, generando un índice consultable.
3) **Grounding:** detecta señales en el texto y produce hipótesis de mapeo a entidades/predicados/operadores.
4) **Routing:** decide qué operador compila la consulta y qué argumentos utilizar.
5) **Compilación:** genera SPARQL a partir de un patrón controlado.
6) **Checker:** valida que la consulta no contiene escritura (Update) y que todos los términos pertenecen al esquema.
7) **Ejecución:** ejecuta la consulta en RDFLib y serializa los resultados.
8) **Explicación:** devuelve la traza completa para inspección.

Los componentes se exponen mediante una CLI y una interfaz visual, además de scripts de evaluación.

**TODO:** añadir diagrama de arquitectura (bloques del pipeline y artefactos de entrada/salida).

**Figura 4.X — Diagrama de arquitectura (especificación).**

La figura debe mostrar un pipeline con cajas numeradas (1–8) y artefactos de entrada/salida. Recomendación de composición:

- **Entrada:** “Pregunta en lenguaje natural (string)”.
- **Caja 1:** “Normalización + sinónimos” → salida: “Texto normalizado”.
- **Caja 2:** “Carga del grafo TTL (RDFLib)” [10] → salida: “Grafo RDF”.
- **Caja 3:** “Indexado del esquema” → salida: “Schema index (clases/predicados/prefijos)”.
- **Caja 4:** “Grounding” → salida: “Hits (palabra/frase → término del esquema)”.
- **Caja 5:** “Routing (familia/operador)” → salida: “Operador + argumentos”.
- **Caja 6:** “Compilación SPARQL” → salida: “Consulta SPARQL”.
- **Caja 7 (gate):** “Checker (seguridad + no invención)” → salida: “SPARQL validada / error controlado”.
- **Caja 8:** “Ejecución SPARQL (RDFLib)” [10] → salida: “Resultados (tabla)”.
- **Salida paralela (desde 4–7):** “Explicación / traza” mostrada en CLI y demos.

Además, la figura puede incluir dos “clientes” a la derecha:

- **CLI** (`src/text2sparql_cli.py`) consumiendo el pipeline.
- **Demo visual** (HTML o Streamlit) [11] consumiendo el pipeline.

**Pie de figura sugerido:** “Pipeline determinista con *gates* de validación antes de ejecutar la consulta; las interfaces son delgadas y solo orquestan carga de grafo, generación, ejecución y presentación”.

Desde el punto de vista de ingeniería, esta arquitectura tiene dos ventajas relevantes:

- **Aislamiento de responsabilidades.** Cada paso tiene una entrada y salida claras (texto normalizado, hits de grounding, operador/ruta elegida, SPARQL generada). Esto facilita depuración y permite justificar decisiones en la memoria.
- **Puntos de control (“gates”) para seguridad y calidad.** El checker actúa como un control obligatorio antes de ejecutar la consulta: si la SPARQL contiene escritura o términos fuera de esquema, la ejecución se bloquea.

La implementación concreta sigue esta estructura: el motor de generación concentra la lógica de grounding, routing y compilación; las interfaces (CLI y demo) son delgadas y se limitan a cargar el grafo, invocar al generador y presentar SPARQL, resultados y explicación.

### 4.3 Entorno tecnológico
Se utiliza Python por su ecosistema de procesamiento de texto y por la disponibilidad de RDFLib para manipulación y consulta de grafos RDF. RDFLib ofrece una API madura para cargar ficheros TTL y ejecutar consultas SPARQL. Para la interfaz de demostración se utiliza Streamlit, por su rapidez para construir UI de pruebas orientada a datos.

En concreto, el backend de ejecución de consultas se apoya en RDFLib [10], mientras que la demo visual se construye con Streamlit [11].

El dataset se representa en formato Turtle (TTL) y se genera de forma sintética para garantizar reproducibilidad.

### 4.4 Decisiones de diseño y alternativas
Las decisiones clave se justifican por los requisitos de control y auditoría:

- **Offline y determinista:** asegura reproducibilidad y evita dependencia de terceros; además reduce riesgos de privacidad.
- **Checker anti-invención:** mejora la credibilidad del sistema y evita consultas “aparentemente correctas” pero inválidas en el grafo.
- **Operadores:** permiten combinar control y extensibilidad: cada nueva familia se añade como un operador con un patrón SPARQL validable.

Como alternativas se consideran: (i) plantillas fijas, con precisión alta pero cobertura limitada, y (ii) enfoques generativos, con mayor expresividad pero menos control sin mecanismos adicionales.

Una decisión adicional, específica para este TFG, es priorizar la **ejecución real** de la SPARQL como parte del propio pipeline. En lugar de detenerse en “generar una consulta plausible”, el sistema valida y ejecuta localmente cada salida. Esto reduce el riesgo de aceptar consultas sintácticamente correctas pero no ejecutables sobre el dataset.

---

## 5. Implementación y pruebas (16–22 págs)
### 5.1 Estructura del proyecto
La implementación se organiza en módulos que separan claramente el motor de traducción, las interfaces y la evaluación. En el repositorio se incluyen:

- Motor de traducción NL→SPARQL.
- Interfaz de línea de comandos (CLI) para ejecución rápida y reproducible.
- Demos para uso interactivo (visual/web).
- Scripts para generar el grafo sintético y ejecutar el conjunto de evaluación.

Esta separación facilita la trazabilidad de cambios: el núcleo (motor) permanece estable mientras las interfaces pueden evolucionar sin afectar a la lógica.

De forma práctica, el punto de entrada del motor es el módulo `src/text2sparql.py`, y las principales interfaces y utilidades son:

- CLI: `src/text2sparql_cli.py` (modo “translate” o “run”).
- Evaluación automática: `src/text2sparql_eval.py` (validación de consultas de referencia o generación desde NL).
- Demo visual: `src/demo_visual.py` (Streamlit) [11].
- Generación del grafo sintético: `src/p510_generate_synthetic.py`.
- Ejecución de queries P510 de referencia: `src/run_queries_p510.py`.

### 5.2 Implementación del motor
#### 5.2.1 Normalización y sinónimos
La normalización busca reducir variaciones superficiales del lenguaje sin perder intención. Se aplican transformaciones como: unificación de mayúsculas/minúsculas, normalización de caracteres y sustitución de sinónimos y variantes frecuentes del dominio. El objetivo es que expresiones equivalentes (p. ej. “proveedor” vs “supplier”) lleguen a una representación común para el *grounding*.

En la implementación, este comportamiento se apoya en una función de normalización estable (minúsculas, eliminación conservadora de caracteres no alfanuméricos y tokenización), y en un diccionario opcional de sinónimos/canonizaciones cargable desde un fichero de “prompt” (por defecto `prompts/system_en.txt`). Esta decisión permite mantener el sistema offline y, al mismo tiempo, ajustar vocabulario del dominio sin reentrenar modelos.

En un sistema de reglas, la normalización tiene un papel especialmente importante: pequeñas variaciones (“content type” vs “contenttype”, pluralización, guiones) pueden cambiar por completo el routing. Por ello se prioriza un conjunto pequeño de transformaciones estables frente a técnicas probabilísticas.

#### 5.2.2 Indexado del esquema
Antes de generar cualquier consulta, el sistema construye un índice del esquema observado en el grafo: clases (`rdf:type`) y predicados presentes. Este índice cumple dos funciones: (i) facilita el mapeo de texto a términos del esquema, y (ii) permite validar que la consulta generada solo usa términos existentes.

El indexado puede restringirse a determinados prefijos del dominio para evitar introducir vocabularios no deseados. Esto es especialmente útil en grafos que mezclan vocabularios generales y específicos.

En la práctica, el índice se obtiene recorriendo el grafo cargado (TTL) y recolectando: (a) todas las clases que aparecen como objeto de `rdf:type`, y (b) todos los predicados que aparecen en cualquier triple. Además, se extrae el conjunto de prefijos declarados en el grafo para poder emitir cabeceras `PREFIX` coherentes y validar que la consulta no introduce espacios de nombres ajenos.

#### 5.2.3 Grounding palabra/frase → concepto
El *grounding* identifica fragmentos del texto que actúan como señales: entidades (p. ej. “Supplier 03”), predicados o atributos (p. ej. “timestamp”, “description”), y operadores (p. ej. “sin”, “faltan”, “cuántos”, “por”). El resultado se representa como un conjunto de *hits* con información suficiente para explicar la decisión: texto detectado, tipo de hit, candidato del esquema asociado y una puntuación o justificación.

La explicación final se compone de estos hits más el razonamiento del router (por qué se eligió una familia y no otra).

En términos de implementación, el *grounding* produce una lista de hits tipados (por ejemplo, `operator`, `entity`, `attribute`, `literal`) junto con el texto detectado y el concepto del esquema asociado. Esta traza se serializa como líneas de explicación que pueden mostrarse en CLI (`--explain`) o en la demo visual.

#### 5.2.4 Routing y operadores
El motor soporta dos estilos de generación, seleccionables por configuración:

- **Motor dinámico (por defecto).** Construye SPARQL “al vuelo” a partir del índice del esquema y señales lingüísticas. En este modo, el pipeline intenta primero una generación **composicional** conservadora (una estructura base con clase origen, relación y/o clase destino) y, si no encaja, deriva a patrones más especializados para familias de auditoría y agregación.
- **Motor por catálogo.** Selecciona una consulta SPARQL pre-escrita desde un catálogo JSONL (por ejemplo `eval/text2sparql_examples.jsonl`) usando similitud de texto. De forma opcional, cuando la similitud no alcanza un umbral, se usa un clasificador Naive Bayes entrenado offline para predecir el id de la consulta con suficiente confianza.

Aunque en el código no se implementa un “registro” explícito de operadores como objetos, el comportamiento equivale a una compilación por familias: la presencia de determinados tokens o hits (p. ej. `missing/without`, `count/how-many`, `by/per`, `duplicate`) dirige la generación hacia patrones que usan construcciones SPARQL estándar como `FILTER NOT EXISTS`, agregación con `GROUP BY`/`COUNT`, o filtros y opcionales [3].

De forma resumida, algunas señales y familias relevantes para el dominio P510-like son:

- **Ausencia / incompletitud (NOT EXISTS).** Disparadores: “missing/without/lack/absent”, “no …”, “do not have”. Compila a patrones con `FILTER NOT EXISTS { ... }` para detectar entidades o enlaces sin relación/metadato.
- **Conteos y distribuciones (GROUP BY).** Disparadores: “how many / count / number of”, junto con “by/per/grouped by”. Compila a `COUNT(DISTINCT ...)` y agrupación por un atributo (p. ej. proveedor/estado).
- **Duplicados e integridad (HAVING / agrupación).** Disparadores: “duplicate/repeated/same link”. Compila a agregaciones con `GROUP BY` y condiciones sobre cardinalidad (p. ej. `HAVING(COUNT(*)>1)`).
- **Listados (SELECT DISTINCT).** Disparadores: “list/show/display/which/what”. Compila a `SELECT DISTINCT` con ordenación y, cuando existe, proyección de identificadores.

Este routing está diseñado para ser conservador: cuando la pregunta sugiere una familia “especializada” (p. ej. auditorías de timestamps, incoherencias de content type, trazabilidad end-to-end), el generador composicional se inhibe y delega en patrones más específicos.

Esta decisión mantiene la solución determinista y extensible: para añadir una familia nueva, se añade un patrón especializado y sus precondiciones (señales NL + grounding necesario), y el checker garantiza que no se introduzcan términos fuera del esquema.

#### 5.2.6 Parámetros de configuración y modos de uso
La generación se controla mediante una configuración explícita (por ejemplo, `GenerationConfig`) que fija propiedades relevantes para reproducibilidad:

- `engine`: selecciona motor dinámico o catálogo.
- `limit`: fuerza un `LIMIT` por defecto en consultas `SELECT` cuando no está presente.
- `match_threshold` y `max_suggestions`: controlan aceptación del emparejamiento por similitud en modo catálogo y el número de sugerencias en fallo.
- `synonyms_file`: permite cargar un glosario/sinónimos para normalización y robustez.
- `classifier_model_file` y `classifier_min_prob`: activan un clasificador offline (Naive Bayes) entrenado con el catálogo para intentar predecir directamente el id de una consulta cuando la similitud textual no es suficiente.

Estos parámetros son relevantes para el capítulo de evaluación: permiten congelar un “perfil” del sistema y reportar resultados comparables entre iteraciones.

#### 5.2.5 Checker y seguridad
El checker aplica dos validaciones críticas. Primero, una validación de **seguridad** que rechaza cualquier consulta con sintaxis asociada a escritura o actualización (SPARQL Update). Segundo, una validación de **esquema** que comprueba que cada IRI/prefijo utilizado pertenece al conjunto indexado del grafo.

Este mecanismo convierte los fallos en errores explícitos y controlados: si una pregunta no puede resolverse con el esquema disponible, el sistema no debe “inventar” una respuesta, sino informar adecuadamente.

Desde el punto de vista del estándar, esta separación es importante: SPARQL 1.1 define tanto un lenguaje de consulta (lectura) [3] como operaciones de actualización [12]. El sistema de este TFG restringe su superficie de ataque a consultas `SELECT` (y variantes equivalentes) y bloquea explícitamente palabras clave asociadas a Update. A nivel de esquema, el checker valida prefijos declarados, términos abreviados (qnames como `p510:Requirement`) y IRIs completas (`<...>`), proporcionando sugerencias cuando el término es “parecido” a uno existente.

Además de las comprobaciones de vocabulario, el checker implementa un bloqueo por palabras clave (lista de operaciones prohibidas) y valida que los espacios de nombres declarados en `PREFIX` existan en el grafo o correspondan a vocabularios estándar. En caso de fallo, devuelve un error con términos problemáticos y sugerencias de términos cercanos, lo que ayuda a depurar reglas de *grounding* y plantillas.

### 5.3 Pruebas y evaluación
#### 5.3.1 Estrategia de pruebas
- Pruebas unitarias/funcionales (si aplica) y pruebas de regresión.
- Smoke test de paráfrasis por grupos (consistencia).

La estrategia de verificación se centra en pruebas **funcionales** reproducibles: para cada pregunta de un conjunto de referencia, el sistema debe generar una SPARQL válida, ejecutarla y devolver resultados. Dado que el sistema es determinista y está anclado a un dataset local, esta verificación puede automatizarse como regresión.

Un aspecto clave es la robustez a parafraseo: para cada intención, se define un grupo de preguntas equivalentes (paráfrasis) y se exige consistencia del operador y del resultado (por ejemplo, misma cardinalidad o coincidencia de filas, según el caso). Esto permite detectar “derivas” introducidas por cambios en reglas de routing o normalización.

En el repositorio, esta idea se materializa en ficheros de salida de *smoke test* (carpeta `eval/`) donde se comparan ejecuciones sobre conjuntos de paráfrasis, y en un script de evaluación automático que recorre ejemplos en JSONL y reporta tasa de éxito y tiempos de ejecución.

El script `src/text2sparql_eval.py` implementa dos modos:

- `--mode reference`: ejecuta las consultas SPARQL de referencia y valida que el dataset y las consultas son consistentes.
- `--mode generate`: genera SPARQL desde la pregunta en lenguaje natural con el motor seleccionado (`--engine dynamic|catalog`) y valida que la consulta generada se ejecuta.

Al tratarse de un sistema determinista, estas pruebas sirven también como regresión: cambios en normalización, routing o checker se reflejan de inmediato en la tasa de aciertos.

#### 5.3.2 Dataset de evaluación
- Lista de ejemplos NL→SPARQL (familias) y cómo se ejecutan.

El dataset de evaluación se compone de un conjunto de preguntas en lenguaje natural, cubriendo las familias de consulta soportadas. Cada ejemplo se ejecuta sobre el grafo sintético y se registra:

- Operador seleccionado.
- SPARQL generada.
- Número de filas y/o contenido de resultados.
- Explicación (traza) para análisis cualitativo.

En este repositorio, el fichero `eval/text2sparql_examples.jsonl` contiene **N = 34** ejemplos (líneas JSONL no vacías). Cada ejemplo incluye al menos una pregunta (`nl`) y una consulta SPARQL (`sparql`).

Para caracterizar el conjunto sin depender de anotaciones manuales, una aproximación reproducible es agrupar por “rasgos” sintácticos de SPARQL: presencia de `FILTER NOT EXISTS` (auditorías de ausencia), presencia de agregación (`COUNT`, `GROUP BY`) y presencia de `HAVING` (duplicados). Con este criterio, la distribución observada es:

- **OTHER/LIST (sin NOT EXISTS/GROUP BY/HAVING): 12**
- **AGG/COUNT/GROUP BY: 11**
- **MISSING/NOT EXISTS: 8**
- **DUPLICATES/HAVING: 3**

Esta descomposición es útil para reportar cobertura por familia y para detectar rápidamente regresiones: si una modificación rompe, por ejemplo, todos los casos de `NOT EXISTS`, el impacto es visible por categoría.

El catálogo de referencia se define en un fichero JSONL con campos como `id`, `nl` (pregunta) y `sparql` (consulta). Este formato facilita tanto la evaluación de consultas “gold” (modo `reference`) como la evaluación de la generación desde NL (modo `generate`), ya que el mismo conjunto sirve como oráculo de ejecución y como conjunto de intenciones.

**Cómo fijar N y la distribución por familias.** Para completar la memoria, basta con contar el número de líneas (ejemplos) del JSONL y clasificar por tipo de intención/operador (por ejemplo, a partir del prefijo del `id` o de etiquetas manuales). Este análisis puede incluirse en forma de tabla: filas=operador/familia, columnas=#ejemplos, #grupos de paráfrasis y tasa de éxito.

#### 5.3.3 Resultados
- Tablas: cobertura, errores, consistencia entre paráfrasis.
- 2–3 casos de estudio con explicación.

Los resultados se presentan en forma de tablas de cobertura y análisis de fallos. Un formato típico incluye:

- **Cobertura por operador:** número de ejemplos resueltos por familia.
- **Errores por tipo:** no se pudo hacer grounding, operador no aplicable, consulta inválida, etc.
- **Consistencia de paráfrasis:** porcentaje de grupos sin divergencias.

Además, se recomienda incluir casos de estudio donde la explicación aporte valor: por ejemplo, una auditoría `NOT EXISTS` donde se vea claramente qué términos del esquema se detectaron y por qué se eligió dicho patrón.

En el momento de cerrar esta versión de la memoria, se han ejecutado las pruebas automáticas del repositorio sobre el grafo sintético generado por defecto. En concreto:

- `python src/text2sparql_eval.py --mode reference` (ejecuta SPARQL de referencia del JSONL).
- `python src/text2sparql_eval.py --mode generate --engine dynamic` (genera desde NL y valida ejecución).
- `python src/text2sparql_eval.py --mode generate --engine catalog` (selecciona desde catálogo y valida ejecución).

En este entorno, el resultado ha sido **34/34 OK (100.0%)** en los tres modos anteriores.

Conviene interpretar esta cifra como **tasa de ejecución sin error** (la consulta se genera y RDFLib la ejecuta). La equivalencia semántica con una consulta “gold” requiere un criterio adicional (por ejemplo, comparar resultados con la SPARQL de referencia o validar manualmente casos representativos), tal y como se discute en los criterios de aceptación y métricas del Cap. 3.

**Medición de tiempos.** El script `text2sparql_eval.py` reporta un tiempo por ejemplo (ms) que incluye ejecución de la consulta y, en modo `generate`, el coste adicional de generar/seleccionar la SPARQL antes de ejecutarla. En este entorno, el resumen estadístico por modo es el siguiente:

**Tabla 5.W — Tiempo por ejemplo (ms) en evaluación automática (N=34).**

| Modo | Media | Mediana | P90 | Mín | Máx |
|---|---:|---:|---:|---:|---:|
| `reference` (solo ejecutar SPARQL gold) | 132.26 | 19.65 | 95.05 | 7.7 | 3334.4 |
| `generate` + `dynamic` | 300.58 | 47.50 | 1387.70 | 21.6 | 3104.4 |
| `generate` + `catalog` | 168.37 | 55.45 | 150.60 | 32.0 | 3360.8 |

Se observa que la **media** puede estar fuertemente influida por un número pequeño de ejemplos “lentos” (máximos del orden de segundos), por lo que la **mediana** y percentiles (P90) son más representativos para describir la experiencia típica. Este tipo de precaución al reportar métricas ayuda a que la evaluación sea más interpretable y comparable [7].

**Entorno de ejecución (para reproducibilidad):** Python 3.14.3, RDFLib 7.5.0 [10], Streamlit 1.56.0 [11] y pandas 3.0.2.

A continuación se deja una estructura sugerida para reportar resultados de forma clara y verificable.

**Tabla 5.X — Cobertura por familia.**

| Familia/operador | #Ejemplos | #OK | #FAIL | Tasa OK |
|---|---:|---:|---:|---:|
| NOT EXISTS (missing) | 8 | 8 | 0 | 100.0% |
| COUNT / GROUP BY | 11 | 11 | 0 | 100.0% |
| Duplicados (HAVING) | 3 | 3 | 0 | 100.0% |
| Otras (listados/otros) | 12 | 12 | 0 | 100.0% |
| **Total** | 34 | 34 | 0 | 100.0% |

**Tabla 5.Y — Consistencia por paráfrasis.**

Además de evaluar ejemplos “unitarios”, se incluye un *smoke test* de paráfrasis (`eval/paraphrase_smoke.py`) que ejecuta **74 preguntas** organizadas en **26 grupos** (cada grupo representa una intención). Para cada pregunta se registra:

- **Operador** detectado a partir de la traza (`operator:` en la explicación, cuando existe).
- **Número de filas** devueltas al ejecutar la SPARQL.

Se define el criterio de consistencia por grupo como:

- El conjunto de operadores observados en el grupo tiene tamaño 1.
- El conjunto de recuentos de filas observados en el grupo tiene tamaño 1.

En la ejecución registrada en `eval/paraphrase_smoke_out_current_utf8.txt` se obtuvo **74/74 OK** y **26/26 grupos consistentes (100.0%)** bajo el criterio anterior. Esta métrica complementa la tasa de ejecución y es útil para vigilar estabilidad del routing frente a reformulaciones, en línea con buenas prácticas de evaluación reproducible [7].

| Grupo | #Paráfrasis | Operador(es) observado(s) | Filas observadas | ¿Consistente? |
|---|---:|---|---|---|
| A.count.links | 1 | (none) | 1 | Sí |
| A.count.requirements | 1 | (none) | 1 | Sí |
| A.count.suppliers | 3 | (none) | 1 | Sí |
| B.missing.end_to_end | 3 | REQUIREMENTS_MISSING_END_TO_END | 7 | Sí |
| B.missing.models_without_tests | 3 | (none) | 30 | Sí |
| B.missing.req_without_physical_model | 3 | (none) | 8 | Sí |
| C.percent.req_with_model | 3 | (none) | 42 | Sí |
| D.audit.contenttype_mismatch | 3 | LINK_CONTENTTYPE_MISMATCH | 4 | Sí |
| D.audit.duplicates | 3 | DUPLICATE_TRACES_AUDIT | 29 | Sí |
| D.audit.links_missing_timestamps | 3 | LINKS_MISSING_TIMESTAMP | 3 | Sí |
| D.audit.links_without_description | 3 | LINKS_WITHOUT_DESCRIPTION | 2 | Sí |
| E.audit.approved_without_approver | 3 | APPROVED_WITHOUT_APPROVER | 2 | Sí |
| E.audit.req_without_approver | 3 | REQUIREMENTS_WITHOUT_APPROVER | 4 | Sí |
| F.groupby.models_by_approval | 3 | MODELS_BY_APPROVAL_STATE | 2 | Sí |
| F.groupby.req_by_author_org | 3 | REQUIREMENTS_BY_AUTHOR_ORG | 7 | Sí |
| F.groupby.req_by_maturity | 3 | REQUIREMENTS_BY_MATURITY | 4 | Sí |
| F.groupby.req_by_subsystem | 3 | REQUIREMENTS_BY_SUBSYSTEM | 6 | Sí |
| F.groupby.req_by_verification_method | 3 | REQUIREMENTS_BY_VERIFICATION_METHOD | 4 | Sí |
| G.manifest.baseline | 3 | MANIFEST_PROJECT_BASELINE | 1 | Sí |
| G.manifest.dev_environment | 3 | DEV_ENVIRONMENT | 1 | Sí |
| G.manifest.plm_summary | 3 | PLM_SUMMARY | 1 | Sí |
| G.manifest.used_documents | 3 | USED_DOCUMENTS | 5 | Sí |
| H.vnv.incomplete | 3 | VNV_SCENARIOS_INCOMPLETE | 3 | Sí |
| H.vnv.summary | 3 | VNV_SCENARIOS_SUMMARY | 10 | Sí |
| I.supplier.models_by_supplier | 3 | MODELS_BY_SUPPLIER | 6 | Sí |
| I.supplier.models_for_supplier | 3 | MODELS_FOR_SUPPLIER | 8 | Sí |

**Tabla 5.Z — Tipos de fallo.**

| Tipo de fallo | Descripción | Ejemplo | Mitigación |
|---|---|---|---|
| Fuera de cobertura | La intención no corresponde a ninguna familia soportada | No observado en N=34 (catálogo) | Mensaje claro + sugerencias |
| Grounding insuficiente | No se detecta entidad/atributo clave del esquema | No observado en N=34; riesgo típico en extensión de dominio | Ampliar sinónimos / señales |
| Checker (esquema) | La SPARQL contiene un término no presente en el grafo | No observado en N=34; el checker bloquea y explica | Ajustar patrón o vocabulario |
| Checker (seguridad) | Se detecta palabra clave de Update | No observado; bloqueo por diseño | Bloqueo por diseño [12] |
| Error de ejecución | El motor SPARQL devuelve error | No observado en N=34; se detectaría como FAIL | Depuración y tests de regresión |
| Inconsistencia de paráfrasis | Misma intención produce distinto operador o distinto resultado | No observado en 26 grupos (smoke test) | Ajustar routing/normalización + añadir tests |

Al redactar la sección final, es recomendable acompañar estas tablas de 2–3 **casos de estudio**. Por ejemplo:

1) Un caso de ausencia con `FILTER NOT EXISTS`, mostrando la SPARQL generada y la traza (hits de grounding + decisión del router) y explicando cómo se usa esta construcción en SPARQL 1.1 para expresar ausencia [3].
2) Un caso de duplicados con `GROUP BY`+`HAVING`, mostrando la interpretación de “duplicado” en el contexto de link nodes.
3) Un caso de fallo controlado (pregunta fuera de cobertura) para evidenciar que el sistema no “alucina” vocabulario.

Esta forma de presentar resultados favorece la replicación: el lector puede volver a ejecutar el ejemplo en local y comparar SPARQL y resultados, alineándose con buenas prácticas de evaluación [7].

##### Casos de estudio (cualitativo) basados en paráfrasis
En esta sección se incluyen tres casos de estudio construidos a partir del *smoke test* de paráfrasis. El objetivo no es solo “que ejecute”, sino mostrar cómo distintas reformulaciones convergen a la misma intención y, por tanto, al mismo patrón SPARQL y a resultados coherentes.

Los textos de las preguntas se toman literalmente de [eval/paraphrase_smoke.py](eval/paraphrase_smoke.py), y la consistencia (operador y recuento de filas) se comprueba con la ejecución registrada en [eval/paraphrase_smoke_out_current_utf8.txt](eval/paraphrase_smoke_out_current_utf8.txt).

**Caso 1 — Auditoría: enlaces sin timestamps (ausencia de metadatos).**

- **Grupo:** `D.audit.links_missing_timestamps`
- **Paráfrasis evaluadas:**
	- “Audit: links missing mandatory timestamps (Timestamp_Archiving or Timestamp_PLM).”
	- “Find traceability links without timestamps.”
	- “Show links where Timestamp_Archiving or Timestamp_PLM is missing.”
- **Resultado observado:** operador único `LINKS_MISSING_TIMESTAMP` y **3 filas** en las tres reformulaciones.

**Interpretación técnica.** Este caso representa una auditoría típica sobre nodos de enlace: se buscan relaciones cuyo nodo intermedio no contiene un metadato obligatorio. En SPARQL 1.1, la ausencia de un patrón puede expresarse mediante construcciones como `FILTER NOT EXISTS { ... }`, que permiten seleccionar enlaces para los que no existe evidencia de los atributos requeridos [3].

En términos de routing, las tres paráfrasis comparten señales robustas ("audit", "missing", "without", y menciones explícitas de “timestamps”), de modo que el sistema converge al mismo operador especializado. Esto es importante en escenarios de auditoría: si reformular la pregunta cambiase la intención seleccionada, la consulta podría volverse engañosa. La consistencia observada respalda el objetivo de reproducibilidad y estabilidad frente a reformulaciones, alineándose con recomendaciones generales sobre evaluación trazable [7].

**Caso 2 — Distribución: requisitos por estado de madurez (agregación y agrupación).**

- **Grupo:** `F.groupby.req_by_maturity`
- **Paráfrasis evaluadas:**
	- “Distribution of requirements by maturity state.”
	- “Group requirements by Maturity_State.”
	- “Count requirements per maturity state.”
- **Resultado observado:** operador único `REQUIREMENTS_BY_MATURITY` y **4 filas** en las tres reformulaciones.

**Interpretación técnica.** Este caso corresponde a una familia de consultas de resumen: agrupar por una categoría (`Maturity_State`) y contar cuántos elementos caen en cada grupo. SPARQL 1.1 soporta agregación y agrupación (`COUNT`, `GROUP BY`), por lo que el patrón natural de compilación es una proyección con agregados y una cláusula de agrupación [3].

En NL, las señales “distribution”, “group by” y “count per” son equivalentes en intención, y el *smoke test* verifica que no hay deriva: la selección del operador y la cardinalidad del resultado se mantienen constantes (4 filas, una por estado presente en el grafo). De cara a la evaluación, esto aporta una evidencia adicional sobre estabilidad del sistema más allá del conjunto “unitario” del catálogo, y facilita justificar de forma reproducible que el routing está controlado [7].

**Caso 3 — Integridad: trazas duplicadas (detección de redundancia).**

- **Grupo:** `D.audit.duplicates`
- **Paráfrasis evaluadas:**
	- “Audit: duplicate traces (same source + predicate + target repeated).”
	- “Find duplicate links / repeated traceability relationships.”
	- “Detect redundant traceability links (same src, same relation, same target).”
- **Resultado observado:** operador único `DUPLICATE_TRACES_AUDIT` y **29 filas** en las tres reformulaciones.

**Interpretación técnica.** El concepto de “duplicado” se formaliza como la existencia de múltiples instancias de la misma relación lógica (misma fuente, misma relación y mismo destino). En SPARQL 1.1, una forma estándar de capturar este patrón es agrupar por las claves de la relación y filtrar grupos con cardinalidad mayor que 1 mediante agregación (`COUNT`) y restricción sobre agregados con `HAVING` [3]. En grafos con *link nodes*, esto puede implementarse agrupando por los extremos (src/dst) y el tipo de relación, independientemente del identificador del nodo de enlace, de manera que la auditoría detecte redundancia semántica aunque existan varias instancias físicas del enlace.

Desde el punto de vista NL→SPARQL, este caso es útil porque los enunciados pueden variar (“duplicate”, “repeated”, “redundant”) sin que cambie la intención. El hecho de que el routing converja al mismo operador y a la misma cardinalidad observada en el dataset sintético (29 filas) aporta evidencia de robustez frente a sinónimos y reformulaciones en auditorías de integridad, y además queda anclado a un log reproducible de ejecución [7].

**Resumen comparativo.** Los tres casos cubren tres patrones típicos del estándar SPARQL: (i) ausencia de evidencia (`FILTER NOT EXISTS`) para auditorías de metadatos, (ii) agregación y agrupación (`COUNT` + `GROUP BY`) para distribuciones, y (iii) detección de redundancia mediante `GROUP BY` + `HAVING` para duplicados [3]. En conjunto, complementan la métrica cuantitativa de consistencia por paráfrasis: no solo se reporta que “es consistente”, sino que se muestra por qué, y se deja una traza ejecutable y repetible que el lector puede verificar en local (dataset + scripts + log) [7].

#### 5.3.5 Modos de fallo y comportamiento esperado
En sistemas deterministas basados en reglas, el fallo “correcto” es tan importante como el acierto. En este TFG se prioriza el fallo controlado por encima de devolver una consulta plausible pero incorrecta. En particular:

- Si la intención no está soportada, el sistema debe informar de forma explícita.
- Si el grounding no puede anclarse al esquema, debe evitarse la generación ad hoc.
- Si el checker detecta términos fuera de esquema, se debe rechazar la consulta (evitando invención).

Este principio está alineado con el objetivo de auditoría y con la motivación de reproducibilidad: una consulta incorrecta pero “bien formada” puede ser más peligrosa que un error visible, especialmente si se utiliza en procesos de verificación/validación.

#### 5.3.6 Amenazas a la validez (interna/externa)
Para que la evaluación sea académicamente sólida conviene explicitar amenazas típicas:

- **Validez interna (oráculo).** Si las consultas de referencia están mal definidas, la evaluación puede marcar como fallo un comportamiento correcto (o viceversa). La mitigación es validar primero el catálogo en modo `reference` y revisar manualmente ejemplos críticos.
- **Validez externa (dataset sintético).** El grafo sintético no captura toda la variabilidad del mundo real. La mitigación es describir claramente las asunciones de generación, y (si es posible) repetir con un subconjunto real anonimizando datos, manteniendo el diseño offline.
- **Validez de constructo (métrica).** “Ejecuta sin error” no implica “responde a la intención”. Por ello se recomienda reportar, además de ejecución, consistencia por paráfrasis y comparaciones frente a consultas de referencia.

Estas notas conectan con la preocupación de replicación en KGQA y con la necesidad de protocolos transparentes [7].

#### 5.3.7 Guía de reproducción (para el lector)
Para facilitar la evaluación por terceros (tutor/tribunal), es útil incluir una guía mínima reproducible. En este repositorio, el flujo recomendado es:

1) Generar o regenerar el grafo sintético (TTL).
2) Ejecutar queries de referencia del directorio `queries_p510/`.
3) Ejecutar evaluación automática sobre el catálogo JSONL.
4) Probar manualmente en CLI o demo visual, revisando la explicación.

Esta sección describe un flujo reproducible para Windows (PowerShell). El objetivo es que el lector pueda regenerar el dataset, ejecutar consultas de referencia y repetir la evaluación sin depender de servicios externos.

**Paso 0 — Crear entorno (recomendado).** Desde la raíz del repositorio:

1) Crear venv:

- `py -m venv .venv`

2) Activar:

- `./.venv/Scripts/Activate.ps1`

3) Instalar dependencias:

- `pip install -r requirements.txt`

El proyecto se apoya en RDFLib para cargar y consultar el grafo [10]. La demo visual puede ejecutarse con Streamlit [11] (opcional).

**Paso 1 — Generar el grafo sintético.**

- `python src/p510_generate_synthetic.py`

Salida esperada: `data/p510_sintetico.ttl`.

**Paso 2 — Ejecutar el catálogo de consultas SPARQL de referencia.**

- `python src/run_queries_p510.py`

Las consultas de referencia están en `queries_p510/`.

**Paso 3 — Probar el traductor NL→SPARQL desde CLI.**

- Motor dinámico:
	- `python src/text2sparql_cli.py "requirements missing end-to-end traceability" --mode run --engine dynamic --explain`

- Motor catálogo:
	- `python src/text2sparql_cli.py "requirements missing end-to-end traceability" --mode run --engine catalog --examples eval/text2sparql_examples.jsonl --explain`

**Paso 4 — Evaluación automática (regresión).**

1) Validar que las SPARQL de referencia del JSONL ejecutan (sanity check):

- `python src/text2sparql_eval.py --mode reference`

2) Evaluar generación desde NL:

- `python src/text2sparql_eval.py --mode generate --engine dynamic`
- `python src/text2sparql_eval.py --mode generate --engine catalog`

El script reporta `[OK]/[FAIL]` por ejemplo y un resumen final con tasa de éxito.

**Paso 5 — Demo local (opcional).**

- Demo HTML+JS servida por Python:
	- `python src/demo_server.py`
	- Abrir `http://127.0.0.1:8000`

- Demo Streamlit:
	- `python -m streamlit run src/demo_visual.py`

**Recomendación para memoria/defensa.** Capturar la salida completa de `text2sparql_eval.py` (con fecha) y adjuntarla como anexo o como fichero en `eval/` para respaldar las cifras del Cap. 5.

---

## 6. Presupuesto y planificación (6–10 págs)
### 6.1 Planificación
La planificación se organiza por fases con entregables verificables. Una propuesta típica:

- Fase 1: análisis del problema, requisitos y casos de uso.
- Fase 2: diseño de arquitectura, decisiones tecnológicas y definición de operadores.
- Fase 3: implementación del motor y checker.
- Fase 4: implementación de interfaces y dataset sintético.
- Fase 5: pruebas, evaluación y estabilización.
- Fase 6: redacción de memoria y preparación de defensa.

**TODO:** ajustar semanas/fechas según calendario real del TFG.

Para que la planificación sea evaluable, cada fase se concreta en entregables que puedan comprobarse en el repositorio:

- **E1 — Dataset y queries de referencia listos.** Fichero TTL generado y consultas SPARQL de referencia ejecutables.
- **E2 — Motor mínimo NL→SPARQL.** Capaz de resolver al menos un subconjunto de familias (p. ej. “missing” y “count”).
- **E3 — Checker de seguridad/esquema.** Bloqueo de Update y validación de términos.
- **E4 — Interfaz CLI.** Ejecución reproducible por comando y salida de SPARQL + resultados.
- **E5 — Evaluación automatizada.** Script que recorre ejemplos y reporta tasa de éxito.
- **E6 — Demo visual.** UI para demostración y revisión de explicación.

Además, se recomienda explicitar riesgos y mitigaciones por fase. Por ejemplo:

- **Riesgo:** crecimiento del alcance (demasiadas familias). **Mitigación:** priorizar familias y añadir operadores incrementalmente.
- **Riesgo:** ambigüedad lingüística (preguntas fuera de dominio). **Mitigación:** fallo controlado + sugerencias.
- **Riesgo:** regresiones por cambios en normalización/routing. **Mitigación:** evaluación automática como regresión.

### 6.2 Diagrama de Gantt
En ausencia de una herramienta específica, el Gantt puede representarse como tabla (semanas vs tareas) y luego exportarse a una figura.

**TODO:** añadir tabla Gantt con fechas reales.

Plantilla sugerida (rellenar con fechas reales):

| Fase | Tareas | Inicio | Fin | Entregable |
|---|---|---:|---:|---|
| F1 | Requisitos, casos de uso, queries objetivo | TODO | TODO | E1 (parcial) |
| F2 | Diseño arquitectura, operadores y checker | TODO | TODO | E2 + E3 |
| F3 | Implementación motor y catálogo | TODO | TODO | E2 estable |
| F4 | CLI + demo visual + generación dataset | TODO | TODO | E4 + E6 |
| F5 | Evaluación, regresión y estabilización | TODO | TODO | E5 + tablas |
| F6 | Redacción final + defensa | TODO | TODO | Memoria + slides |

### 6.3 Presupuesto
El presupuesto se expresa principalmente como coste de dedicación (horas de trabajo). El resto de costes suelen ser marginales si se utilizan herramientas open source y un equipo personal.

Ejemplo de tabla (sustituir valores):

| Concepto | Cantidad | Coste unitario | Coste total |
|---|---:|---:|---:|
| Dedicación (desarrollo + redacción) | TODO horas | TODO €/hora | TODO € |
| Infraestructura (equipo, electricidad) | 1 | TODO € | TODO € |
| Software (licencias) | 0 | 0 € | 0 € |
| **Total** |  |  | **TODO €** |

También se describen riesgos (por ejemplo, deriva de requisitos, complejidad de operadores) y medidas de mitigación (tests de regresión, alcance acotado, hitos intermedios).

Una forma habitual de justificar el coste de dedicación es desglosar horas por tipo de actividad:

- **Análisis y documentación del dominio:** TODO h
- **Diseño (arquitectura, operadores, checker):** TODO h
- **Implementación (motor + interfaces):** TODO h
- **Pruebas y evaluación:** TODO h
- **Redacción y revisión de la memoria:** TODO h

En caso de incluir coste de infraestructura, basta con una estimación conservadora (equipo personal amortizado y consumo eléctrico) y una nota indicando que no se ha requerido infraestructura cloud (por diseño offline).

---

## 7. Entorno socio-económico y marco legal (6–10 págs)
### 7.1 Impacto socio-económico
- Impacto en productividad (reducción de barrera SPARQL).
- Impacto en calidad y auditoría (consultas consistentes, trazabilidad).
- Limitaciones: dataset sintético y alcance.

La solución propuesta reduce el coste de formular consultas sobre grafos RDF al permitir que perfiles no expertos en SPARQL expresen preguntas de auditoría y trazabilidad en lenguaje natural. En términos de productividad, el impacto esperado es una disminución del tiempo dedicado a redactar consultas y depurar errores sintácticos o de esquema.

En términos de calidad, el enfoque determinista y el checker anti-invención contribuyen a que las consultas sean **consistentes** y trazables: se evita la generación de vocabulario inexistente y se ofrece una explicación que apoya procesos de auditoría.

No obstante, el impacto está condicionado por el alcance del sistema: al tratarse de un conjunto acotado de familias, la cobertura fuera del dominio no está garantizada.

### 7.2 Estándares y buenas prácticas
- W3C RDF/SPARQL.
- Vocabularios (FOAF, DCTERMS) y convenciones.

El sistema se apoya en estándares consolidados del W3C: RDF para representación de datos y SPARQL 1.1 para consulta. Cuando se representan organizaciones y metadatos generales se emplean vocabularios ampliamente utilizados (por ejemplo FOAF y Dublin Core Terms), lo que mejora interoperabilidad y claridad.

Desde una perspectiva de buenas prácticas, apoyarse en recomendaciones W3C aporta dos beneficios directos:

- **Portabilidad de consultas.** SPARQL 1.1 define construcciones (por ejemplo, `OPTIONAL`, agregación, y `FILTER NOT EXISTS`) con semántica clara, lo que permite razonar sobre el comportamiento del sistema sin depender de extensiones propietarias [3].
- **Modelo de datos interoperable.** RDF 1.1 define cómo representar grafos, IRIs y literales; esto facilita que los datos sintéticos y las consultas sean comparables con herramientas estándar [1], [2].

Además, el hecho de usar vocabularios como FOAF para organizaciones y DCMI Terms para metadatos generales reduce la necesidad de “inventar” predicados para conceptos comunes [8], [9].

### 7.3 Licencias y cumplimiento
- Licencias de dependencias (Python, RDFLib, Streamlit) y compatibilidad.
- Privacidad: al ser offline, minimiza exposición de datos.
- Seguridad: prevención de consultas de escritura (SPARQL Update) y ejecución controlada.

Desde el punto de vista de licenciamiento, la solución se implementa sobre herramientas y librerías open source. Este TFG debe documentar las licencias principales de las dependencias y verificar su compatibilidad con el uso académico y la distribución del código (si aplica). Una práctica recomendable es registrar las licencias a partir de fuentes oficiales (p. ej. SPDX) y conservar un listado de dependencias.

Para fundamentar esta sección, puede citarse la definición formal de “open source” de la Open Source Initiative [13] y el listado oficial de licencias SPDX [14].

En materia de privacidad, el enfoque offline evita el envío de datos a terceros. En materia de seguridad, la validación que bloquea SPARQL Update reduce el riesgo de modificaciones no deseadas del dataset.

#### 7.3.1 Checklist de cumplimiento (propuesta)
Para que esta sección sea operativa (y no solo declarativa), se propone un checklist mínimo:

1) **Inventario de dependencias.** Conservar `requirements.txt` y, si es posible, un volcado de dependencias instaladas con versión (por ejemplo, salida de `pip freeze`) asociado a una fecha.
2) **Identificación de licencias.** Para cada dependencia principal, registrar licencia según la fuente oficial del proyecto y, cuando exista, su identificador SPDX [14].
3) **Compatibilidad y distribución.** Si se distribuye el código (repositorio público), asegurar que la distribución cumple las condiciones de las licencias (atribución, avisos, etc.).
4) **Fuentes de referencia.** Basar la justificación en definiciones formales (p. ej. la Open Source Definition) [13] y en listados normalizados (SPDX) [14].

Este checklist es deliberadamente conservador: no asume que todas las dependencias tengan un identificador SPDX claro, pero fuerza a documentar la fuente y evita afirmaciones no verificadas.

### 7.6 Seguridad, privacidad y modelo de amenaza (ampliación)
Aunque el dataset de este TFG es sintético, es útil analizar qué cambiaría si el sistema se aplicase a grafos reales (posiblemente sensibles). El diseño elegido incorpora medidas que, en términos generales, reducen superficie de ataque:

- **Ejecución offline por defecto.** No hay necesidad de enviar texto de preguntas ni datos del grafo a terceros, lo que reduce riesgos de exposición.
- **Restricción del lenguaje ejecutable.** Se bloquean operaciones de SPARQL Update y otras construcciones asociadas a modificación del grafo, conforme al estándar de actualización [12]. Esta medida reduce el riesgo de corrupción accidental o maliciosa del dataset.
- **Validación de esquema (*anti-invención*).** Se rechazan términos fuera del esquema observado, mitigando tanto errores del motor como intentos de inyección de IRIs/prefijos no deseados.

Un modelo de amenaza razonable para una versión aplicada a datos reales incluiría:

1) **Entrada maliciosa o errónea (preguntas adversarias).** Un usuario podría intentar forzar consultas costosas o introducir palabras clave prohibidas. Mitigación: checker, límites (`LIMIT`), y fallo controlado.
2) **Denegación de servicio local (consultas pesadas).** Incluso con `SELECT`, ciertas consultas pueden ser lentas. Mitigación: límites, timeouts en ejecución (si se añade), y reporte de tiempos (Cap. 5).
3) **Riesgo de datos personales.** Si el grafo contiene datos personales, aplican obligaciones de tratamiento. Mitigación: diseño offline, minimización, y documentación de medidas conforme al RGPD cuando aplique [15].

Este análisis no sustituye a una auditoría formal, pero ayuda a justificar por qué las decisiones de diseño (offline, determinismo, checker) están alineadas con un uso responsable.

### 7.4 Legislación aplicable (según contexto)
- Si se aplican datos personales: marco RGPD (describir en términos generales cómo el diseño reduce riesgos).
- Si no hay datos personales: indicarlo explícitamente y justificar.

**TODO (decidir según el caso):** si el dataset y las preguntas no contienen datos personales reales, debe indicarse explícitamente que el RGPD no aplica directamente al contenido del grafo. Aun así, conviene justificar cómo el diseño (offline, control de ejecución) es compatible con principios de minimización y seguridad.

Como referencia normativa general puede citarse el Reglamento (UE) 2016/679 (RGPD) [15].

En este TFG, el riesgo legal suele concentrarse más en el **uso de datasets reales** que en el propio algoritmo. Si se trabaja únicamente con datos sintéticos, se debe dejar explícito (y justificable) que no se tratan datos personales, y por tanto el RGPD no aplica directamente al contenido del grafo. Aun así, es razonable describir cómo el diseño offline y el control de ejecución serían compatibles con principios de seguridad y minimización en caso de migrar a datos reales [15].

### 7.5 Declaración ampliada de uso de IA y medidas anti-plagio
De acuerdo con los requisitos académicos, se declara el uso de herramientas de IA como apoyo en el desarrollo del proyecto.

**Uso permitido y alcance.** Las herramientas de IA se han utilizado para acelerar tareas auxiliares (por ejemplo, lluvia de ideas, generación de borradores, sugerencias de código o reformulación). No se ha utilizado la IA para “copiar” trabajos previos ni para introducir contenidos protegidos.

**Revisión y validación.** Toda salida generada por IA se ha sometido a:

- Revisión técnica (coherencia con el repositorio, el dataset y los resultados).
- Reescritura cuando fue necesario para mantener una redacción original.
- Verificación empírica (ejecución de scripts, consultas SPARQL y pruebas de regresión).

**Medidas anti-plagio.** La memoria se redacta de forma original y se apoya en referencias citadas en formato IEEE. Las ideas, definiciones o fragmentos tomados de estándares y documentación se referencian adecuadamente. El código mostrado en el documento se limita a fragmentos necesarios para explicar el funcionamiento y siempre corresponde al repositorio del proyecto.

---

## 8. Conclusiones y trabajos futuros (3–6 págs)
### 8.1 Conclusiones
- Relacionar resultados con objetivos.

En este trabajo se ha definido e implementado un sistema determinista de traducción de lenguaje natural a SPARQL para un dominio P510-like. El diseño por familias (operadores/patrones) y el *grounding* al esquema permiten controlar la generación, evitando la invención de predicados/clases y aportando reproducibilidad. La incorporación de una traza explicativa facilita la inspección del comportamiento y mejora la confianza en los resultados.

Para cerrar el trabajo, es importante vincular explícitamente el resultado con los objetivos O1–O7 (Cap. 1):

- **O1 — Traducción texto→SPARQL:** el motor genera consultas `SELECT` para varias familias típicas (listados, conteos, ausencias y auditorías). La evidencia se presenta en los ejemplos del catálogo y en la ejecución sobre el TTL.
- **O2 — Offline y determinista:** toda la ejecución se realiza en local (sin dependencias remotas). La misma entrada produce la misma SPARQL y el mismo resultado si el dataset no cambia.
- **O3 — Grounding al esquema:** las decisiones se basan en un índice de clases/predicados observados y se restringen a vocabularios existentes.
- **O4 — Checker anti-invención y seguridad:** se bloquean operaciones de Update y se validan prefijos/términos; los fallos se reportan como errores controlados.
- **O5 — Explicabilidad:** se devuelve una traza con normalización, hits de grounding y señales que justifican la ruta elegida.
- **O6 — Validación y pruebas:** se incluye evaluación automática como regresión, además de *smoke tests* con paráfrasis.
- **O7 — Interfaz de demostración:** el sistema se utiliza desde CLI y desde una demo visual, mostrando SPARQL, resultados y explicación.

**TODO (cierre final):** sustituir estas afirmaciones por cifras y tablas concretas (tasa de éxito global, consistencia por paráfrasis y ejemplos representativos), una vez ejecutada la evaluación definitiva.

**Cierre con resultados medidos (ejecución).** En la evaluación automática incluida en el repositorio (N=34 ejemplos del catálogo JSONL), se obtuvo una tasa de ejecución sin errores del **100.0% (34/34)** tanto al ejecutar las consultas de referencia (`reference`) como al generar desde NL con el motor dinámico y con el motor catálogo (`generate`). Además, los tiempos por ejemplo (ms) muestran que el coste típico (mediana) es del orden de decenas de milisegundos, aunque existen casos más costosos (máximos del orden de segundos), lo que justifica reportar mediana y percentiles además de la media (Cap. 5.3.3).

Estas cifras deben interpretarse con cautela: validan que el pipeline produce consultas ejecutables y que el checker no bloquea indebidamente el conjunto evaluado, pero no sustituyen a una validación de equivalencia semántica completa para todas las intenciones. En un trabajo futuro, esta validez semántica puede reforzarse comparando resultados contra un oráculo “gold” (por ejemplo, las SPARQL de referencia) y ampliando el conjunto de paráfrasis por intención.

### 8.2 Trabajos futuros
- Ampliar cobertura de operadores/familias.
- Mejoras de evaluación (más paráfrasis, datasets reales si es posible).
- Mejoras de explicabilidad (visualización, exportación).

Como trabajos futuros se proponen: ampliar el catálogo de operadores para cubrir nuevas familias, incorporar datasets reales (si hay acceso y permisos) y formalizar aún más la evaluación (por ejemplo, métricas de equivalencia semántica entre consultas o validaciones sobre resultados esperados). En el ámbito de la explicabilidad, se podrían añadir visualizaciones que destaquen el grounding por token y la correspondencia entre la pregunta y los patrones SPARQL generados.

De forma más concreta, algunas líneas de extensión razonables son:

- **Cobertura de lenguaje (multilingüe).** Actualmente el flujo está orientado a preguntas en inglés; un paso natural es añadir un glosario/normalización para español (o detección de idioma) sin perder determinismo.
- **Enriquecimiento del esquema.** Extraer estadísticas del grafo (frecuencias de predicados, tipos más comunes) para mejorar sugerencias y desambiguación, manteniendo el checker como barrera de seguridad.
- **Métricas más informativas.** Además de “ejecuta/no ejecuta”, incluir métricas de equivalencia de resultados entre paráfrasis y análisis de estabilidad del routing.
- **Operadores composicionales más ricos.** Introducir combinaciones controladas (por ejemplo, ausencia + agrupación) cuando el dominio lo requiera, manteniendo plantillas verificables.

---

## 9. Bibliografía (2–4 págs)
Las referencias se listan en estilo IEEE, numeradas por orden de aparición.

[1] W3C, “RDF 1.1 Primer,” W3C Recommendation, 2014. [Online]. Available: https://www.w3.org/TR/rdf11-primer/. [Accessed: Apr. 22, 2026].

[2] W3C, “SPARQL 1.1 Overview,” W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-overview/. [Accessed: Apr. 22, 2026].

[3] W3C, “SPARQL 1.1 Query Language,” W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-query/. [Accessed: Apr. 22, 2026].

[4] L. Zettlemoyer and M. Collins, “Learning to Map Sentences to Logical Form: Structured Classification with Probabilistic CCGs,” in Proc. Uncertainty in Artificial Intelligence (UAI), 2005.

[5] J. Berant, A. Chou, R. Frostig, and P. Liang, “Semantic Parsing on Freebase from Question-Answer Pairs,” in Proc. Conference on Empirical Methods in Natural Language Processing (EMNLP), 2013.

[6] T. Yu et al., “Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task,” arXiv:1809.08887, 2018. doi: 10.48550/arXiv.1809.08887.

[7] A. Perevalov, X. Yan, L. Kovriguina, L. Jiang, A. Both, and R. Usbeck, “Knowledge Graph Question Answering Leaderboard: A Community Resource to Prevent a Replication Crisis,” arXiv:2201.08174, 2022. doi: 10.48550/arXiv.2201.08174.

[8] D. Brickley and L. Miller, “FOAF Vocabulary Specification,” n.d. [Online]. Available: http://xmlns.com/foaf/spec/. [Accessed: Apr. 22, 2026].

[9] Dublin Core Metadata Initiative, “DCMI Metadata Terms,” n.d. [Online]. Available: https://www.dublincore.org/specifications/dublin-core/dcmi-terms/. [Accessed: Apr. 22, 2026].

[10] RDFLib contributors, “RDFLib Documentation,” n.d. [Online]. Available: https://rdflib.readthedocs.io/. [Accessed: Apr. 22, 2026].

[11] Streamlit Inc., “Streamlit Documentation,” n.d. [Online]. Available: https://docs.streamlit.io/. [Accessed: Apr. 22, 2026].

[12] W3C, “SPARQL 1.1 Update,” W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-update/. [Accessed: Apr. 22, 2026].

[13] Open Source Initiative, “The Open Source Definition,” n.d. [Online]. Available: https://opensource.org/osd/. [Accessed: Apr. 22, 2026].

[14] SPDX Workgroup, “SPDX License List,” n.d. [Online]. Available: https://spdx.org/licenses/. [Accessed: Apr. 22, 2026].

[15] European Union, “Regulation (EU) 2016/679 (General Data Protection Regulation),” Official Journal of the European Union, 2016. [Online]. Available: https://eur-lex.europa.eu/. [Accessed: Apr. 22, 2026].

---

### (Opcional) Anexos
- Tabla “Operador → patrón SPARQL → señales NL → esquema usado”.
- Guía de reproducción (comandos y versiones).

Si la memoria lo permite (por ejemplo, como Anexo A), una tabla de “operadores/familias” con ejemplos representativos ayuda a que el lector vea rápidamente qué cubre el sistema y qué no cubre. En este TFG, ese anexo se alinea con el enfoque por familias: ausencia (`NOT EXISTS`), agregación (`GROUP BY`/`COUNT`), duplicados (`HAVING`) y listados (`SELECT DISTINCT`).

#### Anexo A — Operadores/familias y patrones SPARQL (resumen)

| Familia (operador) | Intención | Señales típicas (NL) | Esqueleto SPARQL (simplificado) | Ejemplo de referencia |
|---|---|---|---|---|
| Ausencia de relación (NOT EXISTS) | Encontrar entidades sin traza/enlace requerido | “sin”, “faltan”, “missing/without”, “no tiene” | `FILTER NOT EXISTS { ?src p510:REL ?ln . ?ln p510:Link ?tgt . ... }` | `q1_req_sin_modelo_fisico.sparql` |
| Ausencia de test (NOT EXISTS) | Modelos sin test asociado | “sin test”, “no verificado”, “models without tests” | `FILTER NOT EXISTS { ?m p510:Verified_by ?ln . ?ln p510:Link ?test . ... }` | `q2_modelos_sin_test.sparql` |
| Conteo total (COUNT) | Contar entidades | “cuántos”, “número de”, “how many” | `SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a ... }` | `q6_cuantos_proveedores.sparql` |
| Duplicados (GROUP BY + HAVING) | Detectar enlaces redundantes | “duplicados”, “repetidos”, “duplicate links” | `GROUP BY ?src ?pred ?tgt HAVING(COUNT(DISTINCT ?ln) > 1)` | `q24_links_duplicados.sparql` |

Notas:
- En el sistema, estos esqueletos se instancian con clases/predicados extraídos del grafo (grounding) y se validan con el checker antes de ejecutar.
- La columna “ejemplo de referencia” apunta a una query que se ejecuta directamente sobre el dataset sintético para comprobar el patrón.
