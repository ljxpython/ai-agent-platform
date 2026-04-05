export function isJwtToken(token: string | null | undefined): token is string {
  if (!token) {
    return false;
  }
  return token.split(".").length === 3;
}
