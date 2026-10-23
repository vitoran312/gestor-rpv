"""Gera o executável portátil no Windows, sem incluir bancos ou anexos pessoais."""
import os
from pathlib import Path
import struct
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from versao import VERSAO


RAIZ = Path(__file__).resolve().parent


def informacoes_versao():
    numeros = tuple(int(n) for n in VERSAO.split('.')) + (0,)
    return f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros!r}, prodvers={numeros!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041604B0', [
    StringStruct('CompanyName', 'Vitoran Tech'),
    StringStruct('FileDescription', 'Gestor de RPV'),
    StringStruct('FileVersion', '{VERSAO}'),
    StringStruct('InternalName', 'GestorRPV'),
    StringStruct('OriginalFilename', 'Gestor de RPV.exe'),
    StringStruct('ProductName', 'Gestor de RPV'),
    StringStruct('ProductVersion', '{VERSAO}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])])
'''


def main():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        print('Gere este executável no Windows com Python de 64 bits.')
        return 1
    trabalho = RAIZ / 'build'
    destino = RAIZ / 'dist'
    trabalho.mkdir(exist_ok=True)
    versao_windows = trabalho / 'versao-windows.txt'
    versao_windows.write_text(informacoes_versao(), encoding='utf-8')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
        '--windowed', '--noupx', '--name', 'Gestor de RPV',
        '--icon', str(RAIZ / 'recursos' / 'vitoran-tech.ico'),
        '--add-data', str(RAIZ / 'recursos') + os.pathsep + 'recursos',
        '--version-file', str(versao_windows), '--distpath', str(destino),
        '--workpath', str(trabalho / 'pyinstaller'), '--specpath', str(trabalho),
        str(RAIZ / 'app.py'),
    ], cwd=RAIZ, check=True)
    exe = destino / 'Gestor de RPV.exe'
    leia_me = destino / 'LEIA-ME.txt'
    leia_me.write_text(
        f'Gestor de RPV {VERSAO} - Vitoran Tech\n\n'
        'Extraia o ZIP e abra Gestor de RPV.exe. Não precisa instalar Python.\n'
        'Programa portátil para Windows 11 de 64 bits.\n\n'
        'Dados e anexos ficam em %LOCALAPPDATA%\\GestorRPV, fora do executável.\n'
        'Para trocar de computador, use Arquivo > Fazer backup e Importar dados.\n'
        'Copiar apenas o executável não transfere seus registros.\n\n'
        'Desenvolvido por Vitor Alves Nascimento.\n', encoding='utf-8-sig')
    pacote = destino / f'GestorRPV-Windows-x64-v{VERSAO}.zip'
    with ZipFile(pacote, 'w', ZIP_DEFLATED) as zipado:
        zipado.write(exe, exe.name)
        zipado.write(leia_me, leia_me.name)
    print(f'Executável pronto: {exe}\nPacote para compartilhar: {pacote}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
