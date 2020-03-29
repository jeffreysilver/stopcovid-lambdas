import enum
from abc import abstractmethod, ABC
import datetime
from typing import Optional, List

from marshmallow import Schema, fields, post_load
from drills import drills


class UserProfileSchema(Schema):
    validated = fields.Boolean(required=True)
    language = fields.Str(allow_none=True)
    name = fields.Str(allow_none=True)
    self_rating = fields.Str(allow_none=True)

    @post_load
    def make_user_profile(self, data, **kwargs):
        return UserProfile(**data)


class UserProfile:
    def __init__(self,
                 validated: bool,
                 name: Optional[str] = None,
                 language: Optional[str] = None,
                 self_rating: Optional[str] = None
                 ):
        self.language = language
        self.validated = validated
        self.name = name
        self.self_rating = self_rating

    def __str__(self):
        return (f"lang={self.language}, validated={self.validated}, "
                f"name={self.name}, rating={self.self_rating}")


class PromptStateSchema(Schema):
    slug = fields.Str(required=True)
    start_time = fields.DateTime(required=True)
    failures = fields.Int(allow_none=True)
    reminder_triggered = fields.Boolean(allow_none=True)

    @post_load
    def make_prompt_state(self, data, **kwargs):
        return PromptState(**data)


class PromptState:
    def __init__(self, slug: str, start_time: datetime.datetime,
                 reminder_triggered: bool = False, failures: int = 0):
        self.slug = slug
        self.failures = failures
        self.start_time = start_time
        self.reminder_triggered = reminder_triggered


class DialogStateSchema(Schema):
    phone_number = fields.Str(required=True)
    user_profile = fields.Nested(UserProfileSchema, allow_none=True)
    # persist the entire drill so that modifications to drills don"t affect
    # drills that are in flight
    current_drill = fields.Nested(drills.DrillSchema, allow_none=True)
    current_prompt_state = fields.Nested(PromptStateSchema, allow_none=True)
    completed_drills = fields.List(fields.Nested(drills.DrillSchema), allow_none=True)

    @post_load
    def make_dialog_state(self, data, **kwargs):
        return DialogState(**data)


class DialogState:
    def __init__(self,
                 phone_number: str,
                 user_profile: Optional[UserProfile] = None,
                 current_drill: Optional[drills.Drill] = None,
                 current_prompt_state: Optional[PromptState] = None,
                 completed_drills: List[drills.Drill] = None):
        self.phone_number = phone_number
        self.user_profile = user_profile or UserProfile(validated=False)
        self.current_drill = current_drill
        self.current_prompt_state = current_prompt_state
        self.completed_drills = completed_drills or []

    def get_prompt(self) -> Optional[drills.Prompt]:
        if self.current_drill is None or self.current_prompt_state is None:
            return None
        return self.current_drill.get_prompt(self.current_prompt_state.slug)

    def get_next_prompt(self) -> Optional[drills.Prompt]:
        return self.current_drill.get_next_prompt(self.current_prompt_state.slug)

    def is_next_prompt_last(self) -> bool:
        return self.current_drill.prompts[-1].slug == self.get_next_prompt().slug


class DialogEventType(enum.Enum):
    DRILL_STARTED = "DRILL_STARTED"
    REMINDER_TRIGGERED = "REMINDER_TRIGGERED"
    USER_CREATED = "USER_CREATED"
    USER_CREATION_FAILED = "USER_CREATION_FAILED"
    COMPLETED_PROMPT = "COMPLETED_PROMPT"
    FAILED_PROMPT = "FAILED_PROMPT"
    ADVANCED_TO_NEXT_PROMPT = "ADVANCED_TO_NEXT_PROMPT"
    DRILL_COMPLETED = "DRILL_COMPLETED"


class DialogEvent(ABC):
    def __init__(self, event_type: DialogEventType, phone_number: str):
        self.phone_number = phone_number
        self.datetime = datetime.datetime.utcnow()
        self.event_type = event_type

    @abstractmethod
    def apply_to(self, dialog_state: DialogState):
        pass


class Command(ABC):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number

    @abstractmethod
    def execute(self, dialog_state: DialogState) -> List[DialogEvent]:
        pass
