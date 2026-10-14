# Applications and capabilities

## Chat
Create, rename, reopen and delete owned conversations. Stream Markdown responses and stop generation. Completed messages persist; interrupted partial output does not become a successful saved answer. The badge shows the active backend; runtime model selection is configuration-driven.

[Open Chat](https://platform.onesa.eu/).

## Knowledge
Upload bounded TXT/PDF documents, search owned sources and select documents for grounded Chat. Preview extracted text and rebuild a document’s search index using the configured
embedding service. Reindex clears the displayed search results; it does not qualify
a new model. Sources persist with answers. The active default remains a labelled lexical baseline. An optional pinned Qwen
embedding service has passed a small local EN/DE retrieval evaluation; production
hosting and wider language/domain quality remain unqualified. Switching requires
controlled document reindexing.

[Open Knowledge](https://platform.onesa.eu/knowledge).

## Agents
Grant registered arithmetic or text_stats tools explicitly. Planning may use mock or the configured model; proposals cannot authorize new tools. Local tools have bounded execution and no arbitrary shell/network effects.

[Open Agents](https://platform.onesa.eu/agents).

## Travel
Generate, save and revise typed itineraries. External provider availability is explicit; no live prices, weather, bookings or maps are claimed.

[Open Travel](https://platform.onesa.eu/travel).

See [visual tutorials](/tutorials) and [API examples](examples.md).


## Account settings

Open **Account settings** from Chat or any workspace feature. Update your display
name, change your password, review active sessions or sign out other sessions.
Password changes sign out all previous sessions and rotate this browser’s session.
Your interface language is a browser preference, independent of your profile.

Download an account JSON export after confirming your password. It contains private
content: store it securely. The export includes live profile, conversations, extracted
documents, agent runs and trips; credentials and derived vectors are excluded.
Large exports require support and are never silently truncated.

Account deletion requires your password and typing `DELETE MY ACCOUNT`. Stop active
chat/tool runs and export anything you need first. Deletion removes your live account,
sessions and owned application data, including document search vectors. Backup copies
require separate retention processing. This action cannot be undone through the app.
