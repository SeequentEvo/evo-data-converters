import pytest

from evo.data_converters.duf.importer.utils import (
    ResolveObjectNameOption,
    ResolveObjectNameType,
    ResolveObjectNameContext,
)
from packages.duf.tests.utils import convert_duf


def _custom_name_resolver(context: ResolveObjectNameContext) -> str:
    return f"{'|'.join(context.layers)} - {context.entity_type} - combined={context.combined} - {str(context.entity.Guid)[:6]}"


expected_combined_default = {
    "LINELAYER - polylines",
    "MIXED - polylines",
    "FACELAYER - polyfaces",
    "MIXED - polyfaces",
}

expected_combined_concat = expected_names = {
    "0 - LINELAYER - polylines",
    "0 - MIXED - polylines",
    "0 - FACELAYER - polyfaces",
    "0 - MIXED - polyfaces",
}

expected_combined_custom = {
    "0|FACELAYER - polyfaces - combined=True - 1c14ef",
    "0|FACELAYER - polyfaces - combined=True - 3917d9",
    "0|LINELAYER - polylines - combined=True - 830221",
    "0|LINELAYER - polylines - combined=True - f83a4e",
    "0|MIXED - polyfaces - combined=True - 5a4d1f",
    "0|MIXED - polylines - combined=True - c4e93c",
}

expected_uncombined_default = {
    "FACELAYER-dwPolyface-1c14ef99-e5e3-4388-bbe6-6120344712b1",
    "FACELAYER-dwPolyface-3917d9dd-f54a-4e2b-87a4-f0523ec9481b",
    "LINELAYER-dwPolyline-f83a4e34-0428-431c-aed7-c554febcbc4a",
    "LINELAYER-dwPolyline-83022162-cbcc-41b1-9a1d-f8bce6ce9bac",
    "MIXED-dwPolyface-5a4d1f74-30e0-4abd-adc6-cc51cfad21ab",
    "MIXED-dwPolyline-c4e93c6e-1df1-4d3a-ba0c-86146b9a114b",
}

expected_uncombined_concat = {
    "0 - FACELAYER - dwPolyface-1c14ef99-e5e3-4388-bbe6-6120344712b1",
    "0 - FACELAYER - dwPolyface-3917d9dd-f54a-4e2b-87a4-f0523ec9481b",
    "0 - LINELAYER - dwPolyline-f83a4e34-0428-431c-aed7-c554febcbc4a",
    "0 - LINELAYER - dwPolyline-83022162-cbcc-41b1-9a1d-f8bce6ce9bac",
    "0 - MIXED - dwPolyface-5a4d1f74-30e0-4abd-adc6-cc51cfad21ab",
    "0 - MIXED - dwPolyline-c4e93c6e-1df1-4d3a-ba0c-86146b9a114b",
}

expected_uncombined_custom = {
    "0|FACELAYER - polyfaces - combined=False - 1c14ef",
    "0|FACELAYER - polyfaces - combined=False - 3917d9",
    "0|LINELAYER - polylines - combined=False - 830221",
    "0|LINELAYER - polylines - combined=False - f83a4e",
    "0|MIXED - polyfaces - combined=False - 5a4d1f",
    "0|MIXED - polylines - combined=False - c4e93c",
}


@pytest.fixture()
def converter(multiple_objects_path, evo_metadata):
    def converter(combined: bool, resolver: ResolveObjectNameType | ResolveObjectNameOption):
        go_objects = convert_duf(
            filepath=multiple_objects_path,
            evo_workspace_metadata=evo_metadata,
            epsg_code=32650,
            combine_objects_in_layers=combined,
            publish_objects=False,
            resolve_object_name=resolver,
        )
        return [go.name for go in go_objects]

    return converter


@pytest.mark.parametrize(
    "combined, resolver, expected_names",
    [
        (True, ResolveObjectNameOption.DEFAULT, expected_combined_default),
        (True, ResolveObjectNameOption.CONCATENATE, expected_combined_concat),
        (True, _custom_name_resolver, expected_combined_custom),
        (False, ResolveObjectNameOption.DEFAULT, expected_uncombined_default),
        (False, ResolveObjectNameOption.CONCATENATE, expected_uncombined_concat),
        (False, _custom_name_resolver, expected_uncombined_custom),
    ],
)
def test_object_name_generation(converter, combined, resolver, expected_names):
    names = converter(combined=combined, resolver=resolver)
    for name in names:
        assert name in expected_names
