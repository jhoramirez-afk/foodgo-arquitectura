"""Evidencia real: Gateway protegido, ocho dominios, replicas y SQS/Lambda."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import datetime as dt
import json
import math
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from cloud import CLUSTER, MESSAGING, outputs, run_on_manager, session

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = {"usuarios": "usuarios", "restaurantes": "restaurantes", "pedidos": "pedidos", "pagos": "pagos",
             "delivery": "envios", "notificaciones": "notificaciones", "cupones": "cupones", "resenas": "resenas"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class Api:
    def __init__(self, s, endpoint):
        parsed = urllib.parse.urlsplit(endpoint)
        expected = ".execute-api." + s.region_name + ".amazonaws.com"
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(expected) or "@" in parsed.netloc or parsed.port or parsed.query or parsed.fragment:
            raise ValueError("El destino firmado debe ser el API Gateway HTTPS de la region")
        self.s, self.endpoint = s, endpoint.rstrip("/")
        self.credentials = s.get_credentials()

    def call(self, path, method="GET", body=None, signed=True):
        url = self.endpoint + path
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        if signed:
            request = AWSRequest(method=method, url=url, data=data, headers=headers)
            SigV4Auth(self.credentials.get_frozen_credentials(), "execute-api", self.s.region_name).add_auth(request)
            headers = dict(request.headers.items())
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
                raw = response.read(1024 * 1024)
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            # El cuerpo de un rechazo IAM puede incluir identificadores de la sesion. No publicarlo.
            return error.code, None
        except (TimeoutError, urllib.error.URLError):
            return 0, None


def wait_ready(api, domain, resource):
    path = f"/{domain}/api/{resource}"
    for attempt in range(180):
        code, data = api.call(path)
        if code == 200 and isinstance(data, list):
            print(domain + ": HTTP 200", flush=True)
            return {"dominio": domain, "http": code}
        if attempt % 15 == 0:
            print(f"Esperando {domain}: HTTP {code}", flush=True)
        time.sleep(2)
    raise RuntimeError("No responde el dominio " + domain)


def processed_messages(logs, group, event_id, start_ms):
    # CloudWatch puede devolver una pagina vacia con nextToken. Recorrer todas
    # las paginas y acotar a esta prueba evita confundirla con ausencia de logs.
    found = set()
    pattern = re.compile(r"Procesado mensaje=(\S+) evento=" + re.escape(event_id) + r"(?=\s|$)")
    pages = logs.get_paginator("filter_log_events").paginate(
        logGroupName=group, startTime=start_ms, filterPattern='"' + event_id + '"',
        PaginationConfig={"PageSize": 100})
    for page in pages:
        for entry in page.get("events", []):
            match = pattern.search(entry.get("message", ""))
            if match:
                found.add(match[1])
    return found


def async_flow(s, api, messaging):
    start_ms = int(time.time() * 1000) - 60000
    message = "Camila, tu pedido de La Cocina de Barrio esta en camino."
    code, notices = api.call("/notificaciones/api/notificaciones")
    if code != 200:
        raise RuntimeError("No se pudo consultar Notificaciones")
    notice = next((n for n in notices if n.get("destinatario") == "camila.soto@example.com" and n.get("mensaje") == message), None)
    if not notice:
        code, notice = api.call("/notificaciones/api/notificaciones", "POST", {
            "destinatario": "camila.soto@example.com", "canal": "EMAIL", "mensaje": message})
        if code != 201:
            raise RuntimeError("No se pudo registrar el aviso de demostracion")
    identifier = notice["id"]
    code, published = api.call(f"/notificaciones/api/notificaciones/{identifier}/encolar", "POST")
    if code != 202 or not isinstance(published, dict) or published.get("estado") != "ENCOLADO":
        raise RuntimeError("El productor no confirmo el envio a SQS")
    event_id = published["eventoId"]
    path = f"/notificaciones/api/notificaciones/{identifier}/intentos"
    for attempt in range(90):
        code, attempts = api.call(path)
        matching = [v for v in attempts if v.get("eventoId") == event_id] if code == 200 else []
        if len(matching) == 1 and matching[0].get("resultado") == "ENVIADO":
            break
        if attempt % 10 == 0:
            print("Esperando el procesamiento real de Lambda", flush=True)
        time.sleep(2)
    else:
        raise RuntimeError("No se comprobo la persistencia del evento procesado por Lambda")
    if not matching[0].get("detalle", "").startswith("Simulación académica:"):
        raise RuntimeError("El aviso debe identificar expresamente que es una simulacion")
    event = {"version": 1, "tipo": "NOTIFICACION_SOLICITADA", "eventoId": event_id, "notificacionId": identifier}
    replay = s.client("sqs").send_message_batch(QueueUrl=messaging["QueueUrl"], Entries=[
        {"Id": "reentrega-1", "MessageBody": json.dumps(event)}, {"Id": "reentrega-2", "MessageBody": json.dumps(event)}])
    if replay.get("Failed") or len(replay.get("Successful", [])) != 2:
        raise RuntimeError("No se pudieron generar las dos reentregas controladas")
    pending = {v["MessageId"] for v in replay["Successful"]}
    logs = s.client("logs")
    for attempt in range(90):
        pending.difference_update(processed_messages(logs, "/aws/lambda/" + messaging["FunctionName"], event_id, start_ms))
        if not pending:
            break
        if attempt % 15 == 0:
            print(f"CloudWatch: esperando {len(pending)} reentregas del evento actual", flush=True)
        time.sleep(2)
    if pending:
        raise RuntimeError("No se verificaron las dos reentregas en los logs reales de Lambda")
    code, attempts = api.call(path)
    matching = [v for v in attempts if v.get("eventoId") == event_id] if code == 200 else []
    if len(matching) != 1:
        raise RuntimeError("Una reentrega duplico el intento")
    print("Flujo asincrono: SQS y Lambda reales, tres mensajes y un intento persistido.", flush=True)
    return {"notificacionId": identifier, "eventoId": event_id, "mensajeOriginal": published["mensajeId"],
            "reentregasProcesadas": 2, "intentosPersistidos": 1, "funcion": messaging["FunctionName"]}


def scale(s, api, manager, replicas):
    script = "#!/bin/bash\nset -eu\nexec 9>/var/lock/foodgo-ep03-deploy.lock\nflock -w 600 9\n"
    script += f"docker service scale --detach=false foodgo_notificaciones={replicas}\n"
    script += "docker service ps foodgo_notificaciones\n"
    observed = []
    elapsed = []
    concurrency = 4 if replicas == 2 else 1

    def request():
        start = time.monotonic()
        status, _ = api.call("/notificaciones/api/notificaciones")
        return status, time.monotonic() - start

    with ThreadPoolExecutor(max_workers=1) as executor, ThreadPoolExecutor(max_workers=concurrency) as clients:
        update = executor.submit(run_on_manager, s, manager, script)
        while not update.done():
            for status, duration in clients.map(lambda _: request(), range(concurrency)):
                observed.append(status)
                elapsed.append(duration)
            time.sleep(1)
        update.result()
    code, _ = api.call("/notificaciones/api/notificaciones")
    observed.append(code)
    if not observed or any(status != 200 for status in observed):
        raise RuntimeError("Se observaron respuestas no exitosas durante el escalado: " + str(observed))
    return {"replicasSolicitadas": replicas, "clientesConcurrentes": concurrency,
            "peticionesDuranteEscalado": len(observed), "respuestasHTTP200": len(observed),
            "latenciaP95Ms": round(1000 * sorted(elapsed)[max(0, math.ceil(len(elapsed) * 0.95) - 1)], 2) if elapsed else None}


def private_backend(s, cluster):
    group = s.client("ec2").describe_security_groups(GroupIds=[cluster["SwarmSecurityGroupId"]])["SecurityGroups"][0]
    if any(rule.get("IpRanges") or rule.get("Ipv6Ranges") or rule.get("PrefixListIds") for rule in group["IpPermissions"]):
        raise RuntimeError("Los nodos Swarm deben aceptar solo los grupos de seguridad internos")
    alb = s.client("elbv2").describe_load_balancers(LoadBalancerArns=[cluster["InternalAlbArn"]])["LoadBalancers"][0]
    if alb["Scheme"] != "internal":
        raise RuntimeError("El balanceador del backend debe ser interno")
    return {"balanceadorInterno": True, "nodosSinReglasDeIngresoPublico": True}


def main():
    parser = argparse.ArgumentParser(description="Prueba cloud FoodGo EP03")
    parser.add_argument("--async-flow", action="store_true")
    parser.add_argument("--scale", action="store_true")
    args = parser.parse_args()
    path = ROOT / "evidencias"
    path.mkdir(exist_ok=True)
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (path / "aws-ep03.json").write_text(json.dumps({"estado": "EN_CURSO", "fechaUTC": checked_at,
        "commitInfraestructura": commit}), encoding="utf-8")
    s, _ = session()
    cfn = s.client("cloudformation")
    cluster, messaging = outputs(cfn, CLUSTER), outputs(cfn, MESSAGING)
    api = Api(s, cluster["ApiEndpoint"])
    code, _ = api.call("/usuarios/api/usuarios", signed=False)
    if code != 403:
        raise RuntimeError("El Gateway debe rechazar el acceso sin firma IAM; se recibio HTTP " + str(code))
    evidence = {"estado": "CORRECTO", "fechaUTC": checked_at, "commitInfraestructura": commit,
                "region": s.region_name, "accesoSinCredenciales": code, "backend": private_backend(s, cluster),
                "servicios": [wait_ready(api, d, r) for d, r in ENDPOINTS.items()]}
    scaled = False
    try:
        if args.scale:
            scaled = True
            evidence["escaladoArriba"] = scale(s, api, cluster["ManagerInstanceId"], 2)
        if args.async_flow:
            evidence["flujoAsincrono"] = async_flow(s, api, messaging)
    finally:
        if scaled:
            evidence["escaladoAbajo"] = scale(s, api, cluster["ManagerInstanceId"], 1)
    (path / "aws-ep03.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Evidencia cloud guardada: acceso protegido, ocho dominios y las comprobaciones solicitadas.")


if __name__ == "__main__":
    main()
