import time
import sys
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from run_queries_p510 import load_graph  # noqa: E402
from text2sparql import GenerationConfig, generate_sparql  # noqa: E402


@dataclass(frozen=True)
class Case:
    group: str
    nl: str


CASES: list[Case] = [
    # A) Counts
    Case("A.count.suppliers", "How many suppliers are there?"),
    Case("A.count.suppliers", "Count the suppliers."),
    Case("A.count.suppliers", "What is the total number of organizations (suppliers)?"),
    Case("A.count.requirements", "How many requirements are there?"),
    Case("A.count.links", "Count the traceability links."),

    # B) Missing traceability
    Case("B.missing.req_without_physical_model", "List requirements without a physical model."),
    Case("B.missing.req_without_physical_model", "Which requirements are missing a Physical Model (Satisfied_by)?"),
    Case("B.missing.req_without_physical_model", "Show requirements that do not have any physical model linked."),

    Case("B.missing.models_without_tests", "Which physical models do not have any associated test case?"),
    Case("B.missing.models_without_tests", "List models missing verification tests (Verified_by)."),
    Case("B.missing.models_without_tests", "Show physical models that are not verified by any test."),

    Case("B.missing.end_to_end", "Find requirements missing end-to-end traceability (Req → Model → Test)."),
    Case("B.missing.end_to_end", "Which requirements do not have full traceability from requirement to model to test?"),
    Case("B.missing.end_to_end", "List requirements with no complete chain to a test."),

    # C) Percent
    Case("C.percent.req_with_model", "Compute the percentage of requirements that have at least one physical model."),
    Case("C.percent.req_with_model", "What percentage of requirements are satisfied by a physical model?"),
    Case("C.percent.req_with_model", "Ratio of requirements with a physical model."),

    # D) Link audits
    Case("D.audit.links_missing_timestamps", "Audit: links missing mandatory timestamps (Timestamp_Archiving or Timestamp_PLM)."),
    Case("D.audit.links_missing_timestamps", "Find traceability links without timestamps."),
    Case("D.audit.links_missing_timestamps", "Show links where Timestamp_Archiving or Timestamp_PLM is missing."),

    Case("D.audit.links_without_description", "Audit: links without a description."),
    Case("D.audit.links_without_description", "Find traceability links missing Description."),
    Case("D.audit.links_without_description", "Show links that do not have any description."),

    Case("D.audit.contenttype_mismatch", "Audit: links whose ContentType is inconsistent with the real target."),
    Case("D.audit.contenttype_mismatch", "Find links where link ContentType differs from target ContentType."),
    Case("D.audit.contenttype_mismatch", "Show ContentType mismatches between link nodes and their targets."),

    Case("D.audit.duplicates", "Audit: duplicate traces (same source + predicate + target repeated)."),
    Case("D.audit.duplicates", "Find duplicate links / repeated traceability relationships."),
    Case("D.audit.duplicates", "Detect redundant traceability links (same src, same relation, same target)."),

    # E) Governance
    Case("E.audit.req_without_approver", "Audit: requirements without an approver."),
    Case("E.audit.req_without_approver", "Find requirements missing Approver."),
    Case("E.audit.req_without_approver", "Show requirements that do not have any approver."),

    Case("E.audit.approved_without_approver", "Audit: entities marked Approved but missing Approver."),
    Case("E.audit.approved_without_approver", "Find approved requirements/models with no approver."),
    Case("E.audit.approved_without_approver", "Show entities with Approval_State = Approved and no Approver."),

    # F) Group-by distributions
    Case("F.groupby.req_by_maturity", "Distribution of requirements by maturity state."),
    Case("F.groupby.req_by_maturity", "Group requirements by Maturity_State."),
    Case("F.groupby.req_by_maturity", "Count requirements per maturity state."),

    Case("F.groupby.req_by_author_org", "Distribution of requirements by author organization."),
    Case("F.groupby.req_by_author_org", "Group requirements by Author_Organization."),
    Case("F.groupby.req_by_author_org", "How many requirements per author organization?"),

    Case("F.groupby.models_by_approval", "How many models are there per approval state?"),
    Case("F.groupby.models_by_approval", "Group physical models by Approval_State."),
    Case("F.groupby.models_by_approval", "Count models per approval state."),

    Case("F.groupby.req_by_subsystem", "Distribution of requirements by subsystem."),
    Case("F.groupby.req_by_subsystem", "Group requirements by subsystem."),
    Case("F.groupby.req_by_subsystem", "Count requirements per subsystem."),

    Case(
        "F.groupby.req_by_verification_method",
        "How many requirements are verified by Test/Analysis/Inspection/Demonstration?",
    ),
    Case("F.groupby.req_by_verification_method", "Group requirements by verification method."),
    Case("F.groupby.req_by_verification_method", "Distribution of requirements by how they are verified."),

    # G) Manifest
    Case("G.manifest.plm_summary", "Give me the PLM summary from the manifest (organization, purpose, version)."),
    Case("G.manifest.plm_summary", "Show manifest PLM info (organization, created on, purpose, objective, version)."),
    Case("G.manifest.plm_summary", "Manifest overview: org, created date, purpose, objective, version."),

    Case("G.manifest.dev_environment", "Show the development environment (tools, OS, language)."),
    Case("G.manifest.dev_environment", "What tools and OS are used in the requirements development environment?"),
    Case(
        "G.manifest.dev_environment",
        "List dev environment details: tool name/version, OS name/version, language.",
    ),

    Case("G.manifest.used_documents", "Which documents are used in the development environment?"),
    Case("G.manifest.used_documents", "List referenced documents used by the dev environment."),
    Case("G.manifest.used_documents", "Show documents linked via uses in the manifest dev structure."),

    Case("G.manifest.baseline", "What are the manifest project code, product, and baseline?"),
    Case(
        "G.manifest.baseline",
        "Show baseline information (name, id, created date) and project/product from the manifest.",
    ),
    Case("G.manifest.baseline", "Which baseline version/release is loaded in the manifest?"),

    # H) V&V scenarios
    Case("H.vnv.summary", "V&V scenarios summary: scenario, credibility, and linked targets."),
    Case("H.vnv.summary", "Show VnV scenarios with verification/validation credibility and targets."),
    Case("H.vnv.summary", "List each scenario id with linked targets (verified_by/validated_by)."),

    Case("H.vnv.incomplete", "Find incomplete V&V scenarios (no Verified_by and no Validated_by)."),
    Case("H.vnv.incomplete", "Which V&V scenarios have neither Verified_by nor Validated_by links?"),
    Case("H.vnv.incomplete", "List scenarios missing both verification and validation links."),

    # I) Supplier / provider
    Case("I.supplier.models_for_supplier", "List the models provided by Supplier 03."),
    Case("I.supplier.models_for_supplier", "Show physical models provided by Supplier 03."),
    Case("I.supplier.models_for_supplier", "Which models belong to supplier Supplier 03?"),

    Case("I.supplier.models_by_supplier", "How many models are there per supplier?"),
    Case("I.supplier.models_by_supplier", "Count physical models per provider."),
    Case("I.supplier.models_by_supplier", "List suppliers and the number of models they provide."),
]


