from __future__ import annotations

from app.models.config_models import DedupConfig
from app.services.dedup_service import DedupService


def test_candidate_urls_canonical_first() -> None:
    svc = DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True))
    assert svc.candidate_urls("https://a.com/x", "https://a.com/canonical") == [
        "https://a.com/canonical",
        "https://a.com/x",
    ]


def test_candidate_urls_unique_values() -> None:
    svc = DedupService(DedupConfig(use_canonical_url_first=True, strip_tracking_params=True))
    assert svc.candidate_urls("https://a.com/x", "https://a.com/x") == ["https://a.com/x"]


def test_candidate_urls_original_first() -> None:
    svc = DedupService(DedupConfig(use_canonical_url_first=False, strip_tracking_params=True))
    assert svc.candidate_urls("https://a.com/x", "https://a.com/c") == ["https://a.com/x", "https://a.com/c"]
