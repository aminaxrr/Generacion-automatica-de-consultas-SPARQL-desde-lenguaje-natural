# TFG — NL → SPARQL traceability (P510-like)

This repository is a TFG project about **generating/selecting SPARQL queries from Natural Language**, focused on **traceability** and **responsibility** (suppliers/owners).

It uses a synthetic RDF graph inspired by **LOTAR P510** (it is not a literal copy):

- Traceability relationships are modeled as **link nodes** of type `p510:Traceability_Link_Type`.
- Pattern example:

	- `?req p510:Satisfied_by ?link .`
	- `?link p510:Link ?model ; p510:ContentType "Physical Model" .`

This enables typical questions like: "are there links?", "is everything traced?", "how many X do I have?", "who is responsible?".

## Quickstart

1) Generate a synthetic P510-like graph:

`python src/p510_generate_synthetic.py`

Output: `data/p510_sintetico.ttl`

2) Run the SPARQL query catalog:

`python src/run_queries_p510.py`

Queries live in `queries_p510/`.

## NL → SPARQL baseline (deterministic)

Includes a **no-ML** baseline (rules + templates) that converts **English questions** into SPARQL and runs them.

Examples:

`python src/nl2sparql_cli.py "How many suppliers are there?"`

`python src/nl2sparql_cli.py "requirements without a physical model"`

`python src/nl2sparql_cli.py "models from Supplier 03"`

This is a reproducible starting point; you can later replace/extend the parser with a classifier, an LLM, etc.

## Text2SPARQL offline (NeoDash Text2Cypher style)

In addition to the rules baseline, there is an **LLM-like** but **local/offline** mode: it generates SPARQL from a question and validates/runs it on the RDF graph.

Script: `python src/text2sparql_cli.py "..."`

Modes:

- `--mode translate`: only generate SPARQL
- `--mode run`: generate + run (default)

Supported backends:

1) **Rules (no models, 100% reproducible)**

`python src/text2sparql_cli.py "How many suppliers are there?" --backend rules --mode run`

2) **Ollama (local)**

- Install/run Ollama and pull a model, for example:
	- `ollama pull llama3.1`

Example:

`python src/text2sparql_cli.py "requirements missing end-to-end traceability" --backend ollama --model llama3.1 --mode run`

Default endpoint is `http://localhost:11434/api/chat`. Override with:

- `TEXT2SPARQL_OLLAMA_URL`

3) **Local OpenAI-compatible server** (e.g., LM Studio, LocalAI, ...)

Configure:

- `TEXT2SPARQL_OPENAI_BASE_URL` (e.g., `http://localhost:1234`)
- `TEXT2SPARQL_OPENAI_API_KEY` (if applicable; can be empty)

Example:

`python src/text2sparql_cli.py "audit duplicate links" --backend openai_compat --model <your_model> --mode run`

### Single “mega prompt” with synonyms (supervisor style)

If you want the mapping/glossary/synonym logic to live fully in a prompt, edit:

- [prompts/system_en.txt](prompts/system_en.txt)

And run:

`python src/text2sparql_cli.py "physical models without tests" --backend ollama --model llama3.1 --prompt-file prompts/system_en.txt --mode run`

Notes:

- The prompt may include a `{LIMIT}` placeholder, replaced by `--limit`.
- If you do not pass `--prompt-file` and `prompts/system_en.txt` exists, it is used automatically.

### Safety / constraints

- Only `SELECT` or `ASK` queries are allowed (blocks `CONSTRUCT/DESCRIBE/INSERT/DELETE/...`).
- If a `SELECT` query has no `LIMIT`, the tool adds `LIMIT 200` (configurable via `--limit`).
- Few-shot examples are in `eval/text2sparql_examples.jsonl` to anchor generation to the `queries_p510/` catalog.

## Visual demo (local web)

There is a lightweight "NeoDash-like" visual demo **with no extra dependencies**: HTML+JS served by the Python standard library.

1) Run the demo:

`python src/demo_server.py`

2) Open:

`http://127.0.0.1:8000`

Notes:

- If `data/p510_sintetico.ttl` is missing, the demo can regenerate it ("Regenerate graph" button).
- To use Ollama: run `ollama serve` and ensure a model is pulled.

### (Optional) Streamlit demo

There is also a Streamlit version in `src/demo_visual.py`, but it depends on `streamlit/pandas` (may require Python ≤ 3.12 depending on wheel availability).

`pip install -r requirements.txt`

`python -m streamlit run src/demo_visual.py`

## Auto-evaluation

Script: `python src/text2sparql_eval.py`

1) Validate that reference SPARQL from JSONL executes (sanity check):

`python src/text2sparql_eval.py --mode reference`

2) Evaluate the generator (generate from NL and check execution):

`python src/text2sparql_eval.py --mode generate --backend rules`

With a local LLM:

`python src/text2sparql_eval.py --mode generate --backend ollama --model llama3.1`

## Included queries (examples)

- Requirements without physical model (missing `Satisfied_by`)
- Physical models without tests (missing `Verified_by`)
- Percentage of requirements with a model
- Requirements missing end-to-end traceability (Req → Model → Test)
- Over-specified requirements (more than one model)
- Supplier count
- Models per supplier

Also (closer to the XSD):

- PLM metadata summary (GeneralPLMInfo)
- Development environment info (RequirementsDevStructure)
- Used documents (`uses`)
- V&V scenarios with credibility (Requirements_Verification_Validation / Scenario)
- Audit: links missing timestamps

Data quality audits:

- Approved without approver (approval inconsistency)
- Links with `ContentType` inconsistent with the real target
- Duplicate traces (same source/predicate/target repeated)
- Links without `Description`

## Next step

Once the graph and the query catalog are stable, NL → SPARQL can be implemented at two levels:

- **Intent classification** (choose a predefined query).
- **Template filling** (e.g., filters by type/supplier/keyword).
