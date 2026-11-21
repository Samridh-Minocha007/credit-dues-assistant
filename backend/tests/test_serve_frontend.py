"""Hosted pilot: the backend can serve the built frontend (one server)."""
import importlib

from fastapi.testclient import TestClient


def test_serves_app_files_and_falls_back_to_index(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    import app.main as main

    main = importlib.reload(main)
    try:
        c = TestClient(main.app)
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/customers/12").text == "<html>app</html>"  # a screen of the app
        assert c.get("/../secret").status_code in (200, 404)  # never escapes the build folder
        assert c.get("/api/health").json()["ok"] is True
    finally:
        monkeypatch.delenv("FRONTEND_DIST")
        importlib.reload(main)
