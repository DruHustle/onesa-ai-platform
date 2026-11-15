/**
 * Pure conversation-selection and draft transitions for the native client.
 * Drafts remain in memory and are scoped to the current signed-in account.
 */

export function draftFor(drafts, conversationId) {
  return drafts.get(conversationId) ?? '';
}

export function withDraft(drafts, conversationId, text) {
  const next = new Map(drafts);
  if (text) next.set(conversationId, text);
  else next.delete(conversationId);
  return next;
}

export function moveDraft(drafts, fromId, toId) {
  const next = new Map(drafts);
  if (next.has(fromId)) next.set(toId, next.get(fromId));
  next.delete(fromId);
  return next;
}

/**
 * Only clear the exact text submitted. If the user edited the input while the
 * request was in flight, preserve the newer draft for the next message.
 */
export function clearSubmittedDraft(drafts, conversationId, submittedText) {
  if (!drafts.has(conversationId) || drafts.get(conversationId) !== submittedText) {
    return drafts;
  }
  const next = new Map(drafts);
  next.delete(conversationId);
  return next;
}

/**
 * Do not change the selected conversation until its detail request succeeds.
 * A failed attempt to open another conversation must leave the current target
 * and visible detail aligned.
 */
export async function openConversation(conversationId, loadDetail, select) {
  const detail = await loadDetail(conversationId);
  select(conversationId, detail);
  return detail;
}
