// Abrir com Face ID: uma chave de acesso (passkey) deste site, guardada no Chaves do iCloud, com a extensão
// PRF. A cada Face ID aprovado, o iPhone devolve sempre o mesmo segredo de 32 bytes para esta chave de acesso;
// dele sai a chave que tranca, aqui no aparelho, a senha do backup e a chave já calculada. Sem o Face ID, o
// que fica guardado é ilegível. Não há servidor: o desafio é aleatório e a assinatura não é usada.
'use strict';

const FaceId = (() => {
  const REGISTRO = 'faceid';
  // Cópia do registro, lida antes do toque: o pedido de Face ID precisa sair logo no toque, sem esperar o banco.
  let memoria;
  const enc = new TextEncoder();

  class FaceIdIndisponivel extends Error {}

  const aleatorio = (n) => crypto.getRandomValues(new Uint8Array(n));
  const paraB64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
  const deB64 = (texto) => Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));

  // Há leitor de rosto ou digital no aparelho? (Não garante a extensão PRF, que só se confirma ao ativar.)
  async function possivel() {
    if (!window.PublicKeyCredential || !PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) {
      return false;
    }
    try {
      if (PublicKeyCredential.getClientCapabilities) {
        const capacidades = await PublicKeyCredential.getClientCapabilities();
        if (capacidades['extension:prf'] === false) {
          return false;
        }
      }
      return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch (erro) {
      return false;
    }
  }

  async function chaveDoSegredo(segredo, sal) {
    const base = await crypto.subtle.importKey('raw', segredo, 'HKDF', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'HKDF', hash: 'SHA-256', salt: sal, info: enc.encode('gestor-rpv faceid') },
      base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  }

  async function segredoPrf(credencial, salPrf) {
    const resposta = await navigator.credentials.get({ publicKey: {
      challenge: aleatorio(32), rpId: location.hostname, userVerification: 'required', timeout: 60000,
      allowCredentials: [{ type: 'public-key', id: credencial }],
      extensions: { prf: { eval: { first: salPrf } } },
    } });
    const resultado = resposta.getClientExtensionResults().prf;
    if (!resultado || !resultado.results || !resultado.results.first) {
      throw new FaceIdIndisponivel('Este iPhone não oferece o recurso necessário para abrir com Face ID (iOS 18 ou mais novo).');
    }
    return new Uint8Array(resultado.results.first);
  }

  // Cria a chave de acesso (pede o Face ID) e tranca `segredo` (um objeto) com ela.
  async function ativar(segredo) {
    const salPrf = aleatorio(32);
    const criada = await navigator.credentials.create({ publicKey: {
      rp: { name: 'Gestor de RPV', id: location.hostname },
      user: { id: aleatorio(16), name: 'Gestor de RPV', displayName: 'Gestor de RPV (abrir com Face ID)' },
      challenge: aleatorio(32),
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
      authenticatorSelection: { authenticatorAttachment: 'platform', residentKey: 'required', userVerification: 'required' },
      timeout: 60000,
      extensions: { prf: { eval: { first: salPrf } } },
    } });
    const extensao = criada.getClientExtensionResults().prf;
    if (!extensao || extensao.enabled === false) {
      throw new FaceIdIndisponivel('Este iPhone não oferece o recurso necessário para abrir com Face ID (iOS 18 ou mais novo).');
    }
    const credencial = new Uint8Array(criada.rawId);
    const registro = { credencial: paraB64(credencial), salPrf: paraB64(salPrf) };
    if (extensao.results && extensao.results.first) {
      await trancar(registro, new Uint8Array(extensao.results.first), segredo);
      return null;
    }
    // O iPhone não devolve o segredo na criação: é preciso mais um Face ID, e o Safari exige um toque antes dele.
    // Devolve a função que o completa, para ser chamada no toque seguinte.
    return async () => trancar(registro, await segredoPrf(credencial, salPrf), segredo);
  }

  async function trancar(registro, segredoPrfObtido, segredo) {
    const salHkdf = aleatorio(32);
    const iv = aleatorio(12);
    const chave = await chaveDoSegredo(segredoPrfObtido, salHkdf);
    const cifrado = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, chave, enc.encode(JSON.stringify(segredo)));
    memoria = { ...registro, salHkdf: paraB64(salHkdf), iv: paraB64(iv), cifrado: paraB64(cifrado) };
    await Guarda.gravar(REGISTRO, memoria);
  }

  async function ativo() {
    memoria = await Guarda.ler(REGISTRO);
    return Boolean(memoria);
  }

  // Pede o Face ID e devolve o objeto guardado em ativar() e mais a função de trocá-lo pelo mesmo Face ID
  // (usada quando chega um backup novo, com outra chave).
  async function abrir() {
    const registro = memoria === undefined ? await Guarda.ler(REGISTRO) : memoria;
    if (!registro) {
      throw new FaceIdIndisponivel('O Face ID ainda não foi ativado neste app.');
    }
    const segredoPrfObtido = await segredoPrf(deB64(registro.credencial), deB64(registro.salPrf));
    const chave = await chaveDoSegredo(segredoPrfObtido, deB64(registro.salHkdf));
    let texto;
    try {
      texto = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: deB64(registro.iv) }, chave, deB64(registro.cifrado));
    } catch (erro) {
      throw new FaceIdIndisponivel('Não foi possível usar o Face ID guardado. Abra com a senha e ative de novo.');
    }
    return {
      segredo: JSON.parse(new TextDecoder().decode(texto)),
      atualizar: (novo) => trancar({ credencial: registro.credencial, salPrf: registro.salPrf }, segredoPrfObtido, novo),
    };
  }

  const desativar = () => {
    memoria = null;
    return Guarda.apagar(REGISTRO);
  };

  return { possivel, ativar, ativo, abrir, desativar, FaceIdIndisponivel, paraB64, deB64 };
})();
