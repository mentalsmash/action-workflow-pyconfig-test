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
from datetime import datetime, timezone

# Determine release date
DateFormat = "%Y-%m-%dT%H:%M:%SZ"

def add(
    tracks_dir: str,
    track: str,
    version: str,
    created_at: str | None = None,
    files: str | None = None) -> dict:
  # Read release tracks directory
  tracks_dir = Path(tracks_dir.strip())
  track_dir = tracks_dir / track.strip()

  # Read current log contents
  release_log_f = track_dir / "release-log.json"
  release_log = json.loads(release_log_f.read_text())

  created_at = created_at.strip() if created_at else ""
  if created_at:
    created_at = datetime.strptime(created_at, DateFormat)
  else:
    created_at = datetime.now(timezone.utc.strftime(DateFormat))

  # Read release version
  version_id = f"{created_at}__{version.strip()}"

  # Copy release files
  files = files or ""
  files = [Path(f.strip()) for f in files.strip().splitlines()]

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
  # Write log
  release_log_f.write_text(json.dumps(release_log))

  return version_entry
