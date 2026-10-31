// O Worker rodando no próprio computador, com um KV na memória: usado pelos testes do programa e do app (e
// para experimentar sem a Cloudflare). `node nuvem/local.mjs` escreve a porta na saída e atende até ser encerrado.
import http from 'node:http';
import { pathToFileURL } from 'node:url';
import worker from './worker.js';

export function kvNaMemoria() {
  const valores = new Map();
  return {
    valores,
    async get(chave, tipo) {
      if (!valores.has(chave)) {
        return null;
      }
      const valor = valores.get(chave);
      if (tipo === 'json') {
        return JSON.parse(typeof valor === 'string' ? valor : new TextDecoder().decode(valor));
      }
      if (tipo === 'arrayBuffer') {
        const bytes = typeof valor === 'string' ? new TextEncoder().encode(valor) : valor;
        return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      }
      return typeof valor === 'string' ? valor : new TextDecoder().decode(valor);
    },
    async put(chave, valor) {
      valores.set(chave, typeof valor === 'string' ? valor : new Uint8Array(valor).slice());
    },
    async delete(chave) {
      valores.delete(chave);
    },
    async list({ prefix = '' } = {}) {
      return { keys: [...valores.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })), list_complete: true };
    },
  };
}

// Nos testes, um aparelho faz muitos pedidos seguidos do mesmo endereço: sem limite de tentativas.
const semLimite = { limit: async () => ({ success: true }) };

export function servir(env = { DADOS: kvNaMemoria(), TENTATIVAS: semLimite }, porta = 0) {
  const servidor = http.createServer(async (pedido, resposta) => {
    const partes = [];
    for await (const parte of pedido) {
      partes.push(parte);
    }
    const corpo = Buffer.concat(partes);
    const requisicao = new Request(`http://${pedido.headers.host}${pedido.url}`, {
      method: pedido.method, headers: pedido.headers, body: ['GET', 'HEAD'].includes(pedido.method) ? undefined : corpo,
    });
    const devolvida = await worker.fetch(requisicao, env);
    resposta.writeHead(devolvida.status, Object.fromEntries(devolvida.headers));
    resposta.end(Buffer.from(await devolvida.arrayBuffer()));
  });
  return new Promise((ok) => servidor.listen(porta, '127.0.0.1', () => ok({ servidor, env, porta: servidor.address().port })));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { porta } = await servir();
  process.stdout.write(`${porta}\n`);
}
