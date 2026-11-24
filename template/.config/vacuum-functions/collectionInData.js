// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 110 (https://opensource.zalando.com/restful-api-guidelines/#110) requires a top-level JSON object;
// gov.au API Responses (Operations on a Resource Collection) adds that a collection MUST be returned in a "data"
// array, giving clients one predictable path to the items and leaving room beside it for metadata such as
// pagination. `given: $.paths` passes the whole (resolved) paths map, so the path keys are available to
// tell a collection from a single resource without guessing from the response shape alone.
//
// A GET counts as listing a collection when its path's last segment is static (not a `{param}`), which
// rules out reads of one resource by its ID, AND its success body has a top-level array property, which
// rules out static singletons such as a healthcheck. Such a body must hold its items in `data`, and no
// other top-level property may be an array.

function getSchema() {
  return { name: "collectionInData" };
}

// A trailing slash would make the last segment empty, but vacuum's built-in path-keys-no-trailing-slash (enabled in
// the recommended set) already fails any such path, so this relies on it rather than stripping empty segments.
function lastSegmentIsParameter(pathKey) {
  var segments = pathKey.split("/");
  var last = segments[segments.length - 1];
  return last.charAt(0) === "{";
}

// Known gap, accepted: only `type: "array"` counts as an array, not the one-element type list `type: ["array"]` that
// JSON Schema also allows. FastAPI never writes that form (Pydantic writes a list as `type: "array"`, and a nullable
// list as anyOf [array, null], which no-nullable-array refuses), so it can't hide a collection here.
function topLevelArrayProperties(schema) {
  var names = [];
  if (!schema || typeof schema !== "object") {
    return names;
  }
  var properties = schema.properties;
  if (!properties || typeof properties !== "object") {
    return names;
  }
  for (var name in properties) {
    var property = properties[name];
    if (property && property.type === "array") {
      names.push(name);
    }
  }
  return names;
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var results = [];
  for (var pathKey in input) {
    if (lastSegmentIsParameter(pathKey)) {
      continue;
    }
    var getOperation = input[pathKey] && input[pathKey].get;
    if (!getOperation || !getOperation.responses) {
      continue;
    }
    for (var statusCode in getOperation.responses) {
      if (statusCode.charAt(0) !== "2") {
        continue;
      }
      var content = getOperation.responses[statusCode].content;
      if (!content || typeof content !== "object") {
        continue;
      }
      for (var mediaType in content) {
        var arrayNames = topLevelArrayProperties(content[mediaType] && content[mediaType].schema);
        for (var i = 0; i < arrayNames.length; i++) {
          if (arrayNames[i] === "data") {
            continue;
          }
          results.push({
            message:
              "GET " +
              pathKey +
              " (" +
              statusCode +
              ") returns a collection under '" +
              arrayNames[i] +
              "'; a collection's items must be in a top-level 'data' array",
          });
        }
      }
    }
  }
  return results;
}
