import os
import subprocess
import urllib
import urllib.request

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class ABCDEFGHIJIKLBuildHook(BuildHookInterface):
    PLUGIN_NAME = 'custom'

    @property
    def dotnet_path(self):
        return os.path.join(self.root, ".dotnet")

    @property
    def dotnet_install_script(self):
        return os.path.join(self.dotnet_path, "dotnet-install.ps1")

    @property
    def dotnet_exe(self):
        return os.path.join(self.dotnet_path, "dotnet.exe")

    @property
    def simple_duf_csharp_project_dir(self):
        return os.path.join(self.root, "csharp", "SimpleDuf")

    @property
    def simple_duf_csharp_project_file(self):
        return os.path.join(self.simple_duf_csharp_project_dir, "duf.csproj")

    @property
    def simple_duf_output_bin(self):
        return os.path.join(self.simple_duf_csharp_project_dir, "bin")

    def initialize(self, version: str, build_data) -> None:
        self._install_local_dotnet_sdk()
        self._build_simple_duf()
    def _install_local_dotnet_sdk(self):
        install_source = "https://dot.net/v1/dotnet-install.ps1"

        os.makedirs(self.dotnet_path, exist_ok=True)
        urllib.request.urlretrieve(install_source, self.dotnet_install_script)

        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-NoLogo",
            "-NoProfile",
            "-File",
            self.dotnet_install_script,
            "-InstallDir",
            self.dotnet_path,
        ]
        subprocess.run(cmd)

    def _build_simple_duf(self):
        cmd = [
            self.dotnet_exe,
            "build",
            "--configuration",
            "Release",
            "--output",
            self.simple_duf_output_bin,
            self.simple_duf_csharp_project_file
        ]
        subprocess.run(cmd)
