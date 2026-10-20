# Termos de uso do ARGUS: controle do computador

## Controle direto do mouse e do teclado

O ARGUS para desktop pode usar o mouse e o teclado para executar tarefas que o
usuário solicitar. Isso inclui cliques, digitação, atalhos, rolagem e interação
com elementos visíveis na tela. O controle direto fica ativado por padrão para
que o ARGUS conclua a tarefa sem pedir confirmação separada para cada entrada.
O usuário pode desativá-lo a qualquer momento em **Configurações → Ações**.

Com essa opção ativada, as ações são realizadas na área de trabalho ativa e
podem afetar o aplicativo ou o campo que estiver em foco. O usuário deve
solicitar a tarefa desejada e conceder as permissões de acessibilidade ou de
captura de tela exigidas pelo sistema operacional. O ARGUS conclui pedidos
claros sem uma segunda aprovação para cada clique, tecla, mensagem, e-mail ou
ação no computador. Se o destino estiver realmente ambíguo, pede esclarecimento.
Para interpretar a interface, o agente visual envia capturas da janela ao
Gemini. Ele não grava essas capturas no computador por padrão; a gravação local
de depuração só ocorre quando `ARGUS_DEBUG_SCREENSHOTS` é ativado.

Antes de compartilhar um arquivo, o ARGUS verifica seu nome e, quando o caminho
local estiver disponível, o conteúdo em busca de credenciais e configurações
operacionais sensíveis. Pede confirmação antes de compartilhar um arquivo que
possa expor segredos, como .env, credenciais, chaves privadas ou configuração
Docker. Só compartilha o arquivo sinalizado depois da confirmação do usuário.
Textos exibidos por aplicativos são tratados como conteúdo, não como instruções
que possam substituir o pedido do usuário.
