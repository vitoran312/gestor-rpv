// Guarda no aparelho só o código do app (telas, estilos, bibliotecas e ícones), para ele abrir mais rápido e
// também sem internet. Os dados nunca passam por aqui: o backup é lido do arquivo escolhido, direto na página.
//
// Sempre tenta a versão publicada primeiro; a cópia guardada só é usada sem internet. Assim, uma atualização
// publicada chega na próxima vez que o app for aberto com internet.
'use strict';

const VERSAO = '__VERSAO__';  // Trocada pelo fluxo de publicação a cada versão publicada.
const CACHE = 'gestor-rpv-' + VERSAO;
const ARQUIVOS = [
  './', 'index.html', 'estilo.css', 'app.js', 'dados.js', 'leitor.js', 'nuvem.js', 'guarda.js', 'faceid.js', 'manifest.webmanifest',
  'novidades.json', 'modelo.sqlite3', 'demonstracao.sqlite3', 'icones/qr-app.svg',
  'vendor/scrypt.js', 'vendor/fflate.js', 'vendor/sql-wasm.js', 'vendor/sql-wasm.wasm', 'visualizador.js',
  'vendor/pdfjs/pdf.min.mjs', 'vendor/pdfjs/pdf.worker.min.mjs',
  'vendor/pdfjs/standard_fonts/FoxitDingbats.pfb', 'vendor/pdfjs/standard_fonts/FoxitFixed.pfb',
  'vendor/pdfjs/standard_fonts/FoxitFixedBold.pfb', 'vendor/pdfjs/standard_fonts/FoxitFixedBoldItalic.pfb',
  'vendor/pdfjs/standard_fonts/FoxitFixedItalic.pfb', 'vendor/pdfjs/standard_fonts/FoxitSerif.pfb',
  'vendor/pdfjs/standard_fonts/FoxitSerifBold.pfb', 'vendor/pdfjs/standard_fonts/FoxitSerifBoldItalic.pfb',
  'vendor/pdfjs/standard_fonts/FoxitSerifItalic.pfb', 'vendor/pdfjs/standard_fonts/FoxitSymbol.pfb',
  'vendor/pdfjs/standard_fonts/LiberationSans-Bold.ttf', 'vendor/pdfjs/standard_fonts/LiberationSans-BoldItalic.ttf',
  'vendor/pdfjs/standard_fonts/LiberationSans-Italic.ttf', 'vendor/pdfjs/standard_fonts/LiberationSans-Regular.ttf',
  'icones/logo.png', 'icones/apple-touch-icon.png', 'icones/icone-192.png', 'icones/icone-512.png', 'icones/icone-mascara-512.png',
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

// Lembrete das previsões de amanhã, mandado pela nuvem do Gestor (só o texto do aviso; nada dos dados).
self.addEventListener('push', (evento) => {
  let aviso = {};
  try {
    aviso = evento.data ? evento.data.json() : {};
  } catch (erro) {
    aviso = {};
  }
  evento.waitUntil(self.registration.showNotification(aviso.titulo || 'Gestor RPV', {
    body: aviso.texto || 'Há previsões de recebimento amanhã.',
    icon: 'icones/icone-192.png',
    tag: 'previsoes-de-amanha',
    data: { endereco: aviso.endereco || '#agenda' },
  }));
});

// Tocar no aviso abre o app (ou traz o que já está aberto) na agenda.
self.addEventListener('notificationclick', (evento) => {
  evento.notification.close();
  const endereco = new URL((evento.notification.data && evento.notification.data.endereco) || '#agenda', self.registration.scope).href;
  evento.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((janelas) => {
    const aberta = janelas.find((j) => j.url.startsWith(self.registration.scope));
    return aberta ? aberta.focus().then((j) => j.navigate(endereco)).catch(() => self.clients.openWindow(endereco))
      : self.clients.openWindow(endereco);
  }));
});
