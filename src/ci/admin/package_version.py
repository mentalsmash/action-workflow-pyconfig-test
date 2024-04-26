import subprocess
from typing import NamedTuple, Generator, TextIO
from datetime import datetime, timedelta, timezone
from functools import partial
import json

from .data_object import DataObject, parse, build
from .gh_api import gh_api
from .fzf import fzf_filter

from cli_helper.log import log

###############################################################################
# GitHub PackageVersion data object (parsed from query result)
###############################################################################
class PackageVersion(NamedTuple):
  id: str
  name: str
  tags: str
  created_at: datetime
  updated_at: datetime

  DatetimeFields = [3, 4]
  DefaultMaxAge = timedelta(days=30)

  def __str__(self) -> str:
    return DataObject.str(self)

  ###############################################################################
  # List package versions
  ###############################################################################
  @classmethod
  def select(
    cls,
    package: str,
    org: str | None = None,
    filter: str | None = None,
    tags: list[str] | None = None,
    package_type: str = "container",
    prompt: str | None = None,
    noninteractive: bool = False,
    versions: list["PackageVersion"] | None = None,
    skip_last_tagged: bool = False
  ) -> list["PackageVersion"]:
    def _ls_versions() -> Generator[PackageVersion, None, None]:
      jq_filter = "[ (.[] | [.id, .name, .metadata.container.tags, .created_at, .updated_at]) ]"
      url = (
        f"/orgs/{org}/packages/{package_type}/{package}/versions"
        if org
        else f"/user/packages/{package_type}/{package}/versions"
      )
      versions = gh_api(url, jq_filter, default=[])
      for version_entry in versions:
        version = build(cls, *version_entry)
        yield version

    def _read_and_parse_versions(input_stream: TextIO) -> list[PackageVersion]:
      return [
        pkg
        for line in input_stream.readlines()
        for sline in [line.decode().strip()]
        if sline
        for pkg in [parse(cls, sline)]
        if pkg
      ]

    if versions is None:
      versions = list(_ls_versions())

    package_label = package if not org else f"{org}/{package}"

    if not versions:
      log.warning("[{}] no versions detected", package_label)
      return []

    if prompt is None:
      prompt = f"available versions for {package}"
    tags = tags or []
    tags_filter = " ".join([
      f"'{tag}'" for tag in tags
    ]) if tags else ""

    filter = filter or ""
    filter = f"{filter}{' ' + tags_filter if tags_filter else ''}"

    sort_versions = partial(sorted, key=lambda p: p.updated_at)
    fzf = fzf_filter(
      filter=filter,
      inputs=sort_versions(versions),
      prompt=prompt,
      noninteractive=noninteractive,
    )
    result = sort_versions(_read_and_parse_versions(fzf.stdout))
    if skip_last_tagged and result:
      latest = next((version for version in reversed(result) if version.tags and version.tags != "[]"), None)
      if latest:
        log.warning("[{}] preserving most recently tagged version: {}", package_label, latest)
        result.remove(latest)
    return result

  ###############################################################################
  # Delete package versions
  ###############################################################################
  @classmethod
  def delete(
    cls,
    package: str,
    org: str | None = None,
    filter: str | None = None,
    package_type: str = "container",
    prompt: str | None = None,
    noninteractive: bool = False,
    noop: bool = False,
    versions: list["PackageVersion"] | None = None,
    if_package_exists: bool = False,
    repository: str | None = None,
    skip_last_tagged: bool = False
  ) -> list["PackageVersion"]:
    if if_package_exists:
      # Check if the package exists, otherwise return without an error
      from .package import Package
      filter = f"'{package} "
      if repository:
        filter = f"'{repository} {filter}"
      packages = Package.select(org=org, filter=filter, package_type=package_type, noninteractive=True)
      package_o = next((pkg for pkg in packages if pkg.name == package), None)
      if package_o is None:
        package_label = package if not org else f"{org}/{package}"
        log.warning("[{}] skipping version delete because package doesn't exist", package_label)
        return []

    def _delete_version(version: PackageVersion):
      url = (
        f"/orgs/{org}/packages/{package_type}/{package}/versions/{version.id}"
        if org
        else f"/user/packages/{package_type}/{package}/versions/{version.id}"
      )
      delete_cmd = ["gh", "api", "-X", "DELETE", url]
      log.command(delete_cmd, check=True)
      subprocess.run(delete_cmd, check=True)

    package_label = package if not org else f"{org}/{package}"
    deleted = []
    if prompt is None:
      prompt = "version to delete"

    to_be_deleted = cls.select(
      package=package,
      org=org,
      filter=filter,
      package_type=package_type,
      prompt=prompt,
      noninteractive=noninteractive,
      versions=versions,
      skip_last_tagged=skip_last_tagged
    )

    for version in to_be_deleted:
      if not noop:
        _delete_version(version)
      deleted.append(version)
    if noop:
      log.warning(
        "[{}] {} version selected but not actually deleted",
        package_label,
        len(deleted),
      )
    else:
      log.warning("[{}] {} runs DELETED", package_label, len(deleted))
    return deleted

  ###############################################################################
  # Prune Untagged
  ###############################################################################
  @classmethod
  def prune_untagged(
    cls,
    package: str,
    org: str | None = None,
    min_age: timedelta | None = None,
    package_type: str = "container",
    noop: bool = False,
  ) -> list["PackageVersion"]:
    owner = org or "user"

    tagged_versions = cls.select(package, org, filter="![] ", package_type=package_type)
    tagged_names = [v.name for v in tagged_versions]
    # Multi-platform Docker images will report only the top-level manifest as tagged.
    # We must inspect the manifest with `docker buildx imagetools` to retrieve the
    # hashes of all associated layers
    if package_type == "container":
      assert org is not None, "an organization is required"
      tagged_layers = [layer
        for manifest in tagged_versions
        for layer in cls._inspect_docker_manifest(package, org, manifest)]
      tagged_names.extend(tagged_layers)
      tagged_names = sorted(set(tagged_names))
  
    untagged_versions = [
      v
      for v in cls.select(package, org, filter="'[] ", package_type=package_type)
      if v.name not in tagged_names
    ]

    if min_age:
      log.info("[{}][{}] considering only versions older than {}", owner, package, min_age)
      now = datetime.now(timezone.utc)
      prunable = [version for version in untagged_versions if (now - version.updated_at) >= min_age]
    else:
      prunable = untagged_versions

    log.info("[{}][{}] {} prunable versions", owner, package, len(prunable))
    for i, version in enumerate(prunable):
      log.info(" {}. {}", i + 1, version)
    
    log.info("[{}][{}] {} retained tagged versions", owner, package, len(tagged_versions))
    for i, version in enumerate(tagged_versions):
      log.info(" {}. {}", i + 1, version)
    
    log.info("[{}][{}] {} total retained versions", owner, package, len(tagged_names))
    for i, version in enumerate(tagged_names):
      log.info(" {}. {}", i + 1, version)

    return cls.delete(
      package=package, org=org, package_type=package_type, versions=prunable, noop=noop
    )

  @classmethod
  def _inspect_docker_manifest(cls,
      package: str,
      org: str,
      manifest: "PackageVersion") -> list[str]:
    # tags is a Python string array encoded in a string
    tags = eval(manifest.tags)
    manifest_label = next(iter(tags))
    manifest_image = f"ghcr.io/{org}/{package}:{manifest_label}"
    cmd = [
      f"docker buildx imagetools inspect {manifest_image} --raw | "
      "jq -r \".manifests[].digest\""
    ]
    log.command(cmd)
    result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE)
    if not result.stdout:
      raise RuntimeError("failed to detect layers for manifest", manifest_image)
    layers = {
      layer
      for layer in result.stdout.decode().strip().splitlines()
      for layer in [layer.strip()] if layer
    }
    return list(layers)

