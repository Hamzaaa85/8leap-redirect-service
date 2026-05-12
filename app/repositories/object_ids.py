from bson import ObjectId


def parse_object_id(value: str) -> ObjectId | None:
    if not ObjectId.is_valid(value):
        return None

    return ObjectId(value)
