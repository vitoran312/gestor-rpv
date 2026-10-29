# Histórico de versões

## 0.53.0

Repaginada visual (identidade Vitoran Pro mantida):
- Minhas operações: cabeçalho compacto, indicadores no topo, busca com lupa, texto de exemplo e ×, tabela, e
  rodapé com o último backup e a Lixeira com ícone e nome. Contas e Gráfico usam o mesmo cabeçalho.
- Tabelas (operações, contas, lixeira): realce da linha sob o mouse, que respeita a cor das atrasadas e
  recebidas; estados vazios com orientação (busca sem resultado, filtros, lixeira, contas, documentos,
  histórico da previsão).
- Validação no campo: entrada e conta contornam em vermelho cada campo citado nos problemas e focam o
  primeiro; o contorno some ao alterar o campo.
- Avisos passageiros (componentes.Notificacao) para entrada salva, alterações, recebimento, previsão,
  exclusão, restauração, contas e dados de demonstração apagados.
- Diálogos e formulários surgem esmaecendo (movimento.surgir); foco visível nos botões pelo teclado; cursor
  de espera em backup, importação e exportação.
- Diálogos de recebimento e previsão com título e o nome do titular abaixo.
- movimento.py: curva ease-out da skill animate, preferência do Windows por menos animação e
  GESTOR_RPV_SEM_ANIMACAO=1. tema.py: tokens ESPACO e TIPO e cores de realce e de aviso.
- App do celular: toque com leve encolhimento (0,97, 160 ms) e entrada sutil ao trocar de tela (4 px, 180 ms),
  sem deslocamento quando o sistema pede menos movimento.

## 0.52.0

App do celular:
- Mais: "Abrir um backup mais novo" (ou "Restaurar uma cópia de segurança", para quem usa só o celular). Escolhido
  o arquivo, o app volta à abertura com ele e, com Face ID ativo, já pede o rosto para abrir.
- Primeira abertura, sem dados no aparelho: o app mostra uma demonstração com os dados fictícios do programa
  (celular/demonstracao.sqlite3, gerado por gerar_modelo_celular.py, com as datas deslocadas para hoje), só para
  consulta, com o aviso de que os dados são meramente sugestivos em todas as telas e o botão "Começar com meus
  dados". A abertura também oferece "Ver a demonstração".

## 0.51.1

- App do celular: no iPhone, a tela da operação voltava para cima ao rolar e escondia os botões do fim. O campo
  de arquivo de "+ Anexar foto ou PDF" passa a ficar contido no próprio botão, o olho do modo discreto ganha
  uma coluna própria no cabeçalho (sem sobreposição) e o fim das telas tem mais folga acima das abas.

## 0.51.0

App do celular:
- Modo discreto: o botão de olho no topo troca todos os valores em reais por "R$ •••••"; fica ligado entre
  aberturas. Os campos dos formulários continuam mostrando o que se digita.
- "Colar e preencher" na entrada nova: lê uma mensagem (WhatsApp, e-mail, processo) e preenche titular,
  valores (Valor Total RPV, aquisição, comissão) e datas (aquisição, previsão) pelo que vem escrito antes de
  cada um; CPF e número do processo (padrão CNJ) vão para as observações.
- "Compartilhar resumo em imagem" na operação: imagem com o logo, o titular, a situação e as datas, sem CPF,
  conta, banco ou Pix; o Valor Total RPV só se a pessoa marcar.

## 0.50.0

App do celular:
- Operação: "Alterar previsão" (a anterior fica no histórico), "Editar dados da entrada" (mesmas regras do
  programa) e "Excluir operação" (vai para a lixeira; quem usa só o celular pode restaurar).
- "+ Anexar foto ou PDF" na operação e "Documentos" na entrada nova: a câmera abre direto; fotos são reduzidas
  (lado maior até 2000 px, JPEG) e PDFs vão como estão (até 25 MB).
- Agenda: no Início, atrasadas, hoje, amanhã e próximos 7 dias (com os nomes de hoje e amanhã); em Agenda, o
  calendário do mês com as previsões de cada dia.
- "Enviar todos para o computador" na lista do que aguarda o computador.

