import os
import auditor

def detectar_intencion(pregunta):
    p = pregunta.lower()

    # Mapeo exacto a tus 11 archivos
    if "huerfano" in p or ("requisito" in p and "sin modelo" in p):
        return "q1_requisitos_huerfanos.sparql", "Buscando requisitos sin modelo"
    
    if "modelo" in p and "sin test" in p:
        return "q2_modelos_sin_test.sparql", "Buscando modelos sin test de verificación"
    
    if "conteo global" in p or "resumen" in p:
        return "q3_conteo_global.sparql", "Conteo global de requisitos y modelos"
    
    if "completa" in p or "camino" in p:
        return "q4_trazabilidad_completa.sparql", "Mostrando cadena completa Req -> Modelo -> Test"
    
    if "implementado" in p and "no verificado" in p:
        return "q5_implementados_no_verificados.sparql", "Requisitos con modelo pero sin test"
    
    if "inutil" in p or "test" in p and "suelto" in p:
        return "q6_tests_inutiles.sparql", "Buscando tests que no verifican nada"
    
    if "tipo" in p or "cada" in p:
        return "q7_conteo_por_tipo.sparql", "Desglose de elementos por tipo"
    
    if "porcentaje" in p or "cobertura" in p:
        return "q8_porcentaje_trazabilidad.sparql", "Calculando porcentaje de éxito"
    
    if "redundante" in p or "varios modelos" in p or "sobre" in p:
        return "q9_sobre_especificacion.sparql", "Buscando requisitos con múltiples modelos"
    
    if "aislado" in p or "sin conexion" in p:
        return "q10_elementos_aislados.sparql", "Buscando elementos totalmente aislados"
    
    if "busca" in p or "sistema" in p or "descrip" in p:
        return "q11_busqueda_texto.sparql", "Buscando palabra 'sistema' en descripciones"

    return None, None

def iniciar_chat():
    print("=====================================================")
    print("   🤖 AUDITOR MBSE - 11 CONSULTAS DE CALIDAD")
    print("=====================================================")
    
    grafo = auditor.cargar_grafo()
    if grafo is None:
        print("❌ Error: Ejecuta primero generar_datos.py")
        return

    print(f"✅ Grafo cargado con {len(grafo)} tripletas.")
    print("💬 Hazme una pregunta sobre la trazabilidad (o 'salir')")

    while True:
        entrada = input("\nPregunta 👉 ")
        if entrada.lower() == "salir": break

        archivo, desc = detectar_intencion(entrada)

        if archivo:
            auditor.ejecutar_consulta(grafo, archivo, desc)
        else:
            print("🤔 No te he entendido bien. Prueba con:")
            print("   - ¿Cual es el porcentaje de trazabilidad?")
            print("   - ¿Dime los requisitos huerfanos?")
            print("   - ¿Cuantos elementos hay de cada tipo?")

if __name__ == "__main__":
    iniciar_chat()