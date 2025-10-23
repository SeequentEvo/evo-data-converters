import os
import shutil
import subprocess
import sys
import urllib
import urllib.request
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


this_dir = Path(__file__).parent.resolve()
sys.path.insert(0, os.path.join(this_dir, "src", "evo", "data_converters", "duf", "common"))
import consts  # noqa: E402


class ABCDEFGHIJIKLBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data) -> None:
        self._install_local_dotnet_sdk()
        self._build_simple_duf()
        self._move_bin_to_package()

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

        os.makedirs(consts.DOTNET_PATH, exist_ok=True)
        urllib.request.urlretrieve(install_source, consts.DOTNET_INSTALL_SCRIPT)

        self._check_script_has_microsoft_cert(consts.DOTNET_INSTALL_SCRIPT)

        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "RemoteSigned",  # Powershell version 5.1 has a default ExecutionPolicy of Restricted
            "-NoLogo",
            "-NoProfile",
            "-File",
            consts.DOTNET_INSTALL_SCRIPT,
            "-InstallDir",
            consts.DOTNET_PATH,
        ]
        subprocess.run(cmd)

    def _build_simple_duf(self):
        cmd = [
            consts.DOTNET_EXE,
            "build",
            "--configuration",
            "Release",
            "--output",
            consts.SIMPLE_DUF_OUTPUT_BIN,
            consts.SIMPLE_DUF_CSHARP_PROJECT_FILE,
        ]
        subprocess.run(cmd)

    def _move_bin_to_package(self):
        source = os.path.join(consts.SIMPLE_DUF_CSHARP_PROJECT_DIR, "bin", "SimpleDuf.dll")
        dest = os.path.join(consts.BIN_PATH, "SimpleDuf.dll")
        if os.path.exists(consts.BIN_PATH):
            shutil.rmtree(consts.BIN_PATH)
        os.makedirs(consts.BIN_PATH)
        shutil.copy(source, dest)
