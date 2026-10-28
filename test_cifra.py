import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import cifra
from backup import SENHA_BACKUP, PASTA_AUTOMATICA, BackupPreparado, SenhaAusente, SenhaNecessaria, criar_backup
from test_contas import SENHA_TESTE, banco_com_contas, dados_rpv


class TestCifra(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)

    def cifrar(self, conteudo, senha='segredo1'):
        origem, cifrado = self.pasta / 'origem', self.pasta / 'cifrado'
        origem.write_bytes(conteudo)
        cifra.cifrar_arquivo(origem, cifrado, senha)
        return cifrado

    def decifrar(self, cifrado, senha='segredo1'):
        destino = self.pasta / 'destino'
        cifra.decifrar_arquivo(cifrado, destino, senha)
        return destino.read_bytes()

    def test_ida_e_volta_em_blocos_de_qualquer_tamanho(self):
        with patch.object(cifra, 'BLOCO', 64):
            for tamanho in (0, 1, 63, 64, 65, 128, 200):
                with self.subTest(tamanho):
                    conteudo = os.urandom(tamanho)
                    cifrado = self.cifrar(conteudo)
                    self.assertTrue(cifra.cifrado(cifrado))
                    if tamanho > 8:
                        self.assertNotIn(conteudo, cifrado.read_bytes())
                    self.assertEqual(self.decifrar(cifrado), conteudo)

    def test_senha_errada_alteracao_corte_ou_acrescimo_sao_recusados(self):
        with patch.object(cifra, 'BLOCO', 64):
            cifrado = self.cifrar(os.urandom(150))
            original = cifrado.read_bytes()
            with self.assertRaises(cifra.SenhaIncorreta):
                self.decifrar(cifrado, 'outra-senha')
            for nome, alterado in (('byte trocado', original[:40] + bytes([original[40] ^ 1]) + original[41:]),
                                   ('cortado no fim de um bloco', original[:31 + 2 * 80]),
                                   ('bloco a mais', original + original[31:31 + 80]),
                                   ('cabeçalho trocado', original[:10] + bytes([original[10] ^ 1]) + original[11:])):
                with self.subTest(nome):
                    cifrado.write_bytes(alterado)
                    with self.assertRaises(cifra.SenhaIncorreta):
                        self.decifrar(cifrado)

    def test_senha_curta_e_recusada(self):
        with self.assertRaisesRegex(ValueError, '6 caracteres'):
            cifra.validar_senha('12345')
        self.assertEqual(cifra.validar_senha('123456'), '123456')


class TestBackupComSenha(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        self.origem.salvar(dados_rpv(nome='Protegida'))

    def test_backup_e_cifrado_e_so_abre_com_a_senha(self):
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        self.assertTrue(cifra.cifrado(arquivo))
        self.assertFalse(zipfile.is_zipfile(arquivo))
        self.assertNotIn(b'Protegida', arquivo.read_bytes())
        for senha in (None, 'senha-errada'):
            with self.subTest(senha), self.assertRaises(SenhaNecessaria), BackupPreparado(arquivo, senha):
                pass
        with BackupPreparado(arquivo, SENHA_TESTE) as preparado:
            self.assertEqual(preparado.resumo['registros'], 1)
            con = sqlite3.connect(preparado.pasta / 'banco.sqlite3')
            try:
                # A senha deste computador não viaja dentro do backup.
                self.assertIsNone(con.execute("SELECT valor FROM configuracoes WHERE chave='senha_backup'").fetchone())
            finally:
                con.close()

    def test_sem_senha_definida_o_backup_nao_e_criado(self):
        self.origem.remover_configuracao(SENHA_BACKUP)
        with self.assertRaises(SenhaAusente):
            criar_backup(self.origem, self.pasta / 'backups')
        self.assertFalse(cifra.cifrado(criar_backup(self.origem, self.pasta / 'locais', exigir_senha=False)))

    def test_importar_mantem_a_senha_e_a_pasta_automatica_deste_computador(self):
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        destino = banco_com_contas(self.pasta / 'destino' / 'gestor.sqlite3')
        destino.salvar_configuracao(SENHA_BACKUP, 'senha-do-destino')
        destino.salvar_configuracao(PASTA_AUTOMATICA, '/pasta/do/destino')
        with BackupPreparado(arquivo, SENHA_TESTE) as preparado:
            seguranca = preparado.restaurar(destino)
        self.assertEqual(destino.configuracao(SENHA_BACKUP), 'senha-do-destino')
        self.assertEqual(destino.configuracao(PASTA_AUTOMATICA), '/pasta/do/destino')
        self.assertEqual([r['nome'] for r in destino.listar()], ['Protegida'])
        # A cópia de segurança feita antes de importar usa a senha do destino.
        with BackupPreparado(seguranca, 'senha-do-destino') as anterior:
            self.assertEqual(anterior.resumo['registros'], 0)


if __name__ == '__main__':
    unittest.main()
