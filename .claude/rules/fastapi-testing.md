---
paths:
  - "backend/tests/**/*.py"
  # In the template repository itself, the same tests sit under template/, where a directory or file name can carry Jinja tags and a .jinja suffix.
  - "template/*backend*/tests/**/*.py*"
---
# FastAPI Testing

- Assert on the response model, not raw JSON: `problem = ProblemDetails.model_validate(response.json())`, then `assert problem.error_type == ...` rather than `response.json()["errorType"]`. String keys are invisible to the type checker and yield implicit `Any`, and validating checks the whole payload against the schema (camelCase aliases included) rather than only the keys the test reads.
