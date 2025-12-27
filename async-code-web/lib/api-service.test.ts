import { describe, expect, it } from "vitest";
import { ApiService } from "./api-service";

describe("ApiService.parseGitHubUrl", () => {
    it("parses https GitHub URLs", () => {
        const result = ApiService.parseGitHubUrl("https://github.com/octocat/Hello-World");
        expect(result).toEqual({ owner: "octocat", repo: "Hello-World" });
    });

    it("parses https GitHub URLs with .git and trailing slash", () => {
        const result = ApiService.parseGitHubUrl("https://github.com/octocat/Hello-World.git/");
        expect(result).toEqual({ owner: "octocat", repo: "Hello-World" });
    });

    it("parses ssh GitHub URLs", () => {
        const result = ApiService.parseGitHubUrl("git@github.com:octocat/Hello-World.git");
        expect(result).toEqual({ owner: "octocat", repo: "Hello-World" });
    });

    it("throws on invalid URLs", () => {
        expect(() => ApiService.parseGitHubUrl("https://example.com/octocat/Hello-World")).toThrow();
    });
});
