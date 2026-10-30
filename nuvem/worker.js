// Gestor RPV na nuvem (Cloudflare Worker, plano gratuito).
//
// Guarda o último backup de cada pessoa e o entrega ao programa no computador. O backup chega já cifrado pelo
// celular com a senha da pessoa (o mesmo arquivo .rpvbackup): aqui ele é só uma sequência de bytes, sem como
// ser lido. Cada pessoa é um identificador derivado da senha (nuvem.py e nuvem.js fazem a mesma conta) e uma
// chave de acesso, também derivada da senha, cujo resumo fica guardado no primeiro envio.
//
// Também manda, uma vez por dia, o lembrete das previsões de amanhã (Web Push), a partir só das datas: nomes e
// valores nunca chegam aqui.
//
// Armazenamento (Workers KV, binding DADOS):
//   auth:<id>                 resumo SHA-256 da chave de acesso
//   meta:<id>                 {versao, partes, tamanho, sal, resumo, criado_em, enviado_em}
//   parte:<id>:<versao>:<n>   pedaços de até 20 MiB do backup (o KV aceita até 25 MiB por valor)
//   lembrete:<id>             {assinatura, previsoes, fuso, avisado}

const PARTE = 20 * 1024 * 1024;
const LIMITE = 95 * 1024 * 1024;
const ORIGENS = ['https://vitoran312.github.io'];
const CABECALHOS = 'Content-Type, X-Gestor-Chave, X-Gestor-Sal, X-Gestor-Criado, X-Gestor-Resumo, X-Gestor-Substituir';

const texto = new TextEncoder();

function cors(pedido) {
  const origem = pedido.headers.get('Origin');
  return origem && (ORIGENS.includes(origem) || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origem)) ? {
    'Access-Control-Allow-Origin': origem,
    'Access-Control-Allow-Methods': 'GET, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': CABECALHOS,
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  } : {};
}

function json(pedido, corpo, status = 200) {
  return new Response(JSON.stringify(corpo), {
    status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...cors(pedido) },
  });
}

function hex(bytes) {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
}

async function sha256(dados) {
  return hex(await crypto.subtle.digest('SHA-256', typeof dados === 'string' ? texto.encode(dados) : dados));
}

// A chave de acesso confere com a registrada no primeiro envio (ou é registrada agora, quando `registrar`).
async function autorizado(pedido, env, id, registrar = false) {
  const chave = pedido.headers.get('X-Gestor-Chave') || '';
  if (!/^[0-9a-f]{64}$/.test(chave)) {
    return false;
  }
  const resumo = await sha256(chave);
  const guardado = await env.DADOS.get(`auth:${id}`);
  if (guardado) {
    return guardado === resumo;
  }
  if (registrar) {
    await env.DADOS.put(`auth:${id}`, resumo);
    return true;
  }
  return false;
}

async function apagarPartes(env, id, meta) {
  if (meta) {
    await Promise.all(Array.from({ length: meta.partes }, (_, n) => env.DADOS.delete(`parte:${id}:${meta.versao}:${n}`)));
  }
}

async function guardarBackup(pedido, env, id) {
  if (!await autorizado(pedido, env, id, true)) {
    return json(pedido, { erro: 'Chave de acesso não confere.' }, 403);
  }
  const sal = pedido.headers.get('X-Gestor-Sal') || '';
  const resumo = pedido.headers.get('X-Gestor-Resumo') || '';
  const criado = pedido.headers.get('X-Gestor-Criado') || '';
  if (!/^[0-9a-f]{32}$/.test(sal) || !/^[0-9a-f]{64}$/.test(resumo) || !/^[0-9T:.+\-Z]{10,40}$/.test(criado)) {
    return json(pedido, { erro: 'Envio incompleto.' }, 400);
  }
  const anterior = await env.DADOS.get(`meta:${id}`, 'json');
  // Outro aparelho com a mesma senha (outro sal de cifra) não sobrescreve sem a pessoa pedir.
  if (anterior && anterior.sal !== sal && pedido.headers.get('X-Gestor-Substituir') !== '1') {
    return json(pedido, { erro: 'Já existe na nuvem um backup de outro aparelho com esta senha.', conflito: true,
      criado_em: anterior.criado_em }, 409);
  }
  const bytes = new Uint8Array(await pedido.arrayBuffer());
  if (!bytes.length || bytes.length > LIMITE) {
    return json(pedido, { erro: 'Tamanho do backup fora do limite.' }, 413);
  }
  const versao = Date.now().toString(36) + crypto.getRandomValues(new Uint8Array(3)).reduce((t, b) => t + b.toString(16), '');
  const partes = Math.ceil(bytes.length / PARTE);
  for (let n = 0; n < partes; n += 1) {
    await env.DADOS.put(`parte:${id}:${versao}:${n}`, bytes.subarray(n * PARTE, (n + 1) * PARTE));
  }
  const meta = { versao, partes, tamanho: bytes.length, sal, resumo, criado_em: criado, enviado_em: new Date().toISOString() };
  await env.DADOS.put(`meta:${id}`, JSON.stringify(meta));
  await apagarPartes(env, id, anterior);
  return json(pedido, meta);
}

