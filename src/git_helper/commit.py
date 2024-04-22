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

def commit(clone_dir: Path, message: str, user: tuple[str, str] | None = None, untracked: list[Path] | None = None, push: bool=True) -> None:
  if user:
    user_name, user_email = user
    subprocess.run([
      "git", "config", "--global", "user.name", user_name
    ], check=True, cwd=clone_dir)
    subprocess.run([
      "git", "config", "--global", "user.email", user_email
    ], check=True, cwd=clone_dir)
  for file in untracked:
    subprocess.run([
      "git", "add", file
    ], check=True, cwd=clone_dir)
  subprocess.run([
    "git", "commit", "-am", message,
  ], check=True, cwd=clone_dir)
  if push:
    subprocess.run([
      "git", "push",
    ], check=True, cwd=clone_dir)
