import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Metric } from "./Metric";

describe("Metric", () => {
  it("renders provenance badge", () => {
    render(<Metric label="Runs" value={3} provenance="measured" />);
    expect(screen.getByText("Measured")).toBeTruthy();
  });
});
