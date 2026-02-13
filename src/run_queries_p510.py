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
        raise RuntimeError(f"No hay .sparql en {queries_dir} con patrón {pattern}")

    for qfile in files:
        print("\n" + "=" * 80)
        print(qfile.name)
        print("-" * 80)
        query = qfile.read_text(encoding="utf-8")
        qres = graph.query(query)
        vars_ = [str(v) for v in qres.vars]
        res = list(qres)
        if not res:
            print("(sin resultados)")
            continue

        if vars_:
            print(" | ".join(vars_))
            print("-" * 80)

        for row in res:
            print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta consultas SPARQL sobre el grafo P510-like")
    parser.add_argument("--ttl", default=os.path.join("data", "p510_sintetico.ttl"), help="Ruta al TTL")
    parser.add_argument("--queries", default="queries_p510", help="Carpeta con .sparql")
    parser.add_argument(
        "--pattern",
        default="*.sparql",
        help="Patrón glob de queries (ej: 'q14_*.sparql' o 'q6_*.sparql')",
    )
    args = parser.parse_args()

    if not os.path.exists(args.ttl):
        raise SystemExit(f"No existe {args.ttl}. Ejecuta primero: python src/p510_generate_synthetic.py")

    g = load_graph(args.ttl)
    run_queries(g, args.queries, pattern=args.pattern)
