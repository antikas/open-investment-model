#!/usr/bin/env node

import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const mcpDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repoDir = resolve(mcpDir, '..');
const modelDir = resolve(repoDir, 'model');
const exportsDir = resolve(repoDir, 'exports');
const identity = JSON.parse(readFileSync(resolve(repoDir, 'metadata/openim.json'), 'utf8'));
const releaseTag = `v${identity.version}`;
const repository = identity.sourceRepository;

function posix(path) {
  return path.split(sep).join('/');
}

function walk(dir, predicate = () => true) {
  const found = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) found.push(...walk(path, predicate));
    else if (predicate(path)) found.push(path);
  }
  return found.sort();
}

function sourceUrl(path) {
  const rel = posix(relative(repoDir, path));
  return `${repository}/blob/${releaseTag}/${rel}`;
}

function cleanInline(text) {
  return text
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
    .replace(/[`*_>#]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function firstParagraph(markdown, afterHeading = true) {
  let text = markdown;
  if (afterHeading) text = text.replace(/^# .+\r?\n/, '');
  for (const block of text.split(/\r?\n\s*\r?\n/)) {
    const clean = cleanInline(block);
    if (clean && !clean.startsWith('|') && !clean.startsWith('---')) return clean;
  }
  return '';
}

function section(markdown, heading) {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return markdown.match(new RegExp(`^## ${escaped}\\s*$([\\s\\S]*?)(?=^## |\\Z)`, 'm'))?.[1]?.trim() ?? '';
}

function heading(markdown) {
  const line = markdown.match(/^#\s+(.+)$/m)?.[1] ?? '';
  const match = line.match(/^([A-Z]{1,3}-\d+(?:\.\d+)?)\s+[—-]\s+(.+)$/);
  return match ? { id: match[1], title: cleanInline(match[2]) } : { id: '', title: cleanInline(line) };
}

function websiteUrlFor(path, kind) {
  const rel = posix(relative(modelDir, path));
  if (kind === 'business-domain') {
    return `${identity.officialUrl}model/${rel.split('/')[1].toLowerCase()}/`;
  }
  if (kind === 'service-domain') {
    const parts = rel.split('/');
    return `${identity.officialUrl}model/${parts[1].toLowerCase()}/${parts[2].replace(/\.md$/, '').toLowerCase()}/`;
  }
  if (kind === 'entity') {
    return `${identity.officialUrl}model/entities/${path.split(sep).at(-1).replace(/\.md$/, '').toLowerCase()}/`;
  }
  return sourceUrl(path);
}

const items = [];

function addMarkdownItem(path, type) {
  const markdown = readFileSync(path, 'utf8');
  const parsed = heading(markdown);
  const purpose = section(markdown, 'Purpose');
  const description = firstParagraph(purpose || markdown, !purpose);
  items.push({
    id: parsed.id,
    type,
    title: parsed.title,
    description,
    content: cleanInline(markdown),
    sourcePath: posix(relative(repoDir, path)),
    sourceUrl: sourceUrl(path),
    officialUrl: websiteUrlFor(path, type),
  });
  return { markdown, parsed };
}

const businessFiles = walk(resolve(modelDir, 'service-domains'), (path) => path.endsWith(`${sep}README.md`));
for (const path of businessFiles) addMarkdownItem(path, 'business-domain');

const serviceFiles = walk(resolve(modelDir, 'service-domains'), (path) => /[\\/]SD-\d+\.\d+-.+\.md$/.test(path));
for (const path of serviceFiles) {
  const { markdown, parsed } = addMarkdownItem(path, 'service-domain');
  const operations = section(markdown, 'Service Operations');
  let operationNumber = 0;
  for (const match of operations.matchAll(/^-\s+\*\*([^*]+)\*\*\s+[—-]\s+(.+)$/gm)) {
    operationNumber += 1;
    const operationSlug = match[1]
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '');
    const parent = items.at(-1);
    items.push({
      id: `${parsed.id}:op-${operationNumber}`,
      type: 'service-operation',
      title: cleanInline(match[1]),
      description: cleanInline(match[2]),
      content: `${cleanInline(match[1])} ${cleanInline(match[2])} ${parsed.title}`,
      parentId: parsed.id,
      sourcePath: parent.sourcePath,
      sourceUrl: `${parent.sourceUrl}#service-operations`,
      officialUrl: `${parent.officialUrl}#${operationSlug}`,
    });
  }
}

const entityFiles = walk(resolve(modelDir, 'entities'), (path) => /[\\/](?:E|PB|FO|PM|DR|RA)-\d+-.+\.md$/.test(path));
for (const path of entityFiles) addMarkdownItem(path, 'entity');

const glossaryPath = resolve(modelDir, 'glossary.md');
const glossary = readFileSync(glossaryPath, 'utf8');
for (const match of glossary.matchAll(/^\*\*([^*]+)\*\*\s+[—-]\s+(.+)$/gm)) {
  const term = cleanInline(match[1]);
  const slug = term.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  items.push({
    id: `glossary:${slug}`,
    type: 'glossary-term',
    title: term,
    description: cleanInline(match[2]),
    content: `${term} ${cleanInline(match[2])}`,
    sourcePath: 'model/glossary.md',
    sourceUrl: `${sourceUrl(glossaryPath)}#${slug}`,
    officialUrl: `${sourceUrl(glossaryPath)}#${slug}`,
  });
}

const relationsPath = resolve(modelDir, 'relations.md');
const relations = readFileSync(relationsPath, 'utf8');
for (const match of relations.matchAll(/^####\s+`([^`]+)`\s+[—-]\s+`([^`]+)`\s*$([\s\S]*?)(?=^#### |^### |\Z)/gm)) {
  const meaning = match[3].match(/^-\s+\*\*Meaning:\*\*\s+(.+)$/m)?.[1] ?? '';
  items.push({
    id: `relation:${match[1]}`,
    type: 'relationship',
    title: match[1],
    description: cleanInline(meaning || `${match[1]} (${match[2]})`),
    content: cleanInline(match[0]),
    sourcePath: 'model/relations.md',
    sourceUrl: `${sourceUrl(relationsPath)}#${match[2]}`,
    officialUrl: `${sourceUrl(relationsPath)}#${match[2]}`,
  });
}

const exportExtensions = new Set(['.archimate', '.bpmn', '.csv', '.cypher', '.gql', '.json', '.md', '.rdf', '.sql', '.svg', '.ttl']);
for (const path of walk(exportsDir, (path) => exportExtensions.has(extname(path).toLowerCase()))) {
  const rel = posix(relative(exportsDir, path));
  items.push({
    id: `export:${rel}`,
    type: 'export',
    title: rel,
    description: `Released OpenIM ${extname(path).slice(1).toUpperCase()} model artefact.`,
    content: rel,
    sourcePath: `exports/${rel}`,
    sourceUrl: `${repository}/raw/${releaseTag}/exports/${rel}`,
    officialUrl: `${identity.officialUrl}exports/${rel}`,
  });
}

items.sort((a, b) => a.id.localeCompare(b.id));
const duplicateIds = items.map((item) => item.id).filter((id, index, all) => all.indexOf(id) !== index);
if (duplicateIds.length) throw new Error(`Duplicate catalogue identifiers: ${[...new Set(duplicateIds)].join(', ')}`);

const counts = Object.fromEntries(
  [...new Set(items.map((item) => item.type))].sort().map((type) => [type, items.filter((item) => item.type === type).length]),
);
const catalog = {
  schemaVersion: '1.0',
  generatedFrom: releaseTag,
  modelVersion: identity.version,
  identity,
  counts,
  items,
};

mkdirSync(resolve(mcpDir, 'dist'), { recursive: true });
writeFileSync(resolve(mcpDir, 'dist/model-index.json'), `${JSON.stringify(catalog)}\n`);
console.log(`OpenIM catalogue ${identity.version}: ${items.length} records (${JSON.stringify(counts)})`);
