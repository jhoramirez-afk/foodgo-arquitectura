"""Fija cada imagen a un commit real antes de construir o desplegar."""
from pathlib import Path
import json
import os
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ["usuarios", "restaurantes", "pedidos", "pagos", "delivery", "notificaciones", "cupones", "resenas", "eureka"]


def main():
    plan = []
    for domain in DOMAINS:
        repo = "AlexanderLlanten/foodgo-eureka-server" if domain == "eureka" else "jhoramirez-afk/foodgo-ms-" + domain
        result = subprocess.run(["git", "-c", "credential.helper=", "ls-remote", "https://github.com/" + repo + ".git", "refs/heads/main"],
                                check=True, capture_output=True, text=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        fields = result.stdout.split()
        sha = fields[0] if fields else ""
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise ValueError("GitHub no devolvio un commit valido: " + repo)
        if domain != "eureka":
            url = f"https://raw.githubusercontent.com/{repo}/{sha}/src/main/resources/application-cloud.yml"
            with urllib.request.urlopen(url, timeout=20) as response:
                if b"instance-id" not in response.read(16384):
                    raise ValueError("Fusionar primero el perfil cloud en " + repo)
        plan.append({"service": domain, "repository": repo, "sha": sha})
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "images.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    matrix = json.dumps({"include": plan}, separators=(",", ":"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("matrix=" + matrix + "\n")
    print("Plan fijado: nueve imagenes con sus commits de main. No se crearon recursos AWS.")


if __name__ == "__main__":
    main()
