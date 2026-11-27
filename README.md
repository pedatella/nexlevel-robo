# Robô de cortes NexLevel (@nexlevel31)

Roda no GitHub Actions às 10h, 16h e 20h (Brasília). Cada rodada escolhe clipes dos criadores liberados, monta 1 corte de 61 a 90 s e manda como rascunho para a caixa de entrada do TikTok. O Lucas recebe uma issue com a legenda pronta e publica pelo app.

- Marca, regras e autorizações: `marca/`
- Ferramentas: `ferramentas/` (`corte.py`, `tiktok_envio.py`, `prompt.md`)
- Token do TikTok cifrado: `estado/tiktok.enc` (chave no segredo `TOKEN_KEY`)
- Rodar na hora: aba Actions → Corte NexLevel → Run workflow

## Para nada falhar
- Até 3 tentativas por rodada (5 min entre elas). Depois que o vídeo vai para o TikTok, não repete.
- Falha vira issue com título começando por "FALHOU".
- O TikTok aceita no máximo 5 rascunhos não publicados: poste os rascunhos para a fila não travar.
- O token do Claude e a conexão com o TikTok vencem em cerca de 1 ano. Para renovar o do Claude, rode `zsh salvar_token_claude.sh`.
