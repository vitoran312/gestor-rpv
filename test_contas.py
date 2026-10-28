import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from dados import Banco
from apoio_testes import banco_com_contas, dados_conta, dados_rpv, prorrogacao_antiga


class TestContas(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name) / 'banco.sqlite3'
        self.banco = banco_com_contas(self.caminho)

    def test_duplicidades_endereco_compartilhado_e_edicao(self):
        primeiro = self.banco.salvar_conta(dados_conta())
        outra = dados_conta(identificacao='Outra', cpf='11144477735', numero='99999-1', pix='outra@example.com')
        segundo = self.banco.salvar_conta(outra)
        self.assertEqual(self.banco.obter_conta(segundo)['endereco'], self.banco.obter_conta(primeiro)['endereco'])
        self.banco.salvar_conta(dados_conta(), primeiro)
        for dados in (dados_conta(identificacao=' CONTA TESTE ', cpf='12345678909', numero='888'),
                      dados_conta(identificacao='Duplicada', cpf='12345678909', numero='123456', pix='nova@example.com'),
                      dados_conta(identificacao='Duplicada', cpf='12345678909', numero='888', pix='TESTE@example.com')):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                self.banco.salvar_conta(dados)
        self.banco.salvar_conta(dados_conta(cpf='529.982.247-25'), primeiro)
        mesma_pessoa = self.banco.salvar_conta(dados_conta(identificacao='Outro banco', cpf='52998224725', numero='777', pix='cpf@example.com'))
        self.assertEqual(self.banco.obter_conta(mesma_pessoa)['cpf'], '52998224725')
        for cpf in ('', '11111111111'):
            with self.subTest(cpf=cpf), self.assertRaises(ValueError):
                self.banco.salvar_conta(dados_conta(cpf=cpf))

    def test_pix_de_telefone_com_ou_sem_ddi_e_a_mesma_chave(self):
        from dados import mesma_chave_pix
        for uma, outra, mesma in (('+55 (11) 99999-9999', '(11) 99999-9999', True),
                                  ('55 11 3333-4444', '11 3333-4444', True),
                                  ('529.982.247-25', '52998224725', True),
                                  ('12.345.678/0001-95', '12345678000195', True),
                                  ('123.456.789-09', '(12) 34567-8909', False),   # CPF e celular com os mesmos dígitos.
                                  ('Teste@Exemplo.com', 'teste@exemplo.com', True),
                                  ('', '', False)):
            with self.subTest(uma=uma, outra=outra):
                self.assertEqual(mesma_chave_pix(uma, outra), mesma)
        self.banco.salvar_conta(dados_conta(pix='+55 (11) 99999-9999'))
        with self.assertRaisesRegex(ValueError, 'chave Pix já está cadastrada'):
            self.banco.salvar_conta(dados_conta(identificacao='Outra', numero='999-1', cpf='11144477735',
                                                pix='(11) 99999-9999'))

    def test_conta_em_uso_conta_operacoes_inclusive_na_lixeira(self):
        conta = self.banco.salvar_conta(dados_conta())
        livre = self.banco.salvar_conta(dados_conta(identificacao='Livre', numero='999-1', cpf='11144477735', pix='livre@x.com'))
        self.banco.salvar(dados_rpv(conta_id=conta))
        self.banco.excluir(self.banco.salvar(dados_rpv(conta_id=conta)))
        self.assertEqual(self.banco.operacoes_da_conta([conta]), 2)
        self.assertEqual(self.banco.operacoes_da_conta([livre]), 0)
        self.assertEqual(self.banco.operacoes_da_conta([conta, livre]), 2)

    def test_snapshot_desativacao_reativacao_e_nome(self):
        identificador = self.banco.salvar_conta(dados_conta())
        rpv = self.banco.salvar(dados_rpv(conta_id=identificador))
        antigo = self.banco.obter(rpv)['conta_snapshot']
        self.banco.salvar_conta(dados_conta(pix='novo@example.com'), identificador)
        self.banco.ativar_conta(identificador, False)
        self.banco.salvar(dados_rpv(conta_id=identificador, observacoes='Editado'), rpv)
        self.assertEqual(self.banco.obter(rpv)['conta_snapshot'], antigo)
        self.assertEqual(json.loads(antigo)['pix'], 'teste@example.com')
        self.assertEqual(self.banco.obter(rpv)['nome'], 'Pessoa De Teste')
        self.assertNotIn(identificador, [c['id'] for c in self.banco.contas(True)])
        with self.assertRaises(ValueError):
            self.banco.salvar(dados_rpv(conta_id=identificador))
        self.banco.ativar_conta(identificador, True)
        novo = self.banco.salvar(dados_rpv(conta_id=identificador))
        self.assertEqual(json.loads(self.banco.obter(novo)['conta_snapshot'])['pix'], 'novo@example.com')

    def test_limites_e_prorrogacoes(self):
        for custo in (0, -1, 2000001):
            with self.subTest(custo=custo), self.assertRaises(ValueError):
                self.banco.salvar(dados_rpv(custo=custo))
        rpv = self.banco.salvar(dados_rpv(custo=2000000))
        outra = self.banco.salvar(dados_rpv())
        prorrogacao_antiga(self.banco, rpv, '2027-01-20')
        prorrogacao_antiga(self.banco, rpv, '2027-02-20')
        lista = {r['id']: r for r in self.banco.listar()}
        self.assertEqual(lista[rpv]['total_prorrogacoes'], 2)
        self.assertEqual(lista[rpv]['previsao_atual'], '2027-02-20')
        self.assertEqual(lista[rpv]['previsao'], '2026-12-20')
        self.assertEqual(lista[outra]['total_prorrogacoes'], 0)
        self.banco.excluir(rpv)
        self.assertEqual(self.banco.obter(rpv)['total_prorrogacoes'], 2)
        self.assertIsNotNone(self.banco.obter(rpv)['lixeira_em'])
        self.assertIsNotNone(self.banco.obter(outra))

    def test_migracao_com_backup_preserva_registros_antigos_invalidos(self):
        antigo = Path(self.pasta.name) / 'antigo.sqlite3'
        with closing(sqlite3.connect(antigo)) as con, con:
            con.execute('''CREATE TABLE rpvs (id INTEGER PRIMARY KEY, nome TEXT, aquisicao TEXT,
                previsto INTEGER, custo INTEGER, conta TEXT CHECK(conta IN ('Vitor','Lilian')),
                previsao TEXT, comissao INTEGER, observacoes TEXT)''')
            con.execute("INSERT INTO rpvs VALUES (42,'Titular antigo','2026-10-01',100,0,'Lilian','2026-12-01',23,'Preservar')")
        migrado = Banco(antigo)
        registro = migrado.obter(42)
        self.assertEqual((registro['nome'], registro['custo'], registro['comissao'], registro['observacoes']),
                         ('Titular antigo', 0, 23, 'Preservar'))
        self.assertEqual(json.loads(registro['conta_snapshot'])['identificacao'], 'Lilian')
        self.assertEqual(len(list(Path(self.pasta.name).glob('backup-antes-0.4.0-*.sqlite3'))), 1)
        with migrado.conectar() as con:
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
        Banco(antigo)
        self.assertEqual(len(list(Path(self.pasta.name).glob('backup-antes-0.4.0-*.sqlite3'))), 1)
        nova = migrado.salvar_conta(dados_conta())
        migrado.salvar(dados_rpv(conta_id=nova))

    def test_instalacao_nova_comeca_sem_contas_e_nao_recria_ao_reabrir(self):
        novo = Path(self.pasta.name) / 'novo.sqlite3'
        self.assertEqual(Banco(novo).contas(), [])
        vitor = next(c for c in self.banco.contas() if c['identificacao'] == 'Vitor')
        self.banco.salvar_conta(dados_conta(identificacao='Vitor Banco Teste'), vitor['id'])
        reaberto = Banco(self.caminho)
        self.assertEqual(len(reaberto.contas()), 2)
        self.assertNotIn('Vitor', [c['identificacao'] for c in reaberto.contas()])
        self.assertEqual(Banco(novo).contas(), [])

    def test_remocao_conta_preserva_operacoes_e_snapshot(self):
        conta = self.banco.salvar_conta(dados_conta(endereco='rua das flores'))
        self.assertEqual(self.banco.obter_conta(conta)['endereco'], 'Rua Das Flores')
        rpv = self.banco.salvar(dados_rpv(conta_id=conta))
        snapshot = self.banco.obter(rpv)['conta_snapshot']
        self.banco.remover_contas([conta])
        self.assertEqual(self.banco.obter(rpv)['conta_snapshot'], snapshot)
        self.assertIsNone(self.banco.obter(rpv)['conta_id'])
        self.assertIsNone(self.banco.obter_conta(conta))
        outra = self.banco.salvar_conta(dados_conta(identificacao='Outra', cpf='11144477735', numero='999', pix='outra@example.com'))
        self.banco.remover_contas([outra])
        self.assertIsNone(self.banco.obter_conta(outra))

    def test_recebimento_persistencia_limites_e_correcao(self):
        from datetime import date, timedelta
        identificador = self.banco.salvar(dados_rpv())
        self.banco.registrar_recebimento(identificador, '2026-10-22')
        reaberto = Banco(self.caminho)
        self.assertEqual(reaberto.obter(identificador)['recebimento'], '2026-10-22')
        for data in ('2026-10-01', (date.today() + timedelta(days=1)).isoformat()):
            with self.subTest(data=data), self.assertRaises(ValueError):
                reaberto.registrar_recebimento(identificador, data)
        reaberto.salvar(dados_rpv(observacoes='Editado'), identificador)
        self.assertEqual(reaberto.obter(identificador)['recebimento'], '2026-10-22')
        reaberto.registrar_recebimento(identificador, None)
        self.assertIsNone(reaberto.obter(identificador)['recebimento'])

    def test_migracao_050_preserva_contas_snapshots_e_prorrogacoes(self):
        identificador = self.banco.salvar(dados_rpv())
        prorrogacao_antiga(self.banco, identificador, '2027-01-20')
        snapshot = self.banco.obter(identificador)['conta_snapshot']
        with self.banco.conectar() as con:
            con.execute('ALTER TABLE rpvs DROP COLUMN recebimento')
            con.execute('PRAGMA user_version=1')
        migrado = Banco(self.caminho)
        self.assertEqual(migrado.obter(identificador)['conta_snapshot'], snapshot)
        self.assertIsNone(migrado.obter(identificador)['recebimento'])
        self.assertEqual(migrado.obter(identificador)['total_prorrogacoes'], 1)
        backups = list(Path(self.pasta.name).glob('backup-antes-0.6.0-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as con:
            colunas = [r[1] for r in con.execute('PRAGMA table_info(rpvs)')]
            self.assertNotIn('recebimento', colunas)
        Banco(self.caminho)
        self.assertEqual(len(list(Path(self.pasta.name).glob('backup-antes-0.6.0-*.sqlite3'))), 1)

    def test_endereco_completo_uf_e_snapshot(self):
        from dados import ESTADOS
        self.assertEqual(len(set(ESTADOS)), 27)
        self.assertTrue({'SP', 'PR', 'DF'}.issubset(ESTADOS))
        conta = self.banco.salvar_conta(dados_conta(numero_endereco='S/N', cidade='sao paulo', estado='sp'))
        self.assertEqual(self.banco.obter_conta(conta)['cidade'], 'Sao Paulo')
        self.assertEqual(self.banco.obter_conta(conta)['estado'], 'SP')
        rpv = self.banco.salvar(dados_rpv(conta_id=conta))
        snapshot = self.banco.obter(rpv)['conta_snapshot']
        self.assertEqual(json.loads(snapshot)['numero_endereco'], 'S/N')
        self.banco.salvar_conta(dados_conta(cidade='Curitiba', estado='PR'), conta)
        self.assertEqual(self.banco.obter(rpv)['conta_snapshot'], snapshot)
        for uf in ('ZZ', ''):
            with self.subTest(uf=uf), self.assertRaises(ValueError):
                self.banco.salvar_conta(dados_conta(estado=uf), conta)

    def test_migracao_060_e_edicao_previsao(self):
        identificador = self.banco.salvar(dados_rpv())
        prorrogacao_antiga(self.banco, identificador, '2027-01-20')
        self.banco.registrar_recebimento(identificador, '2026-10-22')
        snapshot = self.banco.obter(identificador)['conta_snapshot']
        with self.banco.conectar() as con:
            con.execute('ALTER TABLE rpvs DROP COLUMN previsao_atual_definida')
            for campo in ('numero_endereco', 'cidade', 'estado'):
                con.execute(f'ALTER TABLE contas DROP COLUMN {campo}')
            con.execute('PRAGMA user_version=2')
        migrado = Banco(self.caminho)
        self.assertEqual(migrado.obter(identificador)['previsao_atual'], '2027-01-20')
        self.assertEqual(migrado.obter(identificador)['recebimento'], '2026-10-22')
        self.assertEqual(migrado.obter(identificador)['conta_snapshot'], snapshot)
        self.assertEqual(migrado.contas()[0]['cidade'], '')
        self.assertEqual(len(list(Path(self.pasta.name).glob('backup-antes-0.7.0-*.sqlite3'))), 1)
        migrado.atualizar_previsao(identificador, '2027-02-20')
        migrado.atualizar_previsao(identificador, '2026-12-20')
        self.assertEqual(migrado.obter(identificador)['previsao_atual'], '2026-12-20')
        self.assertEqual(migrado.obter(identificador)['total_prorrogacoes'], 1)
        migrado.atualizar_previsao(identificador, '2026-12-01')
        with self.assertRaises(ValueError):
            migrado.atualizar_previsao(identificador, '2026-10-01')
        self.assertEqual(migrado.obter(identificador)['previsao_atual'], '2026-12-01')
        Banco(self.caminho)
        self.assertEqual(len(list(Path(self.pasta.name).glob('backup-antes-0.7.0-*.sqlite3'))), 1)


if __name__ == '__main__':
    unittest.main()
