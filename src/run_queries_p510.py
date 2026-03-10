import argparse
import os
from pathlib import Path

from rdflib import Graph


def load_graph(ttl_path: str) -> Graph:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return g


def run_queries(graph: Graph, queries_dir: str, pattern: str = "*.sparql") -> None:
    qdir = Path(queries_dir)
    files = sorted([p for p in qdir.glob(pattern)])
    if not files:
        raise RuntimeError(f"No .sparql files found in {queries_dir} matching pattern {pattern}")

    for qfile in files:
        print("\n" + "=" * 80)
        print(qfile.name)
        print("-" * 80)
        query = qfile.read_text(encoding="utf-8")
        qres = graph.query(query)
        vars_ = [str(v) for v in qres.vars]
        res = list(qres)
        if not res:
            print("(no results)")
            continue

        if vars_:
            print(" | ".join(vars_))
            print("-" * 80)

        for row in res:
            print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SPARQL queries over the P510-like graph")
    parser.add_argument("--ttl", default=os.path.join("data", "p510_sintetico.ttl"), help="Path to the TTL file")
    parser.add_argument("--queries", default="queries_p510", help="Folder containing .sparql files")
    parser.add_argument(
        "--pattern",
        default="*.sparql",
        help="Glob pattern for query files (e.g. 'q14_*.sparql' or 'q6_*.sparql')",
    )
    args = parser.parse_args()

    if not os.path.exists(args.ttl):
        raise SystemExit(
            f"File not found: {args.ttl}. Generate it first: python src/p510_generate_synthetic.py"
        )

    g = load_graph(args.ttl)
    run_queries(g, args.queries, pattern=args.pattern)
