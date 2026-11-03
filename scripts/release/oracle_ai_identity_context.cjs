// Private owner-probe configuration; this file grants no release authority.
const fs = require('node:fs'), crypto = require('node:crypto');
const uuid = /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const actors = ['primary', 'foreign'];
function need(value) { if (!value) throw Error('AI_IDENTITY_CONTEXT_REFUSED'); }
function validateIdentity(identity, actor = 'primary') {
  need(identity?.profile === 'shared-identity-v1' && actors.includes(actor));
  need(['staging', 'production'].includes(identity.environment));
  const app = new URL(identity.origin), issuer = new URL(identity.issuer);
  need(app.protocol === 'https:' && app.origin === identity.origin && !app.port);
  need(identity.environment === 'production' ? app.hostname === 'platform.onesa.eu'
    : /^onesa-ai-platform-git-staging-[a-z0-9-]+\.vercel\.app$/.test(app.hostname));
  need(issuer.protocol === 'https:' && !issuer.username && !issuer.password && !issuer.port && !issuer.search && !issuer.hash && issuer.pathname === '/api/v1/identity');
  need(identity.environment === 'production' ? issuer.hostname === 'portal.onesa.eu'
    : issuer.hostname === 'portal-staging.onesa.eu' || /^onesa-company-portal-[a-z0-9-]+\.vercel\.app$/.test(issuer.hostname));
  need(/^[A-Za-z0-9_-]{16,128}$/.test(identity.client_id));
  need(/^[a-f0-9]{40}$/.test(identity.candidate_commit) && uuid.test(identity.operation_id));
  need(Number.isFinite(Date.parse(identity.expires_at)) && Date.now() < Date.parse(identity.expires_at) && Date.parse(identity.expires_at) <= Date.now() + 3600000);
  need(Object.keys(identity.accounts || {}).sort().join(',') === 'foreign,primary');
  for (const value of Object.values(identity.accounts)) {
    need(uuid.test(value.subject) && uuid.test(value.local_user_id));
    need(typeof value.email === 'string' && /^[^\s@]{1,64}@[^\s@]{1,189}$/.test(value.email) && value.email === value.email.toLowerCase());
    need(['password', 'local_password'].every(key => typeof value[key] === 'string' && value[key].length >= 12 && value[key].length <= (key === 'local_password' ? 128 : 256)));
    need(/^[A-Z2-7]{16,128}$/.test(value.totp_secret));
  }
  for (const key of ['subject', 'local_user_id', 'email']) need(identity.accounts.primary[key] !== identity.accounts.foreign[key]);
  need(typeof identity.portal_bypass === 'string' && identity.portal_bypass.length <= 2048 && !/[\x00-\x20\x7f]/.test(identity.portal_bypass));
  need(identity.environment !== 'production' || identity.portal_bypass === '');
  return {app: app.origin, portal: issuer.origin, account: identity.accounts[actor]};
}
function validateUsers(identity, users) {
  validateIdentity(identity);
  need(Array.isArray(users) && users.length === 2);
  users.forEach((user, index) => {
    const account = identity.accounts[actors[index]];
    need(user.id === account.local_user_id && user.email === account.email && user.password === account.password);
  });
  return users;
}
function validateContext(context, users = context.users) {
  const identity = context.identity;
  validateUsers(identity, users);
  need(identity.candidate_commit === (context.binding?.candidate_commit || context.candidate_commit));
  need(identity.operation_id === (context.operation_id || context.qualification_id));
  need(identity.origin === (context.origin || context.frontend_origin));
  need(identity.environment === (context.environment || 'staging'));
  return identity;
}
function journalSession(identity, cookie, csrf) {
  validateIdentity(identity);
  const file = identity.session_journal, info = fs.lstatSync(file);
  need(file === '/private/output/identity-sessions.jsonl' && info.isFile() && !info.isSymbolicLink() && info.uid === process.getuid() && (info.mode & 0o077) === 0 && info.nlink === 1 && info.size < 65536);
  const row = {operation_id: identity.operation_id,
    token_sha256: crypto.createHash('sha256').update(cookie.value).digest('hex'),
    csrf_sha256: crypto.createHash('sha256').update(csrf).digest('hex')};
  const fd = fs.openSync(file, fs.constants.O_WRONLY | fs.constants.O_APPEND | fs.constants.O_NOFOLLOW);
  try { need(fs.fstatSync(fd).ino === info.ino); fs.writeSync(fd, JSON.stringify(row) + '\n'); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
}
module.exports = {validateIdentity, validateUsers, validateContext, journalSession};
