from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """
    Base for every request and response schema.

    The API speaks camelCase so the TypeScript frontend needs no mapping layer,
    while Python stays snake_case. `populate_by_name` keeps snake_case input
    working too, so nothing breaks for non-browser clients.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
