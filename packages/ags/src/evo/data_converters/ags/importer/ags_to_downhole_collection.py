from evo.data_converters.ags.common import AgsContext
from evo.objects.utils import ObjectDataClient
from evo_schemas.objects import DownholeCollection_V1_3_0 as DownholeCollection


def create_downhole_collection(
    ags_context: AgsContext, data_client: ObjectDataClient, tags: dict[str, str] | None
) -> DownholeCollection | None:
    pass
