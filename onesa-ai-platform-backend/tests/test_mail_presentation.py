import pytest

from app.mail_presentation import identity_email_html_v1


def test_identity_mail_keeps_secret_out_of_preview_and_escapes_action():
    link = "https://ai.example.invalid/recovery#token=synthetic-token&x=<unsafe>"
    html = identity_email_html_v1("recovery", link, "https://ai.example.invalid")
    assert "Recover your account" in html
    assert "&amp;x=&lt;unsafe&gt;" in html
    assert "<unsafe>" not in html
    assert "prefers-color-scheme:dark" in html
    assert "synthetic-token" not in html.split("<title>")[1].split("</title>")[0]
    assert 'src="http' not in html


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "https://evil.invalid/reset",
        "https://name:pass@ai.example.invalid/reset",
    ],
)
def test_identity_mail_rejects_untrusted_action(link):
    with pytest.raises(ValueError, match="Untrusted"):
        identity_email_html_v1("recovery", link, "https://ai.example.invalid")
