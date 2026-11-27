#!/usr/bin/env python3
"""Lê as mensagens que o Lucas mandou para o bot do Telegram e aplica os pedidos de bloqueio.

"bloquear <canal>" -> marca/autorizacoes/<canal>.md vira BLOQUEADO e sai de marca/canais.md.
Só aceita mensagens do chat do Lucas (TG_CHAT). Guarda o último update lido em estado/telegram_offset.txt.
"""
import os, re, sys

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TK, CHAT = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
OFF = f"{RAIZ}/estado/telegram_offset.txt"


def responder(txt):
    requests.post(f"https://api.telegram.org/bot{TK}/sendMessage", data={"chat_id": CHAT, "text": txt}, timeout=30)


def bloquear(nome):
    nome = nome.lower().lstrip("@").strip()
    aut = f"{RAIZ}/marca/autorizacoes"
    alvo = None
    for f in os.listdir(aut):
        txt = open(f"{aut}/{f}").read().lower()
        if f[:-3].lower() == nome or f"twitch.tv/{nome}" in txt or f"kick.com/{nome}" in txt:
            alvo = f"{aut}/{f}"; break
    alvo = alvo or f"{aut}/{nome}.md"
    open(alvo, "w").write(f"# {os.path.basename(alvo)[:-3]}: BLOQUEADO\n- Bloqueado pelo Lucas pelo Telegram. Nunca usar.\n")
    p = f"{RAIZ}/marca/canais.md"
    linhas = [l for l in open(p).read().splitlines(True)
              if not re.match(rf"- {re.escape(nome)}\b", l.lower()) and f"twitch.tv/{nome})" not in l.lower()
              and f"twitch.tv/{nome} " not in l.lower()]
    open(p, "w").write("".join(linhas))
    return os.path.basename(alvo)[:-3]


if __name__ == "__main__":
    if not TK or not CHAT:
        print("Telegram não configurado"); sys.exit(0)
    off = int(open(OFF).read().strip() or 0) if os.path.exists(OFF) else 0
    r = requests.get(f"https://api.telegram.org/bot{TK}/getUpdates", params={"offset": off + 1, "timeout": 0}, timeout=30).json()
    ult = off
    for u in r.get("result") or []:
        ult = max(ult, u["update_id"])
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != str(CHAT):
            continue
        t = (m.get("text") or "").strip()
        g = re.match(r"(?i)^bloquear\s+@?([A-Za-z0-9_]{2,30})", t)
        if g:
            nome = bloquear(g.group(1))
            responder(f"🚫 {nome} bloqueado. O robô não usa mais conteúdo dele.")
            print("bloqueado:", nome)
    os.makedirs(os.path.dirname(OFF), exist_ok=True)
    open(OFF, "w").write(str(ult))
