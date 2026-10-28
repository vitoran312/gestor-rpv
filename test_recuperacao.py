import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import recuperacao
from backup import criar_backup
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
        self.assertEqual(banco.configuracao('senha_backup'), SENHA_TESTE)
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


if __name__ == '__main__':
    unittest.main()
