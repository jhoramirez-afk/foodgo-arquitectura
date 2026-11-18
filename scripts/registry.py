"""Publica imagenes inmutables en ECR sin imprimir contrasenas ni tokens."""
from pathlib import Path
import argparse
import base64
import re
import subprocess

from botocore.exceptions import ClientError
from cloud import SERVICES, session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True, choices=SERVICES)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--context", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{40}", args.sha):
        raise ValueError("La imagen debe identificarse mediante el commit completo")
    s, account = session()
    registry = f"{account}.dkr.ecr.{s.region_name}.amazonaws.com"
    repository = "foodgo/" + args.service
    image = registry + "/" + repository + ":" + args.sha
    ecr = s.client("ecr")
    try:
        ecr.describe_images(repositoryName=repository, imageIds=[{"imageTag": args.sha}])
        print(args.service + ": imagen inmutable ya publicada; se conserva")
        return
    except ecr.exceptions.ImageNotFoundException:
        pass
    token = ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
    username, password = base64.b64decode(token).decode("utf-8").split(":", 1)
    subprocess.run(["docker", "login", registry, "--username", username, "--password-stdin"],
                   input=password + "\n", text=True, check=True)
    del password, token
    source = "AlexanderLlanten/foodgo-eureka-server" if args.service == "eureka" else "jhoramirez-afk/foodgo-ms-" + args.service
    context = args.context.resolve()
    subprocess.run(["docker", "build", "--pull", "--progress", "plain", "--label", "org.opencontainers.image.revision=" + args.sha,
                    "--label", "org.opencontainers.image.source=https://github.com/" + source,
                    "--tag", image, "--file", str(context / "Dockerfile"), str(context)], check=True)
    subprocess.run(["docker", "push", image], check=True)
    print(args.service + ": imagen construida con pruebas y publicada por commit")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        raise SystemExit("AWS rechazo la operacion: " + error.response["Error"]["Code"]) from None
