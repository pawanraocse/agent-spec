import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Knowledge } from "./Knowledge";
import { fixtureFetch } from "../test/fixtures";

function mount() {
  const posts: { path: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      posts.push({ path: String(input), body });
      const reply = body.action === "prune" && !body.apply
        ? { ok: true, preview: true, older_than: body.older_than, facts: [{ fact_id: "f1", type: "gotcha", subject: "old gotcha" }] }
        : { ok: true, result: "forgot it" };
      return Promise.resolve(new Response(JSON.stringify(reply), { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    return fixtureFetch(input);
  }));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { posts, ...render(<QueryClientProvider client={qc}><Knowledge /></QueryClientProvider>) };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Memory controls", () => {
  it("shows fact text, hides retired facts until asked, and flags the index over its limit", async () => {
    const { findByText, queryByText, getByLabelText, getByRole } = mount();
    await findByText(/stale copy of skills/);
    expect(queryByText("graphify misreads this repo")).toBeNull();
    fireEvent.click(getByLabelText(/show retired/));
    await findByText("graphify misreads this repo");
    expect(getByRole("meter", { name: "Memory index size" }).getAttribute("aria-valuenow")).toBe("100");
  });

  it("forget asks once more before it posts", async () => {
    const { findByText, getByRole, posts } = mount();
    await findByText(/stale copy of skills/);
    fireEvent.click(getByRole("button", { name: "Forget .agents is a stale copy" }));
    expect(posts).toEqual([]);
    fireEvent.click(getByRole("button", { name: "Forget?" }));
    await waitFor(() => expect(posts[0]?.body).toEqual({ action: "forget", id: "20261113-agents-is-a-stale-copy-89bdca" }));
    await findByText("forgot it");
  });

  it("prune previews before it can delete", async () => {
    const { findByText, getByRole, posts } = mount();
    await findByText(/stale copy of skills/);
    fireEvent.click(getByRole("button", { name: "Preview" }));
    await findByText("old gotcha");
    expect(posts[0].body).toEqual({ action: "prune", older_than: 90 });
    fireEvent.click(getByRole("button", { name: /Delete .* facts/ }));
    await waitFor(() => expect(posts[1]?.body).toEqual({ action: "prune", older_than: 90, apply: true }));
  });

  it("edit sends a new version of the fact", async () => {
    const { findByText, getByRole, getByLabelText, posts } = mount();
    await findByText(/stale copy of skills/);
    fireEvent.click(getByRole("button", { name: "Edit .agents is a stale copy" }));
    fireEvent.change(getByLabelText("Subject"), { target: { value: ".agents is retired" } });
    fireEvent.click(getByRole("button", { name: /Save new version/ }));
    await waitFor(() => expect(posts[0]?.body).toMatchObject({ action: "edit", id: "20261113-agents-is-a-stale-copy-89bdca", subject: ".agents is retired", type: "gotcha" }));
  });
});
