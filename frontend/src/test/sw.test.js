import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cwd } from "node:process";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

describe("WordNest service worker cache cleanup", () => {
  it("deletes only stale WordNest caches and preserves sibling app caches", async () => {
    const source = readFileSync(resolve(cwd(), "public/sw.js"), "utf8");
    const listeners = {};
    const deleteCache = vi.fn(() => Promise.resolve(true));
    const cacheStorage = {
      keys: vi.fn(() =>
        Promise.resolve([
          "wordnest-shell-v1",
          "wordnest-shell-v2",
          "wordnest-shell-v3",
          "another-project-shell-v7",
        ]),
      ),
      delete: deleteCache,
    };
    const serviceWorker = {
      addEventListener: (type, listener) => {
        listeners[type] = listener;
      },
      clients: { claim: vi.fn(() => Promise.resolve()) },
    };

    runInNewContext(source, {
      URL,
      Promise,
      caches: cacheStorage,
      self: serviceWorker,
    });

    let activation;
    listeners.activate({ waitUntil: (promise) => { activation = promise; } });
    await activation;

    expect(deleteCache).toHaveBeenCalledTimes(3);
    expect(deleteCache).toHaveBeenCalledWith("wordnest-shell-v1");
    expect(deleteCache).toHaveBeenCalledWith("wordnest-shell-v2");
    expect(deleteCache).toHaveBeenCalledWith("wordnest-shell-v3");
    expect(deleteCache).not.toHaveBeenCalledWith("another-project-shell-v7");
  });
});
