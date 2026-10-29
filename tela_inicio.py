"""Tela inicial: data e título, cartão Nova entrada em destaque (nanquim), cartões de acesso, avisos e rodapé.

Marca, tema, Sobre e Sair ficam na barra lateral (barra_lateral.py), sempre visível ao lado desta tela.

A tela é um Canvas: as luzes de fundo e as superfícies arredondadas dos cartões são desenhadas nele, e o
conteúdo de cada cartão fica num quadro posicionado por cima. Assim as luzes aparecem entre os cartões
sem retângulos de fundo, e títulos soltos (cabeçalho e assinatura) são textos do próprio Canvas.
"""
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import ttk

from arte_inicio import ArteVidro, LuzesFundo, Relogio
from dados import situacao
from tema import cores, modo_atual, PALETAS
from versao import VERSAO
from visual import Icone, LARGURA_LAYOUT_LARGO, _png_arredondado, familia_titulo, margens_sombra, misturar, px, sombra_cartao

# Tamanho máximo da composição da tela inicial (em pixels a 100% de escala), nas proporções de referência.
COMPOSICAO = (1420, 900)

ATALHOS = (
    ('entrada', 'Uma nova operação', 'Cadastre sua próxima aquisição\ne reúna os documentos da entrada.', 'Nova entrada'),
    ('historico', 'Tudo sob controle', 'Consulte valores, acompanhe prazos\ne confirme seus recebimentos.', 'Minhas operações'),
    ('contas', 'Contas de recebimento', 'Mantenha seus dados bancários\norganizados e sempre à mão.', 'Contas de recebimento'),
)


DIAS = ('segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo')
MESES = ('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
         'novembro', 'dezembro')


def data_por_extenso(dia=None):
    """"Quinta-feira, 29 de outubro de 2026": a data no alto da tela inicial."""
    dia = dia or date.today()
    return f'{DIAS[dia.weekday()].capitalize()}, {dia.day} de {MESES[dia.month - 1]} de {dia.year}'


def cores_superficie(paleta, tipo):
    """Preenchimento, contorno e raio de cada tipo de superfície da tela inicial."""
    if tipo == 'destaque':
        return paleta['heroi'], paleta['heroi_borda'], 20
    if tipo == 'aviso':
        return paleta['superficie'], misturar(paleta['borda_suave'], paleta['vermelho'], 0.4), 16
    return paleta['superficie'], paleta['borda_suave'], 16


def recuo_superficie(paleta, tipo, p):
    """Distância da borda da imagem até o conteúdo: margem da sombra mais o raio do canto."""
    esquerda, topo, direita, base = margens_sombra(sombra_cartao(paleta))
    raio = p(cores_superficie(paleta, tipo)[2])
    return esquerda + raio, topo + raio, direita + raio, base + raio


class IconeAlerta(tk.Canvas):
    def __init__(self, pai):
        super().__init__(pai, width=34, height=34, highlightthickness=0, bd=0)
        self.atualizar_tema()

    def atualizar_tema(self):
        c = cores()
        self.configure(bg=c['superficie'])
        self.delete('all')
        self.create_oval(3, 3, 31, 31, outline=c['vermelho'], width=2)
        self.create_line(17, 10, 17, 19, fill=c['vermelho'], width=2.4, capstyle='round')
        self.create_oval(15.6, 22.6, 18.4, 25.4, fill=c['vermelho'], outline='')


class TelaInicio(tk.Canvas):
    """Canvas da tela inicial; atualizar_tema é chamado pela troca de tema, como nos demais componentes."""

    def __init__(self, pai, aplicativo):
        super().__init__(pai, highlightthickness=0, bd=0)
        self.app = aplicativo

    def atualizar_tema(self):
        self.app.tematizar_inicio()


