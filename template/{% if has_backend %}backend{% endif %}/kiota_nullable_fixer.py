"""Fix Kiota's incorrect nullable handling for anyOf string or null fields.

Kiota generates complex "composed types" for simple anyOf: [simple_type, null] schemas.
This script simplifies them back to Optional[str], Optional[bool], Optional[int], Optional[float], or Optional[datetime].

Open github issue: https://github.com/microsoft/kiota/issues/6869 (which just generally makes it challenging to use the composed types)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx


def load_openapi_schema(source: str) -> dict[str, Any]:
    """Load OpenAPI schema from URL or file path."""
    # Check if it looks like a URL
    if source.startswith(("http://", "https://")):
        try:
            response = httpx.get(source, timeout=5.0)
            _ = response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"Error fetching OpenAPI schema from {source}: {e}")
            sys.exit(1)
    else:
        # Treat as file path
        file_path = Path(source)
        if not file_path.exists():
            print(f"Error: OpenAPI schema file not found: {file_path}")
            sys.exit(1)
        try:
            with file_path.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading OpenAPI schema from {file_path}: {e}")
            sys.exit(1)


def get_anyof_simple_nullable_fields(schema: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Parse OpenAPI schema to find fields defined as anyOf: [simple_type, null].

    Returns: dict mapping model_name -> {field_name: type_name}
    """
    result: dict[str, dict[str, str]] = {}
    schemas = schema.get("components", {}).get("schemas", {})

    for model_name, model_schema in schemas.items():
        properties = model_schema.get("properties", {})
        simple_nullable_fields: dict[str, str] = {}

        for field_name, field_schema in properties.items():
            # Check if it's an anyOf with exactly 2 items
            if "anyOf" in field_schema:
                any_of: list[dict[str, Any]] = field_schema["anyOf"]
                if len(any_of) == 2:
                    # Check for null type
                    null_item: dict[str, Any] | None = None
                    other_item: dict[str, Any] | None = None
                    for item in any_of:
                        if item.get("type") == "null":
                            null_item = item
                        else:
                            other_item = item

                    if null_item and other_item:
                        other_type = other_item.get("type")
                        other_format = other_item.get("format")

                        # Handle arrays
                        if other_type == "array":
                            items = other_item.get("items", {})
                            item_type = items.get("type")
                            if item_type == "string":
                                simple_nullable_fields[field_name] = "list[str]"
                            elif item_type == "integer":
                                simple_nullable_fields[field_name] = "list[int]"
                            elif item_type == "number":
                                simple_nullable_fields[field_name] = "list[float]"
                            elif item_type == "boolean":
                                simple_nullable_fields[field_name] = "list[bool]"
                        # Handle string with date-time format
                        elif other_type == "string" and other_format == "date-time":
                            simple_nullable_fields[field_name] = "datetime"
                        # Handle regular simple types
                        elif other_type == "string":
                            simple_nullable_fields[field_name] = "str"
                        elif other_type == "boolean":
                            simple_nullable_fields[field_name] = "bool"
                        elif other_type == "integer":
                            simple_nullable_fields[field_name] = "int"
                        elif other_type == "number":
                            simple_nullable_fields[field_name] = "float"

        if simple_nullable_fields:
            result[model_name] = simple_nullable_fields

    return result


def pascal_to_snake(pascal_str: str) -> str:
    """Convert PascalCase to snake_case."""
    # Insert underscore before uppercase letters (except first)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", pascal_str)
    return snake.lower()


def camel_to_snake(camel_str: str) -> str:
    """Convert camelCase to snake_case."""
    # Insert underscore before uppercase letters
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", camel_str)
    return snake.lower()


def fix_composed_type_file(file_path: Path) -> bool:
    """Remove a composed type file that's no longer needed."""
    if file_path.exists():
        file_path.unlink()
        print(f"  Removed composed type file: {file_path.name}")
        return True
    return False


