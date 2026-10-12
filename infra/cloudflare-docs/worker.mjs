// Advanced-mode Pages Worker: authorize every document, asset and search-index request.
const keys = new Map();
const denied = () => new Response('Authorized engineering access required.', {status:401});
const denialReason = error => {
  const known = new Set(['Access configuration missing','Access audience missing','Engineering identities missing','Approved hosts missing','Access keys unavailable','Access key response exceeds bound','Access keys invalid']);
  return known.has(error?.message) ? error.message : error?.name === 'TimeoutError' ? 'Access certificate request timed out' : 'Access verification failed';
};

function decode(value) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) throw new Error('Invalid token encoding');
  return Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')), char => char.charCodeAt(0));
}

function configuration(env) {
  if (!/^[a-z0-9][a-z0-9-]*\.cloudflareaccess\.com$/.test(env.CF_ACCESS_TEAM_DOMAIN || '')) throw new Error('Access configuration missing');
  const audiences=JSON.parse(env.CF_ACCESS_AUDIENCES || 'null');
  const emails=JSON.parse(env.CF_ACCESS_ENGINEERING_EMAILS || 'null');
  const hosts=JSON.parse(env.CF_ACCESS_ALLOWED_HOSTS || 'null');
  if (!Array.isArray(audiences) || !audiences.length || audiences.length>8 || audiences.some(x=>typeof x!=='string'||!/^[a-f0-9]{64}$/.test(x))) throw new Error('Access audience missing');
  if (!Array.isArray(emails)||!emails.length||emails.length>50||emails.some(x=>typeof x!=='string'||!/^\S+@\S+\.\S+$/.test(x))) throw new Error('Engineering identities missing');
  if (!Array.isArray(hosts)||!hosts.length||hosts.length>8||hosts.some(x=>typeof x!=='string'||!(/^[a-z0-9-]+\.pages\.dev$/.test(x)||/^\*\.[a-z0-9-]+\.pages\.dev$/.test(x)||x==='engineering.docs.onesa.eu'))) throw new Error('Approved hosts missing');
  return {issuer:'https://'+env.CF_ACCESS_TEAM_DOMAIN,audiences,emails:emails.map(x=>x.toLowerCase()),hosts};
}

async function publicKeys(issuer, kid) {
  const cached=keys.get(issuer);
  if (cached && cached.expires>Date.now() && cached.keys.some(x=>x.kid===kid)) return cached.keys;
  const response=await fetch(issuer+'/cdn-cgi/access/certs',{redirect:'error',signal:AbortSignal.timeout(3000)});
  if (!response.ok) throw new Error('Access keys unavailable');
  const raw=await response.text();
  if (raw.length>65536) throw new Error('Access key response exceeds bound');
  const value=JSON.parse(raw);
  if (!Array.isArray(value.keys)||!value.keys.length||value.keys.length>16) throw new Error('Access keys invalid');
  keys.set(issuer,{keys:value.keys,expires:Date.now()+300000});
  return value.keys;
}

export async function authorize(request, env) {
  const config=configuration(env);
  const url=new URL(request.url);
  if (url.protocol!=='https:' || !config.hosts.some(host=>host===url.hostname||(host.startsWith('*.')&&url.hostname.endsWith(host.slice(1))&&url.hostname!==host.slice(2)))) return false;
  const cookie=(request.headers.get('cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('CF_Authorization='));
  const token=request.headers.get('cf-access-jwt-assertion') || cookie?.slice('CF_Authorization='.length) || '';
  if (token.length>8192) return false;
  const parts=token.split('.');
  if (parts.length!==3) return false;
  const header=JSON.parse(new TextDecoder().decode(decode(parts[0])));
  const claims=JSON.parse(new TextDecoder().decode(decode(parts[1])));
  const now=Math.floor(Date.now()/1000);
  if (header.alg!=='RS256'||typeof header.kid!=='string'||header.kid.length>128||claims.iss!==config.issuer||!Array.isArray(claims.aud)||!claims.aud.some(x=>config.audiences.includes(x))||!Number.isInteger(claims.exp)||claims.exp<=now||!Number.isInteger(claims.iat)||claims.iat>now+30||claims.nbf!==undefined&&(!Number.isInteger(claims.nbf)||claims.nbf>now+30)||typeof claims.sub!=='string'||!claims.sub||typeof claims.email!=='string'||!config.emails.includes(claims.email.toLowerCase())) return false;
  const jwks=await publicKeys(config.issuer,header.kid);
  const jwk=jwks.find(x=>x.kid===header.kid&&x.kty==='RSA'&&(!x.alg||x.alg==='RS256')&&(!x.use||x.use==='sig'));
  if (!jwk) return false;
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  return crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));
}

export default {
  async fetch(request,env) {
    let response;
    try {
      if (!['GET','HEAD'].includes(request.method)) response=new Response('Method unavailable.',{status:405});
      else if (!await authorize(request,env)) {
        console.warn(JSON.stringify({event:'engineering_access_denied',reason:'Identity, claims or signature rejected'}));
        response=denied();
      }
      else response=await env.ASSETS.fetch(request);
    } catch(error) {
      // Publish only fixed diagnostic categories; never token, cookie, URL or identity data.
      console.warn(JSON.stringify({event:'engineering_access_denied',reason:denialReason(error)}));
      response=denied();
    }
    const headers=new Headers(response.headers);
    headers.set('cache-control','private, no-store');
    headers.set('x-robots-tag','noindex, nofollow, noarchive');
    headers.set('x-content-type-options','nosniff');
    headers.set('referrer-policy','no-referrer');
    return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
  }
};
