"""The AI model catalog must stay internally consistent with the settings catalog.

These are cheap structural guards: the catalog is hand-maintained data, and a typo in it
would surface as an empty dropdown or an unsaveable slot rather than a crash.
"""

from __future__ import annotations

import pytest

from src.llm.catalog import (
    PROVIDER_KEY_SETTINGS,
    PROVIDER_LABELS,
    ROLE_SPECS,
    ROLES,
    model_setting_key,
    provider_setting_key,
    role_spec,
)
from src.runtime_config import SPECS_BY_KEY


def test_every_role_is_described_exactly_once():
    assert tuple(spec.role for spec in ROLE_SPECS) == ROLES


@pytest.mark.parametrize("spec", ROLE_SPECS, ids=lambda s: s.role)
def test_role_offers_at_least_one_provider_and_a_default_that_serves_it(spec):
    assert spec.providers, f"{spec.role} has no providers"
    assert spec.default_provider in spec.providers


@pytest.mark.parametrize("spec", ROLE_SPECS, ids=lambda s: s.role)
def test_each_provider_recommends_exactly_one_model(spec):
    for provider, models in spec.providers.items():
        assert models, f"{spec.role}/{provider} has no models"
        recommended = [model for model in models if model.recommended]
        assert len(recommended) == 1, f"{spec.role}/{provider} must mark one recommended model"
        assert spec.recommended_model(provider) == recommended[0].id


@pytest.mark.parametrize("spec", ROLE_SPECS, ids=lambda s: s.role)
def test_every_provider_has_a_label_and_a_key_setting_that_exists(spec):
    for provider in spec.providers:
        assert provider in PROVIDER_LABELS
        key = PROVIDER_KEY_SETTINGS[provider]
        assert key in SPECS_BY_KEY, f"{key} is missing from the settings catalog"
        assert SPECS_BY_KEY[key].is_secret is True


@pytest.mark.parametrize("spec", ROLE_SPECS, ids=lambda s: s.role)
def test_each_slot_is_editable_from_the_dashboard(spec):
    provider_key = SPECS_BY_KEY[provider_setting_key(spec.role)]
    model_key = SPECS_BY_KEY[model_setting_key(spec.role)]

    assert set(spec.providers) <= set(provider_key.choices)
    assert "none" in provider_key.choices, "every slot must be switchable off"
    # Model ids move faster than releases, so a custom value is always accepted.
    assert model_key.allow_custom is True
    assert model_key.default == spec.recommended_model(spec.default_provider)


def test_unknown_role_fails_loudly():
    with pytest.raises(KeyError):
        role_spec("astrology")
