#!/usr/bin/env python3
"""Ferramenta de cortes da NexLevel (@nexlevel31), rodando no GitHub Actions. Uso (da raiz do repositório):

  PY=python3; cd ferramentas
  $PY corte.py clipes <canal> [1|7|30|tudo]                 lista os clipes mais vistos (views, duração, título, slug)
  $PY corte.py baixar <pasta> <canal> <slug> [...]   baixa clipes, gera grade de quadros (<id>_grade.jpg) e quadro.png
  $PY corte.py estender <pasta> <slug_twitch> [antes] [depois]  baixa o trecho da live em volta do clipe (mais contexto, mesma cena)
  $PY corte.py live <canal_twitch> [n]               acha os n momentos mais agitados da última live gravada (pelo áudio)
  $PY corte.py trecho <pasta> <canal> <video_id> <ini> <fim>  baixa esse pedaço da live como se fosse um clipe
  $PY corte.py transcrever <pasta>                   transcreve todos os .mp4 da pasta/brutos (palavras.json)
  $PY corte.py montar <pasta>/corte.json             monta o vídeo 1080x1920 (título, câmera, jogo, legendas, crédito, selo)
  (canal da Twitch sem prefixo; Kick com prefixo: kick:coringa)
  $PY corte.py quadros <pasta> [ini] [fim]          folha com 1 quadro por segundo do vídeo final, com o segundo escrito
  $PY corte.py quadro <pasta> <segundo>             1 quadro em tamanho real com grade de 100 px (medir a caixa do borrão)
  $PY corte.py publicar <pasta>/corte.json           envia como rascunho para a caixa de entrada do TikTok

corte.json:
{
  "titulo": ["LINHA 1 BRANCA", "LINHA 2 ROXA"],
  "criador": "alanzoka", "link": "twitch.tv/alanzoka",
  "cam": [x, y, w, h] ou null,            # caixa da câmera do streamer no quadro 1920x1080 (sem barras de sub/doação)
  "jogo": [x, y, w, h],                   # recorte do jogo; proporção ~1080:990 (ex.: 1063x975) e fora da câmera
  "trechos": [{"arquivo": "<id>.mp4", "ini": 0.0, "fim": 30.0}, ...],   # gancho primeiro; total 61 a 90 s
  "legenda": "texto da publicação (formato do DNA, 5 hashtags)",
  "borrar": [{"ini": 12.0, "fim": 15.5, "caixa": [300, 1200, 400, 500]}]  # opcional: borra SÓ essa caixa (tela final 1080x1920) nesses segundos
}
"""
import glob, json, os, re, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FF", "ffmpeg")
FONTES = os.environ.get("FONTES", f"{RAIZ}/fontes")
MARCA = f"{RAIZ}/marca"
LOGO = f"{MARCA}/public/logo.png"
ROXO_ASS = "&HF52C8B&"
# melhor qualidade até 1440p (fica mais nítido ao reduzir para 1080), nunca a versão vertical automática da Twitch
QUALIDADE = "best[height<=1440][format_id!*=portrait]/best[format_id!*=portrait]/best"
# YouTube: vídeo e áudio vêm separados; junta o melhor até 1440p (nunca Shorts verticais)
QUALIDADE_YT = "bv*[height<=1440][height>=720]+ba/b[height<=1440]/bv*+ba/b"


def _eh_yt(canal):
    return canal.startswith("yt:")


def _url_video(canal, video_id):
    """Endereço do vídeo/live gravada: YouTube (canal "yt:@handle") ou Twitch."""
    if _eh_yt(canal):
        return f"https://www.youtube.com/watch?v={video_id}"
    return f"https://www.twitch.tv/videos/{video_id}"


def _url_clipe(canal, slug):
    """canal "kick:coringa" = Kick; sem prefixo = Twitch."""
    if canal.startswith("kick:"):
        return f"https://kick.com/{canal[5:]}/clips/{slug}"
    return f"https://www.twitch.tv/{canal}/clip/{slug}"


