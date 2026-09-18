"""
OPTCG Coach - Script Utilitário para Deploy do Cloudflare Worker
Uso:
    python tools/deploy_worker.py
As credenciais podem ser passadas via variáveis de ambiente:
    CF_EMAIL, CF_ACCOUNT_ID, CF_API_KEY
ou digitadas interativamente.
"""
import os
import sys
import json
import urllib.request

SCRIPT_NAME = "optcg-coach-api"
WORKER_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cloudflare_worker", "worker.js")

def deploy():
    email = os.environ.get("CF_EMAIL") or input("Email do Cloudflare: ").strip()
    account_id = os.environ.get("CF_ACCOUNT_ID") or input("Account ID do Cloudflare: ").strip()
    api_key = os.environ.get("CF_API_KEY") or input("Global API Key do Cloudflare: ").strip()

    if not email or not account_id or not api_key:
        print("[ERRO] Credenciais incompletas. Cancelando deploy.")
        return False

    if not os.path.isfile(WORKER_FILE):
        print(f"[ERRO] Arquivo {WORKER_FILE} nao encontrado.")
        return False

    with open(WORKER_FILE, "r", encoding="utf-8") as f:
        worker_code = f.read()

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{SCRIPT_NAME}"
    boundary = "CloudflareBoundaryDeploy"
    crlf = "\r\n"
    metadata = json.dumps({"main_module": "worker.js"})

    parts = [
        f"--{boundary}",
        'Content-Disposition: form-data; name="metadata"',
        'Content-Type: application/json',
        '',
        metadata,
        f"--{boundary}",
        'Content-Disposition: form-data; name="worker.js"; filename="worker.js"',
        'Content-Type: application/javascript+module',
        '',
        worker_code,
        f"--{boundary}--"
    ]

    body_bytes = crlf.join(parts).encode("utf-8")
    req = urllib.request.Request(url, data=body_bytes, method="PUT")
    req.add_header("X-Auth-Email", email)
    req.add_header("X-Auth-Key", api_key)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("success"):
                print("[SUCESSO] Cloudflare Worker atualizado com sucesso!")
                return True
            else:
                print(f"[ERRO] Falha no deploy: {result}")
                return False
    except Exception as ex:
        print(f"[ERRO] Falha ao enviar para Cloudflare: {ex}")
        return False

if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
