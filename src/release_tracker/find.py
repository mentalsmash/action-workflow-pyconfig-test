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
import re
import json
from pathlib import Path

def find(
    release_log: list[dict] = None,
    version: str | None = None,
    created_at: str | None = None,
    match_re: str | None = None,
    tracks_dir: str | None = None,
    track: str | None = None) -> list[tuple[int, str | dict]]:
  load_log = release_log is None
  if load_log:
    # Read release tracks directory
    tracks_dir = Path(tracks_dir.strip())
    track_dir = tracks_dir / track.strip()
    # Read current log contents
    release_log_f = track_dir / "release-log.json"
    release_log = json.loads(release_log_f.read_text())

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
  
  if load_log:
    return candidates
  return [
    (i, release["version"])
      for i, release in candidates
  ]

