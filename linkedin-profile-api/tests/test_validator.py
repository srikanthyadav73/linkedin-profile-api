from app.utils.validator import is_valid_linkedin_profile_url


def test_valid_profile_url() -> None:
    assert is_valid_linkedin_profile_url("https://www.linkedin.com/in/example/")


def test_valid_profile_url_no_trailing_slash() -> None:
    assert is_valid_linkedin_profile_url("https://www.linkedin.com/in/example")


def test_valid_profile_url_without_www() -> None:
    assert is_valid_linkedin_profile_url("https://linkedin.com/in/example")


def test_invalid_domain() -> None:
    assert not is_valid_linkedin_profile_url("https://google.com")


def test_invalid_not_a_url() -> None:
    assert not is_valid_linkedin_profile_url("not-a-url")


def test_invalid_empty_string() -> None:
    assert not is_valid_linkedin_profile_url("")


def test_invalid_company_page_not_profile() -> None:
    assert not is_valid_linkedin_profile_url("https://www.linkedin.com/company/example/")


def test_invalid_http_not_https() -> None:
    assert not is_valid_linkedin_profile_url("http://www.linkedin.com/in/example/")


def test_valid_country_subdomains() -> None:
    assert is_valid_linkedin_profile_url("https://in.linkedin.com/in/madan-surthani-7a90571ba")
    assert is_valid_linkedin_profile_url("https://uk.linkedin.com/in/example-slug")
    assert is_valid_linkedin_profile_url("https://ca.linkedin.com/in/example-slug/")


def test_invalid_lookalike_domain() -> None:
    assert not is_valid_linkedin_profile_url("https://evil.com/?next=linkedin.com")

