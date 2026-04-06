import os
import time
import random
import logging
from flask import Flask, render_template, request, send_from_directory
from dotenv import load_dotenv
from groq import Groq
from duckduckgo_search import DDGS
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.colors import HexColor

# 1. CONFIGURATION
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "agency_internal_tool_v2")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Groq (Llama 3.3 70B)
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    logger.error("❌ GROQ_API_KEY is missing or not loaded.")
    raise ValueError("GROQ_API_KEY not found in environment variables")

client = Groq(api_key=api_key)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 2. TARGETED INTELLIGENCE SEARCH
def safe_search(query, max_retries=3):
    wait_time = 2
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(1.0, 3.0)) 
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=6, backend="html"))
                if results: return results
        except Exception as e:
            logger.warning(f"⚠️ Search Hiccup: {e}")
            time.sleep(wait_time)
            wait_time *= 2
    return []

def fetch_targeted_intel(data, report_mode):
    logger.info(f"🕵️‍♂️ MODE: {report_mode.upper()} | BRAND: {data['brand_name']}")
    ind = data['industry']
    loc = data['location']
    comps = data.get('competitors', 'Competitors').split('\n')[0]

    context_buffer = []

    # MODE A: SINGLE ANALYSIS SEARCH
    if report_mode == "analysis":
        q1 = f"{ind} market trends growth decline innovations financial costs {loc} 2026"
        q2 = f"{comps} complaints reviews problems site:reddit.com OR site:trustpilot.com"
        r1, r2 = safe_search(q1), safe_search(q2)
        
        blob1 = "\n".join([f"- {r['body'][:400]}..." for r in r1])
        blob2 = "\n".join([f"- {r['body'][:400]}..." for r in r2])
        context_buffer.append(f"=== MARKET LANDSCAPE & FINANCIALS ===\n{blob1}")
        context_buffer.append(f"=== COMPETITOR FLAWS & REVIEWS ===\n{blob2}")

    # MODE B: SINGLE STRATEGY SEARCH
    elif report_mode == "strategy":
        q1 = f"{ind} market gaps unmet needs growth hacks case studies {loc}"
        q2 = f"{ind} {comps} marketing channels subscription models positioning {loc}"
        r1, r2 = safe_search(q1), safe_search(q2)
        
        blob1 = "\n".join([f"- {r['body'][:400]}..." for r in r1])
        blob2 = "\n".join([f"- {r['body'][:400]}..." for r in r2])
        context_buffer.append(f"=== GAPS & WINNING TACTICS ===\n{blob1}")
        context_buffer.append(f"=== CHANNEL & PRICING DATA ===\n{blob2}")

    # MODE C: BOTH (FULL 3-QUERY SEARCH)
    else:
        q1 = f"{ind} market size trends innovations financial costs {loc} 2026"
        q2 = f"{comps} complaints reviews issues site:reddit.com OR site:trustpilot.com"
        q3 = f"{ind} best marketing campaigns growth hacks case study {loc}"
        r1, r2, r3 = safe_search(q1), safe_search(q2), safe_search(q3)
        
        blob1 = "\n".join([f"- {r['body'][:400]}..." for r in r1])
        blob2 = "\n".join([f"- {r['body'][:400]}..." for r in r2])
        blob3 = "\n".join([f"- {r['body'][:400]}..." for r in r3])
        context_buffer.append(f"=== MARKET & FINANCIAL DATA ===\n{blob1}")
        context_buffer.append(f"=== COMPETITOR COMPLAINTS ===\n{blob2}")
        context_buffer.append(f"=== WINNING TACTICS ===\n{blob3}")

    return "\n\n".join(context_buffer)

# 3. DYNAMIC ARCHETYPE LOGIC
def determine_archetype(data):
    p_type = data.get('product_type', 'Physical')
    ind = data.get('industry', '')
    if p_type == 'Service' or ind in ['Local Services', 'Consulting']: return "SERVICE_BIZ"
    elif p_type in ['Digital', 'Subscription'] or ind in ['EdTech', 'FinTech', 'SaaS']: return "SAAS_TECH"
    elif ind in ['FMCG', 'Food & Beverage', 'Beauty & Personal Care']: return "D2C_CONSUMABLE"
    elif ind == 'Fashion': return "FASHION_RETAIL"
    return "GENERAL_RETAIL"

