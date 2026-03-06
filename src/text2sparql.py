import json
import os
import re
import time
import urllib.error
import urllib.request
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
    backend: str = "ollama"  # ollama | openai_compat | rules
    model: str = "llama3.1"
    max_retries: int = 2
    timeout_s: float = 30.0
    temperature: float = 0.1
    limit: int = 200
    schema_max_items: int = 10
    fewshot_max_examples: int = 3
    ollama_num_predict: int = 400
    rules_first: bool = True
    prompt_file: str | None = None


@dataclass(frozen=True)
class GenerationResult:
    sparql: str
    backend_used: str
    attempts: int
    error: str | None = None


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
            raise ValueError(f"SPARQL no permitido: contiene '{kw}'")

    if not re.search(r"\b(SELECT|ASK)\b", upper):
        raise ValueError("SPARQL no permitido: debe ser SELECT o ASK")


def ensure_limit(sparql: str, limit: int) -> str:
    """Append LIMIT if missing (for SELECT only)."""

    s = sparql.strip()
    upper = s.upper()
    if re.search(r"\bASK\b", upper):
        return s

    if re.search(r"\bLIMIT\b", upper):
        return s

    return s + f"\nLIMIT {int(limit)}\n"


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
        "RESUMEN DEL ESQUEMA/DATOS (extraído del grafo actual)\n"
        "\nCLASES (rdf:type) más frecuentes:\n"
        f"{fmt(top_types)}\n"
        "\nPROPIEDADES (predicados) más frecuentes:\n"
        f"{fmt(top_preds)}\n"
        "\nVALORES comunes de p510:ContentType:\n"
        f"{fmt(top_ct)}\n"
    )


def build_prompt(
    question_es: str,
    schema_summary: str,
    examples: list[dict[str, Any]],
    limit: int,
    fewshot_max_examples: int,
    system_prompt_override: str | None = None,
) -> list[dict[str, str]]:
    system = system_prompt_override or (
        "Eres un asistente local 'Text2SPARQL' para un grafo RDF inspirado en LOTAR P510. "
        "Devuelves SOLO una consulta SPARQL válida (sin explicaciones) que responda a la pregunta en español.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- Solo se permite SELECT o ASK.\n"
        "- Incluye PREFIX necesarios.\n"
        "- Respeta el modelo de trazabilidad por nodo-enlace: p510:Satisfied_by / Verified_by / Validated_by / uses "
        "apuntan a un nodo p510:Traceability_Link_Type, y el destino real está en p510:Link.\n"
        "- Evita sintaxis problemática: NO empieces líneas con '!' ni uses '!EXISTS'. Prefiere: FILTER NOT EXISTS { ... }.\n"
        f"- Si la consulta es SELECT y no tiene LIMIT, añade LIMIT {limit}.\n"
        "- No inventes IRIs fuera de estos prefijos típicos: p510, rdf, foaf, ex.\n"
        "- Si no puedes responder con exactitud, produce la mejor aproximación segura y explícita.\n"
        "- Formato de salida: un único bloque ```sparql ...```\n"
    )

    fewshot_parts: list[str] = []
    for ex in examples:
        nl = ex.get("nl")
        sp = ex.get("sparql")
        if not isinstance(nl, str) or not isinstance(sp, str):
            continue
        fewshot_parts.append(f"Pregunta: {nl}\nSPARQL:\n```sparql\n{sp.strip()}\n```\n")

    user = (
        f"{schema_summary}\n\n"
        "EJEMPLOS (few-shot):\n"
        + "\n".join(fewshot_parts[:fewshot_max_examples])
        + "\n\n"
        f"Pregunta: {question_es}\n"
        "SPARQL:\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _http_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def ollama_chat(
    messages: list[dict[str, str]],
    model: str,
    timeout_s: float,
    temperature: float,
    num_predict: int,
) -> str:
    # Ollama supports a chat API locally.
    # https://github.com/ollama/ollama/blob/main/docs/api.md
    url = os.environ.get("TEXT2SPARQL_OLLAMA_URL", "http://localhost:11434/api/chat")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": float(temperature), "num_predict": int(num_predict)},
    }
    obj = _http_json(url, payload, timeout_s=timeout_s)
    msg = obj.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError("Respuesta inesperada de Ollama")
    return content


