"""Backup, importação, exportação e pasta dos documentos."""
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, filedialog, simpledialog, ttk

import cifra
import entradas_celular
from backup import (criar_backup, documentos_sem_arquivo, BackupPreparado, aviso_backup, executar_backup_automatico, PASTA_AUTOMATICA,
                    SenhaAusente, SenhaNecessaria, salvar_senha, senha_salva)
from componentes import centralizar, ocupado
from movimento import surgir
from visual import px
from tema import cores
from documentos import abrir_pasta
from exportacao import exportar_excel, nome_sugerido
from ordenacao import ordenar
from mensagens import descrever_erro
from diario import log


class ArquivosMixin:
    def atualizar_backup_ao_ativar(self, evento):
        if evento.widget is self.janela or evento.widget is self.historico:
            self.atualizar_ultimo_backup()

    def atualizar_ultimo_backup(self):
        quando = self.banco.ultimo_backup()
        aviso = aviso_backup(quando)
        if aviso and self.falha_backup_automatico:
            aviso = ('Defina a senha dos backups em Arquivo → Backup automático. ' if self.falha_backup_automatico == 'senha'
                     else 'O backup automático não conseguiu gravar na pasta escolhida. ') + aviso
        try:
            sumidos = len(documentos_sem_arquivo(self.banco))
        except (OSError, sqlite3.Error):
            sumidos = 0
        if sumidos:
            # O backup automático também deixa de fora o anexo sumido; sem este aviso, ninguém saberia.
            aviso = (f'{sumidos} anexo(s) sumiram da pasta de documentos e ficam fora dos backups. '
                     + (aviso or 'Clique aqui para fazer um backup.'))
        self.texto_aviso_backup.set(aviso)
        try:
            data = datetime.fromisoformat(quando).astimezone().strftime('%d/%m/%Y') if quando else 'ainda não realizado'
        except (ValueError, TypeError):
            data = 'não disponível'
        if self.texto_ultimo_backup is not None:
            automatico = ''
            if self.banco.configuracao(PASTA_AUTOMATICA):
                automatico = (' · Backup automático ativo' if senha_salva(self.banco) else
                              ' · Backup automático parado: falta criar a senha dos backups')
            self.texto_ultimo_backup.set('Último backup: ' + data + automatico)

    def verificar_backup_automatico(self, forcar=False):
        """Roda ao abrir e a cada seis horas; uma falha vira aviso discreto, sem janelas modais."""
        if not self.janela.winfo_exists():
            return None
        arquivo = None
        try:
            arquivo = executar_backup_automatico(self.banco, forcar=forcar)
            self.falha_backup_automatico = False
        except (OSError, sqlite3.Error, ValueError) as erro:
            log.warning('Backup automático não gravado.', exc_info=True)
            self.falha_backup_automatico = 'senha' if isinstance(erro, SenhaAusente) else True
            if forcar:
                raise
        finally:
            self.atualizar_ultimo_backup()
            if not forcar:
                self.agendamento_backup = self.janela.after(6 * 60 * 60 * 1000, self.verificar_backup_automatico)
        return arquivo

    def importar_entradas_celular(self, automatico=False):
        """Entradas cadastradas no app do celular (arquivos .rpvcelular na pasta do backup automático).

        Ao abrir o programa (automatico=True) só aparece algo se houver entradas novas; pelo menu, sem nada na
        pasta, a pessoa pode escolher os arquivos à mão.
        """
        if not self.janela.winfo_exists():
            return
        pai = self.janela_ativa()
        try:
            encontradas, problemas = entradas_celular.procurar(self.banco)
            if not encontradas and not problemas and not automatico:
                arquivos = filedialog.askopenfilenames(parent=pai, title='Entradas enviadas pelo app do celular',
                                                       filetypes=[('Entrada do app do celular', '*.rpvcelular')])
                if not arquivos:
                    return
                encontradas, problemas = entradas_celular.conferir(self.banco, arquivos)
        except (OSError, sqlite3.Error) as erro:
            log.warning('Entradas do celular não conferidas.', exc_info=True)
            if not automatico:
                messagebox.showerror('Entradas do celular', descrever_erro(erro), parent=pai)
            return
        aviso = ''.join(f'\n• {arquivo.name}: {mensagem}' for arquivo, mensagem in problemas[:5])
        aviso = f'\n\nNão foi possível abrir {len(problemas)} arquivo(s):{aviso}' if problemas else ''
        if not encontradas:
            if problemas and not automatico:
                messagebox.showwarning('Entradas do celular', 'Nenhuma entrada nova para importar.' + aviso, parent=pai)
            elif problemas:
                log.warning('Arquivos do celular não abertos na pasta do backup automático: %d.', len(problemas))
            return
        lista = '\n'.join('• ' + entradas_celular.resumo(e) for _, e in encontradas[:15])
        if len(encontradas) > 15:
            lista += f'\n… e mais {len(encontradas) - 15}.'
        if not messagebox.askyesno('Entradas do celular', f'Chegaram do app do celular: '
                                   f'{entradas_celular.contar(encontradas)}.\n\n{lista}{aviso}\n\nImportar agora?',
                                   parent=pai):
            return
        try:
            with ocupado(pai):
                gravadas, recusadas = entradas_celular.importar(self.banco, encontradas)
        except (OSError, sqlite3.Error) as erro:
            messagebox.showerror('Entradas do celular', 'Não foi possível importar. ' + descrever_erro(erro), parent=pai)
            return
        texto = f'{gravadas} item(ns) importado(s) do celular.'
        if recusadas:
            texto += ('\n\nNão aplicadas (entrada ou conta: corrija no celular e envie de novo; mudança numa '
                      'operação: confira e faça aqui, se ainda quiser):') + ''.join(
                f'\n• {nome}: {mensagem}' for nome, mensagem in recusadas)
        messagebox.showinfo('Entradas do celular', texto, parent=pai)
        self.atualizar()
        self.atualizar_aviso_atrasadas()
        if self.janela_contas is not None and self.janela_contas.tela.winfo_exists():
            self.janela_contas.atualizar()  # Contas novas vindas do celular já aparecem na lista aberta.

    def fechar_programa(self):
        """Fecha o programa. Com o backup automático ativo, antes grava um backup se algo mudou desde o último:
        assim a pasta (por exemplo, no Google Drive) sempre tem os dados do último uso, para o celular."""
        if self.banco.configuracao(PASTA_AUTOMATICA) and senha_salva(self.banco):
            self.janela.title('Gestor de RPV — salvando o backup…')
            self.janela.configure(cursor='watch')
            self.janela.update_idletasks()
            try:
                executar_backup_automatico(self.banco, ao_fechar=True)
            except (OSError, sqlite3.Error, ValueError) as erro:
                log.warning('Backup ao fechar não gravado.', exc_info=True)
                self.janela.title('Gestor de RPV')
                self.janela.configure(cursor='')
                if not messagebox.askyesno('Backup automático', 'Não foi possível salvar o backup antes de fechar. '
                                           + descrever_erro(erro) + '\n\nFechar mesmo assim?', parent=self.janela,
                                           icon='warning'):
                    return
        self.janela.destroy()

    def cancelar_agendamento_backup(self, evento):
        if evento.widget is not self.janela:
            return
        for nome in ('agendamento_backup', 'agendamento_data', 'agendamento_tema', 'agendamento_arte', 'agendamento_celular'):
            setattr(self, nome, None)
        # Qualquer tarefa ainda agendada (redesenhos com after_idle, relógio da animação, backup) é
        # cancelada: depois de fechar a janela, ela chamaria funções que não existem mais.
        for agendamento in self.janela.tk.splitlist(self.janela.tk.call('after', 'info')):
            self.janela.tk.call('after', 'cancel', agendamento)  # after_cancel falha com tarefas criadas pelo próprio Tk.

    def configurar_backup_automatico(self):
        pai = self.janela_ativa()
        tela = tk.Toplevel(pai)
        tela.withdraw()
        tela.title('Backup automático')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(pai)
        corpo = ttk.Frame(tela, padding=24)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text='Backup automático', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(corpo, wraplength=px(corpo, 520), justify='left', style='Subtitulo.TLabel', text=(
            'Ao fechar o programa (se algo mudou desde o último backup) e também uma vez por semana, o programa '
            'salva sozinho uma cópia completa — dados e documentos — na pasta escolhida. Prefira uma pasta '
            'sincronizada, como OneDrive ou Google Drive, para ter uma cópia fora deste computador; no Google '
            'Drive, o app do celular abre sempre o backup mais recente. As cópias são protegidas pela senha dos '
            'backups: sem ela, ninguém consegue abri-las.')).pack(anchor='w', pady=(6, 16))
        situacao = tk.StringVar()
        ttk.Label(corpo, textvariable=situacao, wraplength=px(corpo, 520), justify='left').pack(anchor='w')
        ttk.Label(corpo, wraplength=px(corpo, 520), justify='left', style='Discreto.TLabel', text=(
            'São mantidas as 10 cópias automáticas mais recentes. Backups feitos manualmente na mesma pasta '
            'não são apagados.')).pack(anchor='w', pady=(8, 20))
        botoes = ttk.Frame(corpo)
        botoes.pack(fill='x')

        def atualizar():
            pasta = self.banco.configuracao(PASTA_AUTOMATICA)
            situacao.set(f'Ativo. Pasta: {pasta}' if pasta else 'Desativado.')
            desativar.state(['!disabled' if pasta else 'disabled'])

        def escolher():
            if not self.garantir_senha_backup(tela):
                messagebox.showinfo('Backup automático', 'O backup automático não foi ativado: os backups só são '
                                    'gravados com senha. Crie a senha para ativá-lo.', parent=tela)
                return
            pasta = filedialog.askdirectory(parent=tela, title='Escolha a pasta do backup automático')
            if not pasta:
                return
            anterior = self.banco.configuracao(PASTA_AUTOMATICA)
            try:
                self.banco.salvar_configuracao(PASTA_AUTOMATICA, pasta)
                arquivo = self.verificar_backup_automatico(forcar=True)
            except (OSError, sqlite3.Error, ValueError) as erro:
                try:
                    if anterior:
                        self.banco.salvar_configuracao(PASTA_AUTOMATICA, anterior)
                    else:
                        self.banco.remover_configuracao(PASTA_AUTOMATICA)
                except sqlite3.Error:
                    log.warning('Pasta anterior do backup automático não restaurada.', exc_info=True)
                self.atualizar_ultimo_backup()
                messagebox.showerror('Backup automático', 'Não foi possível usar esta pasta. ' + descrever_erro(erro), parent=tela)
                atualizar()
                return
            atualizar()
            messagebox.showinfo('Backup automático', f'Backup automático ativado. Primeira cópia salva em:\n{arquivo}', parent=tela)

        def desativar_backup():
            try:
                self.banco.remover_configuracao(PASTA_AUTOMATICA)
            except sqlite3.Error:
                messagebox.showerror('Backup automático', 'Não foi possível desativar.', parent=tela)
                return
            self.falha_backup_automatico = False
            self.atualizar_ultimo_backup()
            atualizar()

        ttk.Button(botoes, text='Fechar', command=tela.destroy).pack(side='right')
        ttk.Button(botoes, text='Escolher pasta…', style='Principal.TButton', command=escolher).pack(side='right', padx=8)
        desativar = ttk.Button(botoes, text='Desativar', command=desativar_backup)
        desativar.pack(side='left')
        ttk.Button(botoes, text='Senha dos backups…', command=lambda: self.definir_senha_backup(tela)).pack(side='left', padx=8)
        atualizar()
        tela.bind('<Escape>', lambda _: tela.destroy())
        centralizar(tela)
        surgir(tela)
        tela.grab_set()

    def garantir_senha_backup(self, pai):
        """Os backups só saem com senha; na primeira vez, a pessoa cria a sua."""
        return bool(senha_salva(self.banco)) or self.definir_senha_backup(pai)

    def definir_senha_backup(self, pai):
        """Cria ou troca a senha dos backups. Devolve True quando uma senha foi salva."""
        atual = senha_salva(self.banco)
        modal_anterior = pai.grab_current()
        tela = tk.Toplevel(pai)
        tela.withdraw()
        tela.title('Senha dos backups')
        tela.configure(bg=cores()['fundo'])
        tela.resizable(False, False)
        tela.transient(pai)
        corpo = ttk.Frame(tela, padding=24)
        corpo.pack(fill='both', expand=True)
        ttk.Label(corpo, text='Senha dos backups', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(corpo, wraplength=px(corpo, 460), justify='left', style='Subtitulo.TLabel', text=(
            'Os backups guardam CPFs, contas e chaves Pix, por isso são protegidos por senha. Anote-a em lugar '
            'seguro: sem ela, não há como abrir os backups. A senha fica salva neste computador para o backup '
            'automático funcionar; a troca vale para os próximos backups (os anteriores continuam com a senha '
            'com que foram feitos).')).pack(anchor='w', pady=(6, 16))
        variaveis, campos = {}, []
        rotulos = ((('atual', 'Senha atual'),) if atual else ()) + (
            ('nova', f'Nova senha (pelo menos {cifra.SENHA_MINIMA} caracteres)'), ('repetida', 'Repita a nova senha'))
        for chave, rotulo in rotulos:
            ttk.Label(corpo, text=rotulo).pack(anchor='w')
            variaveis[chave] = tk.StringVar()
            campo = ttk.Entry(corpo, textvariable=variaveis[chave], show='•', width=40)
            campo.pack(fill='x', pady=(2, 12))
            campos.append(campo)
        salva = []

        def salvar(_evento=None):
            try:
                if atual and not cifra.mesma_senha(variaveis['atual'].get(), atual):
                    raise ValueError('A senha atual não confere.')
                if variaveis['nova'].get() != variaveis['repetida'].get():
                    raise ValueError('As duas senhas novas não são iguais.')
                salvar_senha(self.banco, variaveis['nova'].get())
            except (ValueError, OSError, sqlite3.Error) as erro:
                messagebox.showerror('Senha dos backups', descrever_erro(erro), parent=tela)
                return
            salva.append(True)
            if self.falha_backup_automatico == 'senha':
                self.falha_backup_automatico = False
            self.atualizar_ultimo_backup()
            tela.destroy()

        botoes = ttk.Frame(corpo)
        botoes.pack(fill='x', pady=(8, 0))
        ttk.Button(botoes, text='Salvar senha', style='Principal.TButton', command=salvar).pack(side='right')
        ttk.Button(botoes, text='Cancelar', command=tela.destroy).pack(side='right', padx=8)
        tela.bind('<Return>', salvar)
        tela.bind('<Escape>', lambda _: tela.destroy())
        centralizar(tela)
        surgir(tela)
        campos[0].focus_set()
        tela.grab_set()
        tela.wait_window()
        # A janela que estava em modo exclusivo (por exemplo, "Backup automático") volta a estar.
        if modal_anterior is not None and modal_anterior.winfo_exists():
            modal_anterior.grab_set()
        return bool(salva)

    def exportar_backup(self):
        pai = self.janela_ativa()
        if not self.garantir_senha_backup(pai):
            messagebox.showinfo('Backup', 'O backup não foi feito: os backups só são gravados com senha. '
                                'Crie a senha para fazer o backup.', parent=pai)
            return
        pasta = filedialog.askdirectory(parent=pai, title='Escolha onde salvar o backup')
        if not pasta:
            return
        try:
            with ocupado(pai):
                arquivo = criar_backup(self.banco, pasta)
        except (OSError, sqlite3.Error, ValueError) as erro:
            messagebox.showerror('Backup', 'Não foi possível criar o backup. ' + descrever_erro(erro), parent=pai)
            return
        self.atualizar_ultimo_backup()
        sumidos = len(documentos_sem_arquivo(self.banco))
        aviso = (f'\n\nAtenção: {sumidos} anexo(s) cadastrado(s) não estão mais na pasta de documentos (apagados por '
                 'fora do programa, pelo antivírus ou pela sincronização) e ficaram fora do backup. As operações e os '
                 'demais anexos foram salvos normalmente.') if sumidos else ''
        messagebox.showinfo('Backup concluído', f'Backup salvo em:\n{arquivo}{aviso}', parent=pai)

    def importar_dados(self):
        if self.janelas_de_edicao_abertas():
            messagebox.showinfo('Importar dados', 'Salve ou feche os formulários abertos (entrada, recebimento, previsão '
                                'ou conta) antes de importar um backup.', parent=self.historico)
            return
        arquivo = filedialog.askopenfilename(parent=self.historico, title='Importar backup do Gestor de RPV',
                                             filetypes=[('Backup do Gestor de RPV', '*.rpvbackup')])
        if not arquivo:
            return
        # Primeiro tenta a senha deste computador, sem perguntar; depois, a que a pessoa digitar.
        senha, digitada = senha_salva(self.banco), False
        while True:
            try:
                with ocupado(self.historico), BackupPreparado(arquivo, senha, pasta_trabalho=self.banco.caminho.parent) as pacote:
                    self.confirmar_importacao(pacote)
                return
            except SenhaNecessaria as erro:
                motivo = 'Nenhuma senha foi digitada.' if digitada and not senha else str(erro)
                pedido = (f'{motivo}\n\n' if digitada else '') + 'Digite a senha deste backup:'
                senha, digitada = simpledialog.askstring('Importar dados', pedido, show='•', parent=self.historico), True
                if senha is None:
                    return
            except (OSError, sqlite3.Error, ValueError, RuntimeError) as erro:
                messagebox.showerror('Importar dados', 'Não foi possível importar o backup. ' + descrever_erro(erro), parent=self.historico)
                return

    def janelas_de_edicao_abertas(self):
        """Janelas onde algo pode estar sendo digitado; calculadora, Sobre e lixeira não contam."""
        livres = {self.sobre, self.janela_lixeira, self.calculadora.tela if self.calculadora is not None else None}

        def toplevels(widget):
            for filho in widget.winfo_children():
                if isinstance(filho, tk.Toplevel):
                    yield filho
                yield from toplevels(filho)
        return [w for w in toplevels(self.janela) if w not in livres and w.winfo_exists()]

    def confirmar_importacao(self, pacote):
        resumo = pacote.resumo
        aviso = ''
        if not pacote.cifrado and senha_salva(self.banco):
            # Backups feitos pelo programa saem sempre com senha; um arquivo sem ela pode ter sido montado por outra
            # pessoa para trocar os dados bancários.
            aviso = ('ATENÇÃO: este backup NÃO tem senha. Os backups deste programa têm senha desde a versão 0.30.0; '
                     'só continue se tiver certeza de que o arquivo é seu e veio de uma versão antiga.\n\n')
        if not messagebox.askyesno('Importar dados', aviso +
            f"O backup contém {resumo['registros']} entrada(s), {resumo['lixeira']} na lixeira, "
            f"{resumo['contas']} conta(s) e {resumo['documentos']} documento(s).\n\n"
            + (f"{resumo['documentos_ausentes']} anexo(s) citado(s) no backup não estão dentro dele e ficarão de fora; "
               'o restante entra normalmente.\n\n' if resumo['documentos_ausentes'] else '') +
            'Ele substituirá os dados deste computador, sem juntar os históricos. '
            'Uma cópia automática dos dados atuais será salva antes. Continuar?',
            parent=self.historico, icon='warning', default='no'):
            return
        seguranca = pacote.restaurar(self.banco)
        # Formulários antigos não podem continuar editando IDs do banco substituído.
        for janela in list(self.janela.winfo_children()):
            if isinstance(janela, tk.Toplevel) and janela != self.historico and (
                self.calculadora is None or janela != self.calculadora.tela):
                janela.destroy()
        for janela in list(self.historico.winfo_children()):
            if isinstance(janela, tk.Toplevel):
                janela.destroy()
        self.reiniciar_filtros()
        messagebox.showinfo('Importação concluída', 'Dados recuperados. Backup anterior salvo em:\n' + str(seguranca),
                            parent=self.historico)

    def exportar_excel(self):
        pai = self.janela_ativa()
        registros = self.banco.listar()
        if not registros:
            messagebox.showinfo('Exportar para Excel', 'Ainda não há operações para exportar.', parent=pai)
            return
        if self.ordenacao:
            registros = ordenar(registros, *self.ordenacao)
        arquivo = filedialog.asksaveasfilename(parent=pai, title='Exportar operações para Excel',
            defaultextension='.xlsx', initialfile=nome_sugerido(), filetypes=[('Planilha do Excel', '*.xlsx')])
        if not arquivo:
            return
        try:
            with ocupado(pai):
                destino = exportar_excel(registros, arquivo)
        except (OSError, sqlite3.Error, ValueError) as erro:
            messagebox.showerror('Exportar para Excel', 'Não foi possível exportar. ' + descrever_erro(erro), parent=pai)
            return
        messagebox.showinfo('Exportação concluída',
                            f'{len(registros)} operação(ões) exportada(s) para:\n{destino}', parent=pai)

    def abrir_pasta_documentos(self):
        pai = self.janela_ativa()
        try:
            pasta = self.banco.pasta_documentos
            pasta.mkdir(parents=True, exist_ok=True)
            abrir_pasta(pasta)
        except (OSError, ValueError) as erro:
            messagebox.showerror('Abrir pasta dos documentos',
                'Não foi possível abrir a pasta dos documentos. ' + descrever_erro(erro), parent=pai)
