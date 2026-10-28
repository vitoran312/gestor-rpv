"""Elementos Vitoran Pro: superfícies planas, cantos suaves e ícones, só com a biblioteca padrão."""
import math
import struct
import zlib
from functools import lru_cache
import tkinter as tk
from tkinter import ttk, font as tkfont
from tema import cores


def familia_fonte(raiz):
    raiz = raiz._root()
    if hasattr(raiz,'_familia_pro'):
        return raiz._familia_pro
    disponiveis = {f.casefold() for f in tkfont.families(raiz)}
    raiz._familia_pro = next((f for f in ('Segoe UI','Inter','DejaVu Sans','Liberation Sans','Helvetica') if f.casefold() in disponiveis),tkfont.nametofont('TkDefaultFont').actual('family'))
    return raiz._familia_pro


def fator_escala(widget):
    """Quanto a tela amplia em relação a 96 DPI (1,0 em 100%, 1,5 em 150%); nunca reduz."""
    raiz = widget._root()
    if not hasattr(raiz, '_fator_escala'):
        raiz._fator_escala = max(1.0, raiz.winfo_fpixels('1i') / 96)
    return raiz._fator_escala


def px(widget, valor):
    """Converte uma medida pensada para 100% de escala em pixels da tela atual."""
    return round(valor * fator_escala(widget))


def _rgb(cor):
    return tuple(int(cor[i:i+2],16) for i in (1,3,5))


def misturar(cor, destino, peso):
    """Cor entre `cor` (peso 0) e `destino` (peso 1), em #rrggbb."""
    return '#' + ''.join(f'{round(x + (y - x) * peso):02x}' for x, y in zip(_rgb(cor), _rgb(destino)))


@lru_cache(maxsize=8)
def _mascara_arredondada(largura,altura,raio):
    """Cobertura do preenchimento e do contorno de 1 px, calculada uma vez por geometria."""
    def distancia(x,y):
        qx,qy = abs(x-largura/2)-(largura/2-raio),abs(y-altura/2)-(altura/2-raio)
        return math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-raio
    amostras = ((.25,.25),(.75,.25),(.25,.75),(.75,.75))
    mascara = []
    for y in range(altura):
        for x in range(largura):
            dentro = sum(distancia(x+dx,y+dy)<=0 for dx,dy in amostras)/4
            miolo = sum(distancia(x+dx,y+dy)<=-1 for dx,dy in amostras)/4
            mascara.append((dentro,miolo))
    return tuple(mascara)


def _codificar_png(largura,altura,dados):
    def bloco(nome,valor):
        return struct.pack('!I',len(valor))+nome+valor+struct.pack('!I',zlib.crc32(nome+valor)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+bloco(b'IHDR',struct.pack('!2I5B',largura,altura,8,6,0,0,0))+
            bloco(b'IDAT',zlib.compress(bytes(dados)))+bloco(b'IEND',b''))


def _pixels_arredondados(cor,contorno,raio,largura,altura):
    """Linhas de pixels RGBA de uma superfície pequena, calculada amostra a amostra."""
    rgb,borda = _rgb(cor),_rgb(contorno or cor)
    linhas = []
    for indice,(dentro,miolo) in enumerate(_mascara_arredondada(largura,altura,raio)):
        if indice%largura==0: linhas.append(bytearray())
        peso = miolo/dentro if dentro else 0
        linhas[-1].extend((*(round(a*peso+b*(1-peso)) for a,b in zip(rgb,borda)),round(255*dentro)))
    return linhas


@lru_cache(maxsize=48)
def _png_arredondado(cor,contorno=None,raio=8,largura=40,altura=36):
    """Superfície plana: preenchimento com contorno opcional de 1 px, sem sombra.

    Só os cantos dependem do raio; o resto repete a faixa reta central. Por isso a imagem grande é montada
    a partir de uma pequena, sem calcular pixel a pixel — o que permite gerar superfícies do tamanho real
    dos cartões e botões (veja aplicar_superficies).
    """
    lado = raio+2
    # Em formatos de pílula (menores que dois cantos), aquela dimensão é calculada inteira, sem esticar.
    lx = lado if largura >= 2*lado else None
    ly = lado if altura >= 2*lado else None
    base = _pixels_arredondados(cor,contorno,raio,2*lx if lx else largura,2*ly if ly else altura)
    def linha(j):
        pixels = base[j]
        if not lx:
            return pixels
        return pixels[:4*lx]+pixels[4*lx:4*lx+4]*(largura-2*lx)+pixels[4*lx:]
    if ly:
        linhas = [linha(j) for j in range(ly)]+[linha(ly)]*(altura-2*ly)+[linha(j) for j in range(ly,2*ly)]
    else:
        linhas = [linha(j) for j in range(altura)]
    dados = bytearray()
    for pixels in linhas:
        dados.append(0)
        dados.extend(pixels)
    return _codificar_png(largura,altura,dados)


