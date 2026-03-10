import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedNLQuery:
    kind: str
    query_file: str | None = None
    supplier_name: str | None = None


def parse_english_question(text: str) -> ParsedNLQuery:
    """Parse an English question and map it to a SPARQL query.

    This baseline is intended for the TFG: it demonstrates a reproducible NL→SPARQL
    approach using rules + templates (no ML).
    """

    normalized = " ".join(text.strip().split())
    lower = normalized.casefold()

    # --- Exact-ish intent rules to existing query catalogue ---
    if any(k in lower for k in ["how many suppliers", "number of suppliers", "count suppliers"]):
        return ParsedNLQuery(kind="file", query_file="q6_cuantos_proveedores.sparql")

    if any(k in lower for k in ["requirements without model", "requirements without a model", "requirements missing a model", "requirements without physical model"]):
        return ParsedNLQuery(kind="file", query_file="q1_req_sin_modelo_fisico.sparql")

    if any(
        k in lower
        for k in [
            "models without tests",
            "models without a test",
            "physical models without tests",
            "models not verified",
            "no associated test",
            "no test associated",
            "missing verification test",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q2_modelos_sin_test.sparql")

    if any(k in lower for k in ["percentage", "coverage"]) and any(k in lower for k in ["requirements", "req"]):
        return ParsedNLQuery(kind="file", query_file="q3_porcentaje_req_con_modelo.sparql")

    if any(k in lower for k in ["end to end", "end-to-end", "end-to end", "e2e", "end to end traceability"]):
        return ParsedNLQuery(kind="file", query_file="q4_req_sin_traza_end_to_end.sparql")

    # --- New metadata queries (enriched dataset) ---
    if any(k in lower for k in ["baseline", "project code", "project id", "product"]):
        return ParsedNLQuery(kind="file", query_file="q26_baseline_y_proyecto.sparql")

    if "requir" in lower and any(k in lower for k in ["subsystem", "module", "domain"]):
        return ParsedNLQuery(kind="file", query_file="q27_requisitos_por_subsistema.sparql")

    if "requir" in lower and any(
        k in lower
        for k in [
            "verification_method",
            "verification method",
            "verified by method",
            "how are requirements verified",
        ]
    ):
        return ParsedNLQuery(kind="file", query_file="q28_requisitos_por_metodo_verificacion.sparql")

    if any(k in lower for k in ["plm summary", "plm overview", "manifest summary"]):
        return ParsedNLQuery(kind="file", query_file="q8_plm_resumen.sparql")

    if any(k in lower for k in ["development environment", "dev environment", "tool version", "operating system", "os version"]):
        return ParsedNLQuery(kind="file", query_file="q9_dev_environment.sparql")

    # Match 'OS' as a standalone token.
    if re.search(r"\bos\b", lower):
        return ParsedNLQuery(kind="file", query_file="q9_dev_environment.sparql")

    if any(k in lower for k in ["used documents", "documents used", "referenced documents", "which documents are used"]):
        return ParsedNLQuery(kind="file", query_file="q10_documentos_usados.sparql")

    if any(k in lower for k in ["v&v scenarios", "vnv scenarios", "scenario summary", "credibility level"]):
        return ParsedNLQuery(kind="file", query_file="q11_vnv_escenarios_resumen.sparql")

    if any(k in lower for k in ["incomplete scenarios", "scenarios without verified_by", "scenarios without validated_by"]):
        return ParsedNLQuery(kind="file", query_file="q12_vnv_escenarios_incompletos.sparql")

    if any(k in lower for k in ["entity count", "count entities", "how many entities"]):
        return ParsedNLQuery(kind="file", query_file="q14_conteo_entidades.sparql")

    if any(k in lower for k in ["links without timestamp", "missing timestamp", "links missing timestamp"]):
        return ParsedNLQuery(kind="file", query_file="q13_links_sin_timestamp.sparql")

    if any(k in lower for k in ["links without description", "missing description"]):
        return ParsedNLQuery(kind="file", query_file="q25_links_sin_description.sparql")

    if any(k in lower for k in ["duplicate links", "duplicate traces", "duplicated links"]):
        return ParsedNLQuery(kind="file", query_file="q24_links_duplicados.sparql")

    if any(k in lower for k in ["repeated links", "repeated traces"]):
        return ParsedNLQuery(kind="file", query_file="q24_links_duplicados.sparql")

    if any(k in lower for k in ["approved without approver", "approved but no approver", "missing approver"]):
        return ParsedNLQuery(kind="file", query_file="q22_aprobados_sin_aprobador.sparql")

    if any(k in lower for k in ["contenttype mismatch", "content type mismatch", "inconsistent contenttype", "contenttype inconsistent"]):
        return ParsedNLQuery(kind="file", query_file="q23_link_contenttype_incoherente.sparql")

    if any(k in lower for k in ["models without supplier", "missing supplier", "missing responsibility"]):
        return ParsedNLQuery(kind="file", query_file="q15_modelos_sin_proveedor.sparql")

    # --- Parameterized intent: models by supplier ---
    # Examples: "models of supplier 03", "models for supplier 3"
    m = re.search(r"models\s+(?:of|for)\s+supplier\s*0*(\d{1,2})\b", lower)
    if m:
        supplier_num = int(m.group(1))
        supplier_name = f"Supplier {supplier_num:02d}"
        return ParsedNLQuery(kind="supplier_models", supplier_name=supplier_name)

    # More flexible variant: "supplier 03" + mentions model
    m2 = re.search(r"\bsupplier\s*0*(\d{1,2})\b", lower)
    if m2 and "model" in lower:
        supplier_num = int(m2.group(1))
        supplier_name = f"Supplier {supplier_num:02d}"
        return ParsedNLQuery(kind="supplier_models", supplier_name=supplier_name)

    raise ValueError(
        "I could not map the question to a query. "
        "Try: 'How many suppliers are there?', 'requirements without model', 'models of supplier 03', etc."
    )


# Backwards-compatibility: keep old name removed in English-only refactor.
# (Intentionally not provided.)