async function atender(pedido, env) {
  const url = new URL(pedido.url);
  if (pedido.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: cors(pedido) });
  }
  if (url.pathname === '/') {
    return json(pedido, { servico: 'gestor-rpv', ok: true });
  }
  if (url.pathname === '/v1/vapid' && pedido.method === 'GET') {
    return json(pedido, { chave: env.VAPID_PUBLICA || null });
  }
  const rota = url.pathname.match(/^\/v1\/(backup|lembretes)\/([0-9a-f]{32})(?:\/([0-9a-z]{1,24})\/(\d{1,3}))?$/);
  if (!rota) {
    return json(pedido, { erro: 'Endereço desconhecido.' }, 404);
  }
  const [, recurso, id, versao, numero] = rota;
  if (recurso === 'backup' && pedido.method === 'PUT' && !versao) {
    return guardarBackup(pedido, env, id);
  }
  if (recurso === 'lembretes' && pedido.method === 'PUT' && !versao) {
    if (!await autorizado(pedido, env, id, true)) {
      return json(pedido, { erro: 'Chave de acesso não confere.' }, 403);
    }
    const corpo = await pedido.json().catch(() => null);
    const valido = corpo && corpo.assinatura && typeof corpo.assinatura.endpoint === 'string'
      && /^https:\/\//.test(corpo.assinatura.endpoint) && corpo.assinatura.keys
      && Array.isArray(corpo.previsoes) && corpo.previsoes.length <= 2000
      && corpo.previsoes.every((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)) && Number.isInteger(corpo.fuso);
    if (!valido) {
      return json(pedido, { erro: 'Lembretes incompletos.' }, 400);
    }
    const anterior = await env.DADOS.get(`lembrete:${id}`, 'json');
    await env.DADOS.put(`lembrete:${id}`, JSON.stringify({ assinatura: corpo.assinatura, previsoes: corpo.previsoes,
      fuso: corpo.fuso, avisado: anterior && anterior.assinatura.endpoint === corpo.assinatura.endpoint ? anterior.avisado : null }));
    return json(pedido, { ok: true });
  }
  // Leituras e exclusões: só com a chave registrada. Sem ela, "não encontrado" (sem dizer se o identificador existe).
  if (!await autorizado(pedido, env, id)) {
    return json(pedido, { erro: 'Nada encontrado.' }, 404);
  }
  if (recurso === 'lembretes' && pedido.method === 'DELETE' && !versao) {
    await env.DADOS.delete(`lembrete:${id}`);
    return json(pedido, { ok: true });
  }
  if (recurso !== 'backup') {
    return json(pedido, { erro: 'Endereço desconhecido.' }, 404);
  }
  const meta = await env.DADOS.get(`meta:${id}`, 'json');
  if (pedido.method === 'DELETE' && !versao) {
    await apagarPartes(env, id, meta);
    await Promise.all([env.DADOS.delete(`meta:${id}`), env.DADOS.delete(`lembrete:${id}`), env.DADOS.delete(`auth:${id}`)]);
    return json(pedido, { ok: true });
  }
  if (pedido.method !== 'GET') {
    return json(pedido, { erro: 'Método não aceito.' }, 405);
  }
  if (!meta) {
    return json(pedido, { erro: 'Nada encontrado.' }, 404);
  }
  if (!versao) {
    return json(pedido, meta);
  }
  const parte = await env.DADOS.get(`parte:${id}:${versao}:${numero}`, 'arrayBuffer');
  if (!parte) {
    return json(pedido, { erro: 'Parte não encontrada (o backup acabou de mudar?).' }, 404);
  }
  return new Response(parte, { headers: { 'Content-Type': 'application/octet-stream', 'Cache-Control': 'no-store', ...cors(pedido) } });
}

// ---- Lembretes (Web Push, RFC 8291 e VAPID, RFC 8292) ---------------------------------------------------------
function b64url(bytes) {
  let binario = '';
  new Uint8Array(bytes).forEach((b) => { binario += String.fromCharCode(b); });
  return btoa(binario).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function deB64url(textoB64) {
  const base = textoB64.replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(base + '='.repeat((4 - (base.length % 4)) % 4)), (c) => c.charCodeAt(0));
}

function juntar(...partes) {
  const total = new Uint8Array(partes.reduce((t, p) => t + p.length, 0));
  let posicao = 0;
  for (const p of partes) {
    total.set(p, posicao);
    posicao += p.length;
  }
  return total;
}

