"""Abertura de documentos locais pelo programa padrão do sistema."""
import os
import subprocess
import sys
from pathlib import Path

EXTENSOES = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'}


def validar_anexo(caminho):
    caminho = Path(caminho).resolve()
    if not caminho.is_file() or caminho.suffix.lower() not in EXTENSOES:
        raise ValueError('Selecione um PDF ou imagem válido e disponível neste computador.')
    return caminho


def abrir_arquivo(caminho):
    caminho = validar_anexo(caminho)
    _abrir_no_sistema(caminho)


def abrir_pasta(caminho):
    caminho = Path(caminho).resolve()
    if not caminho.is_dir():
        raise ValueError('A pasta de documentos não está disponível neste computador.')
    _abrir_no_sistema(caminho)


def _abrir_no_sistema(caminho):
    if os.name == 'nt':
        os.startfile(str(caminho))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(caminho)])
    else:
        subprocess.Popen(['xdg-open', str(caminho)])
