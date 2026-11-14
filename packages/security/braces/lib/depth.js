'use strict';

// Keep recursive upstream walkers below the call-stack limit. Parent/prev links
// are intentionally excluded: the parsed AST uses these legitimate back-links.
const MAX_DEPTH = 64;
const fail = () => {
  const error = new RangeError('Brace nesting exceeds the supported limit of 64');
  error.code = 'ERR_BRACES_MAX_DEPTH';
  throw error;
};
const assertAst = ast => {
  const stack = [{node: ast, depth: 0}];
  const ancestors = new WeakSet();
  let visited = 0;
  while (stack.length) {
    const {node, depth, exit} = stack.pop();
    if (!node || typeof node !== 'object') throw new TypeError('Expected an AST node');
    if (exit) { ancestors.delete(node); continue; }
    if (depth > MAX_DEPTH + 2 || ancestors.has(node)) fail();
    if (++visited > 65536) {
      const error = new RangeError('Brace AST exceeds the supported node limit');
      error.code = 'ERR_BRACES_MAX_NODES';
      throw error;
    }
    ancestors.add(node);
    stack.push({node, exit: true});
    if (node.nodes) {
      if (!Array.isArray(node.nodes)) throw new TypeError('Expected AST nodes array');
      for (const child of node.nodes) stack.push({node: child, depth: depth + 1});
    }
  }
};
module.exports = {MAX_DEPTH, fail, assertAst};
