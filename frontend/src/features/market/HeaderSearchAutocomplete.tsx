import React, {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import {
  Bitcoin,
  CircleDollarSign,
  Landmark,
  Search,
  TrendingUp,
  X,
} from "lucide-react";
import { searchMarket } from "./api";
import type { AssetType, SearchSuggestion } from "./types";

interface HeaderSearchAutocompleteProps {
  onSelect: (suggestion: SearchSuggestion) => void;
  initialValue?: string;
  className?: string;
}

interface DropdownRect {
  top: number;
  left: number;
  width: number;
}

const BADGE_STYLES: Record<AssetType, string> = {
  EQUITY: "bg-sky-500/10 text-sky-300 ring-sky-500/20",
  ETF: "bg-violet-500/10 text-violet-300 ring-violet-500/20",
  COMMODITY: "bg-amber-500/10 text-amber-300 ring-amber-500/20",
  CRYPTO: "bg-orange-500/10 text-orange-300 ring-orange-500/20",
  FOREX: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20",
};

function badgeLabel(type: AssetType): string {
  return type === "EQUITY" ? "STOCK" : type;
}

function AssetIcon({ type }: { type: AssetType }) {
  const props = { size: 17, strokeWidth: 1.8 };
  switch (type) {
    case "CRYPTO":
      return <Bitcoin {...props} />;
    case "COMMODITY":
      return <CircleDollarSign {...props} />;
    case "FOREX":
      return <Landmark {...props} />;
    default:
      return <TrendingUp {...props} />;
  }
}

export function HeaderSearchAutocomplete({
  onSelect,
  initialValue = "",
  className = "",
}: HeaderSearchAutocompleteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const listboxId = useId();

  const [query, setQuery] = useState(initialValue);
  const [results, setResults] = useState<SearchSuggestion[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rect, setRect] = useState<DropdownRect | null>(null);

  const updatePosition = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    const bounds = input.getBoundingClientRect();
    setRect({
      top: bounds.bottom + 8,
      left: bounds.left,
      width: bounds.width,
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    const trimmed = query.trim();
    requestRef.current?.abort();

    if (!trimmed) {
      setResults([]);
      setActiveIndex(-1);
      setOpen(false);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;

    const timer = window.setTimeout(async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await searchMarket(trimmed, controller.signal);
        if (controller.signal.aborted) return;
        setResults(response.results);
        setActiveIndex(response.results.length ? 0 : -1);
        setOpen(true);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
        setOpen(true);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 150);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const choose = useCallback(
    (suggestion: SearchSuggestion) => {
      onSelect(suggestion);
      setQuery(suggestion.symbol);
      setOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    },
    [onSelect],
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
      }
      setActiveIndex((index) =>
        results.length === 0 ? -1 : (index + 1) % results.length,
      );
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) =>
        results.length === 0 ? -1 : index <= 0 ? results.length - 1 : index - 1,
      );
      return;
    }

    if (event.key === "Enter" && activeIndex >= 0 && results[activeIndex]) {
      event.preventDefault();
      choose(results[activeIndex]);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  const popup =
    open && rect && typeof document !== "undefined"
      ? createPortal(
          <div
            role="listbox"
            id={listboxId}
            aria-label="Market search results"
            className="fixed z-[10000] overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 shadow-2xl shadow-black/40 backdrop-blur-xl"
            style={{
              top: rect.top,
              left: rect.left,
              width: rect.width,
            }}
          >
            {loading && results.length === 0 && (
              <div className="px-4 py-4 text-sm text-slate-400">
                Searching markets…
              </div>
            )}
            {!loading && error && (
              <div className="px-4 py-4 text-sm text-rose-300">{error}</div>
            )}
            {!loading && !error && results.length === 0 && (
              <div className="px-4 py-4 text-sm text-slate-500">
                No matching instruments.
              </div>
            )}
            {results.map((item, index) => {
              const active = index === activeIndex;
              return (
                <button
                  key={`${item.asset_type}:${item.symbol}`}
                  id={`${listboxId}-${index}`}
                  role="option"
                  aria-selected={active}
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onPointerDown={(event) => {
                    event.preventDefault();
                  }}
                  onClick={() => choose(item)}
                  className={`flex w-full items-center gap-3 border-b border-slate-800/70 px-4 py-3 text-left transition last:border-b-0 ${
                    active ? "bg-slate-800/90" : "bg-transparent hover:bg-slate-900"
                  }`}
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-slate-300">
                    <AssetIcon type={item.asset_type} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-100">
                        {item.symbol}
                      </span>
                      <span
                        className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold tracking-wide ring-1 ${
                          BADGE_STYLES[item.asset_type]
                        }`}
                      >
                        {badgeLabel(item.asset_type)}
                      </span>
                    </div>
                    <div className="truncate text-xs text-slate-400">
                      {item.name}
                    </div>
                  </div>
                  <div className="shrink-0 text-right text-[11px] text-slate-500">
                    {item.exchange}
                  </div>
                </button>
              );
            })}
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <div className={`relative ${className}`}>
        <Search
          size={17}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
        />
        <input
          ref={inputRef}
          value={query}
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Search stocks, ETFs, crypto, FX, commodities…"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined
          }
          onFocus={() => {
            if (results.length || loading) {
              setOpen(true);
            }
          }}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          onKeyDown={handleKeyDown}
          className="h-10 w-full rounded-lg border border-slate-700 bg-slate-900/80 pl-10 pr-9 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-500/70 focus:ring-2 focus:ring-sky-500/10"
        />
        {query && (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => {
              setQuery("");
              setOpen(false);
              inputRef.current?.focus();
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          >
            <X size={15} />
          </button>
        )}
      </div>
      {popup}
    </>
  );
}
