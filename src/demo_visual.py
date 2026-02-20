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
    st.caption("Pregunta en español → SPARQL → ejecución sobre el grafo RDF P510-like")

    with st.sidebar:
        st.header("Datos")
        default_ttl = os.path.join("data", "p510_sintetico.ttl")
        ttl_path = st.text_input("Ruta TTL", value=default_ttl)

        col_gen_a, col_gen_b = st.columns(2)
        with col_gen_a:
            n_req = st.number_input("#Req", min_value=5, max_value=500, value=50, step=5)
            n_models = st.number_input("#Modelos", min_value=5, max_value=500, value=30, step=5)
        with col_gen_b:
            n_tests = st.number_input("#Tests", min_value=1, max_value=500, value=20, step=5)
            n_suppliers = st.number_input("#Proveedores", min_value=1, max_value=50, value=6, step=1)

        if st.button("Generar/Regenerar grafo", use_container_width=True):
            out = generar_grafo_p510(
                out_path=ttl_path,
                n_requisitos=int(n_req),
                n_modelos=int(n_models),
                n_tests=int(n_tests),
                n_proveedores=int(n_suppliers),
            )
            st.success(f"Generado: {out}")
            st.cache_resource.clear()

        st.divider()

        st.header("Backend")
        backend = st.selectbox("Backend", options=["rules", "ollama", "openai_compat"], index=1)
        model = st.text_input("Modelo", value="llama3.2:3b" if backend == "ollama" else "llama3.1")

        st.caption("Variables de entorno útiles")
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

        st.header("Generación")
        examples_path = st.text_input("Few-shot JSONL", value=os.path.join("eval", "text2sparql_examples.jsonl"))
        rules_first = st.checkbox("Rules-first (catálogo → LLM)", value=True)
        max_retries = st.number_input("Reintentos", min_value=0, max_value=5, value=2, step=1)
        timeout_s = st.number_input("Timeout backend (s)", min_value=1.0, max_value=600.0, value=30.0, step=5.0)
        temperature = st.number_input("Temperatura", min_value=0.0, max_value=2.0, value=0.1, step=0.05)
        limit = st.number_input("LIMIT (si falta)", min_value=1, max_value=5000, value=200, step=50)

        st.divider()

        st.header("Ejecución")
        max_rows = st.number_input("Filas máx", min_value=1, max_value=5000, value=200, step=50)

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Pregunta")
        question = st.text_area(
            "",
            value="requisitos sin trazabilidad end to end",
            height=120,
            placeholder="Ej: 'modelos sin test' o 'auditoría links duplicados'",
        )

        run = st.button("Generar y ejecutar", type="primary", use_container_width=True)

        st.subheader("Grafo")
        if not Path(ttl_path).exists():
            st.warning("No existe el TTL. Pulsa 'Generar/Regenerar grafo' en la barra lateral.")
        else:
            st.info(f"TTL: {ttl_path}")

    with right:
        st.subheader("Resultado")

        if run:
            if not Path(ttl_path).exists():
                st.error("No existe el TTL. Genera el grafo primero.")
            elif not question.strip():
                st.error("Escribe una pregunta en español.")
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

                    with st.expander("SPARQL generada", expanded=True):
                        st.code(result.sparql.strip(), language="sparql")

                    qres = g.query(result.sparql)
                    df = _result_to_df(qres, max_rows=int(max_rows))

                    with st.expander("Resultados", expanded=True):
                        st.dataframe(df, use_container_width=True)

                except Exception as e:  # noqa: BLE001
                    elapsed = time.perf_counter() - start
                    st.error(f"Fallo tras {elapsed:.2f}s: {e}")


if __name__ == "__main__":
    main()
