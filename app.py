"""
AI Job & Internship Finder - Main Flask Application
"""

import os
import json
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-me-in-production")
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "True").lower() == "true"

# ── Database init ─────────────────────────────────────────────────────────────
from database import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    update_user_profile, save_job_to_db, get_all_jobs, get_job_by_id,
    search_jobs_in_db, get_job_count, save_job_for_user, unsave_job_for_user,
    get_saved_jobs, is_job_saved, get_saved_jobs_count, apply_to_job,
    get_applications, update_application_status, get_applications_count,
    log_monitor_run, get_monitoring_history, get_recently_added_jobs,
)

with app.app_context():
    init_db()


# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if "user_id" in session:
        return get_user_by_id(session["user_id"])
    return None


# ── Context processor ─────────────────────────────────────────────────────────
@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC PAGES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    stats = {
        "total_jobs": get_job_count(is_internship=False),
        "total_internships": get_job_count(is_internship=True),
        "recent_jobs": get_recently_added_jobs(limit=6),
    }
    return render_template("home.html", stats=stats)


@app.route("/about")
def about():
    return render_template("about.html")


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # Validation
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("Valid email is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html",
                                   name=name, email=email)

        password_hash = generate_password_hash(password)
        success, msg = create_user(name, email, password_hash)
        if success:
            user = get_user_by_email(email)
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash(f"Welcome, {name}! Your account has been created.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash(msg, "error")

    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/login.html", email=email)

        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", email=email)

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = get_current_user()
    stats = {
        "total_jobs": get_job_count(is_internship=False),
        "total_internships": get_job_count(is_internship=True),
        "saved_count": get_saved_jobs_count(user_id),
        "applied_count": get_applications_count(user_id),
        "recent_jobs": get_recently_added_jobs(limit=6),
        "monitoring_history": get_monitoring_history(limit=5),
    }
    return render_template("dashboard.html", user=user, stats=stats)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    if request.method == "POST":
        skills = request.form.get("skills", "").strip()
        interests = request.form.get("interests", "").strip()
        preferred_location = request.form.get("preferred_location", "").strip()
        experience_level = request.form.get("experience_level", "fresher")
        update_user_profile(session["user_id"], skills, interests,
                            preferred_location, experience_level)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


# ─────────────────────────────────────────────────────────────────────────────
# FIND JOBS / INTERNSHIPS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/find-jobs")
def find_jobs():
    query = request.args.get("q", "")
    location = request.args.get("location", "")
    work_mode = request.args.get("work_mode", "")

    jobs = search_jobs_in_db(
        query=query,
        location=location,
        is_internship=False,
        work_mode=work_mode,
    ) if query or location or work_mode else get_all_jobs(is_internship=False, limit=30)

    user_id = session.get("user_id")
    saved_ids = set()
    if user_id:
        saved = get_saved_jobs(user_id)
        saved_ids = {j["id"] for j in saved}

    return render_template("find_jobs.html",
                           jobs=jobs, query=query, location=location,
                           work_mode=work_mode, saved_ids=saved_ids,
                           page_type="jobs")


@app.route("/find-internships")
def find_internships():
    query = request.args.get("q", "")
    location = request.args.get("location", "")
    work_mode = request.args.get("work_mode", "")

    jobs = search_jobs_in_db(
        query=query,
        location=location,
        is_internship=True,
        work_mode=work_mode,
    ) if query or location or work_mode else get_all_jobs(is_internship=True, limit=30)

    user_id = session.get("user_id")
    saved_ids = set()
    if user_id:
        saved = get_saved_jobs(user_id)
        saved_ids = {j["id"] for j in saved}

    return render_template("find_jobs.html",
                           jobs=jobs, query=query, location=location,
                           work_mode=work_mode, saved_ids=saved_ids,
                           page_type="internships")


@app.route("/job/<int:job_id>")
def job_detail(job_id):
    job = get_job_by_id(job_id)
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("find_jobs"))

    user_id = session.get("user_id")
    is_saved = is_job_saved(user_id, job_id) if user_id else False

    # Local skill matching if user is logged in
    skill_match = None
    if user_id:
        user = get_current_user()
        if user and user.get("skills") and job.get("skills_required"):
            from modules.research_module import match_skills_to_job
            skill_match = match_skills_to_job(
                user["skills"], job["skills_required"]
            )

    return render_template("job_detail.html",
                           job=job, is_saved=is_saved, skill_match=skill_match)


