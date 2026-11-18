// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Ties a date/time property's name to its format, in both directions, adapted to camelCase:
//   functionOptions.check "naming" (Zalando 235 "SHOULD use naming convention for date/time properties"): a
//     property with format date-time, date or time must say so in its name, by ending in `At` or containing
//     date, time or day (`timestamp` included), so a reader knows it holds a point in time without the schema.
//   functionOptions.check "format" (Zalando 169 "MUST use standard formats for date and time properties"): a
//     property named as a point in time must carry the RFC 3339 format that says so, rather than being a bare
//     string or an epoch number: `…At` and `…Timestamp` need date-time, and `…Date` needs date or date-time.
//
// `given: $.components.schemas[*]` passes one (resolved) model schema at a time; only its own properties are
// checked, since a referenced model is checked as its own component. A nullable property's format sits on a
// non-null anyOf/oneOf branch (how Pydantic emits `datetime | None`), so the branches are searched too.

var DATE_TIME_FORMATS = ["date-time", "date", "time"];

function getSchema() {
  return {
    name: "dateTimeProperty",
    properties: [{ name: "check", description: "naming (Zalando 235) or format (Zalando 169)" }],
    required: ["check"],
  };
}

function propertyFormat(property) {
  if (typeof property.format === "string") {
    return property.format;
  }
  var branches = property.anyOf || property.oneOf;
  if (!Array.isArray(branches)) {
    return null;
  }
  for (var i = 0; i < branches.length; i++) {
    if (branches[i] && typeof branches[i].format === "string") {
      return branches[i].format;
    }
  }
  return null;
}

function namingProblem(name, format) {
  if (DATE_TIME_FORMATS.indexOf(format) === -1) {
    return null;
  }
  if (/At$/.test(name)) {
    return null;
  }
  if (/date|time|day/i.test(name)) {
    return null;
  }
  return (
    "property '" + name + "' has format " + format + " but its name doesn't end in 'At' or mention date, time or day"
  );
}

function describeFormat(format) {
  if (format === null) {
    return "it has no format";
  }
  return "its format is " + format;
}

function formatProblem(name, format) {
  if (/[a-z0-9](At|Timestamp)$/.test(name) || name === "timestamp") {
    if (format === "date-time") {
      return null;
    }
    return "property '" + name + "' is named as a point in time but " + describeFormat(format) + ", not date-time";
  }
  if (/[a-z0-9]Date$/.test(name) || name === "date") {
    if (format === "date") {
      return null;
    }
    if (format === "date-time") {
      return null;
    }
    return "property '" + name + "' is named as a date but " + describeFormat(format) + ", not date or date-time";
  }
  return null;
}

// vacuum passes only the input to runRule; the rule's functionOptions come in through the global `context`.
function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var properties = input.properties;
  if (!properties || typeof properties !== "object") {
    return [];
  }
  var check = context.ruleAction.functionOptions.check;
  var results = [];
  for (var name in properties) {
    if (!properties[name] || typeof properties[name] !== "object") {
      continue;
    }
    var format = propertyFormat(properties[name]);
    var problem = check === "naming" ? namingProblem(name, format) : formatProblem(name, format);
    if (problem !== null) {
      results.push({ message: problem });
    }
  }
  return results;
}