def fix_model_file(file_path: Path, model_name: str, fields: dict[str, str]) -> bool:
    """Fix a model file to use Optional[type] instead of composed types."""
    content = file_path.read_text()
    original_content = content

    needs_datetime_import = False

    for field, field_type in fields.items():
        # Convert field name from camelCase (in schema) to snake_case (in Python code)
        field_snake = camel_to_snake(field)

        # Convert to the composed type class name
        # NOTE: Kiota uses the camelCase field name in the class name, but snake_case in the file name
        composed_type_class_name = f"{model_name}_{field}"  # Uses camelCase field name

        # Determine the appropriate getter/writer methods and type name
        getter_method: str
        writer_method: str
        python_type: str
        primitive_type: str | None = None

        if field_type == "str":
            getter_method = "get_str_value"
            writer_method = "write_str_value"
            python_type = "str"
        elif field_type == "bool":
            getter_method = "get_bool_value"
            writer_method = "write_bool_value"
            python_type = "bool"
        elif field_type == "int":
            getter_method = "get_int_value"
            writer_method = "write_int_value"
            python_type = "int"
        elif field_type == "float":
            getter_method = "get_float_value"
            writer_method = "write_float_value"
            python_type = "float"
        elif field_type == "datetime":
            getter_method = "get_datetime_value"
            writer_method = "write_datetime_value"
            python_type = "datetime.datetime"
            needs_datetime_import = True
        elif field_type.startswith("list["):
            # Extract the inner type (e.g., "list[int]" -> "int")
            inner_type = field_type[5:-1]  # Remove "list[" and "]"
            getter_method = "get_collection_of_primitive_values"
            writer_method = "write_collection_of_primitive_values"
            python_type = field_type
            primitive_type = inner_type
        else:
            continue

        # 1. Fix the import statement - remove the composed type import (with any amount of leading/indentation whitespace)
        # Match both top-level and indented imports (e.g., inside if TYPE_CHECKING:)
        import_pattern = rf"^[ \t]*from \.{re.escape(pascal_to_snake(model_name))}_{re.escape(field_snake)} import {re.escape(composed_type_class_name)}\n"
        matches_before = len(re.findall(import_pattern, content, flags=re.MULTILINE))
        content = re.sub(import_pattern, "", content, flags=re.MULTILINE)
        if matches_before > 0:
            print(f"    Removed {matches_before} import(s) for {composed_type_class_name}")

        # 2. Fix the attribute declaration
        # Change: field_name: Optional[ComposedType] = None
        # To: field_name: Optional[str|bool|int|float|datetime.datetime] = None
        attr_pattern = (
            rf"(\s+{re.escape(field_snake)}:\s+)Optional\[{re.escape(composed_type_class_name)}\](\s*=\s*None)"
        )
        content = re.sub(attr_pattern, rf"\1Optional[{python_type}]\2", content)

        # 3. Fix get_field_deserializers
        # Change: lambda n: setattr(self, "field", n.get_object_value(ComposedType))
        # To: lambda n: setattr(self, "field", n.get_str_value()) or n.get_bool_value() etc.
        # Note: The key in the dict is camelCase (from JSON), but the attribute name is snake_case
        deserializer_pattern = rf'("{re.escape(field)}":\s+lambda\s+n\s*:\s*setattr\(self,\s*[\'"]{re.escape(field_snake)}[\'"]\s*,\s*)n\.get_object_value\({re.escape(composed_type_class_name)}\)\)'
        if primitive_type:
            # For collections, pass the type
            content = re.sub(deserializer_pattern, rf"\1n.{getter_method}({primitive_type}))", content)
        else:
            content = re.sub(deserializer_pattern, rf"\1n.{getter_method}())", content)

        # 4. Fix serialize method
        # Change: writer.write_object_value("field", self.field)
        # To: writer.write_str_value("field", self.field) or write_bool_value etc.
        # Note: The key is camelCase but the attribute is snake_case
        serialize_pattern = rf'writer\.write_object_value\("{re.escape(field)}",\s+self\.{re.escape(field_snake)}\)'
        content = re.sub(serialize_pattern, f'writer.{writer_method}("{field}", self.{field_snake})', content)

    # 5. Add datetime import if needed
    if needs_datetime_import and "import datetime" not in content:
        # Add after "from __future__ import annotations" line
        content = re.sub(r"(from __future__ import annotations\n)", r"\1import datetime\n", content)

    # 6. Clean up empty TYPE_CHECKING blocks
    # Remove: if TYPE_CHECKING:\n\n (with optional whitespace)
    empty_type_checking_pattern = r"if TYPE_CHECKING:\s*\n\s*\n"
    content = re.sub(empty_type_checking_pattern, "", content)

    # 7. Also remove TYPE_CHECKING from imports if the block is now gone
    if "if TYPE_CHECKING:" not in content:
        # Remove TYPE_CHECKING from the typing import
        content = re.sub(r",\s*TYPE_CHECKING", "", content)
        content = re.sub(r"TYPE_CHECKING,\s*", "", content)

    if content != original_content:
        _ = file_path.write_text(content)
        print(f"  Fixed model file: {model_name}")
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Kiota's incorrect nullable handling in generated Python models")
    _ = parser.add_argument(
        "openapi_source",
        help="OpenAPI schema source (URL starting with http:// or https://, or file path)",
    )
    _ = parser.add_argument(
        "kiota_dir",
        help="Path to the directory containing generated Kiota",
    )

    args = parser.parse_args()

    # Validate models directory
    models_dir = Path(args.kiota_dir) / "models"
    if not models_dir.exists():
        print(f"Error: Models directory not found: {models_dir.absolute()}")
        sys.exit(1)
    if not models_dir.is_dir():
        print(f"Error: Models path is not a directory: {models_dir.absolute()}")
        sys.exit(1)

    # Load OpenAPI schema
    print(f"Loading OpenAPI schema from: {args.openapi_source}")
    schema = load_openapi_schema(args.openapi_source)

    # Find fields to fix
    simple_nullable_fields = get_anyof_simple_nullable_fields(schema)

    if not simple_nullable_fields:
        print("No anyOf [simple_type, null] fields found in OpenAPI schema")
        return

    print(f"Found {len(simple_nullable_fields)} models with anyOf [simple_type, null] fields")

    fixed_models = 0
    removed_files = 0

    for model_name, fields in simple_nullable_fields.items():
        field_list = [f"{k}:{v}" for k, v in fields.items()]
        print(f"\nProcessing {model_name}: {', '.join(field_list)}")

        # Fix the main model file (convert PascalCase to snake_case)
        model_file = models_dir / f"{pascal_to_snake(model_name)}.py"
        if model_file.exists():
            if fix_model_file(model_file, model_name, fields):
                fixed_models += 1
        else:
            print(f"  Warning: Model file not found: {model_file}")

        # Remove composed type files
        for field in fields.keys():
            # Convert field name from camelCase to snake_case for the file name
            field_snake = camel_to_snake(field)
            composed_type_file = models_dir / f"{pascal_to_snake(model_name)}_{field_snake}.py"
            if fix_composed_type_file(composed_type_file):
                removed_files += 1

    print(f"\n✓ Fixed {fixed_models} model files")
    print(f"✓ Removed {removed_files} composed type files")


if __name__ == "__main__":
    main()
