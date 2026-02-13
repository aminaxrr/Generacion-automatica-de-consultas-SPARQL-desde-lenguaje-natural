import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedNLQuery:
    kind: str
    query_file: str | None = None
    supplier_name: str | None = None


def parse_spanish_question(text: str) -> ParsedNLQuery:
    """Parsea una pregunta (ES) y la mapea a una consulta SPARQL.

    Esta demo está pensada para el TFG: muestra un baseline reproducible de NL→SPARQL
    mediante reglas + plantillas, sin ML.
    """

    normalized = " ".join(text.strip().split())
    lower = normalized.casefold()

    # --- Exact-ish intent rules to existing query catalogue ---
    if any(k in lower for k in ["cuántos proveedores", "cuantos proveedores", "número de proveedores", "numero de proveedores"]):
        return ParsedNLQuery(kind="file", query_file="q6_cuantos_proveedores.sparql")

    if any(k in lower for k in ["requisitos sin modelo", "requisitos que no tienen modelo", "requisitos sin modelo físico", "requisitos sin modelo fisico"]):
        return ParsedNLQuery(kind="file", query_file="q1_req_sin_modelo_fisico.sparql")

    if any(k in lower for k in ["modelos sin test", "modelos sin pruebas", "modelos no verificados", "modelos que no tienen test"]):
        return ParsedNLQuery(kind="file", query_file="q2_modelos_sin_test.sparql")

    if any(k in lower for k in ["porcentaje", "cobertura"]) and any(k in lower for k in ["requisitos", "req"]):
        return ParsedNLQuery(kind="file", query_file="q3_porcentaje_req_con_modelo.sparql")

    if any(k in lower for k in ["trazabilidad completa", "end to end", "extremo a extremo", "e2e"]):
        return ParsedNLQuery(kind="file", query_file="q4_req_sin_traza_end_to_end.sparql")

    if any(k in lower for k in ["resumen plm", "plm resumen", "metadatos plm"]):
        return ParsedNLQuery(kind="file", query_file="q8_plm_resumen.sparql")

    if any(k in lower for k in ["entidades", "conteo de entidades", "cuántas entidades", "cuantas entidades"]):
        return ParsedNLQuery(kind="file", query_file="q14_conteo_entidades.sparql")

    if any(k in lower for k in ["enlaces sin timestamp", "links sin timestamp", "falta timestamp"]):
        return ParsedNLQuery(kind="file", query_file="q13_links_sin_timestamp.sparql")

    if any(k in lower for k in ["enlaces duplicados", "links duplicados", "duplicados"]):
        return ParsedNLQuery(kind="file", query_file="q24_links_duplicados.sparql")

    if any(k in lower for k in ["aprobados sin aprobador", "approved sin approver", "sin aprobador"]):
        return ParsedNLQuery(kind="file", query_file="q22_aprobados_sin_aprobador.sparql")

    # --- Parameterized intent: models by supplier ---
    # Examples: "modelos del proveedor 03", "modelos del proveedor 3", "modelos de Proveedor 02"
    m = re.search(r"modelos\s+(?:del|de)\s+proveedor\s*0*(\d{1,2})\b", lower)
    if m:
        supplier_num = int(m.group(1))
        supplier_name = f"Proveedor {supplier_num:02d}"
        return ParsedNLQuery(kind="supplier_models", supplier_name=supplier_name)

    raise ValueError(
        "No pude mapear la pregunta a una consulta. "
        "Prueba con: '¿Cuántos proveedores hay?', 'requisitos sin modelo', 'modelos del proveedor 03', etc."
    )