def _rows(qres) -> int:
    # Force evaluation
    return sum(1 for _ in qres)


def _operator_from_explanation(expl: list[str] | None) -> str:
    if not expl:
        return "(none)"
    for line in expl:
        if line.startswith("operator:"):
            return line.split(":", 1)[1].strip()
    return "(none)"


def main() -> None:
    g = load_graph("data/p510_sintetico.ttl")
    cfg = GenerationConfig(engine="dynamic", limit=200)

    ok = 0
    fail = 0

    by_group: dict[str, list[tuple[str, int, str]]] = {}

    started_all = time.perf_counter()
    for i, case in enumerate(CASES, start=1):
        t0 = time.perf_counter()
        try:
            res = generate_sparql(g, case.nl, config=cfg)
            op = _operator_from_explanation(res.explanation)
            rows = _rows(g.query(res.sparql))
            ok += 1
            by_group.setdefault(case.group, []).append((op, rows, case.nl))
            dt = (time.perf_counter() - t0) * 1000
            print(f"[OK]   {i:02d}/{len(CASES)}  {case.group:35s}  op={op:30s}  rows={rows:4d}  {dt:7.1f}ms")
        except Exception as e:  # noqa: BLE001
            fail += 1
            dt = (time.perf_counter() - t0) * 1000
            print(f"[FAIL] {i:02d}/{len(CASES)}  {case.group:35s}  {dt:7.1f}ms  {case.nl}")
            print(f"       {type(e).__name__}: {e}")

    elapsed_all = time.perf_counter() - started_all

    print("-" * 100)
    print(f"Total: {len(CASES)} | OK: {ok} | FAIL: {fail} | elapsed={elapsed_all:.2f}s")

    # Group consistency checks
    print("\nGroup consistency (operator sets + row counts):")
    for group, items in sorted(by_group.items()):
        ops = sorted(set(op for op, _rows, _nl in items))
        rowset = sorted(set(r for _op, r, _nl in items))
        flag = ""
        if len(ops) > 1:
            flag += " OP_MISMATCH"
        if len(rowset) > 1:
            flag += " ROWS_DIFF"
        print(f"- {group:35s} ops={ops} rows={rowset}{flag}")


if __name__ == "__main__":
    main()
