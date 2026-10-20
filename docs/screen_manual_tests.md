# Checklist manual: controle visual de tela

Execute com a janela de teste em primeiro plano e confirme que nenhuma ação é
disparada em uma conversa ou conta real sem pedido explícito.

- [ ] Perguntar “o que está na tela?” e conferir o resumo da janela focada.
- [ ] No Discord, abrir uma conversa pelo nome quando ela aparece em posições
  diferentes na lista; confirmar que o cabeçalho corresponde ao destinatário.
- [ ] Enviar uma mensagem de teste no Discord, WhatsApp e Telegram; conferir o
  texto exato na conversa e que ARGUS não acrescentou uma assinatura.
- [ ] Abrir um resultado do Spotify por título e artista sem pedir que o usuário
  selecione o resultado quando só houver uma correspondência visível.
- [ ] Digitar texto com acentos e emoji no Bloco de Notas; confirmar que o foco
  do campo foi verificado antes de colar.
- [ ] Rolar até um item que inicialmente não está visível e confirmar o estado
  da tela após cada ação.
- [ ] Repetir com escala de tela do Windows em 100%, 125% e 150%, incluindo uma
  janela posicionada fora da origem do monitor principal.
- [ ] Abrir duas janelas com controles de mesmo nome e conferir que ARGUS pede
  esclarecimento ou usa a posição visual para escolher o alvo exato.
- [ ] Pedir para compartilhar um arquivo comum e conferir que não há confirmação
  redundante; repetir com um arquivo .env ou docker-compose.yml e conferir que
  a confirmação aparece antes do envio.
- [ ] Acionar Ctrl+Alt+Shift+Esc durante uma tarefa e conferir que a sequência
  para imediatamente.
- [ ] Ativar ARGUS_DEBUG_SCREENSHOTS=true e conferir que as capturas anotadas
  ficam somente em logs/screen/<run_id>/; com o padrão, nenhum screenshot é
  gravado em disco.
