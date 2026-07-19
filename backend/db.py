"""SQLite database interface for saving comparison history."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)

# Configurable database file path (defaults to ./data/history.db)
DB_PATH = os.getenv("HISTORY_DB_PATH", "./data/history.db")


def init_db():
    """Create data directories and initialize the database schema."""
    db_file = Path(DB_PATH)
    try:
        # Create directories if they do not exist
        db_file.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()

        # Create comparisons history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                prompt_a TEXT NOT NULL,
                prompt_b TEXT NOT NULL,
                test_input TEXT NOT NULL,
                model TEXT NOT NULL,
                use_system_instruction INTEGER NOT NULL,
                runs INTEGER NOT NULL,
                result_a TEXT NOT NULL,       -- JSON string of ResultItem
                result_b TEXT NOT NULL,       -- JSON string of ResultItem
                runs_a TEXT,                 -- JSON string of list[ResultItem] or NULL
                runs_b TEXT,                 -- JSON string of list[ResultItem] or NULL
                variance_a TEXT,             -- JSON string of VarianceSummary or NULL
                variance_b TEXT,             -- JSON string of VarianceSummary or NULL
                judge_verdict TEXT           -- JSON string of JudgeVerdict or NULL
            )
        """)
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully at %s", db_file.resolve())
    except Exception as e:
        logger.error("❌ Failed to initialize database: %s", e)
        raise e


def _save_comparison_sync(req_data: dict, resp_data: dict):
    """Synchronous db insert run in threadpool."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()

        # Convert Request/Response components to JSON strings for database storage
        cursor.execute("""
            INSERT INTO comparisons (
                timestamp, prompt_a, prompt_b, test_input, model,
                use_system_instruction, runs, result_a, result_b,
                runs_a, runs_b, variance_a, variance_b, judge_verdict
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            req_data.get("prompt_a", ""),
            req_data.get("prompt_b", ""),
            req_data.get("test_input", ""),
            req_data.get("model", ""),
            1 if req_data.get("use_system_instruction", True) else 0,
            req_data.get("runs", 1),
            json.dumps(resp_data.get("result_a", {})),
            json.dumps(resp_data.get("result_b", {})),
            json.dumps(resp_data.get("runs_a")) if resp_data.get("runs_a") else None,
            json.dumps(resp_data.get("runs_b")) if resp_data.get("runs_b") else None,
            json.dumps(resp_data.get("variance_a")) if resp_data.get("variance_a") else None,
            json.dumps(resp_data.get("variance_b")) if resp_data.get("variance_b") else None,
            json.dumps(resp_data.get("judge_verdict")) if resp_data.get("judge_verdict") else None,
        ))
        conn.commit()
        logger.info("💾 Comparison saved to database history")
    except Exception as e:
        logger.error("❌ Failed to save comparison to database: %s", e)
    finally:
        conn.close()


async def save_comparison(req_data: dict, resp_data: dict):
    """Save a comparison record asynchronously via thread pool."""
    await asyncio.to_thread(_save_comparison_sync, req_data, resp_data)


def _get_history_sync(page: int, limit: int) -> dict:
    """Synchronous db paginated query run in threadpool."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Get total row count
        cursor.execute("SELECT COUNT(*) FROM comparisons")
        total_count = cursor.fetchone()[0]

        offset = (page - 1) * limit
        cursor.execute("""
            SELECT * FROM comparisons
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()

        comparisons = []
        for row in rows:
            comp = dict(row)
            # Reconstruct typed schemas from serialized JSON strings
            comp["use_system_instruction"] = bool(comp["use_system_instruction"])
            comp["result_a"] = json.loads(comp["result_a"])
            comp["result_b"] = json.loads(comp["result_b"])
            comp["runs_a"] = json.loads(comp["runs_a"]) if comp["runs_a"] else None
            comp["runs_b"] = json.loads(comp["runs_b"]) if comp["runs_b"] else None
            comp["variance_a"] = json.loads(comp["variance_a"]) if comp["variance_a"] else None
            comp["variance_b"] = json.loads(comp["variance_b"]) if comp["variance_b"] else None
            comp["judge_verdict"] = json.loads(comp["judge_verdict"]) if comp["judge_verdict"] else None
            comparisons.append(comp)

        return {
            "comparisons": comparisons,
            "total": total_count,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        logger.error("❌ Failed to retrieve history from database: %s", e)
        return {
            "comparisons": [],
            "total": 0,
            "page": page,
            "limit": limit
        }
    finally:
        conn.close()


async def get_history(page: int, limit: int) -> dict:
    """Retrieve comparisons history asynchronously via thread pool."""
    return await asyncio.to_thread(_get_history_sync, page, limit)