Programa:
- Importa do celular alterações, novas previsões, exclusões e documentos. Cada mudança traz os valores que o
  celular via: só os campos mudados são gravados, e se a operação mudou no computador depois daquele backup a
  mudança é recusada com aviso (e não volta a ser perguntada).

## 0.49.0

App do celular para quem não usa o computador:
- "Começar sem computador" na primeira abertura: a pessoa cria a própria senha (mesmas regras do programa) e
  o app abre com os dados vazios, com uma dica de por onde começar.
- Contas, entradas e recebimentos gravados direto no celular, com as mesmas regras e transformações do
  programa; os dados ficam guardados como um backup trancado pela senha, que o programa consegue importar.
- "Fazer cópia de segurança" (Mais) e aviso no Início quando há mudanças sem cópia.
- "Convidar alguém" (Mais): link, mensagem pronta e QR code.

## 0.48.0

- App do celular: a abertura (logo animado e tela de desbloqueio) mostra o nome GESTOR RPV.

## 0.47.0

- App do celular: "+ Nova conta" na aba Contas, com as mesmas regras do programa (campos obrigatórios, CPF,
  estado, e sem repetir apelido, conta bancária ou chave Pix). A conta fica guardada no celular, aparece em
  Contas como "aguarda o computador" e já pode ser escolhida numa entrada nova.
- Programa: as entradas do celular passam a trazer também contas de recebimento; as contas são importadas antes
  das entradas, que as encontram pelo nome.

## 0.46.0

- App do celular: o logo da abertura fica cerca de 2,5 cm acima do centro, fora da área coberta pela janela de
  confirmação do Face ID do iPhone.

## 0.45.0

- App do celular: ao abrir, o logo aparece sozinho e o Face ID só é pedido depois da animação (a janela do
  iPhone cobria a abertura). O logo fica ao fundo enquanto o Face ID é pedido e esmaece já mostrando o Início,
  ou a tela de desbloqueio se o Face ID for cancelado.

## 0.44.0

- App do celular: valores com pontuação automática enquanto se digita (os números entram pelos centavos, como
  no programa); colar "1.500,00" também funciona.
- App do celular: abertura com o logo, que some em cerca de 1,5 s. Com um backup guardado, a primeira tela é
  só de desbloqueio (Face ID, ou senha); escolher outro backup fica em "Trocar por um backup mais novo".
- "O que mudou nas últimas versões": as cinco últimas versões, com a contagem de novidades e correções, no
  Sobre do programa e no app (Mais → Novidades), a partir de uma lista única (novidades.py).

## 0.43.0

Entradas cadastradas no celular:
- App: "+ Nova entrada" em Operações, com as mesmas regras do programa (todos os problemas numa mensagem só) e
  o lucro calculado na hora. A entrada fica guardada no celular, cifrada com a chave do backup, e "Enviar para
  o computador" salva o arquivo na pasta do backup no Google Drive. Em Operações aparece quantas aguardam o
  computador; elas somem sozinhas quando um backup mais novo mostra que já foram importadas.
- Programa: ao abrir, procura as entradas do celular na pasta do backup automático, mostra a lista e pergunta se
  quer importar (também em Arquivo → Entradas do celular…). Cada entrada entra uma vez só, mesmo que o arquivo
  volte pela sincronização; entradas fora das regras (por exemplo, conta desativada) são recusadas com o
  motivo e continuam na pasta para nova tentativa.

## 0.42.0

- Backup ao fechar o programa: com o backup automático ativo, fechar o Gestor (X da janela ou Sair) grava
  uma cópia na pasta escolhida se algo mudou desde o último backup (operações, contas, recebimentos,
  previsões, lixeira ou anexos; preferências como o tema não contam). Com a pasta no Google Drive, o app do
  celular encontra sempre o backup do último uso. Se a cópia falhar, o programa pergunta antes de fechar.
  O backup semanal continua.
- Testes do app do celular também no GitHub, a cada envio, no Chromium e no WebKit (o motor do Safari).
- App do celular: em "Sobre este backup", a versão do programa que gerou o backup passa a se chamar "Feito no
  computador pela versão", e a versão do app aparece separada.

