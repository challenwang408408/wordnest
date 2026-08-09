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
