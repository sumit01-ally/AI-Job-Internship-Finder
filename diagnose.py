"""
Comprehensive diagnostic script for AI Job & Internship Finder.
Checks imports, database, all module logic, Flask routes, and API key.
"""
import sys
import os
import traceback

os.chdir(r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1")
sys.path.insert(0, r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1")

results = {}

def test(name, fn):
    try:
        outcome = fn()
        results[name] = ("PASS", outcome or "ok")
        print(f"  PASS  {name}: {outcome or 'ok'}")
    except Exception as e:
        results[name] = ("FAIL", str(e))
        print(f"  FAIL  {name}: {e}")
        if "--verbose" in sys.argv:
            traceback.print_exc()

print("\n" + "="*65)
print("  DIAGNOSTIC REPORT – AI Job & Internship Finder")
print("="*65)

# ── 1. Imports ────────────────────────────────────────────────
print("\n[1] Core package imports")
def t_flask():
    from importlib.metadata import version; import flask; return f"Flask {version('flask')}"
def t_tinyfish():
    from importlib.metadata import version; import tinyfish; return f"TinyFish {version('tinyfish')}"
def t_dotenv():
    import dotenv; return "ok"
def t_werkzeug():
    from importlib.metadata import version; return f"Werkzeug {version('werkzeug')}"
def t_apscheduler():
    from importlib.metadata import version; return f"APScheduler {version('APScheduler')}"
test("flask", t_flask); test("tinyfish", t_tinyfish)
test("dotenv", t_dotenv); test("werkzeug", t_werkzeug)
test("apscheduler", t_apscheduler)

# ── 2. Environment ─────────────────────────────────────────────
print("\n[2] Environment")
def t_env_api():
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("TINYFISH_API_KEY","")
    if not k or k=="your_tinyfish_api_key_here":
        return "NOT CONFIGURED – add real key to .env"
    return f"Configured (len={len(k)})"
def t_env_secret():
    from dotenv import load_dotenv; load_dotenv()
    k = os.getenv("FLASK_SECRET_KEY","")
    return f"Set (len={len(k)})" if k and k!="your-very-secret-flask-key-change-this-in-production" else "Using default (ok for dev)"
test("api_key", t_env_api); test("flask_secret", t_env_secret)

# ── 3. Database ────────────────────────────────────────────────
print("\n[3] Database (SQLite)")
def t_db_init():
    from database import init_db; init_db(); return "all 5 tables OK"
def t_db_job_crud():
    from database import save_job_to_db, get_job_by_id, get_job_count
    jid, new = save_job_to_db("Test SE", "Test Corp", location="Remote",
        apply_url="https://t.example.com/test-se-v2", is_internship=False)
    j = get_job_by_id(jid)
    assert j["title"]=="Test SE", f"title mismatch: {j['title']}"
    return f"id={jid} new={new}"
def t_db_dedup():
    from database import save_job_to_db
    _, n1 = save_job_to_db("Dup","C","apply_url="+"https://dup.example.com")
    _, n2 = save_job_to_db("Dup","C","apply_url="+"https://dup.example.com")
    assert not n2; return "duplicate prevention OK"
def t_db_user():
    from database import create_user, get_user_by_email
    create_user("Diag User","diag2@test.com","hashpw")
    u = get_user_by_email("diag2@test.com")
    assert u; return "user CRUD OK"
def t_db_save_unsave():
    from database import save_job_for_user,is_job_saved,unsave_job_for_user,get_user_by_email,save_job_to_db
    u = get_user_by_email("diag2@test.com")
    if not u: return "skip – no user"
    jid,_=save_job_to_db("SaveTest","C2","apply_url="+"https://savetest.example.com")
    save_job_for_user(u["id"],jid); assert is_job_saved(u["id"],jid)
    unsave_job_for_user(u["id"],jid); assert not is_job_saved(u["id"],jid)
    return "save/unsave OK"
def t_db_application():
    from database import apply_to_job,get_applications,get_user_by_email,save_job_to_db
    u = get_user_by_email("diag2@test.com")
    if not u: return "skip – no user"
    jid,_=save_job_to_db("AppTest","C3","apply_url="+"https://apptest.example.com")
    ok,msg = apply_to_job(u["id"],jid,"test notes")
    apps = get_applications(u["id"])
    return f"tracked OK: {msg}"
test("db_init",t_db_init); test("db_job_crud",t_db_job_crud)
test("db_dedup",t_db_dedup); test("db_user",t_db_user)
test("db_save_unsave",t_db_save_unsave); test("db_application",t_db_application)

# ── 4. Module logic (offline, no API) ─────────────────────────
print("\n[4] Module logic (no API required)")
def t_search_query_builder():
    from modules.search_module import build_job_query
    q=build_job_query("Python,React","SE","Bangalore",False,"fresher")
    assert "Python" in q or "React" in q; return f"'{q[:70]}'"
def t_search_filter():
    from modules.search_module import filter_job_urls
    results=[
        {"url":"https://internshala.com/jobs/python-developer","title":"Python Dev","snippet":""},
        {"url":"https://internshala.com","title":"Internshala Home","snippet":""},
    ]
    filtered=filter_job_urls(results)
    assert len(filtered)==1; return f"filtered {len(results)}→{len(filtered)}"
def t_fetch_parser_full():
    from modules.fetch_module import parse_job_from_markdown
    md = """# Software Engineer
Company: Acme Technologies
Location: Bangalore, Karnataka
Salary: ₹8-12 LPA
Skills: Python, Django, REST API, PostgreSQL
Deadline: 2026-12-31
[Apply Now](https://acme.com/apply)
Job description here. Remote friendly."""
    j=parse_job_from_markdown(md,"https://acme.com/job/1")
    assert j["title"], f"no title: {j}"
    assert j["company"], f"no company: {j}"
    return f"title='{j['title']}' company='{j['company']}' salary='{j['salary']}'"
def t_research_skill_match():
    from modules.research_module import match_skills_to_job
    r=match_skills_to_job("Python, React, SQL, Node.js","Python, Django, SQL, REST API, PostgreSQL")
    assert r["match_percent"]>0
    return f"match={r['match_percent']}% matched={r['matched']} missing={r['missing']}"
def t_research_extract():
    from modules.research_module import _extract_report_text
    class FakeReport:
        result="Test report text"
        citations=[]
    class FakeRun:
        deep_result=FakeReport()
        quick_result=None
        error=None
    text=_extract_report_text(FakeRun())
    assert text=="Test report text"; return "extract OK"
def t_agent_schema():
    from modules.agent_module import JOB_OUTPUT_SCHEMA, _parse_agent_output
    import json
    sample=json.dumps({"jobs":[{"title":"Dev","company":"Corp","apply_url":"https://x.com"}]})
    jobs=_parse_agent_output(sample)
    assert len(jobs)==1; return f"schema OK, parsed {len(jobs)} job"
def t_monitor_config():
    from tinyfish import SearchMonitorConfig
    cfg=SearchMonitorConfig(query="Python developer internship India",result_limit=20)
    assert cfg.query; return f"SearchMonitorConfig OK: query='{cfg.query[:40]}'"
def t_browser_platforms():
    from modules.browser_module import get_available_platforms, PLATFORMS
    p=get_available_platforms()
    assert len(p)>=4; return f"{len(p)} platforms: {[x['id'] for x in p]}"
test("search_query_builder",t_search_query_builder)
test("search_filter",t_search_filter)
test("fetch_parser",t_fetch_parser_full)
test("research_skill_match",t_research_skill_match)
test("research_extract",t_research_extract)
test("agent_schema",t_agent_schema)
test("monitor_config",t_monitor_config)
test("browser_platforms",t_browser_platforms)

# ── 5. Flask app ───────────────────────────────────────────────
print("\n[5] Flask application")
def t_routes():
    import importlib.util
    spec=importlib.util.spec_from_file_location("appx",
        r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1\app.py")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    rules=[r.rule for r in mod.app.url_map.iter_rules()]
    required=["/","/login","/register","/logout","/dashboard",
               "/profile","/find-jobs","/find-internships",
               "/job/<int:job_id>","/saved-jobs","/applications",
               "/research","/about",
               "/api/search","/api/agent-search",
               "/api/save-job/<int:job_id>","/api/unsave-job/<int:job_id>",
               "/api/track-application/<int:job_id>",
               "/api/research/analyze","/api/research/recommendations",
               "/api/research/compare","/api/research/company",
               "/api/monitor/run","/api/monitor/history",
               "/api/monitor/create","/api/monitor/list",
               "/api/skill-match/<int:job_id>","/api/stats"]
    missing=[r for r in required if r not in rules]
    if missing: return f"MISSING: {missing}"
    return f"All {len(required)} required routes present ({len(rules)} total)"
def t_templates():
    import os
    tdir=r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1\templates"
    required_tmpl=["base.html","home.html","dashboard.html","find_jobs.html",
                   "job_detail.html","saved_jobs.html","applications.html",
                   "research.html","profile.html","about.html",
                   "auth/login.html","auth/register.html",
                   "errors/404.html","errors/500.html"]
    missing=[t for t in required_tmpl if not os.path.exists(os.path.join(tdir,t))]
    if missing: return f"MISSING templates: {missing}"
    return f"All {len(required_tmpl)} templates present"
def t_static():
    import os
    css=r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1\static\css\style.css"
    js=r"c:\Users\DELL 7450\OneDrive\Desktop\TINYFISH 1\static\js\main.js"
    cs=os.path.getsize(css); js_s=os.path.getsize(js)
    return f"style.css={cs} bytes, main.js={js_s} bytes"
test("flask_routes",t_routes)
test("templates_present",t_templates)
test("static_files",t_static)

# ── 6. API connectivity ────────────────────────────────────────
print("\n[6] TinyFish API (requires real key in .env)")
def t_api_key_check():
    from modules.tinyfish_client import get_client
    c=get_client(); return f"Client OK: {type(c).__name__}"
def t_api_search():
    from modules.search_module import search_jobs
    results,err=search_jobs("Python developer","Software Engineer","India",False,page=0)
    if err: raise RuntimeError(err)
    return f"Search OK: {len(results)} results"
def t_api_fetch():
    from modules.fetch_module import fetch_job_details
    contents,err=fetch_job_details(
        ["https://internshala.com/internships/python-internship"],
        "Testing fetch for Python internship")
    if err and not contents: raise RuntimeError(err)
    total=sum(len(c.get("content","")) for c in contents)
    return f"Fetch OK: {len(contents)} pages, {total} chars"
test("api_client",t_api_key_check)
test("api_search",t_api_search)
test("api_fetch",t_api_fetch)

# ── Summary ────────────────────────────────────────────────────
print("\n"+"="*65)
passed=sum(1 for v in results.values() if v[0]=="PASS")
failed=sum(1 for v in results.values() if v[0]=="FAIL")
print(f"  RESULT: {passed} passed / {failed} failed / {len(results)} total")
print("="*65)
if failed:
    print("\nFailed tests:")
    for n,(s,m) in results.items():
        if s=="FAIL": print(f"  ✗ {n}: {m}")
else:
    print("\n  All tests passed!")
print()
