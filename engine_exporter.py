import os
import json
import ssl
import websocket
import logging

# Función send integrada
def send(ws, method, handle, params=None):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "handle": handle,
        "method": method,
        "params": params or {}
    }
    ws.send(json.dumps(request))
    response = json.loads(ws.recv())
    return response

def export_app_objects(app_id, output_folder, conn):
    logging.info("Estableciendo conexión WebSocket con Engine API")

    engine_host = conn.get("engine_host", conn["host"].replace("https://", "").split(":" )[0])
    ws_url = f"wss://{engine_host}:4747/app/"

    sslopt = {
        "certfile": conn["cert_file"],
        "keyfile": conn["key_file"],
        "cert_reqs": ssl.CERT_REQUIRED
    }

    if conn.get("root_cert"):
        sslopt["ca_certs"] = conn["root_cert"]
    else:
        logging.warning("No se especificó root_cert. Se omitirá la verificación del certificado.")
        sslopt["cert_reqs"] = ssl.CERT_NONE

    ws = websocket.create_connection(
        ws_url,
        sslopt=sslopt,
        header=[
            f"X-Qlik-User: {conn['header_user']}"
        ]
    )

    initial_message = json.loads(ws.recv())
    logging.debug(f"Mensaje inicial descartado: {initial_message}")

    logging.info("Conexión WebSocket establecida. Abriendo documento...")
    open_doc = send(ws, "OpenDoc", handle=-1, params=[app_id])

    if "result" not in open_doc:
        logging.error(f"Error al abrir el documento: {open_doc}")
        ws.close()
        raise RuntimeError("No se pudo abrir la app. Verifica que el app_id es correcto y que tienes permisos.")

    doc_handle = open_doc["result"]["qReturn"]["qHandle"]

    logging.info(f"Documento abierto con handle {doc_handle}")

    # Exportar script
    logging.info("Exportando script...")
    try:
        script_reply = send(ws, "GetScript", handle=doc_handle)
        with open(os.path.join(output_folder, "script.qvs"), "w", encoding="utf-8") as f:
            f.write(script_reply["result"]["qScript"])
    except Exception as e:
        logging.warning(f"No se pudo exportar el script: {e}")

    # Exportar variables
    logging.info("Exportando variables...")
    try:
        vars_reply = send(ws, "GetAllVariables", handle=doc_handle, params={"qIncludeReserved": True, "qIncludeConfig": False})
        if "result" in vars_reply and "qVariableList" in vars_reply["result"]:
            variables = vars_reply["result"]["qVariableList"]["qItems"]
            with open(os.path.join(output_folder, "variables.json"), "w", encoding="utf-8") as f:
                json.dump(variables, f, indent=2)
        else:
            logging.warning("No se encontraron variables en la aplicación.")
    except Exception as e:
        logging.warning(f"No se pudieron obtener las variables: {e}")

    # Exportar objetos extendidos
    logging.info("Exportando objetos extendidos...")
    try:
        infos_reply = send(ws, "GetAllInfos", handle=doc_handle)
        infos = infos_reply["result"]["qInfos"]
    except Exception as e:
        logging.warning(f"No se pudieron obtener los objetos extendidos: {e}")
        infos = []

    measures, dimensions, sheets, others = [], [], [], []
    for info in infos:
        qid = info["qId"]
        qtype = info["qType"]

        try:
            if qtype == "measure":
                obj = send(ws, "GetMeasure", handle=doc_handle, params=[qid])
                handle_id = obj["result"]["qReturn"]["qHandle"]
                prop = send(ws, "GetProperties", handle=handle_id)
                measures.append(prop["result"])

            elif qtype == "dimension":
                obj = send(ws, "GetDimension", handle=doc_handle, params=[qid])
                prop = send(ws, "GetProperties", handle=obj["result"]["qReturn"]["qHandle"])
                dimensions.append(prop["result"])

            elif qtype == "sheet":
                obj = send(ws, "GetObject", handle=doc_handle, params=[qid])
                prop = send(ws, "GetProperties", handle=obj["result"]["qReturn"]["qHandle"])
                sheets.append(prop["result"])

            else:
                others.append(info)
        except Exception as e:
            logging.warning(f"No se pudo exportar el objeto {qid} ({qtype}): {e}")
            others.append(info)

    try:
        with open(os.path.join(output_folder, "measures.json"), "w", encoding="utf-8") as f:
            json.dump(measures, f, indent=2)
    except Exception as e:
        logging.warning(f"Error al guardar medidas: {e}")

    try:
        with open(os.path.join(output_folder, "dimensions.json"), "w", encoding="utf-8") as f:
            json.dump(dimensions, f, indent=2)
    except Exception as e:
        logging.warning(f"Error al guardar dimensiones: {e}")

    try:
        with open(os.path.join(output_folder, "sheets.json"), "w", encoding="utf-8") as f:
            json.dump(sheets, f, indent=2)
    except Exception as e:
        logging.warning(f"Error al guardar hojas: {e}")

    try:
        with open(os.path.join(output_folder, "other_objects.json"), "w", encoding="utf-8") as f:
            json.dump(others, f, indent=2)
    except Exception as e:
        logging.warning(f"Error al guardar otros objetos: {e}")

    ws.close()
    logging.info("Exportación completa y conexión cerrada.")

