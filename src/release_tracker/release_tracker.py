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
import sys
import yaml
import json
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone

from git_helper import commit as git_commit, config_user as git_config_user
from docker_helper import inspect as inspect_docker
from cli_helper.log import log
from cli_helper.inline_yaml import inline_yaml_load

class ReleaseTracker:
  TracksConfigFile = "tracks.yml"
  ReleaseLogFile = "release-log.json"
  DateFormat = "%Y-%m-%dT%H:%M:%SZ"
  DefaultTracks = """
tracks:
  - name: nightly
  - name: stable
"""

  @classmethod
  def define_parser(cls) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("release-tracker")    
    parser.set_defaults(action=None)

    parser.add_argument(
      "-r",
      "--repository",
      help="Name of the tracker repository.",
      required=True
    )

    parser.add_argument(
      "-p",
      "--path",
      help="Local clone of the tracker repository.",
      default=Path.cwd(),
      type=Path
    )

    parser.add_argument(
      "-s",
      "--storage",
      help="Subdirectory within the repository where this tracker's storage is located.",
      default="releases",
    )

    parser.add_argument("-C", "--commit",
      help="Commit changes to the local repository",
      default=False,
      action="store_true")

    parser.add_argument("-P", "--push",
      help="Push changes to the remote repository. Implies --commit.",
      default=False,
      action="store_true")

    subparsers = parser.add_subparsers(dest="action")


    parser_config_clone = subparsers.add_parser(
      "config-clone", help=""
    )
    parser_config_clone.add_argument("-n", "--name",
      help="git user name",
      required=True)
    parser_config_clone.add_argument("-e", "--email",
      help="git user email",
      required=True)


    parser_initialize = subparsers.add_parser(
      "init", help=""
    )
    parser_initialize.add_argument("-T", "--tracks",
      help="Tracks configuration file as an inline string or an external file",
      default=None)


    parser_add = subparsers.add_parser(
      "add", help=""
    )
    parser_add.add_argument("-t", "--track",
      help="Target release track",
      required=True)
    parser_add.add_argument("-c", "--created-at",
      metavar="",
      help="Creation timestamp for the new version.",
      default=None)
    parser_add.add_argument("-f", "--file",
      default=[],
      action="append",
      help="A file to store for the new version.")
    parser_add.add_argument("-V", "--version",
      help="Label for the new version")


    parser_add_docker = subparsers.add_parser(
      "add-docker", help=""
    )
    parser_add_docker.add_argument("-t", "--track",
      help="Target release track",
      required=True)
    parser_add_docker.add_argument("-c", "--created-at",
      metavar="",
      help="Creation timestamp for the new version.",
      default=None)
    parser_add_docker.add_argument("-i", "--image",
      default=[],
      action="append",
      help="A docker image included in the new version.")
    parser_add_docker.add_argument("-V", "--version",
      help="Label for the new version")

    parser_find = subparsers.add_parser(
      "find", help=""
    )
    parser_find.add_argument("-t", "--track",
      help="Target release track",
      required=True)
    parser_find.add_argument("-c", "--created-at",
      metavar="",
      help="Match based on creation timestamp.",
      default=None)
    parser_find.add_argument("-V", "--version",
      help="Match based on version label.",
      default=None)
    parser_find.add_argument("-R", "--regex",
      help="Match based on a regular expression.",
      default=None)
    parser_find.add_argument("--compact",
      help="Print only layer hashes insted of full manifests.",
      default=False,
      action="store_true")

    parser_del = subparsers.add_parser(
      "del", help=""
    )
    parser_del.add_argument("-t", "--track",
      help="Target release track",
      required=True)
    parser_del.add_argument("-c", "--created-at",
      metavar="",
      help="Match based on creation timestamp.",
      default=None)
    parser_del.add_argument("-V", "--version",
      help="Match based on version label.",
      default=None)
    parser_del.add_argument("-R", "--regex",
      help="Match based on a regular expression.",
      default=None)

    return parser

  @classmethod
  def main(cls) -> None:
    parser = cls.define_parser()
    args = parser.parse_args()

    if not args.action:
      log.error("no action specified")
      parser.print_help()
      sys.exit(1)

    tracker = ReleaseTracker(
      repository=args.repository,
      path=args.path,
      storage=args.storage)

    if args.action == "config-clone":
      tracker.configure_clone(user=(args.name, args.email))
    elif args.action == "init":
      tracks = inline_yaml_load(args.tracks) if args.tracks else ""
      tracker.initialize(
        tracks=tracks,
        commit=args.commit,
        push=args.push)
    elif args.action == "add":
      tracker.add(
        track=args.track,
        version=args.version,
        created_at=args.created_at,
        files="\n".join(map(str, args.file)),
        commit=args.commit,
        push=args.push)
    elif args.action == "add-docker":
      tracker.add_docker(
        track=args.track,
        version=args.version,
        created_at=args.created_at,
        images="\n".join(map(str, args.image)),
        commit=args.commit,
        push=args.push)
    elif args.action == "find":
      matched = tracker.find(
        track=args.track,
        version=args.version,
        created_at=args.created_at,
        match_re=args.regex)
      print(yaml.safe_dump(matched))
    elif args.action == "del":
      tracker.delete(
        track=args.track,
        version=args.version,
        created_at=args.created_at,
        match_re=args.regex,
        commit=args.commit,
        push=args.push)
    else:
      raise RuntimeError("action not implemented", args.action)


  @classmethod
  def version_id(cls, created_at: str, version: str) -> str:
    return f"{created_at.strip()}__{version.strip()}"


  def __init__(self,
        repository: str,
        path: str | Path,
        storage: str = "releases") -> None:
    self.repository = repository.strip()
    self.path = Path(str(path).strip())
    self.storage = self.path / storage.strip()
    self._release_logs = {}
  
  def configure_clone(self, user: tuple[str, str]):
    git_config_user(clone_dir=self.path, user=user)


  def initialize(self,
      tracks: str,
      commit: bool = False,
      push: bool = False) -> None:
    # Load release tracks configuration
    tracks = tracks.strip()
    if not tracks:
      tracks = self.DefaultTracks
    tracks_cfg = yaml.safe_load(tracks)

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
        untracked=[self.storage.relative_to(self.path)],
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
      created_at = datetime.now(timezone.utc).strftime(self.DateFormat)

    # Read release version
    version_id = self.version_id(created_at, version)

    # Copy release files
    files = files or ""
    files = [Path(f.strip()) for f in files.strip().splitlines()]

    track_dir = self.storage / track

    version_files = []
    if files:
      version_dir = track_dir / version_id
      version_dir.mkdir(exist_ok=True, parents=True)
      for f_src in files:
        f_dst = version_dir / f_src.name
        shutil.copy2(f_src, f_dst)
        version_files.append(f_dst)

    # Add release log entry
    version_entry = {
      "created_at": created_at,
      "files": [str(f.relative_to(track_dir)) for f in version_files],
      "version": version,
    }
    release_log.append(version_entry)
    self.write_release_log(track, release_log)

    log.info("ADDED {}", version_id)

    if (commit or push):
      untracked = []
      if track_dir.exists():
        untracked.append(track_dir.relative_to(self.path))
      git_commit(
        clone_dir=self.path,
        message=f"[tracker][{track}][new][{version}] {created_at}",
        untracked=untracked,
        push=push)
      log.info("changes COMMITED{}", "" if not push else " and PUSHED")

    return version_entry


  def add_docker(self,
      track: str,
      version: str,
      images: str,
      created_at: str | None = None,
      commit: bool = False,
      push: bool = False) -> dict:
    import tempfile
    tmp_h = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_h.name)
    manifest = tmp_dir / "docker-manifests.json"
    inspect_docker(images, manifest)
    self.add(
      track=track,
      version=version,
      files="\n".join(map(str, [
        manifest,
      ])),
      created_at=created_at,
      commit=commit,
      push=push)


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
    release_log_f.write_text(json.dumps(release_log, indent=2))
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
          if match_re.match(
              self.version_id(release["created_at"], release["version"]))
      ]
    else:
      created_at = created_at or ""
      version = version or ""
      created_at, version_suffix = self.version_id(created_at, version).split("__")
      candidates = [
        (i, release)
        for i, release in enumerate(release_log)
        if release["version"].endswith(version_suffix)
          and (
            not created_at
            or release["created_at"] == created_at
          )
      ]
    if not versions_only:
      return candidates
    return [
      (i, self.version_id(release["created_at"], release["version"]))
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

    popped = 0
    for i, version_id in candidates:
      release_log.pop(i - popped)
      popped += 1
      version_dir = track_dir / version_id
      if not version_dir.exists():
        continue
      shutil.rmtree(version_dir)
      log.info("DELETED {}", version_id)

    self.write_release_log(track, release_log)

    if popped and (commit or push):
      git_commit(
        clone_dir=self.path,
        message=f"[tracker][{track}][del] {len(candidates)} versions",
        push=push)
      log.info("changes COMMITED{}", "" if not push else " and PUSHED")
    else:
      log.warning("nothing changed")
      if (commit or push):
        raise RuntimeError("nothing changed")

    return candidates

