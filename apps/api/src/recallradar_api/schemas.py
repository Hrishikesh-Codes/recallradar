"""Request and response models. These are the API's contract with the web app (openapi.json)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from recallradar_core.enums import NoticeType, RecallSource, RecallStatus, RemedyType
from recallradar_matching.engine import Tier

InputKind = Literal["text", "link", "barcode", "vin"]


class CheckInput(BaseModel):
    type: InputKind
    value: str = Field(min_length=1, max_length=2000)


class CheckRequest(BaseModel):
    input: CheckInput
    purchase_date: date | None = Field(
        default=None, description="Overrides a date found in the input."
    )


class QueryOut(BaseModel):
    """How we read the input, so the user can correct it."""

    input_type: str
    product_name: str | None
    brand: str | None
    model_numbers: list[str]
    upcs: list[str]
    lot_codes: list[str]
    purchase_date: date | None
    retailer: str | None
    categories: list[str]


class Restriction(BaseModel):
    kind: str
    detail: str


class RecallSummary(BaseModel):
    id: int
    source: RecallSource
    source_label: str = Field(description='"CPSC", "FDA", ...')
    source_recall_id: str
    reference: str | None
    notice_type: NoticeType
    title: str
    hazard: str | None
    remedy: str | None
    remedy_type: RemedyType
    recall_date: date | None
    status: RecallStatus
    classification: str | None
    firm: str | None
    official_url: str
    image_url: str | None


class ProductOut(BaseModel):
    product_name: str
    brand: str | None
    model_numbers: list[str]
    upcs: list[str]
    lot_codes: list[str]
    sold_start_date: date | None
    sold_end_date: date | None
    unit_restricted: bool
    restrictions: list[Restriction]
    where_to_look: list[str]
    quantity: str | None


class MatchOut(BaseModel):
    tier: Tier | None = Field(description="null for related recalls that aren't a match")
    recall: RecallSummary
    product: ProductOut
    reasons: list[str]
    what_to_check: list[str]
    similarity: float = Field(description="name similarity 0-1; 0 when matched by identifier only")


class SourceCoverage(BaseModel):
    source: RecallSource
    label: str
    recalls: int
    last_synced_at: datetime | None


class Coverage(BaseModel):
    checked: list[SourceCoverage]
    not_covered: list[RecallSource] = Field(
        description="Sources this product's category needs that we don't ingest yet."
    )
    recalls_checked: int
    updated_at: datetime | None


class CheckResponse(BaseModel):
    id: UUID = Field(description="Quote this when sending feedback on the result.")
    verdict: Tier
    query: QueryOut
    matches: list[MatchOut]
    related: list[MatchOut]
    coverage: Coverage
    notes: list[str]


class RecallDetail(BaseModel):
    recall: RecallSummary
    description: str | None
    distribution: str | None
    products: list[ProductOut]


class Stats(BaseModel):
    recalls: int
    products: int
    sources: list[SourceCoverage]
    updated_at: datetime | None


FeedbackLabel = Literal["mine", "not_mine", "handled"]


class FeedbackRequest(BaseModel):
    check_id: UUID
    recall_id: int
    label: FeedbackLabel
    tier_shown: Tier | None = None
    query: QueryOut | None = Field(
        default=None, description="What was checked; stored as a matching label (SPEC §6.7)."
    )


class Accepted(BaseModel):
    status: Literal["accepted"] = "accepted"


class ItemMatchOut(BaseModel):
    recall: RecallSummary
    tier: Tier
    reasons: list[str]
    first_matched_at: datetime
    dismissed: bool


class ItemOut(BaseModel):
    id: int
    label: str
    input_type: InputKind
    input_value: str
    purchase_date: date | None
    verdict: Tier
    last_checked_at: datetime
    created_at: datetime
    matches: list[ItemMatchOut]


class NewItem(BaseModel):
    input: CheckInput
    label: str | None = Field(default=None, max_length=200)
    purchase_date: date | None = None


AlertTier = Literal["recalled", "check_unit"]


class SettingsOut(BaseModel):
    email_alerts: bool
    alert_tiers: list[AlertTier]


class Me(BaseModel):
    id: str
    email: str | None = Field(description="null for demo (anonymous) accounts")
    is_anonymous: bool
    settings: SettingsOut
    items: int


class Export(BaseModel):
    """Everything we hold about a user (SPEC §11: full data export)."""

    exported_at: datetime
    account: dict[str, object]
    settings: SettingsOut
    items: list[ItemOut]
    alerts: list[dict[str, object]]
