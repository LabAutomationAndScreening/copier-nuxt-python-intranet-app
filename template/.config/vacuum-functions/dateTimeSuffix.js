// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// gov.au Naming Conventions: a date/time field's name ends in the suffix of its type, and each suffix means
// exactly that type. In camelCase:
//   format date-time  <->  name ends in `DateTime` (an instant)
//   format date       <->  name ends in `Date`     (a calendar day, no time zone)
//   format time       <->  name ends in `Time` but not `DateTime` (a time of day)
// Checked in both directions, so a date-only value can't hide behind an instant's name or the reverse (a
// "date" parsed to UTC midnight lands on the previous day west of Greenwich), and a name that promises a date
// or time can't be a bare string or an epoch number. `…At` and `…Timestamp` names are refused outright, since
// they are the other common convention for instants and would otherwise pass as unsuffixed names.
//
// The input is either one (resolved) model schema from `$.components.schemas[*]`, whose own properties are
// checked (a referenced model is checked as its own component), or one operation parameter. A nullable value's
// format sits on a non-null anyOf/oneOf branch (how Pydantic emits `datetime | None`), so branches are searched.

function getSchema() {
  return { name: "dateTimeSuffix" };
}

function schemaFormat(schema) {
  if (!schema || typeof schema !== "object") {
    return null;
  }
  if (typeof schema.format === "string") {
    return schema.format;
  }
  var branches = schema.anyOf || schema.oneOf;
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

function suffixFormat(name) {
  if (/DateTime$/.test(name) || name === "dateTime") {
    return "date-time";
  }
  if (/Date$/.test(name) || name === "date") {
    return "date";
  }
  if (/Time$/.test(name) || name === "time") {
    return "time";
  }
  return null;
}

var SUFFIX_FOR_FORMAT = { "date-time": "DateTime", date: "Date", time: "Time" };

function describeFormat(format) {
  if (format === null) {
    return "it has no format";
  }
  return "its format is " + format;
}

function problem(kind, name, format) {
  var expectedFormat = suffixFormat(name);
  var expectedSuffix = SUFFIX_FOR_FORMAT[format];
  if (/[a-z0-9](At|Timestamp)$/.test(name) || name === "timestamp") {
    return kind + " '" + name + "' is named as an instant in the …At/…Timestamp style; end it in DateTime instead";
  }
  if (expectedFormat !== null) {
    if (expectedFormat === format) {
      return null;
    }
    return kind + " '" + name + "' ends in a " + expectedFormat + " suffix but " + describeFormat(format);
  }
  if (expectedSuffix !== undefined) {
    return kind + " '" + name + "' has format " + format + " but its name doesn't end in " + expectedSuffix;
  }
  return null;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var results = [];
  if (typeof input.name === "string" && typeof input.in === "string") {
    var parameterProblem = problem(input.in + " parameter", input.name, schemaFormat(input.schema));
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
    var propertyProblem = problem("property", name, schemaFormat(properties[name]));
    if (propertyProblem !== null) {
      results.push({ message: propertyProblem });
    }
  }
  return results;
}
