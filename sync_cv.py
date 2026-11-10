#!/usr/bin/env python3
"""
sync_cv.py — Synchronizes HTML Portfolio with LaTeX CV and compiles PDF
Usage:
    python sync_cv.py           # Sync once and compile Long_Nguyen_CV.pdf
    python sync_cv.py --watch   # Watch index.html for changes and sync in real time
"""

import sys
import os
import re
import time
import shutil
import subprocess
from pathlib import Path
from html import unescape

SCRIPT_DIR = Path(__file__).parent.resolve()
HTML_FILE = SCRIPT_DIR / "index.html"
TEX_FILE = SCRIPT_DIR / "resume.tex"
PDF_TARGET = SCRIPT_DIR / "Long_Nguyen_CV.pdf"


def clean_text(text: str) -> str:
    """Strip HTML tags and unescape HTML entities."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return " ".join(text.split())


def tex_escape(text: str) -> str:
    """Escape LaTeX special characters while preserving intentional latex formatting."""
    if not text:
        return ""
    text = unescape(text)
    # Special character map
    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("€", r"\texteuro{}"),
        ("–", "--"),
        ("—", "---"),
        ("·", "$|$"),
        ("•", r"$\bullet$"),
        ("↗", ""),
    ]
    for orig, rep in replacements:
        text = text.replace(orig, rep)
    return text.strip()


def parse_html(html_path: Path) -> dict:
    """Extract resume data from index.html."""
    content = html_path.read_text(encoding="utf-8")

    data = {
        "name": "Long Nguyen",
        "location": "Tampere / Espoo, Finland",
        "email": "nguyenthelong072@gmail.com",
        "phone": "(+358) 408589351",
        "linkedin": "https://linkedin.com/in/long-nguyen-9b299a197/",
        "github": "https://github.com/nntk072",
        "summary": "",
        "experiences": [],
        "education": [],
        "projects": [],
        "skills": {},
        "achievements": [],
        "languages": "English (Professional), Vietnamese (Bilingual), Finnish (Elementary)",
    }

    # Extract Summary from About section
    about_match = re.search(r'<section id="about"[^>]*>.*?</section>', content, re.DOTALL)
    if about_match:
        paras = re.findall(r'<p>(.*?)</p>', about_match.group(0), re.DOTALL)
        if paras:
            data["summary"] = clean_text(paras[0])

    # Extract Experiences from #experience
    exp_section = re.search(r'<section id="experience"[^>]*>.*?</section>', content, re.DOTALL)
    if exp_section:
        items = re.findall(r'<div class="timeline-item">(.*?)</div>\s*</div>\s*</div>', exp_section.group(0), re.DOTALL)
        for item in items:
            role_m = re.search(r'<span class="timeline-role">(.*?)</span>', item, re.DOTALL)
            date_m = re.search(r'<span class="timeline-date">(.*?)</span>', item, re.DOTALL)
            comp_m = re.search(r'<div class="timeline-company">(.*?)</div>', item, re.DOTALL)

            role = clean_text(role_m.group(1)) if role_m else ""
            date = clean_text(date_m.group(1)) if date_m else ""
            comp_raw = clean_text(comp_m.group(1)) if comp_m else ""

            # Split company and location if separated by ·
            comp_parts = [p.strip() for p in comp_raw.split("·")]
            comp = comp_parts[0] if comp_parts else comp_raw
            loc = comp_parts[-1] if len(comp_parts) > 1 else "Finland"

            bullets = []
            for b in re.findall(r'<li>(.*?)</li>', item, re.DOTALL):
                bullets.append(clean_text(b))

            # Tags / skills
            tags = [clean_text(t) for t in re.findall(r'<span class="tag[^"]*">(.*?)</span>', item)]

            # Check for topic
            topic_m = re.search(r'<strong>Topic:</strong>\s*<em>(.*?)</em>', item)
            topic = clean_text(topic_m.group(1)) if topic_m else None

            data["experiences"].append({
                "role": role,
                "date": date,
                "company": comp,
                "location": loc,
                "bullets": bullets,
                "tags": tags,
                "topic": topic
            })

    # Extract Education from #education
    edu_section = re.search(r'<section id="education"[^>]*>.*?</section>', content, re.DOTALL)
    if edu_section:
        edu_cards = re.findall(r'<div class="edu-card">(.*?)</div>\s*</div>', edu_section.group(0), re.DOTALL)
        for card in edu_cards:
            school_m = re.search(r'<div class="edu-school">(.*?)</div>', card, re.DOTALL)
            degree_m = re.search(r'<div class="edu-degree">(.*?)</div>', card, re.DOTALL)
            meta_m = re.search(r'<div class="edu-meta">(.*?)</div>', card, re.DOTALL)
            gpa_m = re.search(r'<span class="edu-gpa">(.*?)</span>', card, re.DOTALL)

            school_raw = clean_text(school_m.group(1)) if school_m else ""
            degree = clean_text(degree_m.group(1)) if degree_m else ""
            meta_raw = meta_m.group(1) if meta_m else ""
            gpa = clean_text(gpa_m.group(1)) if gpa_m else ""

            school_parts = [p.strip() for p in school_raw.split("·")]
            school = school_parts[0] if school_parts else school_raw
            loc = school_parts[1] if len(school_parts) > 1 else "Finland"

            # Parse meta dates and details
            dates_m = re.search(r'([A-Za-z]{3}\s*\d{4}\s*[–-]\s*[A-Za-z0-9]{3,4}\s*\d{0,4})', meta_raw)
            dates = dates_m.group(1) if dates_m else ""

            spec_m = re.search(r'<strong>(?:Specialization|Major):</strong>\s*([^<]+)', meta_raw)
            spec = clean_text(spec_m.group(1)) if spec_m else ""

            thesis_m = re.search(r'<strong>(?:M\.Sc\.|B\.Sc\.) Thesis:</strong>\s*<em>([^<]+)</em>', meta_raw)
            thesis = clean_text(thesis_m.group(1)) if thesis_m else ""

            data["education"].append({
                "school": school,
                "location": loc,
                "degree": degree,
                "dates": dates,
                "gpa": gpa,
                "spec": spec,
                "thesis": thesis
            })

    # Extract Projects from #projects
    proj_section = re.search(r'<section id="projects"[^>]*>.*?</section>', content, re.DOTALL)
    if proj_section:
        proj_items = re.findall(r'<div class="timeline-item">(.*?)</div>\s*</div>\s*</div>', proj_section.group(0), re.DOTALL)
        for p in proj_items:
            role_m = re.search(r'<span class="timeline-role">(.*?)</span>', p, re.DOTALL)
            date_m = re.search(r'<span class="timeline-date">(.*?)</span>', p, re.DOTALL)
            comp_m = re.search(r'<div class="timeline-company">(.*?)</div>', p, re.DOTALL)
            desc_m = re.search(r'<div class="timeline-body">\s*<p>(.*?)</p>', p, re.DOTALL)
            link_m = re.search(r'<a href="(https://github.com/[^"]+)"', p)

            title = clean_text(role_m.group(1)) if role_m else ""
            date = clean_text(date_m.group(1)) if date_m else ""
            comp = clean_text(comp_m.group(1)) if comp_m else ""
            desc = clean_text(desc_m.group(1)) if desc_m else ""
            link = link_m.group(1) if link_m else ""
            tags = [clean_text(t) for t in re.findall(r'<span class="tag[^"]*">(.*?)</span>', p)]

            data["projects"].append({
                "title": title,
                "date": date,
                "category": comp,
                "desc": desc,
                "link": link,
                "tags": tags
            })

    # Extract Skills from #skills
    skills_section = re.search(r'<section id="skills"[^>]*>.*?</section>', content, re.DOTALL)
    if skills_section:
        cards = re.findall(r'<div class="skill-card">(.*?)</div>\s*</div>', skills_section.group(0), re.DOTALL)
        for c in cards:
            cat_m = re.search(r'<div class="skill-cat">(.*?)</div>', c, re.DOTALL)
            pills = re.findall(r'<span class="skill-pill">(.*?)</span>', c, re.DOTALL)
            if cat_m and pills:
                data["skills"][clean_text(cat_m.group(1))] = [clean_text(p) for p in pills]

    # Extract Achievements
    ach_section = re.search(r'<section id="achievements"[^>]*>.*?</section>', content, re.DOTALL)
    if ach_section:
        ach_cards = re.findall(r'<div class="ach-card">(.*?)</div>\s*</div>', ach_section.group(0), re.DOTALL)
        for c in ach_cards:
            title_m = re.search(r'<div class="ach-title">(.*?)</div>', c, re.DOTALL)
            desc_m = re.search(r'<div class="ach-desc">(.*?)</div>', c, re.DOTALL)
            if title_m:
                data["achievements"].append({
                    "title": clean_text(title_m.group(1)),
                    "desc": clean_text(desc_m.group(1)) if desc_m else ""
                })

    return data


def generate_latex(data: dict) -> str:
    """Generate LaTeX document matching the user's Rezume template."""
    tex = []
    tex.append(r"""%-------------------------
% Rezume, a latex resume template for developers
% Synchronized automatically from index.html via sync_cv.py
%-------------------------
\documentclass[a4paper,11pt]{article}

\usepackage{verbatim}
\usepackage{titlesec}
\usepackage{color}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage{tabularx}
\usepackage{latexsym}
\usepackage{marvosym}
\usepackage[empty]{fullpage}
\usepackage[hidelinks]{hyperref}
\usepackage[normalem]{ulem}
\usepackage[english]{babel}

\input glyphtounicode
\pdfgentounicode=1

%----------FONT OPTIONS-------------------
\usepackage{lmodern}
\renewcommand{\familydefault}{\sfdefault}
\urlstyle{same}
%-----------------------------------------

%----------MARGIN OPTIONS-----------------
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0in}
\renewcommand{\footrulewidth}{0in}
\setlength{\tabcolsep}{0in}
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\topmargin}{-0.5in}
\addtolength{\textwidth}{1.0in}
\addtolength{\textheight}{1.0in}
\raggedbottom{}
\raggedright{}
%------------------------------------------

%--------SECTIONING COMMANDS---------
\titleformat{\section}
  {\scshape\large}{}
    {0em}{\color{blue}}[\color{black}\titlerule\vspace{0pt}]
%-------------------------------------

%--------REDEFINITIONS----------------
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand{\ULdepth}{2pt}
%-------------------------------------

%--------CUSTOM COMMANDS--------------
\newcommand{\resumeItem}[1]{
  \item\small{#1}
}

\newcommand{\resumeItemListStart}{\begin{itemize}[rightmargin=0.11in]}
\newcommand{\resumeItemListEnd}{\end{itemize}}

\newcommand{\resumeSectionType}[3]{
  \item\begin{tabular*}{0.96\textwidth}[t]{
    p{0.18\linewidth}p{0.02\linewidth}p{0.76\linewidth}
  }
    \textbf{#1} & #2 & #3
  \end{tabular*}\vspace{-2pt}
}

\newcommand{\resumeTrioHeading}[3]{
  \item\small{
    \begin{tabular*}{0.96\textwidth}[t]{
      p{0.43\linewidth}@{\extracolsep{\fill}}p{0.39\linewidth}@{\extracolsep{\fill}}r
    }
      \textbf{#1} & \textit{#2} & #3
    \end{tabular*}
  }
}

\newcommand{\resumeQuadHeading}[4]{
  \item
  \begin{tabular*}{0.96\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & #2 \\
    \textit{\small#3} & \textit{\small #4} \\
  \end{tabular*}
}

\newcommand{\resumeHeadingListStart}{
  \begin{itemize}[leftmargin=0.15in, label={}]
}
\newcommand{\resumeHeadingListEnd}{\end{itemize}}
%-------------------------------------------

\begin{document}
""")

    # Header / Contact details
    tex.append(r"""%-----------CONTACT DETAILS------------------
\begin{tabular*}{\textwidth}{l@{\extracolsep{\fill}}r}
  \textbf{\Huge """ + tex_escape(data["name"]) + r""" \vspace{2pt}} &
  Location: """ + tex_escape(data["location"]) + r""" \\
  \href{""" + data["linkedin"] + r"""}{\uline{LinkedIn}} $|$
  \href{""" + data["github"] + r"""}{\uline{GitHub}} &
  Email: \href{mailto:""" + data["email"] + r"""}{\uline{""" + data["email"] + r"""}} $|$
  Mobile: """ + tex_escape(data["phone"]) + r""" \\
\end{tabular*}
%--------------------------------------------
""")

    # Summary
    if data["summary"]:
        tex.append(r"""%-----------SUMMARY--------------------------
\section{Summary}
\small{
""" + tex_escape(data["summary"]) + r"""
}
%--------------------------------------------
""")

    # Experience
    if data["experiences"]:
        tex.append(r"""%-----------EXPERIENCE-----------------------
\section{Experience}
""")
        for exp in data["experiences"]:
            role = tex_escape(exp["role"])
            dates = tex_escape(exp["date"])
            company = tex_escape(exp["company"])
            loc = tex_escape(exp["location"])

            tex.append(r"""\resumeHeadingListStart{}
  \resumeQuadHeading{""" + role + r"""}{""" + dates + r"""}
  {""" + company + r"""}{""" + loc + r"""}
    \resumeItemListStart{}""")

            if exp.get("topic"):
                tex.append(r"""      \resumeItem{Topic: \textit{""" + tex_escape(exp["topic"]) + r"""}}""")

            for bullet in exp["bullets"]:
                tex.append(r"""      \resumeItem{""" + tex_escape(bullet) + r"""}""")

            if exp.get("tags"):
                tex.append(r"""      \resumeItem{Skills: """ + tex_escape(", ".join(exp["tags"])) + r"""}""")

            tex.append(r"""    \resumeItemListEnd{}
\resumeHeadingListEnd{}""")

    # Education
    if data["education"]:
        tex.append(r"""%-----------EDUCATION-------------------------
\section{Education}
""")
        for edu in data["education"]:
            school = tex_escape(edu["school"])
            loc = tex_escape(edu["location"])
            degree = tex_escape(edu["degree"])
            dates = tex_escape(edu["dates"])

            tex.append(r"""\resumeHeadingListStart{}
  \resumeQuadHeading{""" + school + r"""}{""" + loc + r"""}
  {""" + degree + r"""}{""" + dates + r"""}
    \resumeItemListStart{}""")

            if edu.get("gpa"):
                tex.append(r"""      \resumeItem{GPA: """ + tex_escape(edu["gpa"]) + r"""}""")

            if edu.get("spec"):
                tex.append(r"""      \resumeItem{Specialization: """ + tex_escape(edu["spec"]) + r"""}""")

            if edu.get("thesis"):
                tex.append(r"""      \resumeItem{Thesis: \textit{""" + tex_escape(edu["thesis"]) + r"""}}""")

            tex.append(r"""    \resumeItemListEnd{}
\resumeHeadingListEnd{}""")

    # Skills
    tex.append(r"""%--------------SKILLS------------------------
\section{Skills}
  \resumeHeadingListStart{}""")
    # Preferred order of skill categories
    cat_mapping = {
        "Languages": "Programming Languages",
        "AI & Machine Learning": "Frameworks",
        "High-Perf & Systems": "Systems & HPC",
        "Software & Tools": "Dev Tools"
    }
    for orig_cat, skills in data["skills"].items():
        cat_name = cat_mapping.get(orig_cat, orig_cat)
        skill_str = tex_escape(", ".join(skills))
        tex.append(r"""    \resumeSectionType{""" + tex_escape(cat_name) + r"""}{:}{""" + skill_str + r"""}""")
    tex.append(r"""    \resumeSectionType{Pace}{:}{244+ ECTS / 2 years (Normal Pace: 120 ECTS / 2 years)}""")
    tex.append(r"""  \resumeHeadingListEnd{}
%--------------------------------------------
""")

    # Projects
    if data["projects"]:
        tex.append(r"""%-----------PROJECTS--------------------------
\section{Projects}
  \resumeHeadingListStart{}""")
        for p in data["projects"]:
            title = tex_escape(p["title"])
            tags_str = tex_escape(", ".join(p["tags"][:4])) if p.get("tags") else ""
            dates = tex_escape(p["date"])
            link = p.get("link", "")

            if link:
                heading = r"\href{" + link + r"}{\uline{" + title + r"}}"
            else:
                heading = title

            tex.append(r"""    \resumeTrioHeading{""" + heading + r"""}{""" + tags_str + r"""}{""" + dates + r"""}
      \resumeItemListStart{}""")
            if p.get("desc"):
                tex.append(r"""        \resumeItem{""" + tex_escape(p["desc"]) + r"""}""")
            tex.append(r"""      \resumeItemListEnd{}""")

        tex.append(r"""  \resumeHeadingListEnd{}
%--------------------------------------------
""")

    # Achievements & Certifications
    if data["achievements"]:
        tex.append(r"""%----------------OTHERS----------------------
\section{Certifications \& Achievements}
  \resumeItemListStart{}""")
        for a in data["achievements"]:
            title = tex_escape(a["title"])
            desc = tex_escape(a["desc"])
            tex.append(r"""    \resumeItem{\textbf{""" + title + r"""}: """ + desc + r"""}""")
        tex.append(r"""  \resumeItemListEnd{}
%--------------------------------------------
""")

    # Additional
    tex.append(r"""%----------------Additional-------------------
\section{Additional}
  \resumeHeadingListStart{}
    \resumeSectionType{Languages}{:}{""" + tex_escape(data["languages"]) + r"""}
  \resumeHeadingListEnd{}
%--------------------------------------------

\end{document}
""")

    return "\n".join(tex)


