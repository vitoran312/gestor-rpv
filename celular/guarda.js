// Guarda no aparelho o último backup aberto (exatamente o arquivo, ainda cifrado com a senha) e a chave
// trancada pelo Face ID. Nada aqui fica legível sem a senha ou o Face ID.
'use strict';

const Guarda = (() => {
  const BANCO = 'gestor-rpv';
  const LOJA = 'guardado';
  let aberto = null;

  function abrir() {
    aberto = aberto || new Promise((ok, falha) => {
      const pedido = indexedDB.open(BANCO, 1);
      pedido.onupgradeneeded = () => pedido.result.createObjectStore(LOJA);
      pedido.onsuccess = () => ok(pedido.result);
      pedido.onerror = () => falha(pedido.error);
    });
    return aberto;
  }

  async function operar(modo, acao) {
    const db = await abrir();
    return new Promise((ok, falha) => {
      const transacao = db.transaction(LOJA, modo);
      const pedido = acao(transacao.objectStore(LOJA));
      transacao.oncomplete = () => ok(pedido.result);
      transacao.onerror = () => falha(transacao.error);
      transacao.onabort = () => falha(transacao.error);
    });
  }

  return {
    ler: (chave) => operar('readonly', (loja) => loja.get(chave)),
    gravar: (chave, valor) => operar('readwrite', (loja) => loja.put(valor, chave)),
    apagar: (chave) => operar('readwrite', (loja) => loja.delete(chave)),
    // Pede ao navegador para não apagar estes dados quando faltar espaço; se ele recusar, o pior caso é ter de
    // escolher o backup de novo.
    persistir: () => (navigator.storage && navigator.storage.persist ? navigator.storage.persist() : Promise.resolve(false))
      .catch(() => false),
  };
})();
