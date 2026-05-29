import os
import json
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime
import google.generativeai as genai
from fpdf import FPDF

# ==========================================
# CONFIGURATION
# ==========================================

TARGET_TITLES = [
    "Technical Support Engineer", "Technical Support Specialist", 
    "Product Support Specialist", "Product Support Engineer", 
    "Customer Success Manager", "Customer Onboarding Specialist", 
    "Implementation Consultant", "Product Onboarding Specialist", 
    "Customer Support Specialist", "Customer Support Engineer"
]

TARGET_LOCATION = "London"
SEEN_JOBS_FILE = "seen_jobs.json"
BASE_RESUME_FILE = "base_resume.txt"

# Environment Variables (Pulled from GitHub Secrets)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
REED_API_KEY = os.getenv("REED_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            try: return json.load(f)
            except: return []
    return []

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f)

def load_base_resume():
    if os.path.exists(BASE_RESUME_FILE):
        with open(BASE_RESUME_FILE, 'r') as f:
            return f.read()
    return ""

def tailor_resume(job_title, job_description, base_resume):
    if not GEMINI_API_KEY or not base_resume:
        print("Missing Gemini API Key or Base Resume. Skipping AI tailoring.")
        return base_resume

    print(f"Tailoring resume for {job_title} using Google Gemini...")
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Use gemini-pro model
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        You are an expert resume writer and career coach.
        I am applying for the role of '{job_title}'.
        
        Below is the job description:
        {job_description}
        
        Below is my current base resume:
        {base_resume}
        
        Please rewrite my resume to match the keywords and tone of the job description to pass ATS filters perfectly. 
        Do not make up any fake experience or lie, just highlight the most relevant skills and rephrase my existing bullet points using the keywords from the job description.
        Output ONLY the final resume text, cleanly formatted in plain text.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[!] Gemini AI Error: {e}")
        return base_resume

def generate_pdf(text, filename):
    print(f"Generating PDF: {filename}")
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        
        # Handle unicode characters gracefully
        text = text.encode('latin-1', 'replace').decode('latin-1')
        
        for line in text.split('\n'):
            pdf.multi_cell(0, 5, txt=line)
            
        pdf.output(filename)
        return filename
    except Exception as e:
        print(f"[!] Error generating PDF: {e}")
        return None

def send_email(job_title, company, url, source, pdf_path):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("Email credentials not set. Skipping email.")
        return

    msg = EmailMessage()
    msg.set_content(f"""
    New Job Found!
    
    Title: {job_title}
    Company: {company}
    Source: {source}
    Location: {TARGET_LOCATION}
    
    Apply here: {url}
    
    Attached is the AI-tailored resume specifically optimized for this job description.
    """)

    msg['Subject'] = f"New Job Alert + Resume: {job_title} at {company}"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
            msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename=os.path.basename(pdf_path))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            print(f"[*] Email sent successfully with PDF for {job_title}")
    except Exception as e:
        print(f"[!] Failed to send email: {e}")

# ==========================================
# SCRAPERS
# ==========================================

def fetch_reed_jobs():
    print("Fetching jobs from Reed.co.uk...")
    if not REED_API_KEY: return []

    new_jobs = []
    url = f"https://www.reed.co.uk/api/1.0/search?keywords=support&locationName={TARGET_LOCATION}"
    
    try:
        response = requests.get(url, auth=(REED_API_KEY, ''))
        if response.status_code == 200:
            data = response.json()
            for job in data.get('results', []):
                job_id = f"reed_{job['jobId']}"
                title = job.get('jobTitle', '')
                company = job.get('employerName', '')
                job_url = job.get('jobUrl', '')
                description = job.get('jobDescription', title) # Fallback to title if empty
                
                if any(t.lower() in title.lower() for t in TARGET_TITLES):
                    new_jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "url": job_url,
                        "description": description,
                        "source": "Reed.co.uk"
                    })
    except Exception as e:
        print(f"[!] Reed API Error: {e}")
    return new_jobs

def fetch_jsearch_jobs():
    print("Fetching jobs from JSearch...")
    if not RAPIDAPI_KEY: return []

    new_jobs = []
    url = "https://jsearch.p.rapidapi.com/search"
    querystring = {"query": f"Technical Support in {TARGET_LOCATION}", "page": "1", "num_pages": "1"}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}

    try:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            for job in data.get('data', []):
                job_id = f"jsearch_{job.get('job_id')}"
                title = job.get('job_title', '')
                company = job.get('employer_name', '')
                job_url = job.get('job_apply_link', '')
                description = job.get('job_description', title)
                
                if any(t.lower() in title.lower() for t in TARGET_TITLES):
                    new_jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "url": job_url,
                        "description": description,
                        "source": "LinkedIn/Indeed (JSearch)"
                    })
    except Exception as e:
        print(f"[!] JSearch API Error: {e}")
    return new_jobs

# ==========================================
# MAIN EXECUTION
# ==========================================

def main():
    print(f"[{datetime.now()}] Starting AI Job Scraper Run...")
    
    seen_jobs = load_json(SEEN_JOBS_FILE)
    base_resume = load_base_resume()
    all_found_jobs = fetch_reed_jobs() + fetch_jsearch_jobs()
    
    new_jobs_count = 0
    
    for job in all_found_jobs:
        if job['id'] not in seen_jobs:
            print(f"[+] NEW JOB: {job['title']} at {job['company']}")
            
            # 1. Tailor Resume with AI
            tailored_text = tailor_resume(job['title'], job['description'], base_resume)
            
            # 2. Generate PDF
            safe_company = "".join(x for x in job['company'] if x.isalnum())
            pdf_filename = f"Resume_{safe_company}.pdf"
            pdf_path = generate_pdf(tailored_text, pdf_filename)
            
            # 3. Send Email with PDF
            send_email(job['title'], job['company'], job['url'], job['source'], pdf_path)
            
            # Clean up the PDF to save space
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
            
            # Mark as seen
            seen_jobs.append(job['id'])
            new_jobs_count += 1
            
    if new_jobs_count > 0:
        save_json(SEEN_JOBS_FILE, seen_jobs)
        print(f"Saved {new_jobs_count} new jobs to database.")
    else:
        print("No new jobs found this run.")

if __name__ == "__main__":
    main()
