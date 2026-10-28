"""Abre e fecha o .exe em dados temporários e sem Python no PATH do processo."""
import ctypes
from contextlib import closing
from ctypes import wintypes
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time


def verificar(exe):
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    with tempfile.TemporaryDirectory(prefix='gestor-exe-teste-') as pasta:
        ambiente = dict(os.environ, LOCALAPPDATA=pasta)
        ambiente['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        processo = subprocess.Popen([str(exe)], env=ambiente)
        try:
            encontrada = []
            @callback
            def janela(hwnd, _):
                titulo = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, titulo, len(titulo))
                if titulo.value != 'Gestor de RPV' or not user32.IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                handle = kernel32.OpenProcess(0x1000, False, pid.value)
                if handle:
                    try:
                        caminho = ctypes.create_unicode_buffer(32768)
                        tamanho = wintypes.DWORD(len(caminho))
                        if kernel32.QueryFullProcessImageNameW(handle, 0, caminho, ctypes.byref(tamanho)) and Path(caminho.value).resolve() == exe:
                            encontrada.append(hwnd)
                    finally:
                        kernel32.CloseHandle(handle)
                return True
            limite = time.monotonic() + 45
            while not encontrada and time.monotonic() < limite:
                if processo.poll() is not None:
                    raise RuntimeError(f'O executável fechou antes de abrir a janela: {processo.returncode}')
                user32.EnumWindows(janela, 0)
                time.sleep(.2)
            if not encontrada:
                raise RuntimeError('A janela do executável não abriu em 45 segundos.')
            user32.PostMessageW(encontrada[0], 0x0010, 0, 0)  # WM_CLOSE
            if processo.wait(timeout=20) != 0:
                raise RuntimeError('O executável terminou com erro.')
            # closing fecha o arquivo; no Windows, um banco aberto impede apagar a pasta temporária.
            with closing(sqlite3.connect(Path(pasta) / 'GestorRPV' / 'gestor.sqlite3')) as con:
                assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert con.execute('PRAGMA user_version').fetchone()[0] == 8
                # Instalação nova abre com os dados fictícios de demonstração.
                assert con.execute('SELECT COUNT(*) FROM contas').fetchone()[0] == 2
                assert con.execute('SELECT COUNT(*) FROM rpvs').fetchone()[0] == 13
                assert con.execute("SELECT COUNT(*) FROM configuracoes WHERE chave='dados_demonstracao'").fetchone()[0] == 1
            print('Executável abriu, criou o banco temporário e fechou sem Python no PATH.')
        finally:
            if processo.poll() is None:
                subprocess.run(['taskkill', '/PID', str(processo.pid), '/T', '/F'], check=False)
                processo.wait(timeout=20)


def verificar_cifra(exe):
    """O .exe precisa levar a biblioteca de criptografia: sem ela, nenhum backup com senha é criado ou aberto."""
    with tempfile.TemporaryDirectory(prefix='gestor-exe-cifra-') as pasta:
        resultado = Path(pasta) / 'resultado.txt'
        ambiente = dict(os.environ, LOCALAPPDATA=pasta, GESTOR_RPV_AUTOTESTE_CIFRA=str(resultado))
        ambiente['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        codigo = subprocess.run([str(exe)], env=ambiente, timeout=120).returncode
        texto = resultado.read_text(encoding='utf-8') if resultado.exists() else '(sem resultado)'
        if codigo != 0 or texto != 'ok':
            raise RuntimeError(f'Criptografia não funciona no executável (código {codigo}):\n{texto}')
    print('Executável cifra e decifra backups.')


if __name__ == '__main__':
    exe = Path(sys.argv[1]).resolve()
    verificar_cifra(exe)
    verificar(exe)
