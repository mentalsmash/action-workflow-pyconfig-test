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
from pathlib import Path


def initialize(tracks: str, tracks_dir: str) -> None:
  # Load release tracks configuration
  tracks_cfg = yaml.safe_load(tracks.strip())

  # Create base directory and write tracks.yml
  tracks_dir = Path(tracks_dir.strip())
  tracks_dir.mkdir(exist_ok=True, parents=True)

  tracks_yml = tracks_dir / "tracks.yml"
  tracks_yml.write_test(yaml.safe_dump(tracks_cfg))

  # Initialize track directories
  for track in tracks_cfg["tracks"]:
    track_dir = tracks_dir / track["name"]
    track_dir.mkdir(exist_ok=True)

    track_log = track_dir / "release-log.json"
    track_log.write_text(json.safe_dump([]))

