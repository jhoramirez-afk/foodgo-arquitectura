"""Provision y despliegue de FoodGo, limitado al Learner Lab configurado."""
from pathlib import Path
import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import tarfile
import time

import boto3
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = "foodgo-ep03-cluster"
MESSAGING = "foodgo-ep03-mensajeria"
RUNTIME = ROOT / ".runtime"
SERVICES = ["usuarios", "restaurantes", "pedidos", "pagos", "delivery", "notificaciones", "cupones", "resenas", "eureka"]


def session():
    region = os.environ.get("AWS_REGION", "us-east-1")
    if region not in ("us-east-1", "us-west-2"):
        raise ValueError("La region debe estar permitida por el Learner Lab")
    result = boto3.Session(region_name=region)
    identity = result.client("sts").get_caller_identity()
    expected = os.environ.get("FOODGO_AWS_ACCOUNT_ID", "")
    if not re.fullmatch(r"\d{12}", expected) or identity["Account"] != expected:
        raise ValueError("Configurar AWS_ACCOUNT_ID del Learner Lab; la cuenta activa debe coincidir")
    if ":assumed-role/voclabs/" not in identity["Arn"]:
        raise ValueError("El despliegue requiere la sesion temporal del usuario del Learner Lab, no LabRole")
    return result, identity["Account"]


def stack(client, name):
    try:
        return client.describe_stacks(StackName=name)["Stacks"][0]
    except ClientError as error:
        if error.response["Error"]["Code"] == "ValidationError" and "does not exist" in error.response["Error"].get("Message", ""):
            return None
        raise


def outputs(client, name):
    current = stack(client, name)
    if not current:
        raise ValueError("Falta provisionar el stack " + name)
    return {v["OutputKey"]: v["OutputValue"] for v in current.get("Outputs", [])}


def deploy_template(client, name, filename, parameters):
    body = filename.read_text(encoding="utf-8")
    client.validate_template(TemplateBody=body)
    previous = stack(client, name)
    options = {"StackName": name, "TemplateBody": body,
               "Parameters": [{"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()],
               "Tags": [{"Key": "Project", "Value": "FoodGo"}, {"Key": "Evaluation", "Value": "EP03"}]}
    if previous:
        if previous["StackStatus"] not in ("CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"):
            raise ValueError("Revisar el estado del stack antes de actualizar: " + previous["StackStatus"])
        try:
            client.update_stack(**options)
        except ClientError as error:
            if "No updates are to be performed" in error.response["Error"].get("Message", ""):
                print(name + ": configuracion vigente")
                return outputs(client, name)
            raise
        waiter = "stack_update_complete"
    else:
        if name == CLUSTER:
            options["StackPolicyBody"] = json.dumps({"Statement": [
                {"Effect": "Allow", "Action": "Update:*", "Principal": "*", "Resource": "*"},
                {"Effect": "Deny", "Action": ["Update:Replace", "Update:Delete"], "Principal": "*", "Resource": [
                    "LogicalResourceId/SwarmManager", "LogicalResourceId/AppDatabasePassword", "LogicalResourceId/RootDatabasePassword"]}]})
        client.create_stack(**options, OnFailure="ROLLBACK")
        waiter = "stack_create_complete"
    print(name + ": esperando CloudFormation", flush=True)
    client.get_waiter(waiter).wait(StackName=name, WaiterConfig={"Delay": 15, "MaxAttempts": 80})
    print(name + ": completado", flush=True)
    return outputs(client, name)


def public_subnets(ec2):
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"]
    if len(vpcs) != 1:
        raise ValueError("Se requiere identificar la VPC predeterminada del laboratorio")
    vpc = vpcs[0]["VpcId"]
    tables = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc]}])["RouteTables"]
    main = next((t for t in tables if any(a.get("Main") for a in t.get("Associations", []))), None)
    candidates = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}])["Subnets"]
    selected = []
    for subnet in sorted(candidates, key=lambda s: s["AvailabilityZone"]):
        table = next((t for t in tables if any(a.get("SubnetId") == subnet["SubnetId"] for a in t.get("Associations", []))), main)
        internet = table and any(r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("GatewayId", "").startswith("igw-") and r.get("State") == "active" for r in table["Routes"])
        if internet and subnet["AvailabilityZone"] not in [s["AvailabilityZone"] for s in selected]:
            selected.append(subnet)
    if len(selected) < 2:
        raise ValueError("Se requieren dos subredes con Internet Gateway en zonas distintas")
    return vpc, selected[0]["SubnetId"], selected[1]["SubnetId"]


