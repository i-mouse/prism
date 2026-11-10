"""paper_context_cache's optional ttl_s: None keeps the claim-count rule, an int is used as given."""
import asyncio

from extraction.context_cache import MAX_TTL_S, ContextCacheStats, paper_context_cache, ttl_for_claims

import replay_fakes


def _created_ttl(n_claims: int, **kwargs) -> str:
    sdk = replay_fakes.FakeSdk()

    async def run():
        async with paper_context_cache(
            sdk.client, replay_fakes.MODEL, "invented paper", n_claims, ContextCacheStats(), **kwargs,
        ) as cache:
            assert cache is not None and cache.ttl_s == int(sdk.created[0].ttl.rstrip("s"))

    asyncio.run(run())
    return sdk.created[0].ttl


def test_ttl_s_none_gives_the_same_ttl_as_before():
    assert _created_ttl(3) == f"{ttl_for_claims(3)}s" == "300s"
    assert _created_ttl(10) == f"{ttl_for_claims(10)}s" == "638s"
    assert _created_ttl(3, ttl_s=None) == "300s"


def test_ttl_s_3600_gives_3600_seconds():
    assert MAX_TTL_S == 3600
    assert _created_ttl(3, ttl_s=3600) == "3600s"
    assert _created_ttl(10, ttl_s=MAX_TTL_S) == "3600s"
