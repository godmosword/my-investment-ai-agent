import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  PAPER_RECONCILE_CLOSED_LIMIT,
  PAPER_RECONCILE_INTENT_LIMIT,
  fetchWindowMayBeTruncated,
  reconcileSymbol,
} from "./paperReconcile.js";

describe("reconcileSymbol honesty", () => {
  it("true empty window is none", () => {
    const r = reconcileSymbol("AAPL", {
      lifecycleRows: [],
      intentRows: [],
      closedRecords: [],
      windowMayBeTruncated: false,
    });
    assert.equal(r.kind, "none");
    assert.equal(r.label, "無紙上記錄");
  });

  it("empty match with truncated window is truncated UNKNOWN", () => {
    const r = reconcileSymbol("AMD", {
      lifecycleRows: [],
      intentRows: [],
      closedRecords: [],
      windowMayBeTruncated: true,
    });
    assert.equal(r.kind, "truncated");
    assert.equal(r.label, "UNKNOWN");
  });

  it("unrecognized status is unknown, not none", () => {
    const r = reconcileSymbol("META", {
      lifecycleRows: [{ asset: "META", status: "WEIRD_STATE" }],
      intentRows: [],
      closedRecords: [],
    });
    assert.equal(r.kind, "unknown");
    assert.equal(r.label, "UNKNOWN");
  });

  it("known non-paper intent statuses stay none", () => {
    for (const status of ["PENDING_REVIEW", "REJECTED", "SUPERSEDED"]) {
      const r = reconcileSymbol("AAPL", {
        lifecycleRows: [],
        intentRows: [{ asset: "AAPL", status }],
        closedRecords: [],
      });
      assert.equal(r.kind, "none", status);
      assert.equal(r.label, "無紙上記錄", status);
    }
  });

  it("mixed unrecognized + non-paper is unknown", () => {
    const r = reconcileSymbol("META", {
      lifecycleRows: [{ asset: "META", status: "WEIRD_STATE" }],
      intentRows: [{ asset: "META", status: "PENDING_REVIEW" }],
      closedRecords: [],
    });
    assert.equal(r.kind, "unknown");
    assert.equal(r.label, "UNKNOWN");
  });

  it("missing status is unknown", () => {
    const r = reconcileSymbol("META", {
      lifecycleRows: [{ asset: "META" }],
      intentRows: [],
      closedRecords: [],
    });
    assert.equal(r.kind, "unknown");
    assert.equal(r.label, "UNKNOWN");
  });

  it("open / closed / finite 0 still work", () => {
    assert.equal(
      reconcileSymbol("NVDA", {
        lifecycleRows: [{ asset: "NVDA", status: "APPROVED_FOR_PAPER" }],
        intentRows: [],
        closedRecords: [],
      }).kind,
      "open",
    );
    const closed = reconcileSymbol("BTC", {
      lifecycleRows: [],
      intentRows: [],
      closedRecords: [{ asset: "BTC", status: "PAPER_CLOSED", return_pct: 0 }],
    });
    assert.equal(closed.kind, "closed");
    assert.equal(closed.returnValue, 0);
  });
});

describe("fetchWindowMayBeTruncated", () => {
  it("detects full intent / closed pages", () => {
    assert.equal(
      fetchWindowMayBeTruncated({
        intentRows: Array.from({ length: PAPER_RECONCILE_INTENT_LIMIT }, (_, i) => ({
          asset: `X${i}`,
        })),
        closedRecords: [],
        lifecycleRows: [],
      }),
      true,
    );
    assert.equal(
      fetchWindowMayBeTruncated({
        intentRows: [],
        closedRecords: Array.from({ length: PAPER_RECONCILE_CLOSED_LIMIT }, (_, i) => ({
          asset: `C${i}`,
        })),
        lifecycleRows: [],
      }),
      true,
    );
    assert.equal(
      fetchWindowMayBeTruncated({
        intentRows: [{ asset: "A" }],
        closedRecords: [{ asset: "B" }],
        lifecycleRows: [{ asset: "C" }],
      }),
      false,
    );
  });
});
