"""Elementos Moss: cantos suaves, sombras e ícones, usando só a biblioteca padrão."""
import math
import struct
import zlib
from functools import lru_cache
import tkinter as tk
from tkinter import ttk, font as tkfont
from tema import cores


def familia_fonte(raiz):
    raiz = raiz._root()
    if hasattr(raiz,'_familia_moss'):
        return raiz._familia_moss
    disponiveis = {f.casefold() for f in tkfont.families(raiz)}
    raiz._familia_moss = next((f for f in ('Segoe UI','Inter','DejaVu Sans','Liberation Sans','Helvetica') if f.casefold() in disponiveis),tkfont.nametofont('TkDefaultFont').actual('family'))
    return raiz._familia_moss


def _rgb(cor):
    return tuple(int(cor[i:i+2],16) for i in (1,3,5))


@lru_cache(maxsize=4)
def _mascara_arredondada(sombra,raio):
    """A geometria da sombra é calculada uma única vez e reutilizada em todas as cores."""
    def distancia(x,y):
        qx,qy = abs(x-48)-(42-raio),abs(y-34)-(28-raio)
        return math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-raio
    mascara = []
    for y in range(72):
        for x in range(96):
            sample_y = y
            cobertura = sum(distancia(x+dx,sample_y+dy)<=0 for dx,dy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)))/4
            d = max(0,distancia(x+.5,sample_y-2.5))
            alpha = .13*math.exp(-d*d/13) if sombra else 0
            a = cobertura+alpha*(1-cobertura)
            mascara.append((cobertura/a if a else 0,round(255*a)))
    return tuple(mascara)


def _codificar_png(largura,altura,dados):
    def bloco(nome,valor):
        return struct.pack('!I',len(valor))+nome+valor+struct.pack('!I',zlib.crc32(nome+valor)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+bloco(b'IHDR',struct.pack('!2I5B',largura,altura,8,6,0,0,0))+
            bloco(b'IDAT',zlib.compress(bytes(dados)))+bloco(b'IEND',b''))


@lru_cache(maxsize=32)
def _png_arredondado(cor,sombra=True,raio=15):
    rgb = _rgb(cor)
    dados = bytearray()
    for indice,(peso,alpha) in enumerate(_mascara_arredondada(sombra,raio)):
        if indice%96==0: dados.append(0)
        dados.extend((round(rgb[0]*peso),round(rgb[1]*peso),round(rgb[2]*peso),alpha))
    return _codificar_png(96,72,dados)


def _png_recebido(c,selecionado):
    """Indicador de 24 px; a margem separa a caixa da data do recebimento."""
    fundo=_rgb(c['primario'] if selecionado else c['campo'])
    borda=_rgb(c['primario'] if selecionado else c['secundario'])
    marca=_rgb('#fffdf8' if sum(_rgb(c['primario']))<384 else '#193623')
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
    cache = getattr(raiz,'_superficies_moss',{})
    raiz._superficies_moss = cache
    chave = c['fundo']
    if chave not in cache:
        imagens = {}
        for nome,cor in (('botao',c['botao']),('ativo',c['ativo']),('pressionado',c['selecao']),
                         ('primario',c['primario']),('primario_ativo',c['primario_ativo']),
                         ('primario_pressionado',c['primario_pressionado']),('cartao',c['superficie']),('inativo',c['fundo'])):
            imagens[nome] = tk.PhotoImage(master=raiz,data=_png_arredondado(cor))
        prefixo = 'Moss'+chave[1:]
        for nome,normal,hover,pressionado in (('secundario','botao','ativo','pressionado'),
                                              ('primario','primario','primario_ativo','primario_pressionado')):
            estilo.element_create(prefixo+nome,'image',imagens[normal],
                                  ('disabled',imagens['inativo']),('pressed',imagens[pressionado]),
                                  ('active',imagens[hover]),border=(24,22,24,24),padding=0,width=72,height=48,sticky='nsew')
        estilo.element_create(prefixo+'cartao','image',imagens['cartao'],border=(24,22,24,24),padding=0,width=72,height=48,sticky='nsew')
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
        self.create_oval(2,2,52,52,fill=c['sage'],outline='')
        linha = dict(fill=c['floresta'],width=2.2,capstyle='round',joinstyle='round')
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
