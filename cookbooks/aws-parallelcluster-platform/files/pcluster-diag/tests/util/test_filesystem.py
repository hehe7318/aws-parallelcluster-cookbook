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

"""Unit tests for the filesystem ownership/permission helpers."""

import grp
import os
import pwd

import pytest

from pcluster_diag.util import filesystem


def test_stat_path_reports_owner_group_and_octal_mode(tmp_path, monkeypatch):
    target = tmp_path / "computefleet-status.json"
    target.write_text("{}", encoding="utf-8")
    os.chmod(target, 0o755)

    monkeypatch.setattr(
        filesystem.pwd, "getpwuid", lambda uid: pwd.struct_passwd(("pcluster-admin", "x", uid, uid, "", "", ""))
    )
    monkeypatch.setattr(filesystem.grp, "getgrgid", lambda gid: grp.struct_group(("pcluster-admin", "x", gid, [])))

    result = filesystem.stat_path(str(target))

    assert result.owner == "pcluster-admin"
    assert result.group == "pcluster-admin"
    assert result.mode == "0755"


def test_stat_path_falls_back_to_numeric_ids_when_names_are_unknown(tmp_path, monkeypatch):
    target = tmp_path / "orphaned"
    target.write_text("x", encoding="utf-8")
    os.chmod(target, 0o640)

    def _no_user(_uid):
        raise KeyError("unknown uid")

    def _no_group(_gid):
        raise KeyError("unknown gid")

    monkeypatch.setattr(filesystem.pwd, "getpwuid", _no_user)
    monkeypatch.setattr(filesystem.grp, "getgrgid", _no_group)

    result = filesystem.stat_path(str(target))

    # With no passwd/group entry, the numeric ids are reported as strings.
    assert result.owner == str(target.stat().st_uid)
    assert result.group == str(target.stat().st_gid)
    assert result.mode == "0640"


def test_stat_path_raises_for_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        filesystem.stat_path(str(tmp_path / "does-not-exist"))
