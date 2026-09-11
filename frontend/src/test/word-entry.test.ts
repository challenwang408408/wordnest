import { describe, expect, it } from "vitest";
import { mergeVoiceWords, parseSpellings } from "../features/words/AddWordPage";

describe("word and phrase entry", () => {
  it("keeps a phrase as one entry", () => {
    expect(parseSpellings("take off")).toEqual(["take off"]);
  });

  it("separates entries at explicit delimiters and preserves phrase spaces", () => {
    expect(parseSpellings("take off\r\napple, look after，ice cream; well-known；don't\tget up"))
      .toEqual(["take off", "apple", "look after", "ice cream", "well-known", "don't", "get up"]);
  });

  it("normalizes phrase whitespace and deduplicates without changing first spelling", () => {
    expect(parseSpellings("  Take   Off  ,take off\nTAKE\u00a0OFF; , \n"))
      .toEqual(["Take Off"]);
  });

  it("counts phrases as single entries toward the 20-entry limit", () => {
    const phrases = Array.from({ length: 21 }, (_, i) => `phrase ${i}`);
    expect(parseSpellings(phrases.join("\n"))).toEqual(phrases.slice(0, 20));
    expect(parseSpellings(" ,；\t\r\n ")).toEqual([]);
  });

  it("preserves typed phrases when appending voice results", () => {
    expect(mergeVoiceWords("take off, apple", ["apple", "look after"]))
      .toBe("take off, apple, look after");
  });
});
