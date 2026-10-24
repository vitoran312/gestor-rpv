"""Roda os testes no CI com um vigia: falhas e testes travados viram anotações na página da execução."""
import os
import sys
import threading
import time
import traceback
import unittest
from pathlib import Path

LIMITE_SEGUNDOS = 120


def anotar(titulo, texto):
    # Anotações do GitHub Actions usam %0A como quebra de linha.
    texto = texto[-3000:].replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::error title={titulo}::{texto}', flush=True)


class Resultado(unittest.TextTestResult):
    atual = None
    inicio = 0.0

    def startTest(self, test):
        Resultado.atual, Resultado.inicio = test.id(), time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        Resultado.atual = None
        super().stopTest(test)

    def addError(self, test, err):
        super().addError(test, err)
        anotar(f'Erro em {test.id()}', ''.join(traceback.format_exception(*err)))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        anotar(f'Falha em {test.id()}', ''.join(traceback.format_exception(*err)))


def vigiar(principal):
    while True:
        time.sleep(5)
        teste = Resultado.atual
        if teste and time.monotonic() - Resultado.inicio > LIMITE_SEGUNDOS:
            pilha = ''.join(traceback.format_stack(sys._current_frames()[principal.ident]))
            anotar(f'Teste travado há mais de {LIMITE_SEGUNDOS} s: {teste}', pilha)
            os._exit(1)


def main():
    raiz = Path(__file__).resolve().parent.parent
    os.chdir(raiz)
    sys.path.insert(0, str(raiz))
    threading.Thread(target=vigiar, args=(threading.main_thread(),), daemon=True).start()
    suite = unittest.defaultTestLoader.discover(str(raiz))
    resultado = unittest.TextTestRunner(verbosity=2, resultclass=Resultado).run(suite)
    return 0 if resultado.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
