// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// gov.au Naming Conventions: "The object and field definition MUST be the same for the request and response body".
// Enforced across the whole API rather than per resource (which lint would have to guess from the paths): every
// property with a given name, in any component schema, has the same definition, so a client never meets one name
// meaning two shapes. A definition here is the type, format, `$ref` target, array item type and enum values.
// Nullability and required-ness are left out, since a payload and a response legitimately differ there (an `id`
// optional on create, always present when read), as are descriptions and bounds, which can fairly depend on context.
//
// Run on `$.components.schemas` unresolved, so a `$ref` compares by the component it names. Each conflicting
// property is reported at its own path, so a deliberate clash can be exempted in .config/vacuum-ignore.yaml.
// functionOptions.ignoreSchemas lists schemas whose field names this project doesn't choose: FastAPI's generated
// validation errors, and ProblemDetails and its subclass ValidationProblemDetails, whose `status` (the HTTP status
// code) and `detail` are named by RFC 9457. functionOptions.ignoreProperties lists property names left out in every
// schema: `data`, the envelope collection-in-data puts every collection's items in, holds a different item type in
// each collection by design.

function getSchema() {
  return {
    name: "consistentPropertyTypes",
    properties: [
      { name: "ignoreSchemas", description: "component schema names to leave out" },
      { name: "ignoreProperties", description: "property names to leave out, in every schema" },
    ],
  };
}

function nonNullBranches(schema) {
  var branches = schema.anyOf || schema.oneOf;
  if (!Array.isArray(branches)) {
    return null;
  }
  var kept = [];
  for (var i = 0; i < branches.length; i++) {
    if (branches[i] && branches[i].type === "null") {
      continue;
    }
    kept.push(branches[i]);
  }
  return kept;
}

function nonNullType(type) {
  if (!Array.isArray(type)) {
    return type;
  }
  var kept = [];
  for (var i = 0; i < type.length; i++) {
    if (type[i] === "null") {
      continue;
    }
    kept.push(type[i]);
  }
  if (kept.length === 1) {
    return kept[0];
  }
  return kept;
}

function refName(ref) {
  var parts = ref.split("/");
  return parts[parts.length - 1];
}

function definition(schema) {
  if (!schema || typeof schema !== "object") {
    return "?";
  }
  var branches = nonNullBranches(schema);
  if (branches !== null) {
    if (branches.length === 1) {
      return definition(branches[0]);
    }
    var parts = [];
    for (var i = 0; i < branches.length; i++) {
      parts.push(definition(branches[i]));
    }
    return "oneOf(" + parts.join(" | ") + ")";
  }
  if (typeof schema.$ref === "string") {
    return refName(schema.$ref);
  }
  var text = JSON.stringify(nonNullType(schema.type));
  if (typeof schema.format === "string") {
    text += " (" + schema.format + ")";
  }
  if (Array.isArray(schema.enum)) {
    text += " enum " + JSON.stringify(schema.enum);
  }
  if (schema.items) {
    text += " of " + definition(schema.items);
  }
  return text;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var options = context.ruleAction.functionOptions || {};
  var ignored = Array.isArray(options.ignoreSchemas) ? options.ignoreSchemas : [];
  var ignoredProperties = Array.isArray(options.ignoreProperties) ? options.ignoreProperties : [];
  var uses = {};
  for (var schemaName in input) {
    if (ignored.indexOf(schemaName) !== -1) {
      continue;
    }
    var properties = input[schemaName] && input[schemaName].properties;
    if (!properties || typeof properties !== "object") {
      continue;
    }
    for (var propertyName in properties) {
      if (ignoredProperties.indexOf(propertyName) !== -1) {
        continue;
      }
      if (!uses[propertyName]) {
        uses[propertyName] = [];
      }
      uses[propertyName].push({ schema: schemaName, definition: definition(properties[propertyName]) });
    }
  }
  var results = [];
  for (var name in uses) {
    var byDefinition = {};
    var definitionCount = 0;
    for (var i = 0; i < uses[name].length; i++) {
      var use = uses[name][i];
      if (!byDefinition[use.definition]) {
        byDefinition[use.definition] = [];
        definitionCount++;
      }
      byDefinition[use.definition].push(use.schema);
    }
    if (definitionCount < 2) {
      continue;
    }
    for (var j = 0; j < uses[name].length; j++) {
      var others = [];
      for (var otherDefinition in byDefinition) {
        if (otherDefinition === uses[name][j].definition) {
          continue;
        }
        others.push(otherDefinition + " in " + byDefinition[otherDefinition].join(", "));
      }
      results.push({
        message: uses[name][j].schema + "." + name + " is " + uses[name][j].definition + ", but " + others.join("; "),
        path: "$.components.schemas['" + uses[name][j].schema + "'].properties['" + name + "']",
      });
    }
  }
  return results;
}
