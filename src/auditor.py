import os
from rdflib import Graph

ARCHIVO_DATOS = os.path.join("data", "grafo_sintetico.ttl")
CARPETA_QUERIES = "queries"

def cargar_grafo():
    if not os.path.exists(ARCHIVO_DATOS):
        return None
    g = Graph()
    g.parse(ARCHIVO_DATOS, format="turtle")
    return g

def ejecutar_consulta(grafo, nombre_archivo, descripcion):
    ruta_query = os.path.join(CARPETA_QUERIES, nombre_archivo)
    
    if not os.path.exists(ruta_query):
        print(f"❌ Error: No encuentro el archivo {nombre_archivo}")
        return

    with open(ruta_query, "r", encoding="utf-8") as f:
        query_str = f.read()
    
    print(f"\n🔍 {descripcion.upper()}")
    resultados = grafo.query(query_str)
    lista_res = list(resultados)
    
    if not lista_res:
        print("   ✅ No se encontraron resultados/incidencias.")
        return

    print(f"   📊 RESULTADOS:")
    for fila in lista_res:
        # Procesamos cada celda de la fila
        valores_limpios = []
        for valor in fila:
            # Si es una URL de nuestro grafo, quitamos la parte larga
            if "#" in str(valor):
                valores_limpios.append(str(valor).split("#")[-1])
            else:
                valores_limpios.append(str(valor))
        
        # Imprimimos la fila formateada
        print("      👉 " + " | ".join(valores_limpios))