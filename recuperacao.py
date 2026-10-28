"""Abertura do banco com saída de emergência: se os dados não abrirem, a pessoa é avisada e pode restaurar um backup.

A importação de backup comum só existe dentro do programa; por isso a restauração também é oferecida aqui,
antes de a janela principal abrir. Nada é apagado: o banco com problema e a pasta de anexos que estava com ele
são renomeados ao lado dos dados.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog

import cifra
from backup import BackupPreparado, SenhaNecessaria, salvar_senha
from dados import Banco, VersaoMaisNova, pasta_dados
from mensagens import descrever_erro
from diario import log

TITULO = 'Gestor de RPV'


def abrir_pasta(pasta):
    try:
        if sys.platform == 'win32':
            os.startfile(pasta)
        else:
            subprocess.Popen(['xdg-open', str(pasta)])
    except OSError:
        log.warning('Pasta dos dados não aberta; a mensagem já mostra o caminho.', exc_info=True)


def restaurar_em_banco_novo(caminho, arquivo, senha=None):
    """Guarda o banco danificado e os anexos dele com outro nome, cria um banco vazio e restaura o backup nele.

    Devolve o banco restaurado e o nome com que o arquivo danificado foi guardado. Se a restauração falhar,
    o banco vazio e os anexos do backup são descartados e o banco e os anexos originais voltam ao lugar.
    """
    marca = f'{datetime.now():%Y%m%d-%H%M%S-%f}'
    guardado = caminho.with_name(f'gestor-danificado-{marca}.sqlite3')
    documentos, documentos_guardados = caminho.parent / 'documentos', caminho.parent / f'documentos-danificado-{marca}'
    tinha_arquivo, tinha_documentos = caminho.exists(), documentos.exists()
    if tinha_arquivo:
        os.replace(caminho, guardado)
    if tinha_documentos:
        os.replace(documentos, documentos_guardados)
    try:
        with BackupPreparado(arquivo, senha, pasta_trabalho=caminho.parent) as preparado:
            # O banco vazio criado aqui não merece cópia de segurança: os dados antigos já estão guardados acima.
            preparado.restaurar(Banco(caminho), copia_de_seguranca=False)
        banco = Banco(caminho)
        if senha:
            # Quem acabou de digitar a senha do backup continua usando-a nos próximos.
            try:
                salvar_senha(banco, senha)
            except ValueError:
                log.info('Senha do backup restaurado fora das regras atuais; será pedida uma nova.')
        return banco, guardado
    except Exception:
        caminho.unlink(missing_ok=True)
        shutil.rmtree(documentos, ignore_errors=True)
        if tinha_arquivo:
            os.replace(guardado, caminho)
        if tinha_documentos:
            os.replace(documentos_guardados, documentos)
        raise


def danificado(caminho):
    """Arquivo de dados vazio (por exemplo, cortado por uma sincronização) também é tratado como danificado."""
    return caminho.exists() and caminho.stat().st_size == 0


def pedir_backup(janela):
    """Escolhe o arquivo e, se ele for protegido, a senha. Devolve (arquivo, senha) ou None se a pessoa desistir."""
    arquivo = filedialog.askopenfilename(parent=janela, title='Restaurar backup do Gestor de RPV',
                                         filetypes=[('Backup do Gestor de RPV', '*.rpvbackup')])
    if not arquivo:
        return None
    try:
        protegido = cifra.cifrado(arquivo)
    except OSError as erro:
        messagebox.showerror(TITULO, f'Não foi possível ler o arquivo escolhido: {descrever_erro(erro)}', parent=janela)
        return pedir_backup(janela)
    senha = None
    if protegido:
        senha = simpledialog.askstring(TITULO, 'Digite a senha deste backup:', show='•', parent=janela)
        if senha is None:
            return pedir_backup(janela)
    return arquivo, senha


def abrir_banco(janela, caminho=None):
    """Abre o banco do aplicativo; em caso de falha, explica, oferece restaurar um backup e, sem ele, encerra."""
    caminho = caminho or pasta_dados() / 'gestor.sqlite3'
    try:
        if danificado(caminho):
            raise ValueError('o arquivo de dados está vazio.')
        return Banco(caminho)
    except VersaoMaisNova as erro:
        # Os dados estão íntegros: só falta atualizar o programa. Nada é renomeado nem restaurado.
        messagebox.showerror(TITULO, f'{erro}\n\nOs dados estão em:\n{caminho.parent}', parent=janela)
        raise SystemExit(1) from None
    except (sqlite3.Error, ValueError, OSError) as erro:
        log.error('Banco de dados não abriu.', exc_info=True)
        motivo = erro if isinstance(erro, ValueError) else 'o arquivo de dados está danificado ou inacessível.'
        escolha = messagebox.askyesno(
            TITULO,
            f'Não foi possível abrir os dados do Gestor de RPV: {motivo}\n\n'
            'Deseja restaurar um backup agora? Se restaurar, o arquivo atual e os anexos dele não são apagados: '
            f'ficam guardados com o nome "...-danificado-..." na pasta:\n{caminho.parent}', parent=janela)
        backup = pedir_backup(janela) if escolha else None
        while backup is not None:
            arquivo, senha = backup
            try:
                banco, guardado = restaurar_em_banco_novo(caminho, arquivo, senha)
            except SenhaNecessaria as falha:
                # Senha errada: pergunta de novo a senha, sem voltar à escolha do arquivo.
                senha = simpledialog.askstring(TITULO, f'{falha}\n\nDigite a senha deste backup:', show='•',
                                               parent=janela)
                backup = (arquivo, senha) if senha is not None else pedir_backup(janela)
                continue
            except (sqlite3.Error, ValueError, OSError) as falha:
                if not messagebox.askretrycancel(TITULO, f'Não foi possível restaurar o backup: {descrever_erro(falha)}',
                                                 parent=janela):
                    break
                backup = pedir_backup(janela)
                continue
            messagebox.showinfo(TITULO, 'Backup restaurado. O arquivo com problema e os anexos dele foram guardados '
                                f'como "{guardado.name}" e "documentos-danificado-…".', parent=janela)
            return banco
        messagebox.showinfo(TITULO, 'O programa será fechado sem alterar nada. Os dados ficam nesta pasta, que será '
                            f'aberta agora:\n{caminho.parent}', parent=janela)
        abrir_pasta(caminho.parent)
        raise SystemExit(1) from None