def clipes(canal, dias="7"):
    if canal.startswith("kick:"):
        import time
        limite = time.time() - int(dias) * 86400
        out = subprocess.run(["yt-dlp", "--flat-playlist", "-I", "1:300", "-J", f"https://kick.com/{canal[5:]}/clips"],
                             capture_output=True, text=True).stdout
        es = [e for e in (json.loads(out).get("entries") or []) if (e.get("timestamp") or 0) >= limite]
        es.sort(key=lambda e: e.get("view_count") or 0, reverse=True)
        for e in es[:40]:
            print(e.get("view_count"), e.get("duration"), e.get("title"), e.get("id"), sep=" | ")
        return
    rng = {"1": "24hr", "7": "7d", "30": "30d", "tudo": "all"}.get(str(dias), "7d")
    out = subprocess.run(["yt-dlp", "--flat-playlist", "-J", f"https://www.twitch.tv/{canal}/clips?filter=clips&range={rng}"],
                         capture_output=True, text=True).stdout
    for e in (json.loads(out).get("entries") or [])[:40]:
        print(e.get("view_count"), e.get("duration"), e.get("title"), e.get("url", "").rsplit("/", 1)[-1], sep=" | ")


def baixar(pasta, canal, *slugs):
    b = f"{pasta}/brutos"; os.makedirs(b, exist_ok=True)
    for s in slugs:
        subprocess.run(["yt-dlp", "-q", "-f", QUALIDADE, "--remux-video", "mp4", "-o", f"{b}/%(id)s.%(ext)s",
                        "--write-info-json", _url_clipe(canal, s)], check=False)
    for j in sorted(glob.glob(f"{b}/*.info.json")):
        d = json.load(open(j)); f = f"{b}/{d['id']}.mp4"
        if not os.path.exists(f): continue
        if not os.path.exists(f"{b}/{d['id']}.canal.txt"):
            open(f"{b}/{d['id']}.canal.txt", "w").write(canal)
        subprocess.run([FF, "-v", "error", "-y", "-i", f, "-vf", "fps=1/5,scale=480:-1,tile=4x3", "-frames:v", "1", f"{b}/{d['id']}_grade.jpg"])
        subprocess.run([FF, "-v", "error", "-y", "-ss", "3", "-i", f, "-frames:v", "1", "-vf", "scale=1920:1080,setsar=1", f"{b}/{d['id']}_quadro.png"])
        print(d["id"], d.get("duration"), d.get("title"), d.get("categories"), sep=" | ")


def estender(pasta, slug, antes="45", depois="45"):
    """Clipe da Twitch -> baixa o trecho da LIVE (VOD) em volta dele: `antes` s antes e `depois` s depois do clipe.
    Usa a API oficial da Twitch (Helix) com o app do Lucas (segredos TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET)."""
    import requests
    cid, sec = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
    if not cid or not sec:
        print("SEM VOD: app da Twitch não configurado. Use o clipe normal."); return
    tk = requests.post("https://id.twitch.tv/oauth2/token", timeout=30,
                       data={"client_id": cid, "client_secret": sec, "grant_type": "client_credentials"}).json().get("access_token")
    r = requests.get("https://api.twitch.tv/helix/clips", params={"id": slug}, timeout=30,
                     headers={"Client-Id": cid, "Authorization": f"Bearer {tk}"}).json()
    c = (r.get("data") or [{}])[0]
    if not c.get("video_id") or c.get("vod_offset") is None:
        print("SEM VOD: a live desse clipe não está disponível (apagada ou só para inscritos). Use o clipe normal."); return
    dur = float(c.get("duration") or 30)
    ini = max(0, int(c["vod_offset"]) - int(antes)); fim = int(c["vod_offset"] + dur) + int(depois)
    b = f"{pasta}/brutos"; os.makedirs(b, exist_ok=True)
    nome = f"{c['video_id']}_{ini}"
    subprocess.run(["yt-dlp", "-q", "-f", QUALIDADE, "--download-sections", f"*{ini}-{fim}", "--remux-video", "mp4",
                    "-o", f"{b}/{nome}.%(ext)s", f"https://www.twitch.tv/videos/{c['video_id']}"], check=False)
    f = f"{b}/{nome}.mp4"
    if not os.path.exists(f):
        print("FALHOU o download do trecho da live. Use o clipe normal."); return
    subprocess.run([FF, "-v", "error", "-y", "-i", f, "-vf", "fps=1/6,scale=480:-1,tile=6x4", "-frames:v", "1", f"{b}/{nome}_grade.jpg"])
    subprocess.run([FF, "-v", "error", "-y", "-ss", "3", "-i", f, "-frames:v", "1", "-vf", "scale=1920:1080,setsar=1", f"{b}/{nome}_quadro.png"])
    print(nome, f"{fim - ini}s da live", f"(o clipe original fica de {int(c['vod_offset']) - ini}s a {int(c['vod_offset'] + dur) - ini}s deste arquivo)", sep=" | ")