## 0.41.0

- App do celular: o leitor de PDF passa a usar a versão do pdf.js feita para navegadores como o Safari do
  iPhone (a anterior exigia recursos que nem todo iPhone tem). Se um PDF ainda assim não puder ser mostrado,
  a mensagem traz o detalhe técnico, e "Compartilhar ou salvar" continua abrindo o arquivo em outro app.
- A versão do app aparece na tela de abertura e em Mais, para conferir se o aparelho já carregou a última.

## 0.40.0

- App do celular: PDFs abrem com a página inteira na largura da tela (antes apareciam em tamanho real,
  parecendo ampliados), com botões de zoom (−, +, Ajustar) e indicação "Página 1 de N". Os PDFs são
  desenhados pelo próprio app (pdf.js), só as páginas perto da parte visível, para não esgotar a memória.
  Imagens ganharam os mesmos botões de zoom.

## 0.39.0

App do celular:
- Guarda o último backup no aparelho (como saiu do computador, trancado pela senha): não é mais preciso
  escolher o arquivo a cada abertura. "Trocar por um backup mais novo" substitui o guardado.
- Abrir com Face ID (iOS 18 ou mais novo): depois de ativado, o app pede o rosto ao abrir e mostra os dados
  na hora, sem digitar a senha e sem os segundos de conferência dela. Ativar e desativar em Mais.
- Tranca sozinho depois de 5 minutos em segundo plano; "Trancar agora" em Mais.
- Dados bancários recolhidos no detalhe da operação e em Contas: aparece só o nome do titular; CPF,
  endereço, banco e Pix só depois de um toque.
- Gráfico mensal com grade e escala; tocar num mês mostra entradas, valor investido, recebido e lucro
  realizado dele; a lista mostra só os meses com movimento.

## 0.38.0

- App do celular abre os anexos: no detalhe da operação, cada documento e comprovante abre na tela (PDF ou
  imagem) e pode ser compartilhado ou salvo pelo menu do iPhone. O anexo só é extraído do backup quando é
  aberto, conferido pelo hash do backup, e sai da memória ao deixar a tela.
- Ícone do app declarado também com tamanho e na forma antiga que o iPhone procura, para não cair no ícone
  genérico ao adicionar à Tela de Início.

## 0.37.0

- App do celular instalável: no Safari do iPhone, Compartilhar → Adicionar à Tela de Início cria o ícone
  "Gestor RPV", que abre em tela cheia. O código do app fica guardado no aparelho e abre também sem
  internet; os dados continuam só na memória enquanto o app está aberto. Cada publicação atualiza o app na
  próxima abertura com internet.

## 0.36.0

- App do celular, primeiras telas (só consulta): Início com indicadores e situação das operações, Operações em
  cartões com busca e filtros, detalhe completo de cada operação, Contas de recebimento, Lixeira, Gráfico
  mensal e dados do backup aberto, nos temas claro e escuro do iPhone. As contas são as mesmas do programa no
  computador, conferidas por testes que comparam os dois. O programa no computador não muda.

## 0.35.1

- O executável gerado passa a ser testado criando e abrindo um backup com senha antes de ser entregue; se a
  biblioteca de criptografia não carregar no computador da pessoa, o diário (`gestor.log`) anota qual módulo
  faltou e se foi uma DLL do Windows.

## 0.35.0

- Início do app do celular (pasta `celular/`): prova técnica que abre no próprio aparelho um backup do
  programa, com a senha dos backups, e mostra quantos registros ele tem e quanto tempo levou. Nada é enviado
  para a internet. Publicação automática no GitHub Pages. O programa no computador não muda.

## 0.34.1

- Se o Windows segurar a pasta dos anexos antigos logo depois de uma importação que deu certo, a tela não
  mostra mais "Não foi possível importar"; a próxima abertura termina a arrumação.
- Abrir o programa uma segunda vez não pisca uma janela vazia antes do aviso.
- Teste da trava de execução única solta o arquivo no fim (no Windows, a pasta temporária não saía).

## 0.34.0

