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
// they are the other common convention for instants and would otherwise pass as unsuffixed names. Booleans are
// skipped: a flag can't hold a date, so a name like `alreadyUpToDate` is an idiom, not a misnamed date.
// Path parameters are snake_case (path-param-snake-case, since FastAPI maps each to a Python argument), so for
// them the suffixes are `_date_time`, `_date` and `_time`, and `_at`/`_timestamp` are refused.
//
// The input is either one (resolved) model schema from `$.components.schemas[*]`, whose own properties are
// checked (a referenced model is checked as its own component), or one operation parameter. A nullable value's
// format sits on a non-null anyOf/oneOf branch (how Pydantic emits `datetime | None`), so branches are searched.

function getSchema() {
  return { name: "dateTimeSuffix" };
}

// The schema's format, read from its non-null anyOf/oneOf branches when it has none of its own. When those branches
// disagree (Pydantic's `datetime | date`, or `datetime | str`), returns the list of their formats (null for a branch
// with none), since no single suffix fits such a field.
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
  var formats = [];
  for (var i = 0; i < branches.length; i++) {
    if (!branches[i] || branches[i].type === "null") {
      continue;
    }
    var format = typeof branches[i].format === "string" ? branches[i].format : null;
    if (formats.indexOf(format) === -1) {
      formats.push(format);
    }
  }
  if (formats.length === 0) {
    return null;
  }
  if (formats.length === 1) {
    return formats[0];
  }
  return formats;
}

var DATE_TIME_FORMATS = ["date-time", "date", "time"];

function mixesDateTimeFormats(formats) {
  for (var i = 0; i < formats.length; i++) {
    if (DATE_TIME_FORMATS.indexOf(formats[i]) !== -1) {
      return true;
    }
  }
  return false;
}

function isBooleanSchema(schema) {
  if (!schema || typeof schema !== "object") {
    return false;
  }
  if (schema.type === "boolean") {
    return true;
  }
  return Array.isArray(schema.type) && schema.type.indexOf("boolean") !== -1;
}

// Each style lists its suffixes longest first, so `_date_time` is matched before `_time`.
var CAMEL = {
  suffixes: [
    { pattern: /DateTime$/, bare: "dateTime", format: "date-time" },
    { pattern: /Date$/, bare: "date", format: "date" },
    { pattern: /Time$/, bare: "time", format: "time" },
  ],
  suffixForFormat: { "date-time": "DateTime", date: "Date", time: "Time" },
  instantName: /[a-z0-9](At|Timestamp)$/,
  instantStyle: "…At/…Timestamp",
};
var SNAKE = {
  suffixes: [
    { pattern: /_date_time$/, bare: "date_time", format: "date-time" },
    { pattern: /_date$/, bare: "date", format: "date" },
    { pattern: /_time$/, bare: "time", format: "time" },
  ],
  suffixForFormat: { "date-time": "_date_time", date: "_date", time: "_time" },
  instantName: /[a-z0-9]_(at|timestamp)$/,
  instantStyle: "…_at/…_timestamp",
};

function suffixFormat(name, style) {
  for (var i = 0; i < style.suffixes.length; i++) {
    if (style.suffixes[i].pattern.test(name) || name === style.suffixes[i].bare) {
      return style.suffixes[i].format;
    }
  }
  return null;
}

function describeFormat(format) {
  if (format === null) {
    return "it has no format";
  }
  return "its format is " + format;
}

function problem(kind, name, format, isBoolean, style) {
  if (isBoolean) {
    return null;
  }
  if (Array.isArray(format)) {
    if (suffixFormat(name, style) === null && !mixesDateTimeFormats(format)) {
      return null;
    }
    var shown = [];
    for (var i = 0; i < format.length; i++) {
      shown.push(format[i] === null ? "no format" : format[i]);
    }
    return (
      kind +
      " '" +
      name +
      "' accepts values of several formats (" +
      shown.join(", ") +
      "); a date/time field needs exactly one"
    );
  }
  var expectedFormat = suffixFormat(name, style);
  var expectedSuffix = style.suffixForFormat[format];
  if (style.instantName.test(name) || name === "timestamp") {
    return (
      kind +
      " '" +
      name +
      "' is named as an instant in the " +
      style.instantStyle +
      " style; end it in " +
      style.suffixForFormat["date-time"] +
      " instead"
    );
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
    var parameterProblem = problem(
      input.in + " parameter",
      input.name,
      schemaFormat(input.schema),
      isBooleanSchema(input.schema),
      input.in === "path" ? SNAKE : CAMEL,
    );
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
    var propertyProblem = problem(
      "property",
      name,
      schemaFormat(properties[name]),
      isBooleanSchema(properties[name]),
      CAMEL,
    );
    if (propertyProblem !== null) {
      results.push({ message: propertyProblem });
    }
  }
  return results;
}
