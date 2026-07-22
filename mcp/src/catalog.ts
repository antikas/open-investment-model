import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ITEM_TYPES = [
  'business-domain',
  'service-domain',
  'service-operation',
  'entity',
  'relationship',
  'glossary-term',
  'export',
] as const;

export type ItemType = (typeof ITEM_TYPES)[number];

export interface OpenImIdentity {
  id: string;
  name: string;
  alternateName: string;
  description: string;
  version: string;
  datePublished: string;
  officialUrl: string;
  sourceRepository: string;
  license: string;
  maturity: string;
  keywords: string[];
  alignsWith: string[];
}

export interface CatalogItem {
  id: string;
  type: ItemType;
  title: string;
  description: string;
  content: string;
  parentId?: string;
  sourcePath: string;
  sourceUrl: string;
  officialUrl: string;
}

export interface Catalog {
  schemaVersion: string;
  generatedFrom: string;
  modelVersion: string;
  identity: OpenImIdentity;
  counts: Record<string, number>;
  items: CatalogItem[];
}

export interface SearchResult extends Omit<CatalogItem, 'content'> {
  score: number;
  modelVersion: string;
}

const moduleDir = dirname(fileURLToPath(import.meta.url));

export function loadCatalog(path = resolve(moduleDir, 'model-index.json')): Catalog {
  return JSON.parse(readFileSync(path, 'utf8')) as Catalog;
}

function fold(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function tokens(value: string): string[] {
  return [...new Set(fold(value).match(/[a-z0-9]+(?:\.[0-9]+)?/g) ?? [])].filter((token) => token.length > 1);
}

function scoreItem(item: CatalogItem, query: string): number {
  const q = fold(query).trim();
  const queryTokens = tokens(q);
  if (!queryTokens.length) return 0;

  const id = fold(item.id);
  const title = fold(item.title);
  const description = fold(item.description);
  const content = fold(item.content);
  let score = 0;

  if (id === q) score += 100;
  if (title === q) score += 80;
  if (title.includes(q)) score += 35;
  if (description.includes(q)) score += 18;
  if (content.includes(q)) score += 8;

  for (const token of queryTokens) {
    if (id.includes(token)) score += 14;
    if (title.includes(token)) score += 10;
    if (description.includes(token)) score += 5;
    if (content.includes(token)) score += 1;
  }

  return score;
}

export function searchCatalog(
  catalog: Catalog,
  query: string,
  types?: ItemType[],
  limit = 10,
): SearchResult[] {
  const allowed = types?.length ? new Set(types) : null;
  return catalog.items
    .filter((item) => !allowed || allowed.has(item.type))
    .map((item) => ({ item, score: scoreItem(item, query) }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.item.id.localeCompare(b.item.id))
    .slice(0, Math.max(1, Math.min(limit, 20)))
    .map(({ item, score }) => ({
      id: item.id,
      type: item.type,
      title: item.title,
      description: item.description,
      parentId: item.parentId,
      sourcePath: item.sourcePath,
      sourceUrl: item.sourceUrl,
      officialUrl: item.officialUrl,
      score,
      modelVersion: catalog.modelVersion,
    }));
}

export function getCatalogItem(catalog: Catalog, id: string): CatalogItem | undefined {
  const wanted = fold(id);
  return catalog.items.find((item) => fold(item.id) === wanted);
}
