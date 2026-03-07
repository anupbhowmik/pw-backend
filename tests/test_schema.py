"""Tests for schema validation, including a simulated repair scenario."""

import json

import pytest
from pydantic import ValidationError

from app.schemas.schemas import ReceiptSchema


VALID_JSON = {
    "store": {"name": "Walmart", "city": "Austin", "state": "TX"},
    "transaction": {
        "purchase_datetime": "2024-03-15T14:30:00",
        "subtotal": 25.47,
        "tax": 2.10,
        "total": 27.57,
    },
    "items": [
        {"description_raw": "BANANAS", "total_price": 1.50, "quantity": 1},
        {"description_raw": "MILK 2%", "total_price": 3.99, "quantity": 1},
    ],
}


INVALID_JSON_MISSING_TOTAL = {
    "store": {"name": "Walmart"},
    "transaction": {
        "purchase_datetime": "2024-03-15T14:30:00",
        "subtotal": 25.47,
        "tax": 2.10,
        # "total" is missing
    },
    "items": [
        {"description_raw": "BANANAS", "total_price": 1.50},
    ],
}


INVALID_JSON_BAD_ITEM = {
    "store": {"name": "Walmart"},
    "transaction": {
        "purchase_datetime": "2024-03-15T14:30:00",
        "subtotal": 25.47,
        "tax": 2.10,
        "total": 27.57,
    },
    "items": [
        {"description_raw": "BANANAS"},  # missing total_price
    ],
}


def test_valid_receipt():
    r = ReceiptSchema.model_validate(VALID_JSON)
    assert r.store.name == "Walmart"
    assert len(r.items) == 2


def test_invalid_missing_total():
    with pytest.raises(ValidationError) as exc_info:
        ReceiptSchema.model_validate(INVALID_JSON_MISSING_TOTAL)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("transaction", "total") for e in errors)


def test_invalid_bad_item():
    with pytest.raises(ValidationError) as exc_info:
        ReceiptSchema.model_validate(INVALID_JSON_BAD_ITEM)
    errors = exc_info.value.errors()
    assert any("total_price" in str(e["loc"]) for e in errors)


def test_simulated_repair_loop():
    """Simulate the repair loop: invalid -> fix -> valid."""
    # Step 1: validate the bad JSON
    try:
        ReceiptSchema.model_validate(INVALID_JSON_MISSING_TOTAL)
        pytest.fail("Should have raised")
    except ValidationError as exc:
        errors = exc.errors()

    # Step 2: "repair" by adding the missing field
    repaired = {**INVALID_JSON_MISSING_TOTAL}
    repaired["transaction"] = {**repaired["transaction"], "total": 27.57}

    # Step 3: validate repaired version
    r = ReceiptSchema.model_validate(repaired)
    assert r.transaction.total == 27.57
