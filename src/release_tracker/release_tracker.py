###############################################################################
# Copyright 2020-2024 Andrea Sorbini
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
###############################################################################
import yaml
import json
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone

from git_helper import commit as git_commit, config_user as git_config_user

class ReleaseTracker:
  TracksConfigFile = "tracks.yml"
  ReleaseLogFile = "release-log.json"
  DateFormat = "%Y-%m-%dT%H:%M:%SZ"

  def __init__(self,
        repository: str,
        path: str,
        storage_prefix: str = "releases") -> None:
    self.repository = repository.strip()
    self.path = Path(path.strip())
    self.storage_prefix = storage_prefix.strip()
    self.storage = self.path / self.storage_prefix
    self._release_logs = {}
  
  def configure_clone(self, user: tuple[str, str]):
    git_config_user(clone_dir=self.path, user=user)


  def initialize(self,
      tracks: str,
      commit: bool = False,
      push: bool = False) -> None:
    # Load release tracks configuration
    tracks_cfg = yaml.safe_load(tracks.strip())

    # Create base directory and write tracks.yml
    self.storage.mkdir(exist_ok=True, parents=True)

    tracks_yml = self.storage / self.TracksConfigFile
    tracks_yml.write_text(yaml.safe_dump(tracks_cfg))

    # Initialize track directories
    for track in tracks_cfg["tracks"]:
      track_dir = self.storage / track["name"]
      track_dir.mkdir(exist_ok=True)
      track_log = track_dir / self.ReleaseLogFile
      track_log.write_text(json.dumps([]))

    if commit:
      git_commit(
        clone_dir=self.path,
        message="[tracker] initialized",
        untracked=[self.storage],
        push=push)


  def add(self,
      track: str,
      version: str,
      created_at: str | None = None,
      files: str | None = None,
      commit: bool = False,
      push: bool = False) -> dict:
    # Read current log contents
    release_log = self.release_log(track)

    created_at = created_at.strip() if created_at else ""
    if created_at:
      created_at = datetime.strptime(created_at, self.DateFormat)
    else:
      created_at = datetime.now(timezone.utc.strftime(self.DateFormat))

    # Read release version
    version_id = f"{created_at}__{version.strip()}"

    # Copy release files
    files = files or ""
    files = [Path(f.strip()) for f in files.strip().splitlines()]

    track_dir = self.storage / track

    if files:
      version_dir = track_dir / version_id
      version_dir.mkdir(exist_ok=True, parents=True)
      for f_src in files:
        f_dst = version_dir / f_src.name
        shutil.copy2(f_src, f_dst)

    # Add release log entry
    version_entry = {
      "created_at": created_at,
      "files": [f.relative_to(track_dir) for f in files],
      "version": version,
    }
    release_log.append(version_entry)
    self.write_release_log(release_log)

    if commit:
      untracked = []
      if track_dir.exists():
        untracked.append(track_dir)
      git_commit(
        clone_dir=self.path,
        message=f"[tracker][{track}] new version {version_id}",
        untracked=untracked,
        push=push)

    return version_entry


  def release_log(self, track: str) -> list[dict]:
    release_log = self._release_logs.get(track)
    if release_log is not None:
      return release_log
    release_log_f = self.storage / track / self.ReleaseLogFile
    release_log = json.loads(release_log_f.read_text())
    self._release_logs[track] = release_log
    return release_log


  def write_release_log(self, track: str, release_log: list[dict]) -> None:
    release_log_f = self.storage / track / self.ReleaseLogFile
    release_log_f.write_text(json.dumps(release_log))
    self._release_logs[track] = release_log


  def find(self,
      track: str,
      version: str | None = None,
      created_at: str | None = None,
      match_re: str | None = None,
      versions_only: bool=False) -> list[tuple[int, str | dict]]:
    release_log = self.release_log(track)
    # Find candidates
    if match_re:
      # Search by regex
      match_re = re.compile(match_re.strip())
      candidates = [
        (i, release)
        for i, release in enumerate(release_log)
          if match_re.match(f"{release['created_at']}__{release['version']}")
      ]
    else:
      version = version.strip()
      created_at = created_at.strip()
      version_suffix = f"__{version}"
      candidates = [
        (i, release)
        for i, release in enumerate(release_log)
        if release["version"].endswith(version_suffix)
          and (
            not created_at
            or release["version"].startswith(created_at)
          )
      ]
    if versions_only:
      return candidates
    return [
      (i, release["version"])
        for i, release in candidates
    ]


  def delete(self,
      track: str,
      version: str,
      created_at: str | None = None,
      match_re: str | None = None,
      commit: bool = False,
      push: bool = False) -> list[tuple[int, str]]:
    # Read current log contents
    release_log = self.release_log(track)

    # Find delete candidates
    candidates = self.find(
      track=track,
      version=version,
      created_at=created_at,
      match_re=match_re,
      versions_only=True)

    track_dir = self.storage / track

    for i, version_id in candidates:
      release_log.pop(i)
      version_dir = track_dir / version_id
      if not version_dir.exists():
        continue
      shutil.rmtree(version_dir)

    self.write_release_log(track, release_log)

    if commit:
      git_commit(
        clone_dir=self.path,
        message=f"[tracker][{track}] deleted {len(candidates)} versions",
        push=push)

    return candidates

