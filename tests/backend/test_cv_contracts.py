from backend.cv_contracts import CvSection, CvSource, Evidence, ParsedCv, Suggestion, validate_suggestion

CV = ParsedCv(
    source=CvSource(id="es", lang="es", path="/local/cv_es.tex", sha256="0" * 64, imported_at="2026-10-21"),
    sections=[CvSection(key="skills", kind="skills", text="Python, SQL, Linux", tex_span=(0, 10))],
    skills=["Python", "SQL", "Linux"],
)


def test_suggestion_with_literal_evidence_is_valid():
    s = Suggestion(id="1", action="emphasize", section_key="skills", before="Python, SQL, Linux",
                   after="Linux, Python, SQL", rationale="La oferta prioriza Linux",
                   evidence=[Evidence(section_key="skills", quote="Linux")])
    assert validate_suggestion(s, CV) == []


def test_invented_skill_is_rejected():
    s = Suggestion(id="2", action="rephrase", section_key="skills", before="Python, SQL, Linux",
                   after="Python, SQL, Linux, Kubernetes", rationale="La oferta pide Kubernetes",
                   evidence=[Evidence(section_key="skills", quote="Kubernetes")])
    assert validate_suggestion(s, CV) == ["2: la cita no existe en skills"]


def test_gap_only_reports():
    gap = Suggestion(id="3", action="gap", section_key="skills", before="", after=None,
                     rationale="Kubernetes requerido y no consta en el CV", evidence=[])
    assert validate_suggestion(gap, CV) == []
    assert validate_suggestion(gap.model_copy(update={"after": "Kubernetes"}), CV)


def test_tailoring_plan_can_pin_original_revision():
    from backend.cv_contracts import TailoringPlan
    plan = TailoringPlan(job_id='synthetic-job', cv_id='es', cv_sha256='a'*64,
                         lang='es', coverage=0, suggestions=[])
    assert plan.cv_sha256 == 'a'*64
