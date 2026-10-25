"""Marca e recursos locais, também disponíveis dentro do executável."""
import sys
from pathlib import Path
import tkinter as tk


RECURSOS = Path(__file__).resolve().parent / 'recursos'


def preparar_windows():
    """Agrupa as janelas na barra de tarefas e desenha o texto na resolução real da tela.

    Sem declarar suporte a DPI, o Windows desenha o programa em 100% e estica a imagem quando a escala
    da tela é 125% ou 150%, deixando as letras borradas ou serrilhadas. Precisa rodar antes de criar o Tk.
    """
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VitoranTech.GestorRPV')
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Escala do sistema (Windows 8.1 ou mais novo).
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()  # Windows mais antigo.
            except (AttributeError, OSError):
                pass


def aplicar_icone(raiz):
    imagens = [tk.PhotoImage(master=raiz,file=str(RECURSOS/f'vitoran-{lado}.png'))
               for lado in (256,64,32)]
    raiz._icones_vitoran = imagens
    raiz._marca_vitoran = tk.PhotoImage(master=raiz,file=str(RECURSOS/'vitoran-128.png'))
    raiz._marca_cabecalho = tk.PhotoImage(master=raiz,file=str(RECURSOS/'vitoran-cabecalho.png'))
    # Versão com 50% de opacidade já gravada no PNG para acompanhar a assinatura.
    raiz._marca_rodape = tk.PhotoImage(master=raiz,file=str(RECURSOS/'vitoran-rodape.png'))
    raiz.iconphoto(True,*imagens)
    if sys.platform == 'win32':
        raiz.iconbitmap(default=str(RECURSOS/'vitoran-tech.ico'))
