import { savePendingCheck, takePendingCheck } from "@/lib/pendingCheck";

describe("pending check handoff", () => {
  it("is read once", () => {
    savePendingCheck({ type: "text", value: "Boppy newborn lounger" });
    expect(takePendingCheck()).toEqual({ type: "text", value: "Boppy newborn lounger" });
    expect(takePendingCheck()).toBeNull();
  });

  it("ignores anything that isn't a check", () => {
    window.sessionStorage.setItem("recallradar:pending-check", '{"type":"vin","value":"x"}');
    expect(takePendingCheck()).toBeNull();
    window.sessionStorage.setItem("recallradar:pending-check", "not json");
    expect(takePendingCheck()).toBeNull();
  });
});
