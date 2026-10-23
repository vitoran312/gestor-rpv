"""Estilos ttk dos temas claro e escuro, criados uma única vez por modo."""
from tkinter import font as tkfont

from tema import cores
from visual import aplicar_superficies


def criar_estilos(janela, estilo, fonte):
    c = cores()
    fundo,campo,texto = c['fundo'],c['campo'],c['texto']
    primario_texto = c['primario_texto']
    estilo.configure('.',font=(fonte,10),background=fundo,foreground=texto,
                     bordercolor=c['borda'],lightcolor=campo,darkcolor=campo,troughcolor=fundo,
                     focuscolor=c['floresta'],selectbackground=c['selecao'],selectforeground=c['texto_selecao'])
    aplicar_superficies(janela)

    # Botões planos: secundário com contorno fino, principal preenchido com a cor da marca.
    estilo.configure('TButton',padding=(16,8),background=fundo,foreground=texto,anchor='center')
    estilo.map('TButton',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
    for nome in ('Inicio.TButton','Inicio.Principal.TButton'):
        estilo.configure(nome,background=c['superficie'],padding=(16,9))
        estilo.map(nome,background=[('disabled',c['superficie']),('!disabled',c['superficie'])])
    for nome in ('Salvar.TButton','Principal.TButton','DiaSelecionado.TButton','Resultado.Calculadora.TButton'):
        estilo.configure(nome,font=(fonte,10,'bold'),padding=(16,8),foreground=primario_texto)
        estilo.map(nome,foreground=[('disabled',c['desabilitado']),('!disabled',primario_texto)])
    estilo.configure('Inicio.Principal.TButton',font=(fonte,10,'bold'))
    estilo.configure('Menu.TButton',font=(fonte,16,'bold'),padding=(22,16))
    estilo.configure('Restaurar.TButton',font=(fonte,10,'bold'),padding=(16,8))
    estilo.configure('Calculadora.TButton',font=(fonte,15),padding=(8,10))
    estilo.configure('Resultado.Calculadora.TButton',font=(fonte,15,'bold'),padding=(8,10))
    estilo.configure('DiaSelecionado.TButton',font=(fonte,10,'bold'))

    for tipo in ('TRadiobutton','TCheckbutton'):
        estilo.configure(tipo,background=fundo,foreground=texto,indicatorbackground=campo,indicatorforeground=texto,
                         indicatormargin=(0,0,8,0),padding=3,upperbordercolor=c['borda'],lowerbordercolor=c['borda'])
        estilo.map(tipo,background=[('disabled',fundo),('active',c['ativo']),('!disabled',fundo)],
                   foreground=[('disabled',c['desabilitado']),('!disabled',texto)],
                   indicatorbackground=[('disabled',fundo),('selected',c['primario']),('!disabled',campo)],
                   indicatorforeground=[('disabled',c['desabilitado']),('selected',primario_texto),('!disabled',texto)])

    # Tipografia: títulos neutros e firmes; a cor da marca fica reservada às ações.
    for nome,tamanho,peso,cor in (
        ('InicioTitulo.TLabel',34,'bold',texto),
        ('Titulo.TLabel',22,'bold',texto),('Subtitulo.TLabel',11,'normal',c['secundario']),
        ('Discreto.TLabel',9,'normal',c['secundario'])):
        estilo.configure(nome,font=(fonte,tamanho,peso),foreground=cor,background=fundo)
    estilo.configure('Superficie.TFrame',background=c['superficie'])
    for nome,tamanho,peso,cor in (
        ('CartaoTitulo.TLabel',15,'bold',texto),('CartaoTexto.TLabel',10,'normal',c['secundario']),
        ('ResumoTitulo.TLabel',10,'normal',c['secundario']),
        ('ResumoValor.TLabel',20,'bold',texto),('ResumoRealizado.TLabel',20,'bold',c['verde'])):
        estilo.configure(nome,background=c['superficie'],font=(fonte,tamanho,peso),foreground=cor)
    estilo.configure('DataCalculada.TLabel',background=fundo,font=(fonte,10,'bold'))
    estilo.map('DataCalculada.TLabel',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
    estilo.configure('BackupAviso.TLabel',background=fundo,foreground=c['vermelho'],font=(fonte,9))
    estilo.configure('Recebido.TLabel',foreground=c['verde'],font=(fonte,10,'bold'))
    estilo.configure('Ajuda.TLabel',font=(fonte,10),background=campo,foreground=texto,padding=12,wraplength=320,
                     relief='solid',borderwidth=1,bordercolor=c['borda_suave'])
    estilo.configure('TSeparator',background=c['borda_suave'])

    # Campos: contorno fino em repouso e anel de 2 px na cor da marca quando em foco.
    for tipo in ('TEntry','TCombobox'):
        estilo.configure(tipo,fieldbackground=campo,foreground=texto,insertcolor=texto,padding=(10,7),borderwidth=1,
                         relief='flat',arrowsize=13,arrowcolor=c['secundario'],background=campo,
                         bordercolor=c['borda'],lightcolor=campo,darkcolor=campo)
        estilo.map(tipo,fieldbackground=[('disabled',fundo),('readonly',campo)],
                   foreground=[('disabled',c['desabilitado']),('readonly',texto)],
                   bordercolor=[('focus',c['floresta']),('!focus',c['borda'])],
                   lightcolor=[('focus',c['floresta']),('!focus',campo)],
                   background=[('active',campo),('!disabled',campo)],
                   arrowcolor=[('disabled',c['desabilitado']),('!disabled',c['secundario'])],
                   selectbackground=[('!disabled',c['selecao'])],selectforeground=[('!disabled',c['texto_selecao'])])
    estilo.configure('Dinheiro.TFrame',background=campo)
    estilo.configure('Dinheiro.TLabel',background=campo,foreground=c['secundario'])

    # Tabelas: linhas limpas, cabeçalho discreto e seleção em tom suave da marca.
    estilo.configure('Treeview',background=campo,fieldbackground=campo,foreground=texto,rowheight=40,
                     borderwidth=1,bordercolor=c['borda_suave'],lightcolor=campo,darkcolor=campo)
    estilo.map('Treeview',background=[('selected',c['selecao'])],foreground=[('selected',c['texto_selecao'])])
    estilo.configure('Treeview.Cell',padding=(14,0))
    estilo.configure('Treeview.Heading',background=c['sage'],foreground=c['secundario'],font=(fonte,10,'bold'),
                     padding=(14,10),relief='flat',borderwidth=0,bordercolor=c['borda_suave'],
                     lightcolor=c['sage'],darkcolor=c['borda_suave'])
    estilo.map('Treeview.Heading',background=[('active',c['ativo'])],foreground=[('active',texto)])
    estilo.configure('Operacoes.Treeview',font=(fonte,12),rowheight=max(52,tkfont.Font(font=(fonte,12)).metrics('linespace')+18))
    estilo.configure('Operacoes.Treeview.Heading',font=(fonte,18))
    estilo.configure('Operacoes.TCheckbutton',font=(fonte,12),background=campo)
    estilo.map('Operacoes.TCheckbutton',background=[('active',c['ativo']),('!disabled',campo)])
    estilo.configure('Recebido.TCheckbutton',foreground=c['verde'],font=(fonte,12,'bold'),background=campo)
    estilo.map('Recebido.TCheckbutton',foreground=[('!disabled',c['verde'])],background=[('active',c['ativo']),('!disabled',campo)])
    estilo.configure('Previsao.TLabel',background=campo,font=(fonte,12),anchor='center')
    estilo.configure('PrevisaoAdiada.TLabel',background=campo,foreground=c['vermelho'],font=(fonte,12),anchor='center')
    estilo.configure('ContaSituacao.TLabel',font=(fonte,12,'bold'),background=campo)
    estilo.configure('ContaIncompleta.TLabel',font=(fonte,12,'bold'),foreground=c['vermelho'],background=campo)
    estilo.configure('Contas.Treeview',font=(fonte,12),rowheight=44)
    estilo.configure('Contas.Treeview.Heading',font=(fonte,11,'bold'))

    # Barras de rolagem finas, sem setas nem ranhuras.
    for orientacao,lado in (('Vertical','ns'),('Horizontal','ew')):
        estilo.layout(f'{orientacao}.TScrollbar',[(f'{orientacao}.Scrollbar.trough',{'sticky':lado,'children':[
            (f'{orientacao}.Scrollbar.thumb',{'expand':'1','sticky':'nswe'})]})])
    estilo.configure('TScrollbar',background=c['borda'],troughcolor=fundo,borderwidth=0,arrowsize=10,gripcount=0,
                     bordercolor=fundo,lightcolor=c['borda'],darkcolor=c['borda'])
    estilo.map('TScrollbar',background=[('active',c['secundario'])],
               lightcolor=[('active',c['secundario'])],darkcolor=[('active',c['secundario'])])