Correções do segundo veredito do chefe da banca, sobre a 0.33.0.

- Uma importação que terminou nunca é desfeita na abertura seguinte. A conclusão agora fica marcada na
  própria pasta de trabalho, logo depois da troca do banco; antes, se essa pasta sobrasse (antivírus
  segurando um arquivo), a segunda abertura trocava os anexos importados pelos antigos.
- O programa só abre uma vez: abrir de novo enquanto ele está aberto (por exemplo, com a janela parada
  durante uma importação) mostra um aviso, em vez de uma segunda execução mexer nos mesmos dados.
- Falha só ao apagar a pasta temporária, depois de uma importação, exclusão ou backup que deu certo, não
  aparece mais como erro: a sobra é limpa numa próxima abertura.
- Restauração interrompida à força na tela de recuperação: a abertura seguinte oferece restaurar de novo,
  em vez de abrir o programa vazio.
- O aviso de backup mostra quantos anexos sumiram da pasta de documentos (o backup automático também os
  deixa de fora).

## 0.33.0

Correções do veredito do chefe da banca sobre a 0.32.0.

**Backup e anexos**
- Anexo que sumiu da pasta de documentos (apagado por fora, antivírus, sincronização) não estraga mais os
  backups: antes, todo backup seguinte saía impossível de restaurar ("Um documento vinculado está ausente").
  Agora o anexo fica de fora com aviso, e backups antigos nessa situação são importados sem ele.
- Restauração interrompida à força (queda de energia) no meio da troca: a abertura seguinte devolve os anexos
  que combinam com o banco, em vez de deixá-los numa pasta temporária que seria apagada em 24 horas.
- Exclusão de anexo interrompida antes de chegar ao banco: o arquivo volta para a pasta de documentos.
- Na tela de recuperação, qualquer erro ao abrir o backup escolhido (por exemplo, um ZIP em formato que o
  programa não lê) oferece escolher outro arquivo, em vez de fechar o programa sem mensagem.

**Valores, senha e demonstração**
- Separador de milhar fora do lugar ("1,23.45", "12.34,56") é recusado, em vez de virar outro valor.
- Senhas em sequência ou repetidas ("abcdefghij", "aaaaaaaaab12") são recusadas.
- Carga da demonstração interrompida entre gravar e anotar um registro não deixa conta ou operação fictícia
  órfã.
- Formulário com prazo em dias e data de aquisição inválida mostra o erro da data uma vez só.

## 0.32.0

Correções da terceira rodada da banca de revisão. Quatro itens da 0.31.0 não estavam completos e foram
terminados aqui: a senha antiga agora é protegida de fato, o formulário mostra formato e regras numa
mensagem só, a carga da demonstração resiste a encerramento forçado e a busca não atravessa palavras.

**Dados e valores**
- Colar "1,500.00" (formato americano) dá R$ 1.500,00; antes virava R$ 1,50 sem aviso. Valores com o espaço
  que Excel e navegadores usam ("R$ 1.500,00" copiado de uma página) também são aceitos.
- Importar um backup é uma troca única: a senha e a pasta do backup automático deste computador já entram no
  banco novo antes da troca, então uma falha não deixa banco e anexos de épocas diferentes.
- Recuperação de banco danificado: anexos presos (arquivo aberto) devolvem o banco ao lugar; um erro só ao
  guardar a senha não desfaz uma restauração que deu certo; escolher o próprio arquivo danificado é
  explicado; a mensagem final diz os nomes reais do que foi guardado e avisa se a senha precisa ser recriada.
- Demonstração: a carga é anotada passo a passo e, se o programa for fechado à força no meio, é limpa e
  refeita na próxima abertura; operação fictícia que recebeu um comprovante de verdade passa a ser da pessoa;
  ao apagar, o programa avisa quantas operações suas usam contas fictícias; anotação adulterada não trava.
- Cópias de segurança internas não contam como "último backup", e uma data de último backup muito no futuro
  (relógio adiantado ou arquivo adulterado) não cala mais o lembrete nem o backup automático.

