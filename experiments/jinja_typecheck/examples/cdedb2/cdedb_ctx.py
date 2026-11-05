"""Types of what cdedb2 passes to its templates (a hand-written approximation).

``BaseContext`` is what ``AbstractFrontend.fill_template`` and ``render``
add for *every* template; each page's context extends it with the values
its frontend method passes to ``self.render(rs, "name", {...})``.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Collection, Mapping
from typing import Any, TypedDict

from typing_extensions import NotRequired

Notification = tuple[str, str, dict[str, Any]]


class User:
    persona_id: int | None
    username: str
    given_names: str
    nickname: str
    family_name: str
    roles: set[str]
    orga: set[int]
    caretaker: set[int]
    checkin_helper: set[int]
    moderator: set[int]
    presider: set[int]
    admin_views: Any
    available_admin_views: Any

    def persona_name(self, include_nickname: bool = False) -> str: ...


class Request:
    url: str
    base_url: str
    method: str


class BaseContext(TypedDict):
    # fill_template
    COUNTRY_CODES: Mapping[str, str]
    ambience: Mapping[str, Any]
    cdedblink: Callable[..., str]
    doclink: Callable[..., str]
    staticlink: Callable[..., str]
    errors: Mapping[str, list[Any]]
    request_time: Callable[[], datetime.timedelta]
    generation_time: Callable[[], datetime.timedelta]
    gettext: Callable[..., str]
    has_warnings: Callable[[], bool]
    is_admin: bool
    is_relevant_admin: Callable[..., bool]
    is_warning: Callable[[str], bool]
    lang: str
    n_: Callable[[str], str]
    ngettext: Callable[..., str]
    notifications: list[Notification]
    original_request: Request
    show_user_link: Callable[..., str]
    user: User
    values: Mapping[str, Any]
    original_endpoint: str
    requestargs: Mapping[str, Any]
    # render
    defect_username: str | None
    mls_with_defect_explicits: Mapping[str, Any] | None
    mandatory_fields: Collection[str]
    csp_nonce: str
    debug_data: NotRequired[Mapping[str, Any]]


class OptionalPageContext(BaseContext):
    """What a page may or may not pass (templates test these with `if`)."""

    jshint: NotRequired[str]
    login_form: NotRequired[bool]
    meta_info: NotRequired[Mapping[str, str | None]]
    mainnav_active: NotRequired[str]
    sidenav_active: NotRequired[str]


class Event:
    """The parts of ``cdedb.models.event.Event`` the index page reads."""

    id: int
    title: str
    begin: datetime.date
    end: datetime.date
    registration_start: datetime.datetime | None
    registration_soft_limit: datetime.datetime | None
    registration_hard_limit: datetime.datetime | None
    is_registration_approved: bool
    is_open: bool
    use_additional_questionnaire: bool
    tracks: Mapping[int, Any]


class ModeratedMailinglist(TypedDict):
    id: int
    title: str
    is_active: bool
    requests: int
    held_mails: int | None


class _OptionalDashboard(TypedDict, total=False):
    """Keys the template tests with ``'key' in dashboard`` before reading."""

    genesis_cases: int
    pending_changes: int
    privilege_changes: int


class Dashboard(_OptionalDashboard):
    """``CoreFrontend.index`` as it would look with defaults for the groups.

    Today ``index`` adds ``orga``, ``orga_registrations`` and ``present``
    (and the other groups) only when the user has something to show,
    and the template relies on them appearing together.
    A type checker cannot know that, so the case study assumes ``index``
    starts from ``orga=[]``, ``orga_registrations={}``, ``present=now()``,
    ``moderator={}`` and so on; the template's ``{% if dashboard.get('orga') %}``
    guards keep working unchanged.
    """

    orga: list[Event]
    orga_registrations: dict[int, int]
    present: datetime.datetime
    moderator: dict[int, ModeratedMailinglist]
    events: dict[int, Event]
    events_registration: dict[int, bool | None]
    events_payment_pending: dict[int, bool]
    assemblies: dict[int, Mapping[str, Any]]


class CoreIndexContext(BaseContext):
    meta_info: Mapping[str, str | None]
    dashboard: Dashboard
