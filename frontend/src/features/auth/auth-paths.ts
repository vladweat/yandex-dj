/** Safe post-login redirect target from `?next=`. */
export function postLoginPath(next: string | null, fallback = "/"): string {
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.startsWith("/login") ||
    next.startsWith("/tg/login")
  ) {
    return fallback;
  }
  return next;
}
