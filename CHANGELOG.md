# Histórico de versões

## 0.22.0

- Dados de demonstração embutidos: na primeira abertura em um computador sem dados, o programa mostra
  13 operações e 2 contas fictícias, com datas ajustadas ao dia da instalação.
- Faixa em Minhas operações avisa sobre os dados fictícios, com o botão Apagar dados de demonstração,
  que remove só o que é fictício e preserva o que a pessoa cadastrou.
- Computadores que já têm dados não recebem a demonstração.
- Retirado o arquivo separado de exemplo (`exemplos/…rpvbackup`), substituído pela demonstração embutida.

## 0.21.0

- Filtros Todas, Pendentes, Atrasadas e Recebidas em Minhas operações, com a quantidade de cada situação.
- Operações atrasadas (previsão atual vencida sem recebimento) destacadas em vermelho na tabela e no filtro.
- Gráfico mensal (Exibir → Gráfico mensal) com capital investido e valor recebido nos últimos 12 meses.
- Backup automático semanal em uma pasta escolhida, com primeira cópia na ativação, limite das 10 cópias
  automáticas mais recentes e aviso discreto quando a pasta estiver indisponível.
- Prorrogação recusada para entradas na lixeira, como as demais alterações.
- Histórico geral de alterações removido de vez; registros antigos ficam na cópia feita antes da atualização.
- Backup com documentos corrigido para o Python 3.13 mais recente no Windows, usado na geração do executável.
- Geração do executável: testes no Windows com vigia contra travamentos, tela de 1920×1080 e
  verificação do executável ajustada à instalação sem contas pré-cadastradas.

## 0.20.0

- Nova interface Vitoran Pro: base neutra em cinzas frios (claro) e grafite (escuro), com um único acento
  de marca por tema — carmim no claro, pêssego no escuro.
- Botões e cartões planos, sem sombras, com contorno de 1 px e cantos de 8 a 12 px.
- Títulos em tons neutros; a cor da marca fica reservada às ações principais, ao foco e aos ícones.
- Campos com contorno fino e anel de foco de 2 px; setas das listas suspensas em tom discreto.
- Tabelas com cabeçalho discreto, margem interna nas células e alinhamento por tipo de dado:
  texto à esquerda, valores à direita e datas centralizadas.
- Barras de rolagem finas, sem setas nem ranhuras.
- Ícones da tela inicial com traço mais fino sobre fundo suave da cor da marca.
- Contraste de texto conferido nos dois temas (WCAG AA).

## 0.19.1

- Emblema Vitoran Tech maior e centralizado no espaço livre acima do título da tela inicial.

## 0.19.0

- Exportação para Excel em Minhas operações (Arquivo → Exportar para Excel), com valores em R$,
  datas, situação de recebimento, cabeçalho fixo e filtros, sem dependências externas.
- O tema claro ou escuro escolhido é lembrado ao reabrir o programa.
- Emblema Vitoran Tech no cabeçalho da tela inicial e, com 50% de opacidade, ao lado da assinatura.
- Instalações novas começam sem contas pré-cadastradas; cadastros antigos são preservados.
- Backups automáticos e cópias anteriores às atualizações limitados às 10 mais recentes.
- Código da interface dividido por tela (`tela_operacoes.py`, `tela_registro.py`, `tela_arquivos.py`)
  e estilos em `estilos.py`, sem mudança de comportamento.

## 0.18.0

- Ícone Vitoran Tech com emblema vinho e V em pêssego nas janelas e no executável Windows.
- Janela Sobre com marca, autor e versão, disponível no início e no menu Ajuda de Minhas operações.
- Gerador Windows por dois cliques, com executável portátil único, ícone e metadados de versão.
- Fluxo GitHub Actions para compilar, testar e publicar o ZIP do Windows a partir das tags.
- Verificação do executável em banco temporário e sem Python no PATH, configurada para o ambiente Windows.

## 0.17.0

- Lembrete discreto de backup no início e em Minhas operações: aparece antes do primeiro backup ou após sete dias sem realizar um.
- Clique no lembrete para escolher a pasta e fazer o backup; o aviso desaparece somente após a gravação bem-sucedida.
- Lembrete recalculado ao abrir ou voltar às janelas principais, sem avisos modais.
- Arquivo → Abrir pasta dos documentos abre o explorador na pasta dos anexos, preservando a separação entre entradas e recebimentos.

## 0.16.3

