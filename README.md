# Gestor de RPV — 0.8.0

Aplicativo pessoal para Windows, em Python com Tkinter e SQLite. Cada computador
mantém seus próprios dados, sem servidor ou sincronização. Não exige pacotes extras.

## Executar e atualizar no Windows

Baixe em **Code → Download ZIP**, extraia **todos os arquivos** e abra `app.py`.
Se precisar ver uma mensagem de erro, abra o Prompt de Comando nessa pasta:

```bat
python app.py
```

Mantenha `app.py`, `dados.py`, `componentes.py`, `contas.py`, `interacao.py`, `tema.py`, `calculadora.py` e `versao.py` juntos.
A tela inicial tem os botões **Nova entrada**, **Ver histórico total**,
**Contas de recebimento** e **Sair**. A versão aparece no canto inferior direito.
As janelas abrem centralizadas; o histórico abre maximizado no Windows.

## Barra de menus do histórico

- **Arquivo → Nova entrada**: abre o cadastro de uma RPV.
- **Arquivo → Contas de recebimento**: administra os dados bancários.
- **Editar → Editar registro / Excluir registro**: atua sobre a linha selecionada.
- **Exibir → Tema claro / Tema escuro**: muda o tema de todas as janelas,
  inclusive formulários, calendários, menus de contexto e calculadora.
  A escolha vale durante a execução; o aplicativo inicia no tema escuro.
- **Calculadora**: abre uma calculadora independente, sem modificar o cadastro.
  Faz soma, subtração, multiplicação, divisão, porcentagem, troca de sinal e
  apagamento. Aceita vírgula, teclado, Enter para calcular e Esc para limpar.
  As operações são sequenciais, como em uma calculadora básica.

Os antigos botões de ações do histórico foram movidos para essa barra.
A busca continua acima da tabela. Os menus de clique direito permanecem disponíveis.

## Contas de recebimento

- Vitor e Lilian aparecem inicialmente sem dados bancários inventados. Use
  **Ver / Editar** para completar os cadastros.
- **Cadastrar nova conta** permite informar identificação, nome completo, endereço,
  número, cidade, estado, banco, agência, conta e chave Pix.
  O estado é selecionado pela sigla em uma lista com as 27 UFs, incluindo DF. CPF é obrigatório, válido e exclusivo entre
  as contas. Cadastros antigos sem CPF aparecem como **⚠ Completar cadastro**,
  em vermelho, e precisam ser completados ao editar.
- Identificação, CPF, chave Pix e combinação banco/agência/conta não podem se repetir,
  inclusive entre contas desativadas. Endereços podem ser iguais.
  Use o mesmo nome de banco nos cadastros para uma comparação consistente.
- **Remover** pede confirmação e exclui definitivamente contas sem RPVs vinculadas.
  Contas já usadas em operações devem ser desativadas para preservar o histórico.
- **Desativar / Reativar** preserva os registros antigos. Contas desativadas não
  aparecem em novas entradas; continuam disponíveis na edição da RPV que já as usa.
- Cada nova operação guarda uma cópia dos dados de recebimento. Alterar uma conta
  não reescreve essa cópia nas operações antigas. O botão **Dados de recebimento**
  do registro permite consultar os dados preservados. Para copiá-los, clique
  com o botão direito sobre os dados e escolha **Copiar**.
- A migração só conhece os dados existentes na versão antiga (Vitor ou Lilian).
  Não preenche retroativamente os dados bancários desconhecidos dos registros antigos.

## Cadastro e histórico

- Nomes completos ganham iniciais maiúsculas enquanto você digita, inclusive
  após espaços. Endereços também ganham iniciais maiúsculas em cada palavra.
  Identificação, banco, busca e observações começam com maiúscula. Chaves Pix e identificadores bancários mantêm sua escrita original.
- Os dois últimos dígitos dos valores são sempre centavos: `5200000` mostra
  `R$ 52.000,00`; `1523659` mostra `R$ 15.236,59`. A máscara é aplicada a cada tecla,
  sem salto do cursor. Também é possível colar um valor já formatado, como
  `R$ 15.236,59`. O prefixo R$ permanece fixo.