# ─────────────────────────────────────────────────────────────────────────────
# SAVED JOBS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/saved-jobs")
@login_required
def saved_jobs():
    jobs = get_saved_jobs(session["user_id"])
    return render_template("saved_jobs.html", jobs=jobs)


# ─────────────────────────────────────────────────────────────────────────────
# APPLICATION TRACKER
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/applications")
@login_required
def applications():
    apps = get_applications(session["user_id"])
    return render_template("applications.html", applications=apps)


@app.route("/applications/<int:job_id>/status", methods=["POST"])
@login_required
def update_status(job_id):
    status = request.form.get("status", "applied")
    valid = ["applied", "screening", "interview", "offer", "rejected", "withdrawn"]
    if status not in valid:
        status = "applied"
    update_application_status(session["user_id"], job_id, status)
    flash("Application status updated.", "success")
    return redirect(url_for("applications"))


# ─────────────────────────────────────────────────────────────────────────────
# AI RESEARCH PAGE
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/research")
@login_required
def research_page():
    user = get_current_user()
    return render_template("research.html", user=user)


# ─────────────────────────────────────────────────────────────────────────────
# REST API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

# ── AI Search (uses TinyFish Search + Fetch) ──────────────────────────────────
@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(silent=True) or {}
    skills = data.get("skills", "").strip()
    job_title = data.get("job_title", "").strip()
    location = data.get("location", "").strip()
    is_internship = data.get("is_internship", False)
    work_mode = data.get("work_mode", "")
    experience_level = data.get("experience_level", "fresher")

    if not skills and not job_title:
        return jsonify({"error": "Please provide skills or job title."}), 400

    try:
        from modules.search_module import search_jobs_multi_page, filter_job_urls
        from modules.fetch_module import extract_jobs_from_urls

        # Step 1: Search
        try:
            search_results = search_jobs_multi_page(
                skills=skills,
                job_title=job_title,
                location=location,
                is_internship=is_internship,
                experience_level=experience_level,
                max_pages=2,
            )
        except RuntimeError as e:
            # search_jobs_multi_page raises RuntimeError wrapping the API error
            err_str = str(e)
            if "API_KEY" in err_str or "not set" in err_str or "api_key" in err_str.lower():
                return jsonify({"error": err_str, "api_key_missing": True}), 503
            return jsonify({"error": err_str}), 500

        filtered = filter_job_urls(search_results)
        urls = [r["url"] for r in filtered[:8]]

        if not urls:
            return jsonify({"jobs": [], "message": "No results found. Try different keywords.",
                            "total": 0, "new_jobs": 0}), 200

        # Step 2: Fetch & extract
        jobs, fetch_error = extract_jobs_from_urls(urls, is_internship=is_internship)

        if fetch_error and not jobs:
            return jsonify({"error": f"Could not extract job details: {fetch_error}"}), 500

        # Step 3: Save to DB & apply work_mode filter
        saved_jobs_list = []
        skipped_work_mode = 0
        for job in jobs:
            if not job.get("title") or not job.get("company"):
                continue
            if work_mode and job.get("work_mode", "").lower() != work_mode.lower():
                skipped_work_mode += 1
                continue

            job_id, is_new = save_job_to_db(
                title=job.get("title", ""),
                company=job.get("company", ""),
                location=job.get("location", location),
                job_type=job.get("job_type", "internship" if is_internship else "full-time"),
                work_mode=job.get("work_mode", "on-site"),
                description=job.get("description", ""),
                skills_required=job.get("skills_required", ""),
                salary=job.get("salary", ""),
                deadline=job.get("deadline", ""),
                apply_url=job.get("apply_url", ""),
                source_url=job.get("source_url", ""),
                is_internship=is_internship,
            )
            job["id"] = job_id
            job["is_new"] = is_new
            saved_jobs_list.append(job)

        # If work_mode filter removed everything, return with clear message
        if not saved_jobs_list and skipped_work_mode > 0:
            return jsonify({
                "jobs": [],
                "total": 0,
                "new_jobs": 0,
                "message": f"Found {skipped_work_mode} job(s) but none matched the '{work_mode}' work mode filter. Try 'Any'.",
            }), 200

        new_jobs_count = sum(1 for j in saved_jobs_list if j.get("is_new"))

        # Log monitor run
        log_monitor_run(
            search_query=f"{skills} {job_title}".strip(),
            location=location,
            jobs_found=len(saved_jobs_list),
            new_jobs=new_jobs_count,
            status="completed",
        )

        return jsonify({
            "jobs": saved_jobs_list,
            "total": len(saved_jobs_list),
            "new_jobs": new_jobs_count,
            "fetch_warnings": fetch_error,  # partial errors (some URLs failed)
        })

    except ValueError as e:
        # API key not configured
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Agent search (TinyFish Agent browser automation) ──────────────────────────
@app.route("/api/agent-search", methods=["POST"])
@login_required
def api_agent_search():
    data = request.get_json(silent=True) or {}
    skills = data.get("skills", "").strip()
    job_title = data.get("job_title", "").strip()
    location = data.get("location", "").strip()
    is_internship = data.get("is_internship", False)
    platform = data.get("platform", "internshala")
    experience_level = data.get("experience_level", "fresher")

    if not skills and not job_title:
        return jsonify({"error": "Please provide skills or job title."}), 400

    try:
        from modules.agent_module import run_job_search_agent
        jobs, error = run_job_search_agent(
            skills=skills,
            job_title=job_title,
            location=location,
            is_internship=is_internship,
            experience_level=experience_level,
            platform=platform,
        )
        if error:
            return jsonify({"error": error}), 500

        saved = []
        for job in jobs:
            if job.get("title") and job.get("company"):
                job_id, is_new = save_job_to_db(
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    location=job.get("location", location),
                    job_type=job.get("job_type", "internship" if is_internship else "full-time"),
                    work_mode=job.get("work_mode", "on-site"),
                    description=job.get("description", ""),
                    skills_required=job.get("skills_required", ""),
                    salary=job.get("salary", ""),
                    deadline=job.get("deadline", ""),
                    apply_url=job.get("apply_url", ""),
                    source_url=job.get("source_url", ""),
                    is_internship=is_internship,
                )
                job["id"] = job_id
                saved.append(job)

        return jsonify({"jobs": saved, "total": len(saved)})

    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Save / Unsave a job ───────────────────────────────────────────────────────
