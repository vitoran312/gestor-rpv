"""Elementos Moss: cantos suaves, sombras e ícones, usando só a biblioteca padrão."""
import math
import struct
import zlib
from functools import lru_cache
import tkinter as tk
from tkinter import ttk, font as tkfont
from tema import cores


def familia_fonte(raiz):
    disponiveis = {f.casefold() for f in tkfont.families(raiz)}
    return next((f for f in ('Segoe UI','Inter','DejaVu Sans','Liberation Sans','Helvetica') if f.casefold() in disponiveis), 'TkDefaultFont')


def _rgb(cor):
    return tuple(int(cor[i:i+2],16) for i in (1,3,5))


@lru_cache(maxsize=32)
def _png_arredondado(cor, sombra=True, raio=15):
    """PNG RGBA com bordas antisserrilhadas; o centro aceita esticamento pelo ttk."""
    largura,altura = 72,48
    rgb = _rgb(cor)
    dados = bytearray()
    def distancia(x,y):
        qx,qy = abs(x-36)-(30-raio), abs(y-22)-(16-raio)
        return math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-raio
    for y in range(altura):
        dados.append(0)
        for x in range(largura):
            sample_y = 22 if 20<=y<=26 else y
            cobertura = sum(distancia(x+dx,sample_y+dy)<=0 for dx,dy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)))/4
            d = max(0,distancia(x+.5,sample_y-2.5))
            alpha = .13*math.exp(-d*d/13) if sombra else 0
            a = cobertura + alpha*(1-cobertura)
            if a:
                pixels = tuple(round(c*cobertura/a) for c in rgb)
                dados.extend((*pixels,round(255*a)))
            else:
                dados.extend((0,0,0,0))
    def bloco(nome,valor):
        return struct.pack('!I',len(valor))+nome+valor+struct.pack('!I',zlib.crc32(nome+valor)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+bloco(b'IHDR',struct.pack('!2I5B',largura,altura,8,6,0,0,0))+
            bloco(b'IDAT',zlib.compress(bytes(dados)))+bloco(b'IEND',b''))


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
                                  ('active',imagens[hover]),border=(24,22,24,24),padding=0,sticky='nsew')
        estilo.element_create(prefixo+'cartao','image',imagens['cartao'],border=(24,22,24,24),padding=0,sticky='nsew')
        cache[chave] = (prefixo,imagens)
    prefixo,_imagens = cache[chave]
    for nome,elemento in (('TButton','secundario'),('Salvar.TButton','primario'),
                          ('Principal.TButton','primario'),('DiaSelecionado.TButton','primario'),('Resultado.Calculadora.TButton','primario'),('Menu.TButton','secundario')):
        estilo.layout(nome,[(prefixo+elemento,{'sticky':'nsew','children':[
            ('Button.padding',{'sticky':'nsew','children':[
                ('Button.focus',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})]})])
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
