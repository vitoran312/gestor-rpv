// Etapa 1: só conta o que há no backup e mede quanto o aparelho leva em cada parte.
'use strict';

(() => {
  const $ = (id) => document.getElementById(id);
  const ETAPAS = { senha: 'Conferindo a senha', decifrar: 'Abrindo o backup' };

  function preencher(lista, itens) {
    lista.replaceChildren();
    for (const [rotulo, valor] of itens) {
      const termo = document.createElement('dt');
      termo.textContent = rotulo;
      const descricao = document.createElement('dd');
      descricao.textContent = valor;
      lista.append(termo, descricao);
    }
  }

  function contar(db, sql) {
    return db.exec(sql)[0].values[0][0];
  }

  function dataHora(iso) {
    const data = new Date(iso);
    return Number.isNaN(data.getTime()) ? 'não informada' : data.toLocaleString('pt-BR');
  }

  function tamanho(bytes) {
    if (bytes < 1024 * 1024) {
      return Math.max(1, Math.round(bytes / 1024)).toLocaleString('pt-BR') + ' KB';
    }
    return (bytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' MB';
  }

  $('formulario').addEventListener('submit', async (evento) => {
    evento.preventDefault();
    const arquivo = $('arquivo').files[0];
    $('erro').hidden = true;
    $('resultado').hidden = true;
    $('abrir').disabled = true;
    const inicio = performance.now();
    try {
      $('andamento').textContent = 'Lendo o arquivo…';
      const bytes = new Uint8Array(await arquivo.arrayBuffer());
      const leitura = await LeitorBackup.ler(bytes, $('senha').value, {
        aoProgredir: (etapa, fracao) => {
          $('andamento').textContent = `${ETAPAS[etapa]}… ${Math.round(fracao * 100)}%`;
        },
      });
      const { db, manifesto, tempos } = leitura;
      try {
        preencher($('resumo'), [
          ['Arquivo', `${arquivo.name} (${tamanho(arquivo.size)})`],
          ['Protegido por senha', leitura.cifrado ? 'sim' : 'não'],
          ['Criado em', dataHora(manifesto.criado_em)],
          ['Versão do programa', manifesto.versao_app || 'não informada'],
          ['Versão do banco', String(contar(db, 'PRAGMA user_version'))],
          ['Operações', String(contar(db, 'SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NULL'))],
          ['Na lixeira', String(contar(db, 'SELECT COUNT(*) FROM rpvs WHERE lixeira_em IS NOT NULL'))],
          ['Contas', String(contar(db, 'SELECT COUNT(*) FROM contas'))],
          ['Documentos cadastrados', String(contar(db, 'SELECT COUNT(*) FROM documentos'))],
          ['Alterações de previsão', String(contar(db, 'SELECT COUNT(*) FROM previsoes_historico'))],
        ]);
      } finally {
        db.close();
      }
      preencher($('tempos'), [
        ...Object.entries(tempos).map(([etapa, ms]) => [etapa.replace('_', ' '), `${ms} ms`]),
        ['total', `${Math.round(performance.now() - inicio)} ms`],
      ]);
      $('andamento').textContent = '';
      $('resultado').hidden = false;
    } catch (erro) {
      $('andamento').textContent = '';
      $('erro').textContent = erro instanceof LeitorBackup.ErroBackup ? erro.message
        : 'Não foi possível abrir o backup neste aparelho: ' + (erro && erro.message ? erro.message : erro);
      $('erro').hidden = false;
    } finally {
      $('abrir').disabled = false;
    }
  });
})();