def _png_recebido(c,selecionado):
    """Indicador de 24 px; a margem separa a caixa da data do recebimento."""
    fundo=_rgb(c['primario'] if selecionado else c['campo'])
    borda=_rgb(c['primario'] if selecionado else c['secundario'])
    marca=_rgb(c['primario_texto'])
    def segmento(x,y,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
        return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
    dados=bytearray()
    for y in range(26):
        dados.append(0)
        for x in range(31):
            amostras=[]
            for dx,dy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)):
                px,py=x+dx,y+dy
                qx,qy=abs(px-13)-8,abs(py-13)-8
                d=math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-4
                if d>0:
                    continue
                cor=borda if d>-1.5 else fundo
                if selecionado and min(segmento(px,py,(6.5,13),(11,17.5)),segmento(px,py,(11,17.5),(19.5,8.5)))<=1.3:
                    cor=marca
                amostras.append(cor)
            if amostras:
                dados.extend((*[round(sum(a[i] for a in amostras)/len(amostras)) for i in range(3)],round(255*len(amostras)/4)))
            else:
                dados.extend((0,0,0,0))
    return _codificar_png(31,26,dados)


def icone_tema(raiz,modo):
    """Lua para ativar o escuro e sol para ativar o claro, sem depender de uma fonte de símbolos."""
    cache = getattr(raiz,'_icones_modo',{})
    raiz._icones_modo = cache
    cor = cores()['texto']
    chave = (modo,cor)
    if chave not in cache:
        rgb = _rgb(cor)
        def dentro(x,y):
            if modo=='claro':
                return math.hypot(x-10,y-10)<=8 and math.hypot(x-14,y-7)>7.5
            if math.hypot(x-10,y-10)<=4:
                return True
            for i in range(8):
                angulo=i*math.pi/4
                ux,uy=math.cos(angulo),math.sin(angulo)
                proj=max(6.5,min(9,(x-10)*ux+(y-10)*uy))
                if math.hypot(x-10-proj*ux,y-10-proj*uy)<=.75:
                    return True
            return False
        dados=bytearray()
        for y in range(20):
            dados.append(0)
            for x in range(20):
                alpha=round(255*sum(dentro(x+dx,y+dy) for dx,dy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)))/4)
                dados.extend((*rgb,alpha))
        cache[chave]=tk.PhotoImage(master=raiz,data=_codificar_png(20,20,dados))
    return cache[chave]


