"""Post-extraction normalization: store names, store categories, item categories, consistency checks."""

from __future__ import annotations

import re

from app.schemas.schemas import ItemSchema, ReceiptSchema

# ================================================================== #
# Store name normalization + store-level category
# ================================================================== #
# Each entry: (regex_pattern, canonical_name, store_category)
# Categories:
#   groceries        – supermarkets, grocery chains
#   wholesale_club   – membership warehouse clubs
#   restaurant       – sit-down, fast-food, fast-casual, cafes
#   pharmacy         – drugstores
#   convenience      – gas stations, corner stores
#   department       – general merchandise / department stores
#   home_improvement – hardware, home/garden
#   electronics      – consumer electronics
#   pet              – pet supply stores
#   clothing         – apparel retailers
#   dollar_store     – dollar / discount stores
#   specialty_food   – bakeries, butcher shops, specialty grocers
#   auto             – auto parts
#   office           – office supply
#   unknown          – fallback

_STORE_CATALOG: list[tuple[re.Pattern, str, str]] = [
    # ---- Grocery ----
    (re.compile(r"WAL[\*\-\s]?MART(?!\s*\.COM)", re.I), "Walmart", "groceries"),
    (re.compile(r"WALMART\s*SUPERCENTER", re.I), "Walmart Supercenter", "groceries"),
    (re.compile(r"WALMART\s*NEIGHBORHOOD", re.I), "Walmart Neighborhood Market", "groceries"),
    (re.compile(r"WEGMANS", re.I), "Wegmans", "groceries"),
    (re.compile(r"ALDI", re.I), "Aldi", "groceries"),
    (re.compile(r"KROGER", re.I), "Kroger", "groceries"),
    (re.compile(r"PUBLIX", re.I), "Publix", "groceries"),
    (re.compile(r"SAFEWAY", re.I), "Safeway", "groceries"),
    (re.compile(r"ALBERTSON", re.I), "Albertsons", "groceries"),
    (re.compile(r"H[\-\s]?E[\-\s]?B\b", re.I), "H-E-B", "groceries"),
    (re.compile(r"WHOLE\s*FOODS", re.I), "Whole Foods", "groceries"),
    (re.compile(r"TRADER\s*JOE", re.I), "Trader Joe's", "groceries"),
    (re.compile(r"SPROUTS", re.I), "Sprouts Farmers Market", "groceries"),
    (re.compile(r"FOOD\s*LION", re.I), "Food Lion", "groceries"),
    (re.compile(r"GIANT\s*(FOOD|EAGLE)?", re.I), "Giant", "groceries"),
    (re.compile(r"STOP\s*[&N]\s*SHOP", re.I), "Stop & Shop", "groceries"),
    (re.compile(r"HARRIS\s*TEETER", re.I), "Harris Teeter", "groceries"),
    (re.compile(r"MEIJER", re.I), "Meijer", "groceries"),
    (re.compile(r"WINCO", re.I), "WinCo Foods", "groceries"),
    (re.compile(r"PIGGLY\s*WIGGLY", re.I), "Piggly Wiggly", "groceries"),
    (re.compile(r"FOOD\s*4\s*LESS", re.I), "Food 4 Less", "groceries"),
    (re.compile(r"SAVE[\-\s]?A[\-\s]?LOT", re.I), "Save-A-Lot", "groceries"),
    (re.compile(r"WINN[\-\s]?DIXIE", re.I), "Winn-Dixie", "groceries"),
    (re.compile(r"SHOP\s*RITE", re.I), "ShopRite", "groceries"),
    (re.compile(r"VONS", re.I), "Vons", "groceries"),
    (re.compile(r"RALPHS", re.I), "Ralphs", "groceries"),
    (re.compile(r"FRED\s*MEYER", re.I), "Fred Meyer", "groceries"),
    (re.compile(r"BI[\-\s]?LO", re.I), "BI-LO", "groceries"),
    (re.compile(r"ACME\s*MARKET", re.I), "Acme Markets", "groceries"),
    (re.compile(r"STATER\s*BROS", re.I), "Stater Bros", "groceries"),
    (re.compile(r"MARKET\s*BASKET", re.I), "Market Basket", "groceries"),
    (re.compile(r"HANNAFORD", re.I), "Hannaford", "groceries"),
    (re.compile(r"INGLES", re.I), "Ingles", "groceries"),
    (re.compile(r"FAREWAY", re.I), "Fareway", "groceries"),
    (re.compile(r"LIDL", re.I), "Lidl", "groceries"),
    (re.compile(r"FRESH\s*MARKET", re.I), "The Fresh Market", "groceries"),
    (re.compile(r"EARTH\s*FARE", re.I), "Earth Fare", "groceries"),
    (re.compile(r"NATURAL\s*GROCERS", re.I), "Natural Grocers", "groceries"),

    # ---- Wholesale / Club ----
    (re.compile(r"COST\s?CO", re.I), "Costco", "wholesale_club"),
    (re.compile(r"SAM'?S\s*CLUB", re.I), "Sam's Club", "wholesale_club"),
    (re.compile(r"BJ'?S\s*(WHOLESALE)?", re.I), "BJ's Wholesale Club", "wholesale_club"),

    # ---- Restaurant / Fast Food / Fast Casual / Cafe ----
    (re.compile(r"MCDONALD", re.I), "McDonald's", "restaurant"),
    (re.compile(r"CHICK[\-\s]?FIL[\-\s]?A", re.I), "Chick-fil-A", "restaurant"),
    (re.compile(r"STARBUCK", re.I), "Starbucks", "restaurant"),
    (re.compile(r"DUNKIN", re.I), "Dunkin'", "restaurant"),
    (re.compile(r"SUBWAY", re.I), "Subway", "restaurant"),
    (re.compile(r"TACO\s*BELL", re.I), "Taco Bell", "restaurant"),
    (re.compile(r"BURGER\s*KING", re.I), "Burger King", "restaurant"),
    (re.compile(r"WENDY", re.I), "Wendy's", "restaurant"),
    (re.compile(r"POPEYE", re.I), "Popeyes", "restaurant"),
    (re.compile(r"PANDA\s*EXPRESS", re.I), "Panda Express", "restaurant"),
    (re.compile(r"CHIPOTLE", re.I), "Chipotle", "restaurant"),
    (re.compile(r"PANERA", re.I), "Panera Bread", "restaurant"),
    (re.compile(r"OLIVE\s*GARDEN", re.I), "Olive Garden", "restaurant"),
    (re.compile(r"APPLEBEE", re.I), "Applebee's", "restaurant"),
    (re.compile(r"CHILI'?S", re.I), "Chili's", "restaurant"),
    (re.compile(r"IHOP", re.I), "IHOP", "restaurant"),
    (re.compile(r"DENNY", re.I), "Denny's", "restaurant"),
    (re.compile(r"WAFFLE\s*HOUSE", re.I), "Waffle House", "restaurant"),
    (re.compile(r"FIVE\s*GUYS", re.I), "Five Guys", "restaurant"),
    (re.compile(r"IN[\-\s]?N[\-\s]?OUT", re.I), "In-N-Out Burger", "restaurant"),
    (re.compile(r"WHATABURGER", re.I), "Whataburger", "restaurant"),
    (re.compile(r"SONIC\s*DRIVE", re.I), "Sonic Drive-In", "restaurant"),
    (re.compile(r"JACK\s*IN\s*THE\s*BOX", re.I), "Jack in the Box", "restaurant"),
    (re.compile(r"DOMINO", re.I), "Domino's", "restaurant"),
    (re.compile(r"PIZZA\s*HUT", re.I), "Pizza Hut", "restaurant"),
    (re.compile(r"PAPA\s*JOHN", re.I), "Papa John's", "restaurant"),
    (re.compile(r"LITTLE\s*CAESAR", re.I), "Little Caesars", "restaurant"),
    (re.compile(r"KFC|KENTUCKY\s*FRIED", re.I), "KFC", "restaurant"),
    (re.compile(r"ARBY", re.I), "Arby's", "restaurant"),
    (re.compile(r"RAISING\s*CANE", re.I), "Raising Cane's", "restaurant"),
    (re.compile(r"WINGSTOP", re.I), "Wingstop", "restaurant"),
    (re.compile(r"BUFFALO\s*WILD\s*WING", re.I), "Buffalo Wild Wings", "restaurant"),
    (re.compile(r"RED\s*LOBSTER", re.I), "Red Lobster", "restaurant"),
    (re.compile(r"OUTBACK\s*STEAK", re.I), "Outback Steakhouse", "restaurant"),
    (re.compile(r"TEXAS\s*ROADHOUSE", re.I), "Texas Roadhouse", "restaurant"),
    (re.compile(r"CRACKER\s*BARREL", re.I), "Cracker Barrel", "restaurant"),
    (re.compile(r"CHEESECAKE\s*FACTORY", re.I), "The Cheesecake Factory", "restaurant"),
    (re.compile(r"P\.?F\.?\s*CHANG", re.I), "P.F. Chang's", "restaurant"),
    (re.compile(r"RUTH'?S?\s*CHRIS", re.I), "Ruth's Chris", "restaurant"),
    (re.compile(r"CAVA\b", re.I), "CAVA", "restaurant"),
    (re.compile(r"SWEETGREEN", re.I), "sweetgreen", "restaurant"),
    (re.compile(r"SHAKE\s*SHACK", re.I), "Shake Shack", "restaurant"),
    (re.compile(r"JERSEY\s*MIKE", re.I), "Jersey Mike's", "restaurant"),
    (re.compile(r"JIMMY\s*JOHN", re.I), "Jimmy John's", "restaurant"),
    (re.compile(r"FIREHOUSE\s*SUB", re.I), "Firehouse Subs", "restaurant"),
    (re.compile(r"ZAXBY", re.I), "Zaxby's", "restaurant"),
    (re.compile(r"CULVER", re.I), "Culver's", "restaurant"),
    (re.compile(r"DAIRY\s*QUEEN", re.I), "Dairy Queen", "restaurant"),
    (re.compile(r"TIM\s*HORTON", re.I), "Tim Hortons", "restaurant"),
    (re.compile(r"KRISPY\s*KREME", re.I), "Krispy Kreme", "restaurant"),

    # ---- Pharmacy / Drugstore ----
    (re.compile(r"CVS", re.I), "CVS", "pharmacy"),
    (re.compile(r"WALGREENS", re.I), "Walgreens", "pharmacy"),
    (re.compile(r"RITE\s*AID", re.I), "Rite Aid", "pharmacy"),

    # ---- Department / General Merchandise ----
    (re.compile(r"TARGET", re.I), "Target", "department"),
    (re.compile(r"AMAZON", re.I), "Amazon", "department"),
    (re.compile(r"WALMART\.COM", re.I), "Walmart.com", "department"),
    (re.compile(r"KOHL'?S", re.I), "Kohl's", "department"),
    (re.compile(r"MACY", re.I), "Macy's", "department"),
    (re.compile(r"NORDSTROM", re.I), "Nordstrom", "department"),
    (re.compile(r"JC\s*PENNEY|JCPENNEY", re.I), "JCPenney", "department"),
    (re.compile(r"MARSHALLS", re.I), "Marshalls", "department"),
    (re.compile(r"TJ\s*MAXX|T\.?J\.?\s*MAXX", re.I), "TJ Maxx", "department"),
    (re.compile(r"ROSS\b", re.I), "Ross", "department"),
    (re.compile(r"BURLINGTON", re.I), "Burlington", "department"),

    # ---- Convenience / Gas ----
    (re.compile(r"7[\-\s]?ELEVEN|7[\-\s]?11", re.I), "7-Eleven", "convenience"),
    (re.compile(r"WAWA", re.I), "Wawa", "convenience"),
    (re.compile(r"SHEETZ", re.I), "Sheetz", "convenience"),
    (re.compile(r"QUIK\s*TRIP|QT\b", re.I), "QuikTrip", "convenience"),
    (re.compile(r"CASEY'?S", re.I), "Casey's", "convenience"),
    (re.compile(r"CIRCLE\s*K", re.I), "Circle K", "convenience"),
    (re.compile(r"SPEEDWAY", re.I), "Speedway", "convenience"),
    (re.compile(r"RACETRAC", re.I), "RaceTrac", "convenience"),
    (re.compile(r"BUCCEE|BUC[\-\s]?EE", re.I), "Buc-ee's", "convenience"),
    (re.compile(r"PILOT\b|FLYING\s*J", re.I), "Pilot Flying J", "convenience"),
    (re.compile(r"LOVE'?S\s*TRAVEL", re.I), "Love's Travel Stops", "convenience"),
    (re.compile(r"CUMBERLAND\s*FARMS", re.I), "Cumberland Farms", "convenience"),

    # ---- Home Improvement ----
    (re.compile(r"HOME\s*DEPOT", re.I), "The Home Depot", "home_improvement"),
    (re.compile(r"LOWE'?S", re.I), "Lowe's", "home_improvement"),
    (re.compile(r"MENARDS", re.I), "Menard's", "home_improvement"),
    (re.compile(r"ACE\s*HARDWARE", re.I), "Ace Hardware", "home_improvement"),
    (re.compile(r"TRUE\s*VALUE", re.I), "True Value", "home_improvement"),
    (re.compile(r"HARBOR\s*FREIGHT", re.I), "Harbor Freight", "home_improvement"),

    # ---- Electronics ----
    (re.compile(r"BEST\s*BUY", re.I), "Best Buy", "electronics"),
    (re.compile(r"APPLE\s*STORE", re.I), "Apple Store", "electronics"),
    (re.compile(r"MICRO\s*CENTER", re.I), "Micro Center", "electronics"),
    (re.compile(r"GAMESTOP", re.I), "GameStop", "electronics"),

    # ---- Pet ----
    (re.compile(r"PETCO", re.I), "Petco", "pet"),
    (re.compile(r"PETSMART", re.I), "PetSmart", "pet"),

    # ---- Dollar / Discount ----
    (re.compile(r"DOLLAR\s*TREE", re.I), "Dollar Tree", "dollar_store"),
    (re.compile(r"DOLLAR\s*GENERAL|DG\b", re.I), "Dollar General", "dollar_store"),
    (re.compile(r"FAMILY\s*DOLLAR", re.I), "Family Dollar", "dollar_store"),
    (re.compile(r"FIVE\s*BELOW", re.I), "Five Below", "dollar_store"),

    # ---- Clothing / Apparel ----
    (re.compile(r"OLD\s*NAVY", re.I), "Old Navy", "clothing"),
    (re.compile(r"GAP\b", re.I), "Gap", "clothing"),
    (re.compile(r"H\s*&\s*M\b", re.I), "H&M", "clothing"),
    (re.compile(r"ZARA\b", re.I), "Zara", "clothing"),
    (re.compile(r"NIKE\b", re.I), "Nike", "clothing"),
    (re.compile(r"FOOT\s*LOCKER", re.I), "Foot Locker", "clothing"),

    # ---- Auto ----
    (re.compile(r"AUTOZONE", re.I), "AutoZone", "auto"),
    (re.compile(r"O'?\s*REILLY", re.I), "O'Reilly Auto Parts", "auto"),
    (re.compile(r"ADVANCE\s*AUTO", re.I), "Advance Auto Parts", "auto"),
    (re.compile(r"NAPA\b", re.I), "NAPA Auto Parts", "auto"),

    # ---- Office ----
    (re.compile(r"STAPLES", re.I), "Staples", "office"),
    (re.compile(r"OFFICE\s*DEPOT|OFFICEMAX", re.I), "Office Depot", "office"),

    # ---- Home / Furniture ----
    (re.compile(r"IKEA", re.I), "IKEA", "home_improvement"),
    (re.compile(r"BED\s*BATH", re.I), "Bed Bath & Beyond", "home_improvement"),
    (re.compile(r"WAYFAIR", re.I), "Wayfair", "home_improvement"),

    # ---- Beauty ----
    (re.compile(r"ULTA", re.I), "Ulta Beauty", "department"),
    (re.compile(r"SEPHORA", re.I), "Sephora", "department"),
    (re.compile(r"BATH\s*(&|AND)\s*BODY", re.I), "Bath & Body Works", "department"),
]


