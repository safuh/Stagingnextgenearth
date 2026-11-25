#!/usr/bin/env python3
"""Build a source-grounded founder pitch deck and proposal from the site media manifest."""
from __future__ import annotations
import json
from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from docx import Document
from docx.shared import Inches as DInches, Pt as DPt, RGBColor as DRGB
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "pitch"
MANIFEST = ROOT / "scripts" / "data" / "nextgen_website_assets.json"
OUT.mkdir(parents=True, exist_ok=True)
PALETTE = {"forest": (22, 54, 41), "deep": (13, 34, 27), "sage": (137, 163, 119), "mint": (218, 231, 211), "cream": (247, 245, 236), "paper": (255, 254, 249), "ink": (35, 48, 41), "muted": (104, 119, 108), "rust": (191, 111, 71), "white": (255,255,255)}

def rgb(key): return RGBColor(*PALETTE.get(key, key))
def image_items():
    if not MANIFEST.exists(): return []
    data=json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [(x["alt"], ROOT / "web" / "public" / x["path"].lstrip("/")) for x in data.get("images", [])]
IMAGES=image_items()
def photo(*terms):
    for alt,path in IMAGES:
        if path.exists() and all(t.casefold() in alt.casefold() for t in terms): return path
    for alt,path in IMAGES:
        if path.exists() and any(t.casefold() in alt.casefold() for t in terms): return path
    return next((p for _,p in IMAGES if p.exists()), None)

def crop_image(src, target, ratio):
    from PIL import Image
    im=Image.open(src).convert("RGB")
    w,h=im.size; current=w/h
    if current>ratio:
        nw=int(h*ratio); left=(w-nw)//2; im=im.crop((left,0,left+nw,h))
    else:
        nh=int(w/ratio); top=(h-nh)//2; im=im.crop((0,top,w,top+nh))
    im.save(target, quality=90)
    return target

def add_photo(slide, path, x,y,w,h, temp_name):
    if not path or not path.exists(): return
    tmp=OUT / f".{temp_name}.jpg"
    crop_image(path,tmp,w/h)
    slide.shapes.add_picture(str(tmp), Inches(x), Inches(y), width=Inches(w), height=Inches(h))
    tmp.unlink(missing_ok=True)

def rect(slide,x,y,w,h,color,transparency=0,rounded=False):
    shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb=rgb(color); shape.fill.transparency=transparency
    shape.line.fill.background(); return shape

def text(slide, value, x,y,w,h, size=16, color="ink", bold=False, font="Aptos", align=None, italic=False):
    box=slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf=box.text_frame; tf.clear(); tf.word_wrap=True
    tf.margin_left=Pt(0); tf.margin_right=Pt(0); tf.margin_top=Pt(0); tf.margin_bottom=Pt(0)
    p=tf.paragraphs[0]; p.text=value
    if align is not None: p.alignment=align
    p.font.name=font; p.font.size=Pt(size); p.font.bold=bold; p.font.italic=italic; p.font.color.rgb=rgb(color)
    return box

def footer(slide, number):
    text(slide,"NEXTGEN FOR EARTH  /  DIGITAL PLATFORM PROPOSAL",.55,7.12,8,.18,8,"muted",True)
    text(slide,f"25 NOV 2026  ·  {number:02d}",10.8,7.12,2,.18,8,"muted",True,align=PP_ALIGN.RIGHT)

def new_slide(prs,bg="cream"):
    s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=rgb(bg); return s

def heading(slide,kicker,title,sub=None):
    text(slide,kicker.upper(),.65,.42,11,.24,9,"rust",True)
    text(slide,title,.65,.82,12, .65,30,"forest",True,"Georgia")
    if sub: text(slide,sub,.68,1.55,11.8,.55,13,"muted")

def bullets(slide, items, x,y,w, size=15, color="ink", gap=.47):
    for i,item in enumerate(items):
        yy=y+i*gap
        rect(slide,x,yy+.07,.11,.11,"rust",rounded=True)
        text(slide,item,x+.25,yy,w-.25,.38,size,color)

