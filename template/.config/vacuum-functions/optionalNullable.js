// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 123 "MUST use same semantics for `null` and absent properties" is about meaning, which a linter
// can't see. This checks the shape that makes the two distinguishable: a property that is both optional (not
// in `required`) and nullable can arrive absent or as null, so a reader can't tell whether they mean the
// same thing. Every property must instead pick one: required and nullable (always sent, may be null), or
// optional and non-nullable (may be left out, never null; in Pydantic, `X | SkipJsonSchema[None] = None`).
//
// `given: $.components.schemas[*]` passes one (resolved) model schema at a time; only its own properties are
// checked, since a referenced model is checked as its own component.

function getSchema() {
  return { name: "optionalNullable" };
}

function admitsNull(property) {
  if (Array.isArray(property.type)) {
    return property.type.indexOf("null") !== -1;
  }
  var branches = property.anyOf || property.oneOf;
  if (!Array.isArray(branches)) {
    return false;
  }
  for (var i = 0; i < branches.length; i++) {
    if (branches[i] && branches[i].type === "null") {
      return true;
    }
  }
  return false;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var properties = input.properties;
  if (!properties || typeof properties !== "object") {
    return [];
  }
  var required = Array.isArray(input.required) ? input.required : [];
  var results = [];
  for (var name in properties) {
    if (required.indexOf(name) !== -1) {
      continue;
    }
    if (!properties[name] || !admitsNull(properties[name])) {
      continue;
    }
    results.push({
      message:
        "property '" +
        name +
        "' is both optional and nullable; make it required (and nullable) or optional and never null",
    });
  }
  return results;
}
