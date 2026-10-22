// Hide closed source comments without enabling raw HTML or rewriting code examples.
// Cache each next closing delimiter, including absent ones, on the parse state.
// A distant closer with trailing text must not cause overlapping suffix scans.
export default function sourceComments(md) {
  const blockClose = Symbol('next block comment close');
  const inlineClose = Symbol('next inline comment close');
  function closing(state, start, key) {
    const previous = state[key];
    if (previous && previous.start <= start && (previous.close < 0 || start + 4 <= previous.close)) return previous.close;
    const close = state.src.indexOf('-->', start + 4);
    state[key] = {start, close};
    return close;
  }
  md.block.ruler.before('paragraph', 'source_comment', (state, startLine, endLine, silent) => {
    if (state.sCount[startLine] - state.blkIndent >= 4) return false;
    const start = state.bMarks[startLine] + state.tShift[startLine];
    if (!state.src.startsWith('<!--', start)) return false;
    const close = closing(state, start, blockClose);
    if (close < 0) return false;
    // Binary search also bounds the line lookup when a later comment cannot be
    // consumed as a standalone block (for example, it has following prose).
    let last = startLine, upper = endLine;
    while (last < upper) {
      const middle = Math.floor((last + upper) / 2);
      if (state.eMarks[middle] < close + 3) last = middle + 1;
      else upper = middle;
    }
    // Only a complete standalone block is consumed. Preserve text after a comment.
    if (last >= endLine) return false;
    const location = state[blockClose];
    if (location.lineEnd !== state.eMarks[last]) {
      location.lineEnd = state.eMarks[last];
      location.onlySpaceAfter = !state.src.slice(close + 3, location.lineEnd).trim();
    }
    if (!location.onlySpaceAfter) return false;
    if (!silent) state.line = last + 1;
    return true;
  }, {alt: ['paragraph', 'reference', 'blockquote']});
  md.inline.ruler.before('text', 'source_comment', (state) => {
    const start = state.pos;
    if (!state.src.startsWith('<!--', start)) return false;
    const close = closing(state, start, inlineClose);
    if (close < 0 || close + 3 > state.posMax) return false;
    state.pos = close + 3;
    return true;
  });
}
