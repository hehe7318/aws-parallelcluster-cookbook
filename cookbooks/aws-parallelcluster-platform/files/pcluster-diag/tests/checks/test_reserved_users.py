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

"""Unit tests for the reserved-user/group checks (existence, uid uniqueness, gid uniqueness)."""

import pytest

from pcluster_diag.checks import reserved_users
from pcluster_diag.checks.reserved_users import (
    ReservedGroupsHaveUniqueIds,
    ReservedUsersExist,
    ReservedUsersHaveUniqueIds,
)
from pcluster_diag.models.context import NodeType
from pcluster_diag.models.result import Status
from tests.sample_data import sample_context

# The reserved ids ParallelCluster assigns (mirrors constants; kept explicit so a constants change is caught).
_EXPECTED_UIDS = {"pcluster-admin": 400, "slurm": 401, "munge": 402}
_EXPECTED_GIDS = {"pcluster-admin": 400, "slurm": 401, "munge": 402, "pcluster-slurm-share": 405}


def _fake_users(monkeypatch, *, uids=None, gids=None, uid_owners=None, gid_owners=None):
    """Patch the ``users`` module the checks call.

    uids/gids: name -> id (None means the user/group does not exist).
    uid_owners/gid_owners: id -> [names]; defaults to the single expected owner per id.
    """
    uids = _EXPECTED_UIDS if uids is None else uids
    gids = _EXPECTED_GIDS if gids is None else gids
    monkeypatch.setattr(reserved_users.users, "get_user_uid", lambda name: uids.get(name))
    monkeypatch.setattr(reserved_users.users, "get_group_gid", lambda name: gids.get(name))
    monkeypatch.setattr(reserved_users.users, "get_user_gid", lambda name: uids.get(name))

    def usernames_for_uid(uid):
        if uid_owners is not None:
            return uid_owners.get(uid, [])
        return [name for name, value in uids.items() if value == uid]

    def groupnames_for_gid(gid):
        if gid_owners is not None:
            return gid_owners.get(gid, [])
        return [name for name, value in gids.items() if value == gid]

    monkeypatch.setattr(reserved_users.users, "get_usernames_for_uid", usernames_for_uid)
    monkeypatch.setattr(reserved_users.users, "get_groupnames_for_gid", groupnames_for_gid)


def _codes(result):
    """Return the list of error codes carried by a Result (empty list when it has no errors)."""
    return [error.code for error in (result.errors or [])]


def _messages(result):
    """Return the joined error messages carried by a Result."""
    return " | ".join(error.message for error in (result.errors or []))


# --- descriptions & applicability -----------------------------------------------------


@pytest.mark.parametrize(
    "check_cls",
    [ReservedUsersExist, ReservedUsersHaveUniqueIds, ReservedGroupsHaveUniqueIds],
)
@pytest.mark.parametrize("node_type", list(NodeType), ids=lambda nt: nt.name)
def test_checks_apply_to_every_node_type(check_cls, node_type):
    # Reserved users/groups exist on every node type, so these checks always apply.
    assert check_cls().should_run(sample_context(node_type)) is True
    assert check_cls().approval_required(sample_context(node_type)) is False


# --- ReservedUsersExist ---------------------------------------------------------------


def test_users_exist_passes_when_all_present_with_expected_ids(monkeypatch):
    _fake_users(monkeypatch)

    result = ReservedUsersExist().run(sample_context())

    assert result.status is Status.PASSED
    assert result.errors is None


def test_users_exist_fails_when_a_user_is_missing(monkeypatch):
    _fake_users(monkeypatch, uids={"pcluster-admin": 400, "slurm": None, "munge": 402})

    result = ReservedUsersExist().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedUsersExist.MISSING_USER]
    assert "user 'slurm' does not exist" in _messages(result)


