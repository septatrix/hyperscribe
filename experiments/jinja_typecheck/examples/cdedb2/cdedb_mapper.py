"""Maps a cdedb2 frontend module and render() template name to the template path."""

import re


def mapper(module, cls, template):
    """cdedb.frontend.<realm>[.sub] + "index" -> "web/<realm>/index.tmpl"."""
    match = re.match(r"cdedb\.frontend\.(\w+)", module)
    if not match or match[1] in ("common",):
        return None
    return f"web/{match[1]}/{template}.tmpl"
