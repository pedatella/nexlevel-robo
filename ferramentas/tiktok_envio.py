"""Envio de rascunho para a caixa de entrada do TikTok (@nexlevel31) pela Content Posting API oficial.

- client key e client secret: segredos TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET do GitHub.
- tokens da conta: estado/tiktok.enc, cifrado com AES-GCM pela chave TOKEN_KEY (segredo do GitHub, base64 de 32 bytes).
  O token de renovação do TikTok troca a cada uso: o arquivo é regravado e o workflow faz commit dele.
- Nada de token ou segredo é impresso.
"""
import base64, json, os, sys, time
from datetime import datetime, timedelta, timezone

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

API = "https://open.tiktokapis.com"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQ = f"{RAIZ}/estado/tiktok.enc"


def _chave():
    return AESGCM(base64.b64decode(os.environ["TOKEN_KEY"]))


def ler_estado():
    bruto = base64.b64decode(open(ARQ).read().strip())
    return json.loads(_chave().decrypt(bruto[:12], bruto[12:], None))


def gravar_estado(d):
    nonce = os.urandom(12)
    tmp = ARQ + ".tmp"
    open(tmp, "w").write(base64.b64encode(nonce + _chave().encrypt(nonce, json.dumps(d).encode(), None)).decode())
    os.replace(tmp, ARQ)


def token():
    t = ler_estado()
    if datetime.fromisoformat(t["expira_em"]) - datetime.now(timezone.utc) > timedelta(minutes=5):
        return t["access_token"]
    r = requests.post(API + "/v2/oauth/token/", timeout=60, headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data={"client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
                            "grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
    d = r.json()
    if d.get("error") or not d.get("access_token"):
        raise SystemExit(f"TikTok recusou a renovação ({d.get('error')}): o Lucas precisa reconectar a conta")
    agora = datetime.now(timezone.utc)
    t.update(access_token=d["access_token"], refresh_token=d.get("refresh_token") or t["refresh_token"],
             expira_em=(agora + timedelta(seconds=int(d.get("expires_in", 86400)))).isoformat(),
             renovacao_expira_em=(agora + timedelta(seconds=int(d.get("refresh_expires_in", 31536000)))).isoformat())
    gravar_estado(t)
    return t["access_token"]


def _api(tk, caminho, corpo):
    r = requests.post(API + caminho, json=corpo, timeout=60,
                      headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json; charset=UTF-8"})
    d = r.json()
    err = (d.get("error") or {}).get("code", "ok")
    if err != "ok":
        raise SystemExit(f"TikTok: {err} {(d.get('error') or {}).get('message', '')}")
    return d.get("data") or {}


def enviar_rascunho(video):
    tk = token()
    tam = os.path.getsize(video)
    if tam > 64 * 1024 * 1024:
        parte = 16 * 1024 * 1024; total = tam // parte
    else:
        parte, total = tam, 1
    d = _api(tk, "/v2/post/publish/inbox/video/init/",
             {"source_info": {"source": "FILE_UPLOAD", "video_size": tam, "chunk_size": parte, "total_chunk_count": total}})
    with open(video, "rb") as fh:
        for i in range(total):
            ini = i * parte; fim = tam - 1 if i == total - 1 else ini + parte - 1
            bloco = fh.read(fim - ini + 1)
            r = requests.put(d["upload_url"], data=bloco, timeout=900,
                             headers={"Content-Type": "video/mp4", "Content-Length": str(len(bloco)),
                                      "Content-Range": f"bytes {ini}-{fim}/{tam}"})
            if r.status_code not in (201, 206):
                raise SystemExit(f"TikTok recusou o arquivo (HTTP {r.status_code})")
    pid = d["publish_id"]; st = {}
    for _ in range(60):
        st = _api(tk, "/v2/post/publish/status/fetch/", {"publish_id": pid})
        if st.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE", "FAILED"):
            break
        time.sleep(10)
    if st.get("status") == "FAILED":
        raise SystemExit(f"TikTok falhou ao processar: {st.get('fail_reason')}")
    return {"publish_id": pid, "status": st.get("status")}


if __name__ == "__main__":
    if sys.argv[1:] == ["testar"]:
        tk = token()
        r = requests.get(API + "/v2/user/info/?fields=display_name", timeout=60, headers={"Authorization": f"Bearer {tk}"})
        print("conta:", (r.json().get("data") or {}).get("user", {}).get("display_name"))
