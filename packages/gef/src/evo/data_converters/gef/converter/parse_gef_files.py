#  Copyright © 2025 Bentley Systems, Incorporated
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#      http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from pathlib import Path

import evo.logging

from pygef.broxml.parse_cpt import read_cpt as read_cpt_xml
from pygef import read_cpt
from pygef.cpt import CPTData

logger = evo.logging.getLogger("data_converters")


def parse_gef_file(filepath: str | Path, replace_column_voids=False) -> list[CPTData]:
    """Parse a single GEF-CPT or GEF-XML file.

    :param filepath: Path to the file to parse.
    :param replace_column_voids: (Default value = False) Whether to interpolate void values
    :return: List of CPTData objects. GEF files contain a single CPTData object. XML files may
                contain multiple CPTData objects.
    """
    try:
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        ext = Path(filepath).suffix.lower()

        if ext == ".xml":
            # No method in pygef to detect type, so just try to read as CPT.
            # XML files can contain multiple CPT entries.
            try:
                multiple_cpt_data = read_cpt_xml(filepath)
            except Exception:
                raise ValueError(f"File '{filepath}' is not a CPT XML file or could not be parsed as CPT data.")

            for cpt_data in multiple_cpt_data:
                check_for_required_columns(cpt_data, filepath)
            return multiple_cpt_data

        elif ext == ".gef":
            cpt_data = read_cpt(filepath, replace_column_voids=replace_column_voids)
            # GEF test ID is in alias.
            # https://github.com/cemsbv/pygef/blob/6002e174b154a6ef7726f7a3aa467d6ada22be92/src/pygef/shim.py#L106
            check_for_required_columns(cpt_data, filepath)
            return [cpt_data]

        else:
            raise ValueError(f"File '{filepath}' has extension '{ext}', expected .xml or .gef.")

    except FileNotFoundError:
        raise
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error processing file '{filepath}': {e}") from e


def parse_gef_files(filepaths: list[str | Path], replace_column_voids=False) -> dict[str, CPTData]:
    """Parse a list of GEF-CPT & GEF-XML files and return a dictionary of CPTData objects keyed by filename.

    Only files identified as CPT (Cone Penetration Test) are read and included.

    :param filepaths: List of file paths to parse.
    :param replace_column_voids: (Default value = False) Whether to interpolate void values

    :return: Dictionary mapping each CPT file's filename to its CPTData object.
    """
    data: dict[str, CPTData] = {}

    for filepath in filepaths:
        try:
            # Get list of CPT in the GEF file, copy to data dict.
            file_result = parse_gef_file(filepath, replace_column_voids=replace_column_voids)
            for cpt_data in file_result:
                cpt_id = get_gef_cpt_id(cpt_data)
                if cpt_id in data:
                    raise ValueError(
                        f"Duplicate ID '{cpt_id}' encountered. Each ID (from CPT 'alias' or 'bro_id') must be unique across all input files."
                    )
                data[cpt_id] = cpt_data
        except FileNotFoundError:
            raise
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Error processing file '{filepath}': {e}") from e

    logger.info(f"Parsed {len(data)} CPT files from {len(filepaths)} input files.")
    return data


def check_for_required_columns(cpt_data: CPTData, filepath: str) -> None:
    """Check that the CPTData object has the required columns.

    Required columns taken from https://bedrock.engineer/reference/formats/gef/gef-cpt/#column-quantities

    :param cpt_data: The CPTData object to check.
    :param filepath: The file path of the GEF file being processed.

    :raises ValueError: If any required columns are missing.
    """
    required_columns = ["penetrationLength", "coneResistance"]
    if hasattr(cpt_data, "data"):
        missing = [col for col in required_columns if col not in cpt_data.data.columns]
        if missing:
            raise ValueError(f"File '{filepath}' is missing required columns: {missing}")


def get_gef_cpt_id(gef: CPTData) -> str:
    """Get a unique identifier for a CPTData object from alias (GEF-CPT) or bro_id (GEF-XML).

    The "alias" property is populated for GEF-CPT format, from the CPT #TESTID header value.

    The "bro_id" property is populated for GEF-XML format, from the CPT broId element.

    :param gef: CPTData to retrieve hole ID from

    :return: The unique identifier for the CPTData object.

    :raises ValueError: If the CPTData is missing the required identifier
    """
    if hasattr(gef, "bro_id") and gef.bro_id:
        return gef.bro_id
    elif hasattr(gef, "alias") and gef.alias:
        return gef.alias
    else:
        raise ValueError("CPT missing required identifier 'bro_id' / 'alias'.")
