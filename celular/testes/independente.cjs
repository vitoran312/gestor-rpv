// Quem usa só o celular: começa sem computador, cadastra conta e entrada, registra o recebimento, tranca e abre
// de novo. Imprime, em JSON, o que aconteceu e o arquivo guardado (base64), para o Python abrir no programa.
'use strict';
const playwright = require('playwright');

const NAVEGADOR = process.env.GESTOR_RPV_NAVEGADOR || 'chromium';

(async () => {
  const [endereco, entradaJson] = process.argv.slice(2);
  const { senha, conta, entrada, segunda, hoje, senhas_ruins: senhasRuins, nomes, senhas_regra: senhasRegra } = JSON.parse(entradaJson);
  const navegador = await playwright[NAVEGADOR].launch();
  const r = {};
  try {
    const pagina = await (await navegador.newContext()).newPage();
    const erros = [];
    pagina.on('pageerror', (erro) => erros.push(String(erro)));
    const texto = () => pagina.evaluate(() => document.getElementById('tela').innerText);
    const ir = async (hash) => {
      await pagina.evaluate((h) => { location.hash = h; }, hash);
      await pagina.waitForFunction((h) => location.hash === h && document.getElementById('tela').childElementCount > 0, hash);
    };
    await pagina.goto(endereco + '/index.html');
    // Regras de dados.js comparadas com o Python.
    r.regras = await pagina.evaluate(({ nomes, senhasRegra }) => ({
      titulos: nomes.map(GestorDados.nomeTitulo),
      senhas: senhasRegra.map((s) => { try { GestorDados.validarSenha(s); return 'ok'; } catch (e) { return e.message; } }),
    }), { nomes, senhasRegra });

    // 0. Primeira vez, sem dados: a demonstração abre sozinha, com o aviso de dados fictícios em todas as telas.
    await pagina.waitForSelector('text=Começar com meus dados', { timeout: 30000 });
    r.demonstracao = {};
    for (const hash of ['#inicio', '#operacoes', '#contas', '#mais', '#nova', '#agenda']) {
      await ir(hash);
      r.demonstracao[hash] = await texto();
    }
    await pagina.evaluate(() => { location.hash = '#operacao/1'; });
    await pagina.waitForSelector('text=Compartilhar resumo em imagem');
    r.demonstracao.operacao = await texto();
    await pagina.click('text=Começar com meus dados');
    await pagina.waitForSelector('#abertura:not([hidden])');
    r.depois_da_demonstracao = await pagina.evaluate(() => ({ app: !document.getElementById('aplicativo').hidden,
      comecar: !document.getElementById('comecar').hidden, demonstracao: !document.getElementById('ver-demonstracao').hidden }));

    // 1. "Começar sem computador", com senhas ruins antes da boa.
    await pagina.click('#comecar');
    r.erros_senha = [];
    for (const [nova, repetida] of senhasRuins) {
      await pagina.fill('#senha-nova', nova);
      await pagina.fill('#senha-repetida', repetida);
      await pagina.click('#criar');
      await pagina.waitForSelector('#erro:not([hidden])');
      r.erros_senha.push(await pagina.textContent('#erro'));
    }
    await pagina.fill('#senha-nova', senha);
    await pagina.fill('#senha-repetida', senha);
    await pagina.click('#criar');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    r.inicio_vazio = await texto();

    // 2. Conta e entrada gravadas direto no celular.
    await ir('#nova-conta');
    for (const [campo, valor] of Object.entries(conta)) {
      if (campo === 'estado') {
        await pagina.selectOption('[name="estado"]', valor);
      } else {
        await pagina.fill(`[name="${campo}"]`, valor);
      }
    }
    await pagina.click('text=Salvar conta');
    await pagina.waitForFunction(() => location.hash === '#contas');
    await pagina.waitForSelector('text=+ Nova conta');
    r.contas = await texto();
    await ir('#nova');
    await pagina.fill('[name="nome"]', entrada.nome);
    await pagina.fill('[name="aquisicao"]', entrada.aquisicao);
    await pagina.fill('[name="custo"]', entrada.custo);
    await pagina.fill('[name="previsto"]', entrada.previsto);
    await pagina.selectOption('[name="conta"]', { index: 1 });
    await pagina.fill('[name="previsao"]', entrada.previsao);
    await pagina.fill('[name="observacoes"]', entrada.observacoes);
    await pagina.click('text=Salvar entrada');
    await pagina.waitForFunction(() => location.hash.startsWith('#operacao/'));
    await pagina.waitForSelector('text=Registrar recebimento');
    r.detalhe = await texto();

    // 3. Recebimento: primeiro no futuro (recusado), depois numa data válida.
    await pagina.fill('[name="recebimento"]', '2099-01-01');
    await pagina.click('text=Registrar recebimento');
    await pagina.waitForFunction(() => document.querySelector('form.recebimento .erro').textContent.length > 0);
    r.erro_recebimento = await pagina.textContent('form.recebimento .erro');
    await pagina.fill('[name="recebimento"]', hoje);
    await pagina.click('text=Registrar recebimento');
    await pagina.waitForFunction(() => !document.querySelector('form.recebimento'));
    r.detalhe_recebido = await texto();

    // 3b. Segunda entrada, já com um PDF e uma foto; depois editada, com nova previsão, mais uma foto, excluída
    // e restaurada da lixeira.
    await ir('#nova');
    await pagina.fill('[name="nome"]', segunda.nome);
    await pagina.fill('[name="aquisicao"]', entrada.aquisicao);
    await pagina.fill('[name="custo"]', segunda.custo);
    await pagina.fill('[name="previsto"]', segunda.previsto);
    await pagina.selectOption('[name="conta"]', { index: 1 });
    await pagina.fill('[name="previsao"]', segunda.previsao);
    await pagina.setInputFiles('[name="documentos"]', [
      { name: 'Ofício.pdf', mimeType: 'application/pdf', buffer: Buffer.from(segunda.pdf, 'base64') },
      { name: 'image.png', mimeType: 'image/png', buffer: Buffer.from(segunda.png, 'base64') }]);
    await pagina.click('text=Salvar entrada');
    await pagina.waitForFunction(() => location.hash.startsWith('#operacao/'));
    await pagina.waitForSelector('text=Excluir operação');
    const segundaId = await pagina.evaluate(() => location.hash.split('/')[1]);
    r.segunda_criada = await texto();
    await ir(`#editar/${segundaId}`);
    await pagina.fill('[name="previsto"]', segunda.novo_previsto);
    await pagina.fill('[name="observacoes"]', 'editada no celular');
    await pagina.click('text=Salvar alterações');
    await pagina.waitForFunction((id) => location.hash === `#operacao/${id}`, segundaId);
    await pagina.waitForSelector('text=Excluir operação');
    await pagina.click('details.acao summary');
    await pagina.fill('[name="nova_previsao"]', segunda.nova_previsao);
    await pagina.click('text=Salvar nova previsão');
    await pagina.waitForSelector('text=A previsão nunca foi alterada.', { state: 'detached' });
    const documentos = () => pagina.evaluate(() => document.querySelectorAll('#tela a[href^="#documento/"]').length);
    await pagina.setInputFiles('[name="anexar"]', { name: 'Recibo.png', mimeType: 'image/png', buffer: Buffer.from(segunda.png, 'base64') });
    await pagina.waitForFunction(() => document.querySelectorAll('#tela a[href^="#documento/"]').length === 3);
    r.segunda_editada = await texto();
    // A foto anexada agora abre na tela (o anexo saiu do pacote regravado).
    await pagina.click('text=Recibo.jpg');
    await pagina.waitForFunction(() => document.querySelector('.documento img') && document.querySelector('.documento img').naturalWidth > 0,
      null, { timeout: 20000 });
    r.foto_aberta = true;
    await ir(`#operacao/${segundaId}`);
    pagina.once('dialog', (d) => d.accept());
    await pagina.click('text=Excluir operação');
    await pagina.waitForFunction(() => location.hash === '#operacoes');
    await pagina.waitForSelector('text=+ Nova entrada');
    r.operacoes_sem_segunda = await texto();
    await ir('#lixeira');
    r.lixeira = await texto();
    await ir(`#operacao/${segundaId}`);
    await pagina.click('text=Restaurar da lixeira');
    await pagina.waitForSelector('text=Excluir operação');
    r.restaurada = await texto();
    r.documentos_restaurada = await documentos();
    // Agenda: avança os meses até o da nova previsão e toca no dia.
    await ir('#agenda');
    for (let i = 0; i < 36 && await pagina.textContent('.mes-agenda .nome') !== segunda.mes_previsao; i += 1) {
      await pagina.click('[aria-label="Próximo mês"]');
    }
    await pagina.click(`[data-dia="${segunda.nova_previsao}"]`);
    r.agenda = await texto();
    await ir('#inicio');
    r.inicio_com_dados = await texto();

    // 4. Trancar e abrir de novo com a senha: os dados continuam.
    await ir('#mais');
    r.mais = await texto();
    await pagina.evaluate(() => trancarGestor());
    await pagina.waitForFunction(() => document.getElementById('fonte-titulo').textContent.length > 0
      && !document.getElementById('abertura').hidden);
    r.abertura = await pagina.evaluate(() => ({
      fonte: document.getElementById('fonte-titulo').textContent,
      comecar: !document.getElementById('comecar').hidden,
      trocar: document.getElementById('trocar-backup').textContent,
    }));
    await pagina.fill('#senha', senha);
    await pagina.click('#abrir');
    await pagina.waitForSelector('#aplicativo:not([hidden])', { timeout: 120000 });
    await ir('#operacoes');
    r.operacoes_depois = await texto();
    await ir(`#operacao/${segundaId}`);
    r.documentos_depois = await documentos();
    await ir('#copia');
    r.copia = await texto();
    await ir('#convite');
    r.convite = await texto();
    r.guardado = await pagina.evaluate(async () => {
      const g = await Guarda.ler('backup');
      return { independente: g.independente, bytes: btoa(Array.from(new Uint8Array(g.bytes), (b) => String.fromCharCode(b)).join('')) };
    });
    // 5. Excluir permanentemente da lixeira: some de vez, com os anexos fora do pacote guardado.
    const tamanho = () => pagina.evaluate(async () => (await Guarda.ler('backup')).bytes.byteLength);
    const antes = await tamanho();
    await ir(`#operacao/${segundaId}`);
    pagina.once('dialog', (d) => d.accept());
    await pagina.click('text=Excluir operação');
    await pagina.waitForFunction(() => location.hash === '#operacoes');
    await ir(`#operacao/${segundaId}`);
    pagina.once('dialog', (d) => { r.aviso_de_vez = d.message(); d.accept(); });
    await pagina.click('text=Excluir permanentemente');
    await pagina.waitForFunction(() => location.hash === '#lixeira');
    await pagina.waitForSelector('text=A lixeira está vazia.');
    r.lixeira_de_vez = await texto();
    await ir('#operacoes');
    r.operacoes_de_vez = await texto();
    r.encolheu_de_vez = antes - await tamanho();
    // 6. Contas: editar (o formulário vem preenchido), desativar e remover, como no computador.
    await ir('#contas');
    await pagina.click('.acoes-conta >> text=Editar');
    await pagina.waitForSelector('[name="identificacao"]');
    r.conta_preenchida = await pagina.inputValue('[name="identificacao"]');
    await pagina.fill('[name="identificacao"]', 'Conta Renomeada');
    await pagina.click('text=Salvar conta');
    await pagina.waitForFunction(() => location.hash === '#contas');
    pagina.once('dialog', (d) => d.accept());
    await pagina.click('.acoes-conta >> text=Desativar');
    await pagina.waitForSelector('.acoes-conta >> text=Reativar');
    r.contas_desativada = await texto();
    pagina.once('dialog', (d) => { r.aviso_remover_conta = d.message(); d.accept(); });
    await pagina.click('.acoes-conta >> text=Remover');
    await pagina.waitForSelector('text=Nenhuma conta cadastrada.');
    await ir('#operacoes');
    await pagina.click('.lista a.item');
    await pagina.waitForSelector('text=Conta de destino');
    r.operacao_sem_conta = await texto();
    r.erros = erros;
  } finally {
    await navegador.close();
  }
  process.stdout.write(JSON.stringify(r));
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
