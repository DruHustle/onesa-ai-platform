// Hide closed source comments without enabling raw HTML or rewriting code examples.
// State-local failed-search bounds prevent repeated scans of unterminated input.
export default function sourceComments(md) {
  const blockWithoutClose = Symbol('comment block without close');
  const inlineWithoutClose = Symbol('comment inline without close');
  md.block.ruler.before('paragraph', 'source_comment', (state, startLine, endLine, silent) => {
    if (state.sCount[startLine] - state.blkIndent >= 4) return false;
    const start = state.bMarks[startLine] + state.tShift[startLine];
    if (!state.src.startsWith('<!--', start) || start >= (state[blockWithoutClose] ?? Infinity)) return false;
    const close = state.src.indexOf('-->', start + 4);
    if (close < 0) {
      state[blockWithoutClose] = start;
      return false;
    }
    let last = startLine;
    while (last < endLine && state.eMarks[last] < close + 3) last++;
    // Only a complete standalone block is consumed. Preserve text after a comment.
    if (last >= endLine || state.src.slice(close + 3, state.eMarks[last]).trim()) return false;
    if (!silent) state.line = last + 1;
    return true;
  }, {alt: ['paragraph', 'reference', 'blockquote']});
  md.inline.ruler.before('text', 'source_comment', (state) => {
    const start = state.pos;
    if (!state.src.startsWith('<!--', start) || start >= (state[inlineWithoutClose] ?? Infinity)) return false;
    const close = state.src.indexOf('-->', start + 4);
    if (close < 0 || close + 3 > state.posMax) {
      state[inlineWithoutClose] = start;
      return false;
    }
    state.pos = close + 3;
    return true;
  });
}
