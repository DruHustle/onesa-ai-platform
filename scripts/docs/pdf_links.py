"""Canonical publication references for public and protected PDF exports."""


def validate_manual_source_links(links, sources, scope):
    origin = (
        "https://docs.onesa.eu"
        if scope == "public"
        else "https://docs.engineering.onesa.eu"
    )
    for source in sources:
        assert origin + "/" + source.removesuffix(".md") in links, (
            f"{scope} PDF source link does not target its canonical documentation: {source}"
        )
