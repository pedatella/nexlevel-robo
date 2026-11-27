#!/bin/zsh
# Gera o token do Claude (assinatura do Lucas), testa e salva direto no segredo do GitHub do robô.
# Não precisa copiar nada: o script pega o código sozinho. O token não fica salvo em arquivo nenhum.
TMP=$(mktemp -t ctk)
trap 'rm -f "$TMP"' EXIT
clear
echo "=============================================================="
echo "  Vai abrir o navegador. Clique em AUTORIZAR (Authorize)."
echo "  Depois volte aqui e espere: eu salvo tudo sozinho."
echo "=============================================================="
echo ""
script -q "$TMP" zsh -c 'stty cols 400 2>/dev/null; claude setup-token'
TOKEN=$(python3 - "$TMP" <<'PY'
import re, sys
t = open(sys.argv[1], errors="ignore").read()
t = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\r", "", t)
m = re.findall(r"sk-ant-oat01-[A-Za-z0-9_\-]{40,}", t)
print(m[-1] if m else "")
PY
)
rm -f "$TMP"
if [ -z "$TOKEN" ]; then
  echo ""; echo "!!! Não achei o código. Avise o Claude no chat."; exit 1
fi
echo ""; echo "Testando o código..."
if ! CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" claude -p "responda só: ok" >/dev/null 2>&1; then
  echo "!!! O código não funcionou no teste. Avise o Claude no chat."; exit 1
fi
printf '%s' "$TOKEN" | gh secret set CLAUDE_CODE_OAUTH_TOKEN -R pedatella/nexlevel-robo && {
  clear
  echo "=============================================================="
  echo "  PRONTO: token salvo no GitHub. Pode voltar para o chat."
  echo "=============================================================="
}
unset TOKEN
