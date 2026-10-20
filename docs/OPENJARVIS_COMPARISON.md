# Comparação entre ARGUS e OpenJarvis

Comparação feita em 20 de outubro de 2026 a partir do código e da documentação
pública disponível nessa data. Os projetos têm objetivos relacionados, mas não
são equivalentes: ARGUS prioriza uma assistente desktop de voz e controle de
aplicativos; OpenJarvis apresenta uma plataforma local-first para agentes,
avaliação de eficiência e melhoria baseada em rastros locais.

## O que cada projeto já faz

| Área | ARGUS | OpenJarvis |
| --- | --- | --- |
| Voz e interface | Conversa por voz em tempo real, interface desktop PyQt e painel web hospedado. | CLI, GUI/web e agentes; presets incluem experiências de chat e briefing falado. |
| Ações desktop | Abre aplicativos e controla janelas, mouse e teclado; para tarefas visuais usa acessibilidade e visão e verifica as ações. | Não tem ferramenta documentada para ver a área de trabalho ou enviar cliques/teclas globais; o exemplo Browser Assistant controla páginas web com ferramentas de navegador. |
| Pesquisa | Pesquisa web e relatório de deep research; processa arquivos enviados/abertos. | Pesquisa multi-etapas na web e em documentos locais indexados, com citações. |
| Memória e automação | Memória de preferências, fila de tarefas, lembretes e algumas rotinas específicas. | Agentes sob demanda, agendados e contínuos, com memória persistente e monitoramento. |
| Skills | Inventário de ferramentas integrado e plugins Python locais. | Catálogo de skills reutilizáveis, instalação de fontes públicas, descoberta e avaliação. |
| Execução local | As ações desktop e o armazenamento local rodam no computador; a conversa Live atual usa Gemini. As opções Ollama/OpenAI da fábrica ainda são placeholders. | A proposta central é local-first, com provedores locais e nuvem opcional. |
| Avaliação | Logs, métricas e auditorias de QA do produto. | Benchmarks explícitos de latência, throughput, energia, FLOPs, custo e qualidade, além de um ciclo de aprendizado com rastros locais. |