def _info(url):
    r = subprocess.run(["yt-dlp", "--skip-download", "-J", url], capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def youtube(canal, n="15"):
    """Lista os vídeos e as lives gravadas mais recentes de um canal do YouTube (canal = "yt:@handle").
    Mostra views | duração | título | id. Vídeos longos (lives, gameplays) servem para `picos`; Shorts são ignorados."""
    h = canal[3:]
    vistos = []
    for aba in ("streams", "videos"):
        out = subprocess.run(["yt-dlp", "--flat-playlist", "-I", f"1:{n}", "-J", f"https://www.youtube.com/{h}/{aba}"],
                             capture_output=True, text=True)
        try:
            es = json.loads(out.stdout).get("entries") or []
        except Exception:  # noqa: BLE001
            print(f"{aba}: YouTube não respondeu ({out.stderr.strip()[-200:]})"); continue
        print(f"== {aba} ({len(es)})")
        for e in es:
            if e.get("id") in vistos: continue
            vistos.append(e.get("id"))
            print(e.get("view_count"), e.get("duration"), e.get("title"), e.get("id"), sep=" | ")


def picos(canal, video_id, n="8"):
    """Acha os momentos mais agitados (gritos, risadas) de um vídeo ou live gravada do YouTube pelo áudio.
    Depois use `trecho <pasta> <canal> <video_id> <ini> <fim>` para baixar o pedaço."""
    import numpy as np, tempfile
    url = _url_video(canal, video_id)
    tmp = tempfile.mkdtemp()
    subprocess.run(["yt-dlp", "-q", "-f", "ba[abr<=80]/ba/b", "-o", f"{tmp}/a.%(ext)s", url], check=False)
    arq = glob.glob(f"{tmp}/a.*")
    if not arq:
        print("SEM ÁUDIO: não consegui baixar esse vídeo."); return
    raw = subprocess.run([FF, "-v", "error", "-i", arq[0], "-f", "s16le", "-ac", "1", "-ar", "2000", "-"], capture_output=True).stdout
    for f in arq: os.remove(f)
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    seg = len(a) // 2000
    if seg < 120:
        print("vídeo curto demais para procurar picos: use inteiro com `trecho` 0 ao fim."); return
    rms = np.sqrt((a[:seg * 2000].reshape(seg, 2000) ** 2).mean(1) + 1)
    db = 20 * np.log10(rms)
    janela = min(300, max(30, seg // 6))
    base = np.convolve(db, np.ones(janela) / janela, "same")
    agito = np.convolve(db - base, np.ones(8) / 8, "same")
    agito[:min(60, seg // 10)] = -99; agito[-min(30, seg // 10):] = -99
    mudo = np.convolve(db, np.ones(20) / 20, "same") < 30          # trechos silenciados não servem
    agito[mudo] = -99
    ps = []
    for i in np.argsort(-agito):
        if len(ps) >= int(n): break
        if all(abs(i - p) > 120 for p in ps): ps.append(int(i))
    print(f"vídeo {video_id} ({seg // 60} min)")
    for p in sorted(ps):
        if agito[p] < 3: continue
        print(f"pico em {p // 3600}h{p % 3600 // 60:02d}m{p % 60:02d}s ({p} s) | força {agito[p]:.1f} dB | trecho sugerido: {canal} {video_id} {max(0, p - 70)} {min(seg, p + 40)}")


def live(canal, n="8", horas=""):
    """Acha os melhores momentos da LIVE GRAVADA mais recente do canal da Twitch pelo áudio (gritos, risadas, agito).
    Baixa só o áudio, mede o volume a cada segundo e devolve os n picos (pelo menos 4 min de distância um do outro).
    Pula lives já varridas (marca/lives_usadas.txt). Depois use `trecho` para baixar o vídeo em volta de cada pico."""
    import numpy as np, tempfile
    usadas_f = f"{MARCA}/lives_usadas.txt"
    usadas = set(open(usadas_f).read().split()) if os.path.exists(usadas_f) else set()
    out = subprocess.run(["yt-dlp", "--flat-playlist", "-I", "1:6", "-J", f"https://www.twitch.tv/{canal}/videos?filter=archives&sort=time"],
                         capture_output=True, text=True).stdout
    vods = [e for e in (json.loads(out).get("entries") or []) if e["id"].lstrip("v") not in usadas] if out.strip() else []
    if not vods:
        print("SEM LIVE: nenhuma live gravada nova desse canal (ou só para inscritos)."); return
    v = vods[0]; vid = v["id"].lstrip("v")
    tmp = tempfile.mkdtemp()
    sec = ["--download-sections", f"*0-{int(float(horas) * 3600)}"] if horas else []
    subprocess.run(["yt-dlp", "-q", "-f", "Audio_Only/bestaudio", *sec, "-o", f"{tmp}/a.%(ext)s", f"https://www.twitch.tv/videos/{vid}"], check=False)
    arq = glob.glob(f"{tmp}/a.*")
    if not arq:
        print("SEM LIVE: não consegui baixar o áudio dessa live."); return
    raw = subprocess.run([FF, "-v", "error", "-i", arq[0], "-f", "s16le", "-ac", "1", "-ar", "2000", "-"], capture_output=True).stdout
    for f in arq: os.remove(f)
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    seg = len(a) // 2000
    rms = np.sqrt((a[:seg * 2000].reshape(seg, 2000) ** 2).mean(1) + 1)
    db = 20 * np.log10(rms)
    base = np.convolve(db, np.ones(300) / 300, "same")            # nível normal dos últimos ~5 min
    agito = np.convolve(db - base, np.ones(8) / 8, "same")         # 8 s acima do normal = momento agitado
    agito[:600] = -99; agito[-300:] = -99                          # ignora começo e fim da live
    caps = _info(f"https://www.twitch.tv/videos/{vid}").get("chapters") or []
    def jogo_em(t):
        for c in caps:
            if c["start_time"] <= t < c["end_time"]: return c["title"]
        return "?"
    NAO_JOGO = ("just chatting", "conversando", "irl", "music", "talk shows", "sports", "watch party", "art", "special events")
    for c in caps:                                                   # só momentos de JOGO
        if c["title"].lower() in NAO_JOGO:
            agito[int(c["start_time"]):int(c["end_time"])] = -99
    picos = []
    for i in np.argsort(-agito):
        if len(picos) >= int(n): break
        if all(abs(i - p) > 240 for p in picos): picos.append(int(i))
    with open(usadas_f, "a") as fh: fh.write(vid + "\n")
    print(f"live {vid} ({seg // 60} min): {v.get('title', '')} | jogos: {', '.join(c['title'] for c in caps) or '?'}")
    for p in sorted(picos):
        if agito[p] < 3: continue
        print(f"pico em {p // 3600}h{p % 3600 // 60:02d}m{p % 60:02d}s ({p} s) | {jogo_em(p)} | força {agito[p]:.1f} dB | trecho sugerido: {canal} {vid} {p - 70} {p + 40}")


def trecho(pasta, canal, video_id, ini, fim):
    """Baixa um pedaço da live gravada (segundos ini a fim) para brutos/, com grade e quadro, como um clipe."""
    b = f"{pasta}/brutos"; os.makedirs(b, exist_ok=True)
    ini, fim = max(0, int(float(ini))), int(float(fim)); nome = f"{video_id}_{ini}"
    fmt = ["-f", QUALIDADE_YT, "--merge-output-format", "mp4"] if _eh_yt(canal) else ["-f", QUALIDADE, "--remux-video", "mp4"]
    subprocess.run(["yt-dlp", "-q", *fmt, "--download-sections", f"*{ini}-{fim}", "--force-keyframes-at-cuts",
                    "-o", f"{b}/{nome}.%(ext)s", _url_video(canal, video_id)], check=False)
    f = f"{b}/{nome}.mp4"
    if not os.path.exists(f):
        print("FALHOU o download desse trecho."); return
    subprocess.run([FF, "-v", "error", "-y", "-i", f, "-vf", "fps=1/5,scale=480:-1,tile=6x4", "-frames:v", "1", f"{b}/{nome}_grade.jpg"])
    subprocess.run([FF, "-v", "error", "-y", "-ss", "3", "-i", f, "-frames:v", "1", "-vf", "scale=1920:1080,setsar=1", f"{b}/{nome}_quadro.png"])
    vol = _volume(f)
    if vol < MUDO_DB:   # a Twitch silencia pedaços de VOD (música com direitos): sem som não serve
        os.makedirs(f"{b}/descartados", exist_ok=True); os.replace(f, f"{b}/descartados/{nome}.mp4")
        print(f"TRECHO MUDO ({vol:.0f} dB): a Twitch silenciou esse pedaço da live. Descartado, escolha outro."); return
    open(f"{b}/{nome}.canal.txt", "w").write(canal)
    print(nome, f"{fim - ini}s", f"canal {canal}", f"som {vol:.0f} dB", sep=" | ")


def transcrever(pasta):
    import numpy as np
    from faster_whisper import WhisperModel
    b = f"{pasta}/brutos"; m = WhisperModel("small", compute_type="int8"); out = {}
    for f in sorted(glob.glob(f"{b}/*.mp4")):
        raw = subprocess.run([FF, "-v", "error", "-i", f, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
        segs, _ = m.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, language="pt", word_timestamps=True)
        ws = []; print("==", os.path.basename(f))
        for s in segs:
            print(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}")
            ws += [(w.start, w.end, w.word) for w in s.words]
        out[os.path.basename(f)] = ws
    json.dump(out, open(f"{b}/palavras.json", "w"), ensure_ascii=False)


def _t(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def _volume(f, ini=None, fim=None):
    """Volume médio do áudio em dB (-91 = silêncio). Sem faixa de áudio: -99."""
    cmd = [FF, "-v", "info"] + (["-ss", str(ini), "-to", str(fim)] if ini is not None else []) + ["-i", f, "-vn", "-af", "volumedetect", "-f", "null", "-"]
    m = re.search(r"mean_volume: (-?[0-9.]+) dB", subprocess.run(cmd, capture_output=True, text=True).stderr)
    return float(m.group(1)) if m else -99.0


MUDO_DB = -50   # abaixo disso o vídeo está praticamente sem som


def _duracao(f):
    pr = FF[:-6] + "ffprobe" if FF.endswith("ffmpeg") else "ffprobe"
    r = subprocess.run([pr, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _caixa(box, asp, altura_cheia=False):
    """Ajusta a caixa (no quadro 1920x1080) para a proporção do destino SEM esticar: encolhe em volta do centro.
    altura_cheia: usa a altura toda (1080) e a largura que a proporção pede, centrada no mesmo ponto."""
    x, y, w, h = map(float, box)
    cx, cy = x + w / 2, y + h / 2
    if altura_cheia:
        h = 1080.0; w = h * asp
    elif w / h > asp:
        w = h * asp
    else:
        h = w / asp
    w, h = min(w, 1920), min(h, 1080)
    x = min(max(0, cx - w / 2), 1920 - w); y = min(max(0, cy - h / 2), 1080 - h)
    return [int(v) // 2 * 2 for v in (x, y, w, h)]


def montar(cfg_path):
    cfg = json.load(open(cfg_path)); pasta = os.path.dirname(os.path.abspath(cfg_path)); b = f"{pasta}/brutos"
    palavras = json.load(open(f"{b}/palavras.json"))
    # CRÉDITO À PROVA DE ERRO: o canal vem do download, não da memória do diretor
    canais = set()
    for x in cfg["trechos"]:
        cf = f"{b}/{os.path.splitext(x['arquivo'])[0]}.canal.txt"
        if not os.path.exists(cf):
            raise SystemExit(f"ERRO: não sei de qual canal veio {x['arquivo']} (baixe com baixar/trecho)")
        canais.add(open(cf).read().strip().lower())
    if len(canais) != 1:
        raise SystemExit(f"ERRO: trechos de canais diferentes {canais}: um corte é de UM criador só")
    canal = canais.pop(); nome_canal = canal.split(":")[-1]
    link_certo = (f"kick.com/{nome_canal}" if canal.startswith("kick:") else
                  f"youtube.com/{nome_canal}".lower() if canal.startswith("yt:") else f"twitch.tv/{nome_canal}")
    if cfg.get("link", "").lower().rstrip("/") != link_certo:
        raise SystemExit(f"ERRO DE CRÉDITO: o vídeo é do canal {link_certo}, mas o corte.json diz link={cfg.get('link')!r} "
                         f"e criador={cfg.get('criador')!r}. Corrija criador, link e legenda.")
    if nome_canal.rstrip("e") not in cfg["legenda"].lower() and nome_canal not in cfg["legenda"].lower():
        print(f"AVISO: a legenda não cita {link_certo}; confira o crédito da legenda.")
    trechos = []
    for x in cfg["trechos"]:      # nunca passa do fim do clipe (evita tela preta)
        fim = min(float(x["fim"]), _duracao(f"{b}/{x['arquivo']}") - 0.05)
        trechos.append((x["arquivo"], float(x["ini"]), fim))
    eventos, base = [], 0.0
    for arq, ini, fim in trechos:
        ws = [(a, z, w.strip()) for a, z, w in palavras[arq] if a >= ini - 0.05 and z <= fim + 0.05 and w.strip()]
        bloco = []
        def fecha():
            if not bloco: return
            a = max(bloco[0][0] - ini + base, base); z = bloco[-1][1] - ini + base
            k = max(range(len(bloco)), key=lambda i: len(bloco[i][2]))
            txt = " ".join((f"{{\\c{ROXO_ASS}}}{w.upper()}{{\\c&HFFFFFF&}}" if i == k else w.upper()) for i, (_, _, w) in enumerate(bloco))
            eventos.append((a, max(z, a + 0.4), txt)); bloco.clear()
        for w in ws:
            if bloco and (len(bloco) >= 3 or w[0] - bloco[-1][1] > 0.6): fecha()
            bloco.append(w)
            if w[2].endswith(("?", "!", ".")): fecha()
        fecha(); base += fim - ini
    dur = base
    if not 15 <= dur <= 90: print(f"AVISO: duração {dur:.1f}s fora de 15 a 90 s")
    for i in range(len(eventos) - 1):
        a, z, x = eventos[i]; eventos[i] = (a, min(z, eventos[i + 1][0] - 0.02), x)
    t1, t2 = cfg["titulo"]; cred = f"Corte da live de {cfg['criador']} · {cfg['link']}"
    ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,Archivo Black,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,6,2,5,60,60,0,1
Style: Tit,Archivo Black,62,&H00FFFFFF,&H00FFFFFF,&H000F0A0A,&H00000000,0,0,0,0,100,100,0,0,1,4,0,8,40,40,70,1
Style: Cred,Liberation Sans,34,&H00E6E6EA,&H00FFFFFF,&H000F0A0A,&HA0000000,1,0,0,0,100,100,0,0,3,10,0,2,40,40,46,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{_t(0)},{_t(dur)},Tit,,0,0,0,,{{\\pos(540,40)}}{t1}\\N{{\\c{ROXO_ASS}}}{t2}
Dialogue: 1,{_t(0)},{_t(dur)},Cred,,0,0,0,,{cred}
"""
    y_leg = 985 if cfg.get("cam") else 1530
    for a, z, x in eventos:
        ass += f"Dialogue: 2,{_t(a)},{_t(z)},Leg,,0,0,0,,{{\\pos(540,{y_leg})\\fad(40,0)}}{x}\n"
    open(f"{pasta}/legendas.ass", "w", encoding="utf-8").write(ass)
    ins, fil, n = [], [], len(trechos)
    for arq, ini, fim in trechos:
        ins += ["-ss", str(ini), "-to", str(fim), "-i", f"{b}/{arq}"]
    ins += ["-loop", "1", "-i", LOGO]
    if cfg.get("cam"):
        cx, cy, cw, ch = _caixa(cfg["cam"], 1080 / 690)
        jx, jy, jw, jh = _caixa(cfg["jogo"], 1080 / 990, altura_cheia=True)
        print("câmera", [cx, cy, cw, ch], "jogo", [jx, jy, jw, jh])
    for i, (arq, ini, fim) in enumerate(trechos):
        d = fim - ini
        fil.append(f"color=c=0x0A0A0F:s=1080x1920:r=30:d={d}[f{i}]")
        norm = f"[{i}:v]fps=30,scale=1920:1080:flags=lanczos,setsar=1"      # todo clipe vira 1920x1080 (as caixas são medidas nesse quadro)
        if cfg.get("cam"):
            fil.append(f"{norm},split[a{i}][b{i}]")
            fil.append(f"[a{i}]crop={cw}:{ch}:{cx}:{cy},scale=1080:690:flags=lanczos,unsharp=5:5:1.0:5:5:0.0,eq=contrast=1.04:saturation=1.05[c{i}]")
            fil.append(f"[b{i}]crop={jw}:{jh}:{jx}:{jy},scale=1080:990:flags=lanczos,unsharp=3:3:0.4[j{i}]")
            fil.append(f"[f{i}][c{i}]overlay=0:240[x{i}];[x{i}][j{i}]overlay=0:930[v{i}]")
        else:   # sem câmera: jogo inteiro (16:9, sem cortar) sobre um fundo desfocado dele mesmo
            fil.append(f"{norm},split[a{i}][b{i}]")
            fil.append(f"[a{i}]scale=1080:1680:force_original_aspect_ratio=increase,crop=1080:1680,boxblur=30:2,eq=brightness=-0.25[bg{i}]")
            fil.append(f"[b{i}]scale=1080:608[j{i}]")
            fil.append(f"[f{i}][bg{i}]overlay=0:240[x{i}];[x{i}][j{i}]overlay=0:776[v{i}]")
        fil.append(f"[{i}:a]aresample=48000,asetpts=PTS-STARTPTS[s{i}]")
    fil.append("".join(f"[v{i}][s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    fil.append(f"[{n}:v]scale=150:-1,format=rgba[logo]")
    linhas = "drawbox=x=0:y=234:w=1080:h=6:color=0x8B2CF5:t=fill" + (",drawbox=x=0:y=926:w=1080:h=6:color=0x8B2CF5:t=fill" if cfg.get("cam") else "")
    # borrar: [{"ini": s, "fim": s, "caixa": [x, y, w, h]}] no tempo e na tela do VÍDEO FINAL (1080x1920).
    # Borra SÓ a caixa (a parte imprópria); sem "caixa", borra a área toda do jogo.
    bor = cfg.get("borrar") or []
    atual = "vc"
    for k, x in enumerate(bor):
        if x.get("caixa"):
            bx, by, bw, bh = [int(v) // 2 * 2 for v in x["caixa"]]
        else:
            bx, by, bw, bh = (0, 930, 1080, 990) if cfg.get("cam") else (0, 240, 1080, 1680)
        bw = max(2, min(bw, 1080 - bx)); bh = max(2, min(bh, 1920 - by))
        quando = f"between(t,{float(x['ini']):.2f},{float(x['fim']):.2f})"
        r = max(2, min(40, min(bw, bh) // 4))
        fil.append(f"[{atual}]split[o{k}][c{k}];[c{k}]crop={bw}:{bh}:{bx}:{by},boxblur={r}:4[bl{k}]")
        fil.append(f"[o{k}][bl{k}]overlay={bx}:{by}:enable='{quando}'[b{k}]")
        atual = f"b{k}"
    fil.append(f"[{atual}]{linhas}[vb]")
    fil.append("[vb][logo]overlay=W-w-24:252:shortest=1[vl]")
    fil.append(f"[vl]subtitles={pasta}/legendas.ass:fontsdir={FONTES}[vf]")
    fil.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[af]")
    saida = f"{pasta}/{os.path.basename(pasta)}.mp4"
    subprocess.run([FF, "-v", "error", "-y", *ins, "-filter_complex", ";".join(fil), "-map", "[vf]", "-map", "[af]", "-t", f"{dur:.2f}",
                    "-c:v", "libx264", "-preset", "medium", "-b:v", "14M", "-maxrate", "16M", "-bufsize", "28M", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", saida], check=True)
    vol = _volume(saida)
    if vol < MUDO_DB:
        os.remove(saida)
        raise SystemExit(f"ERRO: o vídeo montado saiu SEM SOM ({vol:.0f} dB). Confira o áudio do clipe/trecho e use outro.")
    print(f"som ok ({vol:.0f} dB)")
    qs = []
    for k, s in enumerate((1, dur * 0.3, dur * 0.65, dur - 3)):
        q = f"{pasta}/q{k}.png"; qs.append(q)
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{s:.1f}", "-i", saida, "-frames:v", "1", "-vf", "scale=360:-1", q])
    subprocess.run([FF, "-v", "error", "-y", *sum((["-i", q] for q in qs), []), "-filter_complex", "hstack=4", f"{pasta}/qa.jpg"])
    for q in qs: os.remove(q)
    # tira com 16 quadros do vídeo inteiro: serve para conferir a HISTÓRIA (começo, meio e fim, sem tela preta)
    subprocess.run([FF, "-v", "error", "-y", "-i", saida, "-vf", f"fps=16/{dur:.2f},scale=270:-1,tile=8x2", "-frames:v", "1", f"{pasta}/tira.jpg"])
    print("ok", saida, f"{dur:.1f}s", len(eventos), "legendas; conferir", f"{pasta}/qa.jpg", "e", f"{pasta}/tira.jpg")


def quadros(pasta, ini="0", fim=""):
    """Folha de quadros do VÍDEO FINAL, 1 por segundo, com o segundo escrito em cada um (para achar onde borrar).
    Gera <pasta>/quadros_<ini>.jpg com até 40 s por folha."""
    saida = f"{pasta}/{os.path.basename(os.path.abspath(pasta))}.mp4"
    dur = _duracao(saida); ini = float(ini); fim = min(float(fim or dur), ini + 40, dur)
    fonte = f"{RAIZ}/fontes/ArchivoBlack-Regular.ttf"
    vf = (f"fps=1,scale=270:-1,drawtext=fontfile={fonte}:text='%{{eif\\:t+{ini:.0f}\\:d}}s':x=8:y=8:fontsize=34:"
          "fontcolor=yellow:borderw=3:bordercolor=black,tile=8x5")
    out = f"{pasta}/quadros_{int(ini)}.jpg"
    subprocess.run([FF, "-v", "error", "-y", "-ss", f"{ini}", "-t", f"{fim - ini}", "-i", saida, "-vf", vf, "-frames:v", "1", out], check=True)
    print("ok", out, f"{ini:.0f}s a {fim:.0f}s")


def quadro(pasta, segundo):
    """Um quadro do vídeo final em tamanho real (1080x1920) com grade de 100 px numerada: serve para medir a caixa do borrão."""
    saida = f"{pasta}/{os.path.basename(os.path.abspath(pasta))}.mp4"
    fonte = f"{RAIZ}/fontes/ArchivoBlack-Regular.ttf"
    linhas = ",".join([f"drawbox=x={x}:y=0:w=2:h=1920:color=yellow@0.6:t=fill" for x in range(100, 1080, 100)] +
                      [f"drawbox=x=0:y={y}:w=1080:h=2:color=yellow@0.6:t=fill" for y in range(100, 1920, 100)])
    nums = ",".join([f"drawtext=fontfile={fonte}:text='{x}':x={x + 4}:y=4:fontsize=22:fontcolor=yellow:borderw=2" for x in range(100, 1080, 100)] +
                    [f"drawtext=fontfile={fonte}:text='{y}':x=4:y={y + 4}:fontsize=22:fontcolor=yellow:borderw=2" for y in range(100, 1920, 100)])
    out = f"{pasta}/quadro_{float(segundo):.0f}s.png"
    subprocess.run([FF, "-v", "error", "-y", "-ss", str(segundo), "-i", saida, "-frames:v", "1", "-vf", f"{linhas},{nums}", out], check=True)
    print("ok", out)


def publicar(cfg_path):
    """Deixa o corte pronto para o Lucas postar: confere o som e grava a legenda.
    Desde 27/11 NÃO envia ao TikTok (pedido do Lucas): o vídeo e a legenda vão pelo Telegram e ele posta."""
    cfg = json.load(open(cfg_path)); pasta = os.path.dirname(os.path.abspath(cfg_path))
    video = f"{pasta}/{os.path.basename(pasta)}.mp4"
    vol = _volume(video)
    if vol < MUDO_DB:
        raise SystemExit(f"ERRO: vídeo SEM SOM ({vol:.0f} dB). Monte de novo com outro clipe.")
    open(f"{pasta}/legenda.txt", "w", encoding="utf-8").write(cfg["legenda"])
    print(json.dumps({"pronto": video, "som_db": round(vol, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"clipes": clipes, "baixar": baixar, "estender": estender, "quadros": quadros, "quadro": quadro, "live": live, "youtube": youtube, "picos": picos, "trecho": trecho, "transcrever": transcrever, "montar": montar, "publicar": publicar}[cmd](*args)
