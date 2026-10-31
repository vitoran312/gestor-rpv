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
r.assinatura_vencida = { ...removido, restou: [...env.DADOS.valores.keys()].some((k) => k.startsWith(`lembrete:${ID}`)) };

// Dois aparelhos com lembretes no mesmo cofre: cada um tem a sua assinatura; o calendário mostra as datas.
const assinaturaB = { endpoint: 'https://push.exemplo/def', keys: assinatura.keys };
const calendarioToken = 'c'.repeat(32);
for (const a of [assinatura, assinaturaB]) {
  await pedir('PUT', `/v1/lembretes/${ID}`, { corpo: JSON.stringify({ assinatura: a, fuso: -180, calendario: calendarioToken,
    previsoes: [amanha, '2026-10-29', '2026-10-29'] }) });
}
r.lembretes_aparelhos = [...env.DADOS.valores.keys()].filter((k) => k.startsWith(`lembrete:${ID}:`)).length;
const destinos = [];
const rodada = await enviarLembretes(env, agora, async (endereco, opcoes) => {
  destinos.push(endereco);
  return new Response(null, { status: 201 });
});
r.dois_aparelhos = { ...rodada, destinos: [...new Set(destinos)].length };
// O aviso de atraso (previsão de ontem, 29/10) sai junto com o de amanhã, com o número para o ícone.
const { avisosDoDia } = await import('./worker.js');
r.avisos_do_dia = avisosDoDia({ previsoes: [amanha, '2026-10-29', '2026-10-29', '2026-10-01'], fuso: -180 }, agora)
  .map((a) => ({ tipo: a.tipo, texto: a.mensagem.texto, endereco: a.mensagem.endereco, selo: a.mensagem.selo }));
const ics = await worker.fetch(new Request(`https://teste/v1/calendario/${calendarioToken}.ics`), env);
r.calendario = { status: ics.status, tipo: ics.headers.get('Content-Type'), texto: await ics.text() };
r.calendario_desconhecido = (await worker.fetch(new Request(`https://teste/v1/calendario/${'d'.repeat(32)}.ics`), env)).status;
r.apagar_lembrete = (await pedir('DELETE', `/v1/lembretes/${ID}`, { corpo: JSON.stringify({ endpoint: assinaturaB.endpoint }) })).status;
r.lembretes_depois = [...env.DADOS.valores.keys()].filter((k) => k.startsWith(`lembrete:${ID}:`)).length;

// Versão base: quem grava partindo de uma versão velha recebe 409 (outro aparelho gravou antes).
const atual = (await pedir('GET', `/v1/backup/${ID}`)).corpo;
const comBase = (base) => enviar(new Uint8Array([4, 4]), '2'.repeat(32), { 'X-Gestor-Base': base });
const velha = await comBase('versao-antiga');
r.base_velha = { status: velha.status, desatualizado: velha.corpo.desatualizado, versao: velha.corpo.versao === atual.versao };
r.base_certa = (await comBase(atual.versao)).status;

// Membros e convite (outro cofre): a dona cria os dados, convida, a convidada entra com a própria senha.
const COFRE = 'e'.repeat(32);
const COFRE_CHAVE = 'f'.repeat(64);
const DONA = '1'.repeat(32);
const DONA_CHAVE = '3'.repeat(64);
const CONVIDADA = '4'.repeat(32);
const CONVIDADA_CHAVE = '5'.repeat(64);
const envelope = { iv: 'aaaa', cifrado: 'bbbb' };
const doCofre = { 'X-Gestor-Cofre': COFRE, 'X-Gestor-Cofre-Chave': COFRE_CHAVE };
await pedir('PUT', `/v1/backup/${COFRE}`, { chave: COFRE_CHAVE, corpo: new Uint8Array([1]), cabecalhos: {
  'X-Gestor-Sal': '6'.repeat(32), 'X-Gestor-Resumo': 'c'.repeat(64), 'X-Gestor-Criado': '2026-10-30T10:00:00Z' } });
r.membro_sem_cofre = (await pedir('PUT', `/v1/membro/${DONA}`, { chave: DONA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'Vitor' }),
  cabecalhos: { 'X-Gestor-Cofre': COFRE, 'X-Gestor-Cofre-Chave': '9'.repeat(64) } })).status;
r.membro_dona = (await pedir('PUT', `/v1/membro/${DONA}`, { chave: DONA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'Vitor' }),
  cabecalhos: doCofre })).status;
