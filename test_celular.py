"""O leitor de backups do app do celular (celular/leitor.js) abre os mesmos arquivos que o programa grava.

Roda um navegador de verdade (Playwright + Chromium); fica de fora quando não há Node.js com Playwright,
como no Windows do CI. Exemplo: GESTOR_RPV_TESTE_CELULAR=1 python -m unittest test_celular -v
"""
import functools
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backup import criar_backup
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv

RAIZ = Path(__file__).resolve().parent


class Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


@unittest.skipUnless(os.environ.get('GESTOR_RPV_TESTE_CELULAR') == '1', 'Requer Node.js com Playwright e '
                     'GESTOR_RPV_TESTE_CELULAR=1')
class TestLeitorDoCelular(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.pasta = Path(cls.temp.name)
        cls.site = cls.pasta / 'site'
        shutil.copytree(RAIZ / 'celular', cls.site, ignore=shutil.ignore_patterns('testes'))
        cls.casos, cls.esperado = cls.montar_backups()
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Silencioso, directory=str(cls.site)))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            saida = subprocess.run(
                ['node', str(RAIZ / 'celular' / 'testes' / 'navegador.cjs'),
                 f'http://127.0.0.1:{servidor.server_address[1]}', json.dumps(cls.casos)],
                capture_output=True, text=True, timeout=300, check=True).stdout
        finally:
            servidor.shutdown()
            servidor.server_close()
        cls.resultados = json.loads(saida)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def montar_backups(cls):
        banco = banco_com_contas(cls.pasta / 'dados' / 'gestor.sqlite3')
        # Um anexo de 2,5 MB faz o backup passar de um bloco da cifra (1 MiB): confere a costura dos blocos.
        anexo = cls.pasta / 'grande.pdf'
        anexo.write_bytes(b'%PDF' + os.urandom(2_500_000))
        banco.salvar(dados_rpv(nome='Ana Júlia D\'Ávila'), anexos=[anexo])
        banco.salvar(dados_rpv(nome='Bruno Lima'))
        banco.excluir(banco.salvar(dados_rpv(nome='Na Lixeira')))
        cifrado = criar_backup(banco, cls.site / 'backups')
        banco.remover_configuracao('senha_backup')
        aberto = criar_backup(banco, cls.site / 'backups', prefixo='SemSenha-', exigir_senha=False)
        adulterado = cls.site / 'backups' / 'adulterado.rpvbackup'
        bytes_ = bytearray(cifrado.read_bytes())
        bytes_[len(bytes_) // 2] ^= 1
        adulterado.write_bytes(bytes_)
        cortado = cls.site / 'backups' / 'cortado.rpvbackup'
        cortado.write_bytes(cifrado.read_bytes()[:-(1024 * 1024 + 16)])  # Sem o último bloco inteiro.
        endereco = lambda arquivo: 'backups/' + arquivo.name
        casos = [
            {'nome': 'cifrado', 'arquivo': endereco(cifrado), 'senha': SENHA_TESTE},
            {'nome': 'sem_senha', 'arquivo': endereco(aberto), 'senha': ''},
            {'nome': 'senha_errada', 'arquivo': endereco(cifrado), 'senha': SENHA_TESTE + 'x'},
            {'nome': 'senha_vazia', 'arquivo': endereco(cifrado), 'senha': ''},
            {'nome': 'adulterado', 'arquivo': endereco(adulterado), 'senha': SENHA_TESTE},
            {'nome': 'cortado', 'arquivo': endereco(cortado), 'senha': SENHA_TESTE},
        ]
        esperado = {'operacoes': 2, 'lixeira': 1, 'contas': len(banco.contas()), 'documentos': 1,
                    'nomes': ['Ana Júlia D\'Ávila', 'Bruno Lima']}
        return casos, esperado

    def test_backup_com_senha_abre_igual_ao_programa(self):
        resultado = self.resultados['cifrado']
        self.assertTrue(resultado.pop('cifrado'))
        resultado.pop('versao_app')
        self.assertEqual(resultado, self.esperado)

    def test_backup_antigo_sem_senha_tambem_abre(self):
        resultado = self.resultados['sem_senha']
        self.assertFalse(resultado['cifrado'])
        self.assertEqual(resultado['nomes'], self.esperado['nomes'])

    def test_senha_errada_ou_ausente_e_recusada(self):
        for caso in ('senha_errada', 'senha_vazia'):
            with self.subTest(caso):
                self.assertEqual(self.resultados[caso]['erro'], 'SenhaIncorreta')

    def test_arquivo_alterado_ou_cortado_e_recusado(self):
        for caso in ('adulterado', 'cortado'):
            with self.subTest(caso):
                self.assertEqual(self.resultados[caso]['erro'], 'SenhaIncorreta')
                self.assertIn('alterado ou está incompleto', self.resultados[caso]['mensagem'])


if __name__ == '__main__':
    unittest.main()