- O campo e a coluna **Valor Total RPV** representam o valor integral do crédito.
- A coluna **Data de Aquisição** informa a data da compra.
- A aquisição deve ser maior que zero e não pode superar o Valor Total RPV.
- Comissão é opcional e apenas informativa: não altera o lucro.
- Os valores são guardados em centavos, sem ponto flutuante.
- As datas têm calendários com navegação por mês e ano.
- O histórico permite buscar por nome/data, editar e excluir com confirmação.
- O histórico mostra somente **Previsão inicial** e **Previsão atual**, sem a
  coluna Prorrogação. Clique na data atual ou use o menu de contexto
  **Editar previsão atual** para alterá-la pelo calendário.
- A previsão atual fica vermelha quando posterior à inicial. É possível corrigir
  a data, inclusive antecipá-la; datas anteriores à aquisição não são aceitas.
- As prorrogações cadastradas em versões anteriores permanecem no banco. Sua
  última data é usada até você definir outra previsão atual explicitamente.
- Cabeçalhos e valores da tabela são centralizados.
- A última coluna, **Recebido**, tem uma caixa clicável. Informe a data pelo
  calendário e salve: a confirmação e a data ficam centralizadas, em verde e negrito.
  A data não pode ser anterior à aquisição nem estar no futuro. Ao clicar de novo,
  é possível corrigir a data ou desmarcar o recebimento com confirmação.
  A célula não desenha texto por trás da caixa, inclusive depois de desmarcar.
- A frase explicativa de centavos foi retirada do formulário; a máscara permanece.

## Clique direito

- Campos de texto: **Recortar**, **Copiar**, **Colar** e **Selecionar tudo**.
  Os atalhos de teclado continuam funcionando. Campos somente de leitura
  permitem copiar, mas não alterar o conteúdo.
- Histórico: clique direito em uma linha para **Editar**, **Excluir**,
  **Editar previsão atual**, marcar **Recebido** ou **Copiar**.
- Contas: clique direito em uma linha para **Editar**, **Desativar/Reativar**, **Remover**
  ou **Copiar** os dados completos.
- Não há mais botão “Copiar dados”; a ação está no menu de contexto.

## Dados e backup

O banco é criado em `%LOCALAPPDATA%\GestorRPV\gestor.sqlite3`, fora da pasta do
código. Atualizar os arquivos do programa preserva esse banco.
Na primeira abertura após uma mudança de estrutura, o banco é adaptado
automaticamente após criar uma cópia na mesma pasta: `backup-antes-0.4.0-*.sqlite3`
para bancos antigos, `backup-antes-0.6.0-*.sqlite3` para bancos da versão 0.5.0, ou
`backup-antes-0.7.0-*.sqlite3` para bancos da versão 0.6.0.
A migração mantém os cadastros, as cópias de dados bancários, os recebimentos
e as datas anteriores. Número, cidade e UF ficam vazios nos cadastros antigos
até serem preenchidos; não são inferidos do endereço existente.
Registros antigos são preservados, mesmo se precisarem de correção pelas novas
regras de valores quando forem editados.

Para backup manual, feche o programa e copie o banco para um local seguro.
O banco não é criptografado. Não envie bancos ou documentos pessoais ao GitHub.

## Validação

```bat
python -m unittest -v
```

Os testes gráficos são opcionais e precisam de uma sessão gráfica. No Prompt de Comando do Windows:

```bat
set GESTOR_RPV_TESTE_UI=1
python -m unittest -v
```

Testam digitação rápida e cursor, calendários, limites de aquisição, contas,
prorrogações, preservação de dados de recebimento e migração do banco antigo.
Todos usam bancos temporários, sem tocar no histórico do usuário.

## Executável

Gere no Windows após testar a interface:

```bat
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Gestor de RPV" app.py
```

O executável fica em `dist`.

## Versões

`versao.py` define a versão exibida. Cada entrega deve atualizar esse arquivo e o
`CHANGELOG.md`, passar pelos testes e receber uma tag correspondente no GitHub,
como `v0.4.0`, apontando para o commit da entrega. O número muda quando a pessoa
baixa e executa a nova versão; não há atualização automática pela internet.

## Próximas etapas

PDFs anexados, registro de eventual diferença entre valor previsto e valor recebido,
e backup/restauração pela interface ainda não estão implementados.
A confirmação de recebimento desta versão registra a data, sem alterar os valores.
