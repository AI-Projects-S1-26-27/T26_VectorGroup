"""Depth-preferred transposition table for the search hooks."""
from c4.search import EXACT, LOWER, UPPER
from threading import RLock


class TranspositionTable:
    """Store node-relative scores; search handles win-distance conversion.

    At capacity, evict the oldest entry. Deeper entries for the same key
    survive shallower writes, and exact entries win ties against bounds.
    """

    def __init__(self, max_entries: int = 100_000):
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries = {}
        self._probes = self._hits = self._stores = 0
        self._native = None
        self._native_lock = RLock()

    def probe(self, key):
        if self._native is not None:
            return self._native.probe(key)
        self._probes += 1
        entry = self._entries.get(key)
        if entry is not None:
            self._hits += 1
        return entry

    def store(self, key, depth, value, flag, best_move):
        if flag not in (EXACT, LOWER, UPPER):
            raise ValueError("unknown transposition-table flag")
        if self._native is not None:
            self._native.store(key, depth, value, flag, best_move)
            return
        old = self._entries.get(key)
        if old is not None:
            if depth < old[0]:
                return
            if depth == old[0] and old[2] == EXACT and flag != EXACT:
                return
        elif len(self._entries) >= self.max_entries:
            del self._entries[next(iter(self._entries))]
        self._entries[key] = (depth, value, flag, best_move)
        self._stores += 1

    def clear(self):
        """Remove entries and reset counters for a fresh experiment."""
        self._entries.clear()
        self._probes = self._hits = self._stores = 0
        if self._native is not None:
            self._native.clear()

    def stats(self):
        """Return a snapshot; stores counts accepted writes."""
        if self._native is not None:
            return self._native.stats()
        return {"entries": len(self._entries), "probes": self._probes,
                "hits": self._hits, "stores": self._stores}

    def __len__(self):
        if self._native is not None:
            return self._native.stats()["entries"]
        return len(self._entries)

    def native_context(self):
        """Lazily share the same public table with the optional accelerator."""
        with self._native_lock:
            if self._native is None:
                from c4.native_search import NativeTable
                context = NativeTable(self.max_entries)
                for key, entry in self._entries.items():
                    context.store(key, *entry)
                context.lib.c4_table_counters(context.handle, self._probes, self._hits, self._stores)
                self._native = context
                self._entries.clear()
            return self._native