- Modos claro e escuro renovados com azul profundo, pêssego, vermelho e vinho.
- Tema claro com fundos suaves e ações em vermelho; tema escuro com superfícies azuis e destaques em pêssego.
- Paleta aplicada a todas as telas, mantendo o verde de recebimentos e lucros realizados.

## 0.16.2

- Nova paleta inspirada em areia, caramelo e marrom para os modos claro e escuro.
- Cores aplicadas em todas as janelas, campos, tabelas, calendários, ícones e menus.
- Contraste dos botões e caixas de seleção adaptado a cada tema, preservando o verde de recebimentos e lucros realizados.

## 0.16.1

- Cabeçalhos de Minhas operações mantidos em 18 pontos e linhas ajustadas para 12 pontos.
- Caixa de Recebido ampliada e centralizada, com cores para os dois temas.
- Opção do menu Arquivo renomeada para Fazer backup.

## 0.16.0

- Tela de histórico renomeada para Minhas operações.
- Fontes das linhas e cabeçalhos da tabela aumentadas de 10 para 18 pontos.
- Lucro realizado como último cartão e data do último backup no rodapé.
- Exclusão permanente na lixeira, com confirmação e remoção dos anexos vinculados.
- Exclusão de anexos já salvos na entrada e no recebimento, com confirmação.
- Remoção real de contas bancárias, preservando operações e dados históricos de recebimento.
- Somente a célula Situação de contas incompletas fica vermelha e em negrito.
- Caixa Recebido sem texto quando desmarcada.
- Mini-histórico de datas anteriores e novas na edição de previsão atual, incluindo antecipações.
- Migração com backup e compatibilidade com os arquivos de backup anteriores.

## 0.15.1

- Remoção do retângulo tracejado de foco nos botões e controles de seleção, nos dois temas.
- Navegação e acionamento pelo teclado preservados.

## 0.15.0

- Retirada do “(R$)” repetido no rótulo Valor de aquisição, preservando a máscara monetária.
- Balões de ajuda distintos para anexos de contratos/protocolos e comprovantes de recebimento.
- Remoção da marca superior e dos números 01/02/03 dos cartões; assinatura mantida no rodapé.
- Ícones próprios de lua e sol no botão de alternância de tema.
- Fonte das linhas de contas aumentada de 10 para 12 pontos, com dimensões ajustadas.
- Cache de temas nativos e fontes, geometria de sombras compartilhada e menos fragmentos na renderização.
- Listas suspensas fechadas deixam de ser criadas durante a troca de tema.

## 0.14.0

- Nova identidade visual inspirada na paleta Moss: floresta, sálvia e marfim.
- Tela inicial com cartões de ações, ícones próprios, tipografia Segoe UI e alternância de tema.
- Botões arredondados, sombras suaves e destaque nas ações principais, sem dependências extras.
- Modo escuro em tons verdes, com atualização de todas as janelas abertas.
- Indicadores financeiros em cartões e tabela com linhas alternadas e cabeçalhos legíveis.
- Formulários de entrada e contas com rolagem, navegação por foco e ações fixas no rodapé.
- Ícones de calendário desenhados pelo programa, sem depender de caracteres especiais.
- Conteúdo e cálculos preservados; nenhuma alteração no esquema do banco.

## 0.13.1

- Assinatura “Vitoran Tech · v…” no rodapé, usando automaticamente a versão do programa.
- Correção do fundo branco nas opções de previsão ao passar o mouse no tema escuro.
- Cores dos controles de seleção definidas para os estados normal, ativo, pressionado e desabilitado nos dois temas.

## 0.13.0

- Previsão inicial por calendário ou dias, com escolha exclusiva e bloqueio da opção inativa.
- Prazo apresentado como “Previsão inicial de recebimento em [xx] dias.”, seguido da data calculada.
- Validação conforme a opção escolhida, mantendo aquisição como base dos dias corridos.
- Botões finais do formulário com dimensões iguais, espaçamentos regulares e destaque para Salvar.
- Indicadores do histórico separados em blocos alinhados e adaptados à largura da janela.
- Lucro realizado em verde; lixeira preservada no canto inferior direito.

## 0.12.0

- Prazo em dias corridos após a aquisição calcula a previsão inicial de recebimento.
- Prazo e calendário sincronizados, com validação de dias inteiros não negativos.
- Coluna Comissão entre aquisição e Valor Total RPV, com zero por padrão e ordenação.
- Lucro realizado e capital investido em aberto no rodapé, respeitando busca e lixeira.
- Comissão permanece informativa e não altera os cálculos financeiros.
- Ações de previsão e recebimento usam os nomes das colunas para preservar os cliques.

## 0.11.0

