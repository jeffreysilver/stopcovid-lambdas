import uuid
from typing import List, Dict, Any

from marshmallow import fields, post_load

from drills import drills
from .persistence import DialogRepository, DynamoDBDialogRepository
from . import types

VALID_OPT_IN_CODES = {"drill0"}


def process_command(command: types.Command, repo: DialogRepository = None):
    if repo is None:
        repo = DynamoDBDialogRepository()
    dialog_state = repo.fetch_dialog_state(command.phone_number)
    events = command.execute(dialog_state)
    for event in events:
        event.apply_to(dialog_state)
    repo.persist_dialog_state(events, dialog_state)


class StartDrill(types.Command):
    def __init__(self, phone_number: str, drill: drills.Drill):
        super().__init__(phone_number)
        self.drill = drill

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        return [DrillStarted(self.phone_number, self.drill)]


class TriggerReminder(types.Command):
    def __init__(self, phone_number: str, drill_id: uuid.UUID, prompt_slug: str):
        super().__init__(phone_number)
        self.prompt_slug = prompt_slug
        self.drill_id = drill_id

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        drill = dialog_state.current_drill
        if drill is None or drill.drill_id != self.drill_id:
            return []

        prompt = dialog_state.current_prompt_state
        if prompt is None or prompt.slug != self.prompt_slug:
            return []

        if prompt.reminder_triggered:
            # to ensure idempotence
            return []

        return [ReminderTriggered(self.phone_number)]


class ProcessSMSMessage(types.Command):
    def __init__(self, phone_number: str, content: str):
        super().__init__(phone_number)
        self.content = content.strip()
        self.content_lower = self.content.lower()

    def execute(self, dialog_state: types.DialogState) -> List[types.DialogEvent]:
        if not dialog_state.user_profile.validated:
            if self.content_lower in VALID_OPT_IN_CODES:
                return [UserCreated(self.phone_number)]
            return [UserCreationFailed(self.phone_number)]

        prompt = dialog_state.get_prompt()
        if prompt is None:
            return []
        events = []
        if prompt.should_advance_with_answer(self.content_lower):
            events.append(CompletedPrompt(self.phone_number, prompt, self.content))
            should_advance = True
        else:
            should_advance = dialog_state.current_prompt_state.failures >= prompt.max_failures
            events.append(FailedPrompt(self.phone_number, prompt, abandoned=should_advance))

        if should_advance:
            next_prompt = dialog_state.get_next_prompt()
            if next_prompt is not None:
                events.append(AdvancedToNextPrompt(self.phone_number, next_prompt))
                if dialog_state.is_next_prompt_last():
                    # assume the last prompt doesn't wait for an answer
                    events.append(DrillCompleted(self.phone_number, dialog_state.current_drill))
        return events


class DrillStartedSchema(types.DialogEventSchema):
    drill = fields.Nested(drills.DrillSchema, required=True)

    @post_load
    def make_drill_started(self, data, **kwargs):
        return DrillStarted(**data)


class DrillStarted(types.DialogEvent):
    def __init__(self, phone_number: str, drill: drills.Drill, **kwargs):
        super().__init__(
            DrillStartedSchema(),
            types.DialogEventType.DRILL_STARTED,
            phone_number,
            **kwargs
        )
        self.drill = drill
        self.prompt = drill.first_prompt()

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_drill = self.drill
        dialog_state.current_prompt_state = types.PromptState(
            self.prompt.slug,
            start_time=self.created_time
        )


class ReminderTriggeredSchema(types.DialogEventSchema):
    @post_load
    def make_reminder_triggered(self, data, **kwargs):
        return ReminderTriggered(**data)


class ReminderTriggered(types.DialogEvent):
    def __init__(self, phone_number: str, **kwargs):
        super().__init__(
            ReminderTriggeredSchema(),
            types.DialogEventType.REMINDER_TRIGGERED,
            phone_number,
            **kwargs
        )

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state.reminder_triggered = True


class UserCreatedSchema(types.DialogEventSchema):
    @post_load
    def make_user_created(self, data, **kwargs):
        return UserCreated(**data)


class UserCreated(types.DialogEvent):
    def __init__(self, phone_number: str, **kwargs):
        super().__init__(
            UserCreatedSchema(),
            types.DialogEventType.USER_CREATED,
            phone_number,
            **kwargs
        )

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.user_profile.validated = True