**Senha e privacidade**
- A senha gravada pela 0.30.0 passa a ser protegida (DPAPI) na primeira leitura, e o banco apaga de verdade
  o que é removido (sem sobras legíveis no arquivo).
- Senha com no mínimo 10 caracteres, recusando bases óbvias com números ou símbolos ("senha@123",
  "password1", "brasil2026"); a senha atual é comparada sem diferença de acentuação.
- O diário de erros grava só o tipo, o código e as linhas do programa, sem mensagens nem caminhos.
- Cópias interrompidas (".…parcial") deixadas na pasta escolhida são limpas no backup seguinte; os anexos
  extraídos não podem passar do tamanho conferido.

**Uso**
- O formulário de entrada mostra numa mensagem só os campos mal escritos e as regras não atendidas; o de conta
  lista todos os campos que faltam, o estado e o CPF de uma vez.
- Importar pede para fechar qualquer formulário aberto (entrada, recebimento, previsão ou conta); senha vazia
  na importação diz que nada foi digitado; cancelar a senha ao ativar o backup automático explica o motivo.
- Busca: com mais de uma palavra, procura a partir do começo das palavras ("silva jo" acha "Silva José",
  "lva j" não); hífen separa palavras ("maria jose" acha "Maria-José"); apóstrofo não ("davila").
- A confirmação de descartar no formulário de conta não fala mais em anexos; clique do meio (Linux) também
  passa pela conferência de valores.

**Manutenção**
- A etapa de migração 0.16.0 usa a mesma condição para guardar a cópia e para migrar; a chamada DPAPI declara
  os tipos; testes novos para cada correção (168 no total).

## 0.31.0

Correções da segunda rodada da banca de revisão.

**Dados que não se perdem**
- Restaurar um backup com o banco danificado guarda também os anexos que estavam com ele
  (`documentos-danificado-…`); antes eles eram apagados. Arquivo de dados vazio também é tratado como
  danificado. Senha errada na recuperação pede a senha de novo, sem voltar à escolha do arquivo.
- "Apagar dados de demonstração" preserva qualquer registro que a pessoa tenha salvo pelo formulário, e uma
  carga de demonstração interrompida não deixa dados fictícios para trás.
- Fechar o formulário de conta com alterações pergunta antes de descartar; importar com um formulário
  aberto pede para fechá-lo antes.
- Colar um valor troca o valor inteiro do campo (antes juntava os dígitos e criava outro valor).

**Segurança**
- O backup é montado na pasta dos dados: na pasta escolhida só chega o arquivo final, cifrado.
- Na importação, os anexos só são gravados depois da confirmação (só o hash deles é conferido antes).
- Senha dos backups protegida pelo Windows (DPAPI) no banco local, com no mínimo 8 caracteres, sem espaços
  nas pontas e sem senhas óbvias; trocar a senha pede a atual. Acentos digitados de jeitos diferentes
  abrem o mesmo backup.
- Quem usa senha é avisado antes de importar um backup sem senha.
- O diário de erros não guarda o texto das mensagens (que pode ter o que foi digitado).

**Uso**
- O formulário lista de uma vez todas as regras não atendidas; colar valor acima do máximo diz o limite.
- Senha errada na importação avisa sempre que errou; cancelar a criação da senha avisa que o backup não
  foi feito; o rodapé avisa quando o backup automático está parado por falta de senha; a janela de backup
  automático continua em primeiro plano depois de definir a senha.
- Recebimento, previsão, lixeira, formulário, Sobre e calculadora abrem uma janela só.
- Chaves Pix: CNPJ com e sem pontuação é a mesma chave; CPF e celular com os mesmos dígitos, não.
- Busca respeita os espaços entre as palavras.

**Manutenção**
- Validação do backup em etapas curtas; esquema único conferido por teste; testes de interface divididos
  em quatro arquivos por assunto, com a base em `apoio_interface.py` e os dados de exemplo em
  `apoio_testes.py`; estilo padronizado e conferido no CI (pycodestyle).

## 0.30.0

Correções apontadas pela banca de revisão (segurança, uso, manutenção e testes).

