"""Abertura do banco com saída de emergência: se os dados não abrirem, a pessoa é avisada e pode restaurar um backup.

Sem isso, um banco danificado fechava o executável sem nenhuma mensagem, e a importação de backup só existe
dentro do programa. O arquivo com problema nunca é apagado: ele é renomeado ao lado dos dados.
"""
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog

import cifra
from backup import SENHA_BACKUP, BackupPreparado
from dados import Banco, VersaoMaisNova, pasta_dados


def abrir_pasta(pasta):
    try:
        if sys.platform == 'win32':
            os.startfile(pasta)
        else:
            subprocess.Popen(['xdg-open', str(pasta)])
    except OSError:
        pass  # A mensagem já mostra o caminho da pasta.


def restaurar_em_banco_novo(caminho, arquivo, senha=None):
    """Guarda o banco danificado com outro nome, cria um vazio e restaura o backup nele.

    Se a restauração falhar, o banco vazio é descartado e o arquivo original volta ao lugar.
    """
    guardado = caminho.with_name(f'gestor-danificado-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3')
    tinha_arquivo = caminho.exists()
    if tinha_arquivo:
        os.replace(caminho, guardado)
    try:
        banco = Banco(caminho)
        with BackupPreparado(arquivo, senha) as preparado:
            preparado.restaurar(banco)
        banco = Banco(caminho)
        if senha:
            # Quem acabou de digitar a senha do backup continua usando-a nos próximos.
            banco.salvar_configuracao(SENHA_BACKUP, senha)
        return banco, guardado
    except Exception:
        caminho.unlink(missing_ok=True)
        if tinha_arquivo:
            os.replace(guardado, caminho)
        raise


def abrir_banco(janela, caminho=None):
    """Abre o banco do aplicativo; em caso de falha, explica, oferece restaurar um backup e, sem ele, encerra."""
    caminho = caminho or pasta_dados() / 'gestor.sqlite3'
    try:
        return Banco(caminho)
    except VersaoMaisNova as erro:
        # Os dados estão íntegros: só falta atualizar o programa. Nada é renomeado nem restaurado.
        messagebox.showerror('Gestor de RPV', f'{erro}\n\nOs dados estão em:\n{caminho.parent}', parent=janela)
        raise SystemExit(1) from None
    except (sqlite3.Error, ValueError, OSError) as erro:
        motivo = erro if isinstance(erro, ValueError) else 'o arquivo de dados está danificado ou inacessível.'
        restaurar = messagebox.askyesno(
            'Gestor de RPV',
            f'Não foi possível abrir os dados do Gestor de RPV: {motivo}\n\n'
            'Deseja restaurar um backup agora? O arquivo atual não será apagado: ele fica guardado '
            f'com o nome "gestor-danificado-…" na pasta:\n{caminho.parent}', parent=janela)
        while restaurar:
            arquivo = filedialog.askopenfilename(parent=janela, title='Restaurar backup do Gestor de RPV',
                                                 filetypes=[('Backup do Gestor de RPV', '*.rpvbackup')])
            if not arquivo:
                break
            senha = None
            if cifra.cifrado(arquivo):
                senha = simpledialog.askstring('Gestor de RPV', 'Digite a senha deste backup:', show='•', parent=janela)
                if senha is None:
                    continue
            try:
                banco, guardado = restaurar_em_banco_novo(caminho, arquivo, senha)
            except (sqlite3.Error, ValueError, OSError) as falha:
                restaurar = messagebox.askretrycancel('Gestor de RPV', f'Não foi possível restaurar o backup: {falha}',
                                                      parent=janela)
                continue
            messagebox.showinfo('Gestor de RPV', 'Backup restaurado. O arquivo com problema foi guardado como '
                                f'"{guardado.name}".', parent=janela)
            return banco
        messagebox.showinfo('Gestor de RPV', 'O programa será fechado. Os dados ficam nesta pasta, que será aberta '
                            f'agora:\n{caminho.parent}', parent=janela)
        abrir_pasta(caminho.parent)
        raise SystemExit(1) from None
