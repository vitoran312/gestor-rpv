import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from backup import criar_backup, BackupPreparado
from dados import Banco
from test_contas import dados_rpv, dados_conta


class TestBackupHistorico(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.origem = Banco(self.pasta / 'origem' / 'gestor.sqlite3')
        self.destino = Banco(self.pasta / 'destino' / 'gestor.sqlite3')

    def test_backup_portatil_tudo_inclusive_documentos_lixeira_auditoria(self):
        conta = self.origem.salvar_conta(dados_conta())
        rpv = self.origem.salvar(dados_rpv(conta_id=conta))
        self.origem.atualizar_previsao(rpv, '2027-01-20')
        self.origem.registrar_recebimento(rpv, '2026-10-22')
        outra = self.origem.salvar(dados_rpv(nome='Lixeira'))
        self.origem.excluir(outra)
        docs = self.origem.caminho.parent / 'documentos' / str(rpv)
        docs.mkdir(parents=True)
        (docs / 'contrato.pdf').write_bytes(b'%PDF-teste-do-contrato')
        (docs / 'protocolo.png').write_bytes(b'PNG-teste-do-protocolo')
        self.destino.salvar(dados_rpv(nome='Anterior'))
        destino_docs = self.destino.caminho.parent / 'documentos'
        destino_docs.mkdir()
        (destino_docs / 'antigo.pdf').write_bytes(b'antigo')
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        with BackupPreparado(arquivo) as preparado:
            self.assertEqual(preparado.resumo, {'registros':1, 'lixeira':1, 'contas':3, 'documentos':2})
            seguranca = preparado.restaurar(self.destino)
        restaurado = Banco(self.destino.caminho)
        self.assertEqual(restaurado.obter(rpv)['previsao_atual'], '2027-01-20')
        self.assertEqual(restaurado.obter(rpv)['recebimento'], '2026-10-22')
        self.assertEqual(len(restaurado.listar_lixeira()), 1)
        self.assertEqual(len(restaurado.historico(rpv)), len(self.origem.historico(rpv)))
        self.assertEqual((destino_docs / str(rpv) / 'contrato.pdf').read_bytes(), b'%PDF-teste-do-contrato')
        self.assertFalse((destino_docs / 'antigo.pdf').exists())
        with BackupPreparado(seguranca) as anterior:
            con = sqlite3.connect(anterior.pasta / 'banco.sqlite3')
            try:
                self.assertEqual(con.execute('SELECT nome FROM rpvs').fetchone()[0], 'Anterior')
            finally:
                con.close()
            self.assertEqual((anterior.pasta / 'documentos' / 'antigo.pdf').read_bytes(), b'antigo')

    def test_backup_vazio_documentos_e_falha_importacao_preserva_destino(self):
        self.origem.salvar(dados_rpv(nome='Origem'))
        self.destino.salvar(dados_rpv(nome='Anterior'))
        docs = self.destino.caminho.parent / 'documentos'
        docs.mkdir()
        (docs / 'antigo.pdf').write_bytes(b'preservar')
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        with BackupPreparado(arquivo) as preparado:
            with patch('backup.copiar_banco', side_effect=sqlite3.OperationalError('Falha simulada')):
                with self.assertRaises(sqlite3.OperationalError):
                    preparado.restaurar(self.destino)
        self.assertEqual(self.destino.listar()[0]['nome'], 'Anterior')
        self.assertEqual((docs / 'antigo.pdf').read_bytes(), b'preservar')
        self.assertEqual(len(list((self.destino.caminho.parent / 'backups_automaticos').glob('*.rpvbackup'))), 1)

    def test_backup_alterado_invalido_ou_caminho_inseguro_nao_importa(self):
        self.origem.salvar(dados_rpv())
        docs = self.origem.caminho.parent / 'documentos'
        docs.mkdir()
        (docs / 'contrato.pdf').write_bytes(b'original')
        arquivo = criar_backup(self.origem, self.pasta / 'backups')
        alterado = self.pasta / 'alterado.rpvbackup'
        with ZipFile(arquivo) as origem, ZipFile(alterado,'w',ZIP_DEFLATED) as alvo:
            for nome in origem.namelist():
                alvo.writestr(nome, b'alterado' if nome == 'documentos/contrato.pdf' else origem.read(nome))
        with self.assertRaises(ValueError), BackupPreparado(alterado):
            pass
        inseguro = self.pasta / 'inseguro.rpvbackup'
        with ZipFile(inseguro,'w') as pacote:
            pacote.writestr('../fora.txt', 'invalido')
        with self.assertRaises(ValueError), BackupPreparado(inseguro):
            pass
        self.assertFalse((self.pasta / 'fora.txt').exists())
        invalido = self.pasta / 'invalido.rpvbackup'
        invalido.write_bytes(b'isto nao e um backup')
        with self.assertRaises(ValueError), BackupPreparado(invalido):
            pass

    def test_historico_atomicidade_lixeira_e_restauracao(self):
        identificador = self.origem.salvar(dados_rpv())
        self.origem.salvar(dados_rpv(observacoes='Alteração'), identificador)
        self.origem.atualizar_previsao(identificador,'2027-01-20')
        self.origem.registrar_recebimento(identificador,'2026-10-22')
        antes = len(self.origem.historico(identificador))
        with self.assertRaises(ValueError):
            self.origem.salvar(dados_rpv(custo=0), identificador)
        self.assertEqual(len(self.origem.historico(identificador)), antes)
        self.origem.excluir(identificador)
        self.assertEqual(self.origem.listar(), [])
        self.assertEqual(len(self.origem.listar_lixeira()), 1)
        self.origem.restaurar(identificador)
        self.assertEqual(self.origem.obter(identificador)['recebimento'], '2026-10-22')
        eventos = self.origem.historico(identificador)
        self.assertEqual(len(eventos), 6)
        self.assertEqual(eventos[0]['acao'],'Restaurado da lixeira')
        previsao = next(e for e in eventos if e['acao']=='Previsão atual')
        self.assertEqual(json.loads(previsao['alteracoes'])['previsao_atual'],
                         {'antes':'2026-12-20','depois':'2027-01-20'})

    def test_migracao_080_remove_unicidade_cpf_preserva_vinculos(self):
        conta = self.origem.salvar_conta(dados_conta())
        identificador = self.origem.salvar(dados_rpv(conta_id=conta))
        self.origem.registrar_recebimento(identificador,'2026-10-22')
        snapshot = self.origem.obter(identificador)['conta_snapshot']
        with self.origem.conectar() as con:
            con.execute('DROP TABLE historico_alteracoes')
            con.execute('ALTER TABLE rpvs DROP COLUMN lixeira_em')
            esquema = con.execute("SELECT sql FROM sqlite_master WHERE name='contas'").fetchone()[0]
            esquema = esquema.replace('CREATE TABLE contas', 'CREATE TABLE contas_legado').replace('cpf TEXT,', 'cpf TEXT UNIQUE,')
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute(esquema)
            campos = ','.join(r['name'] for r in con.execute('PRAGMA table_info(contas)'))
            con.execute(f'INSERT INTO contas_legado ({campos}) SELECT {campos} FROM contas')
            con.execute('DROP TABLE contas')
            con.execute('ALTER TABLE contas_legado RENAME TO contas')
            con.execute('PRAGMA user_version=3')
        migrado = Banco(self.origem.caminho)
        nova = migrado.salvar_conta(dados_conta(identificacao='Outro banco',numero='999',pix='outro@example.com'))
        self.assertNotEqual(conta,nova)
        self.assertEqual(migrado.obter(identificador)['conta_snapshot'],snapshot)
        self.assertEqual(migrado.obter(identificador)['recebimento'],'2026-10-22')
        with migrado.conectar() as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertFalse(Banco.cpf_unico(con))
        self.assertEqual(migrado.historico(identificador)[0]['acao'],'Registro anterior à versão 0.9.0')
        self.assertEqual(len(list(migrado.caminho.parent.glob('backup-antes-0.9.0-*.sqlite3'))),1)

    def test_backup_dentro_da_pasta_documentos_nao_inclui_a_si_mesmo(self):
        self.origem.salvar(dados_rpv())
        docs = self.origem.caminho.parent / 'documentos'
        docs.mkdir()
        (docs / 'contrato.pdf').write_bytes(b'%PDF-contrato')
        primeiro = criar_backup(self.origem, docs)
        segundo = criar_backup(self.origem, docs)
        with BackupPreparado(segundo) as preparado:
            self.assertEqual(preparado.resumo['documentos'],1)
        self.assertTrue(primeiro.exists())


if __name__ == '__main__':
    unittest.main()
