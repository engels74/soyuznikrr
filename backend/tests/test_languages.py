"""Tests for the ISO 639-1 language module and endpoint.

Covers:
- LANGUAGES dict structure and content
- get_sorted_languages() ordering (en first, rest alphabetical by code)
- is_valid_language_code() acceptance and rejection
- GET /api/v1/languages endpoint response format and sorting
"""

import re

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from zondarr.api.wizards import list_languages
from zondarr.core.languages import (
    LANGUAGES,
    get_sorted_languages,
    is_valid_language_code,
)


class TestLanguagesDict:
    """Unit tests for the LANGUAGES constant."""

    def test_languages_has_expected_count(self) -> None:
        """LANGUAGES contains ~184 ISO 639-1 entries."""
        assert len(LANGUAGES) >= 180
        assert len(LANGUAGES) <= 190

    def test_all_keys_are_two_lowercase_letters(self) -> None:
        """Every key is exactly two lowercase ASCII letters."""
        pattern = re.compile(r"^[a-z]{2}$")
        for code in LANGUAGES:
            assert pattern.match(code), f"Invalid language code: {code!r}"

    def test_english_is_present(self) -> None:
        """English ('en') is in the LANGUAGES dict."""
        assert "en" in LANGUAGES
        assert LANGUAGES["en"] == "English"

    def test_all_values_are_non_empty_strings(self) -> None:
        """Every value is a non-empty string."""
        for code, name in LANGUAGES.items():
            assert isinstance(name, str), f"Value for {code!r} is not a string"
            assert len(name) > 0, f"Value for {code!r} is empty"


class TestGetSortedLanguages:
    """Unit tests for get_sorted_languages()."""

    def test_returns_list_of_tuples(self) -> None:
        """Returns a list of (code, name) tuples."""
        result = get_sorted_languages()
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_english_is_first(self) -> None:
        """English is the first entry."""
        result = get_sorted_languages()
        assert result[0] == ("en", "English")

    def test_rest_sorted_alphabetically_by_code(self) -> None:
        """All entries after English are sorted alphabetically by code."""
        result = get_sorted_languages()
        rest = result[1:]
        codes = [code for code, _ in rest]
        assert codes == sorted(codes)

    def test_length_matches_languages_dict(self) -> None:
        """Result length matches LANGUAGES dict."""
        result = get_sorted_languages()
        assert len(result) == len(LANGUAGES)

    def test_en_not_duplicated_in_rest(self) -> None:
        """English does not appear in the rest of the sorted list."""
        result = get_sorted_languages()
        rest_codes = [code for code, _ in result[1:]]
        assert "en" not in rest_codes


class TestIsValidLanguageCode:
    """Unit tests for is_valid_language_code()."""

    @pytest.mark.parametrize("code", ["en", "de", "fr", "es", "ja", "zh"])
    def test_accepts_valid_codes(self, code: str) -> None:
        """Known ISO 639-1 codes are accepted."""
        assert is_valid_language_code(code) is True

    @pytest.mark.parametrize("code", ["xx", "eng", "123", "", "EN", "e", "abc"])
    def test_rejects_invalid_codes(self, code: str) -> None:
        """Invalid codes (non-existent, wrong length, wrong case) are rejected."""
        assert is_valid_language_code(code) is False


class TestLanguagesEndpoint:
    """Integration tests for GET /api/v1/languages."""

    def test_returns_200_with_list(self) -> None:
        """Endpoint returns HTTP 200 with a list of language objects."""
        app = Litestar(route_handlers=[list_languages])

        with TestClient(app) as client:
            response = client.get("/api/v1/languages")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_entries_have_code_and_name_fields(self) -> None:
        """Each entry has 'code' and 'name' string fields."""
        app = Litestar(route_handlers=[list_languages])

        with TestClient(app) as client:
            response = client.get("/api/v1/languages")
            data = response.json()
            for entry in data:
                assert "code" in entry
                assert "name" in entry
                assert isinstance(entry["code"], str)
                assert isinstance(entry["name"], str)

    def test_english_is_first_entry(self) -> None:
        """English is the first entry in the response."""
        app = Litestar(route_handlers=[list_languages])

        with TestClient(app) as client:
            response = client.get("/api/v1/languages")
            data = response.json()
            assert data[0]["code"] == "en"
            assert data[0]["name"] == "English"

    def test_rest_sorted_by_code(self) -> None:
        """Entries after English are sorted alphabetically by code."""
        app = Litestar(route_handlers=[list_languages])

        with TestClient(app) as client:
            response = client.get("/api/v1/languages")
            data = response.json()
            rest_codes = [entry["code"] for entry in data[1:]]
            assert rest_codes == sorted(rest_codes)

    def test_total_count_matches_languages_dict(self) -> None:
        """Response length matches the LANGUAGES dict size."""
        app = Litestar(route_handlers=[list_languages])

        with TestClient(app) as client:
            response = client.get("/api/v1/languages")
            data = response.json()
            assert len(data) == len(LANGUAGES)
