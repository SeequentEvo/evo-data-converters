import re

from .duf_wrapper import BaseEntity


def validify(name: str) -> str:
    # use a regex to make a valid windows file name
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:255]  # limit to 255 chars


def get_name(obj: BaseEntity) -> str:
    if (label := getattr(obj, "Label", None)) is not None:
        return validify(label)
    obj_name = f"{type(obj).__name__}_{str(obj.Guid)[:8]}"
    if (layer := getattr(obj, "Layer", None)) is not None:
        layer_name = layer.Name if hasattr(layer, "Name") else ""
        return validify(f"{layer_name}_{obj_name}".lstrip('_'))
    else:
        return validify(obj_name)
