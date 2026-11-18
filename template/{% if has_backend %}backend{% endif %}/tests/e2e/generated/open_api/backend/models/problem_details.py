from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.api_error import APIError
from kiota_abstractions.serialization import Parsable, ParseNode, SerializationWriter
from typing import Any, Optional, TYPE_CHECKING, Union

@dataclass
class ProblemDetails(APIError, Parsable):
    """
    RFC 9457 problem details describing an error response.Returned (as application/problem+json) for error responses so clients and codegen tools such as Kiotahave a consistent, machine-readable error shape.
    """
    # A URI reference identifying the problem type.
    type: Optional[str] = "about:blank"
    # A human-readable explanation specific to this occurrence of the problem.
    detail: Optional[str] = None
    # The internal exception class name, when available.
    error_type: Optional[str] = None
    # The path of the request that met this problem, without its query string.
    instance: Optional[str] = None
    # The HTTP status code for this problem.
    status: Optional[int] = None
    # A short, human-readable summary of the problem.
    title: Optional[str] = None
    # Identifies this occurrence in the server's logs: search them for it to find what led to the problem.
    trace_id: Optional[str] = None
    
    @staticmethod
    def create_from_discriminator_value(parse_node: ParseNode) -> ProblemDetails:
        """
        Creates a new instance of the appropriate class based on discriminator value
        param parse_node: The parse node to use to read the discriminator value and create the object
        Returns: ProblemDetails
        """
        if parse_node is None:
            raise TypeError("parse_node cannot be null.")
        return ProblemDetails()
    
    def get_field_deserializers(self,) -> dict[str, Callable[[ParseNode], None]]:
        """
        The deserialization information for the current model
        Returns: dict[str, Callable[[ParseNode], None]]
        """
        fields: dict[str, Callable[[Any], None]] = {
            "detail": lambda n : setattr(self, 'detail', n.get_str_value()),
            "errorType": lambda n : setattr(self, 'error_type', n.get_str_value()),
            "instance": lambda n : setattr(self, 'instance', n.get_str_value()),
            "status": lambda n : setattr(self, 'status', n.get_int_value()),
            "title": lambda n : setattr(self, 'title', n.get_str_value()),
            "traceId": lambda n : setattr(self, 'trace_id', n.get_str_value()),
            "type": lambda n : setattr(self, 'type', n.get_str_value()),
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
        writer.write_str_value("detail", self.detail)
        writer.write_str_value("errorType", self.error_type)
        writer.write_str_value("instance", self.instance)
        writer.write_int_value("status", self.status)
        writer.write_str_value("title", self.title)
        writer.write_str_value("traceId", self.trace_id)
        writer.write_str_value("type", self.type)
    
    @property
    def primary_message(self) -> Optional[str]:
        """
        The primary error message.
        """
        if self.detail is not None:
            return '' if self.detail is None else self.detail
        return ''