@app.route("/api/save-job/<int:job_id>", methods=["POST"])
@login_required
def api_save_job(job_id):
    success, msg = save_job_for_user(session["user_id"], job_id)
    return jsonify({"success": success, "message": msg})


@app.route("/api/unsave-job/<int:job_id>", methods=["POST"])
@login_required
def api_unsave_job(job_id):
    unsave_job_for_user(session["user_id"], job_id)
    return jsonify({"success": True, "message": "Job removed from saved."})


# ── Track application ─────────────────────────────────────────────────────────
@app.route("/api/track-application/<int:job_id>", methods=["POST"])
@login_required
def api_track_application(job_id):
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "")
    success, msg = apply_to_job(session["user_id"], job_id, notes=notes)
    return jsonify({"success": success, "message": msg})


# ── AI Research endpoints ─────────────────────────────────────────────────────
@app.route("/api/research/analyze", methods=["POST"])
@login_required
def api_research_analyze():
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    user = get_current_user()

    job = get_job_by_id(job_id) if job_id else None
    if not job:
        return jsonify({"error": "Job not found."}), 404

    try:
        from modules.research_module import analyze_job_description
        result, error = analyze_job_description(
            job_title=job["title"],
            company=job["company"],
            description=job["description"],
            user_skills=user.get("skills", "") if user else "",
        )
        if error:
            return jsonify({"error": error}), 500
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/recommendations", methods=["GET"])
@login_required
def api_recommendations():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        from modules.research_module import get_job_recommendations
        result, error = get_job_recommendations(
            user_skills=user.get("skills", ""),
            user_interests=user.get("interests", ""),
            experience_level=user.get("experience_level", "fresher"),
            preferred_location=user.get("preferred_location", ""),
        )
        if error:
            return jsonify({"error": error}), 500
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/compare", methods=["POST"])
@login_required
def api_compare_jobs():
    data = request.get_json(silent=True) or {}
    job_ids = data.get("job_ids", [])

    if not job_ids or len(job_ids) < 2:
        return jsonify({"error": "Please provide at least 2 job IDs to compare."}), 400

    jobs = [get_job_by_id(jid) for jid in job_ids[:5]]
    jobs = [j for j in jobs if j]

    try:
        from modules.research_module import compare_job_opportunities
        result, error = compare_job_opportunities(jobs)
        if error:
            return jsonify({"error": error}), 500
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/company", methods=["POST"])
@login_required
def api_research_company():
    data = request.get_json(silent=True) or {}
    company_name = data.get("company", "").strip()
    job_title = data.get("job_title", "").strip()

    if not company_name:
        return jsonify({"error": "Company name is required."}), 400

    try:
        from modules.research_module import research_company
        result, error = research_company(company_name, job_title)
        if error:
            return jsonify({"error": error}), 500
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Monitor endpoints ─────────────────────────────────────────────────────────
@app.route("/api/monitor/run", methods=["POST"])
@login_required
def api_run_monitor():
    data = request.get_json(silent=True) or {}
    skills = data.get("skills", "")
    location = data.get("location", "")
    is_internship = data.get("is_internship", False)

    try:
        from modules.monitor_module import run_local_monitor
        summary = run_local_monitor(
            skills=skills,
            location=location,
            is_internship=is_internship,
        )
        return jsonify({"success": True, "summary": summary})
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/monitor/history")
@login_required
def api_monitor_history():
    history = get_monitoring_history(limit=20)
    return jsonify({"history": history})


