import json
import re
import difflib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import Graph
from rdflib.namespace import RDF


FORBIDDEN_KEYWORDS = (
    "CONSTRUCT",
    "DESCRIBE",
    "INSERT",
    "DELETE",
    "LOAD",
    "CLEAR",
    "DROP",
    "CREATE",
    "MOVE",
    "COPY",
    "ADD",
)


@dataclass(frozen=True)
class GenerationConfig:
    # Engine:
    # - dynamic: build SPARQL on-the-fly by mapping NL terms to graph classes/predicates
    # - catalog: select a pre-written SPARQL from a JSONL catalog
    engine: str = "dynamic"
    limit: int = 200
    match_threshold: float = 0.35
    max_suggestions: int = 3
    synonyms_file: str | None = None
    classifier_model_file: str | None = None
    classifier_min_prob: float = 0.60


@dataclass(frozen=True)
class GenerationResult:
    sparql: str
    attempts: int
    matched_nl: str | None = None
    matched_id: str | None = None
    match_score: float | None = None
    error: str | None = None
    explanation: list[str] | None = None


@dataclass(frozen=True)
class SynonymMap:
    # normalized synonym phrase -> normalized canonical phrase
    phrases: list[tuple[str, str]]
    # normalized single token -> normalized canonical single token
    words: dict[str, str]


@dataclass(frozen=True)
class NBModel:
    version: int
    classes: list[str]
    vocab: dict[str, int]
    log_prior: dict[str, float]
    log_likelihood: dict[str, list[float]]
    default_log_likelihood: dict[str, float]
    class_example_nl: dict[str, str]


@dataclass(frozen=True)
class SchemaIndex:
    classes: set[str]
    predicates: set[str]
    prefixes: dict[str, str]
    class_by_local: dict[str, str]
    pred_by_local: dict[str, str]


@dataclass(frozen=True)
class GroundingHit:
    phrase: str
    kind: str  # operator|entity|predicate|attribute|literal
    mapped_to: str


@dataclass(frozen=True)
class GroundingResult:
    normalized: str
    tokens_sig: set[str]
    hits: list[GroundingHit]

    def explain_lines(self, max_hits: int = 30) -> list[str]:
        lines: list[str] = []
        lines.append(f"normalized: {self.normalized}")
        lines.append("tokens_sig: " + ", ".join(sorted(self.tokens_sig))[:200])
        for h in self.hits[:max_hits]:
            lines.append(f"ground: '{h.phrase}' -> {h.kind}={h.mapped_to}")
        if len(self.hits) > max_hits:
            lines.append(f"ground: (+{len(self.hits) - max_hits} more)")
        return lines


_STD_OK_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "owl": "http://www.w3.org/2002/07/owl#",
}


