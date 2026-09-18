"""
OPTCG Coach - Script Utilitário para Testar o Cloudflare Worker do Coach IA
Uso:
    python tools/test_worker.py
"""
import urllib.request
import json
import sys

DEFAULT_WORKER_URL = "https://optcg-coach-api.gustavodallagoferreira.workers.dev/"

def test_worker(url=DEFAULT_WORKER_URL):
    print(f"[*] Testando conexao com o Worker: {url}")
    
    # 1. Teste GET (Modelos disponiveis)
    req_get = urllib.request.Request(url, method='GET')
    req_get.add_header('User-Agent', 'Mozilla/5.0')
    try:
        with urllib.request.urlopen(req_get, timeout=10) as resp:
            print(f"[OK] GET respondeu HTTP {resp.status}")
    except Exception as e:
        print(f"[WARN] Falha no teste GET: {e}")

    # 2. Teste POST (Geracao com Gemini)
    payload = {
        'contents': [
            {'role': 'user', 'parts': [{'text': 'Diga apenas: Conexao OK'}]}
        ]
    }
    data = json.dumps(payload).encode('utf-8')
    req_post = urllib.request.Request(url, data=data, method='POST')
    req_post.add_header('Content-Type', 'application/json')
    req_post.add_header('User-Agent', 'Mozilla/5.0')
    
    try:
        with urllib.request.urlopen(req_post, timeout=25) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            candidates = res_data.get('candidates', [])
            if candidates:
                reply = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                print(f"[SUCESSO] IA respondeu com sucesso: '{reply.strip()}'")
                return True
            else:
                print(f"[INFO] Resposta sem candidatos: {res_data}")
                return False
    except urllib.error.HTTPError as he:
        print(f"[ERRO] HTTP {he.code}: {he.read().decode('utf-8')[:300]}")
        return False
    except Exception as ex:
        print(f"[ERRO] Excecao ao chamar Worker: {ex}")
        return False

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WORKER_URL
    success = test_worker(target)
    sys.exit(0 if success else 1)
