"""Backup, importação, exportação e pasta dos documentos."""
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, filedialog

from backup import criar_backup, BackupPreparado, aviso_backup
from documentos import abrir_pasta
from exportacao import exportar_excel, nome_sugerido
from ordenacao import ordenar


class ArquivosMixin:
    def atualizar_backup_ao_ativar(self,evento):
        if evento.widget is self.janela or evento.widget is self.historico:
            self.atualizar_ultimo_backup()

    def atualizar_ultimo_backup(self):
        quando=self.banco.ultimo_backup()
        self.texto_aviso_backup.set(aviso_backup(quando))
        try:
            data = datetime.fromisoformat(quando).astimezone().strftime('%d/%m/%Y') if quando else 'ainda não realizado'
        except (ValueError,TypeError):
            data = 'não disponível'
        if hasattr(self,'texto_ultimo_backup'):
            self.texto_ultimo_backup.set('Último backup: '+data)

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
                seguranca = pacote.restaurar(self.banco)
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
