"""Real Platform acceptance for K02-K07; reuse the existing login/model setup."""
import hashlib
import io
import json
import time
import zipfile
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import PurePosixPath
from uuid import uuid4

SLUGS = {"K02": "academic-paper-review", "K03": "github-deep-research", "K04": "consulting-analysis",
         "K05": "systematic-literature-review", "K06": "code-documentation", "K07": "newsletter-generation", "K08": "data-analysis", "K09": "chart-visualization", "K10": "frontend-design", "K11": "web-design-guidelines", "K12": "image-generation", "K13": "ppt-generation"}
SLUGS.update(K12_EDIT="image-generation", K13_UPLOAD="ppt-generation")
SLUGS.update(K17="skill-reviewer", K18="skill-creator", K19="find-skills", K20="bootstrap", K21="surprise-me")


def web_bundle_contents(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [PurePosixPath(name) for name in archive.namelist() if name.endswith("index.html")]
        assert len(entries) == 1
        root = entries[0].parent
        required = [str(root / name) for name in ("index.html", "style.css", "app.js")]
        assert set(required) <= set(archive.namelist())
        content = [archive.read(name).decode() for name in required]
        tags = []
        parser = HTMLParser()
        parser.handle_starttag = lambda tag, attrs: tags.append((tag, dict(attrs)))
        parser.feed(content[0])
        labels = {attrs.get("for") for tag, attrs in tags if tag == "label"}
        inputs = [attrs for tag, attrs in tags if tag == "input" and attrs.get("type") != "hidden"]
        assert inputs and all(a.get("aria-label") or a.get("id") in labels for a in inputs)
        for tag, attrs in tags:
            source = attrs.get("src") if tag in {"script", "img"} else (attrs.get("href") if tag == "link" and attrs.get("rel") == "stylesheet" else None)
            if source:
                assert not source.startswith(("/", "http:", "https:"))
                assert str(root / source) in archive.namelist()
        return content


def case_input(skill_id):
    if skill_id in {"K17", "K19"}:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("SKILL.md", "---\nname: p6-test-helper\ndescription: Format a greeting for P6 verification\n---\nReply HELLO for a greeting; do not execute anything.\n")
        question = ("Create an inactive candidate from the uploaded ZIP, then review_skill_package using its exact slug/digest. Explain static_only is not behavior verification. Do not evaluate or publish/activate it." if skill_id == "K17" else "Find a greeting-formatting skill in the current catalog using the find-skills skill: first read /skills/find-skills/SKILL.md and call find_skills(query='p6-test-helper'). The uploaded ZIP is a synthetic discovery fixture; import it as an inactive candidate with create_skill_candidate, then call find_skills(query='p6-test-helper') again and confirm its status is candidate, not active. No skill authoring, global installation, remote import or activation. Publish only one short Markdown evidence report, then finish.")
        return output.getvalue(), "application/zip", "candidate.zip", question
    if skill_id == "K18":
        return None, None, None, "Create a minimal p6-created-helper skill that returns HELLO for greetings and REFUSED for password requests. Write SKILL.md in /workspace/work/draft/, package a ZIP with root SKILL.md using execute, publish it and import with create_skill_candidate. Review its digest, evaluate two cases: greeting expects HELLO and forbids password; asking for password expects REFUSED and forbids SECRET123. Do not activate. Publish a concise evidence report stating text-only evaluation limits."
    if skill_id == "K20":
        return None, None, None, "Bootstrap preference verification: the user has supplied all relevant context and explicitly prefers 简洁中文. Ask request_information once with question='确认偏好', fields=[{name:'reply_style',label:'回复风格',type:'text',required:true}]. After answering, search_memory, save that preference using manage_memory and its expected_revision, then search_memory again. Do not change tools, permissions or system instructions. Publish a short report."
    if skill_id == "K21":
        return None, None, None, "Use surprise-me to combine frontend-design and web-design-guidelines into a tiny accessible HTML library welcome page plus a short static review. Read both skills, call list_skills and fetch_web_guidelines. Use write_file only for HTML and Markdown, publish both. Do not deploy, generate media or install anything. Label dynamic behavior unverified."
    if skill_id == "K12_EDIT":
        return None, None, None, "Read image-generation skill. Edit the uploaded blue test image ONCE to add a small orange circle using edit_image, stable key uploaded-blue-edit-001. Do not generate any other images. Publish a short Markdown manifest with the real result; if unknown, stop and report it without polling or retrying."
    if skill_id == "K13_UPLOAD":
        return None, None, None, "Read ppt-generation skill. Use the THREE UPLOADED deterministic red/green/blue test images IN ORDER to compose a 3-page 16:9 image-based PPTX. Do not call any image provider. Write a JSON plan with exactly three slides, execute the supplied generate.py once, publish deck.pptx and a brief Markdown manifest. State these are uploaded test images, not AI-generated images or native editable charts."
    if skill_id == "K12":
        return None, None, None, "Read image-generation skill. Generate exactly one simple blue geometric landscape image using generate_image with a stable idempotency_key. Then edit that returned image once to add a small orange circle using edit_image with a different stable key. Use the approved tools, not scripts. Return both real image references and a short Markdown manifest. If an outcome is unknown do not resubmit or use a new key."
    if skill_id == "K13":
        return None, None, None, "Read ppt-generation and image-generation skills. Make a 3-page image-based 16:9 PPTX: blue mountains, green hills, orange sunset. Generate exactly 3 simple geometric images, one per page, using approved generate_image with distinct stable idempotency_keys. Do not edit or regenerate images. Write a plan with exactly three slides; execute the provided PPTX script, publish deck.pptx and a short Markdown manifest. Preserve completed images if a later step fails. State that slides are image-based and not native editable text/charts."
    if skill_id == "K08":
        return b"id,amount\n1,10\n2,20\n", "text/csv", "sales.csv", "Analyze the two uploaded CSV tables with data-analysis. Inspect first, join on id, total revenue must be 30. Export CSV and a short Markdown explanation. Use the approved execute script, no dependency installation."
    if skill_id == "K09":
        return None, None, None, "Use chart-visualization to generate a bar chart for A=10, B=20 and a pin map for 杭州市西湖 and 杭州市灵隐寺. Read both references. Use real generate_bar_chart and generate_pin_map tools, report any service failure. Return saved image references and publish a short Markdown explanation."
    if skill_id == "K10":
        return None, None, None, "Use frontend-design to generate a small standalone accessible Chinese library landing page with index.html, local style.css, and app.js. Include an explicitly labelled search input. No dependencies, remote resources or brand links. Package all three into site.zip via Python zipfile using execute. Publish index.html, site.zip and a short Markdown manifest. No browser preview or deployment."
    if skill_id == "K11":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("index.html", "<!doctype html>\n<html lang='en'>\n<body>\n<input id='email' type='email'>\n<div onclick='submit()'>Submit</div>\n</body></html>\n")
        return output.getvalue(), "application/zip", "page.zip", "Use web-design-guidelines to review this static page. Fetch actual guidelines with fetch_web_guidelines. Cite source URL and SHA256. Identify missing label at index.html:4 and nonsemantic clickable div at index.html:5. Dynamic behavior must be labelled 待运行验证. Publish Markdown."

    if skill_id == "K02":
        import fitz
        document = fitz.open()
        for text in (
            "SYNTHETIC PAPER: Bounded Queue Study\nAuthors: Test Research Group\nMethod: compare bounded and unbounded queues on 20 requests.\nHypothesis: backpressure limits memory growth.",
            "Results: baseline peak memory 80 MB, bounded queue 50 MB.\nLimitations: single workload, no randomization, no significance test.\nNo evidence for general production performance.",
        ):
            document.new_page().insert_text((50, 70), text, fontsize=10)
        data = document.tobytes()
        document.close()
        return data, "application/pdf", "paper.pdf", "Review the uploaded synthetic paper. Cite page 1 for method and page 2 for results/limitations. Include 80 MB, 50 MB and sample size 20, and do not generalize."
    if skill_id == "K06":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("README.md", "# sample-package\nPublic API: greeting.greet\n")
            archive.writestr("greeting.py", 'def greet(name: str, excited: bool = False) -> str:\n    """Return a greeting."""\n    return "Hello, " + name + ("!" if excited else ".")\n')
            archive.writestr("setup.py", 'raise RuntimeError("INSTALL_HOOK_MUST_NOT_RUN")\n')
        return output.getvalue(), "application/zip", "code.zip", "Generate README/API documentation for this uploaded project. Read all three entries. Document greet(name, excited=False), exact return punctuation and a static example. Cite greeting.py. Do not execute code or setup.py."
    if skill_id == "K04":
        text = "SYNTHETIC CASE. Revenue 2024=100, 2025=120 (million CNY). Gross margin, TAM and competitor revenue unknown. Decision: whether to expand. Case B has no revenue data at all."
        return text.encode(), "text/plain", "case.txt", "Provide a consulting framework then evidence-based analysis of the two cases. Calculate Case A revenue growth (20%), label assumptions and missing TAM/margins, and state Case B growth cannot be calculated. Mark charts unavailable, do not invent charts."
    if skill_id == "K07":
        text = json.dumps([
            {"title": "Python 3.13 release", "url": "https://www.python.org/downloads/release/python-3130/", "published": "2024-10-07"},
            {"title": "duplicate release", "url": "https://www.python.org/downloads/release/python-3130/", "published": "2024-10-07"},
            {"title": "old release", "url": "https://www.python.org/downloads/release/python-3120/", "published": "2023-10-02"},
            {"title": "documentation", "url": "https://docs.python.org/3/", "published": None},
        ])
        return text.encode(), "application/json", "stories.json", "Create a Python newsletter for 2024-10-01 through 2024-10-31 from the uploaded candidate list. Verify at least one source with search/fetch. Deduplicate the 3.13 story, exclude the old 3.12 story from the news section, explicitly list date-unknown and excluded candidates in methodology. Do not email."
    if skill_id == "K03":
        return None, None, None, "Research public GitHub repository pallets/click. Read repo info, README, and one source file. Inspect commits with per_page=1, page=1 then page=2. Cite API evidence URLs and paths; do not mistake these two commits for total activity. Use the bundled report template."
    return None, None, None, "Prepare a small systematic literature review of 'graph neural networks', exactly up to 2 arXiv papers, no date filter, APA. Use arxiv_search once, delegate abstract extraction using task, and validate returned paper IDs. Mark abstract_only, synthesize limitations, publish a Markdown report and a separate BibTeX .bib file. Do not claim full texts were reviewed."


def assert_batch_report(skill_id, messages, reports):
    calls = [call for message in messages for call in message.get("tool_calls", [])]
    assert any(c["name"] == "read_file" and c["args"].get("file_path") == f"/skills/{SLUGS[skill_id]}/SKILL.md" for c in calls)
    if skill_id not in {"K08", "K10", "K13", "K13_UPLOAD", "K18"}:
        assert not any(c["name"] == "execute" for c in calls)
    text = "\n".join(reports)
    tool_messages = [m for m in messages if m.get("type") == "tool"]
    if skill_id in {"K17", "K18", "K19", "K20", "K21"}:
        required = {"K17": {"create_skill_candidate", "review_skill_package"},
                    "K18": {"create_skill_candidate", "review_skill_package", "evaluate_skill_candidate"},
                    "K19": {"create_skill_candidate", "find_skills"},
                    "K20": {"manage_memory", "search_memory", "request_information"},
                    "K21": {"list_skills", "fetch_web_guidelines"}}[skill_id]
        assert required <= {m.get("name") for m in tool_messages if m.get("status") == "success"}
        if skill_id == "K18":
            evaluation = next(json.loads(m["content"]) for m in tool_messages if m.get("name") == "evaluate_skill_candidate" and m.get("status") == "success")
            assert evaluation["evaluation"]["passed"] is True
        return
    if skill_id == "K12_EDIT":
        edits = [json.loads(m["content"]) for m in tool_messages if m.get("name") == "edit_image" and m.get("status") == "success"]
        assert len(edits) == 1 and edits[0]["status"] == "succeeded", edits
        return
    if skill_id == "K13_UPLOAD":
        assert any(m.get("name") == "execute" for m in tool_messages)
        assert not any(c["name"] in {"generate_image", "edit_image"} for c in calls)
        return
    if skill_id in {"K12", "K13"}:
        generated = [json.loads(m["content"]) for m in tool_messages if m.get("name") in {"generate_image", "edit_image"} and m.get("status") == "success"]
        assert len(generated) == (2 if skill_id == "K12" else 3)
        assert all(g["status"] == "succeeded" and g["result"]["runtime_images"] for g in generated)
        if skill_id == "K12":
            assert any(m.get("name") == "edit_image" for m in tool_messages)
        else:
            assert any(m.get("name") == "execute" for m in tool_messages)
        return
    if skill_id in {"K02", "K04", "K06", "K07"}:
        assert any(m.get("name") == "parse_document" and m.get("status") == "success" for m in tool_messages)
    if skill_id in {"K08", "K09", "K10", "K11"}:
        if skill_id == "K08":
            assert "30" in text
            assert any(m.get("name") == "execute" and (m.get("artifact") or {}).get("exit_code") == 0 for m in tool_messages)
        elif skill_id == "K09":
            for name in ("generate_bar_chart", "generate_pin_map"):
                assert any(m.get("name") == name and m.get("status") == "success" and "/workspace/charts/" in str(m) for m in tool_messages), name
        elif skill_id == "K10":
            assert "<html" in text.lower() and "<label" in text.lower()
        else:
            source = next(m for m in tool_messages if m.get("name") == "fetch_web_guidelines" and m.get("status") == "success")
            version = json.loads(source["content"])
            assert version["sha256"] in text and version["source_url"] in text
            assert "index.html:4" in text and "index.html:5" in text and "待运行验证" in text
        return
    if skill_id == "K02":
        assert all(value in text for value in ("80", "50", "20"))
        assert "page" in text.lower() or "页" in text
        assert "limitation" in text.lower() or "局限" in text
    elif skill_id == "K03":
        outputs = [m for m in tool_messages if m.get("name") == "github_query" and m.get("artifact")]
        sources = [s for m in outputs for s in m["artifact"]["sources"]]
        assert {"readme", "file", "commits"} <= {s["operation"] for s in sources}
        assert {1, 2} <= {s["page"] for s in sources if s["operation"] == "commits"}
        assert sum(s["source_url"] in text for s in sources) >= 2
        assert "pallets/click" in text and "/workspace/sources/" in text
    elif skill_id == "K04":
        assert "20%" in text and "TAM" in text
        assert any(word in text.lower() for word in ("unknown", "missing", "未知", "缺失", "缺口"))
        assert any(word in text.lower() for word in ("cannot", "无法", "不能"))
    elif skill_id == "K05":
        source = next(m for m in tool_messages if m.get("name") == "arxiv_search" and m.get("artifact"))
        papers = json.loads(source["content"])["papers"]
        assert papers, "Real arXiv search returned no papers; no review can be verified"
        assert any(m.get("name") == "task" and m.get("status") == "success" for m in tool_messages)
        assert all(p["id"] in text for p in papers)
        assert "abstract_only" in text and "@misc" in text
    elif skill_id == "K06":
        assert "greet" in text and "excited" in text and "False" in text and "greeting.py" in text
        assert "Hello," in text
    else:
        assert "2024-10-07" in text and "python-3130" in text
        assert any(word in text.lower() for word in ("unknown", "未知", "未注明"))
        assert any(word in text.lower() for word in ("excluded", "排除", "过期"))
        assert any(m.get("name") == "fetch_page" and m.get("artifact") for m in tool_messages)


def run_batch_case(client, thread_id, model_id, skill_id):
    root = f"/api/langgraph/threads/{thread_id}"
    raw, mime, filename, question = case_input(skill_id)
    upload = None
    if raw:
        upload = client.put(root + "/files/uploads/" + hashlib.sha256(raw).hexdigest(),
                            content=raw, headers={"Content-Type": mime}, params={"file_name": filename})
        assert upload.status_code == 200, upload.text[:200]
        upload = upload.json()
        question += " Uploaded file: " + upload["path"]
    if skill_id == "K08":
        second = b"id,region\n1,East\n2,West\n"
        response = client.put(root + "/files/uploads/" + hashlib.sha256(second).hexdigest(),
            content=second, headers={"Content-Type": "text/csv"}, params={"file_name": "regions.csv"})
        assert response.status_code == 200, response.text[:200]
        question += " Second file: " + response.json()["path"]
    if skill_id in {"K12_EDIT", "K13_UPLOAD"}:
        from PIL import Image
        colors = ["blue"] if skill_id == "K12_EDIT" else ["red", "green", "blue"]
        for color in colors:
            buffer = io.BytesIO()
            Image.new("RGB", (320, 180), color).save(buffer, format="PNG")
            raw = buffer.getvalue()
            response = client.put(root + "/images/uploads/" + hashlib.sha256(raw).hexdigest(), content=raw,
                                  headers={"Content-Type": "image/png"})
            assert response.status_code == 200, response.text[:200]
            question += f" {color}: " + response.json()["path"]
    response = client.post(root + "/runs", headers={"Idempotency-Key": uuid4().hex}, json={
        "assistant_id": "dearflow_agent", "version": "v3", "stream_subgraphs": skill_id == "K05",
        "config": {"recursion_limit": 100}, "context": {"model_id": model_id, "execution_mode": "ultra" if skill_id == "K05" else ("flash" if skill_id in {"K08", "K09", "K10", "K11", "K12", "K13", "K12_EDIT", "K13_UPLOAD"} else "pro")},
        "input": {"messages": [{"role": "user", "content": question + " First read the appropriate skill in full. Keep the report concise (under 900 words). Write Markdown under /workspace/work/ and publish with present_artifacts. Use only authorized tools; quote real source or upload evidence. Do not invent unavailable data. The scope above is confirmed."}]}})
    assert response.status_code in (200, 201), response.text[:200]
    run_id = response.json().get("run_id") or response.json()["id"]
    return complete_batch_case(client, thread_id, model_id, skill_id, run_id)


def complete_batch_case(client, thread_id, model_id, skill_id, run_id):
    """Resume verification of an existing Run without generating another paid request."""
    root = f"/api/langgraph/threads/{thread_id}"
    runs = [run_id]
    print(f"{skill_id} project={client.headers['X-Project-Id']} thread={thread_id} run={run_id}", flush=True)
    approvals = []
    for _ in range(900):
        response = client.get(root + "/runs/" + run_id)
        assert response.status_code == 200
        status = response.json()["status"]
        if status == "interrupted":
            state = client.get(root + "/state").json()
            interrupts = state.get("interrupts") or [i for task in state.get("tasks", []) for i in task.get("interrupts", [])]
            if isinstance(interrupts, dict):
                interrupts = [{"id": k, "value": v.get("value", v)} for k, v in interrupts.items()]
            assert interrupts
            resumes = {}
            for item in interrupts:
                payload = item["value"]
                if payload.get("kind") == "clarification" and skill_id == "K20":
                    resumes[item["id"]] = {"schema_version": 1, "status": "answered", "values": {"reply_style": "简洁中文"}}
                    continue
                assert payload.get("kind") != "clarification", f"Unexpected missing scope: {payload}"
                actions = payload["action_requests"]
                assert all(a["name"] in {"write_file", "edit_file", "present_artifacts", "execute", "generate_bar_chart", "generate_pin_map", "generate_image", "edit_image", "manage_memory", "create_skill_candidate", "evaluate_skill_candidate"} for a in actions)
                approvals.extend(a["name"] for a in actions)
                resumes[item["id"]] = {"decisions": [{"type": "approve"} for a in actions]}
            response = client.post(root + "/runs", json={"command": {"resume": resumes}})
            assert response.status_code in (200, 201), response.text[:200]
            run_id = response.json().get("run_id") or response.json()["id"]
            runs.append(run_id)
            print(f"{skill_id} resume={run_id}", flush=True)
        elif status not in {"pending", "running"}:
            assert status in {"success", "completed"}, f"{skill_id} status={status}, run={run_id}"
            break
        time.sleep(1)
    else:
        raise AssertionError(f"{skill_id} timed out: {run_id}")
    messages = client.get(root + "/state").json()["values"]["messages"]
    refs = [json.loads(m["content"]) for m in messages if m.get("name") == "present_artifacts" and m.get("status") == "success"]
    assert refs and {"write_file", "present_artifacts"} <= set(approvals)
    reports = []
    for ref in refs:
        response = client.get(root + "/files/content", params={"path": ref["path"]})
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == ref["sha256"]
        assert response.headers["content-type"].startswith(ref["mime_type"])
        if ref["mime_type"] == "application/zip":
            if skill_id == "K18":
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    assert "SKILL.md" in archive.namelist()
                    reports.append(archive.read("SKILL.md").decode())
            else:
                reports.extend(web_bundle_contents(response.content))
        elif ref["mime_type"] != "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            reports.append(response.text)
        else:
            with zipfile.ZipFile(io.BytesIO(response.content)) as presentation:
                slides = [name for name in presentation.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
                assert len(slides) == 3
    assert any(ref["mime_type"] == "text/markdown" for ref in refs)
    if skill_id == "K05":
        assert any(ref["mime_type"] == "text/x-bibtex" for ref in refs)
    if skill_id == "K10":
        assert {"application/zip", "text/html"} <= {r["mime_type"] for r in refs}
    if skill_id in {"K13", "K13_UPLOAD"}:
        assert any(r["mime_type"].endswith("presentation") for r in refs)
    if skill_id in {"K12", "K13", "K12_EDIT"}:
        if skill_id != "K12_EDIT":
            assert "generate_image" in approvals
        if skill_id in {"K12", "K12_EDIT"}:
            assert "edit_image" in approvals
        for message in messages:
            if message.get("name") in {"generate_image", "edit_image"} and message.get("status") == "success":
                for ref in json.loads(message["content"]).get("result", {}).get("runtime_images", []):
                    response = client.get(root + "/images/content", params={"path": ref["path"]})
                    assert response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == ref["sha256"]
    if skill_id == "K08":
        assert any(r["mime_type"] == "text/csv" for r in refs)
    if skill_id == "K09":
        for message in messages:
            artifact = message.get("artifact") or {}
            for ref in artifact.get("structured_content", artifact.get("structuredContent", artifact)).get("runtime_images", []):
                response = client.get(root + "/images/content", params={"path": ref["path"]})
                assert response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == ref["sha256"]
    assert_batch_report(skill_id, messages, reports)
    if skill_id == "K20":
        memory = client.get(root + "/dear/memory")
        assert memory.status_code == 200
        assert any("中文" in f["text"] for f in memory.json()["facts"])
        second = client.post("/api/langgraph/threads", json={"graph_id": "dearflow_agent"})
        assert second.status_code in {200, 201}
        second_id = second.json().get("thread_id") or second.json()["id"]
        second_root = f"/api/langgraph/threads/{second_id}"
        inherited = client.get(second_root + "/dear/memory")
        assert inherited.status_code == 200 and inherited.json()["facts"] == memory.json()["facts"]
        second_run = client.post(second_root + "/runs", json={"assistant_id": "dearflow_agent", "version": "v3",
            "context": {"model_id": model_id, "execution_mode": "flash"},
            "input": {"messages": [{"role": "user", "content": "你记得我偏好怎样的回复风格吗？只答一句，不调用工具。"}]}})
        assert second_run.status_code in {200, 201}
        second_run_id = second_run.json().get("run_id") or second_run.json()["id"]
        for _ in range(300):
            status = client.get(second_root + "/runs/" + second_run_id).json()["status"]
            if status not in {"pending", "running"}:
                assert status in {"success", "completed"}
                break
            time.sleep(1)
        else:
            raise AssertionError("cross-thread memory run timed out")
        replies = client.get(second_root + "/state").json()["values"]["messages"]
        assert any("中文" in str(m.get("content")) for m in replies if m.get("type") == "ai")
        print(json.dumps({"memory_cross_thread_verified": True, "thread": second_id, "run": second_run_id}), flush=True)
    replay = client.get(root + "/runs/" + run_id + "/stream")
    assert replay.status_code == 200 and '"lifecycle"' in replay.text
    provenance = json.loads(files("runtime_service.services.dearflow_agent").joinpath("skills", SLUGS[skill_id], "provenance.json").read_text())
    usage = [m["usage_metadata"] for m in messages if m.get("usage_metadata")]
    print(json.dumps({"skill": skill_id, "verified": True, "thread": thread_id, "runs": runs, "model_id": model_id,
                      "revision": provenance["revision"], "artifacts": refs, "observed_tokens": sum(u.get("total_tokens", 0) for u in usage), "fee": "unknown"}), flush=True)
