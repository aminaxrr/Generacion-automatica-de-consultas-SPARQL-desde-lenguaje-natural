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

    explain: list[str] = []
    explain.append(f"normalized: {qn}")
    explain.append("tokens_sig: " + ", ".join(sorted(tokens_sig))[:200])

    def has_any(options: set[str]) -> bool:
        return bool(tokens_sig & options)

    # Determine query form.
    is_count = bool(
        re.search(
            r"\b(how\s+many|count(\s+of)?|number\s+of|total\s+number\s+of|quantity\s+of|amount\s+of)\b",
            qn,
        )
        or (tokens_sig & {"count", "number", "total", "quantity", "amount"})
    )

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

    def has_any(token_set: set[str], options: set[str]) -> bool:
        return bool(token_set & options)

    # Intent detection
    # Count phrasing is varied: "how many", "what is the number of", "total number of", etc.
    is_count = bool(
        re.search(
            r"\b(how\s+many|count(\s+of)?|number\s+of|total\s+number\s+of|quantity\s+of|amount\s+of)\b",
            qn,
        )
        or has_any(tokens_sig, {"count", "number", "total", "quantity", "amount"})
    )

    # Core domain terms (mapped to schema local names)
    want_req = has_any(tokens_sig, {"requirement", "req", "spec", "specification"})
    want_model = has_any(tokens_sig, {"model", "designmodel", "physicalmodel"})
    want_test = has_any(tokens_sig, {"test", "testcase", "verification", "verify"})
    want_supplier = has_any(tokens_sig, {"supplier", "provider", "vendor", "organization", "org", "owner", "responsible"})
    want_link = has_any(tokens_sig, {"link", "trace", "traceability", "relationship", "relation"})
    want_document = has_any(tokens_sig, {"document", "doc", "documentation"})

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
    )

    # Resolve common classes/predicates from the real graph
    cls_req = _find_class(index, "Requirement")
    cls_model = _find_class(index, "DesignModel")
    cls_test = _find_class(index, "VerificationTest", "TestCase", "Test")
    cls_link = _find_class(index, "Traceability_Link_Type")
    cls_org = _find_class(index, "Organization")  # foaf:Organization

    pred_id = _find_pred(index, "Id")
    pred_link = _find_pred(index, "Link")
    pred_ct = _find_pred(index, "ContentType")

    pred_author_org = _find_pred(index, "Author_Organization")

    pred_satisfied = _find_pred(index, "Satisfied_by")
    pred_verified = _find_pred(index, "Verified_by")
    pred_validated = _find_pred(index, "Validated_by")
    pred_uses = _find_pred(index, "uses")

    def _base_explain() -> list[str]:
        lines: list[str] = []
        lines.append(f"normalized: {qn}")
        lines.append("tokens_sig: " + ", ".join(sorted(tokens_sig))[:200])
        if is_count:
            lines.append("query_form: COUNT")
        elif any(t in tokens for t in {"list", "show"}) or qn.startswith("list ") or qn.startswith("show "):
            lines.append("query_form: LIST")
        if wants_missing:
            lines.append("constraint: missing/negation")
        if is_audit:
            lines.append("operator_hint: audit")
        if is_duplicate:
            lines.append("operator_hint: duplicate")
        if want_author:
            lines.append("constraint: authored-by")
        return lines

    def _term(uri: str | None) -> str:
        if not uri:
            return "<missing>"
        return _local_name(uri)

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

    # Missing tests for models
    if want_model and wants_missing and want_test:
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

    # Used documents (generic: list targets of uses links)
    if want_document and (
        has_any(tokens_sig, {"use", "used", "using", "reference", "referenced", "cite", "cited"})
        or "used" in tokens
        or "uses" in tokens
        or "used" in tokens_raw
        or "uses" in tokens_raw
        or "referenced" in tokens_raw
        or re.search(r"\b(used\s+by|referenced\s+by|depends\s+on)\b", qn)
    ):
        if not (pred_uses and pred_link):
            raise ValueError("Dynamic generator: graph missing required schema terms for 'used documents'.")
        pfx = _prefix_lines(index)
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
    if want_req and wants_missing and ("end" in tokens and "traceability" in tokens or "endtoend" in tokens):
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
