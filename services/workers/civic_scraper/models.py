from dataclasses import asdict, dataclass, field


@dataclass
class Meeting:
    source: str
    jurisdiction: str
    body: str
    date: str
    time: str | None
    location: str | None
    meeting_details_url: str | None
    agenda_url: str | None
    minutes_url: str | None
    video_url: str | None

    def to_dict(self):
        return asdict(self)


@dataclass
class Attachment:
    name: str
    url: str

    def to_dict(self):
        return asdict(self)


@dataclass
class LegislationDetails:
    legislation_url: str
    status: str | None
    text: str | None
    recommendations: str | None
    attachments: list[Attachment] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["attachments"] = [a.to_dict() for a in self.attachments]
        return d


@dataclass
class AgendaItem:
    file_number: str | None
    title: str
    type: str | None
    agenda_note: str | None
    legislation_url: str | None
    action: str | None
    result: str | None
    version: str | None

    @property
    def is_consent(self) -> bool:
        return bool(self.type and "consent" in self.type.lower())

    def to_dict(self):
        d = asdict(self)
        d["is_consent"] = self.is_consent
        return d
