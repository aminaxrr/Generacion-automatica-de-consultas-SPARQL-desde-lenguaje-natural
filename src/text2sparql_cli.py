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
        description="Text2SPARQL offline (no backend): map an English question to a known SPARQL query from a JSONL catalog"
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
        "--examples",
        default=os.path.join("eval", "text2sparql_examples.jsonl"),
        help="JSONL catalog with 'nl' and 'sparql' fields",
    )
    parser.add_argument(
        "--synonyms-file",
        default=None,
        help=(
            "Optional synonyms/glossary 'prompt' file. If it contains a '### SYNONYMS START/END' block, "
            "only that block is parsed. Defaults to prompts/system_en.txt when present."
        ),
    )
    parser.add_argument(
        "--classifier-model",
        default=None,
        help=(
            "Optional offline classifier model file (trained from the catalog). "
            "If provided and confident enough, it selects the catalog id directly."
        ),
    )
    parser.add_argument(
        "--classifier-min-prob",
        type=float,
        default=0.60,
        help="Minimum probability to accept classifier prediction (otherwise fallback to similarity matcher)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="LIMIT to enforce if missing (SELECT only)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Minimum similarity score required to accept a match",
    )
    parser.add_argument(
        "--suggestions",
        type=int,
        default=3,
        help="How many candidate matches to show on failure",
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

    config = GenerationConfig(
        limit=args.limit,
        match_threshold=float(args.threshold),
        max_suggestions=int(args.suggestions),
        synonyms_file=args.synonyms_file,
        classifier_model_file=args.classifier_model,
        classifier_min_prob=float(args.classifier_min_prob),
    )

    result = generate_sparql(g, args.text, config=config, examples_path=examples_path)

    print(f"Attempts: {result.attempts}")
    if result.matched_id or result.matched_nl:
        mid = result.matched_id or "(no id)"
        mnl = result.matched_nl or "(no nl)"
        ms = result.match_score
        ms_s = f"{ms:.3f}" if isinstance(ms, float) else "(n/a)"
        print(f"Matched: {mid} · score={ms_s}")
        print(f"Matched NL: {mnl}")
    print("-" * 80)
    print(result.sparql.strip())
    print("-" * 80)

    if args.mode == "translate":
        return

    qres = g.query(result.sparql)
    _print_results(qres, max_rows=args.rows)


if __name__ == "__main__":
    main()
