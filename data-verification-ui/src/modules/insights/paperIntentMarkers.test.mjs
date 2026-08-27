import test from "node:test";
import assert from "node:assert/strict";
import { paperIntentMarkers, chartTimeFromEvidence } from "./paperIntentMarkers.js";

const paperNvda = {
  signal_id: "e2e-nvda-paper-1",
  asset: "NVDA",
  status: "APPROVED_FOR_PAPER",
  direction: "LONG",
  created_at: "2026-05-14T15:00:00Z",
  status_updated_at: "2026-05-14T15:00:00Z",
  entry_price: 999,
};

const spyPending = {
  signal_id: "e2e-spy-1",
  asset: "SPY",
  status: "PENDING_REVIEW",
  direction: "LONG",
  created_at: "2026-04-14T00:00:00Z",
};

const liveNvda = {
  signal_id: "live-nvda",
  asset: "NVDA",
  status: "LIVE_SUBMITTED",
  direction: "LONG",
  created_at: "2026-05-14T00:00:00Z",
};

test("matching PAPER row becomes one marker with evidence time", () => {
  const markers = paperIntentMarkers([paperNvda, spyPending], "nvda");
  assert.equal(markers.length, 1);
  assert.equal(markers[0].signal_id, "e2e-nvda-paper-1");
  assert.equal(markers[0].time, "2026-05-14");
  assert.equal(markers[0].direction, "LONG");
  assert.equal("entry_price" in markers[0], false);
});

test("other symbol and non-paper statuses are dropped", () => {
  const markers = paperIntentMarkers([paperNvda, spyPending, liveNvda], "NVDA");
  assert.equal(markers.length, 1);
  assert.equal(markers[0].signal_id, "e2e-nvda-paper-1");
});

test("empty / missing time / missing symbol yield no markers", () => {
  assert.deepEqual(paperIntentMarkers([], "NVDA"), []);
  assert.deepEqual(paperIntentMarkers(null, "NVDA"), []);
  assert.deepEqual(paperIntentMarkers([paperNvda], ""), []);
  const noTime = { ...paperNvda, created_at: null, status_updated_at: null };
  assert.deepEqual(paperIntentMarkers([noTime], "NVDA"), []);
});

test("chartTimeFromEvidence uses the event timestamp date only", () => {
  assert.equal(chartTimeFromEvidence("2026-05-14"), "2026-05-14");
  assert.equal(chartTimeFromEvidence("2026-05-14T15:00:00Z"), "2026-05-14");
  assert.equal(chartTimeFromEvidence(""), null);
});