As descrições do OpenJarvis vêm do [README do projeto](https://github.com/open-jarvis/OpenJarvis),
do [guia de skills](https://open-jarvis.github.io/OpenJarvis/user-guide/skills/),
da [documentação de deep research](https://open-jarvis.github.io/OpenJarvis/user-guide/deep-research/)
e do [guia de benchmarks](https://open-jarvis.github.io/OpenJarvis/user-guide/benchmarks/)
e da seção [System Access](https://open-jarvis.github.io/OpenJarvis/user-guide/system-access/),
que esclarece a ausência de computer use.

O guia técnico do OpenJarvis também documenta um registro de ferramentas com
especificações, despacho central e resultados estruturados; o exemplo Browser
Assistant combina navegação, `web_search` e raciocínio em várias etapas. Para o
ARGUS, a lição prática é separar pesquisa online do controle de uma janela real e
deixar cada ferramenta declarar claramente o que controla.

## A função principal do ARGUS: abrir e operar aplicativos

Esse é um diferencial central do ARGUS, e não uma lacuna em relação ao
OpenJarvis. O ARGUS já inclui `open_app`, controles do sistema e uma ferramenta
de tela que combina acessibilidade do Windows com localização visual e confirma
o resultado após cada ação. O OpenJarvis oferece uma interface desktop para
conversar com o agente; sua documentação diz explicitamente que ele não vê a
tela nem controla mouse/teclado. Ele pode abrir aplicativos por comandos de
shell configurados pelo usuário, mas isso não equivale ao agente visual de
desktop do ARGUS.

O ajuste contínuo no ARGUS é tornar confiável a cadeia inteira: escolher um app
instalado, abrir ou focar sua janela, identificar o controle certo, agir e
verificar o resultado. O fluxo visual já faz essa sequência e o controle de
mídia seleciona faixas pelo título/artista. Esta atualização corrige mais três
falhas encontradas no uso real: modelo de busca Gemini descontinuado, seleção de
Chrome mesmo quando ele não está instalado e disputa do Playwright com o perfil
real de um navegador já aberto. Também permite usar o alvo visível como fallback
de digitação no Windows quando a UI Automation não expõe o campo, mantendo a
ação dentro da janela confirmada. Se o usuário pedir explicitamente uma ação em
um editor ou terminal, o agente pode digitar nesse app dentro da tarefa sem
pedir uma confirmação por tecla.

## Lacunas encontradas no ARGUS

1. **Busca em coleção de documentos:** antes desta mudança, ARGUS processava um arquivo por solicitação, sem biblioteca local pesquisável. Esta PR adiciona indexação explícita e busca com citações de caminho/linhas.
2. **Inferência local com Ollama:** a configuração menciona Ollama, mas o provider e a fábrica lançam `NotImplementedError`; o fluxo principal de conversa usa Gemini Live. Ainda falta suporte funcional integrado.
3. **Catálogo portátil de skills:** plugins ARGUS são módulos Python locais e não oferecem o catálogo, descoberta, instalação e avaliação de skills do OpenJarvis. Continua sendo uma lacuna.
4. **Agentes de longa duração e agendamento geral:** há fila de tarefas, lembretes e rotinas pontuais, mas não um serviço genérico de agentes agendados/contínuos com estado persistente.
5. **Benchmarks de eficiência:** logs e QA de produto não substituem benchmarks repetíveis de latência, throughput, custo e energia nem o ciclo de otimização a partir de rastros.

## Escopo implementado nesta mudança

- `local_knowledge` oferece `index`, `search`, `list` e `remove`.
- O usuário precisa indicar explicitamente o arquivo ou pasta. Não há indexação automática nem varredura da pasta pessoal ou do disco.
- O índice usa SQLite FTS5 em `memory/local_knowledge.sqlite3`, ignorado pelo Git.
- Tipos aceitos incluem texto, Markdown, código, JSON/CSV, PDF, DOCX e PPTX. Arquivos ocultos, pastas de dependências, nomes de configuração sensível e arquivos cujo conteúdo parece conter credenciais são ignorados.
- A busca devolve pequenos excertos com caminho e linhas, para a resposta poder citar as fontes. O índice fica no computador, mas os excertos recuperados são enviados ao modelo ativo (Gemini no fluxo atual).
- Remover apaga apenas entradas do índice e nunca os arquivos de origem. O conteúdo dos documentos é tratado como dado não confiável, não como instrução.
- Para tarefas visuais em aplicativos, `window_title` agora pode nomear um app fechado: ARGUS o abre, espera pela janela e a foca antes de agir. A reprodução por busca textual no Spotify faz essa cadeia automaticamente no Windows.
- Chamadas de abrir app, controlar tela e mídia são executadas em sequência para evitar corrida entre abrir o aplicativo e tentar clicar nele.
- Buscas usam `gemini-3.8-flash` com Google Search grounding e fontes quando disponíveis; `ARGUS_WEB_SEARCH_MODEL` permite trocar o modelo sem alterar código. O fallback DDG usa o pacote atual `ddgs` e informa quando provedores não trouxeram resultados, em vez de dizer que a busca não existe.
- Pesquisa comum vai para `web_search`; tarefas que pedem uma janela visível vão para `screen_control`. `browser_control` usa um perfil isolado quando o navegador já está aberto e só usa o perfil salvo do usuário quando ele está fechado, evitando disputar um perfil ativo.
- Pedidos de navegador escolhem o navegador padrão instalado; se o modelo pedir Chrome e o computador não tiver Chrome, o ARGUS continua com o navegador disponível. A busca no navegador gerenciado usa DuckDuckGo por padrão para evitar a página de captcha vista no Google.

## Próximos passos sugeridos

Priorizar um provider local funcional e integrado ao fluxo de conversa; depois,
desenhar um formato de skills com permissões e instalação segura. Em seguida,
adicionar um scheduler genérico e benchmarks reproduzíveis. A busca local deste
PR cobre apenas o primeiro degrau da pesquisa híbrida do OpenJarvis: ela não faz
busca vetorial, planejamento multi-etapas ou aprendizado sobre rastros.
