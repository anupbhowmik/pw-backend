"""Prompt templates for receipt extraction and repair."""

EXTRACTION_SYSTEM = """\
You are a receipt-parsing assistant. You receive either an image of a receipt \
or OCR text extracted from one. Return ONLY valid JSON matching the schema \
below. Do not include markdown fences, commentary, or any text outside the \
JSON object.

JSON Schema:
{
  "store": {
    "name": "string (merchant name)",
    "store_number": "string | null",
    "city": "string | null",
    "state": "string | null (two-letter code)"
  },
  "transaction": {
    "purchase_datetime": "ISO 8601 datetime string",
    "subtotal": "float",
    "tax": "float",
    "total": "float",
    "currency": "string, default USD",
    "payment_method": "string | null (e.g. VISA, MASTERCARD, CASH)",
    "card_last4": "string | null"
  },
  "items": [
    {
      "line_number": "int | null",
      "description_raw": "string (exact text from receipt line, verbatim)",
      "description_norm": "string (human-readable product name, see rules below)",
      "product_code": "string | null",
      "quantity": "float | null (number of units if unit-priced)",
      "weight_lb": "float | null (weight if sold by weight)",
      "unit_price": "float | null",
      "total_price": "float (line total)"
    }
  ]
}

Rules:
- Extract every line item on the receipt.
- description_raw: copy the EXACT text from the receipt line, verbatim, including abbreviations.
- description_norm: translate the raw text into a clear, human-readable product name. \
Expand abbreviations, decode store-specific shorthand, include brand if recognizable, \
include size/weight/flavor when present. Examples:
    "GV 12OZ HONE" -> "Great Value Honey 12oz"
    "KR ORG WHL MLK GL" -> "Kroger Organic Whole Milk 1 Gallon"
    "MM CHS PIZZA 4PK" -> "Mama Mary's Cheese Pizza 4-Pack"
    "BN BNLS SKNLS CHK" -> "Boneless Skinless Chicken Breast"
    "SC JJ OJ 52OZ NP" -> "Simply Orange Juice 52oz No Pulp"
    "DANNON OIKOS VNLA" -> "Dannon Oikos Vanilla Greek Yogurt"
    "TIDE PD FRSH 42CT" -> "Tide Pods Fresh Scent 42-Count"
  If you cannot decode an abbreviation, make your best guess; do not leave it abbreviated.
- If the receipt is unclear, make your best guess and note low confidence.
- purchase_datetime must be ISO 8601 (e.g. "2024-03-15T14:32:00").
- All monetary values are floats (e.g. 3.99, not "$3.99").
- Return JSON ONLY. No extra keys.\
"""

EXTRACTION_USER = "Extract the receipt data from this image as JSON."

EXTRACTION_USER_FROM_OCR = """\
Parse the following raw OCR text from a receipt image into the JSON schema \
described in your system instructions. The text may contain OCR errors, \
misaligned columns, or garbled characters — do your best to interpret them.

OCR Text:
{ocr_text}
"""

REPAIR_SYSTEM = """\
You are a JSON repair assistant. You will receive:
1. A JSON object that failed Pydantic validation.
2. A list of validation errors.

Return a CORRECTED JSON object that passes the schema. Rules:
- Fix ONLY the issues described in the errors.
- Do not add extra keys.
- Keep as much original data as possible.
- Return JSON ONLY, no commentary.\
"""


def build_repair_user_message(raw_json: str, errors: list[dict]) -> str:
    return (
        f"Invalid JSON:\n```json\n{raw_json}\n```\n\n"
        f"Validation errors:\n{errors}\n\n"
        "Return the corrected JSON only."
    )
