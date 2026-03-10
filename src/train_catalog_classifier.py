import argparse
import os
from pathlib import Path

from text2sparql import SynonymMap, _load_synonyms_file, _nb_train, nb_save  # type: ignore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a simple offline Naive Bayes catalog classifier (no backend)"
    )
    parser.add_argument(
        "--examples",
        default=os.path.join("eval", "text2sparql_examples.jsonl"),
        help="JSONL catalog with fields: id, nl, sparql",
    )
    parser.add_argument(
        "--synonyms-file",
        default=os.path.join("prompts", "system_en.txt"),
        help="Synonyms prompt file (uses ### SYNONYMS START/END block if present)",
    )
    parser.add_argument(
        "--out",
        default=os.path.join("models", "catalog_nb_v1.json"),
        help="Output model path",
    )
    parser.add_argument("--alpha", type=float, default=1.0, help="Laplace smoothing")

    args = parser.parse_args()

    ex_path = Path(args.examples)
    if not ex_path.exists():
        raise SystemExit(f"Examples file not found: {ex_path}")

    synonyms: SynonymMap | None = None
    syn_path = Path(args.synonyms_file)
    if syn_path.exists():
        synonyms = _load_synonyms_file(str(syn_path))

    # Reuse loader from engine by reading JSONL via text2sparql.
    # Avoid importing private function at top-level to keep this script simple.
    import json

    examples = []
    for line in ex_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        examples.append(json.loads(line))

    model = _nb_train(examples, synonyms=synonyms, alpha=float(args.alpha))
    nb_save(model, str(args.out))

    print(f"Saved model: {args.out}")
    print(f"Classes: {len(model.classes)}")
    print(f"Vocab size: {len(model.vocab)}")


if __name__ == "__main__":
    main()
