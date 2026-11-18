// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 176 "MUST support problem JSON": every documented error response of an operation (each 4xx and 5xx,
// and the `default` catch-all) is application/problem+json, the media type the exception handlers send. Run on
// `$.paths[*][*].responses`, one operation's responses at a time. A JSONPath rule can't do this: vacuum 0.30's
// key selector (`~`) finds nothing under a response keyed `default`, so it would miss the catch-all.

var PROBLEM_JSON = "application/problem+json";

function getSchema() {
  return { name: "errorResponsesProblemJson" };
}

function isErrorResponse(statusKey) {
  if (statusKey === "default") {
    return true;
  }
  return /^[45]/.test(statusKey);
}

function runRule(input) {
  if (!input || typeof input !== "object") {
    return [];
  }
  var results = [];
  for (var statusKey in input) {
    if (!isErrorResponse(statusKey)) {
      continue;
    }
    var content = input[statusKey] && input[statusKey].content;
    if (!content || typeof content !== "object") {
      continue;
    }
    for (var mediaType in content) {
      if (mediaType === PROBLEM_JSON) {
        continue;
      }
      results.push({
        message: "the " + statusKey + " response is " + mediaType + ", but error responses must be " + PROBLEM_JSON,
      });
    }
  }
  return results;
}