def get_financial_guardrails(archetype):
    if archetype == "D2C_CONSUMABLE": return "Benchmark: 55-65% Gross Margin | CAC ₹500-1200 | Mkt Spend: 20-25% of Rev"
    if archetype == "SAAS_TECH": return "Benchmark: 80%+ Gross Margin | CAC ₹3000+ | Churn < 5% is critical"
    if archetype == "SERVICE_BIZ": return "Benchmark: 70-80% Gross Margin | CAC Low (Referral) | Net Margin 30-40%"
    if archetype == "FASHION_RETAIL": return "Benchmark: 50-60% Gross Margin | High Return Rates (20%) | Seasonal Inventory risks"
    return "Benchmark: 50% Gross Margin | Net Margin 10-15% | Standard Retail costs"

# 4. LLAMA 3 GENERATOR (8/10 Quality)
def call_groq(prompt, system_role):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4, 
            max_tokens=6500 
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"

def generate_deep_report(data, web_data, archetype, phase_type):
    guardrails = get_financial_guardrails(archetype)
    
    client_dna = f"""
    INDUSTRY: {data['industry']}
    BRAND: {data['brand_name']} ({data['location']})
    STAGE: {data['business_stage']}
    PRODUCT: {data['product_desc']} (Type: {data['product_type']})
    PRICE: {data.get('currency', 'INR')} {data.get('price_min', '0')} - {data.get('price_max', '1000')}
    USP: {data['usp']}
    
    TARGET AUDIENCE:
    - Persona: {data['customer_type']} | {data['income_band']} Income | Age: {data['age_range']}
    - Pain Points: "{data['pain_points']}"
    - Buying Triggers: "{data['buying_triggers']}"
    
    CURRENT SITUATION (Brand Status):
    - Spend: {data.get('monthly_spend', '0')} | Conversion: {data.get('conversion_rate', '0')}
    - Active Channels: {', '.join(data.get('platforms', []))}
    - Winning: "{data.get('whats_working', 'N/A')}"
    - Failing: "{data.get('whats_not_working', 'N/A')}"
    
    COMPETITIVE INTEL:
    - Competitors: {data['competitors']}
    - Why they win: "{data.get('competitor_strengths', 'N/A')}"
    
    FINANCIAL BENCHMARKS: {guardrails}
    WEB INTELLIGENCE: {web_data}
    """

    anti_echo = """
    CRITICAL RULE: DO NOT simply repeat the Client Data. Your job is to ANALYZE the implications of these facts. 
    If the client states "Sales are zero", do not repeat "Sales are zero." Instead, diagnose WHY based on Web Intel.
    BAN CORPORATE SPEAK: Do not use phrases like "Launch targeted campaigns". Be exact.
    """

    if phase_type == "analysis":
        role = f"You are an elite Market Research Analyst for the {data['industry']} sector. Output strictly formatted HTML."
        prompt = f"""
        TASK: Produce an 8/10 Quality "Market Research & Analysis Dossier".
        {anti_echo}
        CONTEXT: {client_dna}

        REQUIRED HTML STRUCTURE:
        <b>1. CURRENT MARKET SCOPE & LANDSCAPE</b><br/>
        - <b>Category Info & Trends:</b> [Detail current growth/downfall trends and innovations using Web Intel].<br/>
        - <b>Financial Costings:</b> [Discuss typical margins, CAC, and operational costs using the FINANCIAL BENCHMARKS].<br/>
        - <b>Market Reality:</b> [Is this sector growing or shrinking? Name specific industry threats].<br/><br/>
        
        <b>2. BRAND'S CURRENT STATUS</b><br/>
        - <b>Sales & Health:</b> [Diagnose their 'Winning/Failing' inputs aggressively based on their Stage].<br/>
        - <b>Social Presence & Awareness:</b> [Critique their potential on their active channels vs industry standards].<br/><br/>
        
        <b>3. COMPETITIVE ANALYSIS</b><br/>
        - <b>The Players & Details:</b> [Analyze the listed competitors and their online presence].<br/>
        - <b>Strategy & USP:</b> [Why do customers currently choose them?].<br/>
        - <b>Drawbacks & Flaws:</b> [Find their Achilles Heel. Cite specific customer complaints from Web Intel].<br/><br/>
        
        <b>4. SWOT ANALYSIS</b><br/>
        - <b>Strengths (Internal):</b> [Based on USP].<br/>
        - <b>Weaknesses (Internal):</b> [Based on 'What's Not Working' and Stage].<br/>
        - <b>Opportunities (External):</b> [Market gaps].<br/>
        - <b>Threats (External):</b> [Competitor moves & market downfall risks].<br/>
        """
        
    else: # Strategy
        role = f"You are a visionary Chief Strategy Officer (CSO) in the {data['industry']} sector. Output strictly formatted HTML."
        prompt = f"""
        TASK: Produce a customized "Strategic Execution Playbook".
        {anti_echo}
        CONTEXT: {client_dna}

        REQUIRED HTML STRUCTURE:
        <b>1. MARKET OPPORTUNITIES & GAPS</b><br/>
        - <b>Client vs Competitors:</b> [Detailed comparison. Exactly where are competitors failing that {data['brand_name']} can win?].<br/>
        - <b>Overcoming the Gap:</b> [Specific strategic pivot required to exploit this gap].<br/><br/>
        
        <b>2. COMPREHENSIVE STRATEGY</b><br/>
        - <b>Brand Strategy:</b> [What should the brand speak about? Define the tone: {data['brand_personality']}].<br/>
        - <b>Marketing Strategy:</b> [Core angles & specific ad hooks based on Pain Points & Buying Triggers].<br/>
        - <b>Channel Strategy:</b> [Detailed plan for Social Media, Offline, and E-com specific to {data['industry']}].<br/><br/>
        
        <b>3. EXECUTION PLAN</b><br/>
        - <b>Implementation Steps:</b> [Actionable Phase 1 (Fix), Phase 2 (Build), Phase 3 (Scale) based on current status].<br/>
        - <b>Executing Positioning:</b> [How to plant the USP in the mind of the target {data['income_band']} audience].<br/>
        - <b>Target Specifics:</b> [Tactics to uniquely reach the {data['age_range']} demographic].<br/>
        - <b>Compliance:</b> [Adhere to: {data.get('compliance_notes', 'Standard Norms')}].<br/>
        """

    return call_groq(prompt, role)

