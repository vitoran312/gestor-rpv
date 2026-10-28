import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import demonstracao
from dados import Banco, situacao
from apoio_testes import dados_conta, dados_rpv


class TestDemonstracao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.caminho = Path(self.temp.name) / 'gestor.sqlite3'

    def test_carrega_somente_em_instalacao_nova_e_vazia(self):
        banco = Banco(self.caminho)
        self.assertTrue(banco.novo)
        self.assertTrue(demonstracao.deve_carregar(banco))
        reaberto = Banco(self.caminho)
        self.assertFalse(reaberto.novo)
        self.assertFalse(demonstracao.deve_carregar(reaberto))
        outro = Banco(Path(self.temp.name) / 'outro.sqlite3')
        outro.salvar_conta(dados_conta())
        self.assertFalse(demonstracao.deve_carregar(outro))

    def test_mesmo_cenario_em_qualquer_data(self):
        for hoje in (demonstracao.REFERENCIA, date(2027, 6, 15), date(2030, 1, 2)):
            with self.subTest(hoje=hoje):
                banco = Banco(Path(self.temp.name) / f'{hoje}.sqlite3')
                # O cadastro recusa recebimentos futuros pela data real; aqui o relógio é o dia simulado.
                dia_simulado = type('Dia', (date,), {'today': classmethod(lambda cls, h=hoje: h)})
                with patch('dados.date', dia_simulado):
                    demonstracao.carregar(banco, hoje=hoje)
                registros = banco.listar()
                self.assertEqual(len(registros), 13)
                self.assertEqual(len(banco.contas()), 2)
                situacoes = [situacao(r, hoje) for r in registros]
                self.assertEqual({s: situacoes.count(s) for s in set(situacoes)},
                                 {'pendente': 5, 'atrasada': 4, 'recebida': 4})
                self.assertTrue(all(r['recebimento'] <= hoje.isoformat() for r in registros if r['recebimento']))
                self.assertEqual(sum(r['previsto'] - r['custo'] for r in registros), 8640000)
                self.assertTrue(demonstracao.ativa(banco))

    def test_remover_apaga_so_a_demonstracao(self):
        banco = Banco(self.caminho)
        demonstracao.carregar(banco)
        conta_demo = banco.contas()[0]
        propria = banco.salvar(dados_rpv(nome='Minha operação', conta_id=conta_demo['id']))
        conta_propria = banco.salvar_conta(dados_conta(identificacao='Minha conta', cpf='11144477735',
                                                       numero='55555-5', pix='minha@exemplo.com'))
        demonstracao.remover(banco)
        self.assertFalse(demonstracao.ativa(banco))
        self.assertEqual([r['id'] for r in banco.listar()], [propria])
        self.assertEqual([c['id'] for c in banco.contas()], [conta_propria])
        restante = banco.obter(propria)
        self.assertIsNone(restante['conta_id'])
        self.assertEqual(restante['conta'], conta_demo['identificacao'])
        with banco.conectar() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM previsoes_historico').fetchone()[0], 0)
        demonstracao.remover(banco)
        self.assertEqual(len(banco.listar()), 1)

    def test_remover_nao_apaga_cadastro_que_reaproveitou_o_numero_de_um_ficticio(self):
        banco = Banco(self.caminho)
        demonstracao.carregar(banco)
        ultima_operacao = max(r['id'] for r in banco.listar())
        ultima_conta = max(c['id'] for c in banco.contas())
        # A pessoa exclui de vez a última operação e a última conta fictícias...
        banco.excluir(ultima_operacao)
        banco.excluir_permanentemente([ultima_operacao])
        banco.remover_contas([ultima_conta])
        # ...e o SQLite dá os mesmos números aos cadastros dela.
        conta = banco.salvar_conta(dados_conta(identificacao='Minha conta', cpf='11144477735',
                                               numero='55555-5', pix='minha@exemplo.com'))
        propria = banco.salvar(dados_rpv(nome='Cliente Real', conta_id=conta))
        self.assertEqual((propria, conta), (ultima_operacao, ultima_conta))
        anexo = Path(self.temp.name) / 'contrato.pdf'
        anexo.write_bytes(b'%PDF-ficticio')
        ficticia = banco.listar()[-1]['id']
        banco.salvar(dict(banco.obter(ficticia)), ficticia, anexos=[anexo])
        arquivo = banco.caminho_documento(banco.documentos(ficticia)[0]['id'])
        demonstracao.remover(banco)
        self.assertEqual([r['nome'] for r in banco.listar()], ['Cliente Real'])
        self.assertEqual(banco.obter(propria)['conta_id'], conta)
        self.assertEqual([c['identificacao'] for c in banco.contas()], ['Minha conta'])
        self.assertFalse(arquivo.exists())

    def test_registro_editado_ou_cadastrado_pela_pessoa_deixa_de_ser_ficticio(self):
        banco = Banco(self.caminho)
        demonstracao.carregar(banco)
        editada = banco.listar()[0]
        banco.salvar(dict(editada, observacoes='Meu cliente de verdade'), editada['id'])
        demonstracao.adotar(banco, operacao=editada['id'])
        # Número reaproveitado com o mesmo nome fictício: o cadastro é da pessoa.
        ultima = max(r['id'] for r in banco.listar())
        nome = banco.obter(ultima)['nome']
        banco.excluir(ultima)
        banco.excluir_permanentemente([ultima])
        conta = banco.contas()[0]
        recadastrada = banco.salvar(dados_rpv(nome=nome, conta_id=conta['id']))
        demonstracao.adotar(banco, operacao=recadastrada)
        demonstracao.adotar(banco, conta=conta['id'])
        demonstracao.remover(banco)
        self.assertEqual(sorted(r['id'] for r in banco.listar()), sorted([editada['id'], recadastrada]))
        self.assertEqual([c['id'] for c in banco.contas()], [conta['id']])

    def test_carga_que_falha_no_meio_nao_deixa_nada_ficticio(self):
        banco = Banco(self.caminho)
        with patch.object(banco, 'registrar_recebimento', side_effect=ValueError('falha simulada')):
            with self.assertRaises(ValueError):
                demonstracao.carregar(banco)
        self.assertEqual((banco.listar(), banco.contas()), ([], []))
        self.assertFalse(demonstracao.ativa(banco))

    def test_carga_interrompida_a_forca_e_limpa_e_refeita_na_abertura_seguinte(self):
        banco = Banco(self.caminho)
        with patch.object(banco, 'registrar_recebimento', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                demonstracao.carregar(banco)
        self.assertEqual((banco.listar(), banco.contas()), ([], []))
        # Encerramento sem chance de limpar (energia, Gerenciador de Tarefas): fica a anotação "carregando".
        demonstracao.anotar(banco, [banco.salvar_conta(demonstracao.CONTAS[0])], [], carregando=True)
        reaberto = Banco(self.caminho)
        self.assertTrue(demonstracao.limpar_carga_interrompida(reaberto))
        self.assertEqual(reaberto.contas(), [])
        self.assertTrue(demonstracao.deve_carregar(reaberto, recomecar=True))

    def test_anotacao_adulterada_nao_trava_quem_salva_nem_quem_apaga(self):
        banco = Banco(self.caminho)
        for anotacao in ('{"operacoes": "x"}', '[1, 2]', 'nao e json', '{"contas": [1, "2"]}'):
            with self.subTest(anotacao=anotacao):
                banco.salvar_configuracao(demonstracao.CHAVE, anotacao)
                demonstracao.adotar(banco, operacao=1)
                demonstracao.remover(banco)
                self.assertFalse(demonstracao.ativa(banco))

    def test_conta_ficticia_usada_por_operacao_propria_e_contada_antes_de_apagar(self):
        banco = Banco(self.caminho)
        demonstracao.carregar(banco)
        propria = banco.salvar(dados_rpv(nome='Cliente Real', conta_id=banco.contas()[0]['id']))
        demonstracao.adotar(banco, operacao=propria)
        self.assertEqual(demonstracao.operacoes_proprias_em_contas_ficticias(banco), 1)


if __name__ == '__main__':
    unittest.main()