class UserCreationFailedSchema(types.DialogEventSchema):
    @post_load
    def make_user_creation_failed(self, data, **kwargs):
        return UserCreationFailed(**data)


class UserCreationFailed(types.DialogEvent):
    def __init__(self, phone_number: str, **kwargs):
        super().__init__(
            UserCreationFailedSchema(),
            types.DialogEventType.USER_CREATION_FAILED,
            phone_number,
            **kwargs
        )

    def apply_to(self, dialog_state: types.DialogState):
        pass


class CompletedPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)
    response = fields.String(required=True)

    @post_load
    def make_completed_prompt(self, data, **kwargs):
        return CompletedPrompt(**data)


class CompletedPrompt(types.DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, response: str, **kwargs):
        super().__init__(
            CompletedPromptSchema(),
            types.DialogEventType.COMPLETED_PROMPT,
            phone_number,
            **kwargs
        )
        self.prompt = prompt
        self.response = response

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state = None
        if self.prompt.response_user_profile_key:
            setattr(dialog_state.user_profile, self.prompt.response_user_profile_key, self.response)


class FailedPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)
    abandoned = fields.Boolean(required=True)

    @post_load
    def make_failed_prompt(self, data, **kwargs):
        return FailedPrompt(**data)


class FailedPrompt(types.DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, abandoned: bool, **kwargs):
        super().__init__(
            FailedPromptSchema(),
            types.DialogEventType.FAILED_PROMPT,
            phone_number,
            **kwargs
        )
        self.prompt = prompt
        self.abandoned = abandoned

    def apply_to(self, dialog_state: types.DialogState):
        if self.abandoned:
            dialog_state.current_prompt_state = None
        else:
            dialog_state.current_prompt_state.failures += 1


class AdvancedToNextPromptSchema(types.DialogEventSchema):
    prompt = fields.Nested(drills.PromptSchema, required=True)

    @post_load
    def make_advanced_to_next_prompt(self, data, **kwargs):
        return AdvancedToNextPrompt(**data)


class AdvancedToNextPrompt(types.DialogEvent):
    def __init__(self, phone_number: str, prompt: drills.Prompt, **kwargs):
        super().__init__(
            AdvancedToNextPromptSchema(),
            types.DialogEventType.ADVANCED_TO_NEXT_PROMPT,
            phone_number,
            **kwargs
        )
        self.prompt = prompt

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.current_prompt_state = types.PromptState(
            self.prompt.slug,
            start_time=self.created_time
        )


class DrillCompletedSchema(types.DialogEventSchema):
    drill = fields.Nested(drills.DrillSchema, required=True)

    @post_load
    def make_drill_completed(self, data, **kwargs):
        return DrillCompleted(**data)


class DrillCompleted(types.DialogEvent):
    def __init__(self, phone_number: str, drill: drills.Drill, **kwargs):
        super().__init__(
            DrillCompletedSchema(),
            types.DialogEventType.DRILL_COMPLETED,
            phone_number,
            **kwargs
        )
        self.drill = drill

    def apply_to(self, dialog_state: types.DialogState):
        dialog_state.completed_drills.append(dialog_state.current_drill)
        dialog_state.current_drill = None


def to_event(event_dict: Dict[str, Any]) -> types.DialogEvent:
    event_type = types.DialogEventType[event_dict['event_type']]
    if event_type == types.DialogEventType.ADVANCED_TO_NEXT_PROMPT:
        return AdvancedToNextPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.DRILL_COMPLETED:
        return DrillCompletedSchema().load(event_dict)
    if event_type == types.DialogEventType.USER_CREATION_FAILED:
        return UserCreationFailedSchema().load(event_dict)
    if event_type == types.DialogEventType.DRILL_STARTED:
        return DrillStartedSchema().load(event_dict)
    if event_type == types.DialogEventType.USER_CREATED:
        return UserCreatedSchema().load(event_dict)
    if event_type == types.DialogEventType.COMPLETED_PROMPT:
        return CompletedPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.FAILED_PROMPT:
        return FailedPromptSchema().load(event_dict)
    if event_type == types.DialogEventType.REMINDER_TRIGGERED:
        return ReminderTriggeredSchema().load(event_dict)
    raise ValueError(f"unknown event type {event_type}")
