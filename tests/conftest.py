from __future__ import annotations

import os
import ipaddress
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest


LIVE_PUBLIC_RECORD_ENV_RE = re.compile(
    r"""(?:getenv|environ\.get)\(\s*["']"""
    r"""((?:RUN_LIVE|LIVE_PUBLIC_RECORDS|OSINT_LIVE_TESTS)[A-Z0-9_]*)"""
    r"""["']"""
)


def _live_public_record_env_names(
    tests_root: Path | None = None,
) -> tuple[str, ...]:
    """Discover the existing opt-in environment gates without importing tests."""

    root = tests_root or Path(__file__).resolve().parent
    names: set[str] = set()
    for path in root.rglob("*.py"):
        names.update(
            LIVE_PUBLIC_RECORD_ENV_RE.findall(
                path.read_text(encoding="utf-8")
            )
        )
    return tuple(sorted(names))


def _enable_live_public_record_tests(
    tests_root: Path | None = None,
) -> tuple[str, ...]:
    names = _live_public_record_env_names(tests_root)
    for name in names:
        os.environ[name] = "1"
    return names


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("public records")
    group.addoption(
        "--run-live-public-records",
        action="store_true",
        default=False,
        help=(
            "Enable the repository's existing opt-in public-record live "
            "checks before test collection"
        ),
    )
    group.addoption(
        "--run-live-data",
        action="store_true",
        default=False,
        help="Allow tests marked live_data (including local large corpora)",
    )
    group.addoption(
        "--offline",
        action="store_true",
        default=False,
        help="Disable live opt-ins and reject external socket connections; loopback fixtures are allowed",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("offline"):
        if config.getoption("run_live_public_records") or config.getoption("run_live_data"):
            raise pytest.UsageError("--offline cannot be combined with live-test options")
        for name in _live_public_record_env_names():
            os.environ.pop(name, None)
    if config.getoption("run_live_public_records"):
        _enable_live_public_record_tests()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    allow_live = config.getoption("run_live_data") or config.getoption("run_live_public_records")
    for item in items:
        # Historical live modules used many separate environment opt-ins. Give
        # all of them the same marker so CI selection is explicit and complete.
        if item.path.name.endswith("_live.py"):
            item.add_marker(pytest.mark.live_data)
        if item.get_closest_marker("live_data") and not allow_live:
            item.add_marker(pytest.mark.skip(reason="live data requires an explicit live-test option"))


@pytest.fixture(autouse=True)
def offline_network_guard(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    if not request.config.getoption("offline"):
        return

    def guard(original):
        def connect(sock, address, *args, **kwargs):
            if sock.family == socket.AF_UNIX or _is_loopback_address(address):
                return original(sock, address, *args, **kwargs)
            raise AssertionError("External network access is disabled by --offline; use a fixture or a live_data test")
        return connect

    monkeypatch.setattr(socket.socket, "connect", guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(socket.socket.connect_ex))
    original_create = socket.create_connection

    def create(address, *args, **kwargs):
        if not _is_loopback_address(address):
            raise AssertionError("External network access is disabled by --offline; use a fixture or a live_data test")
        return original_create(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", create)


def _is_loopback_address(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if host == "localhost":
        return True  # The connect guard also checks the eventual resolved IP.
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fixtures_root(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_data_dir(fixtures_root: Path) -> Path:
    return fixtures_root / "data"


@pytest.fixture
def copy_fixture_db(tmp_path: Path, fixtures_data_dir: Path) -> Callable[[str], Path]:
    def _copy(name: str) -> Path:
        source = fixtures_data_dir / name
        if not source.exists():
            raise FileNotFoundError(f"Fixture DB not found: {source}")
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target

    return _copy


@pytest.fixture
def copy_fixture_tree(tmp_path: Path, fixtures_data_dir: Path) -> Callable[[str], Path]:
    def _copy(relative_dir: str) -> Path:
        source = fixtures_data_dir / relative_dir
        if not source.exists():
            raise FileNotFoundError(f"Fixture directory not found: {source}")
        target = tmp_path / relative_dir
        shutil.copytree(source, target)
        return target

    return _copy


@pytest.fixture
def run_python_script(repo_root: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(script_relpath: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        script_path = repo_root / script_relpath
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        return subprocess.run(
            [sys.executable, str(script_path), *args],
            cwd=str(cwd or repo_root),
            capture_output=True,
            text=True,
            check=False,
        )

    return _run
