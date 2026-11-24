// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 174 "MUST use common field names and semantics": an identifier is an opaque string, so clients compare it
// and never do arithmetic on it or rely on its order, and the server can change how it is stored without breaking
// them. A string id need not be a UUID (Zalando 144 "SHOULD only use UUIDs if necessary"): an autoincrement key is
// fine sent as "42". It also keeps an int64 key out of a JavaScript number, which loses precision above 2^53.
//
// A name `id`, ending in `Id` or (a path parameter, which is snake_case) in `_id` must be a string; `ids`, `…Ids`
// or `…_ids` must be an array of strings, none of which can be null (the array itself may be nullable). The input is
// either one (resolved) model schema from `$.components.schemas[*]`, whose own properties are checked, or one
// operation parameter. A nullable value's type is a `type` list or an anyOf/oneOf branch (how Pydantic emits
// `str | None`), so both shapes are read.

function getSchema() {
  return { name: "stringIds" };
}

function nonNullTypes(schema) {
  if (!schema || typeof schema !== "object") {
    return [];
  }
  var branches = schema.anyOf || schema.oneOf;
  if (Array.isArray(branches)) {
    var fromBranches = [];
    for (var i = 0; i < branches.length; i++) {
      var branchTypes = nonNullTypes(branches[i]);
      for (var j = 0; j < branchTypes.length; j++) {
        fromBranches.push(branchTypes[j]);
      }
    }
    return fromBranches;
  }
  var types = Array.isArray(schema.type) ? schema.type : [schema.type];
  var kept = [];
  for (var k = 0; k < types.length; k++) {
    if (types[k] === "null") {
      continue;
    }
    kept.push(types[k]);
  }
  return kept;
}

function nonNullBranch(schema) {
  var branches = schema && (schema.anyOf || schema.oneOf);
  if (!Array.isArray(branches)) {
    return schema;
  }
  for (var i = 0; i < branches.length; i++) {
    if (branches[i] && branches[i].type !== "null") {
      return branches[i];
    }
  }
  return schema;
}

// Whether a schema accepts null, by its own type or by any anyOf/oneOf branch (how Pydantic writes `str | None`).
function admitsNull(schema) {
  if (!schema || typeof schema !== "object") {
    return false;
  }
  if (schema.type === "null" || (Array.isArray(schema.type) && schema.type.indexOf("null") !== -1)) {
    return true;
  }
  var branches = schema.anyOf || schema.oneOf;
  if (!Array.isArray(branches)) {
    return false;
  }
  for (var i = 0; i < branches.length; i++) {
    if (admitsNull(branches[i])) {
      return true;
    }
  }
  return false;
}

// Every non-null alternative is a string (Pydantic writes `UUID | str` as two string branches), and there is one.
function isOnlyString(schema) {
  var types = nonNullTypes(schema);
  if (types.length === 0) {
    return false;
  }
  for (var i = 0; i < types.length; i++) {
    if (types[i] !== "string") {
      return false;
    }
  }
  return true;
}

function problem(kind, name, schema) {
  if (/^id$|Id$|_id$/.test(name)) {
    if (isOnlyString(schema)) {
      return null;
    }
    return kind + " '" + name + '\' is an identifier, so it must be a string (an integer key can be sent as "42")';
  }
  if (/^ids$|Ids$|_ids$/.test(name)) {
    var types = nonNullTypes(schema);
    var array = nonNullBranch(schema);
    if (types.length === 1 && types[0] === "array" && isOnlyString(array.items) && !admitsNull(array.items)) {
      return null;
    }
    return kind + " '" + name + "' holds identifiers, so it must be an array of strings, none of them null";
  }
  return null;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var results = [];
  if (typeof input.name === "string" && typeof input.in === "string") {
    var parameterProblem = problem(input.in + " parameter", input.name, input.schema);
    if (parameterProblem !== null) {
      results.push({ message: parameterProblem });
    }
    return results;
  }
  var properties = input.properties;
  if (!properties || typeof properties !== "object") {
    return results;
  }
  for (var name in properties) {
    var propertyProblem = problem("property", name, properties[name]);
    if (propertyProblem !== null) {
      results.push({ message: propertyProblem });
    }
  }
  return results;
}