- Anexar PDFs e imagens na janela de recebimento, com consulta e abertura dos comprovantes.
- Comprovantes em pasta separada, sem mistura com os documentos da entrada.
- Gravação conjunta da data e dos anexos; falhas de cópia não deixam recebimento parcial.
- Backup e importação preservam as duas categorias e aceitam arquivos das versões 0.9.0 e 0.10.0.
- Backup e Importar dados movidos para o menu Arquivo, retirando os botões da tela.
- Migração com cópia de segurança e preservação dos documentos existentes.

## 0.10.0

- Seleção de várias linhas por arrasto, Ctrl+clique, Shift+clique e Ctrl+A.
- Navegação por setas, Home/End e Page Up/Down; Enter edita, Delete envia à lixeira.
- Exclusão e restauração em lote; menus de contexto preservam a seleção.
- Lixeira com ícone isolado no canto inferior direito do histórico.
- Correção da apresentação e do texto do botão Restaurar entradas.
- Retirada do histórico de alterações da interface e de novos registros de auditoria.
- Anexos PDF e imagens por entrada, com cópia local, consulta e abertura.
- Backup e importação incluem os anexos; compatibilidade com backups da versão 0.9.0.
- Migração com cópia de segurança e preservação dos dados existentes.

## 0.9.0

- Backup portátil `.rpvbackup` com banco, documentos, lixeira e auditoria.
- Importação validada, com confirmação de substituição e backup automático anterior.
- Histórico de alterações por RPV, com data/hora e valores anteriores/novos.
- Exclusão para lixeira e restauração de entradas.
- Ordenação por cabeçalhos em três cliques: primeira direção, inversa e ordem original.
- Várias contas por CPF, mantendo proteção contra repetição de conta bancária e Pix.
- Retirada do total investido da visualização.
- Migração com backup e preservação dos vínculos existentes.

## 0.8.0

- Correção do texto sobreposto à caixa de recebimento ao desmarcar.
- Campos e colunas renomeados para “Valor Total RPV” e “Data de Aquisição”.
- Ações do histórico movidas para uma barra de menus: Arquivo, Editar e Exibir.
- Alternância entre tema claro e escuro em todas as janelas.
- Calculadora integrada com botões e teclado, operações básicas e porcentagem.
- Remoção da frase sobre comissão no histórico, sem alterar os cálculos.

## 0.7.0

- Endereço com número, cidade e estado selecionado pelas siglas das 27 UFs.
- Migração com backup, preservando endereços, snapshots, recebimentos e datas existentes.
- Retirada da coluna Prorrogação; edição direta da previsão atual pelo calendário.
- Previsão atual em vermelho quando posterior à inicial.
- Controle e data de recebimento centralizados na coluna.

## 0.6.0

- Iniciais maiúsculas também após espaços nos endereços.
- Remoção de contas sem vínculos, com confirmação; proteção das contas usadas em RPVs.
- Retirada da frase de ajuda sobre centavos no cadastro.
- Botão real “Adicionar / Ver” nas linhas do histórico de prorrogações e
  cadastro de nova prorrogação em janela separada.
- Coluna “Recebido” com caixa clicável, calendário, data persistida e destaque
  verde em negrito; permite corrigir ou desmarcar com confirmação.
- Migração com backup dos bancos da versão 0.5.0.

## 0.5.0

- CPF obrigatório com máscara automática; agência sem o texto “se houver”.
- Menus de clique direito nos campos, contas e histórico.
- Ação “Copiar” pelo clique direito, substituindo os botões de cópia.
- Capitalização durante a digitação em campos de texto e nomes completos.
- Cadastros incompletos destacados em vermelho com símbolo de alerta.
- Máscara de valores com os dois últimos dígitos como centavos, cursor estável
  e suporte a copiar/colar/recortar valores.

## 0.4.0

Primeira entrega com número de versão visível na interface.

- Contas de recebimento: cadastro, consulta, edição, desativação e reativação.
- Validação de duplicidades de CPF, identificação, dados bancários e chave Pix.
- Cópia dos dados de recebimento guardada em cada operação, com consulta e cópia.
- Nomes completos com iniciais maiúsculas.
- Correção do cursor nos valores: digitação em reais e formatação ao sair do campo.
- Aquisição maior que zero e limitada ao valor previsto de recebimento.
- Coluna clicável de prorrogações, calendário e histórico de datas por RPV.
- Alinhamento centralizado de títulos e valores no histórico.
- Migração automática do banco anterior com backup prévio.

Antes desta versão, as entregas ainda não tinham numeração oficial.
