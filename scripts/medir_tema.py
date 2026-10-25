"""Mede, etapa por etapa, quanto tempo a troca de tema leva; o CI publica os números como anotações."""
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ['LOCALAPPDATA'] = tempfile.mkdtemp(prefix='gestor-medir-tema-')

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

import app  # noqa: E402
import tema  # noqa: E402
from identidade import preparar_windows  # noqa: E402


def ms(inicio):
    return round((time.perf_counter() - inicio) * 1000)


def contar(widget):
    return 1 + sum(contar(filho) for filho in widget.children.values())


def medir(programa, janela, rotulo, linhas):
    janela.update()
    totais = []
    for _ in range(4):
        inicio = time.perf_counter()
        programa.alternar_tema()
        janela.update_idletasks()
        janela.update()
        totais.append(ms(inicio))
    # Etapas separadas da troca, na mesma ordem de configurar_tema.
    estilo = ttk.Style(janela)
    modo = 'escuro' if programa.modo_tema.get() == 'claro' else 'claro'
    programa.modo_tema.set(modo)
    tema.definir_modo(modo)
    inicio = time.perf_counter()
    estilo.theme_use('VitoranPro' + modo.title())
    etapa_tema = ms(inicio)
    inicio = time.perf_counter()
    janela.update_idletasks()
    etapa_layout = ms(inicio)
    inicio = time.perf_counter()
    tema.atualizar_widgets(janela)
    etapa_widgets = ms(inicio)
    inicio = time.perf_counter()
    janela.update()
    etapa_desenho = ms(inicio)
    linhas.append(f'{rotulo}: trocas {totais} ms | theme_use {etapa_tema} · layout {etapa_layout} · '
                  f'atualizar_widgets {etapa_widgets} · desenho {etapa_desenho} ms | {contar(janela)} widgets')


def main():
    preparar_windows()
    janela = tk.Tk()
    inicio = time.perf_counter()
    programa = app.Aplicativo(janela)
    janela.update()
    linhas = [f'Abertura: {ms(inicio)} ms · Tk {janela.tk.call("info", "patchlevel")} · '
              f'escala {janela.winfo_fpixels("1i") / 96:.2f}']
    programa.preparar_outro_tema()
    medir(programa, janela, 'Início', linhas)
    programa.mostrar_historico()
    medir(programa, janela, 'Minhas operações', linhas)
    programa.voltar()
    programa.mostrar_contas()
    medir(programa, janela, 'Contas', linhas)
    janela.destroy()
    for linha in linhas:
        print(linha, flush=True)
        if os.environ.get('GITHUB_ACTIONS'):
            print(f'::notice title=Tema::{linha}', flush=True)


if __name__ == '__main__':
    main()
