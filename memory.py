"""Memory management for Maxwell Bot"""

import json
import logging
import asyncio
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

MAX_MEMORY_CHARS = 1000
MAX_LTM_LINES = 999
MAX_CHANNELS = 25


def _atomic_json_write_sync(path: Path, data):
    """Atomic JSON write: temp file -> fsync -> rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_text_write_sync(path: Path, text: str):
    """Atomic text write: temp file -> fsync -> rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _normalize_ltm_line(content: str) -> str:
    """Keep one memory per physical line so the file stays easy to edit."""
    return " ".join(str(content).split())[:MAX_MEMORY_CHARS]


class MemoryManager:
    """Memory manager with async I/O, debounced saves, and atomic writes."""

    def __init__(self, data_dir: str, max_messages: int = 30):
        self.data_dir = Path(data_dir)
        self.max_messages = min(max_messages, 30)
        self.memory_file = self.data_dir / "memory.json"
        self.ltm_file = self.data_dir / "long_term_memory.txt"
        self.memory = {}
        self.long_term_memory = []
        self._lock = asyncio.Lock()
        self._dirty = False
        self._save_task = None

    def load_from_disk(self):
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                self._prune_short_term_memory()
                logger.info(f"Loaded memory for {len(self.memory)} channels")
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load memory: {e}")
            self.memory = {}

        try:
            if self.ltm_file.exists():
                lines = self.ltm_file.read_text(encoding="utf-8").splitlines()
                self.long_term_memory = [
                    {"id": i + 1, "content": line.strip()}
                    for i, line in enumerate(lines[:MAX_LTM_LINES])
                    if line.strip()
                ]
                logger.info(f"Loaded {len(self.long_term_memory)} long-term memory lines")
        except OSError as e:
            logger.error(f"Failed to load long-term memory: {e}")
            self.long_term_memory = []

    async def _atomic_save(self, filepath: Path, data):
        """Thread-safe atomic JSON save."""
        try:
            await asyncio.to_thread(_atomic_json_write_sync, filepath, data)
        except Exception as e:
            logger.error(f"Failed to save {filepath}: {e}")

    def _prune_short_term_memory(self):
        """Keep short-term memory small before it reaches prompts or disk."""
        if not isinstance(self.memory, dict):
            self.memory = {}
            return
        pruned = {}
        for channel_id, messages in self.memory.items():
            if isinstance(messages, list):
                pruned[str(channel_id)] = messages[-self.max_messages:]

        def latest_ts(item):
            messages = item[1]
            if not messages:
                return ""
            return str(messages[-1].get("timestamp", ""))

        newest = sorted(pruned.items(), key=latest_ts, reverse=True)[:MAX_CHANNELS]
        self.memory = dict(newest)

    def _schedule_save(self):
        """Debounce: save within 5 seconds of last write"""
        self._dirty = True
        if self._save_task is not None:
            self._save_task.cancel()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._save_task = loop.call_later(5, self._do_save)

    def _do_save(self):
        """Actually save if dirty — snapshot data so we don't race mutations."""
        if self._dirty:
            self._dirty = False
            snapshot = json.loads(json.dumps(self.memory, ensure_ascii=False))
            asyncio.ensure_future(self._atomic_save(self.memory_file, snapshot))
        self._save_task = None

    async def flush(self):
        """Flush any pending memory save immediately. Call on shutdown."""
        if self._save_task is not None:
            self._save_task.cancel()
            self._save_task = None
        if self._dirty:
            self._dirty = False
            snapshot = json.loads(json.dumps(self.memory, ensure_ascii=False))
            await self._atomic_save(self.memory_file, snapshot)
            logger.info("Memory flushed to disk")

    async def _save_ltm(self):
        """Save long-term memory as one editable text file."""
        lines = [_normalize_ltm_line(entry.get("content", "")) for entry in self.long_term_memory]
        lines = [line for line in lines if line][:MAX_LTM_LINES]
        text = "\n".join(lines)
        if text:
            text += "\n"
        await asyncio.to_thread(_atomic_text_write_sync, self.ltm_file, text)
        self.long_term_memory = [
            {"id": i + 1, "content": line} for i, line in enumerate(lines)
        ]

    async def get_channel_memory(self, channel_id: str) -> list:
        async with self._lock:
            return list(self.memory.get(channel_id, []))

    async def add_to_channel_memory(self, channel_id: str, message: dict):
        async with self._lock:
            if channel_id not in self.memory:
                self.memory[channel_id] = []

            message["timestamp"] = datetime.now(timezone.utc).isoformat()
            self.memory[channel_id].append(message)

            if len(self.memory[channel_id]) > self.max_messages:
                self.memory[channel_id] = self.memory[channel_id][-self.max_messages:]

            # Evict oldest channels if over limit
            if len(self.memory) > MAX_CHANNELS:
                self._prune_short_term_memory()

            self._schedule_save()

    async def clear_channel_memory(self, channel_id: str):
        async with self._lock:
            if channel_id in self.memory:
                del self.memory[channel_id]
                self._schedule_save()
                logger.info(f"Cleared memory for channel {channel_id}")

    async def add_long_term_memory(self, content: str) -> str:
        content = _normalize_ltm_line(content)
        if not content:
            return "0"
        async with self._lock:
            self.long_term_memory.append({"id": len(self.long_term_memory) + 1, "content": content})
            if len(self.long_term_memory) > MAX_LTM_LINES:
                self.long_term_memory = self.long_term_memory[-MAX_LTM_LINES:]

            await self._save_ltm()
            next_id = len(self.long_term_memory)
            logger.info(f"Added long-term memory #{next_id}")
            return str(next_id)

    async def edit_long_term_memory(self, memory_id: str, content: str) -> bool:
        content = _normalize_ltm_line(content)
        async with self._lock:
            for entry in self.long_term_memory:
                if str(entry["id"]) == str(memory_id):
                    entry["content"] = content
                    await self._save_ltm()
                    logger.info(f"Edited long-term memory #{memory_id}")
                    return True
        return False

    async def remove_long_term_memory(self, memory_id: str) -> bool:
        async with self._lock:
            before = len(self.long_term_memory)
            self.long_term_memory = [
                m for m in self.long_term_memory if str(m["id"]) != str(memory_id)
            ]
            if len(self.long_term_memory) < before:
                await self._save_ltm()
                logger.info(f"Removed long-term memory #{memory_id}")
                return True
        return False

    def get_long_term_memory(self) -> list:
        return list(self.long_term_memory)

    def get_server_prompt(self, server_id: str) -> Optional[str]:
        prompts_file = self.data_dir / "prompts.json"
        try:
            if prompts_file.exists():
                with open(prompts_file, "r", encoding="utf-8") as f:
                    prompts = json.load(f)
                return prompts.get(server_id)
        except Exception as e:
            logger.error(f"Failed to load server prompts: {e}")
        return None

    def set_server_prompt(self, server_id: str, prompt: str):
        prompts_file = self.data_dir / "prompts.json"
        try:
            prompts_file.parent.mkdir(parents=True, exist_ok=True)
            prompts = {}
            if prompts_file.exists():
                with open(prompts_file, "r", encoding="utf-8") as f:
                    prompts = json.load(f)
            prompts[server_id] = prompt
            with open(prompts_file, "w", encoding="utf-8") as f:
                json.dump(prompts, f, indent=2, ensure_ascii=False)
            logger.info(f"Set prompt for server {server_id}")
        except Exception as e:
            logger.error(f"Failed to set server prompt: {e}")

    def clear_server_prompt(self, server_id: str):
        prompts_file = self.data_dir / "prompts.json"
        try:
            if prompts_file.exists():
                with open(prompts_file, "r", encoding="utf-8") as f:
                    prompts = json.load(f)
                if server_id in prompts:
                    del prompts[server_id]
                with open(prompts_file, "w", encoding="utf-8") as f:
                    json.dump(prompts, f, indent=2, ensure_ascii=False)
                logger.info(f"Cleared prompt for server {server_id}")
        except Exception as e:
            logger.error(f"Failed to clear server prompt: {e}")
