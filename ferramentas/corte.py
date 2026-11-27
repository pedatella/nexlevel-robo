#!/usr/bin/env python3
"""Ferramenta de cortes da NexLevel (@nexlevel31), rodando no GitHub Actions. Uso (da raiz do repositório):

  PY=python3; cd ferramentas
  $PY corte.py clipes <canal> [dias]                 lista os clipes mais vistos (views, duração, título, slug)
  $PY corte.py baixar <pasta> <canal> <slug> [...]   baixa clipes, gera grade de quadros (<id>_grade.jpg) e quadro.png
  $PY corte.py transcrever <pasta>                   transcreve todos os .mp4 da pasta/brutos (palavras.json)
  $PY corte.py montar <pasta>/corte.json             monta o vídeo 1080x1920 (título, câmera, jogo, legendas, crédito, selo)
  (canal da Twitch sem prefixo; Kick com prefixo: kick:coringa)
  $PY corte.py publicar <pasta>/corte.json           envia como rascunho para a caixa de entrada do TikTok

corte.json:
{
  "titulo": ["LINHA 1 BRANCA", "LINHA 2 ROXA"],
  "criador": "alanzoka", "link": "twitch.tv/alanzoka",
  "cam": [x, y, w, h] ou null,            # caixa da câmera do streamer no quadro 1920x1080 (sem barras de sub/doação)
  "jogo": [x, y, w, h],                   # recorte do jogo; proporção ~1080:990 (ex.: 1063x975) e fora da câmera
  "trechos": [{"arquivo": "<id>.mp4", "ini": 0.0, "fim": 30.0}, ...],   # gancho primeiro; total 61 a 90 s
  "legenda": "texto da publicação (formato do DNA, 5 hashtags)",
}
"""
import glob, json, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = os.environ.get("FF", "ffmpeg")
FONTES = os.environ.get("FONTES", f"{RAIZ}/fontes")
MARCA = f"{RAIZ}/marca"
LOGO = f"{MARCA}/public/logo.png"
ROXO_ASS = "&HF52C8B&"


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
    rng = {"1": "24hr", "7": "7d", "30": "30d"}.get(str(dias), "7d")
    out = subprocess.run(["yt-dlp", "--flat-playlist", "-J", f"https://www.twitch.tv/{canal}/clips?filter=clips&range={rng}"],
                         capture_output=True, text=True).stdout
    for e in (json.loads(out).get("entries") or [])[:40]:
        print(e.get("view_count"), e.get("duration"), e.get("title"), e.get("url", "").rsplit("/", 1)[-1], sep=" | ")


def baixar(pasta, canal, *slugs):
    b = f"{pasta}/brutos"; os.makedirs(b, exist_ok=True)
    for s in slugs:
        subprocess.run(["yt-dlp", "-q", "-f", "best[height<=1080]/best", "--remux-video", "mp4", "-o", f"{b}/%(id)s.%(ext)s",
                        "--write-info-json", _url_clipe(canal, s)], check=False)
    for j in sorted(glob.glob(f"{b}/*.info.json")):
        d = json.load(open(j)); f = f"{b}/{d['id']}.mp4"
        if not os.path.exists(f): continue
        subprocess.run([FF, "-v", "error", "-y", "-i", f, "-vf", "fps=1/5,scale=480:-1,tile=4x3", "-frames:v", "1", f"{b}/{d['id']}_grade.jpg"])
        subprocess.run([FF, "-v", "error", "-y", "-ss", "3", "-i", f, "-frames:v", "1", "-vf", "scale=1920:1080,setsar=1", f"{b}/{d['id']}_quadro.png"])
        print(d["id"], d.get("duration"), d.get("title"), d.get("categories"), sep=" | ")


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
        norm = f"[{i}:v]fps=30,scale=1920:1080,setsar=1"      # todo clipe vira 1920x1080 (as caixas são medidas nesse quadro)
        if cfg.get("cam"):
            fil.append(f"{norm},split[a{i}][b{i}]")
            fil.append(f"[a{i}]crop={cw}:{ch}:{cx}:{cy},scale=1080:690[c{i}]")
            fil.append(f"[b{i}]crop={jw}:{jh}:{jx}:{jy},scale=1080:990[j{i}]")
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
    fil.append(f"[vc]{linhas}[vb]")
    fil.append("[vb][logo]overlay=W-w-24:252:shortest=1[vl]")
    fil.append(f"[vl]subtitles={pasta}/legendas.ass:fontsdir={FONTES}[vf]")
    fil.append("[ac]loudnorm=I=-14:TP=-1.5:LRA=11[af]")
    saida = f"{pasta}/{os.path.basename(pasta)}.mp4"
    subprocess.run([FF, "-v", "error", "-y", *ins, "-filter_complex", ";".join(fil), "-map", "[vf]", "-map", "[af]", "-t", f"{dur:.2f}",
                    "-c:v", "libx264", "-preset", "medium", "-b:v", "14M", "-maxrate", "16M", "-bufsize", "28M", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", saida], check=True)
    qs = []
    for k, s in enumerate((1, dur * 0.3, dur * 0.65, dur - 3)):
        q = f"{pasta}/q{k}.png"; qs.append(q)
        subprocess.run([FF, "-v", "error", "-y", "-ss", f"{s:.1f}", "-i", saida, "-frames:v", "1", "-vf", "scale=360:-1", q])
    subprocess.run([FF, "-v", "error", "-y", *sum((["-i", q] for q in qs), []), "-filter_complex", "hstack=4", f"{pasta}/qa.jpg"])
    for q in qs: os.remove(q)
    # tira com 16 quadros do vídeo inteiro: serve para conferir a HISTÓRIA (começo, meio e fim, sem tela preta)
    subprocess.run([FF, "-v", "error", "-y", "-i", saida, "-vf", f"fps=16/{dur:.2f},scale=270:-1,tile=8x2", "-frames:v", "1", f"{pasta}/tira.jpg"])
    print("ok", saida, f"{dur:.1f}s", len(eventos), "legendas; conferir", f"{pasta}/qa.jpg", "e", f"{pasta}/tira.jpg")


def publicar(cfg_path):
    """Envia o vídeo para a caixa de entrada do TikTok (@nexlevel31) e guarda a legenda para o Lucas colar."""
    cfg = json.load(open(cfg_path)); pasta = os.path.dirname(os.path.abspath(cfg_path))
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import tiktok_envio
    video = f"{pasta}/{os.path.basename(pasta)}.mp4"
    r = tiktok_envio.enviar_rascunho(video)
    open(f"{pasta}/legenda.txt", "w", encoding="utf-8").write(cfg["legenda"])
    print(json.dumps({"tiktok": r, "video": video}, ensure_ascii=False))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    {"clipes": clipes, "baixar": baixar, "transcrever": transcrever, "montar": montar, "publicar": publicar}[cmd](*args)
