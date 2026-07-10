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

"""Checks asserting ParallelCluster's reserved POSIX users and groups exist with unique, expected ids.

A reserved id shared with a pre-existing account is a real, hard-to-diagnose failure mode: when
ParallelCluster's ``pcluster-admin`` shares its uid with another ``/etc/passwd`` entry, ``su`` and sudo
resolve the uid to whichever name comes first, so the daemons that rely on ``pcluster-admin``'s NOPASSWD
sudoers rules silently run as the wrong user and lose their privileges.
"""

from pcluster_diag.core.constants import RESERVED_GROUP_IDS, RESERVED_USER_IDS
from pcluster_diag.models.check import Check
from pcluster_diag.models.check_error import CheckError
from pcluster_diag.models.context import Context
from pcluster_diag.models.result import Result
from pcluster_diag.util import users


class ReservedUsersHaveUniqueIds(Check):
    """Verify each reserved ParallelCluster user's uid is not shared with any other user.

    A duplicate (non-unique) uid is the root cause behind daemons losing their sudo privileges: the
    kernel resolves a uid to the first matching ``/etc/passwd`` entry, so a reserved user (e.g.
    ``pcluster-admin``) that shares its uid with another account can be resolved to that other name,
    which does not carry the reserved user's NOPASSWD sudoers rules.
    """

    SHARED_UID = "E1"

    @property
    def description(self) -> str:
        """Return the human-readable description of this Check."""
        return "Verify that each reserved ParallelCluster user has a unique uid (not shared with another user)."

    def run(self, context: Context) -> Result:
        """Pass when every present reserved user owns its uid alone; fail listing each shared uid."""
        errors = []
        for name in RESERVED_USER_IDS:
            uid = users.get_user_uid(name)
            if uid is None:
                continue  # absence is ReservedUsersExist's concern
            others = [other for other in users.get_usernames_for_uid(uid) if other != name]
            if others:
                errors.append(
                    CheckError(
                        self.SHARED_UID,
                        "uid {} of reserved user '{}' is also used by: {}. Assign the conflicting "
                        "account(s) a uid outside the range reserved by ParallelCluster ({}).".format(
                            uid, name, ", ".join(others), _reserved_id_range()
                        ),
                    )
                )

        if errors:
            return Result.failure(self, errors=errors)
        return Result.passed(self)


class ReservedGroupsHaveUniqueIds(Check):
    """Verify each reserved ParallelCluster group's gid is not shared with any other group."""

    SHARED_GID = "E1"

    @property
    def description(self) -> str:
        """Return the human-readable description of this Check."""
        return "Verify that each reserved ParallelCluster group has a unique gid (not shared with another group)."

    def run(self, context: Context) -> Result:
        """Pass when every present reserved group owns its gid alone; fail listing each shared gid."""
        errors = []
        for name in RESERVED_GROUP_IDS:
            gid = users.get_group_gid(name)
            if gid is None:
                continue  # absence is ReservedUsersExist's concern
            others = [other for other in users.get_groupnames_for_gid(gid) if other != name]
            if others:
                errors.append(
                    CheckError(
                        self.SHARED_GID,
                        "gid {} of reserved group '{}' is also used by: {}. Assign the conflicting "
                        "group(s) a gid outside the range reserved by ParallelCluster ({}).".format(
                            gid, name, ", ".join(others), _reserved_id_range()
                        ),
                    )
                )

        if errors:
            return Result.failure(self, errors=errors)
        return Result.passed(self)


class ReservedUsersExist(Check):
    """Verify that ParallelCluster's reserved users and groups exist with the ids it assigns.

    Missing reserved users/groups, or ones carrying an unexpected id, indicate the AMI or bootstrap did
    not provision them as ParallelCluster expects. A mismatched ``pcluster-admin`` uid may be intentional
    (set at build time via the ``cluster_admin_user_id`` Chef attribute); the message points that out.
    """

    MISSING_USER = "E1"
    UNEXPECTED_UID = "E2"
    MISSING_GROUP = "E3"
    UNEXPECTED_GID = "E4"

    @property
    def description(self) -> str:
        """Return the human-readable description of this Check."""
        return "Verify that reserved ParallelCluster users and groups exist with their expected uid/gid."

    def run(self, context: Context) -> Result:
        """Pass when every reserved user/group present has its expected id; fail on missing or mismatched ones."""
        errors = []

        for name, expected_uid in RESERVED_USER_IDS.items():
            actual_uid = users.get_user_uid(name)
            if actual_uid is None:
                errors.append(
                    CheckError(
                        self.MISSING_USER, "user '{}' does not exist (expected uid {}).".format(name, expected_uid)
                    )
                )
            elif actual_uid != expected_uid:
                errors.append(
                    CheckError(
                        self.UNEXPECTED_UID,
                        "user '{}' has uid {} but ParallelCluster expects {}. The uid of the cluster admin "
                        "user can be changed at build time via the 'cluster_admin_user_id' Chef attribute, "
                        "so a mismatch there may be intentional.".format(name, actual_uid, expected_uid),
                    )
                )

        for name, expected_gid in RESERVED_GROUP_IDS.items():
            actual_gid = users.get_group_gid(name)
            if actual_gid is None:
                errors.append(
                    CheckError(
                        self.MISSING_GROUP, "group '{}' does not exist (expected gid {}).".format(name, expected_gid)
                    )
                )
            elif actual_gid != expected_gid:
                errors.append(
                    CheckError(
                        self.UNEXPECTED_GID,
                        "group '{}' has gid {} but ParallelCluster expects {}.".format(name, actual_gid, expected_gid),
                    )
                )

        if errors:
            return Result.failure(self, errors=errors)
        return Result.passed(self)


def _reserved_id_range() -> str:
    """Return the inclusive reserved-id range across the reserved user and group ids as ``lo-hi``."""
    ids = list(RESERVED_USER_IDS.values()) + list(RESERVED_GROUP_IDS.values())
    return "{}-{}".format(min(ids), max(ids))
