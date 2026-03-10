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

        st.header("Backend")
        backend = st.selectbox("Backend", options=["rules", "ollama", "openai_compat"], index=1)
        model = st.text_input("Model", value="llama3.2:3b" if backend == "ollama" else "llama3.1")

        st.caption("Useful environment variables")
        st.code(
            "\n".join(
                [
                    "TEXT2SPARQL_OLLAMA_URL=http://localhost:11434/api/chat",
                    "TEXT2SPARQL_OPENAI_BASE_URL=http://localhost:1234",
                    "TEXT2SPARQL_OPENAI_API_KEY=",
                ]
            )
        )

        st.divider()

        st.header("Generation")
        examples_path = st.text_input("Few-shot JSONL", value=os.path.join("eval", "text2sparql_examples.jsonl"))
        rules_first = st.checkbox("Rules-first (catalog → LLM)", value=False)
        max_retries = st.number_input("Retries", min_value=0, max_value=5, value=2, step=1)
        timeout_s = st.number_input("Timeout backend (s)", min_value=1.0, max_value=600.0, value=30.0, step=5.0)
        temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, value=0.1, step=0.05)
        limit = st.number_input("LIMIT (if missing)", min_value=1, max_value=5000, value=200, step=50)

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
                        backend=backend,
                        model=model.strip() or "llama3.1",
                        max_retries=int(max_retries),
                        timeout_s=float(timeout_s),
                        temperature=float(temperature),
                        limit=int(limit),
                        rules_first=bool(rules_first),
                    )

                    examples_path_eff = examples_path if Path(examples_path).exists() else None
                    result = generate_sparql(g, question.strip(), config=cfg, examples_path=examples_path_eff)

                    elapsed = time.perf_counter() - start
                    st.success(f"OK · backend={result.backend_used} · attempts={result.attempts} · {elapsed:.2f}s")

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
