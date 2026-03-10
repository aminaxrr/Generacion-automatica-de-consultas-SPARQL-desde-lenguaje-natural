import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from rdflib import Graph

from p510_generate_synthetic import generar_grafo_p510
from run_queries_p510 import load_graph
from text2sparql import GenerationConfig, generate_sparql


def _ttl_mtime_key(ttl_path: str) -> float:
    try:
        return Path(ttl_path).stat().st_mtime
    except FileNotFoundError:
        return 0.0


@st.cache_resource
def _load_graph_cached(ttl_path: str, mtime_key: float) -> Graph:  # noqa: ARG001 - mtime_key busts cache
    return load_graph(ttl_path)


def _result_to_df(qres: Any, max_rows: int) -> pd.DataFrame:
    # rdflib ASK results expose askAnswer
    if hasattr(qres, "askAnswer") and qres.askAnswer is not None:
        return pd.DataFrame([{"askAnswer": bool(qres.askAnswer)}])

    vars_ = [str(v) for v in getattr(qres, "vars", [])]
    rows: list[dict[str, str]] = []

    for i, row in enumerate(qres):
        if max_rows is not None and i >= max_rows:
            break

        as_tuple = list(row)
        out: dict[str, str] = {}
        for j, var in enumerate(vars_):
            val = as_tuple[j] if j < len(as_tuple) else None
            out[var] = "" if val is None else str(val)
        rows.append(out)

    if not rows:
        return pd.DataFrame(columns=vars_)

    return pd.DataFrame(rows)


def main() -> None:
    st.set_page_config(page_title="TFG · Text2SPARQL (offline)", layout="wide")

    st.title("Text2SPARQL offline (demo visual)")
    st.caption("English question → SPARQL → execution over the P510-like RDF graph")

    with st.sidebar:
        st.header("Data")
        default_ttl = os.path.join("data", "p510_sintetico.ttl")
        ttl_path = st.text_input("TTL path", value=default_ttl)

        col_gen_a, col_gen_b = st.columns(2)
        with col_gen_a:
            n_req = st.number_input("#Requirements", min_value=5, max_value=500, value=50, step=5)
            n_models = st.number_input("#Models", min_value=5, max_value=500, value=30, step=5)
        with col_gen_b:
            n_tests = st.number_input("#Tests", min_value=1, max_value=500, value=20, step=5)
            n_suppliers = st.number_input("#Suppliers", min_value=1, max_value=50, value=6, step=1)

        if st.button("Generate/regenerate graph", use_container_width=True):
            out = generar_grafo_p510(
                out_path=ttl_path,
                n_requisitos=int(n_req),
                n_modelos=int(n_models),
                n_tests=int(n_tests),
                n_proveedores=int(n_suppliers),
            )
            st.success(f"Generated: {out}")
            st.cache_resource.clear()

        st.divider()

        st.header("Mode")
        st.caption("Deterministic catalog matching (no backend, no server)")

        st.divider()

        st.header("Generation")
        examples_path = st.text_input("Catalog JSONL", value=os.path.join("eval", "text2sparql_examples.jsonl"))
        synonyms_file = st.text_input("Synonyms prompt file", value=os.path.join("prompts", "system_en.txt"))
        classifier_model = st.text_input("Classifier model (optional)", value=os.path.join("models", "catalog_nb_v1.json"))
        classifier_min_prob = st.number_input(
            "Classifier min probability",
            min_value=0.0,
            max_value=1.0,
            value=0.60,
            step=0.01,
        )
        limit = st.number_input("LIMIT (if missing)", min_value=1, max_value=5000, value=200, step=50)
        threshold = st.number_input("Match threshold", min_value=0.0, max_value=1.0, value=0.35, step=0.01)

        st.divider()

        st.header("Execution")
        max_rows = st.number_input("Max rows", min_value=1, max_value=5000, value=200, step=50)

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Question")
        question = st.text_area(
            "",
            value="requirements missing end-to-end traceability",
            height=120,
            placeholder="E.g. 'models without tests' or 'audit duplicate links'",
        )

        run = st.button("Generate and run", type="primary", use_container_width=True)

        st.subheader("Graph")
        if not Path(ttl_path).exists():
            st.warning("TTL not found. Click 'Generate/regenerate graph' in the sidebar.")
        else:
            st.info(f"TTL: {ttl_path}")

    with right:
        st.subheader("Results")

        if run:
            if not Path(ttl_path).exists():
                st.error("TTL not found. Generate the graph first.")
            elif not question.strip():
                st.error("Write a question in English.")
            else:
                start = time.perf_counter()
                try:
                    g = _load_graph_cached(ttl_path, _ttl_mtime_key(ttl_path))

                    cfg = GenerationConfig(
                        limit=int(limit),
                        match_threshold=float(threshold),
                        synonyms_file=(synonyms_file if Path(synonyms_file).exists() else None),
                        classifier_model_file=(classifier_model if Path(classifier_model).exists() else None),
                        classifier_min_prob=float(classifier_min_prob),
                    )

                    examples_path_eff = examples_path if Path(examples_path).exists() else None
                    result = generate_sparql(g, question.strip(), config=cfg, examples_path=examples_path_eff)

                    elapsed = time.perf_counter() - start
                    ms = result.match_score
                    ms_s = f"{ms:.3f}" if isinstance(ms, float) else "n/a"
                    st.success(
                        f"OK · match={result.matched_id or 'catalog'} · score={ms_s} · attempts={result.attempts} · {elapsed:.2f}s"
                    )

                    with st.expander("Generated SPARQL", expanded=True):
                        st.code(result.sparql.strip(), language="sparql")

                    qres = g.query(result.sparql)
                    df = _result_to_df(qres, max_rows=int(max_rows))

                    with st.expander("Query results", expanded=True):
                        st.dataframe(df, use_container_width=True)

                except Exception as e:  # noqa: BLE001
                    elapsed = time.perf_counter() - start
                    st.error(f"Failed after {elapsed:.2f}s: {e}")


if __name__ == "__main__":
    main()