def normalize_store_name(raw: str) -> tuple[str, str]:
    """Return (canonical_name, store_category)."""
    for pattern, canonical, category in _STORE_CATALOG:
        if pattern.search(raw):
            return canonical, category
    return raw.strip().title(), "unknown"


# ================================================================== #
# Store-category → receipt-level spending category
# ================================================================== #
# Maps store_category to a human-friendly receipt-level purchase category
# reflecting typical US monthly household spending buckets.

STORE_CATEGORY_TO_PURCHASE_TYPE: dict[str, str] = {
    "groceries": "Groceries",
    "wholesale_club": "Groceries",       # bulk grocery is still groceries
    "restaurant": "Dining Out",
    "pharmacy": "Health & Pharmacy",
    "convenience": "Convenience & Gas",
    "department": "Shopping & General",
    "home_improvement": "Home & Garden",
    "electronics": "Electronics & Tech",
    "pet": "Pet Care",
    "dollar_store": "Household Essentials",
    "clothing": "Clothing & Apparel",
    "auto": "Auto & Transport",
    "office": "Office & Supplies",
    "specialty_food": "Groceries",
    "unknown": "Other",
}


# ================================================================== #
# Item-level category classification (unchanged, expanded)
# ================================================================== #

_CATEGORY_RULES: list[tuple[re.Pattern, str, float]] = [
    # Produce
    (re.compile(r"\b(banana|apple|grape|orange|lemon|lime|avocado|tomato|onion|potato|lettuce|carrot|celery|pepper|cucumber|berr|strawberr|blueberr|raspberr|blackberr|mango|peach|pear|melon|watermelon|cantaloupe|spinach|kale|broccoli|garlic|ginger|zucchini|squash|mushroom|corn|cabbage|asparagus|artichoke|beet|radish|herb|cilantro|parsley|basil|mint|jalape)\b", re.I), "produce", 0.85),
    # Dairy
    (re.compile(r"\b(milk|cream|cheese|yogurt|butter|egg|sour cream|cottage|half\s*&\s*half|whipping|creamer)\b", re.I), "dairy", 0.85),
    # Bakery
    (re.compile(r"\b(bread|bagel|muffin|croissant|roll|bun|cake|donut|doughnut|pastry|cookie|pie|tortilla|pita|naan|biscuit|scone)\b", re.I), "bakery", 0.80),
    # Frozen
    (re.compile(r"\b(frozen|ice cream|frzn|popsicle|gelato|frozen pizza|frozen dinner|frozen meal|freezer)\b", re.I), "frozen", 0.80),
    # Meat & Seafood
    (re.compile(r"\b(chicken|beef|pork|steak|salmon|shrimp|fish|turkey|sausage|bacon|ham|ground|lamb|veal|tilapia|crab|lobster|tuna|cod|brisket|ribs|wing|thigh|breast|drumstick|meatball)\b", re.I), "meat_seafood", 0.80),
    # Beverages
    (re.compile(r"\b(water|soda|juice|coffee|tea|beer|wine|spirit|drink|beverage|cola|pepsi|sprite|gatorade|powerade|lemonade|kombucha|smoothie|energy drink|red bull|monster|lacroix|sparkling)\b", re.I), "beverages", 0.75),
    # Snacks
    (re.compile(r"\b(chip|cracker|pretzel|popcorn|snack|nut|trail mix|granola|candy|chocolate|gummy|jerky|rice cake|fruit snack)\b", re.I), "snacks", 0.70),
    # Household & Cleaning
    (re.compile(r"\b(soap|shampoo|toothpaste|deodorant|tissue|paper towel|toilet|detergent|bleach|trash bag|cleaning|wipe|sponge|dish\s*soap|laundry|fabric soft|dryer sheet|mop|broom|disinfect|lysol|clorox|febreze)\b", re.I), "household", 0.75),
    # Health & Personal Care
    (re.compile(r"\b(vitamin|medicine|tylenol|advil|ibuprofen|bandaid|band[\-\s]?aid|first aid|sunscreen|lotion|moisturizer|razor|shaving|tampon|pad|diaper|baby wipe|formula|thermometer)\b", re.I), "health_personal", 0.75),
    # Pantry / Dry Goods
    (re.compile(r"\b(rice|pasta|noodle|cereal|oatmeal|flour|sugar|salt|oil|vinegar|sauce|ketchup|mustard|mayo|dressing|soup|broth|bean|lentil|canned|spice|seasoning|honey|jam|jelly|peanut butter|syrup)\b", re.I), "pantry", 0.70),
    # Baby
    (re.compile(r"\b(diaper|baby food|formula|pacifier|baby|infant)\b", re.I), "baby", 0.75),
    # Pet
    (re.compile(r"\b(dog food|cat food|pet|kibble|litter|cat litter|puppy|kitten|pet treat)\b", re.I), "pet", 0.75),
]


