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

## Text2SPARQL offline (dynamic generator + checker)

This tool generates SPARQL **dynamically** from an English question (no backend, no server) by:

- tokenizing/normalizing the question (with a synonyms/glossary file),
- mapping terms to real **classes/properties present in the RDF graph**,
- building a SPARQL query on-the-fly,
- and running a checker to avoid invented terms.

Script: `python src/text2sparql_cli.py "..."`

Modes:

- `--mode translate`: only generate SPARQL
- `--mode run`: generate + run (default)

Optional catalog mode (legacy):

- `eval/text2sparql_examples.jsonl` (fields: `nl`, `sparql`, optional `id`)

Synonyms / glossary ("prompt" file):

- Edit `prompts/system_en.txt` and maintain the `### SYNONYMS START/END` block.
- This project parses that block locally (no LLM) to normalize synonyms before matching.

Example:

`python src/text2sparql_cli.py "requirements missing end-to-end traceability" --mode run --engine dynamic`

Catalog mode example:

`python src/text2sparql_cli.py "requirements missing end-to-end traceability" --mode run --engine catalog --examples eval/text2sparql_examples.jsonl`

### (Optional) Offline classifier ("own model")

If you want a simple **self-contained model** (still no backend/server), you can train a Multinomial Naive Bayes classifier on the catalog and let it predict the best `id`.

1) Train:

`python src/train_catalog_classifier.py --examples eval/text2sparql_examples.jsonl --out models/catalog_nb_v1.json`

2) Use it (falls back to similarity matching if not confident enough):

`python src/text2sparql_cli.py "how many suppliers are there" --classifier-model models/catalog_nb_v1.json --classifier-min-prob 0.60`

If a question does not match any known example above a similarity threshold, the tool fails and prints the closest candidates.

### Safety / constraints

- Only `SELECT` or `ASK` queries are allowed (blocks `CONSTRUCT/DESCRIBE/INSERT/DELETE/...`).
- If a `SELECT` query has no `LIMIT`, the tool adds `LIMIT 200` (configurable via `--limit`).
- Checker: blocks queries that reference QNames not present in the graph schema (prevents invented classes/properties).

## Visual demo (local web)

There is a lightweight "NeoDash-like" visual demo **with no extra dependencies**: HTML+JS served by the Python standard library.

1) Run the demo:

`python src/demo_server.py`

2) Open:

`http://127.0.0.1:8000`

Notes:

- If `data/p510_sintetico.ttl` is missing, the demo can regenerate it ("Regenerate graph" button).
- The web demo also accepts a classifier model path (defaults to `models/catalog_nb_v1.json`).

### (Optional) Streamlit demo

There is also a Streamlit version in `src/demo_visual.py`, but it depends on `streamlit/pandas` (may require Python ≤ 3.12 depending on wheel availability).

`pip install -r requirements.txt`

`python -m streamlit run src/demo_visual.py`

## Auto-evaluation

Script: `python src/text2sparql_eval.py`

1) Validate that reference SPARQL from JSONL executes (sanity check):

`python src/text2sparql_eval.py --mode reference`

2) Evaluate the generator (generate from NL and check execution):

`python src/text2sparql_eval.py --mode generate`

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