def openai_compat_chat(
    messages: list[dict[str, str]],
    model: str,
    timeout_s: float,
    temperature: float,
) -> str:
    base = os.environ.get("TEXT2SPARQL_OPENAI_BASE_URL", "http://localhost:1234")
    api_key = os.environ.get("TEXT2SPARQL_OPENAI_API_KEY", "")
    url = base.rstrip("/") + "/v1/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
    }

    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    obj = json.loads(raw)

    choices = obj.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Respuesta inesperada del servidor OpenAI-compatible")

    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise RuntimeError("Respuesta inesperada del servidor OpenAI-compatible")

    return content


def validate_and_run(graph: Graph, sparql: str) -> Any:
    ensure_select_or_ask_only(sparql)
    return graph.query(sparql)


def _load_prompt_file(path: str, limit: int) -> str:
    text = Path(path).read_text(encoding="utf-8")
    # Allow prompt templates to reference the LIMIT value.
    return text.replace("{LIMIT}", str(int(limit)))


def generate_sparql(
    graph: Graph,
    question_es: str,
    config: GenerationConfig,
    examples_path: str | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> GenerationResult:
    schema = build_schema_summary(graph, max_items=config.schema_max_items)
    if examples is None:
        examples = _read_jsonl(examples_path) if examples_path else []

    system_prompt_override: str | None = None
    if config.prompt_file:
        try:
            p = Path(config.prompt_file)
            if p.exists():
                system_prompt_override = _load_prompt_file(str(p), limit=config.limit)
        except Exception:
            system_prompt_override = None

    last_error: str | None = None
    sparql_candidate: str | None = None

    # Hybrid shortcut: if the baseline rule parser can map the question to an existing
    # query, prefer it. This matches real-world Text2Cypher-style systems where a
    # catalog is used when possible, and LLM generation is a fallback.
    if config.backend != "rules" and config.rules_first:
        try:
            from nl2sparql import parse_spanish_question
            from nl2sparql_cli import build_query

            parsed = parse_spanish_question(question_es)
            sparql_candidate = build_query(parsed, "queries_p510")
            sparql_candidate = ensure_limit(sparql_candidate, config.limit)
            validate_and_run(graph, sparql_candidate)
            return GenerationResult(
                sparql=sparql_candidate,
                backend_used="rules_first",
                attempts=1,
                error=None,
            )
        except Exception:
            sparql_candidate = None

    for attempt in range(1, config.max_retries + 2):
        if config.backend == "rules":
            # Reuse the reproducible baseline.
            from nl2sparql import parse_spanish_question
            from nl2sparql_cli import build_query

            parsed = parse_spanish_question(question_es)
            sparql_candidate = build_query(parsed, "queries_p510")
        else:
            messages = build_prompt(
                question_es,
                schema,
                examples,
                limit=config.limit,
                fewshot_max_examples=config.fewshot_max_examples,
                system_prompt_override=system_prompt_override,
            )

            if last_error and sparql_candidate:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "La consulta anterior dio error al validar/ejecutar. "
                            "Corrige SOLO la SPARQL.\n\n"
                            f"Error: {last_error}\n\n"
                            f"SPARQL previa:\n```sparql\n{_shorten(sparql_candidate, 3000)}\n```\n"
                        ),
                    }
                )

            try:
                if config.backend == "ollama":
                    raw = ollama_chat(
                        messages=messages,
                        model=config.model,
                        timeout_s=config.timeout_s,
                        temperature=config.temperature,
                        num_predict=config.ollama_num_predict,
                    )
                elif config.backend == "openai_compat":
                    raw = openai_compat_chat(
                        messages=messages,
                        model=config.model,
                        timeout_s=config.timeout_s,
                        temperature=config.temperature,
                    )
                else:
                    raise ValueError(f"Backend desconocido: {config.backend}")

                sparql_candidate = extract_sparql(raw)
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = f"Error de red/backend: {e}"
                continue

        try:
            if sparql_candidate is None:
                raise RuntimeError("No se generó ninguna consulta")
            sparql_candidate = ensure_limit(sparql_candidate, config.limit)
            validate_and_run(graph, sparql_candidate)
            return GenerationResult(
                sparql=sparql_candidate,
                backend_used=config.backend,
                attempts=attempt,
                error=None,
            )
        except Exception as e:  # noqa: BLE001 - surface error to retry loop
            last_error = str(e)
            time.sleep(0.1)

    raise RuntimeError(f"No se pudo generar SPARQL válida tras reintentos. Último error: {last_error}")
