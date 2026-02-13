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
    """Crea un nodo `p510:Traceability_Link_Type` y lo cuelga desde `source` con `link_predicate`."""
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
        # omitimos uno de los dos timestamps
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
    """Genera un grafo RDF "P510-like".

    Puntos clave del perfil (para el TFG):
    - Entidades: Requirement, DesignModel (Physical Model), VerificationTest (Test Case)
    - Trazas: en vez de aristas directas, se crean nodos `p510:Traceability_Link_Type`.
      Ejemplo: `?req p510:Satisfied_by ?link . ?link p510:Link ?modelo`.
    - Responsables: los modelos tienen `ex:providedBy ?supplier`.
    """

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

    # Para parecerse al TTL del profe: URIs en /p510/instances/<seed>/... y nodos contenedor.
    seed = str(random.randint(1_000_000_000, 9_999_999_999))
    instances_base = Namespace(f"{INSTANCES_ROOT}{seed}/")

    manifest = _new_instance_uri(instances_base, "P510_Manifest")
    g.add((manifest, RDF.type, P510.P510_ManifestType))
    g.add((manifest, RDFS.label, Literal("P510_Manifest")))

    general_info = _new_instance_uri(instances_base, "GeneralPLMInfo")
    g.add((general_info, RDF.type, P510.GeneralPLMInfoType))
    g.add((general_info, RDFS.label, Literal("GeneralPLMInfo")))
    g.add((manifest, P510.has_GeneralPLMInfo, general_info))
    # también añadimos una relación "tipo elemento" para parecerse más a la serialización del ejemplo
    g.add((manifest, P510.GeneralPLMInfo, general_info))

    # Propiedades típicas del XSD (más completas)
    g.add((general_info, P510.Unique_object_id, Literal(str(uuid.uuid4()))))
    g.add((general_info, P510.Unique_baseline_id, Literal(str(uuid.uuid4()))))
    g.add((general_info, P510.Version_identifier, Literal("1.0")))
    created_ts = _now_iso()
    g.add((general_info, P510.Created_on, Literal(created_ts, datatype=XSD.dateTime)))
    g.add((general_info, P510.Last_Modified_Date, Literal(created_ts, datatype=XSD.dateTime)))
    g.add((general_info, P510.Model_Purpose, Literal("TFG: consultas SPARQL desde Lenguaje Natural")))
    g.add((general_info, P510.Model_Objective, Literal("Auditar trazabilidad y responsables")))
    g.add((general_info, P510.Organization, Literal("Universidad")))
    g.add((general_info, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork"])) ))
    g.add((general_info, P510.Approval_State, Literal(random.choice(["Pending", "Approved"])) ))
    g.add((general_info, P510.Created_by, Literal(random.choice(["Amina", "Tutor", "Equipo MBSE"]))))
    g.add((general_info, P510.Author_Organization, Literal("Universidad")))

    dev_struct = _new_instance_uri(instances_base, "RequirementsDevStructure")
    g.add((dev_struct, RDF.type, P510.RequirementsDevStructureType))
    g.add((dev_struct, RDFS.label, Literal("RequirementsDevStructure")))
    g.add((manifest, P510.has_RequirementsDevStructure, dev_struct))
    g.add((manifest, P510.RequirementsDevStructure, dev_struct))

    # Campos del XSD: RequirementsDevStructureType
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
    g.add((dev_struct, P510.Language, Literal("es-ES")))

    vnv = _new_instance_uri(instances_base, "Requirements_Verification_Validation")
    g.add((vnv, RDF.type, P510.Requirements_Verification_Validation_Type))
    g.add((vnv, RDFS.label, Literal("Requirements_Verification_Validation")))
    g.add((manifest, P510.has_Requirements_Verification_Validation, vnv))
    g.add((manifest, P510.Requirements_Verification_Validation, vnv))

    # Campos del XSD: Requirements_Verification_Validation_Type
    g.add((vnv, P510.Specification_Consistency, Literal(True)))
    g.add((vnv, P510.Specification_Completeness, Literal(True)))

    traceability = _new_instance_uri(instances_base, "Requirements_Traceability")
    g.add((traceability, RDF.type, P510.Requirements_Traceability_Type))
    g.add((traceability, RDFS.label, Literal("Requirements_Traceability")))
    g.add((manifest, P510.has_Requirements_Traceability, traceability))
    g.add((manifest, P510.Requirements_Traceability, traceability))

    # Crear algunos documentos (para `RequirementsDevStructureType/uses`)
    documentos: list[URIRef] = []
    for i in range(1, 6):
        doc = instances_base[f"_Document_{i:02d}"]
        g.add((doc, RDF.type, EX.Document))
        g.add((doc, RDFS.label, Literal(f"Document {i:02d}")))
        g.add((doc, P510.ContentType, Literal("Document")))
        g.add((doc, P510.Description, Literal(f"Documento de apoyo {i:02d}")))
        documentos.append(doc)

    for doc in documentos:
        _mk_link(
            g,
            P510.uses,
            source=dev_struct,
            target=doc,
            content_type="Document",
            description="Artefacto usado en la ingeniería de requisitos",
            prob_missing_timestamp=prob_link_missing_timestamp,
            prob_wrong_contenttype=prob_link_wrong_contenttype,
            prob_missing_description=prob_link_missing_description,
            content_type_universe=content_type_universe,
        )

    # Personas (responsables) y proveedores (organizaciones)
    personas = [
        "Amina",
        "Lucía",
        "Mario",
        "Sara",
        "Álvaro",
        "Noelia",
        "Equipo MBSE",
    ]

    proveedores: list[URIRef] = []
    for i in range(1, n_proveedores + 1):
        prov = instances_base[f"_Supplier_{i:02d}"]
        g.add((prov, RDF.type, FOAF.Organization))
        g.add((prov, FOAF.name, Literal(f"Proveedor {i:02d}")))
        g.add((prov, RDFS.label, Literal(f"Supplier_{i:02d}")))
        proveedores.append(prov)

    requisitos: list[URIRef] = []
    for i in range(1, n_requisitos + 1):
        req = instances_base[f"_Requirement_{i:03d}"]
        g.add((req, RDF.type, P510.Requirement))
        g.add((req, RDFS.label, Literal(f"Requirement {i:03d}")))
        g.add((req, P510.Id, Literal(f"REQ-{i:03d}")))
        g.add((req, P510.Description, Literal(f"El sistema debe cumplir la función {i}")))
        g.add((req, P510.ContentType, Literal("Requirement")))

        # Metadatos/responsables (útiles para consultas)
        g.add((req, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((req, P510.Created_by, Literal(random.choice(personas))))
        g.add((req, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork", "Obsolete"]))))
        g.add((req, P510.Approval_State, Literal(random.choice(["Pending", "Approved", "Rejected"]))))

        if random.random() > prob_req_sin_aprobador:
            g.add((req, P510.Approver, Literal(random.choice(personas))))

        if random.random() > prob_req_sin_org_autora:
            # en el XSD es xs:string, aquí guardamos el nombre de la organización
            g.add((req, P510.Author_Organization, Literal(f"Proveedor {random.randint(1, n_proveedores):02d}")))

        requisitos.append(req)

    modelos: list[URIRef] = []
    for i in range(1, n_modelos + 1):
        model = instances_base[f"_PhysicalModel_{i:03d}"]
        g.add((model, RDF.type, P510.DesignModel))
        g.add((model, RDFS.label, Literal(f"PhysicalModel {i:03d}")))
        g.add((model, P510.Id, Literal(f"MOD-{i:03d}")))
        g.add((model, P510.Description, Literal(f"Modelo físico {i}")))
        g.add((model, P510.ContentType, Literal("Physical Model")))

        g.add((model, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((model, P510.Created_by, Literal(random.choice(personas))))
        g.add((model, P510.Maturity_State, Literal(random.choice(["Draft", "Released", "InWork"]))))
        approval_state = random.choice(["Pending", "Approved"])
        g.add((model, P510.Approval_State, Literal(approval_state)))
        if random.random() > 0.15:
            g.add((model, P510.Author_Organization, Literal(f"Proveedor {random.randint(1, n_proveedores):02d}")))
        # Aprover solo algunas veces incluso si está Approved (para auditar incoherencias)
        if approval_state == "Approved" and random.random() > 0.12:
            g.add((model, P510.Approver, Literal(random.choice(personas))))

        # A veces faltará proveedor para poder auditarlo
        if random.random() > prob_modelo_sin_proveedor:
            g.add((model, EX.providedBy, random.choice(proveedores)))
        modelos.append(model)

    tests: list[URIRef] = []
    for i in range(1, n_tests + 1):
        test = instances_base[f"_TestCase_{i:03d}"]
        g.add((test, RDF.type, P510.VerificationTest))
        g.add((test, RDFS.label, Literal(f"TestCase {i:03d}")))
        g.add((test, P510.Id, Literal(f"TST-{i:03d}")))
        g.add((test, P510.Description, Literal(f"Test de verificación {i}")))
        g.add((test, P510.ContentType, Literal("Test Case")))
        g.add((test, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
        g.add((test, P510.Created_by, Literal(random.choice(personas))))
        g.add((test, EX.status, Literal(random.choice(["Passed", "Failed", "NotRun"]))))
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
                description="El requisito queda satisfecho por este modelo físico",
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
                    description="(duplicado) El requisito queda satisfecho por este modelo físico",
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
                description="El modelo queda verificado por este caso de prueba",
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
                    description="(duplicado) El modelo queda verificado por este caso de prueba",
                    traceability_root=traceability,
                    prob_missing_timestamp=prob_link_missing_timestamp,
                    prob_wrong_contenttype=prob_link_wrong_contenttype,
                    prob_missing_description=prob_link_missing_description,
                    content_type_universe=content_type_universe,
                )

    # --- Escenarios de verificación/validación (XSD: Verification_Validation_Scenario_Type) ---
    evidencias: list[URIRef] = []
    for i in range(1, 6):
        ev = instances_base[f"_Evidence_{i:02d}"]
        g.add((ev, RDF.type, EX.Evidence))
        # En P510 real esto suele ser un tipo específico; lo incluimos como señal semántica.
        g.add((ev, RDF.type, P510.Verification_Validation_Evidence_Type))
        g.add((ev, RDFS.label, Literal(f"Evidence {i:02d}")))
        g.add((ev, P510.Id, Literal(f"EVD-{i:03d}")))
        g.add((ev, P510.ContentType, Literal("Evidence")))
        g.add((ev, P510.Description, Literal(f"Evidencia de validación {i:02d}")))
        g.add((ev, P510.Created_on, Literal(_now_iso(), datatype=XSD.dateTime)))
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

        # Enlazar el escenario desde el bloque V&V
        g.add((vnv, P510.Scenario, sc))

        # A veces dejamos escenarios "incompletos" para poder auditarlos con SPARQL.
        # Con seed fija, esta regla determinista garantiza al menos 1 caso en la mayoría de tamaños.
        if (i % 7 == 0) or (random.random() < 0.12):
            continue

        if random.random() < 0.7:
            _mk_link(
                g,
                P510.Verified_by,
                source=sc,
                target=random.choice(tests),
                content_type="Test Case",
                description="Evidencia de verificación (test case)",
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
                description="Evidencia de validación",
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
    print(f"✅ Grafo P510-like generado: {out}")
