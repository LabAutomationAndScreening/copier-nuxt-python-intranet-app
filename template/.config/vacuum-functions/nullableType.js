// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Flags every schema within its input that admits both `functionOptions.type` and null: either as
// an anyOf/oneOf with a branch of that type and a `null` branch (how Pydantic emits `bool | None` under
// OpenAPI 3.1) or as a `type` list holding both. Used for Zalando's "MUST not use `null` for boolean
// properties" [122] (a nullable boolean is a three-valued flag whose null rarely means anything a client
// can act on) and "SHOULD not use `null` for empty arrays" [124] (an empty array already says "none").
//
// vacuum hands the function its input already resolved, so the rules point it at component schemas and
// parameters rather than the whole document; walking the paths too would report each model again at every
// operation that uses it.

function getSchema() {
  return {
    name: "nullableType",
    properties: [{ name: "type", description: "the JSON Schema type that must not be nullable" }],
    required: ["type"],
  };
}

function branchTypes(branches) {
  var types = [];
  for (var i = 0; i < branches.length; i++) {
    if (branches[i] && typeof branches[i].type === "string") {
      types.push(branches[i].type);
    }
  }
  return types;
}

function admitsTypeAndNull(node, type) {
  if (Array.isArray(node.type)) {
    return node.type.indexOf(type) !== -1 && node.type.indexOf("null") !== -1;
  }
  var branches = node.anyOf || node.oneOf;
  if (Array.isArray(branches)) {
    var types = branchTypes(branches);
    return types.indexOf(type) !== -1 && types.indexOf("null") !== -1;
  }
  return false;
}

// A nested node with both `title` and `properties` is a model referenced from this one, already resolved in
// place; it is checked as its own component, so walking it here would report its fields a second time.
// Known gap, accepted: an inline object schema that has a title but is no component would be skipped too. FastAPI
// never writes one: Pydantic always emits a nested model as a `$ref` to its own component, so every titled object
// found here is a resolved reference.
function isNestedModel(node, location) {
  return location !== "" && typeof node.title === "string" && node.properties && typeof node.properties === "object";
}

function walk(node, location, type, results) {
  if (!node || typeof node !== "object") {
    return;
  }
  if (!Array.isArray(node)) {
    if (isNestedModel(node, location)) {
      return;
    }
    if (admitsTypeAndNull(node, type)) {
      var where = location === "" ? "the schema itself" : location.substring(1);
      results.push({ message: where + " allows null as well as " + type });
    }
  }
  for (var key in node) {
    walk(node[key], location + "." + key, type, results);
  }
}

// vacuum passes only the input to runRule; the rule's functionOptions come in through the global `context`.
function runRule(input) {
  var results = [];
  walk(input, "", context.ruleAction.functionOptions.type, results);
  return results;
}
