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
    return scrypt.scrypt(texto, sal, SCRYPT.N, SCRYPT.r, SCRYPT.p, SCRYPT.tamanho, aoProgredir);
  }

  function iguais(a, b) {
    return a && b && a.length === b.length && a.every((x, i) => x === b[i]);
  }

  // `acesso` traz a senha ou a chave já calculada deste backup ({sal, bruta}, guardada pelo Face ID): com a
  // chave, a conferência demorada da senha (scrypt) é pulada. Devolve o conteúdo e a chave usada.
  async function decifrar(bytes, acesso, aoProgredir = () => {}) {
    if (bytes.length < CABECALHO + ETIQUETA || !cifrado(bytes)) {
      throw new ErroBackup('O arquivo não é um backup com senha do Gestor de RPV.');
    }
    const cabecalho = bytes.subarray(0, CABECALHO);
    const sal = cabecalho.subarray(MAGICO.length, MAGICO.length + TAMANHO_SAL);
    const prefixo = cabecalho.subarray(MAGICO.length + TAMANHO_SAL);
    let bruta;
    if (acesso.chave && iguais(acesso.chave.sal, sal)) {
      bruta = acesso.chave.bruta;
    } else if (acesso.senha) {
      bruta = await derivarChave(acesso.senha, sal, (p) => aoProgredir('senha', p));
    } else {
      throw new SenhaIncorreta('Este backup é protegido por senha.');
    }
    const chave = await crypto.subtle.importKey('raw', bruta, 'AES-GCM', false, ['decrypt']);
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
    return { conteudo: resultado, chave: { sal: Uint8Array.from(sal), bruta: Uint8Array.from(bruta) } };
  }

  // Cifra no mesmo formato de cifra.cifrar_arquivo, com a chave do backup aberto (mesmo sal): o computador abre
  // com a senha dos backups, e o celular não precisa refazer a conferência demorada da senha.
  async function cifrar(conteudo, chave) {
    const prefixo = crypto.getRandomValues(new Uint8Array(TAMANHO_PREFIXO));
    const cabecalho = new Uint8Array(CABECALHO);
    cabecalho.set(MAGICO, 0);
    cabecalho.set(chave.sal, MAGICO.length);
    cabecalho.set(prefixo, MAGICO.length + TAMANHO_SAL);
    const aes = await crypto.subtle.importKey('raw', chave.bruta, 'AES-GCM', false, ['encrypt']);
    const partes = [cabecalho];
    let total = CABECALHO;
    for (let inicio = 0, indice = 0; ; inicio += BLOCO, indice += 1) {
      const fim = Math.min(inicio + BLOCO, conteudo.length);
      const ultimo = fim === conteudo.length;
      const parte = new Uint8Array(await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: nonce(prefixo, indice, ultimo), additionalData: cabecalho, tagLength: 128 },
        aes, conteudo.subarray(inicio, fim)));
      partes.push(parte);
      total += parte.length;
      if (ultimo) {
        break;
      }
    }
    const resultado = new Uint8Array(total);
    let posicao = 0;
    for (const parte of partes) {
      resultado.set(parte, posicao);
      posicao += parte.length;
    }
    return resultado;
  }

  // O sal de um arquivo cifrado (para saber se a chave do backup aberto agora serve para ele).
  function salDe(bytes) {
    return cifrado(bytes) ? bytes.slice(MAGICO.length, MAGICO.length + TAMANHO_SAL) : null;
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

  // Um anexo do backup ("12/abc….pdf", como gravado na tabela documentos), conferido pelo hash do manifesto.
  async function extrairDocumento(zip, manifesto, caminho) {
    const nome = 'documentos/' + caminho;
    const esperado = manifesto.arquivos[nome];
    if (!esperado || caminho.includes('..')) {
      throw new ErroBackup('Este documento não está no backup.');
    }
    let arquivos;
    try {
      arquivos = fflate.unzipSync(zip, { filter: (f) => f.name === nome });
    } catch (erro) {
      throw new ErroBackup('Não foi possível abrir o documento.');
    }
    const bytes = arquivos[nome];
    if (!bytes || await sha256(bytes) !== esperado) {
      throw new ErroBackup('O documento do backup está danificado ou foi alterado.');
    }
    return bytes;
  }

  let carregarSql = null;

  function sqlJs() {
    // O motor do SQLite (WebAssembly) só é carregado uma vez.
    carregarSql = carregarSql || initSqlJs({ locateFile: (nome) => 'vendor/' + nome });
    return carregarSql;
  }

  // Lê o backup inteiro. Devolve o banco aberto (somente para consulta), o manifesto e os tempos de cada etapa.
  async function ler(bytes, senha, { aoProgredir = () => {}, comAnexos = false, chave = null } = {}) {
    const tempos = {};
    let marca = performance.now();
    const medir = (etapa) => {
      const agora = performance.now();
      tempos[etapa] = Math.round(agora - marca);
      marca = agora;
    };
    const ehCifrado = cifrado(bytes);
    let zip = bytes;
    let chaveUsada = null;
    if (ehCifrado) {
      ({ conteudo: zip, chave: chaveUsada } = await decifrar(bytes, { senha, chave }, aoProgredir));
      medir('decifrar');
    } else if (!comeca(bytes, [0x50, 0x4b])) {
      throw new ErroBackup('O arquivo não é um backup do Gestor de RPV.');
    }
    const { manifesto, banco, arquivos } = await abrirPacote(zip, comAnexos);
    medir('descompactar');
    const SQL = await sqlJs();
    const db = new SQL.Database(banco);
    medir('abrir_banco');
    // Os anexos ficam compactados na memória e só são extraídos quando a pessoa abre um deles.
    const extrair = (caminho) => extrairDocumento(zip, manifesto, caminho);
    return { db, manifesto, cifrado: ehCifrado, tempos, arquivos, extrair, chave: chaveUsada };
  }

  return { ler, decifrar, cifrar, salDe, cifrado, ErroBackup, SenhaIncorreta };
})();