**Segurança dos dados**
- Importar backup recusa triggers, views e estruturas que o aplicativo não cria e recria o banco
  copiando só os dados: um backup forjado não consegue mais trocar a chave Pix das contas salvas depois.
  Ao abrir, o banco local também descarta triggers e views.
- Backups protegidos por senha (AES-256-GCM, chave por scrypt). A senha é criada no primeiro backup e
  fica só neste computador; backups antigos sem senha continuam importáveis.
- Backup só leva e só aceita anexos cadastrados, com nome e extensão gerados pelo programa.
- Importação recusa compactação suspeita, confere o espaço livre, extrai na pasta dos dados e limpa
  sobras de importações interrompidas.

**Dados que não se perdem**
- "Apagar dados de demonstração" não remove mais cadastros reais que reaproveitaram o número de um
  registro fictício, e apaga também os anexos fictícios.
- Banco danificado não fecha o programa calado: aparece a explicação e a opção de restaurar um backup;
  o arquivo com problema é guardado. Banco de versão mais nova não é aberto nem rebaixado.
- Fechar formulário, recebimento ou previsão com alterações pergunta antes de descartar.
- Ctrl+N repetido abre um formulário só (antes duplicava a entrada); a lixeira abre uma vez e acompanha
  as exclusões.

**Validações**
- Valores aceitam só dígitos 0-9 e um separador decimal ("1e3", "1_000" e dígitos de outros alfabetos
  são recusados; colar um valor inválido explica o motivo).
- Datas entre 1900 e 2100; aquisição no futuro, previsão antes da aquisição e comissão acima do total
  são recusadas também na gravação. Nome com até 150 caracteres e observações com até 5000.
- O formulário lista todos os problemas de uma vez, dizendo o campo de cada um, e falhas do sistema
  aparecem em português, sem códigos técnicos.
- Chave Pix de telefone com e sem +55 é a mesma; remover conta em uso avisa quantas operações a usam.

**Outros**
- Excel: situação Atrasada como na tela, sem caracteres que invalidam o arquivo e com células dentro do
  limite do Excel; "relatorio.csv" vira "relatorio.xlsx".
- Busca ignora acentos e pontuação e procura também na conta; ordenação por nome respeita os espaços.
- Calculadora usa o resultado exato (1 ÷ 3 × 3 = 1), repete o número em "5 + =" e não mostra "-0" nem
  notação científica.
- Manutenção: migrações em etapas nomeadas com esquema único, código repetido removido, funções grandes
  divididas, código morto retirado, diário de erros em `gestor.log`, actions fixadas por SHA com
  Dependabot, testes no CI a cada push com pyflakes, e 33 testes novos.

## 0.29.2

- Tela inicial: título afastado 8 px do emblema; no Windows, a imagem do emblema encostava no texto.

## 0.29.1

- Operações recebidas com a linha inteira em verde (antes azul), nos dois temas. Contraste WCAG AA:
  4,7:1 no claro e 8,4:1 no escuro.
- Página do gráfico mensal centralizada na janela.

## 0.29.0

- Minhas operações: no tema claro, os títulos das colunas ficam em negrito.
- Operações recebidas com a linha inteira em azul (fundo e texto), nos dois temas, o oposto do vermelho
  das atrasadas. Contraste WCAG AA: 5,5:1 no claro e 7,7:1 no escuro.
- Gráfico mensal refeito: quantidade de entradas (pela data de aquisição) e de recebidas (pela data do
  recebimento) por mês, em vez de valores. Barras em 3D mais grossas, com face, topo e lateral
  sombreados, número no topo de cada barra e grade em perspectiva. Recebidas em verde; entradas em tom
  neutro. Área do gráfico limitada a 1000 px de largura.
- Janela Sobre com o contato vitoran312@gmail.com para sugestões ou dúvidas; clicar abre o e-mail.

## 0.28.1

- Tela inicial com tamanho máximo de 1420 × 900 (na escala de 100%), centralizada: em telas grandes os
  cartões não esticam mais, mantendo as proporções da referência, e o fundo sobra ao redor.
- Placas de vidro e luzes de fundo ficam paradas depois da animação de entrada (cerca de 4 s); o laço
  de animação termina sozinho, sem uso de CPU depois disso.

