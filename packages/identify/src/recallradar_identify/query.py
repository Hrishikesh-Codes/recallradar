"""ProductQuery: what every input method produces and the matcher consumes (SPEC §5)."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from recallradar_core.categories import Category


class InputType(StrEnum):
    TEXT = "text"
    LINK = "link"
    BARCODE = "barcode"
    LABEL_PHOTO = "label_photo"  # M2
    SCREENSHOT = "screenshot"  # M2
    VIN = "vin"  # M2


class Vehicle(BaseModel):
    """A car, truck or motorcycle, from a decoded VIN or from text like "2019 Honda Civic"."""

    make: str
    model: str | None = None
    year: int | None = None


class ProductQuery(BaseModel):
    """A product to check, with how sure we are about each field (0-1).

    Providers (text, link, barcode, and later Gmail/Knot sync) fill what they can; the matcher
    never needs to know which provider made the query.
    """

    input_type: InputType
    raw: str = Field(max_length=2000)
    product_name: str | None = None
    brand: str | None = None
    model_numbers: list[str] = Field(default_factory=list)
    upcs: list[str] = Field(default_factory=list, description="GTIN-14")
    lot_codes: list[str] = Field(default_factory=list)
    purchase_date: date | None = None
    retailer: str | None = None
    categories: list[Category] = Field(default_factory=list)
    #: Set from a decoded VIN. Typed text is matched against vehicle recalls by the engine.
    vehicle: Vehicle | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    #: Things the user should know about how we read their input.
    notes: list[str] = Field(default_factory=list)

    def search_text(self) -> str:
        """Free text for lexical and semantic search. Only typed text falls back to the raw
        input: a barcode's digits or a link's URL aren't a description of the product."""
        fallback = self.raw if self.input_type is InputType.TEXT else None  # label: name lines
        parts = [self.brand, self.product_name or fallback]
        return " ".join(p for p in parts if p).strip()
