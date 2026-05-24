/**
 * Centralized config. Reads NEXT_PUBLIC_* env vars at module load.
 * Throws loudly if anything required is missing.
 */
function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required env var: ${name}. Did you create frontend/.env.local?`
    );
  }
  return value;
}

export const config = {
  apiBaseUrl: required(
    "NEXT_PUBLIC_API_BASE_URL",
    process.env.NEXT_PUBLIC_API_BASE_URL
  ),
  apiKey: required("NEXT_PUBLIC_API_KEY", process.env.NEXT_PUBLIC_API_KEY),
} as const;