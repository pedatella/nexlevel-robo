#!/bin/bash
# Manda o vídeo do corte para o Telegram do Lucas (limite do bot: 50 MB; acima disso, recomprime).
# Uso: telegram_video.sh <video.mp4>   (precisa de TG_TOKEN e TG_CHAT no ambiente)
V="$1"
[ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ] && [ -f "$V" ] || { echo "sem vídeo ou Telegram"; exit 0; }
if [ "$(stat -c %s "$V")" -gt 45000000 ]; then
  ffmpeg -loglevel error -y -i "$V" -c:v libx264 -preset veryfast -crf 26 -maxrate 3500k -bufsize 7000k -c:a aac -b:a 128k -movflags +faststart /tmp/tg.mp4 && V=/tmp/tg.mp4
fi
curl -s "https://api.telegram.org/bot$TG_TOKEN/sendVideo" -F "chat_id=$TG_CHAT" -F "supports_streaming=true" \
  -F "video=@$V" --form-string "caption=📲 Vídeo do corte (com som): salve na galeria e poste no TikTok." \
  -o /dev/null -w "Telegram vídeo HTTP %{http_code}\n"
