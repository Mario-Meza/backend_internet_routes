from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    phone: str = Field(
        min_length=7,
        max_length=20,
    )

    location: str = Field(
        min_length=2,
        max_length=100,
    )

    reference: str | None = Field(
        default=None,
        max_length=250,
    )


class CustomerUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=20,
    )

    location: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    reference: str | None = Field(
        default=None,
        max_length=250,
    )


class CustomerActiveUpdate(BaseModel):
    active: bool


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: str
    location: str
    reference: str | None = None
    active: bool