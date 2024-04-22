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
import json
import yaml
import shutil
from pathlib import Path

from .find import find

def delete(
    tracks_dir: str,
    track: str,
    version: str,
    created_at: str | None = None,
    match_re: str | None = None) -> None:
  # Read release tracks directory
  tracks_dir = Path(tracks_dir.strip())
  track_dir = tracks_dir / track.strip()

  # Read current log contents
  release_log_f = track_dir / "release-log.json"
  release_log = json.loads(release_log_f.read_text())

  # Find delete candidates
  candidates = find(release_log, version=version, created_at=created_at, match_re=match_re)

  for i, version_id in candidates:
    release_log.pop(i)
    version_dir = track_dir / version_id
    if not version_dir.exists():
      continue
    shutil.rmtree(version_dir)
  
  # Write log
  release_log_f.write_text(json.dumps(release_log))

  # Add release log entry
  print("::group::Deleted Entries")
  print(yaml.safe_dump(candidates))
  print("::endgroup::")
