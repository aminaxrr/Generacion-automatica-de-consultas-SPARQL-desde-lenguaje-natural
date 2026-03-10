import argparse
import os
from pathlib import Path

from rdflib import Graph

from run_queries_p510 import load_graph
from text2sparql import GenerationConfig, generate_sparql


def _print_results(qres, max_rows: int) -> None:
    vars_ = [str(v) for v in getattr(qres, "vars", [])]

    if vars_:
        print(" | ".join(vars_))
        print("-" * 80)

    rows_printed = 0
    for row in qres:
        print(" | ".join(str(x) for x in row))
        rows_printed += 1
        if max_rows is not None and rows_printed >= max_rows:
            break

    if rows_printed == 0:
        # ASK queries will show one row with a boolean in rdflib,
        # but keep this fallback for empty resultsets.
        print("(no results)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Text2SPARQL offline: generate (and optionally run) SPARQL from an English question"
    )
    parser.add_argument("text", help="Question in English")
    parser.add_argument(
        "--ttl",
        default=os.path.join("data", "p510_sintetico.ttl"),
        help="Path to the TTL file",
    )
    parser.add_argument(
        "--mode",
        choices=["translate", "run"],
        default="run",
        help="Only generate SPARQL (translate) or generate + run it (run)",
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai_compat", "rules"],
        default="ollama",
        help="Local backend: ollama | openai_compat | rules",
    )
    parser.add_argument(
        "--model",
        default="llama3.1",
        help="Model name (depends on backend)",
    )
    parser.add_argument(
        "--examples",
        default=os.path.join("eval", "text2sparql_examples.jsonl"),
        help="Few-shot JSONL with NL↔SPARQL pairs",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Path to a system prompt text file with glossary/synonyms. Can use {LIMIT}.",
    )
    parser.add_argument(
        "--rules-first",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="If enabled, try the deterministic catalog mapping before using the LLM.",
    )
    parser.add_argument("--max-retries", type=int, default=2, help="Retries if validation/execution fails")
    parser.add_argument("--timeout", type=float, default=30.0, help="Backend timeout (seconds)")
    parser.add_argument("--temperature", type=float, default=0.1, help="Sampling temperature")
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="LIMIT to enforce if missing (SELECT only)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50,
        help="Max rows to print when running",
    )
    args = parser.parse_args()

    if not os.path.exists(args.ttl):
        raise SystemExit(
            f"File not found: {args.ttl}. Generate it first: python src/p510_generate_synthetic.py"
        )

    examples_path: str | None = args.examples
    if examples_path and not Path(examples_path).exists():
        examples_path = None

    g: Graph = load_graph(args.ttl)

    prompt_file: str | None = args.prompt_file
    if prompt_file is None:
        default_en = Path("prompts") / "system_en.txt"
        if default_en.exists():
            prompt_file = str(default_en)

    config = GenerationConfig(
        backend=args.backend,
        model=args.model,
        max_retries=args.max_retries,
        timeout_s=args.timeout,
        temperature=args.temperature,
        limit=args.limit,
        rules_first=bool(args.rules_first),
        prompt_file=prompt_file,
    )

    result = generate_sparql(g, args.text, config=config, examples_path=examples_path)

    print(f"Backend: {result.backend_used}")
    print(f"Attempts: {result.attempts}")
    print("-" * 80)
    print(result.sparql.strip())
    print("-" * 80)

    if args.mode == "translate":
        return

    qres = g.query(result.sparql)
    _print_results(qres, max_rows=args.rows)


if __name__ == "__main__":
    main()
