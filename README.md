# Robô de cortes NexLevel (@nexlevel31)

Roda no GitHub Actions às 10h, 16h e 20h (Brasília). Cada rodada escolhe clipes dos criadores liberados, monta 1 corte de 61 a 90 s e manda como rascunho para a caixa de entrada do TikTok. O Lucas recebe uma issue com a legenda pronta e publica pelo app.

- Marca, regras e autorizações: `marca/`
- Ferramentas: `ferramentas/` (`corte.py`, `tiktok_envio.py`, `prompt.md`)
- Token do TikTok cifrado: `estado/tiktok.enc` (chave no segredo `TOKEN_KEY`)
- Rodar na hora: aba Actions → Corte NexLevel → Run workflow
