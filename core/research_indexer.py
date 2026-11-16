"""
Scheduled Public-Information Indexing Subsystem for Operation JARVIS.
Maintains a separate SQLite FTS5 research index (data/research_index.db)
for public papers, advisories, and tech news, keeping personal memory (LOCAL_AI_MEMORY)
strictly isolated and protected from unverified web content.
"""
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from registry.internet_gateway import internet_gateway

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESEARCH_DB_PATH = DATA_DIR / "research_index.db"
STATUS_FILE = DATA_DIR / "indexer_status.json"
PID_FILE = DATA_DIR / "indexer.pid"

logger = logging.getLogger("jarvis.research_indexer")

DEFAULT_SOURCES = [
    {
        "id": "src-arxiv-ai",
        "name": "arXiv AI & Machine Learning Research",
        "url": "https://export.arxiv.org/api/query?search_query=all:agent+OR+transformer+OR+reasoning&start=0&max_results=5",
        "type": "arxiv",
        "enabled": 1,
        "interval_seconds": 3600
    },
    {
        "id": "src-hn-tech",
        "name": "HackerNews Technology Announcements",
        "url": "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=5",
        "type": "tech_news",
        "enabled": 1,
        "interval_seconds": 1800
    },
    {
        "id": "src-cve-advisories",
        "name": "CIRCL / NVD Security Advisories",
        "url": "https://cve.circl.lu/api/last",
        "type": "cve",
        "enabled": 1,
        "interval_seconds": 7200
    }
]


