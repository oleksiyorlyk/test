"""Read-only HTTP checks from the backend container through the frontend proxy."""

import json
import urllib.error
import urllib.request


def read(path):
    request = urllib.request.Request("http://frontend" + path, headers={"Host": "localhost:8080"})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        return response.read()


def main():
    home = read("/")
    assert b'id="root"' in home
    assert read("/jobs/offline") == home
    health = json.loads(read("/api/health"))
    assert health["mode"] == "local"
    assert health["checks"]["playwright"]
    assert isinstance(json.loads(read("/api/jobs"))["items"], list)
    schema = json.loads(read("/openapi.json"))
    assert "/api/jobs" in schema["paths"]
    assert b"swagger-ui" in read("/docs")
    assert b"redoc" in read("/redoc").lower()
    try:
        read("/api/jobs/ci-missing/artifacts/ci-missing")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
        assert json.load(exc)["error"]["code"] == "NOT_FOUND"
    else:
        raise AssertionError("Missing artifact must return a JSON 404")
    print("Nginx SPA, API, OpenAPI, Swagger, ReDoc and JSON errors: OK")


if __name__ == "__main__":
    main()
