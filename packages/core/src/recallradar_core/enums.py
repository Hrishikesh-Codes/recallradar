"""Closed vocabularies stored in the database (as text + CHECK constraint, see DECISIONS.md)."""

from enum import StrEnum


class RecallSource(StrEnum):
    CPSC = "cpsc"
    FDA_FOOD = "fda_food"
    FDA_DRUG = "fda_drug"
    FDA_DEVICE = "fda_device"
    FSIS = "fsis"
    NHTSA = "nhtsa"


# How sources are named to users: "Checked against ... from CPSC and FDA".
SOURCE_LABELS: dict[RecallSource, str] = {
    RecallSource.CPSC: "CPSC",
    RecallSource.FDA_FOOD: "FDA",
    RecallSource.FDA_DRUG: "FDA",
    RecallSource.FDA_DEVICE: "FDA",
    RecallSource.FSIS: "USDA FSIS",
    RecallSource.NHTSA: "NHTSA",
}


class NoticeType(StrEnum):
    RECALL = "recall"
    # CPSC "warns consumers" when a firm won't agree to a recall. Not a recall: never call it one.
    WARNING = "warning"
    # USDA FSIS public health alert: product that can't be recalled (often no longer for sale, or
    # illegally imported) but shouldn't be eaten. Also not a recall.
    ALERT = "alert"


# How notices are named in reasons, emails, and on screen: never "recall" for a warning or alert.
NOTICE_NAMES = {
    NoticeType.RECALL: "recall",
    NoticeType.WARNING: "warning",
    NoticeType.ALERT: "public health alert",
}


class RemedyType(StrEnum):
    REFUND = "refund"
    REPAIR = "repair"
    REPLACE = "replace"
    DISPOSE = "dispose"
    OTHER = "other"


class RecallStatus(StrEnum):
    ONGOING = "ongoing"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


class ChunkSection(StrEnum):
    SUMMARY = "summary"
    HAZARD = "hazard"
    REMEDY = "remedy"
    PRODUCTS = "products"
    HOW_TO_IDENTIFY = "how_to_identify"
    OTHER = "other"


class SyncMode(StrEnum):
    BACKFILL = "backfill"
    INCREMENTAL = "incremental"


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
