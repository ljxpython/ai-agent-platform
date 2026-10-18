/**
 * Global Web Crypto polyfill for insecure contexts (e.g. non-HTTPS IP access).
 *
 * In modern browsers, `crypto.randomUUID` is restricted to Secure Contexts
 * (HTTPS or localhost). In plain HTTP access (such as public IP addresses),
 * `crypto.randomUUID` is undefined. This polyfill provides standard RFC 4122 v4
 * UUID generation using `crypto.getRandomValues` when available, falling back
 * to pseudo-random numbers.
 */
export function installCryptoRandomUUIDPolyfill(): void {
  if (typeof window === "undefined") return;

  const cryptoObj =
    window.crypto || (window as unknown as { msCrypto?: Crypto }).msCrypto;

  if (!cryptoObj) {
    try {
      (window as unknown as { crypto: Partial<Crypto> }).crypto = {};
    } catch {
      // Ignore if window.crypto is non-writable
    }
  }

  const targetCrypto = window.crypto;
  if (targetCrypto && typeof targetCrypto.randomUUID !== "function") {
    try {
      Object.defineProperty(targetCrypto, "randomUUID", {
        value:
          function randomUUID(): `${string}-${string}-${string}-${string}-${string}` {
            if (typeof targetCrypto.getRandomValues === "function") {
              const bytes = new Uint8Array(16);
              targetCrypto.getRandomValues(bytes);
              bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
              bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 10xx
              const hex: string[] = [];
              for (let i = 0; i < 16; i++) {
                hex.push(bytes[i].toString(16).padStart(2, "0"));
              }
              return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}` as `${string}-${string}-${string}-${string}-${string}`;
            }

            return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
              /[xy]/g,
              (c) => {
                const r = (Math.random() * 16) | 0;
                const v = c === "x" ? r : (r & 0x3) | 0x8;
                return v.toString(16);
              },
            ) as `${string}-${string}-${string}-${string}-${string}`;
          },
        configurable: true,
        writable: true,
      });
    } catch {
      (targetCrypto as unknown as Record<string, unknown>).randomUUID =
        function randomUUID(): `${string}-${string}-${string}-${string}-${string}` {
          return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
            /[xy]/g,
            (c) => {
              const r = (Math.random() * 16) | 0;
              const v = c === "x" ? r : (r & 0x3) | 0x8;
              return v.toString(16);
            },
          ) as `${string}-${string}-${string}-${string}-${string}`;
        };
    }
  }
}

// Automatically install on module import
installCryptoRandomUUIDPolyfill();
