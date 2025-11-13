import os
import subprocess
import urllib
import urllib.request

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class ABCDEFGHIJIKLBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

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

    @staticmethod
    def _check_script_has_microsoft_cert(script: str):
        """
        Raises PermissionError if the cert does not belong to Microsoft Corporation. It doesn't check that the cert is
        valid. That's left to `-ExecutionPolicy RemoteSigned`.
        """
        # This powershell command grabs the "CN" value from the "Subject" field of the certificate. It shows as
        # "Microsoft Corporation", which is assumed to be stable and secure.
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-AuthenticodeSignature {script}).SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)",
        ]
        name = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        expected = "Microsoft Corporation"
        if name != expected:
            script_name = os.path.basename(script)
            msg = f"Unexpected name on the certificate of {script_name}. Expected: {expected}, Got: {name}"
            raise PermissionError(msg)

    def _install_local_dotnet_sdk(self):
        install_source = "https://dot.net/v1/dotnet-install.ps1"

        os.makedirs(self.dotnet_path, exist_ok=True)
        urllib.request.urlretrieve(install_source, self.dotnet_install_script)

        self._check_script_has_microsoft_cert(self.dotnet_install_script)

        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "RemoteSigned",  # Powershell version 5.1 has a default ExecutionPolicy of Restricted
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
            self.simple_duf_csharp_project_file,
        ]
        subprocess.run(cmd)
