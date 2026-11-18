from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .parameter_location import ParameterLocation

@dataclass
class ValidationIssue(Parsable):
    """
    One reason a request failed validation, and where in the request it is.
    """
    # A machine-readable reason for the issue, from Pydantic's error types; more may be added.
    code: Optional[str] = None
    # What is wrong with the value, in words a person can act on.
    detail: Optional[str] = None
    # Where the invalid parameter is sent, spelled as OpenAPI's parameter `in`. Present only with `parameter`.
    in_: Optional[ParameterLocation] = None
    # The name of the invalid query, path, header or cookie parameter. Present only with `in`.
    parameter: Optional[str] = None
    # Where the invalid value is in the JSON request body, as a JSON Pointer (RFC 6901) in URI fragment form; `#` is the whole body. Present only for an issue in the body.
    pointer: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ValidationIssue:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ValidationIssue
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ValidationIssue()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        from .parameter_location import ParameterLocation

        from .parameter_location import ParameterLocation

        fields: dict[str, Callable[[Any], None]] = {
            "code": lambda n : setattr(self, 'code', n.get_str_value()),
            "detail": lambda n : setattr(self, 'detail', n.get_str_value()),
            "in": lambda n : setattr(self, 'in_', n.get_enum_value(ParameterLocation)),
            "parameter": lambda n : setattr(self, 'parameter', n.get_str_value()),
            "pointer": lambda n : setattr(self, 'pointer', n.get_str_value()),
        }
        return fields
    
    def serialize(self,writer: SerializationWriter) -> None:
        """
        Serializes information the current object
        param writer: Serialization writer to use to serialize this model
        Returns: None
        """
        if writer is None:
            raise TypeError("writer cannot be null.")
        writer.write_str_value("code", self.code)
        writer.write_str_value("detail", self.detail)
        writer.write_enum_value("in", self.in_)
        writer.write_str_value("parameter", self.parameter)
        writer.write_str_value("pointer", self.pointer)
    