def aplicar_superficies(raiz):
    """Imagens guardadas pela raiz; estilos nativos mantêm foco, teclado e acessibilidade."""
    c = cores()
    estilo = ttk.Style(raiz)
    cache = getattr(raiz,'_superficies_pro',{})
    raiz._superficies_pro = cache
    chave = c['fundo']
    if chave not in cache:
        imagens = {}
        for nome,cor,contorno in (('botao',c['botao'],c['borda']),('ativo',c['ativo'],c['borda']),
                                  ('pressionado',c['selecao'],c['floresta']),
                                  ('primario',c['primario'],None),('primario_ativo',c['primario_ativo'],None),
                                  ('primario_pressionado',c['primario_pressionado'],None),
                                  ('inativo',c['fundo'],c['borda_suave'])):
            imagens[nome] = tk.PhotoImage(master=raiz,data=_png_arredondado(cor,contorno,8,480,48))
        # O ttk preenche o miolo repetindo a imagem como azulejos; no Windows, centenas de azulejos pequenos
        # com transparência tornavam lenta a troca de tema. Imagens do tamanho real cobrem cada superfície
        # com um ou dois azulejos; os tamanhos mínimos das superfícies continuam os mesmos.
        imagens['filtro'] = tk.PhotoImage(master=raiz,data=_png_arredondado(c['fundo'],c['borda_suave'],16,240,32))
        imagens['filtro_ativo'] = tk.PhotoImage(master=raiz,data=_png_arredondado(c['ativo'],c['borda'],16,240,32))
        imagens['filtro_selecionado'] = tk.PhotoImage(master=raiz,data=_png_arredondado(c['realce'],c['floresta'],16,240,32))
        imagens['cartao'] = tk.PhotoImage(master=raiz,data=_png_arredondado(c['superficie'],c['borda_suave'],12,1200,800))
        prefixo = 'Pro'+chave[1:]
        for nome,normal,hover,pressionado in (('secundario','botao','ativo','pressionado'),
                                              ('primario','primario','primario_ativo','primario_pressionado')):
            estilo.element_create(prefixo+nome,'image',imagens[normal],
                                  ('disabled',imagens['inativo']),('pressed',imagens[pressionado]),
                                  ('active',imagens[hover]),border=(10,10,10,10),padding=0,width=40,height=36,sticky='nsew')
        estilo.element_create(prefixo+'filtro','image',imagens['filtro'],('selected',imagens['filtro_selecionado']),
                              ('active',imagens['filtro_ativo']),border=(16,14,16,14),padding=0,width=40,height=32,sticky='nsew')
        estilo.element_create(prefixo+'cartao','image',imagens['cartao'],border=(14,14,14,14),padding=0,width=48,height=48,sticky='nsew')
        for selecionado in (False,True):
            imagens['recebido'+str(selecionado)]=tk.PhotoImage(master=raiz,data=_png_recebido(c,selecionado))
        estilo.element_create(prefixo+'recebido','image',imagens['recebidoFalse'],
                              ('selected',imagens['recebidoTrue']),sticky='')
        cache[chave] = (prefixo,imagens)
    prefixo,_imagens = cache[chave]
    for nome,elemento in (('TButton','secundario'),('Salvar.TButton','primario'),
                          ('Principal.TButton','primario'),('DiaSelecionado.TButton','primario'),('Resultado.Calculadora.TButton','primario'),('Menu.TButton','secundario')):
        estilo.layout(nome,[(prefixo+elemento,{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[
                ('Button.label',{'sticky':'nsew'})]})]})])
    def sem_contorno_foco(layout):
        resultado=[]
        for elemento,opcoes in layout:
            opcoes=dict(opcoes)
            if 'children' in opcoes:
                opcoes['children']=sem_contorno_foco(opcoes['children'])
            if elemento.endswith('.focus'):
                resultado.extend(opcoes.get('children',[]))
            else:
                resultado.append((elemento,opcoes))
        return resultado
    for nome in ('TRadiobutton','TCheckbutton'):
        estilo.layout(nome,sem_contorno_foco(estilo.layout(nome)))
    for nome in ('Recebido.TCheckbutton','Operacoes.TCheckbutton'):
        estilo.layout(nome,[('Checkbutton.padding',{'sticky':'nswe','children':[
            (prefixo+'recebido',{'side':'left','sticky':''}),
            ('Checkbutton.label',{'side':'left','sticky':'nswe'})]})])
    for nome in ('Filtro.TRadiobutton','FiltroAlerta.TRadiobutton'):
        estilo.layout(nome,[(prefixo+'filtro',{'sticky':'nsew','children':[
            ('Radiobutton.padding',{'sticky':'nsew','children':[('Radiobutton.label',{'sticky':'nsew'})]})]})])
    for nome in ('Cartao.TFrame','Resumo.TFrame'):
        estilo.layout(nome,[(prefixo+'cartao',{'sticky':'nsew','children':[('Frame.padding',{'sticky':'nsew'})]})])
        estilo.configure(nome,background=c['fundo'],borderwidth=0)


class Icone(tk.Canvas):
    def __init__(self,pai,nome):
        super().__init__(pai,width=54,height=54,highlightthickness=0,bd=0)
        self.nome = nome
        self.atualizar_tema()

    def atualizar_tema(self):
        c = cores()
        self.configure(bg=c['superficie'])
        self.delete('all')
        self.create_oval(5,5,49,49,fill=c['realce'],outline='')
        linha = dict(fill=c['floresta'],width=1.8,capstyle='round',joinstyle='round')
        if self.nome == 'entrada':
            self.create_line(17,14,32,14,38,20,38,40,17,40,17,14,**linha)
            self.create_line(31,14,31,21,38,21,**linha)
            self.create_line(23,29,32,29,**linha)
            self.create_line(27.5,24.5,27.5,33.5,**linha)
        elif self.nome == 'historico':
            self.create_line(16,40,16,33,22,33,22,40,**linha)
            self.create_line(25,40,25,26,31,26,31,40,**linha)
            self.create_line(34,40,34,18,40,18,40,40,**linha)
            self.create_line(15,27,24,19,30,21,39,12,**linha)
        else:
            self.create_line(14,22,27,13,40,22,14,22,**linha)
            for x in (18,27,36): self.create_line(x,27,x,37,**linha)
            self.create_line(14,41,40,41,**linha)
