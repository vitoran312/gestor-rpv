"""Backup, importação, exportação e pasta dos documentos."""
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, filedialog, ttk

from backup import criar_backup, BackupPreparado, aviso_backup, executar_backup_automatico, PASTA_AUTOMATICA
from componentes import centralizar
from visual import px
from tema import cores
from documentos import abrir_pasta
from exportacao import exportar_excel, nome_sugerido
from ordenacao import ordenar


class ArquivosMixin:
    def atualizar_backup_ao_ativar(self,evento):
        if evento.widget is self.janela or evento.widget is self.historico:
            self.atualizar_ultimo_backup()

    def atualizar_ultimo_backup(self):
        quando=self.banco.ultimo_backup()
        aviso = aviso_backup(quando)
        if aviso and getattr(self,'falha_backup_automatico',False):
            aviso = 'O backup automático não conseguiu gravar na pasta escolhida. ' + aviso
        self.texto_aviso_backup.set(aviso)
        try:
            data = datetime.fromisoformat(quando).astimezone().strftime('%d/%m/%Y') if quando else 'ainda não realizado'
        except (ValueError,TypeError):
            data = 'não disponível'
        if hasattr(self,'texto_ultimo_backup'):
            automatico = ' · Backup automático semanal ativo' if self.banco.configuracao(PASTA_AUTOMATICA) else ''
            self.texto_ultimo_backup.set('Último backup: '+data+automatico)

    def verificar_backup_automatico(self, forcar=False):
        """Roda ao abrir e a cada seis horas; uma falha vira aviso discreto, sem janelas modais."""
        if not self.janela.winfo_exists():
            return None
        arquivo = None
        try:
            arquivo = executar_backup_automatico(self.banco, forcar=forcar)
            self.falha_backup_automatico = False
        except (OSError, sqlite3.Error, ValueError):
            self.falha_backup_automatico = True
            if forcar:
                raise
        finally:
            self.atualizar_ultimo_backup()
            if not forcar:
                self.agendamento_backup = self.janela.after(6 * 60 * 60 * 1000, self.verificar_backup_automatico)
        return arquivo

    def cancelar_agendamento_backup(self, evento):
        if evento.widget is not self.janela:
            return
        for nome in ('agendamento_backup', 'agendamento_data', 'agendamento_tema', 'agendamento_arte'):
            if getattr(self, nome, None):
                self.janela.after_cancel(getattr(self, nome))
                setattr(self, nome, None)

    def configurar_backup_automatico(self):
        pai = self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela
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
            'Uma vez por semana, o programa salva sozinho uma cópia completa — dados e documentos — na pasta '
            'escolhida. Prefira uma pasta sincronizada, como OneDrive ou Google Drive, para ter uma cópia fora '
            'deste computador.')).pack(anchor='w', pady=(6, 16))
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
                    pass
                self.atualizar_ultimo_backup()
                messagebox.showerror('Backup automático', 'Não foi possível usar esta pasta. ' + str(erro), parent=tela)
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
        atualizar()
        tela.bind('<Escape>', lambda _: tela.destroy())
        centralizar(tela)
        tela.deiconify()
        tela.grab_set()

    def exportar_backup(self):
        pai = self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela
        pasta = filedialog.askdirectory(parent=pai, title='Escolha onde salvar o backup')
        if not pasta:
            return
        try:
            arquivo = criar_backup(self.banco, pasta)
        except (OSError, sqlite3.Error, ValueError) as erro:
            messagebox.showerror('Backup', 'Não foi possível criar o backup. ' + str(erro), parent=pai)
            return
        self.atualizar_ultimo_backup()
        messagebox.showinfo('Backup concluído', f'Backup salvo em:\n{arquivo}', parent=pai)

    def importar_dados(self):
        arquivo = filedialog.askopenfilename(parent=self.historico, title='Importar backup do Gestor de RPV',
                                             filetypes=[('Backup do Gestor de RPV', '*.rpvbackup')])
        if not arquivo:
            return
        try:
            with BackupPreparado(arquivo) as pacote:
                resumo = pacote.resumo
                if not messagebox.askyesno('Importar dados',
                    f"O backup contém {resumo['registros']} entrada(s), {resumo['lixeira']} na lixeira, "
                    f"{resumo['contas']} conta(s) e {resumo['documentos']} documento(s).\n\n"
                    'Ele substituirá os dados deste computador, sem juntar os históricos. '
                    'Uma cópia automática dos dados atuais será salva antes. Continuar?',
                    parent=self.historico, icon='warning', default='no'):
                    return
                # A pasta do backup automático pertence a este computador, não ao arquivo importado.
                pasta_automatica = self.banco.configuracao(PASTA_AUTOMATICA)
                seguranca = pacote.restaurar(self.banco)
                if pasta_automatica:
                    self.banco.salvar_configuracao(PASTA_AUTOMATICA, pasta_automatica)
                else:
                    self.banco.remover_configuracao(PASTA_AUTOMATICA)
        except (OSError, sqlite3.Error, ValueError, RuntimeError) as erro:
            messagebox.showerror('Importar dados', 'Não foi possível importar o backup. ' + str(erro), parent=self.historico)
            return
        # Formulários antigos não podem continuar editando IDs do banco substituído.
        for janela in list(self.janela.winfo_children()):
            if isinstance(janela, tk.Toplevel) and janela != self.historico and (
                self.calculadora is None or janela != self.calculadora.tela):
                janela.destroy()
        for janela in list(self.historico.winfo_children()):
            if isinstance(janela, tk.Toplevel):
                janela.destroy()
        self.busca.set('')
        self.filtro.set('todas')
        self.ordenacao = None
        for chave, titulo in self.titulos_colunas.items():
            self.tabela.heading(chave, text=titulo)
        self.atualizar()
        messagebox.showinfo('Importação concluída', 'Dados recuperados. Backup anterior salvo em:\n' + str(seguranca),
                            parent=self.historico)

    def exportar_excel(self):
        pai = self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela
        registros = self.banco.listar()
        if not registros:
            messagebox.showinfo('Exportar para Excel', 'Ainda não há operações para exportar.', parent=pai)
            return
        if getattr(self, 'ordenacao', None):
            registros = ordenar(registros, *self.ordenacao)
        arquivo = filedialog.asksaveasfilename(parent=pai, title='Exportar operações para Excel',
            defaultextension='.xlsx', initialfile=nome_sugerido(), filetypes=[('Planilha do Excel', '*.xlsx')])
        if not arquivo:
            return
        try:
            destino = exportar_excel(registros, arquivo)
        except (OSError, sqlite3.Error, ValueError) as erro:
            messagebox.showerror('Exportar para Excel', 'Não foi possível exportar. ' + str(erro), parent=pai)
            return
        messagebox.showinfo('Exportação concluída',
                            f'{len(registros)} operação(ões) exportada(s) para:\n{destino}', parent=pai)

    def abrir_pasta_documentos(self):
        pai = self.historico if self.historico is not None and self.historico.winfo_exists() else self.janela
        try:
            pasta = self.banco.caminho.parent / 'documentos'
            pasta.mkdir(parents=True,exist_ok=True)
            abrir_pasta(pasta)
        except (OSError,ValueError) as erro:
            messagebox.showerror('Abrir pasta dos documentos',
                'Não foi possível abrir a pasta dos documentos. ' + str(erro),parent=pai)