def classify_item(description: str) -> tuple[str, float]:
    for pattern, category, conf in _CATEGORY_RULES:
        if pattern.search(description):
            return category, conf
    return "grocery", 0.5


def normalize_item(item: ItemSchema) -> ItemSchema:
    raw = item.description_raw

    # Prefer the LLM-provided human-readable name; fall back to title-cased raw
    if item.description_norm and item.description_norm.strip():
        norm = re.sub(r"\s+", " ", item.description_norm.strip())
    else:
        norm = re.sub(r"\s+", " ", raw.strip()).title()

    cat, cat_conf = classify_item(f"{raw} {norm}")  # classify on both raw + norm for better matching

    return item.model_copy(
        update={
            "description_norm": norm,
            "category": item.category or cat,
            "category_confidence": item.category_confidence or cat_conf,
            "total_price": round(item.total_price, 2),
            "unit_price": round(item.unit_price, 2) if item.unit_price is not None else None,
        }
    )


# ================================================================== #
# Full receipt normalization
# ================================================================== #


def normalize_receipt(receipt: ReceiptSchema, model_name: str) -> ReceiptSchema:
    warnings: list[str] = list(receipt.metadata.warnings)

    # Normalize store name + resolve store category
    canonical_name, store_cat = normalize_store_name(receipt.store.name)
    purchase_category = STORE_CATEGORY_TO_PURCHASE_TYPE.get(store_cat, "Other")

    store = receipt.store.model_copy(
        update={
            "name": canonical_name,
            "category": purchase_category,
            "city": receipt.store.city.strip().title() if receipt.store.city else None,
            "state": receipt.store.state.strip().upper() if receipt.store.state else None,
        }
    )

    # Normalize items
    items = [normalize_item(it) for it in receipt.items]

    # Normalize transaction totals
    txn = receipt.transaction.model_copy(
        update={
            "subtotal": round(receipt.transaction.subtotal, 2),
            "tax": round(receipt.transaction.tax, 2),
            "total": round(receipt.transaction.total, 2),
        }
    )

    # Consistency check
    line_sum = round(sum(it.total_price for it in items), 2)
    diff = abs(line_sum - txn.subtotal)
    confidence = receipt.metadata.confidence
    if diff > 0.10:
        warnings.append(
            f"Line-item sum ${line_sum:.2f} differs from subtotal ${txn.subtotal:.2f} by ${diff:.2f}"
        )
        confidence = max(0.0, confidence - 0.2)

    metadata = receipt.metadata.model_copy(
        update={
            "extraction_model": model_name,
            "confidence": round(confidence, 2),
            "warnings": warnings,
        }
    )

    return ReceiptSchema(store=store, transaction=txn, items=items, metadata=metadata)
