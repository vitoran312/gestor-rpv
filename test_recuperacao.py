import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import recuperacao
from backup import criar_backup, senha_salva
from test_contas import SENHA_TESTE, banco_com_contas, dados_rpv


class TestRecuperacao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.caminho = self.pasta / 'dados' / 'gestor.sqlite3'
        self.caminho.parent.mkdir()
        self.lixo = b'isto nao e um banco sqlite' * 200
        self.caminho.write_bytes(self.lixo)

    def test_banco_danificado_avisa_e_encerra_sem_apagar_o_arquivo(self):
        with patch.object(recuperacao.messagebox, 'askyesno', return_value=False) as pergunta, \
                patch.object(recuperacao.messagebox, 'showinfo') as aviso, \
                patch.object(recuperacao, 'abrir_pasta') as abrir:
            with self.assertRaises(SystemExit):
                recuperacao.abrir_banco(None, self.caminho)
        self.assertIn('danificado', pergunta.call_args.args[1])
        self.assertIn(str(self.caminho.parent), aviso.call_args.args[1])
        abrir.assert_called_once_with(self.caminho.parent)
        self.assertEqual(self.caminho.read_bytes(), self.lixo)

    def test_banco_danificado_restaura_backup_e_guarda_o_arquivo_original(self):
        origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        origem.salvar(dados_rpv(nome='Recuperada'))
        arquivo = criar_backup(origem, self.pasta / 'backups')
        with patch.object(recuperacao.messagebox, 'askyesno', return_value=True), \
                patch.object(recuperacao.filedialog, 'askopenfilename', return_value=str(arquivo)), \
                patch.object(recuperacao.simpledialog, 'askstring', return_value=SENHA_TESTE), \
                patch.object(recuperacao.messagebox, 'showinfo'):
            banco = recuperacao.abrir_banco(None, self.caminho)
        self.assertEqual([r['nome'] for r in banco.listar()], ['Recuperada'])
        self.assertEqual(senha_salva(banco), SENHA_TESTE)
        guardados = list(self.caminho.parent.glob('gestor-danificado-*.sqlite3'))
        self.assertEqual([g.read_bytes() for g in guardados], [self.lixo])

    def test_falha_na_restauracao_devolve_o_arquivo_original(self):
        invalido = self.pasta / 'invalido.rpvbackup'
        invalido.write_bytes(b'nada')
        with patch.object(recuperacao.messagebox, 'askyesno', return_value=True), \
                patch.object(recuperacao.filedialog, 'askopenfilename', return_value=str(invalido)), \
                patch.object(recuperacao.messagebox, 'askretrycancel', return_value=False) as erro, \
                patch.object(recuperacao.messagebox, 'showinfo'), patch.object(recuperacao, 'abrir_pasta'):
            with self.assertRaises(SystemExit):
                recuperacao.abrir_banco(None, self.caminho)
        self.assertIn('backup', erro.call_args.args[1])
        self.assertEqual(self.caminho.read_bytes(), self.lixo)
        self.assertEqual(list(self.caminho.parent.glob('gestor-danificado-*')), [])

    def test_banco_de_versao_mais_nova_nao_e_aberto_nem_rebaixado(self):
        self.caminho.unlink()
        banco = banco_com_contas(self.caminho)
        with banco.conectar() as con:
            con.execute('PRAGMA user_version=9')
        with patch.object(recuperacao.messagebox, 'showerror') as erro:
            with self.assertRaises(SystemExit):
                recuperacao.abrir_banco(None, self.caminho)
        self.assertIn('versão mais nova', erro.call_args.args[1])
        with banco.conectar() as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 9)
        self.assertEqual(list(self.caminho.parent.glob('gestor-danificado-*')), [])

    def backup_com(self, nome, anexo=None):
        origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        identificador = origem.salvar(dados_rpv(nome=nome))
        if anexo:
            arquivo = self.pasta / 'anexo.pdf'
            arquivo.write_bytes(anexo)
            origem.salvar(dict(origem.obter(identificador)), identificador, anexos=[arquivo])
        return criar_backup(origem, self.pasta / 'backups')

    def restaurar_respondendo(self, arquivo, senhas):
        respostas = iter(senhas)
        with patch.object(recuperacao.messagebox, 'askyesno', return_value=True), \
                patch.object(recuperacao.filedialog, 'askopenfilename', return_value=str(arquivo)), \
                patch.object(recuperacao.simpledialog, 'askstring', side_effect=lambda *a, **k: next(respostas)) as pedido, \
                patch.object(recuperacao.messagebox, 'showinfo'):
            return recuperacao.abrir_banco(None, self.caminho), pedido

    def test_anexos_do_banco_danificado_ficam_guardados(self):
        antigos = self.caminho.parent / 'documentos' / '7'
        antigos.mkdir(parents=True)
        (antigos / 'contrato.pdf').write_bytes(b'%PDF-anexo-que-so-existia-aqui')
        banco, _pedido = self.restaurar_respondendo(self.backup_com('Recuperada', b'%PDF-do-backup'), [SENHA_TESTE])
        guardados = list(self.caminho.parent.glob('documentos-danificado-*'))
        self.assertEqual(len(guardados), 1)
        self.assertEqual((guardados[0] / '7' / 'contrato.pdf').read_bytes(), b'%PDF-anexo-que-so-existia-aqui')
        documento = banco.documentos(banco.listar()[0]['id'])[0]
        self.assertEqual(banco.caminho_documento(documento['id']).read_bytes(), b'%PDF-do-backup')
        # O banco vazio criado no meio da recuperação não vira uma "cópia de segurança" inútil.
        self.assertEqual(list((self.caminho.parent / 'backups_automaticos').glob('*')), [])

    def test_falha_devolve_banco_e_anexos_originais(self):
        antigos = self.caminho.parent / 'documentos'
        antigos.mkdir()
        (antigos / 'antigo.pdf').write_bytes(b'antigo')
        with patch('backup.copiar_banco', side_effect=OSError(28, 'No space left')), \
                patch.object(recuperacao.messagebox, 'askretrycancel', return_value=False), \
                patch.object(recuperacao, 'abrir_pasta'), self.assertRaises(SystemExit):
            self.restaurar_respondendo(self.backup_com('Qualquer', b'%PDF'), [SENHA_TESTE])
        self.assertEqual(self.caminho.read_bytes(), self.lixo)
        self.assertEqual((antigos / 'antigo.pdf').read_bytes(), b'antigo')
        self.assertEqual(list(self.caminho.parent.glob('*danificado*')), [])

    def test_senha_errada_pergunta_a_senha_de_novo_sem_voltar_ao_arquivo(self):
        banco, pedido = self.restaurar_respondendo(self.backup_com('Recuperada'), ['errada-1', 'errada-2', SENHA_TESTE])
        self.assertEqual(pedido.call_count, 3)
        self.assertIn('Senha incorreta', pedido.call_args_list[1].args[1])
        self.assertEqual([r['nome'] for r in banco.listar()], ['Recuperada'])

    def test_arquivo_de_dados_vazio_e_tratado_como_danificado(self):
        self.caminho.write_bytes(b'')
        banco, _pedido = self.restaurar_respondendo(self.backup_com('Recuperada'), [SENHA_TESTE])
        self.assertEqual([r['nome'] for r in banco.listar()], ['Recuperada'])

    def test_arquivo_escolhido_que_nao_pode_ser_lido_mostra_erro(self):
        respostas = iter([str(self.pasta / 'sumiu.rpvbackup'), ''])
        with patch.object(recuperacao.messagebox, 'askyesno', return_value=True), \
                patch.object(recuperacao.filedialog, 'askopenfilename', side_effect=lambda **k: next(respostas)), \
                patch.object(recuperacao.messagebox, 'showerror') as erro, \
                patch.object(recuperacao.messagebox, 'showinfo'), patch.object(recuperacao, 'abrir_pasta'):
            with self.assertRaises(SystemExit):
                recuperacao.abrir_banco(None, self.caminho)
        self.assertIn('não foi encontrado', erro.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
