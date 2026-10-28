"""Calculadora de quatro operações, sem eval nem dependências externas."""
import tkinter as tk
from decimal import Decimal, DecimalException, localcontext
from tkinter import ttk

from componentes import centralizar
from tema import cores
from visual import familia_fonte


class MotorCalculadora:
    def __init__(self):
        self.limpar()

    def limpar(self):
        self.texto = '0'
        self.acumulado = None
        self.operacao = None
        self.novo = True
        self.erro = False
        self.repetir = None
        self.exato = None  # Resultado com todas as casas; o visor mostra só 12 dígitos.

    def valor(self):
        # O próximo cálculo usa o resultado exato, e não o arredondado do visor: 1 ÷ 3 × 3 dá 1.
        return self.exato if self.exato is not None else Decimal(self.texto.replace(',', '.'))

    def mostrar(self, valor):
        if not valor.is_finite():
            raise ArithmeticError
        exato = valor
        with localcontext() as contexto:
            contexto.prec = 12
            valor = +valor
        if valor.adjusted() >= 12:
            raise OverflowError  # Mais de 12 dígitos inteiros não cabem no visor.
        if valor == 0 or valor.adjusted() <= -8:
            texto, exato = '0', Decimal(0)
        else:
            texto = format(valor, 'f')
            if '.' in texto:
                texto = texto.rstrip('0').rstrip('.')
        self.texto = texto.replace('.', ',')
        self.exato = exato

    @staticmethod
    def calcular(a, b, operacao):
        with localcontext() as contexto:
            contexto.prec = 28
            if operacao == '+':
                return a + b
            if operacao == '−':
                return a - b
            if operacao == '×':
                return a * b
            if operacao == '÷':
                if b == 0:
                    raise ZeroDivisionError
                return a / b
        raise ArithmeticError

    def clicar(self, tecla):
        if tecla == 'C':
            self.limpar()
            return
        if self.erro:
            if tecla in '0123456789' or tecla == ',':
                self.limpar()
            else:
                return
        if tecla in '0123456789,⌫±':
            self.exato = None  # Ao editar o visor, vale o número digitado.
        try:
            if tecla in '0123456789':
                if self.novo:
                    self.texto = tecla
                    if self.operacao is None:
                        self.repetir = None
                elif self.texto in ('0', '-0'):
                    self.texto = ('-' if self.texto.startswith('-') else '') + tecla
                elif len([c for c in self.texto if c.isdigit()]) < 12:
                    self.texto += tecla
                self.novo = False
            elif tecla == ',':
                if self.novo:
                    self.texto = '0,'
                    self.repetir = None
                    self.novo = False
                elif ',' not in self.texto and 'E' not in self.texto:
                    self.texto += ','
            elif tecla == '⌫' and not self.novo:
                self.texto = '0' if 'E' in self.texto else self.texto[:-1]
                if self.texto in ('', '-'):
                    self.texto = '0'
            elif tecla == '±':
                if self.novo and self.operacao is not None:
                    self.texto = '0'
                if self.texto != '0':  # Zero não tem sinal; o visor nunca mostra "-0".
                    self.texto = self.texto[1:] if self.texto.startswith('-') else '-' + self.texto
                self.novo = False
            elif tecla == '%':
                valor = self.valor() / Decimal(100)
                if self.operacao in ('+', '−') and self.acumulado is not None:
                    valor *= self.acumulado
                self.mostrar(valor)
                self.novo = False
            elif tecla in ('+', '−', '×', '÷'):
                if self.operacao and not self.novo:
                    self.mostrar(self.calcular(self.acumulado, self.valor(), self.operacao))
                self.acumulado = self.valor()
                self.operacao = tecla
                self.novo = True
                self.repetir = None
            elif tecla == '=':
                if self.operacao:
                    # "5 + =" repete o primeiro número (dá 10), como nas calculadoras comuns.
                    segundo = self.acumulado if self.novo else self.valor()
                    self.mostrar(self.calcular(self.acumulado, segundo, self.operacao))
                    self.repetir = (self.operacao, segundo)
                    self.operacao = None
                    self.acumulado = None
                    self.novo = True
                elif self.repetir and self.operacao is None:
                    operacao, segundo = self.repetir
                    self.mostrar(self.calcular(self.valor(), segundo, operacao))
                    self.novo = True
        except ZeroDivisionError:
            self.limpar()
            self.texto = 'Não divide por zero'
            self.erro = True
        except OverflowError:
            self.limpar()
            self.texto = 'Número grande demais'
            self.erro = True
        except (DecimalException, ArithmeticError, ValueError):
            self.limpar()
            self.texto = 'Erro'
            self.erro = True


class JanelaCalculadora:
    def __init__(self, pai):
        self.motor = MotorCalculadora()
        self.tela = tk.Toplevel(pai)
        self.tela.withdraw()
        self.tela.title('Calculadora')
        self.tela.configure(bg=cores()['fundo'])
        self.tela.resizable(False, False)
        corpo = ttk.Frame(self.tela, padding=15)
        corpo.pack(fill='both', expand=True)
        self.texto = tk.StringVar(value='0')
        ttk.Entry(corpo, textvariable=self.texto, state='readonly', justify='right',
                  font=(familia_fonte(pai), 24, 'bold'), width=24).pack(fill='x', ipady=12, pady=(0, 12))
        painel = ttk.Frame(corpo)
        painel.pack(fill='both', expand=True)
        teclas = (('C', '⌫', '%', '÷'), ('7', '8', '9', '×'),
                  ('4', '5', '6', '−'), ('1', '2', '3', '+'), ('±', '0', ',', '='))
        for linha, grupo in enumerate(teclas):
            painel.rowconfigure(linha, weight=1)
            for coluna, tecla in enumerate(grupo):
                ttk.Button(painel, text=tecla, style='Resultado.Calculadora.TButton' if tecla == '=' else 'Calculadora.TButton', width=4,
                           command=lambda t=tecla: self.clicar(t)).grid(row=linha, column=coluna,
                                    sticky='nsew', padx=3, pady=3)
        for coluna in range(4):
            painel.columnconfigure(coluna, weight=1)
        self.tela.bind('<KeyPress>', self.teclado)
        centralizar(self.tela, 370, 480)
        self.tela.deiconify()
        self.tela.focus_set()

    def clicar(self, tecla):
        self.motor.clicar(tecla)
        self.texto.set(self.motor.texto)

    def teclado(self, evento):
        atalhos = {'Return': '=', 'KP_Enter': '=', 'BackSpace': '⌫', 'Escape': 'C', 'Delete': 'C'}
        caracteres = {'.': ',', ',': ',', '+': '+', '-': '−', '*': '×', '/': '÷', '%': '%', '=': '=', 'c': 'C', 'C': 'C'}
        tecla = atalhos.get(evento.keysym)
        if tecla is None:
            tecla = evento.char if evento.char and evento.char in '0123456789' else caracteres.get(evento.char)
        if tecla is not None:
            self.clicar(tecla)
            return 'break'
