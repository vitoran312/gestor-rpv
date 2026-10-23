import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from backup import criar_backup, BackupPreparado, executar_backup_automatico, PASTA_AUTOMATICA
from dados import Banco, limitar_backups
from test_contas import banco_com_contas, dados_rpv, dados_conta


class TestBackupHistorico(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.origem = banco_com_contas(self.pasta / 'origem' / 'gestor.sqlite3')
        self.destino = banco_com_contas(self.pasta / 'destino' / 'gestor.sqlite3')

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

    def test_lixeira_restauracao_e_prorrogacao_somente_na_lista_ativa(self):
        identificador = self.origem.salvar(dados_rpv())
        self.origem.salvar(dados_rpv(observacoes='Alteração'), identificador)
        self.origem.atualizar_previsao(identificador,'2027-01-20')
        self.origem.registrar_recebimento(identificador,'2026-10-22')
        with self.assertRaises(ValueError):
            self.origem.salvar(dados_rpv(custo=0), identificador)
        self.assertEqual(self.origem.obter(identificador)['observacoes'], 'Alteração')
        self.origem.excluir(identificador)
        with self.assertRaises(ValueError):
            self.origem.prorrogar(identificador, '2027-03-01')
        self.assertEqual(self.origem.prorrogacoes(identificador), [])
        self.assertEqual(self.origem.listar(), [])
        self.assertEqual(len(self.origem.listar_lixeira()), 1)
        self.origem.restaurar(identificador)
        self.assertEqual(self.origem.obter(identificador)['recebimento'], '2026-10-22')
        self.origem.prorrogar(identificador, '2027-03-01')
        self.assertEqual(len(self.origem.prorrogacoes(identificador)), 1)

    def test_migracao_080_remove_unicidade_cpf_preserva_vinculos(self):
        conta = self.origem.salvar_conta(dados_conta())
        identificador = self.origem.salvar(dados_rpv(conta_id=conta))
        self.origem.registrar_recebimento(identificador,'2026-10-22')
        snapshot = self.origem.obter(identificador)['conta_snapshot']
        with self.origem.conectar() as con:
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
        with migrado.conectar() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name='historico_alteracoes'").fetchone())
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

    def test_backups_automaticos_mantem_somente_os_dez_mais_recentes(self):
        automaticos = self.destino.caminho.parent / 'backups_automaticos'
        automaticos.mkdir()
        for indice in range(12):
            antigo = automaticos / f'GestorRPV-202001{indice:02d}.rpvbackup'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        outro = automaticos / 'manter.txt'
        outro.write_text('não é backup')
        self.origem.salvar(dados_rpv(nome='Origem'))
        arquivo = criar_backup(self.origem, self.pasta / 'exportado')
        with BackupPreparado(arquivo) as pacote:
            seguranca = pacote.restaurar(self.destino)
        restantes = list(automaticos.glob('*.rpvbackup'))
        self.assertEqual(len(restantes), 10)
        self.assertIn(seguranca, restantes)
        self.assertFalse((automaticos / 'GestorRPV-20200100.rpvbackup').exists())
        self.assertTrue(outro.exists())
        limitar_backups(automaticos, '*.rpvbackup', manter=3)
        self.assertEqual(len(list(automaticos.glob('*.rpvbackup'))), 3)
        self.assertTrue(seguranca.exists())

    def test_backups_antes_da_atualizacao_mantem_somente_os_dez_mais_recentes(self):
        pasta = self.destino.caminho.parent
        for indice in range(11):
            antigo = pasta / f'backup-antes-0.9.0-202001{indice:02d}.sqlite3'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        with self.destino.conectar() as con:
            con.execute('PRAGMA user_version=6')
        Banco(self.destino.caminho)
        restantes = list(pasta.glob('backup-antes-*.sqlite3'))
        self.assertEqual(len(restantes), 10)
        self.assertEqual(len(list(pasta.glob('backup-antes-0.16.0-*.sqlite3'))), 1)
        self.assertFalse((pasta / 'backup-antes-0.9.0-20200100.sqlite3').exists())


    def test_backup_automatico_semanal_preserva_backups_manuais(self):
        self.assertIsNone(executar_backup_automatico(self.origem))
        pasta = self.pasta / 'nuvem'
        pasta.mkdir()
        manual = criar_backup(self.origem, pasta)
        self.origem.salvar_configuracao(PASTA_AUTOMATICA, str(pasta))
        self.assertIsNone(executar_backup_automatico(self.origem))
        self.origem.registrar_backup('2020-01-01T12:00:00')
        primeiro = executar_backup_automatico(self.origem)
        self.assertTrue(primeiro.name.startswith('GestorRPV-auto-'))
        self.assertIsNone(executar_backup_automatico(self.origem))
        for indice in range(11):
            antigo = pasta / f'GestorRPV-auto-202001{indice:02d}.rpvbackup'
            antigo.write_bytes(b'antigo')
            os.utime(antigo, (1_600_000_000 + indice, 1_600_000_000 + indice))
        ultimo = executar_backup_automatico(self.origem, forcar=True)
        self.assertEqual(len(list(pasta.glob('GestorRPV-auto-*.rpvbackup'))), 10)
        self.assertTrue(ultimo.exists())
        self.assertTrue(primeiro.exists())
        self.assertTrue(manual.exists())
        with BackupPreparado(ultimo) as preparado:
            self.assertEqual(preparado.resumo['contas'], 2)

    def test_backup_automatico_com_pasta_indisponivel_nao_cria_pasta(self):
        ausente = self.pasta / 'disco-externo' / 'backups'
        self.origem.salvar_configuracao(PASTA_AUTOMATICA, str(ausente))
        with self.assertRaises(OSError):
            executar_backup_automatico(self.origem)
        self.assertFalse(ausente.exists())
        self.assertIsNone(self.origem.ultimo_backup())

    def test_migracao_021_remove_historico_geral_e_guarda_copia(self):
        identificador = self.origem.salvar(dados_rpv())
        with self.origem.conectar() as con:
            con.execute('''CREATE TABLE historico_alteracoes (
                id INTEGER PRIMARY KEY, rpv_id INTEGER NOT NULL REFERENCES rpvs(id) ON DELETE CASCADE,
                quando TEXT NOT NULL, acao TEXT NOT NULL, alteracoes TEXT NOT NULL)''')
            con.execute("INSERT INTO historico_alteracoes (rpv_id,quando,acao,alteracoes) VALUES (?,'2026-01-01','Legado','{}')",
                        (identificador,))
            con.execute('PRAGMA user_version=7')
        migrado = Banco(self.origem.caminho)
        with migrado.conectar() as con:
            self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0], 8)
            self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name='historico_alteracoes'").fetchone())
        copias = list(migrado.caminho.parent.glob('backup-antes-0.21.0-*.sqlite3'))
        self.assertEqual(len(copias), 1)
        copia = sqlite3.connect(copias[0])
        try:
            self.assertEqual(copia.execute('SELECT COUNT(*) FROM historico_alteracoes').fetchone()[0], 1)
        finally:
            copia.close()
        self.assertEqual(migrado.obter(identificador)['nome'], 'Pessoa De Teste')

if __name__ == '__main__':
    unittest.main()
