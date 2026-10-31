// Gestor RPV na nuvem (Cloudflare Worker, plano gratuito).
//
// Guarda o último backup de cada "cofre" (os dados de uma pessoa, ou de uma casa que os divide) e o entrega aos
// aparelhos. O backup chega já cifrado pelo celular: aqui ele é só uma sequência de bytes, sem como ser lido.
//
// Quem é quem:
//   cofre   identificador e chave de acesso sorteados no celular ao criar os dados (ou, nos dados antigos,
//           derivados da senha). Quem tem a chave lê e grava o backup.
//   membro  uma pessoa com acesso ao cofre: identificador e chave derivados da senha DELA (scrypt, no aparelho).
//           Guarda um "envelope": a chave dos dados e as do cofre, cifradas com a senha dela. É assim que um
//           celular novo recupera os dados só com a senha.
//   convite um envelope cifrado com um código curto, válido por 15 minutos, que só vira membro uma vez.
//
// Também manda, uma vez por dia, os avisos (Web Push) das previsões de amanhã e das que passaram da data, e
// serve o calendário (ICS) das previsões — tudo a partir só das datas: nomes e valores nunca chegam aqui.
//
// Armazenamento (Workers KV, binding DADOS):
//   auth:<id>                    resumo SHA-256 da chave de acesso (de um cofre ou de um membro)
//   meta:<cofre>                 {versao, partes, tamanho, sal, resumo, criado_em, enviado_em}
//   parte:<cofre>:<versao>:<n>   pedaços de até 20 MiB do backup (o KV aceita até 25 MiB por valor)
//   membro:<id>                  {cofre, envelope, nome, desde}
//   membros:<cofre>              [{id, nome, desde}]
//   convite:<id>                 {cofre, envelope} (expira sozinho)
//   lembrete:<cofre>:<aparelho>  {assinatura, previsoes, fuso, avisado_amanha, avisado_atraso}
//   agenda:<cofre>               {previsoes, fuso}            (o calendário)
//   calendario:<token>           <cofre>

const PARTE = 20 * 1024 * 1024;
const LIMITE = 95 * 1024 * 1024;
const CONVITE_SEGUNDOS = 15 * 60;
const TENTATIVAS_POR_MINUTO = 30;
const ORIGENS = ['https://vitoran312.github.io'];
const CABECALHOS = 'Content-Type, X-Gestor-Chave, X-Gestor-Sal, X-Gestor-Criado, X-Gestor-Resumo, X-Gestor-Substituir, '
  + 'X-Gestor-Base, X-Gestor-Cofre, X-Gestor-Cofre-Chave, X-Gestor-Anterior, X-Gestor-Anterior-Chave, X-Gestor-Convite';
const ID = /^[0-9a-f]{32}$/;
const CHAVE = /^[0-9a-f]{64}$/;

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

// Limite de tentativas por endereço (nas rotas em que alguém poderia tentar senhas ou códigos às cegas). Usa o
// limitador da Cloudflare quando o Worker tem um; sem ele, uma contagem por instância, que já freia o grosso.
const contagens = new Map();
async function dentroDoLimite(pedido, env) {
  const ip = pedido.headers.get('CF-Connecting-IP') || 'local';
  if (env.TENTATIVAS && typeof env.TENTATIVAS.limit === 'function') {
    try {
      return (await env.TENTATIVAS.limit({ key: ip })).success;
    } catch (erro) {
      // Sem o limitador agora: cai na contagem local.
    }
  }
  const minuto = Math.floor(Date.now() / 60000);
  const atual = contagens.get(ip);
  const conta = atual && atual.minuto === minuto ? atual.conta + 1 : 1;
  contagens.set(ip, { minuto, conta });
  if (contagens.size > 5000) {
    contagens.clear();
  }
  return conta <= TENTATIVAS_POR_MINUTO;
}