const lido = await pedir('GET', `/v1/membro/${DONA}`, { chave: DONA_CHAVE });
r.membro_lido = { status: lido.status, nome: lido.corpo.nome, cofre: lido.corpo.cofre === COFRE, envelope: lido.corpo.envelope.cifrado };
r.membro_chave_errada = (await pedir('GET', `/v1/membro/${DONA}`, { chave: '9'.repeat(64) })).status;
const CODIGO = '7'.repeat(32);
r.convite_sem_cofre = (await pedir('PUT', `/v1/convite/${CODIGO}`, { corpo: JSON.stringify({ envelope }) })).status;
r.convite = (await pedir('PUT', `/v1/convite/${CODIGO}`, { corpo: JSON.stringify({ envelope }), cabecalhos: doCofre })).status;
r.convite_lido = (await pedir('GET', `/v1/convite/${CODIGO}`, { chave: '' })).corpo.envelope.cifrado;
r.convite_errado = (await pedir('GET', `/v1/convite/${'8'.repeat(32)}`, { chave: '' })).status;
r.entrou = (await pedir('PUT', `/v1/membro/${CONVIDADA}`, { chave: CONVIDADA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'Ana' }),
  cabecalhos: { ...doCofre, 'X-Gestor-Convite': CODIGO } })).status;
r.convite_usado = (await pedir('GET', `/v1/convite/${CODIGO}`, { chave: '' })).status;  // Vale para uma pessoa só.
r.membros = (await pedir('GET', `/v1/cofre/${COFRE}/membros`, { chave: COFRE_CHAVE })).corpo.membros.map((m) => m.nome);
r.membros_sem_chave = (await pedir('GET', `/v1/cofre/${COFRE}/membros`, { chave: 'a'.repeat(64) })).status;
// Outra pessoa (outro cofre) com a mesma senha da dona: não toma o lugar dela.
r.mesma_senha_outro_cofre = (await pedir('PUT', `/v1/membro/${DONA}`, { chave: DONA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'X' }),
  cabecalhos: { 'X-Gestor-Cofre': ID, 'X-Gestor-Cofre-Chave': CHAVE } })).status;
// A dona tira o acesso da convidada (pelo cofre) e troca a chave: passa para um cofre novo, provando o antigo.
r.remover = (await pedir('DELETE', `/v1/membro/${CONVIDADA}`, { chave: '', cabecalhos: doCofre })).status;
r.removida = (await pedir('GET', `/v1/membro/${CONVIDADA}`, { chave: CONVIDADA_CHAVE })).status;
const NOVO = '2'.repeat(32);
const NOVO_CHAVE = '6'.repeat(64);
await pedir('PUT', `/v1/backup/${NOVO}`, { chave: NOVO_CHAVE, corpo: new Uint8Array([2]), cabecalhos: {
  'X-Gestor-Sal': '6'.repeat(32), 'X-Gestor-Resumo': 'c'.repeat(64), 'X-Gestor-Criado': '2026-10-30T10:00:00Z' } });
r.trocar_sem_provar = (await pedir('PUT', `/v1/membro/${DONA}`, { chave: DONA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'Vitor' }),
  cabecalhos: { 'X-Gestor-Cofre': NOVO, 'X-Gestor-Cofre-Chave': NOVO_CHAVE } })).status;
r.trocar = (await pedir('PUT', `/v1/membro/${DONA}`, { chave: DONA_CHAVE, corpo: JSON.stringify({ envelope, nome: 'Vitor' }),
  cabecalhos: { 'X-Gestor-Cofre': NOVO, 'X-Gestor-Cofre-Chave': NOVO_CHAVE, 'X-Gestor-Anterior': COFRE,
    'X-Gestor-Anterior-Chave': COFRE_CHAVE } })).status;
r.dona_no_novo = (await pedir('GET', `/v1/membro/${DONA}`, { chave: DONA_CHAVE })).corpo.cofre === NOVO;
r.apagar_antigo = (await pedir('DELETE', `/v1/backup/${COFRE}`, { chave: COFRE_CHAVE })).status;
r.antigo_sobrou = [...env.DADOS.valores.keys()].filter((k) => k.includes(COFRE));

// Limite de tentativas: depois de 30 por minuto do mesmo endereço, 429.
const tentativas = [];
for (let i = 0; i < 35; i += 1) {
  tentativas.push((await worker.fetch(new Request(`https://teste/v1/convite/${'9'.repeat(32)}`,
    { headers: { 'CF-Connecting-IP': '203.0.113.9' } }), env)).status);
}
r.limite = { primeiras: tentativas.slice(0, 5), ultimas: tentativas.slice(-3) };

r.apagar = (await pedir('DELETE', `/v1/backup/${ID}`)).status;
r.depois_de_apagar = (await pedir('GET', `/v1/backup/${ID}`)).status;
r.sobrou = [...env.DADOS.valores.keys()].filter((k) => !k.includes(NOVO) && !k.includes(DONA) && !k.startsWith('calendario:'));
process.stdout.write(JSON.stringify(r));
