"""Seleção de linhas e atalhos, limitados à tabela que possui o foco."""
def pressionar_linha(tabela, linha, estado=0):
    tabela._selecionando_mouse = True
    tabela.focus_set()
    controle, shift = bool(estado & 4), bool(estado & 1)
    linhas = list(tabela.get_children())
    anterior = tuple(tabela.selection())
    ancora = getattr(tabela, '_ancora', None)
    if linha:
        if shift and ancora in linhas:
            a,b = sorted((linhas.index(ancora),linhas.index(linha)))
            selecao = linhas[a:b+1]
            tabela.selection_set(tuple(dict.fromkeys(anterior + tuple(selecao))) if controle else selecao)
        elif controle:
            if linha in anterior:
                tabela.selection_remove(linha)
            else:
                tabela.selection_add(linha)
            tabela._ancora = linha
        else:
            tabela.selection_set(linha)
            tabela._ancora = linha
        tabela.focus(linha)
    elif not controle and not shift:
        tabela.selection_set(())
    tabela._inicio_arrasto = linha
    tabela._base_arrasto = anterior if controle else ()
    tabela._arrastando = False
    tabela._modificadores_mouse = estado & 5


def arrastar(tabela, y):
    if not getattr(tabela, '_selecionando_mouse', False):
        return
    linha = tabela.identify_row(y)
    if y < 25:
        tabela.yview_scroll(-1,'units')
    elif y > tabela.winfo_height()-5:
        tabela.yview_scroll(1,'units')
    if not linha:
        return 'break'
    inicio = getattr(tabela,'_inicio_arrasto',None)
    if not inicio:
        inicio = linha
        tabela._inicio_arrasto = linha
    linhas = list(tabela.get_children())
    if inicio not in linhas:
        return 'break'
    a,b = sorted((linhas.index(inicio),linhas.index(linha)))
    tabela.selection_set(tuple(dict.fromkeys(tuple(getattr(tabela,'_base_arrasto',())) + tuple(linhas[a:b+1]))))
    tabela.focus(linha)
    tabela._arrastando = True
    return 'break'


def habilitar_selecao(tabela, abrir=None, excluir=None, copiar=None):
    tabela.configure(selectmode='extended')

    def pressionar(evento):
        if tabela.identify_region(evento.x,evento.y) in ('heading','separator'):
            tabela._selecionando_mouse = False
            return
        pressionar_linha(tabela,tabela.identify_row(evento.y),evento.state)
        return 'break'

    def mover(evento):
        linhas = list(tabela.get_children())
        if not linhas:
            return 'break'
        foco = tabela.focus()
        indice = linhas.index(foco) if foco in linhas else 0
        pagina = max(1,tabela.winfo_height()//34-1)
        destino = {'Up':indice-1,'Down':indice+1,'Home':0,'End':len(linhas)-1,
                   'Prior':indice-pagina,'Next':indice+pagina}[evento.keysym]
        destino = max(0,min(len(linhas)-1,destino))
        linha = linhas[destino]
        if evento.state & 1:
            ancora = getattr(tabela,'_ancora',foco)
            if ancora not in linhas:
                ancora = foco if foco in linhas else linha
            a,b = sorted((linhas.index(ancora),destino))
            tabela.selection_set(linhas[a:b+1])
        elif not evento.state & 4:
            tabela.selection_set(linha)
            tabela._ancora = linha
        tabela.focus(linha)
        tabela.see(linha)
        return 'break'

    def executar(funcao):
        if funcao:
            funcao()
        return 'break'

    def selecionar_tudo(_evento):
        tabela.selection_set(tabela.get_children())
        return 'break'

    def limpar(_evento):
        tabela.selection_set(())
        return 'break'

    tabela.bind('<Button-1>',pressionar)
    tabela.bind('<B1-Motion>',lambda e: arrastar(tabela,e.y))
    for tecla in ('Up','Down','Home','End','Prior','Next'):
        tabela.bind('<'+tecla+'>',mover)
    for atalho in ('<Control-a>','<Control-A>'):
        tabela.bind(atalho,selecionar_tudo)
    tabela.bind('<Escape>',limpar)
    tabela.bind('<Delete>',lambda _: executar(excluir))
    tabela.bind('<Return>',lambda _: executar(abrir))
    tabela.bind('<KP_Enter>',lambda _: executar(abrir))
    if copiar:
        tabela.bind('<Control-c>',lambda _: executar(copiar))
        tabela.bind('<Control-C>',lambda _: executar(copiar))
