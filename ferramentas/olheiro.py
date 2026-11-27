#!/usr/bin/env python3
"""Olheiro da NexLevel: uma vez por semana acha streamers brasileiros de JOGOS em alta e libera os melhores para o robô.

Autorizado pelo Lucas em 27/11/2026 ("pode analisar os streamers que estão em alta e ir pegando conteúdo deles").
- Candidatos: ranking de espectadores da Twitch em português (TwitchTracker) + lista reserva em marca/olheiro_reserva.txt.
- Mede a semana de clipes de cada um (quantidade, views, clipes longos, jogos) e dá uma nota.
- Libera até N novos por semana (autorizacoes/<canal>.md + canais.md) e avisa no Telegram.
- Nunca libera quem está BLOQUEADO ou PENDENTE em autorizacoes/, nem canal de cassino/aposta.
- O Lucas tira qualquer um mandando "bloquear <canal>" para o bot do Telegram (ver bloqueios.py).
"""
import json, os, re, subprocess, sys, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUT = f"{RAIZ}/marca/autorizacoes"
NAO_JOGO = {"just chatting", "conversando", "irl", "music", "talk shows & podcasts", "sports", "slots", "virtual casino",
            "poker", "pools, hot tubs, and beaches", "asmr", "art", "special events", "?"}


def ja_conhecidos():
    s = set()
    for f in os.listdir(AUT):
        if f.endswith(".md") and f != "PENDENTES.md":
            s.add(f[:-3].lower())
            txt = open(f"{AUT}/{f}").read().lower()
            for m in re.findall(r"twitch\.tv/([a-z0-9_]+)", txt):
                s.add(m)
    pend = open(f"{AUT}/PENDENTES.md").read().lower() if os.path.exists(f"{AUT}/PENDENTES.md") else ""
    canais = open(f"{RAIZ}/marca/canais.md").read().lower()
    s |= set(re.findall(r"twitch\.tv/([a-z0-9_]+)", canais)) | set(re.findall(r"[a-z0-9_]{3,}", pend))
    return s


def candidatos():
    nomes = []
    try:
        import requests
        h = requests.get("https://twitchtracker.com/channels/viewership/portuguese", timeout=30,
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}).text
        nomes = re.findall(r'href="/([A-Za-z0-9_]{3,25})"', h)
    except Exception as e:  # noqa: BLE001
        print("ranking indisponível:", type(e).__name__)
    reserva = f"{RAIZ}/marca/olheiro_reserva.txt"
    if os.path.exists(reserva):
        nomes += [l.strip() for l in open(reserva) if l.strip() and not l.startswith("#")]
    # posição no ranking de espectadores (0 = mais assistido); a lista reserva fica sem posição
    vistos, out, n_rank = set(), [], len(nomes) - (len(open(reserva).read().split()) if os.path.exists(reserva) else 0)
    for k, n in enumerate(nomes):
        n = n.lower()
        if n in vistos or n in {"channels", "games", "statistics", "subscribers", "languages", "search", "login"}:
            continue
        vistos.add(n); out.append((n, len([x for x in out if x[1] is not None]) if k < n_rank else None))
    return out[:70]


def medir(canal):
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", f"https://www.twitch.tv/{canal}/clips?filter=clips&range=7d"],
                       capture_output=True, text=True, timeout=180)
    try:
        es = json.loads(r.stdout).get("entries") or []
    except Exception:  # noqa: BLE001
        es = []
    if not es:
        return None
    views = [e.get("view_count") or 0 for e in es]
    longos = sum(1 for e in es if (e.get("duration") or 0) >= 45)
    jogos = []
    for e in sorted(es, key=lambda x: -(x.get("view_count") or 0))[:4]:
        i = subprocess.run(["yt-dlp", "--skip-download", "-J", e["url"]], capture_output=True, text=True, timeout=120)
        try:
            jogos += json.loads(i.stdout).get("categories") or []
        except Exception:  # noqa: BLE001
            pass
    de_jogo = [j for j in jogos if j.lower() not in NAO_JOGO]
    cassino = any(j.lower() in {"slots", "virtual casino", "poker"} for j in jogos)
    return {"canal": canal, "clipes": len(es), "views": sum(views), "top": max(views), "longos": longos,
            "jogos": sorted(set(jogos)), "parte_jogo": len(de_jogo) / max(1, len(jogos)), "cassino": cassino}


