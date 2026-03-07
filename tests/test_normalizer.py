"""Unit tests for the normalizer service."""

from app.schemas.schemas import (
    ExtractionMetadata,
    ItemSchema,
    ReceiptSchema,
    StoreSchema,
    TransactionSchema,
)
from app.services.normalizer import classify_item, normalize_receipt, normalize_store_name


# ---------- Store name + category ---------- #


def test_store_name_walmart():
    name, cat = normalize_store_name("WAL*MART")
    assert name == "Walmart"
    assert cat == "groceries"


def test_store_name_walmart_variants():
    assert normalize_store_name("WAL-MART")[0] == "Walmart"
    assert normalize_store_name("wal mart")[0] == "Walmart"


def test_store_name_wegmans():
    name, cat = normalize_store_name("WEGMANS FOOD")
    assert name == "Wegmans"
    assert cat == "groceries"


def test_store_name_aldi():
    name, cat = normalize_store_name("ALDI #1234")
    assert name == "Aldi"
    assert cat == "groceries"


def test_store_name_sams_club():
    name, cat = normalize_store_name("SAMS CLUB")
    assert name == "Sam's Club"
    assert cat == "wholesale_club"


def test_store_name_bjs():
    name, cat = normalize_store_name("BJ'S WHOLESALE")
    assert name == "BJ's Wholesale Club"
    assert cat == "wholesale_club"


def test_store_name_costco():
    name, cat = normalize_store_name("COSTCO WHOLESALE")
    assert name == "Costco"
    assert cat == "wholesale_club"


def test_store_name_mcdonalds():
    name, cat = normalize_store_name("MCDONALDS #12345")
    assert name == "McDonald's"
    assert cat == "restaurant"


def test_store_name_chick_fil_a():
    name, cat = normalize_store_name("CHICK-FIL-A")
    assert name == "Chick-fil-A"
    assert cat == "restaurant"


def test_store_name_starbucks():
    name, cat = normalize_store_name("STARBUCKS STORE #456")
    assert name == "Starbucks"
    assert cat == "restaurant"


def test_store_name_cvs():
    name, cat = normalize_store_name("CVS/PHARMACY")
    assert name == "CVS"
    assert cat == "pharmacy"


def test_store_name_home_depot():
    name, cat = normalize_store_name("THE HOME DEPOT")
    assert name == "The Home Depot"
    assert cat == "home_improvement"


def test_store_name_target():
    name, cat = normalize_store_name("TARGET T-1234")
    assert name == "Target"
    assert cat == "department"


def test_store_name_7eleven():
    name, cat = normalize_store_name("7-ELEVEN")
    assert name == "7-Eleven"
    assert cat == "convenience"


def test_store_name_dollar_general():
    name, cat = normalize_store_name("DOLLAR GENERAL")
    assert name == "Dollar General"
    assert cat == "dollar_store"


def test_store_name_passthrough():
    name, cat = normalize_store_name("Local Grocery")
    assert name == "Local Grocery"
    assert cat == "unknown"


# ---------- Item classification ---------- #


def test_classify_item_produce():
    cat, conf = classify_item("ORGANIC BANANAS")
    assert cat == "produce"


def test_classify_item_dairy():
    cat, conf = classify_item("2% MILK 1GAL")
    assert cat == "dairy"


def test_classify_item_pantry():
    cat, conf = classify_item("BROWN RICE 5LB")
    assert cat == "pantry"


def test_classify_item_health():
    cat, conf = classify_item("TYLENOL EXTRA STR")
    assert cat == "health_personal"


def test_classify_item_default():
    cat, conf = classify_item("MYSTERY ITEM XYZ")
    assert cat == "grocery"


# ---------- Full receipt normalization ---------- #


def test_normalize_receipt_store_category():
    receipt = ReceiptSchema(
        store=StoreSchema(name="WAL*MART", city="austin", state="tx"),
        transaction=TransactionSchema(
            purchase_datetime="2024-03-15T14:30:00",
            subtotal=5.49,
            tax=0.45,
            total=5.94,
        ),
        items=[
            ItemSchema(description_raw="BANANAS", total_price=1.50),
            ItemSchema(description_raw="MILK", total_price=3.99),
        ],
        metadata=ExtractionMetadata(extraction_model="gemini-2.5-flash-lite", confidence=0.95),
    )
    result = normalize_receipt(receipt, "gemini-2.5-flash-lite")
    assert result.store.name == "Walmart"
    assert result.store.category == "Groceries"
    assert result.store.city == "Austin"
    assert result.store.state == "TX"


def test_normalize_receipt_restaurant_category():
    receipt = ReceiptSchema(
        store=StoreSchema(name="CHIPOTLE MEXICAN"),
        transaction=TransactionSchema(
            purchase_datetime="2024-03-15T12:00:00",
            subtotal=12.50,
            tax=1.00,
            total=13.50,
        ),
        items=[ItemSchema(description_raw="BURRITO BOWL", total_price=12.50)],
    )
    result = normalize_receipt(receipt, "gemini-2.5-flash-lite")
    assert result.store.name == "Chipotle"
    assert result.store.category == "Dining Out"


def test_normalize_receipt_consistency_warning():
    receipt = ReceiptSchema(
        store=StoreSchema(name="WEGMANS", city="rochester", state="ny"),
        transaction=TransactionSchema(
            purchase_datetime="2024-03-15T14:30:00",
            subtotal=10.00,
            tax=0.83,
            total=10.83,
        ),
        items=[
            ItemSchema(description_raw="BANANAS", total_price=1.50),
            ItemSchema(description_raw="MILK", total_price=3.99),
            # Sum = 5.49, subtotal = 10.00 -> mismatch
        ],
        metadata=ExtractionMetadata(extraction_model="gemini-2.5-flash-lite", confidence=0.95),
    )
    result = normalize_receipt(receipt, "gemini-2.5-flash-lite")
    assert result.store.name == "Wegmans"
    assert result.store.category == "Groceries"
    assert any("differs from subtotal" in w for w in result.metadata.warnings)
    assert result.metadata.confidence < 0.95


def test_normalize_receipt_items_categorized():
    receipt = ReceiptSchema(
        store=StoreSchema(name="Target"),
        transaction=TransactionSchema(
            purchase_datetime="2024-03-15T14:30:00",
            subtotal=5.49,
            tax=0.45,
            total=5.94,
        ),
        items=[
            ItemSchema(description_raw="ORGANIC BANANAS", total_price=1.50),
            ItemSchema(description_raw="BREAD WHOLE WHEAT", total_price=3.99),
        ],
    )
    result = normalize_receipt(receipt, "gemini-2.5-flash-lite")
    assert result.items[0].category == "produce"
    assert result.items[1].category == "bakery"
    assert result.items[0].description_norm == "Organic Bananas"
