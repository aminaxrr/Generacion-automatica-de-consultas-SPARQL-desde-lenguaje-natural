<<<## 1. Introducción
En numerosos entornos de ingeniería y gobierno del dato, la información relevante no está organizada como tablas aisladas, sino como un conjunto de artefactos conectados: requisitos, modelos, pruebas, responsables y enlaces de trazabilidad. Esta representación relacional encaja de forma natural con grafos RDF, donde se pueden describir entidades heterogéneas y relaciones enriquecidas con metadatos (fechas, tipos, descripciones) de manera flexible.

En este contexto, SPARQL es el mecanismo estándar para interrogar el grafo y formalizar auditorías: detectar ausencia de evidencias, incoherencias de metadatos o duplicidades en trazas. No obstante, la adopción práctica de SPARQL presenta una barrera de entrada significativa: además de conocer la sintaxis, el usuario debe manejar el vocabulario del dominio y patrones de consulta que no son triviales (por ejemplo, ausencia con `FILTER NOT EXISTS` o duplicados con `GROUP BY/HAVING`).

Este proyecto plantea una solución orientada a esas restricciones: un sistema que traduce preguntas en lenguaje natural a consultas SPARQL ejecutables sobre un grafo RDF local, devolviendo también una traza explicable de decisiones. La propuesta prioriza requisitos de ingeniería habituales en auditoría: ejecución offline, comportamiento determinista, control estricto del esquema y registro de evidencias reproducibles.

### 1.1 Motivación
Como ya se ha mencionado, en escenarios de ingeniería y gobierno del dato es habitual representar la información como un conjunto de artefactos conectados (requisitos, modelos, pruebas y enlaces de trazabilidad), donde la calidad del dato se verifica mediante consultas de auditoría. En estos entornos, comprobar ausencia de evidencias, incoherencias de metadatos o duplicidades deja de ser una tarea puntual y se convierte en una necesidad recurrente.

Sin embargo, formular estas auditorías directamente en SPARQL supone una barrera de entrada significativa: además de conocer la sintaxis, el usuario debe manejar el vocabulario real del grafo y patrones de consulta que no son triviales (por ejemplo, ausencia con `FILTER NOT EXISTS` o duplicados con `GROUP BY/HAVING`). Esta dificultad se acentúa cuando la consulta debe ser no solo correcta, sino también reproducible y explicable, ya que en auditoría no basta con "obtener una respuesta"; es necesario justificarla.

El avance de las técnicas de procesamiento de lenguaje natural y los sistemas de traducción NL→consulta abre una oportunidad en este contexto: facilitar el acceso a consultas sobre grafos sin exigir que el usuario sea experto en SPARQL. No obstante, en un entorno de auditoría la flexibilidad por sí sola no es suficiente; también se requiere control del esquema, prevención de invención de vocabulario y trazabilidad de decisiones.

Por ello, la propuesta se orienta a un enfoque controlado: traducir preguntas a un conjunto acotado de familias de consulta, compilar patrones SPARQL deterministas y acompañar la salida con una traza explicable. De este modo se reduce la fricción de uso sin renunciar a requisitos de seguridad, verificabilidad y ejecución offline.

### 1.2 Antecedentes
En los últimos años se han consolidado distintas líneas de trabajo orientadas a traducir lenguaje natural a consultas ejecutables sobre bases de conocimiento y grafos (KGQA y *semantic parsing*). En el caso de RDF, el reto no es únicamente "producir una consulta sintácticamente válida", sino decidir qué predicados y patrones son adecuados dentro de un espacio de vocabularios (IRIs) y grafos que pueden estar incompletos.

En la práctica, este escenario ha dado lugar a soluciones con distintos grados de control. Por un lado, existen enfoques basados en catálogos o plantillas, fáciles de validar pero limitados en cobertura. Por otro lado, hay aproximaciones más abiertas (incluyendo componentes generativos) que pueden aumentar expresividad, pero que requieren mecanismos adicionales para evitar invención de términos y para asegurar trazabilidad y reproducibilidad.

En este proyecto, el objetivo no es maximizar cobertura generalista, sino habilitar auditorías repetibles sobre un dominio acotado. Por ello se priorizan tres ideas: (i) *grounding* explícito al esquema observado, (ii) restricción del espacio de consultas mediante operadores/familias, y (iii) validación previa a ejecución mediante un *checker* que transforma fallos de esquema o de seguridad en errores controlados y explicables.

### 1.3 Objetivos
#### 1.3.1 Objetivo general
El objetivo general del proyecto consiste en diseñar e implementar una herramienta que permita formular preguntas en lenguaje natural sobre un grafo RDF y obtener como salida una consulta SPARQL ejecutable, el resultado de ejecutarla localmente y una explicación del proceso de traducción.

#### 1.3.2 Objetivos específicos
Para concretar ese objetivo, se persiguen los siguientes objetivos específicos:
- Definir familias de auditoría y su oráculo SPARQL de referencia.
- Diseñar e implementar un traductor NL→SPARQL de solo lectura (`SELECT`) orientado a dichas familias.
- Asegurar ejecución local y reproducible (offline y determinista).
- Incorporar *grounding* al esquema observado (clases y predicados presentes en el grafo).
- Implementar un *checker* que bloquee SPARQL Update y rechace vocabulario fuera de esquema.
- Proporcionar una traza de explicación de la traducción (operador y señales de *grounding*).
- Ofrecer dos modos de uso: CLI y demo visual para inspeccionar consulta, resultados y explicación.

### 1.4 Estructura del documento
En este apartado se describe de forma breve la estructura seguida por el presente documento:
- Introducción: presenta el contexto del proyecto, la motivación, los objetivos y el alcance.
- Estado del arte: revisa enfoques para traducir lenguaje natural a consultas sobre grafos y discute alternativas desde el punto de vista de control, reproducibilidad y evaluación.
- Análisis del problema: define el problema a resolver, describe el modelo de datos de referencia y concreta requisitos y casos de uso.
- Diseño de la solución: detalla la arquitectura del traductor NL→SPARQL, el *grounding* al esquema y el *checker* de seguridad.
- Implementación y evaluación: describe los componentes implementados, la estrategia de pruebas y los resultados experimentales.
- Interfaz de usuario: presenta la CLI y la demo visual, incluyendo evidencias del modo explicación (`--explain`).
- Infraestructura y servicios cloud: documenta estructura del proyecto, entorno de ejecución y puesta en marcha (en este caso, una ejecución deliberadamente offline).
- Marco regulador: resume aspectos de protección de datos, licencias y consideraciones de uso responsable.
- Entorno socioeconómico: discute el impacto del proyecto e incorpora planificación y presupuesto.
- Conclusiones: sintetiza los resultados obtenidos y propone líneas de trabajo futuro.
- Bibliografía: recopila todas las referencias utilizadas a lo largo del documento.
- Anexos: incluye información complementaria (por ejemplo, resúmenes técnicos y la declaración de uso de IA generativa).

### 1.5 Glosario y abreviaturas
Esta sección tiene como objetivo principal facilitar la comprensión del documento mediante la inclusión de un glosario de términos técnicos y una serie de abreviaturas utilizadas a lo largo del trabajo.

#### 1.5.1 Glosario
- Prefijo: abreviatura para un *namespace* (p. ej. `p510:`, `dcterms:`) en SPARQL/Turtle.
- Semantic parsing: traducción de lenguaje natural a una forma lógica o programa ejecutable (en este proyecto, SPARQL).
- Grounding: anclaje de menciones del texto a vocabulario real del esquema (clases/predicados observados).
- Operador: familia de intención (p. ej. ausencia, duplicados, agregación) que se compila a un patrón SPARQL.
- Checker: validación previa que bloquea SPARQL Update y términos fuera del esquema permitido.
- Link node: nodo intermedio que reifica una relación para poder adjuntar metadatos (timestamps, description, etc.).
- End-to-end: cadena de trazabilidad requisito → modelo → test (u otras variantes definidas por el dominio).

#### 1.5.2 Abreviaturas
- RDF: Resource Description Framework, modelo de datos basado en triples [1].
- SPARQL: lenguaje estándar de consulta para RDF y grafos [2], [3].
- TTL/Turtle: formato de serialización para RDF (fichero `.ttl`) [1].
- IRI: identificador para nombrar recursos, clases y predicados en RDF.
- KGQA: *Question Answering* sobre grafos de conocimiento.
- RDFLib: librería de Python usada para cargar TTL y ejecutar SPARQL localmente [10].

La declaración de uso de IA generativa exigida por UC3M se incluye en el Anexo B.

### 1.6 Alcance y limitaciones
El alcance del trabajo se centra en un dominio P510-like (inspirado en trazabilidad de ingeniería) representado mediante un grafo RDF y un conjunto de consultas de referencia. La herramienta no pretende responder preguntas arbitrarias de propósito general, sino cubrir de forma sólida un conjunto de familias de auditoría frecuentes (ausencia de relaciones, agregaciones, duplicados e incoherencias de metadatos).

Como consecuencia, las limitaciones principales del enfoque son:

- Ambigüedad del lenguaje natural: formulaciones diferentes pueden activar señales distintas si no hay evidencia suficiente para desambiguar.
- Dependencia del esquema: el sistema no puede utilizar términos que no existan en el grafo; si una propiedad o clase no está presente, no se inventa.
- Cobertura acotada: fuera de las familias soportadas, el comportamiento esperado es fallar de forma controlada y explicable.

### 1.7 Contribuciones
Para concretar la aportación del trabajo (más allá de una demostración puntual), se resumen a continuación las contribuciones técnicas verificables en el repositorio:

- C1 — Banco de pruebas RDF reproducible: generador de dataset sintético P510-like con semilla fija y "ruido" controlado para habilitar auditorías no triviales (Cap. 3.2.1).
- C2 — Oráculo ejecutable de auditorías: conjunto de consultas SPARQL de referencia (`queries_p510/`) que formalizan reglas de integridad y gobierno del dato como patrones revisables (Cap. 5.1.3).
- C3 — Motor NL→SPARQL determinista por operadores: traductor que mapea señales lingüísticas y grounding al esquema a consultas `SELECT` para familias acotadas (ausencia, agregación, duplicados y auditorías especializadas), preservando trazabilidad de decisiones (Cap. 4.2.6, Cap. 5.2.4).
- C4 — Checker y barrera de seguridad: validación previa a ejecución que bloquea operaciones de escritura y rechaza vocabulario fuera del esquema observado (Cap. 4.2.7, Cap. 5.2.6).
- C5 — Protocolo de evaluación reproducible: scripts de evaluación y pruebas de paráfrasis que cuantifican ejecución sin error y estabilidad por intención, con evidencias persistentes en `eval/` (Cap. 5.3.3).

---

## 2. Estado del arte
Esta sección contiene una revisión de los avances más relevantes en la traducción de lenguaje natural a consultas ejecutables sobre grafos RDF. Por tanto, el objetivo de este capítulo es contextualizar el desarrollo de la herramienta dentro del panorama actual, identificando soluciones existentes, enfoques aplicables y limitaciones relevantes cuando el sistema se utiliza en auditoría e integridad del dato.

A continuación se analizan los fundamentos de KGQA y *semantic parsing*, así como las principales familias de enfoques (catálogos/plantillas, reglas u operadores y modelos generativos), con el fin de justificar el punto de partida desde el que se plantea la propuesta desarrollada en este proyecto: determinismo, control estricto del esquema, explicabilidad y evaluación reproducible mediante ejecución real de SPARQL.

### 2.1 NL→consulta sobre grafos KGQA / semantic parsing
En este apartado se introducen los conceptos básicos necesarios para enmarcar el problema NL→SPARQL dentro de la literatura existente. En primer lugar, la traducción de lenguaje natural a una consulta formal se sitúa en el área de *Question Answering* y, más concretamente, en **semantic parsing**: transformar una pregunta en una representación lógica o ejecutable. Cuando el conocimiento subyacente es un grafo (RDF/Knowledge Graph), el problema suele denominarse **Question Answering over Knowledge Graphs (KGQA)**.

En SPARQL, el "espacio de programas" es especialmente rico: la semántica se expresa con patrones de triples, restricciones con filtros, opcionalidad (`OPTIONAL`) y ausencia de evidencia (`FILTER NOT EXISTS`) tal y como define el estándar [3]. A diferencia de text-to-SQL, donde el esquema suele presentarse como tablas y columnas con nombres relativamente homogéneos, en RDF el esquema se materializa como **IRIs y prefijos** (vocabularios) y admite modelos más flexibles (por ejemplo, clases opcionales, propiedades multi-valor y grafos con incompletitud). Esto aumenta la dificultad de (i) decidir qué predicados usar y (ii) garantizar que la consulta generada respeta el esquema real del grafo.

Por ello, una parte relevante de los enfoques de KGQA dependen de un fuerte acoplamiento al **esquema**, al menos mediante uno de estos mecanismos: (a) diccionarios o lexicones palabra→predicado/clase, (b) alineamiento de menciones a entidades del grafo, (c) reglas o gramáticas que restringen la generación, y/o (d) entrenamiento con supervisión (total o débil) para aprender el mapeo NL→consulta.

En este proyecto, además, existe un requisito adicional de ingeniería: la generación debe ser **determinista** y ejecutable **offline**, lo que condiciona las técnicas seleccionables.

#### 2.1.1 Enfoques clásicos de semantic parsing
Dentro de los enfoques clásicos, la literatura describe líneas de trabajo que aprenden a mapear lenguaje natural a representaciones formales mediante estructuras lingüísticas (por ejemplo, gramáticas CCG) y aprendizaje supervisado. Un ejemplo temprano y ampliamente citado es el trabajo de Zettlemoyer y Collins, que aprende un mapeo a formas lógicas usando CCG probabilísticas [4]. Este tipo de enfoques aporta una idea clave: imponer una **estructura intermedia** que limite el espacio de programas posibles y que permita explicar cómo se compone la consulta a partir de fragmentos del texto.

Posteriormente, la comunidad explora configuraciones donde el grafo es una base de conocimiento a gran escala y la supervisión disponible es débil (pares pregunta–respuesta) en lugar de consultas explícitas. Berant et al. proponen un enfoque en Freebase donde se induce el programa a partir de la señal de respuesta [5]. En términos prácticos, estos trabajos motivan dos conclusiones: (i) el anclaje al esquema y la desambiguación sobre el grafo son el cuello de botella, y (ii) la evaluación requiere protocolos cuidadosos para evitar sobreajustes a un único esquema o a programas repetidos.

