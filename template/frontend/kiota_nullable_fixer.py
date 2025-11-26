"""Fix Kiota's incorrect nullable handling for required fields. Reads the OpenAPI schema and removes | null from required, non-nullable fields.

Open github issue: https://github.com/microsoft/kiota/issues/3911
"""

import json
import re
from pathlib import Path

# Path to OpenAPI schema
OPENAPI_SCHEMA = (
    Path(__file__).parent.parent
    / "backend"
    / "tests"
    / "unit"
    / "__snapshots__"
    / "test_basic_server_functionality"
    / "test_openapi_schema.json"
)
assert OPENAPI_SCHEMA.exists() is True
MODELS_DIR = Path(__file__).parent / "app" / "generated" / "open-api" / "backend" / "models"
assert MODELS_DIR.exists() is True


def get_required_non_nullable_fields() -> dict[str, set[str]]:
    """Parse OpenAPI schema to find required, non-nullable fields."""
    # pylint: disable=duplicate-code # in repositories with both frontends and backends, this function appears in both
    with OPENAPI_SCHEMA.open() as f:
        schema = json.load(f)

    result: dict[str, set[str]] = {}
    schemas = schema.get("components", {}).get("schemas", {})

    for model_name, model_schema in schemas.items():
        required_fields = set(model_schema.get("required", []))
        properties = model_schema.get("properties", {})

        non_nullable_required: set[str] = set()
        for field_name in required_fields:
            if field_name in properties:
                field_schema = properties[field_name]
                # Explicit nullable check - only include if explicitly not nullable
                is_nullable = field_schema.get("nullable")
                if is_nullable is False or ("nullable" not in field_schema):
                    non_nullable_required.add(field_name)

        if non_nullable_required:
            result[model_name] = non_nullable_required
    # pylint: enable=duplicate-code
    return result


def extract_model_block(content: str, model_name: str) -> tuple[str | None, int, int]:
    """Extract the specific model block from the file content.

    Returns: (block_content, start_pos, end_pos) or (None, -1, -1) if not found
    """
    # Look for "export interface ModelName" or "export type ModelName"
    pattern = rf"export\s+(?:interface|type)\s+{re.escape(model_name)}\s.*\{{"
    match = re.search(pattern, content)

    if not match:
        print(f"Could not find model {model_name} in content")
        return None, -1, -1

    start_pos = match.start()

    # Find the matching closing brace
    brace_count = 0
    in_block = False
    end_pos = -1

    for i in range(match.end() - 1, len(content)):
        if content[i] == "{":
            brace_count += 1
            in_block = True
        elif content[i] == "}":
            brace_count -= 1
            if in_block and brace_count == 0:
                end_pos = i + 1
                break

    if end_pos == -1:
        return None, -1, -1

    return content[start_pos:end_pos], start_pos, end_pos


def fix_typescript_file(file_path: Path, model_name: str, fields: set[str]) -> bool:
    """Fix nullable issues in a TypeScript model file."""
    content = file_path.read_text()

    # Extract the specific model block
    block_content, start_pos, end_pos = extract_model_block(content, model_name)

    if block_content is None:
        print(f"Could not find block content for {model_name} in {file_path}")
        return False

    original_block = block_content

    for field in fields:
        # Convert snake_case to camelCase for field matching
        camel_field = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), field)

        # Pattern 1: Remove trailing " | null" or "| null" from the type
        # This handles: fieldName?: SomeType | null; or fieldName: SomeType | null;
        pattern_null = rf"({camel_field}\??):\s*(.+?)\s*\|\s*null\s*;"
        block_content = re.sub(pattern_null, r"\1: \2;", block_content)

        # Pattern 2: Remove optional marker "?" for required fields
        # This handles: fieldName?: SomeType; -> fieldName: SomeType;
        pattern_optional = rf"{camel_field}\?:\s*([^;]+);"
        replacement_optional = rf"{camel_field}: \1;"
        block_content = re.sub(pattern_optional, replacement_optional, block_content)

    if block_content != original_block:
        # Replace the block in the original content
        new_content = content[:start_pos] + block_content + content[end_pos:]
        _ = file_path.write_text(new_content)
        print(f"Fixed {model_name}: {', '.join(fields)}")
        return True
    return False


def main():
    required_fields = get_required_non_nullable_fields()

    if not required_fields:
        print("No required non-nullable fields found in OpenAPI schema")
        return

    print(f"Found {len(required_fields)} models with required non-nullable fields: {required_fields}")

    fixed_count = 0
    for model_name, fields in required_fields.items():
        # Convert model name to filename (e.g., HealthcheckResponse -> index.ts)
        # Kiota puts all models in index.ts for TypeScript
        index_file = MODELS_DIR / "index.ts"

        if fix_typescript_file(index_file, model_name, fields):
            fixed_count += 1

    print(f"\nFixed {fixed_count} models")


if __name__ == "__main__":
    main()
