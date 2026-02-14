import argparse
import os
import time
from pathlib import Path

from run_queries_p510 import load_graph
from text2sparql import GenerationConfig, generate_sparql


def _read_jsonl(path: str) -> list[dict]:
    items: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(__import__("json").loads(line))
    return items


def _run_query(graph, sparql: str) -> int:
    qres = graph.query(sparql)
    # Force evaluation for rdflib
    return sum(1 for _ in qres)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-eval Text2SPARQL: ejecuta ejemplos JSONL y reporta pass/fail (RDFLib)"
    )
    parser.add_argument(
        "--ttl",
        default=os.path.join("data", "p510_sintetico.ttl"),
        help="Ruta al TTL",
    )
    parser.add_argument(
        "--examples",
        default=os.path.join("eval", "text2sparql_examples.jsonl"),
        help="JSONL con ejemplos (nl + sparql)",
    )
    parser.add_argument(
        "--mode",
        choices=["reference", "generate"],
        default="reference",
        help="reference: valida SPARQL de referencia; generate: genera desde NL y valida ejecución",
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai_compat", "rules"],
        default="rules",
        help="Backend para mode=generate",
    )
    parser.add_argument("--model", default="llama3.1", help="Modelo para mode=generate")
    parser.add_argument("--max-retries", type=int, default=1, help="Reintentos en generación")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout backend")
    parser.add_argument("--temperature", type=float, default=0.1, help="Temperatura")
    parser.add_argument("--limit", type=int, default=200, help="LIMIT a forzar si falta")
    parser.add_argument("--max", type=int, default=0, help="Máximo de ejemplos a evaluar (0=todos)")
    parser.add_argument(
        "--on-unmapped",
        choices=["auto", "skip", "fail"],
        default="auto",
        help=(
            "Qué hacer si el backend no puede mapear la pregunta (solo aplica a backend=rules): "
            "auto=skip, skip=SKIP, fail=FAIL"
        ),
    )
    args = parser.parse_args()

    if not os.path.exists(args.ttl):
        raise SystemExit(f"No existe {args.ttl}. Ejecuta primero: python src/p510_generate_synthetic.py")

    examples_path = Path(args.examples)
    if not examples_path.exists():
        raise SystemExit(f"No existe {examples_path}")

    examples = _read_jsonl(str(examples_path))
    if args.max and args.max > 0:
        examples = examples[: args.max]

    g = load_graph(args.ttl)

    ok = 0
    fail = 0
    skipped = 0

    config = GenerationConfig(
        backend=args.backend,
        model=args.model,
        max_retries=args.max_retries,
        timeout_s=args.timeout,
        temperature=args.temperature,
        limit=args.limit,
    )

    on_unmapped = args.on_unmapped
    if on_unmapped == "auto":
        on_unmapped = "skip" if (args.mode == "generate" and args.backend == "rules") else "fail"

    try:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex.get("id", f"ex{idx:02d}")
            nl = ex.get("nl")
            ref = ex.get("sparql")

            started = time.perf_counter()
            try:
                if args.mode == "reference":
                    if not isinstance(ref, str) or not ref.strip():
                        raise ValueError("Ejemplo sin 'sparql'")
                    rows = _run_query(g, ref)
                else:
                    if not isinstance(nl, str) or not nl.strip():
                        raise ValueError("Ejemplo sin 'nl'")

                    # Leave-one-out few-shot: do not include the current example in the prompt.
                    other_examples = [e for e in examples if e is not ex]
                    result = generate_sparql(
                        g,
                        nl,
                        config=config,
                        examples=other_examples,
                    )
                    rows = _run_query(g, result.sparql)

                elapsed_ms = (time.perf_counter() - started) * 1000.0
                ok += 1
                print(f"[OK]   {ex_id}  rows={rows}  {elapsed_ms:.1f}ms")
            except ValueError as e:
                # For backend=rules, not all NL variants are covered by the baseline.
                # In that case, allow SKIP to measure coverage separately from correctness.
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if args.mode == "generate" and args.backend == "rules" and on_unmapped == "skip":
                    skipped += 1
                    msg = str(e).replace("\n", " ")
                    print(f"[SKIP] {ex_id}  {elapsed_ms:.1f}ms  {msg}")
                else:
                    fail += 1
                    msg = str(e).replace("\n", " ")
                    print(f"[FAIL] {ex_id}  {elapsed_ms:.1f}ms  {msg}")
            except Exception as e:  # noqa: BLE001
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                fail += 1
                msg = str(e).replace("\n", " ")
                print(f"[FAIL] {ex_id}  {elapsed_ms:.1f}ms  {msg}")
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Detenido por KeyboardInterrupt.")

    total = ok + fail + skipped
    attempted = ok + fail
    print("-" * 80)
    attempted_rate = (100.0 * ok / attempted) if attempted else 0.0
    print(f"Total: {total} | OK: {ok} | FAIL: {fail} | SKIP: {skipped}")
    print(f"Attempted: {attempted} | Pass rate (attempted): {attempted_rate:.1f}%")


if __name__ == "__main__":
    main()
