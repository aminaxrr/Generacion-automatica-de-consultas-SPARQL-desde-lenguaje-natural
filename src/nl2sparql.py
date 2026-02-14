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

    if any(
        k in lower
        for k in [
            "modelos sin test",
            "modelos sin pruebas",
            "modelos no verificados",
            "modelos que no tienen test",
            "modelos que no tienen ningún test",
            "modelos que no tienen ningun test",
            "no tienen test asociado",
            "sin ningún test asociado",
            "sin ningun test asociado",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q2_modelos_sin_test.sparql")

    if any(k in lower for k in ["porcentaje", "cobertura"]) and any(k in lower for k in ["requisitos", "req"]):
        return ParsedNLQuery(kind="file", query_file="q3_porcentaje_req_con_modelo.sparql")

    if any(k in lower for k in ["trazabilidad completa", "end to end", "end-to-end", "extremo a extremo", "e2e"]):
        return ParsedNLQuery(kind="file", query_file="q4_req_sin_traza_end_to_end.sparql")

    if any(k in lower for k in ["resumen plm", "plm resumen", "metadatos plm"]):
        return ParsedNLQuery(kind="file", query_file="q8_plm_resumen.sparql")

    if any(
        k in lower
        for k in [
            "entorno de desarrollo",
            "development environment",
            "herramientas",
            "sistema operativo",
            "os ",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q9_dev_environment.sparql")

    if any(
        k in lower
        for k in [
            "documentos usados",
            "documentos se usan",
            "qué documentos se usan",
            "que documentos se usan",
            "documentos en el entorno de desarrollo",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q10_documentos_usados.sparql")

    if any(k in lower for k in ["resumen v&v", "resumen vnv", "escenarios v&v", "escenarios vnv", "credibilidad"]):
        return ParsedNLQuery(kind="file", query_file="q11_vnv_escenarios_resumen.sparql")

    if any(
        k in lower
        for k in [
            "escenarios incompletos",
            "v&v incompletos",
            "vnv incompletos",
            "sin verified_by",
            "sin validated_by",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q12_vnv_escenarios_incompletos.sparql")

    if any(k in lower for k in ["entidades", "conteo de entidades", "cuántas entidades", "cuantas entidades"]):
        return ParsedNLQuery(kind="file", query_file="q14_conteo_entidades.sparql")

    if any(k in lower for k in ["enlaces sin timestamp", "links sin timestamp", "falta timestamp"]):
        return ParsedNLQuery(kind="file", query_file="q13_links_sin_timestamp.sparql")

    if any(k in lower for k in ["links sin descripción", "links sin descripcion", "enlaces sin descripción", "enlaces sin descripcion"]):
        return ParsedNLQuery(kind="file", query_file="q25_links_sin_description.sparql")

    if any(k in lower for k in ["enlaces duplicados", "links duplicados", "duplicados"]):
        return ParsedNLQuery(kind="file", query_file="q24_links_duplicados.sparql")

    if any(k in lower for k in ["trazas duplicadas", "links duplicadas", "duplicadas"]):
        return ParsedNLQuery(kind="file", query_file="q24_links_duplicados.sparql")

    if any(k in lower for k in ["aprobados sin aprobador", "approved sin approver", "sin aprobador"]):
        return ParsedNLQuery(kind="file", query_file="q22_aprobados_sin_aprobador.sparql")

    if any(
        k in lower
        for k in [
            "contenttype incoherente",
            "content type incoherente",
            "incoherente con el destino",
            "no coincide con el destino",
            "no coincide con el contenttype",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q23_link_contenttype_incoherente.sparql")

    if any(k in lower for k in ["sin proveedor", "modelos sin proveedor", "proveedor faltante", "responsable faltante"]):
        return ParsedNLQuery(kind="file", query_file="q15_modelos_sin_proveedor.sparql")

    # --- Parameterized intent: models by supplier ---
    # Examples: "modelos del proveedor 03", "modelos del proveedor 3", "modelos de Proveedor 02"
    m = re.search(r"modelos\s+(?:del|de)\s+proveedor\s*0*(\d{1,2})\b", lower)
    if m:
        supplier_num = int(m.group(1))
        supplier_name = f"Proveedor {supplier_num:02d}"
        return ParsedNLQuery(kind="supplier_models", supplier_name=supplier_name)

    # More flexible variant: "modelos de un proveedor ... Proveedor 03"
    m2 = re.search(r"\bproveedor\s*0*(\d{1,2})\b", lower)
    if m2 and "modelo" in lower:
        supplier_num = int(m2.group(1))
        supplier_name = f"Proveedor {supplier_num:02d}"
        return ParsedNLQuery(kind="supplier_models", supplier_name=supplier_name)

    raise ValueError(
        "No pude mapear la pregunta a una consulta. "
        "Prueba con: '¿Cuántos proveedores hay?', 'requisitos sin modelo', 'modelos del proveedor 03', etc."
    )
