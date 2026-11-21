// Vacuum custom JS function (goja runtime: no npm, no require/import — plain self-contained JS).
//
// Zalando 176 "MUST support problem JSON": every documented error response of an operation (each 4xx and 5xx,
// and the `default` catch-all) is application/problem+json, the media type the exception handlers send. Run on
// `$.paths[*][*].responses`, one operation's responses at a time. One function checks both halves, every media type
// being problem+json and problem+json being there, where plain rules would take two: `field: "@key"`, which would let
// a single `pattern` rule check the media-type keys, is ignored by vacuum's `pattern`
// (https://github.com/daveshanley/vacuum/issues/1072).
// An error response with no content, or no application/problem+json among its media types, fails too: documenting
// it with nothing would let a client generated from the schema miss the problem details it is sent.

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
      results.push({
        message: "the " + statusKey + " response documents no content, but error responses must be " + PROBLEM_JSON,
      });
      continue;
    }
    if (!(PROBLEM_JSON in content)) {
      results.push({
        message:
          "the " +
          statusKey +
          " response has no " +
          PROBLEM_JSON +
          " content, but error responses must be " +
          PROBLEM_JSON,
      });
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
