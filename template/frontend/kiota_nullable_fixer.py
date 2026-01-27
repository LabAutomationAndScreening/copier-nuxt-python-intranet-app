"""Fix Kiota's incorrect nullable handling for TypeScript code generation.

This script addresses two Kiota bugs:
1. Incorrectly adds | null to required non-nullable fields
2. Incorrectly generates empty "Member1" interfaces for anyOf nullable types

Open github issue: https://github.com/microsoft/kiota/issues/3911
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

# Default path to OpenAPI schema
DEFAULT_OPENAPI_SCHEMA = (
    Path(__file__).parent.parent
    / "backend"
    / "tests"
    / "unit"
    / "__snapshots__"
    / "test_basic_server_functionality"
    / "test_openapi_schema.json"
)
DEFAULT_MODELS_DIR = Path(__file__).parent / "app" / "generated" / "open-api" / "backend" / "models"


def load_openapi_schema(source: str) -> dict[str, Any]:
    """Load OpenAPI schema from URL or file path."""
    # Check if it looks like a URL
    if source.startswith(("http://", "https://")):
        try:
            with urlopen(source, timeout=5.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except (URLError, json.JSONDecodeError, OSError) as e:
            print(f"Error fetching OpenAPI schema from {source}: {e}")
            sys.exit(1)
    else:
        # pylint: disable=duplicate-code # this is shared with the fixer script for typescript code
        # Treat as file path
        file_path = Path(source)
        if not file_path.exists():
            print(f"Error: OpenAPI schema file not found: {file_path}")
            sys.exit(1)
        try:
            with file_path.open() as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Error reading OpenAPI schema from {file_path}: {e}")
            sys.exit(1)
        # pylint: enable=duplicate-code


def get_required_non_nullable_fields(schema: dict[str, Any]) -> dict[str, set[str]]:
    """Parse OpenAPI schema to find required, non-nullable fields."""
    # pylint: disable=duplicate-code # in repositories with both frontends and backends, this function appears in both
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


def fix_anyof_nullable_types(file_path: Path) -> int:
    """Fix Kiota's bogus Member1 interfaces for anyOf nullable types.

    Kiota generates empty Member1 interfaces for fields with anyOf: [type, null].
    This causes deserialization to fail, storing primitives as objects in additionalData.

    This function:
    1. Removes all Member1 interface declarations
    2. Removes all Member1 references from code (types, parameters, casts, calls)
    3. Removes helper functions that only exist for Member1 or union wrappers
    4. Cleans up resulting syntax errors
    5. Preserves legitimate entity functions

    Returns: Number of fixes applied
    """
    content = file_path.read_text()
    original_content = content
    fixes_applied = 0

    # Find all Member1 interface/type patterns
    member1_pattern = r"(\w+)Member1"
    member1_types = set(re.findall(member1_pattern, content))

    # Step 1: Remove all Member1 interface declarations
    # Matches: export interface XxxMember1 extends Parsable {}
    interface_pattern = r"export\s+interface\s+\w+Member1\s+extends\s+Parsable\s*\{\s*\}\n?"
    content, count = re.subn(interface_pattern, "", content)
    fixes_applied += count

    # Step 2: Remove Member1 from type definitions
    for base_type in member1_types:
        member1_type = f"{base_type}Member1"

        # Pattern: export type BaseType = Member1 | OtherType;
        # Replace with: export type BaseType = OtherType | null;
        type_pattern1 = rf"(export\s+type\s+{re.escape(base_type)}\s*=\s*){re.escape(member1_type)}\s*\|\s*([^;]+);"
        if re.search(type_pattern1, content):
            content = re.sub(type_pattern1, r"\1\2 | null;", content)
            fixes_applied += 1

        # Pattern: export type BaseType = OtherType | Member1;
        type_pattern2 = rf"(export\s+type\s+{re.escape(base_type)}\s*=\s*)([^;|]+)\s*\|\s*{re.escape(member1_type)}\s*;"
        if re.search(type_pattern2, content):
            content = re.sub(type_pattern2, r"\1\2 | null;", content)
            fixes_applied += 1

    # Step 3: Fix deserialization patterns that call Member1 functions
    # Pattern: field = n.getObjectValue<Member1Type>(createXxxMember1...) ?? n.getPrimitiveValue()
    # Replace with: field = n.getPrimitiveValue()

    # Handle string fields - two patterns for different orderings
    # Pattern 1: getObjectValue first
    deser_string_pattern1 = r"(\w+\.\w+\s*=\s*)n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)\s*\?\?\s*(n\.getString(?:Value)?\(\)[^;]*)"
    content, count = re.subn(deser_string_pattern1, r"\1\3", content)
    fixes_applied += count

    # Pattern 2: getString first
    deser_string_pattern2 = r"(\w+\.\w+\s*=\s*)(n\.getString(?:Value)?\(\)[^;]*?)\s*\?\?\s*n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)"
    content, count = re.subn(deser_string_pattern2, r"\1\2", content)
    fixes_applied += count

    # Handle boolean fields - two patterns for different orderings
    # Pattern 1: getObjectValue first
    deser_bool_pattern1 = r"(\w+\.\w+\s*=\s*)n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)\s*\?\?\s*n\.getBooleanValue\(\)"
    content, count = re.subn(deser_bool_pattern1, r"\1n.getBooleanValue()", content)
    fixes_applied += count

    # Pattern 2: getBooleanValue first
    deser_bool_pattern2 = r"(\w+\.\w+\s*=\s*)n\.getBooleanValue\(\)\s*\?\?\s*n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)"
    content, count = re.subn(deser_bool_pattern2, r"\1n.getBooleanValue()", content)
    fixes_applied += count

    # Handle number fields - two patterns for different orderings
    # Pattern 1: getObjectValue first
    deser_number_pattern1 = r"(\w+\.\w+\s*=\s*)n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)\s*\?\?\s*n\.getNumberValue\(\)"
    content, count = re.subn(deser_number_pattern1, r"\1n.getNumberValue()", content)
    fixes_applied += count

    # Pattern 2: getNumberValue first
    deser_number_pattern2 = r"(\w+\.\w+\s*=\s*)n\.getNumberValue\(\)\s*\?\?\s*n\.getObjectValue<?(\w+Member1)?>?\(create\w+Member1FromDiscriminatorValue\)"
    content, count = re.subn(deser_number_pattern2, r"\1n.getNumberValue()", content)
    fixes_applied += count

    # Handle collection fields - two patterns depending on order
    # Pattern 1: getObjectValue first, then getCollectionOfPrimitiveValues
    deser_collection_pattern = r"(\w+\.\w+\s*=\s*)n\.getObjectValue<\w+Member1>\(create\w+Member1FromDiscriminatorValue\)\s*\?\?\s*(n\.getCollectionOfPrimitiveValues<[^>]+>\(\)[^;]*)"
    content, count = re.subn(deser_collection_pattern, r"\1\2", content)
    fixes_applied += count

    # Pattern 2: getCollectionOfPrimitiveValues first, then getObjectValue (with Member1)
    # Handle both with and without type parameter: getObjectValue<Member1>(...) or getObjectValue(...)
    deser_collection_pattern2 = r"(\w+\.\w+\s*=\s*)(n\.getCollectionOfPrimitiveValues<[^>]+>\(\))\s*\?\?\s*n\.getObjectValue(?:<\w+Member1>)?\(create\w+Member1FromDiscriminatorValue\)"
    content, count = re.subn(deser_collection_pattern2, r"\1\2", content)
    fixes_applied += count

    # Remove spread operator calls to deserializeIntoXxxMember1
    # Pattern: ...deserializeIntoXxxMember1(foo)
    spread_deser_pattern = r"\.\.\.\s*deserializeInto\w+Member1\([^)]+\)\s*,?"
    content, count = re.subn(spread_deser_pattern, "", content)
    fixes_applied += count

    # Remove serialization calls to serializeXxxMember1
    # Pattern: serializeXxxMember1(writer, foo);
    serialize_call_pattern = r"serialize\w+Member1\([^)]+\)\s*;"
    content, count = re.subn(serialize_call_pattern, "", content)
    fixes_applied += count

    # Fix writeObjectValue calls with Member1 type parameters
    # Pattern: writer.writeObjectValue<XxxMember1>("field", value, serializeFunc);
    # Replace with: writer.writeObjectValue("field", value, serializeFunc); (remove type param)
    write_member1_pattern = r"writer\.writeObjectValue<(\w+Member1)>"
    content, count = re.subn(write_member1_pattern, r"writer.writeObjectValue", content)
    fixes_applied += count

    # Fix writeObjectValue for array fields that should use writeCollectionOfPrimitiveValues
    # After removing Member1, we might have: writer.writeObjectValue<| string>("field", array_value, ...)
    # This should be: writer.writeCollectionOfPrimitiveValues<string>("field", array_value)
    # Pattern: writeObjectValue<stuff | primitive_type[]>("anyfield", value, serializeFunc)
    write_collection_pattern = (
        r'writer\.writeObjectValue<[^>]*\|\s*((?:string|number|boolean)\[\])>\("([^"]+)",\s*([^,]+),\s*[^)]+\)'
    )
    content, count = re.subn(
        write_collection_pattern, r'writer.writeCollectionOfPrimitiveValues<\1>("\2", \3)', content
    )
    fixes_applied += count

    # Also handle the cleaned-up version with just the array type left
    # Pattern: writer.writeObjectValue< string[]>("anyfield", value, serializeFunc)
    write_collection_pattern2 = (
        r'writer\.writeObjectValue<\s*((?:string|number|boolean)\[\])\s*>\("([^"]+)",\s*([^,]+),\s*[^)]+\)'
    )
    content, count = re.subn(
        write_collection_pattern2, r'writer.writeCollectionOfPrimitiveValues<\1>("\2", \3)', content
    )
    fixes_applied += count

    # Step 3.5: Remove remaining Member1 references from type parameters and casts
    # Pattern: <XxxMember1> in generic type parameters
    for base_type in member1_types:
        member1_type = f"{base_type}Member1"
        # Remove from type parameters: <Member1Type>
        content = re.sub(rf"<{re.escape(member1_type)}>", "", content)
        # Remove from union in type parameters: <Foo | Member1Type> -> <Foo>
        # Use [^<>]+ to match the other type, which preserves [] brackets
        content = re.sub(rf"<([^<>]+)\|\s*{re.escape(member1_type)}>", r"<\1>", content)
        content = re.sub(rf"<{re.escape(member1_type)}\s*\|([^<>]+)>", r"<\1>", content)

    # Step 4: Remove Member1 from union types ONLY (not from function names!)
    # This handles property types, parameters, casts, etc.
    # But we must NOT remove Member1 from function names - those functions will be removed entirely in Step 5

    for base_type in member1_types:
        member1_type = f"{base_type}Member1"

        # Remove "| Member1Type" with various spacing
        content = re.sub(rf"\|\s*{re.escape(member1_type)}\b", "", content)

        # Remove "Member1Type |" with various spacing
        content = re.sub(rf"\b{re.escape(member1_type)}\s*\|", "", content)

        # Remove from type casts: "(foo as Member1Type)" -> "(foo as )"
        # We'll clean up the dangling "as" in the next step
        content = re.sub(rf"\bas\s+{re.escape(member1_type)}\b", "as ", content)

    # Step 4.25: Fix writeObjectValue issues that are only visible after Member1 removal
    # Handle fields where Kiota incorrectly generated primitive instead of primitive[]
    # Pattern: writer.writeObjectValue<number>("raw_readings", value, serializeType_raw_readings)
    # This happens when Kiota generates <Member1 | number> instead of <Member1 | number[]>
    # After Step 3.5 removes Member1, we're left with <number> but should be array
    # The serialize function follows the pattern serialize{TypeName}_{field_name}
    # Convert to: writer.writeCollectionOfPrimitiveValues<number>("raw_readings", value)
    # Note: writeCollectionOfPrimitiveValues expects the element type, not array type
    write_wrong_primitive_pattern = (
        r'writer\.writeObjectValue<\s*(string|number|boolean)\s*>\("([^"]+)",\s*([^,]+),\s*serialize\w+_[^)]+\)'
    )
    content, count = re.subn(
        write_wrong_primitive_pattern, r'writer.writeCollectionOfPrimitiveValues<\1>("\2", \3)', content
    )
    fixes_applied += count

    # Handle non-array fields that correctly remain as writeObjectValue after Member1 removal
    # Pattern: writer.writeObjectValue< primitive>("field", value, serializeFunc)
    # These should stay as writeObjectValue but fix the spacing (they don't have underscore pattern)
    write_primitive_pattern = r"writer\.writeObjectValue<\s*(string|number|boolean)\s*>\("
    content, count = re.subn(write_primitive_pattern, r"writer.writeObjectValue<\1>(", content)
    fixes_applied += count

    # Step 4.5: Clean up syntax errors from Member1 removal

    # Fix patterns like "!foo | bar" which should be "!foo || bar" (boolean logic)
    content = re.sub(r"(![\w.]+)\s+\|\s+(\w)", r"\1 || \2", content)

    # Fix triple/double pipes from removal: "|| | " -> "||"
    content = re.sub(r"\|\|\s*\|+", "||", content)

    # Fix leading pipe in types: ": | Type" -> ": Type"
    content = re.sub(r":\s*\|\s+", ": ", content)

    # Fix trailing pipe: "Type |;" -> "Type;"
    content = re.sub(r"\|\s*;", ";", content)

    # Fix trailing pipe before closing: "Type | )" -> "Type)"
    content = re.sub(r"\|\s*\)", ")", content)

    # Fix trailing pipe before comma: "Type | ," -> "Type,"
    content = re.sub(r"\|\s*,", ",", content)

    # Fix empty type parameters: "<>" -> should be removed
    content = re.sub(r"<\s*>", "", content)

    # Fix "Parsable | >" -> "Parsable>"
    content = re.sub(r"Parsable\s*\|\s*>", "Parsable>", content)

    # Fix dangling "as " with nothing after it: "(foo as )" -> "(foo)"
    content = re.sub(r"\bas\s+\)", ")", content)
    content = re.sub(r"\bas\s+,", ",", content)
    content = re.sub(r"\bas\s+;", ";", content)

    # Fix multiple spaces
    content = re.sub(r"  +", " ", content)

    # Step 5: Remove helper functions
    # We need to remove:
    # A) All functions with "Member1" in the name
    # B) Union wrapper functions (deserialize/serialize functions for base types that reference Member1)

    # Pattern A: Remove all Member1 helper functions INCLUDING their JSDoc comments
    # Matches: /** ... */ // @ts-ignore export function createXxxMember1FromDiscriminatorValue(...) { ... }
    # Matches: /** ... */ // @ts-ignore export function deserializeIntoXxxMember1(...) { ... }
    # Matches: /** ... */ // @ts-ignore export function serializeXxxMember1(...) { ... }

    # Build pattern to match any function with "Member1" literally in the function name
    # Use a single pass to find all functions with Member1 in their name
    # Pattern matches JSDoc (non-greedy, stops at first */), then function with Member1 in name
    func_pattern_with_jsdoc = r"/\*\*[^*]*(?:\*(?!/)[^*]*)*\*/\s*(?://\s*@ts-ignore\s+)?export\s+function\s+(\w*Member1\w*)\s*\([^\)]*\)\s*:\s*[^{]+\s*\{"

    while True:
        match = re.search(func_pattern_with_jsdoc, content)
        if not match:
            break

        # Find matching closing brace
        start_pos = match.end() - 1  # Position of opening {
        brace_count = 1
        pos = start_pos + 1

        while pos < len(content) and brace_count > 0:
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
            pos += 1

        if brace_count == 0:
            # Remove from start of JSDoc to end of closing brace (including newline)
            end_pos = pos
            if end_pos < len(content) and content[end_pos] == "\n":
                end_pos += 1
            content = content[: match.start()] + content[end_pos:]
            fixes_applied += 1
        else:
            break  # Couldn't find matching brace, stop to avoid infinite loop

    # Pattern B: We DON'T need this pattern anymore!
    # The Member1 union types (like CreateDeviceMetricsViewPayload_id) should be kept
    # We only remove functions that have "Member1" literally in their name (Pattern A above)

    # Step 6: Final cleanup pass
    # Remove any remaining empty lines created by deletions (more than 2 consecutive newlines)
    content = re.sub(r"\n{3,}", "\n\n", content)

    if content != original_content:
        _ = file_path.write_text(content)
        print(f"Applied {fixes_applied} anyOf nullable fixes")
        return fixes_applied

    return 0


def main(schema: dict[str, Any] | None = None):
    """Main function to fix TypeScript models.

    Args:
        schema: OpenAPI schema dict. If None, loads from default path for backward compatibility.
    """
    if schema is None:
        # Backward compatibility: load from default path if no schema provided
        if not DEFAULT_OPENAPI_SCHEMA.exists():
            print(f"Error: Default OpenAPI schema file not found: {DEFAULT_OPENAPI_SCHEMA}")
            sys.exit(1)
        with DEFAULT_OPENAPI_SCHEMA.open() as f:
            schema = json.load(f)
            if schema is None:
                print("Error: Failed to load OpenAPI schema from default path")
                sys.exit(1)

    index_file = MODELS_DIR / "index.ts"

    # Fix 1: Required non-nullable fields (original functionality)
    required_fields = get_required_non_nullable_fields(schema)
    if required_fields:
        print(f"Found {len(required_fields)} models with required non-nullable fields")
        fixed_count = 0
        for model_name, fields in required_fields.items():
            if fix_typescript_file(index_file, model_name, fields):
                fixed_count += 1
        print(f"Fixed {fixed_count} models for required fields")
    else:
        print("No required non-nullable field fixes needed")

    # Fix 2: anyOf nullable types with Member1 interfaces
    print("\nFixing anyOf nullable types...")
    anyof_fixes = fix_anyof_nullable_types(index_file)
    if anyof_fixes > 0:
        print(f"✓ Fixed {anyof_fixes} types with anyOf nullable issues")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fix Kiota's incorrect nullable handling in generated TypeScript models"
    )
    _ = parser.add_argument(
        "openapi_source",
        nargs="?",
        default=str(DEFAULT_OPENAPI_SCHEMA),
        help=(
            "OpenAPI schema source (URL starting with http:// or https://, or file path). "
            f"Defaults to {DEFAULT_OPENAPI_SCHEMA.relative_to(Path(__file__).parent.parent)}"
        ),
    )
    _ = parser.add_argument(
        "models_dir",
        nargs="?",
        default=str(DEFAULT_MODELS_DIR),
        help=(
            "Path to the directory containing generated Kiota models. "
            f"Defaults to {DEFAULT_MODELS_DIR.relative_to(Path(__file__).parent)}"
        ),
    )

    args = parser.parse_args()

    # Validate models directory
    models_dir = Path(args.models_dir)
    # pylint: disable=duplicate-code # this is shared with the fixer script for typescript code
    if not models_dir.exists():
        print(f"Error: Models directory not found: {models_dir.absolute()}")
        sys.exit(1)
    if not models_dir.is_dir():
        print(f"Error: Models path is not a directory: {models_dir.absolute()}")
        sys.exit(1)

    # Load OpenAPI schema
    print(f"Loading OpenAPI schema from: {args.openapi_source}")
    openapi_schema = load_openapi_schema(args.openapi_source)
    # pylint: enable=duplicate-code

    # Override globals with CLI args
    MODELS_DIR = models_dir

    main(openapi_schema)
