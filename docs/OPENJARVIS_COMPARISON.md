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
| Ações desktop | Controle visual e de acessibilidade, navegador, arquivos, mídia, e-mail e mensagens. | Ferramentas e agentes configuráveis; o foco não é automação visual do desktop do usuário. |
| Pesquisa | Pesquisa web e relatório de deep research; processa arquivos enviados/abertos. | Pesquisa multi-etapas na web e em documentos locais indexados, com citações. |
| Memória e automação | Memória de preferências, fila de tarefas, lembretes e algumas rotinas específicas. | Agentes sob demanda, agendados e contínuos, com memória persistente e monitoramento. |
| Skills | Inventário de ferramentas integrado e plugins Python locais. | Catálogo de skills reutilizáveis, instalação de fontes públicas, descoberta e avaliação. |
| Execução local | As ações desktop e o armazenamento local rodam no computador; a conversa Live atual usa Gemini. As opções Ollama/OpenAI da fábrica ainda são placeholders. | A proposta central é local-first, com provedores locais e nuvem opcional. |
| Avaliação | Logs, métricas e auditorias de QA do produto. | Benchmarks explícitos de latência, throughput, energia, FLOPs, custo e qualidade, além de um ciclo de aprendizado com rastros locais. |

As descrições do OpenJarvis vêm do [README do projeto](https://github.com/open-jarvis/OpenJarvis),
do [guia de skills](https://open-jarvis.github.io/OpenJarvis/user-guide/skills/),
da [documentação de deep research](https://open-jarvis.github.io/OpenJarvis/user-guide/deep-research/)
e do [guia de benchmarks](https://open-jarvis.github.io/OpenJarvis/user-guide/benchmarks/).

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

## Próximos passos sugeridos

Priorizar um provider local funcional e integrado ao fluxo de conversa; depois,
desenhar um formato de skills com permissões e instalação segura. Em seguida,
adicionar um scheduler genérico e benchmarks reproduzíveis. A busca local deste
PR cobre apenas o primeiro degrau da pesquisa híbrida do OpenJarvis: ela não faz
busca vetorial, planejamento multi-etapas ou aprendizado sobre rastros.
