import type { AssetPayload, SearchResponse } from "./types";

export async function searchMarket(
  query: string,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const response = await fetch(
    `/api/market/search?q=${encodeURIComponent(query)}`,
    {
      method: "GET",
      signal,
      headers: {
        Accept: "application/json",
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json() as Promise<SearchResponse>;
}

export async function fetchAsset(
  symbol: string,
  signal?: AbortSignal,
): Promise<AssetPayload> {
  const response = await fetch(
    `/api/market/asset/${encodeURIComponent(symbol)}`,
    {
      signal,
      headers: {
        Accept: "application/json",
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Asset fetch failed: ${response.status}`);
  }
  return response.json() as Promise<AssetPayload>;
}
