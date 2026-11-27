#!/bin/zsh
# Conecta o robô NexLevel ao seu Telegram. O token do bot não aparece na tela nem fica salvo em arquivo.
clear
while true; do
  echo "=============================================================="
  echo "  PASSO 1: cole o TOKEN do BotFather (Cmd+V) e aperte Enter."
  echo "  (nada aparece enquanto cola, é normal)"
  echo "=============================================================="
  read -rs "TK?> "
  echo ""
  TK=$(printf '%s' "$TK" | tr -d ' \r\n')
  NOME=$(curl -s "https://api.telegram.org/bot$TK/getMe" | python3 -c "
import json,sys
try: d=json.load(sys.stdin); print(d['result']['username'] if d.get('ok') else '')
except Exception: print('')")
  if [ -n "$NOME" ]; then echo "  OK: token do bot @$NOME"; break; fi
  echo "  !!! Esse token não funcionou. Copie de novo a linha inteira do BotFather (ex.: 123456:AAH...)."
  echo ""
done
echo ""
echo "=============================================================="
echo "  PASSO 2: no Telegram, abra t.me/$NOME , toque em INICIAR"
echo "  e mande 'oi'. Não precisa voltar aqui: eu espero sozinho."
echo "=============================================================="
CHAT=""
for i in $(seq 1 60); do
  CHAT=$(curl -s "https://api.telegram.org/bot$TK/getUpdates" | python3 -c "
import json,sys
try:
    r=json.load(sys.stdin).get('result') or []
    ids=[u['message']['chat']['id'] for u in r if u.get('message')]
    print(ids[-1] if ids else '')
except Exception: print('')")
  [ -n "$CHAT" ] && break
  sleep 3
done
if [ -z "$CHAT" ]; then
  echo ""; echo "!!! Não chegou mensagem em 3 minutos. Rode de novo: zsh salvar_telegram.sh"; exit 1
fi
printf '%s' "$TK" | gh secret set TELEGRAM_TOKEN -R pedatella/nexlevel-robo || exit 1
printf '%s' "$CHAT" | gh secret set TELEGRAM_CHAT_ID -R pedatella/nexlevel-robo || exit 1
curl -s "https://api.telegram.org/bot$TK/sendMessage" --data-urlencode "chat_id=$CHAT" \
  --data-urlencode "text=✅ Robô NexLevel conectado! A cada corte você recebe aqui o aviso e a legenda pronta." -o /dev/null
unset TK
clear
echo "=============================================================="
echo "  PRONTO: Telegram conectado. Olhe o seu Telegram e volte ao chat."
echo "=============================================================="
