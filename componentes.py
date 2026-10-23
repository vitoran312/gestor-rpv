"""Componentes de interface, sem dependências externas."""
from tema import cores
import calendar
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from dados import moeda, centavos


def centralizar(janela, largura=None, altura=None):
    if not janela.winfo_exists():
        return
    janela.update_idletasks()
    tela_largura = janela.winfo_screenwidth()
    tela_altura = janela.winfo_screenheight()
    largura = min(largura or janela.winfo_reqwidth(), max(320, tela_largura - 80))
    altura = min(altura or janela.winfo_reqheight(), max(300, tela_altura - 100))
    x = max(0, (tela_largura - largura) // 2)
    y = max(0, (tela_altura - altura) // 2)
    janela.geometry(f'{largura}x{altura}+{x}+{y}')


def maximizar(janela):
    try:
        janela.state('zoomed')  # Windows
    except tk.TclError:
        try:
            janela.attributes('-zoomed', True)  # Linux
        except tk.TclError:
            centralizar(janela, janela.winfo_screenwidth() - 80,
                        janela.winfo_screenheight() - 100)


def formatar_digitacao_moeda(texto):
    """Números sem separadores são centavos; valores formatados podem ser colados."""
    texto = texto.strip()
    if not texto:
        return moeda(0)
    if texto.isascii() and texto.isdigit():
        valor = int(texto)
        if valor > 99999999999999:
            raise ValueError('Valor acima do limite permitido.')
        return moeda(valor)
    return moeda(centavos(texto))


class CampoMoeda(ttk.Frame):
    def __init__(self, pai, variavel):
        super().__init__(pai, style='Dinheiro.TFrame', padding=(8, 1))
        self.variavel = variavel
        # A variável pública contém reais formatados, prontos para persistência.
        variavel.set(moeda(centavos(variavel.get() or '0')))
        ttk.Label(self, text='R$', style='Dinheiro.TLabel').pack(side='left')
        self.entrada = ttk.Entry(self, textvariable=variavel, justify='right', width=26)
        self.entrada.pack(side='left', fill='x', expand=True)
        self.entrada.bind('<KeyPress>', self.tecla)
        self.entrada.bind('<<Paste>>', self.colar)
        self.entrada.bind('<<Cut>>', self.recortar)
        self.entrada.bind('<FocusOut>', self.formatar)
        self.entrada.bind('<FocusIn>', self.selecionar)

    def selecionar(self, _evento=None):
        self.entrada.selection_range(0, tk.END)

    def editar(self, acao, inserir=''):
        texto = self.variavel.get()
        if inserir and not any(c in '123456789' for c in texto):
            self.entrada.selection_range(0, tk.END)
        inicio = self.entrada.index('insert')
        fim = inicio
        selecionado = self.entrada.selection_present()
        if selecionado:
            inicio = self.entrada.index('sel.first')
            fim = self.entrada.index('sel.last')
        antes = sum(c.isdigit() for c in texto[:inicio])
        depois = sum(c.isdigit() for c in texto[:fim])
        digitos = ''.join(c for c in texto if c.isdigit())
        if selecionado:
            digitos = digitos[:antes] + digitos[depois:]
        elif acao == 'BackSpace' and antes:
            digitos = digitos[:antes-1] + digitos[antes:]
            antes -= 1
        elif acao == 'Delete':
            digitos = digitos[:antes] + digitos[antes+1:]
        digitos = digitos[:antes] + inserir + digitos[antes:]
        posicao = antes + len(inserir)
        direita = len(digitos) - posicao
        try:
            novo = formatar_digitacao_moeda(digitos)
        except ValueError:
            self.entrada.bell()
            return 'break'
        self.variavel.set(novo)
        self.entrada.selection_clear()
        cursor = len(novo)
        if direita:
            vistos = 0
            for indice in range(len(novo)-1, -1, -1):
                if novo[indice].isdigit():
                    vistos += 1
                if vistos == direita:
                    cursor = indice
                    break
        self.entrada.icursor(cursor)
        return 'break'

    def tecla(self, evento):
        if evento.keysym in ('BackSpace', 'Delete'):
            return self.editar(evento.keysym)
        if evento.char in '0123456789' and evento.char:
            return self.editar('Inserir', evento.char)
        if evento.char and evento.char.isprintable():
            return 'break'

    def colar(self, _evento=None):
        try:
            texto = self.entrada.clipboard_get().strip()
            valor = formatar_digitacao_moeda(texto)
        except (tk.TclError, ValueError):
            self.entrada.bell()
            return 'break'
        return self.editar('Inserir', ''.join(c for c in valor if c.isdigit()).lstrip('0') or '0')

    def recortar(self, _evento=None):
        if self.entrada.selection_present():
            texto = self.variavel.get()[self.entrada.index('sel.first'):self.entrada.index('sel.last')]
            self.entrada.clipboard_clear()
            self.entrada.clipboard_append(texto)
            self.editar('Delete')
        return 'break'

    def formatar(self, _evento=None):
        try:
            self.variavel.set(moeda(centavos(self.variavel.get())))
        except ValueError:
            pass


class CampoData(ttk.Frame):
    MESES = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')

    def __init__(self, pai, variavel):
        super().__init__(pai)
        self.variavel = variavel
        self.calendario = None
        self.entrada = ttk.Entry(self, textvariable=variavel, width=25)
        self.entrada.pack(side='left', fill='x', expand=True)
        self.botao = ttk.Button(self, text='▦', width=3, command=self.abrir)
        self.botao.pack(side='left', padx=(5, 0))

    def habilitar(self, ativo):
        estado = '!disabled' if ativo else 'disabled'
        self.entrada.state([estado])
        self.botao.state([estado])
        if not ativo and self.calendario is not None and self.calendario.winfo_exists():
            self.fechar()

    def abrir(self):
        if self.botao.instate(['disabled']):
            return
        if self.calendario is not None and self.calendario.winfo_exists():
            self.calendario.lift()
            return
        try:
            escolhida = datetime.strptime(self.variavel.get(), '%d/%m/%Y').date()
        except ValueError:
            escolhida = date.today()
        self.mes, self.ano = escolhida.month, escolhida.year
        pai = self.winfo_toplevel()
        self.calendario = tk.Toplevel(pai)
        tela = self.calendario
        tela.withdraw()
        tela.title('Selecionar data')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(pai)
        self.grab_anterior = self.grab_current()
        quadro = ttk.Frame(tela, padding=12)
        quadro.pack(fill='both', expand=True)
        barra = ttk.Frame(quadro)
        barra.pack(fill='x', pady=(0, 8))
        ttk.Button(barra, text='«', width=3, command=lambda: self.mover(-12)).pack(side='left')
        ttk.Button(barra, text='‹', width=3, command=lambda: self.mover(-1)).pack(side='left')
        self.titulo = ttk.Label(barra, width=22, anchor='center')
        self.titulo.pack(side='left', fill='x', expand=True)
        ttk.Button(barra, text='›', width=3, command=lambda: self.mover(1)).pack(side='left')
        ttk.Button(barra, text='»', width=3, command=lambda: self.mover(12)).pack(side='left')
        self.dias = ttk.Frame(quadro)
        self.dias.pack(fill='both', expand=True)
        rodape = ttk.Frame(quadro)
        rodape.pack(fill='x', pady=(10, 0))
        ttk.Button(rodape, text='Hoje', command=lambda: self.selecionar(date.today())).pack(side='left')
        ttk.Button(rodape, text='Cancelar', command=self.fechar).pack(side='right')
        tela.protocol('WM_DELETE_WINDOW', self.fechar)
        tela.bind('<Escape>', lambda _: self.fechar())
        self.desenhar()
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()
        tela.focus_set()

    def mover(self, quantidade):
        indice = (self.ano - 1) * 12 + self.mes - 1 + quantidade
        if 0 <= indice < 9999 * 12:
            self.ano, mes = divmod(indice, 12)
            self.ano += 1
            self.mes = mes + 1
            self.desenhar()

    def desenhar(self):
        for widget in self.dias.winfo_children():
            widget.destroy()
        self.titulo.config(text=f'{self.MESES[self.mes - 1]} {self.ano}')
        for coluna, dia in enumerate(('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')):
            ttk.Label(self.dias, text=dia, anchor='center').grid(row=0, column=coluna, sticky='ew', pady=5)
        semanas = calendar.monthcalendar(self.ano, self.mes)
        semanas += [[0] * 7 for _ in range(6 - len(semanas))]
        for linha, semana in enumerate(semanas, 1):
            for coluna, dia in enumerate(semana):
                if dia:
                    valor = date(self.ano, self.mes, dia)
                    estilo = 'DiaSelecionado.TButton' if self.variavel.get() == valor.strftime('%d/%m/%Y') else 'TButton'
                    ttk.Button(self.dias, text=str(dia), width=3, style=estilo,
                               command=lambda d=valor: self.selecionar(d)).grid(row=linha, column=coluna, padx=2, pady=2)
                else:
                    ttk.Label(self.dias, text='', width=3).grid(row=linha, column=coluna, padx=2, pady=2)
            self.dias.rowconfigure(linha, minsize=42)

    def selecionar(self, valor):
        self.variavel.set(valor.strftime('%d/%m/%Y'))
        self.fechar()

    def fechar(self):
        self.calendario.grab_release()
        self.calendario.destroy()
        if self.grab_anterior is not None and self.grab_anterior.winfo_exists():
            self.grab_anterior.grab_set()
        self.focus_set()
        return 'break'
