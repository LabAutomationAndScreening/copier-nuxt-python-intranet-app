// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 171 "MUST define a format for number and integer types": flags every schema within its input that admits
// `number` without a `format` of float, double or decimal, so a client knows which floating-point type to decode
// into. The integer half is owasp-integer-format's. A nullable number is a `type` list holding "number" and "null"
// or an anyOf/oneOf branch (how Pydantic emits `float | None`), so both shapes are checked. Pydantic emits no format
// for `float`, though a Python float is always an IEEE 754 double, so `format: double` is always true of it.
//
// vacuum hands the function its input already resolved, so the rule points it at component schemas and parameters
// rather than the whole document; walking the paths too would report each model again at every operation using it.

var NUMBER_FORMATS = ["float", "double", "decimal"];

function getSchema() {
  return { name: "numberFormat" };
}

function admitsNumber(node) {
  if (node.type === "number") {
    return true;
  }
  return Array.isArray(node.type) && node.type.indexOf("number") !== -1;
}

// A nested node with both `title` and `properties` is a model referenced from this one, already resolved in place;
// it is checked as its own component, so walking it here would report its fields a second time.
function isNestedModel(node, location) {
  return location !== "" && typeof node.title === "string" && node.properties && typeof node.properties === "object";
}

function walk(node, location, results) {
  if (!node || typeof node !== "object") {
    return;
  }
  if (!Array.isArray(node)) {
    if (isNestedModel(node, location)) {
      return;
    }
    if (admitsNumber(node) && NUMBER_FORMATS.indexOf(node.format) === -1) {
      var where = location === "" ? "the schema itself" : location.substring(1);
      results.push({ message: where + " is a number with no float, double or decimal format" });
    }
  }
  for (var key in node) {
    walk(node[key], location + "." + key, results);
  }
}

function runRule(input) {
  var results = [];
  walk(input, "", results);
  return results;
}
