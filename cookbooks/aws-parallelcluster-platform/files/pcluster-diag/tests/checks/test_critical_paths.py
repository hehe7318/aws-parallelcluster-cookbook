# Copyright 2026 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the
# License. A copy of the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "LICENSE.txt" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the critical-paths permission check."""

from pcluster_diag.checks import critical_paths
from pcluster_diag.checks.critical_paths import CriticalPath, CriticalPathsHaveExpectedPermissions
from pcluster_diag.core.constants import COMPUTEFLEET_STATUS_PATH
from pcluster_diag.models.context import NodeType
from pcluster_diag.models.result import Status
from pcluster_diag.util.filesystem import PathStat
from tests.sample_data import sample_context

# A single head-node critical path used by most tests (mirrors computefleet-status.json).
_HEAD_PATH = CriticalPath(
    path="/opt/parallelcluster/shared/computefleet-status.json",
    owner="pcluster-admin",
    group="pcluster-admin",
    mode="0755",
    node_types=(NodeType.HEAD,),
)


def _check(paths=None):
    """Build the check with an explicit path list (defaults to the single head-node path)."""
    return CriticalPathsHaveExpectedPermissions(critical_paths=[_HEAD_PATH] if paths is None else paths)


def _fake_stat(monkeypatch, mapping):
    """Patch filesystem.stat_path: mapping is path -> PathStat, a missing key raises FileNotFoundError."""

    def stat_path(path):
        if path not in mapping:
            raise FileNotFoundError(path)
        return mapping[path]

    monkeypatch.setattr(critical_paths.filesystem, "stat_path", stat_path)


def _codes(result):
    """Return the list of error codes carried by a Result (empty list when it has no errors)."""
    return [error.code for error in (result.errors or [])]


def _messages(result):
    """Return the joined error messages carried by a Result."""
    return " | ".join(error.message for error in (result.errors or []))


def test_default_critical_paths_include_computefleet_status():
    entry = next(c for c in critical_paths.CRITICAL_PATHS if c.path == COMPUTEFLEET_STATUS_PATH)

    assert entry.owner == "pcluster-admin"
    assert entry.group == "pcluster-admin"
    assert entry.mode == "0755"
    assert entry.node_types == (NodeType.HEAD,)


def test_description():
    assert "critical files" in _check().description


def test_should_run_only_on_node_types_with_applicable_paths():
    # The sample head path applies to HEAD only.
    assert _check().should_run(sample_context(NodeType.HEAD)) is True
    assert _check().should_run(sample_context(NodeType.COMPUTE)) is False
    assert _check().should_run(sample_context(NodeType.LOGIN)) is False


def test_run_passes_when_owner_group_mode_all_match(monkeypatch):
    _fake_stat(monkeypatch, {_HEAD_PATH.path: PathStat(owner="pcluster-admin", group="pcluster-admin", mode="0755")})

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.PASSED
    assert result.errors is None


def test_run_fails_when_owner_wrong(monkeypatch):
    # The file exists but is no longer owned by pcluster-admin.
    _fake_stat(monkeypatch, {_HEAD_PATH.path: PathStat(owner="root", group="pcluster-admin", mode="0755")})

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.FAILURE
    assert _codes(result) == [CriticalPathsHaveExpectedPermissions.WRONG_OWNERSHIP]
    assert "is owned by root:pcluster-admin but should be pcluster-admin:pcluster-admin" in _messages(result)


def test_run_fails_when_group_wrong(monkeypatch):
    _fake_stat(monkeypatch, {_HEAD_PATH.path: PathStat(owner="pcluster-admin", group="root", mode="0755")})

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.FAILURE
    assert _codes(result) == [CriticalPathsHaveExpectedPermissions.WRONG_OWNERSHIP]
    assert "pcluster-admin:root but should be pcluster-admin:pcluster-admin" in _messages(result)


def test_run_fails_when_mode_wrong(monkeypatch):
    _fake_stat(monkeypatch, {_HEAD_PATH.path: PathStat(owner="pcluster-admin", group="pcluster-admin", mode="0700")})

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.FAILURE
    assert _codes(result) == [CriticalPathsHaveExpectedPermissions.WRONG_MODE]
    assert "has mode 0700 but should be 0755" in _messages(result)


def test_run_reports_both_ownership_and_mode_when_both_wrong(monkeypatch):
    _fake_stat(monkeypatch, {_HEAD_PATH.path: PathStat(owner="root", group="root", mode="0700")})

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.FAILURE
    assert _codes(result) == [
        CriticalPathsHaveExpectedPermissions.WRONG_OWNERSHIP,
        CriticalPathsHaveExpectedPermissions.WRONG_MODE,
    ]


def test_run_fails_when_path_missing(monkeypatch):
    _fake_stat(monkeypatch, {})  # nothing exists -> FileNotFoundError

    result = _check().run(sample_context(NodeType.HEAD))

    assert result.status is Status.FAILURE
    assert _codes(result) == [CriticalPathsHaveExpectedPermissions.MISSING_PATH]
    assert "is missing" in _messages(result)


def test_run_only_inspects_paths_for_current_node_type(monkeypatch):
    compute_path = CriticalPath("/x", "root", "root", "0644", (NodeType.COMPUTE,))
    inspected = []

    def stat_path(path):
        inspected.append(path)
        return PathStat(owner="pcluster-admin", group="pcluster-admin", mode="0755")

    monkeypatch.setattr(critical_paths.filesystem, "stat_path", stat_path)

    _check([_HEAD_PATH, compute_path]).run(sample_context(NodeType.HEAD))

    # Only the HEAD path is inspected; the compute-only path is skipped on the head node.
    assert inspected == [_HEAD_PATH.path]
