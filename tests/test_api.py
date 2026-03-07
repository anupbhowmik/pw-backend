"""Integration-style tests for the API (no DB, mock LLM)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

MOCK_LLM_RESPONSE = json.dumps({
    "store": {"name": "WAL*MART", "city": "austin", "state": "tx"},
    "transaction": {
        "purchase_datetime": "2024-03-15T14:30:00",
        "subtotal": 5.49,
        "tax": 0.45,
        "total": 5.94,
    },
    "items": [
        {"description_raw": "BANANAS", "total_price": 1.50, "quantity": 3, "unit_price": 0.50},
        {"description_raw": "BREAD WHOLE WHEAT", "total_price": 3.99, "quantity": 1},
    ],
})

# 1x1 white JPEG (smallest valid JPEG)
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300080606070605080707070909080a0c"
    "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c"
    "20242e2720222c231c1c2837292c30313434341f"
    "27393d38323c2e333432ffc0000b080001000101"
    "011100ffc4001f000001050101010101010000000"
    "0000000000102030405060708090a0bffc4002010"
    "000201030302040305050404000001770001020300"
    "0411ffda00080101000003f400bfd5368a28a00ffd9"
)


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_extract_requires_auth():
    """Extract endpoint now requires JWT auth — returns 403 without it."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/documents/extract",
            files={"file": ("receipt.jpg", TINY_JPEG, "image/jpeg")},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extract_bad_content_type():
    """Even with auth header, bad content type is rejected — but auth check comes first."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/documents/extract",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers={"Authorization": "Bearer fake-token"},
        )
    # Auth fails before content-type check
    assert resp.status_code == 401
