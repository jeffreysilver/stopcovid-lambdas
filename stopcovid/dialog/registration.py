import functools
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any, Dict

import requests
from marshmallow import Schema, fields, post_load


class CodeValidationPayloadSchema(Schema):
    valid = fields.Boolean(required=True)
    is_demo = fields.Boolean()
    account_info = fields.Mapping(keys=fields.Str(), allow_none=True)

    @post_load
    def make_code_validation_payload(self, data, **kwargs):
        return CodeValidationPayload(**data)


@dataclass
class CodeValidationPayload:
    valid: bool
    is_demo: bool = False
    account_info: Optional[Dict[str, Any]] = None


class RegistrationValidator(ABC):
    @abstractmethod
    def validate_code(self, code) -> CodeValidationPayload:
        pass


class DefaultRegistrationValidator(RegistrationValidator):
    @functools.lru_cache(maxsize=1024)
    def validate_code(self, code, **kwargs) -> CodeValidationPayload:
        url = kwargs.get("url", os.getenv("REGISTRATION_VALIDATION_URL"))
        key = kwargs.get("key", os.getenv("REGISTRATION_VALIDATION_KEY"))
        response = requests.post(
            url=url,
            json={"code": code},
            headers={"authorization": f"Basic {key}", "content-type": "application/json"},
        )
        return CodeValidationPayloadSchema().load(response.json())
