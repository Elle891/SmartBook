"""
Property tests for ISO 20022 field configuration (Task 25.1–25.2).

# Feature: smart-accounting-software, Properties 23–24
**Validates: Requirements 28.4, 28.5, 28.7**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from payment.fields import (
    VISIBILITY_HIDDEN,
    VISIBILITY_OPTIONAL,
    VISIBILITY_REQUIRED,
    FieldConfigValidationError,
    build_default_field_configs,
    default_visibility_for_field,
    enforce_mandatory_fields,
    merge_with_mandatory_defaults,
    render_form_fields,
)
from payment.pain001 import MANDATORY_FIELDS
from payment.routing_matrix import all_routing_settlement_pairs

_VISIBILITY = st.sampled_from([VISIBILITY_REQUIRED, VISIBILITY_OPTIONAL, VISIBILITY_HIDDEN])
_NON_MANDATORY = st.sampled_from(
    [f for f in (
        "debtor_name",
        "debtor_agent_bic",
        "exchange_rate",
        "remittance_information",
    )]
)


class TestProperty23MandatoryFieldsAlwaysRequired:
    @given(
        scope=st.sampled_from(["Domestic", "International"]),
        mandatory_override=st.sampled_from([VISIBILITY_OPTIONAL, VISIBILITY_HIDDEN]),
    )
    @settings(max_examples=40)
    def test_cannot_hide_or_optionalize_mandatory_field(
        self, scope: str, mandatory_override: str
    ) -> None:
        field = MANDATORY_FIELDS[0]
        config = {field: mandatory_override}
        with pytest.raises(FieldConfigValidationError):
            enforce_mandatory_fields(config)
        _ = scope

    @given(scope=st.sampled_from(["Domestic", "International"]))
    @settings(max_examples=20)
    def test_default_seed_marks_all_mandatory_required(self, scope: str) -> None:
        for s, routing, settlement, field_name, visibility in build_default_field_configs():
            if s != scope:
                continue
            if field_name in MANDATORY_FIELDS:
                assert visibility == VISIBILITY_REQUIRED
            _ = (routing, settlement)

    @given(field_name=_NON_MANDATORY, visibility=_VISIBILITY)
    @settings(max_examples=30)
    def test_merge_forces_mandatory_required(
        self, field_name: str, visibility: str
    ) -> None:
        merged = merge_with_mandatory_defaults({field_name: visibility})
        for mandatory in MANDATORY_FIELDS:
            assert merged[mandatory] == VISIBILITY_REQUIRED


class TestProperty24FormFieldsMatchConfiguration:
    @given(
        optional_visible=st.lists(_NON_MANDATORY, min_size=0, max_size=4, unique=True),
        hidden_fields=st.lists(_NON_MANDATORY, min_size=0, max_size=2, unique=True),
    )
    @settings(max_examples=50)
    def test_rendered_fields_are_required_plus_optional_only(
        self, optional_visible: list[str], hidden_fields: list[str]
    ) -> None:
        config: dict[str, str] = {m: VISIBILITY_REQUIRED for m in MANDATORY_FIELDS}
        for f in optional_visible:
            if f not in MANDATORY_FIELDS:
                config[f] = VISIBILITY_OPTIONAL
        for f in hidden_fields:
            if f not in MANDATORY_FIELDS:
                config[f] = VISIBILITY_HIDDEN

        rendered = render_form_fields(config)
        expected = sorted(
            name
            for name, vis in config.items()
            if vis in (VISIBILITY_REQUIRED, VISIBILITY_OPTIONAL)
        )
        assert rendered == expected
        for hidden in hidden_fields:
            if hidden not in MANDATORY_FIELDS:
                assert hidden not in rendered

    def test_default_visibilities_never_hide_mandatory(self):
        for scope in ("Domestic", "International"):
            for routing, _settlement in all_routing_settlement_pairs(payment_scope=scope):
                for field in MANDATORY_FIELDS:
                    assert (
                        default_visibility_for_field(field, routing_method=routing)
                        == VISIBILITY_REQUIRED
                    )
