import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("field", ["mail_from", "mail_reply_to"])
@pytest.mark.parametrize(
    "value",
    [
        "Onesa AI <notifications-ai@onesa.eu>\r\nBcc: victim@example.com",
        "first@onesa.eu, second@onesa.eu",
        "Onesa <first@onesa.eu>, <second@onesa.eu>",
        "Onesa <not-an-address>",
        "Onesa\x00 <notifications-ai@onesa.eu>",
        " " * 321 + "sender@onesa.eu",
    ],
)
def test_mail_configuration_refuses_injection_and_multiple_addresses(field, value):
    with pytest.raises(ValidationError) as failure:
        Settings(**{field: value})
    assert value not in str(failure.value)


@pytest.mark.parametrize(
    "value",
    [
        "Onesa AI <notifications-ai@onesa.eu>",
        "Onesa Accounts <accounts@onesa.eu>",
        '"Onesa, AI" <notifications-ai@onesa.eu>',
        "notifications-ai@onesa.eu",
        "Onesa AI <noreply@mail.onesa.eu>",
        "",
    ],
)
def test_mail_configuration_preserves_explicit_header_bytes(value):
    settings = Settings(mail_from=value, mail_reply_to=value)
    assert settings.mail_from == value
    assert settings.mail_reply_to == value


def test_mail_credentials_are_excluded_from_configuration_repr():
    settings = Settings(
        mail_provider="resend",
        resend_api_key="<synthetic-provider-key-not-for-logs>",
        auth_delivery_key="<synthetic-delivery-key>" + "x" * 48,
        mail_from="Onesa AI <notifications-ai@onesa.eu>",
    )
    assert settings.resend_api_key not in repr(settings)
    assert settings.auth_delivery_key not in repr(settings)


def test_mail_stays_disabled_without_configuration_and_requires_sender_when_enabled():
    assert Settings().mail_provider == "disabled"
    with pytest.raises(ValidationError):
        Settings(
            mail_provider="resend",
            resend_api_key="<synthetic-provider-key>",
            auth_delivery_key="<synthetic-delivery-key>" + "x" * 48,
        )
