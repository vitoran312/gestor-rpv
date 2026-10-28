"""Exclusões, migração e backup: verificações de integridade das operações."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import hashlib

from dados import Banco
from backup import criar_backup, BackupPreparado, FORMATO
from test_contas import banco_com_contas, dados_conta, dados_rpv, SENHA_TESTE


class TestOperacoes016(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta=Path(self.temp.name)
        self.banco=banco_com_contas(self.pasta/'dados'/'banco.sqlite3')
        self.pdf=self.pasta/'contrato.pdf'
        self.pdf.write_bytes(b'%PDF original')

    def test_exclusao_permanente_somente_lixeira_com_cascata_e_documentos(self):
        primeiro=self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        segundo=self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        self.banco.registrar_recebimento(primeiro,'2026-10-22',anexos=[self.pdf])
        self.banco.atualizar_previsao(primeiro,'2027-01-22')
        arquivos=[self.banco.caminho_documento(d['id']) for tipo in ('entrada','recebimento') for d in self.banco.documentos(primeiro,tipo)]
        self.banco.excluir(primeiro)
        with self.assertRaises(ValueError):self.banco.excluir_permanentemente([primeiro,segundo])
        self.assertIsNotNone(self.banco.obter(primeiro))
        self.assertTrue(all(p.exists() for p in arquivos))
        self.banco.excluir_permanentemente([primeiro])
        self.assertIsNone(self.banco.obter(primeiro))
        self.assertTrue(all(not p.exists() for p in arquivos))
        self.assertEqual(self.banco.historico_previsoes(primeiro),[])
        self.assertIsNotNone(self.banco.obter(segundo))
        self.assertTrue(self.pdf.exists())
        with self.banco.conectar() as con:self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_exclusao_de_arquivo_e_entrada_reverte_em_falha_do_banco(self):
        identificador=self.banco.salvar(dados_rpv(),anexos=[self.pdf])
        documento=self.banco.documentos(identificador)[0]
        caminho=self.banco.caminho_documento(documento['id'])
        with self.banco.conectar() as con:
            con.execute("CREATE TRIGGER impedir_exclusao BEFORE DELETE ON documentos BEGIN SELECT RAISE(ABORT,'falha simulada'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.banco.remover_documento(documento['id'])
        self.assertTrue(caminho.exists())
        self.banco.excluir(identificador)
        with self.assertRaises(sqlite3.IntegrityError):self.banco.excluir_permanentemente([identificador])
        self.assertTrue(caminho.exists())
        self.assertIsNotNone(self.banco.obter(identificador))
        with self.banco.conectar() as con:con.execute('DROP TRIGGER impedir_exclusao')
        self.banco.remover_documento(documento['id'])
        self.assertFalse(caminho.exists())
        self.assertTrue(self.pdf.exists())
        self.assertEqual(self.banco.documentos(identificador),[])

    def test_remocao_de_conta_real_preserva_edicao_e_dados_anteriores(self):
        conta=self.banco.salvar_conta(dados_conta())
        rpv=self.banco.salvar(dados_rpv(conta_id=conta))
        copia=self.banco.obter(rpv)['conta_snapshot']
        self.banco.remover_conta(conta)
        self.assertIsNone(self.banco.obter_conta(conta))
        self.banco.salvar(dados_rpv(conta_id=None,observacoes='Corrigido'),rpv)
        self.assertEqual(self.banco.obter(rpv)['conta_snapshot'],copia)
        self.assertEqual(self.banco.obter(rpv)['conta'],'Conta teste')
        self.assertIsNone(self.banco.obter(rpv)['conta_id'])
        novo=self.banco.salvar_conta(dados_conta(identificacao='Nova conta',pix='novo@example.com',numero='9999'))
        self.banco.salvar(dados_rpv(conta_id=novo),rpv)
        self.assertEqual(self.banco.obter(rpv)['conta_id'],novo)

    def test_historico_de_previsoes_antecipa_repete_e_persiste(self):
        rpv=self.banco.salvar(dados_rpv())
        for data in ('2027-01-20','2026-11-20','2026-11-20'):
            self.banco.atualizar_previsao(rpv,data)
        eventos=Banco(self.banco.caminho).historico_previsoes(rpv)
        self.assertEqual([(e['anterior'],e['nova']) for e in eventos],
                         [('2027-01-20','2026-11-20'),('2026-12-20','2027-01-20')])
        with self.assertRaises(ValueError):self.banco.atualizar_previsao(rpv,'2026-01-01')
        self.assertEqual(len(self.banco.historico_previsoes(rpv)),2)

    def test_ultimo_backup_so_muda_no_sucesso_e_viaja_no_arquivo(self):
        self.assertIsNone(self.banco.ultimo_backup())
        rpv=self.banco.salvar(dados_rpv())
        self.banco.atualizar_previsao(rpv,'2027-01-20')
        pacote=criar_backup(self.banco,self.pasta/'backups')
        quando=self.banco.ultimo_backup()
        self.assertIsNotNone(quando)
        destino=Banco(self.pasta/'destino'/'banco.sqlite3')
        with BackupPreparado(pacote, SENHA_TESTE) as preparado:preparado.restaurar(destino)
        self.assertEqual(destino.ultimo_backup(),quando)
        self.assertEqual(len(destino.historico_previsoes(rpv)),1)
        self.banco.registrar_backup('2020-01-01T12:00:00+00:00')
        with patch('backup.os.replace',side_effect=OSError('Falha simulada')):
            with self.assertRaises(OSError):criar_backup(self.banco,self.pasta/'falha')
        self.assertEqual(self.banco.ultimo_backup(),'2020-01-01T12:00:00+00:00')

    def test_migracao_versao6_real_e_importacao_preservam_anexos_e_ids(self):
        conta=self.banco.salvar_conta(dados_conta())
        rpv=self.banco.salvar(dados_rpv(conta_id=conta),anexos=[self.pdf])
        documento=self.banco.documentos(rpv)[0]
        with self.banco.conectar() as con:
            con.execute('PRAGMA foreign_keys=OFF')
            esquema=con.execute("SELECT sql FROM sqlite_master WHERE name='rpvs'").fetchone()[0]
            esquema=esquema.replace('CREATE TABLE rpvs','CREATE TABLE rpvs_legado',1).replace('conta_id INTEGER REFERENCES contas(id) ON DELETE SET NULL','conta_id INTEGER NOT NULL REFERENCES contas(id)')
            con.execute(esquema)
            con.execute('INSERT INTO rpvs_legado SELECT * FROM rpvs')
            con.execute('DROP TABLE rpvs')
            con.execute('ALTER TABLE rpvs_legado RENAME TO rpvs')
            con.execute('DROP TABLE configuracoes')
            con.execute('DROP TABLE previsoes_historico')
            con.execute('PRAGMA user_version=6')
        arquivos={'banco.sqlite3':self.banco.caminho.read_bytes(),
                  'documentos/'+documento['caminho']:self.banco.caminho_documento(documento['id']).read_bytes()}
        legado=self.pasta/'legado.rpvbackup'
        with ZipFile(legado,'w') as zipado:
            for nome,conteudo in arquivos.items():zipado.writestr(nome,conteudo)
            zipado.writestr('manifesto.json',json.dumps({'formato':FORMATO,'versao_formato':1,
                'arquivos':{n:hashlib.sha256(c).hexdigest() for n,c in arquivos.items()}}))
        migrado=Banco(self.banco.caminho)
        self.assertTrue(list(migrado.caminho.parent.glob('backup-antes-0.16.0-*.sqlite3')))
        destino=Banco(self.pasta/'novo'/'banco.sqlite3')
        with BackupPreparado(legado, SENHA_TESTE) as preparado:preparado.restaurar(destino)
        destino.remover_conta(conta)
        self.assertIsNone(destino.obter(rpv)['conta_id'])
        self.assertTrue(destino.caminho_documento(documento['id']).exists())
        with destino.conectar() as con:self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