def test_users_exist_fails_when_uid_mismatches(monkeypatch):
    _fake_users(monkeypatch, uids={"pcluster-admin": 1500, "slurm": 401, "munge": 402})

    result = ReservedUsersExist().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedUsersExist.UNEXPECTED_UID]
    assert "user 'pcluster-admin' has uid 1500 but ParallelCluster expects 400" in _messages(result)
    # The message points out the admin uid can be intentionally overridden at build time.
    assert "cluster_admin_user_id" in _messages(result)


def test_users_exist_fails_when_group_missing(monkeypatch):
    _fake_users(
        monkeypatch,
        gids={"pcluster-admin": 400, "slurm": 401, "munge": 402, "pcluster-slurm-share": None},
    )

    result = ReservedUsersExist().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedUsersExist.MISSING_GROUP]
    assert "group 'pcluster-slurm-share' does not exist (expected gid 405)" in _messages(result)


def test_users_exist_fails_when_gid_mismatches(monkeypatch):
    _fake_users(monkeypatch, gids={"pcluster-admin": 400, "slurm": 401, "munge": 402, "pcluster-slurm-share": 999})

    result = ReservedUsersExist().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedUsersExist.UNEXPECTED_GID]
    assert "group 'pcluster-slurm-share' has gid 999 but ParallelCluster expects 405" in _messages(result)


# --- ReservedUsersHaveUniqueIds -------------------------------------------------------


def test_user_uids_unique_passes_when_each_uid_has_one_owner(monkeypatch):
    _fake_users(monkeypatch)

    result = ReservedUsersHaveUniqueIds().run(sample_context())

    assert result.status is Status.PASSED
    assert result.errors is None


def test_user_uids_unique_fails_on_shared_uid(monkeypatch):
    # pcluster-admin (uid 400) collides with a pre-existing account that comes first in /etc/passwd.
    _fake_users(
        monkeypatch,
        uid_owners={400: ["svc-erd", "pcluster-admin"], 401: ["slurm"], 402: ["munge"]},
    )

    result = ReservedUsersHaveUniqueIds().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedUsersHaveUniqueIds.SHARED_UID]
    assert "uid 400 of reserved user 'pcluster-admin' is also used by: svc-erd" in _messages(result)
    # The reserved range is surfaced so the user knows which ids to avoid.
    assert "400-405" in _messages(result)


def test_user_uids_unique_skips_absent_users(monkeypatch):
    # A missing user is ReservedUsersExist's concern; the uniqueness check must not trip on it.
    _fake_users(monkeypatch, uids={"pcluster-admin": None, "slurm": 401, "munge": 402})

    result = ReservedUsersHaveUniqueIds().run(sample_context())

    assert result.status is Status.PASSED


# --- ReservedGroupsHaveUniqueIds ------------------------------------------------------


def test_group_gids_unique_passes_when_each_gid_has_one_owner(monkeypatch):
    _fake_users(monkeypatch)

    result = ReservedGroupsHaveUniqueIds().run(sample_context())

    assert result.status is Status.PASSED
    assert result.errors is None


def test_group_gids_unique_fails_on_shared_gid(monkeypatch):
    _fake_users(
        monkeypatch,
        gid_owners={
            400: ["pcluster-admin", "legacy-grp"],
            401: ["slurm"],
            402: ["munge"],
            405: ["pcluster-slurm-share"],
        },
    )

    result = ReservedGroupsHaveUniqueIds().run(sample_context())

    assert result.status is Status.FAILURE
    assert _codes(result) == [ReservedGroupsHaveUniqueIds.SHARED_GID]
    assert "gid 400 of reserved group 'pcluster-admin' is also used by: legacy-grp" in _messages(result)


def test_group_gids_unique_skips_absent_groups(monkeypatch):
    # A missing group is ReservedUsersExist's concern; the uniqueness check must not trip on it.
    _fake_users(
        monkeypatch,
        gids={"pcluster-admin": 400, "slurm": 401, "munge": 402, "pcluster-slurm-share": None},
    )

    result = ReservedGroupsHaveUniqueIds().run(sample_context())

    assert result.status is Status.PASSED
