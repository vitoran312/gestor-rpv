"""Marca e recursos locais, também disponíveis dentro do executável."""
import sys
from pathlib import Path
import tkinter as tk


RECURSOS = Path(__file__).resolve().parent / 'recursos'


def preparar_windows():
    """Agrupa as janelas com a marca do aplicativo na barra de tarefas."""
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VitoranTech.GestorRPV')


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