class InicioMixin:
    def construir_inicio(self, janela):
        c = cores()
        tela = self.inicio = TelaInicio(janela, self)
        tela.configure(bg=c['fundo'])
        tela.pack(fill='both', expand=True)
        self.superficies_inicio = {}
        self.medidas_inicio = {}
        self.pecas_inicio = {}
        self.luzes_inicio = LuzesFundo(tela)

        self.data_inicio = tela.create_text(0, 0, text=data_por_extenso(), anchor='sw')
        self.titulo_inicio = tela.create_text(0, 0, text='Gestor de RPV', anchor='sw')
        self.subtitulo_inicio = tela.create_text(0, 0, text='Registros, recebimentos e documentos. Tudo no seu lugar.',
                                                 anchor='nw')

        self.cartoes_inicio = []
        self.partes_inicio = {}
        acoes = {'entrada': self.formulario, 'historico': self.mostrar_historico, 'contas': self.mostrar_contas}
        for icone, titulo, descricao, rotulo in ATALHOS:
            destaque = icone == 'entrada'
            fundo_cartao = 'Heroi.TFrame' if destaque else 'Superficie.TFrame'
            cartao = ttk.Frame(tela, style=fundo_cartao)
            faixa = ttk.Frame(cartao, style=fundo_cartao)
            Icone(faixa, icone, heroi=destaque).pack(side='left')
            rotulo_titulo = ttk.Label(cartao, text=titulo, style='DestaqueTitulo.TLabel' if destaque else 'CartaoTitulo.TLabel')
            rotulo_descricao = ttk.Label(cartao, text=descricao, justify='left',
                                         style='DestaqueTexto.TLabel' if destaque else 'CartaoTexto.TLabel')
            botao_cartao = ttk.Button(cartao, text=rotulo, command=acoes[icone],
                                      style='Destaque.Principal.TButton' if destaque else 'Inicio.TButton')
            if destaque:
                # Margem direita mínima: a arte de vidro vai até a borda; textos e botão mantêm a folga.
                cartao.configure(padding=(px(tela, 40), px(tela, 36), 0, px(tela, 36)))
                cartao.columnconfigure(0, weight=1)
                cartao.rowconfigure(3, weight=1)
                faixa.grid(row=0, column=0, sticky='w')
                rotulo_titulo.grid(row=1, column=0, sticky='w', pady=(px(tela, 22), px(tela, 10)))
                rotulo_descricao.grid(row=2, column=0, sticky='w')
                botao_cartao.grid(row=4, column=0, sticky='ew', pady=(px(tela, 24), 0), padx=(0, px(tela, 40)))
                # Arte de vidro atrás do conteúdo, no espaço livre à direita dos textos.
                self.arte_inicio = ArteVidro(cartao)
                self.arte_inicio.tk.call('lower', self.arte_inicio._w)  # No Canvas, lower() moveria desenhos.
                cartao.bind('<Configure>', lambda _: self.janela.after_idle(self.posicionar_arte), add='+')
            else:
                # Ícone à esquerda; título, descrição e botão empilhados e centralizados na altura do cartão.
                cartao.configure(padding=(px(tela, 30), px(tela, 18)))
                cartao.columnconfigure(1, weight=1)
                cartao.rowconfigure((0, 4), weight=1)
                faixa.grid(row=1, column=0, rowspan=3, sticky='nw', padx=(0, px(tela, 22)))
                rotulo_titulo.grid(row=1, column=1, sticky='w', pady=(0, px(tela, 6)))
                rotulo_descricao.grid(row=2, column=1, sticky='w')
                botao_cartao.grid(row=3, column=1, sticky='w', pady=(px(tela, 16), 0))
            self.partes_inicio[cartao] = (faixa, rotulo_titulo, rotulo_descricao, botao_cartao)
            self.cartoes_inicio.append(cartao)
            self.pecas_inicio[icone] = (cartao, 'destaque' if destaque else 'cartao')

        self.texto_aviso_atrasadas = tk.StringVar()
        self.texto_aviso_backup = tk.StringVar()
        for chave, variavel, estilo, acao in (
                ('atrasadas', self.texto_aviso_atrasadas, 'InicioAtrasadas.TLabel', self.mostrar_atrasadas),
                ('backup', self.texto_aviso_backup, 'InicioBackup.TLabel', self.exportar_backup)):
            aviso = ttk.Frame(tela, style='Superficie.TFrame', padding=(px(tela, 8), 0), cursor='hand2')
            aviso.columnconfigure(1, weight=1)
            aviso.rowconfigure(0, weight=1)
            IconeAlerta(aviso).grid(row=0, column=0, padx=(0, px(tela, 14)))
            rotulo = ttk.Label(aviso, textvariable=variavel, style=estilo, cursor='hand2')
            rotulo.grid(row=0, column=1, sticky='w')
            for widget in (aviso, *aviso.winfo_children()):
                widget.bind('<Button-1>', lambda _, a=acao: a())
            self.pecas_inicio[chave] = (aviso, 'aviso')
            setattr(self, f'aviso_{chave}_inicio', rotulo)
            variavel.trace_add('write', lambda *_: self.janela.after_idle(self.organizar_inicio))

        self.marca_assinatura = tela.create_image(0, 0, image=janela._marca_rodape, anchor='e')
        self.assinatura_inicio = tela.create_text(0, 0, text=f'Vitoran Tech · v{VERSAO}', anchor='e')
        self.janelas_inicio = {chave: tela.create_window(0, 0, window=peca, anchor='nw')
                               for chave, (peca, _tipo) in self.pecas_inicio.items()}
        self.desenhos_inicio = {chave: tela.create_image(0, 0, anchor='nw') for chave in self.pecas_inicio}
        self.relogio_inicio = Relogio(tela, self.arte_inicio)
        tela.bind('<Configure>', lambda _: self.organizar_inicio())
        self.tematizar_inicio()

    def tematizar_inicio(self):
        c = cores()
        tela = self.inicio
        tela.configure(bg=c['fundo'])
        tela.itemconfigure(self.data_inicio, fill=c['marca'], font=(self.fonte, 10, 'bold'))
        tela.itemconfigure(self.titulo_inicio, fill=c['texto'], font=(familia_titulo(tela), 36, 'bold'))
        tela.itemconfigure(self.subtitulo_inicio, fill=c['secundario'], font=(self.fonte, 12))
        tela.itemconfigure(self.assinatura_inicio, fill=c['secundario'], font=(self.fonte, 9))
        self.luzes_inicio.atualizar_tema()
        self.organizar_inicio()

    def superficie_inicio(self, tipo, largura, altura, modo=None):
        """Superfície arredondada no tamanho exato, guardada por tema e tamanho (veja descartar_superficies)."""
        modo = modo or modo_atual()
        chave = (modo, tipo, largura, altura)
        if chave not in self.superficies_inicio:
            preenchimento, contorno, raio = cores_superficie(PALETAS[modo], tipo)
            dados = _png_arredondado(preenchimento, contorno, px(self.inicio, raio), largura, altura,
                                     sombra_cartao(PALETAS[modo]))
            self.superficies_inicio[chave] = tk.PhotoImage(master=self.inicio, data=dados)
        return self.superficies_inicio[chave]

    def preparar_superficies_inicio(self, modo):
        for chave, (peca, tipo) in self.pecas_inicio.items():
            if self.inicio.itemcget(self.desenhos_inicio[chave], 'state') != 'hidden':
                largura, altura = self.medidas_inicio.get(chave, (0, 0))
                if largura > 0 and altura > 0:
                    self.superficie_inicio(tipo, largura, altura, modo)

    def organizar_inicio(self):
        """Distribui cabeçalho, cartões, avisos e rodapé na área da janela, nas proporções da tela inicial."""
        tela = self.inicio
        if not tela.winfo_exists():
            return
        largura, altura = tela.winfo_width(), tela.winfo_height()
        if largura < 50 or altura < 50:
            return
        p = lambda v: px(tela, v)
        # A composição tem tamanho máximo e fica centralizada: em telas grandes, sobra fundo ao redor,
        # em vez de esticar os cartões. Daqui para baixo, largura e altura são as da composição.
        janela_largura, janela_altura = largura, altura
        largura, altura = min(largura, p(COMPOSICAO[0])), min(altura, p(COMPOSICAO[1]))
        ox, oy = (janela_largura - largura) // 2, (janela_altura - altura) // 2
        margem, espaco = p(40), p(18)
        topo_cabecalho = p(40)
        tela.coords(self.data_inicio, margem + p(4), topo_cabecalho + p(22))
        tela.coords(self.titulo_inicio, margem, topo_cabecalho + p(78))
        tela.coords(self.subtitulo_inicio, margem + p(2), topo_cabecalho + p(86))
        rodape = altura - p(24)
        tela.coords(self.assinatura_inicio, largura - margem, rodape - p(6))
        assinatura = tela.bbox(self.assinatura_inicio)
        tela.coords(self.marca_assinatura, (assinatura[0] if assinatura else largura - margem) - p(6), rodape - p(6))

        topo = topo_cabecalho + p(138)
        base = rodape - p(30)
        avisos = [chave for chave, variavel in (('atrasadas', self.texto_aviso_atrasadas),
                                                 ('backup', self.texto_aviso_backup)) if variavel.get()]
        altura_aviso = p(96)
        retangulos = {}
        conteudo = largura - 2 * margem
        if largura >= p(LARGURA_LAYOUT_LARGO):
            # Cartão em destaque à esquerda; à direita, os dois atalhos empilhados e os avisos.
            esquerda = round(conteudo * 0.56)
            direita_x = margem + esquerda + espaco
            direita = conteudo - esquerda - espaco
            retangulos['entrada'] = (margem, topo, esquerda, base - topo)
            area = base - topo - len(avisos) * (altura_aviso + espaco)
            cartao = max(p(110), (area - espaco) // 2)
            retangulos['historico'] = (direita_x, topo, direita, cartao)
            retangulos['contas'] = (direita_x, topo + cartao + espaco, direita, cartao)
            y = topo + 2 * (cartao + espaco)
            for chave in avisos:
                retangulos[chave] = (direita_x, y, direita, altura_aviso)
                y += altura_aviso + espaco
        else:
            # Janelas estreitas: destaque em cima, atalhos lado a lado e avisos abaixo.
            avisos_altura = len(avisos) * (altura_aviso + espaco)
            area = base - topo - avisos_altura
            destaque = max(p(240), round((area - espaco) * 0.55))
            retangulos['entrada'] = (margem, topo, conteudo, destaque)
            metade = (conteudo - espaco) // 2
            linha = topo + destaque + espaco
            cartao = max(p(120), area - destaque - espaco)
            retangulos['historico'] = (margem, linha, metade, cartao)
            retangulos['contas'] = (margem + metade + espaco, linha, conteudo - metade - espaco, cartao)
            y = linha + cartao + espaco
            for chave in avisos:
                retangulos[chave] = (margem, y, conteudo, altura_aviso)
                y += altura_aviso + espaco
        self.layout_largo_inicio = largura >= p(LARGURA_LAYOUT_LARGO)
        self.medidas_inicio = {}
        for chave, (peca, tipo) in self.pecas_inicio.items():
            desenho, janela_peca = self.desenhos_inicio[chave], self.janelas_inicio[chave]
            if chave not in retangulos:
                # Sem imagem: a superfície desse tamanho pode ser descartada logo abaixo.
                tela.itemconfigure(desenho, state='hidden', image='')
                tela.itemconfigure(janela_peca, state='hidden')
                continue
            x, y, w, h = (round(v) for v in retangulos[chave])
            self.medidas_inicio[chave] = (w, h)
            # O conteúdo fica dentro dos cantos arredondados (e longe da sombra), desenhados no Canvas.
            esquerda, topo_peca, direita, base_peca = recuo_superficie(cores(), tipo, p)
            tela.coords(desenho, x, y)
            tela.itemconfigure(desenho, image=self.superficie_inicio(tipo, w, h), state='normal')
            tela.coords(janela_peca, x + esquerda, y + topo_peca)
            tela.itemconfigure(janela_peca, width=max(1, w - esquerda - direita), height=max(1, h - topo_peca - base_peca),
                               state='normal')
        # Descarta só tamanhos que nenhum cartão usa mais; os dois temas do tamanho atual continuam guardados.
        em_uso = {(tipo, *self.medidas_inicio[chave]) for chave, (_peca, tipo) in self.pecas_inicio.items()
                  if chave in self.medidas_inicio}
        for chave in [k for k in self.superficies_inicio if k[1:] not in em_uso]:
            del self.superficies_inicio[chave]
        # Desloca tudo o que foi posicionado para a composição centralizada.
        visiveis = [chave for chave in self.pecas_inicio if chave in retangulos]
        itens = [self.janelas_inicio[nome] for nome in visiveis]
        itens += [self.desenhos_inicio[chave] for chave in visiveis]
        itens += [self.data_inicio, self.titulo_inicio, self.subtitulo_inicio,
                  self.assinatura_inicio, self.marca_assinatura]
        for item in itens:
            tela.move(item, ox, oy)
        self.luzes_inicio.desenhar((ox, oy, largura, altura))
        self.janela.after_idle(self.posicionar_arte)

    def posicionar_arte(self):
        """A arte ocupa só o espaço livre do cartão em destaque: à direita dos textos, acima do botão."""
        arte = self.arte_inicio
        if not arte.winfo_exists():
            return
        cartao = arte.master
        _faixa, titulo, descricao, botao = self.partes_inicio[cartao]
        esquerda = max(titulo.winfo_x() + titulo.winfo_reqwidth(), descricao.winfo_x() + descricao.winfo_reqwidth()) + px(cartao, 24)
        topo, direita = px(cartao, 8), cartao.winfo_width()
        base = botao.winfo_y() - px(cartao, 14)
        if direita - esquerda < px(cartao, 120) or base - topo < px(cartao, 110):
            arte.place_forget()
        else:
            # bordermode='outside': as medidas partem da borda externa do quadro, sem somar o padding.
            arte.place(x=esquerda, y=topo, width=direita - esquerda, height=base - topo, bordermode='outside')

    def atualizar_aviso_atrasadas(self):
        """Varre as previsões atuais ao abrir e ao voltar ao início; nada depende de abrir a lista."""
        try:
            total = sum(situacao(r) == 'atrasada' for r in self.banco.listar())
        except sqlite3.Error:
            total = 0
        self.texto_aviso_atrasadas.set(
            '' if not total else f'{total} operação atrasada. Clique para ver.' if total == 1
            else f'{total} operações atrasadas. Clique para ver.')
