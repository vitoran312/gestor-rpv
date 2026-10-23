"""Limite semanal e datas do lembrete de backup."""
import unittest
from datetime import date

from backup import aviso_backup


class TestLembreteBackup(unittest.TestCase):
    def test_primeiro_backup_e_data_invalida(self):
        self.assertIn('ainda não fez', aviso_backup(None))
        self.assertIn('indisponível', aviso_backup('data inválida'))

    def test_limite_de_sete_dias_e_virada_do_mes(self):
        quando = '2026-10-28T12:00:00'
        self.assertEqual(aviso_backup(quando, date(2026, 11, 3)), '')
        self.assertIn('7 dias', aviso_backup(quando, date(2026, 11, 4)))
        self.assertIn('8 dias', aviso_backup(quando, date(2026, 11, 5)))

    def test_backup_recente_ou_relogio_atrasado(self):
        quando = '2026-10-28T12:00:00'
        self.assertEqual(aviso_backup(quando, date(2026, 10, 28)), '')
        self.assertEqual(aviso_backup(quando, date(2026, 10, 27)), '')


if __name__ == '__main__':
    unittest.main()
