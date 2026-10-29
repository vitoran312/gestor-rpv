"""Barra lateral da janela principal: marca, Nova entrada, navegação entre as páginas e ações de dados.

Fica sempre visível, à esquerda de qualquer página (as páginas continuam numa pilha; veja navegacao.py).
Cada item chama as mesmas ações dos cartões e menus; nada aqui decide regras. Em janelas estreitas, recolhe
para só os ícones, com o nome num balão ao passar o mouse. O item da página à frente fica aceso, com um
filete champanhe que desliza até ele (200 ms, ease-out).
"""
import tkinter as tk
from tkinter import ttk

from componentes import BalaoAjuda
from movimento import animar
from tema import cores
from versao import VERSAO
from visual import icone_navegacao, px

LARGURA = 236
RECOLHIDA = 76
LIMITE_RECOLHER = 1240  # Largura da janela (a 100% de escala) abaixo da qual a barra mostra só os ícones.
TITULOS_PAGINAS = {'Minhas operações': 'historico', 'Contas de recebimento': 'contas', 'Gráfico mensal': 'grafico'}


class BarraLateral(ttk.Frame):
    def __init__(self, aplicativo):
        super().__init__(aplicativo.janela, style='Lateral.TFrame', padding=(px(aplicativo.janela, 14), px(aplicativo.janela, 18),
                                                                            px(aplicativo.janela, 14), px(aplicativo.janela, 16)))
        self.app = aplicativo
        self.recolhida = False
        self.ativo = None
        self.y_indicador = None
        self.icones = {}  # botão -> nome do ícone
        self.textos = {}  # botão -> texto completo
        janela = aplicativo.janela

        marca = ttk.Frame(self, style='Lateral.TFrame')
        marca.pack(fill='x', pady=(0, px(self, 22)))
        self.emblema = ttk.Label(marca, image=janela._icones_vitoran[2], style='LateralMarca.TLabel')
        self.emblema.pack(side='left')
        self.textos_marca = ttk.Frame(marca, style='Lateral.TFrame')
        self.textos_marca.pack(side='left', padx=(px(self, 10), 0))
        ttk.Label(self.textos_marca, text='Gestor RPV', style='LateralMarca.TLabel').pack(anchor='w')
        ttk.Label(self.textos_marca, text='Vitoran Tech', style='LateralEmpresa.TLabel').pack(anchor='w')

        self.nova = self.botao('nova', 'Nova entrada', aplicativo.formulario, estilo='Acento.TButton')
        self.nova.pack(fill='x', pady=(0, px(self, 24)))

        self.secoes = [self.secao('PÁGINAS')]
        self.itens = {}
        for chave, icone, texto, acao in (('inicio', 'inicio', 'Início', self.ir_ao_inicio),
                                          ('historico', 'operacoes', 'Minhas operações', aplicativo.mostrar_historico),
                                          ('contas', 'contas', 'Contas de recebimento', aplicativo.mostrar_contas),
                                          ('grafico', 'grafico', 'Gráfico mensal', aplicativo.mostrar_grafico)):
            self.itens[chave] = self.botao(icone, texto, acao)
            self.itens[chave].pack(fill='x', pady=1)
            # Quando o item ganha posição (janela aberta, barra recolhida ou expandida), o filete o acompanha.
            self.itens[chave].bind('<Configure>', lambda _, k=chave: self.marcar(k, animado=False) if self.ativo == k else None,
                                   add='+')
        self.secoes.append(self.secao('FERRAMENTAS', topo=px(self, 22)))
        for icone, texto, acao in (('calculadora', 'Calculadora', aplicativo.abrir_calculadora),
                                   ('backup', 'Fazer backup', aplicativo.exportar_backup),
                                   ('exportar', 'Exportar para Excel', aplicativo.exportar_excel)):
            self.botao(icone, texto, acao).pack(fill='x', pady=1)

        rodape = ttk.Frame(self, style='Lateral.TFrame')
        rodape.pack(side='bottom', fill='x')
        aplicativo.texto_alternar_tema = tk.StringVar()
        aplicativo.botao_alternar_tema = ttk.Button(rodape, textvariable=aplicativo.texto_alternar_tema,
                                                    command=aplicativo.alternar_tema, style='Lateral.TButton', compound='left')
        aplicativo.botao_alternar_tema.pack(fill='x', pady=1)
        self.textos[aplicativo.botao_alternar_tema] = None  # O texto vem da variável (Modo escuro / Modo claro).
        aplicativo.botao_sobre = self.botao('sobre', 'Sobre', aplicativo.mostrar_sobre, pai=rodape)
        aplicativo.botao_sobre.pack(fill='x', pady=1)
        aplicativo.botao_sair = self.botao('sair', 'Sair', aplicativo.fechar_programa, pai=rodape)
        aplicativo.botao_sair.pack(fill='x', pady=1)
        self.versao = ttk.Label(rodape, text=f'Versão {VERSAO}', style='LateralEmpresa.TLabel')
        self.versao.pack(anchor='w', padx=px(self, 14), pady=(px(self, 10), 0))
        BalaoAjuda(aplicativo.botao_alternar_tema, 'Alternar entre os temas claro e escuro', condicao=lambda: self.recolhida)

        # Filete do item ativo, colado à esquerda da barra.
        self.indicador = ttk.Frame(self, style='LateralIndicador.TFrame', width=px(self, 3))
        janela.bind('<Configure>', self.ajustar_largura, add='+')
        self.configure(width=px(self, LARGURA))
        self.atualizar_tema()

    def secao(self, texto, topo=0):
        rotulo = ttk.Label(self, text=texto, style='LateralSecao.TLabel')
        rotulo.pack(anchor='w', padx=px(self, 14), pady=(topo, px(self, 6)))
        return rotulo

    def botao(self, icone, texto, acao, estilo='Lateral.TButton', pai=None):
        botao = ttk.Button(pai or self, text=texto, command=acao, style=estilo,
                           compound='left', takefocus=True)
        self.icones[botao] = icone
        self.textos[botao] = texto
        BalaoAjuda(botao, texto, condicao=lambda: self.recolhida)
        return botao

    def ir_ao_inicio(self):
        while self.app.paginas:
            self.app.paginas[-1].destroy()

    def atualizar_tema(self):
        c = cores()
        raiz = self._root()
        for botao, icone in self.icones.items():
            if not botao.winfo_exists():
                continue
            if str(botao.cget('style')) == 'Acento.TButton':
                botao.configure(image=icone_navegacao(raiz, icone, c['acento_texto']))
            else:
                apagado, aceso = icone_navegacao(raiz, icone, c['heroi_secundario']), icone_navegacao(raiz, icone, c['heroi_texto'])
                botao.configure(image=(apagado, 'selected', aceso, 'active', aceso))
        self.app.atualizar_alternador_tema()

    def ajustar_largura(self, evento):
        if evento.widget is not self.app.janela:
            return
        recolher = evento.width < px(self, LIMITE_RECOLHER)
        if recolher == self.recolhida:
            return
        self.recolhida = recolher
        for botao, texto in self.textos.items():
            if botao.winfo_exists():
                botao.configure(compound='image' if recolher else 'left')
        self.nova.configure(text='' if recolher else 'Nova entrada', compound='image' if recolher else 'left')
        for widget in (self.textos_marca, self.versao, *self.secoes):
            if recolher:
                widget.pack_forget()
            elif widget is self.textos_marca:
                widget.pack(side='left', padx=(px(self, 10), 0))
        if not recolher:
            self.versao.pack(anchor='w', padx=px(self, 14), pady=(px(self, 10), 0))
            # As seções voltam no lugar: antes do primeiro item de cada grupo.
            self.secoes[0].pack(anchor='w', padx=px(self, 14), pady=(0, px(self, 6)), before=self.itens['inicio'])
            primeiro_ferramenta = next(b for b, i in self.icones.items() if i == 'calculadora')
            self.secoes[1].pack(anchor='w', padx=px(self, 14), pady=(px(self, 22), px(self, 6)), before=primeiro_ferramenta)
        self.configure(width=px(self, RECOLHIDA if recolher else LARGURA))

    def marcar(self, chave, animado=True):
        """Acende o item da página à frente e leva o filete até ele."""
        self.ativo = chave
        for nome, botao in self.itens.items():
            botao.state(['selected'] if nome == chave else ['!selected'])
        botao = self.itens.get(chave)
        if botao is None or not botao.winfo_manager() or botao.winfo_height() <= 1:
            self.indicador.place_forget()
            self.y_indicador = None
            return
        destino = botao.winfo_y()
        altura = botao.winfo_height()
        origem = self.y_indicador if (animado and self.y_indicador is not None) else destino

        self.animacao = getattr(self, 'animacao', 0) + 1
        animacao = self.animacao  # Um clique novo antes do fim cancela o deslizamento anterior.

        def mover(efeito):
            if animacao != self.animacao:
                return
            y = round(origem + (destino - origem) * efeito)
            self.indicador.place(x=px(self, 4), y=y + px(self, 9), width=px(self, 3), height=max(1, altura - px(self, 18)))
            self.indicador.lift()
        self.y_indicador = destino
        animar(self.indicador, 200, mover)

    def pagina_mudou(self, pagina, inicio):
        chave = 'inicio' if pagina is inicio else TITULOS_PAGINAS.get(getattr(pagina, 'titulo_pagina', ''))
        self.marcar(chave)
