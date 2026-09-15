/** Safe post-login redirect target from `?next=`. */
export function postLoginPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) {
    return "/";
  }
  return next;
}