## 0.28.0

- Tela inicial reorganizada para ocupar a tela cheia sem espaços vazios: cabeçalho com o emblema à
  esquerda do título, cartão Uma nova operação grande à esquerda (cerca de 56% da largura), os cartões
  Tudo sob controle e Contas de recebimento empilhados à direita e o aviso de atrasadas ou de backup
  logo abaixo deles. Em janelas estreitas, os cartões passam para baixo do cartão principal.
- Entrada das placas de vidro mais longa, cerca de 4 segundos. Depois dela, as placas continuam
  flutuando devagar, poucos pixels, sem parar.
- Luzes de fundo translúcidas em pêssego e carmim que derivam lentamente atrás de toda a tela inicial,
  nas cores de cada tema. Trocar de tema só troca as cores: o movimento continua de onde estava.
- A animação pausa fora da tela inicial e com a janela minimizada. Uso de CPU medido (um núcleo):
  ~19% durante a entrada, ~9% parado na tela inicial, ~1% nas outras páginas.
- Textos, botões, navegação, banco de dados e regras de negócio permanecem inalterados.

## 0.27.0

- Arte de placas de vidro translúcidas atrás do conteúdo do cartão Uma nova operação, com animação de
  abertura única: as placas surgem em sequência, deslizam até a posição final e as bordas acendem em
  pêssego (carmim no tema claro). Dura cerca de 2,5 segundos e termina parada.
- Transparência por composição de imagens PNG no Canvas, sem transparência de janela; cada quadro custa
  cerca de 2 ms. Textos, botões, navegação e dados permanecem inalterados.

## 0.26.0

- Janela de nova entrada e edição de registro cerca de 30% maior: fontes de 10 para 13 pontos, campos,
  setas, espaçamentos e botões na mesma proporção. Em telas baixas, os campos rolam e os botões
  continuam fixos no rodapé.

## 0.25.1

- Troca entre modo claro e escuro cerca de 3 vezes mais rápida no Windows: cartões, botões e filtros
  passam a usar imagens do tamanho real, em vez de centenas de pedaços pequenos repetidos. Medido no
  Windows do GitHub: início de ~200 para ~60 ms, Minhas operações de ~145 para ~88 ms, Contas de ~160
  para ~58 ms; abertura de 1,9 para 1,3 s. A aparência é idêntica (comparação pixel a pixel).
- Fluxo manual “Medir troca de tema” no GitHub Actions para medir a troca no Windows.

## 0.25.0

- Fontes nítidas no Windows com escala de tela acima de 100%: o programa declara suporte a DPI e deixa
  de ser ampliado como imagem, o que borrava e serrilhava as letras.
- Janelas, colunas, linhas das tabelas, cartão de contas e quebras de texto acompanham a escala da tela.

## 0.24.1

- Contas de recebimento voltam ao layout simples (botões, lista e aviso), agora dentro de um cartão
  centralizado com cerca de metade do tamanho da área livre. O painel de detalhes da 0.24.0 foi retirado.

## 0.24.0

- Contas de recebimento em lista e detalhes: a conta selecionada mostra dados bancários, situação,
  ações e as operações que a usam, com atrasadas primeiro e totais a receber e já recebidos.
- Resumo de contas no topo da página e seleção automática da primeira conta.
- Troca entre modo claro e escuro mais rápida: o outro tema é preparado em segundo plano após a abertura
  e a preferência é gravada depois do redesenho.

## 0.23.0

- Uma única janela: Minhas operações, Contas de recebimento e Gráfico mensal abrem como páginas dentro
  da janela principal, com o botão ← Voltar (ou Alt+←) para a página anterior. A janela abre maximizada.
- A barra de menus aparece apenas na página Minhas operações, onde suas ações se aplicam.
- Operações atrasadas com a linha inteira em vermelho: fundo e texto, inclusive Previsão atual e Recebido.
- Conferência automática das atrasadas pela data do computador ao abrir, ao voltar às páginas e na virada
  do dia com o programa aberto.
- Aviso na tela inicial com a quantidade de operações atrasadas; o clique abre a lista já filtrada.

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
