// Cenários do Worker para test_nuvem.py: envio, leitura em partes, chave errada, conflito, exclusão e o
// lembrete cifrado (que o teste em Python decifra por conta própria, conferindo a RFC 8291).
import worker, { enviarLembretes, diaLocal } from './worker.js';
import { kvNaMemoria } from './local.mjs';

const env = { DADOS: kvNaMemoria() };
const ID = 'a'.repeat(32);
const CHAVE = 'b'.repeat(64);
const r = {};

const pedir = async (metodo, caminho, { chave = CHAVE, corpo, cabecalhos = {} } = {}) => {
  const resposta = await worker.fetch(new Request(`https://teste${caminho}`, {
    method: metodo, body: corpo, headers: { 'X-Gestor-Chave': chave, ...cabecalhos },
  }), env);
  const tipo = resposta.headers.get('Content-Type') || '';
  return { status: resposta.status, corpo: tipo.includes('json') ? await resposta.json() : new Uint8Array(await resposta.arrayBuffer()) };
};
const enviar = (bytes, sal, extra = {}) => pedir('PUT', `/v1/backup/${ID}`, { corpo: bytes, cabecalhos: {
  'X-Gestor-Sal': sal, 'X-Gestor-Resumo': 'c'.repeat(64), 'X-Gestor-Criado': '2026-10-30T10:00:00-03:00', ...extra } });

// Um backup maior que uma parte (20 MiB) volta inteiro, em duas partes.
const grande = new Uint8Array(21 * 1024 * 1024).map((_, i) => i % 251);
const primeiro = await enviar(grande, '1'.repeat(32));
r.envio = { status: primeiro.status, partes: primeiro.corpo.partes, tamanho: primeiro.corpo.tamanho };
const meta = (await pedir('GET', `/v1/backup/${ID}`)).corpo;
const pedacos = [];
for (let n = 0; n < meta.partes; n += 1) {
  pedacos.push((await pedir('GET', `/v1/backup/${ID}/${meta.versao}/${n}`)).corpo);
}
const junto = new Uint8Array(pedacos.reduce((t, p) => t + p.length, 0));
let pos = 0;
pedacos.forEach((p) => { junto.set(p, pos); pos += p.length; });
r.igual = junto.length === grande.length && junto.every((b, i) => b === grande[i]);
r.chave_errada = (await pedir('GET', `/v1/backup/${ID}`, { chave: 'd'.repeat(64) })).status;
r.envio_chave_errada = (await pedir('PUT', `/v1/backup/${ID}`, { chave: 'd'.repeat(64), corpo: new Uint8Array([1]),
  cabecalhos: { 'X-Gestor-Sal': '1'.repeat(32), 'X-Gestor-Resumo': 'c'.repeat(64), 'X-Gestor-Criado': '2026-10-30T10:00:00Z' } })).status;
r.sem_chave = (await pedir('GET', `/v1/backup/${ID}`, { chave: '' })).status;
// Outro aparelho (outro sal) com a mesma senha: recusado, a menos que a pessoa peça para substituir.
r.conflito = (await enviar(new Uint8Array([9, 9]), '2'.repeat(32))).status;
const substituido = await enviar(new Uint8Array([7, 7, 7]), '2'.repeat(32), { 'X-Gestor-Substituir': '1' });
r.substituido = substituido.status;
r.partes_antigas = [...env.DADOS.valores.keys()].filter((k) => k.startsWith(`parte:${ID}:${meta.versao}`)).length;
r.mesmo_aparelho = (await enviar(new Uint8Array([5]), '2'.repeat(32))).status;
r.endereco_ruim = (await pedir('GET', '/v1/backup/xyz')).status;

// Lembretes: a assinatura de um "navegador" de teste; o Worker cifra e o teste em Python decifra.
const aparelho = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
const publica = new Uint8Array(await crypto.subtle.exportKey('raw', aparelho.publicKey));
const segredo = crypto.getRandomValues(new Uint8Array(16));
const b64 = (b) => Buffer.from(b).toString('base64url');
const vapid = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
env.VAPID_PRIVADA = JSON.stringify(await crypto.subtle.exportKey('jwk', vapid.privateKey));
env.VAPID_PUBLICA = b64(new Uint8Array(await crypto.subtle.exportKey('raw', vapid.publicKey)));
const agora = Date.UTC(2026, 9, 30, 11, 0);  // 30/10, 8h em Brasília.
const amanha = diaLocal(agora, -180, 1);
const assinatura = { endpoint: 'https://push.exemplo/abc', keys: { p256dh: b64(publica), auth: b64(segredo) } };
r.lembrete = (await pedir('PUT', `/v1/lembretes/${ID}`, { corpo: JSON.stringify({ assinatura, fuso: -180,
  previsoes: [amanha, amanha, '2026-12-25'] }), cabecalhos: { 'Content-Type': 'application/json' } })).status;
r.lembrete_ruim = (await pedir('PUT', `/v1/lembretes/${ID}`, { corpo: JSON.stringify({ assinatura, fuso: -180,
  previsoes: ['ontem'] }) })).status;
const enviados = [];
const falsoFetch = async (endereco, opcoes) => {
  enviados.push({ endereco, cabecalhos: opcoes.headers, corpo: b64(opcoes.body) });
  return new Response(null, { status: 201 });
};
r.primeira_rodada = await enviarLembretes(env, agora, falsoFetch);
r.segunda_rodada = await enviarLembretes(env, agora, falsoFetch);  // O mesmo dia não é avisado duas vezes.
r.amanha = amanha;
r.notificacao = { ...enviados[0], privada_aparelho: await crypto.subtle.exportKey('jwk', aparelho.privateKey),
  segredo: b64(segredo), vapid_publica: env.VAPID_PUBLICA };
const semPrevisao = await enviarLembretes(env, Date.UTC(2026, 9, 20, 11, 0), falsoFetch);
r.sem_previsao = semPrevisao;
const removido = await enviarLembretes(env, Date.UTC(2026, 11, 24, 11, 0), async () => new Response(null, { status: 410 }));
r.assinatura_vencida = { ...removido, restou: env.DADOS.valores.has(`lembrete:${ID}`) };

r.apagar = (await pedir('DELETE', `/v1/backup/${ID}`)).status;
r.depois_de_apagar = (await pedir('GET', `/v1/backup/${ID}`)).status;
r.sobrou = [...env.DADOS.valores.keys()];
process.stdout.write(JSON.stringify(r));