### 2.2 Enfoques principales
Una vez establecido el marco KGQA/*semantic parsing*, en la literatura y en la práctica industrial se observan tres familias de enfoques relevantes:

1) **Recuperación basada en catálogo/plantillas.** Se define un conjunto de consultas SPARQL (plantillas) y se selecciona la más cercana a la intención del usuario. Suele ser robusto y fácil de validar, pero limita la expresividad al catálogo predefinido.

2) **Compilación determinista por reglas u operadores.** En lugar de elegir una plantilla concreta, el sistema identifica un **operador** (por ejemplo, "missing data", "count by category", "duplicates") y lo compila a un patrón SPARQL, rellenando variables y predicados a partir del esquema. Este enfoque puede generalizar dentro del dominio y mantiene control estricto del resultado.

3) **Modelos neuronales y LLM.** Los modelos generativos pueden producir consultas complejas a partir de ejemplos, pero plantean riesgos: (i) no determinismo, (ii) posibilidad de **inventar** predicados/clases no existentes, y (iii) dependencia de un servicio o de un modelo pesado. En dominios con auditoría y control, estos riesgos pueden ser inaceptables si no se añade un fuerte control posterior.

En el contexto concreto de este proyecto (auditoría de integridad de datos y trazabilidad), estos riesgos se conectan con requisitos prácticos: las consultas deben ser **repetibles** y deben respetar un **esquema observado**. Por ello, incluso aunque se discutan LLM como alternativa, la implementación prioriza un pipeline determinista con validación previa a la ejecución (checker) y con ejecución local de SPARQL conforme al estándar [3]. Esta elección facilita la trazabilidad del experimento y reduce incertidumbre metodológica, alineándose con la preocupación por reproducibilidad en evaluación de KGQA [7].

La Tabla 1 resume, de forma cualitativa, los trade-offs relevantes para este proyecto.

| Enfoque | Ventajas | Inconvenientes | Adecuación a este proyecto |
|---|---|---|---|
| Catálogo/plantillas | Validación simple, alta precisión por consulta | Cobertura limitada, mantenimiento manual | Útil como baseline, no como solución principal |
| Operadores/reglas | Determinismo, control del esquema, extensible por familias | Requiere ingeniería del dominio y señales NL | **Enfoque elegido** |
| Neuronal/LLM | Expresividad, menos reglas explícitas | No determinismo, invención de esquema, coste/privacidad | Útil para comparación y discusión |

#### 2.2.1 Text-to-SQL como referencia metodológica
Como referencia metodológica, aunque text-to-SQL no es equivalente a text-to-SPARQL, comparte una motivación importante: traducir preguntas en NL a un lenguaje formal de consulta. En particular, el benchmark Spider introduce explícitamente el reto de **generalización a esquemas no vistos** y ha servido como referencia para discutir cobertura, complejidad y evaluación en tareas de *semantic parsing* [6]. En este proyecto se toma Spider como inspiración metodológica (familias de consulta, conjuntos de ejemplos y evaluación reproducible), aunque el dominio y el lenguaje formal final sean distintos.

#### 2.2.2 Evaluación y reproducibilidad en KGQA
En relación con la evaluación, la comparación entre sistemas KGQA es difícil porque cambian los datasets, las particiones, el preprocesado y, en ocasiones, la propia definición de métricas. Perevalov et al. analizan este problema y proponen un recurso comunitario de leaderboard, destacando riesgos de "crisis de replicación" cuando la evaluación no es trazable o no es comparable entre trabajos [7]. Esta observación conecta directamente con los requisitos de este proyecto: si el objetivo es soportar auditorías y consultas repetibles, la **reproducibilidad** y la **explicación** dejan de ser opcionales.

### 2.3 Posicionamiento del proyecto
Este proyecto adopta un enfoque de **compilación por operadores** con *grounding* al esquema y un **checker anti-invención**. La intención es maximizar la reproducibilidad y la seguridad del resultado: toda consulta generada debe ser ejecutable en un grafo local y no debe introducir términos fuera del conjunto observado en los datos. Además, se incorpora **explicabilidad** para que el usuario pueda entender por qué se eligió un operador y cómo se interpretaron palabras y frases.

En la capa de NL, el sistema trabaja con un conjunto **controlado** de señales léxicas y patrones de intención (p. ej., "missing/without", "how many/count", "group by", "duplicate"), que se usan para seleccionar un operador y disparar una compilación SPARQL trazable. Esta capa se integra con el *grounding* al esquema y con el checker, de modo que la decisión de operador y el mapeo a términos del grafo queden registrados y sean auditables.

Este posicionamiento no busca competir en generalidad con enfoques generativos, sino ofrecer una solución sólida para un dominio acotado y con necesidades de auditoría.

En concreto, la herramienta desarrollada en este proyecto se sitúa más cerca de los enfoques (1) y (2) descritos (catálogo/plantillas y compilación determinista por operadores), pero incorpora elementos inspirados por el estado del arte: (i) un *grounding* explícito al esquema (para evitar términos inventados) y (ii) una estrategia de evaluación que incluye consistencia frente a paráfrasis y ejecución real de la consulta.

**Referencias clave**: estándar SPARQL [3], trabajos clásicos de semantic parsing [4], KBQA débilmente supervisado [5], benchmark metodológico [6] y discusión de reproducibilidad en KGQA [7].

### 2.4 Patrones SPARQL relevantes para auditoría taxonomía
En este apartado se sintetizan patrones SPARQL que aparecen de forma recurrente en auditorías sobre RDF y que, por tanto, sirven como guía práctica para diseñar un traductor NL→SPARQL por familias. Una diferencia importante entre text-to-SQL y text-to-SPARQL es que, en RDF, las consultas se construyen sobre **patrones de triples** y la semántica se expresa con combinaciones de un conjunto relativamente pequeño de *constructos* del estándar. Para un proyecto orientado a auditorías de integridad y trazabilidad, resulta útil identificar una **taxonomía de patrones SPARQL** y usarla como "lenguaje intermedio" entre la pregunta en NL y la compilación final.

En este proyecto se priorizan patrones que aparecen de forma recurrente en auditoría:

1) **Ausencia de evidencia (incompletitud).**
	- Construcciones típicas: `FILTER NOT EXISTS { ... }`, `!EXISTS { ... }`, y (en menor medida) combinaciones con `OPTIONAL`.
	- Uso típico: "requirements without a model", "links without description", "scenarios missing `Verified_by`/`Validated_by`".
	- Riesgo técnico: en grafos RDF, la ausencia es semánticamente delicada; la forma correcta suele ser `NOT EXISTS` sobre el patrón exacto (no "comparar contra NULL"), conforme a SPARQL 1.1 [3].

2) **Agregación y distribución (resúmenes).**
	- Construcciones típicas: `COUNT`, `GROUP BY`, `ORDER BY` (y proyecciones agregadas).
	- Uso típico: "how many X", "distribution by maturity", "models per supplier".
	- Riesgo técnico: definir si el conteo debe ser `COUNT(*)`, `COUNT(?x)` o `COUNT(DISTINCT ?x)` (evitar duplicados por joins), tal y como especifica SPARQL 1.1 [3].

3) **Redundancia e integridad (duplicados).**
	- Construcciones típicas: `GROUP BY` + `HAVING(COUNT(...) > 1)`.
	- Uso típico: "duplicate links", "repeated traces".
	- Riesgo técnico: elegir la clave de agrupación correcta (p. ej. extremos de la relación + predicado) para detectar duplicados semánticos aunque existan múltiples nodos de enlace.

4) **Coherencia de metadatos (reglas de calidad).**
	- Construcciones típicas: `FILTER`, `OPTIONAL` + comprobaciones, y patrones con `EXISTS`/`NOT EXISTS`.
	- Uso típico: "inconsistent contentType", "missing mandatory timestamps".
	- Riesgo técnico: la forma de modelar metadatos (p. ej. *link nodes*) afecta directamente al patrón SPARQL; por ello, una memoria de este tipo debe vincular explícitamente modelado y patrón [3].

En la práctica, esta taxonomía se usa como guía de diseño: cada familia soportada por el sistema se implementa como un patrón SPARQL controlado (Cap. 5), y la evaluación se organiza por familias para detectar regresiones (Cap. 5.3).

### 2.5 Evaluación en KGQA: oráculos, métricas y trazabilidad
En este apartado se describe cómo evaluar de forma trazable un sistema NL→SPARQL en un dominio acotado. Para que la evaluación sea científicamente útil, debe especificar (i) qué se considera "correcto", (ii) cómo se obtiene un oráculo y (iii) qué variación experimental se tolera. En KGQA, esta discusión es especialmente relevante: hay múltiples grados de libertad (dataset, motor SPARQL, particiones, definición de equivalencia) y se han señalado riesgos de replicación cuando no se publican artefactos y protocolos de forma comparable [7].

En traducción NL→SPARQL, la evaluación es especialmente delicada por dos razones:

1) **Hay múltiples consultas correctas.** Dos consultas pueden diferir sintácticamente (orden de patrones, nombres de variables, uso de `OPTIONAL` equivalente en un subconjunto) y, aun así, devolver el mismo resultado. En RDF/SPARQL, además, la semántica por defecto es de **multiconjunto** (puede haber duplicados si no se usa `DISTINCT`), lo cual afecta a cómo se compara "la salida" [3].
2) **El resultado depende del motor y del dataset concreto.** Un sistema puede "parecer correcto" en un TTL pequeño y fallar en otro grafo con el mismo vocabulario pero distinta densidad o incompletitud. Asimismo, aunque SPARQL 1.1 define la semántica, los motores pueden diferir en rendimiento y en detalles de implementación, por lo que el protocolo debe fijar explícitamente el motor utilizado (RDFLib en este proyecto) [3], [10].

Por tanto, en lugar de reportar una única métrica ("acierto/fallo"), es preferible descomponer la evaluación en capas y acompañarla de artefactos reproducibles.

En este proyecto se distinguen explícitamente tres niveles de evaluación:

- **Correctitud ejecutable (sintaxis + ejecución).** La consulta compila, pasa el checker y se ejecuta sin error en un motor concreto (RDFLib en este caso) [10]. Es un mínimo necesario para ingeniería, pero no garantiza equivalencia semántica.
- **Correctitud respecto a un oráculo (denotacional).** La salida coincide con el resultado de una consulta de referencia, o con un conjunto de resultados esperado. Este nivel requiere fijar un oráculo (por ejemplo, `queries_p510/` o `eval/text2sparql_examples.jsonl`).
- **Robustez/estabilidad (paráfrasis).** Reformulaciones de la misma intención deben conducir a decisiones coherentes (mismo operador o mismo resultado). Esta idea se conecta con la necesidad de evitar "deriva" por cambios menores, y se operacionaliza con el *smoke test* de paráfrasis (Cap. 5.3), reforzando trazabilidad [7].

#### 2.5.1 Oráculos: consultas gold, resultados esperados y trazabilidad
Un oráculo es el mecanismo con el que se decide si una salida es correcta. En NL→SPARQL existen, como mínimo, tres opciones (no excluyentes):

- **Oráculo por consulta de referencia (SPARQL gold).** Se fija una consulta SPARQL para cada intención. Es la aproximación más directa cuando el dominio es acotado y se dispone de un conjunto de queries auditables (como en `queries_p510/`). Ventaja: es ejecutable y verificable por terceros. Inconveniente: comparar "consulta generada" vs "consulta gold" por string no es robusto, porque puede haber consultas distintas pero equivalentes.
- **Oráculo denotacional (por resultados).** Se fija el *resultado esperado* (o se define que el resultado debe coincidir con el de una consulta de referencia). Esta opción es coherente con la naturaleza de SPARQL: lo importante es la tabla de bindings (y su semántica de multiconjunto) [3].
- **Oráculo por propiedades (metas de auditoría).** En auditorías, a veces basta con validar propiedades: por ejemplo, que el resultado incluya únicamente link nodes without timestamps, o que un duplicado tenga `COUNT>1`. Esta opción no reemplaza al oráculo denotacional, pero ayuda a explicar "por qué es correcto".

En este proyecto se prioriza un oráculo ejecutable: (i) consultas de referencia en `queries_p510/` (familias del dominio), y (ii) un catálogo JSONL con parejas NL–SPARQL (`eval/text2sparql_examples.jsonl`) que permite evaluar tanto ejecución de la gold como generación desde NL (Cap. 5.3) [10].

#### 2.5.2 Métricas recomendadas y por qué la exact match es insuficiente
Una métrica habitual en *semantic parsing* es la coincidencia exacta del programa (exact match). En NL→SPARQL esta métrica tiene una utilidad limitada por:

- renombrado de variables, reordenación de patrones, o uso de variantes sintácticas;
- equivalencias denotacionales (mismo resultado con distinta forma);
- decisiones de `DISTINCT` y multiplicidad que dependen del esquema y de joins [3].

Por ello, para este dominio se recomiendan métricas por capas (Tabla 2.A) que separen "es ejecutable" de "es semánticamente equivalente" y de "es estable".

**Tabla 2.A — Métricas por capas para NL→SPARQL en un dominio auditado.**

| Capa | Métrica | Qué verifica | Riesgo si se usa sola |
|---|---|---|---|
| Ejecutable | Tasa OK (ejecuta sin error) | Sintaxis + checker + motor SPARQL | Puede ser una consulta válida pero equivocada |
| Denotacional | Coincidencia de resultados con oráculo | Semántica de la intención | Depende del oráculo elegido y del motor |
| Estabilidad | Consistencia por paráfrasis (mismo operador / misma cardinalidad / mismos resultados) | Robustez a reformulaciones | Puede ocultar sesgos si las paráfrasis son limitadas |
| Eficiencia | Mediana/P90 de tiempo | Viabilidad práctica | No mide corrección |

En la práctica de este proyecto, la evaluación automatizada reporta la capa ejecutable (OK/FAIL) y tiempos, mientras que el smoke test añade una capa de estabilidad por paráfrasis (Cap. 5.3.3). Para una validación denotacional completa, el protocolo natural es comparar resultados contra la SPARQL gold correspondiente (misma intención), preservando la semántica de multiconjunto o normalizando con `DISTINCT` cuando aplique [3].

#### 2.5.3 Equivalencia y comparadores de resultado detalles que importan
Para que "comparar resultados" sea una operación reproducible, el protocolo debe especificar:

- **¿Conjunto o multiconjunto?** SPARQL produce multiconjuntos por defecto; si el objetivo es una auditoría "por entidad", suele ser razonable usar `DISTINCT` o comparar tras deduplicación [3].
- **Orden y paginación.** A menos que se defina `ORDER BY`, el orden no es parte de la semántica. Además, imponer `LIMIT` es útil por seguridad y rendimiento, pero puede invalidar una comparación denotacional si el límite trunca resultados.
- **Representación de IRIs y literales.** La comparación debe considerar normalización (p. ej. representación de fechas, tipos de literal) para evitar falsos negativos.

En este proyecto, el *gate* de `LIMIT` se justifica como requisito de seguridad/robustez (Cap. 5.2.5), y la evaluación se centra en casos donde `LIMIT` no compromete la interpretación (auditorías con cardinalidades moderadas y resúmenes agregados). Cuando se quiera validar denotacionalmente sin ambigüedad, el experimento debe ejecutarse sin truncado o con un `LIMIT` suficientemente alto para cubrir el resultado completo.

#### 2.5.4 Robustez a paráfrasis como métrica de estabilidad más allá de acierta
Una fuente común de problemas en sistemas basados en reglas es la **deriva por cambios mínimos**: pequeñas modificaciones en normalización, sinónimos o expresiones regulares pueden alterar el operador elegido. Este fallo es especialmente peligroso en auditoría, porque dos preguntas equivalentes podrían producir consultas distintas (y, por tanto, resultados no comparables).

El criterio de estabilidad puede operacionalizarse de varias maneras, ordenadas por exigencia:

1) **Mismo operador** (familia): la explicación reporta la misma línea `operator:`.
2) **Misma cardinalidad**: el nº de filas devuelto es idéntico.
3) **Mismos bindings** (denotacional): el resultado completo coincide (bajo una política de normalización).

En este proyecto se utiliza el smoke test de paráfrasis como prueba de regresión con los dos primeros criterios (operador + cardinalidad) porque son baratos, deterministas y detectan regresiones de routing con alta sensibilidad (Cap. 5.3.3) [7].

#### 2.5.5 Reporting reproducible: qué artefactos deben acompañar a las tablas
Para evitar resultados "no replicables", se recomienda que una memoria de NL→SPARQL incluya, junto a las cifras, un checklist mínimo (Tabla 2.B) de artefactos que permitan repetir el experimento.

**Tabla 2.B — Checklist mínimo de reproducibilidad para este tipo de proyecto.**

| Elemento | Qué fija | Ejemplo en este repositorio |
|---|---|---|
| Dataset exacto | Grafo y vocabulario observado | `data/p510_sintetico.ttl` + semilla del generador |
| Oráculo ejecutable | Qué se considera correcto | `queries_p510/` y `eval/text2sparql_examples.jsonl` |
| Motor SPARQL | Semántica + rendimiento observado | RDFLib [10] |
| Configuración | Límites/umbrales que afectan resultados | `GenerationConfig` (limit, thresholds) |
| Logs de ejecución | Evidencia verificable de la corrida | ficheros en `eval/` (OK/FAIL, tiempos) |

Este tipo de reporting está alineado con la motivación de evitar una "crisis de replicación" en tareas KGQA: sin artefactos y protocolo, comparar resultados entre trabajos deja de ser significativo [7].

#### 2.5.6 Amenazas típicas a la validez en NL→SPARQL y mitigaciones
Incluso con un protocolo reproducible, hay amenazas recurrentes:

- **Sesgo por dominio acotado.** Un sistema por operadores puede obtener tasas muy altas si el conjunto de evaluación coincide con sus familias; por eso conviene reportar cobertura por familia (y explicitar qué queda fuera) [6].
- **Sesgo por dataset sintético.** Un grafo sintético permite controlar variables, pero no captura toda la ambigüedad del mundo real. La mitigación es describir el proceso de generación, introducir ruido controlado (para auditorías no triviales) y ser explícito con el alcance.
- **Dependencia del motor.** Cambiar de motor SPARQL puede afectar tiempos e incluso compatibilidad con ciertos patrones; por eso el motor debe fijarse explícitamente y citar el estándar como base conceptual [3], [10].
- **Definición de equivalencia.** Si solo se mide "ejecuta", se corre el riesgo de inflar resultados; si se mide exact match, se penalizan equivalencias legítimas. Mitigación: métricas por capas y casos de estudio cualitativos (Cap. 5.3.3) [7].

Además, se adopta una idea metodológica inspirada por benchmarks de *semantic parsing*: reportar cobertura por familias y discutir el reto de generalización (aunque aquí el esquema está controlado y el objetivo es determinismo) [6].

### 2.6 Discusión: determinismo, explicabilidad y control vs. enfoques generativos
Por último, esta sección discute el trade-off entre control/auditoría y cobertura/expresividad. Los enfoques generativos (incluidos LLM) pueden producir consultas muy expresivas, pero en escenarios de auditoría aparecen requisitos que cambian el criterio de "mejor":

- **Reproducibilidad.** En auditoría, es preferible un sistema que siempre devuelva el mismo resultado y que falle de forma controlada ante ambigüedad, que uno que "acierte a veces" pero no sea repetible [7].
- **Control del esquema.** La generación debe respetar el vocabulario real; en RDF esto implica conocer IRIs/prefijos y evitar propiedades inexistentes, lo que aquí se fuerza con grounding + checker.
- **Explicabilidad.** La posibilidad de justificar el operador y los términos del esquema elegidos no solo ayuda a depuración; también mejora la confianza cuando el sistema se usa para validar integridad de datos (Cap. 5.2).

Esta sección concreta ese posicionamiento con un punto de vista metodológico: qué significa "control y verificabilidad" en términos de **artefactos**, **métricas** y **criterios de comparación**. El objetivo es que la evaluación no dependa de una demostración puntual, sino de un protocolo que pueda ejecutarse de forma repetible y que produzca evidencias persistentes (logs) [7].

#### 2.6.1 Protocolo reproducible en este proyecto artefactos y responsabilidades
Una diferencia práctica entre un prototipo "que funciona" y un sistema evaluable es que el segundo fija explícitamente:

- el **grafo** sobre el que se evalúa (dataset exacto),
- el **motor SPARQL** y su versión (para que ejecución y tiempos sean comparables),
- el **oráculo** (gold SPARQL / resultados esperados),
- el **pipeline** de ejecución (scripts, parámetros, formato de salida),
- y la **persistencia** de evidencias (logs de la corrida).

En este repositorio, estos elementos se materializan como (Tabla 2.C): dataset sintético (`data/p510_sintetico.ttl`), consultas gold del dominio (`queries_p510/`), catálogo NL–SPARQL (`eval/text2sparql_examples.jsonl`), scripts de ejecución/evaluación (`src/` y `eval/`) y logs de salida en `eval/`. El motor de ejecución de referencia es RDFLib, que implementa evaluación SPARQL sobre grafos RDF en Python [10].

**Tabla 2.C — Artefactos reproducibles y qué evidencian.**

| Artefacto | Rol en el protocolo | Evidencia generada |
|---|---|---|
| `data/p510_sintetico.ttl` | Dataset fijo para ejecución local | Resultados SPARQL deterministas dado el grafo |
| `queries_p510/` | Oráculo por consultas gold (auditorías) | Consultas revisables por terceros |
| `eval/text2sparql_examples.jsonl` | Oráculo NL–SPARQL para evaluación | Pares NL–SPARQL ejecutables |
| `src/text2sparql_eval.py` + `src/text2sparql.py` | Motor y harness de evaluación | OK/FAIL, SPARQL generado y traza |
| `eval/catalog_generate_run.txt` | Log de corrida del catálogo | Métricas de ejecución + auditoría de fallos |
| `eval/paraphrase_smoke.py` + `eval/paraphrase_smoke_out_*.txt` | Estabilidad por paráfrasis | Consistencia por grupo e indicadores de regresión |

Esta separación de responsabilidades permite que un tercero replique el experimento sin "interpretar" decisiones implícitas (por ejemplo, qué límites se usan, qué esquema se permite o qué se considera correcto), mitigando parte del problema de replicación discutido en KGQA [7].

#### 2.6.2 Qué se mide en la práctica: capas y señales de regresión
Con la taxonomía de Cap. 2.5, el protocolo de este proyecto prioriza dos propiedades de ingeniería:

- **Correctitud ejecutable (OK/FAIL) a escala.** Un sistema que genera una consulta "casi correcta" pero que no ejecuta no es útil en auditoría. Por eso el primer filtro es que la consulta compile y se ejecute sobre RDFLib sin error [10].
- **Estabilidad por intención (paráfrasis).** La consistencia por grupos de paráfrasis actúa como prueba de regresión: detecta cambios en normalización o routing que, de otro modo, pueden pasar inadvertidos si solo se mira el total de aciertos [7].

La elección de estas capas se justifica porque el objetivo no es maximizar cobertura abierta, sino garantizar que, **dentro de un dominio acotado**, el comportamiento sea repetible y auditado. Esta forma de evaluación es coherente con un enfoque por "familias" de consultas, típico en *semantic parsing* cuando se restringe el espacio de programas mediante gramáticas u operadores [6].

#### 2.6.3 Comparación: consulta, resultado y explicación tres objetos distintos
En sistemas NL→SPARQL conviene distinguir tres objetos de comparación, que no deben confundirse:

- **La consulta SPARQL** (texto del programa). Útil para depurar y para revisar que se usa el patrón correcto (`NOT EXISTS`, `GROUP BY/HAVING`, etc.), pero frágil como métrica de evaluación por equivalencias sintácticas.
- **El resultado** (bindings). Es el objeto natural para equivalencia denotacional, siempre que se especifique si se compara como conjunto o multiconjunto y cómo se normalizan literales [3].
- **La explicación** (traza). En este proyecto incluye una etiqueta `operator:` y evidencias de grounding, y se usa como señal de estabilidad y como mecanismo de auditoría interna: si dos paráfrasis dan el mismo resultado pero con operadores distintos, eso puede indicar fragilidad del routing.

La consecuencia práctica es que una evaluación seria no debería reducirse a "la consulta es igual" o "el resultado coincide", sino reportar (al menos) una capa ejecutable y una capa de estabilidad, y reservar la capa denotacional para los casos donde el oráculo esté bien definido y no haya truncado por `LIMIT` (Cap. 2.5.3).

#### 2.6.4 Trade-off frente a enfoques generativos: cuándo gana cada uno
La discusión "reglas vs. modelos" no es binaria; depende de requisitos. Para situar el proyecto:

- **Cuando el requisito dominante es control/auditoría**, un enfoque determinista con grounding y checker tiene ventajas claras: evita invención de vocabulario, produce fallos controlados y hace posible una evaluación reproducible por scripts y logs [7].
- **Cuando el requisito dominante es cobertura abierta**, modelos generativos (incluidos LLM) suelen cubrir más diversidad lingüística y pueden sintetizar consultas complejas, pero a costa de variabilidad, mayor superficie de alucinación y necesidad de *guardrails* adicionales (validación de esquema, ejecución segura, etc.).

De hecho, incluso en un escenario con LLM, una práctica recomendada es conservar un "núcleo" verificable: validar contra el esquema observado, bloquear SPARQL Update y registrar trazas de decisión y ejecución. En ese sentido, el diseño de este proyecto puede interpretarse como un punto de apoyo: un backend ejecutable y auditable sobre el que, en el futuro, podría acoplarse un componente generativo sin renunciar a las restricciones de seguridad y reproducibilidad.

Por tanto, el posicionamiento del proyecto no es "maximizar expresividad" sino "maximizar control y verificabilidad dentro de un dominio acotado", con evaluación reproducible y artefactos ejecutables.

---

## 3. Análisis del problema

Esta sección contiene el análisis del problema que se aborda en el proyecto y el marco desde el que se diseña la solución. Por tanto, el objetivo de este capítulo es delimitar el tipo de preguntas que se pretende soportar, las restricciones obligatorias (offline, determinismo y control del esquema) y los artefactos que se consideran evidencia de funcionamiento (consulta ejecutable, resultado y traza de explicación).

A continuación se describe el modelo de datos de referencia (grafo P510-like), se derivan requisitos verificables y se concretan casos de uso representativos para auditoría e integridad del dato.

### 3.1 Descripción del problema qué se quiere resolver
En este apartado se concreta el problema desde el punto de vista funcional: permitir que un usuario formule preguntas en lenguaje natural sobre un conjunto de datos representado como un grafo RDF y obtenga una respuesta sin necesidad de conocer SPARQL. El usuario objetivo es un perfil técnico que entiende el dominio (requisitos, verificaciones, evidencias, proveedores y relaciones de trazabilidad), pero que no necesariamente domina la sintaxis del lenguaje de consulta ni los detalles del vocabulario RDF utilizado.

Para que la herramienta sea útil en auditoría, la salida no debe limitarse a un texto "interpretativo". El sistema debe recibir como entrada una pregunta en lenguaje natural y producir como salida: (i) una consulta SPARQL de solo lectura (`SELECT`) alineada con el esquema del grafo, (ii) el resultado obtenido al ejecutarla localmente, y (iii) una traza de explicación que permita entender el operador elegido y el patrón de consulta aplicado.

El diseño del sistema está condicionado por cuatro restricciones esenciales:
- **Offline:** la ejecución no depende de servicios externos ni requiere enviar datos fuera del entorno local.
- **Determinismo:** a igualdad de entrada y grafo, el sistema debe tomar las mismas decisiones y producir resultados reproducibles.
- **Seguridad:** se bloquea SPARQL Update y cualquier operación de escritura o modificación del grafo.
- **Control del esquema:** no se inventan clases ni predicados; la compilación se limita al vocabulario observado en el dataset.

### 3.2 Contexto de datos y modelo del dominio P510-like
Para hacer el problema abordable y reproducible, se trabaja con un grafo RDF **sintético** inspirado en un dominio P510-like. A continuación se resume, a alto nivel, qué elementos representa:

- **Artefactos de ingeniería** (por ejemplo, requisitos, modelos, tests, escenarios de V&V).
- **Organizaciones/proveedores** asociados a artefactos.
- **Relaciones de trazabilidad** entre artefactos.
- **Metadatos** asociados a relaciones (contenido, descripción, marcas temporales, etc.).

El grafo utiliza prefijos habituales en RDF y en vocabularios generales:

- `p510:` para el dominio específico (clases y predicados del modelo de trazabilidad).
- `ex:` para extensiones y entidades sintéticas auxiliares.
- `foaf:` para representar organizaciones [8].
- `dcterms:` para metadatos temporales [9].

Un elemento relevante del modelado es el uso de **nodos intermedios de enlace** (*link nodes*). En lugar de expresar una relación como un triple directo `A → B`, se introduce un nodo `L` que permite añadir metadatos a la relación (por ejemplo, tipo de enlace, contentType, timestamp o description). Este patrón habilita auditorías como "links without timestamps" o "links with inconsistent contentType".

En términos de patrón, la idea es separar "relación" y "metadatos de la relación":

- Entidad origen (p. ej. un requisito) se conecta a un nodo de enlace mediante un predicado del dominio (p. ej. `Satisfied_by`, `Verified_by`, `Validated_by`).
- El nodo de enlace apunta a la entidad destino mediante un predicado genérico (p. ej. `Link`).
- El nodo de enlace contiene metadatos: `ContentType`, `Description`, timestamps, etc.

Este modelado es típico en escenarios donde la trazabilidad no es solo un vínculo binario, sino un artefacto con propiedades auditables.

**Figura 3.1 — Patrón de *link node* para trazabilidad (modelo P510-like).**

La Figura 3.1 muestra el patrón que se usa en el dataset para representar una relación de trazabilidad con metadatos. La idea es que la relación "real" se materializa en dos saltos: (i) del origen al link node con un predicado del dominio y (ii) del link node al destino con un puntero genérico. Sobre el link node se adjuntan metadatos auditables (tipo, timestamps, description, contentType).

```
?req   a                    p510:Requirement .
?req   p510:Satisfied_by     ?ln .

?ln    a                    p510:Traceability_Link_Type .
?ln    p510:Link             ?model .
?ln    p510:ContentType       "Physical Model" .
?ln    p510:Description       ?desc .
?ln    p510:Timestamp_PLM     ?ts_plm .
?ln    p510:Timestamp_Archiving ?ts_arc .

?model a                    p510:DesignModel .
```

**Ejemplo mínimo en Turtle.** El siguiente fragmento (simplificado) ilustra cómo se ve este patrón en serialización TTL. En la práctica, el repositorio utiliza prefijos y IRIs coherentes con el grafo, y los timestamps/metadatos se expresan con predicados del dominio (p. ej. `p510:Timestamp_PLM`) o, en metadatos generales, con vocabularios estándar como DCTERMS [9].

```turtle
@prefix p510: <http://example.org/p510#> .
@prefix ex:   <http://example.org/ex#> .

ex:req_001 a p510:Requirement ;
  p510:Id "REQ-001" ;
  p510:Satisfied_by ex:ln_1001 .

ex:ln_1001 a p510:Traceability_Link_Type ;
  p510:Link ex:model_003 ;
  p510:ContentType "Physical Model" ;
  p510:Description "Trace created by ..." .

ex:model_003 a p510:DesignModel ;
  p510:Id "MODEL-003" .
```

**Implicaciones para SPARQL (por qué este patrón importa).** En SPARQL, la reificación mediante link nodes cambia el "esqueleto" de las consultas. En lugar de un triple directo `?req p510:Satisfied_by ?model`, el patrón base incluye el nodo intermedio y permite expresar auditorías sobre metadatos con construcciones estándar de SPARQL 1.1 [3]. Por ejemplo:


- **Ausencia de metadatos en la traza** (auditoría de calidad): "links without timestamps". Se formula como ausencia de un patrón sobre el nodo `?ln`:
	- patrón típico: `FILTER NOT EXISTS { ?ln p510:Timestamp_PLM ?ts }` (o la combinación que aplique) [3].
- **Incoherencia de metadatos**: "contentType mismatch". Se formula como un filtro sobre `?ln p510:ContentType ?ct` (y, si se requiere, condiciones adicionales sobre origen/destino), evitando inferencias no verificables.
- **Duplicados semánticos**: agrupar por (origen, relación, destino) y detectar más de una instancia física de link node con `GROUP BY` + `HAVING` [3].

Este es el motivo por el que el Cap. 5 incluye operadores especializados para auditorías de trazabilidad: el modelado (Cap. 3) determina qué patrones SPARQL son necesarios y, por tanto, qué familias de NL→SPARQL hay que soportar.

#### 3.2.1 Dataset sintético y reproducibilidad
En este apartado se describe el dataset sintético y el mecanismo de reproducibilidad experimental. El dataset se genera de forma sintética para poder (i) compartirlo sin restricciones, (ii) controlar el tamaño y la densidad de trazas y (iii) repetir experimentos bajo condiciones equivalentes. En la práctica, el repositorio incorpora un generador que permite parametrizar el número de requisitos, modelos, tests y proveedores, y produce un fichero TTL reproducible.

Este enfoque permite diseñar un banco de pruebas para auditorías típicas del dominio sin depender de datos reales (que podrían estar sujetos a confidencialidad). La contrapartida es que la complejidad semántica del mundo real no está completamente representada; por ello, en la discusión de limitaciones (Cap. 1 y Cap. 10) se explicita el alcance.

##### Diseño del generador y ruido controlado para auditorías
El generador sintético (módulo `src/p510_generate_synthetic.py`) no se limita a crear instancias "limpias", sino que introduce **imperfecciones controladas** para que existan casos auditables (lo que hace que las queries de integridad no sean triviales). Este diseño es importante a nivel metodológico: si el dataset fuese perfectamente completo y coherente, consultas como "links without timestamps" o "Approved without approver" tenderían a devolver cero filas, y el sistema no podría validarse de forma realista.

En términos de parámetros, el generador permite controlar (entre otros):

- Tamaños: `n_requisitos`, `n_modelos`, `n_tests`, `n_proveedores`.
- Probabilidades de ausencia: `prob_req_sin_modelo`, `prob_modelo_sin_test`, `prob_modelo_sin_proveedor`, `prob_req_sin_aprobador`, `prob_req_sin_org_autora`.
- Probabilidades de "suciedad" en *link nodes*: `prob_link_missing_timestamp`, `prob_link_missing_description`, `prob_link_wrong_contenttype`.
- Probabilidad de redundancia: `prob_link_duplicate` (crea trazas duplicadas para habilitar auditorías de duplicados).

Estas imperfecciones se implementan a través de nodos de enlace tipados (`p510:Traceability_Link_Type`) que reifican la trazabilidad y permiten adjuntar metadatos (tipo, contentType, timestamps, description). Este patrón de modelado es compatible con RDF y con el estilo de consulta por patrones de triples definido por SPARQL 1.1 [1], [3].

##### Determinismo del dataset
Para garantizar repetibilidad, el generador fija explícitamente una semilla (`random.seed(42)`), lo que hace que, a igualdad de parámetros, el TTL producido sea estable (misma estructura y mismas imperfecciones), facilitando regresión y comparación de resultados en el tiempo. Además, el propio grafo incorpora metadatos editoriales (por ejemplo, un nodo `ex:Dataset` con `ex:seed` y `ex:generator_version`), lo que mejora trazabilidad experimental.

##### Estadísticas del grafo actual evidencia
Para evitar que la memoria se quede en descripciones abstractas, se reportan estadísticas del TTL actual (`data/p510_sintetico.ttl`) cargado con RDFLib [10]. Estas cifras permiten justificar por qué determinadas consultas devuelven cardinalidades concretas y ayudan a contextualizar los tiempos de ejecución.

**Tabla 3.A — Resumen del tamaño y vocabulario del grafo (TTL actual).**

| Métrica | Valor |
|---|---:|
| Triples totales | 2432 |
| Sujetos únicos | 222 |
| Predicados únicos | 79 |
| Objetos únicos | 681 |

**Tabla 3.B — Conteos por tipo (rdf:type) en el grafo (TTL actual).**

| Tipo (clase) | #Instancias |
|---|---:|
| `p510:Requirement` | 50 |
| `p510:DesignModel` | 30 |
| `p510:VerificationTest` | 20 |
| `p510:Traceability_Link_Type` | 89 |
| `p510:Verification_Validation_Scenario_Type` | 10 |
| `foaf:Organization` | 6 |

Estas tablas se obtienen de forma reproducible cargando el TTL en RDFLib y contando triples y `rdf:type` (ver Cap. 5.3 para el flujo de ejecución). Su objetivo es dar contexto: el sistema no opera sobre "un grafo abstracto", sino sobre un dataset concreto y medible.

#### 3.2.2 Vocabulario y predicados principales evidencia sobre el TTL
El modelo P510-like del dataset se expresa en RDF como un conjunto de **clases** (vía `rdf:type`) y un conjunto de **predicados** (propiedades) que conectan entidades y aportan metadatos. Aunque el grafo contiene un vocabulario más amplio (79 predicados distintos en total, Tabla 3.A), para comprender el comportamiento del traductor NL→SPARQL interesa aislar los predicados del **namespace del dominio** (`p510:`) que realmente aparecen en el TTL actual.

La Tabla 3.C resume los predicados `p510:` más frecuentes en el grafo (conteo de ocurrencias como predicado en triples). Estas frecuencias ayudan a justificar dos decisiones del sistema:

1) El *grounding* debe estar **anclado al vocabulario observado** (predicados que existen), no a un esquema "ideal".
2) Las familias de auditoría del proyecto se apoyan en un subconjunto pequeño y estable de propiedades: trazabilidad (`Satisfied_by`, `Verified_by`, `Validated_by`), reificación del enlace (`Link`) y metadatos de gobierno/calidad (`Approval_State`, `Approver`, timestamps, etc.).

**Tabla 3.C — Predicados `p510:` más frecuentes en el grafo (TTL actual).**

| Predicado (`p510:`) | Rol en el dominio | #Triples (predicado) |
|---|---|---:|
| `ContentType` | Tipo de contenido (en nodos de enlace y/o destino) | 199 |
| `Description` | Descripción humana del enlace/artefacto | 198 |
| `Id` | Identificador del artefacto | 116 |
| `Created_on` | Marca temporal de creación | 106 |
| `Created_by` | Autor/creador del artefacto | 101 |
| `Maturity_State` | Estado de madurez (gobierno) | 101 |
| `Satisfied_by` | Relación req → (link node) para trazabilidad a modelo | 92 |
| `Link` | Puntero desde link node al artefacto destino | 89 |
| `Type` | Tipo de enlace (cuando se representa como dato) | 89 |
| `Timestamp_PLM` | Timestamp de PLM en link node | 88 |
| `Timestamp_Archiving` | Timestamp de archivado en link node | 87 |
| `Approval_State` | Estado de aprobación | 81 |
| `Author_Organization` | Organización autora | 72 |
| `Verified_by` | Relación (link node) de verificación | 65 |
| `Approver` | Aprobador (gobierno) | 59 |
| `Validated_by` | Relación (link node) de validación | 4 |

Este listado no pretende "definir el estándar", sino documentar el vocabulario *realmente presente* en el dataset que se utiliza como oráculo experimental del proyecto. En un escenario con datos industriales, el mismo tipo de análisis (extraer predicados/clases observados) es un paso práctico para construir un diccionario de términos, validar consultas y detectar incoherencias.

#### 3.2.3 Reglas de coherencia y calidad de datos qué se audita
La motivación del proyecto no es solo "contestar preguntas", sino habilitar auditorías repetibles sobre un grafo de trazabilidad. En este contexto, el sistema operacionaliza varias **reglas de calidad** como consultas SPARQL verificables. Estas reglas se implementan como *familias* de consulta en la herramienta (Cap. 5) y se respaldan con consultas de referencia en `queries_p510/`.

Para documentarlas con precisión, se distinguen cuatro categorías.

**(R1) Ausencia de metadatos obligatorios en un link node.**
Los nodos de enlace (`p510:Traceability_Link_Type`) reifican la trazabilidad para poder adjuntar metadatos. Una regla típica es que, cuando existe el enlace, ciertos metadatos deben existir (por ejemplo timestamps y/o descripción). En SPARQL, la "ausencia" se expresa de forma robusta con `FILTER NOT EXISTS { ... }` sobre el patrón exacto, conforme a SPARQL 1.1 [3].

- Ejemplos de auditoría:
	- links without timestamps: `q13_links_sin_timestamp.sparql`
	- links without description: `q25_links_sin_description.sparql`

**(R2) Incoherencias de `ContentType` entre el link node y el destino.**
Si el enlace contiene un `ContentType` declarado (por ejemplo "Physical Model" o "Test Case"), este debe ser compatible con la entidad destino a la que apunta el `Link`. La consulta de auditoría identifica los casos donde el tipo declarado en el enlace no coincide con el tipo (o contentType) del destino.

- Ejemplo de auditoría: `q23_link_contenttype_incoherente.sparql`

**(R3) Duplicidad de trazas (relaciones repetidas).**
En trazabilidad, un duplicado puede definirse como dos o más link nodes distintos que codifican la misma relación semántica (mismo origen, mismo predicado de trazabilidad y mismo destino). Esta regla se expresa con agregación: `GROUP BY` + `HAVING(COUNT(...) > 1)`.

- Ejemplo de auditoría: `q24_links_duplicados.sparql`

**(R4) Reglas de gobierno: estados sin responsable.**
En metadatos de gobierno, ciertas combinaciones son sospechosas, por ejemplo entidades marcadas como "Approved" sin `Approver`. Esto se modela como una conjunción: (a) filtro por estado + (b) ausencia del atributo requerido.

- Ejemplo de auditoría: `q22_aprobados_sin_aprobador.sparql`

Estas reglas tienen dos ventajas metodológicas: (i) son verificables ejecutando SPARQL sobre el grafo local (RDFLib) [10], y (ii) obligan al traductor NL→SPARQL a manejar patrones relevantes del estándar (ausencia con `NOT EXISTS`, agregación con `GROUP BY/HAVING`, etc.) [3].

#### 3.2.4 Implicaciones para el traductor NL→SPARQL por qué operadores
Las reglas anteriores se repiten con variaciones (cambiar clase objetivo, cambiar predicado de trazabilidad, cambiar metadato). Por eso el sistema no genera consultas "desde cero", sino que selecciona un **operador** (familia) que encapsula un patrón SPARQL y expone un conjunto pequeño de parámetros:

- clase objetivo (p. ej. `p510:Requirement` vs `p510:DesignModel`),
- predicado de trazabilidad (p. ej. `Satisfied_by`/`Verified_by`),
- metadato auditado (p. ej. `Timestamp_PLM`, `Description`),
- filtros de tipo/contenido (`ContentType`, `Approval_State`).

Esta parametrización encaja con el objetivo del proyecto: maximizar **control** y **reproducibilidad** en un dominio acotado. Además, reduce el número de decisiones "lingüísticas" que hay que resolver: se buscan señales de intención ("missing", "without", "duplicate", "count", "approved but no approver") y se instancian plantillas verificables.

#### 3.2.5 Catálogo de auditorías mapa: patrón de grafo → SPARQL → query de referencia
Para que el Cap. 3 no se quede en una descripción conceptual, se incluye un catálogo de auditorías que enlaza directamente con el directorio `queries_p510/`. La intención es doble:

1) **Trazabilidad documental:** cada regla discutida en el texto tiene una implementación ejecutable (una query) que puede usarse como oráculo.
2) **Diseño orientado a patrones:** el traductor NL→SPARQL (Cap. 5) no "imagina" consultas; reconoce familias y las instancia, tal y como están formalizadas en SPARQL 1.1 [3].

En las descripciones siguientes se usa la notación `?src/?ln/?tgt` para referirse al patrón de link node introducido en la Figura 3.1.

**Tabla 3.D — Resumen de auditorías y patrones (queries de referencia).**

| Query | Familia | Operador SPARQL (núcleo) | Patrón mínimo de grafo (idea) |
|---|---|---|---|
| `q1_req_sin_modelo_fisico.sparql` | Cobertura de trazabilidad | `FILTER NOT EXISTS` | `Requirement` without `Satisfied_by`→`ln` (CT="Physical Model")→`Link`→`DesignModel` |
| `q2_modelos_sin_test.sparql` | Cobertura de verificación | `FILTER NOT EXISTS` | `DesignModel` (CT="Physical Model") without `Verified_by`→`ln` (CT="Test Case")→`Link`→`Test` |
| `q3_porcentaje_req_con_modelo.sparql` | Cobertura (ratio) | `OPTIONAL` + `COUNT` + aritmética | Contar `Requirement` totales y `Requirement` con `Satisfied_by` a modelo físico |
| `q4_req_sin_traza_end_to_end.sparql` | End-to-end Req→Model→Test | `FILTER NOT EXISTS` (cadena) | Falta cadena `req`→`ln`→`modelo` y `modelo`→`ln`→`test` con CTs esperados |
| `q5_reqs_sobre_especificados.sparql` | Sobre-especificación | `GROUP BY` + `HAVING` | `Requirement` con `COUNT(DISTINCT ?modelo) > 1` vía `Satisfied_by` (CT="Physical Model") |
| `q6_cuantos_proveedores.sparql` | Conteo | `COUNT(DISTINCT ...)` | `?prov a foaf:Organization` |
| `q7_modelos_por_proveedor.sparql` | Distribución por proveedor | `GROUP BY` + `COUNT` | `DesignModel` (CT="Physical Model") con `ex:providedBy ?prov` |
| `q8_plm_resumen.sparql` | Metadatos PLM | `OPTIONAL` | `Manifest`→`has_GeneralPLMInfo`→`info` y campos opcionales |
| `q9_dev_environment.sparql` | Entorno de desarrollo | `OPTIONAL` | `Manifest`→`has_RequirementsDevStructure`→`dev` y campos opcionales |
| `q10_documentos_usados.sparql` | Documentos vinculados | patrón link node + filtro CT | `dev` `uses` `ln` (CT="Document") `Link` `doc` |
| `q11_vnv_escenarios_resumen.sparql` | Resumen V&V | `OPTIONAL` + `UNION` | `Manifest`→V&V→`Scenario` y (opcional) `Verified_by`/`Validated_by`→`ln`→`Link` |
| `q12_vnv_escenarios_incompletos.sparql` | Integridad V&V | doble `FILTER NOT EXISTS` | `Scenario` without `Verified_by` and without `Validated_by` |
| `q13_links_sin_timestamp.sparql` | Calidad de link node | `FILTER` con `!EXISTS` + OR | `Traceability_Link_Type` without `Timestamp_Archiving` or without `Timestamp_PLM` |
| `q14_conteo_entidades.sparql` | Conteo global por tipo | `VALUES` + `UNION` + `GROUP BY` | Conteos por `rdf:type` + caso `Document` por `ContentType` |
| `q15_modelos_sin_proveedor.sparql` | Gobierno / completitud | `FILTER NOT EXISTS` | `DesignModel` (CT="Physical Model") without `ex:providedBy` |
| `q16_requisitos_sin_aprobador.sparql` | Gobierno / completitud | `OPTIONAL` + `FILTER NOT EXISTS` | `Requirement` (estado opcional) without `Approver` |
| `q17_requisitos_por_maturity.sparql` | Distribución por estado | `OPTIONAL` + `GROUP BY` | `Requirement` con `Maturity_State` opcional |
| `q18_requisitos_por_org_autora.sparql` | Distribución por organización | `OPTIONAL` + `GROUP BY` | `Requirement` con `Author_Organization` opcional |
| `q19_proveedor_top_modelos_sin_test.sparql` | Riesgo por proveedor | `FILTER NOT EXISTS` + `GROUP BY` | Por `prov`: contar `DesignModel` without `Verified_by` a `Test Case` |
| `q20_modelos_por_estado_aprobacion.sparql` | Distribución por approval | `OPTIONAL` + `GROUP BY` | `DesignModel` (CT="Physical Model") con `Approval_State` opcional |
| `q21_tests_por_proveedor_via_modelo.sparql` | Cobertura por proveedor | `GROUP BY` + `COUNT(DISTINCT)` | Por `prov`: `DesignModel`→`Verified_by`→`ln` (CT="Test Case")→`Link`→`test` |
| `q22_aprobados_sin_aprobador.sparql` | Gobierno (regla compuesta) | `UNION` + `FILTER NOT EXISTS` | `Requirement` o `DesignModel` con `Approval_State="Approved"` without `Approver` |
| `q23_link_contenttype_incoherente.sparql` | Coherencia de tipos | `OPTIONAL` + `BOUND` + `FILTER !=` | `ln` CT != `target` CT cuando el destino tiene CT |
| `q24_links_duplicados.sparql` | Duplicidad | `VALUES` + `GROUP BY` + `HAVING` | Duplicados por (`src`, `pred`, `target`) a través de múltiples `ln` |
| `q25_links_sin_description.sparql` | Calidad de link node | `FILTER NOT EXISTS` | `Traceability_Link_Type` without `Description` |
| `q26_baseline_y_proyecto.sparql` | Metadatos proyecto/baseline | `OPTIONAL` anidado | `Manifest`→`info` con `ex:hasBaseline`→`bl` y `dcterms:created` |
| `q27_requisitos_por_subsistema.sparql` | Distribución por atributo | `OPTIONAL` + `GROUP BY` | `Requirement` con `ex:subsystem` opcional |
| `q28_requisitos_por_metodo_verificacion.sparql` | Distribución por atributo | `OPTIONAL` + `GROUP BY` | `Requirement` con `ex:verification_method` opcional |

Notas:
- La columna "patrón mínimo" es intencionalmente abreviada; los detalles completos (triples y filtros) están en cada fichero `.sparql` y en las secciones siguientes.
- La Tabla 3.D es el "puente" operativo: conecta el modelado (Figura 3.1) con las familias/operadores que el traductor implementa (Cap. 5).

##### 3.2.5.1 Trazabilidad requisito ↔ modelo ↔ test
**`q1_req_sin_modelo_fisico.sparql` — Requisitos sin modelo físico.**
- Intención: "qué requisitos no están satisfechos por ningún modelo físico".
- Operador SPARQL: ausencia con `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement ; p510:Satisfied_by ?link .`
	- `?link p510:Link ?modelo ; p510:ContentType "Physical Model" .`

**`q2_modelos_sin_test.sparql` — Physical models without tests.**
- Intención: "models without tests / without verification".
- Operador SPARQL: ausencia con `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `?modelo a p510:DesignModel ; p510:ContentType "Physical Model" .`
	- Falta `?modelo p510:Verified_by ?link . ?link p510:ContentType "Test Case" ; p510:Link ?test .`

**`q4_req_sin_traza_end_to_end.sparql` — Requisitos sin traza end-to-end hasta test.**
- Intención: "requirements that do NOT reach a test via a physical model".
- Operador SPARQL: ausencia de un patrón *encadenado* (dos link nodes) con `FILTER NOT EXISTS` [3].
- Núcleo de patrón (cadena completa):
	- `?req p510:Satisfied_by ?l1 . ?l1 p510:ContentType "Physical Model" ; p510:Link ?modelo .`
	- `?modelo p510:Verified_by ?l2 . ?l2 p510:ContentType "Test Case" ; p510:Link ?test .`

**`q5_reqs_sobre_especificados.sparql` — Requisitos con más de un modelo físico.**
- Intención: "requirements with more than one physical model".
- Operador SPARQL: agregación `GROUP BY` + `HAVING(COUNT(DISTINCT ...) > 1)` [3].
- Núcleo de patrón:
	- `?req p510:Satisfied_by ?link . ?link p510:ContentType "Physical Model" ; p510:Link ?modelo .`
	- Agrupar por `?req` y contar `?modelo`.

**`q3_porcentaje_req_con_modelo.sparql` — Porcentaje de requisitos con modelo.**
- Intención: ratio/cobertura ("percentage of requirements with a model").
- Operador SPARQL: agregación + expresión aritmética sobre agregados [3].
- Núcleo de patrón:
	- `OPTIONAL { ?req p510:Satisfied_by ?link . ?link p510:ContentType "Physical Model" ; p510:Link ?modelo . BIND(?req AS ?reqConModelo) }`
	- `100.0 * COUNT(DISTINCT ?reqConModelo) / COUNT(DISTINCT ?req)`.

##### 3.2.5.2 Calidad de datos en link nodes metadatos y coherencia
**`q13_links_sin_timestamp.sparql` — Links without timestamps.**
- Intención: "links that violate XSD because they lack timestamps".
- Operador SPARQL: ausencia con `EXISTS/!EXISTS` dentro de `FILTER` (dos condiciones OR) [3].
- Núcleo de patrón:
	- `?link a p510:Traceability_Link_Type .`
	- Falta `p510:Timestamp_Archiving` o falta `p510:Timestamp_PLM`.

**`q25_links_sin_description.sparql` — Links without description.**
- Intención: "links without Description".
- Operador SPARQL: ausencia con `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `?link a p510:Traceability_Link_Type ; p510:ContentType ?ct .`
	- Falta `?link p510:Description ?d`.

**`q23_link_contenttype_incoherente.sparql` — Incoherencia `ContentType` (link vs destino).**
- Intención: "links whose contentType doesn't match the target contentType".
- Operador SPARQL: `OPTIONAL` + `BOUND` + filtro de desigualdad [3].
- Núcleo de patrón:
	- `?link a p510:Traceability_Link_Type ; p510:ContentType ?linkCT ; p510:Link ?target .`
	- `OPTIONAL { ?target p510:ContentType ?targetCT }`
	- `FILTER(BOUND(?targetCT) && ?linkCT != ?targetCT)`.

**`q24_links_duplicados.sparql` — Duplicados semánticos de trazas (origen+predicado+destino).**
- Intención: "duplicate links".
- Operador SPARQL: enumeración de predicados con `VALUES`, agregación y `HAVING` [3].
- Núcleo de patrón:
	- `VALUES ?pred { p510:Satisfied_by p510:Verified_by p510:Validated_by p510:uses }`
	- `?src ?pred ?link . ?link p510:Link ?target .`
	- `GROUP BY ?src ?pred ?target`.

##### 3.2.5.3 Gobierno del dato approval, maturity, responsabilidades
**`q16_requisitos_sin_aprobador.sparql` — Requirements without approver.**
- Intención: "requirements without approver (independientemente del estado)".
- Operador SPARQL: `OPTIONAL` + `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement ; p510:Id ?id . OPTIONAL { ?req p510:Approval_State ?state }`
	- Falta `?req p510:Approver ?a`.

**`q22_aprobados_sin_aprobador.sparql` — Approved without Approver (Requirements y Models).**
- Intención: "approved but no approver".
- Operador SPARQL: `UNION` (dos tipos) + `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- Caso 1: `?entity a p510:Requirement ; p510:Approval_State "Approved" .`
	- Caso 2: `?entity a p510:DesignModel ; p510:Approval_State "Approved" .`
	- En ambos: falta `p510:Approver`.

**`q17_requisitos_por_maturity.sparql` — Distribución por estado de madurez.**
- Intención: "requirements by maturity state".
- Operador SPARQL: `OPTIONAL` + `GROUP BY` + `COUNT` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement . OPTIONAL { ?req p510:Maturity_State ?maturity }`
	- Agrupar por `?maturity`.

**`q18_requisitos_por_org_autora.sparql` — Distribución por organización autora.**
- Intención: "requirements by author organization".
- Operador SPARQL: `OPTIONAL` + `GROUP BY` + `COUNT` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement . OPTIONAL { ?req p510:Author_Organization ?org }`

##### 3.2.5.4 Proveedores y agregaciones derivadas
**`q6_cuantos_proveedores.sparql` — Número total de proveedores.**
- Intención: "how many suppliers".
- Operador SPARQL: `COUNT(DISTINCT ...)` [3].
- Núcleo de patrón:
	- `?prov a foaf:Organization` [8].

**`q7_modelos_por_proveedor.sparql` — Modelos físicos por proveedor.**
- Intención: "models per supplier".
- Operador SPARQL: `GROUP BY` + `COUNT` [3].
- Núcleo de patrón:
	- `?modelo a p510:DesignModel ; p510:ContentType "Physical Model" ; ex:providedBy ?prov .`

**`q15_modelos_sin_proveedor.sparql` — Physical models without supplier.**
- Intención: "models without supplier".
- Operador SPARQL: ausencia con `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `?modelo a p510:DesignModel ; p510:ContentType "Physical Model" .`
	- Falta `?modelo ex:providedBy ?prov`.

**`q19_proveedor_top_modelos_sin_test.sparql` — Suppliers with most models without tests.**
- Intención: "top suppliers with models without verification".
- Operador SPARQL: combinación de `FILTER NOT EXISTS` + agregación [3].
- Núcleo de patrón:
	- `?modelo ex:providedBy ?prov` + falta `?modelo p510:Verified_by ?link ...`.
	- Agrupar por `?prov`.

**`q21_tests_por_proveedor_via_modelo.sparql` — Tests por proveedor (vía modelos).**
- Intención: "tests associated with each supplier's models".
- Operador SPARQL: `GROUP BY` + `COUNT(DISTINCT ?test)` [3].
- Núcleo de patrón:
	- `?modelo ex:providedBy ?prov . ?modelo p510:Verified_by ?link . ?link p510:Link ?test .`

##### 3.2.5.5 Distribuciones por estados approval y resúmenes
**`q20_modelos_por_estado_aprobacion.sparql` — Modelos por estado de aprobación.**
- Intención: "distribution of models by approval state".
- Operador SPARQL: `OPTIONAL` + `GROUP BY` [3].
- Núcleo de patrón:
	- `?modelo a p510:DesignModel ; p510:ContentType "Physical Model" . OPTIONAL { ?modelo p510:Approval_State ?approval }`

##### 3.2.5.6 Consultas sobre manifest, PLM, entorno y documentos
Las siguientes queries explotan el nodo `p510:P510_ManifestType` como "entrada" del grafo, y recuperan secciones de información general (PLM, entorno) y/o vínculos a documentos, mediante link nodes.

**`q8_plm_resumen.sparql` — Resumen PLM (metadatos generales).**
- Intención: "PLM summary: org, created, purpose, objective, version".
- Operador SPARQL: recuperación parcial con `OPTIONAL` [3].
- Núcleo de patrón:
	- `?manifest a p510:P510_ManifestType ; p510:has_GeneralPLMInfo ?info .`
	- Campos opcionales en `?info` (p. ej. `p510:Organization`, `p510:Created_on`).

**`q9_dev_environment.sparql` — Entorno de desarrollo (tool, OS, formato, técnica, lenguaje).**
- Intención: "development environment".
- Operador SPARQL: `OPTIONAL` [3].
- Núcleo de patrón:
	- `?manifest a p510:P510_ManifestType ; p510:has_RequirementsDevStructure ?dev .`
	- Campos opcionales (`p510:DevTool_Name`, `p510:DevOS_Name`, etc.).

**`q10_documentos_usados.sparql` — Documentos usados (via link node `uses`).**
- Intención: "what documents are used / referenced by the project".
- Operador SPARQL: patrón de link node + filtro por `ContentType` [3].
- Núcleo de patrón:
	- `?dev p510:uses ?link . ?link a p510:Traceability_Link_Type ; p510:ContentType "Document" ; p510:Link ?doc .`

**`q26_baseline_y_proyecto.sparql` — Baseline y datos de proyecto.**
- Intención: recuperar metadatos de proyecto y baseline.
- Operador SPARQL: `OPTIONAL` anidado (subestructura) [3].
- Núcleo de patrón:
	- `?manifest ... p510:has_GeneralPLMInfo ?info .`
	- Baseline como subnodo (`ex:hasBaseline ?bl`) con `dcterms:created` [9].

##### 3.2.5.7 Escenarios de verificación/validación V&V
**`q11_vnv_escenarios_resumen.sparql` — Resumen de escenarios V&V.**
- Intención: listar escenarios y, si existen, sus enlaces de verificación/validación.
- Operador SPARQL: `OPTIONAL` + `UNION` para alternar `Verified_by`/`Validated_by` [3].
- Núcleo de patrón:
	- `?manifest ... p510:has_Requirements_Verification_Validation ?vnv . ?vnv p510:Scenario ?sc .`
	- Enlaces opcionales: `?sc p510:Verified_by|p510:Validated_by ?link . ?link p510:Link ?target .`

**`q12_vnv_escenarios_incompletos.sparql` — Escenarios sin vínculos de verificación ni validación.**
- Intención: detectar escenarios "incompletos" sin trazas V&V.
- Operador SPARQL: doble ausencia con `FILTER NOT EXISTS` [3].
- Núcleo de patrón:
	- `FILTER NOT EXISTS { ?sc p510:Verified_by ?_v }`
	- `FILTER NOT EXISTS { ?sc p510:Validated_by ?_a }`

##### 3.2.5.8 Conteos de entidades y distribuciones por atributos externos ex:
Estas queries ilustran dos ideas: (i) el uso de conteos globales como "sanidad" del grafo y (ii) distribuciones sobre atributos del namespace `ex:` que el generador incorpora para auditorías y segmentación.

**`q14_conteo_entidades.sparql` — Conteos globales por tipo.**
- Intención: "entity counts by type".
- Operador SPARQL: combinación de `VALUES`, `UNION`, `GROUP BY` [3].
- Núcleo de patrón:
	- `VALUES (?entity ?type) { ("Requirement" p510:Requirement) ... } ?s a ?type .`
	- Caso `Document`: `?s p510:ContentType "Document"`.

**`q27_requisitos_por_subsistema.sparql` — Requisitos por subsistema.**
- Intención: distribución por `ex:subsystem`.
- Operador SPARQL: `OPTIONAL` + `GROUP BY` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement . OPTIONAL { ?req ex:subsystem ?subsystem }`

**`q28_requisitos_por_metodo_verificacion.sparql` — Requisitos por método de verificación.**
- Intención: distribución por `ex:verification_method`.
- Operador SPARQL: `OPTIONAL` + `GROUP BY` [3].
- Núcleo de patrón:
	- `?req a p510:Requirement . OPTIONAL { ?req ex:verification_method ?method }`

Este catálogo funciona como "puente" entre el modelado del grafo (Cap. 3) y la implementación del traductor (Cap. 5): cada operador que se implementa en el motor dinámico tiene (al menos) una query de referencia que materializa el patrón y permite validar resultados de forma independiente.

### 3.3 Especificación de requisitos
La especificación de requisitos es un artefacto fundamental en el desarrollo de cualquier sistema, ya que establece de forma clara, precisa y verificable qué debe hacer la solución y bajo qué restricciones debe operar. En un proyecto orientado a auditoría e integridad del dato, además, esta especificación actúa como un "contrato" técnico: delimita el alcance del sistema (qué preguntas soporta) y fija condiciones no negociables (offline, determinismo y control estricto del esquema).

De forma general, una buena especificación debe aspirar a las siguientes características:
- **Correcta:** los requisitos responden a necesidades justificadas del sistema.
- **No ambigua:** cada requisito admite una única interpretación.
- **Completa:** recoge todos los requisitos significativos dentro del alcance.
- **Consistente:** no contiene contradicciones internas.
- **Clasificada por importancia y/o estabilidad:** cada requisito incluye prioridad y/o probabilidad de cambio.
- **Verificable:** puede comprobarse mediante prueba, revisión o análisis.
- **Modificable:** la estructura del documento permite cambios simples y consistentes.
- **Trazable:** cada requisito tiene identificación única y puede referenciarse durante el ciclo de vida.

Dentro del conjunto de requisitos se distinguen dos grandes grupos:
- **Requisitos funcionales:** describen funciones y servicios del sistema (qué hace ante entradas/situaciones).
- **Requisitos no funcionales:** fijan restricciones y propiedades de calidad (rendimiento, seguridad, reproducibilidad, etc.).

Antes de presentar los requisitos del proyecto, se describe a continuación la estructura utilizada para documentarlos. Cada campo cumple una función específica:
- **Identificador:** código único de referencia (RF-xx o RNF-xx).
- **Nombre:** título breve y representativo.
- **Fuente:** origen del requisito (por ejemplo, necesidades de auditoría, requisitos del dominio o decisiones de ingeniería).
- **Prioridad:** importancia relativa dentro del sistema (Alta/Media/Baja).
- **Estabilidad:** probabilidad de mantenerse sin cambios (Alta/Media/Baja).
- **Necesidad:** dependencia del éxito del sistema respecto a su cumplimiento (Alta/Media/Baja).
- **Verificabilidad:** facilidad para comprobar su cumplimiento de forma objetiva (Alta/Media/Baja).
- **Descripción:** explicación completa del requisito.

La siguiente tabla representa la plantilla utilizada para la especificación de requisitos funcionales y no funcionales del sistema.

**Tabla 3.3 — Plantilla de especificación de requisitos.**

| Identificador | Nombre | Fuente | Prioridad | Estabilidad | Necesidad | Verificabilidad | Descripción |
|---|---|---|---|---|---|---|---|
| RF-xx / RNF-xx | (texto) | (texto) | Alta/Media/Baja | Alta/Media/Baja | Alta/Media/Baja | Alta/Media/Baja | (texto) |

#### 3.3.1 Requisitos funcionales
A continuación se recoge un resumen de los requisitos funcionales del sistema, que describen las funciones que debe ofrecer la herramienta para satisfacer las necesidades del usuario y cumplir los objetivos del proyecto.

**Tabla 3.4 — Tabla resumen de requisitos funcionales.**

| Identificador | Nombre | Prioridad |
|---|---|---|
| RF-01 | Generación de consultas SPARQL de lectura desde preguntas en texto | Alta |
| RF-02 | Ejecución local de la consulta sobre un grafo RDF y devolución de resultados tabulares | Alta |
| RF-03 | Control de esquema: uso exclusivo de vocabulario observado y rechazo de términos inventados | Alta |
| RF-04 | Explicación trazable: operador elegido, señales de grounding y patrón aplicado | Media |
| RF-05 | Disponibilidad del sistema en CLI y demo visual | Media |

Para mantener el cuerpo del documento legible, la especificación detallada (según la plantilla de la Tabla 3.3) se resume en las tablas de este apartado y se complementa con evidencias ejecutables en el repositorio (Cap. 5).

#### 3.3.2 Requisitos no funcionales
En esta sección se recoge un resumen de los requisitos no funcionales, que fijan restricciones y propiedades de calidad necesarias para que el sistema sea útil en auditoría.

**Tabla 3.5 — Tabla resumen de requisitos no funcionales.**

| Identificador | Nombre | Prioridad |
|---|---|---|
| RNF-01 | Determinismo del pipeline (misma entrada y grafo → misma SPARQL y salida) | Alta |
| RNF-02 | Reproducibilidad experimental (dataset/oráculos/scripts y logs) | Alta |
| RNF-03 | Seguridad: bloqueo de SPARQL Update y validación previa a ejecución | Alta |
| RNF-04 | Extensibilidad por familias (incorporación de nuevos operadores/patrones) | Media |

### 3.4 Casos de uso
Los casos de uso representan cómo interactúan los actores con el sistema para alcanzar objetivos concretos, describiendo el comportamiento desde la perspectiva del usuario. En este proyecto se utilizan para concretar el alcance funcional (qué flujos soporta la herramienta) y, posteriormente, verificar cobertura respecto a requisitos.

Antes de presentar los casos de uso, se describe la estructura utilizada para documentarlos:
- **Identificador:** clave única (CU-01, CU-02, …).
- **Nombre:** título breve.
- **Actor:** entidad que interactúa con el sistema (Usuario/Sistema).
- **Fuente:** requisitos relacionados.
- **Precondiciones:** condiciones necesarias antes de iniciar el caso.
- **Postcondiciones:** estado esperado al finalizar.
- **Descripción:** explicación detallada de la interacción.

**Tabla 3.6 — Plantilla de casos de uso.**

| Identificador | Nombre | Actor | Fuente | Precondiciones | Postcondiciones | Descripción |
|---|---|---|---|---|---|---|
| CU-xx | (texto) | Usuario/Sistema | RF-xx | (texto) | (texto) | (texto) |

#### 3.4.1 Resumen de casos de uso
Se presenta a continuación un resumen de los casos de uso principales, que cubren el flujo end-to-end de la herramienta (generación, validación y ejecución) y la inspección mediante explicación.

**Tabla 3.7 — Tabla resumen de casos de uso.**

| Identificador | Nombre | Actor |
|---|---|---|
| CU-01 | Realizar una consulta en lenguaje natural | Usuario |
| CU-02 | Generar consulta SPARQL (routing + compilación por operador) | Sistema |
| CU-03 | Validar consulta (checker: no Update + no invención de vocabulario) | Sistema |
| CU-04 | Ejecutar consulta sobre el grafo local y devolver resultados | Sistema |
| CU-05 | Mostrar explicación/traza del proceso | Sistema |

#### 3.4.2 Matriz de trazabilidad
Por último se muestra una matriz de trazabilidad que relaciona requisitos funcionales y casos de uso, con el objetivo de comprobar que las funcionalidades esperadas (requisitos) están cubiertas por las interacciones descritas.

**Tabla 3.8 — Matriz de trazabilidad (RF ↔ CU).**

|  | CU-01 | CU-02 | CU-03 | CU-04 | CU-05 |
|---|---|---|---|---|---|
| RF-01 | X | X |  |  |  |
| RF-02 | X | X |  | X |  |
| RF-03 |  |  | X |  |  |
| RF-04 |  | X | X | X | X |
| RF-05 | X |  |  |  | X |

### 3.5 Riesgos técnicos potenciales
En el diseño y desarrollo de un sistema NL→SPARQL, especialmente en un contexto de auditoría, es importante anticipar riesgos técnicos que puedan comprometer precisión, rendimiento o mantenibilidad. El objetivo de este análisis es identificar escenarios problemáticos y definir mitigaciones que reduzcan su impacto.

Para cada riesgo se consideran los siguientes campos:
- **Riesgo técnico:** descripción breve del problema.
- **Descripción:** detalle de en qué consiste y por qué afecta al sistema.
- **Probabilidad:** estimación de ocurrencia (Alta/Media/Baja).
- **Impacto:** gravedad si ocurre (Alto/Medio/Bajo).
- **Mitigación:** acciones para evitar o reducir el efecto.

**Tabla 3.9 — Riesgos técnicos.**

| Riesgo técnico | Descripción | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| Deriva del routing por cambios mínimos | Pequeños cambios en normalización/sinónimos alteran el operador elegido y rompen estabilidad por intención | Media | Alto | Smoke test de paráfrasis como regresión; versionado de sinónimos; priorización explícita de operadores |
| Consultas inválidas por invención de vocabulario | Generación de predicados/clases no presentes en el grafo observado | Media | Alto | Checker estricto de términos; sugerencias "did you mean"; grounding únicamente a vocabulario observado |
| Rendimiento insuficiente en consultas costosas | Consultas con agregación/joins sobre grafos mayores degradan tiempos | Media | Medio | `LIMIT` por defecto; métricas de tiempo en evaluación; diseño de operadores acotados y patrones eficientes |
| Ambigüedad lingüística fuera de cobertura | Preguntas no mapeables a familias soportadas producen resultados incorrectos o inconsistentes | Media | Medio | Fallo controlado (error explicable); catálogo/baseline; documentación explícita de cobertura por familias |
| Dependencia del motor SPARQL | Diferencias entre motores afectan compatibilidad o rendimiento | Baja | Medio | Fijar motor de referencia (RDFLib) y versión; artefactos reproducibles; advertir limitaciones |

### 3.6 Criterios de aceptación y métricas
Por último, esta sección fija criterios de aceptación y métricas simples para validar el sistema de forma reproducible, distinguiendo entre ejecución, alineación al esquema y estabilidad por intención.

Para considerar el sistema válido, se establecen los siguientes criterios de aceptación:

- Ejecución correcta: la SPARQL generada se ejecuta sin errores sobre el grafo.
- Alineación al esquema: no aparecen prefijos o predicados inexistentes.
- Cobertura de ejemplos: porcentaje de ejemplos del conjunto de evaluación que el sistema resuelve dentro del conjunto de operadores soportados.
- Robustez a parafraseo: dentro de una misma familia (misma intención), distintas paráfrasis deben converger al mismo operador y a resultados consistentes (por ejemplo, misma cardinalidad o misma salida esperada).

En la evaluación se reportan métricas simples y reproducibles: tasa de éxito por ejemplo, distribución de operadores elegidos y consistencia por grupos de paráfrasis.

Para interpretar los resultados de forma honesta (y evitar conclusiones infladas), es importante distinguir entre:

- **Corrección ejecutable:** la consulta se ejecuta sin error en el motor SPARQL (en este caso, RDFLib [10]).
- **Corrección semántica aproximada:** el resultado coincide con lo esperado para el caso de uso (por ejemplo, "requirements without a physical model" devuelve exactamente los requisitos que no tienen ese enlace). Esta corrección requiere un oráculo (consulta de referencia o validación manual) y no se deduce solo del hecho de "ejecutar".
- **Estabilidad:** la misma intención expresada con paráfrasis conduce a un routing consistente y, por tanto, a resultados comparables.

Esta distinción es relevante porque, como discute la literatura de evaluación en KGQA, comparar sistemas sin un protocolo claro puede llevar a resultados poco reproducibles o difíciles de verificar [7].

---

## 4. Diseño

Esta sección contiene el diseño de la solución: la estrategia de traducción determinista, el pipeline de arquitectura y los mecanismos de control (grounding y checker) que permiten justificar y auditar el comportamiento del sistema.

Por tanto, el objetivo de este capítulo es describir cómo se transforma una pregunta en lenguaje natural en una consulta SPARQL ejecutable sobre un grafo local, manteniendo determinismo, seguridad y alineación estricta al esquema observado.

A continuación se presenta la solución propuesta, la arquitectura del sistema, el entorno tecnológico y las decisiones de diseño consideradas.

### 4.1 Solución propuesta
En este apartado se describe la solución propuesta a nivel conceptual. La solución se basa en un motor de traducción determinista que identifica (a) la **intención** del usuario dentro de un conjunto de familias soportadas y (b) los elementos del dominio relevantes (entidades, predicados, filtros). A partir de esa información compila una SPARQL siguiendo un patrón asociado a un **operador**.

Un principio central del diseño es el **grounding**: las palabras y frases detectadas no se interpretan "en abstracto", sino que se asocian a términos del esquema (predicados/clases) extraídos del grafo. Esta decisión permite controlar el comportamiento del sistema y evita resultados engañosos.

La explicación se modela como una traza que incluye: normalización aplicada, coincidencias de grounding (palabra/frase → concepto del esquema), operador elegido y justificación, y el patrón SPARQL utilizado.

### 4.2 Arquitectura del sistema
En este apartado se describe la arquitectura como un pipeline lineal con pasos claramente separables:

1) **Normalización y sinónimos:** homogeneiza texto (por ejemplo, mayúsculas/minúsculas, tildes, variantes léxicas) para robustez.
2) **Indexado del esquema:** extrae del grafo el conjunto de clases/predicados relevantes, generando un índice consultable.
3) **Grounding:** detecta señales en el texto y produce hipótesis de mapeo a entidades/predicados/operadores.
4) **Routing:** decide qué operador compila la consulta y qué argumentos utilizar.
5) **Compilación:** genera SPARQL a partir de un patrón controlado.
6) **Checker:** valida que la consulta no contiene escritura (Update) y que todos los términos pertenecen al esquema.
7) **Ejecución:** ejecuta la consulta en RDFLib y serializa los resultados.
8) **Explicación:** devuelve la traza completa para inspección.

Los componentes se exponen mediante una CLI y una interfaz visual, además de scripts de evaluación.

#### 4.2.1 Diagrama conceptual texto
Aunque en una versión final conviene incluir una figura, el pipeline puede describirse de forma auto-contenida como un grafo de artefactos y transformaciones:

```
Pregunta NL
  └─> (1) Normalización + sinónimos
	  └─> Texto normalizado + tokens significativos
		  ├─> (2) Carga TTL -> Grafo RDF (RDFLib) [10]
		  │      └─> (3) Indexado -> SchemaIndex (clases/predicados/prefijos)
		  └─> (4) Grounding -> Hits + traza parcial
			   └─> (5) Routing -> Operador/familia + argumentos
				   └─> (6) Compilación -> SPARQL
					   └─> (7) Checker (gate) -> SPARQL validada | error
						   └─> (8) Ejecución (RDFLib) -> Resultados

Salida: (a) tabla de resultados, (b) explicación/traza (hits + operador + motivos)
Clientes: CLI / demo visual / scripts de evaluación
```

Este diagrama textual ya fija, de manera verificable, qué "entra" y qué "sale" en cada etapa.

#### 4.2.2 Contratos de datos interfaces internas
El sistema define explícitamente contratos para mantener el pipeline modular:

- **Configuración de generación.** Una estructura de configuración recoge el modo de motor (dinámico vs catálogo), límites por defecto (`LIMIT`), umbrales de similitud, rutas de sinónimos y, opcionalmente, parámetros del clasificador offline.
- **Resultado de generación.** El motor devuelve como mínimo la SPARQL resultante, el número de intentos, y metadatos para trazabilidad (por ejemplo, id/candidato emparejado en modo catálogo). En modo explicable, además devuelve una lista de líneas de explicación que el cliente (CLI/demo) solo imprime.

Estos contratos permiten que las interfaces sean "delgadas": no deciden lógica, solo orquestan entrada/salida.

#### 4.2.3 Manejo de errores y modos de fallo
En un sistema de auditoría, "fallar bien" es parte del diseño. Se distinguen modos de fallo esperables:

- **Pregunta fuera de cobertura.** No hay señales suficientes para rutear a una familia; se devuelve error con sugerencias (modo catálogo) o un mensaje de incapacidad (modo dinámico).
- **Violación de seguridad.** La SPARQL contiene palabras clave prohibidas o no es `SELECT`/`ASK`; se rechaza antes de ejecución.
- **Invención de términos.** La SPARQL referencia clases/predicados inexistentes o prefijos no permitidos; el checker rechaza e incluye sugerencias.
- **Ejecución fallida.** El motor SPARQL lanza error (p. ej. sintaxis); se reporta como error controlado.

Este tratamiento convierte "salidas engañosas" en errores verificables y facilita depuración (Cap. 5.2.6).

#### 4.2.4 Estructuras internas y contratos según implementación
El diseño del motor se apoya en contratos explícitos, implementados como *dataclasses inmutables* (`@dataclass(frozen=True)`) en [src/text2sparql.py](src/text2sparql.py). Esta decisión simplifica la depuración (los objetos son "snapshots" del estado) y refuerza determinismo (no hay mutaciones implícitas entre fases).

Los artefactos internos principales son:

- **`GenerationConfig`.** Configura el motor: `engine` (`dynamic|catalog`), `limit` por defecto, umbrales de similitud (`match_threshold`), y parámetros opcionales del clasificador Naive Bayes offline (ruta y probabilidad mínima).
- **`GenerationResult`.** Resultado end-to-end de generación: `sparql`, nº de intentos, (opcional) `matched_id/matched_nl/match_score` cuando la salida proviene de selección de catálogo, `error` si falla, y `explanation` cuando se solicita modo explicable.
- **`SchemaIndex`.** Índice del esquema observado: conjunto de clases (`rdf:type`), predicados del grafo, prefijos disponibles y mapas normalizados `class_by_local/pred_by_local` para resolver nombres locales.
- **`GroundingResult` y `GroundingHit`.** Producto del grounding: texto normalizado, conjunto de tokens significativos (`tokens_sig`) y lista de "hits" que asocian frase → (`operator|entity|predicate|attribute|literal`) → término del esquema.
- **`SynonymMap`.** Diccionario de sinónimos normalizados (frases y palabras) que permite unificar expresiones antes de rutear.

Esta separación permite que el sistema tenga un núcleo claro: *indexar → hacer grounding → decidir operador → compilar → chequear → ejecutar*.

#### 4.2.5 Normalización y sinónimos robustez sin aleatoriedad
Un reto práctico de NL→SPARQL es que el usuario no usa necesariamente los mismos identificadores que el esquema (`Approval_State` vs "approved state", `Timestamp_PLM` vs "PLM timestamp", etc.). Para reducir sensibilidad a variaciones, la implementación incorpora:

- **Normalización estable de claves.** Funciones como `_norm_key(...)` y `_local_name(...)` convierten nombres a formas comparables (minúsculas, eliminar separadores no alfanuméricos) para mapear tokens NL ↔ nombres locales del esquema.
- **Mapa de sinónimos determinista.** Se carga un fichero de sinónimos (`SynonymMap`), por defecto desde `prompts/system_en.txt` si existe, y se aplica como preprocesado (unificando variantes léxicas).

La filosofía es deliberadamente conservadora: el sistema prefiere "no hacer grounding" a forzar un mapeo dudoso. Esto se alinea con el requisito RNF3 (seguridad) y con el objetivo de auditoría (fallo controlado antes que consulta inventada).

#### 4.2.6 Routing por operadores como política explícita registry ordenado
La decisión central del motor es seleccionar un **operador** (familia) y compilar un patrón SPARQL. En [src/text2sparql.py](src/text2sparql.py) esto se implementa como un *registry* de operadores escrito como ramas `if` **ordenadas**, lo que convierte el routing en una política explícita y fácil de inspeccionar.

El proceso (simplificado) es:

1) Construir `SchemaIndex` observando el grafo.
2) Calcular señales booleanas y *hits* de grounding (p. ej. `wants_missing`, `is_duplicate`, `want_req`, `want_link`, presencia de literales como "Physical Model").
3) Evaluar operadores en orden de prioridad y seleccionar el primero aplicable.
4) Compilar SPARQL con prefijos del grafo (`_prefix_lines(...)`) y aplicar `LIMIT` (`ensure_limit(...)`).

Esta implementación tiene una consecuencia importante: dos expresiones similares en NL que activan las mismas señales deben caer en el mismo operador. Esto explica por qué el *smoke test* de paráfrasis se formula como prueba de regresión de estabilidad (Cap. 5.3.3).

#### 4.2.7 Checker anti-invención como control obligatorio antes de ejecutar
El control de esquema se realiza con la función `check_no_invented_terms(...)`. Su objetivo es rechazar consultas que (a) declaran prefijos hacia namespaces ajenos al grafo observado o (b) referencian clases/predicados que no aparecen como términos del grafo.

Aunque no es un parser SPARQL completo, el checker es estricto en los puntos críticos:

- Valida `PREFIX` declarados comparándolos con namespaces observados en el grafo y con vocabularios estándar permitidos.
- Busca términos prefijados (`p510:...`, `foaf:...`) y los expande a IRIs; si pertenecen a un namespace permitido pero no están en el conjunto de clases/predicados observados, se rechazan.
- Valida roles estructurales dentro del `WHERE`: objetos de `a <Class>` deben ser clases, y términos en posición de predicado deben estar en el conjunto de predicados.
- Añade sugerencias (*did you mean...*) basadas en similitud de nombre local (`difflib.get_close_matches`) para facilitar depuración.

Este *gate* convierte el requisito "no inventar vocabulario" en una verificación ejecutable. A nivel de diseño, también permite comparar de forma más honesta enfoques generativos: cualquier salida debe superar el checker antes de considerarse válida.

#### 4.2.8 Diseño multi-motor: `dynamic` vs `catalog` y clasificador offline opcional
El sistema expone dos estrategias de generación en `generate_sparql(...)`:

- **Motor `dynamic` (principal).** Genera SPARQL *on-the-fly* con grounding al esquema y operadores (no requiere catálogo). Es el enfoque que maximiza extensibilidad por familias y control de vocabulario.
- **Motor `catalog` (baseline/legacy).** Selecciona la mejor consulta de un catálogo JSONL por similitud textual. Si la similitud es baja (por debajo de `match_threshold`), puede activarse un **clasificador Naive Bayes** entrenado offline (si se proporciona modelo), que propone un `id` de ejemplo.

Este diseño permite comparar dos formas de "acotar el espacio de programas": (i) plantillas (catálogo) vs (ii) compilación por operadores. En ambos casos, el checker y la ejecución local actúan como verificación final.

Desde el punto de vista de ingeniería, esta arquitectura tiene dos ventajas relevantes:
- **Aislamiento de responsabilidades.** Cada paso tiene una entrada y salida claras (texto normalizado, hits de grounding, operador/ruta elegida, SPARQL generada). Esto facilita depuración y permite justificar decisiones.
- **Puntos de control ("gates") para seguridad y calidad.** El checker actúa como un control obligatorio antes de ejecutar la consulta: si la SPARQL contiene escritura o términos fuera de esquema, la ejecución se bloquea.

La implementación concreta sigue esta estructura: el motor de generación concentra la lógica de grounding, routing y compilación; las interfaces (CLI y demo) son delgadas y se limitan a cargar el grafo, invocar al generador y presentar SPARQL, resultados y explicación.

### 4.3 Entorno tecnológico
En este apartado se resume el entorno tecnológico seleccionado y su justificación. Se utiliza Python por su ecosistema de procesamiento de texto y por la disponibilidad de RDFLib para manipulación y consulta de grafos RDF. RDFLib ofrece una API madura para cargar ficheros TTL y ejecutar consultas SPARQL. Para la interfaz de demostración se utiliza Streamlit, por su rapidez para construir UI de pruebas orientada a datos.

En concreto, el backend de ejecución de consultas se apoya en RDFLib [10], mientras que la demo visual se construye con Streamlit [11].

El dataset se representa en formato Turtle (TTL) y se genera de forma sintética para garantizar reproducibilidad.

### 4.4 Decisiones de diseño y alternativas
Por último, se justifican las decisiones clave en función de los requisitos de control y auditoría:
- **Offline y determinista:** asegura reproducibilidad y evita dependencia de terceros; además reduce riesgos de privacidad.
- **Checker anti-invención:** mejora la credibilidad del sistema y evita consultas "aparentemente correctas" pero inválidas en el grafo.
- **Operadores:** permiten combinar control y extensibilidad: cada nueva familia se añade como un operador con un patrón SPARQL validable.

Como alternativas se consideran: (i) plantillas fijas, con precisión alta pero cobertura limitada, y (ii) enfoques generativos, con mayor expresividad pero menos control sin mecanismos adicionales.

Una decisión adicional, específica para este proyecto, es priorizar la **ejecución real** de la SPARQL como parte del propio pipeline. En lugar de detenerse en "generar una consulta plausible", el sistema valida y ejecuta localmente cada salida. Esto reduce el riesgo de aceptar consultas sintácticamente correctas pero no ejecutables sobre el dataset.

### 4.5 Validación del sistema criterios y protocolo
Una vez se han implementado las fases principales del pipeline (normalización, grounding, routing, compilación, checker y ejecución), se plantea un proceso de validación orientado a evaluar su rendimiento y utilidad en un contexto de auditoría. Esta validación se centra en el sistema al completo, desde la consulta en lenguaje natural hasta la obtención del resultado tabular y la traza explicable, e incluye tanto métricas automáticas como observaciones manuales.

El objetivo de este apartado no es anticipar resultados numéricos, sino fijar **qué se mide**, **cómo se mide** y **cómo se interpreta**, de manera coherente con los requisitos no funcionales de determinismo, reproducibilidad y seguridad (Cap. 3).

#### 4.5.1 Tiempos de respuesta end-to-end
En una herramienta offline, el tiempo de respuesta viene determinado por (i) la carga del TTL y el indexado del esquema, (ii) la generación de SPARQL (grounding + routing + compilación), (iii) la validación del checker, y (iv) la ejecución en el motor SPARQL (RDFLib) [10].

Para medir de forma honesta este coste, se distinguen dos escenarios:
- **Arranque en frío (cold start):** incluye la carga del grafo y el indexado.
- **Arranque en caliente (warm start):** reutiliza el grafo ya cargado y mide principalmente generación + checker + ejecución.

De manera análoga al ejemplo, se seleccionan varias preguntas representativas (familias de ausencia, duplicados y agregación) y se repiten varias ejecuciones consecutivas. La Tabla 4.1 muestra una plantilla de registro que permite recoger los tiempos y calcular medias.

Las medidas de este apartado se han realizado localmente en Windows 11 (Python 3.14.3, RDFLib 7.5.0), ejecutando el pipeline completo (generación + checker + ejecución) sobre `data/p510_sintetico.ttl`.

**Tabla 4.1 — Plantilla de registro de tiempos de respuesta (segundos).**

| Pregunta (intención) | Escenario | Tiempo 1 (s) | Tiempo 2 (s) | Tiempo 3 (s) |
|---|---|---:|---:|---:|
| "requirements without physical model" | warm | 1.45 | 1.30 | 1.26 |
| "audit duplicate links" | warm | 0.12 | 0.14 | 0.19 |
| "how many suppliers?" | warm | 0.06 | 0.03 | 0.03 |
| "links missing timestamps" | warm | 0.06 | 0.08 | 0.07 |
| "requirements without physical model" | cold | 1.99 | 1.61 | 1.44 |
| "audit duplicate links" | cold | 0.23 | 0.22 | 0.28 |
| "how many suppliers?" | cold | 0.14 | 0.13 | 0.15 |
| "links missing timestamps" | cold | 0.16 | 0.17 | 0.17 |

En estas 12 ejecuciones, el tiempo medio end-to-end ha sido de aproximadamente 0.40 s en warm start y 0.56 s en cold start.

En el caso del proyecto, el propósito de esta medida es doble: (i) caracterizar la experiencia de uso de CLI y demo visual, y (ii) detectar regresiones de rendimiento cuando se incorporan nuevas familias u operaciones SPARQL más costosas.

#### 4.5.2 Evaluación automática: ejecutabilidad, seguridad y estabilidad
Para un sistema NL→SPARQL orientado a auditoría, "calidad" no solo significa obtener un resultado, sino garantizar que la consulta es **ejecutable**, **segura** y **alineada con el esquema observado**. Por ello, las métricas automáticas se organizan en tres ejes:
- **Ejecutabilidad.** Proporción de preguntas para las que el pipeline produce una SPARQL que (a) pasa el checker y (b) se ejecuta sin error en RDFLib.
- **Seguridad y control de esquema.** Proporción de consultas rechazadas por contener SPARQL Update o términos fuera del vocabulario observado (RNF-03).
- **Estabilidad por intención.** Para grupos de paráfrasis (misma intención, distinta formulación), se espera convergencia al mismo operador y resultados comparables (RNF-01).


En particular, la estabilidad puede medirse de forma similar a una métrica "por grupo":

$$
\mathrm{Consistencia}_{op}=\frac{1}{G}\sum_{g=1}^{G}\mathbb{1}\big[op_{g,1}=op_{g,2}=\dots=op_{g,n_g}\big]
$$

donde $G$ es el número de grupos de paráfrasis y $op_{g,i}$ es el operador seleccionado (línea `operator:` en la traza) para la i-ésima paráfrasis del grupo $g$. Complementariamente, puede definirse una consistencia de resultado basada en igualdad de cardinalidad o igualdad del conjunto de filas (cuando sea aplicable).

La Tabla 4.2 resume estas métricas y su interpretación. Las ejecuciones automáticas se apoyan en los scripts de evaluación del repositorio (Cap. 5.3), de manera que la validación sea reproducible.

**Tabla 4.2 — Métricas automáticas de validación (definición).**

| Métrica | Qué mide | Por qué es relevante |
|---|---|---|
| Tasa de éxito ejecutable | SPARQL pasa checker y ejecuta sin error | Evita "consultas plausibles" pero inútiles |
| Tasa de rechazo por esquema | Consultas rechazadas por términos no observados | Refuerza RF-03 y RNF-03 (no invención) |
| Tasa de rechazo por Update | Consultas bloqueadas por escritura | Garantiza seguridad de la ejecución |
| Consistencia por paráfrasis ($\mathrm{Consistencia}_{op}$) | Misma intención → mismo operador | Evidencia determinismo y estabilidad (RNF-01) |
| Distribución de operadores | Frecuencia por familia | Detecta sesgos del routing y gaps de cobertura |

Al aplicar estas métricas al repositorio (motor `dynamic`, grafo sintético P510), se obtienen los siguientes resultados:
- **Tasa de éxito ejecutable:** 34/34 ejemplos del catálogo (`eval/text2sparql_examples.jsonl`) generan una SPARQL que se ejecuta sin error en RDFLib (100%).
- **Rechazos por seguridad/esquema:** en este conjunto no se observan rechazos por Update ni por checker (0%).
- **Estabilidad por intención:** en el *smoke test* de paráfrasis (`eval/paraphrase_smoke.py`) se obtiene $\mathrm{Consistencia}_{op}=26/26=1.00$ (74 casos agrupados en 26 intenciones), y también consistencia de cardinalidad en todos los grupos.

Adicionalmente, el tiempo medio end-to-end por ejemplo (generación + checker + ejecución, grafo ya cargado) es de aproximadamente 262 ms, con un percentil 95 de aproximadamente 1.74 s, lo cual ayuda a detectar regresiones si se añaden familias más costosas.

#### 4.5.3 Evaluación manual de casos calidad de intención y explicación
Además de métricas automáticas, resulta útil una revisión manual de un conjunto pequeño de casos representativos, especialmente para evaluar la **claridad de la explicación** y la **adecuación del operador** seleccionado.

En esta revisión se consideran criterios prácticos:
- **Corrección de intención:** el operador seleccionado coincide con lo que el usuario pretende auditar.
- **Alineación al esquema:** los predicados/clases usados son los del grafo observado (sin inventar vocabulario).
- **Comprensibilidad:** la traza explica, de forma legible, qué señales activaron el routing y qué patrón SPARQL se aplicó.
- **Modo de fallo:** cuando la pregunta está fuera de cobertura, el sistema falla de forma controlada (mensaje explicable), en lugar de producir una salida engañosa.

Como conjunto mínimo, se recomiendan casos de: (i) ausencia (`FILTER NOT EXISTS`), (ii) duplicidad (`GROUP BY/HAVING`) y (iii) agregación (`COUNT`/distribuciones). En el Cap. 5 se muestran capturas de ejecuciones reales (CLI y demo) que ejemplifican estos casos.

Se muestran a continuación tres casos representativos ejecutados sobre `data/p510_sintetico.ttl`. En cada caso se indica la intención, el patrón SPARQL dominante y un análisis cualitativo de la explicación.

**Caso 1: Requisitos sin modelo físico.**

Pregunta: "List requirements without a physical model."

Resultado observado: 8 filas devueltas.

SPARQL generada (extracto):

```sparql
SELECT DISTINCT ?id ?req WHERE {
	?req a p510:Requirement .
	FILTER NOT EXISTS {
		?req p510:Satisfied_by ?ln .
		?ln a p510:Traceability_Link_Type ;
				p510:ContentType "Physical Model" ;
				p510:Link ?target .
		?target a p510:DesignModel .
	}
	OPTIONAL { ?req p510:Id ?id . }
}
```

Análisis:
- **Corrección de intención:** el sistema interpreta correctamente una auditoría por ausencia (señal "missing/without") y compila el patrón `FILTER NOT EXISTS` sobre la relación `Satisfied_by` restringida a `ContentType="Physical Model"`.
- **Alineación al esquema:** se emplean clases y predicados del vocabulario observado (`Requirement`, `Satisfied_by`, `Traceability_Link_Type`, `Link`, `ContentType`).
- **Comprensibilidad:** aunque no aparece un nombre de operador explícito en la traza para este caso, la explicación incluye los elementos clave (tokens significativos, restricción de ausencia, relación y clases origen/destino), lo que permite auditar por qué se construye el patrón.
- **Errores:** no se observan errores; la consulta es ejecutable y devuelve una lista acotada.

**Caso 2: Auditoría de duplicados.**

Pregunta: "Audit: duplicate traces (same source + predicate + target repeated)."

Resultado observado: 29 filas devueltas.

SPARQL generada (extracto):

```sparql
SELECT ?src ?pred ?target (COUNT(DISTINCT ?link) AS ?numLinks) WHERE {
	VALUES ?pred { p510:Satisfied_by p510:Verified_by p510:Validated_by p510:uses }
	?src ?pred ?link .
	?link p510:Link ?target .
}
GROUP BY ?src ?pred ?target
HAVING(COUNT(DISTINCT ?link) > 1)
```

Análisis:
- **Corrección de intención:** el operador seleccionado es `DUPLICATE_TRACES_AUDIT`, coherente con la intención "duplicate".
- **Alineación al esquema:** el patrón se limita a predicados del dominio y a `p510:Link` como conexión al objetivo, evitando inventar relaciones.
- **Comprensibilidad:** la traza expone el patrón aplicado ("`VALUES` + `GROUP BY/HAVING`") y lista explícitamente los predicados auditados.
- **Errores:** no se observan errores; la consulta identifica duplicidad por cardinalidad (>1).

**Caso 3: Links without timestamps.**

Pregunta: "Find traceability links without timestamps."

Resultado observado: 3 filas devueltas.

SPARQL generada (extracto):

```sparql
SELECT ?link WHERE {
	?link a p510:Traceability_Link_Type .
	FILTER(
		!EXISTS { ?link p510:Timestamp_Archiving ?ta } ||
		!EXISTS { ?link p510:Timestamp_PLM ?tp }
	)
}
```

Análisis:
- **Corrección de intención:** el operador seleccionado es `LINKS_MISSING_TIMESTAMP`, que compila una ausencia sobre dos campos considerados obligatorios.
- **Alineación al esquema:** el grounding reconoce "timestamp" como atributo y limita la consulta a `Timestamp_Archiving`/`Timestamp_PLM`.
- **Comprensibilidad:** la explicación enlaza la palabra clave ("timestamp") con el atributo y explicita el criterio ("missing: Timestamp_Archiving or Timestamp_PLM").
- **Errores:** no se observan errores; la salida es directa y verificable.

---

## 5. Implementación y pruebas
En esta sección se describe la implementación del sistema y el conjunto de pruebas con el que se valida su comportamiento. A diferencia de enfoques basados en modelos generativos, en este proyecto la "generación" se entiende como compilación determinista de patrones SPARQL a partir de señales lingüísticas y del vocabulario observado en el propio grafo.

También se detalla el proceso de configuración y calibración del motor (umbrales, límite por defecto, sinónimos y modo de ejecución), con el fin de mantener reproducibilidad y estabilidad por intención. Por último, se presenta la evaluación automática (catálogo de ejemplos y *smoke tests* de paráfrasis) que permite detectar regresiones cuando se introducen nuevos operadores o se ajustan reglas.

### 5.1 Estructura del proyecto
La implementación se organiza en módulos que separan claramente el motor de traducción, las interfaces y la evaluación. En el repositorio se incluyen:

- Motor de traducción NL→SPARQL.
- Interfaz de línea de comandos (CLI) para ejecución rápida y reproducible.
- Demos para uso interactivo (visual/web).
- Scripts para generar el grafo sintético y ejecutar el conjunto de evaluación.

Esta separación facilita la trazabilidad de cambios: el núcleo (motor) permanece estable mientras las interfaces pueden evolucionar sin afectar a la lógica.

De forma práctica, el punto de entrada del motor es el módulo `src/text2sparql.py`, y las principales interfaces y utilidades son:

- CLI: `src/text2sparql_cli.py` (modo "translate" o "run").
- Evaluación automática: `src/text2sparql_eval.py` (validación de consultas de referencia o generación desde NL).
- Demo visual: `src/demo_visual.py` (Streamlit) [11].
- Generación del grafo sintético: `src/p510_generate_synthetic.py`.
- Ejecución de queries P510 de referencia: `src/run_queries_p510.py`.

#### 5.1.1 Proceso de desarrollo de consultas de referencia a operadores
El desarrollo del repositorio sigue una lógica incremental orientada a reproducibilidad:

1) **Definir el dato y el oráculo.** Se genera un grafo reproducible (TTL) con `src/p510_generate_synthetic.py` y se fijan consultas SPARQL de referencia en `queries_p510/`. Estas consultas se ejecutan en lote con `src/run_queries_p510.py` para validar que dataset y consultas son coherentes.
2) **Implementar el motor determinista.** A partir de las familias del oráculo (ausencia, distribuciones, duplicados, integridad) se implementan patrones de compilación por operadores en `src/text2sparql.py`.
3) **Cerrar el circuito con *gates*.** Se añade el checker (seguridad y control de esquema) antes de permitir la ejecución, para evitar SPARQL Update [12] y vocabulario inventado.
4) **Instrumentar y evaluar.** Se incorpora una CLI reproducible (`src/text2sparql_cli.py`) y una evaluación automática (`src/text2sparql_eval.py`) que ejecuta tanto el oráculo (`--mode reference`) como la generación (`--mode generate`).
5) **Robustez a reformulaciones.** Se añade un *smoke test* de paráfrasis (`eval/paraphrase_smoke.py`) como prueba de regresión: misma intención, distintas formulaciones, mismo operador y resultados consistentes.

Este esquema de iteración está alineado con la idea de mantener una evaluación trazable y repetible: cada cambio del motor se contrasta contra un conjunto estable de consultas/ejemplos y contra pruebas de robustez [7].

#### 5.1.2 Flujo de funcionamiento de la herramienta end-to-end
El flujo de ejecución, de extremo a extremo, es el siguiente:

1) **Entrada (NL).** El usuario introduce una pregunta en la CLI (`src/text2sparql_cli.py`) o en la demo (`src/demo_visual.py`).
2) **Carga de grafo.** Se carga `data/p510_sintetico.ttl` en memoria (RDFLib) [10].
3) **Indexado del esquema.** Se extraen clases y predicados presentes para construir el *schema index*.
4) **Normalización + *grounding*.** Se normaliza el texto y se detectan hits (entidades/atributos/operadores).
5) **Routing → operador.** Se selecciona una familia/operador soportado (p. ej. auditoría de timestamps, duplicados, distribución por categoría).
6) **Compilación SPARQL.** El operador se compila a un patrón SPARQL conforme al estándar (por ejemplo, `FILTER NOT EXISTS`, `GROUP BY`, `HAVING`) [3].
7) **Checker (gate).** Se valida que la SPARQL es de lectura (sin Update) [12] y no contiene términos fuera de esquema.
8) **Ejecución + salida.** Se ejecuta la consulta en RDFLib [10] y se presentan resultados (tabla) y explicación (`--explain`).

El elemento clave es que la salida no es solo SPARQL: también se devuelve una traza con el operador elegido (línea `operator:` en la explicación) y los hits de *grounding*, lo que facilita depuración y auditoría.

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/ui_streamlit_end2end.png}
\caption{Demo visual (Streamlit): ejemplo end-to-end. La captura muestra la demo de \texttt{src/demo_visual.py} con una pregunta de auditoría ("requirements missing end-to-end traceability"). En la misma vista se observa (i) la SPARQL generada, (ii) el \emph{match} del motor y (iii) una tabla con los resultados tras ejecución local sobre el TTL.}
\label{fig:ui_streamlit_end2end}
\end{figure}

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/ui_streamlit_duplicates.png}
\caption{Demo visual: auditoría de duplicados (familia \texttt{GROUP BY/HAVING}). La captura muestra una pregunta ("audit duplicate links") que enruta al operador de duplicados y evidencia el patrón SPARQL característico con agregación (\texttt{HAVING(COUNT(DISTINCT ?link) > 1)}), coherente con la query de referencia \texttt{q24\_links\_duplicados.sparql}.}
\label{fig:ui_streamlit_duplicates}
\end{figure}

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/ui_streamlit_explain_end2end.png}
\caption{Demo visual: traza de explicación (equivalente a \texttt{--explain}) en el caso end-to-end. Se observa la normalización, los hits de \emph{grounding} y, especialmente, la selección explícita de operador (\texttt{operator: ...}) y del patrón de compilación (por ejemplo, \texttt{NOT EXISTS} con el camino Req$\rightarrow$Model$\rightarrow$Test).}
\label{fig:ui_streamlit_explain_end2end}
\end{figure}

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/ui_streamlit_explain_duplicates.png}
\caption{Demo visual: traza de explicación para la auditoría de duplicados. La explicación evidencia el enrutado hacia el operador de duplicidad y el uso del patrón de agregación (\texttt{GROUP BY/HAVING}).}
\label{fig:ui_streamlit_explain_duplicates}
\end{figure}

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/cli_explain_end2end.png}
\caption{CLI: salida \texttt{--explain} (fragmento) para el caso end-to-end. La captura se genera a partir del output real de \texttt{src/text2sparql\_cli.py} y muestra (i) normalización, (ii) hits de \emph{grounding}, (iii) la línea \texttt{operator:} y (iv) la descripción del patrón.}
\label{fig:cli_explain_end2end}
\end{figure}

\begin{figure}[ht]
\centering
\includegraphics[width=0.65\linewidth,keepaspectratio]{figures/cli_explain_duplicates.png}
\caption{CLI: salida \texttt{--explain} (fragmento) para la auditoría de duplicados. La captura corresponde a una ejecución real con la intención "audit duplicate links" y muestra la selección del operador y el patrón de agregación con \texttt{GROUP BY/HAVING}.}
\label{fig:cli_explain_duplicates}
\end{figure}

#### 5.1.3 Consultas SPARQL de referencia cubiertas directorio `queries_p510/`
El directorio `queries_p510/` contiene el conjunto de consultas SPARQL "oráculo" del dominio P510-like. Estas consultas se utilizan para (i) validar el dataset (ejecutan correctamente y devuelven resultados plausibles) y (ii) servir como referencia para diseñar y contrastar familias/operadores.

**Tabla 5.AB — Catálogo de queries SPARQL de referencia (`queries_p510/`).**

| Query | Intención (según nombre/comentario) | Rasgo SPARQL dominante |
|---|---|---|
| `q1_req_sin_modelo_fisico.sparql` | Requirements without physical model | `FILTER NOT EXISTS` |
| `q2_modelos_sin_test.sparql` | Physical models without tests | `FILTER NOT EXISTS` |
| `q3_porcentaje_req_con_modelo.sparql` | Percentage of requirements with a model | `COUNT` / agregación |
| `q4_req_sin_traza_end_to_end.sparql` | Requirements missing end-to-end traceability (Req→Model→Test) | `FILTER NOT EXISTS` |
| `q5_reqs_sobre_especificados.sparql` | Requirements with more than one physical model | `GROUP BY` + `HAVING` |
| `q6_cuantos_proveedores.sparql` | How many suppliers | `COUNT` |
| `q7_modelos_por_proveedor.sparql` | Models per supplier | `GROUP BY` + `COUNT` |
| `q8_plm_resumen.sparql` | Manifest PLM summary | `OPTIONAL` / proyección |
| `q9_dev_environment.sparql` | Manifest development environment | `OPTIONAL` |
| `q10_documentos_usados.sparql` | Documents used in the environment | `OPTIONAL` |
| `q11_vnv_escenarios_resumen.sparql` | V&V scenarios summary | `OPTIONAL` |
| `q12_vnv_escenarios_incompletos.sparql` | Scenarios missing Verified_by and Validated_by | `FILTER NOT EXISTS` |
| `q13_links_sin_timestamp.sparql` | Links missing mandatory timestamps | `EXISTS`/`FILTER` (ausencia) |
| `q14_conteo_entidades.sparql` | Global entity count by type | `GROUP BY` + `COUNT` |
| `q15_modelos_sin_proveedor.sparql` | Models without supplier | `FILTER NOT EXISTS` |
| `q16_requisitos_sin_aprobador.sparql` | Requirements without approver | `FILTER NOT EXISTS` |
| `q17_requisitos_por_maturity.sparql` | Requirements by maturity state | `GROUP BY` + `COUNT` |
| `q18_requisitos_por_org_autora.sparql` | Requirements by author organization | `GROUP BY` + `COUNT` |
| `q19_proveedor_top_modelos_sin_test.sparql` | Suppliers with most models without verification | `FILTER NOT EXISTS` + agregación |
| `q20_modelos_por_estado_aprobacion.sparql` | Models by approval state | `GROUP BY` + `COUNT` |
| `q21_tests_por_proveedor_via_modelo.sparql` | Tests per supplier (vía modelos) | `GROUP BY` + `COUNT` |
| `q22_aprobados_sin_aprobador.sparql` | Approved items without approver | `FILTER NOT EXISTS` |
| `q23_link_contenttype_incoherente.sparql` | Links with ContentType inconsistencies | `OPTIONAL` / filtros |
| `q24_links_duplicados.sparql` | Duplicate traces (same src+pred+target repeated) | `GROUP BY` + `HAVING` |
| `q25_links_sin_description.sparql` | Links without Description | `FILTER NOT EXISTS` |
| `q26_baseline_y_proyecto.sparql` | Manifest baseline and project | `OPTIONAL` |
| `q27_requisitos_por_subsistema.sparql` | Requirements by subsystem | `GROUP BY` + `COUNT` |
| `q28_requisitos_por_metodo_verificacion.sparql` | Requirements by verification method | `GROUP BY` + `COUNT` |

### 5.2 Implementación del motor
#### 5.2.1 Normalización y sinónimos
La normalización busca reducir variaciones superficiales del lenguaje sin perder intención. Se aplican transformaciones como: unificación de mayúsculas/minúsculas, normalización de caracteres y sustitución de sinónimos y variantes frecuentes del dominio. El objetivo es que expresiones equivalentes (p. ej. "provider" vs "supplier") lleguen a una representación común para el *grounding*.

En la implementación, este comportamiento se apoya en una función de normalización estable (minúsculas, eliminación conservadora de caracteres no alfanuméricos y tokenización), y en un diccionario opcional de sinónimos/canonizaciones cargable desde un fichero de "prompt" (por defecto `prompts/system_en.txt`). Esta decisión permite mantener el sistema offline y, al mismo tiempo, ajustar vocabulario del dominio sin reentrenar modelos.

En un sistema de reglas, la normalización tiene un papel especialmente importante: pequeñas variaciones ("content type" vs "contenttype", pluralización, guiones) pueden cambiar por completo el routing. Por ello se prioriza un conjunto pequeño de transformaciones estables frente a técnicas probabilísticas.

#### 5.2.2 Indexado del esquema
Antes de generar cualquier consulta, el sistema construye un índice del esquema observado en el grafo: clases (`rdf:type`) y predicados presentes. Este índice cumple dos funciones: (i) facilita el mapeo de texto a términos del esquema, y (ii) permite validar que la consulta generada solo usa términos existentes.

El indexado puede restringirse a determinados prefijos del dominio para evitar introducir vocabularios no deseados. Esto es especialmente útil en grafos que mezclan vocabularios generales y específicos.

En la práctica, el índice se obtiene recorriendo el grafo cargado (TTL) y recolectando: (a) todas las clases que aparecen como objeto de `rdf:type`, y (b) todos los predicados que aparecen en cualquier triple. Además, se extrae el conjunto de prefijos declarados en el grafo para poder emitir cabeceras `PREFIX` coherentes y validar que la consulta no introduce espacios de nombres ajenos.

En el código, este índice se materializa en una estructura tipo `SchemaIndex` con, al menos:

- Conjuntos de IRIs (`classes`, `predicates`).
- Mapeos de "local name" normalizado a IRI (`class_by_local`, `pred_by_local`) para resolver términos como "Requirement" → `p510:Requirement`.
- Un diccionario de prefijos observados en el grafo (`prefixes`), ampliado con prefijos estándar (`rdf`, `rdfs`, `xsd`, `owl`) para poder aceptar vocabularios bien conocidos.

Este paso tiene coste lineal en el tamaño del grafo ($O(|T|)$ triples) y se ejecuta una vez por carga del dataset. En un sistema offline con un TTL acotado, es una estrategia razonable: evita depender de ontologías externas y alinea el motor de generación con el vocabulario realmente presente.

#### 5.2.3 Grounding palabra/frase → concepto
El *grounding* identifica fragmentos del texto que actúan como señales: entidades (p. ej. "Supplier 03"), predicados o atributos (p. ej. "timestamp", "description"), y operadores (p. ej. "missing", "without", "how many", "by"). El resultado se representa como un conjunto de *hits* con información suficiente para explicar la decisión: texto detectado, tipo de hit, candidato del esquema asociado y una puntuación o justificación.

La explicación final se compone de estos hits más el razonamiento del router (por qué se eligió una familia y no otra).

En términos de implementación, el *grounding* produce una lista de hits tipados (por ejemplo, `operator`, `entity`, `attribute`, `literal`) junto con el texto detectado y el concepto del esquema asociado. Esta traza se serializa como líneas de explicación que pueden mostrarse en CLI (`--explain`) o en la demo visual.

El proceso es deliberadamente conservador y está basado en reglas deterministas:

- Primero se normaliza el texto (`lowercase` + sustitución de caracteres no alfanuméricos por espacios + colapso de espacios). Opcionalmente se aplican sustituciones de sinónimos cargadas desde un fichero.
- Se construye un conjunto de tokens "significativos" eliminando *stopwords* y aplicando una singularización barata (p. ej. eliminar `-s` en plurales cuando procede).
- Sobre esa representación se disparan expresiones regulares que detectan:
	- **Operadores**: `COUNT` ("how many / count / number of"), ausencia (`NOT_EXISTS`: "missing/without/lack/absent/no"), duplicados (`DUPLICATE`), auditoría (`AUDIT`), agrupación (`GROUP_BY`: "by/per/grouped by"), etc.
	- **Entidades**: `Requirement`, `DesignModel`, `VerificationTest`, `Traceability_Link_Type`, `Organization`, etc., usando el `SchemaIndex` para que solo se reporten hits cuando la clase existe en el grafo.
	- **Atributos/predicados clave**: `Id`, `ContentType`, `Description`, `Approver`, `Approval_State`, `Maturity_State`, `Timestamp_*`, etc.
	- **Literales frecuentes** del dominio (p. ej. "Physical Model", "Test Case") y literales extraídos de la pregunta (p. ej. "Supplier 03").

Este diseño tiene dos ventajas: (i) las decisiones son explicables y auditables, y (ii) el grounding queda "pegado" al esquema real (si un atributo no existe en el TTL, no puede aparecer como hit), lo cual reduce errores de invención.

#### 5.2.4 Routing y operadores
El motor soporta dos estilos de generación, seleccionables por configuración:

- **Motor dinámico (por defecto).** Construye SPARQL "al vuelo" a partir del índice del esquema y señales lingüísticas. En este modo, el pipeline intenta primero una generación **composicional** conservadora (una estructura base con clase origen, relación y/o clase destino) y, si no encaja, deriva a patrones más especializados para familias de auditoría y agregación.
- **Motor por catálogo.** Selecciona una consulta SPARQL pre-escrita desde un catálogo JSONL (por ejemplo `eval/text2sparql_examples.jsonl`) usando similitud de texto. De forma opcional, cuando la similitud no alcanza un umbral, se usa un clasificador Naive Bayes entrenado offline para predecir el id de la consulta con suficiente confianza.

En el modo catálogo, la similitud no se basa únicamente en "coincidencia de caracteres", sino que combina (a) una razón tipo SequenceMatcher sobre el texto normalizado, y (b) solapamiento de tokens (Jaccard) tras normalización y eliminación de *stopwords*. La puntuación final es un blend lineal de ambas. Si el mejor candidato no supera `match_threshold`, el sistema puede (si hay modelo disponible) usar un clasificador Naive Bayes offline como *fallback*; solo se acepta si la probabilidad supera `classifier_min_prob`. Este esquema evita "sobreajustes" por similitud textual baja y produce errores informativos con sugerencias cuando la pregunta cae fuera de cobertura.

Aunque en el código no se implementa un "registro" explícito de operadores como objetos, el comportamiento equivale a una compilación por familias: la presencia de determinados tokens o hits (p. ej. `missing/without`, `count/how-many`, `by/per`, `duplicate`) dirige la generación hacia patrones que usan construcciones SPARQL estándar como `FILTER NOT EXISTS`, agregación con `GROUP BY`/`COUNT`, o filtros y opcionales [3].

De forma resumida, algunas señales y familias relevantes para el dominio P510-like son:

- **Ausencia / incompletitud (NOT EXISTS).** Disparadores: "missing/without/lack/absent", "no …", "do not have". Compila a patrones con `FILTER NOT EXISTS { ... }` para detectar entidades o enlaces sin relación/metadato.
- **Conteos y distribuciones (GROUP BY).** Disparadores: "how many / count / number of", junto con "by/per/grouped by". Compila a `COUNT(DISTINCT ...)` y agrupación por un atributo (p. ej. proveedor/estado).
- **Duplicados e integridad (HAVING / agrupación).** Disparadores: "duplicate/repeated/same link". Compila a agregaciones con `GROUP BY` y condiciones sobre cardinalidad (p. ej. `HAVING(COUNT(*)>1)`).
- **Listados (SELECT DISTINCT).** Disparadores: "list/show/display/which/what". Compila a `SELECT DISTINCT` con ordenación y, cuando existe, proyección de identificadores.

Este routing está diseñado para ser conservador: cuando la pregunta sugiere una familia "especializada" (p. ej. auditorías de timestamps, incoherencias de content type, trazabilidad end-to-end), el generador composicional se inhibe y delega en patrones más específicos.

Esta decisión mantiene la solución determinista y extensible: para añadir una familia nueva, se añade un patrón especializado y sus precondiciones (señales NL + grounding necesario), y el checker garantiza que no se introduzcan términos fuera del esquema.

##### 5.2.4.1 Catálogo de operadores del motor dinámico extracto
La Tabla 5.AC documenta un subconjunto representativo de operadores implementados en el motor dinámico. Se listan (i) señales mínimas en NL, (ii) precondiciones de esquema (términos `p510:` que deben existir en el TTL), y (iii) el constructo SPARQL dominante. Esta tabla "cierra el círculo" entre requisitos (Cap. 3), diseño por operadores (Cap. 4) e implementación (Cap. 5).

**Tabla 5.AC — Operadores del motor dinámico: señales, precondiciones y patrón SPARQL.**

| Operador (traza `operator:`) | Señales NL (ejemplos) | Precondiciones de esquema | Patrón SPARQL dominante |
|---|---|---|---|
| `LINKS_MISSING_TIMESTAMP` | "links missing timestamps", "without timestamps", "Audit: timestamps" | `p510:Traceability_Link_Type`, `p510:Timestamp_Archiving`, `p510:Timestamp_PLM` | `!EXISTS` en filtro booleano |
| `LINKS_WITHOUT_DESCRIPTION` | "links without description" | `p510:Traceability_Link_Type`, `p510:Description` | `FILTER NOT EXISTS { ?link p510:Description ?d }` |
| `LINK_CONTENTTYPE_MISMATCH` | "contenttype mismatch / inconsistent" | `p510:Traceability_Link_Type`, `p510:ContentType`, `p510:Link` | `OPTIONAL` + `BOUND` + desigualdad |
| `DUPLICATE_TRACES_AUDIT` | "duplicate traces/links", "repeated", "redundant" | Alguno de `p510:Satisfied_by`, `p510:Verified_by`, `p510:Validated_by`, `p510:uses` (+ `p510:Link` si existe) | `VALUES` + `GROUP BY` + `HAVING` |
| `REQUIREMENTS_WITHOUT_PHYSICAL_MODEL` | "requirements without physical model" | `p510:Requirement`, `p510:Id`, `p510:Satisfied_by`, `p510:Link`, `p510:ContentType` | `FILTER NOT EXISTS` con restricción `ContentType="Physical Model"` |
| `REQUIREMENTS_PERCENT_WITH_MODEL` | "percentage/ratio requirements with model" | `p510:Requirement`, `p510:Satisfied_by`, `p510:Link`, `p510:ContentType` | Agregación con `COUNT(DISTINCT ...)` + `OPTIONAL` |
| `COUNT_ENTITIES` | "how many / count" + entidad | Clase objetivo (Requirement/DesignModel/VerificationTest/Traceability_Link_Type/Organization) | `COUNT(DISTINCT ?x)` |

Nótese que las "precondiciones de esquema" no son un detalle cosmético: cuando un término requerido no existe en el grafo, el motor debe fallar con un error explicable. Esto evita que el sistema "simule" una consulta válida usando un predicado inventado y mantiene el cumplimiento de RNF3 (seguridad) y RF3 (grounding) (Cap. 3).

##### 5.2.4.2 Prioridad entre operadores y desambiguación
En un pipeline determinista, cuando varias señales están presentes a la vez (por ejemplo, "audit" + "missing" + "timestamp" + "links"), el sistema necesita una política de prioridad. La implementación resuelve este problema con un orden explícito en el *registry* de operadores: primero se prueban auditorías muy específicas (timestampts/description/contenttype), después integridad estructural (duplicados), y más tarde familias más generales (ausencia de relación, agregación, listados).

Esta elección reduce ambigüedad: una pregunta que contiene "timestamp" no debería acabar en un operador genérico de "missing", porque existe un operador especializado con una plantilla mejor alineada con la intención. En la práctica, esta política se valida con los grupos de paráfrasis del smoke test (Cap. 5.3.3), que fuerzan a que reformulaciones converjan a la misma familia.

#### 5.2.5 Parámetros de configuración y modos de uso
La generación se controla mediante una configuración explícita (`GenerationConfig`) que fija propiedades relevantes para reproducibilidad. En la práctica, esta configuración se expone tanto en el código como en la CLI (véase `src/text2sparql_cli.py`).

De manera análoga a cómo se documentan parámetros de generación en otros enfoques, a continuación se describen los parámetros principales del motor y su efecto sobre comportamiento y evaluación.
- `engine` (`dynamic`/`catalog`, por defecto `dynamic`). Selecciona el modo de generación:
    - `dynamic` compila SPARQL por operadores a partir de grounding y patrones.
    - `catalog` selecciona una consulta desde un catálogo JSONL por similitud (baseline).
    En CLI: `--engine dynamic|catalog`.
- `limit` (por defecto `200`). Asegura que las consultas `SELECT` incluyan un `LIMIT` cuando no está presente, acotando resultados y tiempos de ejecución para que la experiencia sea estable.
    En CLI: `--limit 200`.
- `match_threshold` (por defecto `0.35`). Umbral mínimo de similitud para aceptar un emparejamiento en modo catálogo. Valores más altos aumentan precisión (menos falsos positivos) pero reducen cobertura; valores más bajos aumentan cobertura pero pueden introducir emparejamientos erróneos.
    En CLI: `--threshold 0.35`.
- `max_suggestions` (por defecto `3`). Número máximo de sugerencias que se muestran cuando no se alcanza el umbral de similitud (modo catálogo), para facilitar depuración y análisis de cobertura.
    En CLI: `--suggestions 3`.
- `synonyms_file` (por defecto `None`, con fallback a `prompts/system_en.txt` cuando está presente). Permite cargar un glosario/sinónimos para normalización determinista. Este parámetro se utiliza como "punto de ajuste" para mejorar robustez sin introducir aleatoriedad: cambios en el glosario deben validarse con el *smoke test* de paráfrasis.
    En CLI: `--synonyms-file <ruta>`.
- `classifier_model_file` y `classifier_min_prob` (por defecto `None` y `0.60`). Activan un clasificador offline (Naive Bayes) entrenado con el catálogo para proponer directamente un id de consulta cuando la similitud textual no es suficiente. `classifier_min_prob` controla cuánta confianza se exige para aceptar la predicción.
    En CLI: `--classifier-model <ruta>` y `--classifier-min-prob 0.60`.

Además de la configuración del motor, la CLI ofrece modos de ejecución:
- `--mode translate` genera SPARQL sin ejecutarla.
- `--mode run` genera y ejecuta la SPARQL sobre el TTL (modo por defecto).
- `--explain` imprime la traza de explicación (normalización, hits de grounding y operador/patrón cuando aplica).

Estos parámetros son relevantes para la evaluación: permiten congelar un "perfil" del sistema (motor + umbrales + glosario + límites) y reportar resultados comparables entre iteraciones.

#### 5.2.6 Checker y seguridad
El checker aplica dos validaciones críticas. Primero, una validación de **seguridad** que rechaza cualquier consulta con sintaxis asociada a escritura o actualización (SPARQL Update) y restringe el lenguaje a `SELECT`/`ASK`. Segundo, una validación de **esquema** que comprueba que cada IRI/prefijo utilizado pertenece al conjunto indexado del grafo.

Este mecanismo convierte los fallos en errores explícitos y controlados: si una pregunta no puede resolverse con el esquema disponible, el sistema no debe "inventar" una respuesta, sino informar adecuadamente.

Desde el punto de vista del estándar, esta separación es importante: SPARQL 1.1 define tanto un lenguaje de consulta (lectura) [3] como operaciones de actualización [12]. El sistema de este proyecto restringe su superficie de ataque a consultas `SELECT`/`ASK` y bloquea explícitamente palabras clave asociadas a Update.

A nivel de esquema, el checker implementa una validación por etapas (heurística pero estricta) sobre el texto SPARQL:

1) **Prefijos y espacios de nombres.** Rechaza consultas que declaran `PREFIX` hacia namespaces no observados en el grafo (o no estándar). Para ello construye el conjunto de namespaces permitidos a partir de las clases y predicados reales del dataset, más vocabularios estándar.
2) **Términos abreviados (qnames).** Localiza tokens de la forma `pfx:Local` y comprueba que expanden a una IRI de clase o predicado existente. Si el namespace es "válido" pero el término local no existe, el checker rechaza y sugiere alternativas cercanas (aproximación tipo `get_close_matches`).
3) **IRIs explícitas.** Analiza IRIs `<...>`; si pertenecen a un namespace permitido pero no están en el conjunto de términos observados, se consideran inventadas.
4) **Chequeos estructurales en `WHERE`.** Extrae el cuerpo de la consulta y valida roles: (a) términos tras `a`/`rdf:type` deben ser clases presentes, y (b) términos en posición de predicado deben ser predicados presentes. Esta etapa evita falsos negativos que pasarían solo con un escaneo de tokens.

Este procedimiento no pretende ser un parser completo de SPARQL (lo cual sería más complejo), pero sí es suficiente para el objetivo del proyecto: impedir que el generador dinámico "alucine" atributos y clases fuera del dataset, y convertir ese caso en error explicable.

Además de las comprobaciones de vocabulario, el checker implementa un bloqueo por palabras clave (lista de operaciones prohibidas) y valida que los espacios de nombres declarados en `PREFIX` existan en el grafo o correspondan a vocabularios estándar. En caso de fallo, devuelve un error con términos problemáticos y sugerencias de términos cercanos, lo que ayuda a depurar reglas de *grounding* y plantillas.

### 5.3 Pruebas y evaluación
#### 5.3.1 Estrategia de pruebas
La estrategia de verificación se centra en pruebas **funcionales** reproducibles: para cada pregunta de un conjunto de referencia, el sistema debe generar una SPARQL válida, ejecutarla y devolver resultados. Dado que el sistema es determinista y está anclado a un dataset local, esta verificación puede automatizarse como regresión.

En términos de métricas, el Cap. 2 propone separar la evaluación en capas (Tabla 2.A): (i) **capa ejecutable** (OK/FAIL de ejecución sin error), (ii) capa denotacional (comparación con oráculo), y (iii) estabilidad por intención (paráfrasis). En esta sección se adopta explícitamente esa terminología para que los resultados sean comparables y no dependan de una "demo" puntual.

Un aspecto clave es la robustez a parafraseo: para cada intención, se define un grupo de preguntas equivalentes (paráfrasis) y se exige **estabilidad por intención**, operacionalizada como consistencia del **operador** (línea `operator:`) y de la **cardinalidad** (nº de filas). Esto permite detectar "derivas" introducidas por cambios en reglas de routing o normalización.

En el repositorio, esta idea se materializa en ficheros de salida de *smoke test* (carpeta `eval/`) donde se comparan ejecuciones sobre conjuntos de paráfrasis, y en un script de evaluación automático que recorre ejemplos en JSONL y reporta tasa de éxito y tiempos de ejecución. Los artefactos mínimos que fijan dataset, oráculo, motor y logs están listados en la Tabla 2.C (Cap. 2.6.1).

El script `src/text2sparql_eval.py` implementa dos modos:

- `--mode reference`: ejecuta las consultas SPARQL de referencia y valida que el dataset y las consultas son consistentes.
- `--mode generate`: genera SPARQL desde la pregunta en lenguaje natural con el motor seleccionado (`--engine dynamic|catalog`) y valida que la consulta generada se ejecuta.

Al tratarse de un sistema determinista, estas pruebas sirven también como regresión: cambios en normalización, routing o checker se reflejan de inmediato en la tasa de aciertos.

#### 5.3.2 Dataset de evaluación
El dataset de evaluación se compone de un conjunto de preguntas en lenguaje natural, cubriendo las familias de consulta soportadas. Cada ejemplo se ejecuta sobre el grafo sintético y se registra:

- Operador seleccionado.
- SPARQL generada.
- Número de filas y/o contenido de resultados.
- Explicación (traza) para análisis cualitativo.

En este repositorio, el fichero `eval/text2sparql_examples.jsonl` contiene **N = 34** ejemplos (líneas JSONL no vacías). Cada ejemplo incluye al menos una pregunta (`nl`) y una consulta SPARQL (`sparql`).

Para caracterizar el conjunto sin depender de anotaciones manuales, una aproximación reproducible es agrupar por "rasgos" sintácticos de SPARQL: presencia de `FILTER NOT EXISTS` (auditorías de ausencia), presencia de agregación (`COUNT`, `GROUP BY`) y presencia de `HAVING` (duplicados). Con este criterio, la distribución observada es:

- **OTHER/LIST (sin NOT EXISTS/GROUP BY/HAVING): 12**
- **AGG/COUNT/GROUP BY: 11**
- **MISSING/NOT EXISTS: 8**
- **DUPLICATES/HAVING: 3**

Esta descomposición es útil para reportar cobertura por familia y para detectar rápidamente regresiones: si una modificación rompe, por ejemplo, todos los casos de `NOT EXISTS`, el impacto es visible por categoría.

El catálogo de referencia se define en un fichero JSONL con campos como `id`, `nl` (pregunta) y `sparql` (consulta). Este formato facilita tanto la evaluación de consultas "gold" (modo `reference`) como la evaluación de la generación desde NL (modo `generate`), ya que el mismo conjunto sirve como oráculo de ejecución y como conjunto de intenciones.

**Cómo fijar N y la distribución por familias.** Para completar la memoria, basta con contar el número de líneas (ejemplos) del JSONL y clasificar por tipo de intención/operador (por ejemplo, a partir del prefijo del `id` o de etiquetas manuales). Este análisis puede incluirse en forma de tabla: filas=operador/familia, columnas=#ejemplos, #grupos de paráfrasis y tasa de éxito.

#### 5.3.3 Resultados
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

Conviene interpretar esta cifra como **capa ejecutable (OK/FAIL)**: la consulta se genera (si aplica), pasa el checker y RDFLib la ejecuta sin error. Este es un mínimo necesario para ingeniería, pero no es equivalente a demostrar correctitud denotacional. La equivalencia semántica con una consulta "gold" requiere un criterio adicional (por ejemplo, comparar resultados con la SPARQL de referencia) y una política de comparación (conjunto vs multiconjunto, normalización), tal y como se discute en el Cap. 2.5.

**Capa denotacional (extensión futura).** Si se quisiera reportar correctitud denotacional de forma automática, el protocolo natural consistiría en (i) ejecutar la SPARQL gold y la SPARQL generada sobre el mismo grafo, (ii) extraer la tabla de bindings, y (iii) comparar tras aplicar una política explícita de normalización: ignorar orden salvo `ORDER BY`, decidir si se compara como conjunto o multiconjunto (por defecto, SPARQL produce multiconjuntos), y normalizar literales/IRIs para evitar falsos negativos [3]. Esta capa debe ejecutarse sin truncado o con un `LIMIT` que no recorte el resultado (Cap. 2.5.3).

Para reforzar reproducibilidad, las ejecuciones se respaldan con logs persistentes en `eval/`. En particular, la corrida del catálogo se registra en `eval/catalog_generate_run.txt`, y la estabilidad por paráfrasis se registra en `eval/paraphrase_smoke_out_current_utf8.txt` (ver Tabla 2.C para el mapa completo de artefactos).

**Medición de tiempos.** El script `text2sparql_eval.py` reporta un tiempo por ejemplo (ms) que incluye ejecución de la consulta y, en modo `generate`, el coste adicional de generar/seleccionar la SPARQL antes de ejecutarla. En este entorno, el resumen estadístico por modo es el siguiente:

**Tabla 5.W — Tiempo por ejemplo (ms) en evaluación automática (N=34).**

| Modo | Media | Mediana | P90 | Mín | Máx |
|---|---:|---:|---:|---:|---:|
| `reference` (solo ejecutar SPARQL gold) | 132.26 | 19.65 | 95.05 | 7.7 | 3334.4 |
| `generate` + `dynamic` | 300.58 | 47.50 | 1387.70 | 21.6 | 3104.4 |
| `generate` + `catalog` | 168.37 | 55.45 | 150.60 | 32.0 | 3360.8 |

Se observa que la **media** puede estar fuertemente influida por un número pequeño de ejemplos "lentos" (máximos del orden de segundos), por lo que la **mediana** y percentiles (P90) son más representativos para describir la experiencia típica. Este tipo de precaución al reportar métricas ayuda a que la evaluación sea más interpretable y comparable [7].

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

Además de evaluar ejemplos "unitarios", se incluye un *smoke test* de paráfrasis (`eval/paraphrase_smoke.py`) que ejecuta **74 preguntas** organizadas en **26 grupos** (cada grupo representa una intención). Para cada pregunta se registra:

- **Operador** detectado a partir de la traza (`operator:` en la explicación, cuando existe).
- **Número de filas** devueltas al ejecutar la SPARQL.

Se define el criterio de consistencia por grupo como:

- El conjunto de operadores observados en el grupo tiene tamaño 1.
- El conjunto de recuentos de filas observados en el grupo tiene tamaño 1.

En la ejecución registrada en `eval/paraphrase_smoke_out_current_utf8.txt` se obtuvo **74/74 OK** y **26/26 grupos consistentes (100.0\%)** bajo el criterio anterior. Esta métrica complementa la tasa de ejecución y es útil para vigilar estabilidad del routing frente a reformulaciones, en línea con buenas prácticas de evaluación reproducible [7].

| Grupo | #Paráfrasis | Operador(es) observado(s) | Filas observadas | ¿Consistente? |
|---|---:|---|---:|---|
| A.count.links | 1 | (none) | 1 | Sí |
| A.count.requirements | 1 | (none) | 1 | Sí |
| A.count.suppliers | 3 | (none) | 1 | Sí |
| B.missing.end\_to\_end | 3 | REQUIREMENTS\_MISSING\_END\_TO\_END | 7 | Sí |
| B.missing.models\_without\_tests | 3 | (none) | 30 | Sí |
| B.missing.req\_without\_physical\_model | 3 | (none) | 8 | Sí |
| C.percent.req\_with\_model | 3 | (none) | 42 | Sí |
| D.audit.contenttype\_mismatch | 3 | LINK\_CONTENTTYPE\_MISMATCH | 4 | Sí |
| D.audit.duplicates | 3 | DUPLICATE\_TRACES\_AUDIT | 29 | Sí |
| D.audit.links\_missing\_timestamps | 3 | LINKS\_MISSING\_TIMESTAMP | 3 | Sí |
| D.audit.links\_without\_description | 3 | LINKS\_WITHOUT\_DESCRIPTION | 2 | Sí |
| E.audit.approved\_without\_approver | 3 | APPROVED\_WITHOUT\_APPROVER | 2 | Sí |
| E.audit.req\_without\_approver | 3 | REQUIREMENTS\_WITHOUT\_APPROVER | 4 | Sí |
| F.groupby.models\_by\_approval | 3 | MODELS\_BY\_APPROVAL\_STATE | 2 | Sí |
| F.groupby.req\_by\_author\_org | 3 | REQUIREMENTS\_BY\_AUTHOR\_ORG | 7 | Sí |
| F.groupby.req\_by\_maturity | 3 | REQUIREMENTS\_BY\_MATURITY | 4 | Sí |
| F.groupby.req\_by\_subsystem | 3 | REQUIREMENTS\_BY\_SUBSYSTEM | 6 | Sí |
| F.groupby.req\_by\_verification\_method | 3 | REQUIREMENTS\_BY\_VERIFICATION\_METHOD | 4 | Sí |
| G.manifest.baseline | 3 | MANIFEST\_PROJECT\_BASELINE | 1 | Sí |
| G.manifest.dev\_environment | 3 | DEV\_ENVIRONMENT | 1 | Sí |
| G.manifest.plm\_summary | 3 | PLM\_SUMMARY | 1 | Sí |
| G.manifest.used\_documents | 3 | USED\_DOCUMENTS | 5 | Sí |
| H.vnv.incomplete | 3 | VNV\_SCENARIOS\_INCOMPLETE | 3 | Sí |
| H.vnv.summary | 3 | VNV\_SCENARIOS\_SUMMARY | 10 | Sí |
| I.supplier.models\_by\_supplier | 3 | MODELS\_BY\_SUPPLIER | 6 | Sí |
| I.supplier.models\_for\_supplier | 3 | MODELS\_FOR\_SUPPLIER | 8 | Sí |

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
2) Un caso de duplicados con `GROUP BY`+`HAVING`, mostrando la interpretación de "duplicado" en el contexto de link nodes.
3) Un caso de fallo controlado (pregunta fuera de cobertura) para evidenciar que el sistema no "alucina" vocabulario.

Esta forma de presentar resultados favorece la replicación: el lector puede volver a ejecutar el ejemplo en local y comparar SPARQL y resultados, alineándose con buenas prácticas de evaluación [7].

##### Casos de estudio cualitativo basados en paráfrasis
En esta sección se incluyen tres casos de estudio construidos a partir del *smoke test* de paráfrasis. El objetivo no es solo "que ejecute", sino mostrar cómo distintas reformulaciones convergen a la misma intención y, por tanto, al mismo patrón SPARQL y a resultados coherentes.

Los textos de las preguntas se toman literalmente de [eval/paraphrase_smoke.py](eval/paraphrase_smoke.py), y la consistencia (operador y recuento de filas) se comprueba con la ejecución registrada en [eval/paraphrase_smoke_out_current_utf8.txt](eval/paraphrase_smoke_out_current_utf8.txt).

**Caso 1 — Auditoría: links without timestamps (ausencia de metadatos).**

- **Grupo:** `D.audit.links_missing_timestamps`
- **Paráfrasis evaluadas:**
	- "Audit: links missing mandatory timestamps (Timestamp_Archiving or Timestamp_PLM)."
	- "Find traceability links without timestamps."
	- "Show links where Timestamp_Archiving or Timestamp_PLM is missing."
- **Resultado observado:** operador único `LINKS_MISSING_TIMESTAMP` y **3 filas** en las tres reformulaciones.

**Interpretación técnica.** Este caso representa una auditoría típica sobre nodos de enlace: se buscan relaciones cuyo nodo intermedio no contiene un metadato obligatorio. En SPARQL 1.1, la ausencia de un patrón puede expresarse mediante construcciones como `FILTER NOT EXISTS { ... }`, que permiten seleccionar enlaces para los que no existe evidencia de los atributos requeridos [3].

En términos de routing, las tres paráfrasis comparten señales robustas ("audit", "missing", "without", y menciones explícitas de "timestamps"), de modo que el sistema converge al mismo operador especializado. Esto es importante en escenarios de auditoría: si reformular la pregunta cambiase la intención seleccionada, la consulta podría volverse engañosa. La consistencia observada respalda el objetivo de reproducibilidad y estabilidad frente a reformulaciones, alineándose con recomendaciones generales sobre evaluación trazable [7].

**Caso 2 — Distribución: requisitos por estado de madurez (agregación y agrupación).**

- **Grupo:** `F.groupby.req_by_maturity`
- **Paráfrasis evaluadas:**
	- "Distribution of requirements by maturity state."
	- "Group requirements by Maturity_State."
	- "Count requirements per maturity state."
- **Resultado observado:** operador único `REQUIREMENTS_BY_MATURITY` y **4 filas** en las tres reformulaciones.

**Interpretación técnica.** Este caso corresponde a una familia de consultas de resumen: agrupar por una categoría (`Maturity_State`) y contar cuántos elementos caen en cada grupo. SPARQL 1.1 soporta agregación y agrupación (`COUNT`, `GROUP BY`), por lo que el patrón natural de compilación es una proyección con agregados y una cláusula de agrupación [3].

En NL, las señales "distribution", "group by" y "count per" son equivalentes en intención, y el *smoke test* verifica que no hay deriva: la selección del operador y la cardinalidad del resultado se mantienen constantes (4 filas, una por estado presente en el grafo). De cara a la evaluación, esto aporta una evidencia adicional sobre estabilidad del sistema más allá del conjunto "unitario" del catálogo, y facilita justificar de forma reproducible que el routing está controlado [7].

**Caso 3 — Integridad: trazas duplicadas (detección de redundancia).**

- **Grupo:** `D.audit.duplicates`
- **Paráfrasis evaluadas:**
	- "Audit: duplicate traces (same source + predicate + target repeated)."
	- "Find duplicate links / repeated traceability relationships."
	- "Detect redundant traceability links (same src, same relation, same target)."
- **Resultado observado:** operador único `DUPLICATE_TRACES_AUDIT` y **29 filas** en las tres reformulaciones.

**Interpretación técnica.** El concepto de "duplicado" se formaliza como la existencia de múltiples instancias de la misma relación lógica (misma fuente, misma relación y mismo destino). En SPARQL 1.1, una forma estándar de capturar este patrón es agrupar por las claves de la relación y filtrar grupos con cardinalidad mayor que 1 mediante agregación (`COUNT`) y restricción sobre agregados con `HAVING` [3]. En grafos con *link nodes*, esto puede implementarse agrupando por los extremos (src/dst) y el tipo de relación, independientemente del identificador del nodo de enlace, de manera que la auditoría detecte redundancia semántica aunque existan varias instancias físicas del enlace.

Desde el punto de vista NL→SPARQL, este caso es útil porque los enunciados pueden variar ("duplicate", "repeated", "redundant") sin que cambie la intención. El hecho de que el routing converja al mismo operador y a la misma cardinalidad observada en el dataset sintético (29 filas) aporta evidencia de robustez frente a sinónimos y reformulaciones en auditorías de integridad, y además queda anclado a un log reproducible de ejecución [7].

**Resumen comparativo.** Los tres casos cubren tres patrones típicos del estándar SPARQL: (i) ausencia de evidencia (`FILTER NOT EXISTS`) para auditorías de metadatos, (ii) agregación y agrupación (`COUNT` + `GROUP BY`) para distribuciones, y (iii) detección de redundancia mediante `GROUP BY` + `HAVING` para duplicados [3]. En conjunto, complementan la métrica cuantitativa de consistencia por paráfrasis: no solo se reporta que "es consistente", sino que se muestra por qué, y se deja una traza ejecutable y repetible que el lector puede verificar en local (dataset + scripts + log) [7].

Para facilitar la lectura, la Tabla 5.AA resume el patrón SPARQL esperado, el operador observado y la cardinalidad resultante (sobre el dataset sintético actual), con evidencia reproducible.

**Tabla 5.AA — Resumen de casos de estudio (paráfrasis).**

| Caso | Grupo | Patrón SPARQL típico (SPARQL 1.1) | Operador observado | Filas observadas | Evidencia |
|---|---|---|---|---:|---|
| Auditoría: links without timestamps | `D.audit.links_missing_timestamps` | Ausencia de metadato (p. ej. `FILTER NOT EXISTS`) | `LINKS_MISSING_TIMESTAMP` | 3 | [eval/paraphrase_smoke_out_current_utf8.txt](eval/paraphrase_smoke_out_current_utf8.txt) |
| Distribución: requisitos por madurez | `F.groupby.req_by_maturity` | Agregación (`COUNT`) + agrupación (`GROUP BY`) | `REQUIREMENTS_BY_MATURITY` | 4 | [eval/paraphrase_smoke_out_current_utf8.txt](eval/paraphrase_smoke_out_current_utf8.txt) |
| Integridad: trazas duplicadas | `D.audit.duplicates` | Redundancia (`GROUP BY` + `HAVING` sobre `COUNT`) | `DUPLICATE_TRACES_AUDIT` | 29 | [eval/paraphrase_smoke_out_current_utf8.txt](eval/paraphrase_smoke_out_current_utf8.txt) |

#### 5.3.5 Modos de fallo y comportamiento esperado
En sistemas deterministas basados en reglas, el fallo "correcto" es tan importante como el acierto. En este proyecto se prioriza el fallo controlado por encima de devolver una consulta plausible pero incorrecta. En particular:

- Si la intención no está soportada, el sistema debe informar de forma explícita.
- Si el grounding no puede anclarse al esquema, debe evitarse la generación ad hoc.
- Si el checker detecta términos fuera de esquema, se debe rechazar la consulta (evitando invención).

Este principio está alineado con el objetivo de auditoría y con la motivación de reproducibilidad: una consulta incorrecta pero "bien formada" puede ser más peligrosa que un error visible, especialmente si se utiliza en procesos de verificación/validación.

#### 5.3.6 Amenazas a la validez interna/externa
Para que la evaluación sea académicamente sólida conviene explicitar amenazas típicas:

- **Validez interna (oráculo).** Si las consultas de referencia están mal definidas, la evaluación puede marcar como fallo un comportamiento correcto (o viceversa). La mitigación es validar primero el catálogo en modo `reference` y revisar manualmente ejemplos críticos.
- **Validez externa (dataset sintético).** El grafo sintético no captura toda la variabilidad del mundo real. La mitigación es describir claramente las asunciones de generación, y (si es posible) repetir con un subconjunto real anonimizando datos, manteniendo el diseño offline.
- **Validez de constructo (métrica).** "Ejecuta sin error" no implica "responde a la intención". Por ello se recomienda reportar, además de ejecución, consistencia por paráfrasis y comparaciones frente a consultas de referencia.

Estas notas conectan con la preocupación de replicación en KGQA y con la necesidad de protocolos transparentes [7].

#### 5.3.7 Guía de reproducción para el lector
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

## 6. Interfaz de usuario
Este capítulo describe las dos formas de interacción con el sistema: (i) una interfaz de línea de comandos (CLI) orientada a ejecución reproducible y (ii) una demo visual orientada a inspección (SPARQL, resultados y explicación).

### 6.1 Enfoque de diseño
La interfaz está planteada para un escenario de auditoría técnica, donde el usuario necesita ver claramente tres objetos distintos: la pregunta (entrada), la consulta SPARQL (programa) y el resultado (bindings). Por ello, tanto en CLI como en la demo visual se prioriza:

- Transparencia: la SPARQL generada siempre es visible.
- Trazabilidad: existe una opción de explicación (`--explain`) que muestra el operador y señales de grounding.
- Reproducibilidad: la CLI permite ejecutar los mismos ejemplos de forma repetida y registrar logs.

### 6.2 Interfaz CLI
La CLI se utiliza como interfaz de referencia porque facilita automatización y captura de evidencias. Permite seleccionar el motor (catálogo u operador dinámico), ejecutar en modo generación o referencia, y activar la explicación. En el Cap. 5 se muestran ejemplos reales de salida con `--explain`.

### 6.3 Demo visual
La demo visual proporciona una vista estructurada de la ejecución: entrada, SPARQL, tabla de resultados y un panel de explicación (operator + grounding). Se usa en la memoria para incluir capturas de pantalla de la interfaz y de la explicación asociada, reforzando la verificabilidad del sistema.

### 6.4 Evidencias visuales incluidas
Las capturas de la interfaz (incluyendo el bloque de explicación) se incorporan en el capítulo de implementación/evaluación para documentar el comportamiento observado.

---

## 7. Infraestructura y servicios cloud
En el diseño de este proyecto, la "infraestructura" se plantea deliberadamente mínima: el sistema se ejecuta offline sobre un grafo local, evitando dependencias de cloud. Aun así, resulta útil documentar entorno, estructura del proyecto y puesta en marcha como parte de la reproducibilidad.

### 7.1 Entorno de ejecución
El sistema se ejecuta en Python sobre Windows, utilizando un entorno virtual y dependencias declaradas en `requirements.txt`. La carga y consulta del grafo se realiza con RDFLib [10]. La demo visual se apoya en Streamlit [11].

### 7.2 Estructura del proyecto
El repositorio se organiza en torno a tres tipos de artefactos:

- Datos y oráculos: `data/` (TTL) y `queries_p510/` (SPARQL de referencia).
- Motor y herramientas: `src/` (traductor, CLI, evaluación, demos).
- Evidencias: `eval/` (logs de corrida y salidas persistentes).

### 7.3 Ejecución y puesta en marcha
El Anexo C describe un protocolo paso a paso para recrear resultados: creación de entorno, generación del TTL, ejecución del oráculo de queries, uso de CLI con `--explain`, y evaluación automática.

### 7.4 Consideraciones de seguridad
Aunque el sistema está orientado a `SELECT`, se incorpora un checker que bloquea explícitamente SPARQL Update [12] y valida vocabulario permitido. Además, se aplica un límite de resultados para evitar salidas excesivas y reducir el riesgo de consultas accidentales costosas.

---

## 8. Marco regulador
Este capítulo resume consideraciones de cumplimiento y uso responsable relevantes cuando un sistema de consulta podría aplicarse sobre grafos reales (potencialmente sensibles). Aunque el dataset del proyecto es sintético, se incluyen estas consideraciones por transferibilidad.

### 8.1 Protección de datos personales y derechos digitales
En este proyecto, el dataset (`data/p510_sintetico.ttl`) es sintético y no contiene datos personales reales. Por tanto, el RGPD no aplica directamente al contenido del grafo en el entorno experimental. No obstante, si el sistema se aplicase a grafos reales con datos personales, sería necesario analizar obligaciones de tratamiento y medidas de minimización y seguridad conforme a la normativa vigente [15].

### 8.2 Ética y uso responsable de IA
Este proyecto se enmarca en la construcción de una herramienta de apoyo para consulta/auditoría sobre grafos RDF: transforma preguntas en lenguaje natural en consultas SPARQL que se ejecutan localmente sobre un dataset. Aunque no utiliza un modelo generativo, se considera pertinente discutir su uso responsable (y, en escenarios de transferencia, su posible encaje regulatorio) porque el sistema automatiza parte de un proceso de análisis.

#### 8.2.1 Categorías de riesgo visión general
En términos generales, los marcos regulatorios europeos sobre IA distinguen categorías de riesgo con obligaciones proporcionales. A nivel conceptual, puede resumirse en:
- **Sistemas prohibidos:** prácticas consideradas inaceptables (por ejemplo, manipulación o explotación de vulnerabilidades, entre otras).
- **Sistemas de alto riesgo:** sistemas utilizados en áreas críticas (por ejemplo, educación, empleo, aplicación de la ley o infraestructuras críticas) y sujetos a requisitos reforzados.
- **Otros sistemas (riesgo limitado o mínimo):** sistemas que no entran en las categorías anteriores y que suelen estar sujetos a obligaciones más ligeras, principalmente relacionadas con transparencia y uso informado.

#### 8.2.2 Encaje del proyecto y obligaciones de transparencia
Dentro de esta categorización, la herramienta desarrollada podría considerarse, en condiciones típicas de uso, un sistema de **riesgo mínimo o limitado**, ya que:
- No realiza identificación biométrica, clasificación de personas ni toma decisiones automatizadas sobre individuos.
- Opera offline sobre un grafo local (en el proyecto, sintético) y devuelve resultados verificables por ejecución.
- Su salida es una consulta SPARQL y un conjunto de resultados; no sustituye el juicio experto sobre la interpretación del resultado.

En consecuencia, las buenas prácticas más relevantes se alinean con la **transparencia** y con evitar un uso engañoso:
- **Notificación al usuario:** informar de que se interactúa con un sistema automático que genera/ejecuta consultas.
- **Uso informado:** clarificar alcance y limitaciones (familias soportadas, dependencia del esquema disponible, posibilidad de "fuera de cobertura").
- **Auditoría:** conservar trazas mínimas (por ejemplo, `--explain`) cuando se utilice en contextos reales, para poder revisar por qué se generó una consulta concreta.

#### 8.2.3 Buenas prácticas aplicadas en este proyecto
Las decisiones técnicas adoptadas durante el desarrollo no se han tomado de manera aislada, sino guiadas por objetivos de reproducibilidad, explicabilidad y control de riesgos. En concreto, se han aplicado las siguientes buenas prácticas.

**Protección de datos personales y derechos digitales**
- **Minimización por diseño:** el dataset del proyecto es sintético y el sistema funciona offline; no requiere enviar datos a terceros. En un despliegue sobre grafos reales, se recomienda mantener el mismo principio: cargar y consultar en local o en infraestructura controlada, y evitar registrar en logs contenido sensible.
- **Conservación responsable de trazas:** en el prototipo se guardan evidencias de ejecución para evaluación (carpeta `eval/`). Si se extendiese a producción, la conservación de historiales debería ser proporcional, con políticas claras de retención y control de acceso.

**Ética y uso responsable de automatización**
- **Generación controlada (determinista):** el motor compila consultas por operadores/patrones y se apoya en *grounding* al esquema observado. Esto limita la aparición de comportamientos no reproducibles y favorece el análisis posterior.
- **Gates de seguridad y anti-invención:** antes de ejecutar, el checker bloquea explícitamente SPARQL Update y valida que los términos pertenecen al vocabulario del grafo. Esta práctica reduce el riesgo de producir consultas "plausibles" pero inválidas o peligrosas.
- **Revisión humana (humano en el bucle):** el sistema no pretende sustituir la revisión experta. La salida se presenta como apoyo (consulta + explicación + resultados) para que una persona pueda validar intención, patrón aplicado y coherencia del resultado.
- **Limitación explícita del alcance:** cuando una pregunta cae fuera de cobertura o no puede anclarse al esquema, el comportamiento esperado es fallar con un error explicable y sugerencias, en lugar de "aproximar" una respuesta.

#### 8.2.4 Declaración académica
La declaración académica de uso de IA generativa exigida por UC3M se incluye en el Anexo B.

### 8.3 Licencias software
La solución se implementa sobre herramientas y librerías de código abierto, cuyas licencias deben respetarse (uso, modificación y redistribución). Para sustentar esta sección, puede citarse la definición de open source de la Open Source Initiative [13] y el listado oficial de licencias SPDX [14].

En este proyecto, las dependencias declaradas en `requirements.txt` incluyen, entre otras:
- **RDFLib** (librería de grafos RDF y motor SPARQL): licencia **BSD 3-Clause** (según la información pública del repositorio del proyecto).
- **Streamlit** (demo visual): licencia **Apache 2.0**.
- **pandas** (utilidades de evaluación/análisis): licencia **BSD 3-Clause**.

Respecto al código desarrollado en el proyecto, si se decidiera su publicación, licencias permisivas como **MIT** o **Apache 2.0** son opciones habituales. En particular:
- MIT es sencilla y muy extendida.
- Apache 2.0 añade cláusulas explícitas sobre patentes, útiles en contextos más formales.

La elección final debería reflejar el objetivo del repositorio (docencia, reutilización o transferencia) y ser coherente con el inventario de dependencias.

---

## 9. Entorno socioeconómico
### 9.1 Impacto socioeconómico
La solución propuesta reduce el coste de formular consultas sobre grafos RDF al permitir que perfiles no expertos en SPARQL expresen preguntas de auditoría y trazabilidad en lenguaje natural. En términos de productividad, el impacto esperado es una disminución del tiempo dedicado a redactar consultas y depurar errores sintácticos o de esquema.

En términos de calidad, el enfoque determinista y el checker anti-invención contribuyen a que las consultas sean consistentes y trazables: se evita la generación de vocabulario inexistente y se ofrece una explicación que apoya procesos de auditoría.

Desde una perspectiva de adopción, la herramienta encaja especialmente bien como soporte a:
- Equipos de ingeniería de sistemas y V&V que necesitan auditorías recurrentes de trazabilidad.
- Integradores o responsables de calidad que trabajan con grafos RDF (o exportaciones equivalentes) y requieren consultas repetibles.
- Contextos formativos donde se quiere introducir SPARQL de forma progresiva (del NL al patrón SPARQL).

No obstante, el impacto está condicionado por el alcance del sistema: al tratarse de un conjunto acotado de familias, la cobertura fuera del dominio no está garantizada.

**Impacto ambiental (orientativo).** En comparación con enfoques que dependen de inferencia en GPU o de servicios cloud, este proyecto tiene un perfil de consumo reducido: la ejecución es local, sin necesidad de entrenamiento ni despliegue en la nube. Aun así, en escenarios reales conviene considerar el coste energético asociado a la ejecución repetida y a la infraestructura de almacenamiento del grafo.

### 9.2 Planificación
La planificación se organiza por fases técnicas, de forma coherente con el desarrollo guiado por oráculo (queries de referencia) y con la evaluación reproducible.

| Fase | Actividades principales | Entregable verificable |
|---|---|---|
| F1 | Definición de dominio y oráculos SPARQL | Conjunto de queries en `queries_p510/` ejecutables sobre el TTL |
| F2 | Generación del dataset sintético y análisis del vocabulario | `data/p510_sintetico.ttl` + estadísticas/reporting del grafo |
| F3 | Implementación del motor NL→SPARQL (operadores) + checker | Motor dinámico + validación anti-update/anti-invención |
| F4 | Interfaz y explicabilidad | CLI + demo visual + trazas `--explain` |
| F5 | Evaluación y regresión | Scripts de evaluación + logs en `eval/` |
| F6 | Redacción final y anexos | Memoria + anexos (reproducibilidad + declaración IA) |

Además, para reportar una planificación temporal al estilo de memorias de ingeniería, puede añadirse una estimación de fechas y esfuerzo. Cuando no se dispone de un registro exacto de horas, es habitual reportar una **estimación razonable** basada en el tipo de tareas realizadas.

Para un proyecto como este (dataset sintético, motor determinista por operadores, checker, CLI + demo, y evaluación reproducible), una dedicación típica suele caer en el rango **320–420 horas**. En la Tabla 9.1 se muestra una instancia concreta de ese rango (≈380 h) para fijar órdenes de magnitud.

| Fase | Inicio | Fin | Duración (días) | Duración (h) |
|---|---:|---:|---:|---:|
| F1 | 10/02/2026 | 16/02/2026 | 7 | 30 |
| F2 | 17/02/2026 | 24/02/2026 | 8 | 35 |
| F3 | 25/02/2026 | 31/03/2026 | 35 | 160 |
| F4 | 01/04/2026 | 14/04/2026 | 14 | 55 |
| F5 | 15/04/2026 | 25/04/2026 | 11 | 45 |
| F6 | 26/04/2026 | 05/05/2026 | 10 | 55 |

Esta planificación es compatible con solapamientos (por ejemplo, evaluación en paralelo a redacción una vez estabilizado el motor). Si se desea reflejarlo, el diagrama de Gantt puede representar F5 y F6 parcialmente en paralelo, manteniendo el mismo total aproximado de horas.

Con estos valores puede construirse un diagrama de Gantt para visualizar solapamientos (por ejemplo, evaluación y redacción pueden ejecutarse en paralelo una vez estabilizado el motor).

### 9.3 Presupuesto
El presupuesto se presenta como una estimación orientativa basada en recursos utilizados. Dado que el proyecto se ejecuta offline con herramientas open source, el coste directo en licencias es nulo o muy bajo; el principal coste estimable es el tiempo de dedicación.

| Concepto | Coste estimado (EUR) | Notas |
|---|---:|---|
| Hardware | 0 | Equipo personal del estudiante (sin amortización imputada) |
| Software | 0 | Dependencias open source (RDFLib, Streamlit, etc.) |
| Servicios cloud | 0 | No se requiere cloud para la ejecución del proyecto |
| Tiempo de desarrollo | ≈380 (rango 320–420) | Estimación en función de horas y tarifa asumida |

Si se desea cuantificar el coste del tiempo, una aproximación es: coste = horas × tarifa. Esta cifra depende del criterio del tribunal (por ejemplo, tarifa de prácticas o tarifa estándar).

Como ejemplo meramente orientativo (no normativo): si se asume una tarifa de 12–15 EUR/h y una dedicación de 320–420 h, el coste imputable al tiempo estaría en el rango aproximado **3.840–6.300 EUR**.

Si se requiere mayor detalle (p. ej. para justificar viabilidad en un entorno real), puede desglosarse el tiempo por roles, manteniendo las tarifas como variables:

| Rol | % (opcional) | Horas | Tarifa (EUR/h) | Coste (EUR) |
|---|---:|---:|---:|---:|
| Dirección/gestión técnica | 10% | 38 | (a estimar) | (auto) |
| Desarrollo software | 65% | 247 | (a estimar) | (auto) |
| Analista de datos/QA | 25% | 95 | (a estimar) | (auto) |
| Total | 100% | 380 | - | (suma) |

En todos los casos, el objetivo de esta sección es dimensionar el esfuerzo, no presentar un coste "de mercado" preciso.

---

## 10. Conclusiones y trabajos futuros
### 10.1 Conclusiones
En este trabajo se ha definido e implementado un sistema determinista de traducción de lenguaje natural a SPARQL para un dominio P510-like. El diseño por familias (operadores/patrones) y el *grounding* al esquema permiten controlar la generación, evitando la invención de predicados/clases y aportando reproducibilidad. La incorporación de una traza explicativa facilita la inspección del comportamiento y mejora la confianza en los resultados.

Para cerrar el trabajo, es importante vincular explícitamente el resultado con los objetivos O1–O7 (Cap. 1):

- **O1 — Traducción texto→SPARQL:** el motor genera consultas `SELECT` para varias familias típicas (listados, conteos, ausencias y auditorías). La evidencia se presenta en los ejemplos del catálogo y en la ejecución sobre el TTL.
- **O2 — Offline y determinista:** toda la ejecución se realiza en local (sin dependencias remotas). La misma entrada produce la misma SPARQL y el mismo resultado si el dataset no cambia.
- **O3 — Grounding al esquema:** las decisiones se basan en un índice de clases/predicados observados y se restringen a vocabularios existentes.
- **O4 — Checker anti-invención y seguridad:** se bloquean operaciones de Update y se validan prefijos/términos; los fallos se reportan como errores controlados.
- **O5 — Explicabilidad:** se devuelve una traza con normalización, hits de grounding y señales que justifican la ruta elegida.
- **O6 — Validación y pruebas:** se incluye evaluación automática como regresión, además de *smoke tests* con paráfrasis.
- **O7 — Interfaz de demostración:** el sistema se utiliza desde CLI y desde una demo visual, mostrando SPARQL, resultados y explicación.

**Cierre con resultados medidos (ejecución y estabilidad).** La evidencia cuantitativa del repositorio respalda que el sistema es ejecutable y estable dentro del alcance definido:

- En la evaluación automática del catálogo (`eval/text2sparql_examples.jsonl`, **N=34**), se obtiene una tasa de ejecución sin errores del **100.0% (34/34)** tanto en modo `reference` (ejecutar SPARQL "gold") como en modo `generate` (generar desde NL) con `engine=dynamic` y con `engine=catalog`.
- En el *smoke test* de paráfrasis (74 preguntas en 26 grupos), la ejecución registrada produce **74/74 OK** y **26/26 grupos consistentes (100.0%)** bajo el criterio de consistencia por operador y recuento de filas (Cap. 5.3.3).

Además, los tiempos por ejemplo (ms) muestran que el coste típico (mediana) es del orden de decenas de milisegundos, aunque existen casos más costosos (máximos del orden de segundos), lo que justifica reportar mediana y percentiles además de la media (Cap. 5.3.3).

Estas cifras deben interpretarse con cautela: validan que el pipeline produce consultas ejecutables y que el checker no bloquea indebidamente el conjunto evaluado, pero no sustituyen a una validación de equivalencia semántica completa para todas las intenciones. En un trabajo futuro, esta validez semántica puede reforzarse comparando resultados contra un oráculo "gold" (por ejemplo, las SPARQL de referencia) y ampliando el conjunto de paráfrasis por intención.

### 10.2 Trabajos futuros
- Ampliar cobertura de operadores/familias.
- Mejoras de evaluación (más paráfrasis, datasets reales si es posible).
- Mejoras de explicabilidad (visualización, exportación).

Como trabajos futuros se proponen: ampliar el catálogo de operadores para cubrir nuevas familias, incorporar datasets reales (si hay acceso y permisos) y formalizar aún más la evaluación (por ejemplo, métricas de equivalencia semántica entre consultas o validaciones sobre resultados esperados). En el ámbito de la explicabilidad, se podrían añadir visualizaciones que destaquen el grounding por token y la correspondencia entre la pregunta y los patrones SPARQL generados.

De forma más concreta, algunas líneas de extensión razonables son:

- **Cobertura léxica.** Ampliar el glosario de sinónimos y normalización manteniendo determinismo y trazabilidad (sin incrementar el espacio de consultas más allá de los operadores soportados).
- **Enriquecimiento del esquema.** Extraer estadísticas del grafo (frecuencias de predicados, tipos más comunes) para mejorar sugerencias y desambiguación, manteniendo el checker como barrera de seguridad.
- **Métricas más informativas.** Además de "ejecuta/no ejecuta", incluir métricas de equivalencia de resultados entre paráfrasis y análisis de estabilidad del routing.
- **Operadores composicionales más ricos.** Introducir combinaciones controladas (por ejemplo, ausencia + agrupación) cuando el dominio lo requiera, manteniendo plantillas verificables.

---

## 11. Bibliografía
Las referencias se listan en estilo IEEE, numeradas por orden de aparición.

[1] W3C, "RDF 1.1 Primer," W3C Recommendation, 2014. [Online]. Available: https://www.w3.org/TR/rdf11-primer/. [Accessed: Apr. 22, 2026].

[2] W3C, "SPARQL 1.1 Overview," W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-overview/. [Accessed: Apr. 22, 2026].

[3] W3C, "SPARQL 1.1 Query Language," W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-query/. [Accessed: Apr. 22, 2026].

[4] L. Zettlemoyer and M. Collins, "Learning to Map Sentences to Logical Form: Structured Classification with Probabilistic CCGs," in Proc. Uncertainty in Artificial Intelligence (UAI), 2005.

[5] J. Berant, A. Chou, R. Frostig, and P. Liang, "Semantic Parsing on Freebase from Question-Answer Pairs," in Proc. Conference on Empirical Methods in Natural Language Processing (EMNLP), 2013.

[6] T. Yu et al., "Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task," arXiv:1809.08887, 2018. doi: 10.48550/arXiv.1809.08887.

[7] A. Perevalov, X. Yan, L. Kovriguina, L. Jiang, A. Both, and R. Usbeck, "Knowledge Graph Question Answering Leaderboard: A Community Resource to Prevent a Replication Crisis," arXiv:2201.08174, 2022. doi: 10.48550/arXiv.2201.08174.

[8] D. Brickley and L. Miller, "FOAF Vocabulary Specification," n.d. [Online]. Available: http://xmlns.com/foaf/spec/. [Accessed: Apr. 22, 2026].

[9] Dublin Core Metadata Initiative, "DCMI Metadata Terms," n.d. [Online]. Available: https://www.dublincore.org/specifications/dublin-core/dcmi-terms/. [Accessed: Apr. 22, 2026].

[10] RDFLib contributors, "RDFLib Documentation," n.d. [Online]. Available: https://rdflib.readthedocs.io/. [Accessed: Apr. 22, 2026].

[11] Streamlit Inc., "Streamlit Documentation," n.d. [Online]. Available: https://docs.streamlit.io/. [Accessed: Apr. 22, 2026].

[12] W3C, "SPARQL 1.1 Update," W3C Recommendation, 2013. [Online]. Available: https://www.w3.org/TR/sparql11-update/. [Accessed: Apr. 22, 2026].

[13] Open Source Initiative, "The Open Source Definition," n.d. [Online]. Available: https://opensource.org/osd/. [Accessed: Apr. 22, 2026].

[14] SPDX Workgroup, "SPDX License List," n.d. [Online]. Available: https://spdx.org/licenses/. [Accessed: Apr. 22, 2026].

[15] European Union, "Regulation (EU) 2016/679 (General Data Protection Regulation)," Official Journal of the European Union, 2016. [Online]. Available: https://eur-lex.europa.eu/. [Accessed: Apr. 22, 2026].

---

## Anexos
En UC3M, además de anexos técnicos opcionales, existe un **anexo no opcional**: la declaración de uso de IA generativa. En este trabajo se incluyen ambos tipos:

- **Anexo A (técnico, opcional):** resumen de operadores/familias y patrones SPARQL.
- **Anexo B (obligatorio UC3M):** declaración de uso de IA generativa.

#### Anexo A — Operadores/familias y patrones SPARQL resumen

| Familia (operador) | Intención | Señales típicas (NL) | Esqueleto SPARQL (simplificado) | Ejemplo de referencia |
|---|---|---|---|---|
| Ausencia de relación (NOT EXISTS) | Find entities missing required trace/link | "missing/without", "does not have" | `FILTER NOT EXISTS { ?src p510:REL ?ln . ?ln p510:Link ?tgt . ... }` | `q1_req_sin_modelo_fisico.sparql` |
| Models without tests (NOT EXISTS) | Models without tests | "models without tests", "without verification" | `FILTER NOT EXISTS { ?m p510:Verified_by ?ln . ?ln p510:Link ?test . ... }` | `q2_modelos_sin_test.sparql` |
| Requirements missing end-to-end traceability (NOT EXISTS) | Requirements missing Req→Model→Test chain | "end-to-end", "missing traceability", "missing full trace" | `FILTER NOT EXISTS { ?req p510:Satisfied_by ?lnm . ?lnm p510:Link ?m . ?m p510:Verified_by ?lnt . ?lnt p510:Link ?t . }` | `q4_req_sin_traza_end_to_end.sparql` |
| Requisitos sobre-especificados (HAVING) | Requisitos con más de un modelo físico | "más de uno", "multiple physical models" | `GROUP BY ?req HAVING(COUNT(DISTINCT ?m) > 1)` | `q5_reqs_sobre_especificados.sparql` |
| Conteo total (COUNT) | Contar entidades (suppliers, links, requisitos, etc.) | "how many", "number of", "count" | `SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE { ?x a ... }` | `q6_cuantos_proveedores.sparql` |
| Porcentaje (COUNT + expresión) | Porcentaje de requisitos con modelo | "percentage", "ratio" | `SELECT (100*?n_with/?n_total AS ?pct) WHERE { ... }` | `q3_porcentaje_req_con_modelo.sparql` |
| Distribución por proveedor (GROUP BY) | Modelos por proveedor | "by supplier", "by provider" | `GROUP BY ?supplier (COUNT(DISTINCT ?m) AS ?n)` | `q7_modelos_por_proveedor.sparql` |
| Distribución por aprobación (GROUP BY) | Modelos por estado de aprobación | "approval state" | `GROUP BY ?state (COUNT(DISTINCT ?m) AS ?n)` | `q20_modelos_por_estado_aprobacion.sparql` |
| Distribución por madurez (GROUP BY) | Requisitos por estado de madurez | "maturity state", "by maturity" | `GROUP BY ?maturity (COUNT(DISTINCT ?req) AS ?n)` | `q17_requisitos_por_maturity.sparql` |
| Distribución por subsistema (GROUP BY) | Requisitos por subsistema | "subsystem", "by subsystem" | `GROUP BY ?subsystem (COUNT(DISTINCT ?req) AS ?n)` | `q27_requisitos_por_subsistema.sparql` |
| Distribución por método V&V (GROUP BY) | Requisitos por método de verificación | "verification method", "by method" | `GROUP BY ?method (COUNT(DISTINCT ?req) AS ?n)` | `q28_requisitos_por_metodo_verificacion.sparql` |
| Auditoría: links without timestamps (NOT EXISTS) | Detect traces missing mandatory timestamps | "missing timestamp", "without timestamps" | `FILTER NOT EXISTS { ?ln p510:Timestamp_PLM ?ts }` | `q13_links_sin_timestamp.sparql` |
| Auditoría: links without description (NOT EXISTS) | Detect traces missing description | "without description", "missing description" | `FILTER NOT EXISTS { ?ln p510:Description ?d }` | `q25_links_sin_description.sparql` |
| Audit: contentType mismatch (FILTER) | Detect contentType inconsistencies | "contentType mismatch", "inconsistent contentType" | `?ln p510:ContentType ?ct . FILTER(?ct != ...)` | `q23_link_contenttype_incoherente.sparql` |
| Auditoría: without approver (NOT EXISTS) | Requirements without approver | "without approver", "missing approver" | `FILTER NOT EXISTS { ?req p510:Approver ?a }` | `q16_requisitos_sin_aprobador.sparql` |
| Auditoría: Approved without Approver (NOT EXISTS) | Approved state without Approver attribute | "approved without approver" | `?x p510:Approval_State "Approved" . FILTER NOT EXISTS { ?x p510:Approver ?a }` | `q22_aprobados_sin_aprobador.sparql` |
| Duplicados (GROUP BY + HAVING) | Detectar enlaces redundantes | "duplicate", "repeated", "duplicate links" | `GROUP BY ?src ?pred ?tgt HAVING(COUNT(DISTINCT ?ln) > 1)` | `q24_links_duplicados.sparql` |

Notas:
- En el sistema, estos esqueletos se instancian con clases/predicados extraídos del grafo (grounding) y se validan con el checker antes de ejecutar.
- La columna "ejemplo de referencia" apunta a una query que se ejecuta directamente sobre el dataset sintético para comprobar el patrón.

#### Anexo B — Declaración de uso de IA generativa obligatoria
Este proyecto se ha desarrollado con apoyo de herramientas de IA generativa como asistente. Su uso se limita a tareas de apoyo y **no sustituye** la autoría ni la validación técnica. En concreto:

- Se ha utilizado IA para apoyo a la redacción (estructuración de capítulos, reformulaciones, mejora de claridad) y para apoyo a programación (sugerencias de fragmentos de código, identificación de puntos a documentar).
- Todo el contenido final (texto, tablas y descripciones) se ha revisado y editado manualmente.
- Los resultados reportados en la memoria se fundamentan en ejecuciones reproducibles del repositorio (scripts en `src/` y logs en `eval/`) y en consultas SPARQL ejecutadas sobre el dataset local.

Si el centro proporciona una plantilla oficial para esta declaración, debe reemplazarse este texto por la plantilla exacta y completarse con la información requerida (herramienta usada, finalidad, alcance, fecha y responsable).

#### Anexo C — Reproducibilidad: cómo repetir todos los resultados paso a paso
Este anexo describe un protocolo mínimo, pensado para que un tercero pueda repetir (i) la generación del dataset, (ii) la ejecución del oráculo y (iii) las dos corridas de evaluación reportadas en el Cap. 5 (capa ejecutable y estabilidad por intención). El objetivo no es "automatizarlo todo", sino fijar **comandos exactos**, **artefactos** y **salidas esperadas**.

##### C.1 Preparación del entorno Python
En Windows, se recomienda un entorno virtual:

```bash
python -m venv .venv
./.venv/Scripts/activate
pip install -r requirements.txt
```

Para respaldo de reproducibilidad, es recomendable capturar una instantánea de versiones:

```bash
python --version
pip freeze > eval/pip_freeze.txt
```

##### C.2 Regeneración del dataset sintético
Para regenerar el TTL (si se desea verificar determinismo), ejecutar el generador. El artefacto esperado es `data/p510_sintetico.ttl`:

```bash
python src/p510_generate_synthetic.py
```

Si el generador fija la semilla (p. ej. `random.seed(42)`), a igualdad de parámetros el TTL resultante debería ser estable (Cap. 3.2.1).

##### C.3 Ejecución del oráculo de consultas SPARQL de referencia
Para comprobar que dataset y oráculo son consistentes (las queries ejecutan), ejecutar el runner de consultas:

```bash
python src/run_queries_p510.py
```

Esta ejecución sirve como verificación de base: si aquí fallara una query, la evaluación posterior sería difícil de interpretar.

##### C.4 Evaluación automática del catálogo capa ejecutable OK/FAIL
La evaluación del catálogo se ejecuta con el harness `src/text2sparql_eval.py`. Se recomiendan dos corridas:

1) **Modo reference** (ejecutar SPARQL gold del JSONL):

```bash
python src/text2sparql_eval.py --mode reference
```

2) **Modo generate** (generar desde NL y ejecutar):

```bash
python src/text2sparql_eval.py --mode generate --engine dynamic
python src/text2sparql_eval.py --mode generate --engine catalog
```

La salida esperada, en el entorno descrito en Cap. 5, es una tasa de ejecución sin error **34/34 OK** (capa ejecutable). Para conservar evidencia, se recomienda redirigir salida a logs con fecha y guardarlos en `eval/`.

##### C.5 Smoke test de paráfrasis estabilidad por intención
Para ejecutar el test de estabilidad por intención:

```bash
python eval/paraphrase_smoke.py
```

El test produce un log de corrida (por ejemplo, `eval/paraphrase_smoke_out_current_utf8.txt`) con el resumen de consistencia por grupo. La salida esperada (sobre el TTL actual) es **74/74 OK** y **26/26 grupos consistentes**, bajo el criterio (operador + cardinalidad) definido en Cap. 5.3.3.

##### C.6 Evidencias mínimas a adjuntar en anexos o como ficheros del repo
Para que un evaluador pueda verificar resultados sin repetir toda la instalación, se recomiendan como mínimo estos ficheros:

- Logs de evaluación del catálogo (p. ej. `eval/catalog_generate_run.txt`).
- Log del smoke test de paráfrasis (p. ej. `eval/paraphrase_smoke_out_current_utf8.txt`).
- Instantánea de entorno (`eval/pip_freeze.txt`) y, si se ha regenerado el TTL, el `data/p510_sintetico.ttl` usado.

Con este conjunto, la trazabilidad del experimento queda completa: dato + oráculo + pipeline + logs.

