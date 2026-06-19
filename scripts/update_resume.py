"""
Update Hanan's resume:
- Remove the 8-bit Microprocessor project (paragraphs 30-32)
- Insert the Horus project in its place
"""

import copy
from docx import Document
from lxml import etree

SRC = r'C:\Users\Hanan\OneDrive - University of Saskatchewan\Jobs\Resumes\Hanan_Hussain_Resume_May2026.docx'
DST = r'C:\Users\Hanan\OneDrive - University of Saskatchewan\Jobs\Resumes\Hanan_Hussain_Resume_June2026.docx'

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def tag(name):
    return f'{{{W}}}{name}'


def make_run(text, bold=False, italic=False):
    """Build a <w:r> element with Times New Roman formatting."""
    r = etree.Element(tag('r'))
    rPr = etree.SubElement(r, tag('rPr'))
    rFonts = etree.SubElement(rPr, tag('rFonts'))
    rFonts.set(f'{{{W}}}ascii', 'Times New Roman')
    rFonts.set(f'{{{W}}}hAnsi', 'Times New Roman')
    rFonts.set(f'{{{W}}}cs', 'Times New Roman')
    if bold:
        etree.SubElement(rPr, tag('b'))
        etree.SubElement(rPr, tag('bCs'))
    if italic:
        etree.SubElement(rPr, tag('i'))
        etree.SubElement(rPr, tag('iCs'))
    t = etree.SubElement(r, tag('t'))
    t.text = text
    if text.startswith(' ') or text.endswith(' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return r


def make_project_name_para(name_bold, separator, year):
    """
    Build a project title paragraph matching the resume's style:
      <bold name>  |  <year>
    Mirrors para 26 (KawaKraft) structure.
    """
    p = etree.Element(tag('p'))
    pPr = etree.SubElement(p, tag('pPr'))
    spacing = etree.SubElement(pPr, tag('spacing'))
    spacing.set(f'{{{W}}}before', '30')
    rPr_pPr = etree.SubElement(pPr, tag('rPr'))
    rFonts = etree.SubElement(rPr_pPr, tag('rFonts'))
    rFonts.set(f'{{{W}}}ascii', 'Times New Roman')
    rFonts.set(f'{{{W}}}hAnsi', 'Times New Roman')
    rFonts.set(f'{{{W}}}cs', 'Times New Roman')

    p.append(make_run(name_bold, bold=True))
    p.append(make_run(separator))
    p.append(make_run(year))
    return p


def make_tech_stack_para(tech):
    """
    Build an italic tech stack paragraph.
    Mirrors para 27 (Django, Next.js...) — has w:after="30".
    """
    p = etree.Element(tag('p'))
    pPr = etree.SubElement(p, tag('pPr'))
    spacing = etree.SubElement(pPr, tag('spacing'))
    spacing.set(f'{{{W}}}after', '30')
    rPr_pPr = etree.SubElement(pPr, tag('rPr'))
    rFonts = etree.SubElement(rPr_pPr, tag('rFonts'))
    rFonts.set(f'{{{W}}}ascii', 'Times New Roman')
    rFonts.set(f'{{{W}}}hAnsi', 'Times New Roman')
    rFonts.set(f'{{{W}}}cs', 'Times New Roman')

    p.append(make_run(tech, italic=True))
    return p


def make_bullet_para(segments):
    """
    Build a bullet paragraph (ListParagraph style, numId=2).
    segments: list of (text, bold) tuples
    Mirrors para 28 structure.
    """
    p = etree.Element(tag('p'))
    pPr = etree.SubElement(p, tag('pPr'))
    # List style
    pStyle = etree.SubElement(pPr, tag('pStyle'))
    pStyle.set(f'{{{W}}}val', 'ListParagraph')
    numPr = etree.SubElement(pPr, tag('numPr'))
    ilvl = etree.SubElement(numPr, tag('ilvl'))
    ilvl.set(f'{{{W}}}val', '0')
    numId = etree.SubElement(numPr, tag('numId'))
    numId.set(f'{{{W}}}val', '2')
    spacing = etree.SubElement(pPr, tag('spacing'))
    spacing.set(f'{{{W}}}before', '20')
    spacing.set(f'{{{W}}}after', '20')
    rPr_pPr = etree.SubElement(pPr, tag('rPr'))
    rFonts = etree.SubElement(rPr_pPr, tag('rFonts'))
    rFonts.set(f'{{{W}}}ascii', 'Times New Roman')
    rFonts.set(f'{{{W}}}hAnsi', 'Times New Roman')
    rFonts.set(f'{{{W}}}cs', 'Times New Roman')

    for text, bold in segments:
        p.append(make_run(text, bold=bold))
    return p


doc = Document(SRC)
body = doc.element.body

# Verify indices are still correct before editing
assert '8-bit Microprocessor' in doc.paragraphs[30].text, f"Para 30 mismatch: {doc.paragraphs[30].text}"
assert 'Verilog, ModelSim' in doc.paragraphs[31].text, f"Para 31 mismatch: {doc.paragraphs[31].text}"
assert 'Designed a modular 8-bit' in doc.paragraphs[32].text, f"Para 32 mismatch: {doc.paragraphs[32].text}"
assert 'Certifications' in doc.paragraphs[33].text, f"Para 33 mismatch: {doc.paragraphs[33].text}"

# Get the Certifications paragraph element — we'll insert before it
cert_elem = doc.paragraphs[33]._element

# Build the 4 Horus paragraphs
horus_paras = [
    make_project_name_para(
        'Horus — Agentic AI Desktop Assistant',
        '  |  ',
        '2025 - 2026'
    ),
    make_tech_stack_para(
        'Python, FastAPI, React, WebSocket, Claude API, ChromaDB, Whisper STT, Google Maps API'
    ),
    make_bullet_para([
        ('Built an Iron Man HUD-style AI desktop assistant with voice I/O, computer use, and persistent memory; rendered ', False),
        ('5 live real-time panels', True),
        (' (stocks, sports scores, maps, Gmail, web search) on a WebSocket-driven React HUD', False),
    ]),
    make_bullet_para([
        ('Architected ', False),
        ('3 parallel sub-agents', True),
        (' (research, code, task) executing concurrently via ThreadPoolExecutor; backed by ChromaDB vector store for ', False),
        ('cross-session recall', True),
        (' and evolving user profile', False),
    ]),
    make_bullet_para([
        ('Implemented autonomous self-improvement loop: background daemon runs every ', False),
        ('6 hours', True),
        (' to discover/install skills and apply ', False),
        ('LLM-safety-reviewed code patches', True),
        (' committed automatically via git — system improves without manual intervention', False),
    ]),
]

# Remove microprocessor paragraphs (30, 31, 32) — remove in reverse to keep indices stable
for idx in [32, 31, 30]:
    p_elem = doc.paragraphs[idx]._element
    p_elem.getparent().remove(p_elem)

# Insert new Horus paragraphs before the Certifications paragraph.
# addprevious() inserts immediately before cert_elem each time, so forward
# iteration gives the correct final order: name, tech, b1, b2, b3, cert.
for p_elem in horus_paras:
    cert_elem.addprevious(p_elem)

doc.save(DST)
print(f"Saved to: {DST}")

# Verify
doc2 = Document(DST)
print(f"\nTotal paragraphs: {len(doc2.paragraphs)}")
for i, p in enumerate(doc2.paragraphs):
    if i >= 28:
        bold_texts = [r.text for r in p.runs if r.bold]
        print(f"  [{i:2}] [{p.style.name[:12]}] {repr(p.text[:65])} | bold={bold_texts[:2]}")
