// Abre o app num navegador (Chromium ou WebKit; o Safari de verdade é conferido no aparelho) e imprime, em JSON, o que
// ele encontrou em cada backup de teste, as contas feitas por dados.js e os erros das telas, para
// test_celular.py comparar com o que o Python gravou e calcula.
'use strict';
const playwright = require('playwright');

// Chromium por padrão; no CI também WebKit, o motor do Safari do iPhone.
const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { casos, regras, telas } = JSON.parse(entradaJson);
  const navegador = await playwright[NAVEGADOR].launch();
  try {
    const pagina = await navegador.newPage();
    const erros = [];
    pagina.on('pageerror', (erro) => erros.push(String(erro)));
    pagina.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    await pagina.goto(endereco + '/index.html');
    const resultados = { leituras: {} };
    for (const caso of casos) {
      resultados.leituras[caso.nome] = await pagina.evaluate(async ({ arquivo, senha }) => {
        const bytes = new Uint8Array(await (await fetch(arquivo)).arrayBuffer());
        try {
          const { db, manifesto, cifrado } = await LeitorBackup.ler(bytes, senha);
          const um = (sql) => db.exec(sql)[0].values[0][0];
          const nomes = db.exec('SELECT nome FROM rpvs WHERE lixeira_em IS NULL ORDER BY id')[0];
          const resultado = {
            cifrado, versao_app: manifesto.versao_app,
            operacoes: um('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NULL'),
            lixeira: um('SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NOT NULL'),
            contas: um('SELECT COUNT(*) FROM contas'),
            documentos: um('SELECT COUNT(*) FROM documentos'),
            nomes: nomes ? nomes.values.map((linha) => linha[0]) : [],
          };
          db.close();
          return resultado;
        } catch (erro) {
          return { erro: erro.constructor.name, mensagem: erro.message };
        }
      }, caso);
    }

    // Regras de dados.js sobre o backup principal, com a mesma data de "hoje" usada no Python.
    resultados.regras = await pagina.evaluate(async ({ arquivo, senha, hoje, termos, valores, textos, textos_cpf, casos_conta, mensagens }) => {
      const D = GestorDados;
      const bytes = new Uint8Array(await (await fetch(arquivo)).arrayBuffer());
      const { db, extrair } = await LeitorBackup.ler(bytes, senha);
      const dados = D.carregar(db);
      db.close();
      const hex = async (b) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', b)),
        (x) => x.toString(16).padStart(2, '0')).join('');
      const anexos = {};
      for (const lista of dados.documentos.values()) {
        for (const d of lista) {
          anexos[d.nome] = await hex(await extrair(d.caminho));
        }
      }
      const recusas = [];
      for (const caminho of ['1/naoexiste.pdf', '../banco.sqlite3', '']) {
        try {
          await extrair(caminho);
          recusas.push('aceito');
        } catch (erro) {
          recusas.push(erro.constructor.name);
        }
      }
      const [ano, mes, dia] = hoje.split('-').map(Number);
      return {
        ordem: dados.operacoes.map((r) => r.id),
        lixeira: dados.lixeira.map((r) => r.id),
        previsao_atual: Object.fromEntries(dados.operacoes.map((r) => [r.id, r.previsao_atual])),
        situacoes: Object.fromEntries(dados.operacoes.map((r) => [r.id, D.situacao(r, hoje)])),
        totais: D.contarSituacoes(dados.operacoes, hoje),
        indicadores: D.indicadores(dados.operacoes),
        buscas: Object.fromEntries(termos.map((t) => [t, D.filtrar(dados.operacoes, t).map((r) => r.id)])),
        resumo: D.resumoMensal(dados.operacoes, 12, new Date(ano, mes - 1, dia)),
        moedas: valores.map(D.moeda),
        cpfs: textos_cpf.map((t) => { try { return D.validarCpf(t); } catch (erro) { return 'ERRO: ' + erro.message; } }),
        contas_regras: casos_conta.map((c) => D.problemasDaConta(c, dados.contas)),
        chaves: textos.map(D.chaveTexto),
        historico: Object.fromEntries([...dados.historico].map(([id, lista]) => [id, lista.length])),
        prorrogacoes: Object.fromEntries([...dados.prorrogacoes].map(([id, lista]) => [id, lista.length])),
        documentos: Object.fromEntries([...dados.documentos].map(([id, lista]) => [id, lista.map((d) => d.nome)])),
        anexos,
        recusas,
        agenda: (() => {
          const a = D.agenda(dados.operacoes, hoje);
          const ids = (lista) => lista.map((r) => r.id);
          return { atrasadas: ids(a.atrasadas), hoje: ids(a.hoje), amanha: ids(a.amanha), semana: ids(a.semana),
            dias: Object.fromEntries([...a.porDia].map(([dia, lista]) => [dia, ids(lista)])) };
        })(),
        mensagens: mensagens.map((m) => D.extrairDaMensagem(m)),
        semanas: Object.fromEntries(['2026-02', '2026-10', '2027-08', '2028-02'].map((m) => [m, D.semanasDoMes(m)])),
        previsoes: dados.operacoes.map((r) => D.problemasDaPrevisao(r, '2026-01-01').concat(D.problemasDaPrevisao(r, r.previsao_atual))),
      };
    }, regras);

    // Sem nada guardado, a demonstração abre sozinha: sai dela para abrir o backup de teste.
    await pagina.waitForSelector('text=Começar com meus dados', { timeout: 30000 });
    await pagina.click('text=Começar com meus dados');
    await pagina.waitForSelector('#abertura:not([hidden])');

    // As telas: abre o backup pelo formulário e passa por todas, guardando o texto de cada uma.
    await pagina.setInputFiles('#arquivo', telas.arquivo);
    await pagina.fill('#senha', telas.senha);
    await pagina.click('#abrir');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    resultados.telas = {};
    for (const endereco of telas.enderecos) {
      await pagina.evaluate((h) => { location.hash = h; }, endereco);
      await pagina.waitForFunction(() => document.getElementById('tela').childElementCount > 0
        && !document.getElementById('tela').innerText.includes('Carregando…'));
      resultados.telas[endereco] = await pagina.evaluate(() => document.getElementById('aplicativo').innerText);
    }
    // Cada anexo aberto na tela: PDF desenhado pelo pdf.js na largura da tela, com zoom; imagem como imagem.
    resultados.documentos = {};
    for (const endereco of telas.documentos) {
      await pagina.evaluate((h) => { location.hash = h; }, endereco);
      const visualizacao = await pagina.waitForSelector('.documento canvas, .documento img, .documento .erro', { timeout: 30000 });
      const tag = await visualizacao.evaluate((e) => e.tagName.toLowerCase());
      if (tag === 'canvas') {
        // Espera a primeira página terminar de ser desenhada (o WebKit leva mais tempo que o Chromium).
        await pagina.waitForFunction(() => document.querySelector('.pagina canvas').dataset.pronta === '1',
          null, { timeout: 30000 });
        const medida = () => pagina.evaluate(() => {
          const tela = document.querySelector('.pagina canvas');
          const contexto = tela.getContext('2d');
          const dados = contexto.getImageData(0, 0, tela.width, Math.floor(tela.height / 4)).data;
          let escuros = 0;
          for (let i = 0; i < dados.length; i += 4) {
            escuros += dados[i] < 128 && dados[i + 3] > 0 ? 1 : 0;
          }
          return {
            paginas: document.querySelectorAll('.pagina').length, pixels_desenhados: tela.width * tela.height,
            texto_desenhado: escuros > 50, largura: tela.getBoundingClientRect().width,
            largura_tela: document.querySelector('.visualizacao').clientWidth,
            titulo: document.getElementById('titulo').textContent,
          };
        });
        const antes = await medida();
        await pagina.click('[aria-label="Aumentar o zoom"]');
        await pagina.waitForFunction(() => document.querySelector('.pagina canvas').dataset.pronta === '1.5',
          null, { timeout: 30000 });
        antes.largura_com_zoom = (await medida()).largura;
        antes.rotulo_zoom = await pagina.evaluate(() => document.querySelector('.zoom span').textContent);
        resultados.documentos[endereco] = antes;
      } else {
        resultados.documentos[endereco] = await visualizacao.evaluate((e) => ({
          tag: e.tagName.toLowerCase(), blob: (e.getAttribute('src') || '').startsWith('blob:'), carregada: false,
          erro: e.tagName === 'P' ? e.textContent : '',
        }));
        if (tag === 'img') {
          await pagina.waitForFunction(() => document.querySelector('.documento img').naturalWidth > 0, null, { timeout: 10000 })
            .then(() => { resultados.documentos[endereco].carregada = true; }).catch(() => {});
        }
      }
    }
    // Nova entrada no celular: primeiro com um erro (a regra aparece), depois certa; o arquivo cifrado que o
    // app guardou volta em base64 para o Python importar como o programa importa.
    if (telas.nova) {
      const n = telas.nova;
      await pagina.evaluate(() => { location.hash = '#nova'; });
      await pagina.waitForSelector('form [name="nome"]');
      await pagina.fill('[name="nome"]', n.nome);
      await pagina.fill('[name="aquisicao"]', n.aquisicao);
      // Máscara de valor: os números entram pelos centavos e a pontuação aparece sozinha.
      await pagina.click('[name="custo"]');
      resultados.mascara = [];
      for (const tecla of '1234567') {
        await pagina.keyboard.type(tecla);
        resultados.mascara.push(await pagina.inputValue('[name="custo"]'));
      }
      await pagina.keyboard.press('Backspace');
      resultados.mascara.push(await pagina.inputValue('[name="custo"]'));
      await pagina.fill('[name="custo"]', '');
      await pagina.keyboard.type('900000');
      await pagina.fill('[name="previsto"]', n.previsto);
      await pagina.selectOption('[name="conta"]', String(n.conta_id));
      await pagina.fill('[name="previsao"]', n.previsao);
      await pagina.fill('[name="comissao"]', n.comissao);
      await pagina.fill('[name="observacoes"]', n.observacoes);
      await pagina.click('text=Salvar entrada');
      await pagina.waitForFunction(() => document.querySelector('form .erro').textContent.length > 0);
      resultados.nova_erro = await pagina.evaluate(() => document.querySelector('form .erro').textContent);
      await pagina.fill('[name="custo"]', n.custo);
      resultados.nova_lucro = await pagina.evaluate(() => document.querySelector('#tela form p.discreto').textContent);
      await pagina.click('text=Salvar entrada');
      await pagina.waitForFunction(() => location.hash.startsWith('#enviar/'));
      resultados.nova_tela = await pagina.evaluate(() => document.getElementById('tela').innerText);
      // Conta nova no celular: primeiro com erros (apelido repetido, CPF inválido), depois certa.
      const contaNova = telas.conta;
      await pagina.evaluate(() => { location.hash = '#nova-conta'; });
      await pagina.waitForSelector('form [name="identificacao"]');
      for (const [campo, valor] of Object.entries({ ...contaNova, identificacao: 'vitor', cpf: '11111111111' })) {
        if (campo === 'estado') {
          await pagina.selectOption('[name="estado"]', valor);
        } else {
          await pagina.fill(`[name="${campo}"]`, valor);
        }
      }
      await pagina.click('text=Salvar conta');
      await pagina.waitForFunction(() => document.querySelector('form .erro').textContent.length > 0);
      resultados.conta_erro = await pagina.evaluate(() => document.querySelector('form .erro').innerText);
      await pagina.fill('[name="identificacao"]', contaNova.identificacao);
      await pagina.fill('[name="cpf"]', contaNova.cpf);
      resultados.cpf_mascara = await pagina.inputValue('[name="cpf"]');
      await pagina.click('text=Salvar conta');
      await pagina.waitForFunction(() => location.hash.startsWith('#enviar/'));
      await pagina.evaluate(() => { location.hash = '#nova'; });
      await pagina.waitForSelector('form [name="conta"]');
      resultados.opcoes_conta = await pagina.evaluate(() => Array.from(document.querySelectorAll('[name="conta"] option'), (o) => o.textContent));
      await pagina.evaluate(() => { location.hash = '#contas'; });
      await pagina.waitForSelector('text=aguarda o computador');
      resultados.nova_arquivos = await pagina.evaluate(async () => (await Guarda.ler('pendentes')).map((p) => ({
        id: p.id, tipo: p.tipo, arquivo: p.arquivo, bytes: btoa(String.fromCharCode(...new Uint8Array(p.bytes))) })));
      await pagina.evaluate(() => { location.hash = '#operacoes'; });
      await pagina.waitForSelector('text=aguarda o computador');
      // Entrada já importada no computador (o backup novo traz a lista): some do celular ao abrir esse backup.
      await pagina.evaluate(async (id) => {
        const lista = await Guarda.ler('pendentes');
        await Guarda.gravar('pendentes', [...lista, { id, arquivo: 'antiga.rpvcelular', criada_em: '2026-10-01T10:00:00Z', bytes: new Uint8Array([1, 2, 3]) }]);
      }, n.ja_importada);
      await pagina.evaluate(() => { location.hash = '#mais'; });
      await pagina.getByText('Trancar agora').click();
      await pagina.waitForSelector('#abertura:not([hidden])');
      await pagina.setInputFiles('#arquivo', n.backup_com_importada);
      await pagina.fill('#senha', telas.senha);
      await pagina.click('#abrir');
      await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
      resultados.pendentes_depois = await pagina.evaluate(async () => (await Guarda.ler('pendentes')).map((p) => p.id));
    }

    // Mudanças em operações do computador: editar, alterar a previsão, excluir e anexar uma foto. Cada uma vira um
    // arquivo para o computador; o Python importa e confere.
    if (telas.mudancas) {
      const m = telas.mudancas;
      const ir = async (hash, seletor) => {
        await pagina.evaluate((h) => { location.hash = h; }, hash);
        await pagina.waitForSelector(seletor);
      };
      const esperarEnvio = () => pagina.waitForFunction(() => location.hash.startsWith('#enviar/'));
      await ir(`#editar/${m.editar}`, 'form [name="nome"]');
      await pagina.click('text=Salvar alterações');
      await pagina.waitForFunction(() => document.querySelector('form .erro').textContent.length > 0);
      resultados.editar_sem_mudar = await pagina.textContent('form .erro');
      resultados.editar_valores = await pagina.evaluate(() => Object.fromEntries(['nome', 'custo', 'previsto', 'previsao', 'conta']
        .map((n) => [n, document.querySelector(`[name="${n}"]`).value])));
      await pagina.fill('[name="previsto"]', '3000000');
      await pagina.fill('[name="observacoes"]', 'editada no celular');
      await pagina.click('text=Salvar alterações');
      await esperarEnvio();
      resultados.editar_tela = await pagina.evaluate(() => document.getElementById('tela').innerText);

      await ir(`#operacao/${m.previsao}`, 'details.acao');
      await pagina.click('details.acao summary');
      await pagina.fill('[name="nova_previsao"]', '2020-01-01');
      await pagina.click('text=Salvar nova previsão');
      await pagina.waitForFunction(() => document.querySelector('details.acao .erro').textContent.length > 0);
      resultados.previsao_erro = await pagina.textContent('details.acao .erro');
      await pagina.fill('[name="nova_previsao"]', m.nova_previsao);
      await pagina.click('text=Salvar nova previsão');
      await esperarEnvio();

      await ir(`#operacao/${m.excluir}`, 'text=Excluir operação');
      pagina.once('dialog', (d) => d.accept());
      await pagina.click('text=Excluir operação');
      await esperarEnvio();

      await ir(`#operacao/${m.anexar}`, '[name="anexar"]');
      await pagina.setInputFiles('[name="anexar"]', { name: 'image.png', mimeType: 'image/png', buffer: Buffer.from(m.png, 'base64') });
      await pagina.waitForFunction(() => location.hash.startsWith('#enviar/') || document.querySelector('p.erro[role="status"]'));
      const erroAnexo = await pagina.evaluate(() => (document.querySelector('p.erro[role="status"]') || {}).textContent);
      if (erroAnexo) {
        throw new Error('Anexo recusado: ' + erroAnexo);
      }
      resultados.anexo_tela = await pagina.evaluate(() => document.getElementById('tela').innerText);

      await ir(`#operacao/${m.editar}`, 'text=Excluir operação');
      resultados.operacao_com_pendente = await pagina.evaluate(() => document.getElementById('tela').innerText);
      await ir('#pendentes', '.menu');
      resultados.pendentes_tela = await pagina.evaluate(() => document.getElementById('tela').innerText);
      resultados.mudancas_arquivos = await pagina.evaluate(async () => (await Guarda.ler('pendentes'))
        .filter((p) => !['entrada', 'conta'].includes(p.tipo)).map((p) => {
          const bytes = new Uint8Array(p.bytes);
          let texto = '';
          for (let i = 0; i < bytes.length; i += 0x8000) {
            texto += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
          }
          return { id: p.id, tipo: p.tipo, arquivo: p.arquivo, bytes: btoa(texto) };
        }));
      // Agenda: no Início e no calendário, com as atrasadas de hoje (pelo relógio do aparelho).
      await ir('#inicio', '.agenda-resumo');
      resultados.inicio_agenda = await pagina.evaluate(() => document.querySelector('.agenda-resumo').innerText);
      await pagina.click('.agenda-resumo');
      await pagina.waitForSelector('.grade-agenda');
      resultados.agenda = await pagina.evaluate(() => {
        const D = GestorDados;
        const hoje = D.hojeIso();
        return {
          texto: document.getElementById('tela').innerText,
          dias: document.querySelectorAll('.grade-agenda [data-dia]').length,
          hoje: document.querySelector('.grade-agenda .dia.hoje').dataset.dia === hoje,
          titulo: document.getElementById('titulo').textContent,
        };
      });
      await pagina.click('[aria-label="Próximo mês"]');
      resultados.agenda_proximo_mes = await pagina.evaluate(() => document.querySelector('.mes-agenda .nome').textContent);
    }

    // Modo discreto, colar e preencher e o resumo em imagem.
    if (telas.extras) {
      const x = telas.extras;
      const textoTela = () => pagina.evaluate(() => document.getElementById('tela').innerText);
      const ir = async (hash, seletor) => {
        await pagina.evaluate((h) => { location.hash = h; }, hash);
        await pagina.waitForSelector(seletor);
      };
      await ir('#inicio', '.indicadores');
      resultados.discreto_antes = await textoTela();
      await pagina.click('#discreto');
      resultados.discreto_inicio = await textoTela();
      if (process.env.GESTOR_RPV_PASTA_IMAGENS) {
        await pagina.screenshot({ path: `${process.env.GESTOR_RPV_PASTA_IMAGENS}/tela-discreto.png` });
      }
      await ir(`#operacao/${x.operacao}`, 'dl.campos');
      resultados.discreto_operacao = await textoTela();
      resultados.discreto_guardado = await pagina.evaluate(() => [localStorage.getItem('discreto'),
        document.getElementById('discreto').getAttribute('aria-pressed')]);
      await pagina.click('#discreto');
      resultados.discreto_depois = await textoTela();

      // No fim da operação, o último botão fica visível acima das abas fixas (a página rola até ele).
      await ir(`#operacao/${x.operacao}`, 'button.perigo');
      await pagina.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      resultados.fim_da_operacao = await pagina.evaluate(() => ({
        botao: document.querySelector('button.perigo').getBoundingClientRect().bottom,
        abas: document.querySelector('.abas').getBoundingClientRect().top,
      }));
      await ir('#nova', 'details.colar');
      await pagina.click('details.colar summary');
      await pagina.fill('[name="texto_colado"]', x.mensagem);
      await pagina.click('details.colar button.secundario');
      resultados.colar = await pagina.evaluate(() => ({
        ...Object.fromEntries(['nome', 'aquisicao', 'custo', 'previsto', 'previsao', 'comissao', 'observacoes']
          .map((n) => [n, document.querySelector(`[name="${n}"]`).value])),
        aviso: document.querySelector('details.colar [role="status"]').textContent,
        lucro: document.querySelector('#tela form p.discreto').textContent,
      }));
      if (process.env.GESTOR_RPV_PASTA_IMAGENS) {
        await pagina.screenshot({ path: `${process.env.GESTOR_RPV_PASTA_IMAGENS}/tela-colar.png`, fullPage: true });
      }
      await pagina.fill('[name="texto_colado"]', 'oi, tudo bem?');
      await pagina.click('details.colar button.secundario');
      resultados.colar_nada = await pagina.textContent('details.colar [role="status"]');

      await ir(`#resumo/${x.operacao}`, 'img.resumo-imagem');
      const imagem = () => pagina.waitForFunction(() => {
        const img = document.querySelector('img.resumo-imagem');
        return img.complete && img.naturalWidth > 0 && img.src;
      }, null, { timeout: 20000 }).then((h) => h.jsonValue());
      const primeira = await imagem();
      // Para conferir o visual: GESTOR_RPV_PASTA_IMAGENS=/pasta guarda a imagem e capturas de tela.
      if (process.env.GESTOR_RPV_PASTA_IMAGENS) {
        const pasta = process.env.GESTOR_RPV_PASTA_IMAGENS;
        // A página não busca endereços blob: (política de segurança): a imagem é copiada por um canvas.
        const base64 = await pagina.evaluate(() => {
          const img = document.querySelector('img.resumo-imagem');
          const tela = document.createElement('canvas');
          tela.width = img.naturalWidth;
          tela.height = img.naturalHeight;
          tela.getContext('2d').drawImage(img, 0, 0);
          return tela.toDataURL('image/png').split(',')[1];
        });
        require('fs').writeFileSync(`${pasta}/resumo.png`, Buffer.from(base64, 'base64'));
        await pagina.screenshot({ path: `${pasta}/tela-resumo.png`, fullPage: true });
      }
      resultados.resumo = await pagina.evaluate(() => {
        const img = document.querySelector('img.resumo-imagem');
        return { largura: img.naturalWidth, altura: img.naturalHeight, texto: document.getElementById('tela').innerText,
          titulo: document.getElementById('titulo').textContent };
      });
      await pagina.check('[name="com_valor"]');
      await pagina.waitForFunction((antes) => document.querySelector('img.resumo-imagem').src !== antes, primeira);
      resultados.resumo_trocou = (await imagem()) !== primeira;
    }

    await pagina.evaluate(() => { location.hash = '#mais'; });
    resultados.blob_liberado = await pagina.evaluate(() => !document.querySelector('.documento'));
    await pagina.getByText('Trancar agora').click();
    resultados.fechado = await pagina.evaluate(() => ({
      abertura: !document.getElementById('abertura').hidden,
      tela_vazia: document.getElementById('tela').childElementCount === 0,
      senha_vazia: document.getElementById('senha').value === '',
    }));
    // App na Tela de Início: o service worker guarda o código, e o app abre de novo sem internet.
    resultados.service_worker = await pagina.evaluate(() => Promise.race([
      navigator.serviceWorker.ready.then(() => true),
      new Promise((ok) => setTimeout(() => ok(false), 15000)),
    ]));
    // O modo sem internet do Playwright não funciona junto com service worker no WebKit: lá, fica só o registro.
    resultados.sem_internet = null;
    if (NAVEGADOR === 'chromium') {
      await pagina.context().setOffline(true);
      await pagina.reload();
      resultados.sem_internet = await pagina.evaluate(() => Boolean(document.getElementById('formulario'))
        && typeof GestorDados === 'object' && typeof LeitorBackup === 'object' && typeof initSqlJs === 'function');
      await pagina.context().setOffline(false);
    }
    resultados.erros = erros;
    process.stdout.write(JSON.stringify(resultados));
  } finally {
    await navegador.close();
  }
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
