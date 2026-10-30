// Backup na nuvem (o Worker da Cloudflare em nuvem/worker.js). O app manda o mesmo arquivo trancado que guarda no
// aparelho; lá ele é só uma sequência de bytes, que sem a senha ninguém lê. O identificador e a chave de acesso
// saem da senha, com a mesma conta de nuvem.py: o programa no computador acha o backup sem cadastro nenhum.
'use strict';

const Nuvem = (() => {
  const ENDERECO = 'https://gestor-rpv.gestor-rpv-vitor.workers.dev';
  const SAL = new TextEncoder().encode('gestor-rpv/nuvem/v1');

  class ErroNuvem extends Error {
    constructor(mensagem, { conflito = false, criadoEm = null } = {}) {
      super(mensagem);
      this.conflito = conflito;
      this.criadoEm = criadoEm;
    }
  }

  const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
  const sha256 = async (bytes) => hex(await crypto.subtle.digest('SHA-256', bytes));

  function juntar(...partes) {
    const total = new Uint8Array(partes.reduce((t, p) => t + p.length, 0));
    let posicao = 0;
    partes.forEach((p) => { total.set(p, posicao); posicao += p.length; });
    return total;
  }

  // {id, chave}: scrypt da senha (NFC, como cifra.derivar_chave) com um sal fixo; leva um ou dois segundos.
  async function credenciais(senha, aoProgredir) {
    const texto = new TextEncoder().encode(senha.normalize('NFC'));
    const base = Uint8Array.from(await scrypt.scrypt(texto, SAL, 2 ** 15, 8, 1, 32, aoProgredir));
    const id = (await sha256(juntar(base, new TextEncoder().encode('id')))).slice(0, 32);
    return { id, chave: await sha256(juntar(base, new TextEncoder().encode('acesso'))) };
  }

  async function pedir(caminho, { metodo = 'GET', chave, corpo, cabecalhos = {} } = {}) {
    let resposta;
    try {
      resposta = await fetch(ENDERECO + caminho, { method: metodo, body: corpo, cache: 'no-store',
        headers: { ...(chave ? { 'X-Gestor-Chave': chave } : {}), ...cabecalhos } });
    } catch (erro) {
      throw new ErroNuvem('Sem conexão com a internet.');
    }
    return resposta;
  }

  async function lerJson(resposta) {
    try {
      return await resposta.json();
    } catch (erro) {
      return {};
    }
  }

  // Manda o backup trancado. `sal` é o da cifra do arquivo: outro aparelho com a mesma senha não sobrescreve
  // sem `substituir`.
  async function enviar(cred, bytes, { sal, criadoEm, substituir = false }) {
    const resposta = await pedir(`/v1/backup/${cred.id}`, { metodo: 'PUT', chave: cred.chave, corpo: bytes, cabecalhos: {
      'Content-Type': 'application/octet-stream', 'X-Gestor-Sal': hex(sal), 'X-Gestor-Criado': criadoEm,
      'X-Gestor-Resumo': await sha256(bytes), ...(substituir ? { 'X-Gestor-Substituir': '1' } : {}) } });
    const corpo = await lerJson(resposta);
    if (resposta.status === 409) {
      throw new ErroNuvem(corpo.erro || 'Já existe outro backup na nuvem com esta senha.', { conflito: true, criadoEm: corpo.criado_em });
    }
    if (!resposta.ok) {
      throw new ErroNuvem(corpo.erro || `A nuvem respondeu ${resposta.status}.`);
    }
    return corpo;
  }

  async function consultar(cred) {
    const resposta = await pedir(`/v1/backup/${cred.id}`, { chave: cred.chave });
    if (resposta.status === 404) {
      return null;
    }
    if (!resposta.ok) {
      throw new ErroNuvem(`A nuvem respondeu ${resposta.status}.`);
    }
    return resposta.json();
  }

  async function baixar(cred, meta, aoProgredir = () => {}) {
    const partes = [];
    for (let n = 0; n < meta.partes; n += 1) {
      const resposta = await pedir(`/v1/backup/${cred.id}/${meta.versao}/${n}`, { chave: cred.chave });
      if (!resposta.ok) {
        throw new ErroNuvem('O backup da nuvem mudou durante o download; tente de novo.');
      }
      partes.push(new Uint8Array(await resposta.arrayBuffer()));
      aoProgredir((n + 1) / meta.partes);
    }
    const bytes = juntar(...partes);
    if (await sha256(bytes) !== meta.resumo) {
      throw new ErroNuvem('O backup baixado da nuvem não confere.');
    }
    return bytes;
  }

  async function apagar(cred) {
    const resposta = await pedir(`/v1/backup/${cred.id}`, { metodo: 'DELETE', chave: cred.chave });
    if (!resposta.ok && resposta.status !== 404) {
      throw new ErroNuvem(`A nuvem respondeu ${resposta.status}.`);
    }
  }

  // Lembretes: só as datas das previsões (sem nomes nem valores) e a assinatura de notificações deste aparelho.
  async function chaveVapid() {
    const resposta = await pedir('/v1/vapid');
    const { chave } = await lerJson(resposta);
    if (!resposta.ok || !chave) {
      throw new ErroNuvem('Os lembretes ainda não estão disponíveis.');
    }
    return chave;
  }

  async function guardarLembretes(cred, assinatura, previsoes) {
    const resposta = await pedir(`/v1/lembretes/${cred.id}`, { metodo: 'PUT', chave: cred.chave,
      corpo: JSON.stringify({ assinatura, previsoes, fuso: -new Date().getTimezoneOffset() }),
      cabecalhos: { 'Content-Type': 'application/json' } });
    if (!resposta.ok) {
      throw new ErroNuvem((await lerJson(resposta)).erro || `A nuvem respondeu ${resposta.status}.`);
    }
  }

  async function apagarLembretes(cred) {
    await pedir(`/v1/lembretes/${cred.id}`, { metodo: 'DELETE', chave: cred.chave });
  }

  return { ENDERECO, ErroNuvem, credenciais, enviar, consultar, baixar, apagar, chaveVapid, guardarLembretes,
    apagarLembretes, hex };
})();
