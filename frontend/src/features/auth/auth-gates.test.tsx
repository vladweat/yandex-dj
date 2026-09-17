import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { AuthGate } from "@/features/auth/auth-gate";
import { GuestGate } from "@/features/auth/guest-gate";
import { postLoginPath } from "@/features/auth/auth-paths";

const replace = vi.fn();
let authState = {
  isAuthenticated: false,
  loading: false,
};
let pathname = "/";
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => pathname,
  useSearchParams: () => searchParams,
}));

vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => authState,
}));

afterEach(() => {
  cleanup();
  replace.mockClear();
  authState = { isAuthenticated: false, loading: false };
  pathname = "/";
  searchParams = new URLSearchParams();
});

describe("postLoginPath", () => {
  it("allows same-origin relative paths", () => {
    expect(postLoginPath("/health")).toBe("/health");
  });

  it("rejects open redirects and login loops", () => {
    expect(postLoginPath(null)).toBe("/");
    expect(postLoginPath("//evil.example")).toBe("/");
    expect(postLoginPath("/login")).toBe("/");
    expect(postLoginPath("https://evil.example")).toBe("/");
  });
});

describe("AuthGate", () => {
  it("shows loading while auth boots", () => {
    authState = { isAuthenticated: false, loading: true };
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("Загрузка…")).toBeTruthy();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("redirects guests to /login with next", () => {
    authState = { isAuthenticated: false, loading: false };
    pathname = "/health";
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("Перенаправление на вход…")).toBeTruthy();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fhealth");
  });

  it("preserves query string in next (e.g. ?prompt=)", () => {
    authState = { isAuthenticated: false, loading: false };
    pathname = "/";
    searchParams = new URLSearchParams("prompt=night+drive");
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(replace).toHaveBeenCalledWith("/login?next=%2F%3Fprompt%3Dnight%2Bdrive");
  });

  it("renders children for authenticated users", () => {
    authState = { isAuthenticated: true, loading: false };
    render(
      <AuthGate>
        <div>secret</div>
      </AuthGate>,
    );
    expect(screen.getByText("secret")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("GuestGate", () => {
  it("keeps the login page for guests", () => {
    authState = { isAuthenticated: false, loading: false };
    render(
      <GuestGate>
        <div>login form</div>
      </GuestGate>,
    );
    expect(screen.getByText("login form")).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects authenticated users to next path", () => {
    authState = { isAuthenticated: true, loading: false };
    searchParams = new URLSearchParams("next=/debug");
    render(
      <GuestGate>
        <div>login form</div>
      </GuestGate>,
    );
    expect(screen.getByText("Перенаправление…")).toBeTruthy();
    expect(replace).toHaveBeenCalledWith("/debug");
  });

  it("redirects authenticated users to next with prompt query", () => {
    authState = { isAuthenticated: true, loading: false };
    searchParams = new URLSearchParams("next=/?prompt=night%20drive");
    render(
      <GuestGate>
        <div>login form</div>
      </GuestGate>,
    );
    expect(replace).toHaveBeenCalledWith("/?prompt=night drive");
  });
});

describe("postLoginPath with query", () => {
  it("keeps prompt deep link", () => {
    expect(postLoginPath("/?prompt=kitchen")).toBe("/?prompt=kitchen");
  });
});
