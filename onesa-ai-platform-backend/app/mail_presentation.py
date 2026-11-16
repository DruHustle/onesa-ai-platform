"""Onesa email design 1.0.0; immutable rendering for versioned identity jobs."""

from html import escape
from string import Template
from urllib.parse import urlsplit

# Generated from the locally versioned Onesa email design; no remote assets.
_TEMPLATE = Template(
    '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name'
    '="viewport" content="width=device-width, initial-scale=1"><meta name="'
    'color-scheme" content="light dark"><meta name="supported-color-schemes'
    '" content="light dark"><title>$title</title>\n<style>body,table,td,a{-w'
    "ebkit-text-size-adjust:100%;-ms-text-size-adjust:100%}table{border-col"
    "lapse:collapse}img{border:0;outline:none}a:focus-visible{outline:3px s"
    "olid #9bc8ff;outline-offset:4px}@media screen and (max-width:480px){.o"
    "uter{padding:20px 10px!important}.hero{padding:26px 24px!important}.co"
    "ntent{padding:28px 24px!important}.title{font-size:29px!important}.foo"
    "ter{padding:22px 24px!important}.action{width:100%!important}.action a"
    "{display:block!important;text-align:center!important}.detail-cell{font"
    "-size:12px!important}}@media(prefers-color-scheme:dark){.canvas{backgr"
    "ound-color:#0b1523!important}.card{background-color:#14243a!important;"
    "border-color:#557a9e!important}.copy,.title{color:#e5edf6!important}.m"
    "uted{color:#b4c4d6!important}.note,.code{background-color:#0b1523!impo"
    "rtant}.details,.detail-cell,.footer,.code{border-color:#557a9e!importa"
    "nt}.fallback{color:#9bc8ff!important}.status-info{background-color:#17"
    "3249!important;color:#d6edf9!important}.status-warning{background-colo"
    "r:#382b16!important;color:#ffdf91!important}.status-success{background"
    "-color:#1d392a!important;color:#a5e2b7!important}}@media(forced-colors"
    ":active){.card,.code,.note{border:1px solid CanvasText!important}a{col"
    'or:LinkText!important}}</style></head>\n<body class="canvas" style="mar'
    "gin:0;padding:0;background-color:#edf2f7;font-family:Arial, Helvetica,"
    ' sans-serif;">\n<div style="display:none;max-height:0;max-width:0;overf'
    'low:hidden;opacity:0;mso-hide:all;">$preview</div>\n<table role="presen'
    'tation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><t'
    'd align="center" class="outer" style="padding:40px 16px;">\n<!--[if mso'
    ']><table role="presentation" width="600" align="center"><tr><td><![end'
    'if]-->\n<table role="presentation" width="100%" cellpadding="0" cellspa'
    'cing="0" border="0" class="card" style="max-width:600px;table-layout:f'
    "ixed;background-color:#ffffff;border:1px solid #dae1e9;border-radius:1"
    '2px;overflow:hidden;">\n<tr><td class="hero" bgcolor="#10263e" style="p'
    "adding:28px 36px;background-color:#10263e;border-bottom:4px solid #236"
    '6d1;">\n<table role="presentation" width="100%" cellpadding="0" cellspa'
    'cing="0"><tr><td style="color:#ffffff;font-size:22px;letter-spacing:3p'
    'x;font-weight:bold;vertical-align:middle;">ONESA</td></tr></table>\n<p '
    'style="margin:12px 0 0;color:#b4c4d6;font-size:13px;line-height:20px;"'
    '>Onesa AI</p></td></tr>\n<tr><td class="content" style="padding:34px 36'
    'px 32px;overflow-wrap:anywhere;word-break:break-word;">\n<p class="mute'
    'd" style="margin:0 0 14px;color:#56677b;font-size:11px;line-height:18p'
    'x;letter-spacing:1.8px;text-transform:uppercase;font-weight:bold;">Acc'
    'ount security</p>\n<h1 class="title" style="margin:0 0 20px;color:#1026'
    "3e;font-family:Arial, Helvetica, sans-serif;font-size:34px;line-height"
    ':1.16;letter-spacing:-0.7px;font-weight:bold;">$title</h1>\n\n<p class="'
    'copy" style="margin:0 0 16px;color:#10263e;font-size:16px;line-height:'
    '27px;">$intro</p><table role="presentation" cellpadding="0" cellspacin'
    'g="0" border="0" class="action" style="margin:28px 0;"><tr><td bgcolor'
    '="#2366d1" style="border-radius:8px;mso-padding-alt:16px 26px;"><a hre'
    'f="$link" style="display:inline-block;background-color:#2366d1;border:'
    "1px solid #2366d1;border-radius:8px;padding:16px 26px;font-family:Aria"
    "l, Helvetica, sans-serif;font-size:16px;line-height:22px;font-weight:b"
    'old;text-decoration:none;color:#ffffff;">$action &nbsp;→</a></td></tr>'
    '</table><table role="presentation" class="note" width="100%" cellpaddi'
    'ng="0" cellspacing="0" style="margin:26px 0 0;background-color:#f5f7fa'
    ';border-left:3px solid #2366d1;"><tr><td class="muted" style="padding:'
    '16px 18px;color:#56677b;font-size:13px;line-height:21px;">Open this pr'
    "ivate, expiring link only if you expected this message. Never share yo"
    'ur access link.</td></tr></table><p class="muted" style="margin:22px 0'
    ' 5px;color:#56677b;font-size:12px;line-height:19px;">Button not workin'
    'g? Copy the complete link into your browser:</p><p style="margin:0;fon'
    't-size:12px;line-height:19px;word-break:break-all;"><a class="fallback'
    '" href="$link" style="color:#2366d1;text-decoration:underline;word-bre'
    'ak:break-all;">$link</a></p>\n</td></tr>\n<tr><td class="footer" style="'
    'padding:22px 36px 26px;border-top:1px solid #dae1e9;"><p class="muted"'
    ' style="margin:0 0 5px;color:#56677b;font-size:11px;line-height:18px;f'
    'ont-weight:bold;">Onesa AI · Onesa</p><p class="muted" style="margin:0'
    ' 0 5px;color:#56677b;font-size:11px;line-height:18px;">This message co'
    "ncerns your Onesa AI account.</p></td></tr>\n</table><!--[if mso]></td>"
    '</tr></table><![endif]-->\n<p class="muted" style="margin:20px 0 0;colo'
    "r:#56677b;font-family:Arial, Helvetica, sans-serif;font-size:11px;line"
    '-height:18px;">ONESA &nbsp;/&nbsp; Onesa AI</p>\n</td></tr></table></bo'
    "dy></html>"
)


def identity_email_html_v1(purpose: str, link: str, origin: str) -> str:
    target, trusted = urlsplit(link), urlsplit(origin)
    if (
        trusted.scheme != "https"
        or trusted.username
        or trusted.password
        or trusted.path not in {"", "/"}
        or trusted.query
        or trusted.fragment
        or target.scheme != trusted.scheme
        or target.netloc != trusted.netloc
        or target.username
        or target.password
        or "\r" in link
        or "\n" in link
    ):
        raise ValueError("Untrusted identity email action")
    invitation = purpose == "invitation"
    if purpose not in {"invitation", "recovery"}:
        raise ValueError("Unknown identity email purpose")
    return _TEMPLATE.substitute(
        link=escape(link, quote=True),
        title="You're invited to Onesa AI" if invitation else "Recover your account",
        preview="Your invitation to Onesa AI."
        if invitation
        else "Instructions for your requested password recovery.",
        intro="You have been invited to Onesa AI. Use your private link to continue."
        if invitation
        else "A password reset was requested for your Onesa AI account.",
        action="Accept invitation" if invitation else "Reset password",
    )
