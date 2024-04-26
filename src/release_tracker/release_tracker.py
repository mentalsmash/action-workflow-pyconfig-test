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
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import NamedTuple
from enum import Enum

from git_helper import commit as git_commit, config_user as git_config_user
from docker_helper import inspect as inspect_docker
from cli_helper.log import log
from cli_helper.inline_yaml import inline_yaml_load

class PrunePolicy(Enum):
  LATEST = 0
  UNIQUE = 1


class ReleaseTrack(NamedTuple):
  name: str
  prune_policy: PrunePolicy
  prune_max_age: int


class ReleaseTracker:
  TracksConfigFile = "tracks.yml"
  ReleaseLogFile = "release-log.json"
  DateFormat = "%Y-%m-%dT%H:%M:%SZ"
  DefaultTracks = """
tracks:
  - name: nightly
    prune-policy: latest
    prune-max-age: 0
  - name: stable
    prune-policy: unique
    prune-max-age: 0
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


    parser_find_prunable = subparsers.add_parser(
      "find-prunable", help=""
    )
    parser_find_prunable.add_argument("-t", "--track",
      help="Target release track",
      required=True)
    parser_find_prunable.add_argument("-m", "--layer",
      help="A tagged layer. Use - to read the list from stdin",
      default=[],
      action="append")
    parser_find_prunable.add_argument(
      "-a",
      "--max-age",
      help='Maximum number of days since the version was created to consider if "prunable" (floating point number).',
      default=None,
      type=float,
    )


    _parser_find_prunable_docker = subparsers.add_parser(
      "find-prunable-docker", help=""
    )

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
    elif args.action == "find-prunable-docker":
      (prunable_versions,
       prunable_layers,
       unprunable_versions,
       unprunable_layers) = tracker.find_prunable_docker_layers()
      for layer in prunable_layers:
        print("-", layer)
      for layer in unprunable_layers:
        print("+", layer)
    elif args.action == "find-prunable":
      prunable = tracker.find_prunable(track=args.track)
      for pruned in prunable:
        print(pruned)
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
    tracks_yml = self.storage / self.TracksConfigFile
    self.tracks: dict[str, ReleaseTrack] = (
      {} if not tracks_yml.exists()
      else self.load_tracks(yaml.safe_load(tracks_yml.read_text()))
    )

  @classmethod
  def load_tracks(cls, tracks: list[dict]) -> dict:
    return {
      t["name"]: {
        ReleaseTrack(
          name=t["name"],
          prune_policy=PrunePolicy[t.get("prune-policy", "unique").upper()],
          prune_max_age=t.get("prune-max-age", 0))
      } for t in tracks
    }

  @classmethod
  def serialize_tracks(cls, tracks: dict[str, ReleaseTrack]) -> list[dict]:
    return {
      "tracks": [
        {
          "name": t.name,
          "prune-policy": t.prune_policy.name.lower(),
          "prune-max-age": t.prune_max_age,
        } for t in sorted(tracks.values(), key=lambda t: t.name)
      ]
    }

  def configure_clone(self, user: tuple[str, str]):
    git_config_user(clone_dir=self.path, user=user)

  def initialize(self,
      project_repo: str,
      tracks: str,
      commit: bool = False,
      push: bool = False) -> None:
    # Load release tracks configuration
    tracks = tracks.strip()
    if not tracks:
      tracks = self.DefaultTracks
    self.tracks = self.load_tracks(yaml.safe_load(tracks))

    # Create base directory and write tracks.yml
    self.storage.mkdir(exist_ok=True, parents=True)

    tracks_yml = self.storage / self.TracksConfigFile
    tracks_yml.write_text(self.serialize_tracks(self.tracks))

    # Initialize track directories
    for track in self.tracks.keys():
      track_dir = self.storage / track.name
      track_dir.mkdir(exist_ok=True)
      track_log = track_dir / self.ReleaseLogFile
      track_log.write_text(json.dumps([]))

    if (commit or push):
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
      hashes: str,
      created_at: str | None = None,
      commit: bool = False,
      push: bool = False) -> dict:
    tmp_h = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp_h.name)
    manifest = tmp_dir / "docker-manifests.json"
    inspect_docker(images, hashes, manifest)
    return self.add(
      track=track,
      version=version,
      files="\n".join(map(str, [
        manifest,
      ])),
      created_at=created_at,
      commit=commit,
      push=push)


  def find_prunable(self,
      track: str
    ) -> list[str]:
    def _find_prunable_unique():
      # Keep the most recent release for every version
      versions_by_id = {}
      for version in self.release_log(track):
        version_id = self.version_id(version["created_at"], version["version"])
        vid_versions = versions_by_id[version_id] = versions_by_id.get(version_id, [])
        vid_versions.append(version_id)
      return sorted({
        vid
        for versions in versions_by_id.items()
        for vid in versions[:-1] # skip most recent recent release for every version
      })

    def _find_prunable_latest():
      # Keep only the most recent release for the track
      return sorted({
        vid
        for version in self.release_log(track)[:-1]
        for vid in [self.version_id(version["created_at"], version["version"])]
      })

    track_cfg = self.tracks[track]
    log.info("[{}] pruning with policy: {}", track, track_cfg.prune_policy)
    if track_cfg.prune_policy == "unique":
      prunable = _find_prunable_unique()
    else:
      prunable = _find_prunable_latest()
    
    if track_cfg.prune_max_age > 0:
      max_age = timedelta(days=track_cfg.prune_max_age)
      old_enough = []
      now = datetime.now()
      for version_id in prunable:
        v_date = datetime.strptime(version_id[:version_id.index("__")], self.DateFormat)
        if now - v_date < max_age:
          continue
        old_enough.append(version_id)
      prunable = old_enough

    return prunable


  def find_prunable_docker_layers(self) -> tuple[list[str], list[str]]:
    def _load_layers(track_dir: Path, version_id: str) -> list[str]:
      version_dir = track_dir / version_id
      docker_manifests_f = version_dir / "docker-manifests.json"
      if not docker_manifests_f.exists():
        log.debug("[{}][{}] not a docker release", version_id)
        return set()
      docker_manifests = json.loads(docker_manifests_f.read_text())
      return set(docker_manifests["layers"].keys())

    prunable_versions = {}
    for track in self.tracks.keys():
      track_versions = self.find_prunable(track)
      if not track_versions:
        log.warning("[{}] no prunable versions specified nor detected", track)
        continue
      prunable_versions[track] = track_versions

    prunable_docker_versions = set()
    unprunable_layers = set()
    unprunable_docker_versions = set()

    for track, track_versions in prunable_versions.items():
      track_dir = self.storage / track
      for version_entry in self.release_log(track):
        version_id = self.version_id(version_entry["created_at"], version_entry["version"])
        v_layers = _load_layers(track_dir, version_id)
        if not v_layers:
          continue
        log.debug("[{}][{}] inspecting version ({} layers)", track, version_id, len(v_layers))
        if version_id not in prunable_versions:
          unprunable_layers = unprunable_layers | v_layers
          unprunable_docker_versions.add(version_id)
        else:
          prunable_docker_versions.add(version_id)
    
    prunable_layers = {
      layer
      for version_id in prunable_docker_versions
        for layer in _load_layers(version_id)
          if layer not in unprunable_layers
    }
    log.info("[{}] {} prunable layers from {} docker versions", track, len(prunable_docker_versions), len(prunable_layers))
    log.info("[{}] {} unprunable layers from {} docker versions", track, len(unprunable_docker_versions), len(unprunable_layers))
    
    return (prunable_docker_versions, prunable_layers, unprunable_docker_versions, unprunable_layers)


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
      versions_only: bool=False,
      entries: str | None = None) -> list[tuple[int, str | dict]]:
    release_log = self.release_log(track)

    match_re = (match_re or "").strip()
    version = (version or "").strip()
    created_at = (created_at or "").strip()
    entries = (entries or "").strip()

    # Find candidates
    if entries:
      candidates = [
        (i, release)
        for i, release in enumerate(release_log)
          for vid in [self.version_id(release["created_at"], release["version"])]
            if vid in entries
      ]
    elif match_re:
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
      entries: str | None = None,
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
      versions_only=True,
      entries=entries)

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

