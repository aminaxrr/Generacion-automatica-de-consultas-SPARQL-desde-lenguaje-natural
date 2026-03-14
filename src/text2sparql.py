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
    if examples is None:
        examples = _read_jsonl(examples_path) if examples_path else []
    if not isinstance(question_es, str) or not question_es.strip():
        raise ValueError("Missing question")

    if not examples:
        raise ValueError(
            "No examples loaded. Provide --examples (JSONL) with 'nl' and 'sparql' fields to enable catalog matching."
        )

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
