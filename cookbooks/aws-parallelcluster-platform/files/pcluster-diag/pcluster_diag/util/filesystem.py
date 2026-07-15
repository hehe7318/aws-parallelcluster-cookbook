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

"""Helpers for inspecting filesystem ownership and permissions."""

import grp
import pwd
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PathStat:
    """The ownership and permissions of a filesystem path.

    Attributes:
        owner: The owning user name, or the numeric uid as a string if it has no ``/etc/passwd`` entry.
        group: The owning group name, or the numeric gid as a string if it has no ``/etc/group`` entry.
        mode: The permission bits as a 4-digit octal string (e.g. ``0755``).
    """

    owner: str
    group: str
    mode: str


def stat_path(path: str) -> PathStat:
    """Return the owner, group, and octal mode of ``path``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
    """
    info = Path(path).stat()
    return PathStat(
        owner=_owner_name(info.st_uid),
        group=_group_name(info.st_gid),
        mode=_octal_mode(info.st_mode),
    )


def _owner_name(uid: int) -> str:
    """Return the user name for ``uid``, or the numeric uid as a string if it has no passwd entry."""
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _group_name(gid: int) -> str:
    """Return the group name for ``gid``, or the numeric gid as a string if it has no group entry."""
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def _octal_mode(mode: int) -> str:
    """Return the permission bits of ``mode`` as a 4-digit octal string (e.g. ``0755``)."""
    return format(stat.S_IMODE(mode), "04o")
