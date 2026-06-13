/**
 * Unit proof of the normalised audit-record mapping + deterministic ordering — the gather's
 * pure half. Pins: the two source record types normalise correctly (the source is carried verbatim);
 * a non-audit value is rejected (never fabricated); the chain order is a total order, reproducible.
 */
import { describe, expect, it } from 'vitest';
import {
  normaliseAuditRecord,
  orderAuditRecords,
  compareAuditRecords,
  type NormalisedAuditRecord,
} from './audit-record.js';

const opClosed = {
  kind: 'operation-closed',
  operationId: 'op-attr-1',
  task: 'attribution',
  status: 'completed',
};

const navPub = {
  kind: 'nav-published',
  workflowId: 'nav-PF0003-1',
  fundId: 'PF-0003',
  navUsd: '1234.56',
  struckAt: '2026-06-01T10:00:00.000Z',
};

describe('normaliseAuditRecord', () => {
  it('normalises an operation-closed record (no own timestamp → occurredAt null, source verbatim)', () => {
    const n = normaliseAuditRecord(opClosed)!;
    expect(n.recordType).toBe('operation-closed');
    expect(n.operationId).toBe('op-attr-1');
    expect(n.occurredAt).toBeNull();
    expect(n.source).toEqual(opClosed);
    expect(n.auditKind).toBe('agentinvest-audit-record');
  });

  it('normalises a nav-published record (struckAt → occurredAt, source verbatim)', () => {
    const n = normaliseAuditRecord(navPub)!;
    expect(n.recordType).toBe('nav-published');
    expect(n.operationId).toBe('nav-PF0003-1');
    expect(n.occurredAt).toBe('2026-06-01T10:00:00.000Z');
    expect(n.source).toEqual(navPub);
  });

  it('REJECTS a non-audit value (null, not a fabricated record)', () => {
    expect(normaliseAuditRecord(null)).toBeNull();
    expect(normaliseAuditRecord({ kind: 'something-else' })).toBeNull();
    expect(normaliseAuditRecord({ kind: 'operation-closed' })).toBeNull(); // missing operationId
  });
});

describe('orderAuditRecords — deterministic chain order', () => {
  function n(occurredAt: string | null, operationId: string): NormalisedAuditRecord {
    return {
      auditKind: 'agentinvest-audit-record',
      recordType: occurredAt ? 'nav-published' : 'operation-closed',
      operationId,
      occurredAt,
      source: { operationId },
    };
  }

  it('orders by occurredAt (ascending; nulls last), then operationId — and is reproducible', () => {
    const input = [
      n(null, 'op-z'),
      n('2026-06-02T00:00:00Z', 'op-b'),
      n(null, 'op-a'),
      n('2026-06-01T00:00:00Z', 'op-c'),
    ];
    const ordered = orderAuditRecords(input).map((r) => r.operationId);
    // timestamped first (ascending), then null-occurredAt by operationId.
    expect(ordered).toEqual(['op-c', 'op-b', 'op-a', 'op-z']);
    // reproducible: re-sorting a shuffled copy yields the same order.
    const shuffled = [input[3], input[0], input[2], input[1]];
    expect(orderAuditRecords(shuffled).map((r) => r.operationId)).toEqual(ordered);
  });

  it('the comparator is a total order (no two distinct keys compare equal by accident)', () => {
    const a = n('2026-06-01T00:00:00Z', 'op-1');
    const b = n('2026-06-01T00:00:00Z', 'op-2');
    expect(compareAuditRecords(a, b)).toBeLessThan(0);
    expect(compareAuditRecords(b, a)).toBeGreaterThan(0);
    expect(compareAuditRecords(a, a)).toBe(0);
  });
});
