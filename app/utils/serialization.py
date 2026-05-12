from datetime import datetime

from bson import ObjectId


def serialize_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_document(document: dict) -> dict:
    return {key: serialize_value(value) for key, value in document.items()}
