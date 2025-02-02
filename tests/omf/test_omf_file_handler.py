from os import path
from pathlib import Path
from unittest import TestCase

from evo.data_converters.omf import OmfReaderContext


class TestOmfReaderContext(TestCase):
    def test_should_load_omfv1_file_as_v2(self) -> None:
        omf_filepath = path.join(path.dirname(__file__), "data/pointset_v1.omf")
        context = OmfReaderContext(omf_filepath)

        temp_file_exists = Path(context.temp_file().name).exists()
        self.assertTrue(temp_file_exists, "Expected to find a temporary file, but found none.")

    def _omf_temp_file_path(self, omf_file: str) -> str:
        context = OmfReaderContext(omf_file)
        filepath: str = context.temp_file().name
        return filepath

    def test_should_automatically_delete_temp_file_after_use(self) -> None:
        omf_file = path.join(path.dirname(__file__), "data/pointset_v1.omf")

        temp_file_path = self._omf_temp_file_path(omf_file)

        temp_file_exists = Path(temp_file_path).exists()
        self.assertFalse(temp_file_exists, "Temporary file should have been deleted, but it still exists.")