class ResearchIndexDB:
    def __init__(self, db_path: Path = RESEARCH_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                type TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                interval_seconds INTEGER DEFAULT 3600,
                last_fetched TEXT
            );
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS research_items (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                snippet TEXT,
                content TEXT,
                published_date TEXT,
                retrieved_at TEXT NOT NULL,
                freshness_category TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources (id)
            );
            """)

            # FTS5 search index table
            conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS research_fts USING fts5(
                title,
                snippet,
                content,
                content='research_items',
                content_rowid='rowid'
            );
            """)

            # Triggers to keep FTS index synchronized
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_research_ai AFTER INSERT ON research_items BEGIN
                INSERT INTO research_fts(rowid, title, snippet, content)
                VALUES (new.rowid, new.title, new.snippet, new.content);
            END;
            """)
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_research_ad AFTER DELETE ON research_items BEGIN
                INSERT INTO research_fts(research_fts, rowid, title, snippet, content)
                VALUES('delete', old.rowid, old.title, old.snippet, old.content);
            END;
            """)
            conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_research_au AFTER UPDATE ON research_items BEGIN
                INSERT INTO research_fts(research_fts, rowid, title, snippet, content)
                VALUES('delete', old.rowid, old.title, old.snippet, old.content);
                INSERT INTO research_fts(rowid, title, snippet, content)
                VALUES (new.rowid, new.title, new.snippet, new.content);
            END;
            """)

            # Seed default sources if missing
            for s in DEFAULT_SOURCES:
                conn.execute("""
                INSERT OR IGNORE INTO sources (id, name, url, type, enabled, interval_seconds)
                VALUES (?, ?, ?, ?, ?, ?);
                """, (s["id"], s["name"], s["url"], s["type"], s["enabled"], s["interval_seconds"]))

            conn.commit()

    def get_sources(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM sources;").fetchall()
            return [dict(r) for r in rows]

    def insert_item(self, source_id: str, url: str, title: str, snippet: str,
                    content: str, published_date: Optional[str], freshness_category: str) -> bool:
        """
        Inserts a new research item with SHA-256 deduplication.
        Returns True if newly inserted, False if duplicated.
        """
        content_hash = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
        item_id = f"res_{content_hash[:16]}"
        retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            # Check existing URL or hash
            existing = conn.execute("SELECT id FROM research_items WHERE url = ? OR content_hash = ?;", (url, content_hash)).fetchone()
            if existing:
                return False

            conn.execute("""
            INSERT INTO research_items (id, source_id, url, title, snippet, content, published_date, retrieved_at, freshness_category, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (item_id, source_id, url, title, snippet, content, published_date, retrieved_at, freshness_category, content_hash))
            conn.commit()
            return True

    def search_research(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        BM25 search over the isolated research FTS5 index.
        """
        sanitized_q = "".join([c for c in query if c.isalnum() or c in (" ", "-", "_")]).strip()
        if not sanitized_q:
            return []

        fts_query = " OR ".join([f'"{token}*"' for token in sanitized_q.split() if token])
        if not fts_query:
            return []

        with self._get_connection() as conn:
            sql = """
            SELECT r.id, r.source_id, r.url, r.title, r.snippet, r.published_date, r.retrieved_at, r.freshness_category,
                   bm25(research_fts) as rank
            FROM research_fts f
            JOIN research_items r ON f.rowid = r.rowid
            WHERE research_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
            """
            rows = conn.execute(sql, (fts_query, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            item_count = conn.execute("SELECT COUNT(*) FROM research_items;").fetchone()[0]
            source_count = conn.execute("SELECT COUNT(*) FROM sources;").fetchone()[0]
            freshness_dist = conn.execute("""
            SELECT freshness_category, COUNT(*) as cnt
            FROM research_items
            GROUP BY freshness_category;
            """).fetchall()
            return {
                "total_indexed_items": item_count,
                "active_sources": source_count,
                "freshness_distribution": {r["freshness_category"]: r["cnt"] for r in freshness_dist},
                "db_path": str(self.db_path)
            }

    def delete_item(self, item_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM research_items WHERE id = ?;", (item_id,))
            conn.commit()
            return cursor.rowcount > 0

    def purge_all(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM research_items;")
            conn.commit()
            return cursor.rowcount


class ResearchIndexerService:
    def __init__(self):
        self.db = ResearchIndexDB()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    def get_status(self) -> Dict[str, Any]:
        stats = self.db.get_stats()
        return {
            "service_active": self._is_running,
            "indexing_policy": "Optional, isolated, read-only background indexing",
            "personal_memory_isolated": True,
            "target_database": str(self.db.db_path),
            "stats": stats
        }

    def run_indexing_cycle(self) -> Dict[str, Any]:
        """
        Executes one pass over all enabled sources, deduplicates, and stores items.
        """
        logger.info("Starting scheduled research indexing cycle...")
        cycle_start = time.time()
        sources = self.db.get_sources()
        new_items_count = 0
        cycle_details = []

        for src in sources:
            if not src.get("enabled"):
                continue

            src_type = src.get("type")
            src_id = src.get("id")
            fetched = []

            try:
                if src_type == "arxiv":
                    fetched = internet_gateway.search_arxiv("agent OR transformer", max_results=3)
                elif src_type == "tech_news":
                    fetched = internet_gateway.search_tech_news("AI OR cybersecurity", max_results=3)
                elif src_type == "cve":
                    fetched = internet_gateway.search_cve("vulnerability", max_results=3)

                added_for_source = 0
                for item in fetched:
                    if self.db.insert_item(
                        source_id=src_id,
                        url=item["url"],
                        title=item["title"],
                        snippet=item.get("snippet", ""),
                        content=item.get("snippet", ""),
                        published_date=item.get("published_date"),
                        freshness_category=item.get("freshness_category", "Unknown Publication Date")
                    ):
                        added_for_source += 1

                new_items_count += added_for_source
                cycle_details.append({
                    "source": src.get("name"),
                    "fetched": len(fetched),
                    "newly_indexed": added_for_source
                })

            except Exception as e:
                logger.warning(f"Error fetching from source {src_id}: {e}")
                cycle_details.append({"source": src.get("name"), "error": str(e)})

        duration = round(time.time() - cycle_start, 2)
        summary = {
            "ok": True,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "new_items_indexed": new_items_count,
            "duration_seconds": duration,
            "sources_evaluated": len(sources),
            "details": cycle_details
        }

        # Write status file
        try:
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        except Exception:
            pass

        return summary

    def start(self, interval_seconds: int = 3600):
        if self._is_running:
            return {"ok": False, "message": "Service is already running."}

        self._stop_event.clear()
        self._is_running = True

        def _loop():
            logger.info("Research indexer background worker started.")
            while not self._stop_event.is_set():
                try:
                    self.run_indexing_cycle()
                except Exception as e:
                    logger.error(f"Error in research indexing cycle: {e}")

                # Wait in small increments so stop is responsive
                for _ in range(interval_seconds):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1.0)
            self._is_running = False
            logger.info("Research indexer background worker stopped.")

        self._worker_thread = threading.Thread(target=_loop, daemon=True, name="ResearchIndexerWorker")
        self._worker_thread.start()
        return {"ok": True, "message": "Research indexer started in background."}

    def stop(self):
        self._stop_event.set()
        self._is_running = False
        return {"ok": True, "message": "Research indexer stop signal dispatched."}

    def emergency_stop(self):
        """Immediately halts indexing and purges active worker state."""
        self._stop_event.set()
        self._is_running = False
        return {"ok": True, "message": "Emergency stop invoked. Indexer halted immediately."}


research_indexer = ResearchIndexerService()