def import_app_objects(app_id, input_folder, conn):
    import os, json, logging
    import ssl
    import websocket
    from engine_exporter import send

    logging.info("Estableciendo conexión WebSocket con Engine API para importación")

    engine_host = conn.get("engine_host", conn["host"].replace("https://", "").split(":" )[0])
    ws_url = f"wss://{engine_host}:4747/app/"

    sslopt = {
        "certfile": conn["cert_file"],
        "keyfile": conn["key_file"],
        "cert_reqs": ssl.CERT_REQUIRED
    }

    if conn.get("root_cert"):
        sslopt["ca_certs"] = conn["root_cert"]
    else:
        logging.warning("No se especificó root_cert. Se omitirá la verificación del certificado.")
        sslopt["cert_reqs"] = ssl.CERT_NONE

    ws = websocket.create_connection(
        ws_url,
        sslopt=sslopt,
        header=[f"X-Qlik-User: {conn['header_user']}"]
    )

    json.loads(ws.recv())
    logging.info("Conexión establecida. Abriendo documento destino...")
    open_doc = send(ws, "OpenDoc", handle=-1, params=[app_id])
    if "result" not in open_doc:
        logging.error(f"No se pudo abrir la app destino: {open_doc}")
        ws.close()
        raise RuntimeError("No se pudo abrir la app destino para importar.")

    doc_handle = open_doc["result"]["qReturn"]["qHandle"]
    logging.info(f"Documento destino abierto con handle {doc_handle}")

    # Script
    script_path = os.path.join(input_folder, "script.qvs")
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            script = f.read()
        send(ws, "SetScript", handle=doc_handle, params={"qScript": script})
        logging.info("Script importado correctamente.")

    # Variables
    variables_path = os.path.join(input_folder, "variables.json")
    if os.path.exists(variables_path):
        with open(variables_path, "r", encoding="utf-8") as f:
            variables = json.load(f)
        for var in variables:
            name = var.get("qName")
            value = var.get("qDefinition", "")
            send(ws, "CreateVariableEx", handle=doc_handle, params={"qName": name, "qDefinition": value})
        logging.info(f"{len(variables)} variables importadas correctamente.")

    # Medidas
    path = os.path.join(input_folder, "measures.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            measures = json.load(f)
        for m in measures:
            props = m.get("qProp", m)
            send(ws, "CreateMeasure", handle=doc_handle, params={"qProp": props})
        logging.info(f"{len(measures)} medidas importadas correctamente.")

    # Dimensiones
    path = os.path.join(input_folder, "dimensions.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            dims = json.load(f)
        for d in dims:
            props = d.get("qProp", d)
            send(ws, "CreateDimension", handle=doc_handle, params={"qProp": props})
        logging.info(f"{len(dims)} dimensiones importadas correctamente.")

    # Hojas
    path = os.path.join(input_folder, "sheets.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            sheets = json.load(f)
        for s in sheets:
            props = s.get("qProp", s)
            send(ws, "CreateObject", handle=doc_handle, params={"qProp": props})
        logging.info(f"{len(sheets)} hojas importadas correctamente.")

    # Otros
    path = os.path.join(input_folder, "other_objects.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            other = json.load(f)
        logging.info(f"{len(other)} objetos ignorados importados como referencia.")

    ws.close()
    logging.info("Importación completada y conexión cerrada.")
