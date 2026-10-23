# Histórico de versões

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
