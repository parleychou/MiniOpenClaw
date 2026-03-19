import pytest
import os
import tempfile
from storage.chat_store import ChatStore


def test_save_and_load_session_record(tmp_path):
    """Test saving and loading session records."""
    store = ChatStore(storage_dir=str(tmp_path))

    record = {
        "session_id": "s_001",
        "user_id": "ou_123",
        "template_name": "codex",
        "work_dir": r"E:\2026\repo\api",
        "session_name": "api-fix",
        "status": "running",
    }

    store.save_session_record(record)
    records = store.load_session_records()

    assert len(records) == 1
    assert records[0]["session_id"] == "s_001"
    assert records[0]["template_name"] == "codex"
    assert records[0]["status"] == "running"


def test_update_existing_session_record(tmp_path):
    """Test updating an existing session record."""
    store = ChatStore(storage_dir=str(tmp_path))

    record1 = {
        "session_id": "s_001",
        "user_id": "ou_123",
        "template_name": "codex",
        "work_dir": r"E:\2026\repo\api",
        "session_name": "api-fix",
        "status": "running",
    }
    store.save_session_record(record1)

    record2 = {
        "session_id": "s_001",
        "user_id": "ou_123",
        "template_name": "codex",
        "work_dir": r"E:\2026\repo\api",
        "session_name": "api-fix",
        "status": "stopped",
    }
    store.save_session_record(record2)

    records = store.load_session_records()
    assert len(records) == 1
    assert records[0]["status"] == "stopped"


def test_load_session_records_empty(tmp_path):
    """Test loading when no records exist."""
    store = ChatStore(storage_dir=str(tmp_path))
    records = store.load_session_records()
    assert records == []


def test_multiple_session_records(tmp_path):
    """Test saving multiple different session records."""
    store = ChatStore(storage_dir=str(tmp_path))

    record1 = {
        "session_id": "s_001",
        "user_id": "ou_123",
        "template_name": "claude_code",
        "work_dir": r"E:\2026\proj1",
        "session_name": "proj1",
        "status": "running",
    }
    record2 = {
        "session_id": "s_002",
        "user_id": "ou_123",
        "template_name": "opencode",
        "work_dir": r"E:\2026\proj2",
        "session_name": "proj2",
        "status": "stopped",
    }

    store.save_session_record(record1)
    store.save_session_record(record2)

    records = store.load_session_records()
    assert len(records) == 2
    session_ids = [r["session_id"] for r in records]
    assert "s_001" in session_ids
    assert "s_002" in session_ids
