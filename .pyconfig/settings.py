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
from pathlib import Path
from typing import NamedTuple

from pyconfig import extract_registries, tuple_to_dict, merge_dicts

###############################################################################
#
###############################################################################
def settings(clone_dir: Path, cfg: NamedTuple, github: NamedTuple) -> dict:
  repo_org, repo = github.repository.split("/")

  #############################################################################
  # Debian packaging settings
  #############################################################################
  debian_builder_base_images_matrix = json.dumps(cfg.debian.builder.base_images)
  debian_builder_docker_build_platforms = ",".join(
    [f"linux/{arch}" for arch in cfg.debian.builder.architectures]
  )
  debian_builder_registries = extract_registries(
    repo_org,
    [
      cfg.debian.builder.repo,
      *cfg.debian.builder.base_images,
    ],
  )
  debian_builder_architectures_matrix = json.dumps(cfg.debian.builder.architectures)

  #############################################################################
  # CI infrastructure settings
  #############################################################################
  admin_repo = cfg.ci.images.admin.image.split(":")[0]
  admin_tag = cfg.ci.images.admin.image.split(":")[-1]
  admin_registries = extract_registries(
    repo_org,
    [
      cfg.ci.images.admin.image,
      cfg.ci.images.admin.base_image,
    ],
  )
  admin_build_platforms_config = ",".join(cfg.ci.images.admin.build_platforms)

  #############################################################################
  # Output generated settings
  #############################################################################
  return {
    ###########################################################################
    # CI config
    ###########################################################################
    "ci": merge_dicts(
      {
        "images": {
          "admin": {
            "login": {
              "dockerhub": "dockerhub" in admin_registries,
              "github": "github" in admin_registries,
            },
            "repo": admin_repo,
            "tag": admin_tag,
            "tags_config": admin_tag,
            "build_platforms_config": admin_build_platforms_config,
          },
        },
      },
      tuple_to_dict(cfg.ci),
    ),
    ###########################################################################
    # Debian config
    ###########################################################################
    "debian": merge_dicts(
      {
        "builder": {
          "base_images_matrix": debian_builder_base_images_matrix,
          "architectures_matrix": debian_builder_architectures_matrix,
          "build_platforms_config": debian_builder_docker_build_platforms,
          "login": {
            "dockerhub": "dockerhub" in debian_builder_registries,
            "github": "github" in debian_builder_registries,
          },
        },
      },
      tuple_to_dict(cfg.debian),
    ),
  }
