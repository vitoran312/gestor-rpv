"""Testes de interface: backup, importação, exportação, anexos e demonstração."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import tela_arquivos
import tela_registro
from dados import Banco
from backup import senha_salva
from apoio_testes import dados_rpv
from apoio_interface import TesteDeInterface, botao, filhos


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_UI') == '1', 'Requer sessão gráfica e GESTOR_RPV_TESTE_UI=1')
class TestArquivos(TesteDeInterface):
    def test_backup_importacao_cancelada_e_confirmada_pela_interface(self):
        dados = dict(nome='Primeira', aquisicao='2026-10-01', previsto=2000000,
                     custo=1200000, conta='Vitor', previsao='2026-12-20', comissao=None, observacoes='')
        self.banco.salvar(dados)
        botoes_iniciais = [w.cget('text') for w in filhos(self.root) if isinstance(w, ttk.Button)]
        self.assertNotIn('Backup', botoes_iniciais)
        self.assertNotIn('Lixeira', botoes_iniciais)
        self.programa.mostrar_historico()
        self.root.update()
        botoes = [w.cget('text') for w in filhos(self.programa.historico) if isinstance(w, ttk.Button)]
        self.assertNotIn('Backup', botoes)
        self.assertNotIn('Importar dados', botoes)
        pasta = Path(self.pasta.name) / 'exportados'
        with patch.object(filedialog, 'askdirectory', return_value=str(pasta)), patch.object(messagebox, 'showinfo'):
            self.programa.menus['Arquivo'].invoke('Fazer backup')
        arquivo = next(pasta.glob('*.rpvbackup'))
        self.banco.salvar(dict(dados, nome='Segunda'))
        with patch.object(filedialog, 'askopenfilename', return_value=str(arquivo)), patch.object(messagebox, 'askyesno', return_value=False):
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.assertEqual(len(self.banco.listar()), 2)
        with patch.object(filedialog, 'askopenfilename', return_value=str(arquivo)), patch.object(messagebox, 'askyesno', return_value=True), patch.object(messagebox, 'showinfo'):
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.root.update()
        self.assertEqual(len(self.banco.listar()), 1)
        self.assertEqual(self.banco.listar()[0]['nome'], 'Primeira')
        self.assertEqual(len(self.programa.tabela.get_children()), 1)

    def test_primeiro_backup_pede_senha_e_importacao_pede_a_senha_do_arquivo(self):
        import cifra
        self.banco.remover_configuracao('senha_backup')
        self.banco.salvar(dados_rpv(nome='Primeira'))
        self.programa.mostrar_historico()
        self.root.update()
        pasta = Path(self.pasta.name) / 'exportados'

        def preencher(senha, repetida):
            tela = next(w for w in filhos(self.root) if isinstance(w, tk.Toplevel) and w.title() == 'Senha dos backups')
            entradas = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
            for entrada, texto in zip(entradas, (senha, repetida)):
                entrada.delete(0, 'end')
                entrada.insert(0, texto)
            botao(tela, 'Salvar senha').invoke()

        # Senhas diferentes são recusadas; a janela continua aberta até acertar.
        self.root.after(200, lambda: preencher('cofre azul 7', 'cofre azul 8'))
        self.root.after(400, lambda: preencher('cofre azul 7', 'cofre azul 7'))
        with patch.object(filedialog, 'askdirectory', return_value=str(pasta)), patch.object(messagebox, 'showinfo'), \
                patch.object(messagebox, 'showerror') as erro:
            self.programa.exportar_backup()
        self.assertIn('não são iguais', erro.call_args.args[1])
        self.assertEqual(senha_salva(self.banco), 'cofre azul 7')
        arquivo = next(pasta.glob('*.rpvbackup'))
        self.assertTrue(cifra.cifrado(arquivo))
        # Em outro computador, com outra senha salva, a importação pede a senha do arquivo.
        self.banco.salvar_configuracao('senha_backup', 'outra-senha')
        self.banco.salvar(dados_rpv(nome='Segunda'))
        respostas = iter(['errada', 'cofre azul 7'])
        with patch.object(filedialog, 'askopenfilename', return_value=str(arquivo)), \
                patch.object(tela_arquivos.simpledialog, 'askstring', side_effect=lambda *a, **k: next(respostas)) as pedido, \
                patch.object(messagebox, 'askyesno', return_value=True), patch.object(messagebox, 'showinfo'):
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.root.update()
        self.assertEqual(pedido.call_count, 2)
        self.assertIn('Senha incorreta', pedido.call_args_list[1].args[1])
        self.assertEqual([r['nome'] for r in self.banco.listar()], ['Primeira'])
        self.assertEqual(senha_salva(self.banco), 'outra-senha')

    def test_senha_dos_backups_troca_cancelamento_e_backup_sem_senha(self):
        from backup import criar_backup
        self.programa.mostrar_historico()
        self.root.update()
        # Cancelar a criação da senha no primeiro backup avisa que o backup não foi feito.
        self.banco.remover_configuracao('senha_backup')
        self.root.after(200, lambda: botao(next(w for w in filhos(self.root) if isinstance(w, tk.Toplevel)
                                                and w.title() == 'Senha dos backups'), 'Cancelar').invoke())
        with patch.object(messagebox, 'showinfo') as aviso:
            self.programa.exportar_backup()
        self.assertIn('não foi feito', aviso.call_args.args[1])
        # Trocar a senha exige a atual; a janela que estava em modo exclusivo volta a estar.
        self.banco.salvar_configuracao('senha_backup', 'cavalo bateria')
        self.programa.configurar_backup_automatico()
        self.root.update()
        automatico = next(w for w in filhos(self.root) if isinstance(w, tk.Toplevel) and w.title() == 'Backup automático')

        def preencher(atual):
            tela = next(w for w in filhos(self.root) if isinstance(w, tk.Toplevel) and w.title() == 'Senha dos backups')
            entradas = [w for w in filhos(tela) if isinstance(w, ttk.Entry)]
            for entrada, texto in zip(entradas, (atual, 'nova senha 1', 'nova senha 1')):
                entrada.delete(0, 'end')
                entrada.insert(0, texto)
            botao(tela, 'Salvar senha').invoke()

        self.root.after(200, lambda: preencher('chute'))
        self.root.after(400, lambda: preencher('cavalo bateria'))
        with patch.object(messagebox, 'showerror') as erro:
            botao(automatico, 'Senha dos backups…').invoke()
        self.assertIn('senha atual não confere', erro.call_args.args[1])
        self.assertEqual(senha_salva(self.banco), 'nova senha 1')
        self.assertEqual(self.root.grab_current(), automatico)
        automatico.destroy()
        # Quem usa senha é avisado ao importar um backup sem senha (pode ter sido forjado).
        self.banco.remover_configuracao('senha_backup')
        sem_senha = criar_backup(self.banco, Path(self.pasta.name) / 'antigo', exigir_senha=False)
        self.banco.salvar_configuracao('senha_backup', 'nova senha 1')
        with patch.object(filedialog, 'askopenfilename', return_value=str(sem_senha)), \
                patch.object(messagebox, 'askyesno', return_value=False) as pergunta:
            self.programa.menus['Arquivo'].invoke('Importar dados')
        self.assertIn('NÃO tem senha', pergunta.call_args.args[1])
        # Com um formulário aberto, a importação pede para fechá-lo antes.
        self.programa.formulario()
        self.root.update()
        with patch.object(filedialog, 'askopenfilename') as escolher, patch.object(messagebox, 'showinfo') as aviso:
            self.programa.importar_dados()
        escolher.assert_not_called()
        self.assertIn('feche os formulários abertos', aviso.call_args.args[1])

    def test_anexar_visualizar_salvar_reabrir_e_cancelar_documentos(self):
        identificador = self.banco.salvar(dados_rpv())
        arquivo = Path(self.pasta.name) / 'contrato.pdf'
        arquivo.write_bytes(b'%PDF-1.4 teste')
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        with patch.object(filedialog, 'askopenfilenames', return_value=(str(arquivo),)):
            botao(form, 'Anexar documentos').invoke()
            botao(form, 'Anexar documentos').invoke()
        self.root.update()
        self.assertEqual(self.banco.documentos(identificador), [])
        documentos = next(w for w in filhos(form) if isinstance(w, ttk.Button)
                          and w.cget('textvariable') and self.root.getvar(w.cget('textvariable')) == 'Documentos (1)')
        documentos.invoke()
        self.root.update()
        janela = next(w for w in form.winfo_children() if isinstance(w, tk.Toplevel))
        lista = next(w for w in filhos(janela) if isinstance(w, ttk.Treeview))
        self.assertEqual(len(lista.get_children()), 1)
        lista.selection_set(lista.get_children()[0])
        with patch.object(tela_registro, 'abrir_arquivo') as abrir:
            botao(janela, 'Abrir documento').invoke()
            abrir.assert_called_once_with(arquivo.resolve())
        botao(janela, 'Fechar').invoke()
        botao(form, 'Salvar registro').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.documentos(identificador)), 1)
        arquivo.unlink()
        self.programa.formulario(identificador)
        self.root.update()
        form = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
        documento = self.banco.documentos(identificador)[0]
        self.assertTrue(self.banco.caminho_documento(documento['id']).exists())
        botao(form, 'Cancelar').invoke()

    def test_comprovantes_recebimento_salvar_cancelar_e_reabrir(self):
        identificador = self.banco.salvar(dados_rpv())
        entrada = Path(self.pasta.name) / 'contrato.pdf'
        entrada.write_bytes(b'%PDF contrato')
        self.banco.salvar(dados_rpv(), identificador, anexos=[entrada])
        recibo = Path(self.pasta.name) / 'recibo.pdf'
        recibo.write_bytes(b'%PDF recibo')
        self.programa.mostrar_historico()
        self.root.update()
        def abrir():
            self.programa.abrir_recebimento(identificador)
            self.root.update()
            return next(w for w in self.programa.historico.winfo_children()
                        if isinstance(w, tk.Toplevel) and w.title() == 'Recebimento')
        tela = abrir()
        with patch.object(filedialog, 'askopenfilenames', return_value=(str(recibo),)):
            botao(tela, 'Anexar documentos').invoke()
        botao(tela, 'Cancelar').invoke()
        self.assertEqual(self.banco.documentos(identificador, tipo='recebimento'), [])
        tela = abrir()
        with patch.object(filedialog, 'askopenfilenames', return_value=(str(recibo),)):
            botao(tela, 'Anexar documentos').invoke()
        botao(tela, 'Salvar recebimento').invoke()
        self.root.update()
        self.assertEqual(len(self.banco.documentos(identificador)), 1)
        recibos = self.banco.documentos(identificador, tipo='recebimento')
        self.assertEqual(len(recibos), 1)
        recibo.unlink()
        tela = abrir()
        documentos = next(w for w in filhos(tela) if isinstance(w, ttk.Button)
                          and w.cget('textvariable') and self.root.getvar(w.cget('textvariable')) == 'Documentos (1)')
        documentos.invoke()
        self.root.update()
        janela = next(w for w in tela.winfo_children() if isinstance(w, tk.Toplevel))
        lista = next(w for w in filhos(janela) if isinstance(w, ttk.Treeview))
        self.assertEqual([lista.item(i, 'values')[0] for i in lista.get_children()], ['recibo.pdf'])
        lista.selection_set(lista.get_children()[0])
        with patch.object(tela_registro, 'abrir_arquivo') as abrir_arquivo:
            botao(janela, 'Abrir documento').invoke()
            abrir_arquivo.assert_called_once_with(self.banco.caminho_documento(recibos[0]['id']))
        botao(janela, 'Fechar').invoke()
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(tela, 'Desmarcar recebimento').invoke()
        self.root.update()
        self.assertIsNone(self.banco.obter(identificador)['recebimento'])
        self.assertTrue(self.banco.caminho_documento(recibos[0]['id']).exists())

    def test_remover_anexos_salvos_de_entrada_e_recebimento(self):
        arquivo = Path(self.pasta.name) / 'comprovante.pdf'
        arquivo.write_bytes(b'%PDF exemplo')
        identificador = self.banco.salvar(dados_rpv(), anexos=[arquivo])
        self.banco.registrar_recebimento(identificador, '2026-10-22', anexos=[arquivo])
        self.programa.mostrar_historico()
        for tipo in ('entrada', 'recebimento'):
            if tipo == 'entrada': self.programa.formulario(identificador)
            else: self.programa.abrir_recebimento(identificador)
            self.root.update()
            dono = self.root if tipo == 'entrada' else self.programa.historico
            tela = next(w for w in dono.winfo_children() if isinstance(w, tk.Toplevel) and w.title() in ('Editar registro', 'Recebimento'))
            abrir = next(w for w in filhos(tela) if isinstance(w, ttk.Button) and w.cget('textvariable') and self.root.getvar(w.cget('textvariable')) == 'Documentos (1)')
            abrir.invoke()
            self.root.update()
            documentos = next(w for w in tela.winfo_children() if isinstance(w, tk.Toplevel))
            lista = next(w for w in filhos(documentos) if isinstance(w, ttk.Treeview))
            lista.selection_set(lista.get_children()[0])
            with patch.object(messagebox, 'askyesno', return_value=False): botao(documentos, 'Remover documento').invoke()
            self.assertEqual(len(self.banco.documentos(identificador, tipo)), 1)
            with patch.object(messagebox, 'askyesno', return_value=True): botao(documentos, 'Remover documento').invoke()
            self.root.update()
            self.assertEqual(self.banco.documentos(identificador, tipo), [])
            self.assertEqual(lista.get_children(), ())
            botao(documentos, 'Fechar').invoke()
            botao(tela, 'Cancelar').invoke()
        self.assertTrue(arquivo.exists())

    def test_lembrete_backup_no_inicio_e_historico_ate_exportar(self):
        self.assertIn('ainda não fez', self.programa.texto_aviso_backup.get())
        with patch.object(filedialog, 'askdirectory', return_value=''):
            self.programa.exportar_backup()
        self.assertIn('ainda não fez', self.programa.texto_aviso_backup.get())
        self.banco.registrar_backup('2020-01-01T12:00:00')
        self.root.event_generate('<FocusIn>')
        self.root.update()
        self.assertIn('dias sem backup', self.programa.texto_aviso_backup.get())
        self.programa.mostrar_historico()
        self.root.update()
        self.assertIn('dias sem backup', self.programa.texto_aviso_backup.get())
        destino = str(Path(self.pasta.name) / 'exportados')
        with patch.object(filedialog, 'askdirectory', return_value=destino), patch.object(messagebox, 'showerror'), patch.object(tela_arquivos, 'criar_backup', side_effect=OSError('Sem espaço')):
            self.programa.exportar_backup()
        self.assertIn('dias sem backup', self.programa.texto_aviso_backup.get())
        self.programa.historico.destroy()
        with patch.object(filedialog, 'askdirectory', return_value=destino), patch.object(messagebox, 'showinfo'):
            self.programa.aviso_backup_inicio.event_generate('<Button-1>')
            self.root.update()
        self.assertEqual(self.programa.texto_aviso_backup.get(), '')
        self.assertTrue(list(Path(destino).glob('*.rpvbackup')))
        self.programa.mostrar_historico()
        self.root.update()
        self.assertEqual(self.programa.texto_aviso_backup.get(), '')

    def test_menu_abre_pasta_documentos_sem_alterar_anexos(self):
        self.programa.mostrar_historico()
        pasta = self.banco.caminho.parent / 'documentos'
        self.assertFalse(pasta.exists())
        with patch.object(tela_arquivos, 'abrir_pasta') as abrir:
            self.programa.menus['Arquivo'].invoke('Abrir pasta dos documentos')
        abrir.assert_called_once_with(pasta)
        self.assertTrue(pasta.is_dir())
        pdf = Path(self.pasta.name) / 'contrato.pdf'
        pdf.write_bytes(b'%PDF-exemplo')
        i = self.banco.salvar(dados_rpv(), anexos=[pdf])
        documento = self.banco.documentos(i)[0]
        with patch.object(tela_arquivos, 'abrir_pasta', side_effect=OSError('Explorador indisponível')), patch.object(messagebox, 'showerror') as erro:
            self.programa.menus['Arquivo'].invoke('Abrir pasta dos documentos')
        erro.assert_called_once()
        self.assertEqual(self.banco.caminho_documento(documento['id']).read_bytes(), b'%PDF-exemplo')

    def test_exportar_excel_pelo_menu(self):
        self.programa.mostrar_historico()
        menu = self.programa.menus['Arquivo']
        rotulos = [menu.entrycget(i, 'label') for i in range(menu.index('end') + 1) if menu.type(i) == 'command']
        self.assertIn('Exportar para Excel', rotulos)
        with patch.object(messagebox, 'showinfo') as aviso, patch.object(filedialog, 'asksaveasfilename') as escolher:
            self.programa.exportar_excel()
        escolher.assert_not_called()
        self.assertIn('Ainda não há operações', aviso.call_args.args[1])
        self.banco.salvar(dados_rpv(nome='Primeira'))
        self.banco.salvar(dados_rpv(nome='Segunda', aquisicao='2026-10-23'))
        with patch.object(filedialog, 'asksaveasfilename', return_value=''), patch.object(messagebox, 'showinfo') as aviso:
            self.programa.exportar_excel()
        aviso.assert_not_called()
        destino = Path(self.pasta.name) / 'planilhas' / 'operacoes.xlsx'
        with patch.object(filedialog, 'asksaveasfilename', return_value=str(destino)), \
                patch.object(messagebox, 'showinfo') as aviso:
            self.programa.exportar_excel()
        self.assertTrue(destino.is_file())
        self.assertIn('2 operação(ões)', aviso.call_args.args[1])

    def test_instalacao_nova_abre_com_demonstracao_e_apaga_pelo_aviso(self):
        self.programa.mostrar_historico()
        self.root.update()
        self.assertFalse(self.programa.aviso_demonstracao.winfo_ismapped())
        self.root.destroy()
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda *args: self.erros.append(args)
        novo = Banco(Path(self.pasta.name) / 'novo' / 'gestor.sqlite3')
        with patch.object(app, 'abrir_banco', return_value=novo):
            self.programa = app.Aplicativo(self.root)
        self.programa.mostrar_historico()
        self.root.update()
        self.assertTrue(self.programa.aviso_demonstracao.winfo_ismapped())
        self.assertEqual(len(self.programa.tabela.get_children()), 13)
        # Uma operação fictícia que recebeu um comprovante de verdade passa a ser da pessoa.
        comprovante = Path(self.pasta.name) / 'meu_comprovante.pdf'
        comprovante.write_bytes(b'%PDF-comprovante-real')
        ficticia = next(r for r in novo.listar() if not r['recebimento'])
        self.programa.abrir_recebimento(ficticia['id'])
        self.root.update()
        self.anexar_e_salvar_recebimento(comprovante)
        self.root.update()
        with patch.object(messagebox, 'askyesno', return_value=False) as pergunta:
            botao(self.programa.historico, 'Apagar dados de demonstração').invoke()
        self.assertEqual(len(self.programa.tabela.get_children()), 13)
        self.assertIn('usam uma conta fictícia', pergunta.call_args.args[1])
        with patch.object(messagebox, 'askyesno', return_value=True):
            botao(self.programa.historico, 'Apagar dados de demonstração').invoke()
        self.root.update()
        self.assertEqual(self.programa.tabela.get_children(), (str(ficticia['id']),))
        documento = novo.documentos(ficticia['id'], tipo='recebimento')[0]
        self.assertEqual(novo.caminho_documento(documento['id']).read_bytes(), b'%PDF-comprovante-real')
        self.assertEqual(novo.contas(), [])
        self.assertFalse(self.programa.aviso_demonstracao.winfo_ismapped())

    def anexar_e_salvar_recebimento(self, arquivo):
        from tkinter import filedialog
        tela = next(w for w in filhos(self.root) if isinstance(w, tk.Toplevel) and w.title() == 'Recebimento')
        with patch.object(filedialog, 'askopenfilenames', return_value=[str(arquivo)]):
            botao(tela, 'Anexar documentos').invoke()
        botao(tela, 'Salvar recebimento').invoke()

    def test_backup_automatico_ativar_desativar_e_falha_discreta(self):
        from backup import PASTA_AUTOMATICA
        self.programa.mostrar_historico()
        self.programa.configurar_backup_automatico()
        self.root.update()
        tela = [w for w in self.programa.historico.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        pasta = Path(self.pasta.name) / 'nuvem'
        pasta.mkdir()
        with patch.object(filedialog, 'askdirectory', return_value=str(pasta)), patch.object(messagebox, 'showinfo') as aviso:
            botao(tela, 'Escolher pasta…').invoke()
        self.assertEqual(self.banco.configuracao(PASTA_AUTOMATICA), str(pasta))
        self.assertEqual(len(list(pasta.glob('GestorRPV-auto-*.rpvbackup'))), 1)
        self.assertIn('ativado', aviso.call_args.args[1])
        self.assertIn('Backup automático semanal ativo', self.programa.texto_ultimo_backup.get())
        self.assertEqual(self.programa.texto_aviso_backup.get(), '')
        ausente = Path(self.pasta.name) / 'ausente'
        with patch.object(filedialog, 'askdirectory', return_value=str(ausente)), patch.object(messagebox, 'showerror') as erro:
            botao(tela, 'Escolher pasta…').invoke()
        self.assertIn('Não foi possível usar esta pasta', erro.call_args.args[1])
        self.assertEqual(self.banco.configuracao(PASTA_AUTOMATICA), str(pasta))
        botao(tela, 'Desativar').invoke()
        self.assertIsNone(self.banco.configuracao(PASTA_AUTOMATICA))
        self.assertNotIn('automático', self.programa.texto_ultimo_backup.get())
        tela.destroy()
        self.banco.salvar_configuracao(PASTA_AUTOMATICA, str(ausente))
        self.banco.registrar_backup('2020-01-01T12:00:00')
        self.programa.verificar_backup_automatico()
        self.assertTrue(self.programa.falha_backup_automatico)
        self.assertIn('backup automático não conseguiu gravar', self.programa.texto_aviso_backup.get())
        # Sem senha definida, o aviso explica o que falta em vez de culpar a pasta.
        self.banco.salvar_configuracao(PASTA_AUTOMATICA, str(pasta))
        self.banco.remover_configuracao('senha_backup')
        self.programa.verificar_backup_automatico()
        self.assertEqual(self.programa.falha_backup_automatico, 'senha')
        self.assertIn('Defina a senha dos backups', self.programa.texto_aviso_backup.get())


if __name__ == '__main__':
    unittest.main()
