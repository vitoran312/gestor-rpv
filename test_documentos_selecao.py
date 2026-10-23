import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dados import Banco
from backup import criar_backup, BackupPreparado
from test_contas import dados_rpv


class TestDocumentos(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.banco = Banco(self.pasta/'app'/'gestor.sqlite3')
        self.pdf = self.pasta/'contrato.pdf'
        self.pdf.write_bytes(b'%PDF-contrato')
        self.imagem = self.pasta/'protocolo.png'
        self.imagem.write_bytes(b'PNG-protocolo')

    def test_anexos_persistem_sem_originais_e_voltam_do_backup(self):
        identificador = self.banco.salvar(dados_rpv(),anexos=[self.pdf,self.imagem])
        documentos = self.banco.documentos(identificador)
        self.assertEqual([d['nome'] for d in documentos],['contrato.pdf','protocolo.png'])
        self.pdf.unlink()
        self.assertEqual(self.banco.caminho_documento(documentos[0]['id']).read_bytes(),b'%PDF-contrato')
        self.banco.excluir(identificador)
        self.banco.restaurar(identificador)
        self.assertEqual(len(self.banco.documentos(identificador)),2)
        pacote = criar_backup(self.banco,self.pasta/'backups')
        destino = Banco(self.pasta/'outro'/'gestor.sqlite3')
        with BackupPreparado(pacote) as preparado:
            preparado.restaurar(destino)
        self.assertEqual(destino.caminho_documento(documentos[0]['id']).read_bytes(),b'%PDF-contrato')

    def test_falha_de_copia_nao_salva_entrada_parcial_nem_apaga_arquivos_antigos(self):
        with patch('dados.shutil.copyfile',side_effect=OSError('Falha simulada')):
            with self.assertRaises(OSError):
                self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        self.assertEqual(self.banco.listar(),[])
        self.assertEqual(list((self.banco.caminho.parent/'documentos').rglob('*.pdf')),[])
        identificador = self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        antigo = self.banco.documentos(identificador)[0]
        with self.assertRaises(ValueError):
            self.banco.salvar(dados_rpv(nome='Mudança'),identificador,anexos=[self.imagem,self.pasta/'ausente.pdf'])
        self.assertEqual(self.banco.obter(identificador)['nome'],'Pessoa De Teste')
        self.assertEqual(len(self.banco.documentos(identificador)),1)
        self.assertTrue(self.banco.caminho_documento(antigo['id']).exists())

    def test_exclusao_e_restauracao_em_lote_sao_atomicas(self):
        primeiro = self.banco.salvar(dados_rpv())
        segundo = self.banco.salvar(dados_rpv())
        with self.assertRaises(ValueError):
            self.banco.excluir_varios([primeiro,999999])
        self.assertEqual(len(self.banco.listar()),2)
        self.banco.excluir_varios([primeiro,segundo])
        self.assertEqual(self.banco.listar(),[])
        with self.assertRaises(ValueError):
            self.banco.restaurar_varios([primeiro,999999])
        self.assertEqual(len(self.banco.listar_lixeira()),2)
        self.banco.restaurar_varios([primeiro,segundo])
        self.assertEqual(len(self.banco.listar()),2)

    def test_importa_backup_090_e_preserva_registros_antigos_sem_gerar_novos(self):
        identificador = self.banco.salvar(dados_rpv())
        with self.banco.conectar() as con:
            con.execute("INSERT INTO historico_alteracoes (rpv_id,quando,acao,alteracoes) VALUES (?, '2026-10-22T12:00:00+00:00','Legado','{}')",(identificador,))
            con.execute('DROP TABLE documentos')
            con.execute('PRAGMA user_version=4')
        pacote = criar_backup(self.banco,self.pasta/'backups')
        destino = Banco(self.pasta/'outro'/'gestor.sqlite3')
        with BackupPreparado(pacote) as preparado:
            preparado.restaurar(destino)
        destino.salvar(dados_rpv(observacoes='Editado'),identificador)
        self.assertEqual(len(destino.historico(identificador)),1)
        self.assertEqual(destino.documentos(identificador),[])
        with destino.conectar() as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],7)

    def test_recebimento_separado_com_backup_e_rollback(self):
        identificador = self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        with self.assertRaises(ValueError):
            self.banco.registrar_recebimento(identificador,'2026-10-22',anexos=[self.imagem,self.pasta/'ausente.pdf'])
        self.assertIsNone(self.banco.obter(identificador)['recebimento'])
        self.assertEqual(self.banco.documentos(identificador,tipo='recebimento'),[])
        self.assertEqual(list((self.banco.caminho.parent/'documentos'/'recebimentos').rglob('*.png')),[])
        self.banco.registrar_recebimento(identificador,'2026-10-22',anexos=[self.imagem])
        entrada = self.banco.documentos(identificador)[0]
        recibo = self.banco.documentos(identificador,tipo='recebimento')[0]
        self.assertNotEqual(self.banco.caminho_documento(entrada['id']).parent,self.banco.caminho_documento(recibo['id']).parent)
        self.assertTrue(recibo['caminho'].startswith('recebimentos/'))
        self.imagem.unlink()
        pacote = criar_backup(self.banco,self.pasta/'exportados')
        destino = Banco(self.pasta/'destino'/'gestor.sqlite3')
        with BackupPreparado(pacote) as preparado:
            preparado.restaurar(destino)
        self.assertEqual(destino.caminho_documento(recibo['id']).read_bytes(),b'PNG-protocolo')
        self.assertEqual(len(destino.documentos(identificador)),1)
        self.assertEqual(len(destino.documentos(identificador,tipo='recebimento')),1)

    def test_migracao_0100_preserva_anexos_como_documentos_de_entrada(self):
        identificador = self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        with self.banco.conectar() as con:
            con.execute('ALTER TABLE documentos DROP COLUMN tipo')
            con.execute('PRAGMA user_version=5')
        pacote = criar_backup(self.banco,self.pasta/'exportados')
        destino = Banco(self.pasta/'destino'/'gestor.sqlite3')
        with BackupPreparado(pacote) as preparado:
            preparado.restaurar(destino)
        self.assertEqual(len(destino.documentos(identificador)),1)
        self.assertEqual(destino.documentos(identificador,tipo='recebimento'),[])
        antigo = Banco(self.banco.caminho)
        self.assertEqual(len(antigo.documentos(identificador)),1)
        self.assertTrue(list(antigo.caminho.parent.glob('backup-antes-0.11.0-*.sqlite3')))


if __name__ == '__main__':
    unittest.main()
