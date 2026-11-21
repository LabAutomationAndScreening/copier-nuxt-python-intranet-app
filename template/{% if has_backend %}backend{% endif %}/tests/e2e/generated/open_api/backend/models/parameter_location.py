from enum import Enum

class ParameterLocation(str, Enum):
    Query = "query",
    Path = "path",
    Header = "header",
    Cookie = "cookie",

