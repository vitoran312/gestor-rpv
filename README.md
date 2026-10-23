# Gestor de RPV

Aplicativo pessoal para Windows, escrito em Python com Tkinter e SQLite.
Cada computador mantém seus próprios dados, sem servidor ou sincronização.

## Primeira versão

A abertura é um menu escuro de tamanho fixo (até 1480 × 980, adaptado à tela),
sem campos de entrada, com os botões
**Nova entrada**, **Ver histórico total** e **Sair**. O cadastro abre em uma janela
separada. O histórico reúne todos os registros e permite buscar, editar e excluir.
Para editar ou excluir, selecione uma linha e use o botão correspondente.
Excluir pede confirmação pelo nome e data e remove permanentemente somente
o registro selecionado. Os totais da lista são atualizados automaticamente.
As janelas abrem centralizadas e o histórico abre maximizado no Windows.
Os campos de data têm um botão de calendário com navegação por mês e ano.
Os valores têm prefixo R$ fixo e máscara automática em centavos: digitar
`1056050` mostra `R$ 10.560,50`. Também é possível colar `R$ 10.560,50`.
A máscara se aplica à comissão, que continua sem afetar o lucro.

- Cadastro e edição de compras de RPVs, com nome do titular e data de aquisição.
- Valores de aquisição e recebimento previsto; lucro previsto calculado automaticamente.
- Comissão opcional apenas informativa, sem efeito no lucro.
- Conta de destino: Vitor ou Lilian.
- Previsão inicial de recebimento, observações e busca por nome/data de aquisição.
- Valores armazenados em centavos, sem arredondamento de ponto flutuante.

## Executar no Windows

Com Python e Tkinter instalados, baixe o repositório (Code → Download ZIP),
extraia a pasta e abra um Prompt de Comando nela:

```bat
python app.py
```

Mantenha `app.py`, `dados.py` e `componentes.py` na mesma pasta. Não são necessários pacotes externos.
No primeiro uso o aplicativo cria automaticamente o banco em
`%LOCALAPPDATA%\GestorRPV\gestor.sqlite3`, fora da pasta do código.
Feche o aplicativo antes de copiar esse arquivo para fazer um backup manual.
O banco não é criptografado; use dados fictícios enquanto estiver avaliando esta versão.
Não envie bancos ou documentos pessoais para o GitHub.

## Validar

```bat
python -m unittest -v
```

Teste também na interface: cadastrar uma compra de R$ 20.000,00 por R$ 12.000,00,
com comissão de R$ 500,00. O lucro previsto deve continuar em R$ 8.000,00.
Feche e reabra o aplicativo para conferir a persistência. Abra o registro,
altere a conta, salve e teste a busca por nome e data.

## Gerar executável no Windows

Após validar a interface:

```bat
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Gestor de RPV" app.py
```

O executável será criado em `dist`. Atualizar o executável não substitui o banco
salvo na pasta de dados do usuário.

## Próximas etapas

- Cadastro dos dados de Vitor e Lilian: nome completo, endereço, banco, conta e Pix.
- Cópia dos dados de destino usados em cada operação.
- Prorrogações em histórico próprio, sem criar colunas para cada nova data.
- PDFs anexados, recebimento integral e valor recebido destacado em verde.
- Backup e restauração incluindo documentos.

Essas etapas ainda não estão implementadas nesta versão.
