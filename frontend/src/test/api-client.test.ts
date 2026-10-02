import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("voice upload", () => {
  it("materializes the recorded blob and uploads the same raw audio bytes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({
        words: ["apple"],
        text: "apple",
        request_id: "req-audio",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const rawAudio = new TextEncoder().encode("recorded-audio");
    const audio = {
      type: "audio/mp4",
      size: rawAudio.byteLength,
      arrayBuffer: vi.fn().mockResolvedValue(rawAudio.buffer),
    } as unknown as File;

    await api.transcribeVoice(1, audio);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.headers).toMatchObject({ "Content-Type": "audio/mp4" });
    expect(init.body).toBe(rawAudio.buffer);
    expect((init.body as ArrayBuffer).byteLength).toBe(audio.size);
  });
});

describe("API session expiry signal", () => {
  it("announces a protected 401 so the app can return to login", async () => {
    const onExpired = vi.fn();
    window.addEventListener("wordnest:auth-expired", onExpired, { once: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "登录已失效" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    )));

    await expect(api.startQuiz(1, { library_ids: [10] })).rejects.toMatchObject({
      status: 401,
      message: "登录已失效",
    });
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it("does not announce expiry for the login endpoint itself", async () => {
    const onExpired = vi.fn();
    window.addEventListener("wordnest:auth-expired", onExpired, { once: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "访问码不对" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    )));

    await expect(api.login("0000")).rejects.toMatchObject({
      status: 401,
      message: "访问码不对",
    });
    expect(onExpired).not.toHaveBeenCalled();
  });
});
