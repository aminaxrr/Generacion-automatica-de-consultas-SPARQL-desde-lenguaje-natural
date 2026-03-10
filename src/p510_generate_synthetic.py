import os
import random
import uuid
from datetime import datetime, timezone

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

BASE = "http://www.lotar.org/schemas/mbse/"
P510 = Namespace(BASE + "p510#")
INSTANCES_ROOT = BASE + "p510/instances/"

EX = Namespace("http://example.org/tfg/mbse#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_instance_uri(instances_base: Namespace, local_prefix: str) -> URIRef:
    return instances_base[f"_{local_prefix}_{uuid.uuid4()}"]


def _mk_link(
    g: Graph,
    link_predicate: URIRef,
    source: URIRef,
    target: URIRef,
    content_type: str,
    description: str | None = None,
    link_type: str = "Local",
    traceability_root: URIRef | None = None,
    *,
    prob_missing_timestamp: float = 0.0,
    prob_wrong_contenttype: float = 0.0,
    prob_missing_description: float = 0.0,
    content_type_universe: list[str] | None = None,
) -> URIRef:
    """Create a `p510:Traceability_Link_Type` node and attach it from `source` using `link_predicate`."""
    instances_base = Namespace(str(source).rsplit("/", 1)[0] + "/")
    link = _new_instance_uri(instances_base, str(link_predicate).split("#")[-1])

    g.add((link, RDF.type, P510.Traceability_Link_Type))
    g.add((link, P510.Type, Literal(link_type)))
    g.add((link, P510.Link, target))

    chosen_ct = content_type
    if content_type_universe and random.random() < prob_wrong_contenttype:
        alternatives = [ct for ct in content_type_universe if ct != content_type]
        if alternatives:
            chosen_ct = random.choice(alternatives)
    g.add((link, P510.ContentType, Literal(chosen_ct)))

    if description and random.random() > prob_missing_description:
        g.add((link, P510.Description, Literal(description)))

    ts = _now_iso()
    if random.random() < prob_missing_timestamp:
        # Omit one of the two timestamps
        if random.random() < 0.5:
            g.add((link, P510.Timestamp_Archiving, Literal(ts, datatype=XSD.dateTime)))
        else:
            g.add((link, P510.Timestamp_PLM, Literal(ts, datatype=XSD.dateTime)))
    else:
        g.add((link, P510.Timestamp_Archiving, Literal(ts, datatype=XSD.dateTime)))
        g.add((link, P510.Timestamp_PLM, Literal(ts, datatype=XSD.dateTime)))

    g.add((source, link_predicate, link))
    if traceability_root is not None:
        g.add((traceability_root, link_predicate, link))
    return link


def generar_grafo_p510(
    out_path: str = os.path.join("data", "p510_sintetico.ttl"),
    n_requisitos: int = 50,
    n_modelos: int = 30,
    n_tests: int = 20,
    prob_req_sin_modelo: float = 0.15,
    prob_modelo_sin_test: float = 0.20,
    n_proveedores: int = 6,
    prob_modelo_sin_proveedor: float = 0.05,
    prob_req_sin_aprobador: float = 0.12,
    prob_req_sin_org_autora: float = 0.08,
    prob_link_missing_timestamp: float = 0.07,
    prob_link_wrong_contenttype: float = 0.04,
    prob_link_duplicate: float = 0.05,
    prob_link_missing_description: float = 0.05,
) -> str:
    """Generate a "P510-like" RDF graph."""

    random.seed(42)

    content_type_universe = [
        "Requirement",
        "Logical Model",
        "Physical Model",
        "Test Plan",
        "Test Case",
        "Document",
        "Evidence",
        "Other",
    ]

    g = Graph()
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("p510", P510)
    g.bind("foaf", FOAF)
    g.bind("ex", EX)
    g.bind("dcterms", DCTERMS)
    g.bind("prov", PROV)

    # To resemble the professor's TTL: URIs under /p510/instances/<seed>/... plus container nodes.
    seed = str(random.randint(1_000_000_000, 9_999_999_999))
    instances_base = Namespace(f"{INSTANCES_ROOT}{seed}/")

    manifest = _new_instance_uri(instances_base, "P510_Manifest")
    g.add((manifest, RDF.type, P510.P510_ManifestType))
    g.add((manifest, RDFS.label, Literal("P510_Manifest")))
    g.add((manifest, P510.Id, Literal(f"P510-MANIFEST-{seed}")))
    g.add((manifest, P510.Description, Literal("Synthetic P510-like manifest for the TFG")))

    # Dataset node (editorial metadata / reproducibility)
    dataset = _new_instance_uri(instances_base, "Dataset")
    g.add((dataset, RDF.type, EX.Dataset))
    g.add((dataset, RDFS.label, Literal("Dataset")))
    g.add((dataset, DCTERMS.title, Literal("Synthetic P510-like dataset")))
    g.add((dataset, DCTERMS.created, Literal(_now_iso(), datatype=XSD.dateTime)))
    g.add((dataset, EX.seed, Literal(seed)))
    g.add((dataset, EX.generator, Literal("p510_generate_synthetic.py")))
    g.add((dataset, EX.generator_version, Literal("1.1")))
    g.add((manifest, EX.describesDataset, dataset))

    general_info = _new_instance_uri(instances_base, "GeneralPLMInfo")
    g.add((general_info, RDF.type, P510.GeneralPLMInfoType))
    g.add((general_info, RDFS.label, Literal("GeneralPLMInfo")))
    g.add((manifest, P510.has_GeneralPLMInfo, general_info))
    # Also add a "typed element" relation to better resemble the reference serialization.
    g.add((manifest, P510.GeneralPLMInfo, general_info))

    # Typical XSD fields (more complete)
    g.add((general_info, P510.Unique_object_id, Literal(str(uuid.uuid4()))))
    g.add((general_info, P510.Unique_baseline_id, Literal(str(uuid.uuid4()))))
    g.add((general_info, P510.Version_identifier, Literal("1.0")))
    created_ts = _now_iso()
    g.add((general_info, P510.Created_on, Literal(created_ts, datatype=XSD.dateTime)))
    g.add((general_info, P510.Last_Modified_Date, Literal(created_ts, datatype=XSD.dateTime)))
    g.add((general_info, P510.Model_Purpose, Literal("TFG: SPARQL queries from Natural Language")))
    g.add((general_info, P510.Model_Objective, Literal("Audit traceability and responsibilities")))
    g.add((general_info, P510.Organization, Literal("University")))
    g.add((general_info, EX.project_code, Literal("TFG-MBSE-P510")))
    g.add((general_info, EX.product, Literal("Aircraft System (synthetic)")))
    g.add((general_info, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork"])) ))
    g.add((general_info, P510.Approval_State, Literal(random.choice(["Pending", "Approved"])) ))
    g.add((general_info, P510.Created_by, Literal(random.choice(["Amina", "Supervisor", "MBSE Team"]))))
    g.add((general_info, P510.Author_Organization, Literal("University")))

    baseline = _new_instance_uri(instances_base, "Baseline")
    g.add((baseline, RDF.type, EX.Baseline))
    g.add((baseline, RDFS.label, Literal("Baseline")))
    g.add((baseline, EX.baseline_id, Literal(str(uuid.uuid4()))))
    g.add((baseline, EX.baseline_name, Literal(random.choice(["BL-0", "BL-1", "BL-2"])) ))
    g.add((baseline, DCTERMS.created, Literal(created_ts, datatype=XSD.dateTime)))
    g.add((general_info, EX.hasBaseline, baseline))

    dev_struct = _new_instance_uri(instances_base, "RequirementsDevStructure")
    g.add((dev_struct, RDF.type, P510.RequirementsDevStructureType))
    g.add((dev_struct, RDFS.label, Literal("RequirementsDevStructure")))
    g.add((manifest, P510.has_RequirementsDevStructure, dev_struct))
    g.add((manifest, P510.RequirementsDevStructure, dev_struct))

    # XSD fields: RequirementsDevStructureType
    g.add((dev_struct, P510.DevTool_Name, Literal("ReqTool")))
    g.add((dev_struct, P510.DevTool_Version, Literal("3.2")))
    g.add((dev_struct, P510.DevTool_License, Literal("Academic")))
    g.add((dev_struct, P510.DevOS_Name, Literal("Windows")))
    g.add((dev_struct, P510.DevOS_Version, Literal("11")))
    g.add((dev_struct, P510.DevOS_License, Literal("OEM")))
    g.add((dev_struct, P510.RequirementAuthoringTechnique, Literal(random.choice(["Formal", "Semi-Formal", "Informal"]))))
    g.add((dev_struct, P510.Format_name, Literal(random.choice(["ReqIF", "SysML", "SysMLV2", "SpecIF"]))))
    g.add((dev_struct, P510.Format_version, Literal("1.0")))
    g.add((dev_struct, P510.Specification_level, Literal("SyRS")))
    g.add((dev_struct, P510.Language, Literal("en-US")))

    vnv = _new_instance_uri(instances_base, "Requirements_Verification_Validation")
    g.add((vnv, RDF.type, P510.Requirements_Verification_Validation_Type))
    g.add((vnv, RDFS.label, Literal("Requirements_Verification_Validation")))
    g.add((manifest, P510.has_Requirements_Verification_Validation, vnv))
    g.add((manifest, P510.Requirements_Verification_Validation, vnv))

    # XSD fields: Requirements_Verification_Validation_Type
    g.add((vnv, P510.Specification_Consistency, Literal(True)))
    g.add((vnv, P510.Specification_Completeness, Literal(True)))

    traceability = _new_instance_uri(instances_base, "Requirements_Traceability")
    g.add((traceability, RDF.type, P510.Requirements_Traceability_Type))
    g.add((traceability, RDFS.label, Literal("Requirements_Traceability")))
    g.add((manifest, P510.has_Requirements_Traceability, traceability))
    g.add((manifest, P510.Requirements_Traceability, traceability))

    # Create some documents (for `RequirementsDevStructureType/uses`)
    documentos: list[URIRef] = []
    for i in range(1, 6):
        doc = instances_base[f"_Document_{i:02d}"]
        g.add((doc, RDF.type, EX.Document))
        g.add((doc, RDFS.label, Literal(f"Document {i:02d}")))
        g.add((doc, P510.ContentType, Literal("Document")))
        g.add((doc, P510.Description, Literal(f"Supporting document {i:02d}")))
        g.add((doc, DCTERMS.title, Literal(f"Supporting Document {i:02d}")))
        g.add((doc, DCTERMS.issued, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((doc, DCTERMS["format"], Literal(random.choice(["application/pdf", "text/plain", "application/xml"]))))
        g.add((doc, EX.doc_kind, Literal(random.choice(["Spec", "Plan", "Report", "Guideline"]))))
        documentos.append(doc)

    for doc in documentos:
        _mk_link(
            g,
            P510.uses,
            source=dev_struct,
            target=doc,
            content_type="Document",
            description="Artifact used in requirements engineering",
            prob_missing_timestamp=prob_link_missing_timestamp,
            prob_wrong_contenttype=prob_link_wrong_contenttype,
            prob_missing_description=prob_link_missing_description,
            content_type_universe=content_type_universe,
        )

    # People (responsible roles) and suppliers (organizations)
    personas = [
        "Amina",
        "Lucia",
        "Mario",
        "Sara",
        "Alvaro",
        "Noelia",
        "MBSE Team",
    ]

    proveedores: list[URIRef] = []
    for i in range(1, n_proveedores + 1):
        prov = instances_base[f"_Supplier_{i:02d}"]
        g.add((prov, RDF.type, FOAF.Organization))
        g.add((prov, FOAF.name, Literal(f"Supplier {i:02d}")))
        g.add((prov, RDFS.label, Literal(f"Supplier_{i:02d}")))
        proveedores.append(prov)

    requisitos: list[URIRef] = []
    subsistemas = [
        "Avionics",
        "Propulsion",
        "Structures",
        "FlightControl",
        "Electrical",
        "Cabin",
    ]
    for i in range(1, n_requisitos + 1):
        req = instances_base[f"_Requirement_{i:03d}"]
        g.add((req, RDF.type, P510.Requirement))
        g.add((req, RDFS.label, Literal(f"Requirement {i:03d}")))
        g.add((req, P510.Id, Literal(f"REQ-{i:03d}")))
        g.add((req, P510.Description, Literal(f"The system shall satisfy function {i}")))
        g.add((req, P510.ContentType, Literal("Requirement")))

        # Responsibility/governance metadata (useful for queries)
        g.add((req, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((req, P510.Created_by, Literal(random.choice(personas))))
        g.add((req, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork", "Obsolete"]))))
        g.add((req, P510.Approval_State, Literal(random.choice(["Pending", "Approved", "Rejected"]))))

        # Additional metadata (for richer NL questions)
        g.add((req, EX.subsystem, Literal(random.choice(subsistemas))))
        g.add((req, EX.priority, Literal(random.randint(1, 5), datatype=XSD.integer)))
        g.add((req, EX.verification_method, Literal(random.choice(["Test", "Analysis", "Inspection", "Demonstration"]))))
        g.add((req, EX.criticality, Literal(random.choice(["Low", "Medium", "High"]))))
        if random.random() > 0.35:
            g.add((req, EX.rationale, Literal("Synthesized rationale to justify the requirement")))

        if random.random() > prob_req_sin_aprobador:
            g.add((req, P510.Approver, Literal(random.choice(personas))))

        if random.random() > prob_req_sin_org_autora:
            # In the XSD it is xs:string; here we store the organization name.
            g.add((req, P510.Author_Organization, Literal(f"Supplier {random.randint(1, n_proveedores):02d}")))

        requisitos.append(req)

    modelos: list[URIRef] = []
    for i in range(1, n_modelos + 1):
        model = instances_base[f"_PhysicalModel_{i:03d}"]
        g.add((model, RDF.type, P510.DesignModel))
        g.add((model, RDFS.label, Literal(f"PhysicalModel {i:03d}")))
        g.add((model, P510.Id, Literal(f"MOD-{i:03d}")))
        g.add((model, P510.Description, Literal(f"Physical model {i}")))
        g.add((model, P510.ContentType, Literal("Physical Model")))

        g.add((model, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((model, P510.Created_by, Literal(random.choice(personas))))
        g.add((model, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork"]))))
        approval_state = random.choice(["Pending", "Approved"])
        g.add((model, P510.Approval_State, Literal(approval_state)))

        g.add((model, EX.model_kind, Literal(random.choice(["CAD", "FEM", "SysML", "Simulink"]))))
        g.add((model, EX.part_number, Literal(f"PN-{random.randint(1000, 9999)}-{i:03d}")))
        g.add((model, EX.subsystem, Literal(random.choice(subsistemas))))
        if random.random() > 0.15:
            g.add((model, P510.Author_Organization, Literal(f"Supplier {random.randint(1, n_proveedores):02d}")))
        # Add Approver only sometimes even if state is Approved (to audit inconsistencies)
        if approval_state == "Approved" and random.random() > 0.12:
            g.add((model, P510.Approver, Literal(random.choice(personas))))

        # Sometimes omit supplier to enable audit queries
        if random.random() > prob_modelo_sin_proveedor:
            g.add((model, EX.providedBy, random.choice(proveedores)))
        modelos.append(model)

    tests: list[URIRef] = []
    for i in range(1, n_tests + 1):
        test = instances_base[f"_TestCase_{i:03d}"]
        g.add((test, RDF.type, P510.VerificationTest))
        g.add((test, RDFS.label, Literal(f"TestCase {i:03d}")))
        g.add((test, P510.Id, Literal(f"TST-{i:03d}")))
        g.add((test, P510.Description, Literal(f"Verification test {i}")))
        g.add((test, P510.ContentType, Literal("Test Case")))
        g.add((test, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((test, P510.Created_by, Literal(random.choice(personas))))
        g.add((test, EX.status, Literal(random.choice(["Passed", "Failed", "NotRun"]))))
        g.add((test, P510.Maturity_State, Literal(random.choice(["Draft", "InWork", "Released"]))))
        g.add((test, EX.test_type, Literal(random.choice(["Unit", "Integration", "System", "Acceptance"]))))
        g.add((test, EX.environment, Literal(random.choice(["SIL", "HIL", "Bench", "Flight"]))))
        tests.append(test)

    for req in requisitos:
        if random.random() > prob_req_sin_modelo:
            modelo_target = random.choice(modelos)
            _mk_link(
                g,
                P510.Satisfied_by,
                source=req,
                target=modelo_target,
                content_type="Physical Model",
                description="This requirement is satisfied by this physical model",
                traceability_root=traceability,
                prob_missing_timestamp=prob_link_missing_timestamp,
                prob_wrong_contenttype=prob_link_wrong_contenttype,
                prob_missing_description=prob_link_missing_description,
                content_type_universe=content_type_universe,
            )

            if random.random() < prob_link_duplicate:
                _mk_link(
                    g,
                    P510.Satisfied_by,
                    source=req,
                    target=modelo_target,
                    content_type="Physical Model",
                    description="(duplicate) This requirement is satisfied by this physical model",
                    traceability_root=traceability,
                    prob_missing_timestamp=prob_link_missing_timestamp,
                    prob_wrong_contenttype=prob_link_wrong_contenttype,
                    prob_missing_description=prob_link_missing_description,
                    content_type_universe=content_type_universe,
                )

    for modelo in modelos:
        if random.random() > prob_modelo_sin_test:
            test_target = random.choice(tests)
            _mk_link(
                g,
                P510.Verified_by,
                source=modelo,
                target=test_target,
                content_type="Test Case",
                description="This model is verified by this test case",
                traceability_root=traceability,
                prob_missing_timestamp=prob_link_missing_timestamp,
                prob_wrong_contenttype=prob_link_wrong_contenttype,
                prob_missing_description=prob_link_missing_description,
                content_type_universe=content_type_universe,
            )

            if random.random() < prob_link_duplicate:
                _mk_link(
                    g,
                    P510.Verified_by,
                    source=modelo,
                    target=test_target,
                    content_type="Test Case",
                    description="(duplicate) This model is verified by this test case",
                    traceability_root=traceability,
                    prob_missing_timestamp=prob_link_missing_timestamp,
                    prob_wrong_contenttype=prob_link_wrong_contenttype,
                    prob_missing_description=prob_link_missing_description,
                    content_type_universe=content_type_universe,
                )

    # --- Verification/validation scenarios (XSD: Verification_Validation_Scenario_Type) ---
    evidencias: list[URIRef] = []
    for i in range(1, 6):
        ev = instances_base[f"_Evidence_{i:02d}"]
        g.add((ev, RDF.type, EX.Evidence))
        # In real P510 this is often a specific type; include it as a semantic cue.
        g.add((ev, RDF.type, P510.Verification_Validation_Evidence_Type))
        g.add((ev, RDFS.label, Literal(f"Evidence {i:02d}")))
        g.add((ev, P510.Id, Literal(f"EVD-{i:03d}")))
        g.add((ev, P510.ContentType, Literal("Evidence")))
        g.add((ev, P510.Description, Literal(f"Validation evidence {i:02d}")))
        g.add((ev, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((ev, PROV.wasAttributedTo, Literal(random.choice(personas))))
        g.add((ev, EX.evidence_kind, Literal(random.choice(["Report", "Log", "Checklist", "Screenshot"]))))
        evidencias.append(ev)

    cred_levels = ["A", "B", "C"]
    n_scenarios = max(8, n_tests // 2)
    for i in range(1, n_scenarios + 1):
        sc = _new_instance_uri(instances_base, "Scenario")
        g.add((sc, RDF.type, P510.Verification_Validation_Scenario_Type))
        g.add((sc, RDFS.label, Literal(f"Scenario {i:02d}")))
        g.add((sc, P510.Id, Literal(f"SCN-{i:03d}")))
        g.add((sc, P510.Verification_Credibility_Level, Literal(random.choice(cred_levels))))
        g.add((sc, P510.Validation_Credibility_Level, Literal(random.choice(cred_levels))))

        # Link the scenario from the V&V block
        g.add((vnv, P510.Scenario, sc))

        # Sometimes leave scenarios "incomplete" to enable SPARQL audit queries.
        # With a fixed seed, this deterministic rule ensures at least 1 case for most sizes.
        if (i % 7 == 0) or (random.random() < 0.12):
            continue

        if random.random() < 0.7:
            _mk_link(
                g,
                P510.Verified_by,
                source=sc,
                target=random.choice(tests),
                content_type="Test Case",
                description="Verification evidence (test case)",
                prob_missing_timestamp=prob_link_missing_timestamp,
                prob_wrong_contenttype=prob_link_wrong_contenttype,
                prob_missing_description=prob_link_missing_description,
                content_type_universe=content_type_universe,
            )
        else:
            _mk_link(
                g,
                P510.Validated_by,
                source=sc,
                target=random.choice(evidencias),
                content_type="Evidence",
                description="Validation evidence",
                prob_missing_timestamp=prob_link_missing_timestamp,
                prob_wrong_contenttype=prob_link_wrong_contenttype,
                prob_missing_description=prob_link_missing_description,
                content_type_universe=content_type_universe,
            )

        report_uri = URIRef(f"http://example.org/reports/{uuid.uuid4()}.pdf")
        g.add((sc, P510.Model_Summary_Report, report_uri))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    g.serialize(destination=out_path, format="turtle", base=BASE)
    return out_path


if __name__ == "__main__":
    out = generar_grafo_p510()
    print(f"✅ Generated P510-like graph: {out}")
