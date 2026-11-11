/** Flatten account tree for pickers and opening balance tables. */

export function flattenAccounts(nodes, depth = 0) {
  const out = [];
  for (const node of nodes || []) {
    out.push({ ...node, depth });
    if (node.children?.length) {
      out.push(...flattenAccounts(node.children, depth + 1));
    }
  }
  return out;
}

export function leafAccounts(nodes) {
  return flattenAccounts(nodes).filter((a) => a.is_leaf);
}

export function findAccount(nodes, code) {
  for (const node of nodes || []) {
    if (node.code === code) return node;
    const found = findAccount(node.children, code);
    if (found) return found;
  }
  return null;
}