# 5. PDF ENGINE
def create_pdf(filename, content, title):
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles['Title']), Spacer(1, 20)]
    
    for line in content.split('\n'):
        if not line.strip(): continue
        clean_line = line.replace('**', '').replace('##', '')
        
        if clean_line[0].isdigit() and "." in clean_line[:3]:
             story.append(Spacer(1, 12))
             story.append(Paragraph(clean_line, styles['Heading1']))
        else:
             story.append(Paragraph(clean_line, styles['Normal']))
             story.append(Spacer(1, 6))
            
    doc.build(story)

# 6. ROUTES
@app.route("/")
def home(): return render_template("index.html")

@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "GET":
        from flask import redirect, url_for
        return redirect(url_for('home'))
        
    data = {k: request.form.get(k, "") for k in request.form}
    data['objectives'] = request.form.getlist("objectives")
    data['age_range'] = ", ".join(request.form.getlist("age_range"))
    data['platforms'] = request.form.getlist("platforms")
    data['availability'] = request.form.getlist("availability")
    
    if data.get('industry') == 'Other':
        data['industry'] = data.get('category_other', 'General')

    # Get user mode (analysis, strategy, or both)
    report_mode = data.get('report_mode', 'both')
    
    archetype = determine_archetype(data)
    web_context = fetch_targeted_intel(data, report_mode)
    
    pdf_file_1 = None
    pdf_file_2 = None
    report_type_display = "Full Intelligence (2 Reports)"
    
    # Generate Analysis if requested
    if report_mode in ['analysis', 'both']:
        logger.info("Generating Phase 1: Analysis...")
        content_1 = generate_deep_report(data, web_context, archetype, "analysis")
        pdf_file_1 = f"{data['brand_name']}_Analysis.pdf".replace(" ", "_")
        create_pdf(pdf_file_1, content_1, f"Market Research: {data['brand_name']}")
        if report_mode == 'analysis': report_type_display = "Deep Analysis"

    # Generate Strategy if requested
    if report_mode in ['strategy', 'both']:
        if report_mode == 'both': time.sleep(2) # Prevent API rate limit
        logger.info("Generating Phase 2: Strategy...")
        content_2 = generate_deep_report(data, web_context, archetype, "strategy")
        pdf_file_2 = f"{data['brand_name']}_Strategy.pdf".replace(" ", "_")
        create_pdf(pdf_file_2, content_2, f"Growth Strategy: {data['brand_name']}")
        if report_mode == 'strategy': report_type_display = "Growth Strategy"

    return render_template("success.html", 
                           pdf_file_1=pdf_file_1,
                           pdf_file_2=pdf_file_2,
                           report_mode=report_mode,
                           brand_name=data['brand_name'],
                           report_type=report_type_display)

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
