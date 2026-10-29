"""Estilos ttk dos temas claro e escuro, criados uma única vez por modo."""
from tkinter import font as tkfont

from tema import cores
from visual import aplicar_superficies, familia_titulo, misturar, px


def criar_estilos(janela, estilo, fonte):
    c = cores()
    fundo, campo, texto = c['fundo'], c['campo'], c['texto']
    primario_texto = c['primario_texto']
    # Títulos em serifa (Georgia no Windows): o tom editorial da identidade Ledger. Valores e interface em sem serifa.
    serifa = familia_titulo(janela)
    estilo.configure('.', font=(fonte, 10), background=fundo, foreground=texto,
                     bordercolor=c['borda'], lightcolor=campo, darkcolor=campo, troughcolor=fundo,
                     focuscolor=c['marca'], selectbackground=c['selecao'], selectforeground=c['texto_selecao'])
    aplicar_superficies(janela)

    # Botões planos: secundário com contorno fino, principal preenchido com a cor da marca.
    estilo.configure('TButton', padding=(16, 9), background=fundo, foreground=texto, anchor='center')
    estilo.map('TButton', background=[('disabled', fundo), ('!disabled', fundo)], foreground=[('disabled', c['desabilitado']), ('!disabled', texto)])
    for nome in ('Inicio.TButton', 'Inicio.Principal.TButton'):
        estilo.configure(nome, background=c['superficie'], padding=(16, 9))
        estilo.map(nome, background=[('disabled', c['superficie']), ('!disabled', c['superficie'])])
    for nome in ('Salvar.TButton', 'Principal.TButton', 'DiaSelecionado.TButton', 'Resultado.Calculadora.TButton'):
        estilo.configure(nome, font=(fonte, 10, 'bold'), padding=(16, 8), foreground=primario_texto)
        estilo.map(nome, foreground=[('disabled', c['desabilitado']), ('!disabled', primario_texto)])
    estilo.configure('Inicio.Principal.TButton', font=(fonte, 10, 'bold'))
    estilo.configure('Menu.TButton', font=(fonte, 16, 'bold'), padding=(22, 16))
    estilo.configure('Restaurar.TButton', font=(fonte, 10, 'bold'), padding=(16, 8))
    estilo.configure('Calculadora.TButton', font=(fonte, 15), padding=(8, 10))
    estilo.configure('Resultado.Calculadora.TButton', font=(fonte, 15, 'bold'), padding=(8, 10))
    estilo.configure('DiaSelecionado.TButton', font=(fonte, 10, 'bold'))

    for tipo in ('TRadiobutton', 'TCheckbutton'):
        estilo.configure(tipo, background=fundo, foreground=texto, indicatorbackground=campo, indicatorforeground=texto,
                         indicatormargin=(0, 0, 8, 0), padding=3, upperbordercolor=c['borda'], lowerbordercolor=c['borda'])
        estilo.map(tipo, background=[('disabled', fundo), ('active', c['ativo']), ('!disabled', fundo)],
                   foreground=[('disabled', c['desabilitado']), ('!disabled', texto)],
                   indicatorbackground=[('disabled', fundo), ('selected', c['primario']), ('!disabled', campo)],
                   indicatorforeground=[('disabled', c['desabilitado']), ('selected', primario_texto), ('!disabled', texto)])

    # Filtros em pílulas: o selecionado ganha o tom suave e o contorno da marca.
    for nome, cor in (('Filtro.TRadiobutton', texto), ('FiltroAlerta.TRadiobutton', c['vermelho'])):
        estilo.configure(nome, padding=(14, 6), background=fundo, foreground=cor, anchor='center')
        estilo.map(nome, background=[('!disabled', fundo)], foreground=[('selected', c['marca'] if cor == texto else cor), ('!disabled', cor)],
                   font=[('selected', (fonte, 10, 'bold')), ('!selected', (fonte, 10))])

    # Aviso de dados de demonstração: faixa suave da cor da marca.
    estilo.configure('Demonstracao.TFrame', background=c['realce'])
    estilo.configure('Demonstracao.TLabel', background=c['realce'], foreground=texto)
    estilo.configure('Demonstracao.TButton', background=c['realce'], padding=(14, 6))
    estilo.map('Demonstracao.TButton', background=[('disabled', c['realce']), ('!disabled', c['realce'])])

    # Janela de nova entrada/edição, cerca de 30% maior (veja tela_registro.ampliar_formulario).
    estilo.configure('Form.TLabel', font=(fonte, 13))
    estilo.configure('FormTitulo.TLabel', font=(serifa, 27, 'bold'), foreground=texto, background=fundo)
    estilo.configure('FormDataCalculada.TLabel', background=fundo, font=(fonte, 13, 'bold'))
    estilo.map('FormDataCalculada.TLabel', background=[('disabled', fundo), ('!disabled', fundo)], foreground=[('disabled', c['desabilitado']), ('!disabled', texto)])
    estilo.configure('FormDinheiro.TLabel', background=campo, foreground=c['secundario'], font=(fonte, 13))
    estilo.configure('Form.TButton', font=(fonte, 13), padding=(21, 10))
    estilo.configure('Form.Salvar.TButton', font=(fonte, 13, 'bold'), padding=(21, 10))
    estilo.configure('Form.TRadiobutton', font=(fonte, 13))
    for tipo in ('TEntry', 'TCombobox'):
        estilo.configure('Form.' + tipo, padding=(13, 9), arrowsize=17)

    # Tela inicial: cartão em destaque, avisos em cartões e botão principal ampliado.
    # Cartão de destaque da tela inicial: nanquim (herói) com título em marfim e o botão champanhe.
    estilo.configure('Heroi.TFrame', background=c['heroi'])
    estilo.configure('DestaqueTitulo.TLabel', background=c['heroi'], foreground=c['heroi_texto'], font=(serifa, 26, 'bold'))
    estilo.configure('DestaqueTexto.TLabel', background=c['heroi'], foreground=c['heroi_secundario'], font=(fonte, 13))
    estilo.configure('Destaque.Principal.TButton', background=c['heroi'], foreground=c['acento_texto'], font=(fonte, 13, 'bold'),
                     padding=(20, 13))
    estilo.map('Destaque.Principal.TButton', background=[('disabled', c['heroi']), ('!disabled', c['heroi'])],
               foreground=[('disabled', c['desabilitado']), ('!disabled', c['acento_texto'])])

    # Barra lateral: itens em marfim apagado que acendem sob o mouse; o ativo fica claro e em negrito.
    estilo.configure('Lateral.TFrame', background=c['heroi'])
    estilo.configure('LateralMarca.TLabel', background=c['heroi'], foreground=c['heroi_texto'], font=(serifa, 15, 'bold'))
    estilo.configure('LateralEmpresa.TLabel', background=c['heroi'], foreground=c['heroi_secundario'], font=(fonte, 9))
    estilo.configure('LateralSecao.TLabel', background=c['heroi'], foreground=misturar(c['heroi_secundario'], c['heroi'], 0.25),
                     font=(fonte, 8, 'bold'))
    estilo.configure('Lateral.TButton', background=c['heroi'], foreground=c['heroi_secundario'], font=(fonte, 10),
                     anchor='w', padding=(14, 10))
    estilo.map('Lateral.TButton', background=[('!disabled', c['heroi'])],
               foreground=[('selected', c['heroi_texto']), ('active', c['heroi_texto']), ('!disabled', c['heroi_secundario'])],
               font=[('selected', (fonte, 10, 'bold')), ('!selected', (fonte, 10))])
    estilo.configure('Acento.TButton', background=c['heroi'], foreground=c['acento_texto'], font=(fonte, 10, 'bold'),
                     anchor='center', padding=(14, 10))
    estilo.map('Acento.TButton', background=[('!disabled', c['heroi'])],
               foreground=[('disabled', c['desabilitado']), ('!disabled', c['acento_texto'])])
    estilo.configure('LateralIndicador.TFrame', background=c['acento'])
    estilo.configure('InicioAtrasadas.TLabel', background=c['superficie'], foreground=c['vermelho'], font=(fonte, 11, 'bold'))
    estilo.configure('InicioBackup.TLabel', background=c['superficie'], foreground=c['vermelho'], font=(fonte, 10))

    # Tipografia: títulos neutros e firmes; a cor da marca fica reservada às ações.
    for nome, tamanho, peso, cor in (
        ('InicioTitulo.TLabel', 34, 'bold', texto),
        ('Titulo.TLabel', 24, 'bold', texto), ('Subtitulo.TLabel', 11, 'normal', c['secundario']),
        ('Discreto.TLabel', 9, 'normal', c['secundario'])):
        estilo.configure(nome, font=(fonte, tamanho, peso), foreground=cor, background=fundo)
    estilo.configure('InicioTitulo.TLabel', font=(serifa, 34, 'bold'))
    estilo.configure('Titulo.TLabel', font=(serifa, 24, 'bold'))
    estilo.configure('Superficie.TFrame', background=c['superficie'])
    for nome, tamanho, peso, cor in (
        ('CartaoTitulo.TLabel', 16, 'bold', texto), ('CartaoTexto.TLabel', 10, 'normal', c['secundario']),
        ('ResumoTitulo.TLabel', 10, 'normal', c['secundario']),
        ('ResumoValor.TLabel', 22, 'bold', texto), ('ResumoRealizado.TLabel', 22, 'bold', c['verde'])):
        estilo.configure(nome, background=c['superficie'], font=(fonte, tamanho, peso), foreground=cor)
    estilo.configure('DataCalculada.TLabel', background=fundo, font=(fonte, 10, 'bold'))
    estilo.map('DataCalculada.TLabel', background=[('disabled', fundo), ('!disabled', fundo)], foreground=[('disabled', c['desabilitado']), ('!disabled', texto)])
    estilo.configure('AtrasadasAviso.TLabel', background=fundo, foreground=c['vermelho'], font=(fonte, 10, 'bold'))
    estilo.configure('Voltar.TButton', padding=(12, 5), font=(fonte, 10))
    estilo.configure('BackupAviso.TLabel', background=fundo, foreground=c['vermelho'], font=(fonte, 9))
    estilo.configure('Contato.TLabel', foreground=c['marca'], font=(fonte, 11, 'underline'))
    estilo.configure('LegendaInvestido.TLabel', foreground=c['secundario'], font=(fonte, 12))
    estilo.configure('LegendaRecebido.TLabel', foreground=c['verde'], font=(fonte, 12))
    estilo.configure('Recebido.TLabel', foreground=c['verde'], font=(fonte, 10, 'bold'))
    estilo.configure('Ajuda.TLabel', font=(fonte, 10), background=campo, foreground=texto, padding=12, wraplength=px(janela, 320),
                     relief='solid', borderwidth=1, bordercolor=c['borda_suave'])
    estilo.configure('TSeparator', background=c['borda_suave'])

    # Campos: contorno fino em repouso e anel de 2 px na cor da marca quando em foco.
    for tipo in ('TEntry', 'TCombobox'):
        estilo.configure(tipo, fieldbackground=campo, foreground=texto, insertcolor=texto, padding=(10, 7), borderwidth=1,
                         relief='flat', arrowsize=13, arrowcolor=c['secundario'], background=campo,
                         bordercolor=c['borda'], lightcolor=campo, darkcolor=campo)
        estilo.map(tipo, fieldbackground=[('disabled', fundo), ('readonly', campo)],
                   foreground=[('disabled', c['desabilitado']), ('readonly', texto)],
                   bordercolor=[('focus', c['marca']), ('!focus', c['borda'])],
                   lightcolor=[('focus', c['marca']), ('!focus', campo)],
                   background=[('active', campo), ('!disabled', campo)],
                   arrowcolor=[('disabled', c['desabilitado']), ('!disabled', c['secundario'])],
                   selectbackground=[('!disabled', c['selecao'])], selectforeground=[('!disabled', c['texto_selecao'])])
    estilo.configure('Dinheiro.TFrame', background=campo)
    estilo.configure('Dinheiro.TLabel', background=campo, foreground=c['secundario'])

    # Busca: espaço à esquerda para a lupa e à direita para o × (veja componentes.CampoBusca).
    estilo.configure('Busca.TEntry', padding=(px(janela, 36), 8, px(janela, 32), 8), font=(fonte, 11))
    estilo.configure('BuscaIcone.TLabel', background=campo, padding=0)
    estilo.configure('BuscaDica.TLabel', background=campo, foreground=c['desabilitado'], font=(fonte, 11), padding=0)
    # Campo com problema (validação do formulário): contorno vermelho, mais forte com o foco.
    for tipo in ('TEntry', 'TCombobox'):
        for prefixo in ('Erro.', 'Form.Erro.'):
            estilo.map(prefixo + tipo, bordercolor=[('!disabled', c['vermelho'])],
                       lightcolor=[('focus', c['vermelho']), ('!focus', misturar(c['vermelho'], campo, 0.55))])
        estilo.configure('Form.Erro.' + tipo, padding=(13, 9), arrowsize=17)
    # Diálogos de uma operação (recebimento, previsão): título e o nome do titular logo abaixo.
    estilo.configure('DialogoTitulo.TLabel', font=(serifa, 18, 'bold'), foreground=texto, background=fundo)
    estilo.configure('DialogoSubtitulo.TLabel', font=(fonte, 10), foreground=c['secundario'], background=fundo)
    # Estado vazio das tabelas.
    estilo.configure('Vazio.TFrame', background=campo)
    estilo.configure('VazioTitulo.TLabel', background=campo, foreground=texto, font=(serifa, 14, 'bold'))
    estilo.configure('VazioTexto.TLabel', background=campo, foreground=c['secundario'], font=(fonte, 10))

    # Tabelas: linhas limpas, cabeçalho discreto e seleção em tom suave da marca.
    estilo.configure('Treeview', background=campo, fieldbackground=campo, foreground=texto, rowheight=px(janela, 40),
                     borderwidth=1, bordercolor=c['borda_suave'], lightcolor=campo, darkcolor=campo)
    estilo.map('Treeview', background=[('selected', c['selecao'])], foreground=[('selected', c['texto_selecao'])])
    estilo.configure('Treeview.Cell', padding=(14, 0))
    estilo.configure('Treeview.Heading', background=c['cabecalho'], foreground=c['secundario'], font=(fonte, 10, 'bold'),
                     padding=(14, 10), relief='flat', borderwidth=0, bordercolor=c['borda_suave'],
                     lightcolor=c['cabecalho'], darkcolor=c['borda_suave'])
    estilo.map('Treeview.Heading', background=[('active', c['ativo'])], foreground=[('active', texto)])
    estilo.configure('Operacoes.Treeview', font=(fonte, 12), rowheight=max(px(janela, 52), tkfont.Font(font=(fonte, 12)).metrics('linespace') + px(janela, 18)))
    # No claro, o cabeçalho cinza-claro precisa do negrito para se destacar das linhas.
    # Cabeçalho discreto e firme: rótulos de coluna não competem com os valores da linha.
    estilo.configure('Operacoes.Treeview.Heading', font=(fonte, 11, 'bold'), padding=(14, 12))
    estilo.configure('Operacoes.TCheckbutton', font=(fonte, 12), background=campo)
    estilo.map('Operacoes.TCheckbutton', background=[('active', c['ativo']), ('!disabled', campo)])
    estilo.configure('Recebido.TCheckbutton', foreground=c['verde'], font=(fonte, 12, 'bold'), background=campo)
    estilo.map('Recebido.TCheckbutton', foreground=[('!disabled', c['verde'])], background=[('active', c['ativo']), ('!disabled', campo)])
    estilo.configure('Previsao.TLabel', background=campo, font=(fonte, 12), anchor='center')
    estilo.configure('PrevisaoAtrasada.TLabel', background=c['atraso'], foreground=c['vermelho'], font=(fonte, 12, 'bold'), anchor='center')
    estilo.configure('Atrasada.Operacoes.TCheckbutton', background=c['atraso'])
    estilo.map('Atrasada.Operacoes.TCheckbutton', background=[('active', c['atraso']), ('!disabled', c['atraso'])])
    # Recebida: a linha inteira em verde, o inverso do vermelho das atrasadas.
    estilo.configure('PrevisaoRecebida.TLabel', background=c['recebida'], foreground=c['verde'], font=(fonte, 12, 'bold'), anchor='center')
    estilo.configure('Recebida.Recebido.TCheckbutton', foreground=c['verde'], background=c['recebida'])
    estilo.map('Recebida.Recebido.TCheckbutton', foreground=[('!disabled', c['verde'])],
               background=[('active', c['recebida']), ('!disabled', c['recebida'])])
    estilo.configure('PrevisaoAdiada.TLabel', background=campo, foreground=c['vermelho'], font=(fonte, 12), anchor='center')
    estilo.configure('ContaSituacao.TLabel', font=(fonte, 12, 'bold'), background=campo)
    estilo.configure('ContaIncompleta.TLabel', font=(fonte, 12, 'bold'), foreground=c['vermelho'], background=campo)
    estilo.configure('Contas.Treeview', font=(fonte, 12), rowheight=max(px(janela, 44), tkfont.Font(font=(fonte, 12)).metrics('linespace') + px(janela, 16)))
    estilo.configure('Contas.Treeview.Heading', font=(fonte, 11, 'bold'))

    # Barras de rolagem finas, sem setas nem ranhuras.
    for orientacao, lado in (('Vertical', 'ns'), ('Horizontal', 'ew')):
        estilo.layout(f'{orientacao}.TScrollbar', [(f'{orientacao}.Scrollbar.trough', {'sticky': lado, 'children': [
            (f'{orientacao}.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
    estilo.configure('TScrollbar', background=c['borda'], troughcolor=fundo, borderwidth=0, arrowsize=10, gripcount=0,
                     bordercolor=fundo, lightcolor=c['borda'], darkcolor=c['borda'])
    estilo.map('TScrollbar', background=[('active', c['secundario'])],
               lightcolor=[('active', c['secundario'])], darkcolor=[('active', c['secundario'])])