def artifact_bucket(s, account):
    name = f"foodgo-ep03-{account}-{s.region_name}"
    s3 = s.client("s3")
    try:
        s3.head_bucket(Bucket=name, ExpectedBucketOwner=account)
    except ClientError as error:
        if str(error.response["Error"]["Code"]) not in ("404", "NoSuchBucket", "NotFound"):
            raise
        params = {"Bucket": name}
        if s.region_name != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": s.region_name}
        s3.create_bucket(**params)
    s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=name, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_ownership_controls(Bucket=name, OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]})
    s3.put_bucket_lifecycle_configuration(Bucket=name, LifecycleConfiguration={"Rules": [{
        "ID": "artefactos-versionados", "Status": "Enabled", "Filter": {"Prefix": "releases/"}, "Expiration": {"Days": 30}}]})
    return name


def provision(args):
    s, account = session()
    cfn = s.client("cloudformation")
    existing = stack(cfn, CLUSTER)
    ec2 = s.client("ec2")
    if existing:
        current = {p["ParameterKey"]: p["ParameterValue"] for p in existing["Parameters"]}
        vpc, subnet_a, subnet_b = current["VpcId"], current["SubnetA"], current["SubnetB"]
        ami = current["LinuxAmi"]
    else:
        vpc, subnet_a, subnet_b = public_subnets(ec2)
        running = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["pending", "running"]}])
        if sum(len(v["Instances"]) for v in running["Reservations"]) > 7:
            raise ValueError("No hay margen para dos nodos dentro del limite de nueve instancias del laboratorio")
        ami = s.client("ssm").get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
    if not re.fullmatch(r"ami-[a-f0-9]+", ami):
        raise ValueError("AMI invalida; no se reemplazaran instancias automaticamente")
    s.client("iam").get_instance_profile(InstanceProfileName="LabInstanceProfile")
    s.client("iam").get_role(RoleName="LabRole")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("El codigo debe pertenecer a un commit Git")
    RUNTIME.mkdir(exist_ok=True)
    manifest = RUNTIME / "images.json"
    if not manifest.is_file():
        raise ValueError("Ejecutar source_matrix.py antes de provisionar")
    jar = ROOT / "functions/notificaciones/target/foodgo-notificaciones-lambda-3.0.0.jar"
    if not jar.is_file():
        raise ValueError("Compilar y probar primero la funcion Lambda")
    run_id = os.environ.get("GITHUB_RUN_ID") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not re.fullmatch(r"[a-zA-Z0-9]+", run_id):
        raise ValueError("Identificador de despliegue invalido")
    prefix = f"releases/{sha}/{run_id}"
    archive = RUNTIME / "swarm.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in [ROOT / "docker-stack.yml", *sorted((ROOT / "swarm").glob("*"))]:
            if path.is_file():
                tar.add(path, arcname=str(path.relative_to(ROOT)).replace("\\", "/"))
    bucket = artifact_bucket(s, account)
    for path, key in [(jar, "function.jar"), (archive, "swarm.tar.gz"), (manifest, "images.json")]:
        s.client("s3").upload_file(str(path), bucket, prefix + "/" + key, ExtraArgs={"ServerSideEncryption": "AES256"})
    cluster = deploy_template(cfn, CLUSTER, ROOT / "infra/aws/cluster.yaml", {
        "VpcId": vpc, "SubnetA": subnet_a, "SubnetB": subnet_b, "LinuxAmi": ami,
        "InstanceType": "t3.medium", "InstanceProfileName": "LabInstanceProfile"})
    messaging = deploy_template(cfn, MESSAGING, ROOT / "infra/aws/mensajeria.yaml", {
        "ArtifactBucket": bucket, "ArtifactKey": prefix + "/function.jar",
        "BackendUrl": "http://" + cluster["InternalAlbDns"] + "/notificaciones",
        "SubnetIds": cluster["SubnetIds"], "LambdaSecurityGroupId": cluster["LambdaSecurityGroupId"]})
    state = {"bucket": bucket, "prefix": prefix, "infraCommit": sha, "region": s.region_name,
             "cluster": cluster, "messaging": messaging}
    (RUNTIME / "deployment.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"bucket={bucket}\nprefix={prefix}\nregistry={cluster['Registry']}\n")
    print("Provision completa: dos nodos, Gateway privado, cola y funcion. Falta desplegar las imagenes.")


def run_on_manager(s, instance, script):
    ssm = s.client("ssm")
    command = ssm.send_command(InstanceIds=[instance], DocumentName="AWS-RunShellScript",
        Comment="FoodGo EP03 - despliegue versionado", Parameters={"commands": [script], "executionTimeout": ["1200"]})["Command"]["CommandId"]
    print("Comando de despliegue enviado a SSM", flush=True)
    for attempt in range(300):
        try:
            result = ssm.get_command_invocation(CommandId=command, InstanceId=instance)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(4)
            continue
        if result["Status"] == "Success":
            print(result.get("StandardOutputContent", "")[-12000:])
            return
        if result["Status"] in ("Failed", "Cancelled", "TimedOut", "Cancelling"):
            raise RuntimeError("Fallo el despliegue SSM: " + result.get("StandardErrorContent", "")[-2000:])
        if attempt % 15 == 0:
            print("SSM: " + result["Status"], flush=True)
        time.sleep(4)
    raise TimeoutError("El despliegue no termino en el tiempo esperado; revisar SSM antes de repetir")


def wait_nodes(s, instance_ids):
    for attempt in range(120):
        rows = s.client("ssm").describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": instance_ids}])["InstanceInformationList"]
        if len(rows) == len(instance_ids) and all(r["PingStatus"] == "Online" for r in rows):
            return
        if attempt % 12 == 0:
            print("Esperando los agentes SSM de los dos nodos", flush=True)
        time.sleep(5)
    raise TimeoutError("Los nodos no aparecen online en SSM")


def deploy(args):
    s, account = session()
    cfn = s.client("cloudformation")
    cluster, messaging = outputs(cfn, CLUSTER), outputs(cfn, MESSAGING)
    wait_nodes(s, [cluster["ManagerInstanceId"], cluster["WorkerInstanceId"]])
    if args.service:
        if args.service not in SERVICES or not re.fullmatch(r"[a-f0-9]{40}", args.sha or ""):
            raise ValueError("Servicio o commit invalido")
        image = f"{cluster['Registry']}/foodgo/{args.service}:{args.sha}"
        script = f"""#!/bin/bash
set -euo pipefail
export AWS_DEFAULT_REGION={shlex.quote(s.region_name)}
exec 9>/var/lock/foodgo-ep03-deploy.lock
flock -w 600 9
aws ecr get-login-password | docker login --username AWS --password-stdin {shlex.quote(cluster['Registry'])}
docker service inspect foodgo_{args.service} >/dev/null
docker service update --detach=false --with-registry-auth --image {shlex.quote(image)} foodgo_{args.service}
docker service ps foodgo_{args.service}
"""
    else:
        if not args.bucket or not re.fullmatch(r"[a-z0-9.-]+", args.bucket):
            raise ValueError("Indicar el bucket propio de los artefactos")
        if not re.fullmatch(r"releases/[a-f0-9]{40}/[a-zA-Z0-9]+", args.prefix or ""):
            raise ValueError("Indicar el prefijo versionado del despliegue")
        plan_file = RUNTIME / "images.json"
        RUNTIME.mkdir(exist_ok=True)
        s.client("s3").download_file(args.bucket, args.prefix + "/images.json", str(plan_file))
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if sorted(p["service"] for p in plan) != sorted(SERVICES):
            raise ValueError("El manifiesto debe incluir exactamente los nueve servicios")
        env_lines = []
        for entry in plan:
            if not re.fullmatch(r"[a-f0-9]{40}", entry["sha"]):
                raise ValueError("Commit de imagen invalido")
            s.client("ecr").describe_images(repositoryName="foodgo/" + entry["service"], imageIds=[{"imageTag": entry["sha"]}])
            env_lines.append("export IMAGE_" + entry["service"].upper() + "=" + shlex.quote(cluster["Registry"] + "/foodgo/" + entry["service"] + ":" + entry["sha"]))
        code_id = args.prefix.split("/")[1][:12]
        source = "s3://" + args.bucket + "/" + args.prefix + "/swarm.tar.gz"
        env = "\n".join(env_lines)
        script = f"""#!/bin/bash
set -euo pipefail
export AWS_DEFAULT_REGION={shlex.quote(s.region_name)}
cloud-init status --wait
exec 9>/var/lock/foodgo-ep03-deploy.lock
flock -w 600 9
for FOODGO_ATTEMPT in $(seq 1 120); do
  FOODGO_READY=$(docker node ls --format '{{{{.Status}}}}' | grep -c '^Ready$' || true)
  [ "$FOODGO_READY" -ge 2 ] && break
  sleep 5
done
[ "$FOODGO_READY" -ge 2 ]
FOODGO_RELEASE=$(mktemp -d /srv/foodgo/releases/deploy-XXXXXXXX)
aws s3 cp {shlex.quote(source)} "$FOODGO_RELEASE/swarm.tar.gz" --only-show-errors
tar -xzf "$FOODGO_RELEASE/swarm.tar.gz" -C "$FOODGO_RELEASE"
cd "$FOODGO_RELEASE"
if ! docker secret inspect foodgo_ep03_db_password >/dev/null 2>&1; then
  aws secretsmanager get-secret-value --secret-id {shlex.quote(cluster['AppPasswordSecretArn'])} --query SecretString --output text | tr -d '\\r\\n' | docker secret create foodgo_ep03_db_password - >/dev/null
fi
if ! docker secret inspect foodgo_ep03_db_root_password >/dev/null 2>&1; then
  aws secretsmanager get-secret-value --secret-id {shlex.quote(cluster['RootPasswordSecretArn'])} --query SecretString --output text | tr -d '\\r\\n' | docker secret create foodgo_ep03_db_root_password - >/dev/null
fi
aws ecr get-login-password | docker login --username AWS --password-stdin {shlex.quote(cluster['Registry'])}
{env}
export SQS_QUEUE_URL={shlex.quote(messaging['QueueUrl'])}
export CONFIG_VERSION={shlex.quote(code_id)}
docker stack deploy --with-registry-auth --resolve-image always -c docker-stack.yml foodgo
docker node ls
docker stack services foodgo
"""
    run_on_manager(s, cluster["ManagerInstanceId"], script)


def main():
    parser = argparse.ArgumentParser(description="FoodGo EP03 en AWS Academy")
    parser.add_argument("command", choices=["provision", "deploy", "update-service"])
    parser.add_argument("--bucket")
    parser.add_argument("--prefix")
    parser.add_argument("--service", choices=SERVICES)
    parser.add_argument("--sha")
    args = parser.parse_args()
    if args.command == "provision":
        provision(args)
    else:
        if args.command == "update-service" and not args.service:
            parser.error("update-service requiere --service y --sha")
        deploy(args)


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        raise SystemExit("AWS rechazo la operacion: " + error.response["Error"]["Code"]) from None