def build_deck():
    prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
    # 1 cover
    s=new_slide(prs,"deep"); add_photo(s,photo("African landscape"),7.0,0,6.333,7.5,"cover")
    rect(s,0,0,7.7,7.5,"deep",8)
    text(s,"NEXTGEN FOR EARTH",.8,.62,5,.3,11,"mint",True)
    text(s,"From a website\nto a connected\nclimate-action\nplatform.",.8,1.5,7.0,3.4,34,"white",True,"Georgia")
    text(s,"A digital platform proposal for leadership review",.85,5.35,6,.45,15,"mint")
    text(s,"Founder presentation  ·  25 November 2026",.85,6.85,6,.25,9,"white",True)
    # 2 opportunity
    s=new_slide(prs); heading(s,"01 / The opportunity","A strong mission deserves a connected operating system.","The current website already communicates a clear public story. The next step is connecting that story to day-to-day delivery.")
    add_photo(s,photo("NextGen Early Career"),7.9,2.35,4.75,3.9,"mission")
    bullets(s,["Train Africa’s next generation of climate scientists.","Translate research into community resilience and action.","Coordinate youth, educators, researchers, health workers and partners.","Make programmes, learning, research and impact easier to manage and explain."],.85,2.55,6.5,15)
    footer(s,2)
    # 3 source inventory
    s=new_slide(prs); heading(s,"02 / Website content inventory","The proposal starts with what NextGen already publishes.","A structured content capture has been prepared from the public website, including copy, links and image assets.")
    cards=[("4","programme pillars"),("3","training tracks"),("12","listed publications"),("9","named partner institutions"),("34","people directory records"),("55","captured image assets")]
    for i,(n,label) in enumerate(cards):
        x=.75+(i%3)*4.15; y=2.45+(i//3)*1.65
        rect(s,x,y,3.75,1.25,"paper",rounded=True); text(s,n,x+.25,y+.18,1.1,.55,28,"forest",True,"Georgia"); text(s,label,x+1.2,y+.3,2.35,.45,13,"muted",True)
    text(s,"Source: nextgenforearth.org, captured 25 Nov 2026. Counts are a content inventory, not independently verified impact outcomes.",.8,6.2,11.7,.45,9,"muted")
    footer(s,3)
    # 4 architecture
    s=new_slide(prs); heading(s,"03 / The platform","One organisation. Connected workflows. Clear accountability.","A modern public experience sits on top of role-aware operational workspaces.")
    blocks=[("PUBLIC WEBSITE","Mission · programmes · research · stories · opportunities"),("PROGRAMME OPERATIONS","Projects · activities · milestones · indicators · reporting"),("PEOPLE & PARTNERS","Profiles · memberships · onboarding · applications · relationships"),("LEARNING & RESEARCH","Courses · mentorship · assessments · studies · datasets · publications"),("CLIMATE & FIELD DATA","Climate intelligence · ODK field capture · quality review"),("GOVERNANCE & CMS","Drafts · approvals · audit history · access controls")]
    for i,(a,b) in enumerate(blocks):
        x=.75+(i%2)*6.2; y=2.35+(i//2)*1.25
        rect(s,x,y,5.7,.96,"paper",rounded=True); text(s,a,x+.2,y+.15,2.1,.25,10,"rust",True); text(s,b,x+2.15,y+.14,3.35,.55,11,"ink")
    footer(s,4)
    # 5 programmes
    s=new_slide(prs); heading(s,"04 / Programme portfolio","Four programme pillars. Three repeatable training tracks.")
    add_photo(s,photo("Youth Climate Stewardship"),8.1,2.1,4.5,4.3,"programme")
    bullets(s,["Research Capacity Building — weekly methods, systematic reviews, evidence synthesis, grant writing, ethics.","Healthcare Worker Training — monthly climate-health and frontline service workshops.","Youth Climate Stewardship — climate literacy, restoration, peer mentorship and community engagement.","Indigenous Knowledge Transfer — traditional ecological wisdom for adaptation and resilience."],.8,2.2,7.0,13,gap=.95)
    footer(s,5)
    # 6 research
    s=new_slide(prs); heading(s,"05 / Research to action","Keep studies, evidence and outputs connected.","The current site lists 12 publications and describes active research in climate seasonality and ageing in Busia and Kilifi.")
    add_photo(s,photo("Elderly African couple"),.8,2.25,4.25,3.9,"research")
    bullets(s,["Research study registry and investigator collaboration.","Protocol versions, review decisions and ethics references.","Dataset catalogue, provenance and controlled access.","Publication registry and OpenAlex-supported metadata enrichment.","NASA POWER climate context and governed field observations."],5.5,2.35,6.8,14,gap=.68)
    footer(s,6)
    # 7 people and partners
    s=new_slide(prs); heading(s,"06 / People and partnerships","Make the network visible — and manageable.","The source site lists leadership, staff, mentors, regional ambassadors, mentees and institutional relationships.")
    add_photo(s,photo("NextGen For Earth Team"),7.6,2.25,5.0,3.8,"team")
    bullets(s,["One directory record can represent multiple roles.","Separate public profiles from login accounts and permissions.","Onboard employees and volunteers through controlled invitations.","Track partner contacts, programme roles, evidence and reporting.","Imported partner listings remain unverified until confirmed."],.85,2.35,6.4,14,gap=.7)
    footer(s,7)
    # 8 impact
    s=new_slide(prs); heading(s,"07 / Evidence and impact","Move from published claims to evidence-backed reporting.","The figures below are currently displayed on the public website; they are not presented as independently audited metrics.")
    metrics=[("100+","youth trained"),("4,000+","children reached"),("12","publications"),("35+","youth mentored"),("40,000+","trees planted")]
    for i,(n,l) in enumerate(metrics):
        x=.65+i*2.55; rect(s,x,2.65,2.25,1.55,"paper",rounded=True); text(s,n,x+.18,2.9,1.9,.55,25,"forest",True,"Georgia",align=PP_ALIGN.CENTER); text(s,l,x+.12,3.55,2.0,.4,11,"muted",True,align=PP_ALIGN.CENTER)
    text(s,"Platform reporting should attach a reporting period, definition, source and evidence for every indicator before formal donor reporting.",.8,5.25,11.5,.75,15,"ink")
    footer(s,8)
    # 9 visual story
    s=new_slide(prs,"deep"); add_photo(s,photo("School Tree Planting"),0,0,6.2,7.5,"field")
    rect(s,5.7,0,7.633,7.5,"deep",0)
    text(s,"08 / FIELD TO BOARDROOM",6.35,.7,6,.3,10,"sage",True)
    text(s,"Capture the work.\nUnderstand the evidence.\nShare the progress.",6.35,1.5,6.2,2.2,28,"white",True,"Georgia")
    bullets(s,["Field activities and attendance.","ODK-compatible observations and sync history.","Research outputs and climate context.","Executive dashboards and funder-ready exports."],6.4,4.25,5.9,14,"white",.55)
    footer(s,9)
    # 10 governance
    s=new_slide(prs); heading(s,"09 / Governance by design","Trust is a feature, not a footnote.")
    bullets(s,["Role-based access scoped to the organisation.","Public directory profiles remain separate from user accounts.","Partner relationships are not treated as verified by import alone.","Safeguarding and PSEA workflows are explicit in programme onboarding.","CMS publication has review states and audit history.","Research protocols, datasets and climate observations retain provenance."],.9,2.25,11.4,15,gap=.62)
    footer(s,10)
    # 11 rollout
    s=new_slide(prs); heading(s,"10 / Delivery approach","A controlled path from staging to operational launch.","Indicative sequence; dates and resourcing are confirmed with leadership and infrastructure owners.")
    stages=[("01","Confirm","Content, permissions, roles, data owner"),("02","Configure","Tenant, branding, imports, integrations"),("03","Validate","Acceptance tests, reconciliations, training"),("04","Pilot","Small cohort, issue resolution, feedback"),("05","Launch","Security, backups, monitoring, handover")]
    for i,(n,t,d) in enumerate(stages):
        x=.65+i*2.55; rect(s,x,2.65,2.2,2.25,"paper",rounded=True); text(s,n,x+.2,2.9,.6,.3,11,"rust",True); text(s,t,x+.2,3.35,1.8,.45,18,"forest",True,"Georgia"); text(s,d,x+.2,3.95,1.8,.75,10,"muted")
    text(s,"Staging is not production. A real staging host, DNS/HTTPS, managed secrets, backups and monitoring are still required.",.8,5.55,11.8,.55,12,"rust",True)
    footer(s,11)
    # 12 ask
    s=new_slide(prs,"forest"); add_photo(s,photo("Pan African Conference"),8.1,0,5.233,7.5,"closing")
    rect(s,0,0,8.4,7.5,"forest",0)
    text(s,"THE DECISION",.8,.75,5,.3,10,"mint",True)
    text(s,"Let’s connect\nthe mission to\nthe work.",.8,1.55,7,2.4,32,"white",True,"Georgia")
    bullets(s,["Nominate a content and data owner.","Confirm image and profile permissions.","Validate partner relationships and impact figures.","Provide staging infrastructure and approve a pilot cohort."],.85,4.45,6.6,13,"white",.55)
    text(s,"NextGen for Earth  ·  Climate science to action",.85,6.8,6,.25,9,"mint",True)
    footer(s,12)
    path=OUT/"NextGen_For_Earth_Founder_Presentation.pptx"; prs.save(path); return path

def set_cell(cell, value, bold=False, color=(35,48,41), size=9):
    cell.text=str(value); cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for p in cell.paragraphs:
        for r in p.runs: r.font.name="Aptos"; r.font.size=DPt(size); r.font.bold=bold; r.font.color.rgb=DRGB(*color)

def build_proposal():
    doc=Document(); sec=doc.sections[0]; sec.top_margin=DInches(.7); sec.bottom_margin=DInches(.65); sec.left_margin=DInches(.8); sec.right_margin=DInches(.8)
    styles=doc.styles
    styles['Normal'].font.name='Aptos'; styles['Normal'].font.size=DPt(10); styles['Normal'].font.color.rgb=DRGB(*PALETTE['ink'])
    for name,size,color in [('Title',30,'forest'),('Heading 1',20,'forest'),('Heading 2',14,'rust'),('Heading 3',11,'forest')]:
        st=styles[name]; st.font.name='Georgia' if name in ('Title','Heading 1') else 'Aptos Display'; st.font.size=DPt(size); st.font.bold=True; st.font.color.rgb=DRGB(*PALETTE[color])
    header=sec.header.paragraphs[0]; header.text='NEXTGEN FOR EARTH  |  DIGITAL PLATFORM PROPOSAL'; header.style='Caption'
    footerp=sec.footer.paragraphs[0]; footerp.text='Confidential discussion draft  ·  25 November 2026'; footerp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    # Cover
    p=doc.add_paragraph(); p.paragraph_format.space_before=DPt(50); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run('NEXTGEN FOR EARTH'); r.bold=True; r.font.size=DPt(13); r.font.color.rgb=DRGB(*PALETTE['rust'])
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=DPt(18)
    r=p.add_run('A connected platform\nfor climate science to action'); r.font.name='Georgia'; r.font.size=DPt(31); r.bold=True; r.font.color.rgb=DRGB(*PALETTE['forest'])
    p=doc.add_paragraph('Digital transformation proposal and founder presentation brief'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size=DPt(13); p.runs[0].font.color.rgb=DRGB(*PALETTE['muted'])
    cover=photo('African landscape')
    if cover: doc.add_picture(str(cover),width=DInches(6.4))
    p=doc.add_paragraph('Prepared for NextGen for Earth leadership  ·  25 November 2026'); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size=DPt(9); p.runs[0].font.color.rgb=DRGB(*PALETTE['muted'])
    doc.add_page_break()
    doc.add_heading('1. Executive summary',level=1)
    doc.add_paragraph('NextGen for Earth has a compelling public mission: training Africa’s next generation of climate scientists and translating evidence into community resilience and action. Its website already communicates programme areas, training tracks, research outputs, institutional relationships, funding priorities, people, field activity and contact pathways. This proposal recommends connecting that public story to a secure organisation-wide operating platform.')
    doc.add_paragraph('The proposed platform combines a refreshed public website with operational workspaces for leadership, administrators, programme teams, researchers, volunteers, learners and institutional partners. It is designed to reduce fragmented records, improve programme coordination, support learning and research governance, and make organisational reporting more evidence-based.')
    doc.add_heading('2. Current website inventory',level=1)
    doc.add_paragraph('A source capture was prepared from https://nextgenforearth.org/ on 25 November 2026. The capture contains the visible page sections, links and image assets, and the existing demo catalogue includes 34 people, 9 partner listings, 4 programme records and 12 listed publications. The capture currently contains 55 images and 39 headings/sections. Counts are inventory figures, not measures of impact.')
    table=doc.add_table(rows=1,cols=2); table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.style='Light Shading Accent 1'
    set_cell(table.rows[0].cells[0],'Website content area',True,(255,255,255),9); set_cell(table.rows[0].cells[1],'Imported / represented in the demo',True,(255,255,255),9)
    rows=[('Mission, vision and approach','Mission, vision, science × community × action'),('Programmes and training','Four programme pillars and three training tracks'),('Theory of change','Inputs, activities, outputs, outcomes and impact'),('Research and publications','12 publication listings and research-area catalogue'),('Active research','Climate seasonality and ageing study in Busia and Kilifi'),('Funding propositions','Youth research fellowship, school stewardship, health-worker training, youth science network'),('Safeguarding and governance','Safeguarding/PSEA, open-access research and registration statement'),('Partners','Nine named research/institutional partner listings'),('People','Leadership, staff, mentors, ambassadors and mentees'),('Media and engagement','Gallery, video links and testimonials'),('Contact','General, communications and Ethiopia contacts; phone, address and social links')]
    for a,b in rows:
        cells=table.add_row().cells; set_cell(cells[0],a,True); set_cell(cells[1],b)
    doc.add_heading('3. Proposed solution',level=1)
    doc.add_paragraph('The platform should act as the organisation’s shared operational record while allowing the public website to present a curated, accessible story. A single organisation tenant contains the people directory, membership permissions, programmes, projects, activities, partner records, training, learning, research, climate data, CMS content and audit history.')
    doc.add_heading('3.1 Public website and content management',level=2)
    doc.add_paragraph('A photo-led, mobile-responsive public experience presents the organisation’s mission, programme catalogue, training opportunities, research and publications, impact reporting, team, partner network, gallery, videos, opportunities and contact channels. Editors work from a CMS with draft, review, approval and publication states. Public content is served from the organisation’s managed records rather than duplicated manually across the website.')
    doc.add_heading('3.2 People, volunteers and partners',level=2)
    doc.add_paragraph('A unified people directory supports multiple roles per person without conflating a public profile with a login account. Employee and volunteer onboarding uses invitations and role-based access. Partner records capture relationship type, country, contact permission, status, supporting evidence and reporting. Website-listed partners remain pending verification until the organisation confirms the relationship.')
    doc.add_heading('3.3 Programmes, learning and delivery',level=2)
    doc.add_paragraph('Programme records group projects, activities, deliverables, milestones, indicators and participants. Learning workflows support courses, modules, lessons, applications, approvals, assessments, mentorship, attendance, progress and certificates. The four programme pillars and three training tracks from the current website provide the initial catalogue structure.')
    doc.add_heading('3.4 Research and climate intelligence',level=2)
    doc.add_paragraph('Research workspaces organise studies, collaborators, protocol versions, ethics decisions, datasets, publications and research milestones. Climate intelligence integrations provide sourced contextual data, while field workflows can receive observations through ODK-compatible collection. Each imported observation should retain provider, timestamp, location, quality status and review history.')
    doc.add_heading('3.5 Governance and reporting',level=2)
    doc.add_paragraph('Role-based permissions, organisation-scoped data access, audit history, review states, safeguarding workflows and evidence-backed indicators are foundational. Dashboard metrics should always retain a definition, period, source and supporting evidence so that donor and board reporting can be reconciled.')
    doc.add_heading('4. Initial content and data migration',level=1)
    doc.add_paragraph('The staging import captures the public site’s text, section headings, outbound links and embedded/remote image assets. It enriches existing directory records with the profile images displayed on the source site. Existing demo seed data loads 34 people, 9 partner listings, 4 programme records, 34 CMS catalogue entries including 12 publications, and 4 programme records. The website importer adds 36 CMS page records from the captured site sections and archives the full text and image inventory.')
    doc.add_paragraph('Imported content is source-attributed. Publicly displayed people may be made visible in the private staging demo as existing public-site content. Institutional partner relationships are not automatically verified. Before production publication, confirm image reuse rights, individual consent, partner logos, names/roles, impact figures, research citations and contact details.')
    doc.add_heading('5. Delivery plan',level=1)
    table=doc.add_table(rows=1,cols=3); table.style='Light Shading Accent 1'; table.alignment=WD_TABLE_ALIGNMENT.CENTER
    for c,v in zip(table.rows[0].cells,['Phase','Work','Exit criteria']): set_cell(c,v,True,(255,255,255),9)
    phases=[('A · Confirm','Content owner, roles, data ownership, safeguarding and hosting decisions','Signed-off content inventory and acceptance criteria'),('B · Configure','Branding, tenant setup, imports, media, integrations and environment configuration','Staging environment and reconciled source data'),('C · Validate','Role-based workflow tests, data checks, user training and defect resolution','Founder/administrator acceptance sign-off'),('D · Pilot','Small cohort of programme, research, learning and volunteer users','Pilot report and prioritised improvements'),('E · Launch','Security review, DNS/HTTPS, backups, monitoring, handover and support','Production readiness approval')]
    for row in phases:
        cells=table.add_row().cells
        for c,v in zip(cells,row): set_cell(c,v)
    doc.add_paragraph('Timing and cost are intentionally not fabricated in this discussion draft. They should be agreed after staging infrastructure, scope priorities, data approvals and support expectations are confirmed.')
    doc.add_heading('6. Deliverables',level=1)
    for item in ['Modern public website connected to the organisation CMS.','Founder and administration workspace with role-aware access and audit history.','People directory, staff/volunteer onboarding and partner register.','Programme catalogue, project/activity tracking and reporting indicators.','Learning management workflows for courses, applications, progress and certificates.','Research registry, publications, datasets and climate-intelligence/field-data workflows.','Imported website content and image inventory with source provenance.','Staging deployment, acceptance-test evidence, user training and handover documentation.']:
        doc.add_paragraph(item,style='List Bullet')
    doc.add_heading('7. Success measures',level=1)
    for item in ['All approved public website sections have a managed CMS source and accountable editor.','Every active programme has an owner, delivery plan, milestones and defined indicators.','Staff and volunteers have appropriate role-scoped access and onboarding status.','Partner records have a named relationship owner and verified status/evidence where applicable.','Training enrolment, attendance, progress and completion can be reconciled.','Research records preserve protocol, ethics, dataset and publication provenance.','Impact reporting can be traced to source, period, method and evidence.']:
        doc.add_paragraph(item,style='List Bullet')
    doc.add_heading('8. Assumptions, risks and exclusions',level=1)
    doc.add_paragraph('Assumptions: NextGen for Earth leadership will nominate a content/data owner; the organisation can provide a staging host and DNS/HTTPS; the organisation can confirm which public media may be reused; and programme leads can validate imported records.')
    doc.add_paragraph('Risks: public pages may contain stale or incomplete details; partner logos and profile images may require additional permission; impact figures may lack a consistent reporting period or evidence; and staging infrastructure is not yet configured. Mitigations include provenance, review states, validation workshops, least-privilege access and explicit production readiness gates.')
    doc.add_paragraph('Exclusions from this proposal draft: independently auditing impact claims; establishing legal partnership status; creating user accounts for every public directory profile; replacing formal research ethics approval; providing payment processing or donor accounting; and guaranteeing live third-party data availability without confirmed provider credentials and service agreements.')
    doc.add_heading('9. Decisions requested from leadership',level=1)
    for item in ['Nominate an executive sponsor and a content/data owner.','Confirm team profile and image permissions for staging and production.','Validate partner relationships, institutional names and approved logos.','Confirm the reporting basis for published impact figures.','Provide staging infrastructure, domain/DNS and HTTPS ownership.','Approve a pilot cohort and the acceptance criteria for launch.']:
        doc.add_paragraph(item,style='List Number')
    doc.add_heading('10. Source notes',level=1)
    doc.add_paragraph('Primary source: NextGen for Earth public website, https://nextgenforearth.org/, captured 25 November 2026. Public website statements and figures in this document are attributed to that source and should be confirmed by the organisation before formal publication or external reporting. The platform feature descriptions are a proposed scope and must be validated through staging acceptance tests before being represented as production-ready.')
    path=OUT/"NextGen_For_Earth_Digital_Platform_Proposal.docx"; doc.save(path); return path

if __name__ == '__main__':
    print('Created', build_deck())
    print('Created', build_proposal())
