// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 120 "SHOULD pluralize array names" and gov.au Naming Conventions ("Fields that represent arrays SHOULD be
// named using plural nouns"): an array property's name says it holds many, so `devices`, not `device` or
// `deviceList`. Like resourcesPlural.js the check is heuristic: a name passes when it ends in "s" or ends in one of
// functionOptions.pluralWords, the plurals that don't (`data`, `children`, ...); matching is on the last camelCase
// word, so `metricData` passes as well as `data`.
//
// Run on `$.components.schemas`, one property per finding at its own path, so a deliberate exception can be exempted
// in .config/vacuum-ignore.yaml. Arrays are plain `type: array`: no-nullable-array already refuses nullable ones.
// functionOptions.ignoreSchemas lists schemas whose field names this project doesn't choose.

function getSchema() {
  return {
    name: "pluralArrayNames",
    properties: [
      { name: "pluralWords", description: "plural words that don't end in s" },
      { name: "ignoreSchemas", description: "component schema names to leave out" },
    ],
  };
}

function lastWord(name) {
  var match = name.match(/[A-Z]?[a-z0-9]+$/);
  if (match === null) {
    return name.toLowerCase();
  }
  return match[0].toLowerCase();
}

function isPlural(name, pluralWords) {
  if (/s$/.test(name)) {
    return true;
  }
  return pluralWords.indexOf(lastWord(name)) !== -1;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var options = context.ruleAction.functionOptions || {};
  var pluralWords = Array.isArray(options.pluralWords) ? options.pluralWords : [];
  var ignored = Array.isArray(options.ignoreSchemas) ? options.ignoreSchemas : [];
  var results = [];
  for (var schemaName in input) {
    if (ignored.indexOf(schemaName) !== -1) {
      continue;
    }
    var properties = input[schemaName] && input[schemaName].properties;
    if (!properties || typeof properties !== "object") {
      continue;
    }
    for (var propertyName in properties) {
      var property = properties[propertyName];
      if (!property || property.type !== "array") {
        continue;
      }
      if (isPlural(propertyName, pluralWords)) {
        continue;
      }
      results.push({
        message: schemaName + "." + propertyName + " is an array, so its name should be a plural noun",
        path: "$.components.schemas['" + schemaName + "'].properties['" + propertyName + "']",
      });
    }
  }
  return results;
}