// A chave de acesso confere com a registrada (ou é registrada agora, quando `registrar`).
async function confere(env, id, chave, registrar = false) {
  if (!ID.test(id || '') || !CHAVE.test(chave || '')) {
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

const autorizado = (pedido, env, id, registrar = false) => confere(env, id, pedido.headers.get('X-Gestor-Chave'), registrar);
const doCofre = (pedido, env) => confere(env, pedido.headers.get('X-Gestor-Cofre'), pedido.headers.get('X-Gestor-Cofre-Chave'));

async function apagarPartes(env, id, meta) {
  if (meta) {
    await Promise.all(Array.from({ length: meta.partes }, (_, n) => env.DADOS.delete(`parte:${id}:${meta.versao}:${n}`)));
  }
}

async function listarChaves(env, prefixo) {
  const chaves = [];
  let cursor;
  do {
    const pagina = await env.DADOS.list({ prefix: prefixo, cursor });
    chaves.push(...pagina.keys.map((k) => k.name));
    cursor = pagina.list_complete ? null : pagina.cursor;
  } while (cursor);
  return chaves;
}

// ---- Backup ------------------------------------------------------------------------------------------------
async function guardarBackup(pedido, env, id) {
  if (!await autorizado(pedido, env, id, true)) {
    return json(pedido, { erro: 'Chave de acesso não confere.' }, 403);
  }
  const sal = pedido.headers.get('X-Gestor-Sal') || '';
  const resumo = pedido.headers.get('X-Gestor-Resumo') || '';
  const criado = pedido.headers.get('X-Gestor-Criado') || '';
  if (!/^[0-9a-f]{32}$/.test(sal) || !CHAVE.test(resumo) || !/^[0-9T:.+\-Z]{10,40}$/.test(criado)) {
    return json(pedido, { erro: 'Envio incompleto.' }, 400);
  }
  const anterior = await env.DADOS.get(`meta:${id}`, 'json');
  // Outro aparelho com a mesma senha (outro sal de cifra) não sobrescreve sem a pessoa pedir.
  if (anterior && anterior.sal !== sal && pedido.headers.get('X-Gestor-Substituir') !== '1') {
    return json(pedido, { erro: 'Já existe na nuvem um backup de outro aparelho com esta senha.', conflito: true,
      criado_em: anterior.criado_em }, 409);
  }
  // Quem gravou partindo de uma versão que não é mais a última precisa juntar o que mudou antes (outro celular
  // da casa gravou nesse meio-tempo).
  const base = pedido.headers.get('X-Gestor-Base');
  if (base && anterior && anterior.versao !== base && pedido.headers.get('X-Gestor-Substituir') !== '1') {
    return json(pedido, { erro: 'Os dados mudaram em outro aparelho.', desatualizado: true, versao: anterior.versao }, 409);
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

async function apagarCofre(env, id) {
  const meta = await env.DADOS.get(`meta:${id}`, 'json');
  await apagarPartes(env, id, meta);
  const lembretes = await listarChaves(env, `lembrete:${id}`);
  // Nos dados antigos, o cofre e a pessoa têm o mesmo identificador: a chave dela continua valendo para o cadastro.
  const pessoa = await env.DADOS.get(`membro:${id}`);
  await Promise.all([...lembretes, `meta:${id}`, `agenda:${id}`, `membros:${id}`, ...(pessoa ? [] : [`auth:${id}`])]
    .map((k) => env.DADOS.delete(k)));
}

// ---- Membros e convites -----------------------------------------------------------------------------------
async function listaDeMembros(env, cofre) {
  return await env.DADOS.get(`membros:${cofre}`, 'json') || [];
}

async function guardarMembro(pedido, env, id) {
  if (!await dentroDoLimite(pedido, env)) {
    return json(pedido, { erro: 'Muitas tentativas. Espere um minuto.' }, 429);
  }
  const cofre = pedido.headers.get('X-Gestor-Cofre');
  if (!await doCofre(pedido, env)) {
    return json(pedido, { erro: 'Sem acesso a estes dados.' }, 403);
  }
  const corpo = await pedido.json().catch(() => null);
  const envelope = corpo && corpo.envelope;
  if (!envelope || typeof envelope.iv !== 'string' || typeof envelope.cifrado !== 'string' || envelope.cifrado.length > 4000) {
    return json(pedido, { erro: 'Envelope incompleto.' }, 400);
  }
  const nome = typeof corpo.nome === 'string' ? corpo.nome.trim().slice(0, 60) : '';
  const existente = await env.DADOS.get(`membro:${id}`, 'json');
  if (existente && existente.cofre !== cofre) {
    // Trocar de cofre só prova quem também abre o anterior (é a mesma pessoa trocando a chave dos dados). Sem
    // isso, é outra pessoa que escolheu a mesma senha: ela precisa de outra.
    const anterior = pedido.headers.get('X-Gestor-Anterior');
    if (anterior !== existente.cofre || !await confere(env, anterior, pedido.headers.get('X-Gestor-Anterior-Chave'))) {
      return json(pedido, { erro: 'Esta senha já é usada por outra pessoa. Escolha outra.', senha_em_uso: true }, 409);
    }
  }
  if (!await autorizado(pedido, env, id, true)) {
    return json(pedido, { erro: 'Esta senha já é usada por outra pessoa. Escolha outra.', senha_em_uso: true }, 409);
  }
  const convite = pedido.headers.get('X-Gestor-Convite');
  if (convite) {
    const guardado = ID.test(convite) && await env.DADOS.get(`convite:${convite}`, 'json');
    if (!guardado || guardado.cofre !== cofre) {
      return json(pedido, { erro: 'Código de convite inválido ou vencido.' }, 404);
    }
    await env.DADOS.delete(`convite:${convite}`);  // Um convite vale para uma pessoa só.
  }
  const desde = existente && existente.cofre === cofre ? existente.desde : new Date().toISOString();
  await env.DADOS.put(`membro:${id}`, JSON.stringify({ cofre, envelope, nome, desde }));
  const lista = (await listaDeMembros(env, cofre)).filter((m) => m.id !== id);
  await env.DADOS.put(`membros:${cofre}`, JSON.stringify([...lista, { id, nome, desde }]));
  if (existente && existente.cofre !== cofre) {
    const antiga = (await listaDeMembros(env, existente.cofre)).filter((m) => m.id !== id);
    await env.DADOS.put(`membros:${existente.cofre}`, JSON.stringify(antiga));
  }
  return json(pedido, { ok: true });
}

async function apagarMembro(pedido, env, id) {
  const registro = await env.DADOS.get(`membro:${id}`, 'json');
  if (!registro) {
    return json(pedido, { ok: true });
  }
  // A própria pessoa, ou alguém com acesso ao cofre dela (para tirar o acesso de outro aparelho).
  const pelaPropria = await autorizado(pedido, env, id);
  const peloCofre = pedido.headers.get('X-Gestor-Cofre') === registro.cofre && await doCofre(pedido, env);
  if (!pelaPropria && !peloCofre) {
    return json(pedido, { erro: 'Sem acesso.' }, 403);
  }
  await env.DADOS.delete(`membro:${id}`);
  if (id !== registro.cofre) {
    await env.DADOS.delete(`auth:${id}`);  // Nos dados antigos, membro e cofre têm o mesmo identificador.
  }
  const lista = (await listaDeMembros(env, registro.cofre)).filter((m) => m.id !== id);
  await env.DADOS.put(`membros:${registro.cofre}`, JSON.stringify(lista));
  return json(pedido, { ok: true });
}

async function guardarConvite(pedido, env, id) {
  if (!await doCofre(pedido, env)) {
    return json(pedido, { erro: 'Sem acesso a estes dados.' }, 403);
  }
  const corpo = await pedido.json().catch(() => null);
  const envelope = corpo && corpo.envelope;
  if (!envelope || typeof envelope.iv !== 'string' || typeof envelope.cifrado !== 'string' || envelope.cifrado.length > 4000) {
    return json(pedido, { erro: 'Convite incompleto.' }, 400);
  }
  await env.DADOS.put(`convite:${id}`, JSON.stringify({ cofre: pedido.headers.get('X-Gestor-Cofre'), envelope }),
    { expirationTtl: CONVITE_SEGUNDOS });
  return json(pedido, { ok: true, expira_em: new Date(Date.now() + CONVITE_SEGUNDOS * 1000).toISOString() });
}

// ---- Lembretes e calendário -------------------------------------------------------------------------------
const DATA = /^\d{4}-\d{2}-\d{2}$/;

async function guardarLembretes(pedido, env, id) {
  if (!await autorizado(pedido, env, id, true)) {
    return json(pedido, { erro: 'Chave de acesso não confere.' }, 403);
  }
  const corpo = await pedido.json().catch(() => null);
  const valido = corpo && corpo.assinatura && typeof corpo.assinatura.endpoint === 'string'
    && /^https:\/\//.test(corpo.assinatura.endpoint) && corpo.assinatura.keys
    && Array.isArray(corpo.previsoes) && corpo.previsoes.length <= 2000
    && corpo.previsoes.every((d) => DATA.test(d)) && Number.isInteger(corpo.fuso);
  if (!valido) {
    return json(pedido, { erro: 'Lembretes incompletos.' }, 400);
  }
  const aparelho = (await sha256(corpo.assinatura.endpoint)).slice(0, 16);
  const chave = `lembrete:${id}:${aparelho}`;
  const anterior = await env.DADOS.get(chave, 'json') || {};
  await env.DADOS.put(chave, JSON.stringify({ assinatura: corpo.assinatura, previsoes: corpo.previsoes, fuso: corpo.fuso,
    avisado_amanha: anterior.avisado_amanha || null, avisado_atraso: anterior.avisado_atraso || null }));
  await env.DADOS.put(`agenda:${id}`, JSON.stringify({ previsoes: corpo.previsoes, fuso: corpo.fuso }));
  await env.DADOS.delete(`lembrete:${id}`);  // Formato antigo (um aparelho só por cofre).
  if (ID.test(corpo.calendario || '') && await env.DADOS.get(`calendario:${corpo.calendario}`) !== id) {
    await env.DADOS.put(`calendario:${corpo.calendario}`, id);
  }
  return json(pedido, { ok: true });
}

async function apagarLembretes(pedido, env, id) {
  const corpo = await pedido.json().catch(() => ({}));
  if (corpo && typeof corpo.endpoint === 'string') {
    await env.DADOS.delete(`lembrete:${id}:${(await sha256(corpo.endpoint)).slice(0, 16)}`);
  }
  await env.DADOS.delete(`lembrete:${id}`);
  return json(pedido, { ok: true });
}

function linhaIcs(chave, valor) {
  return `${chave}:${valor}`;
}

async function calendario(pedido, env, token) {
  const id = await env.DADOS.get(`calendario:${token}`);
  const agenda = id && await env.DADOS.get(`agenda:${id}`, 'json');
  if (!agenda) {
    return new Response('Calendário não encontrado.', { status: 404 });
  }
  const contagem = new Map();
  agenda.previsoes.forEach((d) => contagem.set(d, (contagem.get(d) || 0) + 1));
  const agora = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const eventos = [...contagem].sort().flatMap(([dia, n]) => {
    const inicio = dia.replace(/-/g, '');
    const fim = new Date(Date.UTC(+dia.slice(0, 4), +dia.slice(5, 7) - 1, +dia.slice(8, 10) + 1)).toISOString().slice(0, 10).replace(/-/g, '');
    return ['BEGIN:VEVENT', linhaIcs('UID', `previsao-${inicio}@gestor-rpv`), linhaIcs('DTSTAMP', agora),
      linhaIcs('DTSTART;VALUE=DATE', inicio), linhaIcs('DTEND;VALUE=DATE', fim),
      linhaIcs('SUMMARY', n === 1 ? 'Previsão de recebimento' : `Previsão de recebimento (${n})`),
      'TRANSP:TRANSPARENT', 'END:VEVENT'];
  });
  const corpo = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Gestor RPV//Previsoes//PT', 'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH', 'X-WR-CALNAME:Gestor RPV', 'X-PUBLISHED-TTL:PT1H', 'REFRESH-INTERVAL;VALUE=DURATION:PT1H',
    ...eventos, 'END:VCALENDAR'].join('\r\n') + '\r\n';
  return new Response(corpo, { headers: { 'Content-Type': 'text/calendar; charset=utf-8', 'Cache-Control': 'no-store' } });
}

// ---- Rotas ------------------------------------------------------------------------------------------------
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
  const ics = url.pathname.match(/^\/v1\/calendario\/([0-9a-f]{32})\.ics$/);
  if (ics && pedido.method === 'GET') {
    return calendario(pedido, env, ics[1]);
  }
  const rota = url.pathname.match(/^\/v1\/(backup|lembretes|membro|convite|cofre)\/([0-9a-f]{32})(?:\/([0-9a-z]{1,24})(?:\/(\d{1,3}))?)?$/);
  if (!rota) {
    return json(pedido, { erro: 'Endereço desconhecido.' }, 404);
  }
  const [, recurso, id, versao, numero] = rota;
  const metodo = pedido.method;
  if (recurso === 'membro' && !versao) {
    if (metodo === 'PUT') {
      return guardarMembro(pedido, env, id);
    }
    if (metodo === 'DELETE') {
      return apagarMembro(pedido, env, id);
    }
    if (metodo === 'GET') {
      if (!await dentroDoLimite(pedido, env)) {
        return json(pedido, { erro: 'Muitas tentativas. Espere um minuto.' }, 429);
      }
      const registro = await autorizado(pedido, env, id) && await env.DADOS.get(`membro:${id}`, 'json');
      return registro ? json(pedido, { envelope: registro.envelope, nome: registro.nome, cofre: registro.cofre })
        : json(pedido, { erro: 'Nada encontrado.' }, 404);
    }
  }
  if (recurso === 'convite' && !versao) {
    if (metodo === 'PUT') {
      return guardarConvite(pedido, env, id);
    }
    if (metodo === 'GET') {
      if (!await dentroDoLimite(pedido, env)) {
        return json(pedido, { erro: 'Muitas tentativas. Espere um minuto.' }, 429);
      }
      const convite = await env.DADOS.get(`convite:${id}`, 'json');
      return convite ? json(pedido, { envelope: convite.envelope }) : json(pedido, { erro: 'Código inválido ou vencido.' }, 404);
    }
  }
  if (recurso === 'cofre' && versao === 'membros' && !numero && metodo === 'GET') {
    if (!await autorizado(pedido, env, id)) {
      return json(pedido, { erro: 'Nada encontrado.' }, 404);
    }
    return json(pedido, { membros: await listaDeMembros(env, id) });
  }
  if (recurso === 'backup' && metodo === 'PUT' && !versao) {
    return guardarBackup(pedido, env, id);
  }
  if (recurso === 'lembretes' && !versao) {
    if (metodo === 'PUT') {
      return guardarLembretes(pedido, env, id);
    }
    if (metodo === 'DELETE' && await autorizado(pedido, env, id)) {
      return apagarLembretes(pedido, env, id);
    }
  }
  if (recurso !== 'backup') {
    return json(pedido, { erro: 'Endereço desconhecido.' }, 404);
  }
  // Leituras e exclusão do backup: só com a chave registrada. Sem ela, "não encontrado" (sem dizer se existe).
  if (!versao && metodo === 'GET' && !await dentroDoLimite(pedido, env)) {
    return json(pedido, { erro: 'Muitas tentativas. Espere um minuto.' }, 429);
  }
  if (!await autorizado(pedido, env, id)) {
    return json(pedido, { erro: 'Nada encontrado.' }, 404);
  }
  if (metodo === 'DELETE' && !versao) {
    await apagarCofre(env, id);
    return json(pedido, { ok: true });
  }
  if (metodo !== 'GET' || (versao && numero === undefined)) {
    return json(pedido, { erro: 'Método não aceito.' }, 405);
  }
  const meta = await env.DADOS.get(`meta:${id}`, 'json');
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

// ---- Avisos (Web Push, RFC 8291 e VAPID, RFC 8292) --------------------------------------------------------
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

// Os avisos do dia para um aparelho: previsões de amanhã e as que passaram da data ontem (ainda não recebidas).
// O número no ícone (selo) é o de previsões vencidas ou de hoje.
function avisosDoDia(lembrete, agora) {
  const hoje = diaLocal(agora, lembrete.fuso);
  const amanha = diaLocal(agora, lembrete.fuso, 1);
  const ontem = diaLocal(agora, lembrete.fuso, -1);
  const selo = lembrete.previsoes.filter((d) => d <= hoje).length;
  const avisos = [];
  const deAmanha = lembrete.previsoes.filter((d) => d === amanha).length;
  if (deAmanha && lembrete.avisado_amanha !== amanha) {
    avisos.push({ tipo: 'amanha', dia: amanha, mensagem: { titulo: 'Gestor RPV', tag: 'previsoes-de-amanha', endereco: '#agenda', selo,
      texto: deAmanha === 1 ? 'Amanhã há 1 previsão de recebimento. Toque para ver na agenda.'
        : `Amanhã há ${deAmanha} previsões de recebimento. Toque para ver na agenda.` } });
  }
  const passaram = lembrete.previsoes.filter((d) => d === ontem).length;
  if (passaram && lembrete.avisado_atraso !== ontem) {
    avisos.push({ tipo: 'atraso', dia: ontem, mensagem: { titulo: 'Gestor RPV', tag: 'previsoes-atrasadas', endereco: '#atrasadas', selo,
      texto: passaram === 1 ? '1 operação passou da previsão. Toque para marcar como recebida.'
        : `${passaram} operações passaram da previsão. Toque para marcar como recebidas.` } });
  }
  return avisos;
}

async function enviarLembretes(env, agora = Date.now(), enviar = fetch) {
  const resultado = { avisados: 0, removidos: 0 };
  for (const nome of await listarChaves(env, 'lembrete:')) {
    const lembrete = await env.DADOS.get(nome, 'json');
    if (!lembrete) {
      continue;
    }
    if (lembrete.avisado && !lembrete.avisado_amanha) {
      lembrete.avisado_amanha = lembrete.avisado;  // Formato antigo.
    }
    let mudou = false;
    for (const aviso of avisosDoDia(lembrete, agora)) {
      const resposta = await enviar(lembrete.assinatura.endpoint, {
        method: 'POST',
        headers: { Authorization: await vapid(lembrete.assinatura.endpoint, env, agora), 'Content-Encoding': 'aes128gcm',
          'Content-Type': 'application/octet-stream', TTL: '43200', Urgency: 'normal' },
        body: await cifrarNotificacao(lembrete.assinatura, JSON.stringify(aviso.mensagem)),
      });
      if (resposta.status === 404 || resposta.status === 410) {
        await env.DADOS.delete(nome);  // A pessoa desinstalou o app ou desligou as notificações.
        resultado.removidos += 1;
        mudou = false;
        break;
      }
      if (resposta.ok) {
        lembrete[aviso.tipo === 'amanha' ? 'avisado_amanha' : 'avisado_atraso'] = aviso.dia;
        resultado.avisados += 1;
        mudou = true;
      }
    }
    if (mudou) {
      await env.DADOS.put(nome, JSON.stringify(lembrete));
    }
  }
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

export { atender, enviarLembretes, cifrarNotificacao, vapid, diaLocal, avisosDoDia };