def compile_pdf() -> bool:
    """Compile resume.tex to PDF using pdflatex."""
    try:
        cmd = ["pdflatex", "--disable-installer", "-interaction=nonstopmode", "resume.tex"]
        result = subprocess.run(cmd, cwd=SCRIPT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            out_pdf = SCRIPT_DIR / "resume.pdf"
            if out_pdf.exists():
                shutil.copyfile(out_pdf, PDF_TARGET)
                print(f"[OK] Successfully compiled: {PDF_TARGET.name}")
                # Clean auxiliary files
                for ext in [".aux", ".log", ".out"]:
                    aux = SCRIPT_DIR / f"resume{ext}"
                    if aux.exists():
                        aux.unlink()
                return True
        else:
            print("[WARN] pdflatex returned non-zero. Check resume.log")
            return False
    except FileNotFoundError:
        print("[WARN] pdflatex command not found in PATH.")
        return False


def sync_once():
    """Perform one synchronization cycle."""
    print(f"[*] Reading {HTML_FILE.name}...")
    data = parse_html(HTML_FILE)
    latex_code = generate_latex(data)
    TEX_FILE.write_text(latex_code, encoding="utf-8")
    print(f"[OK] Updated {TEX_FILE.name}")
    compile_pdf()


def watch_mode():
    """Watch index.html for modifications and sync automatically."""
    print(f"[*] Watching {HTML_FILE.name} for changes... (Press Ctrl+C to stop)")
    last_mtime = HTML_FILE.stat().st_mtime
    sync_once()

    while True:
        try:
            time.sleep(1)
            current_mtime = HTML_FILE.stat().st_mtime
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                print(f"\n[*] Change detected in {HTML_FILE.name} at {time.strftime('%X')}!")
                sync_once()
        except KeyboardInterrupt:
            print("\n[*] Watch mode stopped.")
            break


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch_mode()
    else:
        sync_once()
