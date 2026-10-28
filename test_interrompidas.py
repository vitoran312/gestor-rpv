"""Encerramentos forçados no meio de uma restauração, exclusão ou carga não podem custar anexos nem dados."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backup
import dados
import demonstracao
from backup import BackupPreparado, criar_backup, recuperar_interrompidas
from dados import PREFIXO_EXCLUSAO, Banco
from apoio_testes import SENHA_TESTE, banco_com_contas, dados_rpv


class Interrompido(BaseException):
    """Simula o programa sendo fechado à força."""


class PastaQueFica(tempfile.TemporaryDirectory):
    """Num encerramento forçado, a pasta de trabalho não é apagada."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._finalizer.detach()

    def cleanup(self):
        pass

    def __exit__(self, *_):
        pass


class TestOperacoesInterrompidas(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = banco_com_contas(self.pasta / 'dados' / 'gestor.sqlite3')
        anexo = self.pasta / 'meu.pdf'
        anexo.write_bytes(b'%PDF meu')
        self.identificador = self.banco.salvar(dados_rpv(nome='Minha'), anexos=[anexo])
        self.caminho = self.banco.documentos(self.identificador)[0]['caminho']

    def arquivo(self):
        return self.banco.pasta_documentos / self.caminho

    def backup_de_outro(self):
        outro = banco_com_contas(self.pasta / 'outro' / 'gestor.sqlite3')
        anexo = self.pasta / 'outro.pdf'
        anexo.write_bytes(b'%PDF outro')
        outro.salvar(dados_rpv(nome='Outra'), anexos=[anexo])
        return criar_backup(outro, self.pasta / 'backups')

    def test_restauracao_interrompida_na_troca_do_banco_devolve_os_anexos(self):
        def replace(origem, destino):
            if 'documentos_importados' in str(destino):
                raise Interrompido  # O processo morre antes de desfazer a troca dos anexos.
            os.rename(origem, destino)

        with BackupPreparado(self.backup_de_outro(), SENHA_TESTE, pasta_trabalho=self.pasta) as preparado:
            with patch.object(backup.tempfile, 'TemporaryDirectory', PastaQueFica), \
                    patch.object(backup, 'copiar_banco', side_effect=Interrompido), \
                    patch.object(backup.os, 'replace', replace), self.assertRaises(Interrompido):
                preparado.restaurar(self.banco, copia_de_seguranca=False)
        self.assertFalse(self.arquivo().exists())  # Os anexos do backup estão no lugar dos da pessoa.
        recuperar_interrompidas(self.banco)
        self.assertEqual(self.arquivo().read_bytes(), b'%PDF meu')
        self.assertEqual([r['nome'] for r in self.banco.listar()], ['Minha'])

    def test_restauracao_concluida_mantem_os_anexos_novos(self):
        with BackupPreparado(self.backup_de_outro(), SENHA_TESTE, pasta_trabalho=self.pasta) as preparado:
            with patch.object(backup.tempfile, 'TemporaryDirectory', PastaQueFica):
                preparado.restaurar(self.banco, copia_de_seguranca=False)  # A pasta de trabalho sobra no disco.
        self.assertImportacaoMantida()

    def test_queda_logo_depois_da_troca_do_banco_mantem_a_importacao(self):
        def replace(origem, destino):
            if Path(destino).name == backup.DESCARTAR:
                raise Interrompido  # O banco já foi trocado; o processo morre antes de marcar a conclusão.
            os.rename(origem, destino)

        with BackupPreparado(self.backup_de_outro(), SENHA_TESTE, pasta_trabalho=self.pasta) as preparado:
            with patch.object(backup.tempfile, 'TemporaryDirectory', PastaQueFica), \
                    patch.object(backup.os, 'replace', replace), self.assertRaises(Interrompido):
                preparado.restaurar(self.banco, copia_de_seguranca=False)
        self.assertImportacaoMantida()

    def assertImportacaoMantida(self):
        """Abre duas vezes: a sobra da pasta de trabalho nunca desfaz uma importação que terminou."""
        for _abertura in range(2):
            recuperar_interrompidas(self.banco)
            novo = self.banco.listar()[0]
            self.assertEqual(novo['nome'], 'Outra')
            caminho = self.banco.documentos(novo['id'])[0]['caminho']
            self.assertEqual((self.banco.pasta_documentos / caminho).read_bytes(), b'%PDF outro')

    def test_segunda_execucao_nao_abre_enquanto_a_primeira_esta_aberta(self):
        import subprocess
        import sys
        import instancia
        dados_app = self.pasta / 'trava'
        self.assertTrue(instancia.travar(dados_app))
        self.addCleanup(instancia.soltar, dados_app)  # No Windows, a pasta só sai depois de fechado o arquivo.
        self.assertTrue(instancia.travar(dados_app))  # A própria execução pode pedir de novo.
        outra = subprocess.run([sys.executable, '-c', 'import sys, instancia; sys.exit(0 if instancia.travar(sys.argv[1]) '
                                'else 3)', str(dados_app)], cwd=Path(__file__).parent)
        self.assertEqual(outra.returncode, 3)
        livre = subprocess.run([sys.executable, '-c', 'import sys, instancia; sys.exit(0 if instancia.travar(sys.argv[1]) '
                                'else 3)', str(self.pasta / 'outra')], cwd=Path(__file__).parent)
        self.assertEqual(livre.returncode, 0)

    def test_exclusao_interrompida_antes_do_banco_devolve_o_anexo(self):
        with patch.object(dados.tempfile, 'TemporaryDirectory', PastaQueFica), self.assertRaises(Interrompido):
            with self.banco.arquivos_para_excluir() as preparar:
                preparar(self.banco.documentos(self.identificador))
                raise Interrompido  # Antes do DELETE chegar ao banco.
        self.assertFalse(self.arquivo().exists())
        self.assertTrue(list(self.banco.caminho.parent.glob(PREFIXO_EXCLUSAO + '*')))
        recuperar_interrompidas(self.banco)
        self.assertEqual(self.arquivo().read_bytes(), b'%PDF meu')

    def test_exclusao_que_chegou_ao_banco_nao_devolve_nada(self):
        documento = self.banco.documentos(self.identificador)[0]
        with patch.object(dados.tempfile, 'TemporaryDirectory', PastaQueFica):
            self.banco.remover_documento(documento['id'])
        recuperar_interrompidas(self.banco)
        self.assertFalse(self.arquivo().exists())

    def test_carga_da_demonstracao_interrompida_antes_de_anotar_nao_deixa_orfao(self):
        vazio = Banco(self.pasta / 'vazio' / 'gestor.sqlite3')
        anotar = demonstracao.anotar

        def anotar_que_cai(banco, contas, operacoes, carregando=False):
            if len(operacoes) == 1:
                raise Interrompido  # A operação já foi gravada, mas não anotada.
            anotar(banco, contas, operacoes, carregando)

        with patch.object(demonstracao, 'anotar', anotar_que_cai), patch.object(demonstracao, 'remover'), \
                self.assertRaises(Interrompido):
            demonstracao.carregar(vazio)
        self.assertEqual(len(vazio.listar()), 1)
        self.assertTrue(demonstracao.limpar_carga_interrompida(vazio))
        self.assertEqual(vazio.listar(), [])
        self.assertEqual(vazio.contas(), [])


if __name__ == '__main__':
    unittest.main()
