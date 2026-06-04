"""
test_api.py — HTTP-level tests via FastAPI TestClient.
"""
import pytest
import io


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestRoles:
    def test_list_roles_returns_list(self, client):
        r = client.get("/roles")
        assert r.status_code == 200
        data = r.json()
        assert "roles" in data
        assert data["total"] > 0

    def test_roles_have_required_fields(self, client):
        r = client.get("/roles")
        for role in r.json()["roles"]:
            assert "role_id" in role
            assert "title" in role

    def test_get_single_role(self, client, roles):
        role_id = next(iter(roles))
        r = client.get(f"/roles/{role_id}")
        assert r.status_code == 200
        assert r.json()["role_id"] == role_id

    def test_get_nonexistent_role_404(self, client):
        r = client.get("/roles/nonexistent_role_xyz")
        assert r.status_code == 404


class TestServices:
    def test_list_services(self, client):
        r = client.get("/services")
        assert r.status_code == 200
        assert r.json()["total"] >= 0

    def test_filter_by_skill(self, client):
        r = client.get("/services?skill=python")
        assert r.status_code == 200
        data = r.json()
        for svc in data["services"]:
            assert "python" in [s.lower() for s in svc["skills_covered"]]

    def test_filter_free_only(self, client):
        r = client.get("/services?free=true")
        assert r.status_code == 200
        for svc in r.json()["services"]:
            assert svc["free"] is True

    def test_get_single_service_404(self, client):
        r = client.get("/services/nonexistent_xyz")
        assert r.status_code == 404


class TestAnalyzeText:
    def test_basic_analysis(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={
            "role_id": role_id,
            "resume_text": "Python developer with 3 years of experience in machine learning and SQL."
        })
        assert r.status_code == 200
        data = r.json()
        assert "readiness" in data
        assert "extracted_skills" in data
        assert "skill_gaps" in data

    def test_empty_text_422(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={"role_id": role_id, "resume_text": "   "})
        assert r.status_code == 422

    def test_invalid_role_404(self, client):
        r = client.post("/analyze/text", data={
            "role_id": "nonexistent_role_xyz",
            "resume_text": "Python developer"
        })
        assert r.status_code == 404

    def test_score_in_range(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={
            "role_id": role_id,
            "resume_text": "Python SQL Docker machine learning pandas"
        })
        assert r.status_code == 200
        score = r.json()["readiness"]["score"]
        assert 0 <= score <= 100

    def test_report_id_present(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={
            "role_id": role_id,
            "resume_text": "Experienced Python developer"
        })
        assert r.json()["report_id"]

    def test_other_role_matches_top5(self, client, roles):
        if len(roles) < 2:
            pytest.skip("Need at least 2 roles for multi-role matching")
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={
            "role_id": role_id,
            "resume_text": "Python, SQL, Docker, Kubernetes, machine learning, TensorFlow"
        })
        assert r.status_code == 200
        matches = r.json()["other_role_matches"]
        assert len(matches) <= 5

    def test_career_path_advice_present(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze/text", data={
            "role_id": role_id,
            "resume_text": "Python developer with experience in machine learning"
        })
        # career_path_advice may be None or dict — just check it's in the response
        assert "career_path_advice" in r.json()


class TestAnalyzeFileUpload:
    def test_txt_upload(self, client, roles):
        role_id = next(iter(roles))
        content = b"Python developer with SQL and Docker experience"
        r = client.post("/analyze", data={"role_id": role_id},
                        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")})
        assert r.status_code == 200

    def test_unsupported_extension_400(self, client, roles):
        role_id = next(iter(roles))
        r = client.post("/analyze", data={"role_id": role_id},
                        files={"file": ("resume.rtf", io.BytesIO(b"content"), "text/plain")})
        assert r.status_code == 400


class TestFeedback:
    def test_submit_feedback(self, client):
        r = client.post("/feedback", json={
            "report_id": "test_report_001",
            "correct_skills": ["python"],
            "wrong_skills": ["java"],
            "missing_skills": ["docker"],
            "comment": "Test feedback"
        })
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_minimal_feedback(self, client):
        r = client.post("/feedback", json={"report_id": "abc123"})
        assert r.status_code == 200


class TestAdminEndpoints:
    def test_catalog_stats(self, client):
        r = client.get("/admin/catalog-stats")
        assert r.status_code == 200
        data = r.json()
        assert "catalog_exists" in data
        assert "skills_count" in data