@app.route("/api/monitor/create", methods=["POST"])
@login_required
def api_create_monitor():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    location = data.get("location", "")
    is_internship = data.get("is_internship", False)
    schedule = data.get("schedule_cron", "0 9 * * *")

    if not query:
        return jsonify({"error": "Search query is required."}), 400

    try:
        from modules.monitor_module import create_job_monitor
        monitor_id, error = create_job_monitor(
            query=query, location=location,
            is_internship=is_internship, schedule_cron=schedule,
        )
        if error:
            return jsonify({"error": error}), 500
        return jsonify({"success": True, "monitor_id": monitor_id})
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/monitor/list")
@login_required
def api_list_monitors():
    try:
        from modules.monitor_module import list_job_monitors
        monitors, error = list_job_monitors()
        if error:
            return jsonify({"error": error, "monitors": []}), 200
        return jsonify({"monitors": monitors})
    except ValueError as e:
        return jsonify({"error": str(e), "api_key_missing": True}), 503
    except Exception as e:
        return jsonify({"monitors": [], "error": str(e)}), 200


# ── Skill match ───────────────────────────────────────────────────────────────
@app.route("/api/skill-match/<int:job_id>")
@login_required
def api_skill_match(job_id):
    job = get_job_by_id(job_id)
    user = get_current_user()
    if not job or not user:
        return jsonify({"error": "Not found"}), 404
    from modules.research_module import match_skills_to_job
    result = match_skills_to_job(
        user.get("skills", ""), job.get("skills_required", "")
    )
    return jsonify(result)


# ── Stats endpoint ────────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    user_id = session.get("user_id")
    stats = {
        "total_jobs": get_job_count(is_internship=False),
        "total_internships": get_job_count(is_internship=True),
    }
    if user_id:
        stats["saved_count"] = get_saved_jobs_count(user_id)
        stats["applied_count"] = get_applications_count(user_id)
    return jsonify(stats)


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AI Job & Internship Finder")
    print("  http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=5000)
