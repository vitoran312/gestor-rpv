# Gestor de RPV — 0.4.0

Aplicativo pessoal para Windows, em Python com Tkinter e SQLite. Cada computador
mantém seus próprios dados, sem servidor ou sincronização. Não exige pacotes extras.

## Executar e atualizar no Windows

Baixe em **Code → Download ZIP**, extraia **todos os arquivos** e abra `app.py`.
Se precisar ver uma mensagem de erro, abra o Prompt de Comando nessa pasta:

```bat
python app.py
```

Mantenha `app.py`, `dados.py`, `componentes.py`, `contas.py` e `versao.py` juntos.
A tela inicial tem os botões **Nova entrada**, **Ver histórico total**,
**Contas de recebimento** e **Sair**. A versão aparece no canto inferior direito.
As janelas abrem centralizadas; o histórico abre maximizado no Windows.

## Contas de recebimento

- Vitor e Lilian aparecem inicialmente sem dados bancários inventados. Use
  **Ver / Editar** para completar os cadastros.
- **Cadastrar nova conta** permite informar identificação, nome completo, endereço,
  banco, agência (se houver), conta e chave Pix. CPF é opcional; quando informado,
  precisa ser válido e exclusivo entre as contas.
- Identificação, CPF, chave Pix e combinação banco/agência/conta não podem se repetir,
  inclusive entre contas desativadas. Endereços podem ser iguais.
  Use o mesmo nome de banco nos cadastros para uma comparação consistente.
- **Desativar / Reativar** preserva os registros antigos. Contas desativadas não
  aparecem em novas entradas; continuam disponíveis na edição da RPV que já as usa.
- Cada nova operação guarda uma cópia dos dados de recebimento. Alterar uma conta
  não reescreve essa cópia nas operações antigas. O botão **Dados de recebimento**
  do registro permite consultar e copiar os dados preservados.
- A migração só conhece os dados existentes na versão antiga (Vitor ou Lilian).
  Não preenche retroativamente os dados bancários desconhecidos dos registros antigos.

## Cadastro e histórico

- Nomes completos são salvos com iniciais maiúsculas.
- Digite valores normalmente: `10560,50` ou `10560`. Ao sair do campo,
  eles serão formatados como `R$ 10.560,50` ou `R$ 10.560,00`.
  O prefixo R$ é fixo, sem mover o cursor durante a digitação.
- A aquisição deve ser maior que zero e não pode superar o recebimento previsto.
- Comissão é opcional e apenas informativa: não altera o lucro.
- Os valores são guardados em centavos, sem ponto flutuante.
- As datas têm calendários com navegação por mês e ano.
- O histórico permite buscar por nome/data, editar e excluir com confirmação.
- A coluna **Prorrogação** tem uma caixa clicável em cada linha. Clique para
  consultar as datas anteriores e cadastrar uma nova previsão pelo calendário.
  Cada nova data deve ser posterior à previsão atual. A previsão inicial é preservada.
- Cada prorrogação é um registro separado, sem criar colunas adicionais por data.
  A tabela mostra a previsão atual e a quantidade de prorrogações.
- Cabeçalhos e valores da tabela são centralizados.

## Dados e backup

O banco é criado em `%LOCALAPPDATA%\GestorRPV\gestor.sqlite3`, fora da pasta do
código. Atualizar os arquivos do programa preserva esse banco.
Na primeira abertura da versão 0.4.0, um banco da versão antiga é adaptado
automaticamente após criar uma cópia `backup-antes-0.4.0-*.sqlite3` na mesma pasta.
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

PDFs anexados, confirmação de recebimento integral com valor recebido em verde,
e backup/restauração pela interface ainda não estão implementados.
