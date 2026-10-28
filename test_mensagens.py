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

    def test_diario_anota_erros_da_interface_sem_o_texto_digitado(self):
        import logging
        import tempfile
        from pathlib import Path
        import diario
        with tempfile.TemporaryDirectory() as pasta:
            diario.ativar(Path(pasta))
            try:
                digitado = 'CPF ' + '529.982.247' + '-25 de Fulano'
                try:
                    raise ValueError(digitado)
                except ValueError as erro:
                    diario.erro_na_interface(type(erro), erro, erro.__traceback__)
                descrever_erro(OSError(errno.ENOSPC, 'No space left', '/home/fulano/x'))
            finally:
                for manipulador in list(diario.log.handlers):
                    if not isinstance(manipulador, logging.NullHandler):
                        diario.log.removeHandler(manipulador)
                        manipulador.close()
            texto = (Path(pasta) / 'gestor.log').read_text(encoding='utf-8')
        self.assertIn('ValueError', texto)
        self.assertIn('OSError (código 28)', texto)
        self.assertNotIn('529.982.247-25', texto)
        self.assertNotIn('fulano', texto)


if __name__ == '__main__':
    unittest.main()
