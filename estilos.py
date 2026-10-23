"""Estilos ttk dos temas claro e escuro, criados uma única vez por modo."""
from tkinter import font as tkfont

from tema import cores
from visual import aplicar_superficies


def criar_estilos(janela, estilo, fonte):
    c = cores()
    fundo,campo,texto = c['fundo'],c['campo'],c['texto']
    primario_texto = c['primario_texto']
    estilo.configure('.',font=(fonte,10),background=fundo,foreground=texto,
                     bordercolor=c['borda'],lightcolor=campo,darkcolor=fundo,troughcolor=fundo)
    aplicar_superficies(janela)
    estilo.configure('TButton',padding=(18,10),background=fundo,foreground=texto,anchor='center')
    estilo.map('TButton',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
    estilo.configure('Inicio.TButton',background=c['superficie'])
    estilo.map('Inicio.TButton',background=[('disabled',c['superficie']),('!disabled',c['superficie'])])
    estilo.configure('Inicio.Principal.TButton',background=c['superficie'])
    estilo.map('Inicio.Principal.TButton',background=[('disabled',c['superficie']),('!disabled',c['superficie'])])
    for nome in ('Salvar.TButton','Principal.TButton','DiaSelecionado.TButton','Resultado.Calculadora.TButton'):
        estilo.configure(nome,font=(fonte,10,'bold'),padding=(18,10),foreground=primario_texto)
        estilo.map(nome,foreground=[('disabled',c['desabilitado']),('!disabled',primario_texto)])
    estilo.configure('Menu.TButton',font=(fonte,16,'bold'),padding=(22,16))
    for tipo in ('TRadiobutton','TCheckbutton'):
        estilo.configure(tipo,background=fundo,foreground=texto,indicatorbackground=campo,indicatorforeground=texto,padding=3)
        estilo.map(tipo,background=[('disabled',fundo),('active',c['ativo']),('!disabled',fundo)],
                   foreground=[('disabled',c['desabilitado']),('!disabled',texto)],
                   indicatorbackground=[('disabled',fundo),('selected',c['primario']),('!disabled',campo)],
                   indicatorforeground=[('disabled',c['desabilitado']),('selected',primario_texto),('!disabled',texto)])
    for nome,tamanho,peso,cor in (
        ('InicioTitulo.TLabel',36,'bold',c['floresta']),
        ('Titulo.TLabel',24,'bold',c['floresta']),('Subtitulo.TLabel',11,'normal',c['secundario']),
        ('Discreto.TLabel',9,'normal',c['secundario'])):
        estilo.configure(nome,font=(fonte,tamanho,peso),foreground=cor,background=fundo)
    estilo.configure('Superficie.TFrame',background=c['superficie'])
    for nome,tamanho,peso,cor in (
        ('CartaoTitulo.TLabel',16,'bold',texto),('CartaoTexto.TLabel',10,'normal',c['secundario']),
        ('ResumoTitulo.TLabel',10,'normal',c['secundario']),
        ('ResumoValor.TLabel',19,'bold',texto),('ResumoRealizado.TLabel',19,'bold',c['verde'])):
        estilo.configure(nome,background=c['superficie'],font=(fonte,tamanho,peso),foreground=cor)
    estilo.configure('DataCalculada.TLabel',background=fundo,font=(fonte,10,'bold'))
    estilo.configure('BackupAviso.TLabel',background=fundo,foreground=c['vermelho'],font=(fonte,9))
    estilo.map('DataCalculada.TLabel',background=[('disabled',fundo),('!disabled',fundo)],foreground=[('disabled',c['desabilitado']),('!disabled',texto)])
    estilo.configure('Dinheiro.TFrame',background=campo)
    estilo.configure('Dinheiro.TLabel',background=campo)
    estilo.configure('DiaSelecionado.TButton',font=(fonte,10,'bold'))
    estilo.configure('Recebido.TCheckbutton',foreground=c['verde'],font=(fonte,12,'bold'),background=campo)
    estilo.map('Recebido.TCheckbutton',foreground=[('!disabled',c['verde'])],background=[('active',c['ativo']),('!disabled',campo)])
    estilo.configure('Previsao.TLabel',background=campo,font=(fonte,12),anchor='center')
    estilo.configure('PrevisaoAdiada.TLabel',background=campo,foreground=c['vermelho'],font=(fonte,12),anchor='center')
    estilo.configure('Recebido.TLabel',foreground=c['verde'],font=(fonte,10,'bold'))
    estilo.configure('Restaurar.TButton',font=(fonte,10,'bold'),padding=(18,10))
    estilo.configure('Calculadora.TButton',font=(fonte,15),padding=(8,10))
    estilo.configure('Resultado.Calculadora.TButton',font=(fonte,15,'bold'),padding=(8,10))
    for tipo in ('TEntry','TCombobox'):
        estilo.configure(tipo,fieldbackground=campo,foreground=texto,insertcolor=texto,padding=(10,8),borderwidth=1,relief='flat',arrowsize=14)
        estilo.map(tipo,fieldbackground=[('disabled',fundo),('readonly',campo)],
                   foreground=[('disabled',c['desabilitado']),('readonly',texto)],
                   bordercolor=[('focus',c['floresta']),('!focus',c['borda'])],
                   selectbackground=[('!disabled',c['selecao'])],selectforeground=[('!disabled',c['texto_selecao'])])
    estilo.configure('Treeview',background=campo,fieldbackground=campo,foreground=texto,rowheight=40,borderwidth=0)
    estilo.map('Treeview',background=[('selected',c['selecao'])],foreground=[('selected',c['texto_selecao'])])
    estilo.configure('Operacoes.Treeview',font=(fonte,12),rowheight=max(52,tkfont.Font(font=(fonte,12)).metrics('linespace')+18))
    estilo.configure('Operacoes.Treeview.Heading',font=(fonte,18,'bold'))
    estilo.configure('Operacoes.TCheckbutton',font=(fonte,12),background=campo)
    estilo.map('Operacoes.TCheckbutton',background=[('active',c['ativo']),('!disabled',campo)])
    estilo.configure('ContaSituacao.TLabel',font=(fonte,12,'bold'),background=campo)
    estilo.configure('ContaIncompleta.TLabel',font=(fonte,12,'bold'),foreground=c['vermelho'],background=campo)
    estilo.configure('Contas.Treeview',font=(fonte,12),rowheight=44)
    estilo.configure('Contas.Treeview.Heading',font=(fonte,11,'bold'))
    estilo.configure('Ajuda.TLabel',font=(fonte,10),background=campo,foreground=texto,padding=12,wraplength=320,relief='solid',borderwidth=1)
    estilo.configure('Treeview.Heading',background=c['sage'],foreground=texto,font=(fonte,10,'bold'),padding=(12,12),relief='flat',borderwidth=0)
    estilo.map('Treeview.Heading',background=[('active',c['ativo'])],foreground=[('active',texto)])
    estilo.configure('TScrollbar',background=c['borda'],troughcolor=fundo,borderwidth=0,arrowsize=12)
    estilo.map('TScrollbar',background=[('active',c['secundario'])])
