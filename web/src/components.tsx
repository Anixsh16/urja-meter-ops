import { AlertTriangle, ArrowRight, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ApiError, get, type Meta, type NetworkNode, type NodePage } from './api';

export function Status({ value }: { value: string | null }) {
  const style = value === 'Installed' ? 'installed' : value === 'Faulty' ? 'faulty' : 'muted';
  return <span className={`status ${style}`}><span />{value ?? 'Unknown'}</span>;
}

export function Freshness({ meta }: { meta: Meta }) {
  return <span className="freshness" title={`Retrieved ${new Date(meta.fetched_at).toLocaleString()}`}><span className="live-dot" />Snapshot {new Date(meta.fetched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {meta.cache === 'hit' ? `${meta.age_seconds}s cached` : 'just retrieved'}</span>;
}

export function ErrorState({ error, retry }: { error: Error; retry: () => void }) {
  return <div className="error-state" role="alert"><AlertTriangle size={23} /><div><strong>We couldn’t load this data</strong><p>{error.message}</p>{error instanceof ApiError && error.requestId ? <small>Request {error.requestId}</small> : null}</div><button className="button secondary" onClick={retry}><RefreshCw size={15} />Retry</button></div>;
}

export function Loading({ label = 'Reading the portal…' }: { label?: string }) {
  return <div className="loading" role="status"><span className="spinner" />{label}</div>;
}

export function Warnings({ warnings }: { warnings: string[] }) {
  const unique = [...new Set(warnings)];
  return unique.length ? <details className="warnings"><summary><AlertTriangle size={14} />Source notes <span>{unique.length}</span></summary><ul>{unique.map(w => <li key={w}>{w}</li>)}</ul></details> : null;
}

export function TreeNode({ node, token, onFilter, depth = 0 }: { node: NetworkNode; token: string; onFilter: (node: NetworkNode) => void; depth?: number }) {
  const [expanded, setExpanded] = useState(false);
  const children = useQuery({ queryKey: ['children', token, node.id], queryFn: ({ signal }) => get<NodePage>(`/network/nodes?parent_id=${encodeURIComponent(node.id)}`, token, signal), enabled: expanded && node.child_count > 0 });
  return <div className="tree-node"><div className="tree-row"><button className="tree-toggle" aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.name}`} aria-expanded={expanded} onClick={() => setExpanded(!expanded)} disabled={!node.child_count}>{expanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}</button><span className={`node-symbol ${node.level === 'zone' ? 'root-node' : ''}`} /> <div className="node-name"><strong>{node.name}</strong><small>{node.level === 'dt' ? 'TRANSFORMER' : node.level.toUpperCase()} · {node.code}</small></div>{node.warnings.length ? <span className="node-warning" title={node.warnings.join(' ')}><AlertTriangle size={15} /><span className="sr-only">Source inconsistency</span></span> : null}<span className="node-count">{node.meter_count} meters</span><button className="text-button" onClick={() => onFilter(node)} aria-label={`View meters in ${node.name}`}><span>View meters</span><ArrowRight size={15} /></button></div>{expanded && depth < 7 ? <div className="tree-children">{node.aliases.length ? <p className="alias-note">Also named: {node.aliases.join(', ')}</p> : null}{children.isPending && node.child_count ? <Loading label="Loading branches…" /> : null}{children.error ? <ErrorState error={children.error} retry={() => void children.refetch()} /> : null}{children.data?.data.items.map(child => <TreeNode key={child.id} node={child} token={token} onFilter={onFilter} depth={depth + 1} />)}</div> : null}</div>;
}
