import argparse
import os
from pathlib import Path

from rdflib import Graph

from nl2sparql import ParsedNLQuery, parse_english_question
from run_queries_p510 import load_graph


def _escape_sparql_string(value: str) -> str:
    # Simple, sufficient escaping for literal string usage in this demo.
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_query(parsed: ParsedNLQuery, queries_dir: str) -> str:
    if parsed.kind == "file":
        if not parsed.query_file:
            raise ValueError("parsed.query_file is required")
        qpath = Path(queries_dir) / parsed.query_file
        if not qpath.exists():
            raise FileNotFoundError(f"Query file not found: {qpath}")
        return qpath.read_text(encoding="utf-8")

    if parsed.kind == "supplier_models":
        if not parsed.supplier_name:
            raise ValueError("parsed.supplier_name is required")
        supplier = _escape_sparql_string(parsed.supplier_name)
        return f"""PREFIX p510: <http://www.lotar.org/schemas/mbse/p510#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ex:   <http://example.org/tfg/mbse#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT ?modelo ?id ?provName
WHERE {{
  ?modelo rdf:type p510:DesignModel ;
          p510:Id ?id ;
          ex:providedBy ?prov .
  ?prov foaf:name ?provName .
  FILTER(LCASE(STR(?provName)) = LCASE("{supplier}"))
}}
ORDER BY ?id
"""

    raise ValueError(f"Unknown kind: {parsed.kind}")


def run_query(graph: Graph, query: str, limit: int | None = None) -> None:
    qres = graph.query(query)
    vars_ = [str(v) for v in qres.vars]

    print(" | ".join(vars_))
    print("-" * 80)

    rows_printed = 0
    for row in qres:
        print(" | ".join(str(x) for x in row))
        rows_printed += 1
        if limit is not None and rows_printed >= limit:
            break

    if rows_printed == 0:
        print("(no results)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline NL→SPARQL demo over the P510-like graph")
    parser.add_argument("text", help="Question in English")
    parser.add_argument("--ttl", default=os.path.join("data", "p510_sintetico.ttl"), help="Path to the TTL file")
    parser.add_argument("--queries", default="queries_p510", help="Folder containing .sparql files")
    parser.add_argument("--limit", type=int, default=50, help="Max rows to print")
    args = parser.parse_args()

    parsed = parse_english_question(args.text)
    sparql = build_query(parsed, args.queries)

    print(f"Intent: {parsed.kind}")
    if parsed.query_file:
        print(f"Query: {parsed.query_file}")
    if parsed.supplier_name:
        print(f"Supplier: {parsed.supplier_name}")
    print("-" * 80)

    g = load_graph(args.ttl)
    run_query(g, sparql, limit=args.limit)


if __name__ == "__main__":
    main()
