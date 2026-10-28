// Guarda no aparelho só o código do app (telas, estilos, bibliotecas e ícones), para ele abrir mais rápido e
// também sem internet. Os dados nunca passam por aqui: o backup é lido do arquivo escolhido, direto na página.
//
// Sempre tenta a versão publicada primeiro; a cópia guardada só é usada sem internet. Assim, uma atualização
// publicada chega na próxima vez que o app for aberto com internet.
'use strict';

const VERSAO = '__VERSAO__';  // Trocada pelo fluxo de publicação a cada versão publicada.
const CACHE = 'gestor-rpv-' + VERSAO;
const ARQUIVOS = [
  './', 'index.html', 'estilo.css', 'app.js', 'dados.js', 'leitor.js', 'manifest.webmanifest',
  'vendor/scrypt.js', 'vendor/fflate.js', 'vendor/sql-wasm.js', 'vendor/sql-wasm.wasm',
  'icones/apple-touch-icon.png', 'icones/icone-192.png', 'icones/icone-512.png', 'icones/icone-mascara-512.png',
];
const PERMITIDOS = new Set(ARQUIVOS.map((arquivo) => new URL(arquivo, self.registration.scope).href));

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(caches.keys()
    .then((nomes) => Promise.all(nomes.filter((n) => n.startsWith('gestor-rpv-') && n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (evento) => {
  const endereco = new URL(evento.request.url);
  endereco.search = '';
  endereco.hash = '';
  // Só os arquivos do app; qualquer outra coisa segue direto para a rede, sem ser guardada.
  if (evento.request.method !== 'GET' || !PERMITIDOS.has(endereco.href)) {
    return;
  }
  evento.respondWith(fetch(evento.request).then((resposta) => {
    if (resposta.ok) {
      const copia = resposta.clone();
      caches.open(CACHE).then((cache) => cache.put(endereco.href, copia));
    }
    return resposta;
  }).catch(() => caches.match(endereco.href).then((guardada) => guardada || Response.error())));
});