async function hmac(chave, dados) {
  const k = await crypto.subtle.importKey('raw', chave, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', k, dados));
}

// Corpo cifrado de uma notificação (aes128gcm), para a assinatura do navegador da pessoa.
async function cifrarNotificacao(assinatura, mensagem, sal = crypto.getRandomValues(new Uint8Array(16)), local = null) {
  const publicaDoAparelho = deB64url(assinatura.keys.p256dh);
  const segredo = deB64url(assinatura.keys.auth);
  const par = local || await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const publicaLocal = new Uint8Array(await crypto.subtle.exportKey('raw', par.publicKey));
  const chaveDoAparelho = await crypto.subtle.importKey('raw', publicaDoAparelho, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const compartilhado = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: chaveDoAparelho }, par.privateKey, 256));
  const prkChave = await hmac(segredo, compartilhado);
  const ikm = await hmac(prkChave, juntar(texto.encode('WebPush: info\0'), publicaDoAparelho, publicaLocal, Uint8Array.of(1)));
  const prk = await hmac(sal, ikm);
  const cek = (await hmac(prk, juntar(texto.encode('Content-Encoding: aes128gcm\0'), Uint8Array.of(1)))).slice(0, 16);
  const nonce = (await hmac(prk, juntar(texto.encode('Content-Encoding: nonce\0'), Uint8Array.of(1)))).slice(0, 12);
  const aes = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const cifrado = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce }, aes,
    juntar(texto.encode(mensagem), Uint8Array.of(2))));
  const tamanhoRegistro = Uint8Array.of(0, 0, 16, 0);  // 4096
  return juntar(sal, tamanhoRegistro, Uint8Array.of(publicaLocal.length), publicaLocal, cifrado);
}

// Cabeçalho Authorization do VAPID: JWT ES256 assinado com a chave privada guardada como segredo do Worker.
async function vapid(endpoint, env, agora = Date.now()) {
  const privada = await crypto.subtle.importKey('jwk', JSON.parse(env.VAPID_PRIVADA), { name: 'ECDSA', namedCurve: 'P-256' },
    false, ['sign']);
  const cabecalho = b64url(texto.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const corpo = b64url(texto.encode(JSON.stringify({ aud: new URL(endpoint).origin, exp: Math.floor(agora / 1000) + 12 * 3600,
    sub: 'mailto:avisos@gestor-rpv.app' })));
  const assinatura = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, privada, texto.encode(`${cabecalho}.${corpo}`));
  return `vapid t=${cabecalho}.${corpo}.${b64url(assinatura)}, k=${env.VAPID_PUBLICA}`;
}

function diaLocal(agora, fuso, somar = 0) {
  return new Date(agora + fuso * 60000 + somar * 86400000).toISOString().slice(0, 10);
}

function mensagemDoDia(quantas) {
  return JSON.stringify({
    titulo: 'Gestor RPV',
    texto: quantas === 1 ? 'Amanhã há 1 previsão de recebimento. Toque para ver na agenda.'
      : `Amanhã há ${quantas} previsões de recebimento. Toque para ver na agenda.`,
    endereco: '#agenda',
  });
}

async function enviarLembretes(env, agora = Date.now(), enviar = fetch) {
  let cursor;
  const resultado = { avisados: 0, removidos: 0 };
  do {
    const pagina = await env.DADOS.list({ prefix: 'lembrete:', cursor });
    for (const { name } of pagina.keys) {
      const lembrete = await env.DADOS.get(name, 'json');
      if (!lembrete) {
        continue;
      }
      const amanha = diaLocal(agora, lembrete.fuso, 1);
      const quantas = lembrete.previsoes.filter((d) => d === amanha).length;
      if (!quantas || lembrete.avisado === amanha) {
        continue;
      }
      const resposta = await enviar(lembrete.assinatura.endpoint, {
        method: 'POST',
        headers: { Authorization: await vapid(lembrete.assinatura.endpoint, env, agora), 'Content-Encoding': 'aes128gcm',
          'Content-Type': 'application/octet-stream', TTL: '43200', Urgency: 'normal' },
        body: await cifrarNotificacao(lembrete.assinatura, mensagemDoDia(quantas)),
      });
      if (resposta.status === 404 || resposta.status === 410) {
        await env.DADOS.delete(name);  // A pessoa desinstalou o app ou desligou as notificações.
        resultado.removidos += 1;
      } else if (resposta.ok) {
        await env.DADOS.put(name, JSON.stringify({ ...lembrete, avisado: amanha }));
        resultado.avisados += 1;
      }
    }
    cursor = pagina.list_complete ? null : pagina.cursor;
  } while (cursor);
  return resultado;
}

export default {
  async fetch(pedido, env) {
    try {
      return await atender(pedido, env);
    } catch (erro) {
      return json(pedido, { erro: 'Falha no servidor.' }, 500);
    }
  },
  async scheduled(_evento, env, contexto) {
    contexto.waitUntil(enviarLembretes(env));
  },
};

export { atender, enviarLembretes, cifrarNotificacao, vapid, diaLocal };
