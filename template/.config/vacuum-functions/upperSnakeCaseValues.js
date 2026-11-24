// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 240 "SHOULD declare enum values using UPPER_SNAKE_CASE string". vacuum's built-in `casing` would do, but under
// this ruleset's (native) contract it checks every matched value as text, so integer, boolean and null values fail
// (`enum: [1, 2]`, or Pydantic's `Literal["READY", None]` written as `enum: ["READY", null]`); only its OpenLint
// contract skips them. This checks string values only: those of every `enum`, every `const` (how Pydantic writes a
// one-value Literal) and an extensible enum's `examples`.
//
// Run unresolved on each component schema and each operation's parameters, request body and responses, walking the
// schemas nested inside. A finding is reported at the input it was found in (a component schema, say, which is where an
// ignore entry names it) and its message gives the path within it. On a schema object, `enum`, `const`, `example`,
// `examples` and `default` hold data, so they are never walked and an object in them is never read as a schema; in a
// `properties` map the same words are property names, whose schemas are walked like any other.

var UPPER_SNAKE_CASE = /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$/;

// Keywords of a schema object whose value is data, not a schema: checked where they hold enum values, never walked.
var DATA_KEYWORDS = ["enum", "const", "example", "examples", "default"];

// Keywords whose keys are property names, so every key, even `default` or `const`, names a schema to walk.
var NAME_MAPS = ["properties", "patternProperties"];

function getSchema() {
  return { name: "upperSnakeCaseValues" };
}

function checkValue(value, where, results) {
  if (typeof value !== "string") {
    return;
  }
  if (UPPER_SNAKE_CASE.test(value)) {
    return;
  }
  results.push({ message: "enum value `" + value + "` (at " + where + ") is not UPPER_SNAKE_CASE" });
}

function checkValues(values, where, results) {
  for (var i = 0; i < values.length; i++) {
    checkValue(values[i], where, results);
  }
}

function joined(where, key) {
  if (where === "") {
    return key;
  }
  return where + "." + key;
}

function isExtensibleEnum(node) {
  return typeof node.description === "string" && /^Extensible enum[.]/.test(node.description);
}

function walkNameMap(map, where, results) {
  if (!map || typeof map !== "object") {
    return;
  }
  for (var name in map) {
    walkSchema(map[name], joined(where, name), results);
  }
}

function walkSchema(node, where, results) {
  if (!node || typeof node !== "object") {
    return;
  }
  if (Array.isArray(node)) {
    for (var i = 0; i < node.length; i++) {
      walkSchema(node[i], where + "[" + i + "]", results);
    }
    return;
  }
  if (Array.isArray(node.enum)) {
    checkValues(node.enum, joined(where, "enum"), results);
  }
  checkValue(node.const, joined(where, "const"), results);
  if (isExtensibleEnum(node)) {
    if (Array.isArray(node.examples)) {
      checkValues(node.examples, joined(where, "examples"), results);
    }
  }
  for (var key in node) {
    if (DATA_KEYWORDS.indexOf(key) !== -1) {
      continue;
    }
    if (NAME_MAPS.indexOf(key) !== -1) {
      walkNameMap(node[key], joined(where, key), results);
      continue;
    }
    walkSchema(node[key], joined(where, key), results);
  }
}

function runRule(input) {
  var results = [];
  walkSchema(input, "", results);
  return results;
}