def famoso(m):
    """Regra do Lucas (27/11): só streamer com público grande, que o público reconhece."""
    no_topo = m.get("pos") is not None and m["pos"] < 15
    return m["top"] >= 1000 and (no_topo or m["views"] >= 5000)


def nota(m):
    # PÚBLICO primeiro (views do melhor clipe, views da semana, posição no ranking); volume de clipes só desempata
    rank = (15 - m["pos"]) * 300 if m.get("pos") is not None and m["pos"] < 15 else 0
    return (m["top"] + m["views"] / 5 + rank + m["longos"] * 5 + min(m["clipes"], 80)) * m["parte_jogo"]


def liberar(m):
    c = m["canal"]
    open(f"{AUT}/{c}.md", "w").write(
        f"# {c}: LIBERADO\n"
        f"- Fonte: olheiro automático em {time.strftime('%d/%m/%Y')}, com autorização geral do Lucas (27/11/2026) "
        f"para usar streamers de jogos em alta.\n"
        f"- Semana medida: {m['clipes']} clipes, {m['longos']} longos, melhor clipe com {m['top']} views; jogos: {', '.join(m['jogos'])}.\n"
        f"- Crédito obrigatório: \"Corte da live de {c} · twitch.tv/{c}\" na tela e na legenda.\n"
        f"- Se o canal disser que não permite reupload/cortes, ou o Lucas mandar bloquear, vira BLOQUEADO.\n")
    with open(f"{RAIZ}/marca/canais.md") as fh:
        canais = fh.read()
    linha = f"- {c} → twitch.tv/{c} (olheiro: {', '.join(j for j in m['jogos'] if j.lower() not in NAO_JOGO)[:60]})\n"
    canais = canais.replace("Bloqueado:", linha + "Bloqueado:", 1) if "Bloqueado:" in canais else canais + linha
    open(f"{RAIZ}/marca/canais.md", "w").write(canais)


def telegram(txt):
    tk, chat = os.environ.get("TG_TOKEN"), os.environ.get("TG_CHAT")
    if not tk or not chat:
        print(txt); return
    import requests
    requests.post(f"https://api.telegram.org/bot{tk}/sendMessage", timeout=30,
                  data={"chat_id": chat, "text": txt, "disable_web_page_preview": "true"})


if __name__ == "__main__":
    n_novos = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    conhecidos = ja_conhecidos()
    medidos = []
    for c, pos in candidatos():
        if c in conhecidos:
            continue
        m = medir(c)
        if not m:
            continue
        m["pos"] = pos
        print(c, "pos", pos, "| clipes", m["clipes"], "longos", m["longos"], "| top", m["top"], "semana", m["views"], m["jogos"],
              "| nota", round(nota(m), 1), "| famoso" if famoso(m) else "")
        if m["cassino"] or m["parte_jogo"] < 0.5 or m["clipes"] < 10 or not famoso(m):
            continue
        medidos.append(m)
    medidos.sort(key=nota, reverse=True)
    novos = medidos[:n_novos]
    for m in novos:
        liberar(m)
    if novos:
        linhas = "\n".join(f"• {m['canal']}: {m['clipes']} clipes na semana ({m['longos']} longos), melhor com {m['top']} views; "
                           f"{', '.join(j for j in m['jogos'] if j.lower() not in NAO_JOGO)}" for m in novos)
        telegram("🔎 Olheiro NexLevel: comecei a usar streamers em alta\n\n" + linhas +
                 "\n\nPara tirar algum, mande aqui: bloquear <nome>")
    else:
        telegram("🔎 Olheiro NexLevel: nenhum streamer novo valeu a pena esta semana.")
