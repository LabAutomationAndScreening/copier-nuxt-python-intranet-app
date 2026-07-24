from pathlib import Path

from jinja2 import Environment
from jinja2.ext import Extension


class TemplateDefaultExtension(Extension):
    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        environment.globals["initial_copier_run"] = not Path(".copier-answers.yml").exists()  # pyright:ignore[reportArgumentType] # no good typing for globals
