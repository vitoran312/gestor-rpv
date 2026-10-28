// Leitura de um .rpvbackup no próprio aparelho, sem enviar nada a lugar nenhum.
//
// Espelha cifra.py e backup.py do programa no computador: cabeçalho MAGICO + sal + prefixo do nonce, blocos de
// 1 MiB em AES-256-GCM (nonce = prefixo + número do bloco + marcador de último bloco, cabeçalho como dado
// autenticado) e chave derivada da senha por scrypt. Dentro, um ZIP com manifesto.json, banco.sqlite3 e anexos.
'use strict';

const LeitorBackup = (() => {
  const MAGICO = new TextEncoder().encode('GRPVCIF1');
  const TAMANHO_SAL = 16;
  const TAMANHO_PREFIXO = 7;
  const CABECALHO = MAGICO.length + TAMANHO_SAL + TAMANHO_PREFIXO;
  const BLOCO = 1024 * 1024;
  const ETIQUETA = 16;
  const SCRYPT = { N: 2 ** 15, r: 8, p: 1, tamanho: 32 };
  const FORMATO = 'gestor-rpv-backup';

  class ErroBackup extends Error {}
  class SenhaIncorreta extends ErroBackup {}

  function comeca(bytes, prefixo) {
    return bytes.length >= prefixo.length && prefixo.every((b, i) => bytes[i] === b);
  }

  function cifrado(bytes) {
    return comeca(bytes, MAGICO);
  }

  function nonce(prefixo, indice, ultimo) {
    const resultado = new Uint8Array(12);
    resultado.set(prefixo, 0);
    new DataView(resultado.buffer).setUint32(TAMANHO_PREFIXO, indice, false);
    resultado[11] = ultimo ? 1 : 0;
    return resultado;
  }

  async function derivarChave(senha, sal, aoProgredir) {
    // NFC: a mesma senha com acentos dá a mesma chave, como em cifra.derivar_chave.
    const texto = new TextEncoder().encode(senha.normalize('NFC'));
    const bruta = await scrypt.scrypt(texto, sal, SCRYPT.N, SCRYPT.r, SCRYPT.p, SCRYPT.tamanho, aoProgredir);
    return crypto.subtle.importKey('raw', bruta, 'AES-GCM', false, ['decrypt']);
  }

  async function decifrar(bytes, senha, aoProgredir = () => {}) {
    if (bytes.length < CABECALHO + ETIQUETA || !cifrado(bytes)) {
      throw new ErroBackup('O arquivo não é um backup com senha do Gestor de RPV.');
    }
    const cabecalho = bytes.subarray(0, CABECALHO);
    const sal = cabecalho.subarray(MAGICO.length, MAGICO.length + TAMANHO_SAL);
    const prefixo = cabecalho.subarray(MAGICO.length + TAMANHO_SAL);
    const chave = await derivarChave(senha, sal, (p) => aoProgredir('senha', p));
    const partes = [];
    let total = 0;
    for (let inicio = CABECALHO, indice = 0; inicio < bytes.length; inicio += BLOCO + ETIQUETA, indice += 1) {
      const fim = Math.min(inicio + BLOCO + ETIQUETA, bytes.length);
      const ultimo = fim === bytes.length;
      let parte;
      try {
        parte = await crypto.subtle.decrypt(
          { name: 'AES-GCM', iv: nonce(prefixo, indice, ultimo), additionalData: cabecalho, tagLength: 128 },
          chave, bytes.subarray(inicio, fim));
      } catch (erro) {
        throw new SenhaIncorreta('Senha incorreta, ou o backup foi alterado ou está incompleto.');
      }
      partes.push(new Uint8Array(parte));
      total += parte.byteLength;
      aoProgredir('decifrar', fim / bytes.length);
    }
    const resultado = new Uint8Array(total);
    let posicao = 0;
    for (const parte of partes) {
      resultado.set(parte, posicao);
      posicao += parte.length;
    }
    return resultado;
  }

  async function sha256(bytes) {
    const resumo = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
    return Array.from(resumo, (b) => b.toString(16).padStart(2, '0')).join('');
  }

  async function abrirPacote(zip, comAnexos) {
    let arquivos;
    try {
      // Sem os anexos, só o banco e o manifesto são descompactados: menos memória no celular.
      arquivos = fflate.unzipSync(zip, { filter: (f) => comAnexos || !f.name.startsWith('documentos/') });
    } catch (erro) {
      throw new ErroBackup('O arquivo não é um backup válido do Gestor de RPV.');
    }
    let manifesto;
    try {
      manifesto = JSON.parse(new TextDecoder().decode(arquivos['manifesto.json']));
    } catch (erro) {
      throw new ErroBackup('Manifesto do backup ausente ou ilegível.');
    }
    if (!manifesto || manifesto.formato !== FORMATO || manifesto.versao_formato !== 1 || !manifesto.arquivos) {
      throw new ErroBackup('Formato de backup não reconhecido.');
    }
    const banco = arquivos['banco.sqlite3'];
    if (!banco || await sha256(banco) !== manifesto.arquivos['banco.sqlite3']) {
      throw new ErroBackup('O banco do backup está danificado ou foi alterado.');
    }
    return { manifesto, banco, arquivos };
  }

  let carregarSql = null;

  function sqlJs() {
    // O motor do SQLite (WebAssembly) só é carregado uma vez.
    carregarSql = carregarSql || initSqlJs({ locateFile: (nome) => 'vendor/' + nome });
    return carregarSql;
  }

  // Lê o backup inteiro. Devolve o banco aberto (somente para consulta), o manifesto e os tempos de cada etapa.
  async function ler(bytes, senha, { aoProgredir = () => {}, comAnexos = false } = {}) {
    const tempos = {};
    let marca = performance.now();
    const medir = (etapa) => {
      const agora = performance.now();
      tempos[etapa] = Math.round(agora - marca);
      marca = agora;
    };
    const ehCifrado = cifrado(bytes);
    let zip = bytes;
    if (ehCifrado) {
      if (!senha) {
        throw new SenhaIncorreta('Este backup é protegido por senha.');
      }
      zip = await decifrar(bytes, senha, aoProgredir);
      medir('decifrar');
    } else if (!comeca(bytes, [0x50, 0x4b])) {
      throw new ErroBackup('O arquivo não é um backup do Gestor de RPV.');
    }
    const { manifesto, banco, arquivos } = await abrirPacote(zip, comAnexos);
    medir('descompactar');
    const SQL = await sqlJs();
    const db = new SQL.Database(banco);
    medir('abrir_banco');
    return { db, manifesto, cifrado: ehCifrado, tempos, arquivos };
  }

  return { ler, decifrar, cifrado, ErroBackup, SenhaIncorreta };
})();
