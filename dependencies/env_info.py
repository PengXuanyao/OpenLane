#!/usr/bin/env python3

# Copyright 2021 Efabless Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import sys
import json
import platform
import subprocess

try:
    from typing import Optional, Any, Dict
except ImportError:
    pass


class StringRepresentable(object):
    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self.__dict__)


class ContainerInfo(StringRepresentable):
    engine = "UNKNOWN"  # type: str
    version = "UNKNOWN"  # type: str
    conmon = False  # type: bool
    rootless = False  # type: bool

    def __init__(self):
        self.engine = "UNKNOWN"
        self.version = "UNKNOWN"
        self.conmon = False
        self.rootless = False

    @staticmethod
    def _try_podman() -> Optional['ContainerInfo']:
        try:
            output = subprocess.check_output(
                ["podman", "info", "--format", "json"]
            ).decode("utf8")
            info = json.loads(output)

            cinfo = ContainerInfo()
            cinfo.engine = "podman"

            # Version
            if "version" in info and "Version" in info["version"]:
                cinfo.version = info["version"]["Version"]
            elif "host" in info and "BuildahVersion" in info["host"]:
                # Fallback: some older podman versions put version in host
                cinfo.version = info["host"].get("BuildahVersion", "UNKNOWN")

            # Conmon
            cinfo.conmon = info.get("host", {}).get("Conmon") is not None

            # Rootless
            cinfo.rootless = info.get("host", {}).get("rootless", False)

            return cinfo
        except Exception:
            return None

    @staticmethod
    def _try_docker() -> Optional['ContainerInfo']:
        try:
            output = subprocess.check_output(
                ["docker", "info", "--format", "{{json .}}"]
            ).decode("utf8")
            info = json.loads(output)

            cinfo = ContainerInfo()
            cinfo.engine = "docker"

            # Version
            try:
                version_output = (
                    subprocess.check_output(["docker", "--version"])
                    .decode("utf8")
                    .strip()
                )
                cinfo.version = re.split(r"\s", version_output)[2].strip(",")
            except Exception:
                pass

            # Conmon: Docker doesn't use conmon, but if somehow present (unlikely), mark it
            # In practice, Docker uses containerd-shim, not conmon
            cinfo.conmon = False

            # Rootless detection via SecurityOptions
            security_options = info.get("SecurityOptions", [])
            for opt in security_options:
                if "rootless" in opt:
                    cinfo.rootless = True
                    break

            return cinfo
        except Exception:
            return None

    @staticmethod
    def get() -> Optional['ContainerInfo']:
        # Try Podman first (more common in rootless/container-focused workflows)
        cinfo = ContainerInfo._try_podman()
        if cinfo is not None:
            return cinfo

        # Fall back to Docker
        cinfo = ContainerInfo._try_docker()
        if cinfo is not None:
            return cinfo

        return None


class OSInfo(StringRepresentable):
    kernel = ""  # type: str
    python_version = ""  # type: str
    kernel_version = ""  # type: str
    distro = None  # type: Optional[str]
    distro_version = None  # type: Optional[str]
    container_info = None  # type: Optional[ContainerInfo]

    def __init__(self):
        self.kernel = platform.system()
        self.python_version = platform.python_version()
        self.kernel_version = platform.release()
        self.distro = None
        self.distro_version = None
        self.container_info = None

    @staticmethod
    def get() -> Optional['OSInfo']:
        osinfo = OSInfo()

        if osinfo.kernel not in ["Linux", "Darwin"]:
            print("Platform %s is unsupported." % osinfo.kernel, file=sys.stderr)
            return None

        if osinfo.kernel == "Darwin":
            osinfo.distro = "macOS"
            osinfo.distro_version = platform.mac_ver()[0]
            try:
                subprocess.check_output(["brew", "--version"], stderr=subprocess.DEVNULL)
                osinfo.package_manager = "brew"
            except Exception:
                osinfo.package_manager = None

        elif osinfo.kernel == "Linux":
            os_release = ""
            for path in ["/etc/os-release", "/etc/lsb-release"]:
                try:
                    with open(path) as f:
                        os_release += f.read()
                except Exception:
                    continue

            if os_release.strip():
                config = {}
                for line in os_release.splitlines():
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"')
                    config[key] = value

                osinfo.distro = config.get("ID") or config.get("DISTRIB_ID")
                osinfo.distro_version = config.get("VERSION_ID") or config.get("DISTRIB_RELEASE")
            else:
                print("Failed to get distribution info.", file=sys.stderr)

        osinfo.container_info = ContainerInfo.get()
        return osinfo


if __name__ == "__main__":
    result = OSInfo.get()
    if result is None:
        sys.exit(1)
    print(result)
