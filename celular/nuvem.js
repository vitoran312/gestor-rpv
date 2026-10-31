// A nuvem do Gestor (o Worker da Cloudflare em nuvem/worker.js).
//
// Os dados ficam num "cofre": o backup trancado com uma chave sorteada no celular (a chave dos dados). Cada pessoa
// com acesso tem um "envelope" com essa chave e com a do cofre, trancado com a senha DELA: é ele que abre os dados
// neste celular e que, guardado também na nuvem, permite recuperar tudo num celular novo só com a senha. Um
// convite é o mesmo conteúdo trancado com um código curto, que vale por 15 minutos e para uma pessoa.
//
// Os identificadores e as chaves de acesso de cada pessoa saem da senha (scrypt com o sal fixo do app), com a
// mesma conta de nuvem.py: nos dados antigos, criados antes do cofre, a senha também era a do cofre.
'use strict';

const Nuvem = (() => {
  const ENDERECO = 'https://gestor-rpv.gestor-rpv-vitor.workers.dev';
  const SAL = new TextEncoder().encode('gestor-rpv/nuvem/v1');
  const ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';  // Sem 0/O e 1/I/L, que se confundem ao ditar.

  class ErroNuvem extends Error {
    constructor(mensagem, extra = {}) {
      super(mensagem);
      Object.assign(this, { conflito: false, desatualizado: false, senhaEmUso: false, criadoEm: null }, extra);
    }
  }

  const codificar = new TextEncoder();
  const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
  const sha256 = async (bytes) => new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  const sha256hex = async (bytes) => hex(await sha256(bytes));
  const aleatorio = (n) => crypto.getRandomValues(new Uint8Array(n));

  function paraB64(bytes) {
    let texto = '';
    new Uint8Array(bytes).forEach((b) => { texto += String.fromCharCode(b); });
    return btoa(texto);
  }

  const deB64 = (texto) => Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));

  function juntar(...partes) {
    const total = new Uint8Array(partes.reduce((t, p) => t + p.length, 0));
    let posicao = 0;
    partes.forEach((p) => { total.set(p, posicao); posicao += p.length; });
    return total;
  }

  // {id, chave, envelope}: o identificador e a chave de acesso da pessoa e a chave que tranca o envelope dela,
  // tudo de um scrypt da senha (NFC, como cifra.derivar_chave); leva um ou dois segundos.
  async function credenciais(senha, aoProgredir) {
    const texto = codificar.encode(senha.normalize('NFC'));
    const base = Uint8Array.from(await scrypt.scrypt(texto, SAL, 2 ** 15, 8, 1, 32, aoProgredir));
    return {
      id: (await sha256hex(juntar(base, codificar.encode('id')))).slice(0, 32),
      chave: await sha256hex(juntar(base, codificar.encode('acesso'))),
      envelope: await sha256(juntar(base, codificar.encode('envelope'))),
    };
  }

  // Um cofre novo: identificador e chave de acesso sorteados (não dependem de senha nenhuma).
  const cofreNovo = () => ({ id: hex(aleatorio(16)), chave: hex(aleatorio(32)) });

  // Envelope: {sal, bruta, cofre} (a chave dos dados e as do cofre) cifrado em AES-GCM.
  async function fecharEnvelope(chave, conteudo) {
    const aes = await crypto.subtle.importKey('raw', chave, 'AES-GCM', false, ['encrypt']);
    const iv = aleatorio(12);
    const claro = codificar.encode(JSON.stringify({ sal: paraB64(conteudo.sal), bruta: paraB64(conteudo.bruta), cofre: conteudo.cofre }));
    return { iv: paraB64(iv), cifrado: paraB64(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aes, claro)) };
  }

  async function abrirEnvelope(chave, envelope) {
    try {
      const aes = await crypto.subtle.importKey('raw', chave, 'AES-GCM', false, ['decrypt']);
      const claro = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: deB64(envelope.iv) }, aes, deB64(envelope.cifrado));
      const conteudo = JSON.parse(new TextDecoder().decode(claro));
      return { sal: deB64(conteudo.sal), bruta: deB64(conteudo.bruta), cofre: conteudo.cofre };
    } catch (erro) {
      throw new ErroNuvem('Senha incorreta.', { senhaIncorreta: true });
    }
  }

  // Convite: um código de 10 letras e números (cerca de 50 bits), com o identificador e a chave saindo dele.
  function codigoNovo() {
    const letras = Array.from(aleatorio(10), (b) => ALFABETO[b % ALFABETO.length]).join('');
    return `${letras.slice(0, 5)}-${letras.slice(5)}`;
  }

  const normalizarCodigo = (codigo) => codigo.toUpperCase().replace(/[^A-Z0-9]/g, '');

  async function chavesDoConvite(codigo) {
    const limpo = normalizarCodigo(codigo);
    return { id: (await sha256hex(codificar.encode(`gestor-rpv/convite/id:${limpo}`))).slice(0, 32),
      chave: await sha256(codificar.encode(`gestor-rpv/convite/chave:${limpo}`)), valido: limpo.length === 10 };
  }

  async function pedir(caminho, { metodo = 'GET', chave, corpo, cabecalhos = {} } = {}) {
    try {
      return await fetch(ENDERECO + caminho, { method: metodo, body: corpo, cache: 'no-store',
        headers: { ...(chave ? { 'X-Gestor-Chave': chave } : {}), ...cabecalhos } });
    } catch (erro) {
      throw new ErroNuvem('Sem conexão com a internet.', { semConexao: true });
    }
  }

  async function lerJson(resposta) {
    try {
      return await resposta.json();
    } catch (erro) {
      return {};
    }
  }

  async function falha(resposta) {
    const corpo = await lerJson(resposta);
    return new ErroNuvem(corpo.erro || `A nuvem respondeu ${resposta.status}.`, {
      conflito: Boolean(corpo.conflito), desatualizado: Boolean(corpo.desatualizado), senhaEmUso: Boolean(corpo.senha_em_uso),
      criadoEm: corpo.criado_em || null, status: resposta.status });
  }

  const provaDoCofre = (cofre) => ({ 'X-Gestor-Cofre': cofre.id, 'X-Gestor-Cofre-Chave': cofre.chave });

  // ---- Backup ----
  // `base`: a versão da nuvem de que estes dados partiram; se outro aparelho gravou depois, a nuvem recusa
  // (desatualizado) e o app junta as mudanças antes de mandar de novo.
  async function enviar(cofre, bytes, { sal, criadoEm, base = null, substituir = false }) {
    const resposta = await pedir(`/v1/backup/${cofre.id}`, { metodo: 'PUT', chave: cofre.chave, corpo: bytes, cabecalhos: {
      'Content-Type': 'application/octet-stream', 'X-Gestor-Sal': hex(sal), 'X-Gestor-Criado': criadoEm,
      'X-Gestor-Resumo': await sha256hex(bytes), ...(base ? { 'X-Gestor-Base': base } : {}),
      ...(substituir ? { 'X-Gestor-Substituir': '1' } : {}) } });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return resposta.json();
  }

  async function consultar(cofre) {
    const resposta = await pedir(`/v1/backup/${cofre.id}`, { chave: cofre.chave });
    if (resposta.status === 404) {
      return null;
    }
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return resposta.json();
  }

  async function baixar(cofre, meta, aoProgredir = () => {}) {
    const partes = [];
    for (let n = 0; n < meta.partes; n += 1) {
      const resposta = await pedir(`/v1/backup/${cofre.id}/${meta.versao}/${n}`, { chave: cofre.chave });
      if (!resposta.ok) {
        throw new ErroNuvem('Os dados da nuvem mudaram durante o download; tente de novo.');
      }
      partes.push(new Uint8Array(await resposta.arrayBuffer()));
      aoProgredir((n + 1) / meta.partes);
    }
    const bytes = juntar(...partes);
    if (await sha256hex(bytes) !== meta.resumo) {
      throw new ErroNuvem('Os dados baixados da nuvem não conferem.');
    }
    return bytes;
  }

  async function apagar(cofre) {
    const resposta = await pedir(`/v1/backup/${cofre.id}`, { metodo: 'DELETE', chave: cofre.chave });
    if (!resposta.ok && resposta.status !== 404) {
      throw await falha(resposta);
    }
  }

  // ---- Pessoas com acesso ----
  async function lerMembro(membro) {
    const resposta = await pedir(`/v1/membro/${membro.id}`, { chave: membro.chave });
    if (resposta.status === 404) {
      return null;
    }
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return resposta.json();
  }

  // `anterior`: o cofre de antes, quando a pessoa troca a chave dos dados (prova que é ela mesma).
  async function guardarMembro(membro, cofre, { envelope, nome = '', convite = null, anterior = null }) {
    const resposta = await pedir(`/v1/membro/${membro.id}`, { metodo: 'PUT', chave: membro.chave,
      corpo: JSON.stringify({ envelope, nome }), cabecalhos: { 'Content-Type': 'application/json', ...provaDoCofre(cofre),
        ...(convite ? { 'X-Gestor-Convite': convite } : {}),
        ...(anterior ? { 'X-Gestor-Anterior': anterior.id, 'X-Gestor-Anterior-Chave': anterior.chave } : {}) } });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
  }

  async function apagarMembro(id, cofre) {
    const resposta = await pedir(`/v1/membro/${id}`, { metodo: 'DELETE', cabecalhos: provaDoCofre(cofre) });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
  }

  async function listarMembros(cofre) {
    const resposta = await pedir(`/v1/cofre/${cofre.id}/membros`, { chave: cofre.chave });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return (await resposta.json()).membros;
  }

  async function guardarConvite(cofre, convite, envelope) {
    const resposta = await pedir(`/v1/convite/${convite.id}`, { metodo: 'PUT', corpo: JSON.stringify({ envelope }),
      cabecalhos: { 'Content-Type': 'application/json', ...provaDoCofre(cofre) } });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return resposta.json();
  }

  async function lerConvite(convite) {
    const resposta = await pedir(`/v1/convite/${convite.id}`);
    if (resposta.status === 404) {
      return null;
    }
    if (!resposta.ok) {
      throw await falha(resposta);
    }
    return (await resposta.json()).envelope;
  }

  // ---- Lembretes e calendário: só as datas das previsões (sem nomes nem valores) ----
  async function chaveVapid() {
    const resposta = await pedir('/v1/vapid');
    const { chave } = await lerJson(resposta);
    if (!resposta.ok || !chave) {
      throw new ErroNuvem('Os lembretes ainda não estão disponíveis.');
    }
    return chave;
  }

  async function guardarLembretes(cofre, assinatura, previsoes, calendario) {
    const resposta = await pedir(`/v1/lembretes/${cofre.id}`, { metodo: 'PUT', chave: cofre.chave,
      corpo: JSON.stringify({ assinatura, previsoes, fuso: -new Date().getTimezoneOffset(), calendario }),
      cabecalhos: { 'Content-Type': 'application/json' } });
    if (!resposta.ok) {
      throw await falha(resposta);
    }
  }

  async function apagarLembretes(cofre, endpoint) {
    await pedir(`/v1/lembretes/${cofre.id}`, { metodo: 'DELETE', chave: cofre.chave,
      corpo: JSON.stringify({ endpoint }), cabecalhos: { 'Content-Type': 'application/json' } });
  }

  const tokenCalendario = () => hex(aleatorio(16));
  const enderecoCalendario = (token) => `${ENDERECO.replace(/^https:/, 'webcal:')}/v1/calendario/${token}.ics`;

  return { ENDERECO, ErroNuvem, credenciais, cofreNovo, fecharEnvelope, abrirEnvelope, codigoNovo, chavesDoConvite,
    enviar, consultar, baixar, apagar, lerMembro, guardarMembro, apagarMembro, listarMembros, guardarConvite, lerConvite,
    chaveVapid, guardarLembretes, apagarLembretes, tokenCalendario, enderecoCalendario, hex, paraB64, deB64 };
})();
