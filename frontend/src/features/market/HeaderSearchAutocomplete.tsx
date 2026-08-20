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
  Command,
  Landmark,
  Search,
  TrendingUp,
  X,
  Layers,
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
  EQUITY: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
  ETF: "bg-violet-500/15 text-violet-300 ring-violet-500/30",
  COMMODITY: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  CRYPTO: "bg-orange-500/15 text-orange-300 ring-orange-500/30",
  FOREX: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
};

function badgeLabel(type: AssetType): string {
  return type === "EQUITY" ? "STOCK" : type;
}

function AssetIcon({ type }: { type: AssetType }) {
  const props = { size: 18, strokeWidth: 2 };
  switch (type) {
    case "CRYPTO":
      return <Bitcoin {...props} className="text-orange-400" />;
    case "COMMODITY":
      return <CircleDollarSign {...props} className="text-amber-400" />;
    case "FOREX":
      return <Landmark {...props} className="text-emerald-400" />;
    case "ETF":
      return <Layers {...props} className="text-violet-400" />;
    default:
      return <TrendingUp {...props} className="text-sky-400" />;
  }
}

const CATEGORY_TABS: { label: string; type: AssetType | "ALL" }[] = [
  { label: "All", type: "ALL" },
  { label: "Stocks", type: "EQUITY" },
  { label: "ETFs", type: "ETF" },
  { label: "Crypto", type: "CRYPTO" },
  { label: "Commodities", type: "COMMODITY" },
  { label: "Forex", type: "FOREX" },
];

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
  const [selectedCategory, setSelectedCategory] = useState<AssetType | "ALL">("ALL");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rect, setRect] = useState<DropdownRect | null>(null);

  // Global hotkey: Ctrl+K, Cmd+K, or "/"
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === "k" && (e.metaKey || e.ctrlKey)) ||
        (e.key === "/" && document.activeElement !== inputRef.current && !(document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement))
      ) {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  const updatePosition = useCallback(() => {
    const input = inputRef.current;
    if (!input) return;
    const bounds = input.getBoundingClientRect();
    setRect({
      top: bounds.bottom + 8,
      left: Math.max(16, bounds.left),
      width: Math.max(bounds.width, 420),
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
    }, 120);

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

  const filteredResults = selectedCategory === "ALL"
    ? results
    : results.filter((r) => r.asset_type === selectedCategory);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      if (results.length) {
        setOpen(true);
        setActiveIndex(0);
        event.preventDefault();
      }
      return;
    }

    if (!open) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!filteredResults.length) return;
      setActiveIndex((prev) => (prev + 1) % filteredResults.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!filteredResults.length) return;
      setActiveIndex((prev) =>
        prev <= 0 ? filteredResults.length - 1 : prev - 1,
      );
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && activeIndex < filteredResults.length) {
        choose(filteredResults[activeIndex]);
      } else if (filteredResults.length > 0) {
        choose(filteredResults[0]);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  const popup =
    open && rect && (results.length > 0 || loading || error)
      ? createPortal(
          <div
            id={listboxId}
            role="listbox"
            style={{
              position: "fixed",
              top: `${rect.top}px`,
              left: `${rect.left}px`,
              width: `${rect.width}px`,
              maxHeight: "460px",
            }}
            className="z-50 overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/95 shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100 flex flex-col"
          >
            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 px-3 py-2 bg-slate-950/60 border-b border-slate-800 overflow-x-auto scrollbar-none">
              {CATEGORY_TABS.map((tab) => {
                const isSelected = selectedCategory === tab.type;
                const count = tab.type === "ALL" ? results.length : results.filter((r) => r.asset_type === tab.type).length;
                return (
                  <button
                    key={tab.type}
                    type="button"
                    onClick={() => {
                      setSelectedCategory(tab.type);
                      setActiveIndex(0);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition cursor-pointer flex items-center gap-1.5 ${
                      isSelected
                        ? "bg-accent-cyan text-slate-950 font-bold shadow-sm shadow-accent-cyan/20"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/80"
                    }`}
                  >
                    <span>{tab.label}</span>
                    {count > 0 && (
                      <span className={`text-[10px] px-1 rounded-full ${isSelected ? "bg-slate-950/20 text-slate-950" : "bg-slate-800 text-slate-400"}`}>
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Results Scroll Area */}
            <div className="overflow-y-auto max-h-80 divide-y divide-slate-800/60">
              {loading && (
                <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-slate-400">
                  <div className="w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin"></div>
                  <span>Searching multi-asset markets…</span>
                </div>
              )}
              {!loading && error && (
                <div className="px-4 py-6 text-sm text-rose-400 text-center">{error}</div>
              )}
              {!loading && !error && filteredResults.length === 0 && (
                <div className="px-4 py-8 text-sm text-slate-500 text-center">
                  No matching instruments found for &ldquo;{query}&rdquo;
                </div>
              )}
              {filteredResults.map((item, index) => {
                const active = index === activeIndex;
                return (
                  <button
                    key={`${item.asset_type}:${item.symbol}`}
                    id={`${listboxId}-${index}`}
                    role="option"
                    aria-selected={active}
                    type="button"
                    onMouseEnter={() => setActiveIndex(index)}
                    onPointerDown={(event) => event.preventDefault()}
                    onClick={() => choose(item)}
                    className={`flex w-full items-center gap-3.5 px-4 py-3 text-left transition cursor-pointer ${
                      active ? "bg-slate-800/90 text-white" : "bg-transparent hover:bg-slate-800/50 text-slate-300"
                    }`}
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-800/90 border border-slate-700/60 shadow-inner">
                      <AssetIcon type={item.asset_type} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-slate-100 tracking-wide">
                          {item.symbol}
                        </span>
                        <span
                          className={`rounded-md px-1.5 py-0.5 text-[10px] font-black tracking-wider ring-1 uppercase ${
                            BADGE_STYLES[item.asset_type]
                          }`}
                        >
                          {badgeLabel(item.asset_type)}
                        </span>
                      </div>
                      <div className="truncate text-xs text-slate-400 font-medium">
                        {item.name}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-xs font-mono text-slate-500">
                      {item.exchange}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Footer Navigation Hint */}
            <div className="px-3 py-1.5 bg-slate-950/80 border-t border-slate-800 text-[11px] font-mono text-slate-500 flex items-center justify-between">
              <span>Navigate with <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-300">↑</kbd> <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-300">↓</kbd></span>
              <span>Select with <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700 text-slate-300">↵ Enter</kbd></span>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <div className={`relative ${className}`}>
        <Search
          size={19}
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 transition"
        />
        <input
          ref={inputRef}
          value={query}
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Search stocks (NVDA), ETFs (SPY), crypto (BTC), commodities (GLD), FX..."
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
          className="h-11 w-full rounded-xl border border-slate-700/80 bg-slate-900/90 pl-11 pr-20 text-sm font-semibold text-slate-100 outline-none transition-all placeholder:text-slate-500 placeholder:font-normal focus:border-accent-cyan focus:ring-2 focus:ring-accent-cyan/30 shadow-inner"
        />
        
        {/* Right side shortcut badge or Clear button */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
          {query ? (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                setQuery("");
                setOpen(false);
                inputRef.current?.focus();
              }}
              className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition cursor-pointer"
            >
              <X size={16} />
            </button>
          ) : (
            <div className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-400 shadow-sm pointer-events-none">
              <Command size={11} />
              <span>K</span>
            </div>
          )}
        </div>
      </div>
      {popup}
    </>
  );
}
