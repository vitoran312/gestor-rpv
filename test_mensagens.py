import errno
import sqlite3
import unittest

from mensagens import descrever_erro


class TestMensagens(unittest.TestCase):
    def test_erros_do_sistema_viram_frases_em_portugues_sem_detalhes_tecnicos(self):
        for erro, trecho in ((OSError(errno.ENOSPC, 'No space left', '/tmp/x'), 'espaço livre'),
                             (OSError(errno.EACCES, 'Permission denied', 'C:/planilha.xlsx'), 'aberto em outro programa'),
                             (IsADirectoryError(errno.EISDIR, 'Is a directory', '/tmp/.exportar-rpv-abc.tmp'), 'é uma pasta'),
                             (OSError(errno.ENAMETOOLONG, 'File name too long'), 'longo demais'),
                             (OSError(9999, 'Strange'), 'não permitiu'),
                             (sqlite3.OperationalError('database is locked'), 'dados do programa'),
                             (ValueError('Mensagem do aplicativo.'), 'Mensagem do aplicativo.')):
            with self.subTest(trecho):
                texto = descrever_erro(erro)
                self.assertIn(trecho, texto)
                self.assertNotIn('Errno', texto)
                self.assertNotIn('.tmp', texto)


if __name__ == '__main__':
    unittest.main()