def _local_name(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _norm_key(s: str) -> str:
    # A stable normalization for mapping NL tokens ↔ local names
    s = s.lower().strip()
    return re.sub(r"[^a-z0-9]+", "", s)


def _build_schema_index(graph: Graph) -> SchemaIndex:
    classes: set[str] = set()
    predicates: set[str] = set()

    for _, _, o in graph.triples((None, RDF.type, None)):
        classes.add(str(o))
    for _, p, _ in graph.triples((None, None, None)):
        predicates.add(str(p))

    prefixes: dict[str, str] = {}
    try:
        for pfx, ns in graph.namespace_manager.namespaces():
            if not pfx:
                continue
            prefixes[str(pfx)] = str(ns)
    except Exception:
        prefixes = {}

    # Ensure common standard prefixes exist for checking.
    for pfx, uri in _STD_OK_PREFIXES.items():
        prefixes.setdefault(pfx, uri)

    class_by_local: dict[str, str] = {}
    pred_by_local: dict[str, str] = {}
    for uri in classes:
        class_by_local[_norm_key(_local_name(uri))] = uri
    for uri in predicates:
        pred_by_local[_norm_key(_local_name(uri))] = uri

    return SchemaIndex(
        classes=classes,
        predicates=predicates,
        prefixes=prefixes,
        class_by_local=class_by_local,
        pred_by_local=pred_by_local,
    )


def _prefix_lines(index: SchemaIndex, preferred: list[str] | None = None) -> str:
    preferred = preferred or ["p510", "ex", "foaf", "dcterms", "rdf", "rdfs", "xsd", "owl"]
    out: list[str] = []
    for pfx in preferred:
        uri = index.prefixes.get(pfx)
        if uri:
            out.append(f"PREFIX {pfx}: <{uri}>")
    return "\n".join(out)


def _extract_query_prefixes(sparql: str) -> dict[str, str]:
    # Parse PREFIX lines from a SPARQL query string.
    pfx: dict[str, str] = {}
    for line in sparql.splitlines():
        line = line.strip()
        if not line.upper().startswith("PREFIX "):
            continue
        m = re.match(r"^PREFIX\s+([A-Za-z_][\w-]*)\s*:\s*<([^>]+)>\s*$", line, flags=re.IGNORECASE)
        if m:
            pfx[m.group(1)] = m.group(2)
    return pfx


def _namespace(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if "/" in uri:
        return uri.rsplit("/", 1)[0] + "/"
    return uri


def _canonical_namespace(ns: str) -> str:
    # Canonicalize a namespace IRI to end with '#' or '/'
    ns = ns.strip()
    if ns.endswith("#") or ns.endswith("/"):
        return ns
    if "#" in ns:
        return ns.rsplit("#", 1)[0] + "#"
    if "/" in ns:
        return ns.rsplit("/", 1)[0] + "/"
    return ns


def _where_body(sparql: str) -> str:
    a = sparql.find("{")
    b = sparql.rfind("}")
    if a != -1 and b != -1 and b > a:
        return sparql[a : b + 1]
    return sparql


def _suggest_terms(index: SchemaIndex, kind: str, local: str) -> str:
    # kind: "class" or "pred"
    key = _norm_key(local)
    pool = index.class_by_local if kind == "class" else index.pred_by_local
    if not pool:
        return ""
    candidates = difflib.get_close_matches(key, list(pool.keys()), n=3, cutoff=0.65)
    if not candidates:
        return ""
    names = [_local_name(pool[c]) for c in candidates if c in pool]
    if not names:
        return ""
    return " (did you mean: " + ", ".join(names) + ")"


def check_no_invented_terms(graph: Graph, sparql: str) -> None:
    """Reject queries that reference classes/properties not present in the graph.

    Goal: prevent a dynamic generator from inventing attributes/classes.
    This checker is heuristic (not a full SPARQL parser) but strict about schema terms.
    """

    index = _build_schema_index(graph)
    declared = _extract_query_prefixes(sparql)

    # Allowed namespaces come from the graph schema itself (classes/predicates), plus std vocabularies.
    allowed_ns: set[str] = set(_STD_OK_PREFIXES.values())
    for iri in index.classes | index.predicates:
        allowed_ns.add(_namespace(iri))
    for ns in index.prefixes.values():
        allowed_ns.add(_canonical_namespace(ns))

    # Validate declared prefixes do not introduce unknown namespaces.
    bad_prefixes: list[str] = []
    for pfx, ns in declared.items():
        ns_c = _canonical_namespace(ns)
        if ns_c in allowed_ns:
            continue
        bad_prefixes.append(f"{pfx}: <{ns}>")
    if bad_prefixes:
        raise ValueError(
            "Checker failed: the query declares prefixes whose namespaces are not present in the graph schema: "
            + ", ".join(sorted(set(bad_prefixes))[:8])
        )

    prefixes = {**index.prefixes, **declared}

    def expand_qname(qname: str) -> str | None:
        if ":" not in qname:
            return None
        pfx, local = qname.split(":", 1)
        ns = prefixes.get(pfx)
        if not ns:
            return None
        return ns + local

    unknown_prefixed: dict[str, str] = {}

    # 1) Token-level check for qnames like p510:Requirement, foaf:name.
    qnames = re.findall(r"\b([A-Za-z_][\w-]*\:[A-Za-z_][\w-]*)\b", sparql)
    for qn in qnames:
        pfx = qn.split(":", 1)[0]
        if pfx.lower() in {"http", "https"}:
            continue
        iri = expand_qname(qn)
        if iri is None:
            unknown_prefixed[qn] = f"{qn} (unknown prefix)"
            continue
        ns = _namespace(iri)
        if ns in _STD_OK_PREFIXES.values():
            continue
        if iri in index.predicates or iri in index.classes:
            continue
        # If it is from an allowed schema namespace but not in schema terms, reject.
        if _canonical_namespace(ns) in allowed_ns or ns in allowed_ns:
            # Provide suggestion based on local name.
            local = qn.split(":", 1)[1]
            hint = _suggest_terms(index, "pred", local) or _suggest_terms(index, "class", local)
            unknown_prefixed[qn] = f"{qn}{hint}"

    # 2) Check explicit IRIs in <...> when they belong to schema namespaces.
    iris = [i for i in re.findall(r"<([^>]+)>", sparql) if i]
    bad_iris: list[str] = []
    for iri in iris:
        # Ignore namespace IRIs in PREFIX lines.
        if iri.endswith("#") or iri.endswith("/"):
            continue
        ns = _namespace(iri)
        if ns in _STD_OK_PREFIXES.values():
            continue
        if _canonical_namespace(ns) not in allowed_ns and ns not in allowed_ns:
            continue
        if iri in index.predicates or iri in index.classes:
            continue
        local = _local_name(iri)
        hint = _suggest_terms(index, "pred", local) or _suggest_terms(index, "class", local)
        bad_iris.append(f"<{iri}>{hint}")

    # 3) Structural checks inside WHERE: validate class objects in `a <Class>` and predicates in triple positions.
    body = _where_body(sparql)

    # a <IRI> / a prefix:Local must be a class term.
    type_terms = re.findall(r"\ba\s+(<[^>]+>|[A-Za-z_][\w-]*\:[A-Za-z_][\w-]*)", body)
    bad_types: list[str] = []
    bad_types_raw: set[str] = set()
    for t in type_terms:
        if t.startswith("<"):
            iri = t[1:-1]
        else:
            iri = expand_qname(t) or ""
        if not iri:
            bad_types_raw.add(t)
            bad_types.append(f"{t} (unknown prefix)")
            continue
        ns = _namespace(iri)
        if ns in _STD_OK_PREFIXES.values():
            continue
        if iri not in index.classes:
            hint = _suggest_terms(index, "class", _local_name(iri))
            bad_types_raw.add(t)
            bad_types.append(f"{t}{hint}")

    # Predicates: capture <IRI> or qname after subject or after ';'
    pred_terms = re.findall(
        r"(?:^|[\n\.{]\s*)\s*(?:\?[A-Za-z_][\w-]*|<[^>]+>)\s+(<[^>]+>|[A-Za-z_][\w-]*\:[A-Za-z_][\w-]*)\s+",
        body,
        flags=re.MULTILINE,
    )
    pred_terms += re.findall(r";\s*(<[^>]+>|[A-Za-z_][\w-]*\:[A-Za-z_][\w-]*)\s+", body)

    bad_preds: list[str] = []
    bad_preds_raw: set[str] = set()
    for t in pred_terms:
        if t == "a":
            continue
        if t.startswith("<"):
            iri = t[1:-1]
        else:
            iri = expand_qname(t) or ""
        if not iri:
            bad_preds_raw.add(t)
            bad_preds.append(f"{t} (unknown prefix)")
            continue
        ns = _namespace(iri)
        if ns in _STD_OK_PREFIXES.values():
            continue
        if iri not in index.predicates:
            hint = _suggest_terms(index, "pred", _local_name(iri))
            bad_preds_raw.add(t)
            bad_preds.append(f"{t}{hint}")

    # Avoid duplicate reporting: if a term is already flagged in a structural role, don't also report it
    # in the generic qname scan.
    unknown_terms = [
        v for k, v in unknown_prefixed.items() if k not in bad_types_raw and k not in bad_preds_raw
    ]

    if unknown_terms or bad_iris or bad_types or bad_preds:
        parts: list[str] = []
        if unknown_terms:
            parts.append("Unknown prefixed terms: " + ", ".join(sorted(set(unknown_terms))[:10]))
        if bad_iris:
            parts.append("Unknown IRIs: " + ", ".join(sorted(set(bad_iris))[:10]))
        if bad_types:
            parts.append("Unknown rdf:type classes: " + ", ".join(sorted(set(bad_types))[:10]))
        if bad_preds:
            parts.append("Unknown predicates: " + ", ".join(sorted(set(bad_preds))[:10]))
        raise ValueError("Checker failed: " + " | ".join(parts))


def _extract_author_org_literal(question: str) -> str | None:
    """Extract an Author_Organization literal from a question.

    Current synthetic data uses values like "Supplier 03" and "University".
    """

    m = re.search(r"\bsupplier\s*(\d{1,2})\b", question, flags=re.IGNORECASE)
    if m:
        return f"Supplier {int(m.group(1)):02d}"
    if re.search(r"\buniversity\b", question, flags=re.IGNORECASE):
        return "University"
    return None


def _extract_supplier_name_literal(question: str) -> str | None:
    """Extract a supplier name literal (e.g., "Supplier 03") from a question.

    Current synthetic data uses values like "Supplier 03".."Supplier 06" (via foaf:name).
    """

    m = re.search(r"\bsupplier\s*(\d{1,2})\b", question, flags=re.IGNORECASE)
    if m:
        return f"Supplier {int(m.group(1)):02d}"
    return None


def _find_class(index: SchemaIndex, *candidates: str) -> str | None:
    for cand in candidates:
        k = _norm_key(cand)
        uri = index.class_by_local.get(k)
        if uri:
            return uri
    return None


def _find_pred(index: SchemaIndex, *candidates: str) -> str | None:
    for cand in candidates:
        k = _norm_key(cand)
        uri = index.pred_by_local.get(k)
        if uri:
            return uri
    return None


def _split_local_tokens(name: str) -> list[str]:
    # Split a schema local-name into tokens: underscores + camel case + digits.
    s = name.replace("_", " ")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", s) if t]


def _ground_question(question: str, normalized: str, tokens_sig: set[str], index: SchemaIndex) -> GroundingResult:
    """Ground NL tokens/phrases to operators and schema concepts.

    This stays deterministic and conservative: it only emits a hit when there is a clear
    mapping to a known schema term or a known query operator.
    """

    q_raw = _normalize_nl_basic(question)
    q = normalized

    hits: list[GroundingHit] = []

    def add(phrase: str, kind: str, mapped_to: str) -> None:
        hits.append(GroundingHit(phrase=phrase, kind=kind, mapped_to=mapped_to))

    # Operators (language-level).
    if re.search(r"\b(how\s+many|count(\s+of)?|number\s+of|total\s+number\s+of|quantity\s+of|amount\s+of)\b", q):
        add("count/how-many", "operator", "COUNT")
    if re.search(r"\b(percent|percentage|ratio)\b", q):
        add("percentage", "operator", "PERCENT")
    if re.search(r"\b(list|show|display|give|return)\b", q):
        add("list/show", "operator", "LIST")
    if re.search(r"\b(without|missing|lack|lacking|absent)\b", q) or "no" in q_raw.split() or re.search(
        r"\b(do\s+not\s+have|does\s+not\s+have|not\s+having)\b", q
    ):
        add("missing/without", "operator", "NOT_EXISTS")
    if re.search(r"\b(duplicate|duplicates|duplicated|repeated|redundant|same\s+link|same\s+trace)\b", q):
        add("duplicate", "operator", "DUPLICATE")
    if re.search(r"\b(audit|check|detect|validate)\b", q):
        add("audit/check", "operator", "AUDIT")
    if re.search(r"\b(summary|overview|resume|resumen)\b", q):
        add("summary", "operator", "SUMMARY")
    if re.search(r"\b(by|per|grouped\s+by)\b", q):
        add("by/per", "operator", "GROUP_BY")
    if re.search(r"\b(top|most)\b", q):
        add("top/most", "operator", "TOP")

    # Domain entities (schema-level classes).
    cls_req = _find_class(index, "Requirement")
    cls_model = _find_class(index, "DesignModel")
    cls_test = _find_class(index, "VerificationTest", "TestCase", "Test")
    cls_link = _find_class(index, "Traceability_Link_Type")
    cls_scn = _find_class(index, "Verification_Validation_Scenario_Type", "VnVScenario")
    cls_manifest = _find_class(index, "P510_ManifestType")
    cls_org = _find_class(index, "Organization")

    if re.search(r"\b(requirement|requirements|reqs?|spec|specification)\b", q) and cls_req:
        add("requirement", "entity", _local_name(cls_req))
    if re.search(r"\b(model|models|design\s*model|physical\s*model)\b", q) and cls_model:
        add("model", "entity", _local_name(cls_model))
    if re.search(r"\b(test|tests|test\s*case|verification)\b", q) and cls_test:
        add("test", "entity", _local_name(cls_test))
    if re.search(r"\b(link|links|trace|traceability)\b", q) and cls_link:
        add("link", "entity", _local_name(cls_link))
    if re.search(r"\b(scenario|scenarios|vnv)\b", q) and cls_scn:
        add("scenario", "entity", _local_name(cls_scn))
    if re.search(r"\b(manifest)\b", q) and cls_manifest:
        add("manifest", "entity", _local_name(cls_manifest))
    if re.search(r"\b(supplier|provider|vendor|organization|org)\b", q) and cls_org:
        add("supplier/org", "entity", _local_name(cls_org))

    # Key schema predicates/attributes.
    pred_id = _find_pred(index, "Id")
    pred_ct = _find_pred(index, "ContentType")
    pred_desc = _find_pred(index, "Description")
    pred_approver = _find_pred(index, "Approver")
    pred_approval = _find_pred(index, "Approval_State")
    pred_maturity = _find_pred(index, "Maturity_State")
    pred_author_org = _find_pred(index, "Author_Organization")
    pred_subsystem = _find_pred(index, "subsystem")
    pred_verif_method = _find_pred(index, "verification_method")
    pred_ts_arch = _find_pred(index, "Timestamp_Archiving")
    pred_ts_plm = _find_pred(index, "Timestamp_PLM")

    pred_project_code = _find_pred(index, "project_code")
    pred_product = _find_pred(index, "product")
    pred_has_baseline = _find_pred(index, "hasBaseline")
    pred_baseline_name = _find_pred(index, "baseline_name")
    pred_baseline_id = _find_pred(index, "baseline_id")
    pred_created = _find_pred(index, "created")

    if pred_id and re.search(r"\b(id|identifier)\b", q):
        add("id", "attribute", _local_name(pred_id))
    if pred_ct and re.search(r"\b(content\s*type|contenttype|type)\b", q):
        add("contenttype", "attribute", _local_name(pred_ct))
    if pred_desc and re.search(r"\b(description|desc)\b", q):
        add("description", "attribute", _local_name(pred_desc))
    if pred_approver and re.search(r"\b(approver)\b", q):
        add("approver", "attribute", _local_name(pred_approver))
    if pred_approval and re.search(r"\b(approval|approved)\b", q):
        add("approval", "attribute", _local_name(pred_approval))
    if pred_maturity and re.search(r"\b(maturity)\b", q):
        add("maturity", "attribute", _local_name(pred_maturity))
    if pred_author_org and re.search(r"\b(author|authored|creator|created|written)\b", q):
        add("author_org", "attribute", _local_name(pred_author_org))
    if pred_subsystem and re.search(r"\b(subsystem)\b", q):
        add("subsystem", "attribute", _local_name(pred_subsystem))
    if pred_verif_method and re.search(r"\b(verification\s+method|method\s+of\s+verification)\b", q):
        add("verification_method", "attribute", _local_name(pred_verif_method))
    if (pred_ts_arch or pred_ts_plm) and re.search(r"\b(timestamp|timestamps)\b", q):
        add("timestamp", "attribute", "Timestamp_*")

    if pred_project_code and re.search(r"\b(project\s+code|project)\b", q):
        add("project code", "attribute", _local_name(pred_project_code))
    if pred_product and re.search(r"\b(product)\b", q):
        add("product", "attribute", _local_name(pred_product))
    if (pred_has_baseline or pred_baseline_name or pred_baseline_id) and re.search(r"\b(baseline|release|version)\b", q):
        add("baseline", "attribute", "baseline_*")
    if pred_created and re.search(r"\b(created|creation\s+date|date)\b", q):
        add("created", "attribute", _local_name(pred_created))

    # Literals commonly used in P510 synthetic content types.
    if re.search(r"\bphysical\s+model\b", q):
        add("Physical Model", "literal", "Physical Model")
    if re.search(r"\btest\s+case\b", q):
        add("Test Case", "literal", "Test Case")
    if re.search(r"\bdocument(s)?\b", q):
        add("Document", "literal", "Document")
    if re.search(r"\bapproved\b", q):
        add("Approved", "literal", "Approved")

    supp = _extract_supplier_name_literal(question)
    if supp:
        add(supp, "literal", supp)

    return GroundingResult(normalized=q, tokens_sig=tokens_sig, hits=hits)


def _compile_group_count_by_attr(
    *,
    graph: Graph,
    index: SchemaIndex,
    subject_class: str,
    subject_var: str,
    attr_pred: str,
    attr_var: str,
    count_var: str = "?num",
    order_desc: bool = True,
    limit: int = 200,
) -> str:
    pfx = _prefix_lines(index)
    order = f"ORDER BY {'DESC' if order_desc else ''}({count_var})".strip()
    sparql = (
        f"{pfx}\n"
        f"SELECT {attr_var} (COUNT(DISTINCT {subject_var}) AS {count_var})\n"
        "WHERE {\n"
        f"  {subject_var} a <{subject_class}> .\n"
        f"  OPTIONAL {{ {subject_var} <{attr_pred}> {attr_var} }}\n"
        "}\n"
        f"GROUP BY {attr_var}\n"
        f"{order}"
    )
    sparql = ensure_limit(sparql, limit)
    check_no_invented_terms(graph, sparql)
    validate_and_run(graph, sparql)
    return sparql


def _compositional_generate(
    graph: Graph,
    question: str,
    config: GenerationConfig,
    synonyms: SynonymMap | None,
    index: SchemaIndex,
) -> GenerationResult | None:
    """Schema-driven compositional generator.

    It tries to build SPARQL by combining:
    - a source entity class (Requirement/DesignModel/VerificationTest/Organization/link node)
    - a relation predicate (Satisfied_by/Verified_by/Validated_by/uses)
    - an optional target entity class (DesignModel/VerificationTest/Document)
    - optional negation (missing/without/no/do not have)

    If it cannot confidently build a query, it returns None and the caller can fallback.
    """

    q_raw = _normalize_nl_basic(question)
    qn = _normalize_nl(question, synonyms=synonyms)
    tokens_raw = set(q_raw.split())
    tokens = set(qn.split())
    tokens_sig = _token_set(question, synonyms=synonyms)

    grounding = _ground_question(question, qn, tokens_sig, index=index)
    explain: list[str] = grounding.explain_lines()

    def has_any(options: set[str]) -> bool:
        return bool(tokens_sig & options)

    has_group_intent = bool(re.search(r"\b(per|by|each)\b", qn) or "distribution" in tokens_sig or "group" in qn)

    # Determine query form.
    is_count = bool(
        re.search(
            r"\b(how\s+many|count(\s+of)?|number\s+of|total\s+number\s+of|quantity\s+of|amount\s+of)\b",
            qn,
        )
        or (tokens_sig & {"count", "number", "total", "quantity", "amount"})
    )

    if (
        ("supplier" in tokens_sig or "provider" in tokens_sig)
        and ("model" in tokens_sig or "designmodel" in tokens_sig or "physicalmodel" in tokens_sig)
        and (is_count or "count" in tokens_sig)
        and ("provide" in tokens_sig or "provided" in tokens_sig)
    ):
        has_group_intent = True

    is_list = bool(
        any(t in tokens for t in {"list", "show", "display", "give", "return", "which", "what"})
        or qn.startswith("list ")
        or qn.startswith("show ")
    )
    if is_count:
        explain.append("query_form: COUNT")
    elif is_list:
        explain.append("query_form: LIST")

    wants_missing = bool(
        (tokens_sig & {"without", "missing", "lack", "lacking", "absent", "none"})
        or any(t in tokens for t in {"without", "missing", "lack", "lacking", "absent", "none", "no"})
        or "no" in tokens_raw
        or re.search(r"\b(do\s+not\s+have|does\s+not\s+have|not\s+having)\b", qn)
        or re.search(r"\bneither\b", qn)
        or re.search(r"\bnot\s+(verified|validated|approved|tested|linked|associated|have|has)\b", qn)
    )
    if wants_missing:
        explain.append("constraint: missing/negation")

    # Defer to specialized logic for patterns that require aggregation or multi-hop semantics.
    is_duplicate = bool(
        (tokens_sig & {"duplicate", "duplicated", "repeat", "repeated", "redundant"})
        or re.search(r"\b(duplicate|duplicates|repeated|same\s+link|same\s+trace)\b", qn)
    )
    if is_duplicate or ("audit" in tokens):
        return None

    if re.search(r"\bend\s*-?\s*to\s*-?\s*end\b", qn) or "endtoend" in tokens_sig:
        return None

    # Also defer end-to-end style phrasing without the literal "end-to-end" token.
    if (
        "traceability" in tokens_sig
        and "requirement" in tokens_sig
        and ("test" in tokens_sig or "testcase" in tokens_sig)
    ):
        return None
    if "chain" in tokens_sig and "requirement" in tokens_sig and ("test" in tokens_sig or "testcase" in tokens_sig):
        return None

    # Defer to specialized operators for audit-style data quality checks, manifest summaries,
    # and GROUP BY/HAVING style questions (compositional generator is intentionally simple).
    if tokens_sig & {
        "timestamp",
        "description",
        "approval",
        "approver",
        "approved",
        "author",
        "maturity",
        "subsystem",
        "verification_method",
        "method",
        "scenario",
        "vnv",
        "baseline",
        "project",
        "environment",
        "tool",
        "os",
        "format",
        "plm",
    }:
        return None
    if ("contenttype" in tokens or "content type" in qn or "contenttype" in qn) and re.search(
        r"\b(mismatch(?:es)?|inconsistent|incoherent|differ|differs|different|does\s+not\s+match|doesn't\s+match|not\s+match)\b",
        qn,
    ):
        return None
    if ("supplier" in tokens_sig or "provider" in tokens_sig) and (
        "per" in tokens
        or "by" in tokens
        or "group" in tokens
        or re.search(r"\bnumber\s+of\b", qn)
        or (has_group_intent and ("model" in tokens_sig or "designmodel" in tokens_sig or "physicalmodel" in tokens_sig))
    ):
        return None

    # Defer common group-by requirements questions to specialized dynamic operators.
    if has_group_intent and "requirement" in tokens_sig and (
        "author" in tokens_sig
        or "organization" in tokens_sig
        or "method" in tokens_sig
        or "verified" in tokens_sig
        or "verify" in tokens_sig
        or "verification" in tokens_sig
        or re.search(r"\bverification\s+method\b", q_raw, flags=re.IGNORECASE)
    ):
        return None

    # Resolve common schema terms.
    cls_req = _find_class(index, "Requirement")
    cls_model = _find_class(index, "DesignModel")
    cls_test = _find_class(index, "VerificationTest", "TestCase", "Test")
    cls_link = _find_class(index, "Traceability_Link_Type")
    cls_org = _find_class(index, "Organization")

    pred_id = _find_pred(index, "Id")
    pred_link = _find_pred(index, "Link")
    pred_ct = _find_pred(index, "ContentType")

    pred_satisfied = _find_pred(index, "Satisfied_by")
    pred_verified = _find_pred(index, "Verified_by")
    pred_validated = _find_pred(index, "Validated_by")
    pred_uses = _find_pred(index, "uses")

    # Concept detection (entity-ish tokens). Keep permissive.
    want_req = has_any({"requirement", "req", "spec", "specification"})
    want_model = has_any({"model", "designmodel", "physicalmodel"})
    want_test = has_any({"test", "testcase", "verification", "verify"})
    want_supplier = has_any({"supplier", "provider", "vendor", "organization", "org", "owner", "responsible"})
    want_link = has_any({"link", "trace", "traceability", "relationship", "relation"})
    want_document = has_any({"document", "doc", "documentation"})

    # If we have an explicit organization literal and the question hints at links/traces, defer to
    # the specialized authored-links query which binds Author_Organization.
    if _extract_author_org_literal(question) and re.search(r"\b(link|links|trace|traceability)\b", qn):
        return None

    # If the question contains a concrete supplier name ("Supplier 03"), defer to the
    # specialized supplier operator (providedBy + foaf:name filtering).
    if _extract_supplier_name_literal(question):
        return None

    # Relation detection (verb-ish tokens). Try to pick one relation.
    rel_pred: str | None = None
    if has_any({"use", "used", "using", "reference", "referenced", "cite", "cited"}) or (
        want_document and ("use" in tokens_sig or "used" in tokens_sig)
    ):
        rel_pred = pred_uses
        explain.append("relation: uses")
    elif has_any({"verify", "verification", "test", "testcase"}):
        rel_pred = pred_verified
        explain.append("relation: Verified_by")
    elif has_any({"validate", "validation", "evidence"}):
        rel_pred = pred_validated
        explain.append("relation: Validated_by")
    elif has_any({"satisfy", "satisfied"}) or (want_model and want_req):
        rel_pred = pred_satisfied
        explain.append("relation: Satisfied_by")

    # Choose source and target classes.
    src_class: str | None = None
    src_var = "?src"
    if want_req and cls_req:
        src_class = cls_req
        src_var = "?req"
        explain.append("source_class: Requirement")
    elif want_model and cls_model:
        src_class = cls_model
        src_var = "?m"
        explain.append("source_class: DesignModel")
    elif want_test and cls_test:
        src_class = cls_test
        src_var = "?t"
        explain.append("source_class: VerificationTest")
    elif want_supplier and cls_org:
        src_class = cls_org
        src_var = "?prov"
        explain.append("source_class: Organization")
    elif want_link and cls_link:
        src_class = cls_link
        src_var = "?l"
        explain.append("source_class: Traceability_Link_Type")

    target_class: str | None = None
    if rel_pred in {pred_verified, pred_validated} and want_test and cls_test:
        target_class = cls_test
        explain.append("target_class: VerificationTest")
    elif rel_pred == pred_satisfied and want_model and cls_model:
        target_class = cls_model
        explain.append("target_class: DesignModel")

    # ContentType constraint hint (these appear in your reference queries).
    # When the user explicitly says "physical model" or "test case" or "document",
    # restrict the link-node ContentType accordingly.
    ct_filter: str | None = None
    if "physical" in tokens_sig and "model" in tokens_sig:
        ct_filter = "Physical Model"
        explain.append("linknode_contenttype: Physical Model")
    elif "test" in tokens_sig and "case" in tokens_sig:
        ct_filter = "Test Case"
        explain.append("linknode_contenttype: Test Case")
    elif want_document:
        ct_filter = "Document"
        explain.append("linknode_contenttype: Document")

    # If we can't even decide a source entity, bail.
    if not src_class:
        return None

    # If the user asked for links and also an org literal (Supplier 03 / University), let the existing
    # specialized block handle it; it does a better job with Author_Organization.
    if want_link and _extract_author_org_literal(question):
        return None

    pfx = _prefix_lines(index)

    # Build base pattern.
    where_lines: list[str] = [f"  {src_var} a <{src_class}> ."]
    opt_id = ""
    if pred_id and src_var not in {"?l"}:
        opt_id = f"OPTIONAL {{ {src_var} <{pred_id}> ?id . }}"

    # Relationship pattern using link-nodes.
    if rel_pred and pred_link:
        inner: list[str] = [
            f"    {src_var} <{rel_pred}> ?ln .",
            f"    ?ln <{pred_link}> ?target .",
        ]
        if cls_link:
            inner.insert(1, f"    ?ln a <{cls_link}> .")
        if ct_filter and pred_ct:
            inner.insert(2 if cls_link else 1, f"    ?ln <{pred_ct}> \"{ct_filter}\" .")
        if target_class:
            inner.append(f"    ?target a <{target_class}> .")

        if wants_missing:
            where_lines.append("  FILTER NOT EXISTS {")
            where_lines.extend(inner)
            where_lines.append("  }")
        else:
            where_lines.extend(["  " + l.strip() for l in inner])

    # Projection.
    if is_count:
        select_line = f"SELECT (COUNT(DISTINCT {src_var}) AS ?count) WHERE {{"
        sparql = f"{pfx}\n{select_line}\n" + "\n".join(where_lines) + "\n}"
    else:
        # Default list: prefer ?id if available, otherwise list the resource.
        if opt_id:
            select_line = "SELECT DISTINCT ?id " + src_var + " WHERE {"
            where = "\n".join(where_lines + ([f"  {opt_id}"] if opt_id else []))
            sparql = f"{pfx}\n{select_line}\n{where}\n}}\nORDER BY ?id"
        else:
            select_line = "SELECT DISTINCT " + src_var + " WHERE {"
            sparql = f"{pfx}\n{select_line}\n" + "\n".join(where_lines) + "\n}\nORDER BY " + src_var

    sparql = ensure_limit(sparql, config.limit)
    check_no_invented_terms(graph, sparql)
    validate_and_run(graph, sparql)
    return GenerationResult(
        sparql=sparql,
        attempts=1,
        matched_id="dynamic",
        matched_nl=None,
        match_score=None,
        explanation=explain,
    )


def _dynamic_generate(graph: Graph, question: str, config: GenerationConfig, synonyms: SynonymMap | None) -> GenerationResult:
    index = _build_schema_index(graph)

    # First try a schema-driven compositional build (no fixed per-question intents).
    try:
        r = _compositional_generate(graph, question, config=config, synonyms=synonyms, index=index)
        if r is not None:
            return r
    except Exception:
        # Fall back to the more specialized dynamic patterns below.
        pass
    q_raw = _normalize_nl_basic(question)
    tokens_raw = set(q_raw.split())

    qn = _normalize_nl(question, synonyms=synonyms)
    tokens = set(qn.split())
    # Significant tokens: normalized, stopwords removed, cheap singularization applied.
    tokens_sig = _token_set(question, synonyms=synonyms)

    grounding = _ground_question(question, qn, tokens_sig, index=index)

    def has_any(token_set: set[str], options: set[str]) -> bool:
        return bool(token_set & options)

    # Intent detection (kept for backward compatibility; grounding is the primary trace source).
    # Count phrasing is varied: "how many", "what is the number of", "total number of", etc.
    is_count_phrase = bool(
        re.search(
            r"\b(how\s+many|count(\s+of)?|number\s+of|total\s+number\s+of|quantity\s+of|amount\s+of)\b",
            qn,
        )
        or has_any(tokens_sig, {"count", "number", "total", "quantity", "amount"})
    )
    is_count = is_count_phrase
    is_percent = bool(re.search(r"\b(percent|percentage|ratio)\b", qn) or "percentage" in tokens_sig)

    has_group_intent = bool(re.search(r"\b(per|by|each)\b", qn) or "distribution" in tokens_sig or "group" in qn)

    # Core domain terms (mapped to schema local names)
    want_req = has_any(tokens_sig, {"requirement", "req", "spec", "specification"})
    want_model = has_any(tokens_sig, {"model", "designmodel", "physicalmodel"})
    want_test = has_any(tokens_sig, {"test", "testcase", "verification", "verify"})
    want_supplier = has_any(tokens_sig, {"supplier", "provider", "vendor", "organization", "org", "owner", "responsible"})
    want_link = has_any(tokens_sig, {"link", "trace", "traceability", "relationship", "relation"})
    want_document = has_any(tokens_sig, {"document", "doc", "documentation"})

    if want_supplier and want_model and is_count_phrase and ("provide" in tokens_sig or "provided" in tokens_sig):
        has_group_intent = True
    if has_group_intent:
        # Prefer GROUP BY operators over a global COUNT.
        is_count = False

    want_author = bool(
        has_any(tokens_sig, {"author", "authored", "creator", "created", "written", "owner"})
        or re.search(r"\b(authored|created|written)\s+by\b", qn)
    )

    is_audit = bool(has_any(tokens_sig, {"audit", "check", "detect", "validate"}))
    is_duplicate = bool(
        has_any(tokens_sig, {"duplicate", "duplicated", "repeat", "repeated", "redundant"})
        or re.search(r"\b(same\s+link|same\s+trace|repeated\s+link|repeated\s+trace)\b", qn)
    )
    wants_missing = bool(
        has_any(tokens_sig, {"without", "missing", "lack", "lacking", "absent", "none"})
        or any(t in tokens for t in {"without", "missing", "lack", "lacking", "absent", "none", "no"})
        or "no" in tokens_raw
        or re.search(r"\b(do\s+not\s+have|does\s+not\s+have|not\s+having)\b", qn)
        or re.search(r"\bneither\b", qn)
        or re.search(r"\bnot\s+(verified|validated|approved|tested|linked|associated|have|has)\b", qn)
    )

    is_approved_state = bool(
        re.search(r"\bapproved\b", q_raw, flags=re.IGNORECASE)
        or re.search(r"\bapproval\b", q_raw, flags=re.IGNORECASE)
        or has_any(tokens_sig, {"approval", "governance"})
        or "approval" in qn
        or "approval state" in qn
    )

    # Resolve common classes/predicates from the real graph
    cls_req = _find_class(index, "Requirement")
    cls_model = _find_class(index, "DesignModel")
    cls_test = _find_class(index, "VerificationTest", "TestCase", "Test")
    cls_link = _find_class(index, "Traceability_Link_Type")
    cls_manifest = _find_class(index, "P510_ManifestType")
    cls_scn = _find_class(index, "Verification_Validation_Scenario_Type", "Verification_Validation_Scenario_Type")
    cls_org = _find_class(index, "Organization")  # foaf:Organization

    pred_id = _find_pred(index, "Id")
    pred_link = _find_pred(index, "Link")
    pred_ct = _find_pred(index, "ContentType")
    pred_desc = _find_pred(index, "Description")
    pred_ts_arch = _find_pred(index, "Timestamp_Archiving")
    pred_ts_plm = _find_pred(index, "Timestamp_PLM")
    pred_approver = _find_pred(index, "Approver")
    pred_approval = _find_pred(index, "Approval_State")
    pred_maturity = _find_pred(index, "Maturity_State")
    pred_subsystem = _find_pred(index, "subsystem")
    pred_verif_method = _find_pred(index, "verification_method")

    pred_author_org = _find_pred(index, "Author_Organization")

    pred_satisfied = _find_pred(index, "Satisfied_by")
    pred_verified = _find_pred(index, "Verified_by")
    pred_validated = _find_pred(index, "Validated_by")
    pred_uses = _find_pred(index, "uses")

    pred_provided_by = _find_pred(index, "providedBy", "provided_by", "providedby")

    pred_manifest_dev = _find_pred(index, "has_RequirementsDevStructure")
    pred_manifest_plm = _find_pred(index, "has_GeneralPLMInfo")
    pred_manifest_vnv = _find_pred(index, "has_Requirements_Verification_Validation")
    pred_vnv_scenario = _find_pred(index, "Scenario")
    pred_ver_level = _find_pred(index, "Verification_Credibility_Level")
    pred_val_level = _find_pred(index, "Validation_Credibility_Level")
    pred_created_on = _find_pred(index, "Created_on")
    pred_org = _find_pred(index, "Organization")
    pred_model_purpose = _find_pred(index, "Model_Purpose")
    pred_model_objective = _find_pred(index, "Model_Objective")
    pred_version_identifier = _find_pred(index, "Version_identifier")
    pred_dev_tool_name = _find_pred(index, "DevTool_Name")
    pred_dev_tool_ver = _find_pred(index, "DevTool_Version")
    pred_dev_os_name = _find_pred(index, "DevOS_Name")
    pred_dev_os_ver = _find_pred(index, "DevOS_Version")
    pred_format_name = _find_pred(index, "Format_name")
    pred_format_ver = _find_pred(index, "Format_version")
    pred_req_authoring = _find_pred(index, "RequirementAuthoringTechnique")
    pred_language = _find_pred(index, "Language")

    pred_name = _find_pred(index, "name")  # foaf:name

    pred_project_code = _find_pred(index, "project_code")
    pred_product = _find_pred(index, "product")
    pred_has_baseline = _find_pred(index, "hasBaseline")
    pred_baseline_name = _find_pred(index, "baseline_name")
    pred_baseline_id = _find_pred(index, "baseline_id")
    pred_baseline_created = _find_pred(index, "created")

    def _base_explain() -> list[str]:
        return grounding.explain_lines()

    def _term(uri: str | None) -> str:
        if not uri:
            return "<missing>"
        return _local_name(uri)

    # ---------------------------------------------------------------------
    # Operator registry (implemented as ordered branches for clarity)
    # ---------------------------------------------------------------------

    # Link quality: missing timestamps
    if want_link and ("timestamp" in tokens or "timestamp" in qn) and wants_missing:
        if not cls_link:
            raise ValueError("Dynamic generator: could not find Traceability_Link_Type class.")
        if not (pred_ts_arch and pred_ts_plm):
            raise ValueError("Dynamic generator: graph missing Timestamp_Archiving/Timestamp_PLM predicates.")
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?link WHERE {\n"
            f"  ?link a <{cls_link}> .\n"
            "  FILTER(\n"
            f"    !EXISTS {{ ?link <{pred_ts_arch}> ?ta }} ||\n"
            f"    !EXISTS {{ ?link <{pred_ts_plm}> ?tp }}\n"
            "  )\n"
            "}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: LINKS_MISSING_TIMESTAMP")
        explain.append("source_class: " + _term(cls_link))
        explain.append("missing: Timestamp_Archiving or Timestamp_PLM")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Link quality: missing description
    if want_link and ("description" in tokens or "description" in qn or "desc" in tokens) and wants_missing:
        if not cls_link:
            raise ValueError("Dynamic generator: could not find Traceability_Link_Type class.")
        if not pred_desc:
            raise ValueError("Dynamic generator: graph missing Description predicate.")
        pfx = _prefix_lines(index)
        opt_ct = f"OPTIONAL {{ ?link <{pred_ct}> ?ct . }}" if pred_ct else ""
        sparql = (
            f"{pfx}\n"
            "SELECT ?link ?ct WHERE {\n"
            f"  ?link a <{cls_link}> .\n"
            f"  {opt_ct}\n"
            f"  FILTER NOT EXISTS {{ ?link <{pred_desc}> ?d }}\n"
            "}\nORDER BY ?ct"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: LINKS_WITHOUT_DESCRIPTION")
        explain.append("source_class: " + _term(cls_link))
        explain.append("missing: Description")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Link quality: ContentType mismatch (link CT vs target CT)
    if want_link and (
        re.search(r"\b(mismatch(?:es)?|inconsistent|incoherent|differ|differs|different|does\s+not\s+match|doesn't\s+match|not\s+match)\b", qn)
        and ("contenttype" in tokens or "content type" in qn or "contenttype" in qn)
    ):
        if not cls_link:
            raise ValueError("Dynamic generator: could not find Traceability_Link_Type class.")
        if not (pred_ct and pred_link):
            raise ValueError("Dynamic generator: graph missing ContentType/Link predicates.")
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?link ?linkCT ?target ?targetCT WHERE {\n"
            f"  ?link a <{cls_link}> ; <{pred_ct}> ?linkCT ; <{pred_link}> ?target .\n"
            f"  OPTIONAL {{ ?target <{pred_ct}> ?targetCT }}\n"
            "  FILTER(BOUND(?targetCT) && ?linkCT != ?targetCT)\n"
            "}\nORDER BY ?linkCT"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: LINK_CONTENTTYPE_MISMATCH")
        explain.append("source_class: " + _term(cls_link))
        explain.append("compare: link.ContentType vs target.ContentType")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Special: duplicate traces audit ("audit" optional; duplicates imply an audit-style query)
    if is_duplicate and (want_link or "trace" in tokens or "traceability" in tokens or "traceability" in qn):
        preds = [p for p in [pred_satisfied, pred_verified, pred_validated, pred_uses] if p]
        if not preds:
            raise ValueError("Dynamic generator: could not find traceability predicates in the graph.")
        pfx = _prefix_lines(index)
        values = " ".join([f"<{p}>" for p in preds])
        body = (
            "SELECT ?src ?pred ?target (COUNT(DISTINCT ?link) AS ?numLinks) WHERE {\n"
            f"  VALUES ?pred {{ {values} }}\n"
            "  ?src ?pred ?link .\n"
        )
        if pred_link:
            body += f"  ?link <{pred_link}> ?target .\n"
        else:
            body += "  ?link ?p2 ?target .\n"

        sparql = (
            f"{pfx}\n"
            f"{body}"
            "}\nGROUP BY ?src ?pred ?target\nHAVING(COUNT(DISTINCT ?link) > 1)\nORDER BY DESC(?numLinks)"
        )

        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: DUPLICATE_TRACES_AUDIT")
        explain.append("pattern: VALUES ?pred {Satisfied_by Verified_by Validated_by uses} + GROUP BY/HAVING")
        explain.append("uses_predicates: " + ", ".join([_term(p) for p in preds]))
        explain.append("link_target: " + _term(pred_link))
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # Requirements missing a physical model (Satisfied_by link-node of ContentType="Physical Model")
    if (
        want_req
        and wants_missing
        and (want_model or "physical" in tokens_sig or "model" in tokens_sig)
        and not want_test
        and not is_approved_state
        and "approver" not in tokens_sig
        and "approval" not in tokens_sig
    ):
        if not (cls_req and pred_id and pred_satisfied and pred_link and pred_ct):
            raise ValueError("Dynamic generator: graph missing required schema terms for 'requirements without physical model'.")
        pfx = _prefix_lines(index)
        select_vars = "?req ?id" + (" ?desc" if pred_desc else "")
        where_lines: list[str] = [
            f"  ?req a <{cls_req}> ; <{pred_id}> ?id .",
        ]
        if pred_desc:
            where_lines.append(f"  OPTIONAL {{ ?req <{pred_desc}> ?desc }}")
        where_lines.extend(
            [
                "  FILTER NOT EXISTS {",
                f"    ?req <{pred_satisfied}> ?link .",
                f"    ?link <{pred_link}> ?modelo .",
                f"    ?link <{pred_ct}> \"Physical Model\" .",
                "  }",
            ]
        )
        sparql = f"{pfx}\nSELECT {select_vars} WHERE {{\n" + "\n".join(where_lines) + "\n}"
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_WITHOUT_PHYSICAL_MODEL")
        explain.append("source_class: " + _term(cls_req))
        explain.append("missing: Satisfied_by -> link(ContentType=Physical Model) -> model")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Percentage of requirements with a model (ratio query)
    if want_req and is_percent:
        if not (cls_req and pred_satisfied and pred_link and pred_ct):
            raise ValueError("Dynamic generator: graph missing required schema terms for 'percentage requirements with model'.")
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT (100.0 * COUNT(DISTINCT ?reqWithModel) / COUNT(DISTINCT ?req) AS ?percentage)\n"
            "WHERE {\n"
            f"  ?req a <{cls_req}> .\n"
            "  OPTIONAL {\n"
            f"    ?req <{pred_satisfied}> ?link .\n"
            f"    ?link <{pred_ct}> \"Physical Model\" ; <{pred_link}> ?modelo .\n"
            "    BIND(?req AS ?reqWithModel)\n"
            "  }\n"
            "}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_PERCENT_WITH_MODEL")
        explain.append("ratio: COUNT(reqWithModel)/COUNT(req)")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Count queries
    if is_count:
        pfx = _prefix_lines(index)
        explain = _base_explain()
        explain.append("operator: COUNT_ENTITIES")
        if want_supplier and cls_org:
            explain.append("entity_class: " + _term(cls_org))
            sparql = (
                f"{pfx}\n"
                f"SELECT (COUNT(DISTINCT ?prov) AS ?count) WHERE {{ ?prov a <{cls_org}> . }}"
            )
        elif want_req and cls_req:
            explain.append("entity_class: " + _term(cls_req))
            sparql = (
                f"{pfx}\n"
                f"SELECT (COUNT(DISTINCT ?req) AS ?count) WHERE {{ ?req a <{cls_req}> . }}"
            )
        elif want_model and cls_model:
            explain.append("entity_class: " + _term(cls_model))
            sparql = (
                f"{pfx}\n"
                f"SELECT (COUNT(DISTINCT ?m) AS ?count) WHERE {{ ?m a <{cls_model}> . }}"
            )
        elif want_test and cls_test:
            explain.append("entity_class: " + _term(cls_test))
            sparql = (
                f"{pfx}\n"
                f"SELECT (COUNT(DISTINCT ?t) AS ?count) WHERE {{ ?t a <{cls_test}> . }}"
            )
        elif want_link and cls_link:
            explain.append("entity_class: " + _term(cls_link))
            sparql = (
                f"{pfx}\n"
                f"SELECT (COUNT(DISTINCT ?l) AS ?count) WHERE {{ ?l a <{cls_link}> . }}"
            )
        else:
            raise ValueError(
                "Dynamic generator: could not infer what to count (try 'how many suppliers/requirements/models/tests')."
            )

        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # Requirements grouped by maturity / author org / subsystem / verification method
    if want_req and ("maturity" in tokens_sig) and cls_req and pred_maturity:
        sparql = _compile_group_count_by_attr(
            graph=graph,
            index=index,
            subject_class=cls_req,
            subject_var="?req",
            attr_pred=pred_maturity,
            attr_var="?maturity",
            count_var="?num",
            limit=config.limit,
        )
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_BY_MATURITY")
        explain.append("group_by: Maturity_State")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if (
        want_req
        and has_group_intent
        and (
            "author" in tokens_sig
            or "authored" in tokens_sig
            or "creator" in tokens_sig
            or "owner" in tokens_sig
            or "author_organization" in tokens_sig
            or "authororganization" in tokens_sig
            or "author organization" in qn
        )
        and cls_req
        and pred_author_org
    ):
        sparql = _compile_group_count_by_attr(
            graph=graph,
            index=index,
            subject_class=cls_req,
            subject_var="?req",
            attr_pred=pred_author_org,
            attr_var="?org",
            count_var="?numRequisitos",
            limit=config.limit,
        )
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_BY_AUTHOR_ORG")
        explain.append("group_by: Author_Organization")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if want_req and ("subsystem" in tokens_sig) and cls_req and pred_subsystem:
        sparql = _compile_group_count_by_attr(
            graph=graph,
            index=index,
            subject_class=cls_req,
            subject_var="?req",
            attr_pred=pred_subsystem,
            attr_var="?subsystem",
            count_var="?numRequisitos",
            limit=config.limit,
        )
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_BY_SUBSYSTEM")
        explain.append("group_by: ex:subsystem")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if (
        want_req
        and has_group_intent
        and cls_req
        and pred_verif_method
        and (
            "verification_method" in tokens_sig
            or ("verification" in tokens_sig and "method" in tokens_sig)
            or "verified" in tokens_sig
            or "verify" in tokens_sig
            or re.search(r"\bhow\b.*\bverified\b", qn)
            or re.search(r"\bverification\s+method\b", q_raw, flags=re.IGNORECASE)
        )
    ):
        sparql = _compile_group_count_by_attr(
            graph=graph,
            index=index,
            subject_class=cls_req,
            subject_var="?req",
            attr_pred=pred_verif_method,
            attr_var="?method",
            count_var="?numRequisitos",
            limit=config.limit,
        )
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_BY_VERIFICATION_METHOD")
        explain.append("group_by: ex:verification_method")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Missing tests for models
    if want_model and wants_missing and want_test and not want_req:
        if not (cls_model and pred_id and pred_verified and pred_link):
            raise ValueError("Dynamic generator: graph missing required schema terms for 'models without tests'.")
        # Optional: confirm tests class exists, otherwise just check link existence.
        test_type = f"?t a <{cls_test}> ." if cls_test else ""
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?id WHERE {\n"
            f"  ?m a <{cls_model}> ; <{pred_id}> ?id .\n"
            "  FILTER NOT EXISTS {\n"
            f"    ?m <{pred_verified}> ?vl .\n"
            f"    ?vl <{pred_link}> ?t .\n"
            f"    {test_type}\n"
            "  }\n"
            "}\nORDER BY ?id"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: MODELS_WITHOUT_TESTS")
        explain.append("source_class: " + _term(cls_model))
        explain.append("relation: " + _term(pred_verified) + " / link-node pattern")
        explain.append("filter: NOT EXISTS verification link")
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # Models without supplier/provider
    if want_model and wants_missing and ("supplier" in tokens_sig or "provider" in tokens_sig or "vendor" in tokens_sig) and pred_provided_by:
        if not (cls_model and pred_id and pred_ct):
            raise ValueError("Dynamic generator: graph missing required schema terms for 'models without provider'.")
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?modelo ?id WHERE {\n"
            f"  ?modelo a <{cls_model}> ; <{pred_id}> ?id ; <{pred_ct}> \"Physical Model\" .\n"
            f"  FILTER NOT EXISTS {{ ?modelo <{pred_provided_by}> ?prov }}\n"
            "}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: MODELS_WITHOUT_PROVIDER")
        explain.append("missing: providedBy")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Models grouped by approval state
    if (
        want_model
        and has_group_intent
        and ("approval" in tokens_sig or "approved" in tokens_sig)
        and cls_model
        and pred_approval
        and not wants_missing
        and "approver" not in tokens_sig
    ):
        sparql = _compile_group_count_by_attr(
            graph=graph,
            index=index,
            subject_class=cls_model,
            subject_var="?modelo",
            attr_pred=pred_approval,
            attr_var="?approval",
            count_var="?numModelos",
            limit=config.limit,
        )
        explain = _base_explain()
        explain.append("operator: MODELS_BY_APPROVAL_STATE")
        explain.append("group_by: Approval_State")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Used documents (manifest dev structure -> uses -> link-node contenttype Document)
    if want_document and (
        has_any(tokens_sig, {"use", "used", "using", "reference", "referenced", "cite", "cited"})
        or "used" in tokens
        or "uses" in tokens
        or "used" in tokens_raw
        or "uses" in tokens_raw
        or "referenced" in tokens_raw
        or re.search(r"\b(used\s+by|referenced\s+by|depends\s+on)\b", qn)
    ):
        pfx = _prefix_lines(index)
        if cls_manifest and pred_manifest_dev and pred_uses and pred_link and cls_link and pred_ct:
            opt_desc = f"OPTIONAL {{ ?doc <{pred_desc}> ?desc }}" if pred_desc else ""
            sparql = (
                f"{pfx}\n"
                "SELECT ?doc ?desc WHERE {\n"
                f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_dev}> ?dev .\n"
                f"  ?dev <{pred_uses}> ?link .\n"
                f"  ?link a <{cls_link}> ; <{pred_ct}> \"Document\" ; <{pred_link}> ?doc .\n"
                f"  {opt_desc}\n"
                "}"
            )
        else:
            # Fallback: generic uses targets
            if not (pred_uses and pred_link):
                raise ValueError("Dynamic generator: graph missing required schema terms for 'used documents'.")
            sparql = (
                f"{pfx}\n"
                "SELECT DISTINCT ?doc WHERE {\n"
                f"  ?src <{pred_uses}> ?ul .\n"
                f"  ?ul <{pred_link}> ?doc .\n"
                "}\nORDER BY ?doc"
            )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: USED_DOCUMENTS")
        explain.append("relation: " + _term(pred_uses) + " / link-node pattern")
        explain.append("target: Link -> ?doc")
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # Requirements without approver
    if (
        want_req
        and wants_missing
        and not is_approved_state
        and ("approver" in tokens_sig or "approver" in tokens)
        and cls_req
        and pred_approver
    ):
        if not pred_id:
            raise ValueError("Dynamic generator: graph missing Id predicate for requirements.")
        pfx = _prefix_lines(index)
        opt_state = f"OPTIONAL {{ ?req <{pred_approval}> ?state }}" if pred_approval else ""
        sparql = (
            f"{pfx}\n"
            "SELECT ?req ?id ?state WHERE {\n"
            f"  ?req a <{cls_req}> ; <{pred_id}> ?id .\n"
            f"  {opt_state}\n"
            f"  FILTER NOT EXISTS {{ ?req <{pred_approver}> ?a }}\n"
            "}\nORDER BY ?id"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_WITHOUT_APPROVER")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Approved but without approver (requirements + models)
    if is_approved_state and wants_missing and ("approver" in tokens_sig or "approver" in tokens) and pred_approver and pred_approval:
        if not pred_id:
            raise ValueError("Dynamic generator: graph missing Id predicate.")
        if not (cls_req and cls_model):
            raise ValueError("Dynamic generator: graph missing Requirement/DesignModel classes.")
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?entity ?id ?type WHERE {\n"
            "  {\n"
            f"    ?entity a <{cls_req}> ; <{pred_id}> ?id ; <{pred_approval}> \"Approved\" .\n"
            "    BIND(\"Requirement\" AS ?type)\n"
            "  }\n"
            "  UNION\n"
            "  {\n"
            f"    ?entity a <{cls_model}> ; <{pred_id}> ?id ; <{pred_approval}> \"Approved\" .\n"
            "    BIND(\"DesignModel\" AS ?type)\n"
            "  }\n"
            f"  FILTER NOT EXISTS {{ ?entity <{pred_approver}> ?a }}\n"
            "}\nORDER BY ?type ?id"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: APPROVED_WITHOUT_APPROVER")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Supplier rollups: models per supplier / tests per supplier / top suppliers with models w/o tests
    supplier_name = _extract_supplier_name_literal(question)

    # Parameterized: list models provided by a given supplier (Supplier 03)
    if supplier_name and pred_provided_by and cls_model and pred_id and pred_name:
        pfx = _prefix_lines(index)

        # If the question explicitly mentions physical models (or got normalized that way), keep the ContentType constraint.
        is_physical = bool(pred_ct and ("physical" in tokens_sig or "physical model" in qn or "physicalmodel" in tokens_sig))

        where_lines: list[str] = [
            f"  ?modelo a <{cls_model}> ; <{pred_id}> ?id ; <{pred_provided_by}> ?prov .",
        ]
        if is_physical and pred_ct:
            where_lines.append(f"  ?modelo <{pred_ct}> \"Physical Model\" .")
        where_lines.extend(
            [
                f"  ?prov <{pred_name}> ?provName .",
                f"  FILTER(LCASE(STR(?provName)) = LCASE(\"{supplier_name}\"))",
            ]
        )

        sparql = (
            f"{pfx}\n"
            "SELECT ?modelo ?id ?provName WHERE {\n"
            + "\n".join(where_lines)
            + "\n}\nORDER BY ?id"
        )

        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: MODELS_FOR_SUPPLIER")
        explain.append(f"supplier: {supplier_name}")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Aggregation: models per supplier (group-by). Require explicit grouping intent.
    if (
        ("supplier" in tokens_sig or "provider" in tokens_sig)
        and pred_provided_by
        and cls_model
        and pred_ct
        and want_model
        and (
            re.search(r"\b(per|each)\b", qn)
            or "group" in qn
            or "distribution" in tokens_sig
            or "count" in tokens_sig
            or re.search(r"\bnumber\s+of\b", qn)
        )
    ):
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?prov (COUNT(DISTINCT ?modelo) AS ?numModelos) WHERE {\n"
            f"  ?modelo a <{cls_model}> ; <{pred_ct}> \"Physical Model\" ; <{pred_provided_by}> ?prov .\n"
            "}\nGROUP BY ?prov\nORDER BY DESC(?numModelos)"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: MODELS_BY_SUPPLIER")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if ("supplier" in tokens_sig or "provider" in tokens_sig) and pred_provided_by and cls_model and pred_ct and want_test and pred_verified and pred_link and ("test" in tokens_sig or "verification" in tokens_sig):
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?prov (COUNT(DISTINCT ?test) AS ?numTests) WHERE {\n"
            f"  ?modelo a <{cls_model}> ; <{pred_ct}> \"Physical Model\" ; <{pred_provided_by}> ?prov .\n"
            f"  ?modelo <{pred_verified}> ?link .\n"
            f"  ?link <{pred_ct}> \"Test Case\" ; <{pred_link}> ?test .\n"
            "}\nGROUP BY ?prov\nORDER BY DESC(?numTests)"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: TESTS_BY_SUPPLIER_VIA_MODEL")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if ("supplier" in tokens_sig or "provider" in tokens_sig) and ("most" in qn or "top" in qn) and pred_provided_by and cls_model and pred_ct and pred_verified and pred_link:
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?prov (COUNT(DISTINCT ?modelo) AS ?numModelosSinTest) WHERE {\n"
            f"  ?modelo a <{cls_model}> ; <{pred_ct}> \"Physical Model\" ; <{pred_provided_by}> ?prov .\n"
            "  FILTER NOT EXISTS {\n"
            f"    ?modelo <{pred_verified}> ?link .\n"
            f"    ?link <{pred_ct}> \"Test Case\" ; <{pred_link}> ?test .\n"
            "  }\n"
            "}\nGROUP BY ?prov\nORDER BY DESC(?numModelosSinTest)"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: SUPPLIERS_TOP_MODELS_WITHOUT_TESTS")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Manifest summaries: PLM info, dev environment, VnV scenarios
    baseline_trigger = bool(re.search(r"\b(baseline|project|product|release)\b", q_raw, flags=re.IGNORECASE))
    if baseline_trigger and cls_manifest and pred_manifest_plm and (pred_project_code or pred_product or pred_has_baseline):
        pfx = _prefix_lines(index)
        where_lines: list[str] = [
            f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_plm}> ?info .",
        ]
        if pred_project_code:
            where_lines.append(f"  OPTIONAL {{ ?info <{pred_project_code}> ?projectCode }}")
        if pred_product:
            where_lines.append(f"  OPTIONAL {{ ?info <{pred_product}> ?product }}")
        if pred_has_baseline:
            where_lines.append(f"  OPTIONAL {{ ?info <{pred_has_baseline}> ?bl .")
            if pred_baseline_name:
                where_lines.append(f"    OPTIONAL {{ ?bl <{pred_baseline_name}> ?baselineName }}")
            if pred_baseline_id:
                where_lines.append(f"    OPTIONAL {{ ?bl <{pred_baseline_id}> ?baselineId }}")
            if pred_baseline_created:
                where_lines.append(f"    OPTIONAL {{ ?bl <{pred_baseline_created}> ?baselineCreated }}")
            where_lines.append("  }")

        sparql = (
            f"{pfx}\n"
            "SELECT ?projectCode ?product ?baselineName ?baselineId ?baselineCreated WHERE {\n"
            + "\n".join(where_lines)
            + "\n}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: MANIFEST_PROJECT_BASELINE")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if ("plm" in tokens_sig or "purpose" in tokens_sig or "objective" in tokens_sig or "version" in tokens_sig) and cls_manifest and pred_manifest_plm:
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?org ?created ?purpose ?objective ?version WHERE {\n"
            f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_plm}> ?info .\n"
            + (f"  OPTIONAL {{ ?info <{pred_org}> ?org }}\n" if pred_org else "")
            + (f"  OPTIONAL {{ ?info <{pred_created_on}> ?created }}\n" if pred_created_on else "")
            + (f"  OPTIONAL {{ ?info <{pred_model_purpose}> ?purpose }}\n" if pred_model_purpose else "")
            + (f"  OPTIONAL {{ ?info <{pred_model_objective}> ?objective }}\n" if pred_model_objective else "")
            + (f"  OPTIONAL {{ ?info <{pred_version_identifier}> ?version }}\n" if pred_version_identifier else "")
            + "}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: PLM_SUMMARY")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if ("environment" in tokens_sig or "tool" in tokens_sig or "os" in tokens_sig or "language" in tokens_sig or "format" in tokens_sig) and cls_manifest and pred_manifest_dev:
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?tool ?toolVer ?os ?osVer ?format ?formatVer ?tech ?lang WHERE {\n"
            f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_dev}> ?dev .\n"
            + (f"  OPTIONAL {{ ?dev <{pred_dev_tool_name}> ?tool }}\n" if pred_dev_tool_name else "")
            + (f"  OPTIONAL {{ ?dev <{pred_dev_tool_ver}> ?toolVer }}\n" if pred_dev_tool_ver else "")
            + (f"  OPTIONAL {{ ?dev <{pred_dev_os_name}> ?os }}\n" if pred_dev_os_name else "")
            + (f"  OPTIONAL {{ ?dev <{pred_dev_os_ver}> ?osVer }}\n" if pred_dev_os_ver else "")
            + (f"  OPTIONAL {{ ?dev <{pred_format_name}> ?format }}\n" if pred_format_name else "")
            + (f"  OPTIONAL {{ ?dev <{pred_format_ver}> ?formatVer }}\n" if pred_format_ver else "")
            + (f"  OPTIONAL {{ ?dev <{pred_req_authoring}> ?tech }}\n" if pred_req_authoring else "")
            + (f"  OPTIONAL {{ ?dev <{pred_language}> ?lang }}\n" if pred_language else "")
            + "}"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: DEV_ENVIRONMENT")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    if ("scenario" in tokens_sig or "vnv" in tokens_sig) and cls_manifest and pred_manifest_vnv and pred_vnv_scenario and pred_id and cls_scn:
        pfx = _prefix_lines(index)
        if wants_missing:
            where_lines: list[str] = [
                f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_vnv}> ?vnv .",
                f"  ?vnv <{pred_vnv_scenario}> ?sc .",
                f"  ?sc <{pred_id}> ?scenarioId .",
            ]
            if pred_verified:
                where_lines.append("  FILTER NOT EXISTS {")
                where_lines.append(f"    ?sc <{pred_verified}> ?_v .")
                where_lines.append("  }")
            if pred_validated:
                where_lines.append("  FILTER NOT EXISTS {")
                where_lines.append(f"    ?sc <{pred_validated}> ?_a .")
                where_lines.append("  }")
            sparql = f"{pfx}\nSELECT ?scenarioId WHERE {{\n" + "\n".join(where_lines) + "\n}\nORDER BY ?scenarioId"
            op_name = "VNV_SCENARIOS_INCOMPLETE"
        else:
            # Summary
            union_blocks: list[str] = []
            if pred_verified:
                union_blocks.append(
                    f"    {{ ?sc <{pred_verified}> ?link . BIND(\"Verified_by\" AS ?tipoEnlace) }}"
                )
            if pred_validated:
                union_blocks.append(
                    f"    {{ ?sc <{pred_validated}> ?link . BIND(\"Validated_by\" AS ?tipoEnlace) }}"
                )
            union = "\n    UNION\n".join(union_blocks) if union_blocks else ""
            opt_target_id = f"OPTIONAL {{ ?target <{pred_id}> ?targetId }}" if pred_id else ""
            opt_v = f"OPTIONAL {{ ?sc <{pred_ver_level}> ?verLevel }}" if pred_ver_level else ""
            opt_a = f"OPTIONAL {{ ?sc <{pred_val_level}> ?valLevel }}" if pred_val_level else ""
            if not union:
                raise ValueError("Dynamic generator: graph missing Verified_by/Validated_by predicates for scenarios.")

            opt_target_line = f"    ?link <{pred_link}> ?target ." if pred_link else ""
            optional_lines: list[str] = ["  OPTIONAL {", union]
            if opt_target_line:
                optional_lines.append(opt_target_line)
            if opt_target_id:
                optional_lines.append(f"    {opt_target_id}")
            optional_lines.append("  }")

            where_lines = [
                f"  ?manifest a <{cls_manifest}> ; <{pred_manifest_vnv}> ?vnv .",
                f"  ?vnv <{pred_vnv_scenario}> ?sc .",
                f"  ?sc <{pred_id}> ?scenarioId .",
            ]
            if opt_v:
                where_lines.append(f"  {opt_v}")
            if opt_a:
                where_lines.append(f"  {opt_a}")
            where_lines.extend(optional_lines)

            sparql = (
                f"{pfx}\n"
                "SELECT ?scenarioId ?verLevel ?valLevel ?tipoEnlace ?targetId WHERE {\n"
                + "\n".join(where_lines)
                + "\n}\nORDER BY ?scenarioId"
            )
            op_name = "VNV_SCENARIOS_SUMMARY"

        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append(f"operator: {op_name}")
        return GenerationResult(sparql=sparql, attempts=1, matched_id="dynamic", explanation=explain)

    # Links for entities authored by a given organization (Author_Organization)
    # Example: "show links for requirements authored by Supplier 03"
    if want_link and (want_author or _extract_author_org_literal(question)):
        org = _extract_author_org_literal(question)
        if not org:
            raise ValueError(
                "Dynamic generator: could not extract an author organization. "
                "Try phrasing like 'authored by Supplier 03' or 'authored by University'."
            )
        if not (pred_author_org and pred_link and cls_link):
            raise ValueError(
                "Dynamic generator: graph missing required schema terms for author/link query (Author_Organization/Link/Traceability_Link_Type)."
            )
        preds = [p for p in [pred_satisfied, pred_verified, pred_validated, pred_uses] if p]
        if not preds:
            raise ValueError("Dynamic generator: could not find traceability predicates in the graph.")

        pfx = _prefix_lines(index)
        values = " ".join([f"<{p}>" for p in preds])
        opt_id = f"OPTIONAL {{ ?src <{pred_id}> ?srcId . }}" if pred_id else ""
        opt_ct = f"OPTIONAL {{ ?link <{pred_ct}> ?ct . }}" if pred_ct else ""

        sparql = (
            f"{pfx}\n"
            "SELECT ?src ?srcId ?pred ?link ?ct ?target WHERE {\n"
            f"  ?src <{pred_author_org}> \"{org}\" .\n"
            f"  VALUES ?pred {{ {values} }}\n"
            "  ?src ?pred ?link .\n"
            f"  ?link a <{cls_link}> ; <{pred_link}> ?target .\n"
            f"  {opt_id}\n"
            f"  {opt_ct}\n"
            "}\nORDER BY ?srcId ?pred ?ct"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: LINKS_BY_AUTHOR_ORG")
        explain.append("author_org_literal: " + org)
        explain.append("pattern: ?src Author_Organization \"...\"; ?src ?pred ?link; ?link Link ?target")
        explain.append("uses_predicates: " + ", ".join([_term(p) for p in preds]))
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # Requirements without end-to-end traceability (Req -> Model -> Test)
    if (
        want_req
        and wants_missing
        and (
            re.search(r"\bend\s*-?\s*to\s*-?\s*end\b", qn)
            or "endtoend" in tokens_sig
            or ("traceability" in tokens_sig and ("test" in tokens_sig or "testcase" in tokens_sig))
            or ("chain" in tokens_sig and ("test" in tokens_sig or "testcase" in tokens_sig))
        )
    ):
        if not (cls_req and pred_id and pred_satisfied and pred_link and pred_verified):
            raise ValueError(
                "Dynamic generator: graph missing required schema terms for end-to-end traceability (Satisfied_by/Verified_by/Link)."
            )
        model_type = f"?m a <{cls_model}> ." if cls_model else ""
        test_type = f"?t a <{cls_test}> ." if cls_test else ""
        pfx = _prefix_lines(index)
        sparql = (
            f"{pfx}\n"
            "SELECT ?id WHERE {\n"
            f"  ?req a <{cls_req}> ; <{pred_id}> ?id .\n"
            "  FILTER NOT EXISTS {\n"
            f"    ?req <{pred_satisfied}> ?sl .\n"
            f"    ?sl <{pred_link}> ?m .\n"
            f"    {model_type}\n"
            f"    ?m <{pred_verified}> ?vl .\n"
            f"    ?vl <{pred_link}> ?t .\n"
            f"    {test_type}\n"
            "  }\n"
            "}\nORDER BY ?id"
        )
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)
        explain = _base_explain()
        explain.append("operator: REQUIREMENTS_MISSING_END_TO_END")
        explain.append("path: Requirement -Satisfied_by-> Model -Verified_by-> Test (via link nodes)")
        explain.append("filter: NOT EXISTS full path")
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_id="dynamic",
            matched_nl=None,
            match_score=None,
            explanation=explain,
        )

    # List/show queries (fallback when a domain is clear but no special intent matches)
    is_list = bool(
        any(t in tokens for t in {"list", "show", "display", "give", "return", "which", "what"})
        or qn.startswith("list ")
        or qn.startswith("show ")
    )

    if is_list or (want_supplier or want_req or want_model or want_test or want_link):
        pfx = _prefix_lines(index)

        if want_supplier and cls_org:
            sparql = f"{pfx}\nSELECT DISTINCT ?prov WHERE {{ ?prov a <{cls_org}> . }}\nORDER BY ?prov"
        elif want_req and cls_req and pred_id:
            sparql = (
                f"{pfx}\n"
                "SELECT ?id WHERE {\n"
                f"  ?req a <{cls_req}> ; <{pred_id}> ?id .\n"
                "}\nORDER BY ?id"
            )
        elif want_model and cls_model and pred_id:
            sparql = (
                f"{pfx}\n"
                "SELECT ?id WHERE {\n"
                f"  ?m a <{cls_model}> ; <{pred_id}> ?id .\n"
                "}\nORDER BY ?id"
            )
        elif want_test and cls_test:
            opt_id = f"OPTIONAL {{ ?t <{pred_id}> ?id . }}" if pred_id else ""
            sparql = (
                f"{pfx}\n"
                "SELECT DISTINCT ?t ?id WHERE {\n"
                f"  ?t a <{cls_test}> .\n"
                f"  {opt_id}\n"
                "}\nORDER BY ?id ?t"
            )
        elif want_link and cls_link:
            opt_ct = f"OPTIONAL {{ ?l <{pred_ct}> ?ct . }}" if pred_ct else ""
            opt_target = f"OPTIONAL {{ ?l <{pred_link}> ?target . }}" if pred_link else ""
            sparql = (
                f"{pfx}\n"
                "SELECT DISTINCT ?l ?ct ?target WHERE {\n"
                f"  ?l a <{cls_link}> .\n"
                f"  {opt_ct}\n"
                f"  {opt_target}\n"
                "}\nORDER BY ?ct ?l"
            )
        else:
            sparql = ""

        if sparql:
            sparql = ensure_limit(sparql, config.limit)
            check_no_invented_terms(graph, sparql)
            validate_and_run(graph, sparql)
            return GenerationResult(
                sparql=sparql,
                attempts=1,
                matched_id="dynamic",
                matched_nl=None,
                match_score=None,
            )

    raise ValueError(
        "Dynamic generator: unsupported question yet. Try examples like: "
        "'how many suppliers are there', 'physical models without tests', 'audit duplicate links', 'used documents', "
        "'requirements without end-to-end traceability'."
    )


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []

    items: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def extract_sparql(text: str) -> str:
    """Extract SPARQL from a model response.

    Accepts either a fenced code block ```sparql ...``` or raw text.
    """

    fenced = re.search(r"```(?:sparql)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # If the model started a fence but didn't close it, drop fence markers.
    if "```" in text:
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("```"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()
        if cleaned:
            return cleaned

    return text.strip().lstrip("`")


def ensure_select_or_ask_only(sparql: str) -> None:
    upper = sparql.upper()
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", upper):
            raise ValueError(f"Forbidden SPARQL: contains '{kw}'")

    if not re.search(r"\b(SELECT|ASK)\b", upper):
        raise ValueError("Forbidden SPARQL: must be SELECT or ASK")


def ensure_limit(sparql: str, limit: int) -> str:
    """Append LIMIT if missing (for SELECT only)."""

    s = sparql.strip()
    upper = s.upper()
    if re.search(r"\bASK\b", upper):
        return s

    if re.search(r"\bLIMIT\b", upper):
        return s

    return s + f"\nLIMIT {int(limit)}\n"


def _normalize_nl_basic(text: str) -> str:
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_nl(text: str, synonyms: SynonymMap | None = None) -> str:
    s = _normalize_nl_basic(text)
    if not synonyms or not synonyms.phrases:
        return s

    padded = f" {s} "
    # Replace longer phrases first (loader sorts by length).
    for syn, canon in synonyms.phrases:
        padded = padded.replace(f" {syn} ", f" {canon} ")
    return re.sub(r"\s+", " ", padded).strip()


_STOPWORDS = {
    "a",
    "an",
    "the",
    "which",
    "what",
    "how",
    "many",
    "are",
    "there",
    "do",
    "does",
    "did",
    "not",
    "have",
    "has",
    "any",
    "associated",
    "list",
    "show",
    "find",
    "compute",
    "give",
    "me",
    "from",
    "in",
    "on",
    "of",
    "for",
    "to",
    "by",
    "with",
    "at",
    "least",
    "one",
    "more",
    "than",
    "and",
    "or",
    "their",
    "its",
    "without",
    "missing",
}


def _token_set(text: str, synonyms: SynonymMap | None = None) -> set[str]:
    s = _normalize_nl(text, synonyms=synonyms)
    stop = {
        *_STOPWORDS,
    }
    tokens: set[str] = set()
    for t in s.split(" "):
        if not t:
            continue
        # Cheap plural singularization for matching.
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        if synonyms and t in synonyms.words:
            t = synonyms.words[t]
        if t in stop:
            continue
        tokens.add(t)
    return tokens


def _token_counts(text: str, synonyms: SynonymMap | None = None) -> dict[str, int]:
    # Similar to _token_set but keeps multiplicity for NB.
    s = _normalize_nl(text, synonyms=synonyms)
    counts: dict[str, int] = {}
    for t in s.split(" "):
        if not t:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        if synonyms and t in synonyms.words:
            t = synonyms.words[t]
        if t in _STOPWORDS:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _similarity(a: str, b: str, synonyms: SynonymMap | None = None) -> float:
    na = _normalize_nl(a, synonyms=synonyms)
    nb = _normalize_nl(b, synonyms=synonyms)
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    jac = _jaccard(_token_set(na, synonyms=synonyms), _token_set(nb, synonyms=synonyms))
    # Blend character-sequence similarity with token overlap.
    return 0.40 * seq + 0.60 * jac


def build_schema_summary(graph: Graph, max_items: int = 30) -> str:
    """Build a compact schema/data summary from the RDF graph.

    This is not a full ontology extraction; it is a pragmatic constraint for prompting.
    """

    type_counts: dict[str, int] = {}
    pred_counts: dict[str, int] = {}
    content_types: dict[str, int] = {}

    for s, p, o in graph.triples((None, RDF.type, None)):
        type_counts[str(o)] = type_counts.get(str(o), 0) + 1

    for s, p, o in graph.triples((None, None, None)):
        pred_counts[str(p)] = pred_counts.get(str(p), 0) + 1

        # Common field in this project
        if str(p).endswith("#ContentType") and hasattr(o, "toPython"):
            val = o.toPython()
            if isinstance(val, str):
                content_types[val] = content_types.get(val, 0) + 1

    top_types = sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)[:max_items]
    top_preds = sorted(pred_counts.items(), key=lambda kv: kv[1], reverse=True)[:max_items]
    top_ct = sorted(content_types.items(), key=lambda kv: kv[1], reverse=True)[:max_items]

    def fmt(items: list[tuple[str, int]]) -> str:
        return "\n".join([f"- {k} ({v})" for k, v in items])

    return (
        "SCHEMA/DATA SUMMARY (extracted from the current graph)\n"
        "\nMost frequent CLASSES (rdf:type):\n"
        f"{fmt(top_types)}\n"
        "\nMost frequent PROPERTIES (predicates):\n"
        f"{fmt(top_preds)}\n"
        "\nCommon values for p510:ContentType:\n"
        f"{fmt(top_ct)}\n"
    )


def validate_and_run(graph: Graph, sparql: str) -> Any:
    ensure_select_or_ask_only(sparql)
    return graph.query(sparql)


def _extract_synonyms_block(text: str) -> str | None:
    start = "### SYNONYMS START"
    end = "### SYNONYMS END"
    if start in text and end in text:
        a = text.index(start) + len(start)
        b = text.index(end)
        if b > a:
            return text[a:b]
    return None


def _load_synonyms_file(path: str) -> SynonymMap:
    raw = Path(path).read_text(encoding="utf-8")
    block = _extract_synonyms_block(raw)
    if block is None:
        # If markers are missing, assume the entire file is a synonyms file.
        block = raw

    phrases: list[tuple[str, str]] = []
    words: dict[str, str] = {}

    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            left, right = line.split(":", 1)
        elif "=" in line:
            left, right = line.split("=", 1)
        else:
            continue

        canon = _normalize_nl_basic(left)
        if not canon:
            continue

        syns = re.split(r"[,;|]", right)
        for syn in syns:
            syn = _normalize_nl_basic(syn)
            if not syn or syn == canon:
                continue
            phrases.append((syn, canon))
            if " " not in syn and " " not in canon:
                words[syn] = canon

    phrases.sort(key=lambda t: len(t[0]), reverse=True)
    return SynonymMap(phrases=phrases, words=words)


def _nb_train(
    examples: list[dict[str, Any]],
    synonyms: SynonymMap | None,
    alpha: float = 1.0,
) -> NBModel:
    # Each example is treated as a class label = example id.
    # This is intentionally simple and fully offline.
    class_texts: list[tuple[str, str]] = []
    for ex in examples:
        ex_id = ex.get("id")
        nl = ex.get("nl")
        sp = ex.get("sparql")
        if not isinstance(ex_id, str) or not ex_id.strip():
            continue
        if not isinstance(nl, str) or not nl.strip():
            continue
        if not isinstance(sp, str) or not sp.strip():
            continue
        class_texts.append((ex_id.strip(), nl.strip()))

    if not class_texts:
        raise ValueError("No trainable examples (need non-empty id, nl, sparql)")

    classes = sorted({cid for cid, _ in class_texts})
    class_counts: dict[str, int] = {c: 0 for c in classes}
    token_counts_by_class: dict[str, dict[str, int]] = {c: {} for c in classes}
    total_tokens_by_class: dict[str, int] = {c: 0 for c in classes}
    class_example_nl: dict[str, str] = {}

    vocab_set: set[str] = set()
    for cid, text in class_texts:
        class_counts[cid] += 1
        if cid not in class_example_nl:
            class_example_nl[cid] = text
        counts = _token_counts(text, synonyms=synonyms)
        for tok, n in counts.items():
            vocab_set.add(tok)
            token_counts_by_class[cid][tok] = token_counts_by_class[cid].get(tok, 0) + n
            total_tokens_by_class[cid] += n

    vocab = {tok: i for i, tok in enumerate(sorted(vocab_set))}
    vsize = len(vocab)
    total_docs = sum(class_counts.values())

    log_prior: dict[str, float] = {}
    log_likelihood: dict[str, list[float]] = {}
    default_log_likelihood: dict[str, float] = {}

    for c in classes:
        log_prior[c] = math.log((class_counts[c] + alpha) / (total_docs + alpha * len(classes)))
        denom = total_tokens_by_class[c] + alpha * vsize
        default_log_likelihood[c] = math.log(alpha / denom)

        arr = [default_log_likelihood[c]] * vsize
        for tok, idx in vocab.items():
            cnt = token_counts_by_class[c].get(tok, 0)
            arr[idx] = math.log((cnt + alpha) / denom)
        log_likelihood[c] = arr

    return NBModel(
        version=1,
        classes=classes,
        vocab=vocab,
        log_prior=log_prior,
        log_likelihood=log_likelihood,
        default_log_likelihood=default_log_likelihood,
        class_example_nl=class_example_nl,
    )


def nb_save(model: NBModel, path: str) -> None:
    obj = {
        "version": model.version,
        "classes": model.classes,
        "vocab": model.vocab,
        "log_prior": model.log_prior,
        "log_likelihood": model.log_likelihood,
        "default_log_likelihood": model.default_log_likelihood,
        "class_example_nl": model.class_example_nl,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def nb_load(path: str) -> NBModel:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return NBModel(
        version=int(obj.get("version") or 1),
        classes=list(obj.get("classes") or []),
        vocab=dict(obj.get("vocab") or {}),
        log_prior=dict(obj.get("log_prior") or {}),
        log_likelihood=dict(obj.get("log_likelihood") or {}),
        default_log_likelihood=dict(obj.get("default_log_likelihood") or {}),
        class_example_nl=dict(obj.get("class_example_nl") or {}),
    )


def nb_predict(
    model: NBModel,
    text: str,
    synonyms: SynonymMap | None,
    top_k: int = 3,
) -> list[tuple[str, float]]:
    counts = _token_counts(text, synonyms=synonyms)
    if not counts:
        return []

    scores: list[tuple[str, float]] = []
    for c in model.classes:
        lp = float(model.log_prior.get(c, -9999.0))
        ll = model.log_likelihood.get(c)
        if not isinstance(ll, list):
            continue
        s = lp
        default_ll = float(model.default_log_likelihood.get(c, -20.0))
        for tok, n in counts.items():
            idx = model.vocab.get(tok)
            if idx is None:
                s += n * default_ll
            else:
                s += n * float(ll[idx])
        scores.append((c, s))

    scores.sort(key=lambda t: t[1], reverse=True)
    scores = scores[: max(1, int(top_k))]

    # Convert log-scores to normalized probabilities (softmax).
    max_s = max(s for _, s in scores)
    exps = [(c, math.exp(s - max_s)) for c, s in scores]
    z = sum(v for _, v in exps) or 1.0
    return [(c, v / z) for c, v in exps]


def _best_catalog_match(
    question: str,
    examples: list[dict[str, Any]],
    synonyms: SynonymMap | None,
) -> tuple[dict[str, Any] | None, float, list[tuple[dict[str, Any], float]]]:
    scored: list[tuple[dict[str, Any], float]] = []
    for ex in examples:
        nl = ex.get("nl")
        sp = ex.get("sparql")
        if not isinstance(nl, str) or not isinstance(sp, str) or not sp.strip():
            continue
        score = _similarity(question, nl, synonyms=synonyms)
        scored.append((ex, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    best_ex = scored[0][0] if scored else None
    best_score = float(scored[0][1]) if scored else 0.0
    return best_ex, best_score, scored


def generate_sparql(
    graph: Graph,
    question_es: str,
    config: GenerationConfig,
    examples_path: str | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> GenerationResult:
    if not isinstance(question_es, str) or not question_es.strip():
        raise ValueError("Missing question")

    synonyms: SynonymMap | None = None
    synonyms_path: str | None = config.synonyms_file
    if synonyms_path is None:
        default_prompt = Path("prompts") / "system_en.txt"
        if default_prompt.exists():
            synonyms_path = str(default_prompt)
    if synonyms_path:
        try:
            p = Path(synonyms_path)
            if p.exists():
                synonyms = _load_synonyms_file(str(p))
        except Exception:
            synonyms = None

    # Dynamic engine: build SPARQL on the fly (no catalog required).
    if (config.engine or "dynamic").lower().strip() == "dynamic":
        return _dynamic_generate(graph, question_es, config=config, synonyms=synonyms)

    # Catalog engine (legacy): needs JSONL examples.
    if examples is None:
        examples = _read_jsonl(examples_path) if examples_path else []

    if not examples:
        raise ValueError(
            "Catalog engine requires examples. Provide --examples (JSONL) with 'nl' and 'sparql' fields, "
            "or switch to --engine dynamic."
        )

    best_ex, best_score, scored = _best_catalog_match(question_es, examples, synonyms=synonyms)
    if best_ex is None:
        raise ValueError("No usable examples found (need 'nl' and non-empty 'sparql').")

    # Optional offline classifier (fallback): only used when similarity is below threshold.
    clf_preds: list[tuple[str, float]] = []
    clf_best_ex: dict[str, Any] | None = None
    clf_best_prob: float | None = None
    if float(best_score) < float(config.match_threshold):
        clf_path = (config.classifier_model_file or "").strip() if config else ""
        if clf_path:
            try:
                mp = Path(clf_path)
                if mp.exists():
                    model = nb_load(str(mp))
                    clf_preds = nb_predict(model, question_es, synonyms=synonyms, top_k=3)
                    if clf_preds:
                        best_id, best_prob = clf_preds[0]
                        if float(best_prob) >= float(config.classifier_min_prob):
                            for ex in examples:
                                ex_id = ex.get("id")
                                sp = ex.get("sparql")
                                if ex_id == best_id and isinstance(sp, str) and sp.strip():
                                    clf_best_ex = ex
                                    clf_best_prob = float(best_prob)
                                    break
            except Exception:
                clf_preds = []
                clf_best_ex = None
                clf_best_prob = None

    if clf_best_ex is not None and clf_best_prob is not None:
        sparql = str(clf_best_ex.get("sparql") or "").strip()
        sparql = ensure_limit(sparql, config.limit)
        check_no_invented_terms(graph, sparql)
        validate_and_run(graph, sparql)

        matched_nl = clf_best_ex.get("nl") if isinstance(clf_best_ex.get("nl"), str) else None
        matched_id = clf_best_ex.get("id") if isinstance(clf_best_ex.get("id"), str) else None
        return GenerationResult(
            sparql=sparql,
            attempts=1,
            matched_nl=matched_nl,
            matched_id=matched_id,
            match_score=float(clf_best_prob),
            error=None,
        )

    if best_score < float(config.match_threshold):
        suggestions = []
        for ex, score in scored[: int(config.max_suggestions)]:
            nl = ex.get("nl")
            ex_id = ex.get("id")
            if isinstance(nl, str):
                prefix = f"[{ex_id}] " if isinstance(ex_id, str) and ex_id else ""
                suggestions.append(f"- {prefix}{nl} (score={score:.3f})")
        hint = "\n".join(suggestions) if suggestions else "(no suggestions)"

        clf_hint = ""
        if clf_preds:
            rows = []
            for cid, prob in clf_preds:
                ex_nl = None
                for ex in examples:
                    if ex.get("id") == cid and isinstance(ex.get("nl"), str):
                        ex_nl = ex.get("nl")
                        break
                label = ex_nl or cid
                rows.append(f"- [{cid}] {label} (prob={prob:.3f})")
            clf_hint = "\n\nClassifier top predictions:\n" + "\n".join(rows)

        raise ValueError(
            "Could not map the question to a known query in the catalog. "
            "Add a new example to eval/text2sparql_examples.jsonl or rephrase.\n\n"
            f"Top matches:\n{hint}{clf_hint}"
        )

    sparql = str(best_ex.get("sparql") or "").strip()
    sparql = ensure_limit(sparql, config.limit)
    check_no_invented_terms(graph, sparql)
    validate_and_run(graph, sparql)

    matched_nl = best_ex.get("nl") if isinstance(best_ex.get("nl"), str) else None
    matched_id = best_ex.get("id") if isinstance(best_ex.get("id"), str) else None

    return GenerationResult(
        sparql=sparql,
        attempts=1,
        matched_nl=matched_nl,
        matched_id=matched_id,
        match_score=float(best_score),
        error=None,
    )
