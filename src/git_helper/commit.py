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
import subprocess
from pathlib import Path

from cli_helper.log import log

from .config_user import config_user

def commit(clone_dir: Path, message: str, user: tuple[str, str] | None = None, untracked: list[Path] | None = None, push: bool=True) -> None:
  if user:
    config_user(clone_dir, user, config_global=False)

  for file in (untracked or []):
    cmd = ["git", "add", file]
    log.command(cmd)
    subprocess.run(cmd, check=True, cwd=clone_dir)

  cmd = ["git", "commit", "-am", message,]
  log.command(cmd)
  subprocess.run(cmd, check=True, cwd=clone_dir)
  if push:
    cmd = ["git", "push",]
    log.command(cmd)
    subprocess.run(cmd, check=True, cwd=clone_dir)
